"""Pydantic models for Policy Change Detection (Module 2).

Defines schemas for deterministic diff operations, fact changes, segmented evidence,
Gemini candidate analysis, comparison reports, and API requests/responses.
"""

from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field, field_validator


class FactChange(BaseModel):
  """Authoritative deterministic difference in a factual data point (date, amount, etc.)."""
  fact_type: Literal["date", "amount", "percentage", "age", "duration", "code", "other"] = Field(
      ..., description="Classification of the extracted factual token"
  )
  old_value: str = Field(..., description="Original value extracted from old document")
  new_value: str = Field(..., description="Updated value extracted from new document")
  description: Optional[str] = Field(default=None, description="Human-readable fact change summary")


class WordDiffOp(BaseModel):
  """Word- or token-level diff operation within a modified clause."""
  op: Literal["equal", "insert", "delete", "replace"] = Field(
      ..., description="Diff operator matching standard sequence matcher"
  )
  old_text: Optional[str] = Field(default="", description="Original deleted or replaced text")
  new_text: Optional[str] = Field(default="", description="New inserted or replacement text")
  old_offsets: Optional[Tuple[int, int]] = Field(default=None, description="Start and end char offsets in old text")
  new_offsets: Optional[Tuple[int, int]] = Field(default=None, description="Start and end char offsets in new text")


class EvidenceReference(BaseModel):
  """Exact text and location coordinates of a segment in a source document."""
  document_id: str = Field(..., description="UUID of source document")
  document_name: str = Field(..., description="Official filename of source document")
  page_start: int = Field(..., description="1-based page number where segment begins")
  page_end: int = Field(..., description="1-based page number where segment concludes")
  text_excerpt: str = Field(..., description="Display excerpt of the segment")
  full_text: Optional[str] = Field(default=None, description="Full original segment text")
  char_start: int = Field(default=0, description="Char offset within document text")
  char_end: int = Field(default=0, description="End char offset")


class CandidateAnalysis(BaseModel):
  """Structured analysis of a candidate change returned by Gemini."""
  candidate_id: str = Field(..., description="Identifier matching candidate item")
  category: Literal[
      "eligibility",
      "deadline",
      "amount_benefit",
      "required_documents",
      "conditions_rules",
      "procedure",
      "definitions_scope",
      "administrative_editorial",
      "other",
  ] = Field(..., description="Functional domain of the change")
  change_type_confirmation: Literal["added", "removed", "modified", "not_material"] = Field(
      ..., description="Confirmation of structural change type"
  )
  is_material: bool = Field(..., description="Whether this change impacts citizen rights, procedures, or eligibility")
  importance: Literal["high", "medium", "low"] = Field(..., description="Severity level of impact for citizens")
  plain_summary: str = Field(..., description="Clear, plain-language description of what changed")
  practical_impact: str = Field(..., description="Actionable meaning for citizen/applicant, strictly text-grounded")
  uncertainty_note: Optional[str] = Field(default=None, description="Note if implication is ambiguous or partial")


class BatchAnalysisResult(BaseModel):
  """Pydantic schema for Gemini structured batch analysis calls."""
  candidates: List[CandidateAnalysis] = Field(
      default_factory=list, description="Array of candidate change evaluations"
  )
  batch_summary: Optional[str] = Field(default=None, description="Optional synthesis of key changes in this batch")


class ChangeItem(BaseModel):
  """A single detected policy change between old and new document versions."""
  change_id: str = Field(..., description="Unique identifier for this change (e.g. 'chg_1')")
  change_type: Literal["added", "removed", "modified"] = Field(
      ..., description="Structural nature of change"
  )
  category: str = Field(default="other", description="Domain classification (eligibility, deadline, etc.)")
  importance: Literal["high", "medium", "low"] = Field(default="medium", description="Citizen impact severity")
  is_material: bool = Field(default=True, description="Whether change represents a substantive policy shift")
  ai_flagged_minor_but_facts_changed: bool = Field(
      default=False,
      description="True if AI considered change minor/not_material but deterministic facts or keywords changed",
  )
  old: Optional[EvidenceReference] = Field(default=None, description="Original clause location and text")
  new: Optional[EvidenceReference] = Field(default=None, description="Updated clause location and text")
  word_diff: List[WordDiffOp] = Field(default_factory=list, description="Token-level highlight diff ops")
  fact_changes: List[FactChange] = Field(default_factory=list, description="Exact before/after deterministic facts")
  plain_summary: str = Field(default="", description="Citizen-friendly plain-language explanation")
  practical_impact: Optional[str] = Field(default=None, description="Concrete civic implication for applicants")
  uncertainty_note: Optional[str] = Field(default=None, description="Transparent note if text is ambiguous")
  ocr_risk: bool = Field(default=False, description="True if change touches pages flagged with OCR or low quality")
  analysis_state: Literal["analysed", "not_analysed", "failed"] = Field(
      default="not_analysed", description="Status of Gemini AI explanation generation"
  )


class MinorDifferenceItem(BaseModel):
  """Record of a formatting-only, moved, or trivial difference filtered out of main changes."""
  item_id: str = Field(..., description="Identifier for this minor difference")
  diff_type: Literal["formatting_only", "moved", "trivial"] = Field(
      ..., description="Type of noise difference"
  )
  old_page: Optional[int] = Field(default=None, description="Page number in old document")
  new_page: Optional[int] = Field(default=None, description="Page number in new document")
  old_text: str = Field(..., description="Original excerpt in old document")
  new_text: str = Field(..., description="Original excerpt in new document")
  reason: str = Field(..., description="Brief reason why this was classified as non-material noise")


class ComparisonCounts(BaseModel):
  """Aggregated statistics of detected changes and filtered noise."""
  added: int = Field(default=0, description="Count of newly added clauses/sections")
  removed: int = Field(default=0, description="Count of removed/repealed clauses")
  modified: int = Field(default=0, description="Count of substantively modified clauses")
  unchanged: int = Field(default=0, description="Count of identical unchanged clauses")
  moved: int = Field(default=0, description="Count of identical clauses reordered in document")
  formatting_only: int = Field(default=0, description="Count of clauses with formatting/whitespace only shifts")
  not_analysed: int = Field(default=0, description="Count of candidate changes missing AI explanations")


class ComparisonReport(BaseModel):
  """Comprehensive structured report produced by Policy Change Detection."""
  comparison_id: str = Field(..., description="Unique UUID for this comparison")
  old_document_id: str = Field(..., description="UUID of baseline/older document")
  old_document_name: str = Field(..., description="Display filename of old document")
  new_document_id: str = Field(..., description="UUID of revised/newer document")
  new_document_name: str = Field(..., description="Display filename of new document")
  created_at: str = Field(..., description="ISO 8601 UTC creation timestamp")
  language: str = Field(default="en", description="Target language ('en' or 'ta')")
  analysis_status: Literal["queued", "running", "completed", "completed_with_warnings", "failed"] = Field(
      ..., description="Overall completion status of the comparison report"
  )
  warnings: List[str] = Field(default_factory=list, description="System warnings (OCR risk, truncation, etc.)")
  overall_summary: str = Field(default="", description="Executive plain-language synthesis of key policy shifts")
  counts: ComparisonCounts = Field(default_factory=ComparisonCounts, description="Quantitative change breakdown")
  changes: List[ChangeItem] = Field(default_factory=list, description="List of verified policy changes")
  minor_differences_count: int = Field(default=0, description="Total count of filtered formatting/noise differences")
  minor_differences: List[MinorDifferenceItem] = Field(
      default_factory=list, description="Detailed list of minor noise differences (collapsed in UI)"
  )
  truncated_candidates: int = Field(
      default=0, description="Number of candidate changes truncated due to max candidate limit"
  )

  @property
  def status(self) -> str:
    """Convenience alias for analysis_status."""
    return self.analysis_status


# --- API Request and Response Models ---

class CompareRequest(BaseModel):
  """Request schema for initiating a policy document comparison."""
  old_document_id: str = Field(..., description="UUID of older/baseline policy document")
  new_document_id: str = Field(..., description="UUID of newer/revised policy document")
  language: Literal["en", "ta", "auto"] = Field(
      default="auto", description="Desired language for AI summaries and impact analysis"
  )
  force: bool = Field(default=False, description="If True, bypass cached comparison results and recompute")

  @field_validator("new_document_id")
  @classmethod
  def documents_must_differ(cls, v: str, info: Any) -> str:
    old_id = info.data.get("old_document_id")
    if old_id and v and old_id.strip() == v.strip():
      raise ValueError("old_document_id and new_document_id must refer to different documents.")
    return v


class CompareJobResponse(BaseModel):
  """Response schema for comparison status polling and completion."""
  comparison_id: str = Field(..., description="Unique UUID for this comparison")
  status: Literal["queued", "running", "completed", "completed_with_warnings", "failed"] = Field(
      ..., description="Current state of background comparison job"
  )
  progress: str = Field(..., description="Human-readable stage progress description")
  created_at: str = Field(..., description="ISO 8601 creation timestamp")
  report: Optional[ComparisonReport] = Field(default=None, description="Populated once comparison completes")


class CompareListSummary(BaseModel):
  """Summary descriptor for listing past comparisons."""
  comparison_id: str = Field(..., description="Unique comparison UUID")
  old_document_id: str = Field(..., description="Old document UUID")
  old_document_name: str = Field(..., description="Old document filename")
  new_document_id: str = Field(..., description="New document UUID")
  new_document_name: str = Field(..., description="New document filename")
  created_at: str = Field(..., description="ISO 8601 creation timestamp")
  language: str = Field(..., description="Report language")
  status: str = Field(..., description="Completion status")
  counts: ComparisonCounts = Field(..., description="Breakdown of detected changes")


class CompareListResponse(BaseModel):
  """Response schema for listing past comparisons."""
  comparisons: List[CompareListSummary] = Field(default_factory=list)
  total: int = Field(default=0)
