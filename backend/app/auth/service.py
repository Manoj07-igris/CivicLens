"""Core Authentication and Account Management Service."""

import datetime
import logging
from typing import Dict, List, Optional, Tuple
import uuid

import email_validator

from app.auth.csrf import generate_csrf_token
from app.auth.emailer import send_password_reset_email
from app.auth.models import (
    ClaimLocalDataResponse,
    LoginRequest,
    RegisterRequest,
    SessionInfo,
    UpdateProfileRequest,
    UserResponse,
)
from app.auth.passwords import (
    dummy_verify,
    hash_password,
    validate_password_policy,
    verify_password,
)
from app.auth.throttle import check_throttle, clear_throttle, record_failure
from app.auth.tokens import generate_reset_token, generate_session_token, hash_ip, hash_token
from app.core.config import get_settings
from app.core.errors import (
    AccountDisabledError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    PasswordPolicyError,
    PasswordResetInvalidError,
    RegistrationDisabledError,
)
from app.db.database import Database, get_database, utc_now_iso

logger = logging.getLogger("civiclens.auth.service")


def normalize_email_address(email_raw: str) -> str:
  """Validate and normalize email address to NFC-normalized lowercase form."""
  if not email_raw or not email_raw.strip():
    raise PasswordPolicyError("Email address cannot be empty.")
  try:
    validated = email_validator.validate_email(email_raw.strip(), check_deliverability=False)
    return validated.normalized.lower()
  except email_validator.EmailNotValidError as exc:
    raise PasswordPolicyError(f"Invalid email address: {str(exc)}")


class AuthService:
  """Unified authentication and user account lifecycle manager."""

  def __init__(self, db: Optional[Database] = None):
    self._db = db or get_database()
    self._settings = get_settings()

  def _record_auth_event(
      self,
      event_type: str,
      user_id: Optional[str] = None,
      ip: Optional[str] = None,
      user_agent: Optional[str] = None,
  ) -> None:
    """Record a sanitized audit trail event."""
    try:
      event_id = str(uuid.uuid4())
      now_str = utc_now_iso()
      ip_hashed = hash_ip(ip) if ip else None
      ua_clean = user_agent[:200] if user_agent else None
      self._db.execute(
          "INSERT INTO auth_events (id, user_id, event_type, created_at, ip_hash, user_agent_summary) "
          "VALUES (?, ?, ?, ?, ?, ?);",
          (event_id, user_id, event_type, now_str, ip_hashed, ua_clean),
      )
    except Exception as exc:
      logger.warning("Could not persist auth event '%s': %s", event_type, exc)

  def get_user_language(self, user_id: str) -> str:
    """Fetch user's preferred language from preferences table or default to 'en'."""
    row = self._db.fetchone(
        "SELECT value FROM preferences WHERE owner_id = ? AND key = 'preferred_language';",
        (user_id,),
    )
    if row and row["value"]:
      val = row["value"].strip('"').strip("'")
      if val in ("en", "ta"):
        return val
    return "en"

  def set_user_language(self, user_id: str, lang: str) -> None:
    """Store user's preferred language in preferences table."""
    clean_lang = "ta" if lang == "ta" else "en"
    now_str = utc_now_iso()
    self._db.execute(
        "INSERT INTO preferences (owner_id, key, value, updated_at) VALUES (?, 'preferred_language', ?, ?) "
        "ON CONFLICT(owner_id, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at;",
        (user_id, clean_lang, now_str),
    )

  def register(
      self,
      req: RegisterRequest,
      ip: Optional[str] = None,
      user_agent: Optional[str] = None,
  ) -> Tuple[UserResponse, str, str]:
    """Register a new user account.

    Returns:
      (UserResponse, raw_session_token, csrf_token)
    """
    if not self._settings.AUTH_ALLOW_REGISTRATION:
      raise RegistrationDisabledError(
          "New account registration is currently disabled.",
          details={"code": "registration_disabled"},
      )

    if not req.accept_terms:
      raise PasswordPolicyError(
          "You must accept the terms of service to create an account.",
          details={"code": "terms_not_accepted"},
      )

    ip_key = f"register:ip:{ip or 'unknown'}"
    check_throttle(self._db, ip_key)

    normalized_email = normalize_email_address(req.email)
    clean_name = req.full_name.strip()

    validate_password_policy(
        password=req.password,
        user_email=normalized_email,
        user_name=clean_name,
    )

    # Check for existing account
    existing = self._db.fetchone(
        "SELECT id FROM users WHERE email_normalized = ?;",
        (normalized_email,),
    )
    if existing:
      record_failure(self._db, ip_key, max_attempts=5)
      self._record_auth_event("REGISTER_COLLISION", None, ip, user_agent)
      raise EmailAlreadyExistsError(
          "An account with this email address already exists.",
          details={"code": "email_unavailable"},
      )

    # Determine user role
    role = "user"
    admin_emails = self._settings.admin_emails_list
    if normalized_email in admin_emails:
      role = "admin"
    elif not admin_emails:
      # Bootstrap rule: first registered user becomes admin if no ADMIN_EMAILS configured
      user_count_row = self._db.fetchone("SELECT COUNT(*) as count FROM users;")
      if user_count_row and user_count_row["count"] == 0:
        role = "admin"
        logger.info("First registered user '%s' automatically assigned 'admin' role.", normalized_email)

    user_id = str(uuid.uuid4())
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_str = now_dt.isoformat()
    password_hashed = hash_password(req.password)
    terms_ver = self._settings.TERMS_VERSION or "2026.1"
    lang = "ta" if req.preferred_language == "ta" else "en"

    with self._db.transaction():
      self._db.execute(
          "INSERT INTO users (id, full_name, email, email_normalized, password_hash, role, is_active, "
          "email_verified, preferred_language, terms_version, terms_accepted_at, created_at, updated_at) "
          "VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?, ?, ?);",
          (user_id, clean_name, req.email, normalized_email, password_hashed, role, lang, terms_ver, now_str, now_str, now_str),
      )
      # Store preferred language in preferences
      self._db.execute(
          "INSERT INTO preferences (owner_id, key, value, updated_at) VALUES (?, 'preferred_language', ?, ?) "
          "ON CONFLICT(owner_id, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at;",
          (user_id, lang, now_str),
      )

      # Create initial session
      session_id = str(uuid.uuid4())
      raw_token = generate_session_token()
      token_h = hash_token(raw_token)
      idle_exp = (now_dt + datetime.timedelta(minutes=self._settings.AUTH_SESSION_IDLE_MINUTES)).isoformat()
      abs_exp = (now_dt + datetime.timedelta(hours=self._settings.AUTH_SESSION_ABSOLUTE_HOURS)).isoformat()
      self._db.execute(
          "INSERT INTO auth_sessions (id, user_id, token_hash, created_at, last_seen_at, "
          "idle_expires_at, absolute_expires_at, remember_me, user_agent, revoked_at) "
          "VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, NULL);",
          (session_id, user_id, token_h, now_str, now_str, idle_exp, abs_exp, user_agent),
      )

    clear_throttle(self._db, ip_key)
    self._record_auth_event("REGISTER_SUCCESS", user_id, ip, user_agent)

    csrf_token = generate_csrf_token(self._settings.effective_auth_secret_key, token_h)

    user_resp = UserResponse(
        id=user_id,
        email=normalized_email,
        full_name=clean_name,
        role=role,
        is_active=True,
        email_verified=False,
        terms_accepted_at=now_str,
        created_at=now_str,
        updated_at=now_str,
        preferred_language=lang,
    )
    return user_resp, raw_token, csrf_token

  def login(
      self,
      req: LoginRequest,
      ip: Optional[str] = None,
      user_agent: Optional[str] = None,
  ) -> Tuple[UserResponse, str, str]:
    """Authenticate user with email and password.

    Returns:
      (UserResponse, raw_session_token, csrf_token)
    """
    normalized_email = normalize_email_address(req.email)
    ip_key = f"login:ip:{ip or 'unknown'}"
    email_key = f"login:email:{normalized_email}"

    check_throttle(self._db, ip_key)
    check_throttle(self._db, email_key)

    user_row = self._db.fetchone(
        "SELECT id, email, password_hash, full_name, role, is_active, email_verified, "
        "preferred_language, terms_accepted_at, created_at, updated_at FROM users WHERE email_normalized = ?;",
        (normalized_email,),
    )

    if not user_row:
      dummy_verify()
      record_failure(self._db, ip_key, max_attempts=10)
      record_failure(self._db, email_key, max_attempts=5)
      self._record_auth_event("LOGIN_FAILURE", None, ip, user_agent)
      raise InvalidCredentialsError("Invalid email or password.")

    if not user_row["is_active"]:
      self._record_auth_event("LOGIN_BLOCKED_INACTIVE", user_row["id"], ip, user_agent)
      raise AccountDisabledError("This account has been deactivated. Please contact an administrator.")

    is_valid, needs_rehash = verify_password(req.password, user_row["password_hash"])
    if not is_valid:
      record_failure(self._db, ip_key, max_attempts=10)
      record_failure(self._db, email_key, max_attempts=5)
      self._db.execute("UPDATE users SET failed_login_count = failed_login_count + 1 WHERE id = ?;", (user_row["id"],))
      self._record_auth_event("LOGIN_FAILURE", user_row["id"], ip, user_agent)
      raise InvalidCredentialsError("Invalid email or password.")

    # Opportunistic Argon2 rehash if cost parameters have been updated
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_str = now_dt.isoformat()
    if needs_rehash:
      try:
        new_hash = hash_password(req.password)
        self._db.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?;",
            (new_hash, now_str, user_row["id"]),
        )
      except Exception as exc:
        logger.warning("Failed to rehash password: %s", exc)

    clear_throttle(self._db, ip_key)
    clear_throttle(self._db, email_key)

    # Prune oldest active session if limit reached
    active_sessions = self._db.fetchall(
        "SELECT id FROM auth_sessions WHERE user_id = ? AND revoked_at IS NULL ORDER BY last_seen_at ASC;",
        (user_row["id"],),
    )
    if len(active_sessions) >= self._settings.AUTH_MAX_SESSIONS_PER_USER:
      self._db.execute(
          "UPDATE auth_sessions SET revoked_at = ? WHERE id = ?;",
          (now_str, active_sessions[0]["id"]),
      )

    # Session generation
    raw_token = generate_session_token()
    token_h = hash_token(raw_token)
    session_id = str(uuid.uuid4())

    if req.remember_me:
      idle_exp = (now_dt + datetime.timedelta(days=self._settings.AUTH_REMEMBER_ME_IDLE_DAYS)).isoformat()
      abs_exp = (now_dt + datetime.timedelta(days=self._settings.AUTH_REMEMBER_ME_ABSOLUTE_DAYS)).isoformat()
    else:
      idle_exp = (now_dt + datetime.timedelta(minutes=self._settings.AUTH_SESSION_IDLE_MINUTES)).isoformat()
      abs_exp = (now_dt + datetime.timedelta(hours=self._settings.AUTH_SESSION_ABSOLUTE_HOURS)).isoformat()

    self._db.execute(
        "INSERT INTO auth_sessions (id, user_id, token_hash, created_at, last_seen_at, "
        "idle_expires_at, absolute_expires_at, remember_me, user_agent, revoked_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL);",
        (
            session_id,
            user_row["id"],
            token_h,
            now_str,
            now_str,
            idle_exp,
            abs_exp,
            1 if req.remember_me else 0,
            user_agent,
        ),
    )
    self._db.execute(
        "UPDATE users SET last_login_at = ?, failed_login_count = 0, updated_at = ? WHERE id = ?;",
        (now_str, now_str, user_row["id"]),
    )

    self._record_auth_event("LOGIN_SUCCESS", user_row["id"], ip, user_agent)
    csrf_token = generate_csrf_token(self._settings.effective_auth_secret_key, token_h)

    lang = user_row["preferred_language"] or "en"

    user_resp = UserResponse(
        id=user_row["id"],
        email=user_row["email"],
        full_name=user_row["full_name"],
        role=user_row["role"],
        is_active=bool(user_row["is_active"]),
        email_verified=bool(user_row["email_verified"]),
        terms_accepted_at=user_row["terms_accepted_at"],
        created_at=user_row["created_at"],
        updated_at=user_row["updated_at"],
        preferred_language=lang,
    )
    return user_resp, raw_token, csrf_token

  def get_user_by_session(
      self, raw_token: str
  ) -> Optional[Tuple[UserResponse, str, str]]:
    """Validate a session token.

    Returns:
      (UserResponse, session_id, token_hash) or None if invalid or expired.
    """
    if not raw_token:
      return None

    token_h = hash_token(raw_token)
    row = self._db.fetchone(
        "SELECT s.id as session_id, s.idle_expires_at, s.absolute_expires_at, s.last_seen_at, s.remember_me, s.revoked_at, "
        "u.id as user_id, u.email, u.full_name, u.role, u.is_active, u.email_verified, "
        "u.preferred_language, u.terms_accepted_at, u.created_at, u.updated_at "
        "FROM auth_sessions s JOIN users u ON s.user_id = u.id "
        "WHERE s.token_hash = ? AND s.revoked_at IS NULL;",
        (token_h,),
    )

    if not row:
      return None

    if not row["is_active"]:
      return None

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_str = now_dt.isoformat()
    if now_str > row["idle_expires_at"] or now_str > row["absolute_expires_at"]:
      self._db.execute("UPDATE auth_sessions SET revoked_at = ? WHERE id = ?;", (now_str, row["session_id"]))
      return None

    # Sliding session renewal throttled to once every 5 minutes (300 seconds)
    try:
      last_seen_dt = datetime.datetime.fromisoformat(row["last_seen_at"])
      if (now_dt - last_seen_dt).total_seconds() > 300:
        if row["remember_me"]:
          new_idle = (now_dt + datetime.timedelta(days=self._settings.AUTH_REMEMBER_ME_IDLE_DAYS)).isoformat()
        else:
          new_idle = (now_dt + datetime.timedelta(minutes=self._settings.AUTH_SESSION_IDLE_MINUTES)).isoformat()

        self._db.execute(
            "UPDATE auth_sessions SET last_seen_at = ?, idle_expires_at = ? WHERE id = ?;",
            (now_str, new_idle, row["session_id"]),
        )
    except Exception as exc:
      logger.warning("Could not update session sliding expiry: %s", exc)

    lang = row["preferred_language"] or "en"

    user_resp = UserResponse(
        id=row["user_id"],
        email=row["email"],
        full_name=row["full_name"],
        role=row["role"],
        is_active=bool(row["is_active"]),
        email_verified=bool(row["email_verified"]),
        terms_accepted_at=row["terms_accepted_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        preferred_language=lang,
    )
    return user_resp, row["session_id"], token_h

  def logout(self, raw_token: str) -> None:
    """Terminate the active session associated with a raw token."""
    if not raw_token:
      return
    token_h = hash_token(raw_token)
    session_row = self._db.fetchone("SELECT id, user_id FROM auth_sessions WHERE token_hash = ? AND revoked_at IS NULL;", (token_h,))
    if session_row:
      now_str = utc_now_iso()
      self._db.execute("UPDATE auth_sessions SET revoked_at = ? WHERE id = ?;", (now_str, session_row["id"]))
      self._record_auth_event("LOGOUT", session_row["user_id"])

  def logout_all(self, user_id: str, keep_token_hash: Optional[str] = None) -> int:
    """Terminate all sessions for a user, optionally keeping the current session."""
    now_str = utc_now_iso()
    if keep_token_hash:
      cur = self._db.execute(
          "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND token_hash != ? AND revoked_at IS NULL;",
          (now_str, user_id, keep_token_hash),
      )
    else:
      cur = self._db.execute(
          "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL;",
          (now_str, user_id),
      )
    count = cur.rowcount
    self._record_auth_event("LOGOUT_ALL", user_id)
    return count

  def get_sessions(self, user_id: str, current_token_hash: str) -> List[SessionInfo]:
    """Retrieve all active sessions for a user."""
    now_str = utc_now_iso()
    rows = self._db.fetchall(
        "SELECT id, created_at, last_seen_at, idle_expires_at, absolute_expires_at, user_agent, token_hash "
        "FROM auth_sessions WHERE user_id = ? AND revoked_at IS NULL AND idle_expires_at > ? AND absolute_expires_at > ? "
        "ORDER BY last_seen_at DESC;",
        (user_id, now_str, now_str),
    )
    sessions = []
    for r in rows:
      exp = min(r["idle_expires_at"], r["absolute_expires_at"])
      sessions.append(
          SessionInfo(
              id=r["id"],
              created_at=r["created_at"],
              last_seen_at=r["last_seen_at"],
              expires_at=exp,
              user_agent=r["user_agent"],
              ip_address=None,
              is_current=(r["token_hash"] == current_token_hash),
          )
      )
    return sessions

  def revoke_session(self, user_id: str, session_id: str) -> bool:
    """Revoke a specific session belonging to the user."""
    now_str = utc_now_iso()
    cur = self._db.execute(
        "UPDATE auth_sessions SET revoked_at = ? WHERE id = ? AND user_id = ? AND revoked_at IS NULL;",
        (now_str, session_id, user_id),
    )
    revoked = cur.rowcount > 0
    if revoked:
      self._record_auth_event("SESSION_REVOKED", user_id)
    return revoked

  def change_password(
      self,
      user_id: str,
      current_password: str,
      new_password: str,
      current_token_hash: str,
  ) -> None:
    """Change account password, verify current password, and revoke other sessions."""
    user = self._db.fetchone(
        "SELECT email, email_normalized, password_hash, full_name FROM users WHERE id = ?;",
        (user_id,),
    )
    if not user:
      raise InvalidCredentialsError("User not found.")

    is_valid, _ = verify_password(current_password, user["password_hash"])
    if not is_valid:
      raise InvalidCredentialsError("Current password is incorrect.")

    validate_password_policy(
        password=new_password,
        user_email=user["email_normalized"],
        user_name=user["full_name"],
    )

    new_hash = hash_password(new_password)
    now_str = utc_now_iso()

    with self._db.transaction():
      self._db.execute(
          "UPDATE users SET password_hash = ?, password_changed_at = ?, updated_at = ? WHERE id = ?;",
          (new_hash, now_str, now_str, user_id),
      )
      # Revoke other sessions as a security precaution
      self._db.execute(
          "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND token_hash != ? AND revoked_at IS NULL;",
          (now_str, user_id, current_token_hash),
      )

    self._record_auth_event("PASSWORD_CHANGE_SUCCESS", user_id)

  def forgot_password(
      self,
      email: str,
      ip: Optional[str] = None,
      lang: str = "en",
  ) -> None:
    """Initiate password recovery. Always succeeds silently to prevent account enumeration."""
    normalized = normalize_email_address(email)
    ip_key = f"reset:ip:{ip or 'unknown'}"
    email_key = f"reset:email:{normalized}"

    check_throttle(self._db, ip_key)
    check_throttle(self._db, email_key)

    record_failure(self._db, ip_key, max_attempts=5)
    record_failure(self._db, email_key, max_attempts=3)

    user = self._db.fetchone(
        "SELECT id, is_active FROM users WHERE email_normalized = ?;",
        (normalized,),
    )

    if user and user["is_active"]:
      now_dt = datetime.datetime.now(datetime.timezone.utc)
      now_str = now_dt.isoformat()
      expiry_dt = now_dt + datetime.timedelta(minutes=self._settings.AUTH_RESET_TOKEN_TTL_MINUTES)
      ip_h = hash_ip(ip) if ip else None

      # Invalidate previous unused reset tokens for this user
      self._db.execute(
          "UPDATE password_reset_tokens SET used_at = ? WHERE user_id = ? AND used_at IS NULL;",
          (now_str, user["id"]),
      )

      raw_reset = generate_reset_token()
      token_h = hash_token(raw_reset)
      token_id = str(uuid.uuid4())

      self._db.execute(
          "INSERT INTO password_reset_tokens (id, user_id, token_hash, created_at, expires_at, used_at, requested_ip_hash) "
          "VALUES (?, ?, ?, ?, ?, NULL, ?);",
          (token_id, user["id"], token_h, now_str, expiry_dt.isoformat(), ip_h),
      )

      self._record_auth_event("PASSWORD_RESET_REQUESTED", user["id"], ip)
      send_password_reset_email(normalized, raw_reset, lang=lang)

  def reset_password(self, token: str, new_password: str) -> None:
    """Complete password recovery with valid reset token."""
    if not token or len(token) < 16:
      raise PasswordResetInvalidError("Invalid or expired password reset link.")

    token_h = hash_token(token)
    row = self._db.fetchone(
        "SELECT r.id, r.user_id, r.expires_at, r.used_at, u.email, u.email_normalized, u.full_name "
        "FROM password_reset_tokens r JOIN users u ON r.user_id = u.id "
        "WHERE r.token_hash = ? AND r.used_at IS NULL;",
        (token_h,),
    )

    if not row:
      raise PasswordResetInvalidError("Invalid or expired password reset link.")

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    try:
      expiry_dt = datetime.datetime.fromisoformat(row["expires_at"])
      if now_dt > expiry_dt:
        raise PasswordResetInvalidError("Password reset link has expired. Please request a new one.")
    except Exception:
      raise PasswordResetInvalidError("Invalid reset token timestamp.")

    validate_password_policy(
        password=new_password,
        user_email=row["email_normalized"],
        user_name=row["full_name"],
    )

    new_hash = hash_password(new_password)
    now_str = now_dt.isoformat()

    with self._db.transaction():
      self._db.execute(
          "UPDATE users SET password_hash = ?, password_changed_at = ?, updated_at = ? WHERE id = ?;",
          (new_hash, now_str, now_str, row["user_id"]),
      )
      self._db.execute(
          "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?;",
          (now_str, row["id"]),
      )
      # Revoke all sessions so the user must log in with the new password
      self._db.execute(
          "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL;",
          (now_str, row["user_id"]),
      )

    self._record_auth_event("PASSWORD_RESET_COMPLETED", row["user_id"])

  def update_profile(self, user_id: str, req: UpdateProfileRequest) -> UserResponse:
    """Update profile attributes such as display name and preferred language."""
    now_str = utc_now_iso()

    if req.full_name is not None:
      clean_name = req.full_name.strip()
      if not clean_name:
        raise PasswordPolicyError("Full name cannot be empty.")
      self._db.execute(
          "UPDATE users SET full_name = ?, updated_at = ? WHERE id = ?;",
          (clean_name, now_str, user_id),
      )

    if req.preferred_language is not None:
      self.set_user_language(user_id, req.preferred_language)

    user = self._db.fetchone(
        "SELECT id, email, full_name, role, is_active, email_verified, "
        "terms_accepted_at, created_at, updated_at FROM users WHERE id = ?;",
        (user_id,),
    )
    lang = self.get_user_language(user_id)

    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        is_active=bool(user["is_active"]),
        email_verified=bool(user["email_verified"]),
        terms_accepted_at=user["terms_accepted_at"],
        created_at=user["created_at"],
        updated_at=user["updated_at"],
        preferred_language=lang,
    )

  def delete_account(self, user_id: str, password_confirm: str) -> None:
    """Permanently delete user account and all personal owned records."""
    user = self._db.fetchone(
        "SELECT password_hash FROM users WHERE id = ?;",
        (user_id,),
    )
    if not user:
      raise InvalidCredentialsError("User account not found.")

    is_valid, _ = verify_password(password_confirm, user["password_hash"])
    if not is_valid:
      raise InvalidCredentialsError("Incorrect password. Account deletion cancelled.")

    tables = [
        "auth_sessions",
        "password_reset_tokens",
        "auth_events",
        "documents",
        "comparisons",
        "verifications",
        "service_guides",
        "grievances",
        "browser_sessions",
        "chat_messages",
        "conversations",
        "activity_history",
        "preferences",
    ]

    with self._db.transaction():
      for tbl in tables:
        try:
          if tbl in ("auth_sessions", "password_reset_tokens", "auth_events"):
            self._db.execute(f"DELETE FROM {tbl} WHERE user_id = ?;", (user_id,))
          else:
            self._db.execute(f"DELETE FROM {tbl} WHERE owner_id = ?;", (user_id,))
        except Exception as exc:
          logger.warning("Error deleting records from %s for user %s: %s", tbl, user_id, exc)

      self._db.execute("DELETE FROM users WHERE id = ?;", (user_id,))

    logger.info("Permanently deleted account and owned records for user '%s'.", user_id)

  def claim_local_data(self, target_user_id: str) -> ClaimLocalDataResponse:
    """Claim and reassign pre-auth local records (owner_id = 'local') to the target user."""
    target_user = self._db.fetchone("SELECT id FROM users WHERE id = ?;", (target_user_id,))
    if not target_user:
      raise InvalidCredentialsError("Target user not found.")

    claimable_tables = [
        "documents",
        "comparisons",
        "verifications",
        "service_guides",
        "grievances",
        "browser_sessions",
        "conversations",
        "chat_messages",
        "activity_history",
        "preferences",
    ]

    claimed: Dict[str, int] = {}
    total = 0

    with self._db.transaction():
      for tbl in claimable_tables:
        try:
          cur = self._db.execute(
              f"UPDATE {tbl} SET owner_id = ? WHERE owner_id = 'local';",
              (target_user_id,),
          )
          count = cur.rowcount
          claimed[tbl] = count
          total += count
        except Exception as exc:
          logger.warning("Could not claim local records from %s: %s", tbl, exc)
          claimed[tbl] = 0

    self._record_auth_event("CLAIM_LOCAL_DATA", target_user_id)
    return ClaimLocalDataResponse(
        claimed_tables=claimed,
        total_records=total,
        message=f"Successfully claimed {total} local records.",
    )
