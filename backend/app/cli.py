"""Administrative Command Line Interface for CivicLens Authentication and Account Management.

Usage:
  python -m app.cli create-admin
  python -m app.cli reset-password --email <email>
  python -m app.cli list-users
  python -m app.cli deactivate-user --email <email>
  python -m app.cli activate-user --email <email>
  python -m app.cli revoke-sessions --email <email>
  python -m app.cli claim-local-data --email <email>
"""

import argparse
import datetime
import getpass
import sys
from typing import Optional
import uuid

from app.auth.passwords import hash_password, validate_password_policy
from app.auth.service import AuthService, normalize_email_address
from app.db.database import get_database, utc_now_iso


def get_db():
  return get_database()


def cmd_create_admin(args: argparse.Namespace) -> None:
  """Interactively create a new administrator account."""
  print("\n--- CivicLens Admin Account Creation ---")
  email_raw = input("Administrator Email: ").strip()
  try:
    email = normalize_email_address(email_raw)
  except Exception as exc:
    print(f"Error: {exc}")
    sys.exit(1)

  full_name = input("Full Name / Display Name: ").strip()
  if not full_name:
    print("Error: Full name cannot be empty.")
    sys.exit(1)

  pwd1 = getpass.getpass("Password (min 12 chars): ")
  pwd2 = getpass.getpass("Confirm Password: ")
  if pwd1 != pwd2:
    print("Error: Passwords do not match.")
    sys.exit(1)

  try:
    validate_password_policy(pwd1, user_email=email, user_name=full_name)
  except Exception as exc:
    print(f"Password Error: {exc}")
    sys.exit(1)

  db = get_db()
  existing = db.fetchone("SELECT id FROM users WHERE email_normalized = ?;", (email,))
  if existing:
    print(f"Error: Account with email '{email}' already exists.")
    sys.exit(1)

  user_id = str(uuid.uuid4())
  now_str = utc_now_iso()
  hashed = hash_password(pwd1)

  with db.transaction():
    db.execute(
        "INSERT INTO users (id, full_name, email, email_normalized, password_hash, role, is_active, email_verified, "
        "preferred_language, terms_version, terms_accepted_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 'admin', 1, 1, 'en', '2026.1', ?, ?, ?);",
        (user_id, full_name, email, email, hashed, now_str, now_str, now_str),
    )

  print(f"\nSuccess! Administrator account created successfully.")
  print(f"User ID: {user_id}")
  print(f"Email:   {email}")
  print(f"Role:    admin\n")


def cmd_reset_password(args: argparse.Namespace) -> None:
  """Reset password for an existing user."""
  email_raw = args.email or input("User Email: ").strip()
  try:
    email = normalize_email_address(email_raw)
  except Exception as exc:
    print(f"Error: {exc}")
    sys.exit(1)

  db = get_db()
  user = db.fetchone("SELECT id, full_name FROM users WHERE email_normalized = ?;", (email,))
  if not user:
    print(f"Error: User with email '{email}' not found.")
    sys.exit(1)

  pwd1 = getpass.getpass("New Password (min 12 chars): ")
  pwd2 = getpass.getpass("Confirm New Password: ")
  if pwd1 != pwd2:
    print("Error: Passwords do not match.")
    sys.exit(1)

  try:
    validate_password_policy(pwd1, user_email=email, user_name=user["full_name"])
  except Exception as exc:
    print(f"Password Error: {exc}")
    sys.exit(1)

  hashed = hash_password(pwd1)
  now_str = utc_now_iso()

  with db.transaction():
    db.execute(
        "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?;",
        (hashed, now_str, user["id"]),
    )
    # Revoke all existing sessions
    db.execute("DELETE FROM auth_sessions WHERE user_id = ?;", (user["id"],))

  print(f"\nSuccess! Password updated for '{email}'. All active sessions have been revoked.\n")


def cmd_list_users(args: argparse.Namespace) -> None:
  """List all registered users with session counts."""
  db = get_db()
  rows = db.fetchall(
      "SELECT u.id, u.email, u.full_name, u.role, u.is_active, u.created_at, "
      "COUNT(s.id) as session_count "
      "FROM users u LEFT JOIN auth_sessions s ON u.id = s.user_id "
      "GROUP BY u.id ORDER BY u.created_at ASC;"
  )
  print(f"\n{'ID':<38} {'Role':<7} {'Active':<7} {'Sessions':<9} {'Email':<30} {'Name'}")
  print("-" * 110)
  for r in rows:
    active_str = "Yes" if r["is_active"] else "No"
    print(f"{r['id']:<38} {r['role']:<7} {active_str:<7} {r['session_count']:<9} {r['email']:<30} {r['full_name']}")
  print(f"\nTotal users: {len(rows)}\n")


def cmd_deactivate_user(args: argparse.Namespace) -> None:
  """Deactivate a user account and terminate all their sessions."""
  email_raw = args.email or input("User Email to deactivate: ").strip()
  email = normalize_email_address(email_raw)
  db = get_db()
  user = db.fetchone("SELECT id FROM users WHERE email_normalized = ?;", (email,))
  if not user:
    print(f"Error: User with email '{email}' not found.")
    sys.exit(1)

  with db.transaction():
    db.execute("UPDATE users SET is_active = 0, updated_at = ? WHERE id = ?;", (utc_now_iso(), user["id"]))
    db.execute("DELETE FROM auth_sessions WHERE user_id = ?;", (user["id"],))

  print(f"\nSuccess! User '{email}' deactivated. All sessions revoked.\n")


def cmd_activate_user(args: argparse.Namespace) -> None:
  """Activate a previously deactivated user account."""
  email_raw = args.email or input("User Email to activate: ").strip()
  email = normalize_email_address(email_raw)
  db = get_db()
  user = db.fetchone("SELECT id FROM users WHERE email_normalized = ?;", (email,))
  if not user:
    print(f"Error: User with email '{email}' not found.")
    sys.exit(1)

  with db.transaction():
    db.execute("UPDATE users SET is_active = 1, updated_at = ? WHERE id = ?;", (utc_now_iso(), user["id"]))

  print(f"\nSuccess! User '{email}' activated.\n")


def cmd_revoke_sessions(args: argparse.Namespace) -> None:
  """Revoke all sessions for a user or all users."""
  db = get_db()
  if args.all:
    cur = db.execute("DELETE FROM auth_sessions;")
    print(f"\nSuccess! Revoked all {cur.rowcount} active sessions system-wide.\n")
    return

  email_raw = args.email or input("User Email: ").strip()
  email = normalize_email_address(email_raw)
  user = db.fetchone("SELECT id FROM users WHERE email_normalized = ?;", (email,))
  if not user:
    print(f"Error: User with email '{email}' not found.")
    sys.exit(1)

  cur = db.execute("DELETE FROM auth_sessions WHERE user_id = ?;", (user["id"],))
  print(f"\nSuccess! Revoked {cur.rowcount} active sessions for '{email}'.\n")


def cmd_claim_local_data(args: argparse.Namespace) -> None:
  """Assign pre-auth local records to a specified user account."""
  email_raw = args.email or input("Target User Email to claim records: ").strip()
  email = normalize_email_address(email_raw)
  db = get_db()
  user = db.fetchone("SELECT id FROM users WHERE email_normalized = ?;", (email,))
  if not user:
    print(f"Error: User with email '{email}' not found.")
    sys.exit(1)

  svc = AuthService(db)
  res = svc.claim_local_data(user["id"])
  print(f"\nSuccess! Claimed {res.total_records} records for '{email}':")
  for tbl, cnt in res.claimed_tables.items():
    if cnt > 0:
      print(f"  - {tbl}: {cnt}")
  print()


def main():
  parser = argparse.ArgumentParser(description="CivicLens Admin CLI")
  subparsers = parser.add_subparsers(dest="command", required=True)

  # create-admin
  subparsers.add_parser("create-admin", help="Create a new administrator account")

  # reset-password
  rp = subparsers.add_parser("reset-password", help="Reset password for a user")
  rp.add_argument("--email", help="Target user email")

  # list-users
  subparsers.add_parser("list-users", help="List all registered accounts")

  # deactivate-user
  du = subparsers.add_parser("deactivate-user", help="Deactivate user account")
  du.add_argument("--email", help="Target user email")

  # activate-user
  au = subparsers.add_parser("activate-user", help="Activate user account")
  au.add_argument("--email", help="Target user email")

  # revoke-sessions
  rs = subparsers.add_parser("revoke-sessions", help="Revoke active sessions")
  rs.add_argument("--email", help="Target user email")
  rs.add_argument("--all", action="store_true", help="Revoke all sessions across all users")

  # claim-local-data
  cl = subparsers.add_parser("claim-local-data", help="Claim pre-auth 'local' records for a user")
  cl.add_argument("--email", help="Target user email")

  args = parser.parse_args()

  commands = {
      "create-admin": cmd_create_admin,
      "reset-password": cmd_reset_password,
      "list-users": cmd_list_users,
      "deactivate-user": cmd_deactivate_user,
      "activate-user": cmd_activate_user,
      "revoke-sessions": cmd_revoke_sessions,
      "claim-local-data": cmd_claim_local_data,
  }

  cmd = commands.get(args.command)
  if cmd:
    cmd(args)
  else:
    parser.print_help()


if __name__ == "__main__":
  main()
