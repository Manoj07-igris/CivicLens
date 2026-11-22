"""FastAPI router for conversational AI chat turns."""

import time
from collections import deque
from typing import Deque
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth.dependencies import CurrentUser, get_current_user
from app.models.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService, get_chat_service

router = APIRouter(prefix="/chat", tags=["AI Chatbot"])

# In-memory rate limiting: max 20 chat turns per 60-second window
CHAT_CALL_TIMESTAMPS: Deque[float] = deque()
RATE_LIMIT_WINDOW_SECONDS = 60.0
MAX_CHAT_CALLS_PER_WINDOW = 20


def check_chat_rate_limit() -> None:
  """Enforce rolling window rate limit on chat endpoint."""
  now = time.time()
  while CHAT_CALL_TIMESTAMPS and now - CHAT_CALL_TIMESTAMPS[0] > RATE_LIMIT_WINDOW_SECONDS:
    CHAT_CALL_TIMESTAMPS.popleft()

  if len(CHAT_CALL_TIMESTAMPS) >= MAX_CHAT_CALLS_PER_WINDOW:
    retry_after = int(RATE_LIMIT_WINDOW_SECONDS - (now - CHAT_CALL_TIMESTAMPS[0])) + 1
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Chat rate limit exceeded ({MAX_CHAT_CALLS_PER_WINDOW} msgs/min). Please try again in {retry_after}s.",
    )

  CHAT_CALL_TIMESTAMPS.append(now)


def reset_chat_rate_limit() -> None:
  """Helper for tests to clear the rate limit deque."""
  CHAT_CALL_TIMESTAMPS.clear()


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to the CivicLens AI assistant",
)
async def post_chat_message(
    chat_request: ChatRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
  """Process a conversational message with the central Gemini assistant.

  Accepts user text, conversational history, and language preference ('en', 'ta', 'auto').
  Stateless in this phase: client submits history; Phase 15 will introduce database persistence.
  """
  check_chat_rate_limit()

  req_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
  return await service.process_chat(chat_request, request_id=req_id)
