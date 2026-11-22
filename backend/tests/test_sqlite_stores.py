"""Contract tests for all 8 SQLite Store implementations (Phase 15)."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))

import uuid
import pytest

from app.core.config import Settings
from app.db.database import Database
from app.db.migrations.runner import MigrationRunner
from app.db.stores import (
    SqliteBrowserSessionStore,
    SqliteComparisonStore,
    SqliteDocumentStore,
    SqliteGrievanceStore,
    SqlitePortalRegistryStore,
    SqliteServiceGuideStore,
    SqliteSourceLibraryStore,
    SqliteVerificationStore,
)
from app.models.browser import BrowserSessionEvent, BrowserSessionRecord
from app.models.grievance import DemoRecord, DemoTrackingEvent, Grievance, GrievanceDraft
from app.models.portal import GrievanceChannelsResult, PortalEntry
from app.models.service_guide import ChecklistItem, ServiceGuideReport
from app.models.verification import CoverageInfo, OfficialSourceMetadata, VerificationReport


@pytest.fixture
def test_env(tmp_path: Path):
  """Set up test environment with an active SQLite database."""
  db_path = tmp_path / "civiclens_test.db"
  settings = Settings(
      DATABASE_PATH=str(db_path),
      DATABASE_BUSY_TIMEOUT_MS=5000,
  )
  db = Database(settings)
  runner = MigrationRunner(db)
  runner.run_migrations()
  return settings, db


def test_sqlite_document_store(test_env):
  """Verify SqliteDocumentStore CRUD, pages, and chunks."""
  settings, db = test_env
  store = SqliteDocumentStore(settings, db=db)

  doc_id = str(uuid.uuid4())
  meta = {
      "id": doc_id,
      "collection": "user",
      "filename": "test_gazette.pdf",
      "display_name": "Test Gazette",
      "size_bytes": 1024,
      "sha256": "abc123sha256",
      "page_count": 2,
      "chunk_count": 2,
      "total_chars": 500,
      "language": "en",
      "status": "ready",
      "ocr_used": False,
      "file_missing": False,
      "uploaded_at": "2026-11-21T10:00:00Z",
  }
  pages = [
      {"page_number": 1, "text": "Page 1 text of civic order", "language": "en", "word_count": 6},
      {"page_number": 2, "text": "Page 2 conditions and procedures", "language": "en", "word_count": 5},
  ]
  chunks = [
      {"chunk_id": f"{doc_id}_c1", "document_id": doc_id, "page_number": 1, "text": "Page 1 text of civic order"},
      {"chunk_id": f"{doc_id}_c2", "document_id": doc_id, "page_number": 2, "text": "Page 2 conditions and procedures"},
  ]

  # Save doc, pages, chunks
  store.create_document(doc_id, meta)
  store.save_pages(doc_id, pages)
  store.save_chunks(doc_id, chunks)

  # Get
  retrieved = store.get_metadata(doc_id)
  assert retrieved is not None
  assert retrieved["filename"] == "test_gazette.pdf"

  # Pages & chunks
  ret_pages = store.get_pages(doc_id)
  assert ret_pages["total_pages"] == 2
  assert len(ret_pages["pages"]) == 2
  assert ret_pages["pages"][0]["page_number"] == 1

  ret_chunks = store.get_chunks(doc_id)
  assert len(ret_chunks) == 2

  # List
  all_docs = store.list_documents()
  assert len(all_docs) >= 1
  assert any(d["id"] == doc_id for d in all_docs)

  # Delete
  deleted = store.delete_document(doc_id)
  assert deleted is True
  assert store.get_metadata(doc_id) is None
  assert len(store.get_pages(doc_id)["pages"]) == 0


def test_sqlite_source_library_store(test_env):
  """Verify SqliteSourceLibraryStore manifest operations."""
  settings, db = test_env
  store = SqliteSourceLibraryStore(settings, db=db)

  src_id = str(uuid.uuid4())
  manifest = OfficialSourceMetadata(
      source_id=src_id,
      title="Tamil Nadu EV Subsidy Policy 2025",
      issuing_authority="Transport Department",
      source_url="https://cms.tn.gov.in/ev_policy.pdf",
      series_id="EV-SUBSIDY-TN",
      status="current",
      filename="ev_policy.pdf",
      file_size_bytes=2048,
      page_count=5,
      sha256="abcdef123456",
      added_at="2026-11-21T10:00:00Z",
  )

  store.save_source(manifest)

  retrieved = store.get_source(src_id)
  assert retrieved is not None
  assert retrieved.title == "Tamil Nadu EV Subsidy Policy 2025"

  all_sources = store.list_sources()
  assert any(s.source_id == src_id for s in all_sources)

  assert store.delete_source(src_id) is True
  assert store.get_source(src_id) is None


def test_sqlite_portal_registry_store(test_env):
  """Verify SqlitePortalRegistryStore returns seeded demo portal and registers new entries."""
  settings, db = test_env
  store = SqlitePortalRegistryStore(settings, db=db)

  # Check seed portals exist
  portals = store.read_all()
  assert len(portals) >= 1

  # Add custom portal
  p_id = str(uuid.uuid4())
  new_portal = PortalEntry(
      id=p_id,
      name="Chennai Corporation Portal",
      department="Greater Chennai Corporation",
      url="https://chennaicorporation.gov.in",
      domain_hint="chennaicorporation.gov.in",
      kind="official_portal",
      description="Municipal services and grievance reporting",
      created_at="2026-11-21T10:00:00Z",
      updated_at="2026-11-21T10:00:00Z",
  )
  store.save_portal(new_portal)

  fetched = store.get(p_id)
  assert fetched is not None
  assert fetched.name == "Chennai Corporation Portal"


def test_sqlite_comparison_store(test_env):
  """Verify SqliteComparisonStore CRUD."""
  settings, db = test_env
  store = SqliteComparisonStore(settings, db=db)

  cmp_id = str(uuid.uuid4())
  job_data = {
      "old_document_id": str(uuid.uuid4()),
      "new_document_id": str(uuid.uuid4()),
      "language": "en",
      "status": "processing",
      "progress": "Analyzing diffs",
      "warnings": [],
  }

  store.save_job(cmp_id, job_data)
  fetched = store.get_job(cmp_id)
  assert fetched is not None
  assert fetched["status"] == "processing"

  report = {
      "comparison_id": cmp_id,
      "overall_summary": "Expanded income thresholds.",
      "counts": {"added": 1, "removed": 0, "modified": 2},
  }
  store.save_report(cmp_id, report)

  ret_report = store.get_report(cmp_id)
  assert ret_report is not None
  assert ret_report["overall_summary"] == "Expanded income thresholds."

  comps = store.list_comparisons()
  assert any(c["id"] == cmp_id for c in comps)

  assert store.delete_comparison(cmp_id) is True
  assert store.get_job(cmp_id) is None


def test_sqlite_verification_store(test_env):
  """Verify SqliteVerificationStore CRUD."""
  settings, db = test_env
  store = SqliteVerificationStore(settings, db=db)

  v_id = str(uuid.uuid4())
  job_data = {
      "claim": "Is electricity 50% off?",
      "status": "completed",
      "scope": "official",
      "overall_verdict": "contradicted",
  }

  store.save_job(v_id, job_data)
  fetched = store.get_job(v_id)
  assert fetched is not None
  assert fetched["status"] == "completed"

  rep = VerificationReport(
      verification_id=v_id,
      created_at="2026-11-21T10:00:00Z",
      language="en",
      scope="official",
      original_claim_text="Is electricity 50% off?",
      overall_verdict="contradicted",
      overall_summary="Official circulars indicate standard tariff applies.",
      claims=[],
      coverage=CoverageInfo(
          official_sources_searched_count=1,
          official_source_titles=["TANGEDCO Tariff 2026"],
          library_version="lib_v1",
      ),
      analysis_status="completed",
  )
  store.save_report(v_id, rep)

  ret_rep = store.get_report(v_id)
  assert ret_rep is not None
  assert ret_rep.overall_verdict == "contradicted"

  assert store.delete_verification(v_id) is True
  assert store.get_job(v_id) is None


def test_sqlite_service_guide_store(test_env):
  """Verify SqliteServiceGuideStore CRUD."""
  settings, db = test_env
  store = SqliteServiceGuideStore(settings, db=db)

  g_id = str(uuid.uuid4())
  rep = ServiceGuideReport(
      id=g_id,
      query="Income Certificate application in Tamil Nadu",
      applicant_type="unspecified",
      mode="source_grounded",
      procedure_overview="Application must be submitted via e-Sevai centre.",
      checklist_items=[
          ChecklistItem(
              id="chk_1",
              category="documents",
              text="Salary Certificate",
              mandatory=True,
          )
      ],
      created_at="2026-11-21T10:00:00Z",
  )

  store.save_guide(rep)
  fetched = store.get_guide(g_id)
  assert fetched is not None
  assert fetched.query == "Income Certificate application in Tamil Nadu"

  guides = store.list_guides()
  assert any(g.id == g_id for g in guides)

  assert store.delete_guide(g_id) is True
  assert store.get_guide(g_id) is None


def test_sqlite_grievance_store(test_env):
  """Verify SqliteGrievanceStore CRUD and demo tracking."""
  settings, db = test_env
  store = SqliteGrievanceStore(settings, db=db)

  g_id = str(uuid.uuid4())
  grievance = Grievance(
      id=g_id,
      category="roads",
      severity="high",
      safety_risk=True,
      description="Deep pothole on 4th Main Road, Anna Nagar causing hazards.",
      location_text="4th Main Road, Anna Nagar",
      draft_hash="hash_1234567890abcdef",
      draft=GrievanceDraft(
          subject_line="Urgent: Hazardous pothole on 4th Main Road",
          body="I wish to bring to your immediate attention the severe road defect...",
          location_line="4th Main Road, Anna Nagar",
          draft_hash="hash_1234567890abcdef",
      ),
      channels=GrievanceChannelsResult(),
      state="draft",
      created_at="2026-11-21T10:00:00Z",
      updated_at="2026-11-21T10:00:00Z",
  )

  store.save(grievance)
  fetched = store.get(g_id)
  assert fetched is not None
  assert fetched.category == "roads"
  assert fetched.safety_risk is True

  # Update to demo registered
  grievance.state = "demo_registered"
  grievance.demo = DemoRecord(
      demo_id="DEMO-TEST123",
      registered_at="2026-11-21T10:05:00Z",
      status="registered",
      events=[
          DemoTrackingEvent(
              event_id="evt_1",
              status="registered",
              timestamp="2026-11-21T10:05:00Z",
              note="Demo record registered.",
          )
      ],
  )
  updated = store.save(grievance)
  assert updated.state == "demo_registered"
  assert updated.demo is not None
  assert updated.demo.demo_id == "DEMO-TEST123"

  all_g = store.list_all()
  assert any(g.id == g_id for g in all_g)

  assert store.delete(g_id) is True
  with pytest.raises(Exception):
    store.get(g_id)


def test_sqlite_browser_session_store(test_env):
  """Verify SqliteBrowserSessionStore session lifecycle and event logging."""
  settings, db = test_env
  store = SqliteBrowserSessionStore(settings, db=db)

  s_id = str(uuid.uuid4())
  session = BrowserSessionRecord(
      session_id=s_id,
      portal_id="demo-income-portal",
      portal_url="http://localhost:8000/demo-portal/",
      workflow_id="income_certificate_demo",
      status="active",
      current_step=1,
      total_steps=4,
      expires_at="2026-11-21T12:00:00Z",
      events=[
          BrowserSessionEvent(
              step_index=1,
              action="open_portal",
              url="http://localhost:8000/demo-portal/",
              message="Opened Income Certificate demo portal.",
              timestamp="2026-11-21T10:00:00Z",
          )
      ],
      created_at="2026-11-21T10:00:00Z",
      updated_at="2026-11-21T10:00:00Z",
  )

  store.save_session(session)
  fetched = store.read_session(s_id)
  assert fetched is not None
  assert fetched.status == "active"
  assert len(fetched.events) == 1

  # Record new event
  new_event = BrowserSessionEvent(
      step_index=2,
      action="fill_step",
      url="http://localhost:8000/demo-portal/step2",
      message="Entered applicant details.",
      timestamp="2026-11-21T10:05:00Z",
  )
  session.current_step = 2
  session.events.append(new_event)
  store.save_session(session)

  updated = store.read_session(s_id)
  assert updated.current_step == 2
  assert len(updated.events) == 2

  store.delete_session(s_id)
  assert store.read_session(s_id) is None
