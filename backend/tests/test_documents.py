"""Comprehensive tests for CivicLens Document Intelligence (Module 1 - Policy Intelligence).

Covers PDF validation, in-memory PDF generation, PyMuPDF extraction,
page-isolated chunking, duplicate detection, OCR capability checks,
cached AI summarization, rate limiting, and lifecycle cleanup.
"""

import io
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))

from app.api.documents import get_capabilities
from app.core.config import get_settings
from app.core.errors import DocumentProcessingError, DocumentRateLimitError
from app.main import app
from app.models.documents import DocumentSummaryResponse
from app.services.document_service import (
    DocumentService,
    assess_page_quality,
    check_ocr_capabilities,
    chunk_page_text,
    get_rate_limiter,
    normalize_text,
    set_document_service,
    validate_pdf_content,
)
from app.services.document_store import DocumentStore, set_document_store
from app.services.gemini_service import GeminiResult, GeminiService, set_gemini_service


def create_in_memory_pdf(pages_text: list[str]) -> bytes:
  """Helper to construct valid in-memory multi-page PDFs using PyMuPDF."""
  doc = fitz.open()
  for text in pages_text:
    page = doc.new_page()
    if text:
      page.insert_text((50, 72), text, fontsize=11)
  data = doc.tobytes()
  doc.close()
  return data


def create_encrypted_pdf() -> bytes:
  """Helper to construct an encrypted password-protected PDF in memory."""
  doc = fitz.open()
  page = doc.new_page()
  page.insert_text((50, 72), "Confidential Secret Government Document", fontsize=11)
  data = doc.tobytes(
      encryption=fitz.PDF_ENCRYPT_AES_256,
      user_pw="secret123",
      owner_pw="owner123",
  )
  doc.close()
  return data


@pytest.fixture
def temp_store(tmp_path):
  """Create an isolated DocumentStore in a temporary directory."""
  store = DocumentStore(base_dir=tmp_path / "uploads")
  set_document_store(store)
  yield store
  set_document_store(None)


@pytest.fixture
def mock_gemini():
  """Mock GeminiService to avoid external API calls during testing."""
  mock = MagicMock(spec=GeminiService)
  mock.active_model = "gemini-2.5-flash"
  mock.is_configured.return_value = True
  mock.generate_text = AsyncMock(
      return_value=GeminiResult(
          text="## Document Overview\nThis is a verified test summary.",
          model="gemini-2.5-flash",
          finish_reason="STOP",
      )
  )
  set_gemini_service(mock)
  yield mock
  set_gemini_service(None)


@pytest.fixture(autouse=True)
def reset_state(temp_store):
  """Reset services and rate limiters between tests."""
  get_rate_limiter().reset()
  set_document_service(None)
  yield
  get_rate_limiter().reset()
  set_document_service(None)


def test_capabilities_endpoint():
  """Verify the capabilities endpoint returns system settings and OCR status."""
  client = TestClient(app)
  res = client.get("/api/v1/documents/capabilities")
  assert res.status_code == 200
  data = res.json()
  assert "ocr_available" in data
  assert isinstance(data["ocr_available"], bool)
  assert data["max_upload_mb"] > 0
  assert data["max_pdf_pages"] > 0
  assert "ocr_languages" in data


def test_normalize_text():
  """Test Unicode normalization, null byte removal, and spacing cleanup."""
  raw = "Hello\x00 World!\r\n\r\n\r\n\r\nLine   2   \n\n\nLine 3\t"
  clean = normalize_text(raw)
  assert "\x00" not in clean
  assert "Hello World!" in clean
  assert "Line   2" in clean
  # Ensure maximum of 2 consecutive newlines
  assert "\n\n\n" not in clean


def test_assess_page_quality():
  """Test quality categorization for normal, blank, and image-based pages."""
  normal_text = "The Government of Tamil Nadu hereby announces the Chief Minister's Breakfast Scheme."
  q_normal, needs_ocr_normal = assess_page_quality(normal_text, has_images=False)
  assert q_normal == "normal"
  assert not needs_ocr_normal

  q_blank, needs_ocr_blank = assess_page_quality("", has_images=False)
  assert q_blank == "blank"
  assert not needs_ocr_blank

  q_scanned, needs_ocr_scanned = assess_page_quality("", has_images=True)
  assert q_scanned == "needs_ocr"
  assert needs_ocr_scanned


def test_chunk_page_text_page_isolation():
  """Verify that chunking strictly respects page boundaries and formats chunk IDs."""
  doc_id = "test-doc-uuid"
  page_num = 3
  long_text = ("Section 1: Welfare Guidelines.\n\n" * 40)  # ~1280 chars
  chunks = chunk_page_text(long_text, doc_id, page_num, chunk_size=500, chunk_overlap=50)

  assert len(chunks) > 1
  for idx, c in enumerate(chunks):
    assert c.document_id == doc_id
    assert c.page_number == page_num  # Critical: never changes across page
    assert c.chunk_id == f"{doc_id}_p{page_num}_c{idx}"
    assert len(c.text) <= 600  # Within tolerance


def test_validate_pdf_content_valid():
  """Verify valid PDF bytes pass validation and return correct page count."""
  pdf_bytes = create_in_memory_pdf(["Page one content.", "Page two content."])
  sha256, pages = validate_pdf_content(pdf_bytes)
  assert len(sha256) == 64
  assert pages == 2


def test_validate_pdf_content_corrupt():
  """Verify corrupted or non-PDF bytes are rejected with a clear error."""
  bad_bytes = b"This is plain text pretending to be a PDF"
  with pytest.raises(DocumentProcessingError) as exc_info:
    validate_pdf_content(bad_bytes)
  assert "Invalid file format" in str(exc_info.value)


def test_validate_pdf_content_encrypted():
  """Verify encrypted PDFs are rejected safely."""
  enc_bytes = create_encrypted_pdf()
  with pytest.raises(DocumentProcessingError) as exc_info:
    validate_pdf_content(enc_bytes)
  assert "Encrypted or password-protected" in str(exc_info.value)


def test_upload_and_process_lifecycle(temp_store, mock_gemini):
  """End-to-end test of upload, background extraction, page retrieval, and deletion."""
  client = TestClient(app)

  sample_pdf = create_in_memory_pdf([
      "Tamil Nadu Welfare Scheme Policy 2026. Official Notification No. 102.",
      "Eligibility: All family cardholders residing in the district.",
  ])

  # 1. Upload valid document
  res = client.post(
      "/api/v1/documents/upload",
      files={"file": ("welfare_policy.pdf", io.BytesIO(sample_pdf), "application/pdf")},
  )
  assert res.status_code == 202
  data = res.json()
  doc_id = data["document_id"]
  assert data["filename"] == "welfare_policy.pdf"
  assert data["page_count"] == 2
  assert not data["is_duplicate"]

  # Run processing pipeline synchronously
  service = DocumentService(store=temp_store, gemini=mock_gemini)
  service.process_document(doc_id)

  # 2. Check metadata via GET /documents/{id}
  res_detail = client.get(f"/api/v1/documents/{doc_id}")
  assert res_detail.status_code == 200
  detail = res_detail.json()
  assert detail["status"] in ("ready", "ready_with_warnings")
  assert len(detail["pages_summary"]) == 2
  assert detail["chunks_count"] >= 2

  # 3. List documents via GET /documents
  res_list = client.get("/api/v1/documents")
  assert res_list.status_code == 200
  docs_list = res_list.json()
  assert any(d["document_id"] == doc_id for d in docs_list)

  # 4. Paginated pages via GET /documents/{id}/pages
  res_pages = client.get(f"/api/v1/documents/{doc_id}/pages?page=1&page_size=10")
  assert res_pages.status_code == 200
  pages_resp = res_pages.json()
  assert pages_resp["total_pages"] == 2
  assert len(pages_resp["pages"]) == 2
  assert "Tamil Nadu Welfare Scheme" in pages_resp["pages"][0]["text"]

  # 5. Single page via GET /documents/{id}/pages/2
  res_page2 = client.get(f"/api/v1/documents/{doc_id}/pages/2")
  assert res_page2.status_code == 200
  assert "Eligibility" in res_page2.json()["text"]

  # 6. Request page that doesn't exist -> 404
  res_p99 = client.get(f"/api/v1/documents/{doc_id}/pages/99")
  assert res_p99.status_code == 404

  # 7. Raw PDF retrieval via GET /documents/{id}/file
  res_file = client.get(f"/api/v1/documents/{doc_id}/file")
  assert res_file.status_code == 200
  assert res_file.headers["content-type"] == "application/pdf"
  assert res_file.headers.get("x-content-type-options") == "nosniff"

  # 8. Duplicate detection test: re-upload identical file
  res_dup = client.post(
      "/api/v1/documents/upload",
      files={"file": ("welfare_policy_copy.pdf", io.BytesIO(sample_pdf), "application/pdf")},
  )
  assert res_dup.status_code == 200
  dup_data = res_dup.json()
  assert dup_data["is_duplicate"] is True
  assert dup_data["document_id"] == doc_id

  # 9. AI Summary test via POST /documents/{id}/summary
  res_summary = client.post(
      f"/api/v1/documents/{doc_id}/summary",
      json={"language": "en"},
  )
  assert res_summary.status_code == 200
  summary_data = res_summary.json()
  assert summary_data["cached"] is False
  assert "Document Overview" in summary_data["summary"]

  # Second request should be cached
  res_summary2 = client.post(
      f"/api/v1/documents/{doc_id}/summary",
      json={"language": "en"},
  )
  assert res_summary2.status_code == 200
  assert res_summary2.json()["cached"] is True

  # 10. Delete document via DELETE /documents/{id}
  res_del = client.delete(f"/api/v1/documents/{doc_id}")
  assert res_del.status_code == 200
  assert res_del.json()["deleted"] is True

  # Verify 404 after deletion
  res_missing = client.get(f"/api/v1/documents/{doc_id}")
  assert res_missing.status_code == 404


def test_upload_rate_limiting(temp_store):
  """Verify that rapid uploads beyond limit trigger 429 RATE_LIMIT_EXCEEDED."""
  client = TestClient(app)
  sample_pdf = create_in_memory_pdf(["Rate limit test page."])

  # Fill up allowed 10 requests
  for i in range(10):
    pdf_bytes = create_in_memory_pdf([f"Unique content {i}"])
    res = client.post(
        "/api/v1/documents/upload",
        files={"file": (f"doc_{i}.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res.status_code == 202

  # 11th request should be rate-limited
  pdf_bytes = create_in_memory_pdf(["Over limit content"])
  res_blocked = client.post(
      "/api/v1/documents/upload",
      files={"file": ("doc_over.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
  )
  assert res_blocked.status_code == 429
  assert res_blocked.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
