"""Filesystem-based document storage layer for CivicLens.

Designed behind an explicit interface so Phase 15 can transition storage
to an SQLite relational database with user ownership without rewriting API callers.
Enforces atomic JSON writes, path-traversal prevention, and filename sanitization.
"""

import json
import logging
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import Settings, get_settings
from app.db.stores import SqliteDocumentStore

logger = logging.getLogger("civiclens.store")

# Alias DocumentStore to SqliteDocumentStore for transparent Phase 15 SQLite persistence
DocumentStore = SqliteDocumentStore



def sanitize_display_filename(filename: str) -> str:
  """Sanitize user-provided filename for safe display and metadata storage.

  Never used as a filesystem path. Strips directory traversal components,
  null bytes, control characters, and truncates to 120 characters.
  """
  if not filename:
    return "untitled_document.pdf"
  # Extract base name only (strip both Windows and Unix directory separators)
  base = os.path.basename(filename.replace("\\", "/"))
  # Remove null bytes and non-printable control characters
  cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", base).strip()
  # Ensure clean .pdf extension
  if not cleaned.lower().endswith(".pdf"):
    cleaned += ".pdf"
  if len(cleaned) > 120:
    cleaned = cleaned[:116] + ".pdf"
  return cleaned or "document.pdf"


def validate_document_id(doc_id: str) -> str:
  """Validate that document_id is a valid UUID4 string to prevent path traversal."""
  try:
    val = uuid.UUID(str(doc_id).strip(), version=4)
    return str(val)
  except (ValueError, AttributeError, TypeError) as exc:
    raise ValueError(f"Invalid document identifier format: '{doc_id}'") from exc


def atomic_write_json(file_path: Path, data: Any) -> None:
  """Write JSON data to a temporary file first, then atomically replace the destination."""
  import time
  temp_path = file_path.with_suffix(f".{uuid.uuid4().hex[:8]}.tmp")
  try:
    with open(temp_path, "w", encoding="utf-8") as f:
      json.dump(data, f, ensure_ascii=False, indent=2)
    # Resilient replacement for Windows file locks / OneDrive indexer
    for attempt in range(6):
      try:
        os.replace(temp_path, file_path)
        break
      except (PermissionError, OSError):
        if attempt == 5:
          raise
        time.sleep(0.05)
  except Exception as exc:
    if temp_path.exists():
      try:
        temp_path.unlink(missing_ok=True)
      except Exception:
        pass
    raise exc


def read_json_safe(file_path: Path) -> Optional[Any]:
  """Safely read and parse a JSON file, returning None if missing or corrupted."""
  if not file_path.exists():
    return None
  try:
    with open(file_path, "r", encoding="utf-8") as f:
      return json.load(f)
  except Exception as exc:
    logger.warning("Failed to read JSON from %s: %s", file_path.name, exc)
    return None


class DocumentStore:
  """Storage manager for document artifacts, pages, chunks, and cached summaries.

  NOTE: Phase 15 will replace this filesystem implementation with SQLite models
  while keeping the exact same method signatures.
  """

  def __init__(
      self,
      settings: Optional[Settings] = None,
      base_dir: Optional[Path] = None,
      indexes_dir: Optional[Path] = None,
  ):
    self._settings = settings or get_settings()
    self._base_dir = base_dir or self._settings.upload_dir
    self._base_dir.mkdir(parents=True, exist_ok=True)
    self._indexes_dir = indexes_dir or self._settings.indexes_dir
    self._indexes_dir.mkdir(parents=True, exist_ok=True)

  def _get_doc_dir(self, doc_id: str) -> Path:
    """Return validated document directory path."""
    valid_id = validate_document_id(doc_id)
    doc_dir = self._base_dir / valid_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    return doc_dir

  def create_document(self, doc_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize storage folder and save initial document metadata."""
    doc_dir = self._get_doc_dir(doc_id)
    meta_path = doc_dir / "meta.json"
    atomic_write_json(meta_path, metadata)
    try:
      from app.db.stores import SqliteDocumentStore
      SqliteDocumentStore(self._settings).create_document(doc_id, metadata)
    except Exception as exc:
      logger.debug("SQLite sync for create_document skipped: %s", exc)
    return metadata

  def get_metadata(self, doc_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve document metadata dictionary."""
    try:
      doc_dir = self._get_doc_dir(doc_id)
      return read_json_safe(doc_dir / "meta.json")
    except ValueError:
      return None

  def list_documents(self) -> List[Dict[str, Any]]:
    """List all document metadata dictionaries, sorted newest first."""
    docs: List[Dict[str, Any]] = []
    if not self._base_dir.exists():
      return docs

    for entry in self._base_dir.iterdir():
      if entry.is_dir():
        meta_file = entry / "meta.json"
        meta = read_json_safe(meta_file)
        if meta and isinstance(meta, dict):
          docs.append(meta)

    # Sort descending by upload timestamp
    docs.sort(key=lambda d: str(d.get("uploaded_at", "")), reverse=True)
    return docs

  def find_by_sha256(self, sha256_hash: str) -> Optional[Dict[str, Any]]:
    """Locate an existing document with the identical SHA-256 content hash."""
    clean_hash = str(sha256_hash).strip().lower()
    for doc in self.list_documents():
      if str(doc.get("sha256", "")).lower() == clean_hash:
        return doc
    return None

  def update_status(
      self,
      doc_id: str,
      status: Optional[str] = None,
      progress: Optional[Dict[str, int]] = None,
      error_message: Optional[str] = None,
      warnings: Optional[List[str]] = None,
      **kwargs: Any,
  ) -> None:
    """Atomically update document status, progress, or extra attributes."""
    doc_dir = self._get_doc_dir(doc_id)
    meta_path = doc_dir / "meta.json"
    meta = read_json_safe(meta_path) or {}

    if status is not None:
      meta["status"] = status
    if progress is not None:
      meta["progress"] = progress
    if error_message is not None:
      meta["error_message"] = error_message
    if warnings is not None:
      existing_warnings = meta.get("warnings", [])
      meta["warnings"] = list(dict.fromkeys(existing_warnings + warnings))

    for k, v in kwargs.items():
      if v is not None:
        meta[k] = v

    atomic_write_json(meta_path, meta)

  def save_pages(self, doc_id: str, pages: List[Dict[str, Any]]) -> None:
    """Persist extracted page-level text and quality indicators."""
    doc_dir = self._get_doc_dir(doc_id)
    atomic_write_json(doc_dir / "pages.json", pages)

  def get_pages(
      self, doc_id: str, page: int = 1, page_size: int = 20
  ) -> Dict[str, Any]:
    """Retrieve paginated page records for a document."""
    doc_dir = self._get_doc_dir(doc_id)
    all_pages = read_json_safe(doc_dir / "pages.json") or []
    total = len(all_pages)

    start = (page - 1) * page_size
    end = start + page_size
    slice_pages = all_pages[start:end]

    return {
        "pages": slice_pages,
        "total_pages": total,
        "page": page,
        "page_size": page_size,
    }

  def get_page(self, doc_id: str, page_number: int) -> Optional[Dict[str, Any]]:
    """Retrieve a single page's text and metadata by 1-based page number."""
    doc_dir = self._get_doc_dir(doc_id)
    all_pages = read_json_safe(doc_dir / "pages.json") or []
    for p in all_pages:
      if p.get("page_number") == page_number:
        return p
    return None

  def save_chunks(self, doc_id: str, chunks: List[Dict[str, Any]]) -> None:
    """Persist page-isolated text chunks for future Phase 8 RAG embedding."""
    doc_dir = self._get_doc_dir(doc_id)
    atomic_write_json(doc_dir / "chunks.json", chunks)

  def get_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
    """Retrieve all chunks generated for a document."""
    doc_dir = self._get_doc_dir(doc_id)
    return read_json_safe(doc_dir / "chunks.json") or []

  def save_summary(self, doc_id: str, language: str, summary: str) -> None:
    """Cache generated AI summary per document and language to conserve quota."""
    doc_dir = self._get_doc_dir(doc_id)
    summaries_file = doc_dir / "summaries.json"
    cache = read_json_safe(summaries_file) or {}
    cache[language.strip().lower()] = summary
    atomic_write_json(summaries_file, cache)

  def get_summary(self, doc_id: str, language: str) -> Optional[str]:
    """Retrieve cached AI summary if previously generated for this language."""
    doc_dir = self._get_doc_dir(doc_id)
    summaries_file = doc_dir / "summaries.json"
    cache = read_json_safe(summaries_file) or {}
    return cache.get(language.strip().lower())

  def get_file_path(self, doc_id: str) -> Optional[Path]:
    """Return local path to the original PDF if present."""
    try:
      doc_dir = self._get_doc_dir(doc_id)
      pdf_path = doc_dir / "original.pdf"
      return pdf_path if pdf_path.exists() else None
    except ValueError:
      return None

  def get_index_dir(self, doc_id: str) -> Path:
    """Return validated index directory path for document vectors."""
    valid_id = validate_document_id(doc_id)
    idx_dir = self._indexes_dir / valid_id
    idx_dir.mkdir(parents=True, exist_ok=True)
    return idx_dir

  def delete_document(self, doc_id: str) -> bool:
    """Completely remove all artifacts, directory, and vector indexes for a document."""
    try:
      valid_id = validate_document_id(doc_id)
      # 1. Clean up index directory
      index_dir = self._indexes_dir / valid_id
      if index_dir.exists():
        shutil.rmtree(index_dir, ignore_errors=True)

      # 2. Clean up document upload directory
      doc_dir = self._base_dir / valid_id
      if doc_dir.exists():
        shutil.rmtree(doc_dir, ignore_errors=True)
        return True
      return False
    except (ValueError, Exception) as exc:
      logger.warning("Error deleting document %s: %s", doc_id, exc)
      return False


# Alias DocumentStore to SqliteDocumentStore for transparent Phase 15 SQLite persistence
DocumentStore = SqliteDocumentStore

_document_store_instance: Optional[DocumentStore] = None

def get_document_store() -> DocumentStore:
  """Dependency provider returning shared DocumentStore instance."""
  global _document_store_instance
  if _document_store_instance is None:
    _document_store_instance = DocumentStore()
  return _document_store_instance


def set_document_store(store: Optional[DocumentStore]) -> None:
  """Test helper to inject or reset DocumentStore."""
  global _document_store_instance
  _document_store_instance = store
