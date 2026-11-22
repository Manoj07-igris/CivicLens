"""Pydantic schemas for the Civic Grievance Assistant (Module 5).

Provides models for grievance analysis, structured Gemini output, drafts,
photo observation items, portal channel matches, demo tracking records,
and API request/response payloads.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.portal import GrievanceChannelsResult
from app.services.grievance_rules import (
    CATEGORY_TRANSLATION_KEYS,
    GrievanceCategory,
)


class GrievanceAnalysisModel(BaseModel):
  """Structured JSON model returned by Gemini generate_structured."""
  category: str = Field(
      ...,
      description="Grievance category (roads, water_supply, streetlights, waste_management, drainage_sewage, public_infrastructure_damage, other)",
  )
  category_reason: str = Field(
      default="",
      description="Brief factual reason for category classification strictly from user text or photo",
  )
  severity_suggestion: Literal["low", "medium", "high", "urgent"] = Field(
      default="medium",
      description="Suggested severity level",
  )
  severity_reasons: List[str] = Field(
      default_factory=list,
      description="Reasons supporting the severity suggestion",
  )
  safety_risk: bool = Field(
      default=False,
      description="Whether there is an active safety hazard to human life or health",
  )
  safety_reasons: List[str] = Field(
      default_factory=list,
      description="Factual safety hazard reasons if safety_risk is true",
  )
  subject_line: str = Field(
      ...,
      description="Clear, neutral, formal subject line for the complaint in requested language",
  )
  body: str = Field(
      ...,
      description="Factual, structured complaint body containing ONLY facts provided by user",
  )
  image_relevant: bool = Field(
      default=True,
      description="Whether the attached photo portrays a relevant civic issue",
  )
  observations: List[str] = Field(
      default_factory=list,
      description="Up to 5 neutral, visible-only photo observations (no individuals, faces, or plates)",
  )
  quality_note: Optional[str] = Field(
      default=None,
      description="Optional observation on photo quality (e.g. blurry, dark, clear)",
  )
  missing_details: List[str] = Field(
      default_factory=list,
      description="Up to 4 short questions for details that would make the complaint more actionable",
  )
  plain_notes: Optional[str] = Field(
      default=None,
      description="Optional short guidance notes for the citizen in their UI language",
  )


class GrievanceObservationItem(BaseModel):
  """Single photo observation with individual confirmation state."""
  item_id: str
  text: str
  confirmed: bool = False


class GrievanceDraft(BaseModel):
  """Structured complaint draft."""
  subject_line: str
  body: str
  location_line: str
  observations: List[GrievanceObservationItem] = Field(default_factory=list)
  final_text: str = ""
  draft_hash: str = ""


class DemoTrackingEvent(BaseModel):
  """Simulated tracking status transition event."""
  event_id: str
  status: Literal["registered", "under_review", "in_progress", "resolved"]
  timestamp: str
  simulated: bool = True
  note: Optional[str] = None


class DemoRecord(BaseModel):
  """Simulated citizen complaint tracking record."""
  demo_id: str = Field(..., description="Non-sequential demo tracking ID, e.g. DEMO-K7X29P")
  registered_at: str
  status: Literal["registered", "under_review", "in_progress", "resolved"] = "registered"
  is_demo: bool = True
  notice: str = "Demo record only. Not sent to any government authority."
  events: List[DemoTrackingEvent] = Field(default_factory=list)
  approval: Dict[str, Any] = Field(default_factory=dict)


class Grievance(BaseModel):
  """Full civic grievance domain entity."""
  id: str = Field(..., description="UUID of the grievance record")
  created_at: str
  updated_at: str
  state: Literal["draft", "demo_registered"] = "draft"
  description: str
  location_text: str = ""
  duration_text: str = ""
  language: str = "en"

  # Category classification
  category: str
  category_source: Literal["ai", "rules", "user"] = "rules"
  category_confidence: Literal["consistent", "needs_confirmation"] = "consistent"
  category_scores: Dict[str, float] = Field(default_factory=dict)

  # Severity & Safety
  severity: Literal["low", "medium", "high", "urgent"] = "medium"
  severity_source: Literal["rules", "ai", "user"] = "rules"
  safety_risk: bool = False
  matched_safety_rules: List[str] = Field(default_factory=list)
  emergency_notice: Optional[str] = None

  # Draft
  draft: GrievanceDraft
  missing_details: List[str] = Field(default_factory=list)
  channels: GrievanceChannelsResult

  # Transparency metadata
  analysis_inputs: Literal["text_only", "text_and_photo"] = "text_only"
  analysis_mode: Literal["ai", "rules_only"] = "ai"
  warnings: List[str] = Field(default_factory=list)
  draft_hash: str

  # Photo metadata
  has_image: bool = False
  image_id: Optional[str] = None

  # Demo tracking
  demo: Optional[DemoRecord] = None


class GrievanceAnalyzeRequest(BaseModel):
  """Request schema for POST /api/v1/grievances/analyze."""
  description: str = Field(
      ...,
      min_length=10,
      max_length=2000,
      description="Citizen's description of the civic problem (10-2000 characters)",
  )
  location_text: Optional[str] = Field(
      default="",
      max_length=300,
      description="Optional location, street name, or landmark (max 300 characters)",
  )
  duration_text: Optional[str] = Field(
      default="",
      max_length=100,
      description="Optional duration, e.g. 'since two weeks' (max 100 characters)",
  )
  language_of_draft: Literal["en", "ta"] = Field(
      default="en",
      description="Language for the generated complaint draft",
  )
  category_hint: Optional[str] = Field(
      default=None,
      description="Optional user-selected category override",
  )
  image_id: Optional[str] = Field(
      default=None,
      description="Optional ID of previously uploaded image",
  )
  image_consent: bool = Field(
      default=False,
      description="Required consent before image is sent to Gemini for analysis",
  )


class GrievancePatchRequest(BaseModel):
  """Request schema for PATCH /api/v1/grievances/{id}."""
  category: Optional[str] = None
  severity: Optional[Literal["low", "medium", "high", "urgent"]] = None
  subject_line: Optional[str] = Field(None, max_length=200)
  body: Optional[str] = Field(None, max_length=4000)
  location_text: Optional[str] = Field(None, max_length=300)
  confirmed_observation_ids: Optional[List[str]] = None


class GrievanceRegisterDemoRequest(BaseModel):
  """Request schema for POST /api/v1/grievances/{id}/register-demo."""
  approved: bool = Field(..., description="Explicit citizen confirmation to create demo record")
  approved_hash: str = Field(..., description="SHA-256 hash of the exact reviewed text")


class GrievanceAdvanceDemoRequest(BaseModel):
  """Request schema for POST /api/v1/grievances/{id}/demo-advance."""
  note: Optional[str] = Field(default=None, max_length=200, description="Optional simulated update note")


class GrievanceCapabilitiesResponse(BaseModel):
  """Response schema for GET /api/v1/grievances/capabilities."""
  min_description_chars: int
  max_description_chars: int
  location_max_chars: int
  max_image_mb: int
  image_max_dimension: int
  image_allowed_types: List[str]
  emergency_contact_text: str
  categories: List[Dict[str, str]]
  demo_id_prefix: str


class GrievanceSummaryItem(BaseModel):
  """Compact summary item for GET /api/v1/grievances listing."""
  id: str
  created_at: str
  updated_at: str
  category: str
  severity: str
  state: str
  subject_line: str
  has_image: bool = False
  demo_id: Optional[str] = None
  demo_status: Optional[str] = None
