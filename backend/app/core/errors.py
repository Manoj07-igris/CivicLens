import logging
from typing import Any
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.gemini_service import GeminiError

logger = logging.getLogger("civiclens.errors")


class DocumentError(Exception):
  """Base exception for document processing errors."""
  def __init__(self, message: str, code: str = "DOCUMENT_ERROR", status_code: int = 400, details: Any = None):
    super().__init__(message)
    self.message = message
    self.code = code
    self.status_code = status_code
    self.details = details


class DocumentNotFoundError(DocumentError):
  """Raised when a requested document ID does not exist."""
  def __init__(self, message: str = "Document not found."):
    super().__init__(message=message, code="DOCUMENT_NOT_FOUND", status_code=404)


class DocumentProcessingError(DocumentError):
  """Raised when a document cannot be parsed or processed."""
  def __init__(self, message: str, details: Any = None):
    super().__init__(message=message, code="DOCUMENT_PROCESSING_ERROR", status_code=422, details=details)


class DocumentRateLimitError(DocumentError):
  """Raised when upload rate limit is exceeded."""
  def __init__(self, message: str = "Upload rate limit exceeded. Please wait before uploading more documents."):
    super().__init__(message=message, code="RATE_LIMIT_EXCEEDED", status_code=429)


class ComparisonError(DocumentError):
  """Base exception for policy comparison errors."""
  def __init__(self, message: str, code: str = "COMPARISON_ERROR", status_code: int = 400, details: Any = None):
    super().__init__(message=message, code=code, status_code=status_code, details=details)


class ComparisonNotFoundError(ComparisonError):
  """Raised when a requested comparison ID does not exist."""
  def __init__(self, message: str = "Comparison not found."):
    super().__init__(message=message, code="COMPARISON_NOT_FOUND", status_code=404)


class SourceLibraryError(DocumentError):
  """Base exception for official source library errors."""
  def __init__(self, message: str, code: str = "SOURCE_LIBRARY_ERROR", status_code: int = 400, details: Any = None):
    super().__init__(message=message, code=code, status_code=status_code, details=details)


class SourceNotFoundError(SourceLibraryError):
  """Raised when an official source ID does not exist."""
  def __init__(self, message: str = "Official source not found in library."):
    super().__init__(message=message, code="SOURCE_NOT_FOUND", status_code=404)


class VerificationError(DocumentError):
  """Base exception for fact verification errors."""
  def __init__(self, message: str, code: str = "VERIFICATION_ERROR", status_code: int = 400, details: Any = None):
    super().__init__(message=message, code=code, status_code=status_code, details=details)


class VerificationNotFoundError(VerificationError):
  """Raised when a verification ID does not exist."""
  def __init__(self, message: str = "Verification report not found."):
    super().__init__(message=message, code="VERIFICATION_NOT_FOUND", status_code=404)


class PIIDetectedError(DocumentError):
  """Raised when user input contains personally identifiable information (Aadhaar, PAN, phone, etc.)."""
  def __init__(self, message: str = "Personal identifiers detected. CivicLens does not accept personal data.", details: Any = None):
    super().__init__(message=message, code="PII_DETECTED", status_code=422, details=details)


class PortalRegistryError(DocumentError):
  """Base exception for portal registry errors."""
  def __init__(self, message: str, code: str = "PORTAL_REGISTRY_ERROR", status_code: int = 400, details: Any = None):
    super().__init__(message=message, code=code, status_code=status_code, details=details)


class PortalNotFoundError(PortalRegistryError):
  """Raised when a requested portal ID does not exist in registry."""
  def __init__(self, message: str = "Official portal not found in registry."):
    super().__init__(message=message, code="PORTAL_NOT_FOUND", status_code=404)


class ServiceGuideError(DocumentError):
  """Base exception for public service guide errors."""
  def __init__(self, message: str, code: str = "SERVICE_GUIDE_ERROR", status_code: int = 400, details: Any = None):
    super().__init__(message=message, code=code, status_code=status_code, details=details)


class ServiceGuideNotFoundError(ServiceGuideError):
  """Raised when a requested service guide ID does not exist."""
  def __init__(self, message: str = "Public service guide not found."):
    super().__init__(message=message, code="SERVICE_GUIDE_NOT_FOUND", status_code=404)


class GrievanceNotFoundError(DocumentNotFoundError):
  """Raised when a requested grievance record is not found."""
  def __init__(self, message: str = "Grievance record not found."):
    super().__init__(message=message)



class BrowserError(DocumentError):
  """Base exception for controlled browser demo workflow errors."""
  def __init__(self, message: str, code: str = "BROWSER_ERROR", status_code: int = 400, details: Any = None):
    super().__init__(message=message, code=code, status_code=status_code, details=details)


class BrowserSessionNotFoundError(BrowserError):
  """Raised when a requested browser session ID does not exist."""
  def __init__(self, message: str = "Browser demo session not found."):
    super().__init__(message=message, code="BROWSER_SESSION_NOT_FOUND", status_code=404)


class BrowserActionError(BrowserError):
  """Raised when a browser automation action fails or encounters invalid state."""
  def __init__(self, message: str, details: Any = None):
    super().__init__(message=message, code="BROWSER_ACTION_ERROR", status_code=422, details=details)


class BrowserNavigationBlockedError(BrowserError):
  """Raised when a browser navigation target is outside the strict local demo allowlist."""
  def __init__(self, message: str = "Navigation outside the local demo portal is strictly prohibited."):
    super().__init__(message=message, code="BROWSER_NAVIGATION_BLOCKED", status_code=403)


class BrowserApprovalRequiredError(BrowserError):
  """Raised when an action requires explicit human approval before execution."""
  def __init__(self, message: str = "Explicit human approval is required to perform this action."):
    super().__init__(message=message, code="APPROVAL_REQUIRED", status_code=403)


# Phase 15 - Database, History and Application Integration Errors
class DatabaseError(DocumentError):
  """Base exception for SQLite database operations."""
  def __init__(self, message: str = "Database operation failed.", code: str = "DATABASE_ERROR", status_code: int = 500, details: Any = None):
    super().__init__(message=message, code=code, status_code=status_code, details=details)


class DatabaseDegradedError(DatabaseError):
  """Raised when database is corrupted or degraded, blocking storage operations."""
  def __init__(self, message: str = "Database is in degraded mode. Storage operations are paused.", details: Any = None):
    super().__init__(message=message, code="DATABASE_DEGRADED", status_code=503, details=details)


class MigrationError(DatabaseError):
  """Raised when database schema migrations fail."""
  def __init__(self, message: str = "Database migration failed.", code: str = "MIGRATION_ERROR", status_code: int = 500, details: Any = None):
    super().__init__(message=message, code=code, status_code=status_code, details=details)


class MigrationChecksumMismatchError(MigrationError):
  """Raised when an already applied migration has a modified SQL checksum."""
  def __init__(self, message: str = "Migration script checksum mismatch. Existing migrations must not be modified."):
    super().__init__(message=message, code="MIGRATION_CHECKSUM_MISMATCH", status_code=500)


class DatabaseSchemaNewerError(MigrationError):
  """Raised when the database schema version is newer than the current application code."""
  def __init__(self, message: str = "Database schema is newer than the running application code. Please upgrade CivicLens."):
    super().__init__(message=message, code="DATABASE_SCHEMA_NEWER", status_code=500)


class ConversationNotFoundError(DocumentError):
  """Raised when a requested conversation ID does not exist."""
  def __init__(self, message: str = "Conversation not found."):
    super().__init__(message=message, code="CONVERSATION_NOT_FOUND", status_code=404)


# Authentication and Authorization Errors
class AuthError(DocumentError):
  """Base exception for authentication and authorization errors."""
  def __init__(self, message: str = "Authentication error.", code: str = "AUTH_ERROR", status_code: int = 400, details: Any = None):
    super().__init__(message=message, code=code, status_code=status_code, details=details)


class AuthenticationRequiredError(AuthError):
  """Raised when an unauthenticated request attempts to access a protected resource."""
  def __init__(self, message: str = "Authentication required."):
    super().__init__(message=message, code="AUTHENTICATION_REQUIRED", status_code=401)


class InvalidCredentialsError(AuthError):
  """Raised when login credentials (email/password) are incorrect."""
  def __init__(self, message: str = "Invalid email or password."):
    super().__init__(message=message, code="INVALID_CREDENTIALS", status_code=401)


class AccountDisabledError(AuthError):
  """Raised when an inactive or suspended user attempts to authenticate."""
  def __init__(self, message: str = "This account has been deactivated."):
    super().__init__(message=message, code="ACCOUNT_DISABLED", status_code=403)


class SessionExpiredError(AuthError):
  """Raised when an auth session has expired or is invalid."""
  def __init__(self, message: str = "Session expired. Please log in again."):
    super().__init__(message=message, code="SESSION_EXPIRED", status_code=401)


class SessionRevokedError(AuthError):
  """Raised when an auth session has been explicitly revoked."""
  def __init__(self, message: str = "Session has been revoked."):
    super().__init__(message=message, code="SESSION_REVOKED", status_code=401)


class AdminRequiredError(AuthError):
  """Raised when a non-admin user attempts an admin-only operation."""
  def __init__(self, message: str = "Administrator access required."):
    super().__init__(message=message, code="ADMIN_REQUIRED", status_code=403)


class CSRFValidationError(AuthError):
  """Raised when a state-changing request fails CSRF verification."""
  def __init__(self, message: str = "CSRF verification failed."):
    super().__init__(message=message, code="CSRF_VALIDATION_FAILED", status_code=403)


class OriginValidationError(AuthError):
  """Raised when a request Origin or Referer header does not match allowed origins."""
  def __init__(self, message: str = "Cross-origin request rejected."):
    super().__init__(message=message, code="ORIGIN_VALIDATION_FAILED", status_code=403)


class PasswordPolicyError(AuthError):
  """Raised when a submitted password fails length, complexity, or blocklist checks."""
  def __init__(self, message: str = "Password does not meet security requirements.", details: Any = None):
    super().__init__(message=message, code="WEAK_PASSWORD", status_code=422, details=details)


class RegistrationDisabledError(AuthError):
  """Raised when registration is attempted but AUTH_ALLOW_REGISTRATION is False."""
  def __init__(self, message: str = "User registration is currently disabled.", details: Any = None):
    super().__init__(message=message, code="REGISTRATION_DISABLED", status_code=403, details=details)


class EmailAlreadyExistsError(AuthError):
  """Raised when registering with an email address that is already in use."""
  def __init__(self, message: str = "An account with this email already exists.", details: Any = None):
    super().__init__(message=message, code="EMAIL_ALREADY_EXISTS", status_code=409, details=details)


class PasswordResetInvalidError(AuthError):
  """Raised when a password reset token is invalid, expired, or already used."""
  def __init__(self, message: str = "Password reset link is invalid or has expired."):
    super().__init__(message=message, code="INVALID_RESET_TOKEN", status_code=400)


class RateLimitExceededError(AuthError):
  """Raised when authentication throttling is triggered."""
  def __init__(self, message: str = "Too many attempts. Please try again later.", details: Any = None):
    super().__init__(message=message, code="RATE_LIMIT_EXCEEDED", status_code=429, details=details)



def create_error_response(
    code: str, message: str, details: Any = None, status_code: int = 400
) -> JSONResponse:
  """Build a standardized JSON error response."""
  payload = {
      "error": {
          "code": code,
          "message": message,
          "details": details,
      }
  }
  return JSONResponse(status_code=status_code, content=payload)


def register_error_handlers(app: FastAPI) -> None:
  """Attach uniform error and exception handlers to the FastAPI app."""

  @app.exception_handler(RequestValidationError)
  async def validation_exception_handler(
      request: Request, exc: RequestValidationError
  ) -> JSONResponse:
    logger.warning("Validation failed for %s %s: %s", request.method, request.url.path, exc.errors())
    # Format field errors cleanly
    field_errors = []
    for err in exc.errors():
      loc = " -> ".join(str(item) for item in err.get("loc", []))
      field_errors.append({
          "location": loc,
          "message": err.get("msg", "Invalid value"),
          "type": err.get("type", "value_error"),
      })
    return create_error_response(
        code="VALIDATION_ERROR",
        message="Invalid request parameters or payload format.",
        details=field_errors,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )

  @app.exception_handler(StarletteHTTPException)
  async def http_exception_handler(
      request: Request, exc: StarletteHTTPException
  ) -> JSONResponse:
    code = "NOT_FOUND" if exc.status_code == 404 else f"HTTP_{exc.status_code}"
    message = exc.detail if isinstance(exc.detail, str) else "HTTP request error."
    return create_error_response(
        code=code,
        message=message,
        details=None,
        status_code=exc.status_code,
    )

  @app.exception_handler(GeminiError)
  async def gemini_exception_handler(
      request: Request, exc: GeminiError
  ) -> JSONResponse:
    logger.warning("Gemini AI error on %s %s: [%s] %s", request.method, request.url.path, exc.code, exc.message)
    details = getattr(exc, "details", None)
    return create_error_response(
        code=exc.code,
        message=exc.message,
        details=details,
        status_code=exc.status_code,
    )

  @app.exception_handler(DocumentError)
  async def document_exception_handler(
      request: Request, exc: DocumentError
  ) -> JSONResponse:
    logger.warning("Document error on %s %s: [%s] %s", request.method, request.url.path, exc.code, exc.message)
    return create_error_response(
        code=exc.code,
        message=exc.message,
        details=exc.details,
        status_code=exc.status_code,
    )

  @app.exception_handler(Exception)
  async def unhandled_exception_handler(
      request: Request, exc: Exception
  ) -> JSONResponse:
    # Log full trace on the server, but return generic message to client to avoid leaking internals
    logger.exception("Unhandled internal exception on %s %s: %s", request.method, request.url.path, exc)
    return create_error_response(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred. Please try again later.",
        details=None,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
