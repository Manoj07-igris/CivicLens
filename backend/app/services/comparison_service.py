"""Policy Change Detection Engine (Module 2).

Provides deterministic document normalization, clause segmentation, sequence alignment,
word-level token diffing, deterministic fact extraction, noise filtering,
and budgeted Gemini structured analysis with strict backend verification.
"""

import asyncio
import difflib
import logging
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.config import Settings, get_settings
from app.core.errors import ComparisonError, DocumentNotFoundError, DocumentProcessingError
from app.core.prompts import get_compare_system_prompt, wrap_untrusted_content
from app.models.comparison import (
    BatchAnalysisResult,
    CandidateAnalysis,
    ChangeItem,
    ComparisonCounts,
    ComparisonReport,
    EvidenceReference,
    FactChange,
    MinorDifferenceItem,
    WordDiffOp,
)
from app.services.comparison_store import ComparisonStore, get_comparison_store
from app.services.document_store import DocumentStore, get_document_store
from app.services.fact_extractor import (
    ALL_HIGH_IMPORTANCE_KEYWORDS,
    AMOUNT_REGEXES,
    AGE_REGEXES,
    CODE_REGEXES,
    DATE_REGEXES,
    DURATION_REGEXES,
    KEYWORD_CATEGORIES,
    PERCENTAGE_REGEXES,
    TAMIL_NUMERAL_MAP,
    extract_facts_from_text,
    has_high_importance_keywords,
    normalize_tamil_digits,
)
from app.services.gemini_service import GeminiError, GeminiService, get_gemini_service
from app.services.language_service import detect_language, resolve_reply_language

logger = logging.getLogger("civiclens.comparison")


@dataclass
class Segment:
  """Document clause or paragraph with canonical representation and coordinates."""
  segment_id: str
  document_id: str
  document_name: str
  page_start: int
  page_end: int
  original_text: str
  canonical_text: str
  char_start: int
  char_end: int
  heading_path: Optional[str] = None
  ocr_risk: bool = False


# --- Stage 2b: Text Normalization ---

def normalize_text_for_comparison(text: str) -> str:
  """Create canonical representation of text for structural diff and alignment."""
  if not text:
    return ""

  # 1. Unicode NFC
  norm = unicodedata.normalize("NFC", text)

  # 2. Unify quotes and dashes
  norm = re.sub(r"[‘’‚‛]", "'", norm)
  norm = re.sub(r"[“”„‟]", '"', norm)
  norm = re.sub(r"[—–−―]", "-", norm)

  # 3. Unify bullets
  norm = re.sub(r"[\u2022\u2023\u25E6\u2043\u2219\u25CB\u25CF]", "•", norm)

  # 4. Map Tamil numerals to Western digits
  for t_digit, w_digit in TAMIL_NUMERAL_MAP.items():
    norm = norm.replace(t_digit, w_digit)

  # 5. Normalize Indian and Western numbers: collapse digit grouping commas
  # e.g. 2,50,000 -> 250000; 10,00,000 -> 1000000; 1,000 -> 1000
  norm = re.sub(r"(?<=\d),(?=\d)", "", norm)

  # 6. Fix hyphenation line breaks (e.g. "approv-\nal" -> "approval")
  norm = re.sub(r"(\b\w+)-\s*\n\s*(\w+\b)", r"\1\2", norm)

  # 7. Lowercase for Latin
  norm = norm.lower()

  # 8. Collapse whitespace
  norm = re.sub(r"\s+", " ", norm).strip()

  return norm


def strip_repeated_headers_and_footers(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
  """Detect and strip running headers/footers appearing on >= 50% of document pages."""
  if len(pages) < 3:
    return pages

  line_counts: Dict[str, int] = {}
  total_pages = len(pages)

  for p in pages:
    lines = [ln.strip() for ln in p.get("text", "").splitlines() if ln.strip()]
    # Check top 3 lines (headers) and bottom 3 lines (footers)
    header_footer_candidates = set(lines[:3] + lines[-3:]) if len(lines) >= 6 else set(lines)
    for ln in header_footer_candidates:
      # Ignore purely blank or very long content lines
      if 3 <= len(ln) <= 100:
        line_counts[ln] = line_counts.get(ln, 0) + 1

  # Header/footer threshold: appears on 50% or more pages
  repeated_lines = {ln for ln, count in line_counts.items() if count >= max(2, int(total_pages * 0.5))}

  cleaned_pages = []
  for p in pages:
    raw_text = p.get("text", "")
    lines = raw_text.splitlines()
    filtered_lines = [ln for ln in lines if ln.strip() not in repeated_lines]
    cleaned_p = dict(p)
    cleaned_p["text"] = "\n".join(filtered_lines)
    cleaned_pages.append(cleaned_p)

  return cleaned_pages


# --- Stage 2c: Document Segmentation ---

def segment_document(
    doc_id: str,
    doc_name: str,
    pages: List[Dict[str, Any]],
    ocr_risk_pages: Set[int],
) -> List[Segment]:
  """Break document pages into structured clauses and paragraphs with page coordinates."""
  segments: List[Segment] = []
  cleaned_pages = strip_repeated_headers_and_footers(pages)

  current_heading: Optional[str] = None
  seg_counter = 0

  # Header detection pattern: numbered clause (1., 1.1, (a), Section 5) or all-caps header
  clause_pattern = re.compile(
      r"^(?:(?:Section|Clause|Rule|Article|பிரிவு|விதி)\s+)?(?:(?:\d+(?:\.\d+)*)|(?:\([a-zA-Z0-9ivxlcdm]+\))|[A-Z]\.|\(\d+\))\s+",
      re.IGNORECASE,
  )

  for p in cleaned_pages:
    page_num = p.get("page_number", 1)
    page_text = p.get("text", "")
    is_ocr = page_num in ocr_risk_pages

    # Split page text into raw paragraphs (by double newline or bullet points)
    raw_blocks = re.split(r"\n\s*\n+", page_text)

    for block in raw_blocks:
      clean_block = block.strip()
      if not clean_block:
        continue

      # Check if this block looks like a section header (short line, no period at end)
      lines = clean_block.splitlines()
      first_line = lines[0].strip() if lines else ""

      if len(lines) == 1 and len(first_line) < 80 and not first_line.endswith("."):
        current_heading = first_line

      canon = normalize_text_for_comparison(clean_block)
      if not canon:
        continue

      seg_counter += 1
      seg_id = f"seg_{doc_id[:8]}_{seg_counter}"

      segments.append(
          Segment(
              segment_id=seg_id,
              document_id=doc_id,
              document_name=doc_name,
              page_start=page_num,
              page_end=page_num,
              original_text=clean_block,
              canonical_text=canon,
              char_start=0,
              char_end=len(clean_block),
              heading_path=current_heading,
              ocr_risk=is_ocr,
          )
      )

  # Merge tiny fragments (< 25 chars) into preceding segment unless it's a heading
  merged_segments: List[Segment] = []
  for seg in segments:
    if merged_segments and len(seg.original_text) < 25 and not clause_pattern.match(seg.original_text):
      prev = merged_segments[-1]
      if prev.page_end == seg.page_start:
        prev.original_text += "\n" + seg.original_text
        prev.canonical_text += " " + seg.canonical_text
        prev.char_end += len(seg.original_text) + 1
        prev.ocr_risk = prev.ocr_risk or seg.ocr_risk
        continue
    merged_segments.append(seg)

  return merged_segments


# --- Stage 2e: Word-level Diff Operations ---

def compute_word_diff(old_text: str, new_text: str) -> List[WordDiffOp]:
  """Produce token-level diff operations (equal, insert, delete, replace) with original casing."""
  old_tokens = re.findall(r"\S+|\s+", old_text)
  new_tokens = re.findall(r"\S+|\s+", new_text)

  matcher = difflib.SequenceMatcher(None, old_tokens, new_tokens)
  diff_ops: List[WordDiffOp] = []

  for tag, i1, i2, j1, j2 in matcher.get_opcodes():
    sub_old = "".join(old_tokens[i1:i2])
    sub_new = "".join(new_tokens[j1:j2])

    diff_ops.append(
        WordDiffOp(
            op=tag,  # type: ignore
            old_text=sub_old,
            new_text=sub_new,
        )
    )

  return diff_ops


# --- Stage 2f: Deterministic Fact Changes ---

def compute_fact_changes(old_text: str, new_text: str) -> List[FactChange]:
  """Identify authoritative before -> after changes between extracted factual tokens."""
  old_facts = extract_facts_from_text(old_text)
  new_facts = extract_facts_from_text(new_text)

  changes: List[FactChange] = []

  for fact_type in ("date", "amount", "percentage", "age", "duration", "code"):
    o_list = old_facts.get(fact_type, [])
    n_list = new_facts.get(fact_type, [])

    # If lists differ, record the shifts
    if o_list != n_list:
      max_len = max(len(o_list), len(n_list))
      for idx in range(max_len):
        o_val = o_list[idx] if idx < len(o_list) else ""
        n_val = n_list[idx] if idx < len(n_list) else ""
        if o_val != n_val:
          changes.append(
              FactChange(
                  fact_type=fact_type,  # type: ignore
                  old_value=o_val,
                  new_value=n_val,
                  description=f"{fact_type.capitalize()} updated: '{o_val}' -> '{n_val}'",
              )
          )

  return changes


# --- Stage 2d: Clause Alignment ---

@dataclass
class AlignedPair:
  status: str  # 'unchanged', 'moved', 'formatting_only', 'modified', 'added', 'removed'
  old_seg: Optional[Segment]
  new_seg: Optional[Segment]
  similarity: float = 0.0


def align_segments(
    old_segments: List[Segment],
    new_segments: List[Segment],
    similarity_threshold: float = 0.55,
) -> Tuple[List[AlignedPair], float]:
  """Align old and new document segments using monotonic SequenceMatcher + LCS pass.

  Returns (aligned_pairs, overall_overlap_ratio).
  """
  matched_old: Set[int] = set()
  matched_new: Set[int] = set()
  pairs: List[AlignedPair] = []

  # Pass 1: Exact canonical matches
  old_canon_map: Dict[str, List[int]] = {}
  for i, s in enumerate(old_segments):
    old_canon_map.setdefault(s.canonical_text, []).append(i)

  for j, n_seg in enumerate(new_segments):
    c = n_seg.canonical_text
    if c in old_canon_map and old_canon_map[c]:
      i = old_canon_map[c].pop(0)
      matched_old.add(i)
      matched_new.add(j)

      o_seg = old_segments[i]
      # Check if original text differs (e.g. whitespace, quotes, dashes)
      if o_seg.original_text.strip() == n_seg.original_text.strip():
        # Check if moved significantly in document (position ratio difference > 0.3)
        pos_diff = abs((i / max(1, len(old_segments))) - (j / max(1, len(new_segments))))
        status = "moved" if pos_diff > 0.35 else "unchanged"
      else:
        status = "formatting_only"

      pairs.append(AlignedPair(status=status, old_seg=o_seg, new_seg=n_seg, similarity=1.0))

  # Pass 2: Fuzzy matching for remaining segments using SequenceMatcher monotonic pass
  unmatched_old_indices = [i for i in range(len(old_segments)) if i not in matched_old]
  unmatched_new_indices = [j for j in range(len(new_segments)) if j not in matched_new]

  for i in unmatched_old_indices:
    o_seg = old_segments[i]
    best_j: Optional[int] = None
    best_score: float = 0.0

    for j in unmatched_new_indices:
      if j in matched_new:
        continue
      n_seg = new_segments[j]

      # SequenceMatcher ratio over canonical text
      ratio = difflib.SequenceMatcher(None, o_seg.canonical_text, n_seg.canonical_text).quick_ratio()
      if ratio < similarity_threshold * 0.8:
        continue

      full_ratio = difflib.SequenceMatcher(None, o_seg.canonical_text, n_seg.canonical_text).ratio()
      if full_ratio > best_score:
        best_score = full_ratio
        best_j = j

    if best_j is not None and best_score >= similarity_threshold:
      matched_old.add(i)
      matched_new.add(best_j)
      n_seg = new_segments[best_j]
      pairs.append(
          AlignedPair(
              status="modified",
              old_seg=o_seg,
              new_seg=n_seg,
              similarity=round(best_score, 3),
          )
      )

  # Pass 3: Remaining unmatched old segments are 'removed'
  for i in range(len(old_segments)):
    if i not in matched_old:
      pairs.append(
          AlignedPair(
              status="removed",
              old_seg=old_segments[i],
              new_seg=None,
              similarity=0.0,
          )
      )

  # Pass 4: Remaining unmatched new segments are 'added'
  for j in range(len(new_segments)):
    if j not in matched_new:
      pairs.append(
          AlignedPair(
              status="added",
              old_seg=None,
              new_seg=new_segments[j],
              similarity=0.0,
          )
      )

  # Compute overall overlap ratio for unrelated document detection
  total_segments = max(1, len(old_segments) + len(new_segments))
  overlap_count = sum(1 for p in pairs if p.status in ("unchanged", "moved", "formatting_only", "modified"))
  overlap_ratio = (overlap_count * 2) / total_segments

  return pairs, overlap_ratio


# --- Stage 2h & 3: Candidate Selection and Gemini Analysis ---

@dataclass
class CandidateContext:
  change_id: str
  change_type: str
  pair: AlignedPair
  fact_changes: List[FactChange]
  is_high_importance: bool
  word_diff: List[WordDiffOp]
  ocr_risk: bool


class ComparisonService:
  """Central engine for executing, caching, and querying policy change comparisons."""

  def __init__(
      self,
      store: Optional[DocumentStore] = None,
      comp_store: Optional[ComparisonStore] = None,
      gemini: Optional[GeminiService] = None,
      settings: Optional[Settings] = None,
      document_store: Optional[DocumentStore] = None,
      comparison_store: Optional[ComparisonStore] = None,
      gemini_service: Optional[GeminiService] = None,
  ):
    self._store = store or document_store or get_document_store()
    self._comp_store = comp_store or comparison_store or get_comparison_store()
    self._gemini = gemini or gemini_service or get_gemini_service()
    self._settings = settings or get_settings()

  async def run_comparison(
      self,
      old_doc_id: str,
      new_doc_id: str,
      language: str = "auto",
      force: bool = False,
      comparison_id: Optional[str] = None,
  ) -> ComparisonReport:
    """Execute complete deterministic comparison and budgeted Gemini analysis."""
    clean_old_id = str(old_doc_id).strip()
    clean_new_id = str(new_doc_id).strip()
    comp_id = comparison_id or str(uuid.uuid4())

    logger.info("[%s] Initiating policy comparison: old=%s vs new=%s", comp_id, clean_old_id, clean_new_id)

    # 1. Validation & Precondition Gate
    if clean_old_id == clean_new_id:
      raise ComparisonError("Older and newer document IDs must refer to different documents.")

    old_meta = self._store.get_metadata(clean_old_id)
    if not old_meta:
      raise DocumentNotFoundError(f"Old document '{clean_old_id}' was not found.")

    new_meta = self._store.get_metadata(clean_new_id)
    if not new_meta:
      raise DocumentNotFoundError(f"New document '{clean_new_id}' was not found.")

    if old_meta.get("status") not in ("ready", "ready_with_warnings"):
      raise ComparisonError(f"Older document '{clean_old_id}' is not in 'ready' status.")

    if new_meta.get("status") not in ("ready", "ready_with_warnings"):
      raise ComparisonError(f"Newer document '{clean_new_id}' is not in 'ready' status.")

    max_pages = self._settings.COMPARE_MAX_PAGES_PER_DOC
    if old_meta.get("page_count", 1) > max_pages or new_meta.get("page_count", 1) > max_pages:
      raise ComparisonError(f"Documents exceed maximum allowed page limit ({max_pages} pages).")

    old_name = old_meta.get("filename", "old_document.pdf")
    new_name = new_meta.get("filename", "new_document.pdf")

    # 2. Resolve target language
    resolved_lang = "en"
    if language in ("en", "ta"):
      resolved_lang = language
    else:
      # Auto-detect language from aggregate document metadata
      doc_lang = new_meta.get("language") or old_meta.get("language") or "en"
      resolved_lang = "ta" if doc_lang == "ta" else "en"

    # 3. Check Cache (Unless forced)
    if not force:
      cached_id = self._comp_store.find_cached(clean_old_id, clean_new_id, resolved_lang)
      if cached_id:
        cached_report_dict = self._comp_store.get_report(cached_id)
        if cached_report_dict:
          logger.info("[%s] Returning cached comparison report from %s", comp_id, cached_id)
          return ComparisonReport.model_validate(cached_report_dict)

    # Update Job Progress: Segmenting & Aligning
    self._comp_store.update_job(
        comp_id,
        status="running",
        progress="Segmenting and normalizing document clauses...",
        old_document_id=clean_old_id,
        new_document_id=clean_new_id,
        old_document_name=old_name,
        new_document_name=new_name,
        language=resolved_lang,
    )

    # Retrieve Page Text
    old_pages_res = self._store.get_pages(clean_old_id, page=1, page_size=1000)
    old_pages = old_pages_res.get("pages", [])

    new_pages_res = self._store.get_pages(clean_new_id, page=1, page_size=1000)
    new_pages = new_pages_res.get("pages", [])

    old_total_chars = sum(len(p.get("text", "")) for p in old_pages)
    new_total_chars = sum(len(p.get("text", "")) for p in new_pages)

    if old_total_chars == 0:
      raise DocumentProcessingError(f"Older document '{clean_old_id}' contains no usable text.")
    if new_total_chars == 0:
      raise DocumentProcessingError(f"Newer document '{clean_new_id}' contains no usable text.")

    # Collect OCR / Low Quality flags
    old_ocr_risk_pages = {
        p.get("page_number", 1)
        for p in old_pages
        if p.get("quality") in ("low_quality", "needs_ocr", "blank") or p.get("extraction_method") == "tesseract_ocr"
    }
    new_ocr_risk_pages = {
        p.get("page_number", 1)
        for p in new_pages
        if p.get("quality") in ("low_quality", "needs_ocr", "blank") or p.get("extraction_method") == "tesseract_ocr"
    }

    warnings: List[str] = []
    if old_ocr_risk_pages or new_ocr_risk_pages:
      warnings.append(
          "Notice: One or both documents contain scanned or OCR-extracted pages. "
          "Minor wording discrepancies may be due to OCR inaccuracies."
      )

    # 4. Segmentation & Alignment
    old_segments = segment_document(clean_old_id, old_name, old_pages, old_ocr_risk_pages)
    new_segments = segment_document(clean_new_id, new_name, new_pages, new_ocr_risk_pages)

    threshold = self._settings.COMPARE_SIMILARITY_MATCH_THRESHOLD
    aligned_pairs, overlap_ratio = align_segments(old_segments, new_segments, similarity_threshold=threshold)

    if overlap_ratio < 0.10 and (len(old_segments) > 2 or len(new_segments) > 2):
      warnings.append("These documents look unrelated; the comparison may not be meaningful.")

    # 5. Classify Pairs, Extract Facts & Separate Noise
    candidates: List[CandidateContext] = []
    minor_diffs: List[MinorDifferenceItem] = []
    counts = ComparisonCounts()

    minor_counter = 0
    change_counter = 0

    for pair in aligned_pairs:
      st = pair.status

      if st == "unchanged":
        counts.unchanged += 1
        continue

      elif st == "moved":
        counts.moved += 1
        minor_counter += 1
        minor_diffs.append(
            MinorDifferenceItem(
                item_id=f"min_{minor_counter}",
                diff_type="moved",
                old_page=pair.old_seg.page_start if pair.old_seg else None,
                new_page=pair.new_seg.page_start if pair.new_seg else None,
                old_text=pair.old_seg.original_text[:140] if pair.old_seg else "",
                new_text=pair.new_seg.original_text[:140] if pair.new_seg else "",
                reason="Section reordered within document without factual changes.",
            )
        )
        continue

      elif st == "formatting_only":
        counts.formatting_only += 1
        minor_counter += 1
        minor_diffs.append(
            MinorDifferenceItem(
                item_id=f"min_{minor_counter}",
                diff_type="formatting_only",
                old_page=pair.old_seg.page_start if pair.old_seg else None,
                new_page=pair.new_seg.page_start if pair.new_seg else None,
                old_text=pair.old_seg.original_text[:140] if pair.old_seg else "",
                new_text=pair.new_seg.original_text[:140] if pair.new_seg else "",
                reason="Formatting, casing, or punctuation differences only.",
            )
        )
        continue

      elif st == "modified":
        counts.modified += 1
        o_txt = pair.old_seg.original_text if pair.old_seg else ""
        n_txt = pair.new_seg.original_text if pair.new_seg else ""

        fact_chgs = compute_fact_changes(o_txt, n_txt)
        is_high = bool(fact_chgs) or has_high_importance_keywords(o_txt) or has_high_importance_keywords(n_txt)
        w_diff = compute_word_diff(o_txt, n_txt)
        is_ocr = bool(pair.old_seg and pair.old_seg.ocr_risk) or bool(pair.new_seg and pair.new_seg.ocr_risk)

        change_counter += 1
        candidates.append(
            CandidateContext(
                change_id=f"chg_{change_counter}",
                change_type="modified",
                pair=pair,
                fact_changes=fact_chgs,
                is_high_importance=is_high,
                word_diff=w_diff,
                ocr_risk=is_ocr,
            )
        )

      elif st == "added":
        counts.added += 1
        n_txt = pair.new_seg.original_text if pair.new_seg else ""
        n_facts = extract_facts_from_text(n_txt)
        fact_chgs = [
            FactChange(fact_type=ft, old_value="", new_value=v, description=f"New {ft} added: '{v}'")  # type: ignore
            for ft, vals in n_facts.items() for v in vals
        ]
        is_high = bool(fact_chgs) or has_high_importance_keywords(n_txt)
        is_ocr = bool(pair.new_seg and pair.new_seg.ocr_risk)

        change_counter += 1
        candidates.append(
            CandidateContext(
                change_id=f"chg_{change_counter}",
                change_type="added",
                pair=pair,
                fact_changes=fact_chgs,
                is_high_importance=is_high,
                word_diff=[],
                ocr_risk=is_ocr,
            )
        )

      elif st == "removed":
        counts.removed += 1
        o_txt = pair.old_seg.original_text if pair.old_seg else ""
        o_facts = extract_facts_from_text(o_txt)
        fact_chgs = [
            FactChange(fact_type=ft, old_value=v, new_value="", description=f"Repealed {ft}: '{v}'")  # type: ignore
            for ft, vals in o_facts.items() for v in vals
        ]
        is_high = bool(fact_chgs) or has_high_importance_keywords(o_txt)
        is_ocr = bool(pair.old_seg and pair.old_seg.ocr_risk)

        change_counter += 1
        candidates.append(
            CandidateContext(
                change_id=f"chg_{change_counter}",
                change_type="removed",
                pair=pair,
                fact_changes=fact_chgs,
                is_high_importance=is_high,
                word_diff=[],
                ocr_risk=is_ocr,
            )
        )

    # 6. Sort & Truncate Candidates
    # Priority: High importance (fact changes / keywords) first, then modified, then added/removed
    candidates.sort(
        key=lambda c: (
            1 if c.is_high_importance else 0,
            len(c.fact_changes),
            1 if c.change_type == "modified" else 0,
        ),
        reverse=True,
    )

    max_cands = self._settings.COMPARE_MAX_CANDIDATES
    truncated_count = max(0, len(candidates) - max_cands)
    if truncated_count > 0:
      warnings.append(
          f"Candidate list capped at top {max_cands} highest-impact changes. "
          f"{truncated_count} lower-priority differences listed with raw diff only."
      )

    active_candidates = candidates[:max_cands]

    # 7. Budgeted Gemini Analysis
    batch_size = self._settings.COMPARE_BATCH_SIZE
    max_calls = self._settings.COMPARE_MAX_GEMINI_CALLS

    # Prepare batches
    batches: List[List[CandidateContext]] = []
    for i in range(0, len(active_candidates), batch_size):
      batches.append(active_candidates[i : i + batch_size])

    # Cap number of batches to max_calls
    if len(batches) > max_calls:
      batches = batches[:max_calls]

    analysis_status = "completed"
    ai_results: Dict[str, CandidateAnalysis] = {}
    batch_summaries: List[str] = []

    # Check if Gemini is configured
    can_call_gemini = self._gemini.is_configured()
    if not can_call_gemini:
      warnings.append("AI explanations unavailable: GEMINI_API_KEY is not configured. Showing deterministic fact changes.")
      analysis_status = "completed_with_warnings"

    if can_call_gemini and batches:
      for b_idx, batch in enumerate(batches):
        self._comp_store.update_job(
            comp_id,
            status="running",
            progress=f"Analyzing change batch {b_idx + 1} of {len(batches)} with Gemini...",
        )

        prompt_text = self._build_batch_prompt(batch, resolved_lang)
        sys_inst = get_compare_system_prompt(resolved_lang)

        try:
          batch_res = await self._gemini.generate_structured(
              prompt=prompt_text,
              response_schema=BatchAnalysisResult,
              system_instruction=sys_inst,
              temperature=0.1,
          )

          # Backend Verification: Only accept returned IDs that were in this batch
          allowed_ids = {c.change_id for c in batch}
          for c_eval in batch_res.candidates:
            if c_eval.candidate_id in allowed_ids:
              ai_results[c_eval.candidate_id] = c_eval

          if batch_res.batch_summary and batch_res.batch_summary.strip():
            batch_summaries.append(batch_res.batch_summary.strip())

        except GeminiError as g_err:
          logger.warning("[%s] Gemini batch %d failed: [%s] %s", comp_id, b_idx + 1, g_err.code, g_err.message)
          warnings.append(f"AI explanation failed for batch {b_idx + 1}: {g_err.message}. Raw differences preserved.")
          analysis_status = "completed_with_warnings"
        except Exception as exc:
          logger.exception("[%s] Unexpected error in batch %d: %s", comp_id, b_idx + 1, exc)
          warnings.append(f"AI explanation encountered an issue for batch {b_idx + 1}. Raw differences preserved.")
          analysis_status = "completed_with_warnings"

    # 8. Assemble ChangeItem Objects
    final_changes: List[ChangeItem] = []

    for cand in candidates:
      c_eval = ai_results.get(cand.change_id)
      pair = cand.pair

      old_ref: Optional[EvidenceReference] = None
      if pair.old_seg:
        old_ref = EvidenceReference(
            document_id=pair.old_seg.document_id,
            document_name=pair.old_seg.document_name,
            page_start=pair.old_seg.page_start,
            page_end=pair.old_seg.page_end,
            text_excerpt=pair.old_seg.original_text[:300] + ("..." if len(pair.old_seg.original_text) > 300 else ""),
            full_text=pair.old_seg.original_text,
            char_start=pair.old_seg.char_start,
            char_end=pair.old_seg.char_end,
        )

      new_ref: Optional[EvidenceReference] = None
      if pair.new_seg:
        new_ref = EvidenceReference(
            document_id=pair.new_seg.document_id,
            document_name=pair.new_seg.document_name,
            page_start=pair.new_seg.page_start,
            page_end=pair.new_seg.page_end,
            text_excerpt=pair.new_seg.original_text[:300] + ("..." if len(pair.new_seg.original_text) > 300 else ""),
            full_text=pair.new_seg.original_text,
            char_start=pair.new_seg.char_start,
            char_end=pair.new_seg.char_end,
        )

      # Determine final category, summary, and importance
      if c_eval:
        category = c_eval.category
        importance = c_eval.importance
        is_material = c_eval.is_material
        plain_summary = c_eval.plain_summary
        practical_impact = c_eval.practical_impact
        uncertainty = c_eval.uncertainty_note
        analysis_state = "analysed"

        # Check if AI marked minor but backend facts changed
        ai_minor_fact_flag = False
        if (not is_material or c_eval.change_type_confirmation == "not_material") and (cand.fact_changes or cand.is_high_importance):
          ai_minor_fact_flag = True
          is_material = True  # Preserve visibility
      else:
        # Fallback to deterministic summary
        category = self._infer_deterministic_category(cand)
        importance = "high" if cand.is_high_importance else "medium"
        is_material = True
        plain_summary = self._generate_deterministic_summary(cand, resolved_lang)
        practical_impact = None
        uncertainty = None
        analysis_state = "not_analysed"
        ai_minor_fact_flag = False
        counts.not_analysed += 1

      final_changes.append(
          ChangeItem(
              change_id=cand.change_id,
              change_type=cand.change_type,  # type: ignore
              category=category,
              importance=importance,  # type: ignore
              is_material=is_material,
              ai_flagged_minor_but_facts_changed=ai_minor_fact_flag,
              old=old_ref,
              new=new_ref,
              word_diff=cand.word_diff,
              fact_changes=cand.fact_changes,
              plain_summary=plain_summary,
              practical_impact=practical_impact,
              uncertainty_note=uncertainty,
              ocr_risk=cand.ocr_risk,
              analysis_state=analysis_state,  # type: ignore
          )
      )

    # 9. Overall Executive Summary
    overall_summary = self._build_overall_summary(
        old_name, new_name, final_changes, batch_summaries, resolved_lang
    )

    now_iso = datetime.now(timezone.utc).isoformat()

    report = ComparisonReport(
        comparison_id=comp_id,
        old_document_id=clean_old_id,
        old_document_name=old_name,
        new_document_id=clean_new_id,
        new_document_name=new_name,
        created_at=now_iso,
        language=resolved_lang,
        analysis_status=analysis_status,  # type: ignore
        warnings=warnings,
        overall_summary=overall_summary,
        counts=counts,
        changes=final_changes,
        minor_differences_count=len(minor_diffs),
        minor_differences=minor_diffs,
        truncated_candidates=truncated_count,
    )

    # Persist report and update job record
    self._comp_store.update_job(
        comp_id,
        status=analysis_status,
        progress="Comparison completed successfully.",
        report=report.model_dump(),
        warnings=warnings,
    )
    from app.services.activity_service import get_activity_service
    get_activity_service().record_activity("comparison.completed", "comparison", comp_id)

    logger.info(
        "[%s] Comparison completed: changes=%d, minor=%d, status=%s",
        comp_id, len(final_changes), len(minor_diffs), analysis_status
    )

    return report

  def run_comparison_sync(
      self,
      old_document_id: str,
      new_document_id: str,
      language: str = "en",
      force: bool = False,
  ) -> ComparisonReport:
    """Synchronous wrapper for running comparisons in tests or scripts."""
    try:
      loop = asyncio.get_event_loop()
    except RuntimeError:
      loop = asyncio.new_event_loop()
      asyncio.set_event_loop(loop)
    if loop.is_running():
      import concurrent.futures
      with concurrent.futures.ThreadPoolExecutor() as pool:
        return pool.submit(
            asyncio.run,
            self.run_comparison(old_document_id, new_document_id, language=language, force=force),
        ).result()
    return loop.run_until_complete(
        self.run_comparison(old_document_id, new_document_id, language=language, force=force)
    )

  async def retry_failed_analysis(self, comp_id: str) -> ComparisonReport:
    """Re-run Gemini AI analysis on candidate changes that were not analyzed."""
    job = self._comp_store.get_job(comp_id)
    if not job:
      raise ComparisonError(f"Comparison '{comp_id}' was not found.")

    report_dict = job.get("report")
    if not report_dict:
      raise ComparisonError("No report found to retry.")

    report = ComparisonReport.model_validate(report_dict)
    unanalysed = [c for c in report.changes if c.analysis_state in ("not_analysed", "failed")]
    if not unanalysed:
      return report

    logger.info("[%s] Retrying AI analysis on %d items", comp_id, len(unanalysed))

    batch_size = self._settings.COMPARE_BATCH_SIZE
    max_calls = self._settings.COMPARE_MAX_GEMINI_CALLS

    batches: List[List[ChangeItem]] = []
    for i in range(0, len(unanalysed), batch_size):
      batches.append(unanalysed[i : i + batch_size])
    if len(batches) > max_calls:
      batches = batches[:max_calls]

    lang = report.language
    sys_inst = get_compare_system_prompt(lang)

    for b_idx, batch in enumerate(batches):
      # Format prompt
      lines = [
          f"Analyze the following {len(batch)} policy change items between baseline (OLD) and revised (NEW) documents.",
          f"Target language: {lang}.",
          "",
      ]
      for item in batch:
        lines.append(f"--- CANDIDATE ID: {item.change_id} ---")
        lines.append(f"Change Type: {item.change_type}")
        if item.fact_changes:
          facts_str = "; ".join(f"{fc.fact_type}: '{fc.old_value}' -> '{fc.new_value}'" for fc in item.fact_changes)
          lines.append(f"Deterministic Facts: {facts_str}")
        lines.append(wrap_untrusted_content(item.old.full_text if item.old else "[NONE]", label="untrusted_old_text"))
        lines.append(wrap_untrusted_content(item.new.full_text if item.new else "[NONE]", label="untrusted_new_text"))
        lines.append("")

      prompt_text = "\n".join(lines)
      try:
        res = await self._gemini.generate_structured(
            prompt=prompt_text,
            response_schema=BatchAnalysisResult,
            system_instruction=sys_inst,
            temperature=0.1,
        )
        eval_map = {e.candidate_id: e for e in res.candidates}
        for item in batch:
          if item.change_id in eval_map:
            ev = eval_map[item.change_id]
            item.category = ev.category
            item.importance = ev.importance
            item.is_material = ev.is_material
            item.plain_summary = ev.plain_summary
            item.practical_impact = ev.practical_impact
            item.uncertainty_note = ev.uncertainty_note
            item.analysis_state = "analysed"
            report.counts.not_analysed = max(0, report.counts.not_analysed - 1)
      except Exception as exc:
        logger.warning("[%s] Retry batch %d failed: %s", comp_id, b_idx + 1, exc)

    # Check if all now analyzed
    remaining_unanalysed = sum(1 for c in report.changes if c.analysis_state != "analysed")
    report.analysis_status = "completed" if remaining_unanalysed == 0 else "completed_with_warnings"

    self._comp_store.update_job(
        comp_id,
        status=report.analysis_status,
        progress="Analysis retried successfully.",
        report=report.model_dump(),
    )

    return report

  def _build_batch_prompt(self, batch: List[CandidateContext], language: str) -> str:
    """Format safe batch prompt with untrusted boundary tags for Gemini analysis."""
    lines = [
        f"Analyze the following {len(batch)} candidate policy changes between baseline (OLD) and revised (NEW) documents.",
        f"Provide structured explanations in requested language ('{language}').",
        "Keep official departmental terms, forms, and statutory acronyms accurate.",
        "",
    ]

    for cand in batch:
      lines.append(f"=== CANDIDATE ID: {cand.change_id} ===")
      lines.append(f"Candidate Type: {cand.change_type}")
      if cand.fact_changes:
        f_str = "; ".join(f"{fc.fact_type}: '{fc.old_value}' -> '{fc.new_value}'" for fc in cand.fact_changes)
        lines.append(f"Detected Fact Changes: {f_str}")

      o_text = cand.pair.old_seg.original_text if cand.pair.old_seg else "[NOT PRESENT IN OLD VERSION]"
      n_text = cand.pair.new_seg.original_text if cand.pair.new_seg else "[NOT PRESENT IN NEW VERSION]"

      lines.append(wrap_untrusted_content(o_text, label="untrusted_old_text"))
      lines.append(wrap_untrusted_content(n_text, label="untrusted_new_text"))
      lines.append("")

    return "\n".join(lines)

  def _infer_deterministic_category(self, cand: CandidateContext) -> str:
    """Infer change category from deterministic fact types or keywords without AI."""
    types = {fc.fact_type for fc in cand.fact_changes}
    if "date" in types:
      return "deadline"
    if "amount" in types:
      return "amount_benefit"
    if "age" in types:
      return "eligibility"
    if "percentage" in types:
      return "conditions_rules"
    if "code" in types:
      return "procedure"

    text = ""
    if cand.pair.new_seg:
      text += cand.pair.new_seg.original_text.lower()
    if cand.pair.old_seg:
      text += " " + cand.pair.old_seg.original_text.lower()

    for cat, kws in KEYWORD_CATEGORIES.items():
      if any(kw in text for kw in kws):
        return cat

    return "other"

  def _generate_deterministic_summary(self, cand: CandidateContext, lang: str) -> str:
    """Generate concise deterministic summary when Gemini is unconfigured or failed."""
    if cand.fact_changes:
      parts = [f"{fc.fact_type.capitalize()}: '{fc.old_value}' -> '{fc.new_value}'" for fc in cand.fact_changes]
      desc = "; ".join(parts)
      return (
          f"மாற்றப்பட்ட விவரங்கள்: {desc}"
          if lang == "ta"
          else f"Updated factual parameters: {desc}"
      )

    if cand.change_type == "added":
      return "புதிய விதி அல்லது பிரிவு சேர்க்கப்பட்டுள்ளது." if lang == "ta" else "Newly introduced policy clause or section."
    elif cand.change_type == "removed":
      return "முந்தைய விதி அல்லது பிரிவு நீக்கப்பட்டுள்ளது." if lang == "ta" else "Repealed or removed policy clause."
    else:
      return "விதிமுறைகளில் மாற்றங்கள் செய்யப்பட்டுள்ளன." if lang == "ta" else "Clause wording updated between versions."

  def _build_overall_summary(
      self,
      old_name: str,
      new_name: str,
      changes: List[ChangeItem],
      batch_summaries: List[str],
      language: str,
  ) -> str:
    """Build concise executive overall summary of policy changes."""
    if batch_summaries:
      return " ".join(batch_summaries)

    high_count = sum(1 for c in changes if c.importance == "high")
    mod_count = sum(1 for c in changes if c.change_type == "modified")
    add_count = sum(1 for c in changes if c.change_type == "added")
    rem_count = sum(1 for c in changes if c.change_type == "removed")

    if language == "ta":
      return (
          f"'{old_name}' மற்றும் '{new_name}' இடையேயான கொள்கை மாற்ற ஒப்பீட்டு அறிக்கை. "
          f"மொத்தம் {len(changes)} மாற்றங்கள் கண்டறியப்பட்டுள்ளன (சேர்க்கப்பட்டவை: {add_count}, "
          f"நீக்கப்பட்டவை: {rem_count}, திருத்தப்பட்டவை: {mod_count}). "
          f"{high_count} முக்கிய மாற்றங்கள் குடிமக்களின் தகுதி, காலக்கெடு அல்லது நிதிப்பயன்களை பாதிக்கின்றன."
      )
    else:
      return (
          f"Policy comparison between '{old_name}' and '{new_name}'. "
          f"Detected {len(changes)} substantive changes (added: {add_count}, "
          f"removed: {rem_count}, modified: {mod_count}). "
          f"{high_count} high-priority change(s) directly impact eligibility, deadlines, or benefits."
      )


# Global singleton
_comparison_service: Optional[ComparisonService] = None


def get_comparison_service() -> ComparisonService:
  global _comparison_service
  if _comparison_service is None:
    _comparison_service = ComparisonService()
  return _comparison_service


def set_comparison_service(service: Optional[ComparisonService]) -> None:
  global _comparison_service
  _comparison_service = service
