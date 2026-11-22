"""Pydantic schemas for the CivicLens conversational AI assistant."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.gemini import GeminiTokenUsage


class ChatMessage(BaseModel):
  """Single message in a conversational session."""

  role: Literal["user", "assistant"] = Field(
      ..., description="Speaker role: 'user' or 'assistant'"
  )
  content: str = Field(..., description="The message content")

  @field_validator("content")
  @classmethod
  def content_must_not_be_blank(cls, v: str) -> str:
    if not v or not v.strip():
      raise ValueError("Message content must not be blank.")
    return v


class ChatRequest(BaseModel):
  """Request schema for POST /api/v1/chat."""

  message: str = Field(
      ...,
      min_length=1,
      max_length=4000,
      description="The citizen's question or message (max 4,000 characters)",
  )
  history: List[ChatMessage] = Field(
      default_factory=list,
      description="Prior conversation history in chronological order",
  )
  language: Literal["en", "ta", "auto"] = Field(
      default="auto",
      description="Desired response language ('en', 'ta', or 'auto' detection)",
  )

  @field_validator("message")
  @classmethod
  def message_must_not_be_whitespace(cls, v: str) -> str:
    stripped = v.strip()
    if not stripped:
      raise ValueError("Message cannot be empty or purely whitespace.")
    return stripped


class SourceCitation(BaseModel):
  """Citation descriptor for verified document evidence (Prepared for Phase 8)."""

  title: str = Field(..., description="Official document or gazette title")
  source_id: str = Field(..., description="Unique document or chunk identifier")
  url: Optional[str] = Field(default=None, description="Official government link if available")
  snippet: Optional[str] = Field(default=None, description="Verbatim referenced excerpt")


class ToolActivityItem(BaseModel):
  """Audit record of a backend tool invoked by the central agent (Prepared for Phase 9)."""

  tool_name: str = Field(..., description="Name of the backend tool executed")
  summary: str = Field(..., description="Plain-language description of action taken")
  status: str = Field(default="completed", description="Status of the tool execution")


class ChatResponse(BaseModel):
  """Response schema for POST /api/v1/chat."""

  reply: str = Field(..., description="AI assistant's plain-language civic response")
  language_used: str = Field(..., description="Language of the reply ('en' or 'ta')")
  model: str = Field(..., description="Gemini model identifier used for generation")
  latency_ms: float = Field(..., description="Processing latency in milliseconds")
  token_usage: Optional[GeminiTokenUsage] = Field(
      default=None, description="Input, candidate, and total token counts"
  )
  message_id: str = Field(..., description="Unique UUID identifying this chat message")
  sources: List[SourceCitation] = Field(
      default_factory=list,
      description="Evidence source citations (empty until Phase 8)",
  )
  tool_activity: List[ToolActivityItem] = Field(
      default_factory=list,
      description="Agent tool execution records (empty until Phase 9)",
  )
