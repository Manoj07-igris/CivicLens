"""Argon2id password hashing, verification, timing equalization, and policy validation."""

import asyncio
import logging
from pathlib import Path
import re
import threading
from typing import Optional, Set, Tuple
import unicodedata

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings
from app.core.errors import PasswordPolicyError

logger = logging.getLogger("civiclens.auth.passwords")

# Load common passwords blocklist
_COMMON_PASSWORDS: Set[str] = set()
_PASSWORDS_FILE = Path(__file__).resolve().parent / "common_passwords.txt"
if _PASSWORDS_FILE.is_file():
  try:
    with open(_PASSWORDS_FILE, "r", encoding="utf-8") as f:
      for line in f:
        clean = line.strip().lower()
        if clean and not clean.startswith("#"):
          _COMMON_PASSWORDS.add(clean)
    logger.info("Loaded %d common passwords into policy blocklist.", len(_COMMON_PASSWORDS))
  except Exception as exc:
    logger.warning("Could not load common passwords list: %s", exc)

_settings = get_settings()

# Initialize Argon2id password hasher with configured parameters
_hasher = PasswordHasher(
    time_cost=_settings.AUTH_ARGON2_TIME_COST,
    memory_cost=_settings.AUTH_ARGON2_MEMORY_COST_KIB,
    parallelism=_settings.AUTH_ARGON2_PARALLELISM,
    hash_len=32,
    salt_len=16,
)

# Concurrency semaphore to bound peak CPU and memory on constrained hardware
_argon2_semaphore = threading.BoundedSemaphore(value=_settings.AUTH_ARGON2_MAX_CONCURRENT)

# Precomputed dummy hash for timing attack mitigation on non-existent users
try:
  _DUMMY_HASH = _hasher.hash("civiclens_dummy_hash_for_timing_safety_2026")
except Exception:
  _DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=1$c29tZXNhbHRzb21lc2FsdA$u2P98T+G1eG+t1b6D5Yv7lQe+8sJ3lVb1Q7W4e6R9oA"


def normalize_password(password: str) -> str:
  """Normalize password unicode characters using Unicode NFC."""
  if not password:
    return ""
  return unicodedata.normalize("NFC", password)


def validate_password_policy(
    password: str,
    user_email: Optional[str] = None,
    user_name: Optional[str] = None,
) -> None:
  """Validate that a candidate password conforms to CivicLens security standards.

  Agreed server policy:
  1. Minimum 12 characters, maximum 128 characters.
  2. Not in the common/breached passwords blocklist.
  3. Does not contain user's email username or full name tokens (>=4 chars).
  4. Not repetitive or a simple sequence.
  5. NO forced character-type composition rules (spaces and any Unicode allowed).
  """
  normalized = normalize_password(password)

  if len(normalized) < 12:
    raise PasswordPolicyError(
        "Password must be at least 12 characters long.",
        details={"code": "password_too_short"},
    )

  if len(normalized) > 128:
    raise PasswordPolicyError(
        "Password must not exceed 128 characters.",
        details={"code": "password_too_long"},
    )

  # Check against common passwords blocklist (case-insensitive)
  lower_pwd = normalized.lower()
  if lower_pwd in _COMMON_PASSWORDS:
    raise PasswordPolicyError(
        "This password is too common and easily guessed. Please choose a more unique passphrase.",
        details={"code": "password_common"},
    )

  # Check simple repetitions and sequences (e.g., "aaaaaaaaaaaa", "123412341234", "abcabcabc")
  if len(set(normalized)) <= 2:
    raise PasswordPolicyError(
        "Password contains repetitive repeating sequences.",
        details={"code": "password_repetitive"},
    )

  if re.search(r"(.)\1{3,}", normalized) or re.search(r"(.{2,4})\1{2,}", normalized):
    raise PasswordPolicyError(
        "Password contains repetitive repeating sequences.",
        details={"code": "password_repetitive"},
    )

  # Check sequential patterns like "123456789012" or "abcdefghijkl"
  sequences = ["0123456789012345", "9876543210987654", "abcdefghijklmnopqrstuvwxyz", "zyxwvutsrqponmlkjihgfedcba"]
  for seq in sequences:
    if any(seq[i : i + 6] in lower_pwd for i in range(len(seq) - 5)):
      raise PasswordPolicyError(
          "Password contains repetitive repeating sequences.",
          details={"code": "password_repetitive"},
      )

  # Check if email prefix is contained
  if user_email:
    local_part = user_email.split("@")[0].lower()
    clean_local = re.sub(r"[^a-z0-9]", "", local_part)
    if len(clean_local) >= 4 and clean_local in lower_pwd:
      raise PasswordPolicyError(
          "Password must not contain parts of your email address.",
          details={"code": "password_contains_personal_info"},
      )

  # Check if full name tokens are contained
  if user_name:
    tokens = re.split(r"[\s,._-]+", user_name.lower())
    for token in tokens:
      clean_token = re.sub(r"[^a-z0-9]", "", token)
      if len(clean_token) >= 4 and clean_token in lower_pwd:
        raise PasswordPolicyError(
            "Password must not contain parts of your name.",
            details={"code": "password_contains_personal_info"},
        )


def hash_password(password: str) -> str:
  """Hash a password with Argon2id using the bounded concurrency semaphore."""
  normalized = normalize_password(password)
  with _argon2_semaphore:
    return _hasher.hash(normalized)


def verify_password(password: str, hashed: str) -> Tuple[bool, bool]:
  """Verify candidate password against Argon2id hash.

  Returns:
    (is_valid, needs_rehash): is_valid is True if password matches.
    needs_rehash is True if Argon2 cost parameters have changed and the hash should be updated.
  """
  if not password or not hashed:
    return False, False

  normalized = normalize_password(password)
  with _argon2_semaphore:
    try:
      _hasher.verify(hashed, normalized)
      needs_rehash = _hasher.check_needs_rehash(hashed)
      return True, needs_rehash
    except (VerifyMismatchError, VerificationError, InvalidHashError):
      return False, False
    except Exception as exc:
      logger.warning("Unexpected error during Argon2 verification: %s", exc)
      return False, False


def dummy_verify() -> None:
  """Perform dummy Argon2 verification to equalize timing for non-existent users."""
  with _argon2_semaphore:
    try:
      _hasher.verify(_DUMMY_HASH, "incorrect_dummy_candidate_string")
    except Exception:
      pass
