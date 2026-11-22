"""Chat orchestration service managing conversational context, trimming, and Gemini integration."""

import logging
import uuid
from typing import List, Optional

from app.core.pii_guard import ensure_no_pii
from app.core.prompts import get_chat_system_prompt
from app.models.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    SourceCitation,
    ToolActivityItem,
)
from app.models.gemini import GeminiTokenUsage
from app.services.gemini_service import GeminiService, get_gemini_service
from app.services.language_service import resolve_reply_language

logger = logging.getLogger("civiclens.chat")

# Guardrails to protect quota and context windows on free-tier
MAX_HISTORY_MESSAGES = 10
MAX_HISTORY_CHARS_BUDGET = 12000


def trim_history(
    history: List[ChatMessage],
    max_messages: int = MAX_HISTORY_MESSAGES,
    max_chars: int = MAX_HISTORY_CHARS_BUDGET,
) -> List[ChatMessage]:
  """Trim conversation history to the most recent messages within a safe character budget."""
  if not history:
    return []

  # 1. Cap to last N messages
  recent = history[-max_messages:]

  # 2. Enforce total character budget from newest to oldest
  budget_remaining = max_chars
  retained: List[ChatMessage] = []

  for msg in reversed(recent):
    msg_len = len(msg.content)
    if msg_len <= budget_remaining:
      retained.append(msg)
      budget_remaining -= msg_len
    else:
      break

  # Restore chronological order
  retained.reverse()
  return retained


class ChatService:
  """Service managing multi-turn civic chat turns with Gemini."""

  def __init__(self, gemini_service: Optional[GeminiService] = None):
    self._gemini = gemini_service or get_gemini_service()

  async def process_chat(
      self,
      request: ChatRequest,
      request_id: Optional[str] = None,
  ) -> ChatResponse:
    """Process a citizen chat turn end-to-end."""
    req_tag = f"[{request_id}] " if request_id else ""
    ensure_no_pii(request.message, field_name="message")

    # 1. Resolve response language based on user query and preference
    reply_lang = resolve_reply_language(
        user_text=request.message,
        selected_language=request.language,
        ui_language="en",
    )

    # 2. Trim history within safe message count and character budgets
    trimmed_history = trim_history(request.history)

    # 3. Build SDK-formatted message contents
    contents: List[dict] = []
    for turn in trimmed_history:
      role = "user" if turn.role == "user" else "model"
      contents.append({"role": role, "content": turn.content})

    # Append current user prompt
    contents.append({"role": "user", "content": request.message})

    # 4. Construct layered system prompt (Base + Chat Notice + Language rules)
    system_instruction = get_chat_system_prompt(reply_language=reply_lang)

    # 5. Call Gemini service
    result = await self._gemini.generate_text(
        prompt_or_messages=contents,
        system_instruction=system_instruction,
    )

    token_usage = None
    if result.total_tokens is not None or result.prompt_tokens is not None:
      token_usage = GeminiTokenUsage(
          prompt_tokens=result.prompt_tokens,
          candidates_tokens=result.candidates_tokens,
          total_tokens=result.total_tokens,
      )

    # Log safe metadata without citizen query or prompt text
    logger.info(
        "%sChat turn completed. Model=%s, Lang=%s, Latency=%.2fms, Tokens=(%s/%s/%s)",
        req_tag,
        result.model,
        reply_lang,
        result.latency_ms,
        result.prompt_tokens,
        result.candidates_tokens,
        result.total_tokens,
    )

    return ChatResponse(
        reply=result.text.strip(),
        language_used=reply_lang,
        model=result.model,
        latency_ms=round(result.latency_ms, 2),
        token_usage=token_usage,
        message_id=str(uuid.uuid4()),
        sources=[],        # Phase 8 will inject document citations here
        tool_activity=[],  # Phase 9 will inject agent tool executions here
    )


_chat_service_instance: Optional[ChatService] = None

def get_chat_service() -> ChatService:
  """Dependency provider returning shared ChatService instance."""
  global _chat_service_instance
  if _chat_service_instance is None:
    _chat_service_instance = ChatService()
  return _chat_service_instance


def set_chat_service(service: Optional[ChatService]) -> None:
  """Test helper to inject or reset mock ChatService."""
  global _chat_service_instance
  _chat_service_instance = service
