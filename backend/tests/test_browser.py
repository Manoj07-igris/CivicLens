"""Unit and integration tests for Playwright Browser Automation (Phase 14).

Tests the 4-layer defense model, session lifecycle, PII guardrails, review hash binding,
and agent tool integration with human-in-the-loop approvals.
"""

import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.errors import (
    BrowserActionError,
    BrowserApprovalRequiredError,
    BrowserNavigationBlockedError,
    PIIDetectedError,
)
from app.main import app
from app.models.agent import AgentChatRequest
from app.services.browser_service import (
    BrowserService,
    compute_review_hash,
    get_browser_service,
    validate_session_id,
)
from app.services.gemini_service import GeminiService, GeminiToolResult, ToolCallItem, set_gemini_service
from app.services.portal_registry import get_portal_registry_service


@pytest.fixture
def mock_browser_service(tmp_path):
  """Provide an isolated BrowserService operating in deterministic simulation mode."""
  settings = get_settings()
  portal_service = get_portal_registry_service()
  # Mock service instance with mock_mode=True to ensure fast unit tests without launching OS Chromium
  svc = BrowserService(settings=settings, portal_service=portal_service, mock_mode=True)
  # Override storage base_dir to tmp_path
  svc._store._base_dir = tmp_path
  return svc


def test_validate_session_id():
  """Verify UUID4 validation prevents directory traversal."""
  valid_uuid = "a0d0f4e3-af71-4f8f-a9dd-8a34182db5c0"
  assert validate_session_id(valid_uuid) == valid_uuid

  # Malicious path traversal attempts must raise ValueError
  with pytest.raises(ValueError):
    validate_session_id("../../../etc/passwd")

  with pytest.raises(ValueError):
    validate_session_id("invalid-uuid-string")


def test_canonical_review_hash():
  """Verify canonical SHA-256 hash is deterministic and invariant to dictionary key ordering."""
  data1 = {"applicant_name": "K. Ananya (Demo)", "taluk": "Mylapore", "annual_income": 72000}
  data2 = {"annual_income": 72000, "applicant_name": "K. Ananya (Demo)", "taluk": "Mylapore"}

  h1 = compute_review_hash(data1)
  h2 = compute_review_hash(data2)
  assert h1 == h2
  assert len(h1) == 64

  # Modified values produce different hash
  data3 = dict(data1, annual_income=90000)
  assert compute_review_hash(data3) != h1


def test_browser_capabilities_and_manifest():
  """Verify GET /api/v1/browser/capabilities and /manifest endpoints."""
  client = TestClient(app)

  res_cap = client.get("/api/v1/browser/capabilities")
  assert res_cap.status_code == 200
  cap_data = res_cap.json()
  assert "supported_workflows" in cap_data
  assert "demo_portal_url" in cap_data
  assert cap_data["max_concurrent_sessions"] >= 1

  res_man = client.get("/api/v1/browser/manifest")
  assert res_man.status_code == 200
  man_data = res_man.json()
  assert man_data["workflow_id"] == "demo_income_certificate"
  assert len(man_data["steps"]) == 5
  assert "fictional_sample_values" in man_data

  res_sample = client.get("/api/v1/browser/sample-data")
  assert res_sample.status_code == 200
  sample_data = res_sample.json()
  assert "disclaimer" in sample_data
  assert sample_data["values"]["applicant_name"] == "K. Ananya (Demo)"


def test_layer_1_registry_gate_blocks_external_portals(mock_browser_service):
  """Verify Layer 1 Defense blocks any non-demo portal from automation."""
  # prt_tn_esevai is an official portal with kind="official"
  with pytest.raises(BrowserNavigationBlockedError):
    mock_browser_service.start_session(portal_id="prt_tn_esevai")

  with pytest.raises(BrowserNavigationBlockedError):
    mock_browser_service.start_session(portal_id="non_existent_portal_id")


def test_pii_guard_blocks_sensitive_identifiers(mock_browser_service):
  """Verify PII guard rejects Aadhaar, PAN, and phone numbers in fill requests."""
  session = mock_browser_service.start_session(portal_id="prt_demo_portal")

  # 12-digit Aadhaar pattern
  with pytest.raises(PIIDetectedError):
    mock_browser_service.fill_step(
        session_id=session.session_id,
        step_index=1,
        values={"applicant_name": "Test User", "remarks": "My Aadhaar is 9876 5432 1098"},
        fictional_confirmed=True,
    )

  # 10-digit Indian mobile number
  with pytest.raises(PIIDetectedError):
    mock_browser_service.fill_step(
        session_id=session.session_id,
        step_index=1,
        values={"applicant_name": "Test User", "remarks": "Call me at 9840123456"},
        fictional_confirmed=True,
    )


def test_session_lifecycle_and_review_hash_enforcement(mock_browser_service):
  """Test full 5-step lifecycle and human approval review hash binding."""
  session = mock_browser_service.start_session(portal_id="prt_demo_portal")
  sid = session.session_id
  assert session.status == "active"
  assert session.current_step == 1

  # Fill Step 1
  mock_browser_service.fill_step(
      session_id=sid,
      step_index=1,
      values={"applicant_name": "K. Ananya (Demo)", "gender": "female"},
      fictional_confirmed=True,
  )

  # Advance Step
  s2 = mock_browser_service.navigate_next(sid)
  assert s2.current_step == 2

  # Navigate Back
  s1 = mock_browser_service.navigate_back(sid)
  assert s1.current_step == 1

  # Generate Review Preview
  preview = mock_browser_service.get_review_preview(sid)
  assert preview.session_id == sid
  assert len(preview.review_hash) == 64
  assert "Applicant" in preview.summary

  # Submission with invalid/tampered hash must fail
  with pytest.raises(BrowserApprovalRequiredError):
    mock_browser_service.submit_demo(
        session_id=sid,
        review_hash="tampered_hash_000000000000000000000000000000000000000000000000000",
        fictional_confirmed=True,
    )

  # Submission with valid hash succeeds
  res = mock_browser_service.submit_demo(
      session_id=sid,
      review_hash=preview.review_hash,
      fictional_confirmed=True,
  )
  assert res.status == "demo_submitted"
  assert res.application_number.startswith("DEMO-IC-")
  assert "simulation" in res.confirmation_message.lower() or "simulated" in res.confirmation_message.lower()

  # Post-submission actions must be rejected
  with pytest.raises(BrowserActionError):
    mock_browser_service.navigate_next(sid)


def test_demo_portal_static_and_submit_endpoints():
  """Verify FastAPI mounts /demo-portal/ and mock submit endpoint."""
  client = TestClient(app)

  # GET /demo-portal/
  res_portal = client.get("/demo-portal/")
  assert res_portal.status_code == 200
  assert "CivicLens" in res_portal.text
  assert "SIMULATION DEMO" in res_portal.text

  # POST /demo-portal/submit with fictional data
  res_submit = client.post(
      "/demo-portal/submit",
      json={
          "data": {"applicant_name": "K. Ananya (Demo)"},
          "fictional_confirmed": True,
          "application_number": "DEMO-IC-TEST01",
      },
  )
  assert res_submit.status_code == 200
  sub_data = res_submit.json()
  assert sub_data["simulation"] is True
  assert sub_data["application_number"] == "DEMO-IC-TEST01"

  # PII in demo submit is blocked
  res_pii = client.post(
      "/demo-portal/submit",
      json={
          "data": {"applicant_name": "Real User", "phone": "9840123456"},
          "fictional_confirmed": True,
      },
  )
  assert res_pii.status_code == 422


def test_agent_open_service_portal_approval_flow():
  """Verify Central Agent pauses for citizen approval when open_service_portal is invoked."""
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True

  # Model decides to call open_service_portal
  mock_gemini.generate_with_tools = AsyncMock(
      return_value=GeminiToolResult(
          model="gemini-2.5-flash",
          text=None,
          tool_calls=[
              ToolCallItem(name="open_service_portal", args={"portal_id": "prt_demo_portal", "lang": "en"})
          ],
      )
  )
  try:
    set_gemini_service(mock_gemini)

    client = TestClient(app)
    res = client.post(
        "/api/v1/agent/chat",
        json={"message": "Help me practice applying for an income certificate in the demo portal"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "browser_demo"
    assert data["pending_approval"] is not None
    assert data["pending_approval"]["tool_name"] == "open_service_portal"
    assert "launch a local demo simulation" in data["reply"].lower()

    approval_id = data["pending_approval"]["approval_id"]

    # Resume approval: citizen approves
    mock_gemini.generate_with_tools = AsyncMock(
        return_value=GeminiToolResult(
            model="gemini-2.5-flash",
            text="I have opened the demo portal session for you.",
            tool_calls=[],
        )
    )

    res_decide = client.post(
        f"/api/v1/agent/approvals/{approval_id}",
        json={"decision": "approve"},
    )
    assert res_decide.status_code == 200
    decide_data = res_decide.json()
    resumed = decide_data["resumed_response"]
    assert resumed["intent"] == "browser_demo"
    assert len(resumed["browser_sessions"]) >= 1
    assert resumed["browser_sessions"][0]["action"] == "open_portal"
  finally:
    set_gemini_service(None)
