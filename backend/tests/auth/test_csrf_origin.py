"""Tests for CSRF synchronizer token and Origin header protection."""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

VALID_ORIGIN = "http://localhost:5173"
MALICIOUS_ORIGIN = "http://evil-attacker.site"


def test_csrf_missing_token_rejected():
  """State-changing mutation without X-CSRF-Token must be rejected with 403."""
  client = TestClient(app)
  email = f"citizen.csrf_{uuid.uuid4().hex[:6]}@civiclens.org"
  password = "SecurePass123!@#"

  res_reg = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": password,
          "full_name": "Kavitha Raman",
          "accept_terms": True,
      },
  )
  assert res_reg.status_code == 201

  # Mutation PATCH /api/v1/auth/me without X-CSRF-Token
  res_patch = client.patch(
      "/api/v1/auth/me",
      json={"full_name": "Updated Kavitha"},
      headers={"Origin": VALID_ORIGIN},
  )
  assert res_patch.status_code == 403
  assert res_patch.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"


def test_csrf_invalid_token_rejected():
  """State-changing mutation with forged/invalid X-CSRF-Token must be rejected with 403."""
  client = TestClient(app)
  email = f"citizen.csrfforged_{uuid.uuid4().hex[:6]}@civiclens.org"
  password = "SecurePass123!@#"

  res_reg = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": password,
          "full_name": "Suresh Raina",
          "accept_terms": True,
      },
  )
  assert res_reg.status_code == 201

  res_patch = client.patch(
      "/api/v1/auth/me",
      json={"full_name": "Updated Suresh"},
      headers={"X-CSRF-Token": "completely_invalid_forged_csrf_token_string", "Origin": VALID_ORIGIN},
  )
  assert res_patch.status_code == 403
  assert res_patch.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"


def test_origin_header_malicious_rejected():
  """Mutation with untrusted/malicious Origin must be rejected with 403 ORIGIN_VALIDATION_FAILED."""
  client = TestClient(app)
  email = f"citizen.origin_{uuid.uuid4().hex[:6]}@civiclens.org"
  password = "SecurePass123!@#"

  res_reg = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": password,
          "full_name": "Meera Nandan",
          "accept_terms": True,
      },
  )
  assert res_reg.status_code == 201
  csrf_token = res_reg.json()["csrf_token"]

  res_patch = client.patch(
      "/api/v1/auth/me",
      json={"full_name": "Updated Meera"},
      headers={"X-CSRF-Token": csrf_token, "Origin": MALICIOUS_ORIGIN},
  )
  assert res_patch.status_code == 403
  assert res_patch.json()["error"]["code"] == "ORIGIN_VALIDATION_FAILED"


def test_csrf_and_origin_valid_succeeds():
  """Mutation with valid Origin and valid X-CSRF-Token succeeds."""
  client = TestClient(app)
  email = f"citizen.validmutation_{uuid.uuid4().hex[:6]}@civiclens.org"
  password = "SecurePass123!@#"

  res_reg = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": password,
          "full_name": "Ananya Roy",
          "accept_terms": True,
      },
  )
  assert res_reg.status_code == 201
  csrf_token = res_reg.json()["csrf_token"]

  res_patch = client.patch(
      "/api/v1/auth/me",
      json={"full_name": "Ananya Roy Updated", "preferred_language": "ta"},
      headers={"X-CSRF-Token": csrf_token, "Origin": VALID_ORIGIN},
  )
  assert res_patch.status_code == 200
  assert res_patch.json()["full_name"] == "Ananya Roy Updated"
  assert res_patch.json()["preferred_language"] == "ta"


def test_read_request_exempt_from_csrf():
  """Safe read operations (GET) do not require X-CSRF-Token or Origin."""
  client = TestClient(app)
  email = f"citizen.read_{uuid.uuid4().hex[:6]}@civiclens.org"
  password = "SecurePass123!@#"

  res_reg = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": password,
          "full_name": "Deepak Chopra",
          "accept_terms": True,
      },
  )
  assert res_reg.status_code == 201

  # GET /api/v1/auth/me without Origin or CSRF header
  res_get = client.get("/api/v1/auth/me")
  assert res_get.status_code == 200
  assert res_get.json()["user"]["email"] == email
