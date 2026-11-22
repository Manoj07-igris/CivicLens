"""Official Source Library Service (Module 3).

Manages curated, administrator-governed official policy documents stored in
backend/data/official_sources/, reusing the Phase 7 extraction and Phase 8
FAISS vector indexing pipelines while keeping official sources strictly isolated
from citizen-uploaded documents.
"""

import datetime
import hashlib
import json
import logging
import re
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import Settings, get_settings
from app.core.errors import (
    DocumentProcessingError,
    SourceLibraryError,
    SourceNotFoundError,
)
from app.models.documents import IndexBuildResponse
from app.models.verification import (
    OfficialSourceCreateRequest,
    OfficialSourceMetadata,
    OfficialSourceUpdateRequest,
)
from app.services.document_service import DocumentService, validate_pdf_content
from app.services.document_store import (
    DocumentStore,
    atomic_write_json,
    read_json_safe,
    sanitize_display_filename,
    validate_document_id,
)
from app.services.rag_service import RAGService, get_rag_service
from app.db.stores import SqliteSourceLibraryStore

logger = logging.getLogger("civiclens.sources")

# Alias SourceLibraryStore to SqliteSourceLibraryStore for transparent Phase 15 SQLite persistence
SourceLibraryStore = SqliteSourceLibraryStore



class SourceLibraryStore:
  """Filesystem storage manager for the official source library manifest and documents.

  Maintains backend/data/official_sources/manifest.json with atomic writes.
  """

  def __init__(self, settings: Optional[Settings] = None):
    self._settings = settings or get_settings()
    self._base_dir: Path = self._settings.official_sources_dir
    self._base_dir.mkdir(parents=True, exist_ok=True)
    self._manifest_file = self._base_dir / "manifest.json"
    self._lock = threading.Lock()

  def _read_manifest(self) -> Dict[str, Any]:
    with self._lock:
      data = read_json_safe(self._manifest_file)
      if data is None or not isinstance(data, dict):
        return {"version": 1, "sources": {}}
      if "sources" not in data or not isinstance(data["sources"], dict):
        data["sources"] = {}
      return data

  def _write_manifest(self, data: Dict[str, Any]) -> None:
    with self._lock:
      atomic_write_json(self._manifest_file, data)

  def compute_library_version(self) -> str:
    """Compute deterministic hash of manifest records and index build times.

    Used in verification report caching so any library change invalidates stale cache.
    """
    manifest = self._read_manifest()
    sources = manifest.get("sources", {})
    if not sources:
      return "v0_empty"

    components: List[str] = []
    # Sort source IDs for deterministic hashing
    for s_id in sorted(sources.keys()):
      s = sources[s_id]
      sig = (
          f"{s_id}:{s.get('status', 'unknown')}:"
          f"{s.get('effective_date', '')}:"
          f"{s.get('index_status', 'not_indexed')}:"
          f"{s.get('index_built_at', '')}:"
          f"{s.get('superseded_by', '')}"
      )
      components.append(sig)

    digest = hashlib.sha256(";".join(components).encode("utf-8")).hexdigest()[:12]
    return f"lib_{digest}"

  def list_sources(self) -> List[OfficialSourceMetadata]:
    """Return all official source metadata records sorted descending by added_at."""
    manifest = self._read_manifest()
    results: List[OfficialSourceMetadata] = []
    for s_data in manifest.get("sources", {}).values():
      try:
        results.append(OfficialSourceMetadata.model_validate(s_data))
      except Exception as exc:
        logger.warning("Corrupt manifest entry for source %s: %s", s_data.get("source_id"), exc)

    results.sort(key=lambda s: s.added_at, reverse=True)
    return results

  def get_source(self, source_id: str) -> Optional[OfficialSourceMetadata]:
    """Retrieve metadata for a specific official source ID."""
    clean_id = validate_document_id(source_id)
    manifest = self._read_manifest()
    s_data = manifest.get("sources", {}).get(clean_id)
    if not s_data:
      return None
    try:
      return OfficialSourceMetadata.model_validate(s_data)
    except Exception as exc:
      logger.warning("Failed to parse source %s: %s", source_id, exc)
      return None

  def save_source(self, metadata: OfficialSourceMetadata) -> None:
    """Insert or update a source metadata record in the manifest."""
    manifest = self._read_manifest()
    manifest.setdefault("sources", {})[metadata.source_id] = metadata.model_dump()
    self._write_manifest(manifest)
    try:
      from app.db.stores import SqliteSourceLibraryStore
      SqliteSourceLibraryStore(self._settings).save_source(metadata)
    except Exception as exc:
      logger.debug("SQLite sync for save_source skipped: %s", exc)

  def delete_source(self, source_id: str) -> bool:
    """Remove a source record, clean its files and index, and clear dangling superseded_by refs."""
    clean_id = validate_document_id(source_id)
    manifest = self._read_manifest()
    sources = manifest.get("sources", {})
    if clean_id not in sources:
      return False

    del sources[clean_id]

    # Clear dangling superseded_by pointers in remaining sources
    for s_data in sources.values():
      if s_data.get("superseded_by") == clean_id:
        s_data["superseded_by"] = None
        s_data["status"] = "unknown"

    self._write_manifest(manifest)

    # 1. Remove source folder in official_sources
    source_dir = self._base_dir / clean_id
    if source_dir.exists():
      shutil.rmtree(source_dir, ignore_errors=True)

    # 2. Remove FAISS vector index in data/indexes
    index_dir = self._settings.indexes_dir / clean_id
    if index_dir.exists():
      shutil.rmtree(index_dir, ignore_errors=True)

    return True

  def find_by_sha256(self, sha256_hash: str) -> Optional[OfficialSourceMetadata]:
    """Locate an existing official source with the identical content hash."""
    clean_hash = str(sha256_hash).strip().lower()
    for source in self.list_sources():
      if source.sha256.lower() == clean_hash:
        return source
    return None


from app.db.stores import SqliteSourceLibraryStore
SourceLibraryStore = SqliteSourceLibraryStore


class SourceLibraryService:
  """High-level service managing official sources lifecycle, extraction, and vector indexing."""

  def __init__(
      self,
      settings: Optional[Settings] = None,
      store: Optional[SourceLibraryStore] = None,
      embeddings: Optional[Any] = None,
  ):
    self._settings = settings or get_settings()
    self._store = store or SourceLibraryStore(self._settings)

    # Internal DocumentStore pointing directly to backend/data/official_sources
    self._doc_store = DocumentStore(
        settings=self._settings,
        base_dir=self._settings.official_sources_dir,
        indexes_dir=self._settings.indexes_dir,
    )
    self._doc_service = DocumentService(
        store=self._doc_store,
        settings=self._settings,
    )
    self._rag_service = RAGService(
        store=self._doc_store,
        settings=self._settings,
        embeddings=embeddings,
    )

  @property
  def store(self) -> SourceLibraryStore:
    return self._store

  @property
  def doc_store(self) -> DocumentStore:
    return self._doc_store

  def list_sources(self) -> List[OfficialSourceMetadata]:
    """Return all official sources from manifest."""
    return self._store.list_sources()

  def get_source(self, source_id: str) -> OfficialSourceMetadata:
    """Retrieve metadata or raise SourceNotFoundError."""
    source = self._store.get_source(source_id)
    if not source:
      raise SourceNotFoundError(f"Official source '{source_id}' not found in library.")
    return source

  def add_source(
      self,
      filename: str,
      file_bytes: bytes,
      req: OfficialSourceCreateRequest,
  ) -> Tuple[OfficialSourceMetadata, bool]:
    """Validate PDF, detect duplicates, stage files, and save metadata to manifest.

    Returns (OfficialSourceMetadata, is_duplicate).
    """
    if not self._settings.ALLOW_SOURCE_MANAGEMENT:
      raise SourceLibraryError(
          "Official source management is disabled by server configuration.",
          code="SOURCE_MANAGEMENT_DISABLED",
          status_code=403,
      )

    max_bytes = self._settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
      raise DocumentProcessingError(
          f"File size exceeds the {self._settings.MAX_UPLOAD_MB} MB limit ({len(file_bytes) / (1024 * 1024):.1f} MB)."
      )

    clean_filename = sanitize_display_filename(filename)
    sha256_hash, page_count = validate_pdf_content(file_bytes, self._settings)

    # Duplicate check within official sources
    existing = self._store.find_by_sha256(sha256_hash)
    if existing:
      logger.info("Matched duplicate official PDF: %s (existing id: %s)", clean_filename, existing.source_id)
      return existing, True

    # Validate superseded_by reference if supplied
    if req.superseded_by:
      target = self._store.get_source(req.superseded_by)
      if not target:
        raise SourceLibraryError(
            f"superseded_by source '{req.superseded_by}' does not exist in library.",
            code="INVALID_SUPERSEDED_BY",
            status_code=422,
        )
      if req.series_id and target.series_id and req.series_id != target.series_id:
        raise SourceLibraryError(
            f"superseded_by source '{req.superseded_by}' belongs to series '{target.series_id}', not '{req.series_id}'.",
            code="SERIES_MISMATCH",
            status_code=422,
        )

    source_id = str(uuid.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Stage storage folder in backend/data/official_sources/<source_id>
    source_dir = self._settings.official_sources_dir / source_id
    source_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = source_dir / "original.pdf"
    with open(pdf_path, "wb") as f:
      f.write(file_bytes)

    # Initialize document store meta.json for DocumentService/RAGService compatibility
    internal_meta: Dict[str, Any] = {
        "document_id": source_id,
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
        "collection": "official",
    }
    self._doc_store.create_document(source_id, internal_meta)

    source_meta = OfficialSourceMetadata(
        source_id=source_id,
        title=req.title,
        issuing_authority=req.issuing_authority,
        source_url=req.source_url,
        publication_date=req.publication_date,
        effective_date=req.effective_date,
        series_id=req.series_id,
        status=req.status,
        superseded_by=req.superseded_by,
        notes=req.notes,
        filename=clean_filename,
        file_size_bytes=len(file_bytes),
        page_count=page_count,
        sha256=sha256_hash,
        language="unknown",
        added_at=now_iso,
        index_status="not_indexed",
        collection="official",
    )
    self._store.save_source(source_meta)
    from app.services.activity_service import get_activity_service
    get_activity_service().record_activity("source.added", "document", source_id)

    logger.info("Staged official source: %s (id: %s, pages: %d)", req.title, source_id, page_count)
    return source_meta, False

  async def process_and_index_source(self, source_id: str) -> None:
    """Execute text extraction and vector index construction sequentially."""
    logger.info("Starting processing and indexing for official source: %s", source_id)
    # 1. Text extraction and chunking
    self._doc_service.process_document(source_id)

    # Sync language and OCR flags from internal meta to manifest
    internal_meta = self._doc_store.get_metadata(source_id) or {}
    source = self._store.get_source(source_id)
    if source:
      source.language = internal_meta.get("language", "unknown")
      source.ocr_applied = internal_meta.get("ocr_applied", False)
      source.ocr_page_count = internal_meta.get("ocr_page_count", 0)
      source.warnings = internal_meta.get("warnings", [])
      self._store.save_source(source)

    # 2. FAISS vector indexing
    await self._rag_service.build_index(source_id, force=True)

    # Sync indexing status to manifest
    updated_internal = self._doc_store.get_metadata(source_id) or {}
    if source:
      source.index_status = updated_internal.get("index_status", "indexed")
      source.index_built_at = updated_internal.get("index_built_at")
      source.indexed_chunks_count = updated_internal.get("indexed_chunks_count", 0)
      self._store.save_source(source)

    logger.info("Completed processing and indexing for official source: %s", source_id)

  def update_source_metadata(
      self,
      source_id: str,
      req: OfficialSourceUpdateRequest,
  ) -> OfficialSourceMetadata:
    """Update metadata attributes in the manifest."""
    if not self._settings.ALLOW_SOURCE_MANAGEMENT:
      raise SourceLibraryError(
          "Official source management is disabled by server configuration.",
          code="SOURCE_MANAGEMENT_DISABLED",
          status_code=403,
      )

    source = self.get_source(source_id)

    # Self-supersession check
    if req.superseded_by is not None:
      if req.superseded_by == source_id:
        raise SourceLibraryError(
            "An official source cannot supersede itself.",
            code="SELF_SUPERSEDED",
            status_code=422,
        )
      target = self._store.get_source(req.superseded_by)
      if not target:
        raise SourceLibraryError(
            f"superseded_by source '{req.superseded_by}' does not exist in library.",
            code="INVALID_SUPERSEDED_BY",
            status_code=422,
        )
      series_to_check = req.series_id or source.series_id
      if series_to_check and target.series_id and series_to_check != target.series_id:
        raise SourceLibraryError(
            f"superseded_by source '{req.superseded_by}' belongs to series '{target.series_id}', not '{series_to_check}'.",
            code="SERIES_MISMATCH",
            status_code=422,
        )

    if req.title is not None:
      source.title = req.title.strip()
    if req.issuing_authority is not None:
      source.issuing_authority = req.issuing_authority.strip()
    if req.source_url is not None:
      source.source_url = req.source_url
    if req.publication_date is not None:
      source.publication_date = req.publication_date
    if req.effective_date is not None:
      source.effective_date = req.effective_date
    if req.series_id is not None:
      source.series_id = req.series_id.strip() or None
    if req.status is not None:
      source.status = req.status
    if req.superseded_by is not None:
      source.superseded_by = req.superseded_by
    if req.notes is not None:
      source.notes = req.notes.strip() or None

    source.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    self._store.save_source(source)
    return source

  def delete_source(self, source_id: str) -> bool:
    """Delete an official source and clean associated index and disk files."""
    if not self._settings.ALLOW_SOURCE_MANAGEMENT:
      raise SourceLibraryError(
          "Official source management is disabled by server configuration.",
          code="SOURCE_MANAGEMENT_DISABLED",
          status_code=403,
      )
    # Check if exists
    self.get_source(source_id)
    return self._store.delete_source(source_id)

  async def rebuild_index(self, source_id: str) -> IndexBuildResponse:
    """Force rebuild of FAISS index for an official source."""
    if not self._settings.ALLOW_SOURCE_MANAGEMENT:
      raise SourceLibraryError(
          "Official source management is disabled by server configuration.",
          code="SOURCE_MANAGEMENT_DISABLED",
          status_code=403,
      )
    source = self.get_source(source_id)
    resp = await self._rag_service.build_index(source_id, force=True)

    internal_meta = self._doc_store.get_metadata(source_id) or {}
    source.index_status = internal_meta.get("index_status", "indexed")
    source.index_built_at = internal_meta.get("index_built_at")
    source.indexed_chunks_count = internal_meta.get("indexed_chunks_count", 0)
    self._store.save_source(source)

    return resp

  def get_file_path(self, source_id: str) -> Optional[Path]:
    """Return path to original PDF file in official sources directory."""
    clean_id = validate_document_id(source_id)
    pdf_path = self._settings.official_sources_dir / clean_id / "original.pdf"
    if pdf_path.exists():
      return pdf_path
    return None

  def get_page(self, source_id: str, page_number: int) -> Optional[Dict[str, Any]]:
    """Retrieve single page details from official source."""
    return self._doc_store.get_page(source_id, page_number)


_source_library_service_instance: Optional[SourceLibraryService] = None

def get_source_library_service() -> SourceLibraryService:
  """Dependency provider returning singleton SourceLibraryService."""
  global _source_library_service_instance
  if _source_library_service_instance is None:
    _source_library_service_instance = SourceLibraryService()
  return _source_library_service_instance


def set_source_library_service(service: Optional[SourceLibraryService]) -> None:
  """Test helper to set or reset singleton SourceLibraryService."""
  global _source_library_service_instance
  _source_library_service_instance = service
