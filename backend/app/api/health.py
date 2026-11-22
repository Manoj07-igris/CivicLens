from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from ..core.config import get_settings
from ..db.database import Database, get_database
from ..models.common import HealthResponse, InfoResponse, ModuleInfo

router = APIRouter(tags=["System & Health"])

API_VERSION = "0.1.0"

CORE_MODULES = [
    ModuleInfo(
        id="policy_intelligence",
        title="Policy Intelligence",
        status="active",
        description="PDF parsing, document chunking, and verifiable question-answering with citations.",
    ),
    ModuleInfo(
        id="policy_change_detection",
        title="Policy Change Detection",
        status="active",
        description="Side-by-side policy version comparison and modification extraction.",
    ),
    ModuleInfo(
        id="fact_verification",
        title="Fact Verification",
        status="active",
        description="Verification of civic claims with 4 verdicts (Supported, Contradicted, Unverified, Outdated).",
    ),
    ModuleInfo(
        id="public_service_assistant",
        title="Public Service Assistant",
        status="active",
        description="Step-by-step procedures, tailored document checklists, and controlled browser walkthroughs.",
    ),
    ModuleInfo(
        id="civic_grievance_assistant",
        title="Civic Grievance Assistant",
        status="active",
        description="Jurisdiction mapping, formal petition drafting, and simulated tracking workflows.",
    ),
]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint",
    description="Returns current service status and UTC timestamp.",
)
async def health_check(db: Database = Depends(get_database)) -> HealthResponse:
  """Liveness check for monitoring service availability."""
  overall_status = "ok" if db.status in ("ok", "importing") else "degraded"
  return HealthResponse(
      status=overall_status,
      service="civiclens-api",
      version=API_VERSION,
      timestamp=datetime.now(timezone.utc).isoformat(),
      database=db.status,
  )


@router.get(
    "/info",
    response_model=InfoResponse,
    summary="System information & metadata",
    description="Returns application environment, supported languages, modules, and Gemini configuration status.",
)
async def system_info() -> InfoResponse:
  """System metadata and status of the five civic intelligence modules."""
  settings = get_settings()
  return InfoResponse(
      app_name="CivicLens API",
      version=API_VERSION,
      environment=settings.APP_ENV,
      supported_languages=["en", "ta"],
      modules=CORE_MODULES,
      gemini_configured=settings.is_gemini_configured,
  )
