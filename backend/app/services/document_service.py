"""Document intelligence service for CivicLens (Module 1 - Policy Intelligence).

Handles PDF validation, streaming size limits, PyMuPDF extraction,
page-isolated chunking, Tesseract OCR fallback, text quality checks,
and Gemini AI document summarization with prompt injection protection.
"""

import collections
import datetime
import hashlib
import io
import logging
import re
import time
import unicodedata
from typing import BinaryIO, Dict, List, Optional, Tuple

import pymupdf as fitz
from PIL import Image

try:
  import pytesseract
except ImportError:
  pytesseract = None  # type: ignore

from app.core.config import Settings, get_settings
from app.core.errors import (
    DocumentError,
    DocumentNotFoundError,
    DocumentProcessingError,
    DocumentRateLimitError,
)
from app.core.prompts import get_document_summary_prompt, wrap_untrusted_content
from app.models.documents import (
    DocumentCapabilitiesResponse,
    DocumentChunk,
    DocumentDetailResponse,
    DocumentMetadata,
    DocumentSummaryResponse,
    DocumentUploadResponse,
    PageDetailResponse,
    PageSummary,
)
from app.services.document_store import DocumentStore, get_document_store, sanitize_display_filename
from app.services.gemini_service import GeminiService, get_gemini_service
from app.services.language_service import detect_language, is_tamil_char
from app.services.activity_service import get_activity_service

logger = logging.getLogger("civiclens.documents")


# In-memory sliding-window upload rate limiter (10 uploads per minute per client key)
class UploadRateLimiter:
  def __init__(self, max_requests: int = 10, window_seconds: int = 60):
    self.max_requests = max_requests
    self.window_seconds = window_seconds
    self._clients: Dict[str, collections.deque] = collections.defaultdict(collections.deque)

  def check(self, client_key: str) -> None:
    now = time.time()
    queue = self._clients[client_key]
    # Evict timestamps older than window
    while queue and (now - queue[0] > self.window_seconds):
      queue.popleft()
    if len(queue) >= self.max_requests:
      raise DocumentRateLimitError(
          f"Upload limit reached ({self.max_requests} uploads per minute). Please wait a moment."
      )
    queue.append(now)

  def reset(self) -> None:
    self._clients.clear()


_rate_limiter = UploadRateLimiter()


def get_rate_limiter() -> UploadRateLimiter:
  return _rate_limiter


def reset_upload_rate_limit() -> None:
  """Test helper to clear the upload sliding window."""
  _rate_limiter.reset()


import shutil

def check_ocr_capabilities(settings: Optional[Settings] = None) -> DocumentCapabilitiesResponse:
  """Inspect system environment to verify Tesseract OCR binary availability and language support."""
  cfg = settings or get_settings()

  target_cmd = cfg.TESSERACT_CMD.strip() if cfg.TESSERACT_CMD else "tesseract"
  if cfg.TESSERACT_CMD and pytesseract is not None:
    pytesseract.pytesseract.tesseract_cmd = cfg.TESSERACT_CMD

  ocr_available = False
  tesseract_version: Optional[str] = None
  available_languages: List[str] = []

  # Fast check: only attempt binary invocation if binary exists in PATH
  binary_found = bool(shutil.which(target_cmd))

  if cfg.OCR_ENABLED and pytesseract is not None and binary_found:
    try:
      ver = pytesseract.get_tesseract_version()
      ocr_available = True
      tesseract_version = str(ver)
      try:
        langs = pytesseract.get_languages()
        available_languages = [str(l) for l in langs if str(l).strip()]
      except Exception:
        available_languages = [l.strip() for l in cfg.OCR_LANGUAGES.split("+") if l.strip()]
    except Exception as exc:
      logger.info("Tesseract OCR not operational on this host: %s", exc)
      ocr_available = False

  return DocumentCapabilitiesResponse(
      ocr_available=ocr_available,
      tesseract_version=tesseract_version,
      ocr_languages=available_languages or [l.strip() for l in cfg.OCR_LANGUAGES.split("+") if l.strip()],
      max_upload_mb=cfg.MAX_UPLOAD_MB,
      max_pdf_pages=cfg.MAX_PDF_PAGES,
      ocr_max_pages=cfg.OCR_MAX_PAGES,
      embedding_model=cfg.EMBEDDING_MODEL_NAME,
      embedding_available=True,
  )


def validate_pdf_content(
    file_bytes: bytes,
    settings: Optional[Settings] = None,
) -> Tuple[str, int]:
  """Validate PDF structure, magic bytes, page limits, and encryption.

  Returns (sha256_hash, page_count).
  Raises DocumentProcessingError if the file is invalid, encrypted, or exceeds page limits.
  """
  cfg = settings or get_settings()

  if not file_bytes:
    raise DocumentProcessingError("The uploaded file is empty.")

  # Verify PDF magic bytes in the leading 1024 bytes
  header = file_bytes[:1024]
  if b"%PDF-" not in header:
    raise DocumentProcessingError(
        "Invalid file format: File header does not match a valid PDF document (%PDF- magic bytes missing)."
    )

  sha256_hash = hashlib.sha256(file_bytes).hexdigest()

  try:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
  except Exception as exc:
    raise DocumentProcessingError(f"Failed to parse PDF document structure: {exc}") from exc

  try:
    if doc.is_encrypted:
      raise DocumentProcessingError(
          "Encrypted or password-protected PDF files cannot be processed. Please provide an unencrypted document."
      )

    page_count = len(doc)
    if page_count < 1:
      raise DocumentProcessingError("The PDF document contains no pages.")

    if page_count > cfg.MAX_PDF_PAGES:
      raise DocumentProcessingError(
          f"Document exceeds maximum page limit of {cfg.MAX_PDF_PAGES} pages (uploaded file has {page_count} pages)."
      )

    return sha256_hash, page_count
  finally:
    doc.close()


def normalize_text(text: str) -> str:
  """Clean and normalize extracted text using Unicode NFC, stripping control characters.

  Preserves tabs, newlines, and valid Unicode scripts (including Tamil).
  Collapses excessive empty lines and trailing spaces.
  """
  if not text:
    return ""

  # Unicode NFC normalization
  normalized = unicodedata.normalize("NFC", text)

  # Remove null bytes and non-printable control characters, but preserve \t and \n
  cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", normalized)

  # Strip trailing whitespace on each line
  lines = [line.rstrip() for line in cleaned.splitlines()]

  # Recombine and collapse 3+ consecutive newlines into 2
  joined = "\n".join(lines)
  joined = re.sub(r"\n{3,}", "\n\n", joined)

  return joined.strip()


def assess_page_quality(text: str, has_images: bool = False) -> Tuple[str, bool]:
  """Evaluate extracted page text to determine quality and whether OCR is warranted.

  Returns (quality_status, needs_ocr).
  Status values: 'normal', 'low_quality', 'needs_ocr', 'blank'.
  """
  stripped = text.strip()
  if not stripped:
    if has_images:
      return "needs_ocr", True
    return "blank", False

  if len(stripped) < 50 and has_images:
    return "needs_ocr", True

  # Check character sanity: ratio of printable alphanumeric / Tamil characters
  valid_chars = sum(1 for c in stripped if c.isalnum() or is_tamil_char(c) or c.isspace())
  ratio = valid_chars / max(1, len(stripped))

  if ratio < 0.4:
    return "low_quality", True

  return "normal", False


def chunk_page_text(
    text: str,
    doc_id: str,
    page_number: int,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> List[DocumentChunk]:
  """Split page text into chunks without ever crossing page boundaries.

  Ensures exact page-level provenance and citation fidelity in RAG answers.
  """
  if not text or not text.strip():
    return []

  text = text.strip()
  if len(text) <= chunk_size:
    return [
        DocumentChunk(
            chunk_id=f"{doc_id}_p{page_number}_c0",
            document_id=doc_id,
            page_number=page_number,
            chunk_index=0,
            text=text,
            char_count=len(text),
        )
    ]

  # Split on paragraph boundaries first
  paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
  chunks: List[str] = []
  current_chunk = ""

  for para in paragraphs:
    if not current_chunk:
      current_chunk = para
    elif len(current_chunk) + len(para) + 2 <= chunk_size:
      current_chunk += "\n\n" + para
    else:
      chunks.append(current_chunk)
      # Retain overlap from end of current chunk
      if chunk_overlap > 0 and len(current_chunk) > chunk_overlap:
        overlap_slice = current_chunk[-chunk_overlap:]
        # Find nearest word boundary if possible
        space_idx = overlap_slice.find(" ")
        if space_idx != -1:
          overlap_slice = overlap_slice[space_idx + 1:]
        current_chunk = overlap_slice + "\n\n" + para
      else:
        current_chunk = para

  if current_chunk and (not chunks or chunks[-1] != current_chunk):
    chunks.append(current_chunk)

  # Fallback for massive monolithic paragraphs that exceed chunk_size
  final_chunks: List[str] = []
  for c in chunks:
    if len(c) <= chunk_size:
      final_chunks.append(c)
    else:
      start = 0
      while start < len(c):
        end = min(start + chunk_size, len(c))
        final_chunks.append(c[start:end])
        if end >= len(c):
          break
        start += max(1, chunk_size - chunk_overlap)

  result: List[DocumentChunk] = []
  for idx, chunk_str in enumerate(final_chunks):
    clean = chunk_str.strip()
    if clean:
      result.append(
          DocumentChunk(
              chunk_id=f"{doc_id}_p{page_number}_c{idx}",
              document_id=doc_id,
              page_number=page_number,
              chunk_index=idx,
              text=clean,
              char_count=len(clean),
          )
      )

  return result


class DocumentService:
  """Orchestrator for document extraction, OCR fallback, persistence, and summarization."""

  def __init__(
      self,
      store: Optional[DocumentStore] = None,
      gemini: Optional[GeminiService] = None,
      settings: Optional[Settings] = None,
  ):
    self._store = store or get_document_store()
    self._gemini = gemini or get_gemini_service()
    self._settings = settings or get_settings()

  def validate_and_stage_upload(
      self,
      filename: str,
      file_bytes: bytes,
      client_key: str = "default",
      owner_id: str = "local",
  ) -> DocumentUploadResponse:
    """Validate PDF upload, detect duplicates by hash, and stage for background extraction."""
    # Check rate limit
    _rate_limiter.check(client_key)

    # Size check against MAX_UPLOAD_MB
    max_bytes = self._settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
      raise DocumentProcessingError(
          f"File size exceeds the {self._settings.MAX_UPLOAD_MB} MB limit ({len(file_bytes) / (1024 * 1024):.1f} MB)."
      )

    clean_filename = sanitize_display_filename(filename)
    sha256_hash, page_count = validate_pdf_content(file_bytes, self._settings)

    # Check for duplicate document scoped to user
    existing = self._store.find_by_sha256(sha256_hash, collection="user", owner_id=owner_id)
    if existing:
      existing_id = existing["document_id"]
      logger.info("Matched duplicate PDF upload: %s (existing id: %s)", clean_filename, existing_id)
      return DocumentUploadResponse(
          document_id=existing_id,
          filename=existing.get("filename", clean_filename),
          file_size_bytes=existing.get("file_size_bytes", len(file_bytes)),
          page_count=existing.get("page_count", page_count),
          status=existing.get("status", "ready"),
          is_duplicate=True,
          message="Identical document already uploaded. Reusing existing processed record.",
      )

    import uuid
    doc_id = str(uuid.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    metadata: Dict[str, Any] = {
        "document_id": doc_id,
        "owner_id": owner_id,
        "filename": clean_filename,
        "file_size_bytes": len(file_bytes),
        "page_count": page_count,
        "sha256": sha256_hash,
        "status": "uploaded",
        "progress": {"current_page": 0, "total_pages": page_count},
        "language": "unknown",
        "ocr_applied": False,
        "ocr_page_count": 0,
        "warnings": [],
        "error_message": None,
        "uploaded_at": now_iso,
        "processed_at": None,
        "index_status": "not_indexed",
        "index_built_at": None,
        "embedding_model": None,
        "indexed_chunks_count": 0,
    }

    # Save original PDF file
    doc_dir = self._store._get_doc_dir(doc_id)
    pdf_path = doc_dir / "original.pdf"
    with open(pdf_path, "wb") as f:
      f.write(file_bytes)

    # Initialize metadata
    self._store.create_document(doc_id, metadata, owner_id=owner_id)
    get_activity_service().record_activity("document.uploaded", "document", doc_id, owner_id=owner_id)
    logger.info("Staged new PDF for processing: %s (id: %s, pages: %d)", clean_filename, doc_id, page_count)

    return DocumentUploadResponse(
        document_id=doc_id,
        filename=clean_filename,
        file_size_bytes=len(file_bytes),
        page_count=page_count,
        status="uploaded",
        is_duplicate=False,
        message="Document uploaded successfully. Processing started in background.",
    )

  def process_document(self, doc_id: str) -> None:
    """Execute text extraction, OCR fallback, and chunking pipeline (synchronous worker)."""
    meta = self._store.get_metadata(doc_id)
    if not meta:
      logger.error("Cannot process document: metadata not found for %s", doc_id)
      return

    pdf_path = self._store.get_file_path(doc_id)
    if not pdf_path or not pdf_path.exists():
      self._store.update_status(doc_id, status="failed", error_message="Original PDF file is missing.")
      return

    self._store.update_status(doc_id, status="processing")

    caps = check_ocr_capabilities(self._settings)
    ocr_available = caps.ocr_available

    warnings: List[str] = []
    page_records: List[Dict[str, Any]] = []
    all_chunks: List[DocumentChunk] = []
    ocr_page_count = 0
    accumulated_text_sample = ""

    try:
      doc = fitz.open(str(pdf_path))
      total_pages = len(doc)

      for page_idx in range(total_pages):
        page_number = page_idx + 1
        page = doc[page_idx]

        # Extract text via PyMuPDF
        raw_text = page.get_text("text") or ""
        has_images = len(page.get_images()) > 0
        quality, needs_ocr = assess_page_quality(raw_text, has_images)
        extraction_method = "pymupdf"

        # OCR Fallback
        if needs_ocr and self._settings.OCR_ENABLED and (page_number <= self._settings.OCR_MAX_PAGES):
          if not ocr_available:
            warn_msg = (
                f"Page {page_number} appears to be scanned or image-based, but Tesseract OCR is not installed or available."
            )
            if warn_msg not in warnings:
              warnings.append(warn_msg)
            if quality == "needs_ocr":
              quality = "low_quality"
          else:
            try:
              pix = page.get_pixmap(dpi=self._settings.OCR_DPI)
              img = Image.open(io.BytesIO(pix.tobytes("png")))
              ocr_text = pytesseract.image_to_string(img, lang=self._settings.OCR_LANGUAGES) or ""
              if len(ocr_text.strip()) > len(raw_text.strip()):
                raw_text = ocr_text
                extraction_method = "ocr"
                ocr_page_count += 1
                quality, _ = assess_page_quality(raw_text, False)
            except Exception as ocr_err:
              logger.warning("OCR error on page %d of doc %s: %s", page_number, doc_id, ocr_err)
              warnings.append(f"OCR failed on page {page_number}: {ocr_err}")

        clean_text = normalize_text(raw_text)
        preview = clean_text[:200].replace("\n", " ").strip()

        page_records.append({
            "page_number": page_number,
            "text": clean_text,
            "char_count": len(clean_text),
            "extraction_method": extraction_method,
            "quality": quality,
            "preview": preview,
        })

        if len(accumulated_text_sample) < 5000 and clean_text:
          accumulated_text_sample += " " + clean_text

        # Generate page-isolated chunks
        page_chunks = chunk_page_text(
            clean_text,
            doc_id,
            page_number,
            chunk_size=self._settings.CHUNK_SIZE_CHARS,
            chunk_overlap=self._settings.CHUNK_OVERLAP_CHARS,
        )
        all_chunks.extend(page_chunks)

        # Update progress
        self._store.update_status(
            doc_id,
            status="processing",
            progress={"current_page": page_number, "total_pages": total_pages},
        )

      doc.close()

      # Detect overall language
      detected_language = detect_language(accumulated_text_sample) if accumulated_text_sample.strip() else "en"

      # Save pages and chunks
      self._store.save_pages(doc_id, page_records)
      self._store.save_chunks(doc_id, [c.model_dump() for c in all_chunks])

      final_status = "ready_with_warnings" if warnings else "ready"
      now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

      self._store.update_status(
          doc_id,
          status=final_status,
          progress={"current_page": total_pages, "total_pages": total_pages},
          language=detected_language,
          ocr_applied=ocr_page_count > 0,
          ocr_page_count=ocr_page_count,
          warnings=warnings,
          processed_at=now_iso,
      )
      get_activity_service().record_activity("document.ready", "document", doc_id)
      logger.info(
          "Finished processing doc %s: status=%s, pages=%d, chunks=%d, language=%s",
          doc_id,
          final_status,
          len(page_records),
          len(all_chunks),
          detected_language,
      )

    except Exception as exc:
      logger.exception("Fatal processing failure for doc %s: %s", doc_id, exc)
      self._store.update_status(
          doc_id,
          status="failed",
          error_message=f"Processing error: {exc}",
      )

  def get_document_detail(self, doc_id: str, owner_id: Optional[str] = None) -> DocumentDetailResponse:
    """Retrieve complete document detail including per-page overview and chunk count."""
    meta = self._store.get_metadata(doc_id, owner_id=owner_id)
    if not meta:
      raise DocumentNotFoundError(f"Document '{doc_id}' not found.")

    pages_data = self._store.get_pages(doc_id, page=1, page_size=1000)
    raw_pages = pages_data.get("pages", [])

    pages_summary = [
        PageSummary(
            page_number=p.get("page_number", idx + 1),
            char_count=p.get("char_count", 0),
            extraction_method=p.get("extraction_method", "pymupdf"),
            quality=p.get("quality", "normal"),
            preview=p.get("preview", ""),
        )
        for idx, p in enumerate(raw_pages)
    ]

    chunks = self._store.get_chunks(doc_id)

    return DocumentDetailResponse(
        document_id=meta["document_id"],
        filename=meta["filename"],
        file_size_bytes=meta["file_size_bytes"],
        page_count=meta.get("page_count", len(raw_pages)),
        sha256=meta["sha256"],
        status=meta.get("status", "uploaded"),
        progress=meta.get("progress"),
        language=meta.get("language", "unknown"),
        ocr_applied=meta.get("ocr_applied", False),
        ocr_page_count=meta.get("ocr_page_count", 0),
        warnings=meta.get("warnings", []),
        error_message=meta.get("error_message"),
        uploaded_at=meta["uploaded_at"],
        processed_at=meta.get("processed_at"),
        index_status=meta.get("index_status", "not_indexed"),
        index_built_at=meta.get("index_built_at"),
        embedding_model=meta.get("embedding_model"),
        indexed_chunks_count=meta.get("indexed_chunks_count"),
        pages_summary=pages_summary,
        chunks_count=len(chunks),
    )

  async def generate_summary(
      self,
      doc_id: str,
      requested_language: str = "auto",
      owner_id: Optional[str] = None,
  ) -> DocumentSummaryResponse:
    """Generate an AI-grounded summary of the official document, cached by language."""
    meta = self._store.get_metadata(doc_id, owner_id=owner_id)
    if not meta:
      raise DocumentNotFoundError(f"Document '{doc_id}' not found.")

    doc_status = meta.get("status")
    if doc_status not in ("ready", "ready_with_warnings"):
      raise DocumentProcessingError(
          f"Document summary cannot be generated while status is '{doc_status}'. Please wait until processing completes."
      )

    doc_language = meta.get("language", "en")
    target_language = doc_language if requested_language == "auto" else requested_language
    if target_language not in ("en", "ta"):
      target_language = "en"

    # Check cache
    cached = self._store.get_summary(doc_id, target_language)
    if cached:
      return DocumentSummaryResponse(
          document_id=doc_id,
          language=target_language,
          summary=cached,
          cached=True,
          model=self._gemini.active_model,
      )

    # Compile document text within a safe character budget
    pages_data = self._store.get_pages(doc_id, page=1, page_size=200)
    pages = pages_data.get("pages", [])

    if not pages:
      raise DocumentProcessingError("No extracted text found for this document.")

    content_parts: List[str] = []
    budget_chars = 30000
    current_chars = 0

    for p in pages:
      p_num = p.get("page_number", 1)
      p_text = p.get("text", "").strip()
      if not p_text:
        continue
      header = f"--- Page {p_num} ---\n"
      addition = header + p_text + "\n\n"
      if current_chars + len(addition) > budget_chars:
        remaining = budget_chars - current_chars
        if remaining > 200:
          content_parts.append(addition[:remaining] + "\n[Document text truncated for model context limit...]\n")
        break
      content_parts.append(addition)
      current_chars += len(addition)

    full_text = "".join(content_parts)
    wrapped_text = wrap_untrusted_content(full_text, label="untrusted_document")
    system_prompt = get_document_summary_prompt(reply_language=target_language)

    user_prompt = (
        f"Please analyze and produce a structured, factual civic summary of the following official document. "
        f"Rely ONLY on the provided text. Never hallucinate rules or dates.\n\n{wrapped_text}"
    )

    result = await self._gemini.generate_text(
        prompt_or_messages=user_prompt,
        system_instruction=system_prompt,
        temperature=0.2,
    )

    summary_text = result.text.strip()
    self._store.save_summary(doc_id, target_language, summary_text)

    return DocumentSummaryResponse(
        document_id=doc_id,
        language=target_language,
        summary=summary_text,
        cached=False,
        model=result.model,
    )

  def delete_document(self, doc_id: str, owner_id: Optional[str] = None) -> bool:
    """Delete a document and related artifacts, scoped by owner."""
    return self._store.delete_document(doc_id, owner_id=owner_id)


_document_service_instance: Optional[DocumentService] = None


def get_document_service() -> DocumentService:
  """Dependency provider returning singleton DocumentService instance."""
  global _document_service_instance
  if _document_service_instance is None:
    _document_service_instance = DocumentService()
  return _document_service_instance


def set_document_service(service: Optional[DocumentService]) -> None:
  """Test helper to inject or reset DocumentService."""
  global _document_service_instance
  _document_service_instance = service
