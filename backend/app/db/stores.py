"""SQLite Store Implementations for CivicLens.

Provides drop-in replacements for all earlier filesystem stores with identical
method signatures, return types, and exception behaviors:
- SqliteDocumentStore
- SqliteSourceLibraryStore
- SqlitePortalRegistryStore
- SqliteComparisonStore
- SqliteVerificationStore
- SqliteServiceGuideStore
- SqliteGrievanceStore
- SqliteBrowserSessionStore
"""

import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from app.core.config import Settings, get_settings
from app.core.errors import (
    ComparisonNotFoundError,
    DocumentNotFoundError,
    DocumentProcessingError,
    GrievanceNotFoundError,
    PortalNotFoundError,
    PortalRegistryError,
    ServiceGuideNotFoundError,
    SourceNotFoundError,
)
from app.db.database import Database, from_json, get_database, to_json, utc_now_iso
from app.models.browser import BrowserSessionRecord
from app.models.grievance import Grievance
from app.models.portal import PortalCreateRequest, PortalEntry, PortalUpdateRequest
from app.models.service_guide import ServiceGuideReport
from app.models.verification import OfficialSourceMetadata, VerificationReport

logger = logging.getLogger("civiclens.db.stores")

SYSTEM_DEMO_PORTAL_ID = "prt_demo_portal"
SYSTEM_DEMO_PORTAL = {
    "id": SYSTEM_DEMO_PORTAL_ID,
    "name": "CivicLens Practice Portal (Educational Simulation)",
    "name_ta": "சிவிக்லென்ஸ் பயிற்சி வலைவாசல் (மாதிரி கல்வி செயல்முறை)",
    "url": "http://127.0.0.1:8000/demo-portal/",
    "department": "Department of Administrative Reforms (Demo Simulation)",
    "scope": "state",
    "description": "Safe, local, loopback educational simulation for practicing online government certificate workflows without transmitting real data.",
    "service_types": ["certificates", "revenue", "welfare"],
    "grievance_categories": ["other"],
    "coverage_area": "Tamil Nadu (Demo Simulation)",
    "caution_notes": "SIMULATION ONLY: This local website runs on your computer. It does not contact government servers and never issues real legal certificates.",
    "domain_hint": "127.0.0.1:8000",
    "system": True,
    "kind": "demo",
    "status": "active",
    "linked_source_ids": [],
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


def sanitize_display_filename(filename: str) -> str:
  """Sanitize user-provided filename for safe display and metadata storage."""
  if not filename:
    return "untitled_document.pdf"
  base = os.path.basename(filename.replace("\\", "/"))
  cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", base).strip()
  if not cleaned.lower().endswith(".pdf"):
    cleaned += ".pdf"
  if len(cleaned) > 120:
    cleaned = cleaned[:116] + ".pdf"
  return cleaned or "document.pdf"


def validate_document_id(doc_id: str) -> str:
  """Validate that document_id is a valid UUID string to prevent path traversal."""
  try:
    return str(uuid.UUID(str(doc_id).strip()))
  except Exception as exc:
    raise ValueError(f"Invalid document identifier format: '{doc_id}'") from exc


# ==============================================================================
# 1. SQLITE DOCUMENT STORE
# ==============================================================================
class SqliteDocumentStore:
  """SQLite-backed document storage manager replacing DocumentStore."""

  def __init__(
      self,
      settings: Optional[Settings] = None,
      db: Optional[Database] = None,
      base_dir: Optional[Path] = None,
      indexes_dir: Optional[Path] = None,
  ):
    self._settings = settings or get_settings()
    self._db = db or get_database()
    self._base_dir = base_dir or self._settings.upload_dir
    self._base_dir.mkdir(parents=True, exist_ok=True)
    self._indexes_dir = indexes_dir or self._settings.indexes_dir
    self._indexes_dir.mkdir(parents=True, exist_ok=True)

  def _get_doc_dir(self, doc_id: str) -> Path:
    valid_id = validate_document_id(doc_id)
    doc_dir = self._base_dir / valid_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    return doc_dir

  def create_document(self, doc_id: str, metadata: Dict[str, Any], owner_id: Optional[str] = None) -> Dict[str, Any]:
    valid_id = validate_document_id(doc_id)
    self._get_doc_dir(valid_id)  # Ensure folder for original.pdf

    collection = metadata.get("collection", "user")
    filename = metadata.get("filename", "document.pdf")
    display_name = sanitize_display_filename(metadata.get("display_name", filename))
    size_bytes = int(metadata.get("size_bytes", 0))
    sha256 = str(metadata.get("sha256", "")).strip().lower()
    page_count = int(metadata.get("page_count", 0))
    language = str(metadata.get("language", "en"))
    status = str(metadata.get("status", "processing"))
    progress_json = to_json(metadata.get("progress"))
    error_message = metadata.get("error_message")
    warnings_json = to_json(metadata.get("warnings", []))
    index_status = str(metadata.get("index_status", "not_indexed"))
    index_model = metadata.get("index_model")
    index_built_at = metadata.get("index_built_at")
    index_chunk_count = int(metadata.get("index_chunk_count", 0))
    ocr_used = 1 if metadata.get("ocr_used") else 0
    total_chars = int(metadata.get("total_chars", 0))
    chunk_count = int(metadata.get("chunk_count", 0))
    relative_path = metadata.get("relative_path") or f"uploads/{valid_id}/original.pdf"
    now_iso = metadata.get("uploaded_at") or metadata.get("created_at") or utc_now_iso()
    resolved_owner = owner_id or metadata.get("owner_id") or "local"

    # Official source fields if applicable
    title = metadata.get("title")
    issuing_authority = metadata.get("issuing_authority")
    source_url = metadata.get("source_url")
    publication_date = metadata.get("publication_date")
    effective_date = metadata.get("effective_date")
    series_id = metadata.get("series_id")
    raw_source_status = metadata.get("source_status") or metadata.get("status")
    source_status = raw_source_status if raw_source_status in ("current", "superseded", "unknown") else "current"
    superseded_by = metadata.get("superseded_by")
    notes = metadata.get("notes")
    library_added_at = metadata.get("added_at") or metadata.get("library_added_at")

    full_data = dict(metadata)
    full_data["id"] = valid_id
    full_data["display_name"] = display_name
    full_data["uploaded_at"] = now_iso
    full_data["owner_id"] = resolved_owner

    sql = """
      INSERT INTO documents (
        id, owner_id, collection, filename, display_name, size_bytes, sha256,
        page_count, language, status, progress, error_message, warnings,
        index_status, index_model, index_built_at, index_chunk_count,
        ocr_used, total_chars, chunk_count, relative_path, file_missing,
        title, issuing_authority, source_url, publication_date, effective_date,
        series_id, source_status, superseded_by, notes, library_added_at,
        created_at, updated_at, data
      ) VALUES (
        ?, ?, ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?, 0,
        ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?,
        ?, ?, ?
      )
      ON CONFLICT(id) DO UPDATE SET
        display_name = excluded.display_name,
        size_bytes = excluded.size_bytes,
        status = excluded.status,
        progress = excluded.progress,
        error_message = excluded.error_message,
        warnings = excluded.warnings,
        page_count = excluded.page_count,
        chunk_count = excluded.chunk_count,
        total_chars = excluded.total_chars,
        index_status = excluded.index_status,
        index_model = excluded.index_model,
        index_built_at = excluded.index_built_at,
        index_chunk_count = excluded.index_chunk_count,
        updated_at = excluded.updated_at,
        data = excluded.data;
    """

    params = (
        valid_id, resolved_owner, collection, filename, display_name, size_bytes, sha256,
        page_count, language, status, progress_json, error_message, warnings_json,
        index_status, index_model, index_built_at, index_chunk_count,
        ocr_used, total_chars, chunk_count, relative_path,
        title, issuing_authority, source_url, publication_date, effective_date,
        series_id, source_status, superseded_by, notes, library_added_at,
        now_iso, now_iso, to_json(full_data),
    )

    with self._db.transaction():
      self._db.execute(sql, params)

    return full_data

  def get_metadata(self, doc_id: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
      valid_id = validate_document_id(doc_id)
    except ValueError:
      return None

    if owner_id is not None:
      row = self._db.fetchone(
          "SELECT * FROM documents WHERE id = ? AND (owner_id = ? OR collection = 'official');",
          (valid_id, owner_id),
      )
    else:
      row = self._db.fetchone("SELECT * FROM documents WHERE id = ?;", (valid_id,))

    if not row:
      return None

    meta = from_json(row["data"], {})
    # Synchronize top-level fields with indexed table columns
    meta["id"] = row["id"]
    meta["document_id"] = row["id"]
    meta["owner_id"] = row["owner_id"]
    meta["collection"] = row["collection"]
    meta["filename"] = row["filename"]
    meta["display_name"] = row["display_name"]
    meta["display_filename"] = row["display_name"]
    meta["size_bytes"] = row["size_bytes"]
    meta["file_size_bytes"] = row["size_bytes"]
    meta["sha256"] = row["sha256"]
    meta["page_count"] = row["page_count"]
    meta["chunk_count"] = row["chunk_count"]
    meta["total_chars"] = row["total_chars"]
    meta["language"] = row["language"]
    meta["status"] = row["status"]
    meta["progress"] = from_json(row["progress"], {})
    meta["error_message"] = row["error_message"]
    meta["warnings"] = from_json(row["warnings"], [])
    meta["index_status"] = row["index_status"]
    meta["index_model"] = row["index_model"]
    meta["index_built_at"] = row["index_built_at"]
    meta["index_chunk_count"] = row["index_chunk_count"]
    meta["ocr_used"] = bool(row["ocr_used"])
    meta["file_missing"] = bool(row["file_missing"])
    meta["uploaded_at"] = row["created_at"]
    return meta

  def list_documents(
      self,
      collection: str = "user",
      limit: Optional[int] = None,
      offset: int = 0,
      owner_id: Optional[str] = None,
  ) -> List[Dict[str, Any]]:
    if collection == "official":
      if limit is not None:
        sql = "SELECT * FROM documents WHERE collection = 'official' ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        rows = self._db.fetchall(sql, (int(limit), int(offset)))
      else:
        sql = "SELECT * FROM documents WHERE collection = 'official' ORDER BY created_at DESC;"
        rows = self._db.fetchall(sql)
    elif owner_id is not None:
      if limit is not None:
        sql = "SELECT * FROM documents WHERE collection = ? AND owner_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        rows = self._db.fetchall(sql, (collection, owner_id, int(limit), int(offset)))
      else:
        sql = "SELECT * FROM documents WHERE collection = ? AND owner_id = ? ORDER BY created_at DESC;"
        rows = self._db.fetchall(sql, (collection, owner_id))
    else:
      if limit is not None:
        sql = "SELECT * FROM documents WHERE collection = ? ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        rows = self._db.fetchall(sql, (collection, int(limit), int(offset)))
      else:
        sql = "SELECT * FROM documents WHERE collection = ? ORDER BY created_at DESC;"
        rows = self._db.fetchall(sql, (collection,))

    docs: List[Dict[str, Any]] = []
    for r in rows:
      meta = from_json(r["data"], {})
      meta["id"] = r["id"]
      meta["document_id"] = r["id"]
      meta["owner_id"] = r["owner_id"]
      meta["collection"] = r["collection"]
      meta["filename"] = r["filename"]
      meta["display_name"] = r["display_name"]
      meta["display_filename"] = r["display_name"]
      meta["size_bytes"] = r["size_bytes"]
      meta["file_size_bytes"] = r["size_bytes"]
      meta["sha256"] = r["sha256"]
      meta["page_count"] = r["page_count"]
      meta["chunk_count"] = r["chunk_count"]
      meta["total_chars"] = r["total_chars"]
      meta["language"] = r["language"]
      meta["status"] = r["status"]
      meta["progress"] = from_json(r["progress"], {})
      meta["error_message"] = r["error_message"]
      meta["warnings"] = from_json(r["warnings"], [])
      meta["index_status"] = r["index_status"]
      meta["index_model"] = r["index_model"]
      meta["index_built_at"] = r["index_built_at"]
      meta["index_chunk_count"] = r["index_chunk_count"]
      meta["ocr_used"] = bool(r["ocr_used"])
      meta["file_missing"] = bool(r["file_missing"])
      meta["uploaded_at"] = r["created_at"]
      docs.append(meta)
    return docs

  def find_by_sha256(
      self,
      sha256_hash: str,
      collection: str = "user",
      owner_id: Optional[str] = None,
  ) -> Optional[Dict[str, Any]]:
    clean_hash = str(sha256_hash).strip().lower()
    if owner_id is not None and collection != "official":
      row = self._db.fetchone(
          "SELECT id FROM documents WHERE LOWER(sha256) = ? AND collection = ? AND owner_id = ?;",
          (clean_hash, collection, owner_id),
      )
    else:
      row = self._db.fetchone(
          "SELECT id FROM documents WHERE LOWER(sha256) = ? AND collection = ?;",
          (clean_hash, collection),
      )
    if row:
      return self.get_metadata(row["id"])
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
    valid_id = validate_document_id(doc_id)
    meta = self.get_metadata(valid_id)
    if not meta:
      return

    now_iso = utc_now_iso()
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

    # Prepare SQL columns
    set_clauses = ["updated_at = ?", "data = ?"]
    params: List[Any] = [now_iso, to_json(meta)]

    if status is not None:
      set_clauses.append("status = ?")
      params.append(status)
    if progress is not None:
      set_clauses.append("progress = ?")
      params.append(to_json(progress))
    if error_message is not None:
      set_clauses.append("error_message = ?")
      params.append(error_message)
    if warnings is not None:
      set_clauses.append("warnings = ?")
      params.append(to_json(meta["warnings"]))

    for col in (
        "page_count", "chunk_count", "total_chars", "index_status",
        "index_model", "index_built_at", "index_chunk_count", "ocr_used",
        "file_missing",
    ):
      if col in kwargs:
        set_clauses.append(f"{col} = ?")
        val = kwargs[col]
        params.append(1 if val is True else 0 if val is False else val)

    params.append(valid_id)
    sql = f"UPDATE documents SET {', '.join(set_clauses)} WHERE id = ?;"

    with self._db.transaction():
      self._db.execute(sql, params)

  def save_pages(self, doc_id: str, pages: List[Dict[str, Any]]) -> None:
    valid_id = validate_document_id(doc_id)
    with self._db.transaction():
      self._db.execute("DELETE FROM document_pages WHERE document_id = ?;", (valid_id,))
      if pages:
        insert_sql = """
          INSERT INTO document_pages (document_id, page_number, text, char_count, method, quality)
          VALUES (?, ?, ?, ?, ?, ?);
        """
        rows = [
            (
                valid_id,
                int(p.get("page_number", idx + 1)),
                str(p.get("text", "")),
                int(p.get("char_count", len(p.get("text", "")))),
                str(p.get("method", "direct_text")),
                str(p.get("quality", "good")),
            )
            for idx, p in enumerate(pages)
        ]
        self._db.executemany(insert_sql, rows)

      # Update document page count
      self._db.execute(
          "UPDATE documents SET page_count = ?, updated_at = ? WHERE id = ?;",
          (len(pages), utc_now_iso(), valid_id),
      )

  def get_pages(
      self, doc_id: str, page: int = 1, page_size: int = 20
  ) -> Dict[str, Any]:
    valid_id = validate_document_id(doc_id)
    count_row = self._db.fetchone(
        "SELECT COUNT(*) AS total FROM document_pages WHERE document_id = ?;",
        (valid_id,),
    )
    total = count_row["total"] if count_row else 0

    offset = (page - 1) * page_size
    rows = self._db.fetchall(
        """
        SELECT page_number, text, char_count, method, quality
        FROM document_pages
        WHERE document_id = ?
        ORDER BY page_number ASC
        LIMIT ? OFFSET ?;
        """,
        (valid_id, page_size, offset),
    )
    pages = [dict(r) for r in rows]

    return {
        "pages": pages,
        "total_pages": total,
        "page": page,
        "page_size": page_size,
    }

  def get_page(self, doc_id: str, page_number: int) -> Optional[Dict[str, Any]]:
    valid_id = validate_document_id(doc_id)
    row = self._db.fetchone(
        """
        SELECT page_number, text, char_count, method, quality
        FROM document_pages
        WHERE document_id = ? AND page_number = ?;
        """,
        (valid_id, int(page_number)),
    )
    return dict(row) if row else None

  def save_chunks(self, doc_id: str, chunks: List[Dict[str, Any]]) -> None:
    valid_id = validate_document_id(doc_id)
    with self._db.transaction():
      self._db.execute("DELETE FROM document_chunks WHERE document_id = ?;", (valid_id,))
      if chunks:
        insert_sql = """
          INSERT INTO document_chunks (chunk_id, document_id, page_number, chunk_index, text, start_offset, end_offset, method)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        rows = [
            (
                str(c.get("chunk_id", f"{valid_id}_p{c.get('page_number', 1)}_c{c.get('chunk_index', idx)}")),
                valid_id,
                int(c.get("page_number", 1)),
                int(c.get("chunk_index", idx)),
                str(c.get("text", "")),
                int(c.get("start_offset", 0)),
                int(c.get("end_offset", 0)),
                str(c.get("method", "direct_text")),
            )
            for idx, c in enumerate(chunks)
        ]
        self._db.executemany(insert_sql, rows)

      # Update chunk count on document
      self._db.execute(
          "UPDATE documents SET chunk_count = ?, updated_at = ? WHERE id = ?;",
          (len(chunks), utc_now_iso(), valid_id),
      )

  def get_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
    valid_id = validate_document_id(doc_id)
    rows = self._db.fetchall(
        """
        SELECT chunk_id, document_id, page_number, chunk_index, text, start_offset, end_offset, method
        FROM document_chunks
        WHERE document_id = ?
        ORDER BY page_number ASC, chunk_index ASC;
        """,
        (valid_id,),
    )
    return [dict(r) for r in rows]

  def save_summary(self, doc_id: str, language: str, summary: str) -> None:
    valid_id = validate_document_id(doc_id)
    row = self._db.fetchone("SELECT summaries FROM documents WHERE id = ?;", (valid_id,))
    if not row:
      return
    cache = from_json(row["summaries"], {})
    cache[language.strip().lower()] = summary

    with self._db.transaction():
      self._db.execute(
          "UPDATE documents SET summaries = ?, updated_at = ? WHERE id = ?;",
          (to_json(cache), utc_now_iso(), valid_id),
      )

  def get_summary(self, doc_id: str, language: str) -> Optional[str]:
    valid_id = validate_document_id(doc_id)
    row = self._db.fetchone("SELECT summaries FROM documents WHERE id = ?;", (valid_id,))
    if not row:
      return None
    cache = from_json(row["summaries"], {})
    return cache.get(language.strip().lower())

  def get_file_path(self, doc_id: str) -> Optional[Path]:
    try:
      valid_id = validate_document_id(doc_id)
      # Check upload path
      p1 = self._base_dir / valid_id / "original.pdf"
      if p1.exists():
        return p1
      # Check official sources path
      p2 = self._settings.official_sources_dir / valid_id / "original.pdf"
      if p2.exists():
        return p2
      return None
    except ValueError:
      return None

  def get_index_dir(self, doc_id: str) -> Path:
    valid_id = validate_document_id(doc_id)
    idx_dir = self._indexes_dir / valid_id
    idx_dir.mkdir(parents=True, exist_ok=True)
    return idx_dir

  def delete_document(self, doc_id: str, owner_id: Optional[str] = None) -> bool:
    try:
      valid_id = validate_document_id(doc_id)
      if owner_id is not None:
        chk = self._db.fetchone("SELECT id FROM documents WHERE id = ? AND owner_id = ?;", (valid_id, owner_id))
        if not chk:
          return False

      # 1. Clean up index folder on disk
      index_dir = self._indexes_dir / valid_id
      if index_dir.exists():
        shutil.rmtree(index_dir, ignore_errors=True)

      # 2. Clean up file folder on disk
      doc_dir = self._base_dir / valid_id
      if doc_dir.exists():
        shutil.rmtree(doc_dir, ignore_errors=True)
      source_dir = self._settings.official_sources_dir / valid_id
      if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

      # 3. Clean up database record (cascades pages and chunks)
      with self._db.transaction():
        if owner_id is not None:
          cursor = self._db.execute("DELETE FROM documents WHERE id = ? AND owner_id = ?;", (valid_id, owner_id))
        else:
          cursor = self._db.execute("DELETE FROM documents WHERE id = ?;", (valid_id,))
        return cursor.rowcount > 0
    except Exception as exc:
      logger.warning("Error deleting document %s: %s", doc_id, exc)
      return False


# ==============================================================================
# 2. SQLITE SOURCE LIBRARY STORE
# ==============================================================================
class SqliteSourceLibraryStore:
  """SQLite-backed official source library store replacing SourceLibraryStore."""

  def __init__(
      self,
      settings: Optional[Settings] = None,
      db: Optional[Database] = None,
      base_dir: Optional[Path] = None,
  ):
    self._settings = settings or get_settings()
    self._db = db or get_database()
    self._base_dir = base_dir or self._settings.comparisons_dir
    self._doc_store = SqliteDocumentStore(self._settings, self._db)

  def compute_library_version(self) -> str:
    """Compute deterministic hash of manifest records and index build times."""
    sources = self.list_sources()
    if not sources:
      return "v0_empty"

    components: List[str] = []
    # Sort source IDs for deterministic hashing
    for s in sorted(sources, key=lambda x: x.source_id):
      sig = (
          f"{s.source_id}:{s.status}:"
          f"{s.effective_date or ''}:"
          f"{s.index_status}:"
          f"{s.index_built_at or ''}:"
          f"{s.superseded_by or ''}"
      )
      components.append(sig)

    digest = hashlib.sha256(";".join(components).encode("utf-8")).hexdigest()[:12]
    return f"lib_{digest}"

  def list_sources(
      self, limit: Optional[int] = None, offset: int = 0
  ) -> List[OfficialSourceMetadata]:
    if limit is not None:
      sql = """
        SELECT * FROM documents
        WHERE collection = 'official'
        ORDER BY library_added_at DESC, created_at DESC
        LIMIT ? OFFSET ?;
      """
      rows = self._db.fetchall(sql, (int(limit), int(offset)))
    else:
      sql = """
        SELECT * FROM documents
        WHERE collection = 'official'
        ORDER BY library_added_at DESC, created_at DESC;
      """
      rows = self._db.fetchall(sql)

    results: List[OfficialSourceMetadata] = []
    for r in rows:
      try:
        data = from_json(r["data"], {})
        raw_status = r["source_status"]
        status_val = raw_status if raw_status in ("current", "superseded", "unknown") else "current"
        payload = {
            "source_id": r["id"],
            "title": r["title"] or r["display_name"],
            "issuing_authority": r["issuing_authority"] or "",
            "source_url": r["source_url"],
            "publication_date": r["publication_date"],
            "effective_date": r["effective_date"],
            "series_id": r["series_id"],
            "status": status_val,
            "superseded_by": r["superseded_by"],
            "notes": r["notes"],
            "added_at": r["library_added_at"] or r["created_at"],
            "filename": r["filename"],
            "size_bytes": r["size_bytes"],
            "sha256": r["sha256"],
            "page_count": r["page_count"],
            "language": r["language"],
            "index_status": r["index_status"],
            "index_model": r["index_model"],
            "index_built_at": r["index_built_at"],
            "index_chunk_count": r["index_chunk_count"],
            "ocr_used": bool(r["ocr_used"]),
            "total_chars": r["total_chars"],
            "chunk_count": r["chunk_count"],
        }
        # Overlay any extra data fields
        payload.update({k: v for k, v in data.items() if k not in payload or payload[k] is None})
        results.append(OfficialSourceMetadata.model_validate(payload))
      except Exception as exc:
        logger.warning("Failed to parse source row %s: %s", r["id"], exc)

    return results

  def get_source(self, source_id: str) -> Optional[OfficialSourceMetadata]:
    try:
      valid_id = validate_document_id(source_id)
    except ValueError:
      return None

    row = self._db.fetchone(
        "SELECT * FROM documents WHERE id = ? AND collection = 'official';",
        (valid_id,),
    )
    if not row:
      return None

    try:
      data = from_json(row["data"], {})
      raw_status = row["source_status"]
      status_val = raw_status if raw_status in ("current", "superseded", "unknown") else "current"
      payload = {
          "source_id": row["id"],
          "title": row["title"] or row["display_name"],
          "issuing_authority": row["issuing_authority"] or "",
          "source_url": row["source_url"],
          "publication_date": row["publication_date"],
          "effective_date": row["effective_date"],
          "series_id": row["series_id"],
          "status": status_val,
          "superseded_by": row["superseded_by"],
          "notes": row["notes"],
          "added_at": row["library_added_at"] or row["created_at"],
          "filename": row["filename"],
          "size_bytes": row["size_bytes"],
          "sha256": row["sha256"],
          "page_count": row["page_count"],
          "language": row["language"],
          "index_status": row["index_status"],
          "index_model": row["index_model"],
          "index_built_at": row["index_built_at"],
          "index_chunk_count": row["index_chunk_count"],
          "ocr_used": bool(row["ocr_used"]),
          "total_chars": row["total_chars"],
          "chunk_count": row["chunk_count"],
      }
      payload.update({k: v for k, v in data.items() if k not in payload or payload[k] is None})
      return OfficialSourceMetadata.model_validate(payload)
    except Exception as exc:
      logger.warning("Failed to parse source %s: %s", source_id, exc)
      return None

  def save_source(self, metadata: OfficialSourceMetadata) -> None:
    valid_id = validate_document_id(metadata.source_id)
    payload = metadata.model_dump()
    payload["collection"] = "official"
    payload["id"] = valid_id
    payload["display_name"] = metadata.title
    payload["source_status"] = metadata.status
    payload["library_added_at"] = metadata.added_at
    self._doc_store.create_document(valid_id, payload)

  def find_by_sha256(self, sha256_hash: str) -> Optional[OfficialSourceMetadata]:
    """Locate an existing official source with the identical content hash."""
    clean_hash = str(sha256_hash).strip().lower()
    row = self._db.fetchone(
        "SELECT id FROM documents WHERE collection = 'official' AND LOWER(sha256) = ?;",
        (clean_hash,),
    )
    if not row:
      return None
    return self.get_source(row["id"])

  def delete_source(self, source_id: str) -> bool:
    try:
      valid_id = validate_document_id(source_id)
      with self._db.transaction():
        # Clear dangling superseded_by references
        self._db.execute(
            "UPDATE documents SET superseded_by = NULL WHERE superseded_by = ?;",
            (valid_id,),
        )
      # Delete document artifact and index
      return self._doc_store.delete_document(valid_id)
    except Exception as exc:
      logger.warning("Error deleting source %s: %s", source_id, exc)
      return False


# ==============================================================================
# 3. SQLITE PORTAL REGISTRY STORE
# ==============================================================================
class SqlitePortalRegistryStore:
  """SQLite-backed portal registry store replacing PortalRegistryStore."""

  def __init__(
      self,
      settings: Optional[Settings] = None,
      db: Optional[Database] = None,
      base_dir: Optional[Path] = None,
  ):
    self._settings = settings or get_settings()
    self._base_dir = base_dir or self._settings.comparisons_dir
    if db is not None:
      self._db = db
    elif base_dir is not None and Path(base_dir) != self._settings.comparisons_dir:
      test_db_path = Path(base_dir) / "test_portals.db"
      self._db = Database(db_path=test_db_path)
      from app.db.migrations.runner import MigrationRunner
      MigrationRunner(self._db).run()
    else:
      self._db = get_database()
    self._ensure_system_demo_portal()

  @property
  def _registry_file(self):
    return self._base_dir / "registry.json"

  @_registry_file.setter
  def _registry_file(self, path: Path):
    path = Path(path)
    self._base_dir = path.parent
    test_db_path = path.parent / "test_portals.db"
    self._db = Database(db_path=test_db_path)
    from app.db.migrations.runner import MigrationRunner
    MigrationRunner(self._db).run()
    self._ensure_system_demo_portal()

  def close(self) -> None:
    if hasattr(self, "_db") and self._db is not None:
      self._db.close_all()

  def _ensure_system_demo_portal(self) -> None:
    row = self._db.fetchone("SELECT id FROM portals WHERE id = ?;", (SYSTEM_DEMO_PORTAL_ID,))
    if not row:
      demo = PortalEntry(**SYSTEM_DEMO_PORTAL)
      self.save_portal(demo)

  def read_all(self) -> Dict[str, PortalEntry]:
    self._ensure_system_demo_portal()
    rows = self._db.fetchall("SELECT * FROM portals ORDER BY created_at DESC;")
    portals: Dict[str, PortalEntry] = {}
    for r in rows:
      try:
        data = from_json(r["data"], {})
        payload = {
            "id": r["id"],
            "name": r["name"],
            "name_ta": r["name_ta"],
            "url": r["url"],
            "department": r["department"],
            "scope": r["scope"],
            "description": r["description"],
            "service_types": from_json(r["service_types"], []),
            "grievance_categories": from_json(r["grievance_categories"], []),
            "coverage_area": r["coverage_area"],
            "caution_notes": r["caution_notes"],
            "domain_hint": r["domain_hint"],
            "system": bool(r["system"]),
            "kind": r["kind"],
            "status": r["status"],
            "linked_source_ids": from_json(r["linked_source_ids"], []),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        payload.update({k: v for k, v in data.items() if k not in payload or payload[k] is None})
        portals[r["id"]] = PortalEntry(**payload)
      except Exception as exc:
        logger.warning("Skipping corrupted portal %s: %s", r["id"], exc)

    return portals

  def get(self, portal_id: str) -> Optional[PortalEntry]:
    """Retrieve a single portal entry by ID."""
    return self.read_all().get(portal_id)

  def save_all(self, portals: Dict[str, PortalEntry]) -> None:
    keep_ids = list(portals.keys())
    with self._db.transaction():
      if keep_ids:
        placeholders = ",".join("?" for _ in keep_ids)
        self._db.execute(f"DELETE FROM portals WHERE id NOT IN ({placeholders}) AND system = 0;", keep_ids)
      else:
        self._db.execute("DELETE FROM portals WHERE system = 0;")
    for p in portals.values():
      self.save_portal(p)

  def delete_portal(self, portal_id: str) -> bool:
    with self._db.transaction():
      cur = self._db.execute("DELETE FROM portals WHERE id = ? AND system = 0;", (portal_id,))
      return cur.rowcount > 0

  def save_portal(self, p: PortalEntry) -> None:
    sql = """
      INSERT INTO portals (
        id, owner_id, name, name_ta, url, department, scope, description,
        service_types, grievance_categories, coverage_area, caution_notes,
        domain_hint, system, kind, status, linked_source_ids,
        created_at, updated_at, data
      ) VALUES (
        ?, 'local', ?, ?, ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?, ?,
        ?, ?, ?
      )
      ON CONFLICT(id) DO UPDATE SET
        name = excluded.name,
        name_ta = excluded.name_ta,
        url = excluded.url,
        department = excluded.department,
        scope = excluded.scope,
        description = excluded.description,
        service_types = excluded.service_types,
        grievance_categories = excluded.grievance_categories,
        coverage_area = excluded.coverage_area,
        caution_notes = excluded.caution_notes,
        domain_hint = excluded.domain_hint,
        system = excluded.system,
        kind = excluded.kind,
        status = excluded.status,
        linked_source_ids = excluded.linked_source_ids,
        updated_at = excluded.updated_at,
        data = excluded.data;
    """
    params = (
        p.id, p.name, p.name_ta, p.url, p.department or "", p.scope or "state", p.description or "",
        to_json(p.service_types), to_json(p.grievance_categories), p.coverage_area, p.caution_notes,
        p.domain_hint, 1 if p.system else 0, p.kind or "official", p.status or "active", to_json(p.linked_source_ids),
        p.created_at or utc_now_iso(), p.updated_at or utc_now_iso(), to_json(p.model_dump()),
    )
    with self._db.transaction():
      self._db.execute(sql, params)


# ==============================================================================
# 4. SQLITE COMPARISON STORE
# ==============================================================================
class SqliteComparisonStore:
  """SQLite-backed comparison store replacing ComparisonStore."""

  def __init__(
      self,
      settings: Optional[Settings] = None,
      db: Optional[Database] = None,
      base_dir: Optional[Path] = None,
  ):
    self._settings = settings or get_settings()
    self._db = db or get_database()
    self._base_dir = base_dir or self._settings.comparisons_dir

  def save_job(self, comp_id: str, job_data: Dict[str, Any], owner_id: Optional[str] = None) -> None:
    now_iso = job_data.get("created_at") or utc_now_iso()
    old_id = str(job_data.get("old_document_id", ""))
    new_id = str(job_data.get("new_document_id", ""))
    lang = str(job_data.get("language", "en")).lower()
    status = str(job_data.get("status", "processing"))
    cache_key = f"{old_id}:{new_id}:{lang}" if status in ("completed", "completed_with_warnings") else None
    resolved_owner = owner_id or job_data.get("owner_id") or "local"

    sql = """
      INSERT INTO comparisons (
        id, owner_id, old_document_id, new_document_id, language, status,
        progress, warnings, has_report, cache_key, created_at, updated_at, data
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        status = excluded.status,
        progress = excluded.progress,
        warnings = excluded.warnings,
        cache_key = excluded.cache_key,
        updated_at = excluded.updated_at,
        data = excluded.data;
    """
    params = (
        comp_id, resolved_owner, old_id, new_id, lang, status,
        job_data.get("progress"), to_json(job_data.get("warnings", [])),
        cache_key, now_iso, now_iso, to_json(job_data),
    )
    with self._db.transaction():
      self._db.execute(sql, params)

  def get_job(self, comp_id: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if owner_id is not None:
      row = self._db.fetchone("SELECT * FROM comparisons WHERE id = ? AND owner_id = ?;", (comp_id, owner_id))
    else:
      row = self._db.fetchone("SELECT * FROM comparisons WHERE id = ?;", (comp_id,))
    if not row:
      return None
    data = from_json(row["data"], {})
    data["comparison_id"] = row["id"]
    data["id"] = row["id"]
    data["owner_id"] = row["owner_id"]
    data["status"] = row["status"]
    data["progress"] = row["progress"]
    data["warnings"] = from_json(row["warnings"], [])
    data["has_report"] = bool(row["has_report"])
    return data

  def update_job(
      self,
      comp_id: str,
      status: Optional[str] = None,
      progress: Optional[str] = None,
      warnings: Optional[List[str]] = None,
      report: Optional[Dict[str, Any]] = None,
      owner_id: Optional[str] = None,
      **kwargs: Any,
  ) -> None:
    job = self.get_job(comp_id, owner_id=owner_id) or {}
    now_iso = utc_now_iso()
    created_at = job.get("created_at") or now_iso
    resolved_owner = owner_id or job.get("owner_id") or "local"

    if status is not None:
      job["status"] = status
    if progress is not None:
      job["progress"] = progress
    if warnings is not None:
      existing = job.get("warnings", [])
      job["warnings"] = list(dict.fromkeys(existing + warnings))
    if report is not None:
      job["report"] = report
      job["has_report"] = True

    for k, v in kwargs.items():
      if v is not None:
        job[k] = v

    rep = report or job.get("report") or {}
    old_id = str(job.get("old_document_id") or rep.get("old_document_id") or "")
    new_id = str(job.get("new_document_id") or rep.get("new_document_id") or "")
    lang = str(job.get("language") or rep.get("language") or "en").lower()
    cur_status = status or job.get("status", "processing")
    cache_key = f"{old_id}:{new_id}:{lang}" if cur_status in ("completed", "completed_with_warnings") else None

    sql = """
      INSERT INTO comparisons (
        id, owner_id, old_document_id, new_document_id, language, status,
        progress, warnings, has_report, cache_key, created_at, updated_at, data
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        status = excluded.status,
        progress = excluded.progress,
        warnings = excluded.warnings,
        has_report = excluded.has_report,
        cache_key = excluded.cache_key,
        updated_at = excluded.updated_at,
        data = excluded.data;
    """
    params = (
        comp_id, resolved_owner, old_id, new_id, lang, cur_status,
        job.get("progress"), to_json(job.get("warnings", [])),
        1 if job.get("has_report") else 0, cache_key, created_at, now_iso, to_json(job),
    )
    with self._db.transaction():
      self._db.execute(sql, params)

  def save_report(self, comp_id: str, report: Dict[str, Any], owner_id: Optional[str] = None) -> None:
    self.update_job(comp_id, report=report, has_report=True, owner_id=owner_id)

  def get_report(self, comp_id: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    job = self.get_job(comp_id, owner_id=owner_id)
    if job and "report" in job:
      return job["report"]
    return None

  def list_comparisons(self, limit: int = 50, offset: int = 0, owner_id: Optional[str] = None) -> List[Dict[str, Any]]:
    if owner_id is not None:
      sql = "SELECT * FROM comparisons WHERE owner_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?;"
      rows = self._db.fetchall(sql, (owner_id, limit, offset))
    else:
      sql = "SELECT * FROM comparisons ORDER BY created_at DESC LIMIT ? OFFSET ?;"
      rows = self._db.fetchall(sql, (limit, offset))
    results = []
    for r in rows:
      data = from_json(r["data"], {})
      data["comparison_id"] = r["id"]
      data["id"] = r["id"]
      data["owner_id"] = r["owner_id"]
      data["status"] = r["status"]
      data["has_report"] = bool(r["has_report"])
      data["created_at"] = r["created_at"]
      results.append(data)
    return results

  def delete_comparison(self, comp_id: str, owner_id: Optional[str] = None) -> bool:
    with self._db.transaction():
      if owner_id is not None:
        cursor = self._db.execute("DELETE FROM comparisons WHERE id = ? AND owner_id = ?;", (comp_id, owner_id))
      else:
        cursor = self._db.execute("DELETE FROM comparisons WHERE id = ?;", (comp_id,))
      return cursor.rowcount > 0

  def find_cached(self, old_doc_id: str, new_doc_id: str, language: str) -> Optional[str]:
    cache_key = f"{old_doc_id.strip()}:{new_doc_id.strip()}:{language.strip().lower()}"
    row = self._db.fetchone(
        "SELECT id FROM comparisons WHERE cache_key = ? AND status IN ('completed', 'completed_with_warnings') ORDER BY created_at DESC LIMIT 1;",
        (cache_key,),
    )
    return row["id"] if row else None


# ==============================================================================
# 5. SQLITE VERIFICATION STORE
# ==============================================================================
class SqliteVerificationStore:
  """SQLite-backed verification store replacing VerificationStore."""

  def __init__(
      self,
      settings: Optional[Settings] = None,
      db: Optional[Database] = None,
      base_dir: Optional[Path] = None,
  ):
    self._settings = settings or get_settings()
    self._db = db or get_database()
    self._base_dir = base_dir or self._settings.comparisons_dir

  def save_job(self, verification_id: str, job_data: Dict[str, Any], owner_id: Optional[str] = None) -> None:
    claim = str(job_data.get("claim", ""))
    claim_snippet = (claim[:120] + "...") if len(claim) > 120 else claim
    verdict = str(job_data.get("overall_verdict", "unverified"))
    scope = str(job_data.get("scope", "official"))
    lang = str(job_data.get("language", "en"))
    now_iso = job_data.get("created_at") or utc_now_iso()
    resolved_owner = owner_id or job_data.get("owner_id") or "local"

    sql = """
      INSERT INTO verifications (
        id, owner_id, claim_snippet, overall_verdict, scope, language,
        status, cache_key, created_at, updated_at, data
      ) VALUES (?, ?, ?, ?, ?, ?, 'completed', NULL, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        claim_snippet = excluded.claim_snippet,
        overall_verdict = excluded.overall_verdict,
        updated_at = excluded.updated_at,
        data = excluded.data;
    """
    params = (verification_id, resolved_owner, claim_snippet, verdict, scope, lang, now_iso, now_iso, to_json(job_data))
    with self._db.transaction():
      self._db.execute(sql, params)

  def get_job(self, verification_id: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if owner_id is not None:
      row = self._db.fetchone("SELECT * FROM verifications WHERE id = ? AND owner_id = ?;", (verification_id, owner_id))
    else:
      row = self._db.fetchone("SELECT * FROM verifications WHERE id = ?;", (verification_id,))
    if not row:
      return None
    return from_json(row["data"], {})

  def save_report(
      self, verification_id: str, report: VerificationReport, cache_key: Optional[str] = None, owner_id: Optional[str] = None
  ) -> None:
    job = self.get_job(verification_id, owner_id=owner_id) or {}
    job["report"] = report.model_dump()
    job["overall_verdict"] = report.overall_verdict
    claim = str(getattr(report, "original_claim_text", getattr(report, "claim", "")))
    claim_snippet = (claim[:120] + "...") if len(claim) > 120 else claim
    now_iso = utc_now_iso()

    sql = """
      UPDATE verifications SET
        claim_snippet = ?, overall_verdict = ?, cache_key = ?, updated_at = ?, data = ?
      WHERE id = ?;
    """
    params = (claim_snippet, report.overall_verdict, cache_key, now_iso, to_json(job), verification_id)
    with self._db.transaction():
      self._db.execute(sql, params)

  def get_report(self, verification_id: str, owner_id: Optional[str] = None) -> Optional[VerificationReport]:
    job = self.get_job(verification_id, owner_id=owner_id)
    if job and "report" in job:
      try:
        return VerificationReport.model_validate(job["report"])
      except Exception as exc:
        logger.warning("Corrupt verification report %s: %s", verification_id, exc)
    return None

  def lookup_cache(self, cache_key: str) -> Optional[VerificationReport]:
    row = self._db.fetchone(
        "SELECT id FROM verifications WHERE cache_key = ? ORDER BY created_at DESC LIMIT 1;",
        (cache_key,),
    )
    if row:
      return self.get_report(row["id"])
    return None

  def list_verifications(self, limit: int = 50, offset: int = 0, owner_id: Optional[str] = None) -> List[Dict[str, Any]]:
    if owner_id is not None:
      sql = "SELECT * FROM verifications WHERE owner_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?;"
      rows = self._db.fetchall(sql, (owner_id, limit, offset))
    else:
      sql = "SELECT * FROM verifications ORDER BY created_at DESC LIMIT ? OFFSET ?;"
      rows = self._db.fetchall(sql, (limit, offset))
    results = []
    for r in rows:
      results.append({
          "verification_id": r["id"],
          "claim_snippet": r["claim_snippet"],
          "overall_verdict": r["overall_verdict"],
          "created_at": r["created_at"],
          "scope": r["scope"],
          "language": r["language"],
      })
    return results

  def delete_verification(self, verification_id: str, owner_id: Optional[str] = None) -> bool:
    with self._db.transaction():
      if owner_id is not None:
        cursor = self._db.execute("DELETE FROM verifications WHERE id = ? AND owner_id = ?;", (verification_id, owner_id))
      else:
        cursor = self._db.execute("DELETE FROM verifications WHERE id = ?;", (verification_id,))
      return cursor.rowcount > 0


# ==============================================================================
# 6. SQLITE SERVICE GUIDE STORE
# ==============================================================================
class SqliteServiceGuideStore:
  """SQLite-backed public service guide store replacing ServiceGuideStore."""

  def __init__(
      self,
      settings: Optional[Settings] = None,
      db: Optional[Database] = None,
      base_dir: Optional[Path] = None,
  ):
    self._settings = settings or get_settings()
    self._db = db or get_database()
    self._base_dir = base_dir or self._settings.comparisons_dir

  def save_guide(self, guide: ServiceGuideReport, owner_id: Optional[str] = None) -> None:
    query = str(guide.query)
    query_snippet = (query[:120] + "...") if len(query) > 120 else query
    now_iso = guide.created_at or utc_now_iso()
    resolved_owner = owner_id or getattr(guide, "owner_id", None) or "local"

    sql = """
      INSERT INTO service_guides (
        id, owner_id, query_snippet, applicant_type, scope, mode,
        created_at, updated_at, data
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        query_snippet = excluded.query_snippet,
        applicant_type = excluded.applicant_type,
        scope = excluded.scope,
        mode = excluded.mode,
        updated_at = excluded.updated_at,
        data = excluded.data;
    """
    scope = getattr(guide, "scope", "all")
    params = (
        guide.id, resolved_owner, query_snippet, guide.applicant_type, scope, guide.mode,
        now_iso, now_iso, to_json(guide.model_dump()),
    )
    with self._db.transaction():
      self._db.execute(sql, params)

  def get_guide(self, guide_id: str, owner_id: Optional[str] = None) -> Optional[ServiceGuideReport]:
    if owner_id is not None:
      row = self._db.fetchone("SELECT data FROM service_guides WHERE id = ? AND owner_id = ?;", (guide_id, owner_id))
    else:
      row = self._db.fetchone("SELECT data FROM service_guides WHERE id = ?;", (guide_id,))
    if not row:
      return None
    data = from_json(row["data"], None)
    if data:
      try:
        return ServiceGuideReport(**data)
      except Exception as exc:
        logger.warning("Corrupted service guide %s: %s", guide_id, exc)
    return None

  def delete_guide(self, guide_id: str, owner_id: Optional[str] = None) -> bool:
    with self._db.transaction():
      if owner_id is not None:
        cursor = self._db.execute("DELETE FROM service_guides WHERE id = ? AND owner_id = ?;", (guide_id, owner_id))
      else:
        cursor = self._db.execute("DELETE FROM service_guides WHERE id = ?;", (guide_id,))
      return cursor.rowcount > 0

  def list_guides(self, limit: int = 20, offset: int = 0, owner_id: Optional[str] = None) -> List[ServiceGuideReport]:
    if owner_id is not None:
      sql = "SELECT data FROM service_guides WHERE owner_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?;"
      rows = self._db.fetchall(sql, (owner_id, limit, offset))
    else:
      sql = "SELECT data FROM service_guides ORDER BY created_at DESC LIMIT ? OFFSET ?;"
      rows = self._db.fetchall(sql, (limit, offset))
    results: List[ServiceGuideReport] = []
    for r in rows:
      data = from_json(r["data"])
      if data:
        try:
          results.append(ServiceGuideReport(**data))
        except Exception:
          pass
    return results


# ==============================================================================
# 7. SQLITE GRIEVANCE STORE
# ==============================================================================
class SqliteGrievanceStore:
  """SQLite-backed civic grievance store replacing GrievanceStore."""

  _active_jobs: Dict[str, Dict[str, Any]] = {}

  def __init__(
      self,
      settings: Optional[Settings] = None,
      db: Optional[Database] = None,
      base_dir: Optional[Path] = None,
  ):
    self._settings = settings or get_settings()
    self._db = db or get_database()
    self._base_dir = base_dir or self._settings.grievances_dir
    self._base_dir.mkdir(parents=True, exist_ok=True)

  def _validate_id(self, grievance_id: str) -> str:
    try:
      return str(uuid.UUID(str(grievance_id)))
    except Exception as exc:
      raise GrievanceNotFoundError(f"Invalid grievance ID: '{grievance_id}'") from exc

  def save_job(self, grievance_id: str, job_data: Dict[str, Any]) -> None:
    # Stored in-memory and alongside record in data JSON if record exists
    valid_id = self._validate_id(grievance_id)
    self._active_jobs[valid_id] = job_data
    try:
      grievance = self.get(valid_id)
      payload = grievance.model_dump()
      payload["_async_job"] = job_data
      with self._db.transaction():
        self._db.execute(
            "UPDATE grievances SET data = ?, updated_at = ? WHERE id = ?;",
            (to_json(payload), utc_now_iso(), valid_id),
        )
    except Exception:
      pass

  def get_job(self, grievance_id: str) -> Optional[Dict[str, Any]]:
    valid_id = self._validate_id(grievance_id)
    if valid_id in self._active_jobs:
      return self._active_jobs[valid_id]
    try:
      grievance = self.get(valid_id)
      return grievance.model_dump().get("_async_job")
    except Exception:
      return None

  def save(self, grievance: Grievance, owner_id: Optional[str] = None) -> Grievance:
    valid_id = self._validate_id(grievance.id)
    now_iso = grievance.created_at or utc_now_iso()
    upd_iso = grievance.updated_at or now_iso
    resolved_owner = owner_id or getattr(grievance, "owner_id", None) or "local"

    sql = """
      INSERT INTO grievances (
        id, owner_id, category, severity, state, safety_risk,
        draft_hash, demo_id, image_id, created_at, updated_at, data
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        category = excluded.category,
        severity = excluded.severity,
        state = excluded.state,
        safety_risk = excluded.safety_risk,
        draft_hash = excluded.draft_hash,
        demo_id = excluded.demo_id,
        image_id = excluded.image_id,
        updated_at = excluded.updated_at,
        data = excluded.data;
    """
    demo_id = grievance.demo.demo_id if grievance.demo else None
    image_id = grievance.image_id

    params = (
        valid_id, resolved_owner, grievance.category, grievance.severity, grievance.state,
        1 if grievance.safety_risk else 0, grievance.draft_hash,
        demo_id, image_id,
        now_iso, upd_iso, to_json(grievance.model_dump()),
    )
    with self._db.transaction():
      self._db.execute(sql, params)
      self._prune_old_drafts_if_needed()

    return grievance

  def get(self, grievance_id: str, owner_id: Optional[str] = None) -> Grievance:
    valid_id = self._validate_id(grievance_id)
    if owner_id is not None:
      row = self._db.fetchone("SELECT data FROM grievances WHERE id = ? AND owner_id = ?;", (valid_id, owner_id))
    else:
      row = self._db.fetchone("SELECT data FROM grievances WHERE id = ?;", (valid_id,))
    if not row:
      raise GrievanceNotFoundError(f"Grievance '{valid_id}' was not found.")
    data = from_json(row["data"])
    if not data or not isinstance(data, dict):
      raise GrievanceNotFoundError(f"Grievance record '{valid_id}' is corrupted.")
    try:
      return Grievance(**data)
    except Exception as exc:
      raise DocumentProcessingError(f"Failed to load grievance '{valid_id}'.") from exc

  def delete(self, grievance_id: str, owner_id: Optional[str] = None) -> bool:
    valid_id = self._validate_id(grievance_id)
    if owner_id is not None:
      chk = self._db.fetchone("SELECT id FROM grievances WHERE id = ? AND owner_id = ?;", (valid_id, owner_id))
      if not chk:
        raise GrievanceNotFoundError(f"Grievance '{valid_id}' not found.")

    self._active_jobs.pop(valid_id, None)
    # Also delete disk image if present
    gdir = self._base_dir / valid_id
    if gdir.exists():
      try:
        shutil.rmtree(gdir, ignore_errors=True)
      except Exception:
        pass

    with self._db.transaction():
      if owner_id is not None:
        cursor = self._db.execute("DELETE FROM grievances WHERE id = ? AND owner_id = ?;", (valid_id, owner_id))
      else:
        cursor = self._db.execute("DELETE FROM grievances WHERE id = ?;", (valid_id,))
      if cursor.rowcount == 0:
        raise GrievanceNotFoundError(f"Grievance '{valid_id}' not found.")
      return True

  def list_all(self, limit: Optional[int] = None, offset: int = 0, owner_id: Optional[str] = None) -> List[Grievance]:
    if owner_id is not None:
      if limit is not None:
        sql = "SELECT data FROM grievances WHERE owner_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        rows = self._db.fetchall(sql, (owner_id, int(limit), int(offset)))
      else:
        sql = "SELECT data FROM grievances WHERE owner_id = ? ORDER BY created_at DESC;"
        rows = self._db.fetchall(sql, (owner_id,))
    elif limit is not None:
      sql = "SELECT data FROM grievances ORDER BY created_at DESC LIMIT ? OFFSET ?;"
      rows = self._db.fetchall(sql, (int(limit), int(offset)))
    else:
      sql = "SELECT data FROM grievances ORDER BY created_at DESC;"
      rows = self._db.fetchall(sql)

    results: List[Grievance] = []
    for r in rows:
      data = from_json(r["data"])
      if data and isinstance(data, dict):
        try:
          results.append(Grievance(**data))
        except Exception:
          pass
    return results

  def _prune_old_drafts_if_needed(self) -> None:
    max_records = self._settings.GRIEVANCE_RECORDS_MAX
    count_row = self._db.fetchone("SELECT COUNT(*) AS total FROM grievances;")
    total = count_row["total"] if count_row else 0
    if total <= max_records:
      return

    excess = total - max_records
    # Only prune records in 'draft' state
    drafts = self._db.fetchall(
        "SELECT id FROM grievances WHERE state = 'draft' ORDER BY created_at ASC LIMIT ?;",
        (excess,),
    )
    for d in drafts:
      self.delete(d["id"])


# ==============================================================================
# 8. SQLITE BROWSER SESSION STORE
# ==============================================================================
class SqliteBrowserSessionStore:
  """SQLite-backed browser demo session store replacing BrowserSessionStore."""

  def __init__(
      self,
      settings: Optional[Settings] = None,
      db: Optional[Database] = None,
      base_dir: Optional[Path] = None,
  ):
    self._settings = settings or get_settings()
    self._db = db or get_database()
    self._base_dir = base_dir or self._settings.browser_sessions_dir
    self._base_dir.mkdir(parents=True, exist_ok=True)

  def get_session_dir(self, session_id: str) -> Path:
    valid_id = validate_document_id(session_id)
    path = self._base_dir / valid_id
    path.mkdir(parents=True, exist_ok=True)
    return path

  def get_screenshots_dir(self, session_id: str) -> Path:
    s_dir = self.get_session_dir(session_id)
    ss_dir = s_dir / "screenshots"
    ss_dir.mkdir(parents=True, exist_ok=True)
    return ss_dir

  def save_session(self, record: BrowserSessionRecord, owner_id: Optional[str] = None) -> None:
    valid_id = validate_document_id(record.session_id)
    now_iso = record.created_at or utc_now_iso()
    upd_iso = record.updated_at or now_iso
    resolved_owner = owner_id or getattr(record, "owner_id", None) or "local"

    sql = """
      INSERT INTO browser_sessions (
        session_id, owner_id, portal_id, workflow_id, status,
        current_step, total_steps, lang, actions_count, screenshots_count,
        last_screenshot_id, expires_at, created_at, updated_at, data
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(session_id) DO UPDATE SET
        status = excluded.status,
        current_step = excluded.current_step,
        actions_count = excluded.actions_count,
        screenshots_count = excluded.screenshots_count,
        last_screenshot_id = excluded.last_screenshot_id,
        updated_at = excluded.updated_at,
        data = excluded.data;
    """
    params = (
        valid_id, resolved_owner, record.portal_id, record.workflow_id, record.status,
        record.current_step, record.total_steps, record.lang,
        record.actions_count, record.screenshots_count, record.last_screenshot_id,
        record.expires_at, now_iso, upd_iso, to_json(record.model_dump()),
    )
    with self._db.transaction():
      self._db.execute(sql, params)
      self._prune_if_needed()

  def read_session(self, session_id: str, owner_id: Optional[str] = None) -> Optional[BrowserSessionRecord]:
    try:
      valid_id = validate_document_id(session_id)
    except ValueError:
      return None

    if owner_id is not None:
      row = self._db.fetchone("SELECT data FROM browser_sessions WHERE session_id = ? AND owner_id = ?;", (valid_id, owner_id))
    else:
      row = self._db.fetchone("SELECT data FROM browser_sessions WHERE session_id = ?;", (valid_id,))
    if not row:
      return None
    data = from_json(row["data"])
    if data and isinstance(data, dict):
      try:
        return BrowserSessionRecord(**data)
      except Exception:
        pass
    return None

  def list_sessions(self, limit: int = 20, offset: int = 0, owner_id: Optional[str] = None) -> List[BrowserSessionRecord]:
    if owner_id is not None:
      sql = "SELECT data FROM browser_sessions WHERE owner_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?;"
      rows = self._db.fetchall(sql, (owner_id, limit, offset))
    else:
      sql = "SELECT data FROM browser_sessions ORDER BY created_at DESC LIMIT ? OFFSET ?;"
      rows = self._db.fetchall(sql, (limit, offset))
    results: List[BrowserSessionRecord] = []
    for r in rows:
      data = from_json(r["data"])
      if data and isinstance(data, dict):
        try:
          results.append(BrowserSessionRecord(**data))
        except Exception:
          pass
    return results

  def save_screenshot(self, session_id: str, screenshot_id: str, image_bytes: bytes) -> Path:
    ss_dir = self.get_screenshots_dir(session_id)
    clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "", screenshot_id)
    out_path = ss_dir / f"{clean_id}.jpg"
    out_path.write_bytes(image_bytes)
    return out_path

  def get_screenshot_path(self, session_id: str, screenshot_id: str) -> Optional[Path]:
    try:
      ss_dir = self.get_screenshots_dir(session_id)
      clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "", screenshot_id)
      path = ss_dir / f"{clean_id}.jpg"
      if path.exists():
        return path
      return None
    except Exception:
      return None

  def delete_session(self, session_id: str, owner_id: Optional[str] = None) -> None:
    try:
      valid_id = validate_document_id(session_id)
      # Clean disk screenshots
      s_dir = self._base_dir / valid_id
      if s_dir.exists():
        shutil.rmtree(s_dir, ignore_errors=True)
      with self._db.transaction():
        if owner_id is not None:
          self._db.execute("DELETE FROM browser_sessions WHERE session_id = ? AND owner_id = ?;", (valid_id, owner_id))
        else:
          self._db.execute("DELETE FROM browser_sessions WHERE session_id = ?;", (valid_id,))
    except Exception as exc:
      logger.warning("Error deleting browser session %s: %s", session_id, exc)

  def _prune_if_needed(self) -> None:
    max_records = self._settings.BROWSER_RECORDS_MAX
    count_row = self._db.fetchone("SELECT COUNT(*) AS total FROM browser_sessions;")
    total = count_row["total"] if count_row else 0
    if total <= max_records:
      return

    excess = total - max_records
    old_sessions = self._db.fetchall(
        "SELECT session_id FROM browser_sessions ORDER BY created_at ASC LIMIT ?;",
        (excess,),
    )
    for s in old_sessions:
      self.delete_session(s["session_id"])
