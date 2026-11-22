"""Pytest configuration and authentication fixtures for CivicLens test suites."""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))

from app.auth.dependencies import CurrentUser, get_current_user, get_optional_current_user, require_admin
from app.main import app

_default_test_user = CurrentUser(
    id="test-user-1",
    email="test@civiclens.test",
    full_name="Test Citizen",
    role="admin",
    is_active=True,
    session_id="test-session-1",
    session_token_hash="test-hash-1",
    raw_token="test-raw-token",
    preferred_language="en",
)

_standard_citizen_user = CurrentUser(
    id="standard-user-1",
    email="citizen@civiclens.test",
    full_name="Standard Citizen",
    role="user",
    is_active=True,
    session_id="user-session-1",
    session_token_hash="user-hash-1",
    raw_token="user-raw-token",
    preferred_language="en",
)

_second_citizen_user = CurrentUser(
    id="standard-user-2",
    email="citizen2@civiclens.test",
    full_name="Second Citizen",
    role="user",
    is_active=True,
    session_id="user-session-2",
    session_token_hash="user-hash-2",
    raw_token="user-raw-token-2",
    preferred_language="en",
)


@pytest.fixture(autouse=True)
def apply_default_auth_override(request):
  """Auto-apply authentication override for legacy tests, but disable for auth test suite."""
  normalized_path = str(request.fspath).replace("\\", "/")
  if "tests/auth" in normalized_path:
    # Dedicated auth tests must run against real un-mocked dependencies
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_current_user, None)
    app.dependency_overrides.pop(require_admin, None)
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_current_user, None)
    app.dependency_overrides.pop(require_admin, None)
  else:
    # Legacy tests use the default test user
    app.dependency_overrides[get_current_user] = lambda: _default_test_user
    app.dependency_overrides[get_optional_current_user] = lambda: _default_test_user
    app.dependency_overrides[require_admin] = lambda: _default_test_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_current_user, None)
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def auth_client():
  """TestClient authenticated as a standard non-admin citizen."""
  app.dependency_overrides[get_current_user] = lambda: _standard_citizen_user
  app.dependency_overrides[get_optional_current_user] = lambda: _standard_citizen_user
  app.dependency_overrides.pop(require_admin, None)
  client = TestClient(app)
  yield client
  app.dependency_overrides.pop(get_current_user, None)
  app.dependency_overrides.pop(get_optional_current_user, None)


@pytest.fixture
def second_user_client():
  """TestClient authenticated as a second citizen for IDOR testing."""
  app.dependency_overrides[get_current_user] = lambda: _second_citizen_user
  app.dependency_overrides[get_optional_current_user] = lambda: _second_citizen_user
  app.dependency_overrides.pop(require_admin, None)
  client = TestClient(app)
  yield client
  app.dependency_overrides.pop(get_current_user, None)
  app.dependency_overrides.pop(get_optional_current_user, None)


@pytest.fixture
def admin_client():
  """TestClient authenticated as an administrator."""
  app.dependency_overrides[get_current_user] = lambda: _default_test_user
  app.dependency_overrides[get_optional_current_user] = lambda: _default_test_user
  app.dependency_overrides[require_admin] = lambda: _default_test_user
  client = TestClient(app)
  yield client
  app.dependency_overrides.pop(get_current_user, None)
  app.dependency_overrides.pop(get_optional_current_user, None)
  app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def unauthenticated_client():
  """TestClient with no authentication overrides."""
  app.dependency_overrides.pop(get_current_user, None)
  app.dependency_overrides.pop(get_optional_current_user, None)
  app.dependency_overrides.pop(require_admin, None)
  client = TestClient(app)
  yield client
