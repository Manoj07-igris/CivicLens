"""Tests for System Status, Diagnostics, Maintenance, Data Wipe, and Preferences (Phase 15)."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_database

client = TestClient(app)


def test_system_status_endpoint():
  """GET /api/v1/system/status should return database health and storage metrics."""
  res = client.get("/api/v1/system/status")
  assert res.status_code == 200
  data = res.json()

  assert data["database_state"] in ("ok", "degraded")
  assert data["schema_version"] >= 1
  assert "database_size_bytes" in data
  assert "wal_size_bytes" in data
  assert "storage" in data

  storage = data["storage"]
  assert "uploads_bytes" in storage
  assert "indexes_bytes" in storage
  assert "official_sources_bytes" in storage
  assert "grievances_bytes" in storage
  assert "database_bytes" in storage
  assert "total_bytes" in storage


def test_system_stats_endpoint():
  """GET /api/v1/system/stats should report item counts across all modules."""
  res = client.get("/api/v1/system/stats")
  assert res.status_code == 200
  data = res.json()

  assert "documents_count" in data
  assert "indexed_documents_count" in data
  assert "official_sources_count" in data
  assert "portals_count" in data
  assert "comparisons_count" in data
  assert "verifications_count" in data
  assert "service_guides_count" in data
  assert "grievances_count" in data
  assert "browser_sessions_count" in data
  assert "conversations_count" in data
  assert "messages_count" in data
  assert "tool_runs_count" in data


def test_system_status_unauthenticated(unauthenticated_client):
  """GET /api/v1/system/status must be accessible without login for public health metrics."""
  res = unauthenticated_client.get("/api/v1/system/status")
  assert res.status_code == 200
  data = res.json()
  assert data["database_state"] in ("ok", "degraded")
  assert "storage" in data


def test_system_stats_unauthenticated(unauthenticated_client):
  """GET /api/v1/system/stats must be accessible without login for public overview metrics."""
  res = unauthenticated_client.get("/api/v1/system/stats")
  assert res.status_code == 200
  data = res.json()
  assert "documents_count" in data
  assert "official_sources_count" in data


def test_system_backup_endpoint():
  """POST /api/v1/system/backup should perform an online hot backup and return filename."""
  res = client.post("/api/v1/system/backup")
  assert res.status_code == 201
  data = res.json()

  assert data["status"] == "success"
  assert "backup_file" in data
  assert data["size_bytes"] > 0
  assert "created_at" in data


def test_system_maintenance_endpoint():
  """POST /api/v1/system/maintenance should run cleanup routines."""
  payload = {
      "remove_orphans": False,
      "vacuum": False,
      "activity_retention_days": 90,
  }
  res = client.post("/api/v1/system/maintenance", json=payload)
  assert res.status_code == 200
  data = res.json()

  assert "interrupted_jobs_failed" in data
  assert "expired_browser_sessions" in data
  assert "activity_records_pruned" in data
  assert "duration_ms" in data


def test_system_data_wipe_phrase_verification():
  """DELETE /api/v1/system/data should require the exact confirmation phrase."""
  # 1. Invalid confirmation phrase fails with 400
  res_bad = client.delete("/api/v1/system/data?confirm=WRONG_PHRASE")
  assert res_bad.status_code == 400

  # Note: We do not trigger "DELETE MY DATA" in routine unit tests to preserve seed/test fixtures.


def test_activity_feed_and_tool_runs():
  """GET /api/v1/activity and /api/v1/activity/tool-runs."""
  # 1. Activity feed
  res_act = client.get("/api/v1/activity?limit=5")
  assert res_act.status_code == 200
  data_act = res_act.json()
  assert "items" in data_act
  assert "total" in data_act

  # 2. Tool runs
  res_tools = client.get("/api/v1/activity/tool-runs?limit=5")
  assert res_tools.status_code == 200
  data_tools = res_tools.json()
  assert "items" in data_tools
  assert "total" in data_tools


def test_preferences_endpoint():
  """GET and PUT /api/v1/preferences for allowlisted preference keys."""
  # 1. Get preference (initially None or empty)
  res_get = client.get("/api/v1/preferences/ui_language")
  assert res_get.status_code == 200

  # 2. Set preference
  res_set = client.put(
      "/api/v1/preferences/ui_language",
      json={"value": "ta"},
  )
  assert res_set.status_code == 200
  assert res_set.json()["key"] == "ui_language"
  assert res_set.json()["value"] == "ta"

  # 3. Disallowed preference key rejected with 400
  res_disallowed = client.put(
      "/api/v1/preferences/disallowed_custom_key",
      json={"value": "forbidden"},
  )
  assert res_disallowed.status_code == 400
