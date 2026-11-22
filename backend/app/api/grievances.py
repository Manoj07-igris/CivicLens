"""API endpoints for Civic Grievance Assistant (Module 5).

Provides:
- GET /capabilities: Public limits, allowed formats, emergency contact info, categories
- POST /image: Upload and sanitize photo (strips EXIF, downscales, saves preview)
- POST /analyze: Start background analysis job (HTTP 202)
- GET /{id}: Job status / complete grievance record
- POST /{id}/retry-analysis: Retry analysis for draft
- PATCH /{id}: Review and edit draft
- POST /{id}/register-demo: Explicit citizen hash-bound demo registration
- POST /{id}/demo-advance: Simulated status progression
- GET /: List user's draft and demo complaints
- DELETE /{id}: Delete grievance record and image
- GET /{id}/image: Safe image serving
"""

import datetime
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import (
    DocumentNotFoundError,
    DocumentProcessingError,
    DocumentRateLimitError,
)
from app.core.pii_guard import ensure_no_pii
from app.models.grievance import (
    Grievance,
    GrievanceAdvanceDemoRequest,
    GrievanceAnalyzeRequest,
    GrievanceCapabilitiesResponse,
    GrievancePatchRequest,
    GrievanceRegisterDemoRequest,
    GrievanceSummaryItem,
)
from app.services.grievance_images import (
    delete_grievance_image,
    get_grievance_image_path,
    process_and_sanitize_image,
    read_and_validate_upload_stream,
    save_grievance_image,
)
from app.services.grievance_rules import (
    CATEGORY_TRANSLATION_KEYS,
    GrievanceCategory,
)
from app.services.grievance_service import (
    GrievanceService,
    get_grievance_service,
)
from app.services.grievance_store import (
    GrievanceNotFoundError,
    GrievanceStore,
    get_grievance_store,
)

logger = logging.getLogger("civiclens.api.grievance")

router = APIRouter(prefix="/grievances", tags=["civic_grievance"])

# Rate limit tracking: IP -> list of timestamps
_RATE_LIMITS: Dict[str, List[float]] = {}


def check_rate_limit(request: Request, limit: int = 6) -> None:
  client_ip = request.client.host if request.client else "unknown"
  now = time.time()
  window = 60.0
  timestamps = _RATE_LIMITS.get(client_ip, [])
  active = [t for t in timestamps if now - t < window]
  if len(active) >= limit:
    raise DocumentRateLimitError(
        f"Grievance assistant rate limit exceeded ({limit} requests/min). Please wait a moment."
    )
  active.append(now)
  _RATE_LIMITS[client_ip] = active


async def run_analysis_background_job(
    grievance_id: str,
    req: GrievanceAnalyzeRequest,
    service: GrievanceService,
    store: GrievanceStore,
    owner_id: Optional[str] = None,
) -> None:
  """Background runner updating stage progress: checking_text -> analyzing -> preparing_draft -> completed."""
  try:
    # Stage 1: checking text
    store.save_job(
        grievance_id,
        {
            "grievance_id": grievance_id,
            "status": "running",
            "stage": "checking_text",
            "progress_pct": 20,
            "error_message": None,
        },
    )

    # Stage 2: analyzing
    store.save_job(
        grievance_id,
        {
            "grievance_id": grievance_id,
            "status": "running",
            "stage": "analyzing",
            "progress_pct": 50,
            "error_message": None,
        },
    )

    grievance = await service.analyze_grievance(req, grievance_id=grievance_id, owner_id=owner_id)

    # Stage 3: preparing draft
    store.save_job(
        grievance_id,
        {
            "grievance_id": grievance_id,
            "status": "running",
            "stage": "preparing_draft",
            "progress_pct": 85,
            "error_message": None,
        },
    )

    # Completed
    store.save_job(
        grievance_id,
        {
            "grievance_id": grievance_id,
            "status": "completed",
            "stage": "completed",
            "progress_pct": 100,
            "error_message": None,
        },
    )
    logger.info("Background analysis job completed for grievance %s", grievance_id)

  except Exception as exc:
    logger.error("Background analysis job failed for grievance %s: %s", grievance_id, exc)
    store.save_job(
        grievance_id,
        {
            "grievance_id": grievance_id,
            "status": "failed",
            "stage": "failed",
            "progress_pct": 100,
            "error_message": str(exc),
        },
    )


@router.get("/capabilities", response_model=GrievanceCapabilitiesResponse)
def get_capabilities(
    settings: Settings = Depends(get_settings),
) -> GrievanceCapabilitiesResponse:
  """Return public operational capabilities and constraints for civic grievance drafting."""
  categories = [
      {"id": c.value, "label_key": CATEGORY_TRANSLATION_KEYS.get(c.value, f"grievance.categories.{c.value}")}
      for c in GrievanceCategory
  ]
  return GrievanceCapabilitiesResponse(
      min_description_chars=settings.grievance_min_description_chars,
      max_description_chars=settings.grievance_max_description_chars,
      location_max_chars=settings.grievance_location_max_chars,
      max_image_mb=settings.grievance_max_image_mb,
      image_max_dimension=settings.grievance_image_max_dimension,
      image_allowed_types=settings.grievance_image_allowed_types,
      emergency_contact_text=settings.emergency_contact_text,
      categories=categories,
      demo_id_prefix=settings.demo_id_prefix,
  )


@router.post("/image", status_code=status.HTTP_201_CREATED)
async def upload_grievance_image(
    file: UploadFile = File(...),
    request: Request = None,
    current_user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
  """Upload, validate, and sanitize a civic problem photo.

  Enforces magic bytes, downscaling, and complete stripping of EXIF/GPS metadata.
  """
  if request:
    check_rate_limit(request, limit=settings.grievance_rate_limit_per_minute)

  raw_bytes, detected_format = await read_and_validate_upload_stream(
      upload_file=file,
      max_mb=settings.grievANCE_MAX_IMAGE_MB,
  )

  sanitized_bytes, w, h = process_and_sanitize_image(raw_bytes, settings=settings)

  # Generate temporary image ID
  image_id = str(uuid.uuid4())
  save_grievance_image(image_id, sanitized_bytes, settings=settings)

  logger.info("Processed image upload: id=%s (%dx%d, format=%s) by user %s", image_id, w, h, detected_format, current_user.id)
  return {
      "image_id": image_id,
      "width": w,
      "height": h,
      "size_bytes": len(sanitized_bytes),
      "format": "jpeg",
      "metadata_removed": True,
      "notice": "All GPS coordinates and device metadata were stripped to protect your privacy.",
  }


@router.post("/analyze", status_code=status.HTTP_202_ACCEPTED)
async def analyze_grievance_start(
    req: GrievanceAnalyzeRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: GrievanceService = Depends(get_grievance_service),
    store: GrievanceStore = Depends(get_grievance_store),
    settings: Settings = Depends(get_settings),
) -> dict:
  """Submit civic problem description and optional photo for structured analysis.

  Runs as an asynchronous background job returning HTTP 202 with grievance_id.
  """
  check_rate_limit(request, limit=settings.grievance_rate_limit_per_minute)

  ensure_no_pii(req.description, field_name="description")
  if req.location_text:
    ensure_no_pii(req.location_text, field_name="location_text")
  if req.duration_text:
    ensure_no_pii(req.duration_text, field_name="duration_text")

  # If image attached, ensure it exists
  image_id = req.image_id
  if image_id:
    img_path = get_grievance_image_path(image_id, settings)
    if not img_path:
      raise DocumentNotFoundError(f"Uploaded photo '{image_id}' was not found. Please re-upload.")

  # Assign new grievance ID (if image exists, reuse image_id folder to associate)
  grievance_id = image_id or str(uuid.uuid4())

  store.save_job(
      grievance_id,
      {
          "grievance_id": grievance_id,
          "status": "queued",
          "stage": "checking_text",
          "progress_pct": 5,
          "error_message": None,
      },
  )

  background_tasks.add_task(
      run_analysis_background_job,
      grievance_id=grievance_id,
      req=req,
      service=service,
      store=store,
      owner_id=current_user.id,
  )

  logger.info("Dispatched background grievance analysis job %s for user %s", grievance_id, current_user.id)
  return {
      "grievance_id": grievance_id,
      "status": "queued",
      "stage": "checking_text",
      "progress_pct": 5,
  }


@router.get("/{id}")
def get_grievance(
    id: str,
    current_user: CurrentUser = Depends(get_current_user),
    store: GrievanceStore = Depends(get_grievance_store),
) -> dict:
  """Get grievance record or background job progress."""
  job = store.get_job(id)
  record_exists = False
  record: Optional[Grievance] = None

  try:
    record = store.get(id, owner_id=None if current_user.is_admin else current_user.id)
    record_exists = True
  except (GrievanceNotFoundError, DocumentNotFoundError):
    record_exists = False

  if record_exists and record:
    return {
        "status": "completed",
        "stage": "completed",
        "progress_pct": 100,
        "grievance": record.model_dump(),
    }

  if job:
    return {
        "status": job.get("status", "running"),
        "stage": job.get("stage", "checking_text"),
        "progress_pct": job.get("progress_pct", 10),
        "error_message": job.get("error_message"),
        "grievance": None,
    }

  raise GrievanceNotFoundError(f"Grievance '{id}' not found.")


@router.post("/{id}/retry-analysis", status_code=status.HTTP_202_ACCEPTED)
async def retry_grievance_analysis(
    id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    store: GrievanceStore = Depends(get_grievance_store),
    service: GrievanceService = Depends(get_grievance_service),
    settings: Settings = Depends(get_settings),
) -> dict:
  """Retry analysis for a draft grievance that previously fell back to rules-only."""
  check_rate_limit(request, limit=settings.grievance_rate_limit_per_minute)

  grievance = store.get(id, owner_id=None if current_user.is_admin else current_user.id)
  if grievance.state == "demo_registered":
    raise DocumentProcessingError("Cannot re-analyze a demo complaint that has already been registered.")

  req = GrievanceAnalyzeRequest(
      description=grievance.description,
      location_text=grievance.location_text,
      duration_text=grievance.duration_text,
      language_of_draft=grievance.language,  # type: ignore
      category_hint=grievance.category if grievance.category_source == "user" else None,
      image_id=grievance.image_id,
      image_consent=True if grievance.has_image else False,
  )

  store.save_job(
      id,
      {
          "grievance_id": id,
          "status": "queued",
          "stage": "checking_text",
          "progress_pct": 10,
          "error_message": None,
      },
  )

  background_tasks.add_task(
      run_analysis_background_job,
      grievance_id=id,
      req=req,
      service=service,
      store=store,
      owner_id=current_user.id,
  )

  return {
      "grievance_id": id,
      "status": "queued",
      "stage": "checking_text",
      "progress_pct": 10,
  }


@router.patch("/{id}", response_model=Grievance)
def patch_grievance(
    id: str,
    patch: GrievancePatchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: GrievanceService = Depends(get_grievance_service),
) -> Grievance:
  """Update draft fields during citizen review and recompute approved hash."""
  return service.update_grievance_draft(
      id, patch, owner_id=None if current_user.is_admin else current_user.id
  )


@router.post("/{id}/register-demo", response_model=Grievance)
def register_demo_grievance(
    id: str,
    req: GrievanceRegisterDemoRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: GrievanceService = Depends(get_grievance_service),
) -> Grievance:
  """Explicitly register a simulated DEMO complaint record bound to citizen approval and hash."""
  return service.register_demo_record(
      grievance_id=id,
      approved=req.approved,
      approved_hash=req.approved_hash,
      method="ui",
      owner_id=None if current_user.is_admin else current_user.id,
  )


@router.post("/{id}/demo-advance", response_model=Grievance)
def advance_demo_grievance_status(
    id: str,
    req: GrievanceAdvanceDemoRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: GrievanceService = Depends(get_grievance_service),
) -> Grievance:
  """Advance simulated demo complaint tracking status forward-only."""
  return service.advance_demo_status(
      id, note=req.note, owner_id=None if current_user.is_admin else current_user.id
  )


@router.get("", response_model=List[GrievanceSummaryItem])
def list_grievances(
    current_user: CurrentUser = Depends(get_current_user),
    store: GrievanceStore = Depends(get_grievance_store),
) -> List[GrievanceSummaryItem]:
  """List stored citizen grievances (drafts and registered demo complaints)."""
  records = store.list_all(owner_id=None if current_user.is_admin else current_user.id)
  results: List[GrievanceSummaryItem] = []
  for r in records:
    demo_id = r.demo.demo_id if r.demo else None
    demo_status = r.demo.status if r.demo else None
    results.append(
        GrievanceSummaryItem(
            id=r.id,
            created_at=r.created_at,
            updated_at=r.updated_at,
            category=r.category,
            severity=r.severity,
            state=r.state,
            subject_line=r.draft.subject_line,
            has_image=r.has_image,
            demo_id=demo_id,
            demo_status=demo_status,
        )
    )
  return results


@router.delete("/{id}")
def delete_grievance(
    id: str,
    current_user: CurrentUser = Depends(get_current_user),
    store: GrievanceStore = Depends(get_grievance_store),
    settings: Settings = Depends(get_settings),
) -> dict:
  """Delete a grievance record and its associated image."""
  store.delete(id, owner_id=None if current_user.is_admin else current_user.id)
  return {"deleted": True, "grievance_id": id}


@router.get("/{id}/image")
def get_grievance_image_endpoint(
    id: str,
    current_user: CurrentUser = Depends(get_current_user),
    store: GrievanceStore = Depends(get_grievance_store),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
  """Safely serve the stored, sanitized JPEG image."""
  # Enforce ownership check on image access
  try:
    store.get(id, owner_id=None if current_user.is_admin else current_user.id)
  except (GrievanceNotFoundError, DocumentNotFoundError):
    raise HTTPException(status_code=404, detail="Photo not found for this grievance.")

  img_path = get_grievance_image_path(id, settings)
  if not img_path:
    raise HTTPException(status_code=404, detail="Photo not found for this grievance.")

  return FileResponse(
      path=str(img_path),
      media_type="image/jpeg",
      headers={
          "X-Content-Type-Options": "nosniff",
          "Cache-Control": "private, no-transform, max-age=86400",
      },
  )
