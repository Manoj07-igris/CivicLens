"""Form Field Extraction and Explanation Service (Module 4).

Assists citizens with understanding complex, bureaucratic government application
forms without collecting or storing personal citizen data.
Extracts candidate form fields and provides plain-language explanations with
clear evidence-basis tracking (stated_in_form_text vs general_knowledge).
"""

import logging
import re
from typing import Any, Dict, List, Optional
import uuid

from app.core.config import Settings, get_settings
from app.core.errors import DocumentNotFoundError, DocumentProcessingError
from app.core.pii_guard import ensure_no_pii
from app.core.prompts import (
    get_form_field_explain_prompt,
    wrap_untrusted_content,
)
from app.models.service_guide import (
    FormFieldCandidate,
    FormFieldExplainDraft,
    FormFieldExplainRequest,
    FormFieldExplainResponse,
    FormFieldExplanationItem,
    FormFieldExtractRequest,
    FormFieldExtractResponse,
)
from app.services.document_store import DocumentStore
from app.services.gemini_service import GeminiService, get_gemini_service

logger = logging.getLogger("civiclens.form_fields")

# Regex to strip model hallucinated URLs and phone/email contacts
URL_REGEX = re.compile(r"https?://[^\s)\]]+", re.IGNORECASE)
CONTACT_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b|"
    r"(?<!\d)(?:(?:\+91|0)[\s-]?)?[6-9]\d{9}(?!\d)"
)

# Common government form field indicators (English & Tamil)
COMMON_FIELD_PATTERNS = [
    # English
    r"name of (?:the )?(?:applicant|candidate|beneficiary|child|deceased)",
    r"father'?s?\s*(?:/|\bor\b)?\s*husband'?s?\s*name",
    r"mother'?s?\s*name",
    r"guardian'?s?\s*name",
    r"date of birth|dob",
    r"gender|sex",
    r"marital status",
    r"permanent address",
    r"present address|current address|communication address",
    r"door no|flat no|house no",
    r"street|road|ward",
    r"village|town|city",
    r"taluk|tehsil|mandal",
    r"district",
    r"pin\s*code|postal code",
    r"aadhaar (?:number|no|card)",
    r"ration card (?:number|no)|smart card (?:number|no)",
    r"community|caste|category",
    r"sub-caste",
    r"religion",
    r"annual (?:family )?income",
    r"occupation|profession",
    r"educational qualification",
    r"bank account (?:number|no)",
    r"bank name & branch|name of the bank",
    r"ifsc (?:code|no)",
    r"micr code",
    r"mobile (?:number|no)|phone (?:number|no)",
    r"email (?:address|id)",
    r"survey (?:number|no)|sub-division (?:number|no)",
    r"patta (?:number|no)",
    r"disability (?:percentage|type|id|udid)",
    r"ration shop (?:number|fps)",

    # Tamil
    r"விண்ணப்பதாரர் பெயர்",
    r"தகப்பனார்\s*(?:/|\bஅல்லது\b)?\s*கணவர் பெயர்",
    r"தாயார் பெயர்",
    r"பிறந்த தேதி",
    r"வயது",
    r"பாலினம்",
    r"திருமண நிலை",
    r"நிரந்தர முகவரி",
    r"தற்போதைய முகவரி",
    r"கதவு எண்",
    r"தெரு|வார்டு",
    r"கிராமம்|நகரம்",
    r"வட்டம்|தாலுகா",
    r"மாவட்டம்",
    r"அஞ்சல் குறியீட்டு எண்|பின்கோடு",
    r"ஆதார் எண்",
    r"குடும்ப அட்டை எண்|ஸ்மார்ட் கார்டு எண்",
    r"சாதி|பிரிவு",
    r"உட்பிரிவு",
    r"மதம்",
    r"ஆண்டு வருமானம்",
    r"தொழில்",
    r"கல்வித் தகுதி",
    r"வங்கி கணக்கு எண்",
    r"வங்கி பெயர் மற்றும் கிளை",
    r"ifsc குறியீடு",
    r"கைபேசி எண்|தொலைபேசி எண்",
    r"மின்னஞ்சல் முகவரி",
    r"புல எண்|சர்வே எண்",
    r"பட்டா எண்",
    r"மாற்றுத்திறனாளி அடையாள அட்டை எண்",
]

COMPILED_FIELD_PATTERNS = [re.compile(p, re.IGNORECASE) for p in COMMON_FIELD_PATTERNS]

NUMBERED_ROW_REGEX = re.compile(
    r"(?:^|\n)\s*(?:\d{1,2}[.)]|\([a-z0-9]\))\s*([A-Za-z\u0B80-\u0BFF\s/()\-&]{3,60})(?::|\.{2,}|_{2,}|\n|$)",
    re.MULTILINE,
)


def _clean_text_for_security(text: str) -> str:
  """Strip potential URLs and contact numbers from model-generated text."""
  t = URL_REGEX.sub("[link removed]", text)
  t = CONTACT_REGEX.sub("[contact removed]", t)
  return t


class FormFieldService:
  """Service for extracting candidate form fields and explaining them."""

  def __init__(
      self,
      settings: Optional[Settings] = None,
      doc_store: Optional[DocumentStore] = None,
      gemini_service: Optional[GeminiService] = None,
  ):
    self._settings = settings or get_settings()
    self._doc_store = doc_store
    self._gemini = gemini_service

  @property
  def doc_store(self) -> DocumentStore:
    if self._doc_store is None:
      self._doc_store = DocumentStore()
    return self._doc_store

  @property
  def gemini(self) -> GeminiService:
    if self._gemini is None:
      self._gemini = get_gemini_service()
    return self._gemini

  def extract_fields(self, req: FormFieldExtractRequest) -> FormFieldExtractResponse:
    """Extract candidate fields from user-uploaded form PDF or raw text."""
    full_text = ""
    pages_text: List[tuple[int, str]] = []

    if req.document_id:
      chunks = self.doc_store.get_chunks(req.document_id)
      if not chunks:
        meta = self.doc_store.get_metadata(req.document_id)
        if not meta:
          raise DocumentNotFoundError(f"Document '{req.document_id}' not found.")
        raise DocumentProcessingError("No text chunks available for this document.")
      
      # Group chunks by page number
      page_map: Dict[int, List[str]] = {}
      for chk in chunks:
        page_map.setdefault(chk.page_number, []).append(chk.text)
      
      for pno in sorted(page_map.keys()):
        ptxt = "\n".join(page_map[pno])
        pages_text.append((pno, ptxt))
        full_text += f"\n--- Page {pno} ---\n" + ptxt
    elif req.raw_text:
      ensure_no_pii(req.raw_text, field_name="raw_text")
      full_text = req.raw_text
      pages_text.append((1, req.raw_text))
    else:
      raise DocumentProcessingError("Either document_id or raw_text must be provided.")

    detected_fields: List[FormFieldCandidate] = []
    seen_names = set()

    # 1. Regex pattern matching against known civic form fields
    for pno, ptext in pages_text:
      for pat in COMPILED_FIELD_PATTERNS:
        for match in pat.finditer(ptext):
          raw_match = match.group(0).strip()
          normalized = raw_match.lower()
          if normalized not in seen_names:
            seen_names.add(normalized)
            # Find surrounding snippet (up to 120 chars)
            start = max(0, match.start() - 30)
            end = min(len(ptext), match.end() + 60)
            snippet = ptext[start:end].replace("\n", " ").strip()
            
            title_case = " ".join(word.capitalize() for word in raw_match.split())
            detected_fields.append(
                FormFieldCandidate(
                    id=f"fld_{uuid.uuid4().hex[:6]}",
                    name=title_case,
                    page_number=pno,
                    context_snippet=snippet,
                )
            )

    # 2. Numbered row regex matching (e.g. 1. Name of Father: ...)
    for pno, ptext in pages_text:
      for match in NUMBERED_ROW_REGEX.finditer(ptext):
        raw_name = match.group(1).strip()
        if len(raw_name) >= 3 and len(raw_name) <= 50:
          normalized = raw_name.lower()
          if normalized not in seen_names:
            seen_names.add(normalized)
            title_case = " ".join(word.capitalize() for word in raw_name.split())
            detected_fields.append(
                FormFieldCandidate(
                    id=f"fld_{uuid.uuid4().hex[:6]}",
                    name=title_case,
                    page_number=pno,
                    context_snippet=match.group(0).strip()[:100],
                )
            )

    # Cap to max configured fields
    max_fields = self._settings.FORM_FIELDS_MAX
    capped_fields = detected_fields[:max_fields]

    return FormFieldExtractResponse(
        fields=capped_fields,
        total_detected=len(capped_fields),
    )

  async def explain_fields(self, req: FormFieldExplainRequest) -> FormFieldExplainResponse:
    """Generate plain-language explanations for candidate form fields."""
    if req.context_text:
      ensure_no_pii(req.context_text, field_name="context_text")

    form_context = req.context_text or ""
    if req.document_id and not form_context:
      chunks = self.doc_store.get_chunks(req.document_id)
      if chunks:
        # Assemble first ~10000 chars of document text
        parts = []
        for chk in chunks[:15]:
          parts.append(f"[Page {chk.page_number}]: {chk.text}")
        form_context = "\n\n".join(parts)[:12000]

    # Target language
    target_lang = req.language
    if target_lang == "auto" or not target_lang:
      target_lang = "en"

    system_prompt = get_form_field_explain_prompt(target_lang)
    fields_list = "\n".join(f"- {name}" for name in req.field_names)

    user_prompt = (
        f"Please explain the following government application form fields for a citizen:\n\n"
        f"Fields to explain:\n{fields_list}\n\n"
        f"Reference Form Text (Untrusted Data):\n"
        f"{wrap_untrusted_content(form_context, label='untrusted_form_data')}\n\n"
        f"Explain each field in simple terms. If the form text explicitly defines the field, "
        f"set basis to 'stated_in_form_text' with an exact quote. If not, set basis to "
        f"'general_knowledge'. Do not invent numbers or URLs."
    )

    draft, token_usage = await self.gemini.generate_structured(
        prompt=user_prompt,
        schema=FormFieldExplainDraft,
        system_prompt=system_prompt,
        temperature=0.1,
    )

    norm_context = form_context.lower() if form_context else ""
    explanations: List[FormFieldExplanationItem] = []

    for item in draft.explanations:
      basis = item.basis
      quote = item.quote_from_form

      # Basis verification: if stated_in_form_text, verify quote exists in form text
      if basis == "stated_in_form_text":
        if not quote or not norm_context or quote.lower() not in norm_context:
          # Quote was hallucinated or missing; downgrade to general knowledge
          basis = "general_knowledge"
          quote = None

      # Sanitize text
      plain_exp = _clean_text_for_security(item.plain_explanation)
      plain_exp_ta = _clean_text_for_security(item.plain_explanation_ta) if item.plain_explanation_ta else None
      where_find = _clean_text_for_security(item.where_to_find)
      where_find_ta = _clean_text_for_security(item.where_to_find_ta) if item.where_to_find_ta else None
      caution = _clean_text_for_security(item.caution) if item.caution else None

      explanations.append(
          FormFieldExplanationItem(
              field_name=item.field_name,
              field_name_ta=item.field_name_ta,
              plain_explanation=plain_exp,
              plain_explanation_ta=plain_exp_ta,
              where_to_find=where_find,
              where_to_find_ta=where_find_ta,
              basis=basis,
              quote_from_form=quote,
              page_number=item.page_number,
              caution=caution,
          )
      )

    disclaimer = (
        "Form field explanations are provided for civic guidance and informational purposes only. "
        "CivicLens does not collect, record, or transmit personal details, and does not submit forms "
        "on behalf of citizens. Always verify specific requirements on the official government portal."
    )

    return FormFieldExplainResponse(
        explanations=explanations,
        disclaimer=disclaimer,
    )


_form_field_service: Optional[FormFieldService] = None


def get_form_field_service() -> FormFieldService:
  global _form_field_service
  if _form_field_service is None:
    _form_field_service = FormFieldService()
  return _form_field_service


def set_form_field_service(service: Optional[FormFieldService]) -> None:
  global _form_field_service
  _form_field_service = service
