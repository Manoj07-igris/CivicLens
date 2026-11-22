"""Unit tests for Unicode script language detection and bilingual instruction formatting."""

import pytest
from app.services.language_service import (
    build_language_instruction,
    detect_language,
    resolve_reply_language,
)


def test_detect_language_english():
  """Verify standard English queries resolve to 'en'."""
  text = "What are the required documents to apply for a community certificate?"
  assert detect_language(text) == "en"


def test_detect_language_tamil():
  """Verify standard Tamil queries resolve to 'ta'."""
  text = "சாதிச் சான்றிதழ் பெற என்னென்ன ஆவணங்கள் தேவைப்படுகின்றன?"
  assert detect_language(text) == "ta"


def test_detect_language_mixed():
  """Verify mixed Tamil and English content resolves to 'mixed'."""
  text = "PM Kisan யோஜனா scheme eligibility என்ன?"
  assert detect_language(text) == "mixed"


def test_detect_language_tanglish_latin_letters():
  """Verify Tanglish written in Latin script is detected as Latin script ('en')."""
  text = "Ration card apply panna enna documents thevai?"
  assert detect_language(text) == "en"


def test_detect_language_empty_and_whitespace():
  """Verify empty and blank inputs safely fallback to 'en'."""
  assert detect_language("") == "en"
  assert detect_language("   \n\t  ") == "en"


def test_detect_language_digits_and_symbols():
  """Verify inputs with only numbers and symbols fallback to 'en'."""
  assert detect_language("1234567890 !@#$%^&*()_+") == "en"


def test_resolve_reply_language_explicit_selection():
  """Verify explicit language overrides question language."""
  # User chose English even though question is in Tamil
  assert resolve_reply_language("வணக்கம்", selected_language="en") == "en"
  # User chose Tamil even though question is in English
  assert resolve_reply_language("Hello there", selected_language="ta") == "ta"


def test_resolve_reply_language_auto_mode():
  """Verify 'auto' mode resolves based on input language."""
  assert resolve_reply_language("வணக்கம் உதவி வேண்டும்", selected_language="auto") == "ta"
  assert resolve_reply_language("How do I file a grievance?", selected_language="auto") == "en"


def test_resolve_reply_language_mixed_auto_falls_back_to_ui():
  """Verify mixed language in 'auto' mode honors the current UI language."""
  mixed_query = "PM Kisan யோஜனா scheme details"
  assert resolve_reply_language(mixed_query, selected_language="auto", ui_language="ta") == "ta"
  assert resolve_reply_language(mixed_query, selected_language="auto", ui_language="en") == "en"
  assert resolve_reply_language(mixed_query, selected_language="auto", ui_language="unknown") == "en"


def test_build_language_instruction_content():
  """Verify language instructions contain proper rules for English and Tamil."""
  ta_instruction = build_language_instruction("ta")
  assert "தமிழ்" in ta_instruction
  assert "parentheses" in ta_instruction

  en_instruction = build_language_instruction("en")
  assert "plain-language" in en_instruction or "simple" in en_instruction
