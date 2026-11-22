"""System Administration, Maintenance, and Diagnostics API router."""

import datetime
import logging
from pathlib import Path
import shutil
import sqlite3
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, get_current_user, get_optional_current_user, require_admin
from app.core.config import Settings, get_settings
from app.core.errors import DocumentProcessingError
from app.db.database import Database, from_json, get_database, utc_now_iso

logger = logging.getLogger("civiclens.api.system")

router = APIRouter(prefix="/system", tags=["system"])


def _dir_size(path: Path) -> int:
  """Safely compute directory size in bytes."""
  if not path.exists():
    return 0
  total = 0
  try:
    for p in path.rglob("*"):
      if p.is_file():
        try:
          total += p.stat().st_size
        except Exception:
          pass
  except Exception:
    pass
  return total


class StorageBreakdown(BaseModel):
  uploads_bytes: int = 0
  indexes_bytes: int = 0
  official_sources_bytes: int = 0
  grievances_bytes: int = 0
  browser_sessions_bytes: int = 0
  backups_bytes: int = 0
  database_bytes: int = 0
  total_bytes: int = 0


class ProcessMemoryInfo(BaseModel):
  rss_bytes: int = 0
  rss_mb: float = 0.0
  peak_rss_bytes: int = 0
  peak_rss_mb: float = 0.0


class SystemResourcesResponse(BaseModel):
  status: str = "healthy"
  process_memory: ProcessMemoryInfo
  active_threads: int = 1
  loaded_indexes_count: int = 0
  active_browser_sessions: int = 0
  database_status: str = "operational"
  budget_limit_mb: float = 6144.0  # 6.0 GB budget ceiling
  within_budget: bool = True
  os_platform: str = ""
  python_version: str = ""


def _get_process_memory() -> Dict[str, Any]:
  """Query current process working set size safely across OS environments."""
  working_set = 0
  peak_working_set = 0
  try:
    import ctypes
    from ctypes import wintypes
    class PMC(ctypes.Structure):
      _fields_ = [
          ('cb', wintypes.DWORD),
          ('PageFaultCount', wintypes.DWORD),
          ('PeakWorkingSetSize', ctypes.c_size_t),
          ('WorkingSetSize', ctypes.c_size_t),
          ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
          ('QuotaPagedPoolUsage', ctypes.c_size_t),
          ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
          ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
          ('PagefileUsage', ctypes.c_size_t),
          ('PeakPagefileUsage', ctypes.c_size_t),
          ('PrivateUsage', ctypes.c_size_t),
      ]
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    h = kernel32.GetCurrentProcess()
    if psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb):
      working_set = int(c.WorkingSetSize)
      peak_working_set = int(c.PeakWorkingSetSize)
  except Exception:
    pass

  return {
      "rss_bytes": working_set,
      "rss_mb": round(working_set / (1024 * 1024), 2),
      "peak_rss_bytes": peak_working_set,
      "peak_rss_mb": round(peak_working_set / (1024 * 1024), 2),
  }


class SystemStatusResponse(BaseModel):
  database_state: str
  schema_version: int
  database_size_bytes: int
  wal_size_bytes: int
  last_backup_time: Optional[str]
  storage: StorageBreakdown


class SystemStatsResponse(BaseModel):
  documents_count: int = 0
  indexed_documents_count: int = 0
  official_sources_count: int = 0
  portals_count: int = 0
  comparisons_count: int = 0
  verifications_count: int = 0
  service_guides_count: int = 0
  grievances_count: int = 0
  browser_sessions_count: int = 0
  conversations_count: int = 0
  messages_count: int = 0
  tool_runs_count: int = 0


class MaintenanceRequest(BaseModel):
  remove_orphans: bool = Field(default=False)
  vacuum: bool = Field(default=False)
  activity_retention_days: Optional[int] = None


class MaintenanceResultResponse(BaseModel):
  interrupted_jobs_failed: int = 0
  expired_browser_sessions: int = 0
  activity_records_pruned: int = 0
  orphans_removed: int = 0
  vacuum_run: bool = False
  duration_ms: float = 0.0


@router.get("/status", response_model=SystemStatusResponse)
def get_system_status(
    current_user: Optional[CurrentUser] = Depends(get_optional_current_user),
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_database),
):
  """Get database health, schema version, and detailed storage breakdown."""
  db_file = settings.database_file
  db_size = db_file.stat().st_size if db_file.exists() else 0

  wal_file = db_file.with_name(db_file.name + "-wal")
  wal_size = wal_file.stat().st_size if wal_file.exists() else 0

  shm_file = db_file.with_name(db_file.name + "-shm")
  shm_size = shm_file.stat().st_size if shm_file.exists() else 0

  # Get schema version
  ver_row = db.fetchone("SELECT MAX(version) AS ver FROM schema_migrations;")
  schema_ver = ver_row["ver"] if ver_row and ver_row["ver"] is not None else 0

  # Get last backup time
  backup_dir = settings.database_backup_dir_path
  backup_files = list(backup_dir.glob("civiclens-*.db"))
  last_backup: Optional[str] = None
  if backup_files:
    backup_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    mtime = backup_files[0].stat().st_mtime
    last_backup = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc).isoformat()

  # Calculate disk sizes
  uploads_sz = _dir_size(settings.upload_dir)
  indexes_sz = _dir_size(settings.indexes_dir)
  official_sz = _dir_size(settings.official_sources_dir)
  grievances_sz = _dir_size(settings.grievances_dir)
  browser_sz = _dir_size(settings.browser_sessions_dir)
  backups_sz = _dir_size(backup_dir)
  database_sz = db_size + wal_size + shm_size
  total_sz = uploads_sz + indexes_sz + official_sz + grievances_sz + browser_sz + backups_sz + database_sz

  return SystemStatusResponse(
      database_state=db.status,
      schema_version=schema_ver,
      database_size_bytes=db_size,
      wal_size_bytes=wal_size,
      last_backup_time=last_backup,
      storage=StorageBreakdown(
          uploads_bytes=uploads_sz,
          indexes_bytes=indexes_sz,
          official_sources_bytes=official_sz,
          grievances_bytes=grievances_sz,
          browser_sessions_bytes=browser_sz,
          backups_bytes=backups_sz,
          database_bytes=database_sz,
          total_bytes=total_sz,
      ),
  )


@router.get("/stats", response_model=SystemStatsResponse)
def get_system_stats(
    current_user: Optional[CurrentUser] = Depends(get_optional_current_user),
    db: Database = Depends(get_database),
):
  """Get record counts across all application modules."""
  def _count(sql: str, params: tuple = ()) -> int:
    r = db.fetchone(sql, params)
    return r[0] if r else 0

  if current_user is None or current_user.is_admin:
    return SystemStatsResponse(
        documents_count=_count("SELECT COUNT(*) FROM documents WHERE collection = 'user';"),
        indexed_documents_count=_count("SELECT COUNT(*) FROM documents WHERE collection = 'user' AND index_status = 'indexed';"),
        official_sources_count=_count("SELECT COUNT(*) FROM documents WHERE collection = 'official';"),
        portals_count=_count("SELECT COUNT(*) FROM portals;"),
        comparisons_count=_count("SELECT COUNT(*) FROM comparisons;"),
        verifications_count=_count("SELECT COUNT(*) FROM verifications;"),
        service_guides_count=_count("SELECT COUNT(*) FROM service_guides;"),
        grievances_count=_count("SELECT COUNT(*) FROM grievances;"),
        browser_sessions_count=_count("SELECT COUNT(*) FROM browser_sessions;"),
        conversations_count=_count("SELECT COUNT(*) FROM conversations;"),
        messages_count=_count("SELECT COUNT(*) FROM messages;"),
        tool_runs_count=_count("SELECT COUNT(*) FROM tool_runs;"),
    )
  else:
    u = current_user.id
    return SystemStatsResponse(
        documents_count=_count("SELECT COUNT(*) FROM documents WHERE collection = 'user' AND owner_id = ?;", (u,)),
        indexed_documents_count=_count("SELECT COUNT(*) FROM documents WHERE collection = 'user' AND index_status = 'indexed' AND owner_id = ?;", (u,)),
        official_sources_count=_count("SELECT COUNT(*) FROM documents WHERE collection = 'official';"),
        portals_count=_count("SELECT COUNT(*) FROM portals;"),
        comparisons_count=_count("SELECT COUNT(*) FROM comparisons WHERE owner_id = ?;", (u,)),
        verifications_count=_count("SELECT COUNT(*) FROM verifications WHERE owner_id = ?;", (u,)),
        service_guides_count=_count("SELECT COUNT(*) FROM service_guides WHERE owner_id = ?;", (u,)),
        grievances_count=_count("SELECT COUNT(*) FROM grievances WHERE owner_id = ?;", (u,)),
        browser_sessions_count=_count("SELECT COUNT(*) FROM browser_sessions WHERE owner_id = ?;", (u,)),
        conversations_count=_count("SELECT COUNT(*) FROM conversations WHERE owner_id = ?;", (u,)),
        messages_count=_count("SELECT COUNT(*) FROM messages m JOIN conversations c ON m.conversation_id = c.id WHERE c.owner_id = ?;", (u,)),
        tool_runs_count=_count("SELECT COUNT(*) FROM tool_runs WHERE owner_id = ?;", (u,)),
    )


@router.post("/backup", status_code=status.HTTP_201_CREATED)
def run_backup(
    admin_user: CurrentUser = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_database),
):
  """Perform an online hot backup using SQLite Backup API and prune older backups."""
  backup_dir = settings.database_backup_dir_path
  backup_dir.mkdir(parents=True, exist_ok=True)

  ts_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
  target_file = backup_dir / f"civiclens-{ts_str}.db"

  db.backup_to(target_file)
  file_size = target_file.stat().st_size if target_file.exists() else 0

  # Prune older backups
  all_backups = sorted(backup_dir.glob("civiclens-*.db"), key=lambda p: p.stat().st_mtime)
  keep = settings.DATABASE_BACKUPS_KEEP
  if len(all_backups) > keep:
    to_delete = all_backups[: len(all_backups) - keep]
    for b in to_delete:
      try:
        b.unlink()
      except Exception as exc:
        logger.warning("Could not prune old backup %s: %s", b, exc)

  return {
      "status": "success",
      "backup_file": str(target_file.name),
      "size_bytes": file_size,
      "created_at": utc_now_iso(),
  }


@router.post("/maintenance", response_model=MaintenanceResultResponse)
def run_maintenance(
    req: MaintenanceRequest = MaintenanceRequest(),
    admin_user: CurrentUser = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_database),
):
  """Run system maintenance: resolve interrupted jobs, expire sessions, prune activity, and optimize."""
  t0 = time.perf_counter()

  # 1. Mark interrupted comparisons as failed (older than 15 mins)
  interrupted_count = 0
  cutoff_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)).isoformat()

  with db.transaction():
    c_cur = db.execute(
        "UPDATE comparisons SET status = 'failed' WHERE status IN ('running', 'staged') AND created_at < ?;",
        (cutoff_iso,),
    )
    interrupted_count += c_cur.rowcount

    v_cur = db.execute(
        "UPDATE verifications SET status = 'failed' WHERE status IN ('running', 'staged', 'searching_sources', 'analyzing_claims') AND created_at < ?;",
        (cutoff_iso,),
    )
    interrupted_count += v_cur.rowcount

  # 2. Expire old browser sessions
  now_iso = utc_now_iso()
  with db.transaction():
    b_cur = db.execute(
        "UPDATE browser_sessions SET status = 'expired' WHERE status = 'active' AND expires_at < ?;",
        (now_iso,),
    )
    expired_sessions = b_cur.rowcount

  # 3. Prune old activity
  from app.services.activity_service import get_activity_service
  pruned_activity = get_activity_service().prune_old_activity(
      retention_days=req.activity_retention_days or settings.ACTIVITY_RETENTION_DAYS
  )

  # 4. Clean orphan files if requested
  orphans_removed = 0
  if req.remove_orphans:
    # Check uploads
    rows = db.fetchall("SELECT id FROM documents;")
    known_doc_ids = {r["id"] for r in rows}
    for sub in settings.upload_dir.iterdir():
      if sub.is_dir() and sub.name not in known_doc_ids:
        try:
          shutil.rmtree(sub, ignore_errors=True)
          orphans_removed += 1
        except Exception:
          pass
    # Check indexes
    for sub in settings.indexes_dir.iterdir():
      if sub.is_dir() and sub.name not in known_doc_ids:
        try:
          shutil.rmtree(sub, ignore_errors=True)
          orphans_removed += 1
        except Exception:
          pass

  # 5. Optimize & optional Vacuum
  vacuum_run = False
  with db.transaction():
    db.execute("PRAGMA optimize;")

  if req.vacuum:
    try:
      # VACUUM cannot run inside a transaction block
      conn = db.get_connection()
      conn.execute("VACUUM;")
      vacuum_run = True
    except Exception as exc:
      logger.warning("VACUUM failed: %s", exc)

  dur_ms = (time.perf_counter() - t0) * 1000.0

  return MaintenanceResultResponse(
      interrupted_jobs_failed=interrupted_count,
      expired_browser_sessions=expired_sessions,
      activity_records_pruned=pruned_activity,
      orphans_removed=orphans_removed,
      vacuum_run=vacuum_run,
      duration_ms=round(dur_ms, 2),
  )


@router.delete("/data", status_code=status.HTTP_200_OK)
def delete_all_data(
    confirm: str = Query(..., description="Must match DELETE_ALL_CONFIRM_PHRASE or 'DELETE MY DATA'"),
    include_library: bool = Query(default=False),
    current_user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_database),
):
  """Delete citizen data. If admin, allows full system reset. If citizen, deletes own data."""
  if current_user.is_admin:
    if confirm != settings.DELETE_ALL_CONFIRM_PHRASE:
      raise HTTPException(
          status_code=400,
          detail=f"Confirmation phrase mismatch. You must provide '{settings.DELETE_ALL_CONFIRM_PHRASE}'.",
      )

    # Check active jobs
    active_jobs = db.fetchone("SELECT COUNT(*) AS c FROM comparisons WHERE status = 'running';")
    if active_jobs and active_jobs["c"] > 0:
      raise HTTPException(status_code=409, detail="Cannot delete data while comparison jobs are currently running.")

    active_verifications = db.fetchone("SELECT COUNT(*) AS c FROM verifications WHERE status IN ('running', 'searching_sources');")
    if active_verifications and active_verifications["c"] > 0:
      raise HTTPException(status_code=409, detail="Cannot delete data while fact verification jobs are running.")

    with db.transaction():
      # 1. Clear chat & activity
      db.execute("DELETE FROM tool_runs;")
      db.execute("DELETE FROM approvals;")
      db.execute("DELETE FROM activity;")
      db.execute("DELETE FROM messages;")
      db.execute("DELETE FROM conversations;")

      # 2. Clear application modules
      db.execute("DELETE FROM browser_sessions;")
      db.execute("DELETE FROM grievances;")
      db.execute("DELETE FROM service_guides;")
      db.execute("DELETE FROM form_field_explanations;")
      db.execute("DELETE FROM verifications;")
      db.execute("DELETE FROM comparisons;")

      # 3. Clear user documents
      if include_library:
        db.execute("DELETE FROM document_chunks;")
        db.execute("DELETE FROM document_pages;")
        db.execute("DELETE FROM documents;")
        # Re-seed system demo portal if needed
        db.execute("DELETE FROM portals WHERE system = 0;")
      else:
        db.execute(
            "DELETE FROM document_chunks WHERE document_id IN (SELECT id FROM documents WHERE collection = 'user');"
        )
        db.execute(
            "DELETE FROM document_pages WHERE document_id IN (SELECT id FROM documents WHERE collection = 'user');"
        )
        db.execute("DELETE FROM documents WHERE collection = 'user';")

    # Clean disk files
    try:
      for sub in settings.upload_dir.iterdir():
        if sub.is_dir():
          shutil.rmtree(sub, ignore_errors=True)
      if include_library:
        for sub in settings.official_sources_dir.iterdir():
          if sub.is_dir():
            shutil.rmtree(sub, ignore_errors=True)
      for sub in settings.indexes_dir.iterdir():
        if sub.is_dir():
          shutil.rmtree(sub, ignore_errors=True)
      for sub in settings.grievances_dir.iterdir():
        if sub.is_dir() or sub.is_file():
          if sub.name != ".gitkeep":
            if sub.is_dir():
              shutil.rmtree(sub, ignore_errors=True)
            else:
              sub.unlink()
      for sub in settings.browser_sessions_dir.iterdir():
        if sub.is_dir():
          shutil.rmtree(sub, ignore_errors=True)
    except Exception as exc:
      logger.warning("Error wiping disk directories: %s", exc)

    return {
        "status": "success",
        "message": "All citizen data wiped successfully.",
        "include_library": include_library,
        "deleted_at": utc_now_iso(),
    }
  else:
    # Citizen deleting only their own data
    if confirm not in ("DELETE MY DATA", settings.DELETE_ALL_CONFIRM_PHRASE):
      raise HTTPException(
          status_code=400,
          detail="Confirmation phrase mismatch. You must provide 'DELETE MY DATA'.",
      )

    u = current_user.id
    # Find user document IDs to clean files
    user_docs = db.fetchall("SELECT id FROM documents WHERE owner_id = ?;", (u,))
    user_doc_ids = {r["id"] for r in user_docs}

    with db.transaction():
      db.execute("DELETE FROM tool_runs WHERE owner_id = ?;", (u,))
      db.execute("DELETE FROM approvals WHERE owner_id = ?;", (u,))
      db.execute("DELETE FROM activity WHERE owner_id = ?;", (u,))
      db.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE owner_id = ?);", (u,))
      db.execute("DELETE FROM conversations WHERE owner_id = ?;", (u,))
      db.execute("DELETE FROM browser_sessions WHERE owner_id = ?;", (u,))
      db.execute("DELETE FROM grievances WHERE owner_id = ?;", (u,))
      db.execute("DELETE FROM service_guides WHERE owner_id = ?;", (u,))
      db.execute("DELETE FROM verifications WHERE owner_id = ?;", (u,))
      db.execute("DELETE FROM comparisons WHERE owner_id = ?;", (u,))
      db.execute("DELETE FROM document_chunks WHERE document_id IN (SELECT id FROM documents WHERE owner_id = ?);", (u,))
      db.execute("DELETE FROM document_pages WHERE document_id IN (SELECT id FROM documents WHERE owner_id = ?);", (u,))
      db.execute("DELETE FROM documents WHERE owner_id = ?;", (u,))

    # Clean disk files for user docs
    try:
      for doc_id in user_doc_ids:
        doc_dir = settings.upload_dir / doc_id
        if doc_dir.exists():
          shutil.rmtree(doc_dir, ignore_errors=True)
        idx_dir = settings.indexes_dir / doc_id
        if idx_dir.exists():
          shutil.rmtree(idx_dir, ignore_errors=True)
    except Exception as exc:
      logger.warning("Error removing user disk files: %s", exc)

    return {
        "status": "success",
        "message": "Your personal data has been deleted.",
        "deleted_at": utc_now_iso(),
    }


@router.get("/import-report")
def get_import_report(
    admin_user: CurrentUser = Depends(require_admin),
    db: Database = Depends(get_database),
):
  """Get legacy file store import summary."""
  rows = db.fetchall("SELECT source_kind, status, files_scanned, records_imported, notes, started_at, completed_at FROM legacy_import;")
  return {
      "imports": [dict(r) for r in rows],
      "total_kinds": len(rows),
  }


@router.get("/resources", response_model=SystemResourcesResponse)
def get_system_resources(
    current_user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_database),
):
  """Report current system resources, RAM consumption, threads, and budget compliance."""
  import sys
  import threading
  import platform

  mem = _get_process_memory()
  threads = threading.active_count()

  b_row = db.fetchone("SELECT COUNT(*) AS c FROM browser_sessions WHERE status = 'active';")
  active_sessions = b_row["c"] if b_row else 0

  indexes_count = 0
  if settings.indexes_dir.exists():
    indexes_count = len([p for p in settings.indexes_dir.iterdir() if p.is_dir()])

  within_budget = mem["rss_mb"] <= 6144.0

  return SystemResourcesResponse(
      status="healthy" if within_budget else "resource_warning",
      process_memory=ProcessMemoryInfo(**mem),
      active_threads=threads,
      loaded_indexes_count=indexes_count,
      active_browser_sessions=active_sessions,
      database_status=db.status,
      budget_limit_mb=6144.0,
      within_budget=within_budget,
      os_platform=platform.platform(),
      python_version=sys.version.split()[0],
  )
