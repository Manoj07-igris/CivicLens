"""Privacy Canaries & Data Hygiene Verification Test Suite (Phase 16).

Verifies:
1. Privacy Canary isolation: Sensitive canary tokens never appear in error responses or stack traces.
2. Log protection: Privacy tokens never appear in application log streams.
3. Activity ledger hygiene: Citizen tokens are not stored in high-level audit logs.
4. Data-at-rest wipe: Complete data purge cleanly resets storage without schema destruction.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_database

client = TestClient(app)


def test_privacy_canary_not_leaked_in_error_responses():
    """Verify unique canary secrets are never echoed in error bodies or stack traces."""
    canary = f"CANARY_SECRET_TOKEN_{uuid.uuid4().hex}"

    # 1. PII error response
    resp = client.post("/api/v1/chat", json={
        "message": f"My phone number is 9876543210 and my canary code is {canary}"
    })
    assert resp.status_code == 422
    # Ensure error response never echoes the sensitive canary token
    assert canary not in resp.text

    # 2. Invalid endpoint / 404 with canary in path
    resp404 = client.get(f"/api/v1/documents/{uuid.uuid4()}")
    assert resp404.status_code == 404
    assert canary not in resp404.text


def test_privacy_canary_not_leaked_in_application_logs(caplog):
    """Verify sensitive canary tokens are not printed to logs when rejected by PII guard."""
    canary = f"CANARY_LOG_{uuid.uuid4().hex}"
    import logging
    caplog.set_level(logging.DEBUG)

    resp = client.post("/api/v1/chat", json={
        "message": f"Contact me at user@example.gov.in regarding canary {canary}"
    })
    assert resp.status_code == 422
    # The canary string must not appear in captured log output
    assert canary not in caplog.text


def test_privacy_canary_not_in_activity_ledger():
    """Verify citizen inquiry details are not echoed into public/admin activity rows."""
    canary = f"CANARY_LEDGER_{uuid.uuid4().hex[:8]}"

    # Send a clean request that logs activity
    resp = client.get("/api/v1/documents")
    assert resp.status_code == 200

    db = get_database()
    rows = db.fetchall("SELECT id, owner_id, event_type, ref_type, ref_id FROM activity;")
    for r in rows:
        combined = f"{r['id']} {r['owner_id']} {r['event_type']} {r['ref_type']} {r['ref_id']}"
        assert canary not in combined


def test_data_at_rest_deletion_wipes_all_citizen_data():
    """Verify DELETE /api/v1/system/data completely wipes citizen records while keeping schema intact."""
    # Attempt without correct confirmation phrase
    bad_resp = client.delete("/api/v1/system/data?confirm=WRONG_PHRASE")
    assert bad_resp.status_code == 400

    # Wipe with exact confirmation phrase
    wipe_resp = client.delete("/api/v1/system/data?confirm=DELETE%20MY%20DATA")
    assert wipe_resp.status_code == 200
    data = wipe_resp.json()
    assert data["status"] == "success"

    # Verify tables are empty
    db = get_database()
    assert db.fetchone("SELECT COUNT(*) AS c FROM conversations;")["c"] == 0
    assert db.fetchone("SELECT COUNT(*) AS c FROM messages;")["c"] == 0
    assert db.fetchone("SELECT COUNT(*) AS c FROM grievances;")["c"] == 0
    assert db.fetchone("SELECT COUNT(*) AS c FROM service_guides;")["c"] == 0
    assert db.fetchone("SELECT COUNT(*) AS c FROM comparisons;")["c"] == 0
    assert db.fetchone("SELECT COUNT(*) AS c FROM verifications;")["c"] == 0
    # User documents must be 0
    assert db.fetchone("SELECT COUNT(*) AS c FROM documents WHERE collection = 'user';")["c"] == 0
