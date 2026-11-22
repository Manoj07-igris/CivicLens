"""Activity Service for CivicLens.

Maintains the system-wide activity ledger with read-time title resolution.
Strict privacy: Never records raw user text, arguments, or document contents.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.core.config import Settings, get_settings
from app.db.database import Database, from_json, get_database, utc_now_iso

logger = logging.getLogger("civiclens.activity")


class ActivityService:
  """System activity ledger with read-time title resolution and privacy guarantees."""

  def __init__(self, settings: Optional[Settings] = None, db: Optional[Database] = None):
    self._settings = settings or get_settings()
    self._db = db or get_database()

  def record_activity(
      self,
      event_type: str,
      ref_type: str,
      ref_id: str,
      severity_hint: Optional[str] = "info",
      owner_id: str = "local",
  ) -> Optional[str]:
    """Record a system event safely.

    Never raises exceptions back to caller to prevent disrupting primary flows.
    """
    try:
      act_id = str(uuid.uuid4())
      created_at = utc_now_iso()
      sql = """
        INSERT INTO activity (id, owner_id, event_type, ref_type, ref_id, severity_hint, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
      """
      with self._db.transaction():
        self._db.execute(sql, (act_id, owner_id, str(event_type), str(ref_type), str(ref_id), severity_hint, created_at))
      return act_id
    except Exception as exc:
      logger.warning("Failed to record activity '%s' for %s/%s: %s", event_type, ref_type, ref_id, exc)
      return None

  def list_activity(
      self,
      limit: int = 20,
      offset: int = 0,
      event_type: Optional[str] = None,
      owner_id: Optional[str] = None,
  ) -> Tuple[List[Dict[str, Any]], int]:
    """List activity events with titles resolved at read time."""
    limit = max(1, min(limit, self._settings.ACTIVITY_PAGE_SIZE_MAX))
    offset = max(0, offset)

    conditions = []
    params: List[Any] = []
    if owner_id is not None:
      conditions.append("owner_id = ?")
      params.append(owner_id)
    if event_type:
      conditions.append("event_type = ?")
      params.append(event_type)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_sql = f"SELECT COUNT(*) AS total FROM activity {where_clause};"
    total_row = self._db.fetchone(count_sql, tuple(params))
    total = total_row["total"] if total_row else 0

    query_sql = f"""
      SELECT id, event_type, ref_type, ref_id, severity_hint, created_at
      FROM activity
      {where_clause}
      ORDER BY created_at DESC
      LIMIT ? OFFSET ?;
    """
    query_params = list(params) + [limit, offset]
    rows = self._db.fetchall(query_sql, tuple(query_params))

    items = []
    for r in rows:
      title, open_hint, is_deleted = self._resolve_entity_info(r["ref_type"], r["ref_id"])
      items.append({
          "id": r["id"],
          "event_type": r["event_type"],
          "ref_type": r["ref_type"],
          "ref_id": r["ref_id"],
          "title": title,
          "open_hint": open_hint,
          "is_deleted": is_deleted,
          "severity_hint": r["severity_hint"] or "info",
          "created_at": r["created_at"],
      })
    return items, total

  def _resolve_entity_info(self, ref_type: str, ref_id: str) -> Tuple[str, str, bool]:
    """Safely look up entity to resolve display title and link hint.

    Returns: (display_title, open_hint, is_deleted)
    """
    try:
      if ref_type == "document":
        row = self._db.fetchone(
            "SELECT filename, display_name, collection FROM documents WHERE id = ?;", (ref_id,)
        )
        if not row:
          return ("(deleted)", "/documents", True)
        name = row["display_name"] or row["filename"] or ref_id[:8]
        hint = "/verify" if row["collection"] == "official" else f"/documents?id={ref_id}"
        return (name, hint, False)

      elif ref_type == "comparison":
        row = self._db.fetchone("SELECT data FROM comparisons WHERE id = ?;", (ref_id,))
        if not row:
          return ("(deleted)", "/compare", True)
        data = from_json(row["data"]) or {}
        meta = data.get("meta") or data
        doc_a_name = meta.get("doc_a_filename") or meta.get("doc_a_id", "")[:8]
        doc_b_name = meta.get("doc_b_filename") or meta.get("doc_b_id", "")[:8]
        title = f"{doc_a_name} vs {doc_b_name}" if doc_a_name and doc_b_name else "Policy Comparison"
        return (title, f"/compare?id={ref_id}", False)

      elif ref_type == "verification":
        row = self._db.fetchone("SELECT claim_text, data FROM verifications WHERE id = ?;", (ref_id,))
        if not row:
          return ("(deleted)", "/verify", True)
        claim = row["claim_text"] or ""
        title = (claim[:60] + "...") if len(claim) > 60 else (claim or "Fact Verification")
        return (title, f"/verify?id={ref_id}", False)

      elif ref_type == "service_guide":
        row = self._db.fetchone("SELECT service_name, data FROM service_guides WHERE id = ?;", (ref_id,))
        if not row:
          return ("(deleted)", "/services", True)
        name = row["service_name"]
        if not name:
          data = from_json(row["data"]) or {}
          name = data.get("service_name") or "Public Service Guide"
        return (name, f"/services?guide_id={ref_id}", False)

      elif ref_type == "grievance":
        row = self._db.fetchone("SELECT category, demo_id FROM grievances WHERE id = ?;", (ref_id,))
        if not row:
          return ("(deleted)", "/grievance", True)
        cat = row["category"] or "Civic Grievance"
        d_id = row["demo_id"]
        title = f"{cat} ({d_id})" if d_id else cat
        return (title, f"/grievance?id={ref_id}", False)

      elif ref_type == "browser_session":
        row = self._db.fetchone("SELECT workflow_id, portal_id FROM browser_sessions WHERE session_id = ?;", (ref_id,))
        if not row:
          return ("(deleted)", "/services", True)
        title = f"Demo Session ({row['workflow_id']})"
        return (title, f"/services?demo_session={ref_id}", False)

      elif ref_type == "conversation":
        row = self._db.fetchone("SELECT title FROM conversations WHERE id = ?;", (ref_id,))
        if not row:
          return ("(deleted)", "/assistant", True)
        title = row["title"] or "Civic Assistant Chat"
        return (title, f"/assistant?conversation_id={ref_id}", False)

      elif ref_type == "portal":
        row = self._db.fetchone("SELECT name FROM portals WHERE id = ?;", (ref_id,))
        if not row:
          return ("(deleted)", "/services", True)
        return (row["name"] or "Portal", "/services", False)

    except Exception as exc:
      logger.warning("Error resolving entity info for %s/%s: %s", ref_type, ref_id, exc)

    return ("(unknown)", "/", True)

  def prune_old_activity(self, retention_days: Optional[int] = None) -> int:
    """Prune activity records older than retention_days."""
    days = retention_days if retention_days is not None else self._settings.ACTIVITY_RETENTION_DAYS
    cutoff_sql = f"datetime('now', '-{int(days)} days')"
    with self._db.transaction():
      cursor = self._db.execute(f"DELETE FROM activity WHERE created_at < {cutoff_sql};")
      count = cursor.rowcount
      if count > 0:
        logger.info("Pruned %d activity records older than %d days", count, days)
      return count

  def get_tool_runs(self, limit: int = 50, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
    """Retrieve safe history of agent tool runs."""
    count_row = self._db.fetchone("SELECT COUNT(*) AS total FROM tool_runs;")
    total = count_row["total"] if count_row else 0
    sql = """
      SELECT id, conversation_id, tool_name, risk_level, status, duration_ms, summary_key, step_index, created_at
      FROM tool_runs
      ORDER BY created_at DESC
      LIMIT ? OFFSET ?;
    """
    rows = self._db.fetchall(sql, (limit, offset))
    items = [dict(r) for r in rows]
    return items, total


_activity_service: Optional[ActivityService] = None

def get_activity_service() -> ActivityService:
  global _activity_service
  if _activity_service is None:
    _activity_service = ActivityService()
  return _activity_service

def set_activity_service(service: Optional[ActivityService]) -> None:
  global _activity_service
  _activity_service = service
