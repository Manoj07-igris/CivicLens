"""Pydantic data models for the Curated Official Portal Registry."""

from typing import List, Optional, Literal
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator


PortalKind = Literal["official", "official_portal", "informational", "grievance", "demo"]
PortalStatus = Literal["active", "deprecated", "maintenance"]
PortalScope = Literal["state", "central", "local", "all"]


class PortalBase(BaseModel):
  name: str = Field(..., min_length=2, max_length=150, description="Portal name in English")
  name_ta: Optional[str] = Field(None, max_length=200, description="Portal name in Tamil")
  url: str = Field(..., max_length=500, description="Valid HTTPS portal URL")
  description: str = Field(..., min_length=5, max_length=1000, description="Brief description of the portal")
  description_ta: Optional[str] = Field(None, max_length=1500, description="Brief description in Tamil")
  department: Optional[str] = Field(None, max_length=150, description="Government department or ministry")
  service_types: List[str] = Field(default_factory=list, description="Services offered, e.g. certificates, revenue, welfare")
  kind: PortalKind = Field(default="official_portal", description="Category of portal")
  scope: PortalScope = Field(default="state", description="Jurisdictional scope")
  state_or_union_territory: Optional[str] = Field(default="Tamil Nadu", max_length=100)
  status: PortalStatus = Field(default="active", description="Status of portal")
  linked_source_ids: List[str] = Field(default_factory=list, description="IDs of official sources in SourceLibrary")
  keywords: List[str] = Field(default_factory=list, description="Search keywords in English and Tamil")
  caution_notes: Optional[str] = Field(None, max_length=500, description="Important caveats (e.g. requires Aadhaar login)")
  # Phase 13 additions for Civic Grievance channels (backward-compatible defaults)
  grievance_categories: List[str] = Field(default_factory=list, description="Grievance categories handled by this portal channel")
  coverage_area: Optional[str] = Field(default="", max_length=200, description="Declared coverage area (e.g. city or district name in EN/TA)")
  # Phase 14 addition for system-managed portals
  system: bool = Field(default=False, description="System-managed portal entry that cannot be edited or deleted")

  @field_validator("url")
  @classmethod
  def validate_url(cls, v: str) -> str:
    v = v.strip()
    parsed = urlparse(v)
    if parsed.scheme not in ("https", "http"):
      raise ValueError("Portal URL must start with https://")
    if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
      raise ValueError("Official portals must use HTTPS (http:// is only allowed for local demo/testing)")
    if parsed.username or parsed.password:
      raise ValueError("Portal URL must not contain user credentials")
    if not parsed.hostname:
      raise ValueError("Portal URL must include a valid hostname")
    return v


class PortalCreateRequest(PortalBase):
  """Request payload to create a new portal registry entry."""
  pass


class PortalUpdateRequest(BaseModel):
  """Request payload to update an existing portal registry entry."""
  name: Optional[str] = Field(None, min_length=2, max_length=150)
  name_ta: Optional[str] = Field(None, max_length=200)
  url: Optional[str] = Field(None, max_length=500)
  description: Optional[str] = Field(None, min_length=5, max_length=1000)
  description_ta: Optional[str] = Field(None, max_length=1500)
  department: Optional[str] = Field(None, max_length=150)
  service_types: Optional[List[str]] = None
  kind: Optional[PortalKind] = None
  scope: Optional[PortalScope] = None
  state_or_union_territory: Optional[str] = None
  status: Optional[PortalStatus] = None
  linked_source_ids: Optional[List[str]] = None
  keywords: Optional[List[str]] = None
  caution_notes: Optional[str] = None
  grievance_categories: Optional[List[str]] = None
  coverage_area: Optional[str] = None

  @field_validator("url")
  @classmethod
  def validate_url(cls, v: Optional[str]) -> Optional[str]:
    if v is None:
      return None
    v = v.strip()
    parsed = urlparse(v)
    if parsed.scheme not in ("https", "http"):
      raise ValueError("Portal URL must start with https://")
    if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
      raise ValueError("Official portals must use HTTPS (http:// is only allowed for local demo/testing)")
    if parsed.username or parsed.password:
      raise ValueError("Portal URL must not contain credentials")
    if not parsed.hostname:
      raise ValueError("Portal URL must include a valid hostname")
    return v


class PortalEntry(PortalBase):
  """Stored official portal record."""
  id: str = Field(..., description="Unique portal ID, e.g. prt_xxx")
  domain_hint: str = Field(..., description="Hostname derived from URL, e.g. tnesevai.tn.gov.in")
  created_at: str
  updated_at: str


class PortalListResponse(BaseModel):
  """Response listing registered portals."""
  total: int
  portals: List[PortalEntry]


class PortalMatchResult(BaseModel):
  """Matched portal item with relevance scoring and reason."""
  portal: PortalEntry
  match_score: float
  match_reason: str


class GrievanceChannelMatch(BaseModel):
  """Vetted reporting channel matched for a civic complaint category."""
  portal_id: str
  name: str
  name_ta: Optional[str] = None
  url: str
  domain_hint: str
  department: Optional[str] = None
  coverage_area: str = ""
  match_basis: str
  caution_notes: Optional[str] = None


class GrievanceChannelsResult(BaseModel):
  """Result of matching grievance channels against the curated registry."""
  channels: List[GrievanceChannelMatch] = Field(default_factory=list)
  declared_notice: str = (
      "Added by the app owner. CivicLens does not check or visit this link. "
      "Confirm the address before entering personal information."
  )
  generic_guidance: List[str] = Field(default_factory=list)
