"""Public Service Assistant & Checklist Service (Module 4).

Generates evidence-backed procedural guidance, interactive categorized checklists,
authoritative key facts (fees/timelines), and deterministic official portal matches
for citizen service applications in English, Tamil, and code-mixed queries.

Strictly enforces:
1. PII Guard: Zero personal data collected or stored.
2. Quoting Rule: Items marked source_confirmed only if verified against passage quotes.
3. Zero Model URLs/Contacts: Model is forbidden from writing links; all links come from registry.
4. Zero-Call Guardrail: If evidence_level is none and allow_general is False, 0 Gemini calls.
5. Storage & Rate Limiting: Atomic file storage and rolling rate limiter.
"""

import datetime
import logging
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.core.config import Settings, get_settings
from app.core.errors import (
    DocumentRateLimitError,
    ServiceGuideError,
    ServiceGuideNotFoundError,
)
from app.core.pii_guard import ensure_no_pii
from app.core.prompts import (
    get_service_general_prompt,
    get_service_guide_prompt,
    wrap_untrusted_content,
)
from app.models.portal import PortalMatchResult
from app.models.service_guide import (
    ApplicantType,
    ChecklistCategory,
    ChecklistItem,
    ConfirmationStatus,
    KeyFactItem,
    ServiceGuideDraft,
    ServiceGuideReport,
    ServiceGuideRequest,
    ServiceSourceCitation,
)
from app.services.document_store import (
    DocumentStore,
    atomic_write_json,
    read_json_safe,
)
from app.services.gemini_service import GeminiService, get_gemini_service
from app.services.language_service import (
    detect_language,
    resolve_reply_language,
)
from app.services.portal_registry import (
    PortalRegistryService,
    get_portal_registry_service,
)
from app.services.rag_service import RAGService, get_rag_service
from app.services.source_library import (
    SourceLibraryService,
    get_source_library_service,
)
from app.db.stores import SqliteServiceGuideStore

logger = logging.getLogger("civiclens.services")

# Alias ServiceGuideStore to SqliteServiceGuideStore for transparent Phase 15 SQLite persistence
ServiceGuideStore = SqliteServiceGuideStore


URL_REGEX = re.compile(r"https?://[^\s)\]]+", re.IGNORECASE)
CONTACT_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b|"
    r"(?<!\d)(?:(?:\+91|0)[\s-]?)?[6-9]\d{9}(?!\d)"
)


def _sanitize_text(text: Any) -> Optional[str]:
  """Strip any model-generated URLs or phone/email contacts."""
  if text is None:
    return None
  if not isinstance(text, str):
    text = str(text)
  if not text:
    return ""
  t = URL_REGEX.sub("[link removed]", text)
  t = CONTACT_REGEX.sub("[contact removed]", t)
  return t


class ServiceGuideStore:
  """Filesystem storage manager for backend/data/service_guides/{guide_id}.json."""

  def __init__(self, settings: Optional[Settings] = None):
    self._settings = settings or get_settings()
    self._base_dir: Path = self._settings.service_guides_dir
    self._base_dir.mkdir(parents=True, exist_ok=True)
    self._lock = threading.Lock()

  def _guide_path(self, guide_id: str) -> Path:
    return self._base_dir / f"{guide_id}.json"

  def save_guide(self, guide: ServiceGuideReport) -> None:
    with self._lock:
      p = self._guide_path(guide.id)
      atomic_write_json(p, guide.model_dump())
    try:
      from app.db.stores import SqliteServiceGuideStore
      SqliteServiceGuideStore(self._settings).save_guide(guide)
    except Exception as exc:
      logger.debug("SQLite sync for save_guide skipped: %s", exc)

  def get_guide(self, guide_id: str) -> Optional[ServiceGuideReport]:
    with self._lock:
      p = self._guide_path(guide_id)
      if not p.exists():
        return None
      data = read_json_safe(p)
      if not data:
        return None
      try:
        return ServiceGuideReport(**data)
      except Exception as exc:
        logger.warning("Corrupted service guide file %s: %s", guide_id, exc)
        return None

  def delete_guide(self, guide_id: str) -> bool:
    with self._lock:
      p = self._guide_path(guide_id)
      if p.exists():
        try:
          p.unlink()
          return True
        except OSError:
          return False
      return False

  def list_guides(self, limit: int = 20) -> List[ServiceGuideReport]:
    guides: List[ServiceGuideReport] = []
    with self._lock:
      for f in self._base_dir.glob("*.json"):
        data = read_json_safe(f)
        if data:
          try:
            guides.append(ServiceGuideReport(**data))
          except Exception:
            pass
    guides.sort(key=lambda x: x.created_at, reverse=True)
    return guides[:limit]


from app.db.stores import SqliteServiceGuideStore
ServiceGuideStore = SqliteServiceGuideStore


class PublicServiceService:
  """Public Service Assistant service managing guides, verification, and portal matches."""

  def __init__(
      self,
      settings: Optional[Settings] = None,
      store: Optional[ServiceGuideStore] = None,
      rag_service: Optional[RAGService] = None,
      source_service: Optional[SourceLibraryService] = None,
      doc_store: Optional[DocumentStore] = None,
      portal_service: Optional[PortalRegistryService] = None,
      gemini_service: Optional[GeminiService] = None,
  ):
    self._settings = settings or get_settings()
    self._store = store or ServiceGuideStore(self._settings)
    self._rag = rag_service
    self._sources = source_service
    self._doc_store = doc_store
    self._portals = portal_service
    self._gemini = gemini_service

    # In-memory rolling rate limiter: ip -> list of timestamps
    self._rate_limits: Dict[str, List[float]] = {}
    self._rate_lock = threading.Lock()

  @property
  def store(self) -> ServiceGuideStore:
    return self._store

  @property
  def rag(self) -> RAGService:
    if self._rag is None:
      self._rag = get_rag_service()
    return self._rag

  @property
  def sources(self) -> SourceLibraryService:
    if self._sources is None:
      self._sources = get_source_library_service()
    return self._sources

  @property
  def doc_store(self) -> DocumentStore:
    if self._doc_store is None:
      self._doc_store = DocumentStore()
    return self._doc_store

  @property
  def portals(self) -> PortalRegistryService:
    if self._portals is None:
      self._portals = get_portal_registry_service()
    return self._portals

  @property
  def gemini(self) -> GeminiService:
    if self._gemini is None:
      self._gemini = get_gemini_service()
    return self._gemini

  def _check_rate_limit(self, client_key: str = "default") -> None:
    now = time.time()
    window = 60.0
    limit = self._settings.SERVICE_RATE_LIMIT_PER_MINUTE

    with self._rate_lock:
      timestamps = self._rate_limits.setdefault(client_key, [])
      # Evict older than 60s
      self._rate_limits[client_key] = [t for t in timestamps if now - t < window]
      if len(self._rate_limits[client_key]) >= limit:
        raise DocumentRateLimitError(
            f"Service guide rate limit exceeded ({limit} requests/min). Please wait a moment."
        )
      self._rate_limits[client_key].append(now)

  async def generate_guide(
      self,
      req: ServiceGuideRequest,
      client_key: str = "default",
      owner_id: str = "local",
  ) -> ServiceGuideReport:
    """Generate or retrieve a public service guidance report and checklist."""
    self._check_rate_limit(client_key)

    # 1. PII Check
    ensure_no_pii(req.query, field_name="query")
    if req.applicant_situation:
      ensure_no_pii(req.applicant_situation, field_name="applicant_situation")

    # Language resolution
    target_lang = req.language
    if target_lang == "auto" or not target_lang:
      detected = detect_language(req.query)
      target_lang = "ta" if detected == "ta" else "en"

    guide_id = f"gde_{uuid.uuid4().hex[:10]}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 2. Evidence Gathering
    searchable_sources: List[Dict[str, Any]] = []

    # Gather official sources
    if req.source_scope in ("all", "official_only"):
      official_list = self.sources.list_sources()
      for s in official_list:
        s_status = s.get("indexing_status") if isinstance(s, dict) else getattr(s, "indexing_status", None)
        if s_status == "ready":
          s_id = s.get("source_id") if isinstance(s, dict) else getattr(s, "source_id", "")
          s_title = s.get("title") if isinstance(s, dict) else getattr(s, "title", "Official Source")
          searchable_sources.append({
              "source_id": s_id,
              "title": s_title,
              "collection": "official",
              "store": self.sources.store,
          })

    # Gather citizen documents
    if req.source_scope in ("all", "user_documents_only"):
      user_docs = self.doc_store.list_documents()
      for d in user_docs:
        d_status = d.get("status") if isinstance(d, dict) else getattr(d, "status", None)
        if d_status == "ready":
          d_id = (
              d.get("document_id") or d.get("id")
              if isinstance(d, dict)
              else getattr(d, "document_id", getattr(d, "id", ""))
          )
          if not d_id or (req.document_ids and d_id not in req.document_ids):
            continue
          d_title = (
              d.get("display_filename") or d.get("filename", "Document")
              if isinstance(d, dict)
              else getattr(d, "display_filename", getattr(d, "filename", "Document"))
          )
          searchable_sources.append({
              "source_id": d_id,
              "title": d_title,
              "collection": "user",
              "store": self.doc_store,
          })

    # 3. Retrieve passages across sources
    passages: List[Dict[str, Any]] = []
    evidence_level = "none"

    if searchable_sources:
      passages, evidence_level, _ = await self.rag.retrieve_across(
          sources=searchable_sources,
          query=req.query,
          top_k_per_source=3,
          top_k_total=self._settings.SERVICE_TOP_K_TOTAL,
      )

    # ZERO-CALL GUARDRAIL: If no evidence found and allow_general is False
    if evidence_level == "none" or not passages:
      if not req.allow_general:
        return self._build_no_sources_report(
            guide_id=guide_id,
            req=req,
            target_lang=target_lang,
            now_iso=now_iso,
        )

    # Mode determination
    mode = "general_guidance" if (evidence_level == "none" or not passages) else "source_grounded"

    # Assign citation labels to passages: S1..Sn for official, D1..Dn for citizen
    labeled_passages: List[Dict[str, Any]] = []
    passage_lookup: Dict[str, Dict[str, Any]] = {}
    cited_source_ids: List[str] = []
    s_idx = 1
    d_idx = 1

    for p in passages:
      p_dict = dict(p)
      coll = p_dict.get("collection", "official")
      if coll == "official":
        lbl = f"[S{s_idx}]"
        s_idx += 1
      else:
        lbl = f"[D{d_idx}]"
        d_idx += 1

      p_dict["label"] = lbl
      labeled_passages.append(p_dict)
      passage_lookup[lbl] = p_dict
      # Also allow lookup without brackets: S1, D1
      passage_lookup[lbl.strip("[]")] = p_dict

      sid = p_dict.get("source_id") or p_dict.get("document_id")
      if sid and sid not in cited_source_ids:
        cited_source_ids.append(sid)

    # 4. Gemini structured call
    if mode == "source_grounded":
      # Build passage reference text
      evidence_blocks = []
      for p in labeled_passages:
        evidence_blocks.append(
            f"Passage {p['label']} (Page {p.get('page_number', 1)}) from \"{p.get('title', 'Document')}\":\n"
            f"{p.get('text', '')}"
        )
      evidence_context = "\n\n".join(evidence_blocks)

      user_prompt = (
          f"Citizen Query: {req.query}\n"
          f"Applicant Demographic: {req.applicant_type}\n"
          f"Situational Context: {req.applicant_situation or 'None provided'}\n\n"
          f"Official Government Passages (Untrusted Reference Data):\n"
          f"{wrap_untrusted_content(evidence_context, label='untrusted_policy_evidence')}\n\n"
          f"Generate procedural guidance, interactive checklist items, and key facts. "
          f"Cite the exact label (e.g. [S1]) and an exact quote snippet for every confirmed item. "
          f"Do not output URLs or contact numbers."
      )
      system_prompt = get_service_guide_prompt(target_lang)
    else:
      # General guidance mode
      user_prompt = (
          f"Citizen Query: {req.query}\n"
          f"Applicant Demographic: {req.applicant_type}\n"
          f"Situational Context: {req.applicant_situation or 'None provided'}\n\n"
          f"Provide standard procedural steps, required documents, and general guidance. "
          f"Do not cite sources or quotes. Do not output URLs or contact numbers."
      )
      system_prompt = get_service_general_prompt(target_lang)

    res = await self.gemini.generate_structured(
        prompt=user_prompt,
        schema=ServiceGuideDraft,
        system_prompt=system_prompt,
        temperature=0.1,
    )
    draft = res[0] if isinstance(res, tuple) else res

    # 5. Deterministic Verification & Sanitization
    return self._verify_and_assemble_report(
        guide_id=guide_id,
        req=req,
        target_lang=target_lang,
        mode=mode,
        draft=draft,
        labeled_passages=labeled_passages,
        passage_lookup=passage_lookup,
        cited_source_ids=cited_source_ids,
        now_iso=now_iso,
        owner_id=owner_id,
    )

  def _build_no_sources_report(
      self,
      guide_id: str,
      req: ServiceGuideRequest,
      target_lang: str,
      now_iso: str,
  ) -> ServiceGuideReport:
    """Build report when 0 official sources match (Zero Gemini calls)."""
    # Deterministic portal match by keyword tokens
    matched_portals = self.portals.match_portals(
        query=req.query,
        linked_source_ids=[],
        limit=3,
        allow_demo=False,
    )

    if target_lang == "ta":
      overview = (
          "இந்த சேவைக்கான அதிகாரப்பூர்வ அரசாணை அல்லது கொள்கை ஆவணங்கள் நூலகத்தில் கிடைக்கவில்லை. "
          "சிவிக்லென்ஸ் குடிமக்களுக்கு சரிபார்க்கப்பட்ட நடைமுறைகளை வழங்க அதிகாரப்பூர்வ ஆவணங்களை மட்டுமே நம்பியுள்ளது. "
          "கீழே உள்ள அதிகாரப்பூர்வ அரசு வலைவாசல்களை நீங்கள் பார்வையிடலாம் அல்லது பொதுவான வழிகாட்டுதலைக் கோரலாம்."
      )
      disclaimers = [
          "சிவிக்லென்ஸ் என்பது ஒரு சுதந்திரமான குடிமை நுண்ணறிவு வழிகாட்டியாகும். இது அரசுத் துறை அல்ல.",
          "ஆதாரங்கள் இல்லாத நிலையில் மாதிரி வழிகாட்டுதல் மட்டுமே வழங்கப்பட முடியும்.",
      ]
    else:
      overview = (
          "No verified official policy documents or government gazettes were found for this service query in the library. "
          "CivicLens relies strictly on authenticated official records to provide verified steps. "
          "You can review available official portals below, or request general procedural guidance."
      )
      disclaimers = [
          "CivicLens is an independent civic intelligence assistant and is not an official government agency.",
          "No verified official sources were found matching this specific query in the current library.",
      ]

    report = ServiceGuideReport(
        id=guide_id,
        query=req.query,
        applicant_type=req.applicant_type,
        applicant_situation=req.applicant_situation,
        language=target_lang,
        mode="no_sources",
        status="ready",
        procedure_overview=overview,
        procedure_overview_ta=overview if target_lang == "ta" else None,
        checklist_items=[],
        key_facts=[],
        cited_sources=[],
        matched_portals=matched_portals,
        disclaimers=disclaimers,
        offer_general_guidance=True,
        created_at=now_iso,
        completed_at=now_iso,
    )
    self._store.save_guide(report)
    from app.services.activity_service import get_activity_service
    get_activity_service().record_activity("service.guide_created", "service_guide", guide_id)
    return report

  def _verify_and_assemble_report(
      self,
      guide_id: str,
      req: ServiceGuideRequest,
      target_lang: str,
      mode: str,
      draft: ServiceGuideDraft,
      labeled_passages: List[Dict[str, Any]],
      passage_lookup: Dict[str, Dict[str, Any]],
      cited_source_ids: List[str],
      now_iso: str,
      owner_id: str = "local",
  ) -> ServiceGuideReport:
    """Verify quote fidelity, verify facts, strip URLs/contacts, and save report."""
    verified_checklist: List[ChecklistItem] = []
    verified_key_facts: List[KeyFactItem] = []
    verified_citations: List[ServiceSourceCitation] = []
    used_sources_set = set()

    max_items = self._settings.SERVICE_MAX_CHECKLIST_ITEMS

    for idx, item in enumerate(draft.checklist_items[:max_items], start=1):
      status: ConfirmationStatus = "needs_check"
      src_label = None
      src_id = None
      src_title = None
      src_page = None
      src_quote = None

      if mode == "general_guidance":
        status = "general_unverified"
      else:
        # Check source citation and verbatim quote
        cand_label = (item.source_label or "").strip()
        cand_quote = (item.source_quote or "").strip()

        matched_p = passage_lookup.get(cand_label) or passage_lookup.get(f"[{cand_label}]")
        if matched_p and cand_quote:
          p_text_lower = (matched_p.get("text") or "").lower()
          # Exact quote check in passage
          if cand_quote.lower() in p_text_lower:
            status = "source_confirmed"
            src_label = matched_p.get("label")
            src_id = matched_p.get("source_id") or matched_p.get("document_id")
            src_title = matched_p.get("title")
            src_page = matched_p.get("page_number", 1)
            src_quote = cand_quote
            used_sources_set.add(src_id)

      # Applicant type tag parsing
      app_tag: Optional[ApplicantType] = None
      if item.applicant_type_tag and item.applicant_type_tag in (
          "student", "farmer", "worker", "senior_citizen", "woman", "business_owner", "other"
      ):
        app_tag = item.applicant_type_tag  # type: ignore

      verified_checklist.append(
          ChecklistItem(
              id=f"chk_{idx}",
              category=item.category,
              text=_sanitize_text(item.text) or "",
              text_ta=_sanitize_text(item.text_ta),
              status=status,
              source_label=src_label,
              source_id=src_id,
              source_title=src_title,
              source_page=src_page,
              source_quote=src_quote,
              applicant_type_tag=app_tag,
              caution=_sanitize_text(item.caution),
          )
      )

    # Key Facts verification (only in source_grounded mode)
    if mode == "source_grounded":
      for f_idx, fact in enumerate(draft.key_facts[:8], start=1):
        cand_label = (fact.source_label or "").strip()
        cand_quote = (fact.source_quote or "").strip()
        val_text = fact.value_text.strip()

        matched_p = passage_lookup.get(cand_label) or passage_lookup.get(f"[{cand_label}]")
        if matched_p and cand_quote and val_text:
          p_text_lower = (matched_p.get("text") or "").lower()
          if cand_quote.lower() in p_text_lower and (val_text.lower() in cand_quote.lower() or val_text.lower() in p_text_lower):
            verified_key_facts.append(
                KeyFactItem(
                    id=f"fact_{f_idx}",
                    fact_type=fact.fact_type,
                    label=_sanitize_text(fact.label) or "Fact",
                    label_ta=_sanitize_text(fact.label_ta),
                    value_text=_sanitize_text(val_text) or "",
                    source_label=matched_p.get("label"),
                    source_quote=cand_quote,
                    page_number=matched_p.get("page_number", 1),
                    confidence=1.0,
                )
            )

    # Assemble verified citations
    for p in labeled_passages:
      sid = p.get("source_id") or p.get("document_id")
      if sid in used_sources_set or len(verified_citations) < 5:
        verified_citations.append(
            ServiceSourceCitation(
                label=p.get("label", "[S1]"),
                source_id=sid or "doc",
                title=p.get("title", "Official Source"),
                source_type="official_source" if p.get("collection") == "official" else "citizen_document",
                page_number=p.get("page_number", 1),
                snippet=(p.get("text", "")[:280] + "...") if len(p.get("text", "")) > 280 else p.get("text", ""),
                issuing_authority=p.get("issuing_authority"),
            )
        )

    # Match portals strictly from registry
    matched_portals = self.portals.match_portals(
        query=req.query,
        linked_source_ids=list(used_sources_set) or cited_source_ids,
        limit=3,
        allow_demo=False,
    )

    # Disclaimers
    disclaimers = [
        "CivicLens is an independent civic intelligence assistant and is not an official government agency.",
        "Formal applications, document uploads, and fee payments must be completed on official government portals.",
    ]
    if mode == "general_guidance":
      disclaimers.append(
          "General Guidance Notice: This checklist is generated from general civic administrative knowledge without verified official source gazettes. Always verify exact fees, deadlines, and required documents on the official government portal."
      )

    report = ServiceGuideReport(
        id=guide_id,
        query=req.query,
        applicant_type=req.applicant_type,
        applicant_situation=req.applicant_situation,
        language=target_lang,
        mode=mode,  # type: ignore
        status="ready",
        procedure_overview=_sanitize_text(draft.procedure_overview) or "",
        procedure_overview_ta=_sanitize_text(draft.procedure_overview_ta),
        checklist_items=verified_checklist,
        key_facts=verified_key_facts,
        cited_sources=verified_citations,
        matched_portals=matched_portals,
        disclaimers=disclaimers,
        offer_general_guidance=False,
        created_at=now_iso,
        completed_at=now_iso,
    )
    self._store.save_guide(report, owner_id=owner_id)
    from app.services.activity_service import get_activity_service
    get_activity_service().record_activity("service.guide_created", "service_guide", guide_id, owner_id=owner_id)
    return report

  def get_guide(self, guide_id: str, owner_id: Optional[str] = None) -> ServiceGuideReport:
    guide = self._store.get_guide(guide_id, owner_id=owner_id)
    if not guide:
      raise ServiceGuideNotFoundError(f"Service guide '{guide_id}' not found.")
    return guide

  def delete_guide(self, guide_id: str, owner_id: Optional[str] = None) -> bool:
    if not self._store.delete_guide(guide_id, owner_id=owner_id):
      raise ServiceGuideNotFoundError(f"Service guide '{guide_id}' not found.")
    return True

  def list_guides(self, limit: int = 20, owner_id: Optional[str] = None) -> List[ServiceGuideReport]:
    return self._store.list_guides(limit=limit, owner_id=owner_id)

  async def retry_analysis(self, guide_id: str) -> ServiceGuideReport:
    """Rerun guidance analysis for an existing query."""
    existing = self.get_guide(guide_id)
    req = ServiceGuideRequest(
        query=existing.query,
        applicant_type=existing.applicant_type,
        applicant_situation=existing.applicant_situation,
        language=existing.language if existing.language in ("en", "ta") else "auto",  # type: ignore
        allow_general=existing.mode == "general_guidance" or existing.offer_general_guidance,
    )
    new_report = await self.generate_guide(req)
    return new_report


_public_service_service: Optional[PublicServiceService] = None


def get_public_service_service() -> PublicServiceService:
  global _public_service_service
  if _public_service_service is None:
    _public_service_service = PublicServiceService()
  return _public_service_service


def set_public_service_service(service: Optional[PublicServiceService]) -> None:
  global _public_service_service
  _public_service_service = service
