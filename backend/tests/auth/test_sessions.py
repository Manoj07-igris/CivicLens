"""Tests for session management, listing, revocation, and logout."""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

ORIGIN_HEADER = {"Origin": "http://localhost:5173"}


def test_session_listing_and_revocation():
  """User can list active sessions and revoke a specific remote session."""
  client1 = TestClient(app)
  client2 = TestClient(app)

  email = f"citizen.sessions_{uuid.uuid4().hex[:6]}@civiclens.org"
  password = "ComplexSecurePass123!@#"

  # Register on client1
  res_reg = client1.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": password,
          "full_name": "Aarav Patel",
          "accept_terms": True,
      },
  )
  assert res_reg.status_code == 201
  csrf1 = res_reg.json()["csrf_token"]

  # Login on client2
  res_login2 = client2.post(
      "/api/v1/auth/login",
      json={"email": email, "password": password},
  )
  assert res_login2.status_code == 200

  # Client1 lists sessions
  res_list = client1.get("/api/v1/auth/sessions")
  assert res_list.status_code == 200
  sessions = res_list.json()
  assert len(sessions) == 2

  current_session = next(s for s in sessions if s["is_current"])
  remote_session = next(s for s in sessions if not s["is_current"])
  assert current_session is not None
  assert remote_session is not None

  # Client1 revokes remote_session
  res_revoke = client1.delete(
      f"/api/v1/auth/sessions/{remote_session['id']}",
      headers={"X-CSRF-Token": csrf1, **ORIGIN_HEADER},
  )
  assert res_revoke.status_code == 200

  # Client2 tries to access /me -> must be rejected with 401
  res_me2 = client2.get("/api/v1/auth/me")
  assert res_me2.status_code == 401
  assert res_me2.json()["error"]["code"] == "SESSION_EXPIRED"

  # Client1 is still valid
  res_me1 = client1.get("/api/v1/auth/me")
  assert res_me1.status_code == 200


def test_logout():
  """Logout terminates active session and clears the session cookie."""
  client = TestClient(app)
  email = f"citizen.logout_{uuid.uuid4().hex[:6]}@civiclens.org"
  password = "ComplexSecurePass123!@#"

  res_reg = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": password,
          "full_name": "Priya Sharma",
          "accept_terms": True,
      },
  )
  assert res_reg.status_code == 201

  # Verify authenticated
  res_me = client.get("/api/v1/auth/me")
  assert res_me.status_code == 200

  # Logout
  res_logout = client.post("/api/v1/auth/logout")
  assert res_logout.status_code == 200

  # Cookie deleted header should be present
  cookie_header = res_logout.headers.get("set-cookie", "")
  assert "civiclens_session=" in cookie_header
  assert 'max-age=0' in cookie_header.lower() or 'expires=' in cookie_header.lower()

  # Follow-up request fails with 401
  res_me_after = client.get("/api/v1/auth/me")
  assert res_me_after.status_code == 401


def test_logout_all():
  """Logout all terminates all user sessions."""
  client1 = TestClient(app)
  client2 = TestClient(app)

  email = f"citizen.logoutall_{uuid.uuid4().hex[:6]}@civiclens.org"
  password = "ComplexSecurePass123!@#"

  res_reg = client1.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": password,
          "full_name": "Vikram Seth",
          "accept_terms": True,
      },
  )
  assert res_reg.status_code == 201
  csrf1 = res_reg.json()["csrf_token"]

  # Client2 logs in
  res_login2 = client2.post(
      "/api/v1/auth/login",
      json={"email": email, "password": password},
  )
  assert res_login2.status_code == 200

  # Client1 logs out of all
  res_all = client1.post(
      "/api/v1/auth/logout-all",
      headers={"X-CSRF-Token": csrf1, **ORIGIN_HEADER},
  )
  assert res_all.status_code == 200

  # Both clients should now receive 401
  assert client1.get("/api/v1/auth/me").status_code == 401
  assert client2.get("/api/v1/auth/me").status_code == 401
