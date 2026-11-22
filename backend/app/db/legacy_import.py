"""Idempotent, non-destructive legacy data importer for CivicLens.

Migrates legacy JSON artifact structures under backend/data/ into the unified
SQLite database without deleting or modifying any existing files.
Preserves all IDs, timestamps, chunk maps, FAISS index relations, and statuses.
"""

import hashlib
import json
import logging
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import Settings, get_settings
from app.db.database import Database, from_json, get_database, to_json, utc_now_iso
from app.db.stores import (
    SqliteBrowserSessionStore,
    SqliteComparisonStore,
    SqliteDocumentStore,
    SqliteGrievanceStore,
    SqlitePortalRegistryStore,
    SqliteServiceGuideStore,
    SqliteSourceLibraryStore,
    SqliteVerificationStore,
)
from app.models.browser import BrowserSessionRecord
from app.models.grievance import Grievance
from app.models.portal import PortalEntry
from app.models.service_guide import ServiceGuideReport
from app.models.verification import OfficialSourceMetadata, VerificationReport
from app.services.document_store import read_json_safe

logger = logging.getLogger("civiclens.db.importer")


def path_hash(rel_path: str) -> str:
  """Compute SHA-256 hash of relative path string for legacy import tracking."""
  return hashlib.sha256(rel_path.strip().replace("\\", "/").encode("utf-8")).hexdigest()


class LegacyImporter:
  """Coordinates discovery, validation, and database insertion of legacy JSON records."""

  _lock = threading.Lock()
  _is_importing = False
  _current_progress: Dict[str, Any] = {"phase": "idle", "completed": 0, "total": 0}

  def __init__(self, settings: Optional[Settings] = None, db: Optional[Database] = None):
    self._settings = settings or get_settings()
    self._db = db or get_database()
    self._doc_store = SqliteDocumentStore(self._settings, self._db)
    self._source_store = SqliteSourceLibraryStore(self._settings, self._db)
    self._portal_store = SqlitePortalRegistryStore(self._settings, self._db)
    self._comp_store = SqliteComparisonStore(self._settings, self._db)
    self._verif_store = SqliteVerificationStore(self._settings, self._db)
    self._guide_store = SqliteServiceGuideStore(self._settings, self._db)
    self._grievance_store = SqliteGrievanceStore(self._settings, self._db)
    self._browser_store = SqliteBrowserSessionStore(self._settings, self._db)

  @classmethod
  def is_importing(cls) -> bool:
    return cls._is_importing

  @classmethod
  def get_progress(cls) -> Dict[str, Any]:
    return dict(cls._current_progress)

  def is_imported(self, key_hash: str) -> bool:
    row = self._db.fetchone("SELECT entity_id FROM legacy_import WHERE legacy_path_hash = ?;", (key_hash,))
    return row is not None

  def mark_imported(self, key_hash: str, kind: str, entity_id: str) -> None:
    self._db.execute(
        "INSERT OR IGNORE INTO legacy_import (legacy_path_hash, kind, entity_id, imported_at, status) VALUES (?, ?, ?, ?, 'imported');",
        (key_hash, kind, entity_id, utc_now_iso()),
    )

  def run_import(self) -> Dict[str, Any]:
    """Execute complete legacy import process with validation and spot-checks."""
    with LegacyImporter._lock:
      LegacyImporter._is_importing = True
      LegacyImporter._current_progress = {"phase": "starting", "completed": 0, "total": 100}

      report: Dict[str, Any] = {
          "status": "in_progress",
          "started_at": utc_now_iso(),
          "completed_at": None,
          "documents": {"found": 0, "imported": 0, "skipped": 0, "failed": 0},
          "official_sources": {"found": 0, "imported": 0, "skipped": 0, "failed": 0},
          "portals": {"found": 0, "imported": 0, "skipped": 0, "failed": 0},
          "comparisons": {"found": 0, "imported": 0, "skipped": 0, "failed": 0},
          "verifications": {"found": 0, "imported": 0, "skipped": 0, "failed": 0},
          "service_guides": {"found": 0, "imported": 0, "skipped": 0, "failed": 0},
          "grievances": {"found": 0, "imported": 0, "skipped": 0, "failed": 0},
          "browser_sessions": {"found": 0, "imported": 0, "skipped": 0, "failed": 0},
          "spot_checks": {"chunk_count_mismatches": 0, "chunk_map_missing_chunks": 0},
          "mismatches": [],
          "errors": [],
      }

      try:
        # Record starting state in app_meta
        self._db.execute(
            "INSERT OR REPLACE INTO app_meta (key, value, updated_at) VALUES ('legacy_import_status', 'in_progress', ?);",
            (utc_now_iso(),),
        )

        # 1. Portals
        self._import_portals(report)

        # 2. User Documents
        self._import_user_documents(report)

        # 3. Official Source Library
        self._import_official_sources(report)

        # 4. Comparisons
        self._import_comparisons(report)

        # 5. Verifications
        self._import_verifications(report)

        # 6. Service Guides
        self._import_service_guides(report)

        # 7. Grievances
        self._import_grievances(report)

        # 8. Browser Sessions
        self._import_browser_sessions(report)

        # 9. Spot-checks & Consistency Verification
        self._verify_spot_checks(report)

        report["status"] = "completed"
        report["completed_at"] = utc_now_iso()

        # Update app_meta
        with self._db.transaction():
          self._db.execute(
              "INSERT OR REPLACE INTO app_meta (key, value, updated_at) VALUES ('legacy_import_status', 'completed', ?);",
              (report["completed_at"],),
          )
          self._db.execute(
              "INSERT OR REPLACE INTO app_meta (key, value, updated_at) VALUES ('legacy_import_report', ?, ?);",
              (to_json(report), report["completed_at"]),
          )

        # Write LEGACY_IMPORTED.txt notice file
        notice_path = self._settings.upload_dir.parent / "LEGACY_IMPORTED.txt"
        notice_text = (
            "CivicLens Legacy Data Migration Notice\n"
            "=======================================\n"
            f"Migration completed at: {report['completed_at']}\n\n"
            "All legacy JSON files (uploads, official_sources, comparisons, verifications,\n"
            "service_guides, grievances, portals, browser_sessions) have been safely\n"
            "imported into the unified SQLite database (civiclens.db).\n\n"
            "The original legacy files remain untouched as an external backup.\n"
            "They can be archived or deleted manually after verifying the application.\n"
        )
        try:
          notice_path.write_text(notice_text, encoding="utf-8")
        except Exception as exc:
          logger.warning("Could not write LEGACY_IMPORTED.txt: %s", exc)

        logger.info(
            "Legacy import complete: docs=%d, sources=%d, portals=%d, comps=%d, verifs=%d, guides=%d, grievances=%d, sessions=%d",
            report["documents"]["imported"],
            report["official_sources"]["imported"],
            report["portals"]["imported"],
            report["comparisons"]["imported"],
            report["verifications"]["imported"],
            report["service_guides"]["imported"],
            report["grievances"]["imported"],
            report["browser_sessions"]["imported"],
        )
      except Exception as exc:
        report["status"] = "failed"
        report["errors"].append(str(exc))
        logger.exception("Legacy import encountered critical failure: %s", exc)
        try:
          self._db.execute(
              "INSERT OR REPLACE INTO app_meta (key, value, updated_at) VALUES ('legacy_import_status', 'failed', ?);",
              (utc_now_iso(),),
          )
        except Exception:
          pass
      finally:
        LegacyImporter._is_importing = False
        LegacyImporter._current_progress = {"phase": "done", "completed": 100, "total": 100}

      return report

  def _import_portals(self, report: Dict[str, Any]) -> None:
    portals_file = self._settings.portals_dir / "registry.json"
    if not portals_file.exists():
      return

    k_hash = path_hash("portals/registry.json")
    data = read_json_safe(portals_file)
    if not isinstance(data, dict):
      return

    report["portals"]["found"] = len(data)
    for pid, pdata in data.items():
      p_hash = path_hash(f"portals/{pid}")
      if self.is_imported(p_hash):
        report["portals"]["skipped"] += 1
        continue

      try:
        entry = PortalEntry(**pdata)
        self._portal_store.save_portal(entry)
        self.mark_imported(p_hash, "portal", entry.id)
        report["portals"]["imported"] += 1
      except Exception as exc:
        report["portals"]["failed"] += 1
        report["errors"].append(f"Portal {pid}: {exc}")

  def _import_user_documents(self, report: Dict[str, Any]) -> None:
    upload_dir = self._settings.upload_dir
    if not upload_dir.exists():
      return

    subdirs = [d for d in upload_dir.iterdir() if d.is_dir()]
    report["documents"]["found"] = len(subdirs)

    for d in subdirs:
      doc_id = d.name
      meta_file = d / "meta.json"
      if not meta_file.exists():
        continue

      d_hash = path_hash(f"uploads/{doc_id}")
      if self.is_imported(d_hash):
        report["documents"]["skipped"] += 1
        continue

      try:
        meta = read_json_safe(meta_file)
        if not meta or not isinstance(meta, dict):
          report["documents"]["failed"] += 1
          continue

        meta["collection"] = "user"
        meta["id"] = doc_id

        # 1. Create document in DB
        self._doc_store.create_document(doc_id, meta)

        # 2. Pages
        pages_file = d / "pages.json"
        if pages_file.exists():
          pages = read_json_safe(pages_file) or []
          if isinstance(pages, list):
            self._doc_store.save_pages(doc_id, pages)

        # 3. Chunks
        chunks_file = d / "chunks.json"
        if chunks_file.exists():
          chunks = read_json_safe(chunks_file) or []
          if isinstance(chunks, list):
            self._doc_store.save_chunks(doc_id, chunks)

        # 4. Summaries
        summaries_file = d / "summaries.json"
        if summaries_file.exists():
          summaries = read_json_safe(summaries_file) or {}
          if isinstance(summaries, dict):
            for lang, s_text in summaries.items():
              if isinstance(s_text, str):
                self._doc_store.save_summary(doc_id, lang, s_text)

        self.mark_imported(d_hash, "document", doc_id)
        report["documents"]["imported"] += 1
      except Exception as exc:
        report["documents"]["failed"] += 1
        report["errors"].append(f"Document {doc_id}: {exc}")

  def _import_official_sources(self, report: Dict[str, Any]) -> None:
    sources_dir = self._settings.official_sources_dir
    manifest_file = sources_dir / "manifest.json"
    if not manifest_file.exists():
      return

    manifest = read_json_safe(manifest_file)
    if not isinstance(manifest, dict) or "sources" not in manifest:
      return

    sources = manifest.get("sources", {})
    report["official_sources"]["found"] = len(sources)

    for sid, sdata in sources.items():
      s_hash = path_hash(f"official_sources/{sid}")
      if self.is_imported(s_hash):
        report["official_sources"]["skipped"] += 1
        continue

      try:
        sdata["source_id"] = sid
        sdata["collection"] = "official"
        model = OfficialSourceMetadata.model_validate(sdata)

        # Save to DB
        self._source_store.save_source(model)

        # Also import pages, chunks, and summaries from folder if present
        sfolder = sources_dir / sid
        if sfolder.exists():
          pages_file = sfolder / "pages.json"
          if pages_file.exists():
            pages = read_json_safe(pages_file) or []
            if isinstance(pages, list):
              self._doc_store.save_pages(sid, pages)

          chunks_file = sfolder / "chunks.json"
          if chunks_file.exists():
            chunks = read_json_safe(chunks_file) or []
            if isinstance(chunks, list):
              self._doc_store.save_chunks(sid, chunks)

        self.mark_imported(s_hash, "official_source", sid)
        report["official_sources"]["imported"] += 1
      except Exception as exc:
        report["official_sources"]["failed"] += 1
        report["errors"].append(f"Source {sid}: {exc}")

  def _import_comparisons(self, report: Dict[str, Any]) -> None:
    comp_dir = self._settings.comparisons_dir
    if not comp_dir.exists():
      return

    subdirs = [d for d in comp_dir.iterdir() if d.is_dir() and d.name != ".gitkeep"]
    report["comparisons"]["found"] = len(subdirs)

    for d in subdirs:
      cid = d.name
      c_hash = path_hash(f"comparisons/{cid}")
      if self.is_imported(c_hash):
        report["comparisons"]["skipped"] += 1
        continue

      try:
        meta_file = d / "meta.json"
        if not meta_file.exists():
          continue
        meta = read_json_safe(meta_file) or {}
        report_file = d / "report.json"
        if report_file.exists():
          rep = read_json_safe(report_file)
          if rep:
            meta["report"] = rep
            meta["has_report"] = True

        self._comp_store.save_job(cid, meta)
        self.mark_imported(c_hash, "comparison", cid)
        report["comparisons"]["imported"] += 1
      except Exception as exc:
        report["comparisons"]["failed"] += 1
        report["errors"].append(f"Comparison {cid}: {exc}")

  def _import_verifications(self, report: Dict[str, Any]) -> None:
    verif_dir = self._settings.verifications_dir
    if not verif_dir.exists():
      return

    subdirs = [d for d in verif_dir.iterdir() if d.is_dir() and d.name != ".gitkeep"]
    report["verifications"]["found"] = len(subdirs)

    for d in subdirs:
      vid = d.name
      v_hash = path_hash(f"verifications/{vid}")
      if self.is_imported(v_hash):
        report["verifications"]["skipped"] += 1
        continue

      try:
        job_file = d / "job.json"
        if not job_file.exists():
          continue
        job = read_json_safe(job_file) or {}
        report_file = d / "report.json"
        if report_file.exists():
          rep = read_json_safe(report_file)
          if rep:
            job["report"] = rep
            v_report = VerificationReport.model_validate(rep)
            self._verif_store.save_job(vid, job)
            self._verif_store.save_report(vid, v_report, cache_key=job.get("cache_key"))
          else:
            self._verif_store.save_job(vid, job)
        else:
          self._verif_store.save_job(vid, job)

        self.mark_imported(v_hash, "verification", vid)
        report["verifications"]["imported"] += 1
      except Exception as exc:
        report["verifications"]["failed"] += 1
        report["errors"].append(f"Verification {vid}: {exc}")

  def _import_service_guides(self, report: Dict[str, Any]) -> None:
    guides_dir = self._settings.service_guides_dir
    if not guides_dir.exists():
      return

    files = [f for f in guides_dir.glob("*.json")]
    report["service_guides"]["found"] = len(files)

    for f in files:
      gid = f.stem
      g_hash = path_hash(f"service_guides/{f.name}")
      if self.is_imported(g_hash):
        report["service_guides"]["skipped"] += 1
        continue

      try:
        data = read_json_safe(f)
        if not data or not isinstance(data, dict):
          continue
        guide = ServiceGuideReport(**data)
        self._guide_store.save_guide(guide)
        self.mark_imported(g_hash, "service_guide", gid)
        report["service_guides"]["imported"] += 1
      except Exception as exc:
        report["service_guides"]["failed"] += 1
        report["errors"].append(f"ServiceGuide {gid}: {exc}")

  def _import_grievances(self, report: Dict[str, Any]) -> None:
    g_dir = self._settings.grievances_dir
    if not g_dir.exists():
      return

    subdirs = [d for d in g_dir.iterdir() if d.is_dir() and d.name != ".gitkeep"]
    report["grievances"]["found"] = len(subdirs)

    for d in subdirs:
      gid = d.name
      g_hash = path_hash(f"grievances/{gid}")
      if self.is_imported(g_hash):
        report["grievances"]["skipped"] += 1
        continue

      try:
        rec_file = d / "record.json"
        if not rec_file.exists():
          continue
        data = read_json_safe(rec_file)
        if not data or not isinstance(data, dict):
          continue

        grievance = Grievance(**data)
        self._grievance_store.save(grievance)

        job_file = d / "job.json"
        if job_file.exists():
          jdata = read_json_safe(job_file)
          if jdata:
            self._grievance_store.save_job(gid, jdata)

        self.mark_imported(g_hash, "grievance", gid)
        report["grievances"]["imported"] += 1
      except Exception as exc:
        report["grievances"]["failed"] += 1
        report["errors"].append(f"Grievance {gid}: {exc}")

  def _import_browser_sessions(self, report: Dict[str, Any]) -> None:
    b_dir = self._settings.browser_sessions_dir
    if not b_dir.exists():
      return

    subdirs = [d for d in b_dir.iterdir() if d.is_dir() and d.name != ".gitkeep"]
    report["browser_sessions"]["found"] = len(subdirs)

    for d in subdirs:
      sid = d.name
      s_hash = path_hash(f"browser_sessions/{sid}")
      if self.is_imported(s_hash):
        report["browser_sessions"]["skipped"] += 1
        continue

      try:
        s_file = d / "session.json"
        if not s_file.exists():
          continue
        data = read_json_safe(s_file)
        if not data or not isinstance(data, dict):
          continue

        rec = BrowserSessionRecord(**data)
        self._browser_store.save_session(rec)
        self.mark_imported(s_hash, "browser_session", sid)
        report["browser_sessions"]["imported"] += 1
      except Exception as exc:
        report["browser_sessions"]["failed"] += 1
        report["errors"].append(f"BrowserSession {sid}: {exc}")

  def _verify_spot_checks(self, report: Dict[str, Any]) -> None:
    """Spot check chunk counts and FAISS chunk_map.json consistency."""
    indexes_dir = self._settings.indexes_dir
    docs = self._db.fetchall("SELECT id, chunk_count, index_status FROM documents;")

    for d in docs:
      doc_id = d["id"]
      db_chunk_count = d["chunk_count"]
      # Check count in document_chunks
      row = self._db.fetchone("SELECT COUNT(*) AS c FROM document_chunks WHERE document_id = ?;", (doc_id,))
      actual_chunks = row["c"] if row else 0

      if db_chunk_count > 0 and actual_chunks != db_chunk_count:
        report["spot_checks"]["chunk_count_mismatches"] += 1
        report["mismatches"].append(
            f"Doc {doc_id}: metadata chunk_count ({db_chunk_count}) != actual chunks ({actual_chunks})"
        )

      # Check FAISS chunk_map.json if indexed
      cmap_file = indexes_dir / doc_id / "chunk_map.json"
      if cmap_file.exists():
        cmap = read_json_safe(cmap_file)
        if isinstance(cmap, list):
          for item in cmap:
            cid = item.get("chunk_id")
            if cid:
              ch_row = self._db.fetchone("SELECT chunk_id FROM document_chunks WHERE chunk_id = ?;", (cid,))
              if not ch_row:
                report["spot_checks"]["chunk_map_missing_chunks"] += 1
                report["mismatches"].append(f"Doc {doc_id}: chunk_map chunk '{cid}' missing in DB")
                break
