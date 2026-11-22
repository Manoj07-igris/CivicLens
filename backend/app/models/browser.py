"""Pydantic data models for Playwright Browser Automation (Controlled Demo Workflow).

Strictly bounded to educational simulation of public service portals on localhost.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


BrowserActionType = Literal[
    "open_portal",
    "fill_step",
    "go_next",
    "go_back",
    "go_to_review",
    "read_back",
    "submit",
    "close",
]

BrowserSessionStatus = Literal[
    "created",
    "active",
    "submitted",
    "error",
    "closed",
    "timed_out",
]


class FormFieldOption(BaseModel):
  """Select option with English and Tamil labels."""
  value: str
  label: str
  label_ta: Optional[str] = None


class FormFieldDefinition(BaseModel):
  """Definition of a single form field in the demo portal."""
  name: str = Field(..., description="Unique field key matching data-field attribute")
  label: str = Field(..., description="Field label in English")
  label_ta: Optional[str] = Field(None, description="Field label in Tamil")
  field_type: Literal["text", "select", "date", "number", "textarea", "checkbox"] = "text"
  selector: str = Field(..., description="CSS locator in demo portal, e.g. [data-field='applicant_name']")
  required: bool = True
  options: Optional[List[FormFieldOption]] = None
  sample_value: Any = None
  min_length: Optional[int] = None
  max_length: Optional[int] = None
  min_val: Optional[float] = None
  max_val: Optional[float] = None
  placeholder: Optional[str] = None
  help_text: Optional[str] = None
  help_text_ta: Optional[str] = None


class FormStepDefinition(BaseModel):
  """Definition of a logical step/page in the demo multi-step form."""
  step_id: str
  step_index: int = Field(..., ge=1, le=10)
  title: str
  title_ta: Optional[str] = None
  description: Optional[str] = None
  description_ta: Optional[str] = None
  fields: List[FormFieldDefinition] = Field(default_factory=list)


class DemoWorkflowManifest(BaseModel):
  """Manifest describing the demo portal multi-step workflow structure."""
  workflow_id: str = "demo_income_certificate"
  title: str = "Demo Income Certificate Application"
  title_ta: Optional[str] = "மாதிரி வருமானச் சான்றிதழ் விண்ணப்பம்"
  service_type: str = "income_certificate"
  target_url: str = "http://127.0.0.1:8000/demo-portal/"
  steps: List[FormStepDefinition] = Field(default_factory=list)
  fictional_sample_values: Dict[str, Any] = Field(default_factory=dict)


class BrowserSessionCreateRequest(BaseModel):
  """Request to start a new controlled browser demo session."""
  portal_id: str = Field(default="prt_demo_portal", description="Portal ID (must be loopback demo portal)")
  lang: Literal["en", "ta"] = Field(default="en", description="UI language for demo portal")
  workflow_id: str = Field(default="demo_income_certificate", description="Workflow to practice")


class BrowserFillStepRequest(BaseModel):
  """Request to fill a specific step with fictional values."""
  step_index: int = Field(..., ge=1, le=10)
  values: Dict[str, Any] = Field(..., description="Field key-value pairs matching step fields")
  fictional_confirmed: bool = Field(
      True,
      description="Mandatory affirmation that all submitted values are fictional demo data",
  )

  @field_validator("fictional_confirmed")
  @classmethod
  def must_be_true(cls, v: bool) -> bool:
    if not v:
      raise ValueError("You must confirm all submitted values are fictional demo data.")
    return v


class BrowserActionRequest(BaseModel):
  """Generic bounded action request."""
  action: BrowserActionType
  step_index: Optional[int] = None
  values: Optional[Dict[str, Any]] = None
  fictional_confirmed: bool = True


class BrowserSessionEvent(BaseModel):
  """Audit log entry for an action executed in the browser session."""
  timestamp: str
  action: str
  step_index: Optional[int] = None
  url: str
  success: bool = True
  message: str = ""
  screenshot_id: Optional[str] = None


class BrowserSessionRecord(BaseModel):
  """Stored browser demo session state."""
  session_id: str = Field(..., description="UUID identifying the active demo session")
  portal_id: str = "prt_demo_portal"
  portal_url: str = "http://127.0.0.1:8000/demo-portal/"
  workflow_id: str = "demo_income_certificate"
  status: BrowserSessionStatus = "created"
  current_step: int = 1
  total_steps: int = 5
  lang: str = "en"
  created_at: str
  updated_at: str
  expires_at: str
  actions_count: int = 0
  screenshots_count: int = 0
  submission_id: Optional[str] = None
  application_number: Optional[str] = None
  events: List[BrowserSessionEvent] = Field(default_factory=list)
  filled_values: Dict[str, Any] = Field(default_factory=dict)
  review_hash: Optional[str] = None
  last_screenshot_id: Optional[str] = None
  last_screenshot_url: Optional[str] = None


class BrowserSubmissionPreview(BaseModel):
  """State preview presented to citizen for human approval prior to demo submission."""
  session_id: str
  review_hash: str = Field(..., description="Canonical SHA-256 hash of filled values and review state")
  filled_values: Dict[str, Any]
  summary: Dict[str, str]
  disclaimer: str = (
      "DEMO SIMULATION ONLY: This is a controlled local simulation for citizen educational purposes. "
      "Submitting this form does NOT create an application with any government department, "
      "does NOT save your data permanently, and does NOT interact with external servers."
  )


class BrowserSubmitRequest(BaseModel):
  """Request to submit the demo form, bound to review_hash."""
  review_hash: str = Field(..., description="SHA-256 hash returned by the preview endpoint")
  fictional_confirmed: bool = Field(True, description="Confirmation of fictional data")

  @field_validator("fictional_confirmed")
  @classmethod
  def must_be_true(cls, v: bool) -> bool:
    if not v:
      raise ValueError("You must confirm all submitted values are fictional demo data.")
    return v


class BrowserSubmissionResult(BaseModel):
  """Result of submitting the demo form."""
  session_id: str
  submission_id: str
  status: Literal["demo_submitted"] = "demo_submitted"
  application_number: str
  timestamp: str
  confirmation_message: str
  confirmation_message_ta: str
  screenshot_id: Optional[str] = None


class BrowserCapabilitiesResponse(BaseModel):
  """Response describing current browser automation status and limits."""
  enabled: bool
  headless: bool
  max_concurrent_sessions: int
  active_sessions_count: int
  supported_workflows: List[str]
  demo_portal_url: str
