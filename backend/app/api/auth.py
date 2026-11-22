"""Authentication and Account Management API Endpoints."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, Request, Response, status

from app.auth.csrf import generate_csrf_token
from app.auth.dependencies import (
    CurrentUser,
    get_auth_service,
    get_current_user,
    get_optional_current_user,
    require_admin,
)
from app.auth.models import (
    AuthCapabilitiesResponse,
    AuthResponse,
    ChangePasswordRequest,
    ClaimLocalDataResponse,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    SessionInfo,
    UpdateProfileRequest,
    UserResponse,
)
from app.auth.service import AuthService
from app.core.config import get_settings

logger = logging.getLogger("civiclens.api.auth")

router = APIRouter(prefix="/auth", tags=["Authentication & Accounts"])


def _set_auth_cookie(response: Response, raw_token: str, remember_me: bool = False) -> None:
  settings = get_settings()
  max_age = (
      settings.AUTH_SESSION_REMEMBER_DAYS * 86400
      if remember_me
      else settings.AUTH_SESSION_MAX_AGE_SECONDS
  )
  response.set_cookie(
      key=settings.AUTH_COOKIE_NAME,
      value=raw_token,
      max_age=max_age,
      httponly=True,
      samesite=settings.auth_cookie_samesite,
      secure=settings.is_auth_cookie_secure,
      path="/",
  )


def _clear_auth_cookie(response: Response) -> None:
  settings = get_settings()
  response.delete_cookie(
      key=settings.AUTH_COOKIE_NAME,
      path="/",
      httponly=True,
      samesite=settings.auth_cookie_samesite,
      secure=settings.is_auth_cookie_secure,
  )


@router.get("/capabilities", response_model=AuthCapabilitiesResponse)
async def get_auth_capabilities() -> AuthCapabilitiesResponse:
  """Retrieve public system authentication capabilities and policy rules."""
  settings = get_settings()
  return AuthCapabilitiesResponse(
      registration_enabled=settings.AUTH_ALLOW_REGISTRATION,
      email_delivery_configured=settings.is_email_delivery_configured,
      dev_mode=(settings.APP_ENV == "development"),
      min_password_length=12,
      max_password_length=128,
  )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    response: Response,
    payload: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
  """Register a new citizen account and issue initial session."""
  client_ip = request.client.host if request.client else None
  user_agent = request.headers.get("user-agent")

  user, raw_token, csrf_token = auth_service.register(
      req=payload,
      ip=client_ip,
      user_agent=user_agent,
  )
  _set_auth_cookie(response, raw_token, remember_me=False)
  return AuthResponse(user=user, csrf_token=csrf_token, token=raw_token)


@router.post("/login", response_model=AuthResponse)
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
  """Authenticate with email and password and issue a session cookie."""
  client_ip = request.client.host if request.client else None
  user_agent = request.headers.get("user-agent")

  user, raw_token, csrf_token = auth_service.login(
      req=payload,
      ip=client_ip,
      user_agent=user_agent,
  )
  _set_auth_cookie(response, raw_token, remember_me=payload.remember_me)
  return AuthResponse(user=user, csrf_token=csrf_token, token=raw_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
  """Terminate current session and clear session cookie."""
  settings = get_settings()
  raw_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
  if raw_token:
    auth_service.logout(raw_token)
  _clear_auth_cookie(response)
  return MessageResponse(message="Successfully logged out.")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
  """Terminate all active sessions for current user and clear cookie."""
  auth_service.logout_all(current_user.id)
  _clear_auth_cookie(response)
  return MessageResponse(message="Successfully logged out of all devices.")


@router.get("/me", response_model=AuthResponse)
async def get_current_user_profile(
    current_user: CurrentUser = Depends(get_current_user),
) -> AuthResponse:
  """Retrieve current authenticated user profile and fresh CSRF synchronizer token."""
  settings = get_settings()
  fresh_csrf = generate_csrf_token(settings.effective_auth_secret_key, current_user.session_token_hash)
  user_resp = UserResponse(
      id=current_user.id,
      email=current_user.email,
      full_name=current_user.full_name,
      role=current_user.role,
      is_active=current_user.is_active,
      email_verified=False,
      terms_accepted_at="",
      created_at="",
      updated_at="",
      preferred_language=current_user.preferred_language,
  )
  return AuthResponse(user=user_resp, csrf_token=fresh_csrf, token=current_user.raw_token)


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    payload: UpdateProfileRequest,
    current_user: CurrentUser = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
  """Update profile attributes such as display name or preferred language."""
  return auth_service.update_profile(current_user.id, payload)


@router.delete("/me", response_model=MessageResponse)
async def delete_account(
    response: Response,
    payload: DeleteAccountRequest,
    current_user: CurrentUser = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
  """Permanently delete user account and all personal owned records."""
  if payload.confirmation.strip().upper() != "DELETE":
    from app.core.errors import InvalidCredentialsError
    raise InvalidCredentialsError("Confirmation text must match 'DELETE'.")

  auth_service.delete_account(current_user.id, payload.password)
  _clear_auth_cookie(response)
  return MessageResponse(message="Account and personal data successfully deleted.")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
  """Change password and invalidate all other active sessions."""
  auth_service.change_password(
      user_id=current_user.id,
      current_password=payload.current_password,
      new_password=payload.new_password,
      current_token_hash=current_user.session_token_hash,
  )
  return MessageResponse(message="Password successfully changed. Other sessions revoked.")


@router.get("/sessions", response_model=List[SessionInfo])
async def list_active_sessions(
    current_user: CurrentUser = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> List[SessionInfo]:
  """List all active sessions for current user."""
  return auth_service.get_sessions(current_user.id, current_user.session_token_hash)


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def revoke_session(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
  """Revoke a specific active session."""
  revoked = auth_service.revoke_session(current_user.id, session_id)
  if not revoked:
    from app.core.errors import SessionRevokedError
    raise SessionRevokedError("Session not found or already revoked.")
  return MessageResponse(message="Session successfully revoked.")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
  """Request a password reset link. Always returns success to prevent user enumeration."""
  client_ip = request.client.host if request.client else None
  lang = request.headers.get("Accept-Language", "en")
  if "ta" in lang.lower():
    lang = "ta"
  else:
    lang = "en"

  auth_service.forgot_password(payload.email, ip=client_ip, lang=lang)
  return MessageResponse(message="If an account exists with this email, password reset instructions have been dispatched.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
  """Reset account password using valid reset token."""
  auth_service.reset_password(payload.token, payload.new_password)
  return MessageResponse(message="Password has been reset successfully. Please log in with your new password.")


@router.post("/claim-local-data", response_model=ClaimLocalDataResponse)
async def claim_local_data(
    current_user: CurrentUser = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
) -> ClaimLocalDataResponse:
  """Admin-only endpoint: migrate pre-auth local records to current admin account."""
  return auth_service.claim_local_data(current_user.id)
