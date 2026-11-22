"""Grievance storage service for CivicLens (Module 5).

Persists grievance analysis records and simulated tracking state.
Backed by SqliteGrievanceStore in Phase 15.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.core.config import Settings, get_settings
from app.core.errors import DocumentNotFoundError
from app.db.stores import SqliteGrievanceStore
from app.models.grievance import Grievance

logger = logging.getLogger("civiclens.grievance.store")


class GrievanceNotFoundError(DocumentNotFoundError):
  """Raised when a requested grievance record is not found."""
  pass


# Alias GrievanceStore to SqliteGrievanceStore for transparent Phase 15 SQLite persistence
GrievanceStore = SqliteGrievanceStore


_grievance_store: Optional[GrievanceStore] = None


def get_grievance_store() -> GrievanceStore:
  global _grievance_store
  if _grievance_store is None:
    _grievance_store = GrievanceStore()
  return _grievance_store


def set_grievance_store(store: Optional[GrievanceStore]) -> None:
  global _grievance_store
  _grievance_store = store
