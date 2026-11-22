"""Activity and History API router."""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, get_current_user
from app.services.activity_service import ActivityService, get_activity_service

logger = logging.getLogger("civiclens.api.activity")

router = APIRouter(prefix="/activity", tags=["activity"])


class ActivityFeedItem(BaseModel):
  id: str
  event_type: str
  ref_type: str
  ref_id: str
  title: str
  open_hint: str
  is_deleted: bool
  severity_hint: str
  created_at: str


class ActivityListResponse(BaseModel):
  items: List[ActivityFeedItem]
  total: int
  limit: int
  offset: int


class ToolRunItem(BaseModel):
  id: str
  conversation_id: Optional[str] = None
  tool_name: str
  risk_level: str
  status: str
  duration_ms: int
  summary_key: Optional[str] = None
  step_index: int
  created_at: str


class ToolRunListResponse(BaseModel):
  items: List[ToolRunItem]
  total: int
  limit: int
  offset: int


@router.get("", response_model=ActivityListResponse)
def list_activity(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    event_type: Optional[str] = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    service: ActivityService = Depends(get_activity_service),
):
  """List system activity feed with read-time resolved titles and navigation links."""
  owner_id = None if current_user.is_admin else current_user.id
  items, total = service.list_activity(limit=limit, offset=offset, event_type=event_type, owner_id=owner_id)
  return ActivityListResponse(
      items=items,
      total=total,
      limit=limit,
      offset=offset,
  )


@router.get("/tool-runs", response_model=ToolRunListResponse)
def list_tool_runs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    service: ActivityService = Depends(get_activity_service),
):
  """List safe audit history of tool runs executed by the agent (no arguments or text)."""
  items, total = service.get_tool_runs(limit=limit, offset=offset)
  return ToolRunListResponse(
      items=items,
      total=total,
      limit=limit,
      offset=offset,
  )
