"""Tests for password recovery (forgot-password and reset-password) flows."""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.auth.throttle import clear_throttle
from app.db.database import get_database
from app.main import app
import app.auth.service as service_module

client = TestClient(app)


def test_forgot_password_silent_success_nonexistent():
  """Forgot password for non-existent user returns 200 without leaking account absence."""
  clear_throttle(get_database(), "reset:ip:testclient")
  res = client.post(
      "/api/v1/auth/forgot-password",
      json={"email": f"nonexistent_{uuid.uuid4().hex[:6]}@civiclens.org"},
  )
  assert res.status_code == 200
  assert "instructions" in res.json()["message"].lower() or "sent" in res.json()["message"].lower()


def test_password_reset_full_flow(monkeypatch):
  """Complete flow: register -> forgot password -> capture token -> reset password -> login."""
  clear_throttle(get_database(), "reset:ip:testclient")
  captured_tokens = []

  def mock_send_email(to_email: str, raw_token: str, lang: str = "en"):
    captured_tokens.append(raw_token)

  monkeypatch.setattr(service_module, "send_password_reset_email", mock_send_email)

  email = f"citizen.reset_{uuid.uuid4().hex[:6]}@civiclens.org"
  initial_password = "InitialPassword123!@#"
  new_password = "BrandNewPassword123!@#"

  # 1. Register
  res_reg = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": initial_password,
          "full_name": "Devi Prasad",
          "accept_terms": True,
      },
  )
  assert res_reg.status_code == 201

  # 2. Forgot password request
  res_forgot = client.post(
      "/api/v1/auth/forgot-password",
      json={"email": email},
  )
  assert res_forgot.status_code == 200
  assert len(captured_tokens) == 1
  raw_token = captured_tokens[0]

  # 3. Reset password with captured token
  res_reset = client.post(
      "/api/v1/auth/reset-password",
      json={
          "token": raw_token,
          "new_password": new_password,
      },
  )
  assert res_reset.status_code == 200
  assert "successfully" in res_reset.json()["message"].lower()

  # 4. Old password must now fail
  res_old_login = client.post(
      "/api/v1/auth/login",
      json={"email": email, "password": initial_password},
  )
  assert res_old_login.status_code == 401

  # 5. New password succeeds
  res_new_login = client.post(
      "/api/v1/auth/login",
      json={"email": email, "password": new_password},
  )
  assert res_new_login.status_code == 200
  assert res_new_login.json()["user"]["email"] == email

  # 6. Reusing the same reset token must fail (single-use)
  res_reuse = client.post(
      "/api/v1/auth/reset-password",
      json={
          "token": raw_token,
          "new_password": "AnotherNewPassword123!@#",
      },
  )
  assert res_reuse.status_code == 400
  assert res_reuse.json()["error"]["code"] == "INVALID_RESET_TOKEN"


def test_password_reset_invalid_token():
  """Attempting password reset with an invalid or fabricated token returns 400."""
  res = client.post(
      "/api/v1/auth/reset-password",
      json={
          "token": "fabricated_invalid_reset_token_12345",
          "new_password": "ValidNewPassword123!@#",
      },
  )
  assert res.status_code == 400
  assert res.json()["error"]["code"] == "INVALID_RESET_TOKEN"
