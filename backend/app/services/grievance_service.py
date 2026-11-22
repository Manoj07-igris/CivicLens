"""Civic Grievance Assistant Engine (Module 5).

Handles:
1. PII Guard enforcement on citizen input (never stores contact info).
2. Deterministic pre-analysis (category classification, safety rules, baseline severity).
3. Budgeted Gemini structured analysis (with optional multimodal image).
4. Deterministic backend verification & assembly:
   - Category consistency checking & user override preference.
   - Severity floor enforcement (model cannot lower severity).
   - Draft integrity: removes ungrounded numbers/dates/measurements, strips URLs/contacts, neutralizes legal threats.
   - Verbatim user location insertion (never model-hallucinated).
   - Unconfirmed photo observations isolation.
   - Removal of personal data questions in missing details.
   - Curated portal channel matching from registry.
   - Static emergency notice if safety risk.
   - SHA-256 draft hash calculation.
5. Deterministic 'rules_only' basic draft fallback on Gemini failure/offline.
6. Caching by input hash (0 calls on repeat).
7. Review editing, hash-bound demo registration, and simulated tracking advancement.
"""

import datetime
import hashlib
import io
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from app.core.config import Settings, get_settings
from app.core.errors import DocumentProcessingError
from app.core.pii_guard import ensure_no_pii
from app.core.prompts import (
    get_grievance_analysis_prompt,
    wrap_untrusted_content,
)
from app.models.grievance import (
    DemoRecord,
    DemoTrackingEvent,
    Grievance,
    GrievanceAnalysisModel,
    GrievanceAnalyzeRequest,
    GrievanceDraft,
    GrievanceObservationItem,
    GrievancePatchRequest,
)
from app.models.portal import GrievanceChannelsResult
from app.services.gemini_service import get_gemini_service
from app.services.grievance_images import (
    get_grievance_image_path,
)
from app.services.grievance_rules import (
    CATEGORY_KEYWORDS,
    CATEGORY_TRANSLATION_KEYS,
    GrievanceCategory,
    classify_category_deterministic,
    combine_severity,
    determine_baseline_severity,
    evaluate_safety_rules,
)
from app.services.grievance_store import GrievanceNotFoundError, get_grievance_store
from app.services.language_service import detect_language
from app.services.portal_registry import get_portal_registry_service

logger = logging.getLogger("civiclens.grievance.engine")

# --- Tamil Numeral Normalization ---
TAMIL_DIGITS_MAP = {
    "௦": "0", "௧": "1", "௨": "2", "௩": "3", "௪": "4",
    "௫": "5", "௬": "6", "௭": "7", "௮": "8", "௯": "9",
}

# --- Threat and Legal Claim Denylist ---
THREAT_LEGAL_DENYLIST: Dict[str, List[str]] = {
    "en": [
        "sue you", "take legal action", "file a lawsuit", "drag to court",
        "drag you to court", "consumer court case", "punish the officials",
        "face legal consequences", "criminal complaint", "file an fir",
        "go on hunger strike", "demand suspension", "court order"
    ],
    "ta": [
        "வழக்கு போடுவேன்", "நீதிமன்றம் செல்வேன்", "சட்ட நடவடிக்கை",
        "தண்டிக்கப்பட வேண்டும்", "எப்.ஐ.ஆர்", "உண்ணாவிரதம்", "போராட்டம்",
        "சஸ்பெண்ட் செய்ய வேண்டும்"
    ],
}

# --- Personal Data Keywords to Filter From Missing Details ---
PERSONAL_DATA_KEYWORDS: List[str] = [
    "phone", "mobile", "contact number", "email", "aadhaar", "pan card",
    "your name", "name of person", "address of person", "bank account",
    "identity card", "voter id", "passport", "தொலைபேசி", "கைபேசி",
    "மின்னஞ்சல்", "ஆதார்", "பெயர்", "முகவரி"
]

# In-memory query cache for grievance analyses
_ANALYSIS_CACHE: Dict[str, Grievance] = {}


def normalize_digits(text: str) -> str:
  """Convert Tamil numerals (௦-௯) to standard ASCII digits."""
  for t_char, d_char in TAMIL_DIGITS_MAP.items():
    text = text.replace(t_char, d_char)
  return text


def extract_numbers_from_text(text: str) -> Set[str]:
  """Extract all standalone or decimal numbers from text after digit normalization."""
  normalized = normalize_digits(text)
  tokens = re.findall(r"\b\d+(?:[\.,]\d+)?\b", normalized)
  clean_tokens = set()
  for t in tokens:
    # Normalize '5.0' vs '5'
    try:
      val = float(t.replace(",", "."))
      clean_tokens.add(str(int(val)) if val.is_integer() else str(val))
    except ValueError:
      clean_tokens.add(t)
  return clean_tokens


def strip_urls_and_contacts(text: str) -> Tuple[str, int]:
  """Strip URLs, email addresses, and phone numbers, returning (sanitized, count)."""
  count = 0

  # URLs
  url_pattern = r"https?://[^\s]+|www\.[^\s]+"
  matches = re.findall(url_pattern, text)
  if matches:
    count += len(matches)
    text = re.sub(url_pattern, "[link removed]", text)

  # Emails
  email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
  matches = re.findall(email_pattern, text)
  if matches:
    count += len(matches)
    text = re.sub(email_pattern, "[contact removed]", text)

  # Indian 10-digit mobile numbers or phone numbers
  phone_pattern = r"\b(?:\+91[- ]?)?[6-9]\d{9}\b|\b0\d{2,4}[- ]?\d{6,8}\b"
  matches = re.findall(phone_pattern, text)
  if matches:
    count += len(matches)
    text = re.sub(phone_pattern, "[contact removed]", text)

  return text, count


def sanitize_threats_and_legal_claims(
    body: str, language: str = "en"
) -> Tuple[str, int]:
  """Replace aggressive threats or legal-claim sentences with a formal civic request."""
  neutral_replacement = (
      "I kindly request the concerned department to inspect this civic issue "
      "and take appropriate remedial action at the earliest."
      if language == "en"
      else "சம்பந்தப்பட்ட துறை அதிகாரிகள் உடனடியாக ஆய்வு செய்து தக்க நடவடிக்கை எடுக்குமாறு பணிவுடன் கேட்டுக்கொள்கிறேன்."
  )

  sentences = re.split(r"(?<=[.!?\n])\s+", body)
  neutralized_count = 0
  clean_sentences = []

  denylist = THREAT_LEGAL_DENYLIST.get("en", []) + THREAT_LEGAL_DENYLIST.get("ta", [])

  for sent in sentences:
    sent_lower = sent.lower()
    has_threat = any(term in sent_lower for term in denylist)
    if has_threat:
      neutralized_count += 1
      clean_sentences.append(neutral_replacement)
    else:
      clean_sentences.append(sent)

  return " ".join(clean_sentences), neutralized_count


def compute_draft_hash(
    final_text: str, category: str, severity: str, location_text: str
) -> str:
  """Compute SHA-256 hash of normalized final complaint text and core metadata."""
  norm = f"{final_text.strip()}|{category.strip().lower()}|{severity.strip().lower()}|{location_text.strip().lower()}"
  return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def assemble_final_text(
    subject_line: str,
    body: str,
    location_line: str,
    observations: List[GrievanceObservationItem],
    language: str = "en",
) -> str:
  """Assemble complete complaint text including confirmed observations."""
  parts = [f"Subject: {subject_line.strip()}", body.strip()]

  if location_line.strip():
    parts.append(location_line.strip())

  confirmed_obs = [obs.text.strip() for obs in observations if obs.confirmed and obs.text.strip()]
  if confirmed_obs:
    header = (
        "Photo observations confirmed by the complainant:"
        if language == "en"
        else "புகார்தாரரால் உறுதிசெய்யப்பட்ட புகைப்பட விவரங்கள்:"
    )
    obs_lines = [header] + [f"- {item}" for item in confirmed_obs]
    parts.append("\n".join(obs_lines))

  return "\n\n".join(parts)


def build_basic_draft_deterministic(
    category: str,
    description: str,
    location_text: str = "",
    duration_text: str = "",
    language: str = "en",
) -> Tuple[str, str, str]:
  """Construct a deterministic basic draft directly from user words without Gemini."""
  cat_label = category.replace("_", " ").title()

  if language == "ta":
    loc_part = f" ({location_text})" if location_text else ""
    subject = f"{cat_label} தொடர்பான குறைதீர்ப்பு மனு{loc_part}"
    body_lines = [description.strip()]
    if duration_text:
      body_lines.append(f"கால அளவு: {duration_text.strip()}")
    body_lines.append("இப்பிரச்சனையை உடனடியாக ஆய்வு செய்து நடவடிக்கை எடுக்குமாறு கேட்டுக்கொள்கிறேன்.")
    body = "\n\n".join(body_lines)
    loc_line = f"இடம்: {location_text.strip()}" if location_text else ""
  else:
    loc_part = f" at {location_text}" if location_text else ""
    subject = f"Complaint regarding {cat_label}{loc_part}"
    body_lines = [description.strip()]
    if duration_text:
      body_lines.append(f"Duration: {duration_text.strip()}")
    body_lines.append(
        "I kindly request the concerned authority to inspect this location and resolve the issue."
    )
    body = "\n\n".join(body_lines)
    loc_line = f"Location: {location_text.strip()}" if location_text else ""

  return subject, body, loc_line


class GrievanceService:
  """Central service for civic grievance analysis, drafting, and demo tracking."""

  def __init__(self, settings: Optional[Settings] = None):
    self._settings = settings or get_settings()
    self._store = get_grievance_store()
    self._portal_service = get_portal_registry_service()
    self._gemini = get_gemini_service()

  def _build_emergency_notice(self, language: str = "en") -> str:
    contact_text = self._settings.emergency_contact_text
    if language == "ta":
      return (
          f"உடனடி ஆபத்து அல்லது அவசரநிலை இருப்பின், உடனடியாக உள்ளூர் அவசர உதவி எண்ணை ({contact_text}) அழைக்கவும். "
          "CivicLens அவசர உதவி சேவை அல்ல."
      )
    return (
        f"If anyone is in immediate danger, contact local emergency services ({contact_text}) first. "
        "CivicLens is not an emergency service."
    )

  def _compute_cache_key(
      self,
      description: str,
      location_text: str,
      duration_text: str,
      language: str,
      category_hint: Optional[str],
      image_bytes: Optional[bytes] = None,
  ) -> str:
    image_hash = hashlib.sha256(image_bytes).hexdigest()[:16] if image_bytes else "no_image"
    norm = f"{description.strip().lower()}|{location_text.strip().lower()}|{duration_text.strip().lower()}|{language}|{category_hint or ''}|{image_hash}|v1"
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()

  async def analyze_grievance(
      self,
      req: GrievanceAnalyzeRequest,
      grievance_id: Optional[str] = None,
      owner_id: Optional[str] = None,
  ) -> Grievance:
    """Run full grievance analysis pipeline."""
    # 1. PII Guardrail Check
    ensure_no_pii(req.description, field_name="description")
    if req.location_text:
      ensure_no_pii(req.location_text, field_name="location_text")
    if req.duration_text:
      ensure_no_pii(req.duration_text, field_name="duration_text")

    gid = grievance_id or str(uuid.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    lang = req.language_of_draft

    # Check for attached image
    image_bytes: Optional[bytes] = None
    has_image = bool(req.image_id)
    if has_image:
      if not req.image_consent:
        raise DocumentProcessingError(
            "Explicit citizen consent is required to analyze attached photos. "
            "Please check the consent box before analyzing."
        )
      img_path = get_grievance_image_path(req.image_id, self._settings)
      if img_path and img_path.exists():
        image_bytes = img_path.read_bytes()

    # Check cache
    cache_key = self._compute_cache_key(
        description=req.description,
        location_text=req.location_text or "",
        duration_text=req.duration_text or "",
        language=lang,
        category_hint=req.category_hint,
        image_bytes=image_bytes,
    )
    if cache_key in _ANALYSIS_CACHE:
      cached = _ANALYSIS_CACHE[cache_key]
      # Return clean copy with current ID and timestamps
      cached_copy = cached.model_copy(
          update={
              "id": gid,
              "created_at": now_iso,
              "updated_at": now_iso,
              "image_id": req.image_id,
              "has_image": has_image,
          }
      )
      self._store.save(cached_copy, owner_id=owner_id)
      logger.info("Serving grievance %s from analysis cache (0 Gemini calls)", gid)
      return cached_copy

    # 2. Deterministic Pre-Analysis (No Gemini)
    cat_rule, cat_scores = classify_category_deterministic(req.description, req.location_text or "")
    safety_risk_rule, matched_safety_rules = evaluate_safety_rules(req.description, req.location_text or "")
    baseline_severity = determine_baseline_severity(
        safety_risk=safety_risk_rule,
        description=req.description,
        duration_text=req.duration_text or "",
        location_text=req.location_text or "",
    )

    # 3. Model Analysis or Rules-Only Fallback
    warnings: List[str] = []
    analysis_mode = "ai"
    analysis_inputs = "text_and_photo" if image_bytes else "text_only"
    model_analysis: Optional[GrievanceAnalysisModel] = None

    if not self._settings.is_gemini_configured:
      analysis_mode = "rules_only"
      warnings.append("AI assistant not configured. Generated basic draft deterministically.")
    else:
      try:
        # Wrap untrusted citizen input in explicit boundary tags
        untrusted_text = (
            f"Citizen Problem Description:\n{req.description}\n\n"
            f"Location / Landmark:\n{req.location_text or 'Not specified'}\n\n"
            f"Problem Duration:\n{req.duration_text or 'Not specified'}\n\n"
            f"Target Draft Language: {lang}\n"
        )
        wrapped_prompt = wrap_untrusted_content(untrusted_text, label="untrusted_citizen_data")
        user_prompt = (
            f"{wrapped_prompt}\n\nPlease analyze this civic problem and structure a formal complaint "
            f"in {lang.upper()} strictly following the directives."
        )

        system_instruction = get_grievance_analysis_prompt(reply_language=lang)

        # Multimodal image parts
        images_param = None
        if image_bytes:
          images_param = [{"data": image_bytes, "mime_type": "image/jpeg"}]

        model_analysis = await self._gemini.generate_structured(
            prompt_or_messages=user_prompt,
            response_model=GrievanceAnalysisModel,
            system_instruction=system_instruction,
            images=images_param,
        )
      except Exception as exc:
        logger.warning("Gemini grievance analysis failed (%s); falling back to rules-only basic draft", exc)
        analysis_mode = "rules_only"
        warnings.append("AI analysis was unavailable or encountered an error. A basic draft was created from your text.")

    # 4. Backend Verification and Assembly
    # 4a. Category Decision
    final_category: str
    category_source: str
    category_confidence: str = "consistent"

    if req.category_hint:
      final_category = req.category_hint.lower().strip()
      category_source = "user"
      category_confidence = "consistent"
    elif model_analysis:
      model_cat = model_analysis.category.lower().strip()
      # Validate model category is one of valid enum values
      valid_enum_values = [c.value for c in GrievanceCategory]
      if model_cat not in valid_enum_values:
        model_cat = cat_rule.value

      if model_cat == cat_rule.value:
        final_category = model_cat
        category_source = "ai"
        category_confidence = "consistent"
      else:
        # Disagreement between model and keyword classifier
        final_category = model_cat
        category_source = "ai"
        category_confidence = "needs_confirmation"
        warnings.append("Category classified by AI differs from keyword rules; please confirm.")
    else:
      final_category = cat_rule.value
      category_source = "rules"
      category_confidence = "consistent" if cat_scores.get(cat_rule.value, 0.0) >= 1.5 else "needs_confirmation"

    # 4b. Severity & Safety Floor
    model_safety = model_analysis.safety_risk if model_analysis else False
    final_safety_risk = safety_risk_rule or model_safety  # Model can only raise, never lower
    if model_analysis and model_analysis.safety_risk and not safety_risk_rule:
      matched_safety_rules.append("ai_identified_safety_risk")

    model_severity_suggestion = model_analysis.severity_suggestion if model_analysis else None
    final_severity = combine_severity(baseline_severity, model_severity_suggestion)
    severity_source = "rules" if (final_severity == baseline_severity and not model_severity_suggestion) else "ai"

    emergency_notice = self._build_emergency_notice(language=lang) if final_safety_risk else None

    # 4c. Draft Assembly and Fact/Integrity Verification
    subject_line: str
    body_text: str
    location_line: str
    photo_observations: List[GrievanceObservationItem] = []

    if model_analysis and analysis_mode == "ai":
      subject_line = model_analysis.subject_line.strip()
      raw_body = model_analysis.body.strip()

      # Extract numbers from user input vs draft body
      user_input_corpus = f"{req.description} {req.location_text or ''} {req.duration_text or ''}"
      allowed_numbers = extract_numbers_from_text(user_input_corpus)

      # Sentence-by-sentence number verification
      body_sentences = re.split(r"(?<=[.!?\n])\s+", raw_body)
      clean_sentences = []
      removed_details_count = 0

      for sent in body_sentences:
        sent_numbers = extract_numbers_from_text(sent)
        unallowed = sent_numbers - allowed_numbers
        if unallowed:
          # Contains invented numbers/quantities
          removed_details_count += 1
          # Omit ungrounded sentence or replace with generic safe phrase
          continue
        clean_sentences.append(sent)

      if removed_details_count > 0:
        warnings.append("Details not supplied by you were removed to ensure factual accuracy.")

      if not clean_sentences:
        # Fallback to user description if all sentences were flagged
        body_text = req.description.strip()
      else:
        body_text = " ".join(clean_sentences)

      # Strip URLs and contact details
      body_text, urls_stripped = strip_urls_and_contacts(body_text)
      subject_line, _ = strip_urls_and_contacts(subject_line)
      if urls_stripped > 0:
        warnings.append("Web links and contact numbers were removed from the draft.")

      # Neutralize threats and legal citations
      body_text, threats_neutralized = sanitize_threats_and_legal_claims(body_text, language=lang)
      if threats_neutralized > 0:
        warnings.append("Aggressive or legal-claim phrasing was adjusted to maintain a formal, constructive tone.")

      # Location line is inserted verbatim from citizen input
      if req.location_text and req.location_text.strip():
        loc_prefix = "Location:" if lang == "en" else "இடம்:"
        location_line = f"{loc_prefix} {req.location_text.strip()}"
      else:
        location_line = ""

      # Process photo observations
      if model_analysis.image_relevant and model_analysis.observations:
        obs_idx = 1
        for obs_text in model_analysis.observations[:5]:
          obs_clean, _ = strip_urls_and_contacts(obs_text.strip())
          # Ensure no personal claims about people
          if any(k in obs_clean.lower() for k in ["person", "people", "man", "woman", "child", "driver"]):
            continue
          if obs_clean:
            photo_observations.append(
                GrievanceObservationItem(
                    item_id=f"obs_{obs_idx}",
                    text=obs_clean,
                    confirmed=False,
                )
            )
            obs_idx += 1
      elif not model_analysis.image_relevant and image_bytes:
        warnings.append("The uploaded image does not appear to show a recognized civic issue.")

      # Missing details: filter out any that ask for personal identifiers
      clean_missing = []
      for q in (model_analysis.missing_details or [])[:4]:
        q_lower = q.lower()
        if not any(k in q_lower for k in PERSONAL_DATA_KEYWORDS):
          clean_missing.append(q.strip())
      missing_details = clean_missing

    else:
      # Deterministic Basic Draft Fallback
      subject_line, body_text, location_line = build_basic_draft_deterministic(
          category=final_category,
          description=req.description,
          location_text=req.location_text or "",
          duration_text=req.duration_text or "",
          language=lang,
      )
      missing_details = [
          "Exact landmark or street junction" if lang == "en" else "சரியான அடையாள இடம் அல்லது தெரு சந்திப்பு",
          "Approximate duration this problem has persisted" if lang == "en" else "இப்பிரச்சனை எத்தனை நாட்களாக நீடிக்கிறது",
      ]

    # Assemble final text and draft hash
    final_text = assemble_final_text(
        subject_line=subject_line,
        body=body_text,
        location_line=location_line,
        observations=photo_observations,
        language=lang,
    )
    draft_hash = compute_draft_hash(
        final_text=final_text,
        category=final_category,
        severity=final_severity,
        location_text=req.location_text or "",
    )

    draft_model = GrievanceDraft(
        subject_line=subject_line,
        body=body_text,
        location_line=location_line,
        observations=photo_observations,
        final_text=final_text,
        draft_hash=draft_hash,
    )

    # 4d. Match Reporting Channels from Curated Portal Registry
    channel_matches = self._portal_service.match_channels(
        category=final_category,
        location_text=req.location_text or "",
        limit=3,
    )

    # Construct complete Grievance record
    grievance = Grievance(
        id=gid,
        created_at=now_iso,
        updated_at=now_iso,
        state="draft",
        description=req.description,
        location_text=req.location_text or "",
        duration_text=req.duration_text or "",
        language=lang,
        category=final_category,
        category_source=category_source,
        category_confidence=category_confidence,
        category_scores=cat_scores,
        severity=final_severity,
        severity_source=severity_source,
        safety_risk=final_safety_risk,
        matched_safety_rules=matched_safety_rules,
        emergency_notice=emergency_notice,
        draft=draft_model,
        missing_details=missing_details,
        channels=channel_matches,
        analysis_inputs=analysis_inputs,
        analysis_mode=analysis_mode,
        warnings=warnings,
        draft_hash=draft_hash,
        has_image=has_image,
        image_id=req.image_id,
        demo=None,
    )

    # Cache and save
    _ANALYSIS_CACHE[cache_key] = grievance
    self._store.save(grievance, owner_id=owner_id)
    from app.services.activity_service import get_activity_service
    get_activity_service().record_activity("grievance.drafted", "grievance", gid, owner_id=owner_id)
    return grievance

  def update_grievance_draft(
      self,
      grievance_id: str,
      patch: GrievancePatchRequest,
      owner_id: Optional[str] = None,
  ) -> Grievance:
    """Update draft fields during citizen review.

    Allows updating category, severity, subject, body, location, and photo observation confirmations.
    Re-runs deterministic PII, link, and threat checks, and recomputes the draft hash.
    Rejects edits once registered.
    """
    grievance = self._store.get(grievance_id, owner_id=owner_id)
    if grievance.state == "demo_registered":
      raise DocumentProcessingError(
          "Cannot edit a demo grievance that has already been registered. "
          "Please start a new complaint if you wish to draft another version."
      )

    lang = grievance.language
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Category update
    if patch.category:
      clean_cat = patch.category.lower().strip()
      valid_enum_values = [c.value for c in GrievanceCategory]
      if clean_cat not in valid_enum_values:
        raise DocumentProcessingError(f"Invalid grievance category: '{patch.category}'")
      grievance.category = clean_cat
      grievance.category_source = "user"
      grievance.category_confidence = "consistent"
      # Refresh channel matches for new category
      grievance.channels = self._portal_service.match_channels(
          category=clean_cat,
          location_text=grievance.location_text,
          limit=3,
      )

    # Severity update
    if patch.severity:
      grievance.severity = patch.severity
      grievance.severity_source = "user"

    # Location update
    if patch.location_text is not None:
      ensure_no_pii(patch.location_text, field_name="location_text")
      grievance.location_text = patch.location_text.strip()
      if grievance.location_text:
        loc_prefix = "Location:" if lang == "en" else "இடம்:"
        grievance.draft.location_line = f"{loc_prefix} {grievance.location_text}"
      else:
        grievance.draft.location_line = ""

    # Subject line update
    if patch.subject_line is not None:
      ensure_no_pii(patch.subject_line, field_name="subject_line")
      clean_sub, _ = strip_urls_and_contacts(patch.subject_line.strip())
      grievance.draft.subject_line = clean_sub

    # Body update
    if patch.body is not None:
      ensure_no_pii(patch.body, field_name="body")
      clean_body, _ = strip_urls_and_contacts(patch.body.strip())
      clean_body, _ = sanitize_threats_and_legal_claims(clean_body, language=lang)
      grievance.draft.body = clean_body

    # Observation confirmation toggles
    if patch.confirmed_observation_ids is not None:
      confirmed_set = set(patch.confirmed_observation_ids)
      for obs in grievance.draft.observations:
        obs.confirmed = obs.item_id in confirmed_set

    # Reassemble final text and recompute draft hash
    grievance.draft.final_text = assemble_final_text(
        subject_line=grievance.draft.subject_line,
        body=grievance.draft.body,
        location_line=grievance.draft.location_line,
        observations=grievance.draft.observations,
        language=lang,
    )
    grievance.draft_hash = compute_draft_hash(
        final_text=grievance.draft.final_text,
        category=grievance.category,
        severity=grievance.severity,
        location_text=grievance.location_text,
    )
    grievance.draft.draft_hash = grievance.draft_hash
    grievance.updated_at = now_iso

    self._store.save(grievance, owner_id=owner_id)
    return grievance

  def register_demo_record(
      self,
      grievance_id: str,
      approved: bool,
      approved_hash: str,
      method: str = "ui",
      owner_id: Optional[str] = None,
  ) -> Grievance:
    """Register demo complaint record bound to citizen explicit approval and draft hash."""
    grievance = self._store.get(grievance_id, owner_id=owner_id)

    # Idempotent return if already registered with matching hash
    if grievance.state == "demo_registered" and grievance.demo:
      if grievance.draft_hash == approved_hash:
        return grievance

    if not approved:
      raise DocumentProcessingError(
          "Explicit citizen approval is required to create a demo complaint record."
      )

    if grievance.draft_hash != approved_hash.strip():
      raise DocumentProcessingError(
          "The reviewed complaint draft was modified since your approval. "
          "Please review the updated text and confirm your approval."
      )

    if not grievance.draft.final_text or not grievance.category:
      raise DocumentProcessingError("Cannot register an incomplete grievance draft.")

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    prefix = self._settings.demo_id_prefix
    # Generate non-sequential random base32 demo ID
    random_suffix = uuid.uuid4().hex[:6].upper()
    demo_id = f"{prefix}-{random_suffix}"

    initial_event = DemoTrackingEvent(
        event_id=f"evt_{uuid.uuid4().hex[:8]}",
        status="registered",
        timestamp=now_iso,
        simulated=True,
        note="Demo complaint record created inside CivicLens (simulated).",
    )

    approval_record = {
        "timestamp": now_iso,
        "hash": approved_hash,
        "method": method,
        "client": "civiclens_web",
    }

    demo_record = DemoRecord(
        demo_id=demo_id,
        registered_at=now_iso,
        status="registered",
        is_demo=True,
        notice="Demo record only. Not sent to any government authority.",
        events=[initial_event],
        approval=approval_record,
    )

    grievance.state = "demo_registered"
    grievance.demo = demo_record
    grievance.updated_at = now_iso

    self._store.save(grievance, owner_id=owner_id)
    from app.services.activity_service import get_activity_service
    get_activity_service().record_activity("grievance.registered", "grievance", grievance_id, owner_id=owner_id)
    logger.info("Registered demo complaint record %s for grievance %s", demo_id, grievance_id)
    return grievance

  def advance_demo_status(
      self,
      grievance_id: str,
      note: Optional[str] = None,
      owner_id: Optional[str] = None,
  ) -> Grievance:
    """Advance demo status forward-only: registered -> under_review -> in_progress -> resolved."""
    grievance = self._store.get(grievance_id, owner_id=owner_id)
    if grievance.state != "demo_registered" or not grievance.demo:
      raise DocumentProcessingError("Cannot advance status on an unregistered draft grievance.")

    current_status = grievance.demo.status
    transitions = {
        "registered": ("under_review", "Departmental review initiated (simulated)"),
        "under_review": ("in_progress", "Field inspection assigned to local unit (simulated)"),
        "in_progress": ("resolved", "Grievance marked as addressed and resolved (simulated)"),
    }

    if current_status not in transitions:
      raise DocumentProcessingError(f"Complaint demo status '{current_status}' is already at final state.")

    next_status, default_note = transitions[current_status]
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    clean_note = default_note
    if note and note.strip():
      ensure_no_pii(note.strip(), field_name="note")
      clean_note = note.strip()

    event = DemoTrackingEvent(
        event_id=f"evt_{uuid.uuid4().hex[:8]}",
        status=next_status,
        timestamp=now_iso,
        simulated=True,
        note=clean_note,
    )

    grievance.demo.status = next_status
    grievance.demo.events.append(event)
    grievance.updated_at = now_iso

    self._store.save(grievance, owner_id=owner_id)
    from app.services.activity_service import get_activity_service
    get_activity_service().record_activity("grievance.status_updated", "grievance", grievance_id, owner_id=owner_id)
    logger.info("Advanced demo status for %s from %s to %s", grievance_id, current_status, next_status)
    return grievance


_grievance_service: Optional[GrievanceService] = None


def get_grievance_service() -> GrievanceService:
  global _grievance_service
  if _grievance_service is None:
    _grievance_service = GrievanceService()
  return _grievance_service


def set_grievance_service(service: Optional[GrievanceService]) -> None:
  global _grievance_service
  _grievance_service = service
