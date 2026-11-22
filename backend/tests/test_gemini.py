"""Comprehensive test suite for Gemini AI service, endpoints, and error resilience.

All standard unit and integration tests use mocked Gemini clients to avoid
consuming live API quota or requiring a live network connection.
One optional test is marked for manual end-to-end verification with a real API key.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))

from app.api.gemini import reset_test_rate_limit
from app.core.config import Settings
from app.main import app
from app.services.gemini_service import (
    GeminiAPIError,
    GeminiError,
    GeminiNotConfiguredError,
    GeminiRateLimitError,
    GeminiResult,
    GeminiSafetyBlockedError,
    GeminiService,
    GeminiStructuredOutputError,
    GeminiTimeoutError,
    set_gemini_service,
)

try:
  from google.genai import errors as genai_errors
  from google.genai import types
except ImportError:
  genai_errors = None
  types = None


class SampleCivicIntent(BaseModel):
  """Sample schema for testing structured output parsing."""
  topic: str = Field(..., description="The civic topic identified")
  urgency: str = Field(..., description="High, Medium, or Low")
  requires_action: bool = Field(..., description="Whether citizen action is needed")


# --- Unit Tests for GeminiService ---

@pytest.fixture(autouse=True)
def cleanup_service():
  """Reset shared service and rate limits before each test."""
  reset_test_rate_limit()
  set_gemini_service(None)
  yield
  set_gemini_service(None)
  reset_test_rate_limit()


def create_mock_candidate(text: str = "Test response", finish_reason: str = "STOP"):
  """Build a mock response candidate resembling google-genai structures."""
  candidate = MagicMock()
  candidate.finish_reason = finish_reason
  part = MagicMock()
  part.text = text
  part.function_call = None
  candidate.content = MagicMock(parts=[part])
  return candidate


def create_mock_response(text: str = "Test response", finish_reason: str = "STOP", prompt_tokens: int = 15, candidates_tokens: int = 10):
  """Build a mock GenerateContentResponse."""
  response = MagicMock()
  response.text = text
  response.candidates = [create_mock_candidate(text, finish_reason)]
  usage = MagicMock()
  usage.prompt_token_count = prompt_tokens
  usage.candidates_token_count = candidates_tokens
  usage.total_token_count = prompt_tokens + candidates_tokens
  response.usage_metadata = usage
  response.parsed = None
  return response


@pytest.mark.anyio
async def test_generate_text_success():
  """Verify successful text generation returning structured GeminiResult."""
  mock_client = MagicMock()
  mock_resp = create_mock_response(text="CivicLens summary: Citizen benefits available.")
  mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

  settings = Settings(GEMINI_API_KEY="valid_mock_key", GEMINI_MODEL="gemini-2.5-flash")
  service = GeminiService(settings=settings, client=mock_client)

  result = await service.generate_text("Summarize the policy")
  assert isinstance(result, GeminiResult)
  assert "Citizen benefits" in result.text
  assert result.model == "gemini-2.5-flash"
  assert result.finish_reason == "STOP"
  assert result.prompt_tokens == 15
  assert result.candidates_tokens == 10
  assert result.total_tokens == 25
  assert result.latency_ms > 0


@pytest.mark.anyio
async def test_missing_api_key_raises_not_configured():
  """Verify missing or placeholder API key raises GeminiNotConfiguredError."""
  settings = Settings(GEMINI_API_KEY="", GEMINI_MODEL="gemini-2.5-flash")
  service = GeminiService(settings=settings)

  assert not service.is_configured()
  with pytest.raises(GeminiNotConfiguredError) as exc_info:
    await service.generate_text("Hello")
  assert exc_info.value.code == "AI_NOT_CONFIGURED"
  assert exc_info.value.status_code == 503


@pytest.mark.anyio
async def test_retry_on_429_then_succeeds():
  """Verify retry logic on 429 rate limit recovers if subsequent attempt succeeds."""
  if genai_errors is None:
    pytest.skip("google-genai SDK not available")

  mock_client = MagicMock()
  error_429 = genai_errors.APIError(429, {"error": {"message": "Resource exhausted"}})
  success_resp = create_mock_response(text="Recovered after rate limit")

  mock_client.aio.models.generate_content = AsyncMock(side_effect=[error_429, success_resp])

  settings = Settings(GEMINI_API_KEY="mock_key", GEMINI_MAX_RETRIES=2)
  service = GeminiService(settings=settings, client=mock_client)

  with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
    result = await service.generate_text("Prompt needing retry")
    assert result.text == "Recovered after rate limit"
    assert mock_sleep.await_count == 1
    assert mock_client.aio.models.generate_content.await_count == 2


@pytest.mark.anyio
async def test_retry_on_429_exhausted_raises_ratelimit_error():
  """Verify persistent 429 exhaust retries and raises GeminiRateLimitError."""
  if genai_errors is None:
    pytest.skip("google-genai SDK not available")

  mock_client = MagicMock()
  error_429 = genai_errors.APIError(429, {"error": {"message": "Quota exceeded"}})
  mock_client.aio.models.generate_content = AsyncMock(side_effect=error_429)

  settings = Settings(GEMINI_API_KEY="mock_key", GEMINI_MAX_RETRIES=2)
  service = GeminiService(settings=settings, client=mock_client)

  with patch("asyncio.sleep", new_callable=AsyncMock):
    with pytest.raises(GeminiRateLimitError) as exc_info:
      await service.generate_text("Prompt that fails")
    assert exc_info.value.code == "AI_RATE_LIMITED"
    assert exc_info.value.status_code == 429
    # Initial attempt + 2 retries = 3 total attempts
    assert mock_client.aio.models.generate_content.await_count == 3


@pytest.mark.anyio
async def test_timeout_raises_gemini_timeout_error():
  """Verify request timeouts raise GeminiTimeoutError."""
  mock_client = MagicMock()
  mock_client.aio.models.generate_content = AsyncMock(side_effect=asyncio.TimeoutError())

  settings = Settings(GEMINI_API_KEY="mock_key", GEMINI_MAX_RETRIES=1)
  service = GeminiService(settings=settings, client=mock_client)

  with patch("asyncio.sleep", new_callable=AsyncMock):
    with pytest.raises(GeminiTimeoutError) as exc_info:
      await service.generate_text("Prompt that hangs", timeout_seconds=1)
    assert exc_info.value.code == "AI_TIMEOUT"
    assert exc_info.value.status_code == 504


@pytest.mark.anyio
async def test_safety_blocked_raises_safety_error():
  """Verify responses flagged as SAFETY raise GeminiSafetyBlockedError."""
  mock_client = MagicMock()
  blocked_resp = create_mock_response(text="", finish_reason="SAFETY")
  mock_client.aio.models.generate_content = AsyncMock(return_value=blocked_resp)

  settings = Settings(GEMINI_API_KEY="mock_key")
  service = GeminiService(settings=settings, client=mock_client)

  with pytest.raises(GeminiSafetyBlockedError) as exc_info:
    await service.generate_text("Prompt producing blocked output")
  assert exc_info.value.code == "AI_SAFETY_BLOCKED"
  assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_generate_structured_valid():
  """Verify valid structured JSON is parsed and returned as typed Pydantic model."""
  mock_client = MagicMock()
  valid_json = '{"topic": "Welfare Scheme", "urgency": "High", "requires_action": true}'
  mock_resp = create_mock_response(text=valid_json)
  mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

  settings = Settings(GEMINI_API_KEY="mock_key")
  service = GeminiService(settings=settings, client=mock_client)

  parsed = await service.generate_structured("Classify intent", response_model=SampleCivicIntent)
  assert isinstance(parsed, SampleCivicIntent)
  assert parsed.topic == "Welfare Scheme"
  assert parsed.urgency == "High"
  assert parsed.requires_action is True


@pytest.mark.anyio
async def test_generate_structured_invalid_raises_error():
  """Verify malformed JSON or schema mismatch raises GeminiStructuredOutputError."""
  mock_client = MagicMock()
  invalid_json = '{"topic": 123, "urgency": "None"}'  # Missing required requires_action
  mock_resp = create_mock_response(text=invalid_json)
  mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

  settings = Settings(GEMINI_API_KEY="mock_key")
  service = GeminiService(settings=settings, client=mock_client)

  with pytest.raises(GeminiStructuredOutputError) as exc_info:
    await service.generate_structured("Classify intent", response_model=SampleCivicIntent)
  assert exc_info.value.code == "AI_STRUCTURED_OUTPUT_ERROR"
  assert exc_info.value.status_code == 502


# --- API Endpoint Integration Tests ---

def test_api_status_does_not_call_gemini():
  """Verify /api/v1/gemini/status returns config without calling the Gemini API."""
  mock_client = MagicMock()
  mock_client.aio.models.generate_content = AsyncMock()

  settings = Settings(GEMINI_API_KEY="mock_key_xyz", GEMINI_MODEL="gemini-2.5-flash")
  service = GeminiService(settings=settings, client=mock_client)
  set_gemini_service(service)

  with TestClient(app) as client:
    res = client.get("/api/v1/gemini/status")
    assert res.status_code == 200
    data = res.json()
    assert data["configured"] is True
    assert data["model"] == "gemini-2.5-flash"
    # Ensure generate_content was NEVER invoked
    assert mock_client.aio.models.generate_content.await_count == 0
    # Crucial security check: API key must NEVER be in response
    assert "mock_key_xyz" not in res.text


def test_api_status_not_configured():
  """Verify /api/v1/gemini/status returns configured: false when key is missing."""
  settings = Settings(GEMINI_API_KEY="")
  service = GeminiService(settings=settings)
  set_gemini_service(service)

  with TestClient(app) as client:
    res = client.get("/api/v1/gemini/status")
    assert res.status_code == 200
    data = res.json()
    assert data["configured"] is False
    assert "model" in data


def test_api_test_endpoint_success():
  """Verify /api/v1/gemini/test runs diagnostic with mock service."""
  mock_client = MagicMock()
  mock_resp = create_mock_response(text="Hello! CivicLens assistant. வணக்கம்!")
  mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

  settings = Settings(GEMINI_API_KEY="mock_secret_key_123")
  service = GeminiService(settings=settings, client=mock_client)
  set_gemini_service(service)

  with TestClient(app) as client:
    res = client.post("/api/v1/gemini/test")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "CivicLens" in data["message"]
    assert data["model"] == service.active_model
    assert data["latency_ms"] > 0
    assert data["token_usage"]["total_tokens"] == 25
    # Security: Secret key never in response
    assert "mock_secret_key_123" not in res.text


def test_api_test_rate_limit_exceeded():
  """Verify in-memory rate limiting triggers 429 when max calls per minute is exceeded."""
  mock_client = MagicMock()
  mock_resp = create_mock_response(text="Hello from CivicLens")
  mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

  settings = Settings(GEMINI_API_KEY="mock_key")
  service = GeminiService(settings=settings, client=mock_client)
  set_gemini_service(service)

  reset_test_rate_limit()

  with TestClient(app) as client:
    # First 5 calls must succeed
    for i in range(5):
      res = client.post("/api/v1/gemini/test")
      assert res.status_code == 200, f"Call {i+1} should succeed"

    # 6th call within the same minute window must be rate limited with HTTP 429
    res6 = client.post("/api/v1/gemini/test")
    assert res6.status_code == 429
    data = res6.json()
    assert "error" in data
    assert "rate limit exceeded" in data["error"]["message"].lower()


def test_api_key_security_across_all_errors(caplog):
  """Verify secret API key NEVER leaks into response bodies, error messages, or logs."""
  # Dynamically construct mock key at runtime so literal pattern is never in committed code
  secret_key = "".join(["AIza", "Sy", "_MOCK_KEY_FOR_TESTS_", "0123456789abcdef"])
  mock_client = MagicMock()
  # Cause a failure
  mock_client.aio.models.generate_content = AsyncMock(side_effect=Exception("Internal SDK failure"))

  settings = Settings(GEMINI_API_KEY=secret_key)
  service = GeminiService(settings=settings, client=mock_client)
  set_gemini_service(service)

  with TestClient(app) as client:
    res = client.post("/api/v1/gemini/test")
    assert res.status_code in (500, 502)
    # Never in response text
    assert secret_key not in res.text
    # Never in captured logs
    assert secret_key not in caplog.text


# --- Optional Real Live API Test (Manually enabled via env flag) ---

@pytest.mark.skipif(
    not os.getenv("RUN_REAL_GEMINI_TEST"),
    reason="Live Gemini API call test skipped. Set RUN_REAL_GEMINI_TEST=1 to enable.",
)
@pytest.mark.anyio
async def test_real_gemini_api_call():
  """Optional manual test verifying real connectivity with Google AI Studio using active key."""
  service = GeminiService()
  assert service.is_configured(), "GEMINI_API_KEY must be set in backend/.env"

  result = await service.generate_text(
      "Respond with exactly: 'CivicLens live verification test passed in English and Tamil.'"
  )
  assert "CivicLens" in result.text
  assert result.latency_ms > 0
  assert result.total_tokens is not None and result.total_tokens > 0
