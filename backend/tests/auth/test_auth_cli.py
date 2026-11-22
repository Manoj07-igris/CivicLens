"""Tests for administrative CLI commands."""

import argparse
import uuid
import pytest
from app.cli import (
    cmd_activate_user,
    cmd_claim_local_data,
    cmd_deactivate_user,
    cmd_list_users,
    cmd_revoke_sessions,
)
from app.db.database import get_database, utc_now_iso


def test_cli_list_users(capsys):
  """list-users command displays registered accounts."""
  cmd_list_users(argparse.Namespace())
  captured = capsys.readouterr()
  assert "Total users:" in captured.out


def test_cli_deactivate_and_activate_user(capsys):
  """deactivate-user sets is_active=0 and revokes sessions; activate-user restores is_active=1."""
  db = get_database()
  user_id = str(uuid.uuid4())
  email = f"cli.toggle_{uuid.uuid4().hex[:6]}@civiclens.org"
  now_str = utc_now_iso()

  from app.auth.passwords import hash_password
  dummy_hash = hash_password("ValidPassword123!@#")

  db.execute(
      "INSERT INTO users (id, full_name, email, email_normalized, password_hash, role, is_active, "
      "email_verified, preferred_language, terms_version, terms_accepted_at, created_at, updated_at) "
      "VALUES (?, 'CLI User', ?, ?, ?, 'user', 1, 0, 'en', '2026.1', ?, ?, ?);",
      (user_id, email, email, dummy_hash, now_str, now_str, now_str),
  )

  # Deactivate
  cmd_deactivate_user(argparse.Namespace(email=email))
  captured = capsys.readouterr()
  assert "deactivated" in captured.out

  row = db.fetchone("SELECT is_active FROM users WHERE id = ?;", (user_id,))
  assert row["is_active"] == 0

  # Activate
  cmd_activate_user(argparse.Namespace(email=email))
  captured = capsys.readouterr()
  assert "activated" in captured.out

  row = db.fetchone("SELECT is_active FROM users WHERE id = ?;", (user_id,))
  assert row["is_active"] == 1


def test_cli_revoke_sessions(capsys):
  """revoke-sessions revokes active sessions for target user."""
  db = get_database()
  user_id = str(uuid.uuid4())
  email = f"cli.revoke_{uuid.uuid4().hex[:6]}@civiclens.org"
  now_str = utc_now_iso()

  from app.auth.passwords import hash_password
  dummy_hash = hash_password("ValidPassword123!@#")

  db.execute(
      "INSERT INTO users (id, full_name, email, email_normalized, password_hash, role, is_active, "
      "email_verified, preferred_language, terms_version, terms_accepted_at, created_at, updated_at) "
      "VALUES (?, 'Revoke User', ?, ?, ?, 'user', 1, 0, 'en', '2026.1', ?, ?, ?);",
      (user_id, email, email, dummy_hash, now_str, now_str, now_str),
  )

  session_id = str(uuid.uuid4())
  db.execute(
      "INSERT INTO auth_sessions (id, user_id, token_hash, created_at, last_seen_at, idle_expires_at, absolute_expires_at) "
      "VALUES (?, ?, 'fake_token_hash_cli', ?, ?, ?, ?);",
      (session_id, user_id, now_str, now_str, now_str, now_str),
  )

  cmd_revoke_sessions(argparse.Namespace(email=email, all=False))
  captured = capsys.readouterr()
  assert "Revoked" in captured.out
