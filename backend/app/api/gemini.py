"""API endpoints for Gemini AI status checks and diagnostic tests."""

import time
from collections import deque
from typing import Deque
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.models.gemini import (
    GeminiStatusResponse,
    GeminiTestResponse,
    GeminiTokenUsage,
)
from app.services.gemini_service import GeminiService, get_gemini_service

router = APIRouter(prefix="/gemini", tags=["Gemini AI"])

# Simple in-memory rate limiter for diagnostics: max 5 test calls per 60-second window
TEST_CALL_TIMESTAMPS: Deque[float] = deque()
RATE_LIMIT_WINDOW_SECONDS = 60.0
MAX_TEST_CALLS_PER_WINDOW = 5

DIAGNOSTIC_PROMPT = (
    "Provide a one-sentence greeting in both English and Tamil, "
    "introducing yourself as CivicLens, the civic intelligence assistant."
)


def check_test_rate_limit() -> None:
  """Enforce rolling window rate limit on diagnostic test calls."""
  now = time.time()
  # Evict timestamps older than window
  while TEST_CALL_TIMESTAMPS and now - TEST_CALL_TIMESTAMPS[0] > RATE_LIMIT_WINDOW_SECONDS:
    TEST_CALL_TIMESTAMPS.popleft()

  if len(TEST_CALL_TIMESTAMPS) >= MAX_TEST_CALLS_PER_WINDOW:
    retry_after = int(RATE_LIMIT_WINDOW_SECONDS - (now - TEST_CALL_TIMESTAMPS[0])) + 1
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Diagnostic test rate limit exceeded ({MAX_TEST_CALLS_PER_WINDOW} calls/min). Please try again in {retry_after}s.",
    )

  TEST_CALL_TIMESTAMPS.append(now)


def reset_test_rate_limit() -> None:
  """Helper for tests to clear the rate limit deque."""
  TEST_CALL_TIMESTAMPS.clear()


@router.get(
    "/status",
    response_model=GeminiStatusResponse,
    summary="Get Gemini configuration status",
)
async def get_gemini_status(
    settings: Settings = Depends(get_settings),
    service: GeminiService = Depends(get_gemini_service),
) -> GeminiStatusResponse:
  """Inspect whether the Gemini AI engine is configured.

  NOTE: This endpoint NEVER contacts the Gemini API and NEVER consumes quota.
  It never exposes the raw API key.
  """
  return GeminiStatusResponse(
      configured=service.is_configured(),
      model=service.active_model,
  )


@router.post(
    "/test",
    response_model=GeminiTestResponse,
    summary="Run diagnostic connectivity test with Gemini",
)
async def test_gemini_connection(
    request: Request,
    service: GeminiService = Depends(get_gemini_service),
) -> GeminiTestResponse:
  """Run an end-to-end diagnostic test with the Gemini API.

  Sends a single, lightweight greeting prompt to verify credentials,
  network latency, and token reporting.
  Rate limited to max 5 calls per minute.
  """
  check_test_rate_limit()

  # Execute minimal test prompt
  result = await service.generate_text(
      prompt_or_messages=DIAGNOSTIC_PROMPT,
      temperature=0.2,
      max_output_tokens=150,
  )

  token_usage = None
  if result.total_tokens is not None or result.prompt_tokens is not None:
    token_usage = GeminiTokenUsage(
        prompt_tokens=result.prompt_tokens,
        candidates_tokens=result.candidates_tokens,
        total_tokens=result.total_tokens,
    )

  return GeminiTestResponse(
      success=True,
      message=result.text.strip(),
      model=result.model,
      latency_ms=round(result.latency_ms, 2),
      token_usage=token_usage,
  )
