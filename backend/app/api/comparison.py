"""API endpoints for Policy Change Detection (Module 2).

Provides background job initiation, status polling, report retrieval,
retry analysis, history listing, and deletion with zero-leak privacy logging.
"""

import collections
from datetime import datetime, timezone
import logging
import time
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import ComparisonError, ComparisonNotFoundError, DocumentNotFoundError, DocumentProcessingError
from app.models.common import ErrorResponse
from app.models.comparison import (
    CompareJobResponse,
    CompareListResponse,
    CompareListSummary,
    CompareRequest,
    ComparisonCounts,
    ComparisonReport,
)
from app.services.comparison_service import ComparisonService, get_comparison_service
from app.services.comparison_store import ComparisonStore, get_comparison_store
from app.services.document_store import DocumentStore, get_document_store

logger = logging.getLogger("civiclens.comparison.api")
router = APIRouter(prefix="/compare", tags=["Policy Change Detection"])


# --- In-Memory Rolling Rate Limiter (Default 3/min) ---

class ComparisonRateLimiter:
  def __init__(self, max_requests: int = 3, window_seconds: int = 60):
    self.max_requests = max_requests
    self.window_seconds = window_seconds
    self._clients: Dict[str, collections.deque] = collections.defaultdict(collections.deque)

  def check(self, client_key: str) -> None:
    now = time.time()
    queue = self._clients[client_key]
    while queue and queue[0] <= now - self.window_seconds:
      queue.popleft()
    if len(queue) >= self.max_requests:
      raise HTTPException(
          status_code=status.HTTP_429_TOO_MANY_REQUESTS,
          detail=f"Comparison rate limit exceeded ({self.max_requests} requests/minute). Please wait before running more comparisons.",
      )
    queue.append(now)

  def reset(self) -> None:
    self._clients.clear()


_rate_limiter = ComparisonRateLimiter()


def get_rate_limiter() -> ComparisonRateLimiter:
  return _rate_limiter


def reset_compare_rate_limit() -> None:
  """Test helper to reset rolling rate limiter."""
  _rate_limiter.reset()


# --- Background Worker Task ---

async def _run_comparison_background_task(
    comp_id: str,
    old_doc_id: str,
    new_doc_id: str,
    language: str,
    force: bool,
    service: ComparisonService,
    store: ComparisonStore,
) -> None:
  """Worker function executing comparison in the background."""
  t_start = time.perf_counter()
  try:
    report = await service.run_comparison(
        old_doc_id=old_doc_id,
        new_doc_id=new_doc_id,
        language=language,
        force=force,
        comparison_id=comp_id,
    )
    dur = (time.perf_counter() - t_start) * 1000.0
    # Safe privacy logging: no text or excerpts logged
    logger.info(
        "Comparison background task finished: id=%s, changes=%d, minor=%d, latency=%.2fms",
        comp_id, len(report.changes), report.minor_differences_count, dur
    )
  except Exception as exc:
    dur = (time.perf_counter() - t_start) * 1000.0
    logger.exception("Comparison background task failed for %s: %s", comp_id, exc)
    store.update_job(
        comp_id,
        status="failed",
        progress=f"Comparison failed: {str(exc)}",
        warnings=[f"Error during comparison: {str(exc)}"],
    )


# --- Endpoints ---

@router.post(
    "",
    response_model=CompareJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid documents or identical IDs"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
    summary="Start a background policy comparison between two documents",
)
async def start_comparison(
    body: CompareRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),
    service: ComparisonService = Depends(get_comparison_service),
    store: ComparisonStore = Depends(get_comparison_store),
    doc_store: DocumentStore = Depends(get_document_store),
    limiter: ComparisonRateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> CompareJobResponse:
  """Initiates policy comparison as a non-blocking background task."""
  client_ip = request.client.host if request.client else "unknown"
  limiter.max_requests = settings.COMPARE_RATE_LIMIT_PER_MINUTE
  limiter.check(client_ip)

  # Validate document existence and readiness synchronously before enqueueing
  old_meta = doc_store.get_metadata(body.old_document_id, owner_id=current_user.id)
  if not old_meta:
    raise DocumentNotFoundError(f"Old document '{body.old_document_id}' was not found.")
  new_meta = doc_store.get_metadata(body.new_document_id, owner_id=current_user.id)
  if not new_meta:
    raise DocumentNotFoundError(f"New document '{body.new_document_id}' was not found.")

  if old_meta.get("status") not in ("ready", "ready_with_warnings"):
    raise DocumentProcessingError(f"Old document '{body.old_document_id}' is not ready for comparison.")
  if new_meta.get("status") not in ("ready", "ready_with_warnings"):
    raise DocumentProcessingError(f"New document '{body.new_document_id}' is not ready for comparison.")

  # Check cache synchronously first: if cached and not forced, return completed immediately
  if not body.force:
    cached_id = store.find_cached(body.old_document_id, body.new_document_id, body.language)
    if cached_id:
      job = store.get_job(cached_id, owner_id=current_user.id)
      if job and job.get("status") in ("completed", "completed_with_warnings"):
        logger.info("Serving comparison %s directly from cache", cached_id)
        response.status_code = status.HTTP_200_OK
        rep = job.get("report")
        return CompareJobResponse(
            comparison_id=cached_id,
            status=job.get("status", "completed"),
            progress="Comparison completed (cached).",
            created_at=job.get("created_at", datetime.now(timezone.utc).isoformat()),
            report=ComparisonReport.model_validate(rep) if rep else None,
        )

  comp_id = str(uuid.uuid4())
  now_iso = datetime.now(timezone.utc).isoformat()

  initial_job = {
      "comparison_id": comp_id,
      "owner_id": current_user.id,
      "old_document_id": body.old_document_id,
      "new_document_id": body.new_document_id,
      "language": body.language,
      "status": "queued",
      "progress": "Comparison job queued...",
      "created_at": now_iso,
  }
  store.save_job(comp_id, initial_job, owner_id=current_user.id)

  background_tasks.add_task(
      _run_comparison_background_task,
      comp_id=comp_id,
      old_doc_id=body.old_document_id,
      new_doc_id=body.new_document_id,
      language=body.language,
      force=body.force,
      service=service,
      store=store,
  )

  return CompareJobResponse(
      comparison_id=comp_id,
      status="queued",
      progress="Comparison job queued...",
      created_at=now_iso,
      report=None,
  )


@router.get(
    "/{comparison_id}",
    response_model=CompareJobResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Comparison not found"},
    },
    summary="Get status, progress, and completed report of a comparison job",
)
async def get_comparison_status(
    comparison_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    store: ComparisonStore = Depends(get_comparison_store),
) -> CompareJobResponse:
  """Poll status or retrieve completed report for a comparison job."""
  job = store.get_job(comparison_id, owner_id=current_user.id)
  if not job:
    raise ComparisonNotFoundError(f"Comparison '{comparison_id}' was not found.")

  rep = job.get("report")
  return CompareJobResponse(
      comparison_id=comparison_id,
      status=job.get("status", "queued"),
      progress=job.get("progress", ""),
      created_at=job.get("created_at", ""),
      report=ComparisonReport.model_validate(rep) if rep else None,
  )


@router.post(
    "/{comparison_id}/retry-analysis",
    response_model=CompareJobResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Comparison not found"},
    },
    summary="Retry AI explanations on candidate changes that were not analyzed",
)
async def retry_comparison_analysis(
    comparison_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: ComparisonService = Depends(get_comparison_service),
    store: ComparisonStore = Depends(get_comparison_store),
) -> CompareJobResponse:
  """Retry Gemini AI explanations on unanalyzed changes."""
  job = store.get_job(comparison_id, owner_id=current_user.id)
  if not job:
    raise ComparisonNotFoundError(f"Comparison '{comparison_id}' was not found.")
  updated_report = await service.retry_failed_analysis(comparison_id)
  job = store.get_job(comparison_id, owner_id=current_user.id) or {}
  return CompareJobResponse(
      comparison_id=comparison_id,
      status=updated_report.analysis_status,
      progress="Analysis retried successfully.",
      created_at=job.get("created_at", ""),
      report=updated_report,
  )


@router.get(
    "",
    response_model=CompareListResponse,
    summary="List past comparison summaries",
)
async def list_past_comparisons(
    limit: int = 50,
    current_user: CurrentUser = Depends(get_current_user),
    store: ComparisonStore = Depends(get_comparison_store),
) -> CompareListResponse:
  """Retrieve historical policy comparisons ordered by creation date."""
  items = store.list_comparisons(limit=limit, owner_id=current_user.id)
  summaries: List[CompareListSummary] = []

  for m in items:
    rep = m.get("report") or {}
    counts_dict = rep.get("counts") or {}
    summaries.append(
        CompareListSummary(
            comparison_id=m.get("comparison_id", ""),
            old_document_id=m.get("old_document_id", ""),
            old_document_name=m.get("old_document_name", "old_document.pdf"),
            new_document_id=m.get("new_document_id", ""),
            new_document_name=m.get("new_document_name", "new_document.pdf"),
            created_at=m.get("created_at", ""),
            language=m.get("language", "en"),
            status=m.get("status", "unknown"),
            counts=ComparisonCounts.model_validate(counts_dict),
        )
    )

  return CompareListResponse(comparisons=summaries, total=len(summaries))


@router.delete(
    "/{comparison_id}",
    summary="Delete a saved comparison report and its job artifacts",
)
async def delete_comparison(
    comparison_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    store: ComparisonStore = Depends(get_comparison_store),
) -> Dict[str, Any]:
  """Permanently remove comparison record from storage."""
  deleted = store.delete_comparison(comparison_id, owner_id=current_user.id)
  if not deleted:
    raise ComparisonNotFoundError(f"Comparison '{comparison_id}' was not found.")
  return {
      "deleted": True,
      "comparison_id": comparison_id,
      "message": "Comparison report deleted successfully.",
  }
