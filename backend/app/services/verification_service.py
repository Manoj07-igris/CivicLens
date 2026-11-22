"""Civic Fact Verification Engine (Module 3).

Executes multi-source hybrid retrieval against curated official sources and user documents,
performs strictly budgeted Gemini structured analysis (at most 2 calls, hard cap 3),
and enforces 100% deterministic backend verdict rules (Supported, Contradicted, Unverified, Outdated).
"""

import asyncio
import datetime
import hashlib
import json
import logging
import re
import threading
import time
import unicodedata
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from app.core.config import Settings, get_settings
from app.core.errors import (
    DocumentNotFoundError,
    DocumentProcessingError,
    VerificationError,
    VerificationNotFoundError,
)
from app.core.pii_guard import ensure_no_pii
from app.core.prompts import (
    get_verify_claim_split_prompt,
    get_verify_judgement_prompt,
    wrap_untrusted_content,
)
from app.models.gemini import GeminiTokenUsage
from app.models.verification import (
    AtomicClaimItem,
    BatchJudgementResult,
    ClaimJudgementItem,
    ClaimResult,
    ClaimSplitResult,
    CoverageInfo,
    EvidenceItemReport,
    FactComparisonItem,
    PassageJudgement,
    SupersededByInfo,
    VerificationReport,
    VerifyRequest,
)
from app.services.document_store import DocumentStore, atomic_write_json, get_document_store, read_json_safe, validate_document_id
from app.services.fact_extractor import (
    extract_facts_from_text,
    facts_match,
    normalize_tamil_digits,
    parse_normalized_date,
)
from app.services.gemini_service import GeminiError, GeminiService, get_gemini_service
from app.services.language_service import detect_language, resolve_reply_language
from app.services.rag_service import RAGService, get_rag_service
from app.services.source_library import SourceLibraryService, get_source_library_service
from app.db.stores import SqliteVerificationStore

logger = logging.getLogger("civiclens.verification")

# Alias VerificationStore to SqliteVerificationStore for transparent Phase 15 SQLite persistence
VerificationStore = SqliteVerificationStore



class VerificationStore:
  """Atomic filesystem store for fact verification jobs, reports, and content-addressed cache."""

  def __init__(self, settings: Optional[Settings] = None):
    self._settings = settings or get_settings()
    self._base_dir: Path = self._settings.verifications_dir
    self._base_dir.mkdir(parents=True, exist_ok=True)
    self._cache_file = self._base_dir / "cache_index.json"
    self._lock = threading.Lock()

  def _read_cache_index(self) -> Dict[str, Any]:
    with self._lock:
      data = read_json_safe(self._cache_file)
      return data if isinstance(data, dict) else {}

  def _write_cache_index(self, data: Dict[str, Any]) -> None:
    with self._lock:
      atomic_write_json(self._cache_file, data)

  def save_job(self, verification_id: str, job_data: Dict[str, Any]) -> None:
    valid_id = validate_document_id(verification_id)
    v_dir = self._base_dir / valid_id
    v_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(v_dir / "job.json", job_data)

  def get_job(self, verification_id: str) -> Optional[Dict[str, Any]]:
    try:
      valid_id = validate_document_id(verification_id)
      return read_json_safe(self._base_dir / valid_id / "job.json")
    except ValueError:
      return None

  def save_report(self, verification_id: str, report: VerificationReport, cache_key: Optional[str] = None) -> None:
    valid_id = validate_document_id(verification_id)
    v_dir = self._base_dir / valid_id
    v_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(v_dir / "report.json", report.model_dump())

    if cache_key:
      cache = self._read_cache_index()
      cache[cache_key] = valid_id
      self._write_cache_index(cache)
    try:
      from app.db.stores import SqliteVerificationStore
      SqliteVerificationStore(self._settings).save_report(verification_id, report, cache_key)
    except Exception as exc:
      logger.debug("SQLite sync for verification report skipped: %s", exc)

  def get_report(self, verification_id: str) -> Optional[VerificationReport]:
    try:
      valid_id = validate_document_id(verification_id)
      data = read_json_safe(self._base_dir / valid_id / "report.json")
      if data and isinstance(data, dict):
        return VerificationReport.model_validate(data)
      return None
    except Exception as exc:
      logger.warning("Failed to parse verification report %s: %s", verification_id, exc)
      return None

  def lookup_cache(self, cache_key: str) -> Optional[VerificationReport]:
    cache = self._read_cache_index()
    v_id = cache.get(cache_key)
    if v_id:
      return self.get_report(v_id)
    return None

  def list_verifications(self) -> List[Dict[str, Any]]:
    """List all past verifications newest first."""
    results: List[Dict[str, Any]] = []
    if not self._base_dir.exists():
      return results

    for entry in self._base_dir.iterdir():
      if entry.is_dir():
        job = read_json_safe(entry / "job.json")
        if job and isinstance(job, dict):
          results.append({
              "verification_id": job.get("verification_id", entry.name),
              "claim_snippet": (job.get("claim", "")[:120] + "...") if len(job.get("claim", "")) > 120 else job.get("claim", ""),
              "overall_verdict": job.get("overall_verdict", "unverified"),
              "created_at": job.get("created_at", ""),
              "scope": job.get("scope", "official"),
              "language": job.get("language", "en"),
          })

    results.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
    return results

  def delete_verification(self, verification_id: str) -> bool:
    try:
      valid_id = validate_document_id(verification_id)
      v_dir = self._base_dir / valid_id
      if v_dir.exists():
        import shutil
        shutil.rmtree(v_dir, ignore_errors=True)

      cache = self._read_cache_index()
      keys_to_del = [k for k, v in cache.items() if v == valid_id]
      if keys_to_del:
        for k in keys_to_del:
          del cache[k]
        self._write_cache_index(cache)
      return True
    except Exception as exc:
      logger.warning("Failed to delete verification %s: %s", verification_id, exc)
      return False


# In-memory sliding-window rate limiter for verifications (5 calls / min)
class VerificationRateLimiter:
  def __init__(self, max_requests: int = 5, window_seconds: int = 60):
    self.max_requests = max_requests
    self.window_seconds = window_seconds
    self._clients: Dict[str, List[float]] = {}
    self._lock = threading.Lock()

  def check(self, client_key: str) -> None:
    now = time.time()
    with self._lock:
      timestamps = self._clients.setdefault(client_key, [])
      self._clients[client_key] = [t for t in timestamps if now - t < self.window_seconds]
      if len(self._clients[client_key]) >= self.max_requests:
        raise VerificationError(
            f"Verification rate limit reached ({self.max_requests} requests per minute). Please wait.",
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
        )
      self._clients[client_key].append(now)

  def reset(self) -> None:
    with self._lock:
      self._clients.clear()


_rate_limiter = VerificationRateLimiter()


def get_verification_rate_limiter() -> VerificationRateLimiter:
  return _rate_limiter


def reset_verify_rate_limit() -> None:
  _rate_limiter.reset()


def _normalize_evidence_status(raw_status: Optional[str]) -> Literal["current", "superseded", "unknown"]:
  if not raw_status:
    return "unknown"
  s = str(raw_status).lower()
  if s in ("current", "superseded"):
    return s  # type: ignore
  if s in ("ready", "ready_with_warnings"):
    return "current"
  return "unknown"


# Alias VerificationStore to SqliteVerificationStore for transparent Phase 15 SQLite persistence
VerificationStore = SqliteVerificationStore


class VerificationService:
  """Central orchestrator for the Fact Verification Engine."""

  def __init__(
      self,
      settings: Optional[Settings] = None,
      store: Optional[VerificationStore] = None,
      source_service: Optional[SourceLibraryService] = None,
      doc_store: Optional[DocumentStore] = None,
      rag_service: Optional[RAGService] = None,
      gemini_service: Optional[GeminiService] = None,
  ):
    self._settings = settings or get_settings()
    self._store = store or VerificationStore(self._settings)
    self._source_service = source_service or get_source_library_service()
    self._doc_store = doc_store or get_document_store()
    self._rag_service = rag_service or get_rag_service()
    self._gemini = gemini_service or get_gemini_service()

  @property
  def store(self) -> VerificationStore:
    return self._store

  def compute_cache_key(
      self,
      claim: str,
      language: str,
      scope: str,
      doc_ids: List[str],
      library_version: str,
  ) -> str:
    norm_claim = unicodedata.normalize("NFC", claim.strip().lower())
    norm_claim = re.sub(r"\s+", " ", norm_claim)
    sorted_docs = ",".join(sorted(doc_ids))
    sig = f"{norm_claim}|{language}|{scope}|{sorted_docs}|{library_version}|v1"
    return hashlib.sha256(sig.encode("utf-8")).hexdigest()

  def start_verification(
      self,
      req: VerifyRequest,
      client_key: str = "default",
      owner_id: str = "local",
  ) -> Tuple[str, bool]:
    """Validate preconditions and register verification job.

    Returns (verification_id, is_cache_hit).
    """
    _rate_limiter.check(client_key)

    clean_claim = req.claim.strip()
    if not clean_claim:
      raise VerificationError("Claim text cannot be empty.", code="EMPTY_CLAIM", status_code=422)
    ensure_no_pii(clean_claim, field_name="claim")
    if len(clean_claim) > self._settings.VERIFY_CLAIM_MAX_CHARS:
      raise VerificationError(
          f"Claim exceeds maximum allowed length of {self._settings.VERIFY_CLAIM_MAX_CHARS} characters.",
          code="CLAIM_TOO_LONG",
          status_code=422,
      )

    # Validate document IDs if provided
    if req.scope in ("documents", "official_and_documents"):
      if req.scope == "documents" and not req.document_ids:
        raise VerificationError(
            "document_ids are required when scope is 'documents'.",
            code="DOCUMENTS_REQUIRED",
            status_code=422,
        )
      for d_id in req.document_ids:
        meta = self._doc_store.get_metadata(d_id, owner_id=owner_id)
        if not meta:
          raise DocumentNotFoundError(f"User document '{d_id}' not found.")

    library_version = self._source_service.store.compute_library_version()
    cache_key = self.compute_cache_key(clean_claim, req.language, req.scope, req.document_ids, library_version)

    # Cache check
    if not req.force:
      cached_report = self._store.lookup_cache(cache_key)
      if cached_report:
        logger.info("Fact verification cache hit for claim hash %s", cache_key[:10])
        # Return existing ID
        return cached_report.verification_id, True

    verification_id = str(uuid.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    job_data = {
        "verification_id": verification_id,
        "owner_id": owner_id,
        "status": "queued",
        "stage": "understanding_claim",
        "progress_pct": 5,
        "claim": clean_claim,
        "language": req.language,
        "scope": req.scope,
        "document_ids": req.document_ids,
        "force": req.force,
        "created_at": now_iso,
        "updated_at": now_iso,
        "error_message": None,
        "overall_verdict": "unverified",
    }
    self._store.save_job(verification_id, job_data, owner_id=owner_id)
    return verification_id, False

  async def execute_verification(self, verification_id: str) -> VerificationReport:
    """Run complete 4-stage fact verification pipeline (invoked in background)."""
    job = self._store.get_job(verification_id)
    if not job:
      raise VerificationNotFoundError(f"Job {verification_id} not found.")

    start_time = time.perf_counter()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    claim_raw: str = job["claim"]
    req_lang: str = job["language"]
    scope: str = job["scope"]
    doc_ids: List[str] = job.get("document_ids", [])

    # Update status to running
    job["status"] = "running"
    job["stage"] = "understanding_claim"
    job["progress_pct"] = 15
    self._store.save_job(verification_id, job)

    gemini_calls_made = 0
    total_tokens = GeminiTokenUsage(prompt_tokens=0, candidates_tokens=0, total_tokens=0)
    warnings: List[str] = []

    # Clean claim text and detect language
    clean_claim = unicodedata.normalize("NFC", claim_raw.strip())
    # Strip non-printable control characters
    clean_claim = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", clean_claim).strip()
    detected_lang = detect_language(clean_claim)
    target_lang = resolve_reply_language(req_lang, detected_lang)

    # --- Stage 1: Atomic Claim Decomposition ---
    atomic_claims: List[AtomicClaimItem] = []

    # Short single-sentence heuristic (skip Call 1 to save quota)
    sentence_period_count = re.sub(r"\d+\.\d+", "", clean_claim).count(".")
    is_short = len(clean_claim) <= 300 and ("\n" not in clean_claim) and (sentence_period_count <= 1)

    if is_short or not self._gemini.is_configured:
      atomic_claims = [
          AtomicClaimItem(
              claim_id="c1",
              claim_text=clean_claim,
              claim_type="other",
              is_checkable_fact=True,
              temporal_scope="current" if any(w in clean_claim.lower() for w in ("now", "currently", "today", "தற்போது", "இப்போது")) else "unspecified",
              key_entities=[],
          )
      ]
    else:
      try:
        job["stage"] = "understanding_claim"
        job["progress_pct"] = 25
        self._store.save_job(verification_id, job)

        split_prompt = get_verify_claim_split_prompt(target_lang)
        wrapped_claim = wrap_untrusted_content(clean_claim, "untrusted_citizen_claim")
        user_msg = (
            f"Decompose the following citizen submission into at most {self._settings.VERIFY_MAX_CLAIMS} "
            f"atomic, independently checkable factual claims:\n\n{wrapped_claim}"
        )

        split_res, split_usage = await self._gemini.generate_structured(
            prompt=user_msg,
            response_schema=ClaimSplitResult,
            system_instruction=split_prompt,
            temperature=0.0,
        )
        gemini_calls_made += 1
        total_tokens.prompt_tokens = (total_tokens.prompt_tokens or 0) + (split_usage.prompt_tokens or 0)
        total_tokens.candidates_tokens = (total_tokens.candidates_tokens or 0) + (split_usage.candidates_tokens or 0)
        total_tokens.total_tokens = (total_tokens.total_tokens or 0) + (split_usage.total_tokens or 0)

        if split_res and split_res.claims:
          atomic_claims = split_res.claims[: self._settings.VERIFY_MAX_CLAIMS]
      except Exception as exc:
        logger.warning("Claim decomposition failed, falling back to monolithic claim: %s", exc)
        warnings.append("AI claim decomposition failed; evaluated submission as a single claim.")

    if not atomic_claims:
      atomic_claims = [
          AtomicClaimItem(
              claim_id="c1",
              claim_text=clean_claim,
              claim_type="other",
              is_checkable_fact=True,
              temporal_scope="unspecified",
              key_entities=[],
          )
      ]

    # Deterministic fact extraction per claim
    claim_facts_map: Dict[str, Dict[str, List[str]]] = {}
    for c in atomic_claims:
      claim_facts_map[c.claim_id] = extract_facts_from_text(c.claim_text)

    # --- Stage 2: Scope Gathering & Multi-Source Retrieval ---
    job["stage"] = "searching_sources"
    job["progress_pct"] = 45
    self._store.save_job(verification_id, job)

    searchable_sources: List[Dict[str, Any]] = []
    official_titles: List[str] = []
    user_doc_titles: List[str] = []

    if scope in ("official", "official_and_documents"):
      all_official = self._source_service.list_sources()
      for src in all_official:
        searchable_sources.append({
            "source_id": src.source_id,
            "title": src.title,
            "issuing_authority": src.issuing_authority,
            "effective_date": src.effective_date,
            "status": src.status,
            "series_id": src.series_id,
            "source_url": src.source_url,
            "collection": "official",
            "store": self._source_service.doc_store,
        })
        official_titles.append(src.title)

    if scope in ("documents", "official_and_documents"):
      for d_id in doc_ids:
        meta = self._doc_store.get_metadata(d_id)
        if meta:
          fname = meta.get("filename", "User Document")
          searchable_sources.append({
              "source_id": d_id,
              "title": fname,
              "issuing_authority": None,
              "effective_date": None,
              "status": meta.get("status", "ready"),
              "series_id": None,
              "source_url": None,
              "collection": "user",
              "store": self._doc_store,
          })
          user_doc_titles.append(fname)

    # Cap sources searched to VERIFY_MAX_SOURCES_SEARCHED
    max_src = self._settings.VERIFY_MAX_SOURCES_SEARCHED
    sources_to_search = searchable_sources[:max_src]
    skipped_due_to_limit: List[Dict[str, str]] = []
    if len(searchable_sources) > max_src:
      warnings.append(
          f"Library contains {len(searchable_sources)} sources; search was limited to the top {max_src} sources."
      )
      for s in searchable_sources[max_src:]:
        skipped_due_to_limit.append({
            "source_id": s["source_id"],
            "title": s["title"],
            "reason": "Exceeded maximum search capacity",
        })

    # Empty Library Condition for scope 'official'
    library_version = self._source_service.store.compute_library_version()
    if scope == "official" and not sources_to_search:
      logger.info("Official source library is empty for verification %s", verification_id)
      empty_claims: List[ClaimResult] = []
      for c in atomic_claims:
        empty_claims.append(
            ClaimResult(
                claim_id=c.claim_id,
                claim_text=c.claim_text,
                claim_type=c.claim_type,
                is_checkable_fact=c.is_checkable_fact,
                claim_facts=claim_facts_map.get(c.claim_id, {}),
                verdict="unverified",
                verdict_basis="no_evidence",
                explanation=(
                    "No official sources have been added to the library yet. "
                    "Verification requires official government circulars, notifications, or gazettes to be indexed. "
                    "Unverified does not mean this claim is false."
                    if target_lang == "en"
                    else "அதிகாரப்பூர்வ ஆதார நூலகத்தில் இன்னும் ஆவணங்கள் சேர்க்கப்படவில்லை. "
                    "சரிபார்ப்பிற்கு அரசாணைகள் அல்லது அறிவிப்புகள் தேவை. "
                    "சரிபார்க்கப்படவில்லை என்பது இக்கூற்று தவறானது என்று பொருள்படாது."
                ),
                matched_aspects=[],
                unmatched_aspects=[c.claim_text],
                supporting_evidence=[],
                contradicting_evidence=[],
                related_evidence=[],
                evidence_level="none",
            )
        )

      cov = CoverageInfo(
          official_sources_searched_count=0,
          official_source_titles=[],
          user_documents_included=False,
          user_document_titles=[],
          passages_examined_count=0,
          sources_skipped=[],
          library_version=library_version,
      )

      report = VerificationReport(
          verification_id=verification_id,
          created_at=now_iso,
          language=target_lang,
          scope=scope,  # type: ignore
          original_claim_text=clean_claim,
          overall_verdict="unverified",
          overall_summary=(
              "Unable to verify claim: the official source library is currently empty. "
              "Add official government documents to the library to enable fact checking."
              if target_lang == "en"
              else "கூற்றைச் சரிபார்க்க முடியவில்லை: அதிகாரப்பூர்வ ஆதார நூலகம் தற்போது காலியாக உள்ளது."
          ),
          claims=empty_claims,
          coverage=cov,
          analysis_status="completed",
          warnings=warnings,
          cache_hit=False,
          model=self._settings.effective_gemini_model,
          token_usage=total_tokens,
      )

      self._store.save_report(verification_id, report)
      job["status"] = "completed"
      job["stage"] = "completed"
      job["progress_pct"] = 100
      job["overall_verdict"] = "unverified"
      self._store.save_job(verification_id, job)
      return report

    # Multi-source retrieval per claim
    claim_retrieval_map: Dict[str, Tuple[List[Dict[str, Any]], str]] = {}
    all_skipped_sources = list(skipped_due_to_limit)
    total_passages_examined = 0

    # Global passage label counter for S-labels across all claims
    s_label_counter = 0
    claim_labelled_passages: Dict[str, List[Dict[str, Any]]] = {}

    for c in atomic_claims:
      q_terms = [c.claim_text]
      if c.key_entities:
        q_terms.extend(c.key_entities)
      query = " ".join(q_terms)

      passages, ev_level, skipped = await self._rag_service.retrieve_across(
          sources=sources_to_search,
          query=query,
          top_k_per_source=self._settings.VERIFY_TOP_K_PER_SOURCE,
          top_k_total=self._settings.VERIFY_TOP_K_TOTAL,
      )
      all_skipped_sources.extend(skipped)
      total_passages_examined += len(passages)
      claim_retrieval_map[c.claim_id] = (passages, ev_level)

      # Assign unique S1, S2 labels per passage for this claim
      labelled_p: List[Dict[str, Any]] = []
      for p in passages:
        s_label_counter += 1
        p_copy = dict(p)
        p_copy["label"] = f"S{s_label_counter}"
        labelled_p.append(p_copy)
      claim_labelled_passages[c.claim_id] = labelled_p

    # Determine which claims require Gemini evaluation
    claims_needing_judgement: List[AtomicClaimItem] = []
    for c in atomic_claims:
      passages, ev_level = claim_retrieval_map[c.claim_id]
      # ZERO-CALL GUARDRAIL: If evidence_level is none or claim is not checkable, skip Gemini
      if ev_level != "none" and c.is_checkable_fact:
        claims_needing_judgement.append(c)

    # --- Stage 3: Evidence Judgement with Gemini (Call 2) ---
    job["stage"] = "analysing_evidence"
    job["progress_pct"] = 70
    self._store.save_job(verification_id, job)

    judgements_by_claim: Dict[str, ClaimJudgementItem] = {}
    ai_available = self._gemini.is_configured

    if claims_needing_judgement and ai_available and gemini_calls_made < self._settings.VERIFY_MAX_GEMINI_CALLS:
      judgement_prompt = get_verify_judgement_prompt(target_lang)

      # Construct batched evidence prompt
      prompt_blocks: List[str] = [
          f"Evaluate the following {len(claims_needing_judgement)} claim(s) against their supplied evidence passages:"
      ]

      for c in claims_needing_judgement:
        p_list = claim_labelled_passages.get(c.claim_id, [])
        c_facts = claim_facts_map.get(c.claim_id, {})

        c_block = [f"=== CLAIM [{c.claim_id}] ==="]
        c_block.append(f"Text: {wrap_untrusted_content(c.claim_text, f'claim_{c.claim_id}')}")
        c_block.append(f"Type: {c.claim_type}")
        c_block.append(f"Temporal Scope: {c.temporal_scope}")
        if any(c_facts.values()):
          c_block.append(f"Extracted Claim Facts: {json.dumps(c_facts, ensure_ascii=False)}")

        c_block.append("Supplied Evidence Passages:")
        for p in p_list:
          p_wrapped = wrap_untrusted_content(p["text"], f"passage_{p['label']}")
          c_block.append(
              f"[{p['label']}] Source Title: '{p['source_title']}' | Authority: '{p.get('issuing_authority') or 'N/A'}' | "
              f"Effective Date: '{p.get('effective_date') or 'N/A'}' | Status: '{p.get('status')}' | Page: {p['page_number']}\n"
              f"{p_wrapped}"
          )

        prompt_blocks.append("\n".join(c_block))

      full_judgement_msg = "\n\n".join(prompt_blocks)

      try:
        batch_res, judge_usage = await self._gemini.generate_structured(
            prompt=full_judgement_msg,
            response_schema=BatchJudgementResult,
            system_instruction=judgement_prompt,
            temperature=0.0,
        )
        gemini_calls_made += 1
        total_tokens.prompt_tokens = (total_tokens.prompt_tokens or 0) + (judge_usage.prompt_tokens or 0)
        total_tokens.candidates_tokens = (total_tokens.candidates_tokens or 0) + (judge_usage.candidates_tokens or 0)
        total_tokens.total_tokens = (total_tokens.total_tokens or 0) + (judge_usage.total_tokens or 0)

        if batch_res and batch_res.judgements:
          for j in batch_res.judgements:
            judgements_by_claim[j.claim_id] = j
      except Exception as exc:
        logger.warning("Evidence judgement call failed: %s", exc)
        ai_available = False
        warnings.append("AI evidence analysis was temporarily unavailable; passages shown as unanalysed.")

    # --- Stage 4: Deterministic Backend Verdict Rules ---
    job["stage"] = "applying_verdict_rules"
    job["progress_pct"] = 85
    self._store.save_job(verification_id, job)

    today = datetime.date.today()
    all_sources_map = {s["source_id"]: s for s in searchable_sources}

    final_claim_results: List[ClaimResult] = []

    for c in atomic_claims:
      p_list = claim_labelled_passages.get(c.claim_id, [])
      _, ev_level = claim_retrieval_map.get(c.claim_id, ([], "none"))
      claim_facts = claim_facts_map.get(c.claim_id, {})
      ai_judgement = judgements_by_claim.get(c.claim_id)

      # 0. Not Checkable statement check
      if not c.is_checkable_fact:
        final_claim_results.append(
            ClaimResult(
                claim_id=c.claim_id,
                claim_text=c.claim_text,
                claim_type=c.claim_type,
                is_checkable_fact=False,
                claim_facts=claim_facts,
                verdict="unverified",
                verdict_basis="not_checkable",
                explanation=(
                    "This statement expresses a subjective opinion, personal prediction, or rumor that cannot be verified against official statutory records."
                    if target_lang == "en"
                    else "இக்கூற்று அகநிலை கருத்து அல்லது எதிர்கால கணிப்பை வெளிப்படுத்துகிறது; அதிகாரப்பூர்வ ஆவணங்கள் மூலம் சரிபார்க்க முடியாது."
                ),
                matched_aspects=[],
                unmatched_aspects=[c.claim_text],
                supporting_evidence=[],
                contradicting_evidence=[],
                related_evidence=[],
                evidence_level="none",
            )
        )
        continue

      # 1. No evidence available check
      if ev_level == "none" or not p_list:
        final_claim_results.append(
            ClaimResult(
                claim_id=c.claim_id,
                claim_text=c.claim_text,
                claim_type=c.claim_type,
                is_checkable_fact=True,
                claim_facts=claim_facts,
                verdict="unverified",
                verdict_basis="no_evidence",
                explanation=(
                    "No matching evidence found in the official records searched. Not finding evidence does not mean the claim is false."
                    if target_lang == "en"
                    else "தேடப்பட்ட அதிகாரப்பூர்வ ஆவணங்களில் தொடர்புடைய சான்றுகள் எதுவும் கிடைக்கவில்லை. சான்று கிடைக்காததால் இக்கூற்று தவறானது என்று பொருள்படாது."
                ),
                matched_aspects=[],
                unmatched_aspects=[c.claim_text],
                supporting_evidence=[],
                contradicting_evidence=[],
                related_evidence=[],
                evidence_level="none",
            )
        )
        continue

      # 2. AI Unavailable / Unanalysed fallback
      if not ai_available or not ai_judgement:
        # Build unanalysed evidence reports
        unanalysed_evidence: List[EvidenceItemReport] = []
        for p in p_list:
          unanalysed_evidence.append(
              EvidenceItemReport(
                  label=p["label"],
                  collection=p["collection"],
                  source_id=p["source_id"],
                  source_title=p["source_title"],
                  issuing_authority=p.get("issuing_authority"),
                  source_url=p.get("source_url"),
                  effective_date=p.get("effective_date"),
                  status=_normalize_evidence_status(p.get("status")),
                  stale=False,
                  page_number=p["page_number"],
                  quote=None,
                  excerpt=p["excerpt"],
                  fact_comparisons=[],
              )
          )

        final_claim_results.append(
            ClaimResult(
                claim_id=c.claim_id,
                claim_text=c.claim_text,
                claim_type=c.claim_type,
                is_checkable_fact=True,
                claim_facts=claim_facts,
                verdict="unverified",
                verdict_basis="ai_unavailable",
                explanation=(
                    "AI verification analysis was unavailable; no verdict could be reached. "
                    "You may review the retrieved evidence passages and retry."
                    if target_lang == "en"
                    else "AI சான்று பகுப்பாய்வு கிடைக்கவில்லை; தீர்ப்பு எட்டப்படவில்லை. சான்றுகளை மதிப்பாய்வு செய்து மீண்டும் முயற்சிக்கவும்."
                ),
                matched_aspects=[],
                unmatched_aspects=[c.claim_text],
                supporting_evidence=[],
                contradicting_evidence=[],
                related_evidence=unanalysed_evidence,
                evidence_level=ev_level,  # type: ignore
            )
        )
        continue

      # 3. Backend Verification of Gemini Judgements
      # Map passage stances and verify quotes verbatim against chunk text
      p_by_label = {p["label"]: p for p in p_list}

      verified_supporting: List[EvidenceItemReport] = []
      verified_contradicting: List[EvidenceItemReport] = []
      verified_related: List[EvidenceItemReport] = []

      for pj in ai_judgement.passages:
        # Drop unknown labels
        p_raw = p_by_label.get(pj.passage_label)
        if not p_raw:
          continue

        chunk_text_clean = unicodedata.normalize("NFC", p_raw["text"])
        chunk_text_clean = re.sub(r"\s+", " ", chunk_text_clean)

        verified_quote: Optional[str] = None
        stance = pj.stance

        if pj.quote and pj.quote.strip():
          q_clean = unicodedata.normalize("NFC", pj.quote.strip())
          q_clean = re.sub(r"\s+", " ", q_clean)
          # Case-insensitive substring check
          if q_clean.lower() in chunk_text_clean.lower():
            verified_quote = pj.quote.strip()
          else:
            # Quote hallucination / fabrication: downgrade stance
            logger.info("Quote verification failed for passage %s: quote=%r text=%r", pj.passage_label, q_clean, chunk_text_clean)
            if stance in ("supports", "contradicts"):
              stance = "related_but_inconclusive"

        # Check staleness
        eff_date_str = p_raw.get("effective_date")
        stale = False
        if eff_date_str:
          parsed_eff = parse_normalized_date(eff_date_str)
          if parsed_eff:
            try:
              eff_dt = datetime.date(parsed_eff[0], parsed_eff[1], parsed_eff[2])
              days_old = (today - eff_dt).days
              if days_old > self._settings.SOURCE_STALE_AFTER_DAYS:
                stale = True
            except Exception:
              pass

        # Perform deterministic fact comparisons between claim and passage
        p_facts = extract_facts_from_text(p_raw["text"])
        fact_comparisons: List[FactComparisonItem] = []

        for f_type in ("date", "amount", "percentage", "age"):
          c_values = claim_facts.get(f_type, [])
          ev_values = p_facts.get(f_type, [])
          for c_val in c_values:
            match_status, ev_match_val = facts_match(c_val, f_type, ev_values)
            fact_comparisons.append(
                FactComparisonItem(
                    fact_type=f_type,
                    claim_value=c_val,
                    source_value=ev_match_val,
                    status=match_status,
                )
            )

        ev_item = EvidenceItemReport(
            label=p_raw["label"],
            collection=p_raw["collection"],
            source_id=p_raw["source_id"],
            source_title=p_raw["source_title"],
            issuing_authority=p_raw.get("issuing_authority"),
            source_url=p_raw.get("source_url"),
            effective_date=p_raw.get("effective_date"),
            status=_normalize_evidence_status(p_raw.get("status")),
            stale=stale,
            page_number=p_raw["page_number"],
            quote=verified_quote,
            excerpt=p_raw["excerpt"],
            fact_comparisons=fact_comparisons,
        )

        if stance == "supports" and verified_quote:
          verified_supporting.append(ev_item)
        elif stance == "contradicts" and verified_quote:
          verified_contradicting.append(ev_item)
        else:
          verified_related.append(ev_item)

      # 4. Enforce Authoritative Backend Rules for Final Verdict
      final_verdict: Literal["supported", "contradicted", "unverified", "outdated"] = "unverified"
      verdict_basis = "no_evidence"
      explanation = ai_judgement.reasoning or ""
      superseded_info: Optional[SupersededByInfo] = None
      time_warning: Optional[str] = None
      conflicting_sources = False

      # Check for conflicts between current official sources
      current_supporting = [s for s in verified_supporting if s.status != "superseded"]
      current_contradicting = [c_ev for c_ev in verified_contradicting if c_ev.status != "superseded"]

      if current_supporting and current_contradicting:
        conflicting_sources = True
        final_verdict = "unverified"
        verdict_basis = "conflicting_sources"
        explanation = (
            "Conflicting evidence found among current official sources. "
            "Different provisions in current records support and contradict aspects of this claim."
            if target_lang == "en"
            else "தற்போதைய அதிகாரப்பூர்வ ஆவணங்களிடையே முரண்பட்ட சான்றுகள் உள்ளன."
        )

      # RULE 5: Outdated check (requires manifest supersession)
      elif (
          any(s.status == "superseded" for s in verified_supporting)
          or ai_judgement.proposed_verdict == "outdated"
      ):
        # Look for older matching source and newer replacement source
        older_source_ev = next((s for s in verified_supporting if s.status == "superseded"), None)
        if not older_source_ev and verified_supporting:
          older_source_ev = verified_supporting[0]

        has_manifest_supersession = False
        if older_source_ev:
          older_src_meta = self._source_service.store.get_source(older_source_ev.source_id)
          if older_src_meta and older_src_meta.superseded_by:
            newer_src_meta = self._source_service.store.get_source(older_src_meta.superseded_by)
            if newer_src_meta:
              # Check if newer source has verified contradicting or replacing evidence
              replacing_ev = next(
                  (c_ev for c_ev in verified_contradicting if c_ev.source_id == newer_src_meta.source_id),
                  None,
              )
              has_manifest_supersession = True
              superseded_info = SupersededByInfo(
                  newer_source_id=newer_src_meta.source_id,
                  newer_source_title=newer_src_meta.title,
                  newer_effective_date=newer_src_meta.effective_date,
                  newer_page_number=replacing_ev.page_number if replacing_ev else None,
                  replacing_quote=replacing_ev.quote if replacing_ev else None,
              )

        if has_manifest_supersession:
          final_verdict = "outdated"
          verdict_basis = "superseded_source"
          explanation = (
              f"Outdated policy: the claim matched an older notification ('{older_source_ev.source_title}'), "
              f"which was formally superseded by a newer official notification ('{superseded_info.newer_source_title}')."
              if target_lang == "en"
              else f"காலாவதியான கொள்கை: இக்கூற்று முந்தைய அரசாணையின்படி ('{older_source_ev.source_title}') இருந்தது; "
              f"ஆனால் அது புதிய அரசாணையால் ('{superseded_info.newer_source_title}') மாற்றப்பட்டுள்ளது."
          )
        else:
          # Downgrade to Unverified with note
          final_verdict = "unverified"
          verdict_basis = "partial_match"
          explanation = (
              "This claim may be outdated. While older records in our library match aspects of it, "
              "we cannot verify a formal supersession chain. Please verify with the latest official gazette."
              if target_lang == "en"
              else "இக்கூற்று காலாவதியாகியிருக்கலாம். சமீபத்திய அதிகாரப்பூர்வ அறிவிப்பை சரிபார்க்கவும்."
          )

      # RULE 4: Contradicted check
      elif current_contradicting:
        # Check deterministic fact mismatch
        has_deterministic_mismatch = any(
            any(fc.status == "mismatch" for fc in c_ev.fact_comparisons)
            for c_ev in current_contradicting
        )
        if has_deterministic_mismatch:
          final_verdict = "contradicted"
          verdict_basis = "verified_quote_and_facts"
        elif ai_judgement.proposed_verdict == "contradicted":
          final_verdict = "contradicted"
          verdict_basis = "model_judgement_with_verified_quote"
        else:
          final_verdict = "unverified"
          verdict_basis = "partial_match"

      # RULE 3: Supported check
      elif current_supporting:
        # Check that EVERY deterministic claim fact matches
        has_claim_facts = any(claim_facts.get(k) for k in ("date", "amount", "percentage", "age"))

        all_facts_matched = True
        fact_mismatch_detected = False

        if has_claim_facts:
          for f_type in ("date", "amount", "percentage", "age"):
            for c_val in claim_facts.get(f_type, []):
              # Check against all current supporting passages
              matched_any = False
              for s_ev in current_supporting:
                p_facts = extract_facts_from_text(p_by_label[s_ev.label]["text"])
                status, _ = facts_match(c_val, f_type, p_facts.get(f_type, []))
                if status == "match":
                  matched_any = True
                  break
                elif status == "mismatch":
                  fact_mismatch_detected = True

              if not matched_any:
                all_facts_matched = False

        if fact_mismatch_detected:
          # Mismatched fact (e.g. claim said Rs 50,000, source said Rs 25,000)
          final_verdict = "contradicted"
          verdict_basis = "verified_quote_and_facts"
        elif not all_facts_matched:
          final_verdict = "unverified"
          verdict_basis = "partial_match"
          explanation = (
              "Partially supported: the official source addresses this scheme, but does not confirm "
              "all specific details (such as dates, amounts, or criteria) stated in your claim."
              if target_lang == "en"
              else "பகுதியளவு மட்டுமே உறுதிப்படுத்தப்பட்டுள்ளது: ஆவணம் இத்திட்டத்தை குறிப்பிடுகிறது, ஆனால் நீங்கள் குறிப்பிட்ட அனைத்து விவரங்களையும் உறுதிப்படுத்தவில்லை."
          )
        else:
          final_verdict = "supported"
          verdict_basis = "verified_quote_and_facts"

          # RULE 8: Time sensitivity & Past deadline check
          if c.temporal_scope == "current":
            for s_ev in current_supporting:
              p_facts = extract_facts_from_text(p_by_label[s_ev.label]["text"])
              for d_val in p_facts.get("date", []):
                p_date = parse_normalized_date(d_val)
                if p_date:
                  try:
                    d_obj = datetime.date(p_date[0], p_date[1], p_date[2])
                    if d_obj < today:
                      time_warning = (
                          f"Notice: The official source states a deadline of {d_val}, which is in the past relative to today's date. "
                          "If the scheme was not formally extended, applications may currently be closed."
                          if target_lang == "en"
                          else f"எச்சரிக்கை: அதிகாரப்பூர்வ ஆவணம் {d_val} என்ற காலக்கெடுவைக் குறிப்பிடுகிறது, இது இன்றைய தேதிக்கு முந்தையது."
                      )
                      final_verdict = "unverified"
                      verdict_basis = "superseded_source"
                      break
                  except Exception:
                    pass

      else:
        # Default fallback to unverified
        final_verdict = "unverified"
        verdict_basis = "partial_match" if verified_related else "no_evidence"

      m_aspects: List[str] = []
      um_aspects: List[str] = []
      if ai_judgement:
        m_aspects.extend(ai_judgement.matched_aspects)
        um_aspects.extend(ai_judgement.unmatched_aspects)
        for p in ai_judgement.passages:
          m_aspects.extend(p.matched_aspects)
          um_aspects.extend(p.unmatched_aspects)

      final_claim_results.append(
          ClaimResult(
              claim_id=c.claim_id,
              claim_text=c.claim_text,
              claim_type=c.claim_type,
              is_checkable_fact=True,
              claim_facts=claim_facts,
              verdict=final_verdict,
              verdict_basis=verdict_basis,
              explanation=explanation,
              matched_aspects=list(dict.fromkeys(m_aspects)),
              unmatched_aspects=list(dict.fromkeys(um_aspects)) or [c.claim_text],
              supporting_evidence=verified_supporting,
              contradicting_evidence=verified_contradicting,
              related_evidence=verified_related,
              superseded_by_info=superseded_info,
              time_sensitivity_warning=time_warning,
              conflicting_sources=conflicting_sources,
              evidence_level=ev_level,  # type: ignore
          )
      )

    # --- Step 5: Overall Result Assembly ---
    verdicts_set = {r.verdict for r in final_claim_results}
    if len(verdicts_set) == 1:
      overall_verdict = list(verdicts_set)[0]
    else:
      overall_verdict = "mixed"

    # Overall Summary synthesis
    if overall_verdict == "supported":
      overall_summary = (
          "Supported by official government records. Verified quotes and exact factual parameters confirm the claim."
          if target_lang == "en"
          else "அதிகாரப்பூர்வ அரசு ஆவணங்களால் உறுதிப்படுத்தப்பட்டது. சரிபார்க்கப்பட்ட மேற்கோள்கள் இக்கூற்றை உறுதிப்படுத்துகின்றன."
      )
    elif overall_verdict == "contradicted":
      overall_summary = (
          "Contradicted by official government records. Verified sources state conflicting or incompatible rules or figures."
          if target_lang == "en"
          else "அதிகாரப்பூர்வ அரசு ஆவணங்களுடன் முரண்படுகிறது."
      )
    elif overall_verdict == "outdated":
      overall_summary = (
          "Outdated: the claim corresponds to an older government order that has been formally replaced by a newer notification."
          if target_lang == "en"
          else "காலாவதியானது: இக்கூற்று முந்தைய அரசாணையுடன் பொருந்துகிறது, ஆனால் அது புதிய அறிவிப்பால் மாற்றப்பட்டுள்ளது."
      )
    elif overall_verdict == "mixed":
      overall_summary = (
          "Mixed verification outcome: the submission contains multiple claims with differing verdicts."
          if target_lang == "en"
          else "கலவையான சரிபார்ப்பு முடிவு: இச்சமர்ப்பிப்பில் வெவ்வேறு தீர்ப்புகளைக் கொண்ட பல கூற்றுகள் உள்ளன."
      )
    else:
      overall_summary = (
          "Unverified: reliable supporting or contradicting evidence was not found in the official sources searched. "
          "Unverified does not mean the claim is false."
          if target_lang == "en"
          else "சரிபார்க்கப்படவில்லை: தேடப்பட்ட ஆதாரங்களில் போதுமான சான்றுகள் கிடைக்கவில்லை. "
          "சரிபார்க்கப்படவில்லை என்பது இக்கூற்று தவறானது என்று பொருள்படாது."
      )

    cov = CoverageInfo(
        official_sources_searched_count=len(official_titles),
        official_source_titles=official_titles,
        user_documents_included=bool(user_doc_titles),
        user_document_titles=user_doc_titles,
        passages_examined_count=total_passages_examined,
        sources_skipped=all_skipped_sources,
        library_version=library_version,
    )

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    analysis_status = "completed_with_warnings" if warnings else "completed"
    if not ai_available:
      analysis_status = "partial"

    cache_key = self.compute_cache_key(clean_claim, req_lang, scope, doc_ids, library_version)

    report = VerificationReport(
        verification_id=verification_id,
        created_at=now_iso,
        language=target_lang,
        scope=scope,  # type: ignore
        original_claim_text=clean_claim,
        overall_verdict=overall_verdict,
        overall_summary=overall_summary,
        claims=final_claim_results,
        coverage=cov,
        analysis_status=analysis_status,
        warnings=warnings,
        cache_hit=False,
        model=self._settings.effective_gemini_model,
        token_usage=total_tokens,
    )

    # Persist report and update cache
    self._store.save_report(verification_id, report, cache_key=cache_key)

    # Finalize job
    job["status"] = analysis_status
    job["stage"] = "completed"
    job["progress_pct"] = 100
    job["overall_verdict"] = overall_verdict
    job["completed_at"] = now_iso
    self._store.save_job(verification_id, job)
    from app.services.activity_service import get_activity_service
    get_activity_service().record_activity("verification.completed", "verification", verification_id)

    duration_ms = (time.perf_counter() - start_time) * 1000.0
    logger.info(
        "Finished fact verification %s (verdict: %s, gemini_calls: %d, latency: %.1f ms)",
        verification_id,
        overall_verdict,
        gemini_calls_made,
        duration_ms,
    )
    return report

  def run_verification_sync(self, req: VerifyRequest, client_key: str = "default") -> VerificationReport:
    """Synchronous execution wrapper for unit tests and direct scripting."""
    v_id, is_cache = self.start_verification(req, client_key=client_key)
    if is_cache:
      report = self._store.get_report(v_id)
      if report:
        return report

    try:
      loop = asyncio.get_running_loop()
    except RuntimeError:
      loop = None

    if loop and loop.is_running():
      import concurrent.futures
      with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, self.execute_verification(v_id))
        return future.result()
    else:
      return asyncio.run(self.execute_verification(v_id))


_verification_service_instance: Optional[VerificationService] = None

def get_verification_service() -> VerificationService:
  """Dependency provider returning singleton VerificationService."""
  global _verification_service_instance
  if _verification_service_instance is None:
    _verification_service_instance = VerificationService()
  return _verification_service_instance


def set_verification_service(service: Optional[VerificationService]) -> None:
  """Test helper to set or reset singleton VerificationService."""
  global _verification_service_instance
  _verification_service_instance = service
