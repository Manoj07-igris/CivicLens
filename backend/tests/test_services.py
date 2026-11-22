"""Comprehensive test suite for Phase 12: Public Service Assistant (Module 4).

Tests:
1. PII Guard: Aadhaar, PAN, phone, email, accounts detection and false-positive protection.
2. Curated Portal Registry: URL validation, domain derivation, CRUD, management toggle, and deterministic matching.
3. Service Guide Engine: Zero-call guardrail, general mode, quote verification, fact verification, URL stripping.
4. Form Field Explainer: Candidate extraction, explanation basis tracking.
5. Agent Tool: generate_checklist execution, evidence ledger updating, intent derivation.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.errors import PIIDetectedError, PortalNotFoundError, ServiceGuideNotFoundError
from app.core.pii_guard import ensure_no_pii, find_pii
from app.main import app
from app.models.gemini import GeminiTokenUsage
from app.models.portal import (
    PortalCreateRequest,
    PortalEntry,
    PortalUpdateRequest,
)
from app.models.service_guide import (
    FormFieldCandidate,
    FormFieldExplainDraft,
    FormFieldExplainDraftItem,
    FormFieldExplainRequest,
    FormFieldExtractRequest,
    ServiceGuideDraft,
    ServiceGuideDraftItem,
    ServiceGuideDraftKeyFact,
    ServiceGuideReport,
    ServiceGuideRequest,
)
from app.services.form_field_service import FormFieldService
from app.services.gemini_service import GeminiService, GeminiToolResult, ToolCallItem, set_gemini_service
from app.services.portal_registry import (
    PortalRegistryService,
    PortalRegistryStore,
)
from app.services.public_service_service import (
    PublicServiceService,
    ServiceGuideStore,
)
from app.services.rag_service import RAGService
from tests.test_rag import FakeEmbeddingService, set_embedding_service


@pytest.fixture(autouse=True)
def fake_embedder():
  """Deterministic fake embedding service for fast, offline testing."""
  embedder = FakeEmbeddingService()
  set_embedding_service(embedder)
  yield embedder
  set_embedding_service(None)


# --- 1. PII Guard Unit Tests ---

def test_pii_guard_detects_sensitive_identifiers():
  """Verify PII Guard detects Aadhaar, PAN, phone, email, and long account digits."""
  # Aadhaar variations
  assert "aadhaar" in find_pii("My Aadhaar is 1234 5678 9012")
  assert "aadhaar" in find_pii("Card number 1234-5678-9012")
  assert "aadhaar" in find_pii("Aadhaar: 123456789012")

  # PAN
  assert "pan" in find_pii("Citizen PAN is ABCDE1234F")

  # Phone numbers
  assert "phone" in find_pii("Contact me at 9876543210")
  assert "phone" in find_pii("Mobile: +91 98765 43210")
  assert "phone" in find_pii("Call 09876543210")

  # Email
  assert "email" in find_pii("Email applicant@tamilnadu.gov.in")

  # Account / Card (16 digits or 13-19 digits)
  assert "account_or_card" in find_pii("Credit card 4111-2222-3333-4444")
  assert "account_or_card" in find_pii("Account number 12345678901234")


def test_pii_guard_false_positive_protection():
  """Verify standard calendar dates, rupee amounts, and scheme codes do NOT trigger PII."""
  clean_queries = [
      "How do I apply for widow pension? My income is Rs. 2,50,000 per year.",
      "Application fee is ₹500 or 10000 rupees as per citizen charter.",
      "Born on 12/05/1980 according to birth certificate.",
      "Applicable under government order G.O. Ms. No. 42 dated 2024-05-12.",
      "Applying for electric vehicle subsidy under scheme TN-EV-2024.",
      "Pradhan Mantri Awas Yojana scheme PMAY-G-2022 rural housing.",
      "Reference Section 42 of the Tamil Nadu Revenue Code.",
  ]

  for q in clean_queries:
    pii = find_pii(q)
    assert pii == [], f"False positive detected in: '{q}' -> {pii}"
    # ensure_no_pii must not raise
    ensure_no_pii(q, field_name="test_query")


def test_pii_guard_ensure_no_pii_raises_cleanly():
  """Verify ensure_no_pii raises PIIDetectedError without leaking values in message."""
  secret_phone = "9876543210"
  secret_aadhaar = "1234 5678 9012"
  query = f"Can I get scheme benefits with phone {secret_phone} and aadhaar {secret_aadhaar}?"

  with pytest.raises(PIIDetectedError) as exc_info:
    ensure_no_pii(query, field_name="citizen_query")

  err = exc_info.value
  assert err.code == "PII_DETECTED"
  assert err.status_code == 422
  # Must NOT echo the actual sensitive numbers
  assert secret_phone not in err.message
  assert secret_aadhaar not in err.message
  assert "phone" in err.message
  assert "aadhaar" in err.message


# --- 2. Curated Portal Registry Tests ---

def test_portal_registry_validation(tmp_path):
  """Verify URL validation rejects insecure protocols, credentials, and invalid hosts."""
  store = PortalRegistryStore()
  store._registry_file = tmp_path / "registry.json"
  svc = PortalRegistryService(store=store)

  # Insecure http URL on external host must fail
  with pytest.raises(ValueError, match="HTTPS"):
    PortalCreateRequest(
        name="Test Insecure",
        url="http://insecure.gov.in",
        description="Insecure portal",
    )

  # Credentials in URL must fail
  with pytest.raises(ValueError, match="credentials"):
    PortalCreateRequest(
        name="Test Creds",
        url="https://admin:password@portal.gov.in",
        description="Credentials portal",
    )

  # Valid HTTPS portal succeeds and derives domain hint
  req = PortalCreateRequest(
      name="TNeGA e-Sevai",
      name_ta="தமிழ்நாடு இ-சேவை",
      url="https://www.tnesevai.tn.gov.in/Citizen/Registration.aspx",
      description="Official portal for citizen certificates in Tamil Nadu",
      department="Revenue and Disaster Management",
      service_types=["revenue", "certificates", "income_certificate"],
      keywords=["tnega", "esevai", "income", "வருமானம்"],
      caution_notes="Requires Aadhaar OTP verification.",
  )
  entry = svc.create_portal(req)
  assert entry.id.startswith("prt_")
  assert entry.domain_hint == "www.tnesevai.tn.gov.in"
  assert entry.name == "TNeGA e-Sevai"

  # Retrieve portal
  fetched = svc.get_portal(entry.id)
  assert fetched.name == entry.name

  # Update portal
  up = svc.update_portal(entry.id, PortalUpdateRequest(name="Tamil Nadu e-Sevai Updated"))
  assert up.name == "Tamil Nadu e-Sevai Updated"

  # Delete portal
  assert svc.delete_portal(entry.id) is True
  with pytest.raises(PortalNotFoundError):
    svc.get_portal(entry.id)


def test_portal_registry_deterministic_matching(tmp_path):
  """Verify match_portals ranks by linked source overlap, service type, and keyword tokens."""
  store = PortalRegistryStore()
  store._registry_file = tmp_path / "registry.json"
  svc = PortalRegistryService(store=store)

  # Create two portals
  p1 = svc.create_portal(
      PortalCreateRequest(
          name="TNeGA e-Sevai Portal",
          url="https://tnesevai.tn.gov.in",
          description="Citizen certificates portal for income and community certificates",
          service_types=["income_certificate", "community_certificate"],
          linked_source_ids=["src_revenue_income"],
          keywords=["income", "certificate", "tnega", "வருமானம்"],
      )
  )

  p2 = svc.create_portal(
      PortalCreateRequest(
          name="TN Agriculture Portal",
          url="https://tnagrisnet.tn.gov.in",
          description="Subsidies and seeds for farmers in Tamil Nadu",
          service_types=["agriculture_subsidy", "farmer"],
          keywords=["farmer", "agriculture", "விவசாயி"],
      )
  )

  # Matching query with linked source
  matches = svc.match_portals(
      query="How do I get an income certificate?",
      linked_source_ids=["src_revenue_income"],
      limit=3,
  )
  assert len(matches) >= 1
  assert matches[0].portal.id == p1.id
  assert "Linked to cited official source" in matches[0].match_reason

  # Tamil query matching
  ta_matches = svc.match_portals(
      query="வருமான சான்றிதழ் பெறுவது எப்படி?",
      limit=3,
  )
  assert len(ta_matches) >= 1
  assert ta_matches[0].portal.id == p1.id


# --- 3. Public Service Guide Engine Tests ---

@pytest.mark.anyio
async def test_service_guide_zero_call_guardrail(tmp_path):
  """Verify zero Gemini calls when no official sources match and allow_general is False."""
  guide_store = ServiceGuideStore()
  guide_store._base_dir = tmp_path / "service_guides"
  guide_store._base_dir.mkdir(parents=True, exist_ok=True)

  # Mock empty RAG retrieve_across returning evidence_level='none'
  mock_rag = MagicMock(spec=RAGService)
  mock_rag.retrieve_across = AsyncMock(return_value=([], "none", []))

  mock_sources = MagicMock()
  mock_sources.list_sources.return_value = []
  mock_sources.store = MagicMock()

  mock_portals = MagicMock()
  mock_portals.match_portals.return_value = []

  mock_doc_store = MagicMock()
  mock_doc_store.list_documents.return_value = []

  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.generate_structured = AsyncMock()

  svc = PublicServiceService(
      store=guide_store,
      rag_service=mock_rag,
      source_service=mock_sources,
      portal_service=mock_portals,
      doc_store=mock_doc_store,
      gemini_service=mock_gemini,
  )

  req = ServiceGuideRequest(
      query="How to apply for solar pump subsidy?",
      allow_general=False,
      source_scope="official_only",
  )

  report = await svc.generate_guide(req)
  assert report.mode == "no_sources"
  assert report.offer_general_guidance is True
  assert len(report.checklist_items) == 0
  assert len(report.key_facts) == 0
  # Crucial guardrail: ZERO Gemini calls were made
  mock_gemini.generate_structured.assert_not_called()


@pytest.mark.anyio
async def test_service_guide_quote_verification_and_sanitization(tmp_path):
  """Verify items with exact verified quotes are source_confirmed, others needs_check, and URLs stripped."""
  guide_store = ServiceGuideStore()
  guide_store._base_dir = tmp_path / "service_guides"
  guide_store._base_dir.mkdir(parents=True, exist_ok=True)

  # Mock RAG returning 1 official passage
  passage_text = (
      "Applicants for Income Certificate must submit Ration Card and Salary Slip. "
      "The official application fee is Rs. 60 payable at the e-Sevai counter. "
      "Processing timeline is 15 working days."
  )
  mock_passages = [
      {
          "source_id": "src_rev_01",
          "title": "TN Revenue Citizen Charter",
          "collection": "official",
          "page_number": 3,
          "text": passage_text,
      }
  ]
  mock_rag = MagicMock(spec=RAGService)
  mock_rag.retrieve_across = AsyncMock(return_value=(mock_passages, "strong", []))

  mock_sources = MagicMock()
  mock_sources.list_sources.return_value = [
      MagicMock(source_id="src_rev_01", title="TN Revenue Citizen Charter", indexing_status="ready")
  ]
  mock_sources.store = MagicMock()

  mock_portals = MagicMock()
  mock_portals.match_portals.return_value = []

  mock_doc_store = MagicMock()
  mock_doc_store.list_documents.return_value = []

  # Mock Gemini structured output
  # Item 1 has verified quote
  # Item 2 has hallucinated quote
  # Item 3 tries to output a URL (must be stripped)
  draft = ServiceGuideDraft(
      procedure_overview="Apply online at https://fake-phishing.com or e-Sevai.",
      checklist_items=[
          ServiceGuideDraftItem(
              category="documents",
              text="Provide Ration Card and Salary Slip.",
              source_label="[S1]",
              source_page=3,
              source_quote="Ration Card and Salary Slip",
          ),
          ServiceGuideDraftItem(
              category="steps",
              text="Pay bribe of Rs 500 to clerk.",
              source_label="[S1]",
              source_page=3,
              source_quote="bribe of Rs 500",  # Hallucinated quote
          ),
          ServiceGuideDraftItem(
              category="steps",
              text="Check status on https://malicious-link.in or call 9876543210",
              source_label=None,
              source_quote=None,
          ),
      ],
      key_facts=[
          ServiceGuideDraftKeyFact(
              fact_type="fee",
              label="Application Fee",
              value_text="Rs. 60",
              source_label="[S1]",
              source_quote="fee is Rs. 60",
              page_number=3,
          ),
          ServiceGuideDraftKeyFact(
              fact_type="fee",
              label="Processing Fee",
              value_text="Rs. 1000",  # Hallucinated fee not in text
              source_label="[S1]",
              source_quote="fee is Rs. 1000",
              page_number=3,
          ),
      ],
  )

  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.generate_structured = AsyncMock(return_value=(draft, GeminiTokenUsage(prompt_tokens=50, candidates_tokens=50, total_tokens=100)))

  svc = PublicServiceService(
      store=guide_store,
      rag_service=mock_rag,
      source_service=mock_sources,
      portal_service=mock_portals,
      doc_store=mock_doc_store,
      gemini_service=mock_gemini,
  )

  req = ServiceGuideRequest(
      query="How to apply for income certificate?",
      applicant_type="unspecified",
      allow_general=False,
  )

  report = await svc.generate_guide(req)
  assert report.mode == "source_grounded"
  assert len(report.checklist_items) == 3

  # Item 1: verified quote -> source_confirmed
  item1 = report.checklist_items[0]
  assert item1.status == "source_confirmed"
  assert item1.source_label == "[S1]"
  assert item1.source_page == 3
  assert item1.source_quote == "Ration Card and Salary Slip"

  # Item 2: hallucinated quote -> demoted to needs_check
  item2 = report.checklist_items[1]
  assert item2.status == "needs_check"
  assert item2.source_label is None
  assert item2.source_quote is None

  # Item 3: model URL and contact stripped
  item3 = report.checklist_items[2]
  assert item3.status == "needs_check"
  assert "[link removed]" in item3.text
  assert "[contact removed]" in item3.text
  assert "https://malicious-link.in" not in item3.text
  assert "9876543210" not in item3.text

  # Overview: URL stripped
  assert "[link removed]" in report.procedure_overview
  assert "https://fake-phishing.com" not in report.procedure_overview

  # Key facts: Verified fact kept, hallucinated fact discarded
  assert len(report.key_facts) == 1
  assert report.key_facts[0].value_text == "Rs. 60"


@pytest.mark.anyio
async def test_service_guide_general_mode(tmp_path):
  """Verify general guidance mode marks all items general_unverified and discards key facts."""
  guide_store = ServiceGuideStore()
  guide_store._base_dir = tmp_path / "service_guides"
  guide_store._base_dir.mkdir(parents=True, exist_ok=True)

  mock_rag = MagicMock(spec=RAGService)
  mock_rag.retrieve_across = AsyncMock(return_value=([], "none", []))

  mock_sources = MagicMock()
  mock_sources.list_sources.return_value = []
  mock_sources.store = MagicMock()

  mock_portals = MagicMock()
  mock_portals.match_portals.return_value = []

  mock_doc_store = MagicMock()
  mock_doc_store.list_documents.return_value = []

  draft = ServiceGuideDraft(
      procedure_overview="General procedure for applying at Tahsildar office.",
      checklist_items=[
          ServiceGuideDraftItem(
              category="documents",
              text="Family ration card or Aadhaar card.",
          ),
          ServiceGuideDraftItem(
              category="steps",
              text="Submit at nearest e-Sevai counter.",
          ),
      ],
      key_facts=[
          ServiceGuideDraftKeyFact(
              fact_type="fee",
              label="Estimated Fee",
              value_text="₹60",
          )
      ],
  )

  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.generate_structured = AsyncMock(return_value=(draft, None))

  svc = PublicServiceService(
      store=guide_store,
      rag_service=mock_rag,
      source_service=mock_sources,
      portal_service=mock_portals,
      doc_store=mock_doc_store,
      gemini_service=mock_gemini,
  )

  req = ServiceGuideRequest(
      query="How do I get a legal heir certificate?",
      allow_general=True,
  )

  report = await svc.generate_guide(req)
  assert report.mode == "general_guidance"
  assert len(report.checklist_items) == 2
  for itm in report.checklist_items:
    assert itm.status == "general_unverified"
    assert itm.source_label is None
    assert itm.source_quote is None

  # Key facts in general mode are discarded to prevent hallucinated fees
  assert len(report.key_facts) == 0


# --- 4. Form Field Explainer Tests ---

@pytest.mark.anyio
async def test_form_field_extraction_and_explanation():
  """Verify form field extraction heuristics and basis verification (stated_in_form_text vs general_knowledge)."""
  svc = FormFieldService()

  raw_form = (
      "Application Form for Community Certificate\n"
      "1. Name of Applicant: __________________\n"
      "2. Father's / Husband's Name: ___________\n"
      "3. Date of Birth: _____________________\n"
      "4. Community / Caste: __________________\n"
      "Note: Community must match the transfer certificate issued by school."
  )

  # Extraction
  ext_req = FormFieldExtractRequest(raw_text=raw_form)
  ext_res = svc.extract_fields(ext_req)
  assert ext_res.total_detected >= 3
  field_names = [f.name.lower() for f in ext_res.fields]
  assert any("name of applicant" in fn for fn in field_names)
  assert any("community" in fn or "caste" in fn for fn in field_names)

  # Mock explanation
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.generate_structured = AsyncMock(
      return_value=(
          FormFieldExplainDraft(
              explanations=[
                  FormFieldExplainDraftItem(
                      field_name="Community / Caste",
                      plain_explanation="Your recognized social category (BC, MBC, SC, ST).",
                      where_to_find="Check your parent's community certificate or school TC.",
                      basis="stated_in_form_text",
                      quote_from_form="Community must match the transfer certificate",
                  ),
                  FormFieldExplainDraftItem(
                      field_name="Father's / Husband's Name",
                      plain_explanation="Full name of your father or husband.",
                      where_to_find="As written on your Aadhaar card or birth certificate.",
                      basis="stated_in_form_text",
                      quote_from_form="This quote does not exist in form",  # Hallucinated quote
                  ),
              ]
          ),
          None,
      )
  )
  svc._gemini = mock_gemini

  exp_req = FormFieldExplainRequest(
      field_names=["Community / Caste", "Father's / Husband's Name"],
      context_text=raw_form,
  )
  exp_res = await svc.explain_fields(exp_req)
  assert len(exp_res.explanations) == 2

  # Field 1: quote exists -> stated_in_form_text
  assert exp_res.explanations[0].basis == "stated_in_form_text"
  assert exp_res.explanations[0].quote_from_form == "Community must match the transfer certificate"

  # Field 2: quote was hallucinated -> downgraded to general_knowledge
  assert exp_res.explanations[1].basis == "general_knowledge"
  assert exp_res.explanations[1].quote_from_form is None


# --- 5. Agent Tool generate_checklist Test ---

def test_agent_tool_generate_checklist():
  """Verify generate_checklist agent tool execution, evidence ledger update, and intent setting."""
  from app.services.public_service_service import set_public_service_service

  mock_ps = MagicMock()
  mock_report = ServiceGuideReport(
      id="gde_test_123",
      query="income certificate application",
      applicant_type="student",
      language="en",
      mode="source_grounded",
      status="ready",
      procedure_overview="Apply online at e-Sevai portal.",
      checklist_items=[],
      key_facts=[],
      cited_sources=[],
      matched_portals=[],
      disclaimers=[],
      offer_general_guidance=False,
      created_at="2026-11-21T00:00:00Z",
  )
  mock_ps.generate_guide = AsyncMock(return_value=mock_report)
  set_public_service_service(mock_ps)

  client = TestClient(app)

  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True

  # Step 1: Model calls generate_checklist
  # Step 2: Model replies using the checklist
  mock_gemini.generate_with_tools = AsyncMock(
      side_effect=[
          GeminiToolResult(
              model="gemini-2.5-flash",
              text=None,
              tool_calls=[
                  ToolCallItem(
                      name="generate_checklist",
                      args={"query": "income certificate application", "applicant_type": "student"},
                  )
              ],
          ),
          GeminiToolResult(
              model="gemini-2.5-flash",
              text="Here is your checklist for income certificate application. You need your Ration Card and Salary Slip.",
              tool_calls=[],
          ),
      ]
  )
  set_gemini_service(mock_gemini)

  res = client.post("/api/v1/agent/chat", json={"message": "How do I apply for income certificate as a student?"})
  assert res.status_code == 200
  data = res.json()

  assert data["intent"] == "public_service_guidance"
  assert len(data["checklists"]) == 1
  assert data["checklists"][0]["query"] != ""
  assert len(data["tool_activity"]) == 1
  assert data["tool_activity"][0]["tool_name"] == "generate_checklist"
  assert data["tool_activity"][0]["status"] == "success"

  set_public_service_service(None)
  set_gemini_service(None)
