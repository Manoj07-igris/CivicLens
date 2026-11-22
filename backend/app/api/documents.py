"""FastAPI endpoints for Document Intelligence (Module 1 - Policy Intelligence).

Provides secure endpoints for PDF upload, processing status lifecycle,
paginated page viewing, raw file retrieval, AI summarization, and management.
"""

import collections
import logging
import time
from typing import Any, Dict, List, Optional
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import DocumentNotFoundError, DocumentProcessingError
from app.core.pii_guard import ensure_no_pii
from app.models.documents import (
    AskRequest,
    AskResponse,
    DocumentCapabilitiesResponse,
    DocumentDetailResponse,
    DocumentMetadata,
    DocumentPagesResponse,
    DocumentRetrieveRequest,
    DocumentRetrieveResponse,
    DocumentSummaryRequest,
    DocumentSummaryResponse,
    DocumentUploadResponse,
    IndexBuildRequest,
    IndexBuildResponse,
    PageDetailResponse,
)
from app.services.document_service import (
    DocumentService,
    check_ocr_capabilities,
    get_document_service,
)
from app.services.document_store import DocumentStore, get_document_store
from app.services.rag_service import RAGService, get_index_cache, get_rag_service

logger = logging.getLogger("civiclens.documents")

router = APIRouter(prefix="/documents", tags=["Document Intelligence"])

# In-memory rolling rate limiter for RAG Q&A (max 10 calls per minute)
RAG_CALL_TIMESTAMPS: collections.deque = collections.deque()
RAG_RATE_LIMIT_WINDOW = 60.0
MAX_RAG_CALLS_PER_MINUTE = 10


def check_rag_rate_limit() -> None:
  """Enforce rolling rate limit on /ask endpoint."""
  now = time.time()
  while RAG_CALL_TIMESTAMPS and (now - RAG_CALL_TIMESTAMPS[0] > RAG_RATE_LIMIT_WINDOW):
    RAG_CALL_TIMESTAMPS.popleft()
  if len(RAG_CALL_TIMESTAMPS) >= MAX_RAG_CALLS_PER_MINUTE:
    retry_after = int(RAG_RATE_LIMIT_WINDOW - (now - RAG_CALL_TIMESTAMPS[0])) + 1
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Document question rate limit exceeded ({MAX_RAG_CALLS_PER_MINUTE} calls/min). Please try again in {retry_after}s.",
    )
  RAG_CALL_TIMESTAMPS.append(now)


def reset_rag_rate_limit() -> None:
  """Helper for tests to clear the rate limit deque."""
  RAG_CALL_TIMESTAMPS.clear()



@router.get(
    "/capabilities",
    response_model=DocumentCapabilitiesResponse,
    summary="Get system PDF processing and OCR capabilities",
)
async def get_capabilities(
    settings: Settings = Depends(get_settings),
) -> DocumentCapabilitiesResponse:
  """Inspect system configuration, Tesseract OCR presence, and upload constraints."""
  return check_ocr_capabilities(settings)


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    summary="Upload an official government PDF for processing",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    request: Request,
    response: Response,
    file: UploadFile = File(..., description="Official government PDF document"),
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentUploadResponse:
  """Upload a public civic PDF.

  Validates magic bytes, enforces streaming size limits, detects duplicates,
  and initiates background text extraction, OCR fallback, and chunking.
  """
  client_ip = request.client.host if request.client else "unknown"
  contents = await file.read()

  # Stage document and check for duplicates scoped to authenticated citizen
  upload_res = service.validate_and_stage_upload(
      filename=file.filename or "document.pdf",
      file_bytes=contents,
      client_key=client_ip,
      owner_id=current_user.id,
  )

  if upload_res.is_duplicate:
    response.status_code = status.HTTP_200_OK
  else:
    response.status_code = status.HTTP_202_ACCEPTED
    # Dispatch extraction pipeline to background task
    background_tasks.add_task(service.process_document, upload_res.document_id)

  return upload_res


@router.get(
    "",
    response_model=List[DocumentMetadata],
    summary="List all uploaded documents",
)
async def list_documents(
    current_user: CurrentUser = Depends(get_current_user),
    store: DocumentStore = Depends(get_document_store),
) -> List[DocumentMetadata]:
  """Retrieve metadata for all uploaded documents for current citizen, newest first."""
  docs = store.list_documents(owner_id=current_user.id)
  return [DocumentMetadata(**d) for d in docs]


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get full document metadata and processing status",
)
async def get_document(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentDetailResponse:
  """Retrieve detailed document status, per-page extraction summary, and chunk counts."""
  return service.get_document_detail(document_id, owner_id=current_user.id)


@router.get(
    "/{document_id}/pages",
    response_model=DocumentPagesResponse,
    summary="Get paginated list of extracted pages",
)
async def get_document_pages(
    document_id: str,
    page: int = Query(default=1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: CurrentUser = Depends(get_current_user),
    store: DocumentStore = Depends(get_document_store),
) -> DocumentPagesResponse:
  """Retrieve page records with full text and extraction method details."""
  meta = store.get_metadata(document_id, owner_id=current_user.id)
  if not meta:
    raise DocumentNotFoundError(f"Document '{document_id}' not found.")

  pages_slice = store.get_pages(document_id, page=page, page_size=page_size)
  page_items = [
      PageDetailResponse(
          document_id=document_id,
          page_number=p["page_number"],
          text=p["text"],
          char_count=p.get("char_count", len(p["text"])),
          extraction_method=p.get("extraction_method", "pymupdf"),
          quality=p.get("quality", "normal"),
          confidence=p.get("confidence"),
      )
      for p in pages_slice.get("pages", [])
  ]

  return DocumentPagesResponse(
      document_id=document_id,
      pages=page_items,
      total_pages=pages_slice.get("total_pages", len(page_items)),
      page=page,
      page_size=page_size,
  )


@router.get(
    "/{document_id}/pages/{page_number}",
    response_model=PageDetailResponse,
    summary="Get extracted text for a specific page",
)
async def get_document_single_page(
    document_id: str,
    page_number: int,
    current_user: CurrentUser = Depends(get_current_user),
    store: DocumentStore = Depends(get_document_store),
) -> PageDetailResponse:
  """Retrieve the extracted text and quality parameters for an individual page."""
  meta = store.get_metadata(document_id, owner_id=current_user.id)
  if not meta:
    raise DocumentNotFoundError(f"Document '{document_id}' not found.")

  page_data = store.get_page(document_id, page_number)
  if not page_data:
    raise DocumentNotFoundError(f"Page {page_number} not found for document '{document_id}'.")

  return PageDetailResponse(
      document_id=document_id,
      page_number=page_data["page_number"],
      text=page_data["text"],
      char_count=page_data.get("char_count", len(page_data["text"])),
      extraction_method=page_data.get("extraction_method", "pymupdf"),
      quality=page_data.get("quality", "normal"),
      confidence=page_data.get("confidence"),
  )


@router.get(
    "/{document_id}/file",
    summary="Download or view the original PDF document",
)
async def get_document_file(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    store: DocumentStore = Depends(get_document_store),
) -> FileResponse:
  """Serve the raw original PDF file with safe headers."""
  meta = store.get_metadata(document_id, owner_id=current_user.id)
  if not meta:
    raise DocumentNotFoundError(f"Document '{document_id}' not found.")

  pdf_path = store.get_file_path(document_id)
  if not pdf_path or not pdf_path.exists():
    raise DocumentNotFoundError(f"Original file for document '{document_id}' is missing from storage.")

  filename = meta.get("filename", "document.pdf")
  return FileResponse(
      path=str(pdf_path),
      media_type="application/pdf",
      headers={
          "X-Content-Type-Options": "nosniff",
          "Content-Disposition": f'inline; filename="{filename}"',
      },
  )


@router.post(
    "/{document_id}/summary",
    response_model=DocumentSummaryResponse,
    summary="Generate an AI civic summary of the document",
)
async def generate_document_summary(
    document_id: str,
    body: DocumentSummaryRequest = DocumentSummaryRequest(),
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentSummaryResponse:
  """Generate a grounded, structured AI summary in English or Tamil.

  Results are cached per document and language to avoid wasteful calls.
  """
  return await service.generate_summary(document_id, requested_language=body.language, owner_id=current_user.id)


@router.post(
    "/{document_id}/index",
    response_model=IndexBuildResponse,
    summary="Build or update vector search index for a document",
)
async def build_index(
    document_id: str,
    body: IndexBuildRequest = IndexBuildRequest(),
    current_user: CurrentUser = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
    store: DocumentStore = Depends(get_document_store),
) -> IndexBuildResponse:
  """Build or refresh the FAISS IndexFlatIP vector index for the document."""
  meta = store.get_metadata(document_id, owner_id=current_user.id)
  if not meta:
    raise DocumentNotFoundError(f"Document '{document_id}' not found.")
  return await rag_service.build_index(document_id, force=body.force)


@router.post(
    "/{document_id}/retrieve",
    response_model=DocumentRetrieveResponse,
    summary="Retrieve candidate passages without generating an answer",
)
async def retrieve_passages(
    document_id: str,
    body: DocumentRetrieveRequest,
    current_user: CurrentUser = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
    store: DocumentStore = Depends(get_document_store),
) -> DocumentRetrieveResponse:
  """Run hybrid vector + lexical retrieval on document passages without LLM invocation."""
  meta = store.get_metadata(document_id, owner_id=current_user.id)
  if not meta:
    raise DocumentNotFoundError(f"Document '{document_id}' not found.")
  passages, evidence_level = await rag_service.retrieve(
      document_id, query=body.query, top_k=body.top_k
  )
  return DocumentRetrieveResponse(
      document_id=document_id,
      query=body.query,
      evidence_level=evidence_level,
      passages=passages,
      total_retrieved=len(passages),
  )


@router.post(
    "/{document_id}/ask",
    response_model=AskResponse,
    summary="Ask a grounded civic question about an uploaded document",
)
async def ask_document(
    document_id: str,
    body: AskRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
    store: DocumentStore = Depends(get_document_store),
) -> AskResponse:
  """Ask an evidence-based question about an official document.

  Uses hybrid retrieval, skips LLM if evidence is missing, and returns strictly verified citations.
  """
  ensure_no_pii(body.question, field_name="question")
  meta = store.get_metadata(document_id, owner_id=current_user.id)
  if not meta:
    raise DocumentNotFoundError(f"Document '{document_id}' not found.")

  check_rag_rate_limit()

  response = await rag_service.answer_question(
      document_id=document_id,
      question=body.question,
      language=body.language,
      history=body.history,
  )

  # Safe privacy logging: Never log question, passage, or answer text
  logger.info(
      "RAG Q&A completed: doc_id=%s, found=%s, evidence_level=%s, retrieved=%d, citations=%d, latency=%.1fms, tokens=%s",
      document_id,
      response.found,
      response.evidence_level,
      response.retrieved_count,
      len(response.citations),
      response.latency_ms,
      response.token_usage.total_tokens if response.token_usage else "N/A",
  )

  return response


@router.delete(
    "/{document_id}",
    summary="Delete a document and all extracted artifacts",
)
async def delete_document(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    store: DocumentStore = Depends(get_document_store),
) -> Dict[str, Any]:
  """Permanently delete a document, extracted pages, and its vector index."""
  meta = store.get_metadata(document_id, owner_id=current_user.id)
  if not meta:
    raise DocumentNotFoundError(f"Document '{document_id}' not found.")

  get_index_cache().invalidate(document_id)
  success = store.delete_document(document_id, owner_id=current_user.id)
  if not success:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Failed to delete document '{document_id}'.",
    )

  return {"deleted": True, "document_id": document_id}
