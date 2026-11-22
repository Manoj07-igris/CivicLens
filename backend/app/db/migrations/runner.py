"""Database Migration Runner for CivicLens.

Applies ordered SQL migration scripts, tracks execution state in `schema_migrations`,
validates SHA-256 script checksums to prevent file tampering, and halts on
schema version mismatches with explicit errors.
"""

import hashlib
import logging
from pathlib import Path
import re
from typing import List, Optional, Tuple

from app.core.errors import (
    DatabaseSchemaNewerError,
    MigrationChecksumMismatchError,
    MigrationError,
)
from app.db.database import Database, utc_now_iso

logger = logging.getLogger("civiclens.db.migrations")

MIGRATIONS_DIR = Path(__file__).resolve().parent


def compute_file_checksum(path: Path) -> str:
  """Compute SHA-256 hexadecimal hash of migration file content."""
  content = path.read_bytes()
  return hashlib.sha256(content).hexdigest()


class MigrationRunner:
  """Executes and tracks SQL schema migrations."""

  def __init__(self, db: Database, migrations_dir: Optional[Path] = None):
    self._db = db
    self._dir = migrations_dir or MIGRATIONS_DIR

  def _discover_migrations(self) -> List[Tuple[int, str, Path]]:
    """Scan directory for files named '0001_name.sql' sorted by version number."""
    found: List[Tuple[int, str, Path]] = []
    if not self._dir.exists():
      return found

    for file_path in self._dir.glob("*.sql"):
      match = re.match(r"^(\d{4})_(.+)\.sql$", file_path.name)
      if match:
        version = int(match.group(1))
        name = match.group(2)
        found.append((version, name, file_path))

    found.sort(key=lambda item: item[0])
    return found

  def run_migrations(self) -> int:
    """Apply all pending migrations in order.

    Returns the count of newly applied migrations.
    """
    conn = self._db.get_connection()

    # 1. Ensure tracking table exists
    conn.execute("""
      CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        checksum TEXT NOT NULL,
        applied_at TEXT NOT NULL
      );
    """)

    # 2. Read already applied migrations from database
    cursor = conn.execute("SELECT version, name, checksum, applied_at FROM schema_migrations ORDER BY version ASC;")
    applied_rows = cursor.fetchall()
    applied_dict = {row["version"]: row for row in applied_rows}

    # 3. Discover migration scripts in code
    code_migrations = self._discover_migrations()
    max_code_version = max((m[0] for m in code_migrations), default=0)
    max_applied_version = max(applied_dict.keys(), default=0)

    # Safety Check: Refuse startup if database schema is newer than application code
    if max_applied_version > max_code_version:
      raise DatabaseSchemaNewerError(
          f"Database schema version ({max_applied_version}) is newer than application code ({max_code_version}). "
          "Please upgrade CivicLens before starting."
      )

    # 4. Verify checksums of already applied migrations
    for version, name, file_path in code_migrations:
      checksum = compute_file_checksum(file_path)
      if version in applied_dict:
        stored_checksum = applied_dict[version]["checksum"]
        if stored_checksum != checksum:
          raise MigrationChecksumMismatchError(
              f"Migration {version:04d}_{name}.sql checksum mismatch! "
              f"Stored: {stored_checksum}, Current: {checksum}. Existing migration scripts must never be modified."
          )

    # 5. Apply unapplied migrations in order
    newly_applied = 0
    for version, name, file_path in code_migrations:
      if version not in applied_dict:
        logger.info("Applying migration %04d_%s.sql...", version, name)
        sql_content = file_path.read_text(encoding="utf-8")
        checksum = compute_file_checksum(file_path)

        # executescript commits preceding statements and executes the entire SQL batch
        conn.executescript(sql_content)
        conn.execute(
            "INSERT INTO schema_migrations (version, name, checksum, applied_at) VALUES (?, ?, ?, ?);",
            (version, name, checksum, utc_now_iso()),
        )

        logger.info("Successfully applied migration %04d_%s.sql", version, name)
        newly_applied += 1

    return newly_applied

  run = run_migrations

  def get_current_schema_version(self) -> int:
    """Return the highest applied migration version or 0."""
    try:
      row = self._db.fetchone("SELECT MAX(version) AS max_v FROM schema_migrations;")
      return row["max_v"] if row and row["max_v"] is not None else 0
    except Exception:
      return 0
