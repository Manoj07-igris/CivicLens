"""Tests proving cross-user ownership isolation and IDOR immunity (HTTP 404 on foreign records)."""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.db.database import get_database, utc_now_iso
from app.main import app

ORIGIN_HEADER = {"Origin": "http://localhost:5173"}


def _register_user(client: TestClient, name: str) -> dict:
  email = f"{name.lower().replace(' ', '')}_{uuid.uuid4().hex[:6]}@civiclens.org"
  password = "SecurePassword123!@#"
  res = client.post(
      "/api/v1/auth/register",
      json={
          "email": email,
          "password": password,
          "full_name": name,
          "accept_terms": True,
      },
  )
  assert res.status_code == 201
  data = res.json()
  return {"id": data["user"]["id"], "email": email, "csrf": data["csrf_token"]}


def test_conversation_idor_isolation():
  """User B cannot access, modify, delete, or list User A's conversations (returns 404)."""
  client_a = TestClient(app)
  client_b = TestClient(app)

  user_a = _register_user(client_a, "Citizen Alpha")
  user_b = _register_user(client_b, "Citizen Beta")

  # User A creates a conversation
  res_create = client_a.post(
      "/api/v1/conversations",
      json={"title": "Alpha Private Chat", "language": "en"},
      headers={"X-CSRF-Token": user_a["csrf"], **ORIGIN_HEADER},
  )
  assert res_create.status_code == 201
  conv_id = res_create.json()["id"]

  # User B attempts to read User A's conversation
  res_read = client_b.get(f"/api/v1/conversations/{conv_id}")
  assert res_read.status_code == 404

  # User B attempts to update User A's conversation
  res_update = client_b.patch(
      f"/api/v1/conversations/{conv_id}",
      json={"title": "Hacked Title"},
      headers={"X-CSRF-Token": user_b["csrf"], **ORIGIN_HEADER},
  )
  assert res_update.status_code == 404

  # User B attempts to delete User A's conversation
  res_del = client_b.delete(
      f"/api/v1/conversations/{conv_id}",
      headers={"X-CSRF-Token": user_b["csrf"], **ORIGIN_HEADER},
  )
  assert res_del.status_code == 404

  # User B lists conversations -> must be empty
  res_list = client_b.get("/api/v1/conversations")
  assert res_list.status_code == 200
  b_ids = [c["id"] for c in res_list.json()["items"]]
  assert conv_id not in b_ids


def test_grievance_idor_isolation():
  """User B cannot access or modify User A's grievance records (returns 404)."""
  client_a = TestClient(app)
  client_b = TestClient(app)

  user_a = _register_user(client_a, "Grievance Alpha")
  user_b = _register_user(client_b, "Grievance Beta")

  db = get_database()
  grv_id = str(uuid.uuid4())
  now_str = utc_now_iso()

  db.execute(
      "INSERT INTO grievances (id, owner_id, category, severity, state, safety_risk, created_at, updated_at, data) "
      "VALUES (?, ?, 'electricity', 'medium', 'draft', 0, ?, ?, '{}');",
      (grv_id, user_a["id"], now_str, now_str),
  )

  # User B attempts to read User A's grievance
  res_read = client_b.get(f"/api/v1/grievances/{grv_id}")
  assert res_read.status_code == 404

  # User B attempts to delete User A's grievance
  res_del = client_b.delete(
      f"/api/v1/grievances/{grv_id}",
      headers={"X-CSRF-Token": user_b["csrf"], **ORIGIN_HEADER},
  )
  assert res_del.status_code == 404

  # User B lists grievances -> must not include User A's grievance
  res_list = client_b.get("/api/v1/grievances")
  assert res_list.status_code == 200
  items = res_list.json().get("items", []) if isinstance(res_list.json(), dict) else res_list.json()
  b_grv_ids = [g["id"] for g in items]
  assert grv_id not in b_grv_ids


def test_document_idor_isolation():
  """User B cannot access or delete User A's uploaded documents (returns 404)."""
  client_a = TestClient(app)
  client_b = TestClient(app)

  user_a = _register_user(client_a, "Doc Alpha")
  user_b = _register_user(client_b, "Doc Beta")

  db = get_database()
  doc_id = str(uuid.uuid4())
  now_str = utc_now_iso()

  db.execute(
      "INSERT INTO documents (id, owner_id, collection, filename, display_name, sha256, size_bytes, page_count, language, status, created_at, updated_at, data) "
      "VALUES (?, ?, 'user', 'alpha_policy.pdf', 'Alpha Policy', ?, 1024, 1, 'en', 'ready', ?, ?, '{}');",
      (doc_id, user_a["id"], uuid.uuid4().hex, now_str, now_str),
  )

  # User B attempts to read User A's document metadata
  res_read = client_b.get(f"/api/v1/documents/{doc_id}")
  assert res_read.status_code == 404

  # User B attempts to delete User A's document
  res_del = client_b.delete(
      f"/api/v1/documents/{doc_id}",
      headers={"X-CSRF-Token": user_b["csrf"], **ORIGIN_HEADER},
  )
  assert res_del.status_code == 404

  # User B lists documents -> must not include User A's document
  res_list = client_b.get("/api/v1/documents")
  assert res_list.status_code == 200
  docs = res_list.json() if isinstance(res_list.json(), list) else res_list.json().get("documents", [])
  b_doc_ids = [d["id"] for d in docs]
  assert doc_id not in b_doc_ids
