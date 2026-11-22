import time
import uuid
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .core.config import get_settings
from .core.logging import setup_logging
from .core.errors import register_error_handlers
from .api.router import api_router

# Initialize logging
logger = setup_logging()
settings = get_settings()

docs_url = None if (settings.APP_ENV == "production" and not settings.ENABLE_API_DOCS) else "/docs"
redoc_url = None if (settings.APP_ENV == "production" and not settings.ENABLE_API_DOCS) else "/redoc"

@asynccontextmanager
async def lifespan(app: FastAPI):
  """Application lifespan context manager for startup and shutdown events."""
  logger.info(
      "Starting CivicLens API v1.1.0-auth in '%s' environment",
      settings.APP_ENV,
  )
  logger.info(
      "Allowed CORS origins: %s",
      ", ".join(settings.cors_origins_list),
  )
  logger.info(
      "Gemini API configured: %s",
      "YES" if settings.is_gemini_configured else "NO (Offline mode active)",
  )
  if not settings.AUTH_SECRET_KEY:
    logger.warning(
        "AUTH_SECRET_KEY is not set in environment. Using development fallback secret key. Configure AUTH_SECRET_KEY in production!"
    )

  # Phase 15 Database Startup & Initialization
  try:
    from app.db.database import get_database
    from app.db.migrations.runner import MigrationRunner
    from app.db.legacy_import import LegacyImporter

    db = get_database()
    # 1. Run database migrations
    runner = MigrationRunner(db)
    applied = runner.run()
    if applied:
      logger.info("Applied %d database migration(s).", applied)

    # 2. Integrity check
    check_ok, check_msg = db.integrity_check()
    if not check_ok:
      logger.error("Database integrity check failed: %s", check_msg)
      db.set_degraded(f"Integrity check failed: {check_msg}")
    else:
      logger.info("Database integrity check passed (quick_check: OK).")

      # 3. Startup maintenance if enabled
      if settings.MAINTENANCE_ON_STARTUP:
        try:
          from app.api.system import MaintenanceRequest, run_maintenance
          run_maintenance(MaintenanceRequest(), settings=settings, db=db)
          logger.info("Startup maintenance completed.")
        except Exception as maint_exc:
          logger.warning("Startup maintenance encountered an issue: %s", maint_exc)

      # 4. Trigger non-blocking legacy import if enabled
      if settings.LEGACY_IMPORT_ENABLED:
        import threading
        importer = LegacyImporter(settings=settings, db=db)
        import_thread = threading.Thread(target=importer.run_import, daemon=True, name="LegacyImporterThread")
        import_thread.start()
        logger.info("Background legacy file import thread initiated.")

  except Exception as db_exc:
    logger.exception("Failed during database initialization: %s", db_exc)
    from app.db.database import get_database
    get_database().set_degraded(str(db_exc))

  yield
  logger.info("CivicLens API shutting down gracefully.")


app = FastAPI(
    title="CivicLens API",
    version="1.1.0-auth",
    description="Agentic AI civic intelligence API powering document analysis, change detection, fact verification, public services, and grievance workflows.",
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
)

# 1. Trusted Host Middleware (DNS Rebinding & Host Injection defense)
# Note: Allows configured hosts plus localhost/127.0.0.1/testserver by default
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts_list,
)

# 2. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# 3. Security Headers Middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
  response: Response = await call_next(request)
  response.headers["X-Content-Type-Options"] = "nosniff"
  response.headers["X-Frame-Options"] = "DENY"
  response.headers["Referrer-Policy"] = "no-referrer"
  response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
  if request.url.path.startswith("/api/"):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
  return response

# 2. Request-ID & Timing Logging Middleware
@app.middleware("http")
async def request_id_and_logging_middleware(request: Request, call_next):
  request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
  request.state.request_id = request_id

  start_time = time.perf_counter()
  response: Response = await call_next(request)
  duration_ms = (time.perf_counter() - start_time) * 1000

  response.headers["X-Request-ID"] = request_id

  logger.info(
      "[%s] %s %s - %d (%.2fms)",
      request_id,
      request.method,
      request.url.path,
      response.status_code,
      duration_ms,
  )
  return response

# 3. Register uniform error handlers
register_error_handlers(app)

# 4. Include API routers
app.include_router(api_router)

# 5. Controlled Local Demo Portal (Phase 14: Playwright Browser Automation)
@app.post("/demo-portal/submit", tags=["Demo Portal"], summary="Controlled Demo Portal Mock Submission")
async def demo_portal_submit(payload: dict = Body(...)):
  """Simulate demo portal submission: rejects PII, stores zero data, returns simulated demo ref."""
  import json
  from app.core.pii_guard import ensure_no_pii
  text_to_scan = json.dumps(payload, ensure_ascii=False)
  ensure_no_pii(text_to_scan)
  app_ref = payload.get("application_number") or f"DEMO-IC-{uuid.uuid4().hex[:6].upper()}"
  return {
      "status": "success",
      "simulation": True,
      "application_number": app_ref,
      "message": "Demo submission recorded in local simulation. No real data sent or saved.",
  }


demo_portal_static_dir = Path(__file__).resolve().parent.parent.parent / "demo_portal" / "public"
if demo_portal_static_dir.exists():
  app.mount("/demo-portal", StaticFiles(directory=str(demo_portal_static_dir), html=True), name="demo-portal")


frontend_dist_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if settings.SERVE_FRONTEND and frontend_dist_dir.exists():
  from fastapi.responses import FileResponse
  assets_dir = frontend_dist_dir / "assets"
  if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

  @app.get("/{full_path:path}", include_in_schema=False)
  async def serve_spa_frontend(full_path: str):
    file_path = frontend_dist_dir / full_path
    if file_path.is_file():
      return FileResponse(file_path)
    return FileResponse(frontend_dist_dir / "index.html")
else:
  @app.get("/", tags=["Root"], summary="API Root")
  async def root_endpoint():
    """Root welcome redirect to interactive documentation."""
    return {
        "message": "Welcome to CivicLens API",
        "version": "1.1.0-auth",
        "docs_url": "/docs" if docs_url else "disabled",
        "health_url": "/api/v1/health",
        "info_url": "/api/v1/info",
    }
