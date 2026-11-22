import sys
from pathlib import Path

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
  """GET /api/v1/health should return 200 with service status, version, and timestamp."""
  response = client.get("/api/v1/health")
  assert response.status_code == 200
  data = response.json()
  assert data["status"] in ("ok", "degraded")
  assert data["service"] == "civiclens-api"
  assert "version" in data
  assert "timestamp" in data
  assert "database" in data
  assert "X-Request-ID" in response.headers


def test_info_endpoint():
  """GET /api/v1/info should return system metadata and the 5 planned modules."""
  response = client.get("/api/v1/info")
  assert response.status_code == 200
  data = response.json()
  assert data["app_name"] == "CivicLens API"
  assert "version" in data
  assert "environment" in data
  assert "en" in data["supported_languages"]
  assert "ta" in data["supported_languages"]

  # Check modules
  modules = data["modules"]
  assert len(modules) == 5
  expected_ids = {
      "policy_intelligence",
      "policy_change_detection",
      "fact_verification",
      "public_service_assistant",
      "civic_grievance_assistant",
  }
  actual_ids = {m["id"] for m in modules}
  assert actual_ids == expected_ids
  for m in modules:
    assert m["status"] in ("planned", "active")

  # Crucial safety check: gemini_configured must be boolean, never a key string
  assert isinstance(data["gemini_configured"], bool)
  assert "X-Request-ID" in response.headers


def test_unknown_route_returns_standard_error_format():
  """Requesting an invalid route should return consistent JSON error structure."""
  response = client.get("/api/v1/non-existent-endpoint")
  assert response.status_code == 404
  data = response.json()
  assert "error" in data
  assert data["error"]["code"] == "NOT_FOUND"
  assert isinstance(data["error"]["message"], str)
  assert data["error"]["details"] is None
  assert "X-Request-ID" in response.headers


def test_request_id_propagation():
  """X-Request-ID supplied by client must be echoed back in response headers."""
  custom_id = "custom-req-7788"
  response = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
  assert response.status_code == 200
  assert response.headers.get("X-Request-ID") == custom_id


def test_root_endpoint():
  """GET / returns welcome metadata with links to docs and health endpoints."""
  response = client.get("/")
  assert response.status_code == 200
  data = response.json()
  assert "docs_url" in data
  assert "health_url" in data
