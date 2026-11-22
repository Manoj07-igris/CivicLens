"""Pydantic models for Document Processing and RAG (Module 1 - Policy Intelligence).

Covers document upload, metadata, page extraction, chunking, OCR status,
vector index status, retrieval, and grounded Q&A with verified citations.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.chat import ChatMessage, ToolActivityItem
from app.models.gemini import GeminiTokenUsage


class PageSummary(BaseModel):
  """High-level summary of a single extracted page."""

  page_number: int = Field(..., description="1-based page number")
  char_count: int = Field(..., description="Character count extracted for this page")
  extraction_method: str = Field(
      default="pymupdf",
      description="Extraction method used ('pymupdf', 'ocr', 'none')",
  )
  quality: str = Field(
      default="normal",
      description="Text quality status ('normal', 'low_quality', 'needs_ocr', 'blank')",
  )
  preview: str = Field(
      default="",
      description="Safe leading text preview (first 100-200 characters)",
  )


class PageDetailResponse(BaseModel):
  """Full extracted text and metadata for a single page."""

  document_id: str = Field(..., description="Unique UUID4 document identifier")
  page_number: int = Field(..., description="1-based page number")
  text: str = Field(..., description="Extracted and normalized page text")
  char_count: int = Field(..., description="Length of extracted page text")
  extraction_method: str = Field(
      ..., description="Method used ('pymupdf', 'ocr', 'none')"
  )
  quality: str = Field(
      ..., description="Quality status ('normal', 'low_quality', 'needs_ocr', 'blank')"
  )
  confidence: Optional[float] = Field(
      default=None, description="Optional OCR confidence score if OCR was used"
  )


class DocumentPagesResponse(BaseModel):
  """Paginated list of page details for a document."""

  document_id: str = Field(..., description="Document UUID4 identifier")
  pages: List[PageDetailResponse] = Field(..., description="Page items for current slice")
  total_pages: int = Field(..., description="Total pages in the document")
  page: int = Field(default=1, description="Current page slice index (1-based)")
  page_size: int = Field(default=20, description="Items per page slice")


class DocumentChunk(BaseModel):
  """Page-isolated text chunk prepared for vector retrieval and exact citation."""

  chunk_id: str = Field(..., description="Unique chunk identifier (e.g. docId_p1_c0)")
  document_id: str = Field(..., description="Parent document UUID4 identifier")
  page_number: int = Field(..., description="Exact 1-based page number (never spans multiple pages)")
  chunk_index: int = Field(..., description="0-based index of the chunk within the page")
  text: str = Field(..., description="Normalized chunk text content")
  char_count: int = Field(..., description="Character length of chunk")


class DocumentMetadata(BaseModel):
  """Core metadata and processing status for an uploaded civic document."""

  document_id: str = Field(..., description="UUID4 identifier")
  filename: str = Field(..., description="Sanitized display filename")
  file_size_bytes: int = Field(..., description="Size of original PDF file in bytes")
  page_count: int = Field(default=0, description="Total number of pages")
  sha256: str = Field(..., description="SHA-256 hash of PDF file for duplicate detection")
  status: str = Field(
      default="uploaded",
      description="Lifecycle status: 'uploaded' | 'processing' | 'ready' | 'ready_with_warnings' | 'failed'",
  )
  progress: Optional[Dict[str, int]] = Field(
      default=None,
      description="Current processing progress, e.g. {'current_page': 5, 'total_pages': 10}",
  )
  language: str = Field(
      default="unknown",
      description="Aggregate language detected ('en', 'ta', 'mixed', 'unknown')",
  )
  ocr_applied: bool = Field(
      default=False,
      description="Whether OCR fallback was triggered on any page",
  )
  ocr_page_count: int = Field(
      default=0,
      description="Number of pages processed via OCR",
  )
  warnings: List[str] = Field(
      default_factory=list,
      description="Operational warnings (e.g. missing OCR engine, low-quality pages)",
  )
  error_message: Optional[str] = Field(
      default=None,
      description="Failure details if processing failed",
  )
  uploaded_at: str = Field(..., description="ISO 8601 UTC timestamp of upload")
  processed_at: Optional[str] = Field(
      default=None,
      description="ISO 8601 UTC timestamp when processing completed",
  )
  # RAG Vector Index Status (Phase 8)
  index_status: str = Field(
      default="not_indexed",
      description="Vector index status: 'not_indexed' | 'indexing' | 'indexed' | 'index_failed'",
  )
  index_built_at: Optional[str] = Field(
      default=None,
      description="ISO 8601 UTC timestamp when vector index was created",
  )
  embedding_model: Optional[str] = Field(
      default=None,
      description="Embedding model name used to generate vectors",
  )
  indexed_chunks_count: Optional[int] = Field(
      default=None,
      description="Total number of chunks indexed in the FAISS index",
  )


class DocumentDetailResponse(DocumentMetadata):
  """Comprehensive document details including page summaries and chunk counts."""

  pages_summary: List[PageSummary] = Field(
      default_factory=list,
      description="Per-page overview summaries",
  )
  chunks_count: int = Field(
      default=0,
      description="Total number of chunks generated",
  )


class DocumentCapabilitiesResponse(BaseModel):
  """System capabilities for PDF processing, OCR fallback, and vector embeddings."""

  ocr_available: bool = Field(..., description="Whether Tesseract OCR binary is installed and operational")
  tesseract_version: Optional[str] = Field(default=None, description="Installed Tesseract OCR version if available")
  ocr_languages: List[str] = Field(default_factory=list, description="Configured/available OCR language models")
  max_upload_mb: int = Field(..., description="Maximum allowed PDF upload size in megabytes")
  max_pdf_pages: int = Field(..., description="Maximum allowed pages in a single PDF")
  ocr_max_pages: int = Field(..., description="Maximum pages subject to OCR fallback per document")
  # RAG Capabilities
  embedding_model: str = Field(
      default="intfloat/multilingual-e5-small",
      description="Configured embedding model identifier",
  )
  embedding_available: bool = Field(
      default=True,
      description="Whether local embedding model engine is operational",
  )


class DocumentUploadResponse(BaseModel):
  """Response returned upon accepting a document upload."""

  document_id: str = Field(..., description="Assigned UUID4 document identifier")
  filename: str = Field(..., description="Sanitized display filename")
  file_size_bytes: int = Field(..., description="Size in bytes")
  page_count: int = Field(..., description="Total pages validated")
  status: str = Field(..., description="Initial processing status ('uploaded' or 'ready' if existing duplicate)")
  is_duplicate: bool = Field(
      default=False,
      description="Whether this upload was matched to an existing document by SHA-256 hash",
  )
  message: str = Field(..., description="Human-readable status summary")


class DocumentSummaryRequest(BaseModel):
  """Request to generate an AI summary for a processed document."""

  language: str = Field(
      default="auto",
      description="Target summary language ('en', 'ta', or 'auto' to match document language)",
  )


class DocumentSummaryResponse(BaseModel):
  """AI-generated grounded summary for an official document."""

  document_id: str = Field(..., description="Document UUID4 identifier")
  language: str = Field(..., description="Language in which the summary was generated ('en' or 'ta')")
  summary: str = Field(..., description="Structured Markdown summary grounded strictly in the document text")
  cached: bool = Field(..., description="Whether this response was served from cache")
  model: str = Field(..., description="Gemini model identifier used to produce the summary")


# ============================================================================
# PHASE 8: RAG & QUESTION ANSWERING MODELS
# ============================================================================

class PassageResult(BaseModel):
  """Individual retrieved passage with exact page provenance and scores."""

  chunk_id: str = Field(..., description="Unique chunk identifier")
  document_id: str = Field(..., description="UUID4 document identifier")
  document_name: str = Field(..., description="Sanitized document display name")
  page_number: int = Field(..., description="Authoritative 1-based page number")
  chunk_index: int = Field(..., description="0-based index of the chunk on the page")
  score: float = Field(..., description="Combined retrieval score (0.0 to 1.0)")
  vector_score: float = Field(..., description="Cosine similarity score from FAISS")
  lexical_score: float = Field(..., description="Lexical token matching score")
  excerpt: str = Field(..., description="Safe leading excerpt (first ~250 characters)")
  text: str = Field(..., description="Full text content of the chunk")


class DocumentRetrieveRequest(BaseModel):
  """Request schema for passage retrieval without LLM answer generation."""

  query: str = Field(
      ...,
      min_length=1,
      max_length=1000,
      description="Search query or keyword phrase",
  )
  top_k: int = Field(
      default=6,
      ge=1,
      le=20,
      description="Maximum number of passages to return",
  )


class DocumentRetrieveResponse(BaseModel):
  """Response containing retrieved evidence passages without invoking Gemini."""

  document_id: str = Field(..., description="Document UUID4 identifier")
  query: str = Field(..., description="Search query")
  evidence_level: Literal["strong", "weak", "none"] = Field(
      ..., description="Backend computed evidence confidence level"
  )
  passages: List[PassageResult] = Field(
      default_factory=list, description="Ranked list of retrieved passages"
  )
  total_retrieved: int = Field(..., description="Count of retrieved passages above threshold")


class CitationItem(BaseModel):
  """Passage citation emitted by the Gemini structured output generator."""

  chunk_id: str = Field(..., description="Exact chunk_id of the passage cited")
  quote: Optional[str] = Field(
      default=None,
      description="Short verbatim excerpt copied directly from the passage text",
  )


class GroundedAnswer(BaseModel):
  """Pydantic schema used for Gemini structured JSON output generation."""

  answer: str = Field(
      ...,
      description="The plain-language answer grounded strictly in the provided passages",
  )
  found: bool = Field(
      ...,
      description="Whether the provided passages contain sufficient facts to answer the question",
  )
  citations: List[CitationItem] = Field(
      default_factory=list,
      description="List of passage citations supporting the statements made",
  )
  missing_information: Optional[str] = Field(
      default=None,
      description="Clear statement of what facts or rules the document does not specify",
  )
  follow_up_suggestion: Optional[str] = Field(
      default=None,
      description="Helpful civic suggestion, such as checking official state portals",
  )


class VerifiedCitation(BaseModel):
  """Verified citation returned to the client after backend validation."""

  chunk_id: str = Field(..., description="Validated chunk identifier")
  document_id: str = Field(..., description="Parent document identifier")
  document_name: str = Field(..., description="Display filename of document")
  page_number: int = Field(..., description="Authoritative 1-based page number from metadata")
  excerpt: str = Field(..., description="Passage excerpt for immediate display")
  verified_quote: Optional[str] = Field(
      default=None,
      description="Quote verified to appear verbatim in chunk text, or None if discarded",
  )
  score: float = Field(..., description="Retrieval similarity score")


class AskRequest(BaseModel):
  """Request schema for POST /api/v1/documents/{id}/ask."""

  question: str = Field(
      ...,
      min_length=1,
      max_length=1000,
      description="Citizen's civic question about the document",
  )
  language: Literal["en", "ta", "auto"] = Field(
      default="auto",
      description="Target response language ('en', 'ta', or 'auto' detection)",
  )
  history: List[ChatMessage] = Field(
      default_factory=list,
      description="Optional prior conversational turns to resolve follow-up context",
  )

  @field_validator("question")
  @classmethod
  def question_must_not_be_blank(cls, v: str) -> str:
    stripped = v.strip()
    if not stripped:
      raise ValueError("Question cannot be empty or whitespace only.")
    return stripped


class AskResponse(BaseModel):
  """Complete grounded answer response with verified citations and provenance."""

  answer: str = Field(..., description="Grounded AI response")
  found: bool = Field(..., description="Whether evidence was found in the document")
  language_used: str = Field(..., description="Language used for the answer ('en' or 'ta')")
  evidence_level: Literal["strong", "weak", "none"] = Field(
      ..., description="Backend computed evidence confidence level"
  )
  citations: List[VerifiedCitation] = Field(
      default_factory=list,
      description="Strictly verified backend citations (page numbers from metadata only)",
  )
  missing_information: Optional[str] = Field(
      default=None,
      description="What information is missing from the document",
  )
  follow_up_suggestion: Optional[str] = Field(
      default=None,
      description="Actionable next step or suggestion for citizen",
  )
  retrieved_count: int = Field(..., description="Count of candidate passages retrieved")
  unverified_citations: bool = Field(
      default=False,
      description="True if model claimed found=true but failed citation verification",
  )
  partial_context: bool = Field(
      default=False,
      description="True if passages were truncated to fit the context character budget",
  )
  model: str = Field(..., description="Gemini model identifier used for generation")
  latency_ms: float = Field(..., description="Total processing latency in milliseconds")
  token_usage: Optional[GeminiTokenUsage] = Field(
      default=None, description="Token usage reported by Gemini API"
  )
  tool_activity: List[ToolActivityItem] = Field(
      default_factory=list,
      description="Audit trace of retrieval and generation operations",
  )


class IndexBuildRequest(BaseModel):
  """Request schema to trigger vector index build for a document."""

  force: bool = Field(
      default=False,
      description="Whether to force rebuild the index even if already up-to-date",
  )


class IndexBuildResponse(BaseModel):
  """Status report of vector index build."""

  document_id: str = Field(..., description="Document UUID4 identifier")
  index_status: str = Field(..., description="Current index status ('indexed', 'indexing', 'index_failed')")
  chunks_indexed: int = Field(default=0, description="Number of chunks successfully embedded into FAISS")
  chunks_skipped: int = Field(default=0, description="Number of blank or unreadable chunks skipped")
  embedding_model: str = Field(..., description="Embedding model name used")
  index_built_at: Optional[str] = Field(default=None, description="ISO timestamp of index completion")
  message: str = Field(..., description="Human-readable status summary")
