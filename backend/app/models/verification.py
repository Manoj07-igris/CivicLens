"""Pydantic models for Official Source Library and Fact Verification (Module 3).

Defines schemas for curated government sources, multi-source retrieval,
atomic claim splitting, evidence stance evaluation, deterministic verdict rules,
and comprehensive verification reports.
"""

import re
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.gemini import GeminiTokenUsage


# --- URL Validation Helper ---

SAFE_URL_REGEX = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)

def validate_safe_url(url: Optional[str]) -> Optional[str]:
  """Ensure URL uses http or https scheme and contains no control characters or dangerous protocols."""
  if not url or not url.strip():
    return None
  clean = url.strip()
  if len(clean) > 500:
    raise ValueError("Source URL must not exceed 500 characters.")
  if not SAFE_URL_REGEX.match(clean):
    raise ValueError("Invalid source URL. Must begin with http:// or https:// and be a valid URL.")
  # Block javascript:, data:, file:
  lower = clean.lower()
  if any(bad in lower for bad in ("javascript:", "data:", "file:", "vbscript:")):
    raise ValueError("Unsafe URL scheme detected.")
  return clean


# --- Official Source Library Schemas ---

class OfficialSourceCreateRequest(BaseModel):
  """Metadata fields accompanying multipart PDF upload for official sources."""

  title: str = Field(
      ...,
      min_length=1,
      max_length=200,
      description="Official title of the government notification, gazette, or policy",
  )
  issuing_authority: str = Field(
      ...,
      min_length=1,
      max_length=200,
      description="Issuing department, ministry, or statutory body (e.g. 'Department of Social Welfare')",
  )
  source_url: Optional[str] = Field(
      default=None,
      max_length=500,
      description="Declared origin URL for reference only (never crawled by backend)",
  )
  publication_date: Optional[str] = Field(
      default=None,
      description="ISO date string when the document was published (e.g. '2024-06-15')",
  )
  effective_date: Optional[str] = Field(
      default=None,
      description="ISO date string when the policy came into force (e.g. '2024-07-01')",
  )
  series_id: Optional[str] = Field(
      default=None,
      max_length=100,
      description="Identifier grouping versions of the same scheme or circular (e.g. 'ev-subsidy-scheme')",
  )
  status: Literal["current", "superseded", "unknown"] = Field(
      default="unknown",
      description="Statutory standing: current, superseded by newer order, or unknown",
  )
  superseded_by: Optional[str] = Field(
      default=None,
      description="Source UUID of the newer notification that replaces this document",
  )
  notes: Optional[str] = Field(
      default=None,
      max_length=1000,
      description="Optional administrative notes or scope description",
  )

  @field_validator("title", "issuing_authority")
  @classmethod
  def strip_required_strings(cls, v: str) -> str:
    cleaned = v.strip()
    if not cleaned:
      raise ValueError("Field cannot be empty or purely whitespace.")
    return cleaned

  @field_validator("source_url")
  @classmethod
  def validate_url(cls, v: Optional[str]) -> Optional[str]:
    return validate_safe_url(v)


class OfficialSourceUpdateRequest(BaseModel):
  """Metadata update payload for an existing official source."""

  title: Optional[str] = Field(default=None, min_length=1, max_length=200)
  issuing_authority: Optional[str] = Field(default=None, min_length=1, max_length=200)
  source_url: Optional[str] = Field(default=None, max_length=500)
  publication_date: Optional[str] = None
  effective_date: Optional[str] = None
  series_id: Optional[str] = Field(default=None, max_length=100)
  status: Optional[Literal["current", "superseded", "unknown"]] = None
  superseded_by: Optional[str] = None
  notes: Optional[str] = Field(default=None, max_length=1000)

  @field_validator("source_url")
  @classmethod
  def validate_url(cls, v: Optional[str]) -> Optional[str]:
    return validate_safe_url(v)


class OfficialSourceMetadata(BaseModel):
  """Authoritative metadata record stored in official sources manifest."""

  source_id: str = Field(..., description="Unique UUID identifier for this official source")
  title: str
  issuing_authority: str
  source_url: Optional[str] = None
  publication_date: Optional[str] = None
  effective_date: Optional[str] = None
  series_id: Optional[str] = None
  status: Literal["current", "superseded", "unknown"] = "unknown"
  superseded_by: Optional[str] = None
  notes: Optional[str] = None
  filename: str
  file_size_bytes: int
  page_count: int
  sha256: str
  language: str = "unknown"
  ocr_applied: bool = False
  ocr_page_count: int = 0
  warnings: List[str] = Field(default_factory=list)
  error_message: Optional[str] = None
  added_at: str
  updated_at: Optional[str] = None
  index_status: Literal["not_indexed", "indexing", "indexed", "index_failed"] = "not_indexed"
  index_built_at: Optional[str] = None
  indexed_chunks_count: int = 0
  collection: Literal["official"] = "official"


class OfficialSourceListResponse(BaseModel):
  """Response schema for GET /api/v1/sources."""

  sources: List[OfficialSourceMetadata]
  total_count: int
  library_version: str


# --- Fact Verification Report Schemas ---

class FactComparisonItem(BaseModel):
  """Result of comparing a claim's deterministic fact against an evidence passage."""

  fact_type: str = Field(..., description="'date', 'amount', 'percentage', 'age', 'duration', 'code'")
  claim_value: str = Field(..., description="Factual value stated in the citizen's claim")
  source_value: Optional[str] = Field(default=None, description="Corresponding value stated in the official source")
  status: Literal["match", "mismatch", "absent"] = Field(..., description="Match status")


class EvidenceItemReport(BaseModel):
  """Individual quoted passage supporting, contradicting, or relating to a claim."""

  label: str = Field(..., description="Canonical citation label, e.g. 'S1', 'S2'")
  collection: Literal["official", "user"] = Field(..., description="Whether source is curated official library or user document")
  source_id: str
  source_title: str
  issuing_authority: Optional[str] = None
  source_url: Optional[str] = None
  effective_date: Optional[str] = None
  status: Literal["current", "superseded", "unknown"] = "unknown"
  stale: bool = False
  page_number: int
  quote: Optional[str] = None
  excerpt: str
  fact_comparisons: List[FactComparisonItem] = Field(default_factory=list)


class SupersededByInfo(BaseModel):
  """Information about a newer official source that replaces an outdated policy claim."""

  newer_source_id: str
  newer_source_title: str
  newer_effective_date: Optional[str] = None
  newer_page_number: Optional[int] = None
  replacing_quote: Optional[str] = None


class ClaimResult(BaseModel):
  """Verification verdict and evidence breakdown for a single atomic claim."""

  claim_id: str
  claim_text: str
  claim_type: str = Field(
      default="other",
      description="'deadline', 'eligibility', 'amount_benefit', 'required_documents', 'procedure', 'scheme_existence_or_status', 'other'",
  )
  is_checkable_fact: bool = True
  claim_facts: Dict[str, List[str]] = Field(default_factory=dict)
  verdict: Literal["supported", "contradicted", "unverified", "outdated"]
  verdict_basis: str = Field(
      ...,
      description=(
          "Authoritative backend basis, e.g. 'verified_quote_and_facts', 'partial_match', "
          "'no_evidence', 'conflicting_sources', 'superseded_source', "
          "'model_judgement_with_verified_quote', 'ai_unavailable', 'not_checkable'"
      ),
  )
  explanation: str
  matched_aspects: List[str] = Field(default_factory=list)
  unmatched_aspects: List[str] = Field(default_factory=list)
  supporting_evidence: List[EvidenceItemReport] = Field(default_factory=list)
  contradicting_evidence: List[EvidenceItemReport] = Field(default_factory=list)
  related_evidence: List[EvidenceItemReport] = Field(default_factory=list)
  superseded_by_info: Optional[SupersededByInfo] = None
  time_sensitivity_warning: Optional[str] = None
  conflicting_sources: bool = False
  evidence_level: Literal["strong", "weak", "none"] = "none"


class CoverageInfo(BaseModel):
  """Audit record of search scope, sources searched, and search limitations."""

  official_sources_searched_count: int
  official_source_titles: List[str] = Field(default_factory=list)
  user_documents_included: bool = False
  user_document_titles: List[str] = Field(default_factory=list)
  passages_examined_count: int = 0
  sources_skipped: List[Dict[str, str]] = Field(default_factory=list)
  library_version: str
  disclaimer: str = "Searched only the sources listed. Not finding evidence does not mean a claim is false."


class VerificationReport(BaseModel):
  """Comprehensive fact verification report."""

  verification_id: str
  created_at: str
  language: str
  scope: Literal["official", "official_and_documents", "documents"]
  original_claim_text: str
  overall_verdict: Literal["supported", "contradicted", "unverified", "outdated", "mixed"]
  overall_summary: str
  claims: List[ClaimResult]
  coverage: CoverageInfo
  analysis_status: Literal["completed", "completed_with_warnings", "partial", "failed"]
  warnings: List[str] = Field(default_factory=list)
  cache_hit: bool = False
  model: str = ""
  token_usage: Optional[GeminiTokenUsage] = None


# --- Verification Request & API Job Schemas ---

class VerifyRequest(BaseModel):
  """Request schema for POST /api/v1/verify."""

  claim: str = Field(
      ...,
      min_length=1,
      max_length=1000,
      description="The public claim or news statement to verify (max 1,000 characters)",
  )
  language: Literal["en", "ta", "auto"] = Field(
      default="auto",
      description="Desired reply language ('en', 'ta', or 'auto' detection)",
  )
  scope: Literal["official", "official_and_documents", "documents"] = Field(
      default="official",
      description="Search scope: official library only, official + user docs, or user docs only",
  )
  document_ids: List[str] = Field(
      default_factory=list,
      max_length=5,
      description="Optional list of user document UUIDs (required if scope is 'documents', max 5)",
  )
  force: bool = Field(
      default=False,
      description="Force re-running analysis bypassing cache",
  )

  @field_validator("claim")
  @classmethod
  def claim_must_not_be_whitespace(cls, v: str) -> str:
    cleaned = v.strip()
    if not cleaned:
      raise ValueError("Claim text cannot be empty or purely whitespace.")
    return cleaned


class VerifyJobResponse(BaseModel):
  """Immediate 202 response schema for POST /api/v1/verify."""

  verification_id: str
  status: Literal["queued", "running", "completed", "completed_with_warnings", "partial", "failed"]
  stage: str
  message: str
  created_at: str


class VerifyStatusResponse(BaseModel):
  """Response schema for GET /api/v1/verify/{id}."""

  verification_id: str
  status: Literal["queued", "running", "completed", "completed_with_warnings", "partial", "failed"]
  stage: str
  progress_pct: int = 0
  report: Optional[VerificationReport] = None
  error_message: Optional[str] = None


class VerifyListSummary(BaseModel):
  """Summary descriptor for listing past verifications."""

  verification_id: str
  claim_snippet: str
  overall_verdict: str
  created_at: str
  scope: str
  language: str


class VerifyListResponse(BaseModel):
  """Response schema for GET /api/v1/verify."""

  verifications: List[VerifyListSummary]
  total_count: int


# --- Gemini Structured Output Schemas (for AI calls) ---

class AtomicClaimItem(BaseModel):
  """Structured item for Call 1: atomic claim decomposition."""

  claim_id: str = Field(..., description="Unique claim identifier, e.g. 'c1', 'c2'")
  claim_text: str = Field(..., description="Exact claim proposition faithful to user input")
  claim_type: Literal[
      "deadline", "eligibility", "amount_benefit", "required_documents",
      "procedure", "scheme_existence_or_status", "other"
  ] = "other"
  is_checkable_fact: bool = Field(
      default=True,
      description="False if statement is subjective opinion, rumor about intent, or prediction",
  )
  temporal_scope: Literal["current", "unspecified", "specific_period"] = "unspecified"
  key_entities: List[str] = Field(default_factory=list, description="Scheme names or department keywords")


class ClaimSplitResult(BaseModel):
  """Top-level container for Call 1 structured output."""

  claims: List[AtomicClaimItem] = Field(
      default_factory=list,
      description="List of at most 5 atomic checkable claims",
  )


class PassageJudgement(BaseModel):
  """Model judgement on a single passage against a claim."""

  passage_label: str = Field(..., description="Citation label such as 'S1', 'S2'")
  stance: Literal["supports", "contradicts", "related_but_inconclusive", "irrelevant"] = "irrelevant"
  quote: Optional[str] = Field(
      default=None,
      description="Exact short quote copied verbatim from the passage text. Required for supports and contradicts.",
  )
  matched_aspects: List[str] = Field(default_factory=list, description="Aspects of the claim addressed by this passage")
  unmatched_aspects: List[str] = Field(default_factory=list, description="Aspects of the claim missing from this passage")


class ClaimJudgementItem(BaseModel):
  """Model proposed judgement for a single claim across evaluated passages."""

  claim_id: str
  proposed_verdict: Literal["supported", "contradicted", "unverified", "outdated"]
  reasoning: str = Field(..., description="Plain-language justification in the requested language")
  matched_aspects: List[str] = Field(default_factory=list, description="Claim aspects confirmed or addressed")
  unmatched_aspects: List[str] = Field(default_factory=list, description="Claim aspects unaddressed or unsupported")
  passages: List[PassageJudgement] = Field(default_factory=list)


class BatchJudgementResult(BaseModel):
  """Top-level container for Call 2 structured output."""

  judgements: List[ClaimJudgementItem] = Field(default_factory=list)
