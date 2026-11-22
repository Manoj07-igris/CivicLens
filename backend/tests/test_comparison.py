"""Comprehensive test suite for Phase 10: Policy Change Detection (Module 2).

Tests:
1. Deterministic normalization (Unicode, Indian numbers, Tamil digits, headers/footers)
2. Clause segmentation and alignment
3. Token-level diffing (word diff)
4. Exact fact extraction (amounts, dates, percentages, ages)
5. Importance scoring and noise filtering (moved, formatting_only -> minor_differences)
6. Gemini structured batch analysis and backend validation
7. Deterministic override (never drop fact changes)
8. Caching and deduplication
9. REST API endpoints (/api/v1/compare, /api/v1/compare/{id}, retry, delete, list)
10. Central Agent integration (compare_documents tool, [C1] dual citations, intent)
"""

import io
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import fitz

from app.main import app
from app.core.config import get_settings
from app.models.comparison import (
    BatchAnalysisResult,
    CandidateAnalysis,
    CompareRequest,
    ComparisonReport,
)
from app.services.comparison_service import (
    AlignedPair,
    ComparisonService,
    Segment,
    align_segments,
    compute_fact_changes,
    compute_word_diff,
    extract_facts_from_text,
    normalize_text_for_comparison,
    segment_document,
    set_comparison_service,
    strip_repeated_headers_and_footers,
)
from app.services.comparison_store import ComparisonStore, set_comparison_store
from app.services.document_service import DocumentService, reset_upload_rate_limit, set_document_service
from app.services.document_store import DocumentStore, get_document_store, set_document_store
from app.services.gemini_service import GeminiService, set_gemini_service
from app.agent.orchestrator import AgentOrchestrator, set_agent_orchestrator
from app.agent.tools import set_tool_registry
from app.api.comparison import reset_compare_rate_limit
from tests.test_rag import FakeEmbeddingService, set_embedding_service


def create_in_memory_pdf(pages: list[str]) -> bytes:
  """Helper to generate a valid PDF byte string in memory."""
  doc = fitz.open()
  for page_text in pages:
    page = doc.new_page()
    page.insert_text((50, 72), page_text, fontsize=11)
  pdf_bytes = doc.tobytes()
  doc.close()
  return pdf_bytes


@pytest.fixture
def temp_store(tmp_path):
  """Isolated DocumentStore and ComparisonStore in a temporary directory."""
  store = DocumentStore(base_dir=tmp_path / "uploads", indexes_dir=tmp_path / "indexes")
  set_document_store(store)
  set_document_service(None)
  comp_store = ComparisonStore(base_dir=tmp_path / "comparisons")
  set_comparison_store(comp_store)
  set_comparison_service(None)
  yield store
  set_document_store(None)
  set_document_service(None)
  set_comparison_store(None)
  set_comparison_service(None)


@pytest.fixture
def fake_embedder():
  """Fake embedder for offline test runs."""
  embedder = FakeEmbeddingService()
  set_embedding_service(embedder)
  yield embedder
  set_embedding_service(None)


@pytest.fixture(autouse=True)
def reset_all_state(temp_store, fake_embedder):
  """Reset all service singletons and rate limits before each test."""
  reset_compare_rate_limit()
  reset_upload_rate_limit()
  set_agent_orchestrator(None)
  set_tool_registry(None)
  yield
  reset_compare_rate_limit()
  reset_upload_rate_limit()
  set_agent_orchestrator(None)
  set_tool_registry(None)
  set_gemini_service(None)


# --- 1. Normalization & Preprocessing Tests ---

def test_normalization_indian_numbers():
  """Verify Indian number separators (e.g. 2,50,000) normalize to western digits (250000)."""
  text = "The annual income limit is Rs. 2,50,000 and the grant is Rs. 1,000."
  normalized = normalize_text_for_comparison(text)
  assert "250000" in normalized
  assert "1000" in normalized
  assert "2,50,000" not in normalized


def test_normalization_tamil_digits():
  """Verify Tamil numerals convert to standard Arabic digits."""
  text = "வழங்கப்படும் தொகை ௧000 ரூபாய் (ஆண்டு வரம்பு ௨,௫0,000)."
  normalized = normalize_text_for_comparison(text)
  assert "1000" in normalized
  assert "250000" in normalized


def test_normalization_dashes_quotes_hyphenation():
  """Verify typography fixes: smart quotes, em-dashes, and hyphenation unwrapping."""
  text = "The “eligible” families—who are sub-\nject to rules—shall receive benefits."
  normalized = normalize_text_for_comparison(text)
  assert '"eligible"' in normalized
  assert "families-who" in normalized
  assert "subject to rules" in normalized


def test_strip_running_headers_footers():
  """Verify repeated headers or page numbers across multiple pages are stripped."""
  pages = [
      {"page_number": 1, "text": "GOVERNMENT OF TAMIL NADU\nDEPARTMENT OF SOCIAL WELFARE\nPage 1 of 3\n\n1. Scheme introduction."},
      {"page_number": 2, "text": "GOVERNMENT OF TAMIL NADU\nDEPARTMENT OF SOCIAL WELFARE\nPage 2 of 3\n\n2. Eligibility criteria."},
      {"page_number": 3, "text": "GOVERNMENT OF TAMIL NADU\nDEPARTMENT OF SOCIAL WELFARE\nPage 3 of 3\n\n3. Application process."},
  ]
  cleaned = strip_repeated_headers_and_footers(pages)
  assert len(cleaned) == 3
  assert "GOVERNMENT OF TAMIL NADU" not in cleaned[0]["text"]
  assert "1. Scheme introduction." in cleaned[0]["text"]
  assert "2. Eligibility criteria." in cleaned[1]["text"]


# --- 2. Clause Segmentation Tests ---

def test_segment_into_clauses_english():
  """Verify clause segmentation on numbered government orders."""
  text = """1. Short Title and Commencement: This order shall be called the Welfare Order 2023.

2. Eligibility Criteria:
(a) The family annual income must not exceed Rs. 2,50,000.
(b) The beneficiary must be at least 21 years of age.

3. Benefit Amount: Rs. 1000 per month."""
  
  pages = [{"page_number": 1, "text": text}]
  segments = segment_document("doc_test", "test.pdf", pages, set())
  assert len(segments) >= 3
  seg_texts = " ".join(s.original_text for s in segments)
  assert "Short Title" in seg_texts
  assert "Eligibility Criteria" in seg_texts
  assert "Benefit Amount" in seg_texts


def test_segment_into_clauses_tamil():
  """Verify clause segmentation works on Tamil text with standard punctuation."""
  text = """1. திட்டத்தின் பெயர்: மகளிர் உரிமைத் தொகை திட்டம் 2023.

2. தகுதி வரம்புகள்:
(அ) ஆண்டு வருமானம் ரூ. 2,50,000 க்குள் இருக்க வேண்டும்.
(ஆ) குறைந்தபட்ச வயது 21 ஆண்டுகள்.

3. உதவித் தொகை: மாதம் ரூ. 1000."""
  
  pages = [{"page_number": 1, "text": text}]
  segments = segment_document("doc_ta", "test_ta.pdf", pages, set())
  assert len(segments) >= 3


# --- 3. Word-Level Token Diffing Tests ---

def test_compute_word_diff():
  """Verify word diff generates correct sequence of equal, added, removed tokens."""
  old_str = "Income limit is 250000 rupees"
  new_str = "Income limit is 300000 rupees only"
  diff_ops = compute_word_diff(old_str, new_str)
  
  ops_dict = [op.model_dump() for op in diff_ops]
  # Should have removed '250000' and added '300000' and 'only'
  removed = [op["old_text"] for op in ops_dict if op["op"] in ("delete", "replace")]
  added = [op["new_text"] for op in ops_dict if op["op"] in ("insert", "replace")]
  
  assert any("250000" in r for r in removed)
  assert any("300000" in a for a in added)


# --- 4. Deterministic Fact Extraction Tests ---

def test_extract_deterministic_facts():
  """Verify extraction of amounts, dates, percentages, and ages."""
  text = "From 01.04.2024, grant of Rs. 1000 increases by 15% for citizens aged 60 years."
  facts = extract_facts_from_text(text)
  
  assert any("1000" in a for a in facts["amount"])
  assert any("01.04.2024" in d for d in facts["date"])
  assert any("15" in p for p in facts["percentage"])
  assert any("60" in a for a in facts["age"])


def test_extract_fact_changes():
  """Verify comparison of old and new text extracts precise numeric delta."""
  old_text = "The monthly allowance is Rs. 1000 for applicants aged 21 years."
  new_text = "The monthly allowance is Rs. 1500 for applicants aged 18 years."
  changes = compute_fact_changes(old_text, new_text)
  
  types = [c.fact_type for c in changes]
  assert "amount" in types
  assert "age" in types
  
  amt_change = next(c for c in changes if c.fact_type == "amount")
  assert "1000" in amt_change.old_value
  assert "1500" in amt_change.new_value


# --- 5. Clause Alignment and Noise Filtering Tests ---

def test_alignment_noise_filtering():
  """Verify formatting changes and moved clauses are separated into minor differences."""
  old_segs = [
      Segment(
          segment_id="s1", document_id="d1", document_name="d1.pdf",
          page_start=1, page_end=1, char_start=0, char_end=50,
          original_text="Section 1: General rules and conditions for welfare grants.",
          canonical_text="section 1 general rules and conditions for welfare grants",
      ),
      Segment(
          segment_id="s2", document_id="d1", document_name="d1.pdf",
          page_start=1, page_end=1, char_start=0, char_end=50,
          original_text="Section 2: Payment shall be made via NEFT on the 1st of every month.",
          canonical_text="section 2 payment shall be made via neft on the 1st of every month",
      ),
      Segment(
          segment_id="s3", document_id="d1", document_name="d1.pdf",
          page_start=1, page_end=1, char_start=0, char_end=50,
          original_text="Section 3: Income limit is 250000 rupees.",
          canonical_text="section 3 income limit is 250000 rupees",
      ),
  ]
  new_segs = [
      Segment(
          segment_id="ns1", document_id="d2", document_name="d2.pdf",
          page_start=1, page_end=1, char_start=0, char_end=50,
          original_text="Section 1:   General rules and conditions for welfare grants.  ",
          canonical_text="section 1 general rules and conditions for welfare grants",
      ),
      Segment(
          segment_id="ns3", document_id="d2", document_name="d2.pdf",
          page_start=1, page_end=1, char_start=0, char_end=50,
          original_text="Section 3: Income limit is 300000 rupees.",
          canonical_text="section 3 income limit is 300000 rupees",
      ),
      Segment(
          segment_id="ns2", document_id="d2", document_name="d2.pdf",
          page_start=2, page_end=2, char_start=0, char_end=50,
          original_text="Section 2: Payment shall be made via NEFT on the 1st of every month.",
          canonical_text="section 2 payment shall be made via neft on the 1st of every month",
      ),
  ]
  
  pairs, overlap = align_segments(old_segs, new_segs, similarity_threshold=0.55)
  
  statuses = [p.status for p in pairs]
  assert "formatting_only" in statuses
  assert "modified" in statuses


# --- 6. End-to-End Comparison Engine & REST API Tests ---

def test_compare_preconditions(temp_store):
  """Verify self-comparison and non-existent IDs are rejected with appropriate HTTP status."""
  client = TestClient(app)
  
  # Upload single doc
  pdf = create_in_memory_pdf(["Sample policy document."])
  res = client.post("/api/v1/documents/upload", files={"file": ("doc.pdf", io.BytesIO(pdf), "application/pdf")})
  doc_id = res.json()["document_id"]
  DocumentService(store=temp_store).process_document(doc_id)
  
  # Self comparison rejected
  res_self = client.post("/api/v1/compare", json={"old_document_id": doc_id, "new_document_id": doc_id})
  assert res_self.status_code == 422
  assert "different documents" in str(res_self.json()).lower()
  
  # Non-existent doc rejected
  fake_id = "00000000-0000-0000-0000-000000000000"
  res_missing = client.post("/api/v1/compare", json={"old_document_id": doc_id, "new_document_id": fake_id})
  assert res_missing.status_code == 404


def test_compare_end_to_end_mocked_gemini(temp_store):
  """Verify full comparison workflow with mock Gemini structured output."""
  client = TestClient(app)
  doc_service = DocumentService(store=temp_store)
  
  # Create Old Doc
  old_pdf = create_in_memory_pdf([
      "TAMIL NADU WELFARE ORDER 2023\n1. Income ceiling: Rs. 2,50,000.\n2. Age limit: 21 years.\n3. Monthly allowance: Rs. 1000."
  ])
  res_old = client.post("/api/v1/documents/upload", files={"file": ("order_2023.pdf", io.BytesIO(old_pdf), "application/pdf")})
  old_id = res_old.json()["document_id"]
  doc_service.process_document(old_id)
  
  # Create New Doc
  new_pdf = create_in_memory_pdf([
      "TAMIL NADU WELFARE ORDER 2024\n1. Income ceiling: Rs. 3,00,000.\n2. Age limit: 18 years.\n3. Monthly allowance: Rs. 1500."
  ])
  res_new = client.post("/api/v1/documents/upload", files={"file": ("order_2024.pdf", io.BytesIO(new_pdf), "application/pdf")})
  new_id = res_new.json()["document_id"]
  doc_service.process_document(new_id)
  
  # Mock Gemini structured call
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True
  
  mock_gemini.generate_structured = AsyncMock(
      return_value=BatchAnalysisResult(
          candidates=[
              CandidateAnalysis(
                  candidate_id="chg_1",  # Matches backend change_id 'chg_1'
                  plain_summary="Income ceiling raised from Rs. 2,50,000 to Rs. 3,00,000.",
                  category="amount_benefit",
                  importance="high",
                  practical_impact="More families can now qualify for the welfare scheme.",
                  change_type_confirmation="modified",
                  is_material=True,
              ),
              CandidateAnalysis(
                  candidate_id="chg_2",
                  plain_summary="Age limit lowered from 21 years to 18 years.",
                  category="eligibility",
                  importance="high",
                  practical_impact="Younger women are now eligible.",
                  change_type_confirmation="modified",
                  is_material=True,
              ),
              CandidateAnalysis(
                  candidate_id="chg_999",  # Hallucinated candidate ID
                  plain_summary="This candidate does not exist in backend alignment.",
                  category="other",
                  importance="low",
                  practical_impact="None",
                  change_type_confirmation="modified",
                  is_material=True,
              ),
          ]
      )
  )
  set_gemini_service(mock_gemini)
  
  # Start comparison
  comp_service = ComparisonService(document_store=temp_store, gemini_service=mock_gemini)
  report = comp_service.run_comparison_sync(old_document_id=old_id, new_document_id=new_id, language="en")
  
  assert report.status == "completed"
  assert report.counts.modified >= 1
  assert len(report.changes) >= 1
  
  # Check hallucinated chg_999 is dropped
  c_ids = [c.change_id for c in report.changes]
  assert "chg_999" not in c_ids
  assert report.changes[0].analysis_state == "analysed"
  
  # Check fact changes are populated deterministically
  has_fact_change = any(len(c.fact_changes) > 0 for c in report.changes)
  assert has_fact_change is True
  
  # Test caching: second run must return cached report without calling Gemini again
  mock_gemini.generate_structured.reset_mock()
  cached_report = comp_service.run_comparison_sync(old_document_id=old_id, new_document_id=new_id, language="en")
  assert cached_report.comparison_id == report.comparison_id
  mock_gemini.generate_structured.assert_not_called()


def test_deterministic_override_on_fact_change(temp_store):
  """Verify that if Gemini marks a candidate not_material, but facts changed, it is kept with flag."""
  doc_service = DocumentService(store=temp_store)
  
  old_pdf = create_in_memory_pdf(["Monthly grant: Rs. 1000."])
  res_old = TestClient(app).post("/api/v1/documents/upload", files={"file": ("old.pdf", io.BytesIO(old_pdf), "application/pdf")})
  old_id = res_old.json()["document_id"]
  doc_service.process_document(old_id)
  
  new_pdf = create_in_memory_pdf(["Monthly grant: Rs. 1500."])
  res_new = TestClient(app).post("/api/v1/documents/upload", files={"file": ("new.pdf", io.BytesIO(new_pdf), "application/pdf")})
  new_id = res_new.json()["document_id"]
  doc_service.process_document(new_id)
  
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True
  
  # LLM erroneously marks this as not material
  mock_gemini.generate_structured = AsyncMock(
      return_value=BatchAnalysisResult(
          candidates=[
              CandidateAnalysis(
                  candidate_id="chg_1",
                  plain_summary="Grant amount text changed.",
                  category="amount_benefit",
                  importance="low",
                  practical_impact="None",
                  change_type_confirmation="not_material",
                  is_material=False,  # Erroneously marked non-material
              )
          ]
      )
  )
  set_gemini_service(mock_gemini)
  
  comp_service = ComparisonService(document_store=temp_store, gemini_service=mock_gemini)
  report = comp_service.run_comparison_sync(old_document_id=old_id, new_document_id=new_id, language="en")
  
  # Backend MUST override and retain the item because fact_changes contains an amount delta
  assert len(report.changes) == 1
  assert report.changes[0].ai_flagged_minor_but_facts_changed is True


def test_comparison_api_endpoints(temp_store):
  """Verify REST API: list, delete, and retrieve comparisons."""
  client = TestClient(app)
  doc_service = DocumentService(store=temp_store)
  
  p1 = create_in_memory_pdf(["Clause 1: Rules."])
  p2 = create_in_memory_pdf(["Clause 1: Updated rules."])
  r1 = client.post("/api/v1/documents/upload", files={"file": ("d1.pdf", io.BytesIO(p1), "application/pdf")})
  r2 = client.post("/api/v1/documents/upload", files={"file": ("d2.pdf", io.BytesIO(p2), "application/pdf")})
  id1 = r1.json()["document_id"]
  id2 = r2.json()["document_id"]
  doc_service.process_document(id1)
  doc_service.process_document(id2)
  
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True
  mock_gemini.generate_structured = AsyncMock(
      return_value=BatchAnalysisResult(candidates=[])
  )
  set_gemini_service(mock_gemini)
  
  # Initiate comparison via POST /api/v1/compare
  res_post = client.post("/api/v1/compare", json={"old_document_id": id1, "new_document_id": id2, "language": "en"})
  assert res_post.status_code in (200, 202)
  job_data = res_post.json()
  comp_id = job_data["comparison_id"]
  
  # GET /api/v1/compare/{id}
  res_get = client.get(f"/api/v1/compare/{comp_id}")
  assert res_get.status_code == 200
  assert res_get.json()["comparison_id"] == comp_id
  
  # GET /api/v1/compare (list)
  res_list = client.get("/api/v1/compare")
  assert res_list.status_code == 200
  assert any(c["comparison_id"] == comp_id for c in res_list.json()["comparisons"])
  
  # DELETE /api/v1/compare/{id}
  res_del = client.delete(f"/api/v1/compare/{comp_id}")
  assert res_del.status_code == 200
  assert res_del.json()["deleted"] is True
  
  # GET after delete -> 404
  res_get_del = client.get(f"/api/v1/compare/{comp_id}")
  assert res_get_del.status_code == 404


# --- 7. Agent Integration: compare_documents tool ---

def test_agent_tool_compare_documents(temp_store):
  """Verify the central agent can invoke compare_documents and cite [C1] with dual page numbers."""
  client = TestClient(app)
  doc_service = DocumentService(store=temp_store)
  
  p1 = create_in_memory_pdf(["Old rule: grant is 1000 rupees."])
  p2 = create_in_memory_pdf(["New rule: grant is 1500 rupees."])
  r1 = client.post("/api/v1/documents/upload", files={"file": ("old.pdf", io.BytesIO(p1), "application/pdf")})
  r2 = client.post("/api/v1/documents/upload", files={"file": ("new.pdf", io.BytesIO(p2), "application/pdf")})
  id1 = r1.json()["document_id"]
  id2 = r2.json()["document_id"]
  doc_service.process_document(id1)
  doc_service.process_document(id2)
  
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True
  
  # 1. Comparison engine structured call
  mock_gemini.generate_structured = AsyncMock(
      return_value=BatchAnalysisResult(
          candidates=[
              CandidateAnalysis(
                  candidate_id="cand_1",
                  plain_summary="Grant increased from 1000 to 1500.",
                  category="amount_benefit",
                  importance="high",
                  practical_impact="Beneficiaries receive 500 more per month.",
                  change_type_confirmation="modified",
                  is_material=True,
              )
          ]
      )
  )
  
  # 2. Agent tool calling loop
  from app.services.gemini_service import GeminiToolResult, ToolCallItem
  mock_gemini.generate_with_tools = AsyncMock(
      side_effect=[
          GeminiToolResult(
              model="gemini-2.5-flash",
              text=None,
              tool_calls=[
                  ToolCallItem(
                      name="compare_documents",
                      args={"old_document_id": id1, "new_document_id": id2},
                  )
              ],
          ),
          GeminiToolResult(
              model="gemini-2.5-flash",
              text="The grant amount was increased from 1000 to 1500 rupees [C1].",
              tool_calls=[],
          ),
      ]
  )
  set_gemini_service(mock_gemini)
  
  res = client.post(
      "/api/v1/agent/chat",
      json={
          "message": "Compare these two orders",
          "document_ids": [id1, id2],
          "language": "en",
      },
  )
  assert res.status_code == 200
  data = res.json()
  
  assert data["intent"] == "policy_comparison"
  assert len(data["sources"]) == 1
  src = data["sources"][0]
  assert src["source_id"] == "C1"
  assert src["old_document_id"] == id1
  assert src["new_document_id"] == id2
  assert src["old_page_number"] == 1
  assert src["new_page_number"] == 1
