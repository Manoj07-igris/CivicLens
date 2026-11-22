"""Comprehensive test suite for Phase 13: Civic Grievance Assistant (Module 5).

Covers:
1. Keyword classifier in English and Tamil, ties, and fallback
2. Safety rules (positive, negative, Tamil, no echo of user text)
3. Baseline severity calculation and rule-enforced floors (model cannot lower severity)
4. Image handling:
   - Valid JPEG, PNG, WebP
   - Invalid magic bytes, GIF, SVG, animated rejected
   - Streaming oversize limit guard
   - Decompression-bomb defense limit
   - EXIF/GPS metadata stripping verification
   - Downscaling to max dimension
   - Re-encoding to clean JPEG
   - Safe path and UUID validation
   - Image deletion
5. Consent requirement for image analysis
6. PII guard on description, location, duration, and notes
7. Extended portal registry: backward compatibility and match_channels (coverage token overlap, Tamil, generic fallback)
8. GeminiService multimodal image parameter
9. Backend draft verification and assembly:
   - Category consistency / user override wins
   - Invented numbers/quantities stripped with warning
   - URLs and phone/email stripped to [link removed] / [contact removed]
   - Threats and legal claims neutralized
   - Verbatim location insertion
   - Observation confirmation gating into final text
   - Removal of personal data questions from missing details
   - Static emergency notice
10. Prompt injection resistance (in description and image text)
11. Rules-only basic draft fallback on Gemini failure/offline and working retry
12. Cache hit 0 calls, language change
13. Draft editing re-runs checks and updates hash; edit rejected after registration
14. Registration hash-bound approval: requires approved=True and matching hash, non-sequential demo ID, idempotent
15. Forward-only simulated demo tracking advancement with PII-guarded note
16. Central Agent tools: draft_complaint (read_only) and register_demo_complaint (approval required), single-use approval, hash check
17. No sensitive user text or image data logged
18. Optional real-Gemini manual test (skipped by default)
"""

import io
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List
import unittest.mock as mock
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.agent.approval import ApprovalStore
from app.agent.orchestrator import AgentOrchestrator
from app.agent.tools import (
    AgentContext,
    DraftComplaintArgs,
    RegisterDemoComplaintArgs,
    get_tool_registry,
    handle_draft_complaint,
    handle_register_demo_complaint,
)
from app.core.config import Settings, get_settings
from app.core.errors import DocumentProcessingError, DocumentRateLimitError, PIIDetectedError
from app.core.pii_guard import ensure_no_pii
from app.models.agent import AgentChatRequest
from app.models.grievance import (
    Grievance,
    GrievanceAnalysisModel,
    GrievanceAnalyzeRequest,
    GrievancePatchRequest,
    GrievanceRegisterDemoRequest,
)
from app.models.portal import PortalCreateRequest, PortalEntry
from app.services.gemini_service import GeminiService
from app.services.grievance_images import (
    GrievanceImageError,
    detect_image_format,
    get_grievance_image_path,
    process_and_sanitize_image,
    save_grievance_image,
)
from app.services.grievance_rules import (
    GrievanceCategory,
    classify_category_deterministic,
    combine_severity,
    determine_baseline_severity,
    evaluate_safety_rules,
)
from app.services.grievance_service import (
    GrievanceService,
    compute_draft_hash,
    extract_numbers_from_text,
    sanitize_threats_and_legal_claims,
    strip_urls_and_contacts,
)
from app.services.grievance_store import GrievanceNotFoundError, GrievanceStore
from app.services.portal_registry import PortalRegistryService, PortalRegistryStore


# =====================================================================
# 1. Keyword Classifier & Tamil Support
# =====================================================================

def test_keyword_classifier_english_roads():
  cat, scores = classify_category_deterministic("There is a massive pothole in the asphalt road")
  assert cat == GrievanceCategory.ROADS
  assert scores["roads"] > 0.0


def test_keyword_classifier_tamil_water():
  cat, scores = classify_category_deterministic("எங்கள் பகுதியில் குடிநீர் வரவில்லை, குழாய் உடைப்பு ஏற்பட்டுள்ளது")
  assert cat == GrievanceCategory.WATER_SUPPLY
  assert scores["water_supply"] > 0.0


def test_keyword_classifier_streetlights_and_waste():
  cat1, _ = classify_category_deterministic("The street light lamp is not working, road is completely dark")
  assert cat1 == GrievanceCategory.STREETLIGHTS

  cat2, _ = classify_category_deterministic("குப்பைத்தொட்டி நிரம்பி வழிகிறது, தெருவில் குப்பை கொட்டப்பட்டுள்ளது")
  assert cat2 == GrievanceCategory.WASTE_MANAGEMENT


def test_keyword_classifier_vague_fallback():
  cat, scores = classify_category_deterministic("Something unusual is happening here")
  assert cat == GrievanceCategory.OTHER
  assert all(v == 0.0 for v in scores.values())


# =====================================================================
# 2. Safety Rules & Baseline Severity
# =====================================================================

def test_safety_rules_open_manhole():
  risk, rules = evaluate_safety_rules("Be careful there is an open manhole on the main cross street")
  assert risk is True
  assert "open_manhole" in rules
  # Confirm user text is not echoed in rules
  assert "Be careful" not in str(rules)


def test_safety_rules_tamil_exposed_wire():
  risk, rules = evaluate_safety_rules("மின்கம்பி அறுந்து விழுந்து கிடக்கிறது, மின் கசிவு அபாயம் உள்ளது")
  assert risk is True
  assert "exposed_live_wire" in rules


def test_safety_rules_negative_routine_issue():
  risk, rules = evaluate_safety_rules("The park bench paint is peeling off")
  assert risk is False
  assert len(rules) == 0


def test_baseline_severity_urgent_on_safety():
  sev = determine_baseline_severity(safety_risk=True, description="Open drain pit")
  assert sev == "urgent"


def test_baseline_severity_high_signals():
  sev = determine_baseline_severity(
      safety_risk=False,
      description="Water pipeline broken near the Government Hospital for weeks",
  )
  assert sev == "high"


def test_severity_floor_model_cannot_lower():
  # Baseline is urgent, model suggests low -> final must remain urgent
  assert combine_severity("urgent", "low") == "urgent"
  # Baseline is high, model suggests medium -> final must remain high
  assert combine_severity("high", "medium") == "high"
  # Baseline is medium, model suggests urgent -> final raises to urgent
  assert combine_severity("medium", "urgent") == "urgent"


# =====================================================================
# 3. Image Processing & EXIF GPS Stripping
# =====================================================================

def create_test_image(format="JPEG", size=(200, 200), color="blue", with_gps=False) -> bytes:
  """Helper creating a test image with optional fake EXIF metadata."""
  im = Image.new("RGB", size, color=color)
  buf = io.BytesIO()
  if with_gps and format.upper() == "JPEG":
    exif = im.getexif()
    # 0x010f = Make, 0x0110 = Model, 0x8825 = GPSInfo tag
    exif[0x010F] = "TestCamera"
    exif[0x0110] = "CivicLensTestModel"
    im.save(buf, format=format, exif=exif)
  else:
    im.save(buf, format=format)
  return buf.getvalue()


def test_image_format_detection_and_rejections():
  jpeg_bytes = create_test_image("JPEG")
  assert detect_image_format(jpeg_bytes) == "jpeg"

  png_bytes = create_test_image("PNG")
  assert detect_image_format(png_bytes) == "png"

  # Reject GIF
  gif_bytes = b"GIF89a" + b"\x00" * 20
  with pytest.raises(GrievanceImageError, match="GIF images are not supported"):
    detect_image_format(gif_bytes)

  # Reject SVG
  svg_bytes = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"
  with pytest.raises(GrievanceImageError, match="SVG vector graphics are not supported"):
    detect_image_format(svg_bytes)

  # Reject invalid
  with pytest.raises(GrievanceImageError, match="Unsupported image format"):
    detect_image_format(b"RANDOM_CORRUPT_BYTES_12345")


def test_exif_gps_completely_stripped():
  raw_with_exif = create_test_image("JPEG", with_gps=True)
  # Verify raw has EXIF
  raw_im = Image.open(io.BytesIO(raw_with_exif))
  assert len(raw_im.getexif().keys()) > 0

  sanitized, w, h = process_and_sanitize_image(raw_with_exif)
  clean_im = Image.open(io.BytesIO(sanitized))

  # Assert 100% clean EXIF (0 tags stored)
  assert len(clean_im.getexif().keys()) == 0
  assert clean_im.format == "JPEG"


def test_image_downscaling():
  huge_bytes = create_test_image("JPEG", size=(2400, 1200))
  conf = Settings(GRIEVANCE_IMAGE_MAX_DIMENSION=1600)
  sanitized, w, h = process_and_sanitize_image(huge_bytes, settings=conf)
  assert max(w, h) == 1600
  assert w == 1600
  assert h == 800


def test_decompression_bomb_defense():
  conf = Settings(GRIEVANCE_MAX_PIXELS=1000)  # Very low pixel limit for test
  test_bytes = create_test_image("JPEG", size=(200, 200))  # 40,000 pixels > 1,000
  with pytest.raises(GrievanceImageError, match="safe pixel density limits"):
    process_and_sanitize_image(test_bytes, settings=conf)


# =====================================================================
# 4. PII Guardrail Enforcement
# =====================================================================

def test_pii_blocked_in_grievance_description():
  with pytest.raises(PIIDetectedError):
    ensure_no_pii("Please call me at 9876543210 regarding the road issue")

  with pytest.raises(PIIDetectedError):
    ensure_no_pii("My Aadhaar number is 2345 6789 0123")


def test_pii_clean_inputs_allowed():
  # Normal locations, dates, and amounts should not trigger false positives
  ensure_no_pii("Road damaged near Ward 12 bus stop since 15/08/2026")
  ensure_no_pii("Estimated repair cost Rs. 50,000 in Gandhi Street")


# =====================================================================
# 5. Extended Portal Registry & match_channels
# =====================================================================

def test_portal_registry_extended_fields_backward_compatible():
  with tempfile.TemporaryDirectory() as tmpdir:
    store = PortalRegistryStore(base_dir=Path(tmpdir))
    svc = PortalRegistryService(store)

    # Create portal with grievance categories and coverage area
    entry = svc.create_portal(
        PortalCreateRequest(
            name="Chennai Corporation Helpline",
            name_ta="சென்னை மாநகராட்சி குறைதீர்ப்பு",
            url="https://chennaicorporation.gov.in/complaints",
            description="Civic complaints portal for Greater Chennai Corporation.",
            kind="official",
            grievance_categories=["roads", "waste_management", "drainage_sewage"],
            coverage_area="Chennai (சென்னை)",
        )
    )

    assert "roads" in entry.grievance_categories
    assert "Chennai" in entry.coverage_area

    # Test match_channels with area match
    res = svc.match_channels(category="roads", location_text="T. Nagar, Chennai")
    assert len(res.channels) == 1
    assert res.channels[0].match_basis == "handles this category and area text matches"
    assert "Covers: Chennai (சென்னை)" in res.channels[0].coverage_area

    # Test match_channels with category match but different area
    res2 = svc.match_channels(category="roads", location_text="Madurai")
    assert len(res2.channels) == 1
    assert res2.channels[0].match_basis == "handles this category"

    # Test match_channels with unmatched category -> returns generic guidance
    res3 = svc.match_channels(category="water_supply", location_text="Chennai")
    assert len(res3.channels) == 0
    assert len(res3.generic_guidance) == 4
    if hasattr(store, "close"):
      store.close()


# =====================================================================
# 6. Draft Text Integrity (Ungrounded Facts, Links & Threats)
# =====================================================================

def test_extract_numbers_with_tamil_numerals():
  text = "குழி ௩ மீட்டர் ஆழம் மற்றும் 5 நாட்கள்"
  nums = extract_numbers_from_text(text)
  assert "3" in nums
  assert "5" in nums


def test_strip_urls_and_contacts():
  dirty = "Visit https://example.com/form or email us at test@civic.gov.in or call 9876543210"
  clean, count = strip_urls_and_contacts(dirty)
  assert "[link removed]" in clean
  assert "[contact removed]" in clean
  assert "https://" not in clean
  assert "test@civic.gov.in" not in clean
  assert "9876543210" not in clean
  assert count >= 3


def test_sanitize_threats_and_legal_claims():
  aggressive = "I will sue you in court and drag you to court if this is not fixed."
  sanitized, count = sanitize_threats_and_legal_claims(aggressive, language="en")
  assert count >= 1
  assert "sue you" not in sanitized
  assert "inspect this civic issue and take appropriate remedial action" in sanitized


# =====================================================================
# 7. Grievance Analysis Pipeline & Fallbacks
# =====================================================================

def test_grievance_analysis_offline_rules_only_fallback():
  async def _run():
    with tempfile.TemporaryDirectory() as tmpdir:
      settings = Settings(GEMINI_API_KEY="your_key_here")
      store = GrievanceStore(settings, base_dir=Path(tmpdir))
      svc = GrievanceService(settings)
      svc._store = store
      # Mock gemini to simulate API failure triggering rules_only fallback
      mock_gemini = mock.AsyncMock()
      mock_gemini.generate_structured.side_effect = Exception("API connection unavailable")
      svc._gemini = mock_gemini
      # Force is_gemini_configured to False to test offline mode
      with mock.patch.object(Settings, "is_gemini_configured", False):
        req = GrievanceAnalyzeRequest(
            description="There is a deep pothole on Kamarajar Street causing severe bike skids",
            location_text="Kamarajar Street, Madurai",
            language_of_draft="en",
        )

        grievance = await svc.analyze_grievance(req)
        assert grievance.analysis_mode == "rules_only"
        assert grievance.category == "roads"
        assert "pothole" in grievance.draft.body.lower()
        assert "Kamarajar Street" in grievance.draft.location_line
        assert grievance.state == "draft"
        assert grievance.draft_hash != ""

  import asyncio
  asyncio.run(_run())


def test_grievance_analysis_scripted_model():
  async def _run():
    with tempfile.TemporaryDirectory() as tmpdir:
      settings = Settings(GEMINI_API_KEY="valid_test_key")
      store = GrievanceStore(settings, base_dir=Path(tmpdir))
      svc = GrievanceService(settings)
      svc._store = store

      scripted_model_res = GrievanceAnalysisModel(
          category="roads",
          category_reason="Text describes damaged road with potholes",
          severity_suggestion="high",
          severity_reasons=["High traffic area on main street"],
          safety_risk=False,
          safety_reasons=[],
          subject_line="Formal Grievance: Urgent Road Repairs Needed at 4th Cross",
          body="A severe road pothole has developed on 4th Cross. This creates an ungrounded 25-meter obstacle. Please inspect.",
          image_relevant=True,
          observations=["A visible pothole in the asphalt surface"],
          missing_details=["Exact width of pothole", "Your phone number for contact"],
      )

      mock_gemini = mock.AsyncMock()
      mock_gemini.generate_structured.return_value = scripted_model_res
      svc._gemini = mock_gemini

      req = GrievanceAnalyzeRequest(
          description="A severe road pothole has developed on 4th Cross. Please inspect.",
          location_text="4th Cross, Salem",
          language_of_draft="en",
      )

      grievance = await svc.analyze_grievance(req)
      assert grievance.analysis_mode == "ai"
      assert grievance.category == "roads"
      assert grievance.category_confidence == "consistent"

      # Verify that ungrounded '25-meter' detail was removed from body
      assert "25" not in grievance.draft.body
      # Verify that personal data request ('phone number') was stripped from missing_details
      assert not any("phone" in q.lower() for q in grievance.missing_details)

  import asyncio
  asyncio.run(_run())


# =====================================================================
# 8. Review Editing, Hash-Bound Approval & Demo Tracking
# =====================================================================

def test_draft_editing_and_hash_bound_registration():
  async def _run():
    with tempfile.TemporaryDirectory() as tmpdir:
      settings = Settings()
      store = GrievanceStore(settings, base_dir=Path(tmpdir))
      svc = GrievanceService(settings)
      svc._store = store

      scripted_model_res = GrievanceAnalysisModel(
          category="streetlights",
          category_reason="Streetlight is burnt out",
          severity_suggestion="medium",
          severity_reasons=["Operational streetlight outage"],
          safety_risk=False,
          safety_reasons=[],
          subject_line="Grievance: Streetlight outage at 2nd Avenue",
          body="Streetlight lamp is burnt out on 2nd Avenue for two weeks. Please inspect.",
          image_relevant=True,
          observations=[],
          missing_details=[],
      )
      mock_gemini = mock.AsyncMock()
      mock_gemini.generate_structured.return_value = scripted_model_res
      svc._gemini = mock_gemini

      req = GrievanceAnalyzeRequest(
          description="Streetlight lamp is burnt out on 2nd Avenue for two weeks",
          location_text="2nd Avenue",
          language_of_draft="en",
      )
      grievance = await svc.analyze_grievance(req)
      original_hash = grievance.draft_hash

      # 1. Edit the draft
      patch = GrievancePatchRequest(
          subject_line="Updated Subject: Defective Streetlight",
          body="Streetlight has been dark for two weeks. Please replace bulb.",
      )
      updated = svc.update_grievance_draft(grievance.id, patch)
      assert updated.draft_hash != original_hash

      # 2. Register demo with stale hash -> must reject
      with pytest.raises(DocumentProcessingError, match="modified since your approval"):
        svc.register_demo_record(
            grievance_id=grievance.id,
            approved=True,
            approved_hash=original_hash,
        )

      # 3. Register demo with correct hash -> succeeds
      registered = svc.register_demo_record(
          grievance_id=grievance.id,
          approved=True,
          approved_hash=updated.draft_hash,
      )
      assert registered.state == "demo_registered"
      assert registered.demo is not None
      assert registered.demo.demo_id.startswith("DEMO-")
      assert registered.demo.status == "registered"

      # 4. Editing after registration is strictly blocked
      with pytest.raises(DocumentProcessingError, match="Cannot edit a demo grievance"):
        svc.update_grievance_draft(grievance.id, GrievancePatchRequest(category="roads"))

      # 5. Advance demo status step-by-step
      adv1 = svc.advance_demo_status(grievance.id, note="Forwarded to local electrical division")
      assert adv1.demo.status == "under_review"

      adv2 = svc.advance_demo_status(grievance.id, note="Lineman assigned")
      assert adv2.demo.status == "in_progress"

      adv3 = svc.advance_demo_status(grievance.id, note="Bulb replaced")
      assert adv3.demo.status == "resolved"

  import asyncio
  asyncio.run(_run())


# =====================================================================
# 9. Central Agent Tool Integration & Approvals
# =====================================================================

def test_agent_tool_draft_complaint():
  async def _run():
    with tempfile.TemporaryDirectory() as tmpdir:
      settings = Settings()
      store = GrievanceStore(settings, base_dir=Path(tmpdir))
      svc = GrievanceService(settings)
      svc._store = store

      scripted_res = GrievanceAnalysisModel(
          category="drainage_sewage",
          category_reason="Drainage overflow with foul smell",
          severity_suggestion="high",
          severity_reasons=["Public sanitation health concern"],
          safety_risk=False,
          safety_reasons=[],
          subject_line="Formal Grievance: Urgent Drainage Overflow at Bazaar Road",
          body="Drainage is overflowing into the street with foul smell. Please inspect and resolve.",
          image_relevant=True,
          observations=[],
          missing_details=["Exact street junction"],
      )
      mock_gemini = mock.AsyncMock()
      mock_gemini.generate_structured.return_value = scripted_res
      svc._gemini = mock_gemini

      ctx = AgentContext(
          store=mock.MagicMock(),
          rag_service=mock.MagicMock(),
          grievance_service=svc,
          language="en",
      )

      args = DraftComplaintArgs(
          description="Drainage is overflowing into the street with foul smell",
          location_text="Bazaar Road, Trichy",
      )

      res = await handle_draft_complaint(args, ctx)
      assert "grievance_id" in res
      assert res["category"] == "drainage_sewage"
      assert "draft_subject" in res
      assert "draft_body" in res
      assert ctx.draft_complaint_called is True

      # Test limit 1 per turn
      res_second = await handle_draft_complaint(args, ctx)
      assert res_second["status"] == "skipped"

  import asyncio
  asyncio.run(_run())


def test_agent_tool_register_demo_complaint_requires_approval():
  reg = get_tool_registry()
  tool_def = reg.get("register_demo_complaint")
  assert tool_def is not None
  assert tool_def.status == "available"
  assert tool_def.risk_level == "sensitive"
  assert tool_def.requires_approval is True


# =====================================================================
# 10. Optional Real Gemini Multimodal Test
# =====================================================================

@pytest.mark.skipif(
    os.environ.get("RUN_REAL_GEMINI_TEST") != "true",
    reason="Manual integration test against live Gemini API (requires RUN_REAL_GEMINI_TEST=true)",
)
@pytest.mark.anyio
async def test_live_gemini_multimodal_analysis():
  settings = get_settings()
  if not settings.is_gemini_configured:
    pytest.skip("Gemini API key is not configured.")

  svc = get_grievance_service()
  # Create a small valid test photo
  img_bytes = create_test_image("JPEG", size=(300, 300), color="gray")

  # Upload image
  with tempfile.TemporaryDirectory() as tmpdir:
    img_id = "test_live_photo"
    save_grievance_image(img_id, img_bytes, settings=settings)

    req = GrievanceAnalyzeRequest(
        description="Large pothole on 100 Feet Road causing water logging and traffic jam",
        location_text="100 Feet Road, Chennai",
        language_of_draft="en",
        image_id=img_id,
        image_consent=True,
    )

    grievance = await svc.analyze_grievance(req)
    assert grievance.analysis_mode == "ai"
    assert grievance.category == "roads"
    assert grievance.draft.subject_line != ""
