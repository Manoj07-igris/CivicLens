"""Deterministic Civic Grievance Classification, Safety Rules, and Severity Heuristics.

Provides:
1. GrievanceCategory enum and bilingual label keys.
2. Deterministic keyword-based category classifier (English & Tamil).
3. Deterministic safety risk evaluation (identifies physical hazards, never echoes user text).
4. Deterministic baseline severity estimation with rule-enforced floors.
"""

from enum import Enum
import re
from typing import Any, Dict, List, Optional, Set, Tuple


class GrievanceCategory(str, Enum):
  """Fixed civic grievance category classification."""
  ROADS = "roads"
  WATER_SUPPLY = "water_supply"
  STREETLIGHTS = "streetlights"
  WASTE_MANAGEMENT = "waste_management"
  DRAINAGE_SEWAGE = "drainage_sewage"
  PUBLIC_INFRASTRUCTURE_DAMAGE = "public_infrastructure_damage"
  OTHER = "other"


CATEGORY_TRANSLATION_KEYS: Dict[str, str] = {
    GrievanceCategory.ROADS.value: "grievance.categories.roads",
    GrievanceCategory.WATER_SUPPLY.value: "grievance.categories.waterSupply",
    GrievanceCategory.STREETLIGHTS.value: "grievance.categories.streetlights",
    GrievanceCategory.WASTE_MANAGEMENT.value: "grievance.categories.wasteManagement",
    GrievanceCategory.DRAINAGE_SEWAGE.value: "grievance.categories.drainageSewage",
    GrievanceCategory.PUBLIC_INFRASTRUCTURE_DAMAGE.value: "grievance.categories.infrastructure",
    GrievanceCategory.OTHER.value: "grievance.categories.other",
}

SEVERITY_LEVELS: Dict[str, int] = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "urgent": 4,
}

# --- Deterministic Category Keywords (English & Tamil) ---
# Each category contains prioritized keywords, root words, and multi-word phrases.
CATEGORY_KEYWORDS: Dict[GrievanceCategory, Dict[str, List[str]]] = {
    GrievanceCategory.ROADS: {
        "en": [
            "pothole", "potholed", "potholes", "damaged road", "broken road",
            "crater", "craters", "road crack", "asphalt", "tar road", "speed breaker",
            "road cave", "uneven road", "surface broken", "dug up road", "road repair",
            "pavement broken", "gravel", "road damaged"
        ],
        "ta": [
            "சாலை", "குழி", "தார்ச்சாலை", "ரோடு", "பள்ளம்", "சாலை சேதம்",
            "குண்டும் குழியுமாக", "தார்", "சாலை பள்ளம்", "சாலை உடைந்து",
            "சாலை பழுது", "போக்குவரத்து பாதிப்பு"
        ],
    },
    GrievanceCategory.WATER_SUPPLY: {
        "en": [
            "no water", "water supply", "drinking water", "pipe burst", "pipe leakage",
            "water leak", "low pressure", "contaminated water", "dirty water",
            "water shortage", "tap water", "pipeline broken", "water not coming",
            "borewell", "water tanker", "saline water"
        ],
        "ta": [
            "குடிநீர்", "தண்ணீர்", "குழாய் உடைப்பு", "நீர் விநியோகம்",
            "தண்ணீர் வரவில்லை", "குழாய் கசிவு", "நீர் பற்றாக்குறை", "குடிநீர் தட்டுப்பாடு",
            "அழுக்கு நீர்", "குழாய் உடைந்து", "நீர் குழாய்", "குடிநீர் வசதி"
        ],
    },
    GrievanceCategory.STREETLIGHTS: {
        "en": [
            "street light", "streetlight", "street lights", "streetlights",
            "lamp not working", "dark street", "broken pole", "light pole",
            "flickering light", "no light", "bulb fused", "darkness",
            "lamp post", "sodium lamp", "led street light", "tube light"
        ],
        "ta": [
            "தெருவிளக்கு", "விளக்கு எரியவில்லை", "மின்விளக்கு", "இருட்டாக",
            "விளக்கு கம்பம்", "மின் கம்பம்", "தெரு விளக்கு", "மின்விளக்கு பழுது",
            "இருள்", "விளக்குகள் எரியவில்லை"
        ],
    },
    GrievanceCategory.WASTE_MANAGEMENT: {
        "en": [
            "garbage", "trash", "rubbish", "dumping", "waste", "litter",
            "overflowing bin", "garbage bin", "rotten waste", "debris", "garbage pile",
            "trash not collected", "waste collection", "solid waste", "smell of garbage"
        ],
        "ta": [
            "குப்பை", "குப்பைத்தொட்டி", "கழிவு", "துர்நாற்றம்", "குப்பை அள்ளவில்லை",
            "குப்பைக் கூளம்", "திடக்கழிவு", "குப்பை தேக்கம்", "குப்பை கொட்டப்பட்டுள்ளது"
        ],
    },
    GrievanceCategory.DRAINAGE_SEWAGE: {
        "en": [
            "drain blocked", "drainage", "sewage", "sewage overflow", "stagnant water",
            "gutter", "clogged drain", "wastewater", "foul smell", "manhole overflowing",
            "drainage leakage", "sewer", "storm water drain", "blocked gutter", "open drain"
        ],
        "ta": [
            "கழிவுநீர்", "வடிகால்", "சாக்கடை", "கழிவுநீர் தேக்கம்", "அடைப்பு",
            "வடிகால் அடைப்பு", "சாக்கடை நீர்", "சாக்கடை அடைப்பு", "துர்நாற்றம் வீசுகிறது",
            "கழிவுநீர் கால்வாய்"
        ],
    },
    GrievanceCategory.PUBLIC_INFRASTRUCTURE_DAMAGE: {
        "en": [
            "damaged bench", "bridge", "public toilet", "bus shelter", "bus stop",
            "footpath", "compound wall", "railing", "park fence", "pavement",
            "broken divider", "public property", "community hall", "play area",
            "handrail", "culvert"
        ],
        "ta": [
            "பாலம்", "பொதுக் கழிப்பிடம்", "பேருந்து நிறுத்தம்", "நடைபாதை",
            "சுவர்", "கைப்பிடி சுவர்", "பூங்கா", "பேருந்து நிழற்குடை",
            "பொது கழிப்பறை", "தடுப்பு சுவர்", "பொது கட்டிடம்"
        ],
    },
    GrievanceCategory.OTHER: {
        "en": ["civic", "encroachment", "nuisance", "stray dogs", "noise", "general issue"],
        "ta": ["பொதுப் பிரச்சனை", "ஆக்கிரமிப்பு", "தொல்லை", "பொது புகார்"],
    },
}

# --- Deterministic SAFETY Risk Rules (EN & TA) ---
# High-consequence life/safety hazard detectors.
SAFETY_RULES: Dict[str, Dict[str, List[str]]] = {
    "open_manhole": {
        "en": [
            "open manhole", "uncovered manhole", "missing manhole lid",
            "open drain pit", "open chamber", "missing drainage cover", "manhole open"
        ],
        "ta": [
            "திறந்த மேன்ஹோல்", "மூடப்படாத சாக்கடை", "மூடி இல்லாத மேன்ஹோல்",
            "சாக்கடை குழி திறந்து", "திறந்த பாதாள சாக்கடை"
        ],
    },
    "exposed_live_wire": {
        "en": [
            "exposed live wire", "fallen live wire", "snapped wire", "electric shock",
            "sparking wire", "loose wire", "wire hanging down", "hanging electric cable",
            "power line fallen", "electrocution risk"
        ],
        "ta": [
            "மின்கம்பி அறுந்து", "மின் கசிவு", "மின்சார கம்பி", "ஸ்பார்க்",
            "மின்கம்பி தொங்குகிறது", "மின் அதிர்ச்சி", "அறுந்த மின்கம்பி"
        ],
    },
    "gas_leak": {
        "en": [
            "gas leak", "lpg cylinder leak", "gas smell", "gas pipeline leak",
            "cooking gas leaking", "smell of gas"
        ],
        "ta": [
            "எரிவாயு கசிவு", "கேஸ் கசிவு", "எரிவாயு வாசனை", "சிலிண்டர் கசிவு"
        ],
    },
    "collapsing_structure": {
        "en": [
            "collapsed structure", "about to collapse", "falling roof", "cracked pillar",
            "dilapidated wall crumbling", "building collapse risk", "bridge cracking",
            "structure unstable", "wall falling", "bridge ready to fall"
        ],
        "ta": [
            "இடியும் நிலையில்", "சுவர் இடிந்து", "கட்டிடம் இடியும்", "பாலம் விரிசல்",
            "மேற்கூரை இடிந்து", "இடிந்து விழும் ஆபத்து"
        ],
    },
    "deep_pit_hazard": {
        "en": [
            "deep pit on road", "sinkhole", "deep trench", "cave in",
            "dangerous crater at night", "unbarricaded trench", "huge pit without warning"
        ],
        "ta": [
            "ஆபத்தான பள்ளம்", "பள்ளம் விழுந்து", "பெரிய குழி விபத்து",
            "ஆழமான குழி", "தரை உள்வாங்கி"
        ],
    },
    "flooding_hazard": {
        "en": [
            "flooding with people trapped", "flood water trapped", "trapped in water",
            "water entered house trapped", "people stranded in water", "flooding inside homes"
        ],
        "ta": [
            "வெள்ள நீர்", "வெள்ளத்தில் சிக்கி", "வீட்டிற்குள் வெள்ளம்", "தண்ணீரில் தத்தளிக்கும்"
        ],
    },
    "blocked_road_hazard": {
        "en": [
            "fallen tree blocking", "fallen pole blocking", "transformer burst",
            "road completely blocked tree", "electric pole on road"
        ],
        "ta": [
            "மரம் விழுந்து பாதை அடைப்பு", "மின்கம்பம் சாய்ந்து", "மின்மாற்றி வெடித்து",
            "மரம் விழுந்து சாலை மறியல்"
        ],
    },
    "fire_hazard": {
        "en": [
            "fire outbreak", "smoke from transformer", "garbage fire",
            "chemical smoke", "sparks and flames"
        ],
        "ta": [
            "தீ விபத்து", "புகை மூட்டம்", "மின்மாற்றியில் தீ", "குப்பையில் தீ"
        ],
    },
    "accident_prone_hazard": {
        "en": [
            "fatal accident", "accident-prone", "vehicles falling",
            "severe injury risk", "causing accidents", "bikers falling down"
        ],
        "ta": [
            "விபத்து அபாயம்", "உயிர்பலி", "வாகனங்கள் கவிழ்ந்து", "அடிக்கடி விபத்து"
        ],
    },
}

# --- Baseline Severity Signal Keywords ---
HIGH_SEVERITY_SIGNALS: Dict[str, List[str]] = {
    "en": [
        "hospital", "school", "bus stand", "bus stop", "railway station",
        "main road", "entire area", "colony", "market", "many people",
        "weeks", "months", "since a month", "for weeks", "contaminated water",
        "sewage entering house", "no water for days"
    ],
    "ta": [
        "மருத்துவமனை", "பள்ளி", "பேருந்து நிலையம்", "முக்கிய சாலை",
        "பகுதி மக்கள்", "சந்தை", "பல குடும்பங்கள்", "வாரக்கணக்கில்",
        "மாதக்கணக்கில்", "பல வாரங்கள்", "குடிநீர் இல்லை பல நாட்கள்",
        "சாக்கடை நீர் வீட்டிற்குள்"
    ],
}

LOW_SEVERITY_SIGNALS: Dict[str, List[str]] = {
    "en": [
        "dirty signboard", "faded paint", "weeds overgrown", "dusty",
        "faint marking", "cosmetic", "minor scratches", "leaf litter"
    ],
    "ta": [
        "மங்கிய பெயர்ப்பலகை", "புல் மண்டி", "அழுக்காக உள்ளது", "சிறு விரிசல்", "தூசி"
    ],
}


def tokenize_unicode(text: str) -> List[str]:
  """Tokenize text into lowercased Unicode words supporting English and Tamil."""
  if not text:
    return []
  # Matches letters and numbers including Tamil unicode range \u0b80-\u0bff
  tokens = re.findall(r"[\w\u0b80-\u0bff]+", text.lower())
  return [t for t in tokens if len(t) > 1]


def classify_category_deterministic(
    text: str, location_text: str = ""
) -> Tuple[GrievanceCategory, Dict[str, float]]:
  """Classify civic problem category using deterministic keyword and phrase matching.

  Returns top suggested category and a dictionary of scores per category.
  """
  combined_text = f"{text} {location_text}".lower()
  scores: Dict[GrievanceCategory, float] = {cat: 0.0 for cat in GrievanceCategory}

  for cat, lang_keywords in CATEGORY_KEYWORDS.items():
    cat_score = 0.0
    for lang, phrases in lang_keywords.items():
      for phrase in phrases:
        phrase_clean = phrase.lower().strip()
        if not phrase_clean:
          continue
        # Check phrase existence in text
        if phrase_clean in combined_text:
          # Multi-word phrase gets higher weight than single token
          weight = 3.0 if " " in phrase_clean else 1.5
          cat_score += weight

    scores[cat] = round(cat_score, 2)

  # Determine highest scoring category
  sorted_cats = sorted(scores.items(), key=lambda item: item[1], reverse=True)
  top_cat, top_score = sorted_cats[0]

  if top_score <= 0.0:
    return GrievanceCategory.OTHER, {k.value: v for k, v in scores.items()}

  return top_cat, {k.value: v for k, v in scores.items()}


def evaluate_safety_rules(
    text: str, location_text: str = ""
) -> Tuple[bool, List[str]]:
  """Deterministically detect physical safety hazards.

  Returns (safety_risk: bool, matched_rule_names: List[str]).
  IMPORTANT: Only returns safe rule names (e.g. 'open_manhole'), NEVER echoes user text.
  """
  combined_text = f"{text} {location_text}".lower()
  matched_rules: List[str] = []

  for rule_name, lang_phrases in SAFETY_RULES.items():
    rule_matched = False
    for lang, phrases in lang_phrases.items():
      for phrase in phrases:
        phrase_clean = phrase.lower().strip()
        if phrase_clean and phrase_clean in combined_text:
          rule_matched = True
          break
      if rule_matched:
        break

    if rule_matched:
      matched_rules.append(rule_name)

  safety_risk = len(matched_rules) > 0
  return safety_risk, matched_rules


def determine_baseline_severity(
    safety_risk: bool,
    description: str,
    duration_text: str = "",
    location_text: str = "",
) -> str:
  """Calculate deterministic baseline severity level.

  Heuristic rules:
  1. 'urgent': any safety risk.
  2. 'high': public health/sanitation failure, impacts key public hubs (hospital, school,
     bus stand, main road), or prolonged duration ('for weeks', 'months').
  3. 'low': minor cosmetic defects without functional or safety disruption.
  4. 'medium': standard operational civic issues.
  """
  if safety_risk:
    return "urgent"

  combined = f"{description} {duration_text} {location_text}".lower()

  # Check high severity signals
  for phrases in HIGH_SEVERITY_SIGNALS.values():
    for phrase in phrases:
      if phrase in combined:
        return "high"

  # Check low severity signals
  for phrases in LOW_SEVERITY_SIGNALS.values():
    for phrase in phrases:
      if phrase in combined:
        return "low"

  return "medium"


def combine_severity(baseline_severity: str, model_suggestion: Optional[str]) -> str:
  """Combine baseline severity and model suggestion.

  The model's suggestion can raise severity, but NEVER lower it below the baseline.
  """
  base_rank = SEVERITY_LEVELS.get(baseline_severity.lower(), 2)
  if not model_suggestion:
    return baseline_severity

  model_rank = SEVERITY_LEVELS.get(model_suggestion.lower(), 1)
  final_rank = max(base_rank, model_rank)

  for name, rank in SEVERITY_LEVELS.items():
    if rank == final_rank:
      return name

  return baseline_severity
