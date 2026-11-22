"""Pydantic schemas for Public Service Assistant (Module 4).

Models for procedural guidance, interactive checklists, key facts,
source citations, portal matching, and form field explanations.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field

from app.models.portal import PortalMatchResult

ApplicantType = Literal[
    "student",
    "farmer",
    "worker",
    "senior_citizen",
    "woman",
    "business_owner",
    "other",
    "unspecified",
]

ChecklistCategory = Literal[
    "documents",
    "information",
    "steps",
    "fees_and_timelines",
    "to_verify",
]

ConfirmationStatus = Literal[
    "source_confirmed",
    "needs_check",
    "general_unverified",
]

ServiceGuideStatus = Literal[
    "processing",
    "ready",
    "failed",
]

ServiceGuideMode = Literal[
    "source_grounded",
    "no_sources",
    "general_guidance",
]


class ChecklistItem(BaseModel):
  """Individual checklist item for public service application."""
  id: str = Field(..., description="Unique item identifier, e.g. chk_1")
  category: ChecklistCategory = Field(..., description="Section category")
  text: str = Field(..., description="Plain-language checklist instruction in English")
  text_ta: Optional[str] = Field(None, description="Checklist instruction in Tamil")
  status: ConfirmationStatus = Field(default="needs_check", description="Verification confirmation state")
  source_label: Optional[str] = Field(None, description="Citation label, e.g. [S1] or [D1]")
  source_id: Optional[str] = Field(None, description="Source document identifier")
  source_title: Optional[str] = Field(None, description="Title of the source document")
  source_page: Optional[int] = Field(None, description="Page number where rule is found")
  source_quote: Optional[str] = Field(None, description="Exact verified quote from the source chunk")
  applicant_type_tag: Optional[ApplicantType] = Field(None, description="Applicable category if specialized")
  caution: Optional[str] = Field(None, description="Important warning or caveat")


class KeyFactItem(BaseModel):
  """Authoritative service fact (fee, timeline, validity, income limit)."""
  id: str = Field(..., description="Unique fact identifier, e.g. fact_1")
  fact_type: Literal["fee", "timeline", "validity", "income_limit", "age_limit", "other"]
  label: str = Field(..., description="Fact label, e.g. 'Application Fee'")
  label_ta: Optional[str] = Field(None, description="Fact label in Tamil")
  value_text: str = Field(..., description="Verified value, e.g. '₹60'")
  source_label: Optional[str] = Field(None, description="Citation label")
  source_quote: Optional[str] = Field(None, description="Verified quote snippet")
  page_number: Optional[int] = Field(None, description="Page number")
  confidence: float = Field(default=1.0)


class ServiceSourceCitation(BaseModel):
  """Cited source passage used as ground truth for public service guidance."""
  label: str = Field(..., description="Citation marker, e.g. [S1] or [D1]")
  source_id: str = Field(..., description="Unique source or document ID")
  title: str = Field(..., description="Title of the source policy or document")
  source_type: Literal["official_source", "citizen_document"] = "official_source"
  page_number: int = Field(..., description="1-indexed page number")
  snippet: str = Field(..., description="Verified verbatim excerpt from the document")
  issuing_authority: Optional[str] = None


class ServiceGuideRequest(BaseModel):
  """Request schema for POST /api/v1/services/guide."""
  query: str = Field(
      ...,
      min_length=3,
      max_length=600,
      description="The citizen's question about public service application",
  )
  applicant_type: ApplicantType = Field(
      default="unspecified",
      description="Target applicant demographic",
  )
  applicant_situation: Optional[str] = Field(
      default=None,
      max_length=500,
      description="Optional situational context (e.g. 'Applying first time, rural')",
  )
  language: Literal["en", "ta", "auto"] = Field(
      default="auto",
      description="Preferred output language",
  )
  allow_general: bool = Field(
      default=False,
      description="Allow general ungrounded guidance when zero official sources are found",
  )
  source_scope: Literal["all", "official_only", "user_documents_only"] = Field(
      default="all",
      description="Scope of documents to retrieve evidence from",
  )
  document_ids: Optional[List[str]] = Field(
      default=None,
      description="Optional specific user document IDs to query",
  )


class ServiceGuideReport(BaseModel):
  """Complete guidance and interactive checklist report."""
  id: str = Field(..., description="Unique guide identifier, e.g. gde_xxx")
  query: str = Field(..., description="Original citizen query")
  applicant_type: ApplicantType = Field(default="unspecified")
  applicant_situation: Optional[str] = None
  language: str = Field(default="en")
  mode: ServiceGuideMode = Field(..., description="Guidance mode based on evidence")
  status: ServiceGuideStatus = Field(default="ready")
  error_message: Optional[str] = None
  procedure_overview: str = Field(..., description="Plain-language procedural summary")
  procedure_overview_ta: Optional[str] = None
  checklist_items: List[ChecklistItem] = Field(default_factory=list)
  key_facts: List[KeyFactItem] = Field(default_factory=list)
  cited_sources: List[ServiceSourceCitation] = Field(default_factory=list)
  matched_portals: List[PortalMatchResult] = Field(default_factory=list)
  disclaimers: List[str] = Field(default_factory=list)
  offer_general_guidance: bool = Field(
      default=False,
      description="True if 0 sources were found and user may request general guidance",
  )
  created_at: str
  completed_at: Optional[str] = None


class ServiceGuideListResponse(BaseModel):
  total: int
  guides: List[ServiceGuideReport]


# --- Gemini Structured Output Draft Schemas ---

class ServiceGuideDraftItem(BaseModel):
  category: ChecklistCategory
  text: str
  text_ta: Optional[str] = None
  applicant_type_tag: Optional[str] = None
  source_label: Optional[str] = None
  source_page: Optional[int] = None
  source_quote: Optional[str] = None
  caution: Optional[str] = None


class ServiceGuideDraftKeyFact(BaseModel):
  fact_type: Literal["fee", "timeline", "validity", "income_limit", "age_limit", "other"]
  label: str
  label_ta: Optional[str] = None
  value_text: str
  source_label: Optional[str] = None
  source_quote: Optional[str] = None
  page_number: Optional[int] = None


class ServiceGuideDraft(BaseModel):
  """Pydantic schema passed to Gemini for structured JSON generation."""
  procedure_overview: str
  procedure_overview_ta: Optional[str] = None
  checklist_items: List[ServiceGuideDraftItem] = Field(default_factory=list)
  key_facts: List[ServiceGuideDraftKeyFact] = Field(default_factory=list)


# --- Form Field Explainer Schemas ---

class FormFieldCandidate(BaseModel):
  """Detected candidate field from application form."""
  id: str
  name: str
  label_ta: Optional[str] = None
  page_number: Optional[int] = None
  context_snippet: Optional[str] = None


class FormFieldExtractRequest(BaseModel):
  document_id: Optional[str] = None
  raw_text: Optional[str] = Field(None, max_length=15000)


class FormFieldExtractResponse(BaseModel):
  fields: List[FormFieldCandidate]
  total_detected: int


class FormFieldExplanationItem(BaseModel):
  """Plain explanation of a specific form field."""
  field_name: str
  field_name_ta: Optional[str] = None
  plain_explanation: str
  plain_explanation_ta: Optional[str] = None
  where_to_find: str
  where_to_find_ta: Optional[str] = None
  basis: Literal["stated_in_form_text", "general_knowledge"] = "stated_in_form_text"
  quote_from_form: Optional[str] = None
  page_number: Optional[int] = None
  caution: Optional[str] = None


class FormFieldExplainRequest(BaseModel):
  document_id: Optional[str] = None
  field_names: List[str] = Field(..., min_length=1, max_length=40)
  context_text: Optional[str] = Field(None, max_length=15000)
  language: Literal["en", "ta", "auto"] = "auto"


class FormFieldExplainDraftItem(BaseModel):
  field_name: str
  field_name_ta: Optional[str] = None
  plain_explanation: str
  plain_explanation_ta: Optional[str] = None
  where_to_find: str
  where_to_find_ta: Optional[str] = None
  basis: Literal["stated_in_form_text", "general_knowledge"] = "stated_in_form_text"
  quote_from_form: Optional[str] = None
  page_number: Optional[int] = None
  caution: Optional[str] = None


class FormFieldExplainDraft(BaseModel):
  explanations: List[FormFieldExplainDraftItem] = Field(default_factory=list)


class FormFieldExplainResponse(BaseModel):
  explanations: List[FormFieldExplanationItem]
  disclaimer: str
