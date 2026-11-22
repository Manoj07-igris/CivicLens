"""Gemini AI service layer for CivicLens.

Provides robust, asynchronous access to the Google Gemini API using the official
google-genai SDK. Supports plain text generation, multi-turn conversations,
validated Pydantic structured output, and minimal tool calling skeletons (Phase 9 ready).
"""

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel, ValidationError

try:
  from google import genai
  from google.genai import errors as genai_errors
  from google.genai import types
except ImportError:
  genai = None  # type: ignore
  genai_errors = None  # type: ignore
  types = None  # type: ignore

from app.core.config import Settings, get_settings
from app.core.prompts import BASE_SYSTEM_PROMPT

logger = logging.getLogger("civiclens.gemini")

T = TypeVar("T", bound=BaseModel)


# --- Custom Exception Hierarchy ---

class GeminiError(Exception):
  """Base exception for all Gemini service failures."""
  def __init__(self, message: str, code: str = "AI_SERVICE_ERROR", status_code: int = 502):
    super().__init__(message)
    self.message = message
    self.code = code
    self.status_code = status_code


class GeminiNotConfiguredError(GeminiError):
  """Raised when attempting an AI call without a valid GEMINI_API_KEY."""
  def __init__(self, message: str = "The Gemini AI service is not configured on this server. Please set GEMINI_API_KEY in backend/.env."):
    super().__init__(message=message, code="AI_NOT_CONFIGURED", status_code=503)


class GeminiRateLimitError(GeminiError):
  """Raised when Gemini API returns 429 Resource Exhausted / Rate Limit."""
  def __init__(self, message: str = "Gemini AI rate limit or quota exceeded. Please wait a moment before trying again.", retry_after: Optional[int] = None):
    super().__init__(message=message, code="AI_RATE_LIMITED", status_code=429)
    self.retry_after = retry_after


class GeminiTimeoutError(GeminiError):
  """Raised when an AI request exceeds timeout limits."""
  def __init__(self, message: str = "The AI service request timed out. Please try again."):
    super().__init__(message=message, code="AI_TIMEOUT", status_code=504)


class GeminiSafetyBlockedError(GeminiError):
  """Raised when output is blocked by content safety filters."""
  def __init__(self, message: str = "The AI response was blocked by content safety filters."):
    super().__init__(message=message, code="AI_SAFETY_BLOCKED", status_code=400)


class GeminiStructuredOutputError(GeminiError):
  """Raised when response cannot be decoded into the requested Pydantic schema."""
  def __init__(self, message: str = "Failed to parse structured output from AI response.", details: Any = None):
    super().__init__(message=message, code="AI_STRUCTURED_OUTPUT_ERROR", status_code=502)
    self.details = details


class GeminiAPIError(GeminiError):
  """Raised on unexpected upstream Gemini API errors."""
  def __init__(self, message: str = "An upstream error occurred communicating with the Gemini AI service.", details: Any = None):
    super().__init__(message=message, code="AI_SERVICE_ERROR", status_code=502)
    self.details = details


# --- Result Data Models ---

@dataclass
class GeminiResult:
  """Clean result object returned from plain text and chat generation."""
  text: str
  model: str
  finish_reason: Optional[str] = None
  prompt_tokens: Optional[int] = None
  candidates_tokens: Optional[int] = None
  total_tokens: Optional[int] = None
  latency_ms: float = 0.0


@dataclass
class ToolCallItem:
  """Descriptor for a function call requested by the model."""
  name: str
  args: Dict[str, Any]
  call_id: Optional[str] = None


@dataclass
class GeminiToolResult:
  """Result object containing either text or function call requests (Phase 9 skeleton)."""
  model: str
  text: Optional[str] = None
  tool_calls: List[ToolCallItem] = field(default_factory=list)
  finish_reason: Optional[str] = None
  prompt_tokens: Optional[int] = None
  candidates_tokens: Optional[int] = None
  total_tokens: Optional[int] = None
  latency_ms: float = 0.0


# --- Core Service Class ---

class GeminiService:
  """Production-grade asynchronous service for Google Gemini API."""

  def __init__(
      self,
      settings: Optional[Settings] = None,
      client: Optional[Any] = None,
  ):
    self._settings = settings or get_settings()
    self._client = client
    self._call_timestamps: List[float] = []
    self._rate_lock: Optional[asyncio.Lock] = None

  async def _enforce_global_rate_limit(self) -> None:
    """Enforce central global rate limit (sliding window) across all Gemini calls."""
    rpm_cap = getattr(self._settings, "GEMINI_GLOBAL_RPM_CAP", 30)
    if rpm_cap <= 0:
      return

    if getattr(self, "_rate_lock", None) is None:
      self._rate_lock = asyncio.Lock()
    if getattr(self, "_call_timestamps", None) is None:
      self._call_timestamps = []

    async with self._rate_lock:
      now = time.monotonic()
      self._call_timestamps = [t for t in self._call_timestamps if now - t < 60.0]
      if len(self._call_timestamps) >= rpm_cap:
        oldest = self._call_timestamps[0]
        sleep_needed = 60.0 - (now - oldest) + 0.05
        if sleep_needed > 0:
          logger.info(
              "Global Gemini RPM cap (%d) reached. Throttling for %.2fs",
              rpm_cap,
              sleep_needed,
          )
          await asyncio.sleep(sleep_needed)
          now = time.monotonic()
          self._call_timestamps = [t for t in self._call_timestamps if now - t < 60.0]
      self._call_timestamps.append(time.monotonic())

  @property
  def settings(self) -> Settings:
    return self._settings

  def is_configured(self) -> bool:
    """Return True if a valid non-placeholder API key is set."""
    return self._settings.is_gemini_configured

  @property
  def active_model(self) -> str:
    """Return the active model name from settings or sensible default."""
    return self._settings.effective_gemini_model

  def _get_client(self) -> Any:
    """Return the google-genai Client, initializing it if necessary."""
    if self._client is not None:
      return self._client

    if not self.is_configured():
      raise GeminiNotConfiguredError()

    if genai is None:
      raise GeminiAPIError("google-genai SDK is not installed in the environment.")

    # Never log the key or print it
    self._client = genai.Client(api_key=self._settings.clean_gemini_api_key)
    return self._client

  def _format_contents(
      self, prompt_or_messages: Union[str, List[Dict[str, str]], List[Any]]
  ) -> Any:
    """Format input into standard SDK contents (string or list of Content parts)."""
    if isinstance(prompt_or_messages, str):
      return prompt_or_messages

    if isinstance(prompt_or_messages, list):
      if not prompt_or_messages:
        return []
      # If list of types.Content (e.g. from Agent orchestrator)
      if types is not None and isinstance(prompt_or_messages[0], types.Content):
        return prompt_or_messages
      # If list of dicts with role/content (e.g. Chat history from Phase 6)
      if isinstance(prompt_or_messages[0], dict):
        if types is not None:
          contents = []
          for msg in prompt_or_messages:
            role = "user" if msg.get("role") in ("user", "citizen") else "model"
            content = msg.get("content", "")
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=content)],
                )
            )
          return contents
      return prompt_or_messages

    return str(prompt_or_messages)

  def _extract_usage(self, response: Any) -> Dict[str, Optional[int]]:
    """Safely extract token counts from GenerateContentResponse."""
    usage = getattr(response, "usage_metadata", None)
    if not usage:
      return {"prompt_tokens": None, "candidates_tokens": None, "total_tokens": None}
    return {
        "prompt_tokens": getattr(usage, "prompt_token_count", None),
        "candidates_tokens": getattr(usage, "candidates_token_count", None),
        "total_tokens": getattr(usage, "total_token_count", None),
    }

  async def generate_text(
      self,
      prompt_or_messages: Union[str, List[Dict[str, str]], List[Any]],
      system_instruction: Optional[str] = None,
      model: Optional[str] = None,
      temperature: Optional[float] = None,
      max_output_tokens: Optional[int] = None,
      timeout_seconds: Optional[int] = None,
  ) -> GeminiResult:
    """Generate plain text from Gemini asynchronously with retries and safety checks."""
    client = self._get_client()
    target_model = model or self.active_model
    effective_instruction = system_instruction or BASE_SYSTEM_PROMPT
    effective_temp = temperature if temperature is not None else self._settings.GEMINI_TEMPERATURE
    effective_max_tokens = max_output_tokens or self._settings.GEMINI_MAX_OUTPUT_TOKENS
    effective_timeout = timeout_seconds or self._settings.GEMINI_TIMEOUT_SECONDS
    max_retries = self._settings.GEMINI_MAX_RETRIES

    contents = self._format_contents(prompt_or_messages)
    await self._enforce_global_rate_limit()

    config = None
    if types is not None:
      config = types.GenerateContentConfig(
          system_instruction=effective_instruction,
          temperature=effective_temp,
          max_output_tokens=effective_max_tokens,
      )

    last_error: Optional[Exception] = None
    start_time = time.perf_counter()

    for attempt in range(max_retries + 1):
      try:
        # Wrap async SDK call with timeout to prevent hung requests
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            ),
            timeout=effective_timeout,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Check safety and finish reasons
        candidate = response.candidates[0] if (hasattr(response, "candidates") and response.candidates) else None
        finish_reason = getattr(candidate, "finish_reason", None)
        finish_str = str(finish_reason).upper() if finish_reason else "STOP"

        if "SAFETY" in finish_str or "BLOCKED" in finish_str:
          logger.warning(
              "Gemini response blocked by safety filter. Model=%s, FinishReason=%s",
              target_model,
              finish_str,
          )
          raise GeminiSafetyBlockedError()

        raw_text = getattr(response, "text", "") or ""

        # Extract token usage
        usage = self._extract_usage(response)

        # Log completion event safely without prompts or keys
        logger.info(
            "Gemini text generated. Model=%s, Latency=%.2fms, Finish=%s, Tokens(in/out/total)=(%s/%s/%s)",
            target_model,
            latency_ms,
            finish_str,
            usage["prompt_tokens"],
            usage["candidates_tokens"],
            usage["total_tokens"],
        )

        return GeminiResult(
            text=raw_text,
            model=target_model,
            finish_reason=finish_str,
            prompt_tokens=usage["prompt_tokens"],
            candidates_tokens=usage["candidates_tokens"],
            total_tokens=usage["total_tokens"],
            latency_ms=latency_ms,
        )

      except asyncio.TimeoutError:
        last_error = GeminiTimeoutError(f"AI request timed out after {effective_timeout}s.")
        logger.warning("Gemini request timeout on attempt %d/%d (Model=%s)", attempt + 1, max_retries + 1, target_model)
      except genai_errors.APIError as exc:
        code = getattr(exc, "code", 500)
        logger.warning(
            "Gemini APIError on attempt %d/%d: Code=%s, Type=%s",
            attempt + 1,
            max_retries + 1,
            code,
            exc.__class__.__name__,
        )
        if code == 429:
          last_error = GeminiRateLimitError(
              message="Gemini AI rate limit or quota reached. Please wait a moment before trying again."
          )
        elif 500 <= code < 600:
          last_error = GeminiAPIError("Gemini server error. Retrying...")
        else:
          # Non-retriable client errors (400, 403, etc.)
          err_msg = getattr(exc, "message", "") or str(exc)
          clean_msg = " ".join(err_msg.splitlines())[:200]
          raise GeminiAPIError(f"Gemini API request failed with code {code}: {clean_msg}") from exc
      except GeminiSafetyBlockedError:
        raise
      except Exception as exc:
        logger.exception("Unexpected error in Gemini service: %s", exc.__class__.__name__)
        last_error = GeminiAPIError(f"Unexpected AI error: {exc.__class__.__name__}")

      # Backoff if retries remain
      if attempt < max_retries:
        backoff = min(1.0 * (2 ** attempt) + random.uniform(0.1, 0.4), 8.0)
        await asyncio.sleep(backoff)

    if last_error:
      raise last_error
    raise GeminiAPIError("Failed to complete Gemini request after retries.")

  async def generate_structured(
      self,
      prompt_or_messages: Union[str, List[Dict[str, str]], List[Any]],
      response_model: Type[T],
      system_instruction: Optional[str] = None,
      model: Optional[str] = None,
      temperature: Optional[float] = None,
      timeout_seconds: Optional[int] = None,
      images: Optional[List[Dict[str, Any]]] = None,
  ) -> T:
    """Generate structured output validated against a Pydantic schema.

    Supports optional multimodal image parts (JPEG, PNG, WebP) without logging bytes.
    """
    client = self._get_client()
    target_model = model or self.active_model
    effective_instruction = system_instruction or BASE_SYSTEM_PROMPT
    effective_temp = temperature if temperature is not None else 0.1  # Low temperature for deterministic structure
    effective_timeout = timeout_seconds or self._settings.GEMINI_TIMEOUT_SECONDS
    max_retries = self._settings.GEMINI_MAX_RETRIES

    if images and types is not None:
      parts: List[Any] = []
      if isinstance(prompt_or_messages, str):
        parts.append(types.Part.from_text(text=prompt_or_messages))
      elif isinstance(prompt_or_messages, list):
        for item in prompt_or_messages:
          if isinstance(item, str):
            parts.append(types.Part.from_text(text=item))
          elif isinstance(item, dict) and "content" in item:
            parts.append(types.Part.from_text(text=str(item["content"])))
          elif hasattr(item, "text"):
            parts.append(item)
      for img in images:
        img_data = img.get("data") if isinstance(img, dict) else getattr(img, "data", None)
        if img_data is None and isinstance(img, dict):
          img_data = img.get("bytes")
        mime = (img.get("mime_type") if isinstance(img, dict) else getattr(img, "mime_type", "image/jpeg")) or "image/jpeg"
        if img_data:
          parts.append(types.Part.from_bytes(data=img_data, mime_type=mime))
      contents = [types.Content(role="user", parts=parts)]
    else:
      contents = self._format_contents(prompt_or_messages)
    await self._enforce_global_rate_limit()

    config = None
    if types is not None:
      config = types.GenerateContentConfig(
          system_instruction=effective_instruction,
          temperature=effective_temp,
          response_mime_type="application/json",
          response_schema=response_model,
      )

    last_error: Optional[Exception] = None
    start_time = time.perf_counter()

    for attempt in range(max_retries + 1):
      try:
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            ),
            timeout=effective_timeout,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Check safety
        candidate = response.candidates[0] if (hasattr(response, "candidates") and response.candidates) else None
        finish_reason = getattr(candidate, "finish_reason", None)
        finish_str = str(finish_reason).upper() if finish_reason else "STOP"

        if "SAFETY" in finish_str or "BLOCKED" in finish_str:
          raise GeminiSafetyBlockedError()

        # If SDK parsed object directly into model instance
        if hasattr(response, "parsed") and isinstance(response.parsed, response_model):
          return response.parsed

        # Otherwise parse raw text JSON
        raw_text = getattr(response, "text", "") or "{}"
        try:
          validated = response_model.model_validate_json(raw_text)
          logger.info(
              "Gemini structured output validated. Model=%s, Schema=%s, Latency=%.2fms",
              target_model,
              response_model.__name__,
              latency_ms,
          )
          return validated
        except ValidationError as val_err:
          logger.warning("Pydantic validation failed for %s", response_model.__name__)
          raise GeminiStructuredOutputError(
              message=f"Model output did not match expected {response_model.__name__} schema.",
              details=val_err.errors(),
          ) from val_err
        except json.JSONDecodeError as json_err:
          raise GeminiStructuredOutputError("AI response was not valid JSON.") from json_err

      except (asyncio.TimeoutError, genai_errors.APIError) as exc:
        if isinstance(exc, genai_errors.APIError) and getattr(exc, "code", 500) == 429:
          last_error = GeminiRateLimitError()
        elif isinstance(exc, asyncio.TimeoutError):
          last_error = GeminiTimeoutError()
        else:
          last_error = GeminiAPIError("Failed during structured generation.")

      if attempt < max_retries:
        await asyncio.sleep(min(1.0 * (2 ** attempt), 6.0))

    if last_error:
      raise last_error
    raise GeminiAPIError("Failed to generate structured output.")

  async def generate_with_tools(
      self,
      prompt_or_messages: Union[str, List[Dict[str, str]], List[Any]],
      tools: List[Any],
      system_instruction: Optional[str] = None,
      model: Optional[str] = None,
      temperature: Optional[float] = None,
      timeout_seconds: Optional[int] = None,
  ) -> GeminiToolResult:
    """Execute Gemini generation with function calling declarations (Phase 9).

    Controls execution strictly on the backend by disabling the SDK's automatic
    function calling feature. Returns requested function calls or text reply.
    """
    client = self._get_client()
    target_model = model or self.active_model
    effective_instruction = system_instruction or BASE_SYSTEM_PROMPT
    effective_temp = temperature if temperature is not None else 0.1
    effective_timeout = timeout_seconds or self._settings.GEMINI_TIMEOUT_SECONDS
    max_retries = self._settings.GEMINI_MAX_RETRIES

    contents = self._format_contents(prompt_or_messages)
    await self._enforce_global_rate_limit()

    config = None
    if types is not None:
      config = types.GenerateContentConfig(
          system_instruction=effective_instruction,
          temperature=effective_temp,
          tools=tools,
          automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
      )

    last_error: Optional[Exception] = None
    start_time = time.perf_counter()

    for attempt in range(max_retries + 1):
      try:
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            ),
            timeout=effective_timeout,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Check safety and finish reasons
        candidate = response.candidates[0] if (hasattr(response, "candidates") and response.candidates) else None
        finish_reason = getattr(candidate, "finish_reason", None)
        finish_str = str(finish_reason).upper() if finish_reason else "STOP"

        if "SAFETY" in finish_str or "BLOCKED" in finish_str:
          logger.warning(
              "Gemini tool call response blocked by safety filter. Model=%s, FinishReason=%s",
              target_model,
              finish_str,
          )
          raise GeminiSafetyBlockedError()

        # Extract function calls if returned by model
        tool_calls: List[ToolCallItem] = []
        text_parts: List[str] = []
        content = getattr(candidate, "content", None) if candidate else None
        if content and hasattr(content, "parts") and content.parts:
          for part in content.parts:
            fn_call = getattr(part, "function_call", None)
            if fn_call:
              fn_name = getattr(fn_call, "name", "unknown")
              raw_args = getattr(fn_call, "args", {})
              fn_args = dict(raw_args) if raw_args else {}
              fn_id = getattr(fn_call, "id", None)
              tool_calls.append(
                  ToolCallItem(
                      name=fn_name,
                      args=fn_args,
                      call_id=fn_id,
                  )
              )
            t = getattr(part, "text", None)
            if t:
              text_parts.append(t)

        final_text = "".join(text_parts) if text_parts else None

        usage = self._extract_usage(response)

        logger.info(
            "Gemini tool call completed. Model=%s, ToolsCount=%d, CallsCount=%d, Latency=%.2fms",
            target_model,
            len(tools),
            len(tool_calls),
            latency_ms,
        )

        return GeminiToolResult(
            model=target_model,
            text=final_text,
            tool_calls=tool_calls,
            finish_reason="TOOL_CALL" if tool_calls else finish_str,
            prompt_tokens=usage["prompt_tokens"],
            candidates_tokens=usage["candidates_tokens"],
            total_tokens=usage["total_tokens"],
            latency_ms=latency_ms,
        )

      except (asyncio.TimeoutError, genai_errors.APIError) as exc:
        if isinstance(exc, genai_errors.APIError) and getattr(exc, "code", 500) == 429:
          last_error = GeminiRateLimitError()
          logger.warning("Gemini API rate limit (429) hit in generate_with_tools. Attempt %d/%d", attempt + 1, max_retries + 1)
        elif isinstance(exc, asyncio.TimeoutError):
          last_error = GeminiTimeoutError()
          logger.warning("Gemini API timeout (%ds) in generate_with_tools on attempt %d/%d", effective_timeout, attempt + 1, max_retries + 1)
        else:
          code = getattr(exc, "code", 500)
          if code in (500, 502, 503, 504):
            last_error = GeminiAPIError(f"Gemini service unavailable ({code}).")
            logger.warning("Transient Gemini error %d in generate_with_tools on attempt %d/%d", code, attempt + 1, max_retries + 1)
          else:
            err_msg = getattr(exc, "message", "") or str(exc)
            clean_msg = " ".join(err_msg.splitlines())[:200]
            raise GeminiAPIError(f"Gemini API request failed with code {code}: {clean_msg}") from exc
      except GeminiSafetyBlockedError:
        raise
      except Exception as exc:
        logger.exception("Unexpected error in Gemini service generate_with_tools: %s", exc.__class__.__name__)
        last_error = GeminiAPIError(f"Unexpected AI error: {exc.__class__.__name__}")

      if attempt < max_retries:
        backoff = min(1.0 * (2 ** attempt) + random.uniform(0.1, 0.4), 8.0)
        await asyncio.sleep(backoff)

    if last_error:
      raise last_error
    raise GeminiAPIError("Failed to complete Gemini request with tools after retries.")


# --- Service Singleton / Dependency Injection ---

_gemini_service_instance: Optional[GeminiService] = None

def get_gemini_service() -> GeminiService:
  """Dependency provider returning the shared GeminiService instance."""
  global _gemini_service_instance
  if _gemini_service_instance is None:
    _gemini_service_instance = GeminiService()
  return _gemini_service_instance


def set_gemini_service(service: Optional[GeminiService]) -> None:
  """Test helper to inject or reset a mock GeminiService instance."""
  global _gemini_service_instance
  _gemini_service_instance = service
  try:
    from app.agent.orchestrator import set_agent_orchestrator
    set_agent_orchestrator(None)
  except Exception:
    pass
  try:
    from app.services.rag_service import set_rag_service
    set_rag_service(None)
  except Exception:
    pass
  try:
    from app.services.verification_service import set_verification_service
    set_verification_service(None)
  except Exception:
    pass
  try:
    from app.services.public_service_service import set_public_service_service
    set_public_service_service(None)
  except Exception:
    pass
  try:
    from app.services.grievance_service import set_grievance_service
    set_grievance_service(None)
  except Exception:
    pass
  try:
    from app.services.comparison_service import set_comparison_service
    set_comparison_service(None)
  except Exception:
    pass
