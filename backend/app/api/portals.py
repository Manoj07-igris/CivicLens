"""Curated Official Portal Registry API Endpoints.

Provides list, retrieve, search, and CRUD operations for verified official portals.
Write operations (create, update, delete) are gated by settings.ALLOW_PORTAL_MANAGEMENT.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, get_current_user, require_admin
from app.core.config import Settings, get_settings
from app.core.errors import PortalNotFoundError, PortalRegistryError
from app.models.portal import (
    PortalCreateRequest,
    PortalEntry,
    PortalListResponse,
    PortalMatchResult,
    PortalUpdateRequest,
)
from app.services.portal_registry import (
    PortalRegistryService,
    get_portal_registry_service,
)

logger = logging.getLogger("civiclens.api.portals")

router = APIRouter(prefix="/portals", tags=["Official Portals"])


class PortalMatchRequest(BaseModel):
  query: str = Field(..., min_length=1, max_length=600)
  linked_source_ids: Optional[List[str]] = Field(default_factory=list)
  limit: int = Field(default=3, ge=1, le=10)
  allow_demo: bool = Field(default=False)


@router.get("", response_model=PortalListResponse)
def list_portals(
    service_type: Optional[str] = Query(None, description="Filter by service type"),
    scope: Optional[str] = Query(None, description="Filter by scope (state, central, local)"),
    status_filter: Optional[str] = Query("active", alias="status", description="Filter by status (active, deprecated)"),
    kind: Optional[str] = Query(None, description="Filter by portal kind"),
    current_user: CurrentUser = Depends(get_current_user),
    service: PortalRegistryService = Depends(get_portal_registry_service),
) -> PortalListResponse:
  """List registered portals matching query filters."""
  portals = service.list_portals(
      service_type=service_type,
      scope=scope,
      status=status_filter,
      kind=kind,
  )
  return PortalListResponse(total=len(portals), portals=portals)


@router.get("/{portal_id}", response_model=PortalEntry)
def get_portal(
    portal_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: PortalRegistryService = Depends(get_portal_registry_service),
) -> PortalEntry:
  """Retrieve details of a single registered portal."""
  return service.get_portal(portal_id)


@router.post("", response_model=PortalEntry, status_code=status.HTTP_201_CREATED)
def create_portal(
    req: PortalCreateRequest,
    admin_user: CurrentUser = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    service: PortalRegistryService = Depends(get_portal_registry_service),
) -> PortalEntry:
  """Register a new official portal (Requires admin privileges)."""
  return service.create_portal(req)


@router.patch("/{portal_id}", response_model=PortalEntry)
def update_portal(
    portal_id: str,
    req: PortalUpdateRequest,
    admin_user: CurrentUser = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    service: PortalRegistryService = Depends(get_portal_registry_service),
) -> PortalEntry:
  """Update an existing registered portal (Requires admin privileges)."""
  return service.update_portal(portal_id, req)


@router.delete("/{portal_id}")
def delete_portal(
    portal_id: str,
    admin_user: CurrentUser = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    service: PortalRegistryService = Depends(get_portal_registry_service),
) -> dict:
  """Delete a portal from the registry (Requires admin privileges)."""
  service.delete_portal(portal_id)
  return {"success": True, "id": portal_id}


@router.post("/match", response_model=List[PortalMatchResult])
def match_portals(
    req: PortalMatchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: PortalRegistryService = Depends(get_portal_registry_service),
) -> List[PortalMatchResult]:
  """Match portals based on user query and cited source IDs."""
  return service.match_portals(
      query=req.query,
      linked_source_ids=req.linked_source_ids,
      limit=req.limit,
      allow_demo=req.allow_demo,
  )
