"""Public Service Assistant API Endpoints (Module 4).

Provides endpoints for procedural guidance, interactive checklists,
past guides retrieval, and application form-field extraction and explanations.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, status

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.config import Settings, get_settings
from app.models.service_guide import (
    FormFieldExplainRequest,
    FormFieldExplainResponse,
    FormFieldExtractRequest,
    FormFieldExtractResponse,
    ServiceGuideListResponse,
    ServiceGuideReport,
    ServiceGuideRequest,
)
from app.services.form_field_service import (
    FormFieldService,
    get_form_field_service,
)
from app.services.public_service_service import (
    PublicServiceService,
    get_public_service_service,
)

logger = logging.getLogger("civiclens.api.services")

router = APIRouter(prefix="/services", tags=["Public Service Assistant"])


@router.post("/guide", response_model=ServiceGuideReport, status_code=status.HTTP_200_OK)
async def generate_service_guide(
    req: ServiceGuideRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: PublicServiceService = Depends(get_public_service_service),
) -> ServiceGuideReport:
  """Generate evidence-backed procedural guidance and interactive checklist."""
  client_ip = request.client.host if request.client else "unknown"
  return await service.generate_guide(req, client_key=client_ip, owner_id=current_user.id)


@router.get("/guide/{guide_id}", response_model=ServiceGuideReport)
def get_service_guide(
    guide_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: PublicServiceService = Depends(get_public_service_service),
) -> ServiceGuideReport:
  """Retrieve an existing public service guidance report."""
  return service.get_guide(guide_id, owner_id=current_user.id)


@router.post("/guide/{guide_id}/retry-analysis", response_model=ServiceGuideReport)
async def retry_service_guide(
    guide_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: PublicServiceService = Depends(get_public_service_service),
) -> ServiceGuideReport:
  """Rerun analysis for an existing public service guide."""
  existing = service.get_guide(guide_id, owner_id=current_user.id)
  return await service.retry_analysis(guide_id)


@router.get("/guides", response_model=ServiceGuideListResponse)
def list_service_guides(
    limit: int = Query(20, ge=1, le=50),
    current_user: CurrentUser = Depends(get_current_user),
    service: PublicServiceService = Depends(get_public_service_service),
) -> ServiceGuideListResponse:
  """List previously generated public service guides."""
  guides = service.list_guides(limit=limit, owner_id=current_user.id)
  return ServiceGuideListResponse(total=len(guides), guides=guides)


@router.delete("/guide/{guide_id}")
def delete_service_guide(
    guide_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: PublicServiceService = Depends(get_public_service_service),
) -> dict:
  """Delete a saved service guide."""
  service.delete_guide(guide_id, owner_id=current_user.id)
  return {"success": True, "id": guide_id}


@router.post("/form-fields/extract", response_model=FormFieldExtractResponse)
def extract_form_fields(
    req: FormFieldExtractRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: FormFieldService = Depends(get_form_field_service),
) -> FormFieldExtractResponse:
  """Detect candidate fields from user-uploaded form PDF or raw text."""
  return service.extract_fields(req)


@router.post("/form-fields/explain", response_model=FormFieldExplainResponse)
async def explain_form_fields(
    req: FormFieldExplainRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: FormFieldService = Depends(get_form_field_service),
) -> FormFieldExplainResponse:
  """Generate plain-language explanations for candidate form fields."""
  return await service.explain_fields(req)
