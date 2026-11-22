"""Stateless CSRF token generation, HMAC verification, and Origin validation."""

import hashlib
import hmac
import logging
from typing import List, Optional
from urllib.parse import urlparse

from app.core.config import get_settings

logger = logging.getLogger("civiclens.auth.csrf")


def generate_csrf_token(secret_key: str, session_token_hash: str) -> str:
  """Derive a stateless HMAC-SHA256 CSRF token from the session token hash and secret."""
  if not secret_key or not session_token_hash:
    return ""
  return hmac.new(
      secret_key.encode("utf-8"),
      session_token_hash.encode("utf-8"),
      hashlib.sha256,
  ).hexdigest()


def verify_csrf_token(secret_key: str, session_token_hash: str, submitted_token: Optional[str]) -> bool:
  """Constant-time comparison between submitted CSRF token and expected HMAC token."""
  if not submitted_token or not secret_key or not session_token_hash:
    return False

  expected = generate_csrf_token(secret_key, session_token_hash)
  return hmac.compare_digest(expected, submitted_token.strip())


def normalize_origin(url_str: str) -> str:
  """Extract scheme://host[:port] from an Origin or Referer URL."""
  if not url_str:
    return ""
  try:
    parsed = urlparse(url_str)
    if not parsed.scheme or not parsed.netloc:
      return ""
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
  except Exception:
    return ""


def verify_origin(origin_header: Optional[str], referer_header: Optional[str]) -> bool:
  """Validate request Origin or Referer against configured allowed frontend origins."""
  settings = get_settings()

  # Build complete set of valid origins
  allowed_set = set()
  for orig in settings.CORS_ORIGINS:
    norm = normalize_origin(orig)
    if norm:
      allowed_set.add(norm.lower())

  frontend_norm = normalize_origin(settings.FRONTEND_BASE_URL)
  if frontend_norm:
    allowed_set.add(frontend_norm.lower())

  # Always include local dev Vite and backend origins if in development
  if settings.APP_ENV == "development":
    allowed_set.add("http://localhost:5173")
    allowed_set.add("http://127.0.0.1:5173")
    allowed_set.add("http://localhost:8000")
    allowed_set.add("http://127.0.0.1:8000")

  candidate = origin_header or referer_header
  if not candidate:
    # If in development or running API tests without browser Origin, allow
    if settings.APP_ENV == "development" or settings.TESTING:
      return True
    return False

  normalized_candidate = normalize_origin(candidate).lower()
  return normalized_candidate in allowed_set
