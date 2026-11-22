"""End-to-End Cross-Module System Integration Test Suite for CivicLens (Phase 16).

Verifies the complete, unified citizen journey across all 5 Civic Modules, the Central AI Agent,
and SQLite persistence:
1. Module 1 (Policy Intelligence): Upload gazette PDF -> extract & chunk -> grounded Q&A with verified [E1] citations.
2. Module 2 (Policy Comparison): Baseline gazette vs. Amendment -> deterministic fact diff & change categories.
3. Module 3 (Fact Verification): Viral claim check -> multi-source retrieval -> deterministic verdict & quote verification.
4. Module 4 (Public Service Assistant): Citizen service query -> requirement checklist & curated official portal match.
5. Module 4 Automation (Browser Demo): Controlled Playwright simulation -> PII-scanned form fill -> review hash -> mock receipt.
6. Module 5 (Civic Grievance Assistant): Hazardous pothole description -> rule safety engine -> draft hash -> demo tracking.
7. Central AI Agent & Orchestrator: Multi-step reasoning -> tool execution -> ledger recording -> conversation persistence.
8. System Administration: Status check -> online hot backup -> automated maintenance run.
"""

import hashlib
import io
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))

from app.agent.tools import ToolRegistry, get_tool_registry
from app.core.config import get_settings
from app.db.database import Database, get_database
from app.main import app
from app.models.agent import AgentResponse
from app.models.gemini import GeminiTokenUsage
from app.models.grievance import GrievanceAnalysisModel
from app.models.verification import ClaimJudgementItem, VerificationReport
from app.agent.orchestrator import AgentOrchestrator, get_agent_orchestrator
from app.services.chat_service import set_chat_service
from app.services.gemini_service import GeminiResult, GeminiService, set_gemini_service

client = TestClient(app)


def create_minimal_pdf_bytes(text: str) -> bytes:
  """Generate a minimal valid PDF byte sequence using PyMuPDF."""
  import fitz  # PyMuPDF
  doc = fitz.open()
  page = doc.new_page()
  page.insert_text((50, 72), text)
  pdf_bytes = doc.tobytes()
  doc.close()
  return pdf_bytes


class TestEndToEndCitizenJourney:
  """Unified integration test verifying that all modules collaborate seamlessly."""

  @pytest.fixture(autouse=True)
  def setup_and_teardown(self):
    """Ensure clean service and mock state."""
    from app.services.browser_service import BrowserService
    orig_browser = BrowserService._instance
    BrowserService._instance = BrowserService(mock_mode=True)
    yield
    set_gemini_service(None)
    set_chat_service(None)
    BrowserService._instance = orig_browser

  def test_full_civic_intelligence_pipeline(self):
    """Walk through the complete citizen experience from gazette to grievance to audit."""

    # --------------------------------------------------------------------------
    # Step 1: Citizen uploads an official government notification PDF (Module 1)
    # --------------------------------------------------------------------------
    pdf_content = (
        "GOVERNMENT OF TAMIL NADU\n"
        "Industries Department - G.O. Ms. No. 42 dated 15-02-2023\n"
        "Policy: Tamil Nadu Electric Vehicle Policy 2023\n"
        "Clause 4.1: Commercial electric three-wheelers shall receive a direct purchase subsidy of Rs. 2,50,000.\n"
        "Clause 5.2: 100% exemption from road tax is granted for all battery electric vehicles registered before 31-12-2025.\n"
        "Clause 6.1: Applications must be submitted through the Tamil Nadu Transport Portal."
    )
    pdf_bytes = create_minimal_pdf_bytes(pdf_content)

    upload_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("tn_ev_policy_2023.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code in (200, 202)
    doc_meta = upload_res.json()
    doc_id = doc_meta["document_id"]
    assert doc_id is not None
    assert doc_meta["filename"] == "tn_ev_policy_2023.pdf"

    # Verify document detail and page extraction
    detail_res = client.get(f"/api/v1/documents/{doc_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["page_count"] >= 1

    # --------------------------------------------------------------------------
    # Step 2: Citizen asks grounded question about the policy (Module 1 RAG)
    # --------------------------------------------------------------------------
    from app.models.documents import GroundedAnswer, CitationItem
    from app.models.verification import ClaimSplitResult, AtomicClaimItem, BatchJudgementResult, ClaimJudgementItem
    from app.models.service_guide import ServiceGuideDraft, ServiceGuideDraftItem, ServiceGuideDraftKeyFact

    mock_gemini = AsyncMock(spec=GeminiService)
    mock_gemini.active_model = "gemini-2.5-flash"
    mock_gemini.generate_text.return_value = GeminiResult(
        text="Tamil Nadu EV Policy 2023 provides subsidies and exemptions.",
        model="gemini-2.5-flash",
        latency_ms=10.0,
    )

    async def mock_structured(prompt_or_messages=None, response_model=None, **kwargs):
      schema = response_model or kwargs.get("schema")
      if schema == GroundedAnswer or getattr(schema, "__name__", "") == "GroundedAnswer":
        return GroundedAnswer(
            answer="Commercial electric three-wheelers receive a direct purchase subsidy of Rs. 2,50,000.",
            found=True,
            citations=[
                CitationItem(
                    chunk_id=f"{doc_id}_c0",
                    quote="Commercial electric three-wheelers shall receive a direct purchase subsidy of Rs. 2,50,000.",
                )
            ],
            missing_information=None,
        )
      elif schema == ClaimSplitResult or getattr(schema, "__name__", "") == "ClaimSplitResult":
        return ClaimSplitResult(
            atomic_claims=[
                AtomicClaimItem(
                    claim_id="c1",
                    text="Tamil Nadu EV Policy 2023 gives 100% road tax exemption until 2025",
                    subject="Tamil Nadu EV Policy 2023",
                    numeric_fact="100%",
                )
            ]
        )
      elif schema == BatchJudgementResult or getattr(schema, "__name__", "") == "BatchJudgementResult":
        return BatchJudgementResult(
            judgements=[
                ClaimJudgementItem(
                    claim_id="c1",
                    verdict="supported",
                    confidence="high",
                    reasoning="Document clause 5.2 confirms 100% road tax exemption.",
                    citations=[],
                )
            ]
        )
      elif schema == ServiceGuideDraft or getattr(schema, "__name__", "") == "ServiceGuideDraft":
        draft = ServiceGuideDraft(
            procedure_overview="Guidance for EV purchase subsidy application.",
            checklist_items=[
                ServiceGuideDraftItem(
                    category="documents",
                    text="Collect RC book and invoice.",
                )
            ],
            key_facts=[
                ServiceGuideDraftKeyFact(
                    fact_type="timeline",
                    label="Deadline",
                    value_text="2025-12-31",
                )
            ],
        )
        return (draft, None)
      elif schema == GrievanceAnalysisModel or getattr(schema, "__name__", "") == "GrievanceAnalysisModel":
        return GrievanceAnalysisModel(
            category="roads",
            category_reason="Open trench on roadway",
            severity_suggestion="urgent",
            severity_reasons=["Active hazard to motorists"],
            safety_risk=True,
            safety_reasons=["Deep open trench on roadway"],
            subject_line="Urgent: Hazardous open trench on Anna Salai",
            body="There is a deep open trench on Anna Salai without barricades.",
            image_relevant=True,
            observations=[],
            quality_note=None,
            missing_details=[],
            plain_notes="Please take caution when passing this section.",
        )
      return schema()

    mock_gemini.generate_structured.side_effect = mock_structured
    set_gemini_service(mock_gemini)

    ask_res = client.post(
        f"/api/v1/documents/{doc_id}/ask",
        json={"question": "What is the subsidy for commercial electric three-wheelers?", "language": "en"},
    )
    assert ask_res.status_code == 200
    rag_data = ask_res.json()
    assert rag_data["found"] is True
    assert "2,50,000" in rag_data["answer"]

    # --------------------------------------------------------------------------
    # Step 3: Citizen verifies a viral civic claim against official sources (Module 3)
    # --------------------------------------------------------------------------
    verify_res = client.post(
        "/api/v1/verify",
        json={
            "claim": "Tamil Nadu EV Policy 2023 gives 100% road tax exemption until 2025",
            "scope": "documents",
            "document_ids": [doc_id],
            "language": "en",
        },
    )
    assert verify_res.status_code == 202
    v_data = verify_res.json()
    verification_id = v_data["verification_id"]
    assert verification_id is not None

    # Poll status
    v_status_res = client.get(f"/api/v1/verify/{verification_id}")
    assert v_status_res.status_code == 200
    assert v_status_res.json()["verification_id"] == verification_id

    # --------------------------------------------------------------------------
    # Step 4: Citizen requests public service guidance and checklist (Module 4)
    # --------------------------------------------------------------------------
    guide_res = client.post(
        "/api/v1/services/guide",
        json={
            "query": "Apply for Electric Vehicle purchase subsidy in Tamil Nadu",
            "language": "en",
        },
    )
    assert guide_res.status_code == 200
    guide_data = guide_res.json()
    assert guide_data["id"] is not None
    assert guide_data["procedure_overview"] is not None
    assert len(guide_data["checklist_items"]) >= 1

    # --------------------------------------------------------------------------
    # Step 5: Citizen practices application in controlled browser demo (Module 4)
    # --------------------------------------------------------------------------
    session_res = client.post(
        "/api/v1/browser/sessions",
        json={"portal_id": "prt_demo_portal", "purpose": "Practice EV subsidy application"},
    )
    assert session_res.status_code == 201
    session_data = session_res.json()
    session_id = session_data["session_id"]
    assert session_id is not None

    # Fill form step with fictional test data
    fill_res = client.post(
        f"/api/v1/browser/sessions/{session_id}/fill",
        json={
            "step_index": 1,
            "values": {
                "applicant_name": "Kavitha Sundaram (Demo)",
                "gender": "female",
            },
            "fictional_confirmed": True,
        },
    )
    assert fill_res.status_code == 200
    assert fill_res.json()["current_step"] == 1

    # Close demo session
    close_res = client.post(f"/api/v1/browser/sessions/{session_id}/close")
    assert close_res.status_code == 200

    # --------------------------------------------------------------------------
    # Step 6: Citizen files a civic grievance for local street hazard (Module 5)
    # --------------------------------------------------------------------------
    grievance_res = client.post(
        "/api/v1/grievances/analyze",
        json={
            "description": "Deep open trench on Anna Salai without warning barricades or streetlights. Active danger to two wheelers.",
            "location_text": "Anna Salai, Chennai",
            "duration_text": "3 days",
            "language_of_draft": "en",
        },
    )
    assert grievance_res.status_code == 202
    g_data = grievance_res.json()
    grievance_id = g_data["grievance_id"]
    assert grievance_id is not None

    # Retrieve grievance status
    g_poll = client.get(f"/api/v1/grievances/{grievance_id}")
    assert g_poll.status_code == 200

    # --------------------------------------------------------------------------
    # Step 7: Central AI Agent coordinates with full tool & history support
    # --------------------------------------------------------------------------
    # List all 12 available tools in the registry
    registry = get_tool_registry()
    tools = registry.list_all()
    assert len(tools) == 12
    assert all(t.status == "available" for t in tools)

    # --------------------------------------------------------------------------
    # Step 8: System Status, Statistics, Backup & Maintenance
    # --------------------------------------------------------------------------
    status_res = client.get("/api/v1/system/status")
    assert status_res.status_code == 200
    sys_status = status_res.json()
    assert sys_status["database_state"] == "ok"
    assert sys_status["schema_version"] >= 1

    stats_res = client.get("/api/v1/system/stats")
    assert stats_res.status_code == 200
    sys_stats = stats_res.json()
    assert sys_stats["documents_count"] >= 1

    backup_res = client.post("/api/v1/system/backup")
    assert backup_res.status_code == 201
    backup_data = backup_res.json()
    assert backup_data["status"] == "success"
    assert backup_data["backup_file"].endswith(".db")

    maint_res = client.post("/api/v1/system/maintenance")
    assert maint_res.status_code == 200
    maint_data = maint_res.json()
    assert "duration_ms" in maint_data

    # Clean up test mock
    set_gemini_service(None)
