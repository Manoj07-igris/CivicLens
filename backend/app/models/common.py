from typing import Any, List, Optional
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
  """Response model for service health check."""

  status: str = Field(default="ok", description="Operational status")
  service: str = Field(default="civiclens-api", description="Service identifier")
  version: str = Field(..., description="API semantic version")
  timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
  database: Optional[str] = Field(default="ok", description="Database status ('ok', 'degraded', 'importing')")


class ModuleInfo(BaseModel):
  """Status descriptor for a CivicLens civic intelligence module."""

  id: str = Field(..., description="Module identifier key")
  title: str = Field(..., description="Human-readable module title")
  status: str = Field(
      default="planned",
      description="Implementation status (e.g. planned, active)",
  )
  description: str = Field(..., description="Short summary of module capability")


class InfoResponse(BaseModel):
  """Response model for system metadata, versioning, and module status."""

  app_name: str = Field(default="CivicLens API", description="Application name")
  version: str = Field(..., description="API semantic version")
  environment: str = Field(..., description="Runtime environment")
  supported_languages: List[str] = Field(
      default=["en", "ta"], description="Bilingual ISO language codes"
  )
  modules: List[ModuleInfo] = Field(
      ..., description="List of five core civic modules and statuses"
  )
  gemini_configured: bool = Field(
      ..., description="Whether Gemini API key is configured"
  )


class ErrorDetail(BaseModel):
  """Structured error content."""

  code: str = Field(..., description="Machine-readable error code")
  message: str = Field(..., description="Human-readable error explanation")
  details: Optional[Any] = Field(
      default=None, description="Optional extra error context or field errors"
  )


class ErrorResponse(BaseModel):
  """Uniform error response structure for CivicLens API."""

  error: ErrorDetail
