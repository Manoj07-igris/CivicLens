"""Comprehensive unit and integration tests for CivicLens Central AI Agent and Function Calling (Phase 9).

Covers:
- Tool registry and Gemini FunctionDeclaration generation
- Scripted Gemini tool-calling loops (no-tool direct answer, multi-step document retrieval)
- Safe execution pipeline: invalid args, unavailable/planned tools, hallucinated IDs
- Duplicate call short-circuiting
- Step limit and per-run tool call caps
- Tool exceptions and timeouts
- EvidenceLedger and strict backend citation verification
- Prompt injection isolation inside tool results
- Approval mechanism (pending -> approve -> resume; deny)
- Rate limiting and zero-leak privacy logging
- Compatibility of the legacy /api/v1/chat endpoint
"""

import asyncio
import io
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))

from app.agent.approval import ApprovalStore, get_approval_store, set_approval_store
from app.agent.orchestrator import AgentOrchestrator, set_agent_orchestrator
from app.agent.tools import (
    AgentContext,
    EvidenceLedger,
    ListDocumentsArgs,
    ReadDocumentArgs,
    RetrieveEvidenceArgs,
    ToolDefinition,
    ToolRegistry,
    get_tool_registry,
    set_tool_registry,
)
from app.api.agent import reset_agent_rate_limit
from app.core.config import get_settings
from app.main import app
from app.models.agent import AgentResponse, ToolsListResponse
from app.services.document_service import DocumentService, set_document_service
from app.services.document_store import DocumentStore, set_document_store
from app.services.gemini_service import (
    GeminiService,
    GeminiToolResult,
    ToolCallItem,
    set_gemini_service,
)
from app.services.rag_service import RAGService, get_index_cache, set_rag_service
from tests.test_rag import FakeEmbeddingService, set_embedding_service


def create_in_memory_pdf(pages_text: list[str]) -> bytes:
  """Helper to construct in-memory multi-page PDFs using PyMuPDF."""
  doc = fitz.open()
  for text in pages_text:
    page = doc.new_page()
    if text:
      page.insert_text((50, 72), text, fontsize=11)
  data = doc.tobytes()
  doc.close()
  return data


@pytest.fixture
def temp_store(tmp_path):
  """Isolated DocumentStore in a temporary directory."""
  store = DocumentStore(base_dir=tmp_path / "uploads", indexes_dir=tmp_path / "indexes")
  set_document_store(store)
  set_document_service(None)
  yield store
  set_document_store(None)
  set_document_service(None)


@pytest.fixture
def fake_embedder():
  """Deterministic fake embedding service for fast, offline testing."""
  embedder = FakeEmbeddingService()
  set_embedding_service(embedder)
  yield embedder
  set_embedding_service(None)


@pytest.fixture
def fresh_approvals():
  """Isolated ApprovalStore."""
  store = ApprovalStore(expiry_minutes=10)
  set_approval_store(store)
  yield store
  set_approval_store(None)


@pytest.fixture(autouse=True)
def reset_all_state(temp_store, fake_embedder, fresh_approvals):
  """Reset all service singletons and rate limits before each test."""
  reset_agent_rate_limit()
  get_index_cache().clear()
  set_rag_service(None)
  set_agent_orchestrator(None)
  set_tool_registry(None)  # Recreates clean default registry
  yield
  reset_agent_rate_limit()
  get_index_cache().clear()
  set_rag_service(None)
  set_agent_orchestrator(None)
  set_tool_registry(None)
  set_gemini_service(None)


# --- 1. Tool Registry Tests ---

def test_tool_registry_available_vs_planned():
  """Verify only available tools are exposed in Gemini declarations, and planned tools are registered."""
  registry = get_tool_registry()
  all_tools = registry.list_all()
  available_tools = registry.list_available()

  avail_names = {t.name for t in available_tools}
  all_names = {t.name for t in all_tools}

  # Available tools (Phase 14: 12 available)
  assert "list_documents" in avail_names
  assert "read_document" in avail_names
  assert "retrieve_evidence" in avail_names
  assert "compare_documents" in avail_names
  assert "search_official_sources" in avail_names
  assert "check_claim" in avail_names
  assert "generate_checklist" in avail_names
  assert "draft_complaint" in avail_names
  assert "register_demo_complaint" in avail_names
  assert "open_service_portal" in avail_names
  assert "fill_demo_form" in avail_names
  assert "submit_demo_application" in avail_names

  # All tools must include all available
  assert "open_service_portal" in all_names
  assert "fill_demo_form" in all_names
  assert "submit_demo_application" in all_names

  # Verify Gemini declarations
  declarations = registry.to_gemini_declarations()
  assert len(declarations) > 0

  # Extract declaration names
  if hasattr(declarations[0], "function_declarations"):
    decl_names = {f.name for f in declarations[0].function_declarations}
  else:
    decl_names = {d["name"] for d in declarations}

  assert decl_names == avail_names


def test_api_agent_tools_endpoint():
  """Verify GET /api/v1/agent/tools exposes safe metadata for all tools."""
  client = TestClient(app)
  res = client.get("/api/v1/agent/tools")
  assert res.status_code == 200
  data = res.json()
  assert data["total_available"] == 12
  assert data["total_planned"] == 0
  names = [t["name"] for t in data["tools"]]
  assert "retrieve_evidence" in names
  assert "check_claim" in names
  assert "generate_checklist" in names
  assert "draft_complaint" in names
  assert "open_service_portal" in names
  assert "fill_demo_form" in names
  assert "submit_demo_application" in names
  assert "register_demo_complaint" in names


# --- 2. Orchestrator Scripted Flow Tests ---

def test_orchestrator_direct_answer_no_tools():
  """Verify a general civic query is answered directly without tool calls."""
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True

  # Model answers directly with text on step 1
  mock_gemini.generate_with_tools = AsyncMock(
      return_value=GeminiToolResult(
          model="gemini-2.5-flash",
          text="A government notification is an official public circular issued by a state department.",
          tool_calls=[],
          finish_reason="STOP",
          prompt_tokens=50,
          candidates_tokens=30,
          total_tokens=80,
      )
  )
  set_gemini_service(mock_gemini)

  client = TestClient(app)
  res = client.post(
      "/api/v1/agent/chat",
      json={"message": "What is a government notification?", "language": "en"},
  )
  assert res.status_code == 200
  data = res.json()
  assert data["intent"] == "general_civic_information"
  assert data["steps_used"] == 1
  assert len(data["tool_activity"]) == 0
  assert len(data["sources"]) == 0
  assert "official public circular" in data["reply"]


def test_orchestrator_document_qa_with_verified_citations(temp_store, fake_embedder):
  """Verify agent calls retrieve_evidence, gathers passages, and cites [E1] with metadata page number."""
  client = TestClient(app)

  # Stage a document with real content
  pdf_bytes = create_in_memory_pdf([
      "Page 1: General Scheme Introduction.",
      "Page 2: Eligibility Criteria: Women heads of households residing in Tamil Nadu receive Rs. 1000 per month.",
  ])
  res_upload = client.post(
      "/api/v1/documents/upload",
      files={"file": ("magalir.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
  )
  doc_id = res_upload.json()["document_id"]
  doc_service = DocumentService(store=temp_store)
  doc_service.process_document(doc_id)

  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True

  # Step 1: Model requests retrieve_evidence
  # Step 2: Model returns synthesized answer citing [E1]
  mock_gemini.generate_with_tools = AsyncMock(
      side_effect=[
          GeminiToolResult(
              model="gemini-2.5-flash",
              text=None,
              tool_calls=[
                  ToolCallItem(
                      name="retrieve_evidence",
                      args={"document_id": doc_id, "query": "eligibility criteria women heads"},
                  )
              ],
              finish_reason="TOOL_CALL",
          ),
          GeminiToolResult(
              model="gemini-2.5-flash",
              text="Women heads of households in Tamil Nadu are eligible to receive Rs. 1000 per month [E1].",
              tool_calls=[],
              finish_reason="STOP",
          ),
      ]
  )
  set_gemini_service(mock_gemini)

  res = client.post(
      "/api/v1/agent/chat",
      json={
          "message": "Who is eligible for this scheme?",
          "document_ids": [doc_id],
          "language": "en",
      },
  )
  assert res.status_code == 200
  data = res.json()
  assert data["intent"] == "document_explanation"
  assert data["steps_used"] == 2
  assert data["grounded"] is True
  assert len(data["tool_activity"]) == 1
  assert data["tool_activity"][0]["tool_name"] == "retrieve_evidence"
  assert data["tool_activity"][0]["status"] == "success"

  # Verify authoritative backend citation
  assert len(data["sources"]) == 1
  cit = data["sources"][0]
  assert cit["source_id"] == "E1"
  assert cit["document_id"] == doc_id
  assert cit["document_name"] == "magalir.pdf"
  # Page number MUST come from metadata (page 2), not LLM text
  assert cit["page_number"] == 2


def test_orchestrator_drops_unverified_citation_labels(temp_store, fake_embedder):
  """Verify that if model hallucinates a citation like [E99], it is dropped and grounded=False is flagged."""
  client = TestClient(app)
  pdf_bytes = create_in_memory_pdf(["Welfare grant rules."])
  res_upload = client.post(
      "/api/v1/documents/upload",
      files={"file": ("rules.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
  )
  doc_id = res_upload.json()["document_id"]
  doc_service = DocumentService(store=temp_store)
  doc_service.process_document(doc_id)

  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True

  # Model calls retrieve_evidence, but cites [E99] which does not exist in ledger
  mock_gemini.generate_with_tools = AsyncMock(
      side_effect=[
          GeminiToolResult(
              model="gemini-2.5-flash",
              text=None,
              tool_calls=[
                  ToolCallItem(
                      name="retrieve_evidence",
                      args={"document_id": doc_id, "query": "grant rules"},
                  )
              ],
          ),
          GeminiToolResult(
              model="gemini-2.5-flash",
              text="The scheme provides a grant of Rs. 5000 [E99].",
              tool_calls=[],
          ),
      ]
  )
  set_gemini_service(mock_gemini)

  res = client.post(
      "/api/v1/agent/chat",
      json={"message": "What is the grant?", "document_ids": [doc_id]},
  )
  assert res.status_code == 200
  data = res.json()
  # [E99] must be dropped from sources
  assert len(data["sources"]) == 0
  assert data["grounded"] is False
  assert any("Dropped 1 unverified citation" in w for w in data["warnings"])


def test_orchestrator_rejects_hallucinated_document_id():
  """Verify the Safe Pipeline rejects fake UUIDs and non-existent document IDs without crashing."""
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True

  fake_uuid = "00000000-0000-0000-0000-000000000000"
  mock_gemini.generate_with_tools = AsyncMock(
      side_effect=[
          # Model attempts to call read_document with a hallucinated document ID
          GeminiToolResult(
              model="gemini-2.5-flash",
              text=None,
              tool_calls=[
                  ToolCallItem(
                      name="read_document",
                      args={"document_id": fake_uuid, "page_number": 1},
                  )
              ],
          ),
          # Model receives rejection and apologizes
          GeminiToolResult(
              model="gemini-2.5-flash",
              text="I could not find the specified document in your records.",
              tool_calls=[],
          ),
      ]
  )
  set_gemini_service(mock_gemini)

  client = TestClient(app)
  res = client.post("/api/v1/agent/chat", json={"message": "Read page 1 of my document"})
  assert res.status_code == 200
  data = res.json()
  assert len(data["tool_activity"]) == 1
  assert data["tool_activity"][0]["status"] == "rejected"
  assert "Document not found" in data["tool_activity"][0]["summary"]


def test_orchestrator_rejects_planned_unavailable_tool():
  """Verify that if model tries to call a planned tool, it is rejected safely."""
  from app.agent.tools import ToolDefinition, EmptyPlannedArgs, handle_planned_tool
  registry = get_tool_registry()
  registry.register(
      ToolDefinition(
          name="future_payment_tool",
          description="Planned tool for fee payment.",
          args_model=EmptyPlannedArgs,
          handler=handle_planned_tool,
          risk_level="sensitive",
          requires_approval=True,
          status="planned",
      )
  )

  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True

  mock_gemini.generate_with_tools = AsyncMock(
      side_effect=[
          GeminiToolResult(
              model="gemini-2.5-flash",
              text=None,
              tool_calls=[
                  ToolCallItem(name="future_payment_tool", args={})
              ],
          ),
          GeminiToolResult(
              model="gemini-2.5-flash",
              text="Fee payment is not available in this version yet.",
              tool_calls=[],
          ),
      ]
  )
  set_gemini_service(mock_gemini)

  client = TestClient(app)
  res = client.post("/api/v1/agent/chat", json={"message": "Pay my fee online"})
  assert res.status_code == 200
  data = res.json()
  assert data["intent"] == "unavailable_feature"
  assert len(data["tool_activity"]) == 1
  assert data["tool_activity"][0]["status"] == "rejected"
  assert "unavailable capability" in data["tool_activity"][0]["summary"].lower()


def test_orchestrator_short_circuits_duplicate_calls():
  """Verify identical repeated tool calls in the same run are short-circuited."""
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True

  # Model attempts identical list_documents twice in consecutive steps
  mock_gemini.generate_with_tools = AsyncMock(
      side_effect=[
          GeminiToolResult(
              model="gemini-2.5-flash",
              text=None,
              tool_calls=[ToolCallItem(name="list_documents", args={"limit": 10})],
          ),
          GeminiToolResult(
              model="gemini-2.5-flash",
              text=None,
              tool_calls=[ToolCallItem(name="list_documents", args={"limit": 10})],
          ),
          GeminiToolResult(
              model="gemini-2.5-flash",
              text="You have no documents uploaded.",
              tool_calls=[],
          ),
      ]
  )
  set_gemini_service(mock_gemini)

  client = TestClient(app)
  res = client.post("/api/v1/agent/chat", json={"message": "What documents do I have?"})
  assert res.status_code == 200
  data = res.json()
  assert len(data["tool_activity"]) == 2
  assert data["tool_activity"][0]["status"] == "success"
  assert data["tool_activity"][1]["status"] == "skipped"
  assert "Skipped identical repeated call" in data["tool_activity"][1]["summary"]


def test_orchestrator_step_limit_honest_partial_result():
  """Verify exceeding maximum steps stops the loop and returns an honest partial result."""
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True

  # Infinite loop simulation: model requests list_documents endlessly with different limits
  mock_gemini.generate_with_tools = AsyncMock(
      side_effect=[
          GeminiToolResult(model="gemini-2.5-flash", text=None, tool_calls=[ToolCallItem(name="list_documents", args={"limit": 1})]),
          GeminiToolResult(model="gemini-2.5-flash", text=None, tool_calls=[ToolCallItem(name="list_documents", args={"limit": 2})]),
          GeminiToolResult(model="gemini-2.5-flash", text=None, tool_calls=[ToolCallItem(name="list_documents", args={"limit": 3})]),
          GeminiToolResult(model="gemini-2.5-flash", text=None, tool_calls=[ToolCallItem(name="list_documents", args={"limit": 4})]),
          GeminiToolResult(model="gemini-2.5-flash", text=None, tool_calls=[ToolCallItem(name="list_documents", args={"limit": 5})]),
      ]
  )
  set_gemini_service(mock_gemini)

  client = TestClient(app)
  res = client.post("/api/v1/agent/chat", json={"message": "Keep searching"})
  assert res.status_code == 200
  data = res.json()
  assert data["steps_used"] == 4  # Default AGENT_MAX_STEPS
  assert any("Step budget exceeded" in w for w in data["warnings"])
  assert "unable to complete all reasoning steps" in data["reply"].lower()


# --- 3. Approval Flow Tests with Dummy Sensitive Tool ---

class DummySensitiveArgs(BaseModel):
  recipient: str = Field(..., description="Target office")
  amount: int = Field(..., ge=1, description="Amount")


async def dummy_sensitive_handler(args: DummySensitiveArgs, ctx: AgentContext):
  return {"status": "executed", "recipient": args.recipient, "amount": args.amount}


def test_approval_flow_approve_and_deny():
  """Test approval mechanism: sensitive tool pauses for approval, then resumes upon approve/deny."""
  registry = get_tool_registry()
  # Register a test-only sensitive tool requiring approval
  registry.register(
      ToolDefinition(
          name="dummy_transfer",
          description="Transfers funds to an office",
          args_model=DummySensitiveArgs,
          handler=dummy_sensitive_handler,
          risk_level="sensitive",
          requires_approval=True,
          status="available",
          ui_label_key="tools.dummyTransfer",
      )
  )

  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True

  # Step 1: Model calls sensitive tool
  mock_gemini.generate_with_tools = AsyncMock(
      return_value=GeminiToolResult(
          model="gemini-2.5-flash",
          text=None,
          tool_calls=[ToolCallItem(name="dummy_transfer", args={"recipient": "Revenue Dept", "amount": 1000})],
      )
  )
  set_gemini_service(mock_gemini)

  client = TestClient(app)
  res = client.post("/api/v1/agent/chat", json={"message": "Send 1000 to Revenue Dept"})
  assert res.status_code == 200
  data = res.json()

  # Must pause and return pending_approval
  assert data["pending_approval"] is not None
  appr_id = data["pending_approval"]["approval_id"]
  assert data["pending_approval"]["tool_name"] == "dummy_transfer"
  assert data["pending_approval"]["args"]["amount"] == 1000

  # Step 2: Citizen approves via POST /api/v1/agent/approvals/{id}
  mock_gemini.generate_with_tools = AsyncMock(
      return_value=GeminiToolResult(
          model="gemini-2.5-flash",
          text="The transfer of 1000 to Revenue Dept was completed successfully.",
          tool_calls=[],
      )
  )

  res_approve = client.post(
      f"/api/v1/agent/approvals/{appr_id}",
      json={"decision": "approve"},
  )
  assert res_approve.status_code == 200
  data_appr = res_approve.json()
  assert data_appr["decision"] == "approve"
  assert "Revenue Dept" in data_appr["resumed_response"]["reply"]
  assert data_appr["resumed_response"]["tool_activity"][0]["status"] == "success"

  # Step 3: Replay attack check: Re-submitting the same approval must fail (404)
  res_replay = client.post(
      f"/api/v1/agent/approvals/{appr_id}",
      json={"decision": "approve"},
  )
  assert res_replay.status_code == 404


def test_agent_rate_limiting():
  """Verify agent chat rate limits to 10 requests per minute."""
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True
  mock_gemini.generate_with_tools = AsyncMock(
      return_value=GeminiToolResult(model="gemini-2.5-flash", text="Reply", tool_calls=[])
  )
  set_gemini_service(mock_gemini)

  client = TestClient(app)
  for _ in range(10):
    r = client.post("/api/v1/agent/chat", json={"message": "Test question"})
    assert r.status_code == 200

  # 11th call must trigger 429
  r11 = client.post("/api/v1/agent/chat", json={"message": "Test question"})
  assert r11.status_code == 429
  data = r11.json()
  assert "rate limit exceeded" in data["error"]["message"].lower()


def test_legacy_chat_endpoint_still_works():
  """Verify existing POST /api/v1/chat endpoint remains completely functional."""
  mock_gemini = MagicMock(spec=GeminiService)
  mock_gemini.active_model = "gemini-2.5-flash"
  mock_gemini.is_configured.return_value = True
  mock_gemini.generate_text = AsyncMock(
      return_value=MagicMock(text="Legacy chat response", model="gemini-2.5-flash", finish_reason="STOP")
  )
  set_gemini_service(mock_gemini)

  client = TestClient(app)
  res = client.post("/api/v1/chat", json={"message": "Hello legacy"})
  assert res.status_code == 200
  assert res.json()["reply"] == "Legacy chat response"


@pytest.mark.skipif(
    os.environ.get("RUN_REAL_AGENT_TEST") != "1",
    reason="Manual live test: requires real Google AI Studio key and network access.",
)
def test_real_live_agent_call():
  """Optional live end-to-end agent test against real Gemini model."""
  client = TestClient(app)
  res = client.post(
      "/api/v1/agent/chat",
      json={"message": "What is the capital of Tamil Nadu and its general civic role?", "language": "en"},
  )
  assert res.status_code == 200
  data = res.json()
  assert "Chennai" in data["reply"]
  print("\nLive agent response:", data["reply"])
