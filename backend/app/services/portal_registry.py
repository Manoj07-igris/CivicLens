"""Curated Official Portal Registry Service.

Stores and matches vetted official government service portals.
Ensures zero hallucinated links: all portal links shown to citizens
come exclusively from the owner-maintained registry.json.
"""

import datetime
import logging
from pathlib import Path
import re
import threading
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import uuid

from app.core.config import Settings, get_settings
from app.core.errors import PortalNotFoundError, PortalRegistryError
from app.models.portal import (
    GrievanceChannelMatch,
    GrievanceChannelsResult,
    PortalCreateRequest,
    PortalEntry,
    PortalMatchResult,
    PortalUpdateRequest,
)
from app.services.document_store import atomic_write_json, read_json_safe
from app.db.stores import SqlitePortalRegistryStore

logger = logging.getLogger("civiclens.portals")

# Alias PortalRegistryStore to SqlitePortalRegistryStore for transparent Phase 15 SQLite persistence
PortalRegistryStore = SqlitePortalRegistryStore


SYSTEM_DEMO_PORTAL_ID = "prt_demo_portal"
SYSTEM_DEMO_PORTAL = {
    "name": "CivicLens Demo Public Service Portal",
    "name_ta": "CivicLens மாதிரி பொது சேவை வலைவாசல்",
    "url": "http://127.0.0.1:8000/demo-portal/",
    "description": "Safe, educational local demo portal for practicing public certificate application workflows (Income Certificate) without submitting real personal data.",
    "description_ta": "உண்மையான தனிநபர் தரவைச் சமர்ப்பிக்காமல் வருமானச் சான்றிதழ் விண்ணப்ப நடைமுறைகளைப் பயிற்சி செய்வதற்கான பாதுகாப்பான கல்வி மாதிரி வலைவாசல்.",
    "department": "Department of Revenue & Digital Governance (DEMO)",
    "service_types": ["demo", "certificates", "income_certificate", "educational_simulation"],
    "kind": "demo",
    "scope": "local",
    "state_or_union_territory": "Tamil Nadu (Demo)",
    "status": "active",
    "system": True,
    "linked_source_ids": [],
    "keywords": ["demo", "simulation", "income certificate", "playwright", "practice", "மாதிரி", "வருமான சான்றிதழ்"],
    "caution_notes": "EDUCATIONAL DEMO ONLY: Runs strictly on localhost. No real data is saved or submitted to any government server. Use fictional data only.",
    "grievance_categories": [],
    "coverage_area": "Demo Simulation Sandbox",
    "id": SYSTEM_DEMO_PORTAL_ID,
    "domain_hint": "127.0.0.1",
    "created_at": "2026-11-21T00:00:00Z",
    "updated_at": "2026-11-21T00:00:00Z"
}


class PortalRegistryStore:
  """Filesystem storage manager for backend/data/portals/registry.json."""

  def __init__(self, settings: Optional[Settings] = None, base_dir: Optional[Path] = None):
    self._settings = settings or get_settings()
    self._base_dir: Path = base_dir or self._settings.portals_dir
    self._base_dir.mkdir(parents=True, exist_ok=True)
    self._registry_file = self._base_dir / "registry.json"
    self._lock = threading.Lock()

  def read_all(self) -> Dict[str, PortalEntry]:
    with self._lock:
      data = read_json_safe(self._registry_file)
      portals = {}
      if isinstance(data, dict):
        for pid, entry_dict in data.items():
          try:
            portals[pid] = PortalEntry(**entry_dict)
          except Exception as exc:
            logger.warning("Skipping corrupted portal entry %s: %s", pid, exc)
      if SYSTEM_DEMO_PORTAL_ID not in portals:
        demo_entry = PortalEntry(**SYSTEM_DEMO_PORTAL)
        portals[SYSTEM_DEMO_PORTAL_ID] = demo_entry
        # Persist system portal seed
        try:
          payload = {pid: p.model_dump() for pid, p in portals.items()}
          atomic_write_json(self._registry_file, payload)
        except Exception as exc:
          logger.warning("Could not persist system demo portal seed: %s", exc)
      return portals

  def save_all(self, portals: Dict[str, PortalEntry]) -> None:
    with self._lock:
      payload = {pid: p.model_dump() for pid, p in portals.items()}
      atomic_write_json(self._registry_file, payload)


from app.db.stores import SqlitePortalRegistryStore
PortalRegistryStore = SqlitePortalRegistryStore


class PortalRegistryService:
  """Service for managing and matching official government portals."""

  def __init__(self, store: Optional[PortalRegistryStore] = None):
    self._store = store or PortalRegistryStore()

  def list_portals(
      self,
      service_type: Optional[str] = None,
      scope: Optional[str] = None,
      status: Optional[str] = "active",
      kind: Optional[str] = None,
  ) -> List[PortalEntry]:
    portals = self._store.read_all()
    results = []
    for p in portals.values():
      if status and p.status != status:
        continue
      if scope and p.scope != scope and p.scope != "all":
        continue
      if kind and p.kind != kind:
        continue
      if service_type and service_type.lower() not in [s.lower() for s in p.service_types]:
        continue
      results.append(p)
    results.sort(key=lambda x: x.created_at, reverse=True)
    return results

  def get_portal(self, portal_id: str) -> PortalEntry:
    portals = self._store.read_all()
    if portal_id not in portals:
      raise PortalNotFoundError(f"Portal '{portal_id}' not found in registry.")
    return portals[portal_id]

  def create_portal(self, req: PortalCreateRequest) -> PortalEntry:
    portals = self._store.read_all()
    portal_id = f"prt_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    parsed = urlparse(req.url)
    domain_hint = (parsed.netloc or "").lower()

    entry = PortalEntry(
        id=portal_id,
        domain_hint=domain_hint,
        created_at=now_iso,
        updated_at=now_iso,
        **req.model_dump(),
    )
    portals[portal_id] = entry
    self._store.save_all(portals)
    try:
      from app.db.stores import SqlitePortalRegistryStore
      SqlitePortalRegistryStore().save_portal(entry)
    except Exception:
      pass
    from app.services.activity_service import get_activity_service
    get_activity_service().record_activity("portal.added", "portal", portal_id)
    logger.info("Registered official portal %s: %s (%s)", portal_id, entry.name, entry.url)
    return entry

  def update_portal(self, portal_id: str, req: PortalUpdateRequest) -> PortalEntry:
    portals = self._store.read_all()
    if portal_id not in portals:
      raise PortalNotFoundError(f"Portal '{portal_id}' not found in registry.")
    existing = portals[portal_id]
    if getattr(existing, "system", False):
      raise PortalRegistryError("System-managed portal entries cannot be modified.", code="SYSTEM_PORTAL_PROTECTED", status_code=403)
    updates = req.model_dump(exclude_unset=True)
    if "url" in updates and updates["url"]:
      parsed = urlparse(updates["url"])
      updates["domain_hint"] = (parsed.netloc or "").lower()
    updates["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    updated_dict = existing.model_dump()
    updated_dict.update(updates)
    updated_entry = PortalEntry(**updated_dict)
    portals[portal_id] = updated_entry
    self._store.save_all(portals)
    logger.info("Updated portal %s: %s", portal_id, updated_entry.name)
    return updated_entry

  def delete_portal(self, portal_id: str) -> bool:
    portals = self._store.read_all()
    if portal_id not in portals:
      raise PortalNotFoundError(f"Portal '{portal_id}' not found in registry.")
    existing = portals[portal_id]
    if getattr(existing, "system", False):
      raise PortalRegistryError("System-managed portal entries cannot be deleted.", code="SYSTEM_PORTAL_PROTECTED", status_code=403)
    del portals[portal_id]
    self._store.save_all(portals)
    try:
      from app.db.stores import SqlitePortalRegistryStore
      SqlitePortalRegistryStore().delete_portal(portal_id)
    except Exception:
      pass
    logger.info("Deleted portal %s from registry", portal_id)
    return True

  def match_portals(
      self,
      query: str,
      linked_source_ids: Optional[List[str]] = None,
      limit: int = 3,
      allow_demo: bool = False,
  ) -> List[PortalMatchResult]:
    """Deterministically rank and match portals for a citizen's query.

    Matches portals by:
    1. Direct association with cited official source IDs (linked_source_ids)
    2. Exact service_type substring match in the query
    3. Multilingual keyword token overlap in name, description, and keywords
    Never returns demo portals unless allow_demo is True.
    """
    portals = self._store.read_all()
    if not portals:
      return []

    tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 1]
    query_lower = query.lower()
    linked_set = set(linked_source_ids or [])

    scored: List[Tuple[float, str, PortalEntry]] = []

    for p in portals.values():
      if p.status != "active":
        continue
      if p.kind == "demo" and not allow_demo:
        continue

      score = 0.0
      reasons: List[str] = []

      # 1. Linked source match
      overlapping_sources = set(p.linked_source_ids).intersection(linked_set)
      if overlapping_sources:
        score += 10.0 + len(overlapping_sources) * 2.0
        reasons.append(f"Linked to cited official source ({len(overlapping_sources)} match)")

      # 2. Service type exact match
      for st in p.service_types:
        st_clean = st.lower().replace("_", " ")
        if st_clean in query_lower:
          score += 5.0
          reasons.append(f"Direct match for service type '{st}'")
          break

      # 3. Keyword / token matches
      token_hits = 0
      text_corpus = f"{p.name} {p.name_ta or ''} {p.description} {p.description_ta or ''} {' '.join(p.keywords)}".lower()
      for token in tokens:
        if token in text_corpus:
          token_hits += 1

      if token_hits > 0:
        score += min(token_hits * 1.5, 6.0)
        reasons.append(f"Keyword match ({token_hits} terms)")

      if score > 0:
        reason_str = "; ".join(reasons) if reasons else "Keyword match"
        scored.append((score, reason_str, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [
        PortalMatchResult(portal=p, match_score=round(s, 2), match_reason=r)
        for s, r, p in scored[:limit]
    ]
    return results

  def match_channels(
      self,
      category: str,
      location_text: str = "",
      limit: int = 3,
  ) -> GrievanceChannelsResult:
    """Deterministically match official complaint channels for a grievance category.

    Filters strictly for portals where:
    - kind is 'official' or 'official_portal'
    - status is 'active'
    - grievance_categories contains the requested category

    Ranks by:
    1. Overlap of coverage_area tokens with location_text (Unicode/Tamil supported)
    2. Presence of verified linked official sources

    Returns a GrievanceChannelsResult with caution notices and generic fallback guidance.
    """
    portals = self._store.read_all()
    target_cat = category.lower().strip()
    loc_tokens = set(re.findall(r"[\w\u0b80-\u0bff]+", location_text.lower()))

    scored: List[Tuple[float, str, PortalEntry]] = []

    for p in portals.values():
      if p.status != "active":
        continue
      if p.kind not in ("official", "official_portal"):
        continue

      cats = [c.lower().strip() for c in (p.grievance_categories or [])]
      if target_cat not in cats and "all" not in cats:
        continue

      # Base match: handles this category
      score = 2.0
      basis = "handles this category"

      # Check coverage area token overlap
      if p.coverage_area and loc_tokens:
        area_tokens = set(re.findall(r"[\w\u0b80-\u0bff]+", p.coverage_area.lower()))
        overlap = loc_tokens.intersection(area_tokens)
        if overlap:
          score += 10.0 + len(overlap) * 2.0
          basis = "handles this category and area text matches"

      # Tie-breaker: linked sources
      if p.linked_source_ids:
        score += 0.5 * len(p.linked_source_ids)

      scored.append((score, basis, p))

    # Static generic guidance if no official channels are matched
    generic_guidance = [
        "Identify the local municipal corporation, municipality, or panchayat department responsible for your area.",
        "Obtain the designated official office address or verified grievance desk from official government directories.",
        "Keep a signed or dated copy of your complaint representation for your personal records.",
        "Note the date, time, and specific location landmarks in all correspondence.",
    ]

    if not scored:
      return GrievanceChannelsResult(
          channels=[],
          generic_guidance=generic_guidance,
      )

    scored.sort(key=lambda x: x[0], reverse=True)
    matches: List[GrievanceChannelMatch] = []

    for _, basis, p in scored[:limit]:
      coverage_str = f"Covers: {p.coverage_area}" if p.coverage_area else "Covers: As declared by the app owner"
      matches.append(
          GrievanceChannelMatch(
              portal_id=p.id,
              name=p.name,
              name_ta=p.name_ta,
              url=p.url,
              domain_hint=p.domain_hint,
              department=p.department,
              coverage_area=coverage_str,
              match_basis=basis,
              caution_notes=p.caution_notes,
          )
      )

    return GrievanceChannelsResult(
        channels=matches,
        generic_guidance=generic_guidance if len(matches) == 0 else [],
    )


_portal_service: Optional[PortalRegistryService] = None


def get_portal_registry_service() -> PortalRegistryService:
  global _portal_service
  if _portal_service is None:
    _portal_service = PortalRegistryService()
  return _portal_service


def set_portal_registry_service(service: Optional[PortalRegistryService]) -> None:
  global _portal_service
  _portal_service = service
