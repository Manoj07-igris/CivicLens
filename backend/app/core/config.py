import os
from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine base directory of backend
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BACKEND_DIR / ".env"

# Sensible default model: Gemini 2.5 Flash is fast, cost-efficient,
# supports multimodal documents, structured JSON outputs, and native tool calling.
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

class Settings(BaseSettings):
  """Application configuration and environment settings."""

  APP_ENV: str = "development"
  CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,https://civic-lens-liard.vercel.app"
  GEMINI_API_KEY: str = ""
  GEMINI_MODEL: str = DEFAULT_GEMINI_MODEL
  GEMINI_TIMEOUT_SECONDS: int = 30
  GEMINI_MAX_RETRIES: int = 2
  GEMINI_TEMPERATURE: float = 0.2
  GEMINI_MAX_OUTPUT_TOKENS: int = 2048
  MAX_UPLOAD_MB: int = 20
  MAX_PDF_PAGES: int = 200
  OCR_ENABLED: bool = True
  OCR_MAX_PAGES: int = 30
  OCR_DPI: int = 200
  OCR_LANGUAGES: str = "tam+eng"
  TESSERACT_CMD: str = ""
  CHUNK_SIZE_CHARS: int = 1000
  CHUNK_OVERLAP_CHARS: int = 150
  EMBEDDING_MODEL_NAME: str = "intfloat/multilingual-e5-small"
  EMBEDDING_BATCH_SIZE: int = 16
  EMBEDDING_CACHE_DIR: str = ""
  RETRIEVAL_TOP_K: int = 6
  RETRIEVAL_MIN_SCORE: float = 0.65
  RAG_MAX_CONTEXT_CHARS: int = 6000
  RAG_RATE_LIMIT_PER_MINUTE: int = 10

  # Central AI Agent and Function Calling Settings (Phase 9)
  AGENT_MAX_STEPS: int = 4
  AGENT_MAX_TOOL_CALLS_PER_RUN: int = 6
  AGENT_TOOL_TIMEOUT_SECONDS: int = 15
  AGENT_RATE_LIMIT_PER_MINUTE: int = 10

  # Policy Change Detection Settings (Phase 10)
  COMPARE_MAX_PAGES_PER_DOC: int = 100
  COMPARE_MAX_CANDIDATES: int = 60
  COMPARE_BATCH_SIZE: int = 12
  COMPARE_MAX_GEMINI_CALLS: int = 4
  COMPARE_SIMILARITY_MATCH_THRESHOLD: float = 0.55
  COMPARE_RATE_LIMIT_PER_MINUTE: int = 3

  # Fact Verification & Official Source Library Settings (Phase 11)
  VERIFY_MAX_GEMINI_CALLS: int = 2
  VERIFY_MAX_CLAIMS: int = 5
  VERIFY_CLAIM_MAX_CHARS: int = 1000
  VERIFY_TOP_K_PER_SOURCE: int = 3
  VERIFY_TOP_K_TOTAL: int = 8
  VERIFY_MAX_SOURCES_SEARCHED: int = 30
  VERIFY_RATE_LIMIT_PER_MINUTE: int = 5
  SOURCE_STALE_AFTER_DAYS: int = 365
  ALLOW_SOURCE_MANAGEMENT: bool = True  # In production deployments, only administrators may manage the library

  # Phase 12 - Public Service Assistant & Portal Registry
  SERVICE_MAX_GEMINI_CALLS: int = 1  # 1 call for grounded guide, max 2 with explicit general guidance
  SERVICE_QUERY_MAX_CHARS: int = 600
  SERVICE_TOP_K_TOTAL: int = 10
  SERVICE_RATE_LIMIT_PER_MINUTE: int = 5
  SERVICE_MAX_CHECKLIST_ITEMS: int = 30
  FORM_FIELDS_MAX: int = 40
  ALLOW_PORTAL_MANAGEMENT: bool = True  # In production deployments, only administrators may manage portals

  # Phase 13 - Civic Grievance Assistant (Module 5)
  GRIEVANCE_MIN_DESCRIPTION_CHARS: int = 10
  GRIEVANCE_MAX_DESCRIPTION_CHARS: int = 2000
  GRIEVANCE_LOCATION_MAX_CHARS: int = 300
  GRIEVANCE_MAX_IMAGE_MB: int = 5
  GRIEVANCE_IMAGE_MAX_DIMENSION: int = 1600  # Longest edge px
  GRIEVANCE_IMAGE_ALLOWED_TYPES: List[str] = ["image/jpeg", "image/png", "image/webp"]
  GRIEVANCE_MAX_PIXELS: int = 25_000_000  # Decompression-bomb defense limit
  GRIEVANCE_MAX_GEMINI_CALLS: int = 1  # 1 call per analysis, hard cap 2
  GRIEVANCE_RATE_LIMIT_PER_MINUTE: int = 6
  GRIEVANCE_RECORDS_MAX: int = 200  # Oldest drafts pruned when limit reached
  EMERGENCY_CONTACT_TEXT: str = "112 (India)"  # Emergency contact info (app owner may edit)
  DEMO_ID_PREFIX: str = "DEMO"

  # Phase 14 - Playwright Browser Automation (Controlled Demo Workflow)
  BROWSER_ENABLED: bool = True
  BROWSER_HEADLESS: bool = True
  BROWSER_SLOW_MO_MS: int = 0
  BROWSER_SESSION_TTL_SECONDS: int = 600  # 10 minutes session TTL
  BROWSER_IDLE_CLOSE_SECONDS: int = 120   # 2 minutes idle close of Chromium instance
  BROWSER_MAX_ACTIONS_PER_SESSION: int = 60
  BROWSER_ACTION_TIMEOUT_MS: int = 8000
  BROWSER_NAVIGATION_TIMEOUT_MS: int = 10000
  BROWSER_VIEWPORT_WIDTH: int = 1024
  BROWSER_VIEWPORT_HEIGHT: int = 720
  BROWSER_SCREENSHOT_MAX_WIDTH: int = 900
  BROWSER_SCREENSHOT_QUALITY: int = 70
  BROWSER_MAX_SCREENSHOTS_PER_SESSION: int = 40
  BROWSER_MAX_CONCURRENT_SESSIONS: int = 1
  BROWSER_RECORDS_MAX: int = 50
  BROWSER_RATE_LIMIT_PER_MINUTE: int = 20
  PUBLIC_BASE_URL: str = "http://127.0.0.1:8000"

  # Phase 15 - Database, History and Application Integration
  DATABASE_PATH: str = "backend/data/civiclens.db"
  DATABASE_BUSY_TIMEOUT_MS: int = 5000
  DATABASE_BACKUP_DIR: str = "backend/data/backups"
  DATABASE_BACKUPS_KEEP: int = 5
  ACTIVITY_RETENTION_DAYS: int = 90
  LEGACY_IMPORT_ENABLED: bool = True
  MAINTENANCE_ON_STARTUP: bool = True
  DELETE_ALL_CONFIRM_PHRASE: str = "DELETE MY DATA"
  ACTIVITY_PAGE_SIZE_MAX: int = 50

  # Phase 16 - Security Hardening, Quota Cap, and Serving Settings
  GEMINI_GLOBAL_RPM_CAP: int = 30
  ALLOWED_HOSTS: str = "127.0.0.1,localhost,testserver,*.onrender.com,*.vercel.app"
  ENABLE_API_DOCS: bool = False
  SERVE_FRONTEND: bool = False

  # Authentication & Multi-User Account System Settings (v1.1.0-auth)
  AUTH_SECRET_KEY: str = ""
  FRONTEND_BASE_URL: str = "http://localhost:5173"
  ADMIN_EMAILS: str = ""
  AUTH_ALLOW_REGISTRATION: bool = True
  AUTH_COOKIE_NAME: str = "civiclens_session"
  AUTH_COOKIE_SECURE: bool = False
  AUTH_SESSION_IDLE_MINUTES: int = 120
  AUTH_SESSION_ABSOLUTE_HOURS: int = 12
  AUTH_REMEMBER_ME_IDLE_DAYS: int = 7
  AUTH_REMEMBER_ME_ABSOLUTE_DAYS: int = 30
  AUTH_MAX_SESSIONS_PER_USER: int = 5
  AUTH_PASSWORD_MIN_LENGTH: int = 12
  AUTH_ARGON2_TIME_COST: int = 3
  AUTH_ARGON2_MEMORY_COST_KIB: int = 65536
  AUTH_ARGON2_PARALLELISM: int = 1
  AUTH_HASH_CONCURRENCY: int = 2
  AUTH_RESET_TOKEN_TTL_MINUTES: int = 30
  AUTH_EVENT_RETENTION_DAYS: int = 90
  AUTH_DEV_PRINT_RESET_LINKS: bool = False
  TRUST_PROXY_HEADERS: bool = False
  TERMS_VERSION: str = "2026.1"

  # SMTP Email Delivery (Optional)
  SMTP_HOST: str = ""
  SMTP_PORT: int = 587
  SMTP_USERNAME: str = ""
  SMTP_PASSWORD: str = ""
  SMTP_FROM: str = "CivicLens <no-reply@civiclens.local>"
  SMTP_SECURITY: str = "starttls"  # starttls | ssl | none

  model_config = SettingsConfigDict(
      env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
      env_file_encoding="utf-8",
      extra="ignore",
  )

  @property
  def upload_dir(self) -> Path:
    """Return root directory for document uploads, ensuring directory exists."""
    path = BACKEND_DIR / "data" / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path

  @property
  def indexes_dir(self) -> Path:
    """Return root directory for FAISS document vector indexes."""
    path = BACKEND_DIR / "data" / "indexes"
    path.mkdir(parents=True, exist_ok=True)
    return path

  @property
  def comparisons_dir(self) -> Path:
    """Return root directory for policy comparison reports and job artifacts."""
    path = BACKEND_DIR / "data" / "comparisons"
    path.mkdir(parents=True, exist_ok=True)
    return path

  @property
  def official_sources_dir(self) -> Path:
    """Return root directory for curated official source documents."""
    path = BACKEND_DIR / "data" / "official_sources"
    path.mkdir(parents=True, exist_ok=True)
    return path

  @property
  def verifications_dir(self) -> Path:
    """Return root directory for fact verification reports and jobs."""
    path = BACKEND_DIR / "data" / "verifications"
    path.mkdir(parents=True, exist_ok=True)
    return path

  @property
  def portals_dir(self) -> Path:
    """Return root directory for curated government portal registry."""
    path = BACKEND_DIR / "data" / "portals"
    path.mkdir(parents=True, exist_ok=True)
    return path

  @property
  def service_guides_dir(self) -> Path:
    """Return root directory for public service guidance and checklist artifacts."""
    path = BACKEND_DIR / "data" / "service_guides"
    path.mkdir(parents=True, exist_ok=True)
    return path

  @property
  def grievances_dir(self) -> Path:
    """Return root directory for civic grievance records, images, and tracking."""
    path = BACKEND_DIR / "data" / "grievances"
    path.mkdir(parents=True, exist_ok=True)
    return path

  @property
  def browser_sessions_dir(self) -> Path:
    """Return root directory for browser demo session snapshots and metadata."""
    path = BACKEND_DIR / "data" / "browser_sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path

  @property
  def database_file(self) -> Path:
    """Return path to primary SQLite database file, ensuring parent directory exists."""
    raw = Path(self.DATABASE_PATH.strip())
    if raw.is_absolute():
      path = raw
    elif str(raw).startswith("backend") or str(raw).startswith("backend/"):
      path = BACKEND_DIR.parent / raw
    else:
      path = BACKEND_DIR / raw
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

  @property
  def database_backup_dir_path(self) -> Path:
    """Return directory for SQLite database backup snapshots."""
    raw = Path(self.DATABASE_BACKUP_DIR.strip())
    if raw.is_absolute():
      path = raw
    elif str(raw).startswith("backend") or str(raw).startswith("backend/"):
      path = BACKEND_DIR.parent / raw
    else:
      path = BACKEND_DIR / raw
    path.mkdir(parents=True, exist_ok=True)
    return path

  @property
  def embedding_cache_path(self) -> Path:
    """Return local directory for cached embedding model files."""
    if self.EMBEDDING_CACHE_DIR and self.EMBEDDING_CACHE_DIR.strip():
      path = Path(self.EMBEDDING_CACHE_DIR.strip())
    else:
      path = BACKEND_DIR / "data" / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path

  @property
  def effective_gemini_model(self) -> str:
    """Return configured model or fall back to default."""
    if self.GEMINI_MODEL and self.GEMINI_MODEL.strip():
      return self.GEMINI_MODEL.strip()
    return DEFAULT_GEMINI_MODEL

  @property
  def cors_origins_list(self) -> List[str]:
    """Parse comma-separated CORS_ORIGINS string into a clean list of origins."""
    if not self.CORS_ORIGINS:
      return ["http://localhost:5173", "http://127.0.0.1:5173"]
    origins = []
    for origin in self.CORS_ORIGINS.split(","):
      cleaned = origin.strip().rstrip("/")
      if cleaned:
        origins.append(cleaned)
    return origins

  @property
  def allowed_hosts_list(self) -> List[str]:
    """Parse comma-separated ALLOWED_HOSTS string into a list of allowed hosts."""
    if not self.ALLOWED_HOSTS:
      return ["127.0.0.1", "localhost", "testserver"]
    return [
        host.strip()
        for host in self.ALLOWED_HOSTS.split(",")
        if host.strip()
    ]

  @property
  def is_gemini_configured(self) -> bool:
    """Return True if a non-placeholder Gemini API key is configured.

    Never exposes the raw key.
    """
    key = self.GEMINI_API_KEY.strip()
    return bool(key and key != "your_key_here")

  # Phase 13 ergonomic accessors
  @property
  def grievance_min_description_chars(self) -> int:
    return self.GRIEVANCE_MIN_DESCRIPTION_CHARS

  @property
  def grievance_max_description_chars(self) -> int:
    return self.GRIEVANCE_MAX_DESCRIPTION_CHARS

  @property
  def grievance_location_max_chars(self) -> int:
    return self.GRIEVANCE_LOCATION_MAX_CHARS

  @property
  def grievance_max_image_mb(self) -> int:
    return self.GRIEVANCE_MAX_IMAGE_MB

  @property
  def grievance_image_max_dimension(self) -> int:
    return self.GRIEVANCE_IMAGE_MAX_DIMENSION

  @property
  def grievance_image_allowed_types(self) -> List[str]:
    return self.GRIEVANCE_IMAGE_ALLOWED_TYPES

  @property
  def grievance_max_pixels(self) -> int:
    return self.GRIEVANCE_MAX_PIXELS

  @property
  def grievance_max_gemini_calls(self) -> int:
    return self.GRIEVANCE_MAX_GEMINI_CALLS

  @property
  def grievance_rate_limit_per_minute(self) -> int:
    return self.GRIEVANCE_RATE_LIMIT_PER_MINUTE

  @property
  def grievance_records_max(self) -> int:
    return self.GRIEVANCE_RECORDS_MAX

  @property
  def emergency_contact_text(self) -> str:
    return self.EMERGENCY_CONTACT_TEXT

  @property
  def demo_id_prefix(self) -> str:
    return self.DEMO_ID_PREFIX

  # Auth Helper Properties
  @property
  def AUTH_ARGON2_MAX_CONCURRENT(self) -> int:
    return self.AUTH_HASH_CONCURRENCY

  @property
  def AUTH_COOKIE_SAMESITE(self) -> str:
    return "lax"

  @property
  def AUTH_SESSION_MAX_AGE_SECONDS(self) -> int:
    return self.AUTH_SESSION_ABSOLUTE_HOURS * 3600

  @property
  def AUTH_SESSION_REMEMBER_DAYS(self) -> int:
    return self.AUTH_REMEMBER_ME_ABSOLUTE_DAYS

  @property
  def AUTH_RESET_TOKEN_LIFETIME_SECONDS(self) -> int:
    return self.AUTH_RESET_TOKEN_TTL_MINUTES * 60

  @property
  def SMTP_USER(self) -> str:
    return self.SMTP_USERNAME

  @property
  def SMTP_FROM_EMAIL(self) -> str:
    return self.SMTP_FROM

  @property
  def SMTP_USE_TLS(self) -> bool:
    return self.SMTP_SECURITY == "starttls"

  @property
  def admin_emails_list(self) -> List[str]:
    if not self.ADMIN_EMAILS:
      return []
    return [e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()]

  @property
  def is_email_delivery_configured(self) -> bool:
    return bool(self.SMTP_HOST and self.SMTP_HOST.strip())

  @property
  def effective_auth_secret_key(self) -> str:
    if self.AUTH_SECRET_KEY and self.AUTH_SECRET_KEY.strip():
      return self.AUTH_SECRET_KEY
    return "civiclens-dev-insecure-secret-key-change-in-production-2026"


@lru_cache
def get_settings() -> Settings:
  """Provide a cached instance of the application settings."""
  return Settings()
