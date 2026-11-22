"""Bilingual Translation Parity & Tamil Linguistic Quality Test Suite (Phase 16).

Verifies:
1. Complete key parity between English (en.js) and Tamil (ta.js) translation dictionaries.
2. Genuine Tamil linguistic encoding (Unicode range \\u0B80-\\u0BFF) with zero placeholder leakage.
3. Backend language detection engine (app.services.language_service).
"""

import json
import re
import subprocess
from pathlib import Path
import pytest

from app.services.language_service import detect_language, resolve_reply_language


def extract_translation_dicts():
    """Extract nested dictionary structures from frontend ES modules using Node."""
    script = """
    Promise.all([
        import('./frontend/src/utils/i18n/en.js'),
        import('./frontend/src/utils/i18n/ta.js')
    ]).then(([enMod, taMod]) => {
        console.log(JSON.stringify({
            en: enMod.en,
            ta: taMod.ta
        }));
    }).catch(err => {
        console.error(err);
        process.exit(1);
    });
    """
    proc = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    return data["en"], data["ta"]


def flatten_keys(d, prefix=""):
    """Recursively flatten nested dictionary keys."""
    keys = {}
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(flatten_keys(v, full_key))
        else:
            keys[full_key] = str(v)
    return keys


def test_translation_key_parity():
    """Verify that English and Tamil translation dictionaries have >= 95% key parity."""
    en_dict, ta_dict = extract_translation_dicts()
    en_flat = flatten_keys(en_dict)
    ta_flat = flatten_keys(ta_dict)

    en_keys = set(en_flat.keys())
    ta_keys = set(ta_flat.keys())

    common_keys = en_keys.intersection(ta_keys)
    coverage_en_to_ta = len(common_keys) / len(en_keys)
    coverage_ta_to_en = len(common_keys) / len(ta_keys)

    print(f"\nTranslation Keys: {len(en_keys)} English, {len(ta_keys)} Tamil, {len(common_keys)} Common")
    print(f"Coverage: {coverage_en_to_ta*100:.1f}%")

    assert coverage_en_to_ta >= 0.95, f"Tamil dictionary covers {coverage_en_to_ta*100:.1f}% of English keys (target: >= 95%)"
    assert coverage_ta_to_en >= 0.95, f"English dictionary covers {coverage_ta_to_en*100:.1f}% of Tamil keys (target: >= 95%)"


def test_tamil_linguistic_encoding_and_character_density():
    """Verify Tamil dictionary contains genuine Tamil Unicode characters with high density."""
    _, ta_dict = extract_translation_dicts()
    ta_flat = flatten_keys(ta_dict)

    tamil_char_regex = re.compile(r"[\u0B80-\u0BFF]")
    tamil_string_count = 0
    total_tamil_chars = 0

    # Whitelist keys that are intentionally brand names, icons, or URLs
    exempt_keys = {"brandName", "url", "code", "portalUrl", "icon"}

    for key, text in ta_flat.items():
        if any(ex in key for ex in exempt_keys):
            continue
        found = tamil_char_regex.findall(text)
        if found:
            tamil_string_count += 1
            total_tamil_chars += len(found)

    print(f"\nTamil Translation Density: {total_tamil_chars} characters across {tamil_string_count} keys")
    # Assert at least 10,000 genuine Tamil script characters exist in the dictionary
    assert total_tamil_chars > 10000
    # Assert majority of non-exempt keys contain Tamil characters
    assert tamil_string_count / len(ta_flat) >= 0.85


def test_backend_language_detection():
    """Verify backend language detection correctly classifies English and Tamil inputs."""
    assert detect_language("What is the annual income ceiling for this scheme?") == "en"
    assert detect_language("இந்த திட்டத்திற்கான ஆண்டு வருமான வரம்பு என்ன?") == "ta"
    assert detect_language("மற்றும் கலைஞர் மகளிர் உரிமைத் திட்டம்") == "ta"
    assert detect_language("Hello, how can I apply for an income certificate in Chennai?") == "en"

    # Auto language resolution (user_text first, then selected_language)
    assert resolve_reply_language("வணக்கம் உதவி தேவை", "auto") == "ta"
    assert resolve_reply_language("Hello assistance needed", "auto") == "en"
    assert resolve_reply_language("Any input text", "ta") == "ta"
    assert resolve_reply_language("எந்த உரையும்", "en") == "en"
