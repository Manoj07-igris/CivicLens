"""User Preferences API router."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, get_current_user
from app.db.database import Database, get_database, utc_now_iso

logger = logging.getLogger("civiclens.api.preferences")

router = APIRouter(prefix="/preferences", tags=["preferences"])

ALLOWED_PREFERENCE_KEYS = {
    "ui_language",
    "chat_language",
    "default_verification_scope",
    "default_service_scope",
    "theme",
    "fictional_demo_confirmed",
    "preferred_language",
}


class PreferenceSetRequest(BaseModel):
  value: str = Field(..., max_length=200, description="Preference value string")


@router.get("", response_model=Dict[str, str])
def get_preferences(
    current_user: CurrentUser = Depends(get_current_user),
    db: Database = Depends(get_database),
):
  """Get all stored citizen preferences for the authenticated user."""
  rows = db.fetchall("SELECT key, value FROM preferences WHERE owner_id = ?;", (current_user.id,))
  return {r["key"]: r["value"] for r in rows}


@router.get("/{key}", response_model=Dict[str, Optional[str]])
def get_preference(
    key: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Database = Depends(get_database),
):
  """Get a single preference value by key for the authenticated user."""
  clean_key = key.strip().lower()
  if clean_key not in ALLOWED_PREFERENCE_KEYS:
    raise HTTPException(
        status_code=400,
        detail=f"Preference key '{key}' is not in the allowed list: {sorted(ALLOWED_PREFERENCE_KEYS)}",
    )
  row = db.fetchone("SELECT value FROM preferences WHERE owner_id = ? AND key = ?;", (current_user.id, clean_key))
  return {"key": clean_key, "value": row["value"] if row else None}


@router.put("/{key}", response_model=Dict[str, str])
def set_preference(
    key: str,
    req: PreferenceSetRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Database = Depends(get_database),
):
  """Set a preference value for the authenticated user."""
  clean_key = key.strip().lower()
  if clean_key not in ALLOWED_PREFERENCE_KEYS:
    raise HTTPException(
        status_code=400,
        detail=f"Preference key '{key}' is not in the allowed list: {sorted(ALLOWED_PREFERENCE_KEYS)}",
    )

  now_iso = utc_now_iso()
  sql = """
    INSERT INTO preferences (owner_id, key, value, updated_at)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(owner_id, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at;
  """
  with db.transaction():
    db.execute(sql, (current_user.id, clean_key, req.value.strip(), now_iso))

  return {"key": clean_key, "value": req.value.strip(), "updated_at": now_iso}
