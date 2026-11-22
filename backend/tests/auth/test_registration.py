"""Tests for citizen registration and password policy enforcement."""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_registration_password_policy_too_short():
  """Password shorter than 12 characters must be rejected by validation schema."""
  res = client.post(
      "/api/v1/auth/register",
      json={
          "email": f"short_{uuid.uuid4().hex[:6]}@civiclens.org",
          "password": "Short1!pass",
          "full_name": "Short Citizen",
          "accept_terms": True,
      },
  )
  assert res.status_code == 422
  assert "at least 12 characters" in str(res.json()).lower()


def test_registration_password_policy_repetitive_sequence():
  """Password with repetitive repeating sequence or simple sequential patterns must be rejected."""
  res = client.post(
      "/api/v1/auth/register",
      json={
          "email": f"repetitive_{uuid.uuid4().hex[:6]}@civiclens.org",
          "password": "abcabcabcabc123123",
          "full_name": "Repetitive Citizen",
          "accept_terms": True,
      },
  )
  assert res.status_code in (400, 422)
  assert "repetitive" in res.json()["error"]["message"].lower() or "sequences" in res.json()["error"]["message"].lower()


def test_registration_password_with_spaces_and_unicode_accepted():
  """Agreed password policy supports spaces and any Unicode (e.g. Tamil characters)."""
  email = f"unicode_{uuid.uuid4().hex[:6]}@civiclens.org"
  res = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": "Tamil Nadu Civic Pass 2026 உறுதி!",
          "full_name": "Unicode Citizen",
          "accept_terms": True,
      },
  )
  assert res.status_code == 201
  assert "user" in res.json()


def test_registration_with_terms_accepted_alias_accepted():
  """Registration payload sending terms_accepted instead of accept_terms must be accepted."""
  email = f"termsalias_{uuid.uuid4().hex[:6]}@civiclens.org"
  res = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": "VerySafe&UniquePass2026!",
          "full_name": "Terms Alias Citizen",
          "terms_accepted": True,
      },
  )
  assert res.status_code == 201
  assert "user" in res.json()


def test_registration_password_policy_common_blocklist():
  """Common password from blocklist must be rejected."""
  res = client.post(
      "/api/v1/auth/register",
      json={
          "email": f"common_{uuid.uuid4().hex[:6]}@civiclens.org",
          "password": "PASSWORD1234!@#",
          "full_name": "John Doe",
          "accept_terms": True,
      },
  )
  assert res.status_code in (400, 422)
  assert "too common" in res.json()["error"]["message"].lower()


def test_registration_password_contains_email_or_name():
  """Password containing name tokens must be rejected."""
  res = client.post(
      "/api/v1/auth/register",
      json={
          "email": f"rajesh.kumar_{uuid.uuid4().hex[:6]}@civiclens.org",
          "password": "RajeshKumar!2026Secure",
          "full_name": "Rajesh Kumar",
          "accept_terms": True,
      },
  )
  assert res.status_code in (400, 422)
  assert "name" in res.json()["error"]["message"].lower() or "email" in res.json()["error"]["message"].lower()


def test_registration_terms_not_accepted():
  """Registration without accepting terms of service must be rejected."""
  res = client.post(
      "/api/v1/auth/register",
      json={
          "email": f"noterms_{uuid.uuid4().hex[:6]}@civiclens.org",
          "password": "SuperSecure#2026Pass!",
          "full_name": "No Terms Citizen",
          "accept_terms": False,
      },
  )
  assert res.status_code in (400, 422)
  assert "terms" in res.json()["error"]["message"].lower()


def test_registration_successful_and_cookie_set():
  """Valid registration creates account, returns csrf_token and user, and sets HttpOnly cookie."""
  email = f"citizen.valid_{uuid.uuid4().hex[:6]}@civiclens.org"
  res = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": "MyStrong&UniquePass2026!",
          "full_name": "Valid Citizen",
          "accept_terms": True,
          "preferred_language": "ta",
      },
  )
  assert res.status_code == 201
  data = res.json()
  assert "user" in data
  assert data["user"]["email"] == email
  assert data["user"]["preferred_language"] == "ta"
  assert "csrf_token" in data
  assert len(data["csrf_token"]) > 20

  # Cookie assertions
  cookie_header = res.headers.get("set-cookie", "")
  assert "civiclens_session=" in cookie_header
  assert "httponly" in cookie_header.lower()
  assert "samesite=lax" in cookie_header.lower()
  assert "path=/api" in cookie_header.lower()


def test_registration_duplicate_email():
  """Attempting to register existing email must return 409 Conflict."""
  email = f"duplicate_{uuid.uuid4().hex[:6]}@civiclens.org"
  # Register first
  res1 = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": "InitialSecure&Pass2026!",
          "full_name": "First User",
          "accept_terms": True,
      },
  )
  assert res1.status_code == 201

  # Register second time
  res2 = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": "SecondSecure&Pass2026!",
          "full_name": "Duplicate User",
          "accept_terms": True,
      },
  )
  assert res2.status_code == 409
  assert res2.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"
