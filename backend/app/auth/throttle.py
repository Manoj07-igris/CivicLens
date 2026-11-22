"""Persistent rate limiting and exponential lockout using SQLite auth_throttle table."""

import datetime
import hashlib
import logging
from typing import Optional

from app.core.errors import RateLimitExceededError
from app.db.database import Database, utc_now_iso

logger = logging.getLogger("civiclens.auth.throttle")


def _key_to_hash(key: str) -> str:
  return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _parse_iso(timestamp_str: Optional[str]) -> Optional[datetime.datetime]:
  if not timestamp_str:
    return None
  try:
    return datetime.datetime.fromisoformat(timestamp_str)
  except Exception:
    return None


def check_throttle(
    db: Database,
    key: str,
) -> None:
  """Check if an action is currently throttled/locked out.

  Raises RateLimitExceededError with retry_after seconds if currently locked.
  """
  h = _key_to_hash(key)
  row = db.fetchone(
      "SELECT locked_until FROM auth_throttle WHERE key_hash = ?;",
      (h,),
  )
  if not row or not row["locked_until"]:
    return

  locked_until = _parse_iso(row["locked_until"])
  if not locked_until:
    return

  now = datetime.datetime.now(datetime.timezone.utc)
  if now < locked_until:
    retry_after = max(1, int((locked_until - now).total_seconds()))
    logger.warning("Throttle hit for key '%s': retry in %d seconds.", key, retry_after)
    raise RateLimitExceededError(
        message=f"Too many attempts. Please try again in {retry_after} seconds.",
        details={"retry_after": retry_after, "key": key},
    )


def record_failure(
    db: Database,
    key: str,
    max_attempts: int = 5,
    base_delay_seconds: int = 2,
    max_delay_seconds: int = 900,
) -> None:
  """Record a failed attempt and apply exponential lockout if threshold exceeded."""
  now_dt = datetime.datetime.now(datetime.timezone.utc)
  now_str = now_dt.isoformat()
  h = _key_to_hash(key)

  row = db.fetchone(
      "SELECT count, window_start, locked_until FROM auth_throttle WHERE key_hash = ?;",
      (h,),
  )

  if not row:
    db.execute(
        "INSERT INTO auth_throttle (key_hash, window_start, count, locked_until) VALUES (?, ?, 1, NULL);",
        (h, now_str),
    )
    return

  attempts = row["count"] + 1
  locked_until_str: Optional[str] = None

  if attempts >= max_attempts:
    # Exponential backoff: base_delay * 2^(attempts - max_attempts) capped at max_delay_seconds
    multiplier = 2 ** min(attempts - max_attempts, 10)
    delay_seconds = min(max_delay_seconds, base_delay_seconds * multiplier)
    locked_until_dt = now_dt + datetime.timedelta(seconds=delay_seconds)
    locked_until_str = locked_until_dt.isoformat()

  db.execute(
      "UPDATE auth_throttle SET count = ?, locked_until = ? WHERE key_hash = ?;",
      (attempts, locked_until_str, h),
  )


def clear_throttle(db: Database, key: str) -> None:
  """Clear lockout and attempt counters upon successful action."""
  try:
    h = _key_to_hash(key)
    db.execute("DELETE FROM auth_throttle WHERE key_hash = ?;", (h,))
  except Exception as exc:
    logger.warning("Could not clear throttle for key '%s': %s", key, exc)
