"""Filesystem storage manager for policy comparison jobs and reports.

Enforces atomic JSON writes, path traversal prevention, UUID validation,
and cached report retrieval. Designed behind a clean class interface
so Phase 15 can swap to SQLite without changing callers.
"""

import json
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import Settings, get_settings
from app.core.errors import ComparisonNotFoundError
from app.db.stores import SqliteComparisonStore

logger = logging.getLogger("civiclens.comparison.store")

# Alias ComparisonStore to SqliteComparisonStore for transparent Phase 15 SQLite persistence
ComparisonStore = SqliteComparisonStore



def validate_comparison_id(comp_id: str) -> str:
  """Validate that comparison_id is a valid UUID string to prevent path traversal."""
  try:
    val = uuid.UUID(str(comp_id).strip())
    return str(val)
  except (ValueError, AttributeError, TypeError) as exc:
    raise ValueError(f"Invalid comparison identifier format: '{comp_id}'") from exc


def atomic_write_json(file_path: Path, data: Any) -> None:
  """Write JSON data to a temporary file first, then atomically replace destination."""
  temp_path = file_path.with_suffix(".tmp")
  try:
    with open(temp_path, "w", encoding="utf-8") as f:
      json.dump(data, f, ensure_ascii=False, indent=2)
    temp_path.replace(file_path)
  except Exception as exc:
    if temp_path.exists():
      temp_path.unlink(missing_ok=True)
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


class ComparisonStore:
  """Manages persistent comparison job states, generated reports, and caching."""

  def __init__(self, settings: Optional[Settings] = None, base_dir: Optional[Path] = None):
    self._settings = settings or get_settings()
    self._base_dir = base_dir or self._settings.comparisons_dir
    self._base_dir.mkdir(parents=True, exist_ok=True)

  def _get_comp_dir(self, comp_id: str) -> Path:
    """Return validated comparison directory path."""
    valid_id = validate_comparison_id(comp_id)
    comp_dir = self._base_dir / valid_id
    comp_dir.mkdir(parents=True, exist_ok=True)
    return comp_dir

  def save_job(self, comp_id: str, job_data: Dict[str, Any]) -> None:
    """Persist initial job state."""
    comp_dir = self._get_comp_dir(comp_id)
    atomic_write_json(comp_dir / "meta.json", job_data)
    self._update_cache_index(comp_id, job_data)

  def get_job(self, comp_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve job metadata or None if not found."""
    try:
      valid_id = validate_comparison_id(comp_id)
      comp_dir = self._base_dir / valid_id
      meta = read_json_safe(comp_dir / "meta.json")
      if not meta:
        return None
      # If completed, attach report if present
      report_path = comp_dir / "report.json"
      if report_path.exists():
        meta["report"] = read_json_safe(report_path)
      return meta
    except ValueError:
      return None

  def update_job(
      self,
      comp_id: str,
      status: Optional[str] = None,
      progress: Optional[str] = None,
      warnings: Optional[List[str]] = None,
      report: Optional[Dict[str, Any]] = None,
      **kwargs: Any,
  ) -> None:
    """Atomically update comparison job progress or status."""
    comp_dir = self._get_comp_dir(comp_id)
    meta_path = comp_dir / "meta.json"
    meta = read_json_safe(meta_path) or {}

    if status is not None:
      meta["status"] = status
    if progress is not None:
      meta["progress"] = progress
    if warnings is not None:
      existing = meta.get("warnings", [])
      meta["warnings"] = list(dict.fromkeys(existing + warnings))

    for k, v in kwargs.items():
      if v is not None:
        meta[k] = v

    if report is not None:
      atomic_write_json(comp_dir / "report.json", report)
      meta["has_report"] = True

    atomic_write_json(meta_path, meta)
    self._update_cache_index(comp_id, meta)
    try:
      from app.db.stores import SqliteComparisonStore
      SqliteComparisonStore(self._settings).update_job(
          comp_id, status=status, progress=progress, warnings=warnings, report=report, **kwargs
      )
    except Exception as exc:
      logger.debug("SQLite sync for comparison update_job skipped: %s", exc)

  def save_report(self, comp_id: str, report: Dict[str, Any]) -> None:
    """Save full structured comparison report."""
    comp_dir = self._get_comp_dir(comp_id)
    atomic_write_json(comp_dir / "report.json", report)

  def get_report(self, comp_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full structured report for a comparison."""
    try:
      valid_id = validate_comparison_id(comp_id)
      comp_dir = self._base_dir / valid_id
      return read_json_safe(comp_dir / "report.json")
    except ValueError:
      return None

  def list_comparisons(self, limit: int = 50) -> List[Dict[str, Any]]:
    """Return past comparison summaries sorted by creation time descending."""
    results: List[Dict[str, Any]] = []
    if not self._base_dir.exists():
      return results

    for item in self._base_dir.iterdir():
      if item.is_dir() and item.name != ".gitkeep":
        meta = read_json_safe(item / "meta.json")
        if meta:
          results.append(meta)

    # Sort newest first
    results.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return results[:limit]

  def delete_comparison(self, comp_id: str) -> bool:
    """Remove a comparison record and its artifacts."""
    try:
      valid_id = validate_comparison_id(comp_id)
      comp_dir = self._base_dir / valid_id
      if comp_dir.exists():
        shutil.rmtree(comp_dir, ignore_errors=True)
        self._remove_from_cache_index(valid_id)
        return True
      return False
    except ValueError:
      return False

  def find_cached(
      self, old_doc_id: str, new_doc_id: str, language: str
  ) -> Optional[str]:
    """Check if an identical comparison is already completed and cached."""
    clean_old = str(old_doc_id).strip()
    clean_new = str(new_doc_id).strip()
    clean_lang = str(language).strip().lower()

    index = read_json_safe(self._base_dir / "cache_index.json") or {}
    cache_key = f"{clean_old}:{clean_new}:{clean_lang}"
    comp_id = index.get(cache_key)
    if comp_id:
      # Ensure file still exists and report is valid
      rep = self.get_report(comp_id)
      if rep and rep.get("analysis_status") in ("completed", "completed_with_warnings"):
        return comp_id
    return None

  def _update_cache_index(self, comp_id: str, meta: Dict[str, Any]) -> None:
    """Update cache index lookup map."""
    old_id = meta.get("old_document_id")
    new_id = meta.get("new_document_id")
    lang = meta.get("language")
    status = meta.get("status")

    if old_id and new_id and lang and status in ("completed", "completed_with_warnings"):
      index_path = self._base_dir / "cache_index.json"
      index = read_json_safe(index_path) or {}
      cache_key = f"{old_id}:{new_id}:{lang.lower()}"
      index[cache_key] = comp_id
      try:
        atomic_write_json(index_path, index)
      except Exception as exc:
        logger.warning("Failed to update comparison cache index: %s", exc)

  def _remove_from_cache_index(self, comp_id: str) -> None:
    """Remove a deleted comparison from cache index."""
    index_path = self._base_dir / "cache_index.json"
    index = read_json_safe(index_path) or {}
    keys_to_remove = [k for k, v in index.items() if v == comp_id]
    if keys_to_remove:
      for k in keys_to_remove:
        del index[k]
      try:
        atomic_write_json(index_path, index)
      except Exception as exc:
        logger.warning("Failed to clean comparison cache index: %s", exc)


# Alias ComparisonStore to SqliteComparisonStore for transparent Phase 15 SQLite persistence
ComparisonStore = SqliteComparisonStore

# Global singleton
_comparison_store: Optional[ComparisonStore] = None


def get_comparison_store() -> ComparisonStore:
  global _comparison_store
  if _comparison_store is None:
    _comparison_store = ComparisonStore()
  return _comparison_store


def set_comparison_store(store: Optional[ComparisonStore]) -> None:
  global _comparison_store
  _comparison_store = store
