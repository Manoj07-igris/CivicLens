"""Language detection and bilingual prompt instruction service for CivicLens.

Provides Unicode-based script analysis to detect English, Tamil, and mixed queries
without third-party dependencies, resolves reply language preferences, and formats
strict language instructions for the Gemini conversational assistant.
"""

from typing import Literal

LanguageCode = Literal["en", "ta", "mixed"]
ReplyLanguage = Literal["en", "ta"]

# Unicode codepoint bounds for Tamil block: U+0B80 to U+0BFF
TAMIL_START = 0x0B80
TAMIL_END = 0x0BFF


def is_tamil_char(char: str) -> bool:
  """Check if a single character belongs to the Tamil Unicode script block."""
  return TAMIL_START <= ord(char) <= TAMIL_END


def is_latin_char(char: str) -> bool:
  """Check if a character is a standard Latin letter (a-z, A-Z)."""
  return ("a" <= char <= "z") or ("A" <= char <= "Z")


def detect_language(text: str) -> LanguageCode:
  """Detect whether input text is primarily English ('en'), Tamil ('ta'), or mixed ('mixed').

  Analyzes script distribution directly without external dependencies.
  Safely handles empty strings, numbers, and symbols.
  """
  if not text or not text.strip():
    return "en"

  tamil_count = 0
  latin_count = 0

  for char in text:
    if is_tamil_char(char):
      tamil_count += 1
    elif is_latin_char(char):
      latin_count += 1

  total_letters = tamil_count + latin_count

  # If no letters (only digits, punctuation, whitespace, emojis), fallback to English
  if total_letters == 0:
    return "en"

  # Exclusive script presence
  if tamil_count > 0 and latin_count == 0:
    return "ta"
  if latin_count > 0 and tamil_count == 0:
    return "en"

  # Both scripts present - evaluate script ratio
  tamil_ratio = tamil_count / total_letters

  # If one script overwhelmingly dominates (> 85%), classify as that script.
  # Otherwise, classify as mixed (e.g. English keywords with Tamil verbs/nouns).
  if tamil_ratio >= 0.85:
    return "ta"
  elif tamil_ratio <= 0.15:
    return "en"
  else:
    return "mixed"


def resolve_reply_language(
    user_text: str,
    selected_language: str = "auto",
    ui_language: str = "en",
) -> ReplyLanguage:
  """Determine the target response language according to user and system rules.

  1. If user explicitly chose 'en' or 'ta', always respect that preference.
  2. If 'auto' is selected:
     - Pure Tamil queries receive Tamil ('ta') replies.
     - Pure English / Latin queries receive English ('en') replies.
     - Mixed queries default to the current UI language (fallback 'en').
  """
  clean_selected = (selected_language or "auto").strip().lower()

  if clean_selected in ("en", "ta"):
    return clean_selected  # type: ignore

  # 'auto' mode: analyze the user's question
  detected = detect_language(user_text)

  if detected == "ta":
    return "ta"
  elif detected == "en":
    return "en"
  else:  # 'mixed'
    clean_ui = (ui_language or "en").strip().lower()
    return clean_ui if clean_ui in ("en", "ta") else "en"  # type: ignore


def build_language_instruction(reply_language: ReplyLanguage) -> str:
  """Generate targeted system instruction guiding Gemini's vocabulary and phrasing."""
  if reply_language == "ta":
    return (
        "\n[LANGUAGE INSTRUCTION: TAMIL (தமிழ்)]\n"
        "- Respond entirely in clear, natural, and accessible Tamil (தமிழ்).\n"
        "- Keep official scheme titles, government department names, circular numbers, "
        "and form codes accurate.\n"
        "- When helpful for citizen clarity, provide the authoritative English official term "
        "in parentheses alongside the Tamil term (e.g. குடும்ப அட்டை (Ration Card), "
        "வருவாய்த்துறை (Revenue Department), பட்டா/சிட்டா (Patta/Chitta)).\n"
        "- Never guess or translate official proper names incorrectly. If an official Tamil designation "
        "is uncertain, preserve the recognized English term."
    )
  else:
    return (
        "\n[LANGUAGE INSTRUCTION: ENGLISH]\n"
        "- Respond in simple, plain-language, citizen-friendly English.\n"
        "- Break down procedural workflows into numbered steps or concise bullet points.\n"
        "- Avoid dense legalese and bureaucratic acronyms; explain any mandatory government "
        "abbreviations upon first use."
    )
