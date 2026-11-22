"""Tests for claiming pre-auth local records (admin-only migration)."""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.db.database import get_database, utc_now_iso
from app.main import app

ORIGIN_HEADER = {"Origin": "http://localhost:5173"}


def test_non_admin_cannot_claim_local_data():
  """Regular citizen account attempting to claim local data receives 403 ADMIN_REQUIRED."""
  client = TestClient(app)
  email = f"citizen.nonadmin_{uuid.uuid4().hex[:6]}@civiclens.org"
  password = "SecurePassword123!@#"

  # First registered user is admin only if no users exist. Ensure at least one admin exists
  # or register a regular user by explicitly setting their role to 'user' in DB
  res = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": password,
          "full_name": "Regular Citizen",
          "accept_terms": True,
      },
  )
  assert res.status_code == 201
  user_id = res.json()["user"]["id"]
  csrf = res.json()["csrf_token"]

  db = get_database()
  # Demote to 'user' explicitly
  db.execute("UPDATE users SET role = 'user' WHERE id = ?;", (user_id,))

  res_claim = client.post(
      "/api/v1/auth/claim-local-data",
      headers={"X-CSRF-Token": csrf, **ORIGIN_HEADER},
  )
  assert res_claim.status_code == 403
  assert res_claim.json()["error"]["code"] == "ADMIN_REQUIRED"


def test_admin_can_claim_local_data():
  """Administrator account successfully claims records with owner_id='local'."""
  client = TestClient(app)
  email = f"admin.claim_{uuid.uuid4().hex[:6]}@civiclens.org"
  password = "SuperSecretKey999!@#"

  res = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": password,
          "full_name": "Karthik Raja",
          "accept_terms": True,
      },
  )
  assert res.status_code == 201
  user_id = res.json()["user"]["id"]
  csrf = res.json()["csrf_token"]

  db = get_database()
  # Promote to admin
  db.execute("UPDATE users SET role = 'admin' WHERE id = ?;", (user_id,))

  # Insert a dummy pre-auth local record
  conv_id = str(uuid.uuid4())
  now_str = utc_now_iso()
  db.execute(
      "INSERT INTO conversations (id, owner_id, title, language_setting, created_at, updated_at) "
      "VALUES (?, 'local', 'Legacy Pre-Auth Chat', 'auto', ?, ?);",
      (conv_id, now_str, now_str),
  )

  # Call claim-local-data
  res_claim = client.post(
      "/api/v1/auth/claim-local-data",
      headers={"X-CSRF-Token": csrf, **ORIGIN_HEADER},
  )
  assert res_claim.status_code == 200
  data = res_claim.json()
  assert "claimed_tables" in data
  assert data["total_records"] >= 1

  # Verify row was reassigned to admin
  row = db.fetchone("SELECT owner_id FROM conversations WHERE id = ?;", (conv_id,))
  assert row is not None
  assert row["owner_id"] == user_id
