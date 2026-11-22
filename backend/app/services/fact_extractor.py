"""Shared deterministic fact extraction and normalisation for CivicLens.

Provides regex-based fact extractors for official dates (English and Tamil),
monetary amounts (INR, Rs, Lakh, Crore, Indian digit grouping), percentages,
age bounds, durations, and statutory codes.
Used across Module 2 (Policy Comparison) and Module 3 (Fact Verification).
"""

import re
import unicodedata
from typing import Any, Dict, List, Literal, Optional, Set, Tuple


# --- Keyword Categories for Civic & Policy Documents ---

KEYWORD_CATEGORIES: Dict[str, Set[str]] = {
    "eligibility": {
        "eligible", "eligibility", "ineligible", "criteria", "qualification",
        "income limit", "annual income", "family income", "bpl", "residence",
        "domicile", "citizen", "caste", "community", "age limit", "minimum age",
        "maximum age", "differently abled", "disability", "widow", "destitute",
        "தகுதி", "தகுதியற்ற", "வருமானம்", "ஆண்டு வருமானம்", "குடும்ப வருமானம்",
        "வறுமைக்கோட்டிற்கு கீழ்", "இருப்பிடம்", "குடிமகன்", "சாதி", "சமூகம்",
        "வயது வரம்பு", "குறைந்தபட்ச வயது", "அதிகபட்ச வயது", "மாற்றுத்திறனாளி",
    },
    "deadline": {
        "deadline", "last date", "closing date", "due date", "valid until",
        "validity", "validity period", "cutoff", "cut-off", "timeline", "expiry",
        "on or before", "within", "extended to", "effective from",
        "கடைசி தேதி", "இறுதி நாள்", "காலக்கெடு", "செல்லுபடியாகும் காலம்",
        "முடிவு தேதி", "நீட்டிக்கப்பட்டுள்ளது", "நடைமுறைக்கு வரும் நாள்",
    },
    "amount_benefit": {
        "rs", "rs.", "inr", "rupees", "amount", "grant", "subsidy", "pension",
        "allowance", "stipend", "scholarship", "financial assistance", "fee",
        "charges", "penalty", "fine", "compensation", "lakh", "crore",
        "ரூ", "ரூ.", "ரூபாய்", "தொகை", "மானியம்", "உதவித்தொகை", "ஓய்வூதியம்",
        "படிப்பக உதவித்தொகை", "நிதியுதவி", "கட்டணம்", "அபராதம்", "இலட்சம்", "கோடி",
    },
    "required_documents": {
        "required documents", "documents required", "mandatory", "certificate",
        "aadhaar", "ration card", "smart card", "pan card", "voter id",
        "patta", "chitta", "encumbrance certificate", "income certificate",
        "community certificate", "nativity certificate", "affidavit", "form",
        "தேவையான ஆவணங்கள்", "சான்றிதழ்", "குடும்ப அட்டை", "ரேஷன் அட்டை",
        "ஆதார்", "பட்டா", "சிட்டா", "வருமானச் சான்றிதழ்", "சாதிச் சான்றிதழ்",
        "இருப்பிடச் சான்றிதழ்", "படிவம்",
    },
    "conditions_rules": {
        "must", "shall", "mandatory", "compulsory", "strictly", "prohibited",
        "restriction", "disqualified", "forfeit", "exempted", "exception",
        "கட்டாயம்", "நிபந்தனை", "விதி", "தடைசெய்யப்பட்டது", "விலக்கு",
    },
}

ALL_HIGH_IMPORTANCE_KEYWORDS: Set[str] = set().union(*KEYWORD_CATEGORIES.values())


# --- Regex Extractors for Deterministic Facts ---

DATE_REGEXES = [
    # DD/MM/YYYY or DD-MM-YYYY
    re.compile(r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})\b"),
    # YYYY-MM-DD
    re.compile(r"\b(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})\b"),
    # 31st December 2025 or 15 Jan 2026
    re.compile(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})\b",
        re.IGNORECASE,
    ),
    # Tamil months: 15 சித்திரை 2025 or 15 ஜனவரி 2026
    re.compile(
        r"\b(\d{1,2})\s+(சித்திரை|வைகாசி|ஆனி|ஆடி|ஆவணி|புரட்டாசி|ஐப்பசி|கார்த்திகை|மார்கழி|தை|மாசி|பங்குனி|ஜனவரி|பிப்ரவரி|மார்ச்|ஏப்ரல்|மே|ஜூன்|ஜூலை|ஆகஸ்ட்|செப்டம்பர்|அக்டோபர்|நவம்பர்|டிசம்பர்)\s+(\d{4})\b"
    ),
]

AMOUNT_REGEXES = [
    # ₹ 2,50,000 or Rs. 50,000 or Rs 500
    re.compile(r"(?:₹|Rs\.?|INR|ரூ\.?|ரூபாய்)\s*([\d,]+(?:\.\d+)?(?:\s*(?:lakh|crore|இலட்சம்|கோடி))?)", re.IGNORECASE),
    # 2.5 lakh or 10 crore
    re.compile(r"\b(\d+(?:\.\d+)?\s*(?:lakh|crore|இலட்சம்|கோடி))\b", re.IGNORECASE),
]

PERCENTAGE_REGEXES = [
    re.compile(r"\b(\d+(?:\.\d+)?\s*(?:%|percent\b|சதவீதம்|விழுக்காடு))", re.IGNORECASE),
]

AGE_REGEXES = [
    re.compile(r"\b(?:age\s*(?:of|limit)?\s*)?(\d{1,2})\s*(?:years|years of age|வயது)\b", re.IGNORECASE),
    re.compile(r"\bவயது\s*(\d{1,2})\b"),
]

DURATION_REGEXES = [
    re.compile(r"\b(\d+\s*(?:days|weeks|months|years|நாட்கள்|வாரங்கள்|மாதங்கள்|ஆண்டுகள்))\b", re.IGNORECASE),
]

CODE_REGEXES = [
    re.compile(r"\b((?:Form|G\.O\.|G\.O\. Ms\.|No\.|Section|வடிவம்|படிவம்|அரசாணை எண்)\s*[\w\.\-/]+)\b", re.IGNORECASE),
]

TAMIL_NUMERAL_MAP = {
    "௦": "0", "௧": "1", "௨": "2", "௩": "3", "௪": "4",
    "௫": "5", "௬": "6", "௭": "7", "௮": "8", "௯": "9",
}

MONTH_NAME_MAP = {
    "january": 1, "jan": 1, "ஜனவரி": 1,
    "february": 2, "feb": 2, "பிப்ரவரி": 2,
    "march": 3, "mar": 3, "மார்ச்": 3,
    "april": 4, "apr": 4, "ஏப்ரல்": 4,
    "may": 5, "மே": 5,
    "june": 6, "jun": 6, "ஜூன்": 6,
    "july": 7, "jul": 7, "ஜூலை": 7,
    "august": 8, "aug": 8, "ஆகஸ்ட்": 8,
    "september": 9, "sep": 9, "செப்டம்பர்": 9,
    "october": 10, "oct": 10, "அக்டோபர்": 10,
    "november": 11, "nov": 11, "நவம்பர்": 11,
    "december": 12, "dec": 12, "டிசம்பர்": 12,
    # Tamil solar calendar months mapped to nominal 1-12 indices for deterministic comparisons
    "சித்திரை": 101, "வைகாசி": 102, "ஆனி": 103, "ஆடி": 104,
    "ஆவணி": 105, "புரட்டாசி": 106, "ஐப்பசி": 107, "கார்த்திகை": 108,
    "மார்கழி": 109, "தை": 110, "மாசி": 111, "பங்குனி": 112,
}


def normalize_tamil_digits(text: str) -> str:
  """Convert Tamil numerals (௦-௯) to standard Western digits (0-9)."""
  if not text:
    return ""
  norm = text
  for t_digit, w_digit in TAMIL_NUMERAL_MAP.items():
    norm = norm.replace(t_digit, w_digit)
  return norm


def extract_facts_from_text(text: str) -> Dict[str, List[str]]:
  """Extract exact dates, amounts, percentages, ages, durations, and statutory codes.

  Identical behavior preserved for both Policy Comparison and Fact Verification.
  """
  facts: Dict[str, List[str]] = {
      "date": [],
      "amount": [],
      "percentage": [],
      "age": [],
      "duration": [],
      "code": [],
  }
  if not text:
    return facts

  for r in DATE_REGEXES:
    for m in r.finditer(text):
      facts["date"].append(m.group(0).strip())

  for r in AMOUNT_REGEXES:
    for m in r.finditer(text):
      facts["amount"].append(m.group(0).strip())

  for r in PERCENTAGE_REGEXES:
    for m in r.finditer(text):
      facts["percentage"].append(m.group(0).strip())

  for r in AGE_REGEXES:
    for m in r.finditer(text):
      facts["age"].append(m.group(0).strip())

  for r in DURATION_REGEXES:
    for m in r.finditer(text):
      facts["duration"].append(m.group(0).strip())

  for r in CODE_REGEXES:
    for m in r.finditer(text):
      facts["code"].append(m.group(0).strip())

  # Deduplicate while preserving order
  for k in facts:
    facts[k] = list(dict.fromkeys(facts[k]))

  return facts


def has_high_importance_keywords(text: str) -> bool:
  """Check whether text contains civic criteria, eligibility, or deadline keywords."""
  if not text:
    return False
  lower = text.lower()
  return any(kw in lower for kw in ALL_HIGH_IMPORTANCE_KEYWORDS)


# --- Normalized Fact Value Parsers ---

def parse_normalized_amount(val_str: str) -> Optional[float]:
  """Parse currency strings into canonical numeric values.

  Handles:
    '2.5 lakh', '2.5 இலட்சம்' -> 250000.0
    '10 crore', '10 கோடி' -> 100000000.0
    'Rs. 2,50,000' -> 250000.0
    '₹500' -> 500.0
  """
  if not val_str:
    return None

  clean = normalize_tamil_digits(val_str).lower()
  # Remove currency symbols and word tokens
  clean = re.sub(r"[₹\$,]|rs\.?|inr|ரூ\.?|ரூபாய்", "", clean).strip()

  multiplier = 1.0
  if "crore" in clean or "கோடி" in clean:
    multiplier = 10000000.0
    clean = re.sub(r"crore|கோடி", "", clean).strip()
  elif "lakh" in clean or "இலட்சம்" in clean or "லட்சம்" in clean:
    multiplier = 100000.0
    clean = re.sub(r"lakh|இலட்சம்|லட்சம்", "", clean).strip()

  # Match remaining digits
  match = re.search(r"(\d+(?:\.\d+)?)", clean)
  if match:
    try:
      return float(match.group(1)) * multiplier
    except (ValueError, TypeError):
      return None
  return None


def parse_normalized_date(val_str: str) -> Optional[Tuple[int, int, int]]:
  """Parse date strings into a canonical (year, month, day) tuple.

  Handles:
    '31/12/2025', '31-12-2025'
    '2025-12-31'
    '31st December 2025', '15 Jan 2026'
    '15 சித்திரை 2025', '15 ஜனவரி 2026'
  """
  if not val_str:
    return None

  clean = normalize_tamil_digits(val_str).strip()

  # Format 1: YYYY-MM-DD or YYYY/MM/DD
  m_iso = re.match(r"^(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})$", clean)
  if m_iso:
    y, m, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
    return (y, m, d)

  # Format 2: DD/MM/YYYY or DD-MM-YYYY
  m_dmy = re.match(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})$", clean)
  if m_dmy:
    d, m, y = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
    if y < 100:
      y += 2000
    return (y, m, d)

  # Format 3: DD Month YYYY (English or Tamil)
  m_text = re.search(
      r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-zA-Z\u0B80-\u0BFF]+)\s+(\d{4})",
      clean,
      re.IGNORECASE,
  )
  if m_text:
    d = int(m_text.group(1))
    m_name = m_text.group(2).lower()
    y = int(m_text.group(3))
    m_idx = MONTH_NAME_MAP.get(m_name)
    if m_idx is not None:
      return (y, m_idx, d)

  return None


def parse_normalized_percentage(val_str: str) -> Optional[float]:
  """Parse percentage strings into numeric float.

  Handles: '10%', '10 percent', '10 சதவீதம்' -> 10.0
  """
  if not val_str:
    return None
  clean = normalize_tamil_digits(val_str).lower()
  match = re.search(r"(\d+(?:\.\d+)?)", clean)
  if match:
    try:
      return float(match.group(1))
    except (ValueError, TypeError):
      return None
  return None


def parse_normalized_age(val_str: str) -> Optional[int]:
  """Parse age strings into integer.

  Handles: '18 years', 'age 18', 'வயது 18' -> 18
  """
  if not val_str:
    return None
  clean = normalize_tamil_digits(val_str).lower()
  match = re.search(r"(\d{1,2})", clean)
  if match:
    try:
      return int(match.group(1))
    except (ValueError, TypeError):
      return None
  return None


def facts_match(
    claim_fact: str,
    fact_type: str,
    evidence_facts: List[str],
) -> Tuple[Literal["match", "mismatch", "absent"], Optional[str]]:
  """Check whether a single claim fact matches, mismatches, or is absent in evidence facts.

  Returns:
    ("match", evidence_value) if an evidence fact represents the same normalized value.
    ("mismatch", conflicting_evidence_value) if evidence contains facts of the same type with different values.
    ("absent", None) if no facts of that type exist in the evidence.
  """
  if not evidence_facts:
    return "absent", None

  if fact_type == "amount":
    c_norm = parse_normalized_amount(claim_fact)
    if c_norm is None:
      # Direct string comparison fallback
      for ev in evidence_facts:
        if claim_fact.strip().lower() == ev.strip().lower():
          return "match", ev
      return "mismatch" if evidence_facts else "absent", evidence_facts[0] if evidence_facts else None

    for ev in evidence_facts:
      ev_norm = parse_normalized_amount(ev)
      if ev_norm is not None and abs(c_norm - ev_norm) < 0.01:
        return "match", ev
    return "mismatch", evidence_facts[0]

  elif fact_type == "date":
    c_date = parse_normalized_date(claim_fact)
    if c_date is None:
      for ev in evidence_facts:
        if claim_fact.strip().lower() == ev.strip().lower():
          return "match", ev
      return "mismatch" if evidence_facts else "absent", evidence_facts[0] if evidence_facts else None

    for ev in evidence_facts:
      ev_date = parse_normalized_date(ev)
      if ev_date is not None and c_date == ev_date:
        return "match", ev
    return "mismatch", evidence_facts[0]

  elif fact_type == "percentage":
    c_pct = parse_normalized_percentage(claim_fact)
    if c_pct is None:
      for ev in evidence_facts:
        if claim_fact.strip().lower() == ev.strip().lower():
          return "match", ev
      return "mismatch" if evidence_facts else "absent", evidence_facts[0] if evidence_facts else None

    for ev in evidence_facts:
      ev_pct = parse_normalized_percentage(ev)
      if ev_pct is not None and abs(c_pct - ev_pct) < 0.01:
        return "match", ev
    return "mismatch", evidence_facts[0]

  elif fact_type == "age":
    c_age = parse_normalized_age(claim_fact)
    if c_age is None:
      for ev in evidence_facts:
        if claim_fact.strip().lower() == ev.strip().lower():
          return "match", ev
      return "mismatch" if evidence_facts else "absent", evidence_facts[0] if evidence_facts else None

    for ev in evidence_facts:
      ev_age = parse_normalized_age(ev)
      if ev_age is not None and c_age == ev_age:
        return "match", ev
    return "mismatch", evidence_facts[0]

  else:
    # Generic token matching for duration, code, etc.
    c_clean = normalize_tamil_digits(claim_fact).strip().lower()
    for ev in evidence_facts:
      ev_clean = normalize_tamil_digits(ev).strip().lower()
      if c_clean == ev_clean or c_clean in ev_clean or ev_clean in c_clean:
        return "match", ev
    return "mismatch", evidence_facts[0]
