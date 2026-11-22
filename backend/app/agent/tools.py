"""Tool registry and definitions for the CivicLens Central AI Agent.

Defines all available and planned backend tools, argument schemas using Pydantic,
Gemini FunctionDeclaration generators, execution risk levels, and approval flags.
"""

from dataclasses import dataclass, field
import logging
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional, Type
from pydantic import BaseModel, Field

try:
  from google.genai import types
except ImportError:
  types = None  # type: ignore

from app.core.errors import DocumentNotFoundError, DocumentProcessingError
from app.core.prompts import wrap_untrusted_content

logger = logging.getLogger("civiclens.agent.tools")


# --- Tool Context ---

@dataclass
class EvidenceItem:
  """Unit of concrete, verified document evidence collected by a tool."""
  label: str  # e.g. "E1", "E2", "C1", "C2", "S1", "S2"
  chunk_id: str
  document_id: str
  document_name: str
  page_number: int
  excerpt: str
  score: float = 0.0
  collection: str = "user"  # "user" or "official"
  issuing_authority: Optional[str] = None
  effective_date: Optional[str] = None
  status: Optional[str] = None
  source_url: Optional[str] = None
  quote: Optional[str] = None
  old_page_number: Optional[int] = None
  new_page_number: Optional[int] = None
  old_document_id: Optional[str] = None
  new_document_id: Optional[str] = None
  comparison_id: Optional[str] = None


@dataclass
class EvidenceLedger:
  """Thread-safe, run-scoped ledger collecting verified evidence items."""
  items: Dict[str, EvidenceItem] = field(default_factory=dict)
  _counter: int = 0
  _c_counter: int = 0
  _s_counter: int = 0

  def add_item(
      self,
      chunk_id: str,
      document_id: str,
      document_name: str,
      page_number: int,
      excerpt: str,
      score: float = 0.0,
  ) -> str:
    """Register an evidence passage and return its canonical label (e.g. 'E1')."""
    # De-duplicate if same chunk already registered
    for label, item in self.items.items():
      if item.chunk_id == chunk_id:
        return label

    self._counter += 1
    label = f"E{self._counter}"
    self.items[label] = EvidenceItem(
        label=label,
        chunk_id=chunk_id,
        document_id=document_id,
        document_name=document_name,
        page_number=page_number,
        excerpt=excerpt,
        score=score,
        collection="user",
    )
    return label

  def add_comparison_item(
      self,
      change_id: str,
      old_doc_id: str,
      old_doc_name: str,
      old_page: int,
      new_doc_id: str,
      new_doc_name: str,
      new_page: int,
      excerpt: str,
      comparison_id: str,
  ) -> str:
    """Register a policy comparison change item with a canonical label (e.g. 'C1')."""
    for label, item in self.items.items():
      if item.chunk_id == change_id:
        return label

    self._c_counter += 1
    label = f"C{self._c_counter}"
    self.items[label] = EvidenceItem(
        label=label,
        chunk_id=change_id,
        document_id=new_doc_id,
        document_name=new_doc_name,
        page_number=new_page,
        excerpt=excerpt,
        old_page_number=old_page,
        new_page_number=new_page,
        old_document_id=old_doc_id,
        new_document_id=new_doc_id,
        comparison_id=comparison_id,
        collection="user",
    )
    return label

  def add_source_item(
      self,
      chunk_id: str,
      source_id: str,
      source_title: str,
      page_number: int,
      excerpt: str,
      collection: str = "official",
      issuing_authority: Optional[str] = None,
      effective_date: Optional[str] = None,
      status: Optional[str] = None,
      source_url: Optional[str] = None,
      quote: Optional[str] = None,
      score: float = 0.0,
  ) -> str:
    """Register an official source or fact verification evidence item with label 'S1', 'S2'."""
    for label, item in self.items.items():
      if item.chunk_id == chunk_id:
        return label

    self._s_counter += 1
    label = f"S{self._s_counter}"
    self.items[label] = EvidenceItem(
        label=label,
        chunk_id=chunk_id,
        document_id=source_id,
        document_name=source_title,
        page_number=page_number,
        excerpt=excerpt,
        score=score,
        collection=collection,
        issuing_authority=issuing_authority,
        effective_date=effective_date,
        status=status,
        source_url=source_url,
        quote=quote,
    )
    return label

  def get_item(self, label: str) -> Optional[EvidenceItem]:
    clean = label.strip().strip("[]").upper()
    return self.items.get(clean)

  def list_items(self) -> List[EvidenceItem]:
    return list(self.items.values())


@dataclass
class AgentContext:
  """Context passed into tool handlers during orchestrator execution."""
  store: Any
  rag_service: Any
  comparison_service: Optional[Any] = None
  source_service: Optional[Any] = None
  verification_service: Optional[Any] = None
  public_service_service: Optional[Any] = None
  selected_document_ids: List[str] = field(default_factory=list)
  evidence_ledger: EvidenceLedger = field(default_factory=EvidenceLedger)
  service_guides: List[Any] = field(default_factory=list)
  grievance_service: Optional[Any] = None
  grievance_records: List[Any] = field(default_factory=list)
  browser_service: Optional[Any] = None
  browser_sessions: List[Any] = field(default_factory=list)
  request_id: Optional[str] = None
  conversation_id: Optional[str] = None
  language: str = "auto"
  current_step: int = 0
  check_claim_called: bool = False
  draft_complaint_called: bool = False
  register_demo_complaint_called: bool = False
  open_service_portal_called: bool = False
  fill_demo_form_called: bool = False
  submit_demo_application_called: bool = False
  user_id: Optional[str] = None


# --- Tool Argument Schemas ---

class ListDocumentsArgs(BaseModel):
  """Arguments for listing ready uploaded documents."""
  limit: int = Field(
      default=20,
      ge=1,
      le=50,
      description="Maximum number of uploaded documents to return (1-50)",
  )


class ReadDocumentArgs(BaseModel):
  """Arguments for reading specific pages of an uploaded document."""
  document_id: str = Field(
      ...,
      description="The unique UUID of the uploaded document to read",
  )
  page_number: Optional[int] = Field(
      default=None,
      ge=1,
      description="Specific 1-based page number to read",
  )
  start_page: Optional[int] = Field(
      default=None,
      ge=1,
      description="Optional start page for a range (inclusive)",
  )
  end_page: Optional[int] = Field(
      default=None,
      ge=1,
      description="Optional end page for a range (inclusive)",
  )


class RetrieveEvidenceArgs(BaseModel):
  """Arguments for semantic and lexical passage retrieval from an uploaded document."""
  document_id: str = Field(
      ...,
      description="The unique UUID of the uploaded document to retrieve evidence from",
  )
  query: str = Field(
      ...,
      min_length=1,
      max_length=500,
      description="Search query describing the specific rule, requirement, eligibility, or benefit to locate",
  )
  top_k: int = Field(
      default=4,
      ge=1,
      le=8,
      description="Number of relevant passages to retrieve (1 to 8)",
  )


class CompareDocumentsArgs(BaseModel):
  """Arguments for comparing two policy documents."""
  old_document_id: str = Field(
      ...,
      description="The unique UUID of the older/baseline government document",
  )
  new_document_id: str = Field(
      ...,
      description="The unique UUID of the newer/revised government document",
  )
  focus: Optional[str] = Field(
      default=None,
      description="Optional focus area (e.g. 'deadlines', 'eligibility', 'amounts', 'benefits')",
  )


class SearchOfficialSourcesArgs(BaseModel):
  """Arguments for searching official government sources and legal notices."""
  query: str = Field(
      ...,
      min_length=1,
      max_length=500,
      description="Civic question, scheme name, circular number, or policy topic to search in official records",
  )
  scope: Literal["official", "official_and_documents", "documents"] = Field(
      default="official",
      description="Search scope ('official' library, 'official_and_documents', or 'documents')",
  )
  top_k: int = Field(
      default=4,
      ge=1,
      le=8,
      description="Number of relevant passages to retrieve (1-8)",
  )


class CheckClaimArgs(BaseModel):
  """Arguments for verifying a public statement or viral claim against official state records."""
  claim: str = Field(
      ...,
      min_length=1,
      max_length=1000,
      description="The specific factual statement, viral claim, or news report to verify against official state records",
  )
  scope: Literal["official", "official_and_documents", "documents"] = Field(
      default="official",
      description="Scope to verify against ('official', 'official_and_documents', or 'documents')",
  )
  document_ids: List[str] = Field(
      default_factory=list,
      description="Optional active user document UUIDs if verifying against user documents",
  )


class GenerateChecklistArgs(BaseModel):
  """Arguments for generating public service procedural guidance, required documents, and interactive checklist."""
  query: str = Field(
      ...,
      min_length=3,
      max_length=600,
      description="The public service procedure the citizen wants to apply for (e.g. 'income certificate', 'widow pension', 'building permit')",
  )
  applicant_type: Optional[str] = Field(
      default="unspecified",
      description="Demographic category of the applicant: student, farmer, worker, senior_citizen, woman, business_owner, other, unspecified",
  )
  applicant_situation: Optional[str] = Field(
      default=None,
      max_length=500,
      description="Optional specific citizen context or situation",
  )


class DraftComplaintArgs(BaseModel):
  """Arguments for drafting a formal civic grievance complaint."""
  description: str = Field(
      ...,
      min_length=10,
      max_length=2000,
      description="Citizen's description of the civic problem (e.g. damaged road, water leak, streetlight outage, garbage, drainage)",
  )
  location_text: Optional[str] = Field(
      default=None,
      max_length=300,
      description="Optional street name, area, or landmark where problem exists",
  )
  duration_text: Optional[str] = Field(
      default=None,
      max_length=100,
      description="Optional duration the problem has persisted, e.g. 'since two weeks'",
  )
  category_hint: Optional[str] = Field(
      default=None,
      description="Optional category: roads, water_supply, streetlights, waste_management, drainage_sewage, public_infrastructure_damage, other",
  )
  language: Optional[str] = Field(
      default="en",
      description="Language for the draft: 'en' or 'ta'",
  )


class RegisterDemoComplaintArgs(BaseModel):
  """Arguments for registering a simulated demo complaint record."""
  grievance_id: str = Field(
      ...,
      description="The UUID of the draft grievance record to register as a demo complaint",
  )


class OpenServicePortalArgs(BaseModel):
  """Arguments for launching a controlled browser demo simulation of a public service portal."""
  portal_id: str = Field(
      default="prt_demo_portal",
      description="Identifier of the portal registry entry. Must be a local demo portal (e.g. prt_demo_portal)",
  )
  lang: Optional[str] = Field(
      default="en",
      description="Language for the demo portal interface: 'en' or 'ta'",
  )


class FillDemoFormArgs(BaseModel):
  """Arguments for filling form steps in the demo public service portal with fictional data."""
  session_id: str = Field(
      ...,
      description="The UUID of the active browser demo session",
  )
  step_index: int = Field(
      ...,
      ge=1,
      le=4,
      description="The step index to fill (1 for Applicant, 2 for Address, 3 for Income, 4 for Purpose)",
  )
  values: Dict[str, Any] = Field(
      ...,
      description="Dictionary of fictional field values to fill into the demo portal",
  )
  fictional_confirmed: bool = Field(
      default=True,
      description="Affirmation that all submitted values are fictional demo data",
  )


class SubmitDemoApplicationArgs(BaseModel):
  """Arguments for submitting the demo application simulation with verified human review hash."""
  session_id: str = Field(
      ...,
      description="The UUID of the active browser demo session",
  )
  review_hash: str = Field(
      ...,
      description="The canonical SHA-256 review hash produced during step 5 review",
  )
  fictional_confirmed: bool = Field(
      default=True,
      description="Affirmation that all submitted values are fictional demo data",
  )


# Empty arguments models for planned future tools
class EmptyPlannedArgs(BaseModel):
  pass


# --- Tool Definition ---

RiskLevel = Literal["read_only", "sensitive", "irreversible"]
ToolStatus = Literal["available", "planned"]


@dataclass
class ToolDefinition:
  """Descriptor for a tool callable by the Central AI Agent."""
  name: str
  description: str
  args_model: Type[BaseModel]
  handler: Callable[[Any, AgentContext], Awaitable[Dict[str, Any]]]
  risk_level: RiskLevel = "read_only"
  requires_approval: bool = False
  status: ToolStatus = "available"
  ui_label_key: str = ""
  timeout_seconds: int = 15


# --- Tool Handlers ---

async def handle_list_documents(args: ListDocumentsArgs, ctx: AgentContext) -> Dict[str, Any]:
  """Return ready uploaded documents from the DocumentStore."""
  all_docs = ctx.store.list_documents(owner_id=ctx.user_id)
  ready_docs = [
      {
          "document_id": d["document_id"],
          "filename": d.get("filename", "unknown.pdf"),
          "page_count": d.get("page_count", 0),
          "language": d.get("language", "en"),
          "index_status": d.get("index_status", "not_indexed"),
      }
      for d in all_docs
      if d.get("status") in ("ready", "ready_with_warnings")
  ][: args.limit]

  return {
      "documents": ready_docs,
      "total_ready_count": len(ready_docs),
      "message": (
          f"Found {len(ready_docs)} ready document(s)."
          if ready_docs
          else "No ready documents uploaded yet. Ask the user to upload an official policy PDF."
      ),
  }


async def handle_read_document(args: ReadDocumentArgs, ctx: AgentContext) -> Dict[str, Any]:
  """Read text from specified pages of an uploaded document with character bounds."""
  doc_id = args.document_id.strip()
  meta = ctx.store.get_metadata(doc_id, owner_id=ctx.user_id)
  if not meta:
    raise DocumentNotFoundError(f"Document '{doc_id}' not found.")

  doc_name = meta.get("filename", "document.pdf")
  total_pages = meta.get("page_count", 1)

  # Determine target page numbers
  if args.page_number is not None:
    target_pages = [args.page_number]
  elif args.start_page is not None or args.end_page is not None:
    start = max(1, args.start_page or 1)
    end = min(total_pages, args.end_page or total_pages)
    target_pages = list(range(start, end + 1))
  else:
    # Default to first 3 pages if unspecified
    target_pages = list(range(1, min(4, total_pages + 1)))

  # Read pages up to a character cap
  MAX_READ_CHARS = 8000
  collected_pages = []
  total_chars = 0
  truncated = False

  for p_num in target_pages:
    if p_num > total_pages:
      continue
    page_rec = ctx.store.get_page(doc_id, p_num)
    if not page_rec:
      continue
    text = (page_rec.get("text") or "").strip()
    if not text:
      continue

    # Register in evidence ledger so citations can link back
    evidence_label = ctx.evidence_ledger.add_item(
        chunk_id=f"{doc_id}_p{p_num}",
        document_id=doc_id,
        document_name=doc_name,
        page_number=p_num,
        excerpt=text[:250].replace("\n", " ").strip(),
    )

    if total_chars + len(text) > MAX_READ_CHARS:
      remaining = MAX_READ_CHARS - total_chars
      text = text[:remaining] + "\n[Text truncated due to size limit]"
      truncated = True

    collected_pages.append({
        "page_number": p_num,
        "evidence_label": evidence_label,
        "text": wrap_untrusted_content(text, f"doc_p{p_num}"),
    })
    total_chars += len(text)
    if truncated:
      break

  return {
      "document_id": doc_id,
      "filename": doc_name,
      "pages_read": len(collected_pages),
      "pages": collected_pages,
      "truncated": truncated,
  }


async def handle_retrieve_evidence(args: RetrieveEvidenceArgs, ctx: AgentContext) -> Dict[str, Any]:
  """Retrieve ranked passages using hybrid vector + lexical search via RAGService."""
  doc_id = args.document_id.strip()
  meta = ctx.store.get_metadata(doc_id, owner_id=ctx.user_id)
  if not meta:
    raise DocumentNotFoundError(f"Document '{doc_id}' not found.")

  doc_name = meta.get("filename", "document.pdf")

  passages, evidence_level = await ctx.rag_service.retrieve(
      document_id=doc_id,
      query=args.query,
      top_k=args.top_k,
  )

  evidence_items = []
  for p in passages:
    label = ctx.evidence_ledger.add_item(
        chunk_id=p.chunk_id,
        document_id=doc_id,
        document_name=doc_name,
        page_number=p.page_number,
        excerpt=p.excerpt,
        score=p.score,
    )
    evidence_items.append({
        "label": label,
        "chunk_id": p.chunk_id,
        "page_number": p.page_number,
        "document_name": doc_name,
        "relevance_score": p.score,
        "text": wrap_untrusted_content(p.text, label.lower()),
    })

  return {
      "document_id": doc_id,
      "filename": doc_name,
      "query": args.query,
      "evidence_level": evidence_level,
      "passages_count": len(evidence_items),
      "evidence": evidence_items,
      "instruction": (
          "Cite statements using ONLY the bracketed labels provided above (e.g. [E1]). "
          "Do not state document filenames or page numbers yourself. "
          if evidence_level != "none"
          else "No passages met the relevance threshold. State honestly that the document does not contain this information."
      ),
  }


async def handle_compare_documents(
    args: CompareDocumentsArgs, ctx: AgentContext
) -> Dict[str, Any]:
  """Execute policy document comparison between two versions."""
  old_id = args.old_document_id.strip()
  new_id = args.new_document_id.strip()

  if old_id == new_id:
    return {
        "error": "The older and newer document IDs must be different to perform a comparison.",
        "status": "invalid_parameters",
    }

  comp_service = ctx.comparison_service
  if comp_service is None:
    from app.services.comparison_service import get_comparison_service
    comp_service = get_comparison_service()

  try:
    report = await comp_service.run_comparison(
        old_doc_id=old_id,
        new_doc_id=new_id,
        language=ctx.language or "auto",
        force=False,
    )
  except Exception as exc:
    logger.exception("compare_documents tool execution failed: %s", exc)
    return {
        "error": f"Failed to compare documents: {str(exc)}",
        "status": "execution_failed",
    }

  material_changes = [c for c in report.changes if c.is_material]
  top_changes = material_changes[:8] if material_changes else report.changes[:8]

  registered_changes = []
  for chg in top_changes:
    old_p = chg.old.page_start if chg.old else 1
    new_p = chg.new.page_start if chg.new else 1
    excerpt_txt = chg.plain_summary or (chg.new.text_excerpt if chg.new else "")

    c_label = ctx.evidence_ledger.add_comparison_item(
        change_id=chg.change_id,
        old_doc_id=report.old_document_id,
        old_doc_name=report.old_document_name,
        old_page=old_p,
        new_doc_id=report.new_document_id,
        new_doc_name=report.new_document_name,
        new_page=new_p,
        excerpt=excerpt_txt,
        comparison_id=report.comparison_id,
    )

    facts_summary = "; ".join(f"{fc.fact_type}: '{fc.old_value}' -> '{fc.new_value}'" for fc in chg.fact_changes) if chg.fact_changes else None

    registered_changes.append({
        "citation_label": f"[{c_label}]",
        "change_type": chg.change_type,
        "category": chg.category,
        "importance": chg.importance,
        "summary": chg.plain_summary,
        "practical_impact": chg.practical_impact,
        "fact_changes": facts_summary,
        "old_page": old_p,
        "new_page": new_p,
    })

  return {
      "status": "success",
      "comparison_id": report.comparison_id,
      "old_document_name": report.old_document_name,
      "new_document_name": report.new_document_name,
      "counts": {
          "added": report.counts.added,
          "removed": report.counts.removed,
          "modified": report.counts.modified,
          "minor_differences": report.minor_differences_count,
      },
      "overall_summary": report.overall_summary,
      "changes": registered_changes,
      "instruction": (
          f"Found {len(report.changes)} changes between {report.old_document_name} and {report.new_document_name}. "
          "Cite statements using ONLY the bracketed labels provided above (e.g. [C1], [C2]). "
          "Do not state document filenames or page numbers yourself."
      ),
  }


async def handle_search_official_sources(
    args: SearchOfficialSourcesArgs, ctx: AgentContext
) -> Dict[str, Any]:
  """Search official state records and gazettes via multi-source hybrid retrieval."""
  from app.services.source_library import get_source_library_service
  src_service = ctx.source_service or get_source_library_service()
  rag_svc = ctx.rag_service

  sources_to_search = []
  if args.scope in ("official", "official_and_documents"):
    for s in src_service.list_sources():
      sources_to_search.append({
          "source_id": s.source_id,
          "title": s.title,
          "issuing_authority": s.issuing_authority,
          "effective_date": s.effective_date,
          "status": s.status,
          "series_id": s.series_id,
          "source_url": s.source_url,
          "collection": "official",
          "store": src_service.doc_store,
      })

  if args.scope in ("documents", "official_and_documents"):
    doc_ids = ctx.selected_document_ids
    for d_id in doc_ids:
      m = ctx.store.get_metadata(d_id)
      if m:
        sources_to_search.append({
            "source_id": d_id,
            "title": m.get("filename", "User Document"),
            "issuing_authority": None,
            "effective_date": None,
            "status": m.get("status", "ready"),
            "series_id": None,
            "source_url": None,
            "collection": "user",
            "store": ctx.store,
        })

  if not sources_to_search:
    return {
        "passages": [],
        "evidence_level": "none",
        "message": (
            "The official source library is currently empty. "
            "Please add official government documents or upload documents to search."
        ),
    }

  passages, ev_level, skipped = await rag_svc.retrieve_across(
      sources=sources_to_search,
      query=args.query,
      top_k_per_source=3,
      top_k_total=args.top_k,
  )

  returned_passages = []
  for p in passages:
    label = ctx.evidence_ledger.add_source_item(
        chunk_id=p["chunk_id"],
        source_id=p["source_id"],
        source_title=p["source_title"],
        page_number=p["page_number"],
        excerpt=p["excerpt"],
        collection=p["collection"],
        issuing_authority=p.get("issuing_authority"),
        effective_date=p.get("effective_date"),
        status=p.get("status"),
        source_url=p.get("source_url"),
        score=p["score"],
    )
    returned_passages.append({
        "label": label,
        "source_title": p["source_title"],
        "collection": p["collection"],
        "issuing_authority": p.get("issuing_authority"),
        "effective_date": p.get("effective_date"),
        "status": p.get("status"),
        "page_number": p["page_number"],
        "score": p["score"],
        "text": wrap_untrusted_content(p["text"], f"source_{label}"),
    })

  return {
      "query": args.query,
      "evidence_level": ev_level,
      "passages_count": len(returned_passages),
      "passages": returned_passages,
      "sources_searched_count": len(sources_to_search),
      "instruction": (
          f"Retrieved {len(returned_passages)} passage(s) from official/curated sources. "
          "Cite statements using ONLY the bracketed labels provided above (e.g. [S1], [S2]). "
          "Do not state document filenames or page numbers yourself."
      ),
  }


async def handle_check_claim(
    args: CheckClaimArgs, ctx: AgentContext
) -> Dict[str, Any]:
  """Verify public claims against official state records and user documents."""
  if ctx.check_claim_called:
    return {
        "error": "check_claim has already been called in this agent run. Limit 1 claim verification per turn.",
        "status": "skipped",
    }
  ctx.check_claim_called = True

  from app.models.verification import VerifyRequest
  from app.services.verification_service import get_verification_service
  v_svc = ctx.verification_service or get_verification_service()
  doc_ids = args.document_ids or ctx.selected_document_ids

  v_req = VerifyRequest(
      claim=args.claim,
      language=ctx.language if ctx.language in ("en", "ta") else "auto",
      scope=args.scope,
      document_ids=doc_ids[:5],
      force=False,
  )

  v_id, _ = v_svc.start_verification(v_req, client_key="agent")
  report = await v_svc.execute_verification(v_id)

  top_evidence = []
  for c_res in report.claims:
    for ev in c_res.supporting_evidence + c_res.contradicting_evidence:
      lbl = ctx.evidence_ledger.add_source_item(
          chunk_id=f"{ev.source_id}_p{ev.page_number}_{ev.label}",
          source_id=ev.source_id,
          source_title=ev.source_title,
          page_number=ev.page_number,
          excerpt=ev.excerpt,
          collection=ev.collection,
          issuing_authority=ev.issuing_authority,
          effective_date=ev.effective_date,
          status=ev.status,
          source_url=ev.source_url,
          quote=ev.quote,
      )
      top_evidence.append({
          "label": f"[{lbl}]",
          "source_title": ev.source_title,
          "collection": ev.collection,
          "page_number": ev.page_number,
          "quote": ev.quote,
          "status": ev.status,
      })

  claims_summary = [
      {
          "claim_id": c.claim_id,
          "claim_text": c.claim_text,
          "verdict": c.verdict,
          "verdict_basis": c.verdict_basis,
          "explanation": c.explanation,
      }
      for c in report.claims
  ]

  return {
      "verification_id": report.verification_id,
      "overall_verdict": report.overall_verdict,
      "overall_summary": report.overall_summary,
      "claims": claims_summary,
      "evidence_passages": top_evidence[:6],
      "coverage": {
          "official_sources_count": report.coverage.official_sources_searched_count,
          "passages_examined": report.coverage.passages_examined_count,
          "library_version": report.coverage.library_version,
      },
      "instruction": (
          f"Verification completed with verdict: '{report.overall_verdict.upper()}'. "
          "Relay this backend verdict and explanation FAITHFULLY. NEVER upgrade or soften the category. "
          "Cite supporting or contradicting passages using ONLY their bracketed labels (e.g. [S1], [S2])."
      ),
  }


async def handle_generate_checklist(args: GenerateChecklistArgs, ctx: AgentContext) -> Dict[str, Any]:
  """Generates evidence-backed procedural guidance, interactive checklist, and official portal links."""
  from app.services.public_service_service import get_public_service_service
  from app.models.service_guide import ServiceGuideRequest

  ps_svc = ctx.public_service_service or get_public_service_service()
  app_type = args.applicant_type if args.applicant_type in (
      "student", "farmer", "worker", "senior_citizen", "woman", "business_owner", "other"
  ) else "unspecified"

  req = ServiceGuideRequest(
      query=args.query,
      applicant_type=app_type,  # type: ignore
      applicant_situation=args.applicant_situation,
      language="auto",
      allow_general=False,
      source_scope="all",
  )

  report = await ps_svc.generate_guide(req, client_key=ctx.request_id or "agent")
  ctx.service_guides.append(report)

  for src in report.cited_sources:
    if src.source_type == "official_source":
      ctx.evidence_ledger.add_source_item(
          chunk_id=f"{src.source_id}_p{src.page_number}",
          source_id=src.source_id,
          source_title=src.title,
          page_number=src.page_number,
          excerpt=src.snippet,
          collection="official",
          issuing_authority=src.issuing_authority,
      )
    else:
      ctx.evidence_ledger.add_item(
          chunk_id=f"{src.source_id}_p{src.page_number}",
          document_id=src.source_id,
          document_name=src.title,
          page_number=src.page_number,
          excerpt=src.snippet,
      )

  checklist_summary = [
      {
          "id": i.id,
          "category": i.category,
          "text": i.text,
          "status": i.status,
          "source_label": i.source_label,
          "source_page": i.source_page,
          "caution": i.caution,
      }
      for i in report.checklist_items[:12]
  ]

  key_facts_summary = [
      {
          "type": k.fact_type,
          "label": k.label,
          "value": k.value_text,
          "source_label": k.source_label,
      }
      for k in report.key_facts
  ]

  portals_summary = [
      {
          "name": p.portal.name,
          "url": p.portal.url,
          "domain": p.portal.domain_hint,
          "caution": p.portal.caution_notes,
      }
      for p in report.matched_portals
  ]

  return {
      "guide_id": report.id,
      "mode": report.mode,
      "procedure_overview": report.procedure_overview,
      "total_checklist_items": len(report.checklist_items),
      "confirmed_items_count": sum(1 for i in report.checklist_items if i.status == "source_confirmed"),
      "checklist_items": checklist_summary,
      "key_facts": key_facts_summary,
      "vetted_portals": portals_summary,
      "instruction": (
          f"Public service guidance generated in mode '{report.mode}'. Present the procedural overview, "
          "mention key confirmed requirements and facts, and reference vetted portals. "
          "NEVER invent or write portal URLs or telephone numbers not present in the vetted_portals above. "
          "If mode is 'no_sources', inform citizen that official gazettes were not found and show vetted portals."
      ),
  }


async def handle_draft_complaint(args: DraftComplaintArgs, ctx: AgentContext) -> Dict[str, Any]:
  """Drafts a formal, respectful, and factual civic grievance petition."""
  if ctx.draft_complaint_called:
    return {
        "error": "draft_complaint has already been called in this agent run. Limit 1 complaint draft per turn.",
        "status": "skipped",
    }
  ctx.draft_complaint_called = True

  from app.services.grievance_service import get_grievance_service
  from app.models.grievance import GrievanceAnalyzeRequest

  svc = ctx.grievance_service or get_grievance_service()
  draft_lang = args.language if args.language in ("en", "ta") else ("ta" if ctx.language == "ta" else "en")

  req = GrievanceAnalyzeRequest(
      description=args.description,
      location_text=args.location_text or "",
      duration_text=args.duration_text or "",
      language_of_draft=draft_lang,  # type: ignore
      category_hint=args.category_hint,
      image_id=None,
      image_consent=False,
  )

  grievance = await svc.analyze_grievance(req)
  ctx.grievance_records.append(grievance)

  channels_summary = [
      {
          "name": ch.name,
          "authority": ch.department or "Government Department",
          "declared_link": ch.url,
          "domain_hint": ch.domain_hint,
          "coverage": ch.coverage_area,
          "match_basis": ch.match_basis,
          "caution": ch.caution_notes or "Declared by the app owner, not verified by CivicLens.",
      }
      for ch in grievance.channels.channels
  ]

  return {
      "grievance_id": grievance.id,
      "category": grievance.category,
      "category_confidence": grievance.category_confidence,
      "severity": grievance.severity,
      "safety_risk": grievance.safety_risk,
      "emergency_notice": grievance.emergency_notice,
      "draft_subject": grievance.draft.subject_line,
      "draft_body": grievance.draft.body,
      "location_line": grievance.draft.location_line,
      "missing_details": grievance.missing_details,
      "matched_channels": channels_summary,
      "generic_guidance": grievance.channels.generic_guidance if not channels_summary else [],
      "warnings": grievance.warnings,
      "draft_hash": grievance.draft_hash,
      "note": "A photo can be added and analyzed in the Grievance Centre.",
      "instruction": (
          "Present this as a formal DRAFT complaint for citizen review. "
          "Do NOT invent any facts, measurements, or quantities not stated by the user. "
          "If safety_risk is true, show the emergency notice FIRST before other content. "
          "Recommend reporting channels ONLY from the matched_channels list with the caution caveat. "
          "Clearly state that this is a draft and has NOT been submitted to any authority. "
          "Inform the citizen that they can open the Grievance Centre to add a photo or review."
      ),
  }


async def handle_register_demo_complaint(
    args: RegisterDemoComplaintArgs, ctx: AgentContext
) -> Dict[str, Any]:
  """Registers a simulated demo complaint record bound to citizen approval."""
  if ctx.register_demo_complaint_called:
    return {
        "error": "register_demo_complaint has already been called in this agent run. Limit 1 demo registration per turn.",
        "status": "skipped",
    }
  ctx.register_demo_complaint_called = True

  from app.services.grievance_service import get_grievance_service
  from app.services.grievance_store import get_grievance_store

  store = get_grievance_store()
  svc = ctx.grievance_service or get_grievance_service()

  grievance = store.get(args.grievance_id)
  registered = svc.register_demo_record(
      grievance_id=grievance.id,
      approved=True,
      approved_hash=grievance.draft_hash,
      method="agent",
  )
  ctx.grievance_records.append(registered)

  return {
      "grievance_id": registered.id,
      "demo_id": registered.demo.demo_id if registered.demo else "DEMO-UNKNOWN",
      "status": registered.demo.status if registered.demo else "registered",
      "is_demo": True,
      "notice": registered.demo.notice if registered.demo else "Demo record only. Not sent to any government authority.",
      "registered_at": registered.demo.registered_at if registered.demo else "",
      "category": registered.category,
      "subject_line": registered.draft.subject_line,
      "instruction": (
          f"Demo record created successfully with ID {registered.demo.demo_id if registered.demo else ''}. "
          "Clearly explain to the citizen that this is a DEMO record only, created inside CivicLens, and NOTHING was sent to any authority."
      ),
  }


async def handle_open_service_portal(
    args: OpenServicePortalArgs, ctx: AgentContext
) -> Dict[str, Any]:
  """Launches an interactive controlled browser session navigating strictly to local demo portal."""
  from app.services.browser_service import get_browser_service
  bs = ctx.browser_service or get_browser_service()
  record = bs.start_session(portal_id=args.portal_id, lang=args.lang or "en")
  ctx.open_service_portal_called = True
  ctx.browser_sessions.append(record)

  return {
      "session_id": record.session_id,
      "portal_id": record.portal_id,
      "portal_url": record.portal_url,
      "status": record.status,
      "current_step": record.current_step,
      "total_steps": record.total_steps,
      "last_screenshot_url": record.last_screenshot_url,
      "disclaimer": "LOCAL DEMO ONLY: Educational simulation on localhost. No real data is stored or transmitted.",
      "instruction": (
          f"Demo portal session initialized with ID {record.session_id}. "
          "Explain that this is an educational simulation sandbox running strictly on localhost. "
          "Ask the citizen if they would like to practice filling Step 1 with sample fictional data."
      ),
  }


async def handle_fill_demo_form(
    args: FillDemoFormArgs, ctx: AgentContext
) -> Dict[str, Any]:
  """Fills form fields in the demo portal with fictional values after PII scanning."""
  from app.services.browser_service import get_browser_service
  bs = ctx.browser_service or get_browser_service()
  record = bs.fill_step(
      session_id=args.session_id,
      step_index=args.step_index,
      values=args.values,
      fictional_confirmed=args.fictional_confirmed,
  )
  ctx.fill_demo_form_called = True

  # Update in ctx.browser_sessions
  existing = next((s for s in ctx.browser_sessions if s.session_id == record.session_id), None)
  if existing:
    ctx.browser_sessions.remove(existing)
  ctx.browser_sessions.append(record)

  return {
      "session_id": record.session_id,
      "step_index": args.step_index,
      "status": record.status,
      "current_step": record.current_step,
      "filled_fields_count": len(args.values),
      "last_screenshot_url": record.last_screenshot_url,
      "disclaimer": "Fictional values entered into local simulation form.",
      "instruction": (
          f"Step {args.step_index} filled with {len(args.values)} fictional values. "
          "Show the citizen what was filled and confirm if they would like to proceed to the next step."
      ),
  }


async def handle_submit_demo_application(
    args: SubmitDemoApplicationArgs, ctx: AgentContext
) -> Dict[str, Any]:
  """Submits the demo application bound to verified human review hash."""
  from app.services.browser_service import get_browser_service
  bs = ctx.browser_service or get_browser_service()
  result = bs.submit_demo(
      session_id=args.session_id,
      review_hash=args.review_hash,
      fictional_confirmed=args.fictional_confirmed,
  )
  ctx.submit_demo_application_called = True

  record = bs.get_session(args.session_id)
  existing = next((s for s in ctx.browser_sessions if s.session_id == record.session_id), None)
  if existing:
    ctx.browser_sessions.remove(existing)
  ctx.browser_sessions.append(record)

  return {
      "session_id": result.session_id,
      "submission_id": result.submission_id,
      "application_number": result.application_number,
      "status": result.status,
      "timestamp": result.timestamp,
      "confirmation_message": result.confirmation_message,
      "disclaimer": "Simulated practice submission only. No real application was submitted to any government portal.",
      "instruction": (
          f"Demo application submitted successfully with reference {result.application_number}. "
          "Remind the citizen that this was a local practice simulation; real applications must be filed "
          "directly on official government portals."
      ),
  }


async def handle_planned_tool(args: Any, ctx: AgentContext) -> Dict[str, Any]:
  """Fallback handler for planned tools that are not yet available in this phase."""
  raise DocumentProcessingError(
      "This capability is planned for an upcoming CivicLens phase and is not available in this version."
  )


# --- Tool Registry ---

class ToolRegistry:
  """Central registry holding all tool definitions for the central agent."""

  def __init__(self) -> None:
    self._tools: Dict[str, ToolDefinition] = {}

  def register(self, tool: ToolDefinition) -> None:
    """Register a tool definition."""
    self._tools[tool.name] = tool
    logger.debug("Registered agent tool: %s (status=%s, risk=%s)", tool.name, tool.status, tool.risk_level)

  def get(self, name: str) -> Optional[ToolDefinition]:
    """Retrieve a tool definition by name."""
    return self._tools.get(name)

  def list_available(self) -> List[ToolDefinition]:
    """List tools currently available to the model."""
    return [t for t in self._tools.values() if t.status == "available"]

  def list_all(self) -> List[ToolDefinition]:
    """List all registered tools (both available and planned)."""
    return list(self._tools.values())

  def to_gemini_declarations(self) -> List[Any]:
    """Generate Gemini FunctionDeclarations for all available tools."""
    available = self.list_available()
    declarations = []

    for t in available:
      schema = t.args_model.model_json_schema()
      # Clean schema for Gemini parameters
      clean_schema = {
          "type": "object",
          "properties": schema.get("properties", {}),
          "required": schema.get("required", []),
      }

      if types is not None:
        decl = types.FunctionDeclaration(
            name=t.name,
            description=t.description,
            parameters_json_schema=clean_schema,
        )
        declarations.append(decl)
      else:
        declarations.append({
            "name": t.name,
            "description": t.description,
            "parameters": clean_schema,
        })

    if types is not None:
      return [types.Tool(function_declarations=declarations)]
    return declarations


# --- Singleton / Built-in Registry Setup ---

_registry_instance: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
  """Return the singleton ToolRegistry initialized with all CivicLens tools."""
  global _registry_instance
  if _registry_instance is None:
    reg = ToolRegistry()

    # 1. Available Tools (Phase 9)
    reg.register(
        ToolDefinition(
            name="list_documents",
            description=(
                "Lists the citizen's uploaded government documents that are processed and ready. "
                "Returns document IDs, filenames, page counts, languages, and vector indexing status. "
                "Use when the user refers to 'this document', 'the PDF', or 'the circular' without "
                "specifying which one, or when you need to discover available documents."
            ),
            args_model=ListDocumentsArgs,
            handler=handle_list_documents,
            risk_level="read_only",
            requires_approval=False,
            status="available",
            ui_label_key="tools.listDocuments",
            timeout_seconds=10,
        )
    )

    reg.register(
        ToolDefinition(
            name="read_document",
            description=(
                "Reads full extracted text from specified pages of an uploaded government document. "
                "Use when you need the complete text of an exact page or small page range (1-3 pages). "
                "Requires a valid document_id from the citizen context or from list_documents."
            ),
            args_model=ReadDocumentArgs,
            handler=handle_read_document,
            risk_level="read_only",
            requires_approval=False,
            status="available",
            ui_label_key="tools.readDocument",
            timeout_seconds=15,
        )
    )

    reg.register(
        ToolDefinition(
            name="retrieve_evidence",
            description=(
                "Searches an uploaded government policy PDF using hybrid vector cosine and Tamil-aware lexical retrieval. "
                "Returns ranked passages labeled [E1], [E2], etc. along with the overall evidence level ('strong', 'weak', 'none'). "
                "ALWAYS call this tool first when answering factual questions about a policy's eligibility, benefits, fees, or rules."
            ),
            args_model=RetrieveEvidenceArgs,
            handler=handle_retrieve_evidence,
            risk_level="read_only",
            requires_approval=False,
            status="available",
            ui_label_key="tools.retrieveEvidence",
            timeout_seconds=20,
        )
    )

    reg.register(
        ToolDefinition(
            name="compare_documents",
            description=(
                "Performs side-by-side structural policy comparison between baseline and revised policy notifications. "
                "Detects added, removed, and modified clauses, exact fact changes (amounts, dates, percentages), and plain-language impact. "
                "Use when the citizen asks what changed between two versions or asks to compare two uploaded documents. "
                "Do NOT use for single-document inquiries."
            ),
            args_model=CompareDocumentsArgs,
            handler=handle_compare_documents,
            risk_level="read_only",
            requires_approval=False,
            status="available",
            ui_label_key="tools.compareDocuments",
            timeout_seconds=45,
        )
    )

    reg.register(
        ToolDefinition(
            name="search_official_sources",
            description=(
                "Searches official state gazettes, government orders, circulars, and statutory archives for verified legal provisions. "
                "Returns ranked passages labeled [S1], [S2] along with the issuing department, effective date, and evidence level. "
                "Use when the citizen asks what official records say about a scheme, rule, circular, or government policy."
            ),
            args_model=SearchOfficialSourcesArgs,
            handler=handle_search_official_sources,
            risk_level="read_only",
            requires_approval=False,
            status="available",
            ui_label_key="tools.searchOfficialSources",
            timeout_seconds=25,
        )
    )

    reg.register(
        ToolDefinition(
            name="check_claim",
            description=(
                "Verifies public claims, news reports, or citizen assertions against official government records. "
                "Performs multi-source retrieval, structured analysis, and enforces strict backend truth verdicts "
                "(Supported, Contradicted, Unverified, or Outdated) with verified quotes and page citations [S1], [S2]. "
                "Use when the citizen asks 'Is this true?', 'Fact check this', or asks to verify a specific civic claim. "
                "Limit 1 claim verification per turn."
            ),
            args_model=CheckClaimArgs,
            handler=handle_check_claim,
            risk_level="read_only",
            requires_approval=False,
            status="available",
            ui_label_key="tools.checkClaim",
            timeout_seconds=35,
        )
    )

    reg.register(
        ToolDefinition(
            name="generate_checklist",
            description=(
                "Generates an interactive eligibility checklist, required documents, and procedural steps for a public service. "
                "Retrieves official government circulars, verifies quotation evidence, checks authoritative fees and timelines, "
                "and links vetted official government portals. "
                "Use when the citizen asks how to apply for a service, what documents are needed, or requests an application checklist."
            ),
            args_model=GenerateChecklistArgs,
            handler=handle_generate_checklist,
            risk_level="read_only",
            requires_approval=False,
            status="available",
            ui_label_key="tools.generateChecklist",
            timeout_seconds=35,
        )
    )

    # 2. Planned Tools (Phases 13 to 14 - NEVER given to Gemini model)

    reg.register(
        ToolDefinition(
            name="draft_complaint",
            description=(
                "Drafts a formal, respectful, and factual civic grievance complaint based on citizen problem description. "
                "Performs deterministic classification and safety risk assessment, checks for hazards, and links vetted official reporting channels. "
                "Use when the citizen describes a civic problem (e.g. damaged road, water supply outage, streetlight not working, garbage, drainage overflow) "
                "and wants help preparing a complaint. Do NOT use for document questions, policy comparisons, fact-checks, or service guides. "
                "Limit 1 complaint draft per turn."
            ),
            args_model=DraftComplaintArgs,
            handler=handle_draft_complaint,
            risk_level="read_only",
            requires_approval=False,
            status="available",
            ui_label_key="tools.draftComplaint",
            timeout_seconds=30,
        )
    )

    reg.register(
        ToolDefinition(
            name="register_demo_complaint",
            description=(
                "Registers a simulated DEMO complaint record inside CivicLens bound to citizen approval and review hash. "
                "Nothing is submitted to any government authority. Requires explicit human approval. "
                "Use ONLY when the citizen explicitly asks to save, register, or track the demo complaint."
            ),
            args_model=RegisterDemoComplaintArgs,
            handler=handle_register_demo_complaint,
            risk_level="sensitive",
            requires_approval=True,
            status="available",
            ui_label_key="tools.registerDemoComplaint",
            timeout_seconds=20,
        )
    )

    # 2. Browser Automation Tools (Phase 14 - Available with Human-in-the-Loop Approval)

    reg.register(
        ToolDefinition(
            name="open_service_portal",
            description=(
                "Launches an interactive controlled browser session navigating to the local demo public service portal. "
                "Runs strictly on localhost for citizen education and workflow simulation. Requires human approval. "
                "Use when the citizen asks to practice applying for a certificate, asks for a live walkthrough, or asks to open the demo portal."
            ),
            args_model=OpenServicePortalArgs,
            handler=handle_open_service_portal,
            risk_level="sensitive",
            requires_approval=True,
            status="available",
            ui_label_key="tools.openServicePortal",
            timeout_seconds=25,
        )
    )

    reg.register(
        ToolDefinition(
            name="fill_demo_form",
            description=(
                "Fills form fields in the active demo portal session with fictional data for educational simulation. "
                "Scans for PII and requires citizen approval of exact fictional values before typing. "
                "Use when the citizen asks to fill sample details into the demo application form."
            ),
            args_model=FillDemoFormArgs,
            handler=handle_fill_demo_form,
            risk_level="sensitive",
            requires_approval=True,
            status="available",
            ui_label_key="tools.fillDemoForm",
            timeout_seconds=20,
        )
    )

    reg.register(
        ToolDefinition(
            name="submit_demo_application",
            description=(
                "Finalizes and records the simulated demo application submission bound to canonical review hash. "
                "Never connects to any government server. Requires citizen approval. "
                "Use when the citizen has reviewed Step 5 and explicitly asks to submit the demo application."
            ),
            args_model=SubmitDemoApplicationArgs,
            handler=handle_submit_demo_application,
            risk_level="irreversible",
            requires_approval=True,
            status="available",
            ui_label_key="tools.submitDemoApplication",
            timeout_seconds=20,
        )
    )

    _registry_instance = reg

  return _registry_instance


def set_tool_registry(registry: Optional[ToolRegistry]) -> None:
  """Test helper to inject or reset the ToolRegistry instance."""
  global _registry_instance
  _registry_instance = registry
