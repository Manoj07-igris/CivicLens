"""Core SQLite Database Manager for CivicLens.

Provides thread-local SQLite connections with WAL mode, foreign keys,
busy timeout handling, transactional execution (BEGIN IMMEDIATE),
PRAGMA quick_check integrity verification, and online backup support.
"""

from contextlib import contextmanager
import datetime
import json
import logging
from pathlib import Path
import sqlite3
import threading
from typing import Any, Callable, Dict, Generator, Iterable, List, Optional, Tuple, Union

from app.core.config import Settings, get_settings
from app.core.errors import DatabaseDegradedError, DatabaseError

logger = logging.getLogger("civiclens.db")


def utc_now_iso() -> str:
  """Return current UTC timestamp in standard ISO-8601 format."""
  return datetime.datetime.now(datetime.timezone.utc).isoformat()


def to_json(val: Any) -> str:
  """Serialize Python data to clean JSON string with UTF-8 encoding."""
  if val is None:
    return "null"
  return json.dumps(val, ensure_ascii=False)


def from_json(val: Optional[str], default: Any = None) -> Any:
  """Safely deserialize JSON string, returning default on None or corrupt data."""
  if val is None:
    return default
  try:
    return json.loads(val)
  except Exception as exc:
    logger.warning("Failed to deserialize JSON column: %s", exc)
    return default


class Database:
  """Thread-safe SQLite database manager for unified persistent storage."""

  _instance: Optional["Database"] = None

  def __init__(self, settings: Optional[Settings] = None, db_path: Optional[Path] = None):
    self._settings = settings or get_settings()
    self._db_path = db_path or self._settings.database_file
    self._busy_timeout_ms = self._settings.DATABASE_BUSY_TIMEOUT_MS
    self._local = threading.local()
    self._all_conns: List[sqlite3.Connection] = []
    self._conns_lock = threading.Lock()
    self._is_degraded = False
    self._degraded_reason: Optional[str] = None

  @property
  def db_path(self) -> Path:
    return self._db_path

  @property
  def is_degraded(self) -> bool:
    return self._is_degraded

  @property
  def status(self) -> str:
    """Return database state: 'ok' or 'degraded'."""
    return "degraded" if self._is_degraded else "ok"

  @property
  def degraded_reason(self) -> Optional[str]:
    return self._degraded_reason

  def set_degraded(self, reason: str) -> None:
    """Enter degraded mode (e.g. following corruption or critical schema failure)."""
    self._is_degraded = True
    self._degraded_reason = reason
    logger.error("CivicLens database placed in DEGRADED mode: %s", reason)

  def clear_degraded(self) -> None:
    """Clear degraded mode after recovery."""
    self._is_degraded = False
    self._degraded_reason = None
    logger.info("CivicLens database degraded mode cleared.")

  def get_connection(self) -> sqlite3.Connection:
    """Retrieve or create thread-local SQLite connection with safety PRAGMAs."""
    conn = getattr(self._local, "conn", None)
    if conn is None:
      # Ensure parent directory exists
      self._db_path.parent.mkdir(parents=True, exist_ok=True)
      conn = sqlite3.connect(
          str(self._db_path),
          timeout=self._busy_timeout_ms / 1000.0,
          check_same_thread=False,
          isolation_level=None,  # Explicit transaction control
      )
      conn.row_factory = sqlite3.Row
      # Apply high-concurrency performance and integrity PRAGMAs
      conn.execute("PRAGMA journal_mode=WAL;")
      conn.execute("PRAGMA foreign_keys=ON;")
      conn.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms};")
      conn.execute("PRAGMA synchronous=NORMAL;")
      self._local.conn = conn
      with self._conns_lock:
        self._all_conns.append(conn)
    return conn

  @contextmanager
  def transaction(self) -> Generator[sqlite3.Connection, None, None]:
    """Execute write operations within an explicit BEGIN IMMEDIATE transaction.

    Rolls back automatically on exception, commits on clean block completion.
    """
    if self._is_degraded:
      raise DatabaseDegradedError(self._degraded_reason or "Database is degraded.")

    conn = self.get_connection()
    conn.execute("BEGIN IMMEDIATE;")
    try:
      yield conn
      conn.execute("COMMIT;")
    except Exception:
      try:
        conn.execute("ROLLBACK;")
      except Exception:
        pass
      raise

  def close(self) -> None:
    """Alias for close_all."""
    self.close_all()

  def execute(
      self, sql: str, params: Union[tuple, dict, List[Any]] = ()
  ) -> sqlite3.Cursor:
    """Execute a parameterized SQL statement."""
    if self._is_degraded:
      # Allow read-only PRAGMAs or queries when checking status, but block general statements
      if not (sql.strip().upper().startswith("PRAGMA") or sql.strip().upper().startswith("SELECT")):
        raise DatabaseDegradedError(self._degraded_reason or "Database is degraded.")

    conn = self.get_connection()
    return conn.execute(sql, params)

  def executemany(
      self, sql: str, seq_of_params: Iterable[Union[tuple, dict, List[Any]]]
  ) -> sqlite3.Cursor:
    """Execute a parameterized SQL statement against multiple parameter tuples."""
    if self._is_degraded:
      raise DatabaseDegradedError(self._degraded_reason or "Database is degraded.")
    conn = self.get_connection()
    return conn.executemany(sql, seq_of_params)

  def fetchone(
      self, sql: str, params: Union[tuple, dict, List[Any]] = ()
  ) -> Optional[sqlite3.Row]:
    """Execute query and fetch a single matching row."""
    cursor = self.execute(sql, params)
    return cursor.fetchone()

  def fetchall(
      self, sql: str, params: Union[tuple, dict, List[Any]] = ()
  ) -> List[sqlite3.Row]:
    """Execute query and fetch all matching rows."""
    cursor = self.execute(sql, params)
    return cursor.fetchall()

  def integrity_check(self) -> Tuple[bool, str]:
    """Execute PRAGMA quick_check to verify SQLite database file integrity."""
    try:
      conn = self.get_connection()
      cursor = conn.execute("PRAGMA quick_check;")
      rows = cursor.fetchall()
      messages = [r[0] for r in rows if r]
      if messages == ["ok"]:
        return True, "ok"
      err_str = "; ".join(messages)
      self.set_degraded(f"Integrity check failed: {err_str}")
      return False, err_str
    except Exception as exc:
      err_str = f"Integrity check exception: {exc}"
      self.set_degraded(err_str)
      return False, err_str

  def backup_to(self, dest_path: Path) -> Path:
    """Perform hot online backup of SQLite database using Connection.backup API."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    source_conn = self.get_connection()
    # Create target database connection
    dest_conn = sqlite3.connect(str(dest_path))
    try:
      with dest_conn:
        source_conn.backup(dest_conn, pages=100, sleep=0.01)
      logger.info("Database online backup completed to %s", dest_path.name)
      return dest_path
    finally:
      dest_conn.close()

  def close_current_thread(self) -> None:
    """Close connection for calling thread."""
    conn = getattr(self._local, "conn", None)
    if conn is not None:
      try:
        conn.close()
      except Exception:
        pass
      self._local.conn = None
      with self._conns_lock:
        if conn in self._all_conns:
          self._all_conns.remove(conn)

  def close_all(self) -> None:
    """Close all open SQLite connections across threads on server shutdown."""
    with self._conns_lock:
      for conn in self._all_conns:
        try:
          conn.close()
        except Exception:
          pass
      self._all_conns.clear()
    self._local.conn = None
    logger.info("Closed all database connections.")


_database_instance: Optional[Database] = None


def get_database() -> Database:
  """Retrieve singleton Database manager instance."""
  global _database_instance
  if _database_instance is None:
    _database_instance = Database()
    try:
      from app.db.migrations.runner import MigrationRunner
      MigrationRunner(_database_instance).run()
    except Exception as exc:
      logger.warning("Auto-migration during get_database initialization: %s", exc)
  return _database_instance


def set_database(db: Optional[Database]) -> None:
  """Inject or reset Database instance (used in tests)."""
  global _database_instance
  _database_instance = db
