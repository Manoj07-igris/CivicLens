"""Pydantic schemas for the Central AI Agent, function calling, tool activity, and approvals."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.chat import ChatMessage
from app.models.gemini import GeminiTokenUsage


class AgentChatRequest(BaseModel):
  """Request schema for POST /api/v1/agent/chat."""

  message: str = Field(
      ...,
      min_length=1,
      max_length=4000,
      description="The citizen's message or question (max 4,000 characters)",
  )
  history: List[ChatMessage] = Field(
      default_factory=list,
      description="Prior conversational history",
  )
  language: Literal["en", "ta", "auto"] = Field(
      default="auto",
      description="Desired reply language ('en', 'ta', or 'auto' detection)",
  )
  document_ids: List[str] = Field(
      default_factory=list,
      max_length=5,
      description="Optional list of active document UUIDs for context (max 5)",
  )
  conversation_id: Optional[str] = Field(
      default=None,
      description="Optional conversation UUID for server-side persistence",
  )

  @field_validator("message")
  @classmethod
  def message_must_not_be_whitespace(cls, v: str) -> str:
    stripped = v.strip()
    if not stripped:
      raise ValueError("Message cannot be empty or purely whitespace.")
    return stripped


class AgentSourceItem(BaseModel):
  """Authoritative source citation verified by backend metadata."""

  source_id: str = Field(..., description="Unique evidence label cited by agent (e.g. 'E1', 'C1', or 'S1')")
  document_id: str = Field(..., description="UUID of the referenced document")
  document_name: str = Field(..., description="Official filename of the referenced document")
  page_number: int = Field(..., description="1-based page number where passage appears")
  excerpt: str = Field(..., description="Verbatim passage snippet or excerpt")
  score: Optional[float] = Field(default=None, description="Retrieval relevance score if available")
  collection: Optional[str] = Field(default=None, description="'official' or 'user'")
  issuing_authority: Optional[str] = Field(default=None, description="Issuing authority if official source")
  effective_date: Optional[str] = Field(default=None, description="Effective date if official source")
  status: Optional[str] = Field(default=None, description="Status if official source")
  source_url: Optional[str] = Field(default=None, description="Declared source URL if official source")
  old_page_number: Optional[int] = Field(default=None, description="Page number in old document if comparison source")
  new_page_number: Optional[int] = Field(default=None, description="Page number in new document if comparison source")
  old_document_id: Optional[str] = Field(default=None, description="Old document UUID if comparison source")
  new_document_id: Optional[str] = Field(default=None, description="New document UUID if comparison source")
  comparison_id: Optional[str] = Field(default=None, description="Comparison ID reference if from compare_documents")


class AgentVerificationSummaryItem(BaseModel):
  """Backend-built summary of a check_claim fact verification."""

  verification_id: str = Field(..., description="UUID of the verification report")
  overall_verdict: str = Field(..., description="'supported', 'contradicted', 'unverified', 'outdated', 'mixed'")
  claim_snippet: str = Field(..., description="Short snippet of the verified claim")
  overall_summary: str = Field(default="", description="Plain-language outcome summary")
  per_claim_verdicts: List[Dict[str, str]] = Field(
      default_factory=list,
      description="List of per-claim {claim_id, verdict, basis}",
  )


class AgentChecklistSummaryItem(BaseModel):
  """Backend-built summary of a generate_checklist public service guidance request."""

  guide_id: str = Field(..., description="UUID of the public service guide")
  query: str = Field(..., description="Target public service query")
  mode: str = Field(..., description="'source_grounded', 'no_sources', or 'general_guidance'")
  total_items: int = Field(default=0)
  confirmed_items_count: int = Field(default=0)
  sample_items: List[str] = Field(default_factory=list)
  matched_portals: List[Dict[str, str]] = Field(default_factory=list)


class AgentGrievanceSummaryItem(BaseModel):
  """Backend-built summary of a draft_complaint or register_demo_complaint action."""

  grievance_id: str = Field(..., description="UUID of the grievance record")
  category: str = Field(..., description="Grievance category")
  severity: str = Field(..., description="Severity level")
  safety_risk: bool = Field(default=False, description="Whether safety hazard was flagged")
  state: str = Field(..., description="'draft' or 'demo_registered'")
  subject_line: str = Field(default="", description="Complaint subject line")
  demo_id: Optional[str] = Field(default=None, description="Non-sequential demo ID if registered")
  demo_status: Optional[str] = Field(default=None, description="Tracking status if demo registered")
  matched_channels: List[Dict[str, str]] = Field(default_factory=list, description="Curated reporting channels")


class AgentBrowserSessionSummaryItem(BaseModel):
  """Backend-built summary of a browser demo workflow action."""

  session_id: str = Field(..., description="UUID of the browser demo session")
  portal_name: str = Field(default="CivicLens Demo Portal", description="Name of the demo portal")
  action: str = Field(..., description="Action taken (open_portal, fill_step, submit)")
  current_step: int = Field(default=1, description="Current step index")
  total_steps: int = Field(default=5, description="Total steps in workflow")
  status: str = Field(default="active", description="Session status")
  application_number: Optional[str] = Field(default=None, description="Demo reference number if submitted")
  screenshot_url: Optional[str] = Field(default=None, description="URL of the latest screenshot")
  summary: str = Field(default="", description="Summary of the action taken")


class AgentToolActivityItem(BaseModel):
  """Audit record of a backend tool invocation during an agent run."""

  tool_name: str = Field(..., description="Name of the backend tool")
  ui_label_key: str = Field(..., description="Translation key for frontend UI display")
  status: Literal["success", "error", "rejected", "pending_approval", "skipped"] = Field(
      ..., description="Execution outcome status"
  )
  summary: str = Field(..., description="Human-readable summary of the action taken (no secrets/passages)")
  duration_ms: float = Field(default=0.0, description="Duration in milliseconds")


class PendingApprovalInfo(BaseModel):
  """Information presented to the citizen when an action requires explicit human confirmation."""

  approval_id: str = Field(..., description="Unique ID for this pending approval request")
  tool_name: str = Field(..., description="Name of the tool requiring approval")
  description: str = Field(..., description="Plain-language description of the action to be performed")
  args: Dict[str, Any] = Field(default_factory=dict, description="Safe summary of tool arguments")
  expires_at: str = Field(..., description="ISO 8601 expiry timestamp")


class AgentResponse(BaseModel):
  """Comprehensive response schema for POST /api/v1/agent/chat."""

  reply: str = Field(..., description="Agent's synthesized response in citizen's language")
  language_used: str = Field(..., description="Language of the reply ('en' or 'ta')")
  intent: Literal[
      "general_civic_information",
      "document_explanation",
      "unavailable_feature",
      "policy_comparison",
      "fact_verification",
      "public_service_guidance",
      "civic_complaint",
      "browser_demo",
  ] = Field(
      ..., description="Derived intent category of the interaction"
  )
  grounded: bool = Field(
      default=True,
      description="Whether document claims are grounded by verified citations",
  )
  sources: List[AgentSourceItem] = Field(
      default_factory=list,
      description="Verified document evidence citations",
  )
  verifications: List[AgentVerificationSummaryItem] = Field(
      default_factory=list,
      description="Backend-built verification summaries for claim results",
  )
  checklists: List[AgentChecklistSummaryItem] = Field(
      default_factory=list,
      description="Backend-built checklist summaries for public service guidance",
  )
  grievances: List[AgentGrievanceSummaryItem] = Field(
      default_factory=list,
      description="Backend-built grievance summaries for civic complaints",
  )
  browser_sessions: List[AgentBrowserSessionSummaryItem] = Field(
      default_factory=list,
      description="Backend-built summaries of browser demo sessions",
  )
  tool_activity: List[AgentToolActivityItem] = Field(
      default_factory=list,
      description="Step-by-step audit record of tool invocations",
  )
  steps_used: int = Field(..., description="Number of Gemini reasoning steps used")
  model: str = Field(..., description="Gemini model identifier used for reasoning")
  latency_ms: float = Field(..., description="Total processing latency in milliseconds")
  token_usage: Optional[GeminiTokenUsage] = Field(
      default=None, description="Total prompt and candidate tokens consumed"
  )
  pending_approval: Optional[PendingApprovalInfo] = Field(
      default=None, description="Action awaiting citizen approval if triggered"
  )
  conversation_id: Optional[str] = Field(
      default=None, description="Persisted conversation UUID"
  )
  warnings: List[str] = Field(
      default_factory=list,
      description="Operational warnings or caution flags",
  )


class ToolDescriptor(BaseModel):
  """Safe descriptor of a registered tool for GET /api/v1/agent/tools."""

  name: str = Field(..., description="Tool identifier")
  description: str = Field(..., description="Tool description explaining when to use it")
  risk_level: str = Field(..., description="'read_only', 'sensitive', or 'irreversible'")
  requires_approval: bool = Field(..., description="Whether execution requires human approval")
  status: str = Field(..., description="'available' or 'planned'")
  ui_label_key: str = Field(..., description="Translation key for frontend UI display")


class ToolsListResponse(BaseModel):
  """Response schema for GET /api/v1/agent/tools."""

  tools: List[ToolDescriptor]
  total_available: int
  total_planned: int


class ApprovalDecisionRequest(BaseModel):
  """Request schema for POST /api/v1/agent/approvals/{approval_id}."""

  decision: Literal["approve", "deny"] = Field(
      ..., description="Citizen decision: 'approve' to execute or 'deny' to cancel"
  )


class ApprovalDecisionResponse(BaseModel):
  """Response schema for POST /api/v1/agent/approvals/{approval_id}."""

  approval_id: str
  decision: str
  resumed_response: Optional[AgentResponse] = None
  message: str
