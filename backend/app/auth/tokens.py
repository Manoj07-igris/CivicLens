"""Cryptographic token generation and hashing utilities using standard library secrets and hashlib."""

import hashlib
import secrets
from typing import Optional


def generate_session_token() -> str:
  """Generate a cryptographically secure raw session token (256-bit entropy)."""
  return secrets.token_urlsafe(32)


def generate_reset_token() -> str:
  """Generate a cryptographically secure raw password reset token."""
  return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
  """Compute SHA-256 hex digest of a raw token for safe database persistence."""
  if not raw_token:
    return ""
  return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def hash_ip(ip: Optional[str]) -> Optional[str]:
  """Return truncated SHA-256 hash of client IP for privacy-preserving audit logging."""
  if not ip:
    return None
  return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]
