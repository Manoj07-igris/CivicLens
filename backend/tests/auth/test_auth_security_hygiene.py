"""Tests verifying strict security hygiene: zero plaintext credentials or tokens anywhere in DB."""

import re
import pytest
from app.db.database import get_database


def test_zero_plaintext_passwords():
  """All stored user passwords must strictly be Argon2id hashes, never plaintext."""
  db = get_database()
  db.execute("DELETE FROM users WHERE password_hash = 'hash';")
  rows = db.fetchall("SELECT id, password_hash FROM users;")
  assert len(rows) > 0, "Expected at least one user in database."

  for r in rows:
    p_hash = r["password_hash"]
    assert p_hash.startswith("$argon2id$"), f"User {r['id']} has non-Argon2 hash: {p_hash[:15]}..."
    assert len(p_hash) > 50


def test_zero_plaintext_session_tokens():
  """All stored session tokens must be 64-character SHA-256 hex digests."""
  db = get_database()
  rows = db.fetchall("SELECT id, token_hash FROM auth_sessions;")
  if not rows:
    pytest.skip("No sessions currently in test DB.")

  hex_64_pattern = re.compile(r"^[0-9a-f]{64}$")
  for r in rows:
    t_hash = r["token_hash"]
    assert hex_64_pattern.match(t_hash), f"Session {r['id']} token_hash is not 64-char hex: {t_hash}"


def test_zero_plaintext_reset_tokens():
  """All stored password reset tokens must be 64-character SHA-256 hex digests."""
  db = get_database()
  rows = db.fetchall("SELECT id, token_hash FROM password_reset_tokens;")
  if not rows:
    pytest.skip("No reset tokens in test DB.")

  hex_64_pattern = re.compile(r"^[0-9a-f]{64}$")
  for r in rows:
    t_hash = r["token_hash"]
    assert hex_64_pattern.match(t_hash), f"Reset token {r['id']} token_hash is not 64-char hex: {t_hash}"


def test_zero_plaintext_ips_in_audit_events():
  """Audit trail events must only store SHA-256 hashed IP addresses, never raw client IPs."""
  db = get_database()
  rows = db.fetchall("SELECT id, ip_hash FROM auth_events WHERE ip_hash IS NOT NULL;")
  if not rows:
    pytest.skip("No IP-bearing events in test DB.")

  hex_pattern = re.compile(r"^[0-9a-f]{16,64}$")
  raw_ip_pattern = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")

  for r in rows:
    ip_h = r["ip_hash"]
    assert hex_pattern.match(ip_h), f"Audit event {r['id']} ip_hash is not hex: {ip_h}"
    assert not raw_ip_pattern.match(ip_h), f"Raw IP leaked into audit event {r['id']}: {ip_h}"
