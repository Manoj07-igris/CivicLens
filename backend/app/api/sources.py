"""Official Source Library API Endpoints (Module 3).

Provides CRUD operations, PDF upload, indexing, and page retrieval for curated government sources.
All write operations are gated by settings.ALLOW_SOURCE_MANAGEMENT.
"""

import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.auth.dependencies import CurrentUser, get_current_user, require_admin
from app.core.config import Settings, get_settings
from app.core.errors import DocumentProcessingError, SourceLibraryError, SourceNotFoundError
from app.models.documents import IndexBuildResponse, PageDetailResponse
from app.models.verification import (
    OfficialSourceCreateRequest,
    OfficialSourceListResponse,
    OfficialSourceMetadata,
    OfficialSourceUpdateRequest,
)
from app.services.source_library import SourceLibraryService, get_source_library_service

logger = logging.getLogger("civiclens.api.sources")

router = APIRouter(prefix="/sources", tags=["Official Sources"])


@router.get("", response_model=OfficialSourceListResponse)
def list_official_sources(
    current_user: CurrentUser = Depends(get_current_user),
    service: SourceLibraryService = Depends(get_source_library_service),
) -> OfficialSourceListResponse:
  """List all official sources in the library along with indexing status."""
  sources = service.list_sources()
  version = service.store.compute_library_version()
  return OfficialSourceListResponse(
      sources=sources,
      total_count=len(sources),
      library_version=version,
  )


@router.get("/{source_id}", response_model=OfficialSourceMetadata)
def get_official_source(
    source_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: SourceLibraryService = Depends(get_source_library_service),
) -> OfficialSourceMetadata:
  """Retrieve metadata for a specific official source."""
  return service.get_source(source_id)


@router.post("", response_model=OfficialSourceMetadata, status_code=status.HTTP_202_ACCEPTED)
async def upload_official_source(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    issuing_authority: str = Form(...),
    source_url: Optional[str] = Form(None),
    publication_date: Optional[str] = Form(None),
    effective_date: Optional[str] = Form(None),
    series_id: Optional[str] = Form(None),
    source_status: str = Form("unknown", alias="status"),
    superseded_by: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    admin_user: CurrentUser = Depends(require_admin),
    service: SourceLibraryService = Depends(get_source_library_service),
) -> OfficialSourceMetadata:
  """Upload a new official government notification PDF and stage for background extraction and indexing."""
  if not file.filename:
    raise DocumentProcessingError("Filename is missing from upload.")

  file_bytes = await file.read()
  if not file_bytes:
    raise DocumentProcessingError("Uploaded file is empty.")

  # Construct and validate request model
  try:
    req = OfficialSourceCreateRequest(
        title=title,
        issuing_authority=issuing_authority,
        source_url=source_url or None,
        publication_date=publication_date or None,
        effective_date=effective_date or None,
        series_id=series_id or None,
        status=source_status,  # type: ignore
        superseded_by=superseded_by or None,
        notes=notes or None,
    )
  except Exception as exc:
    raise SourceLibraryError(f"Validation error in source metadata: {exc}", code="VALIDATION_ERROR", status_code=422)

  source_meta, is_dup = service.add_source(
      filename=file.filename,
      file_bytes=file_bytes,
      req=req,
  )

  if not is_dup:
    # Dispatch processing and FAISS vector indexing in background
    background_tasks.add_task(service.process_and_index_source, source_meta.source_id)

  return source_meta


@router.patch("/{source_id}", response_model=OfficialSourceMetadata)
def update_official_source_metadata(
    source_id: str,
    body: OfficialSourceUpdateRequest,
    admin_user: CurrentUser = Depends(require_admin),
    service: SourceLibraryService = Depends(get_source_library_service),
) -> OfficialSourceMetadata:
  """Update metadata fields of an existing official source."""
  return service.update_source_metadata(source_id, body)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_official_source(
    source_id: str,
    admin_user: CurrentUser = Depends(require_admin),
    service: SourceLibraryService = Depends(get_source_library_service),
) -> Response:
  """Delete an official source, its disk files, index, and clear superseded references."""
  service.delete_source(source_id)
  return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{source_id}/index", response_model=IndexBuildResponse)
async def rebuild_official_source_index(
    source_id: str,
    admin_user: CurrentUser = Depends(require_admin),
    service: SourceLibraryService = Depends(get_source_library_service),
) -> IndexBuildResponse:
  """Force rebuild of the FAISS vector index for an official source."""
  return await service.rebuild_index(source_id)


@router.get("/{source_id}/file")
def get_official_source_file(
    source_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: SourceLibraryService = Depends(get_source_library_service),
) -> FileResponse:
  """Serve the original PDF file with safe headers."""
  source = service.get_source(source_id)
  file_path = service.get_file_path(source_id)
  if not file_path or not file_path.exists():
    raise SourceNotFoundError(f"PDF file for source '{source_id}' is not on disk.")

  headers = {
      "Content-Disposition": f'inline; filename="{source.filename}"',
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "private, max-age=3600",
  }
  return FileResponse(
      path=str(file_path),
      media_type="application/pdf",
      headers=headers,
  )


@router.get("/{source_id}/pages/{page_number}", response_model=PageDetailResponse)
def get_official_source_page(
    source_id: str,
    page_number: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: SourceLibraryService = Depends(get_source_library_service),
) -> PageDetailResponse:
  """Retrieve detailed text and OCR status of a specific page of an official source."""
  source = service.get_source(source_id)
  page_rec = service.get_page(source_id, page_number)
  if not page_rec:
    raise SourceNotFoundError(f"Page {page_number} not found in source '{source_id}'.")

  return PageDetailResponse(
      document_id=source_id,
      page_number=page_number,
      char_count=page_rec.get("char_count", 0),
      ocr_used=page_rec.get("ocr_used", False),
      text_quality=page_rec.get("text_quality", "normal"),
      text=page_rec.get("text", ""),
      chunk_count=page_rec.get("chunk_count", 0),
  )
