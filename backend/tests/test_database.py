"""Tests for Database Core and Migration Runner (Phase 15)."""

import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import pytest

from app.core.config import Settings
from app.db.database import Database, DatabaseDegradedError
from app.db.migrations.runner import MigrationRunner


@pytest.fixture
def temp_db(tmp_path: Path):
  """Provision an isolated temporary database for testing."""
  db_path = tmp_path / "test_civiclens.db"
  settings = Settings(
      DATABASE_PATH=str(db_path),
      DATABASE_BUSY_TIMEOUT_MS=5000,
  )
  db = Database(settings)
  runner = MigrationRunner(db)
  runner.run_migrations()
  yield db
  db.close()


def test_database_wal_and_foreign_keys(temp_db: Database):
  """Verify WAL mode and foreign key enforcement are active."""
  conn = temp_db.get_connection()
  
  # Check foreign keys
  fk_cursor = conn.execute("PRAGMA foreign_keys;")
  assert fk_cursor.fetchone()[0] == 1, "Foreign keys must be enabled"

  # Check journal mode (in memory or WAL depending on filesystem)
  jm_cursor = conn.execute("PRAGMA journal_mode;")
  mode = jm_cursor.fetchone()[0].lower()
  assert mode in ("wal", "memory"), f"Expected WAL or memory journal mode, got {mode}"


def test_thread_local_connections(temp_db: Database):
  """Verify each thread receives its own SQLite connection instance."""
  conns = []

  def get_conn():
    c = temp_db.get_connection()
    conns.append(id(c))

  t1 = threading.Thread(target=get_conn)
  t2 = threading.Thread(target=get_conn)
  t1.start()
  t2.start()
  t1.join()
  t2.join()

  assert len(conns) == 2
  assert conns[0] != conns[1], "Different threads must have distinct connection instances"


def test_transaction_commit_and_rollback(temp_db: Database):
  """Verify transactions commit on clean exit and roll back on exceptions."""
  # 1. Commit test
  with temp_db.transaction():
    temp_db.execute(
        "INSERT INTO preferences (key, value, updated_at) VALUES (?, ?, ?);",
        ("test.theme", "dark", "2026-11-21T00:00:00Z"),
    )

  row = temp_db.fetchone("SELECT value FROM preferences WHERE key = ?;", ("test.theme",))
  assert row is not None
  assert row["value"] == "dark"

  # 2. Rollback test
  with pytest.raises(ValueError):
    with temp_db.transaction():
      temp_db.execute(
          "UPDATE preferences SET value = ?, updated_at = ? WHERE key = ?;",
          ("light", "2026-11-21T00:01:00Z", "test.theme"),
      )
      raise ValueError("Simulated failure inside transaction")

  # Value should remain "dark" due to rollback
  row_after = temp_db.fetchone("SELECT value FROM preferences WHERE key = ?;", ("test.theme",))
  assert row_after["value"] == "dark"


def test_quick_check_integrity(temp_db: Database):
  """Verify quick_check passes on valid database."""
  is_ok, msg = temp_db.integrity_check()
  assert is_ok is True
  assert msg == "ok"


def test_online_hot_backup(temp_db: Database, tmp_path: Path):
  """Verify online hot backup generates a readable, valid clone."""
  backup_dest = tmp_path / "backups" / "backup_test.db"
  backup_dest.parent.mkdir(parents=True, exist_ok=True)

  # Insert data
  with temp_db.transaction():
    temp_db.execute(
        "INSERT INTO preferences (key, value, updated_at) VALUES (?, ?, ?);",
        ("system.lang", "ta", "2026-11-21T00:00:00Z"),
    )

  # Run backup
  res_path = temp_db.backup_to(backup_dest)
  assert res_path.exists()
  assert res_path.stat().st_size > 0

  # Open backup and verify data
  b_conn = sqlite3.connect(str(backup_dest))
  b_cursor = b_conn.execute("SELECT value FROM preferences WHERE key = 'system.lang';")
  b_row = b_cursor.fetchone()
  assert b_row is not None
  assert b_row[0] == "ta"
  b_conn.close()


def test_migration_runner_idempotent(temp_db: Database):
  """Verify running migrations multiple times is idempotent."""
  runner = MigrationRunner(temp_db)
  applied_count = runner.run_migrations()
  assert applied_count == 0, "Second migration run should apply 0 migrations"

  # Verify schema_migrations table
  rows = temp_db.fetchall("SELECT version, name, checksum FROM schema_migrations;")
  assert len(rows) >= 1
  assert rows[0]["name"] == "init"
  assert len(rows[0]["checksum"]) == 64  # SHA-256


def test_degraded_mode_status(tmp_path: Path):
  """Verify degraded mode behavior when database cannot be opened."""
  settings = Settings(
      DATABASE_PATH=str(tmp_path / "unusable" / "sub" / "db.sqlite"),
  )
  db = Database(settings)
  db.set_degraded("Disk failure simulation")
  assert db.is_degraded is True
  assert db.status == "degraded"

  with pytest.raises(DatabaseDegradedError):
    with db.transaction():
      db.execute("INSERT INTO preferences (key, value) VALUES ('k', 'v');")
