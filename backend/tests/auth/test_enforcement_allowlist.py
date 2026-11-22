"""Tests confirming the strict public allowlist and default-deny authentication boundary."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_public_allowlist_endpoints_accessible_without_auth():
  """All endpoints in the designated public allowlist return successful status without session cookies."""
  public_endpoints = [
      ("/api/v1/health", 200),
      ("/api/v1/gemini/status", 200),
      ("/api/v1/documents/capabilities", 200),
      ("/api/v1/auth/capabilities", 200),
  ]

  for endpoint, expected_status in public_endpoints:
    res = client.get(endpoint)
    assert res.status_code == expected_status, f"Public endpoint {endpoint} returned {res.status_code}"


def test_protected_endpoints_return_401_without_session():
  """All application feature endpoints enforce default-deny and return 401 AUTHENTICATION_REQUIRED."""
  protected_endpoints = [
      "/api/v1/auth/me",
      "/api/v1/auth/sessions",
      "/api/v1/documents",
      "/api/v1/compare",
      "/api/v1/verify",
      "/api/v1/services/guides",
      "/api/v1/grievances",
      "/api/v1/conversations",
      "/api/v1/activity",
      "/api/v1/preferences",
      "/api/v1/sources",
      "/api/v1/portals",
  ]

  for endpoint in protected_endpoints:
    res = client.get(endpoint)
    assert res.status_code == 401, f"Expected 401 on {endpoint}, got {res.status_code}"
    error_code = res.json().get("error", {}).get("code")
    assert error_code == "AUTHENTICATION_REQUIRED", f"Unexpected error code on {endpoint}: {error_code}"
