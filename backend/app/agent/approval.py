"""In-memory approval store for sensitive or irreversible agent tools."""

from dataclasses import dataclass, field
import datetime
import threading
from typing import Any, Dict, List, Optional
import uuid

from app.core.errors import DocumentNotFoundError, DocumentProcessingError
from app.models.agent import PendingApprovalInfo


@dataclass
class PendingApproval:
  """Record of a tool invocation paused pending human approval."""
  approval_id: str
  tool_name: str
  description: str
  args: Dict[str, Any]
  run_state: Dict[str, Any]
  created_at: datetime.datetime
  expires_at: datetime.datetime
  user_id: Optional[str] = None

  def to_info(self) -> PendingApprovalInfo:
    return PendingApprovalInfo(
        approval_id=self.approval_id,
        tool_name=self.tool_name,
        description=self.description,
        args=self.args,
        expires_at=self.expires_at.isoformat(),
    )


class ApprovalStore:
  """Thread-safe in-memory store for pending tool approvals."""

  def __init__(self, expiry_minutes: int = 10) -> None:
    self.expiry_minutes = expiry_minutes
    self._store: Dict[str, PendingApproval] = {}
    self._lock = threading.Lock()

  def create_approval(
      self,
      tool_name: str,
      description: str,
      args: Dict[str, Any],
      run_state: Dict[str, Any],
      user_id: Optional[str] = None,
  ) -> PendingApproval:
    """Register a new pending approval and return its descriptor."""
    approval_id = f"appr_{uuid.uuid4().hex[:12]}"
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(minutes=self.expiry_minutes)

    appr = PendingApproval(
        approval_id=approval_id,
        tool_name=tool_name,
        description=description,
        args=args,
        run_state=run_state,
        created_at=now,
        expires_at=expires_at,
        user_id=user_id,
    )

    with self._lock:
      self._cleanup_expired()
      self._store[approval_id] = appr

    return appr

  def get_and_consume(
      self,
      approval_id: str,
      user_id: Optional[str] = None,
      is_admin: bool = False,
  ) -> PendingApproval:
    """Retrieve and atomically remove an active pending approval.

    Raises DocumentNotFoundError if approval_id is unknown or expired.
    """
    with self._lock:
      self._cleanup_expired()
      appr = self._store.get(approval_id)
      if not appr:
        raise DocumentNotFoundError(
            f"Approval request '{approval_id}' was not found, has expired, or was already decided."
        )
      # Check ownership: non-admin users cannot access another user's approval
      if user_id and appr.user_id and appr.user_id != user_id and not is_admin:
        raise DocumentNotFoundError(
            f"Approval request '{approval_id}' was not found, has expired, or was already decided."
        )
      appr = self._store.pop(approval_id)

    now = datetime.datetime.now(datetime.timezone.utc)
    if appr.expires_at < now:
      raise DocumentProcessingError(
          f"Approval request '{approval_id}' has expired. Please re-issue your request."
      )

    return appr

  def clear(self) -> None:
    """Clear all approvals (used between tests)."""
    with self._lock:
      self._store.clear()

  def _cleanup_expired(self) -> None:
    """Remove expired records."""
    now = datetime.datetime.now(datetime.timezone.utc)
    expired_keys = [k for k, v in self._store.items() if v.expires_at < now]
    for k in expired_keys:
      self._store.pop(k, None)


_approval_store_instance: Optional[ApprovalStore] = None


def get_approval_store() -> ApprovalStore:
  """Dependency provider for shared ApprovalStore."""
  global _approval_store_instance
  if _approval_store_instance is None:
    _approval_store_instance = ApprovalStore()
  return _approval_store_instance


def set_approval_store(store: Optional[ApprovalStore]) -> None:
  """Test helper to inject or reset the ApprovalStore."""
  global _approval_store_instance
  _approval_store_instance = store
