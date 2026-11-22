"""CivicLens PII Guard.

Detects and blocks Personally Identifiable Information (PII) including Aadhaar,
PAN, Indian phone numbers, emails, and bank account / card numbers.
Protects against false positives for dates, rupee amounts, and scheme codes.
Never echoes the detected sensitive values back to the user or into logs.
"""

import re
from typing import List

from app.core.errors import PIIDetectedError

# Email addresses
EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Indian PAN: 5 uppercase letters, 4 digits, 1 uppercase letter
PAN_REGEX = re.compile(
    r"\b[A-Za-z]{5}[0-9]{4}[A-Za-z]\b"
)

# Indian Phone numbers: 10 digits starting with 6-9, optional +91/0 prefix and separator
PHONE_REGEX = re.compile(
    r"(?<!\d)(?:(?:\+91|0)[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)|"
    r"(?<!\d)(?:(?:\+91|0)[\s-]?)?[6-9]\d{9}(?!\d)"
)

# Aadhaar: 12 digits (4-4-4 formatted with space/hyphen, or 12 consecutive digits)
AADHAAR_REGEX = re.compile(
    r"(?<!\d)\d{4}[\s-]\d{4}[\s-]\d{4}(?!\d)|"
    r"(?<!\d)\d{12}(?!\d)"
)

# Long account / card numbers: 16 digits (4-4-4-4) or 13-19 consecutive digits
ACCOUNT_CARD_REGEX = re.compile(
    r"(?<!\d)\d{4}[\s-]\d{4}[\s-]\d{4}[\s-]\d{4}(?!\d)|"
    r"(?<!\d)\d{13,19}(?!\d)"
)

# False-positive filters (entities to mask before checking numeric PII)
# 1. Currency amounts: Rs. 2,50,000 / ₹ 500 / 10000 rupees / 5 lakhs / 2.5 crore
CURRENCY_REGEX = re.compile(
    r"(?:Rs\.?|₹|INR)\s*[\d,]+(?:\.\d+)?|"
    r"\b\d[\d,]*(?:\.\d+)?\s*(?:rupees|rs|lakh|lakhs|crore|crores)\b",
    re.IGNORECASE,
)

# 2. Standard dates: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
DATE_REGEX = re.compile(
    r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b|"
    r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b"
)

# 3. Scheme and Government Order codes: G.O. Ms. No. 42, TN-EV-2024, PMAY-G-2022
SCHEME_ORDER_REGEX = re.compile(
    r"\bG\.?O\.?\s*(?:Ms\.?|Rt\.?|P)?\s*(?:No\.?)?\s*[\d/.-]+|"
    r"\b[A-Za-z]{2,10}-[A-Za-z0-9-]+\b|"
    r"\b(?:Section|Article|Act|Clause)\s+\d+[A-Za-z]?\b",
    re.IGNORECASE,
)


def _mask_non_pii_entities(text: str) -> str:
  """Mask out non-PII numeric patterns like currency, dates, and order numbers."""
  # Replace matched false positives with whitespace of same length to preserve indices
  masked = CURRENCY_REGEX.sub(lambda m: " " * len(m.group(0)), text)
  masked = DATE_REGEX.sub(lambda m: " " * len(m.group(0)), masked)
  masked = SCHEME_ORDER_REGEX.sub(lambda m: " " * len(m.group(0)), masked)
  return masked


def find_pii(text: str) -> List[str]:
  """Analyze text and return a list of detected PII types without leaking values.

  Returns a list of detected types, e.g. ["aadhaar", "phone"].
  If no PII is found, returns an empty list.
  """
  if not text or not text.strip():
    return []

  detected: List[str] = []

  # Check text-based PII first
  if EMAIL_REGEX.search(text):
    detected.append("email")

  if PAN_REGEX.search(text):
    detected.append("pan")

  # Mask non-PII numeric items (dates, currencies, GO codes)
  masked_text = _mask_non_pii_entities(text)

  # Check card or bank account (13-19 digits or 4-4-4-4)
  if ACCOUNT_CARD_REGEX.search(masked_text):
    detected.append("account_or_card")
  elif AADHAAR_REGEX.search(masked_text):
    # If not 13-19 digits, check if it matches 12 digits (Aadhaar)
    detected.append("aadhaar")

  # Check Indian phone number (10 digits starting with 6-9)
  # Note: lookahead/lookbehind ensures 12/16 digits are not flagged as phone
  if PHONE_REGEX.search(masked_text):
    detected.append("phone")

  # Deduplicate preserving order
  seen = set()
  unique_detected = []
  for item in detected:
    if item not in seen:
      seen.add(item)
      unique_detected.append(item)

  return unique_detected


def ensure_no_pii(text: str, field_name: str = "query") -> None:
  """Validate that the text does not contain any sensitive personal identifiers.

  Raises PIIDetectedError if any PII is detected, without echoing the values.
  """
  detected = find_pii(text)
  if detected:
    types_str = ", ".join(detected)
    raise PIIDetectedError(
        message=(
            f"Personal identifier ({types_str}) detected in {field_name}. "
            "CivicLens does not accept or store personal data such as Aadhaar, "
            "PAN, phone numbers, or account details. Please remove personal "
            "details and ask only general procedural questions."
        ),
        details={"detected_types": detected, "field": field_name},
    )
