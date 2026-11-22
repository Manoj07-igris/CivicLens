"""Civic Fact Verification API Endpoints (Module 3).

Provides asynchronous job submission, polling, report retrieval, and management
for civic fact verification against official archives and user documents.
Enforces rolling rate limiting (5 req/min) and strict privacy logging.
"""

import datetime
import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, Response, status

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import VerificationError, VerificationNotFoundError
from app.models.verification import (
    VerificationReport,
    VerifyJobResponse,
    VerifyListResponse,
    VerifyListSummary,
    VerifyRequest,
    VerifyStatusResponse,
)
from app.services.verification_service import VerificationService, get_verification_service

logger = logging.getLogger("civiclens.api.verify")

router = APIRouter(prefix="/verify", tags=["Fact Verification"])


def get_client_ip(request: Request) -> str:
  """Extract client IP from request for rate limiting."""
  forwarded = request.headers.get("X-Forwarded-For")
  if forwarded:
    return forwarded.split(",")[0].strip()
  return request.client.host if request.client else "unknown"


@router.post("", response_model=VerifyJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_claim_verification(
    body: VerifyRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
) -> VerifyJobResponse:
  """Submit a civic claim for fact verification against official sources.

  Runs as an asynchronous background job, returning HTTP 202 with verification_id.
  """
  client_key = get_client_ip(request)
  v_id, is_cache = service.start_verification(body, client_key=client_key, owner_id=current_user.id)

  now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

  if is_cache:
    # Instant completion via content-addressed cache
    cached_report = service.store.get_report(v_id, owner_id=current_user.id)
    overall_verdict = cached_report.overall_verdict if cached_report else "unverified"
    return VerifyJobResponse(
        verification_id=v_id,
        status="completed",
        stage="completed",
        message=f"Verification loaded from cache (verdict: {overall_verdict}).",
        created_at=now_iso,
    )

  # Dispatch async background worker
  background_tasks.add_task(service.execute_verification, v_id)

  return VerifyJobResponse(
      verification_id=v_id,
      status="queued",
      stage="understanding_claim",
      message="Verification job queued successfully. Background processing started.",
      created_at=now_iso,
  )


@router.get("/{verification_id}", response_model=VerifyStatusResponse)
def get_verification_status(
    verification_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
) -> VerifyStatusResponse:
  """Retrieve live progress, stage, and full report when verification completes."""
  job = service.store.get_job(verification_id, owner_id=current_user.id)
  if not job:
    raise VerificationNotFoundError(f"Verification '{verification_id}' not found.")

  report = service.store.get_report(verification_id, owner_id=current_user.id)
  status_val = job.get("status", "running")
  stage_val = job.get("stage", "running")
  progress = job.get("progress_pct", 50)
  err = job.get("error_message")

  return VerifyStatusResponse(
      verification_id=verification_id,
      status=status_val,
      stage=stage_val,
      progress_pct=progress,
      report=report,
      error_message=err,
  )


@router.post("/{verification_id}/retry-analysis", response_model=VerifyJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_verification_analysis(
    verification_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
) -> VerifyJobResponse:
  """Retry evidence analysis for an existing verification job."""
  job = service.store.get_job(verification_id, owner_id=current_user.id)
  if not job:
    raise VerificationNotFoundError(f"Verification '{verification_id}' not found.")

  job["status"] = "queued"
  job["stage"] = "analysing_evidence"
  job["progress_pct"] = 50
  job["error_message"] = None
  service.store.save_job(verification_id, job, owner_id=current_user.id)

  background_tasks.add_task(service.execute_verification, verification_id)

  now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
  return VerifyJobResponse(
      verification_id=verification_id,
      status="queued",
      stage="analysing_evidence",
      message="Verification analysis retry initiated.",
      created_at=now_iso,
  )


@router.get("", response_model=VerifyListResponse)
def list_past_verifications(
    current_user: CurrentUser = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
) -> VerifyListResponse:
  """List past fact verifications."""
  items = service.store.list_verifications(owner_id=current_user.id)
  summaries = [
      VerifyListSummary(
          verification_id=i["verification_id"],
          claim_snippet=i["claim_snippet"],
          overall_verdict=i["overall_verdict"],
          created_at=i["created_at"],
          scope=i["scope"],
          language=i["language"],
      )
      for i in items
  ]
  return VerifyListResponse(
      verifications=summaries,
      total_count=len(summaries),
  )


@router.delete("/{verification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_verification(
    verification_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
) -> Response:
  """Delete a verification report and job records."""
  deleted = service.store.delete_verification(verification_id, owner_id=current_user.id)
  if not deleted:
    raise VerificationNotFoundError(f"Verification '{verification_id}' not found.")
  return Response(status_code=status.HTTP_204_NO_CONTENT)
