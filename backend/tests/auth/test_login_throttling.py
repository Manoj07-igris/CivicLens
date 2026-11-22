"""Tests for user login, credentials verification, and persistent throttling."""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_login_successful():
  """Valid credentials return user profile, csrf_token, and session cookie."""
  email = f"citizen.login_{uuid.uuid4().hex[:6]}@civiclens.org"
  password = "ValidPassword123!@#"
  # Register
  res_reg = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": password,
          "full_name": "Login Citizen",
          "accept_terms": True,
      },
  )
  assert res_reg.status_code == 201

  # Login
  res_login = client.post(
      "/api/v1/auth/login",
      json={
          "email": email,
          "password": password,
          "remember_me": False,
      },
  )
  assert res_login.status_code == 200
  data = res_login.json()
  assert data["user"]["email"] == email
  assert "csrf_token" in data
  assert len(data["csrf_token"]) > 20

  cookie_header = res_login.headers.get("set-cookie", "")
  assert "civiclens_session=" in cookie_header
  assert "httponly" in cookie_header.lower()


def test_login_invalid_password():
  """Incorrect password returns 401 INVALID_CREDENTIALS."""
  email = f"citizen.wrongpass_{uuid.uuid4().hex[:6]}@civiclens.org"
  password = "CorrectPassword123!@#"
  client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": password,
          "full_name": "Wrong Pass Citizen",
          "accept_terms": True,
      },
  )

  res = client.post(
      "/api/v1/auth/login",
      json={
          "email": email,
          "password": "WrongPassword123!@#",
      },
  )
  assert res.status_code == 401
  assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_nonexistent_user():
  """Login attempt for non-existent user returns 401 INVALID_CREDENTIALS (timing equalized)."""
  res = client.post(
      "/api/v1/auth/login",
      json={
          "email": f"nonexistent_{uuid.uuid4().hex[:6]}@civiclens.org",
          "password": "SomeRandomPassword123!@#",
      },
  )
  assert res.status_code == 401
  assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_throttling_lockout():
  """5 failed login attempts for an account trigger persistent lockout with 429."""
  email = f"citizen.lockout_{uuid.uuid4().hex[:6]}@civiclens.org"
  password = "TargetPassword123!@#"
  client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": password,
          "full_name": "Lockout Citizen",
          "accept_terms": True,
      },
  )

  # 5 failed attempts
  for _ in range(5):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword123!@#"},
    )
    assert res.status_code == 401

  # 6th attempt should be locked out
  res_locked = client.post(
      "/api/v1/auth/login",
      json={"email": email, "password": password},
  )
  assert res_locked.status_code == 429
  assert "locked" in res_locked.json()["error"]["message"].lower() or "too many" in res_locked.json()["error"]["message"].lower()
