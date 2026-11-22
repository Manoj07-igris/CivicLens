"""Pydantic models for persisted Chat Conversations and Messages."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class ConversationMetadata(BaseModel):
  """Metadata header for a persisted conversational session."""

  id: str = Field(..., description="Unique conversation UUID")
  title: str = Field(..., description="Conversation display title")
  language_setting: str = Field(default="auto", description="Preferred language ('en', 'ta', 'auto')")
  document_ids: List[str] = Field(default_factory=list, description="Attached document UUIDs")
  message_count: int = Field(default=0, description="Total number of stored messages")
  created_at: str = Field(..., description="ISO 8601 creation timestamp")
  updated_at: str = Field(..., description="ISO 8601 last update timestamp")


class ConversationCreateRequest(BaseModel):
  """Request schema to create a new conversation."""

  title: Optional[str] = Field(default=None, max_length=120, description="Optional custom title")
  language_setting: Literal["en", "ta", "auto"] = Field(default="auto")
  document_ids: List[str] = Field(default_factory=list, max_length=5)


class ConversationUpdateRequest(BaseModel):
  """Request schema to patch an existing conversation."""

  title: Optional[str] = Field(default=None, max_length=120)
  language_setting: Optional[Literal["en", "ta", "auto"]] = Field(default=None)
  document_ids: Optional[List[str]] = Field(default=None, max_length=5)


class ConversationMessage(BaseModel):
  """Single stored chat message."""

  id: str = Field(..., description="Unique message UUID")
  conversation_id: str = Field(..., description="Parent conversation UUID")
  seq: int = Field(..., description="1-based message sequence number")
  role: Literal["user", "assistant"] = Field(..., description="Message author")
  content: str = Field(..., description="Text content")
  language_used: Optional[str] = Field(default=None)
  intent: Optional[str] = Field(default=None)
  grounded: Optional[bool] = Field(default=None)
  model: Optional[str] = Field(default=None)
  meta: Dict[str, Any] = Field(default_factory=dict, description="Structured artifacts (sources, tools, summaries)")
  created_at: str = Field(..., description="ISO 8601 creation timestamp")


class ConversationDetailResponse(BaseModel):
  """Response schema for getting a conversation with its messages."""

  conversation: ConversationMetadata
  messages: List[ConversationMessage]
  has_more: bool = Field(default=False)


class ConversationListResponse(BaseModel):
  """Paginated list of conversations."""

  items: List[ConversationMetadata]
  total: int
  limit: int
  offset: int


class ConversationImportItem(BaseModel):
  """A single conversation imported from browser localStorage."""

  id: Optional[str] = None
  title: Optional[str] = "Imported Conversation"
  language_setting: Optional[str] = "auto"
  document_ids: List[str] = Field(default_factory=list)
  messages: List[Dict[str, Any]] = Field(default_factory=list)
  created_at: Optional[str] = None
  updated_at: Optional[str] = None


class ConversationImportRequest(BaseModel):
  """Payload for bulk importing conversations from localStorage."""

  conversations: List[ConversationImportItem]
