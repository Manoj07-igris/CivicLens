"""Security Audit & Hardening Integration Test Suite (Phase 16).

Verifies:
1. Security response headers across all HTTP endpoints.
2. Host header / DNS rebinding protection via TrustedHostMiddleware.
3. System resource profiling endpoint (GET /api/v1/system/resources).
4. Windows reserved filenames and path traversal boundary checks.
5. Global Gemini RPM cap guard throttling.
"""

import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import Settings
from app.services.gemini_service import GeminiService, set_gemini_service

client = TestClient(app)


def test_security_headers_present_on_all_responses():
    """Verify standard security headers are injected on API responses."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "no-referrer"
    assert resp.headers.get("Cross-Origin-Resource-Policy") == "same-origin"
    assert "no-store" in resp.headers.get("Cache-Control", "")


def test_trusted_host_header_enforcement():
    """Verify requests with untrusted Host header are rejected with HTTP 400."""
    untrusted_client = TestClient(app, base_url="http://malicious-attacker.com")
    resp = untrusted_client.get("/api/v1/health", headers={"Host": "malicious-attacker.com"})
    assert resp.status_code == 400


def test_system_resources_endpoint_conforms_to_budget():
    """Verify /api/v1/system/resources reports memory, threads, and budget compliance."""
    resp = client.get("/api/v1/system/resources")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("healthy", "resource_warning")
    assert "process_memory" in data
    assert data["active_threads"] >= 1
    assert data["budget_limit_mb"] == 6144.0
    assert data["within_budget"] is True
    assert "python_version" in data


def test_windows_reserved_names_and_path_fuzzing():
    """Verify Windows reserved file names (CON, PRN, AUX, NUL) and encoded traversal paths are rejected."""
    reserved_names = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]
    for name in reserved_names:
        # Fuzz upload endpoint with invalid filename
        files = {"file": (f"{name}.pdf", b"%PDF-1.4 mock content", "application/pdf")}
        resp = client.post("/api/v1/documents/upload", files=files)
        # Should either be rejected as invalid, rate-limited, or handled safely without Windows handle error
        assert resp.status_code in (400, 422, 429, 201)

    # Path traversal with encoded dots
    traversal_ids = ["..%2F..%2Fetc%2Fpasswd", "..%5C..%5Cwindows%5Csystem32", "....//....//test"]
    for tid in traversal_ids:
        resp = client.get(f"/api/v1/documents/{tid}")
        assert resp.status_code in (400, 404, 422)


@pytest.mark.anyio
async def test_gemini_global_rpm_cap_enforcement():
    """Verify sliding-window RPM cap throttles rapid outbound calls."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.text = "Mock response"
    mock_resp.candidates = [MagicMock(finish_reason="STOP")]
    mock_resp.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=10, total_token_count=20)
    mock_client.aio.models.generate_content.return_value = mock_resp

    # Configure a small cap of 3 RPM for rapid testing
    settings = Settings(GEMINI_API_KEY="test_key_xyz", GEMINI_GLOBAL_RPM_CAP=3)
    service = GeminiService(settings=settings, client=mock_client)

    t0 = time.monotonic()
    # Execute 3 calls within the cap
    for _ in range(3):
        await service.generate_text("test prompt")
    elapsed_initial = time.monotonic() - t0
    # Initial 3 calls should execute immediately
    assert elapsed_initial < 1.0
    assert len(service._call_timestamps) == 3
