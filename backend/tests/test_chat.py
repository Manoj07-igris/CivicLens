"""Comprehensive tests for CivicLens conversational AI assistant endpoint and service."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))

from app.api.chat import reset_chat_rate_limit
from app.main import app
from app.models.chat import ChatMessage, ChatRequest
from app.services.chat_service import ChatService, set_chat_service, trim_history
from app.services.gemini_service import (
    GeminiNotConfiguredError,
    GeminiRateLimitError,
    GeminiResult,
    GeminiService,
)


@pytest.fixture(autouse=True)
def cleanup():
  reset_chat_rate_limit()
  set_chat_service(None)
  yield
  reset_chat_rate_limit()
  set_chat_service(None)


def test_trim_history_max_messages():
  """Verify history is capped to the maximum number of allowed turns."""
  history = [
      ChatMessage(role="user", content=f"User turn {i}")
      if i % 2 == 0
      else ChatMessage(role="assistant", content=f"Assistant turn {i}")
      for i in range(20)
  ]
  trimmed = trim_history(history, max_messages=10, max_chars=50000)
  assert len(trimmed) == 10
  assert trimmed[-1].content == "Assistant turn 19"
  assert trimmed[0].content == "User turn 10"


def test_trim_history_char_budget():
  """Verify history trims older messages if total character budget is exceeded."""
  history = [
      ChatMessage(role="user", content="A" * 100),
      ChatMessage(role="assistant", content="B" * 100),
      ChatMessage(role="user", content="C" * 100),
  ]
  # Budget allows only 200 chars -> newest 2 should be kept
  trimmed = trim_history(history, max_messages=10, max_chars=200)
  assert len(trimmed) == 2
  assert trimmed[0].content == "B" * 100
  assert trimmed[1].content == "C" * 100


def test_chat_success_english():
  """Verify end-to-end chat turn in English with mocked GeminiService."""
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.generate_text = AsyncMock(
      return_value=GeminiResult(
          text="A community certificate is issued by the Revenue Department.",
          model="gemini-2.5-flash",
          finish_reason="STOP",
          prompt_tokens=120,
          candidates_tokens=45,
          total_tokens=165,
          latency_ms=350.0,
      )
  )

  service = ChatService(gemini_service=mock_gemini)
  set_chat_service(service)

  payload = {
      "message": "What is a community certificate?",
      "history": [],
      "language": "en",
  }

  with TestClient(app) as client:
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "community certificate" in data["reply"]
    assert data["language_used"] == "en"
    assert data["model"] == "gemini-2.5-flash"
    assert data["latency_ms"] == 350.0
    assert data["token_usage"]["total_tokens"] == 165
    assert "message_id" in data
    assert data["sources"] == []
    assert data["tool_activity"] == []

    # Verify system instruction contains evidence & no-fabrication rules
    _, kwargs = mock_gemini.generate_text.call_args
    system_inst = kwargs.get("system_instruction", "")
    assert "EVIDENCE-BASED GROUNDING" in system_inst
    assert "no user-uploaded government documents" in system_inst
    assert "ENGLISH" in system_inst


def test_chat_tamil_language_selection():
  """Verify explicit Tamil language selection injects Tamil language rules."""
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.generate_text = AsyncMock(
      return_value=GeminiResult(
          text="சாதிச் சான்றிதழ் வருவாய்த் துறையால் வழங்கப்படுகிறது.",
          model="gemini-2.5-flash",
          latency_ms=400.0,
      )
  )

  service = ChatService(gemini_service=mock_gemini)
  set_chat_service(service)

  payload = {
      "message": "சாதிச் சான்றிதழ் என்றால் என்ன?",
      "history": [],
      "language": "ta",
  }

  with TestClient(app) as client:
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["language_used"] == "ta"

    _, kwargs = mock_gemini.generate_text.call_args
    system_inst = kwargs.get("system_instruction", "")
    assert "TAMIL (தமிழ்)" in system_inst


def test_chat_auto_mode_tamil_question():
  """Verify 'auto' mode resolves Tamil query to Tamil response."""
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.generate_text = AsyncMock(
      return_value=GeminiResult(
          text="வணக்கம்! நான் சிவிக்லென்ஸ் உதவியாளர்.",
          model="gemini-2.5-flash",
          latency_ms=250.0,
      )
  )

  service = ChatService(gemini_service=mock_gemini)
  set_chat_service(service)

  payload = {
      "message": "வணக்கம்! என்ன உதவி செய்வீர்கள்?",
      "language": "auto",
  }

  with TestClient(app) as client:
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["language_used"] == "ta"


def test_chat_validation_rejects_empty_message():
  """Verify empty or blank messages are rejected with 422."""
  with TestClient(app) as client:
    res = client.post("/api/v1/chat", json={"message": "   ", "language": "en"})
    assert res.status_code == 422
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_chat_validation_rejects_oversized_message():
  """Verify messages exceeding 4,000 characters are rejected with 422."""
  oversized = "A" * 4001
  with TestClient(app) as client:
    res = client.post("/api/v1/chat", json={"message": oversized, "language": "en"})
    assert res.status_code == 422
    data = res.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_chat_rate_limiting_triggers():
  """Verify exceeding 20 chat requests in 1 minute triggers HTTP 429."""
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.generate_text = AsyncMock(
      return_value=GeminiResult(text="Reply", model="gemini-2.5-flash")
  )
  service = ChatService(gemini_service=mock_gemini)
  set_chat_service(service)

  with TestClient(app) as client:
    for i in range(20):
      res = client.post("/api/v1/chat", json={"message": f"Query {i}"})
      assert res.status_code == 200

    # 21st call within window must return 429
    res21 = client.post("/api/v1/chat", json={"message": "Query 21"})
    assert res21.status_code == 429
    data = res21.json()
    assert "error" in data
    assert "rate limit exceeded" in data["error"]["message"].lower()


def test_chat_surfaces_gemini_not_configured():
  """Verify missing GEMINI_API_KEY returns friendly 503 error."""
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.generate_text = AsyncMock(side_effect=GeminiNotConfiguredError())
  service = ChatService(gemini_service=mock_gemini)
  set_chat_service(service)

  with TestClient(app) as client:
    res = client.post("/api/v1/chat", json={"message": "Hello"})
    assert res.status_code == 503
    data = res.json()
    assert data["error"]["code"] == "AI_NOT_CONFIGURED"


def test_chat_surfaces_gemini_rate_limit():
  """Verify upstream Gemini 429 returns friendly 429 error."""
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.generate_text = AsyncMock(side_effect=GeminiRateLimitError())
  service = ChatService(gemini_service=mock_gemini)
  set_chat_service(service)

  with TestClient(app) as client:
    res = client.post("/api/v1/chat", json={"message": "Hello"})
    assert res.status_code == 429
    data = res.json()
    assert data["error"]["code"] == "AI_RATE_LIMITED"


def test_chat_logs_never_leak_content_or_keys(caplog):
  """Verify sensitive citizen query text and API keys are never captured in logs."""
  secret_phrase = "MY_HIGHLY_PRIVATE_CITIZEN_PROBLEM_12345"
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.generate_text = AsyncMock(
      return_value=GeminiResult(text="Civic response", model="gemini-2.5-flash")
  )
  service = ChatService(gemini_service=mock_gemini)
  set_chat_service(service)

  with TestClient(app) as client:
    res = client.post("/api/v1/chat", json={"message": secret_phrase})
    assert res.status_code == 200
    assert secret_phrase not in caplog.text
