"""API router for Playwright Browser Automation (Controlled Demo Workflow).

Strictly bounded to local simulation on loopback demo portal.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import (
    BrowserActionError,
    BrowserApprovalRequiredError,
    BrowserNavigationBlockedError,
    BrowserSessionNotFoundError,
    PIIDetectedError,
)
from app.models.browser import (
    BrowserCapabilitiesResponse,
    BrowserFillStepRequest,
    BrowserSessionCreateRequest,
    BrowserSessionRecord,
    BrowserSubmissionPreview,
    BrowserSubmissionResult,
    BrowserSubmitRequest,
    DemoWorkflowManifest,
)
from app.services.browser_service import BrowserService, get_browser_service

router = APIRouter(prefix="/browser", tags=["Browser Demo Automation"])


@router.get(
    "/capabilities",
    response_model=BrowserCapabilitiesResponse,
    summary="Get browser automation capabilities and sandbox limits",
)
async def get_capabilities(
    current_user: CurrentUser = Depends(get_current_user),
    service: BrowserService = Depends(get_browser_service),
) -> BrowserCapabilitiesResponse:
  """Return Playwright automation availability, concurrency status, and demo portal URL."""
  return service.get_capabilities()


@router.get(
    "/manifest",
    response_model=DemoWorkflowManifest,
    summary="Get demo portal workflow manifest",
)
async def get_manifest(
    current_user: CurrentUser = Depends(get_current_user),
    service: BrowserService = Depends(get_browser_service),
) -> DemoWorkflowManifest:
  """Return structured workflow definition, form field locators, and validation rules."""
  return service.manifest


@router.get(
    "/sample-data",
    summary="Get verified fictional sample data for demo form",
)
async def get_sample_data(
    current_user: CurrentUser = Depends(get_current_user),
    service: BrowserService = Depends(get_browser_service),
) -> Dict[str, Any]:
  """Return safe fictional sample values for educational demonstration."""
  return {
      "workflow_id": service.manifest.workflow_id,
      "disclaimer": "All values are purely fictional. Never use real personal data.",
      "values": service.manifest.fictional_sample_values,
  }


@router.post(
    "/sessions",
    response_model=BrowserSessionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize controlled demo browser session",
)
async def create_session(
    payload: BrowserSessionCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: BrowserService = Depends(get_browser_service),
) -> BrowserSessionRecord:
  """Start an isolated browser session navigating strictly to the local demo portal."""
  return service.start_session(
      portal_id=payload.portal_id,
      lang=payload.lang,
      workflow_id=payload.workflow_id,
      owner_id=current_user.id,
  )


@router.get(
    "/sessions",
    response_model=List[BrowserSessionRecord],
    summary="List recent demo browser sessions",
)
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    service: BrowserService = Depends(get_browser_service),
) -> List[BrowserSessionRecord]:
  """List stored demo sessions and audit summaries."""
  return service.list_sessions(limit=limit, owner_id=None if current_user.is_admin else current_user.id)


@router.get(
    "/sessions/{session_id}",
    response_model=BrowserSessionRecord,
    summary="Get demo session status and event log",
)
async def get_session(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: BrowserService = Depends(get_browser_service),
) -> BrowserSessionRecord:
  """Retrieve status, step progress, filled values, and screenshot references for a session."""
  return service.get_session(session_id, owner_id=None if current_user.is_admin else current_user.id)


@router.post(
    "/sessions/{session_id}/fill",
    response_model=BrowserSessionRecord,
    summary="Fill fictional values into current step form fields",
)
async def fill_step(
    session_id: str,
    payload: BrowserFillStepRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: BrowserService = Depends(get_browser_service),
) -> BrowserSessionRecord:
  """Fill form step with fictional values after strict PII scanning."""
  return service.fill_step(
      session_id=session_id,
      step_index=payload.step_index,
      values=payload.values,
      fictional_confirmed=payload.fictional_confirmed,
      owner_id=None if current_user.is_admin else current_user.id,
  )


@router.post(
    "/sessions/{session_id}/next",
    response_model=BrowserSessionRecord,
    summary="Navigate to next step in demo portal",
)
async def navigate_next(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: BrowserService = Depends(get_browser_service),
) -> BrowserSessionRecord:
  """Advance to the subsequent form step."""
  return service.navigate_next(session_id, owner_id=None if current_user.is_admin else current_user.id)


@router.post(
    "/sessions/{session_id}/back",
    response_model=BrowserSessionRecord,
    summary="Navigate to previous step in demo portal",
)
async def navigate_back(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: BrowserService = Depends(get_browser_service),
) -> BrowserSessionRecord:
  """Return to the previous form step."""
  return service.navigate_back(session_id, owner_id=None if current_user.is_admin else current_user.id)


@router.get(
    "/sessions/{session_id}/preview",
    response_model=BrowserSubmissionPreview,
    summary="Get verified submission preview and canonical review hash",
)
async def get_review_preview(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: BrowserService = Depends(get_browser_service),
) -> BrowserSubmissionPreview:
  """Generate submission summary and canonical SHA-256 review hash for human approval."""
  return service.get_review_preview(session_id, owner_id=None if current_user.is_admin else current_user.id)


@router.post(
    "/sessions/{session_id}/submit",
    response_model=BrowserSubmissionResult,
    summary="Submit demo application with verified human review hash",
)
async def submit_demo(
    session_id: str,
    payload: BrowserSubmitRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: BrowserService = Depends(get_browser_service),
) -> BrowserSubmissionResult:
  """Finalize demo application simulation bound to exact verified review hash."""
  return service.submit_demo(
      session_id=session_id,
      review_hash=payload.review_hash,
      fictional_confirmed=payload.fictional_confirmed,
      owner_id=None if current_user.is_admin else current_user.id,
  )


@router.post(
    "/sessions/{session_id}/close",
    response_model=BrowserSessionRecord,
    summary="Close active demo browser session",
)
async def close_session(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: BrowserService = Depends(get_browser_service),
) -> BrowserSessionRecord:
  """Explicitly close and release the browser page and context."""
  return service.close_session(session_id, owner_id=None if current_user.is_admin else current_user.id)


@router.get(
    "/sessions/{session_id}/screenshots/{screenshot_id}",
    summary="Retrieve compressed JPEG screenshot from demo session",
)
async def get_screenshot(
    session_id: str,
    screenshot_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: BrowserService = Depends(get_browser_service),
) -> FileResponse:
  """Serve captured JPEG screenshot for visual audit and citizen confidence."""
  path = service.get_screenshot_path(session_id, screenshot_id, owner_id=None if current_user.is_admin else current_user.id)
  return FileResponse(
      path=path,
      media_type="image/jpeg",
      headers={"Cache-Control": "public, max-age=3600"},
  )
