"""Pydantic request and response schemas for Authentication and Account Management."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field, model_validator


class UserResponse(BaseModel):
  """Public user profile model."""

  id: str = Field(..., description="Unique user identifier (UUID)")
  email: str = Field(..., description="Normalized email address")
  full_name: str = Field(..., description="User full display name")
  role: str = Field(..., description="Authorization role ('user' or 'admin')")
  is_active: bool = Field(default=True, description="Account active status")
  email_verified: bool = Field(default=False, description="Whether email has been verified")
  terms_accepted_at: str = Field(..., description="ISO UTC timestamp of terms acceptance")
  created_at: str = Field(..., description="Account creation ISO UTC timestamp")
  updated_at: str = Field(..., description="Account last update ISO UTC timestamp")
  preferred_language: Optional[str] = Field(default="en", description="Preferred UI language ('en' or 'ta')")


class SessionInfo(BaseModel):
  """Details of an active authentication session."""

  id: str = Field(..., description="Session identifier")
  created_at: str = Field(..., description="Session creation ISO UTC timestamp")
  last_seen_at: str = Field(..., description="Last activity ISO UTC timestamp")
  expires_at: str = Field(..., description="Session expiration ISO UTC timestamp")
  user_agent: Optional[str] = Field(default=None, description="Client user agent description")
  ip_address: Optional[str] = Field(default=None, description="Client IP address")
  is_current: bool = Field(default=False, description="Whether this is the caller's active session")


class RegisterRequest(BaseModel):
  """Account registration payload."""

  email: EmailStr = Field(..., description="User email address")
  password: str = Field(..., min_length=12, max_length=128, description="Account password (12-128 chars)")
  full_name: str = Field(..., min_length=1, max_length=120, description="Full name or display name")
  accept_terms: bool = Field(..., description="Must be true to accept terms of service")
  preferred_language: Optional[str] = Field(default="en", description="Preferred language ('en' or 'ta')")

  @model_validator(mode="before")
  @classmethod
  def normalize_terms_and_fields(cls, data: Any) -> Any:
    if isinstance(data, dict):
      if "accept_terms" not in data and "terms_accepted" in data:
        data["accept_terms"] = data["terms_accepted"]
    return data


class LoginRequest(BaseModel):
  """User login payload."""

  email: EmailStr = Field(..., description="User email address")
  password: str = Field(..., min_length=1, max_length=128, description="Account password")
  remember_me: bool = Field(default=False, description="Whether to issue extended 30-day session")


class AuthResponse(BaseModel):
  """Successful authentication response payload."""

  user: UserResponse = Field(..., description="Authenticated user profile")
  csrf_token: str = Field(..., description="Stateless CSRF synchronizer token for subsequent write requests")
  token: Optional[str] = Field(default=None, description="Session bearer token for cross-origin environments")


class ChangePasswordRequest(BaseModel):
  """Password update payload."""

  current_password: str = Field(..., min_length=1, max_length=128, description="Existing account password")
  new_password: str = Field(..., min_length=12, max_length=128, description="New account password (12-128 chars)")


class UpdateProfileRequest(BaseModel):
  """Profile update payload."""

  full_name: Optional[str] = Field(default=None, min_length=1, max_length=120, description="Updated full name")
  preferred_language: Optional[str] = Field(default=None, description="Preferred language ('en' or 'ta')")


class ForgotPasswordRequest(BaseModel):
  """Password recovery request payload."""

  email: EmailStr = Field(..., description="Email address associated with account")


class ResetPasswordRequest(BaseModel):
  """Password reset execution payload."""

  token: str = Field(..., min_length=16, description="Reset token delivered via email or dev console")
  new_password: str = Field(..., min_length=12, max_length=128, description="New password (12-128 chars)")


class DeleteAccountRequest(BaseModel):
  """Account deletion confirmation payload."""

  password: str = Field(..., min_length=1, max_length=128, description="Current account password for confirmation")
  confirmation: str = Field(..., description="Must match 'DELETE' to confirm irreversible erasure")


class ClaimLocalDataResponse(BaseModel):
  """Result of claiming pre-auth local records."""

  claimed_tables: Dict[str, int] = Field(..., description="Record counts updated per table")
  total_records: int = Field(..., description="Total count of migrated records")
  message: str = Field(..., description="Status summary")


class AuthCapabilitiesResponse(BaseModel):
  """Public auth metadata and configuration capabilities."""

  registration_enabled: bool = Field(..., description="Whether new signups are allowed")
  email_delivery_configured: bool = Field(..., description="Whether live SMTP delivery is active")
  dev_mode: bool = Field(..., description="Whether server is running in development mode")
  min_password_length: int = Field(default=12, description="Minimum password characters required")
  max_password_length: int = Field(default=128, description="Maximum password characters allowed")


class AuthEventInfo(BaseModel):
  """Sanitized audit log event description."""

  id: str = Field(..., description="Event identifier")
  event_type: str = Field(..., description="Audit event category")
  ip_address: Optional[str] = Field(default=None, description="Sanitized client IP")
  user_agent: Optional[str] = Field(default=None, description="Sanitized user agent")
  created_at: str = Field(..., description="Event ISO UTC timestamp")


class MessageResponse(BaseModel):
  """Standard message response."""

  message: str = Field(..., description="Informational message")
  status: str = Field(default="ok", description="Status string")
