"""FastAPI dependencies for authentication, role-based authorization, and CSRF protection."""

from dataclasses import dataclass
import logging
from typing import Optional

from fastapi import Depends, Request

from app.auth.csrf import verify_csrf_token, verify_origin
from app.auth.service import AuthService
from app.core.config import get_settings
from app.core.errors import (
    AdminRequiredError,
    AuthenticationRequiredError,
    CSRFValidationError,
    OriginValidationError,
    SessionExpiredError,
)
from app.db.database import get_database

logger = logging.getLogger("civiclens.auth.dependencies")


@dataclass
class CurrentUser:
  """Representation of the currently authenticated principal."""

  id: str
  email: str
  full_name: str
  role: str
  is_active: bool
  session_id: str
  session_token_hash: str
  raw_token: str
  preferred_language: str = "en"

  @property
  def is_admin(self) -> bool:
    return self.role == "admin"


def get_auth_service() -> AuthService:
  """Dependency providing AuthService instance bound to application SQLite database."""
  return AuthService(db=get_database())


async def get_current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> CurrentUser:
  """Extract and validate the authenticated session cookie, enforcing CSRF & Origin on mutations.

  Raises:
    AuthenticationRequiredError: When session cookie is absent.
    SessionExpiredError: When session is expired, deleted, or associated with an inactive user.
    CSRFValidationError: When state-changing mutation lacks valid HMAC CSRF token.
    OriginValidationError: When mutation fails Origin/Referer verification.
  """
  settings = get_settings()
  raw_token = request.cookies.get(settings.AUTH_COOKIE_NAME)

  if not raw_token:
    raise AuthenticationRequiredError("Authentication required. Please log in.")

  session_result = auth_service.get_user_by_session(raw_token)
  if not session_result:
    raise SessionExpiredError("Your session has expired or is invalid. Please log in again.")

  user_resp, session_id, token_hash = session_result

  # Defend state-changing methods with stateless CSRF synchronizer token and Origin verification
  if request.method in ("POST", "PUT", "PATCH", "DELETE"):
    # 1. Origin verification
    origin_header = request.headers.get("origin")
    referer_header = request.headers.get("referer")
    if not verify_origin(origin_header, referer_header):
      logger.warning("Origin verification failed on %s %s from origin %s", request.method, request.url.path, origin_header)
      raise OriginValidationError("Cross-origin request rejected.")

    # 2. Synchronizer token verification
    submitted_csrf = request.headers.get("X-CSRF-Token")
    if not verify_csrf_token(settings.effective_auth_secret_key, token_hash, submitted_csrf):
      logger.warning("CSRF token verification failed on %s %s for user %s", request.method, request.url.path, user_resp.id)
      raise CSRFValidationError("CSRF token missing or invalid. Please refresh and try again.")

  return CurrentUser(
      id=user_resp.id,
      email=user_resp.email,
      full_name=user_resp.full_name,
      role=user_resp.role,
      is_active=user_resp.is_active,
      session_id=session_id,
      session_token_hash=token_hash,
      raw_token=raw_token,
      preferred_language=user_resp.preferred_language or "en",
  )


async def get_optional_current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> Optional[CurrentUser]:
  """Extract current user if authenticated session cookie is valid, or None without raising error."""
  settings = get_settings()
  raw_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
  if not raw_token:
    return None

  session_result = auth_service.get_user_by_session(raw_token)
  if not session_result:
    return None

  user_resp, session_id, token_hash = session_result
  return CurrentUser(
      id=user_resp.id,
      email=user_resp.email,
      full_name=user_resp.full_name,
      role=user_resp.role,
      is_active=user_resp.is_active,
      session_id=session_id,
      session_token_hash=token_hash,
      raw_token=raw_token,
      preferred_language=user_resp.preferred_language or "en",
  )


async def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
  """Enforce that current authenticated principal has the 'admin' role."""
  if not current_user.is_admin:
    raise AdminRequiredError("Administrator access required for this resource.")
  return current_user
