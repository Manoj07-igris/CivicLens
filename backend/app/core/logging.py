import logging
import sys
from .config import get_settings

def setup_logging() -> logging.Logger:
  """Configure structured, clean console logging for CivicLens."""
  settings = get_settings()

  log_level = logging.DEBUG if settings.APP_ENV.lower() == "development" else logging.INFO

  log_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
  date_format = "%Y-%m-%d %H:%M:%S"

  # Configure root logger
  logging.basicConfig(
      level=log_level,
      format=log_format,
      datefmt=date_format,
      handlers=[logging.StreamHandler(sys.stdout)],
      force=True,
  )

  # Reduce third-party noise
  logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

  logger = logging.getLogger("civiclens")
  logger.setLevel(log_level)
  return logger
