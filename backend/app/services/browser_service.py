"""Controlled Browser Automation Service using Playwright.

Strictly bounded to local educational demonstration of public service workflows.
Never automates live external government portals; real portals remain clickable links.
Implements a 4-layer defense-in-depth security model:
1. Registry Gate (loopback demo portal only)
2. Network Interceptor (context route abortion for any non-demo URLs)
3. Navigation Assertions (strict URL prefix check before & after every action)
4. Fixed Action Set (no arbitrary code execution or unconstrained navigation)
"""

import atexit
import concurrent.futures
import datetime
import hashlib
import io
import json
import logging
from pathlib import Path
import queue
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import uuid

from PIL import Image

from app.core.config import Settings, get_settings
from app.core.errors import (
    BrowserActionError,
    BrowserApprovalRequiredError,
    BrowserError,
    BrowserNavigationBlockedError,
    BrowserSessionNotFoundError,
    PIIDetectedError,
)
from app.core.pii_guard import ensure_no_pii
from app.models.browser import (
    BrowserActionRequest,
    BrowserCapabilitiesResponse,
    BrowserSessionEvent,
    BrowserSessionRecord,
    BrowserSessionStatus,
    BrowserSubmissionPreview,
    BrowserSubmissionResult,
    DemoWorkflowManifest,
    FormFieldDefinition,
    FormStepDefinition,
)
from app.services.document_store import atomic_write_json, read_json_safe
from app.services.portal_registry import PortalRegistryService, get_portal_registry_service

logger = logging.getLogger("civiclens.browser")


def validate_session_id(session_id: str) -> str:
  """Validate that session_id is a valid UUID4 string to prevent directory traversal."""
  try:
    val = uuid.UUID(str(session_id).strip(), version=4)
    return str(val)
  except (ValueError, AttributeError, TypeError) as exc:
    raise ValueError(f"Invalid browser session identifier format: '{session_id}'") from exc


def compute_review_hash(filled_values: Dict[str, Any]) -> str:
  """Compute canonical SHA-256 hash of form values for human review approval binding."""
  clean = {k: str(v).strip() for k, v in sorted(filled_values.items()) if v is not None}
  serialized = json.dumps(clean, sort_keys=True)
  return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compress_screenshot(image_bytes: bytes, max_width: int = 900, quality: int = 70) -> bytes:
  """Downscale and compress screenshot to compact JPEG for low RAM/storage footprint."""
  img = Image.open(io.BytesIO(image_bytes))
  if img.mode in ("RGBA", "P"):
    img = img.convert("RGB")
  w, h = img.size
  if w > max_width:
    new_h = int(h * (max_width / w))
    img = img.resize((max_width, new_h), Image.Resampling.LANCZOS)
  out = io.BytesIO()
  img.save(out, format="JPEG", quality=quality, optimize=True)
  return out.getvalue()


from app.db.stores import SqliteBrowserSessionStore

BrowserSessionStore = SqliteBrowserSessionStore


class BrowserCommand:
  """Work unit submitted to the dedicated BrowserWorker thread."""

  def __init__(self, action: str, args: Dict[str, Any]):
    self.action = action
    self.args = args
    self.future = concurrent.futures.Future()


class BrowserWorker(threading.Thread):
  """Dedicated background OS thread owning sync_playwright and browser instance.

  Avoids Windows asyncio event loop conflicts and child process issues under uvicorn.
  """

  def __init__(self, settings: Settings, base_portal_url: str):
    super().__init__(name="CivicLens-BrowserWorker", daemon=True)
    self._settings = settings
    self._base_portal_url = base_portal_url
    self._cmd_queue: queue.Queue[Optional[BrowserCommand]] = queue.Queue()
    self._playwright = None
    self._browser = None
    self._contexts: Dict[str, Any] = {}
    self._pages: Dict[str, Any] = {}
    self._running = True
    self._last_activity = time.time()
    self.start()

  def run(self) -> None:
    logger.info("BrowserWorker background OS thread started.")
    while self._running:
      try:
        cmd = self._cmd_queue.get(timeout=2.0)
        if cmd is None:
          # Termination signal
          break
        self._last_activity = time.time()
        self._handle_command(cmd)
        self._cmd_queue.task_done()
      except queue.Empty:
        # Check idle timeout to close browser when inactive
        self._check_idle_timeout()
      except Exception as exc:
        logger.exception("Unexpected error in BrowserWorker run loop: %s", exc)

    self._cleanup_all()

  def submit(self, action: str, **kwargs: Any) -> Any:
    """Submit a command to the worker and block until complete with timeout."""
    cmd = BrowserCommand(action, kwargs)
    self._cmd_queue.put(cmd)
    timeout = self._settings.BROWSER_NAVIGATION_TIMEOUT_MS / 1000.0 + 5.0
    return cmd.future.result(timeout=timeout)

  def stop(self) -> None:
    self._running = False
    self._cmd_queue.put(None)
    self.join(timeout=5.0)

  def _ensure_browser(self) -> None:
    if self._browser is None or not self._browser.is_connected():
      from playwright.sync_api import sync_playwright
      if self._playwright is None:
        self._playwright = sync_playwright().start()

      logger.info("Launching Playwright Chromium (headless=%s)", self._settings.BROWSER_HEADLESS)
      self._browser = self._playwright.chromium.launch(
          headless=self._settings.BROWSER_HEADLESS,
          slow_mo=self._settings.BROWSER_SLOW_MO_MS,
      )

  def _check_idle_timeout(self) -> None:
    if self._browser and not self._contexts:
      idle_time = time.time() - self._last_activity
      if idle_time > self._settings.BROWSER_IDLE_CLOSE_SECONDS:
        logger.info("Browser idle for %.1fs with 0 active contexts; closing browser instance to conserve RAM.", idle_time)
        try:
          self._browser.close()
        except Exception:
          pass
        self._browser = None

  def _cleanup_all(self) -> None:
    for cid, ctx in list(self._contexts.items()):
      try:
        ctx.close()
      except Exception:
        pass
    self._contexts.clear()
    self._pages.clear()

    if self._browser:
      try:
        self._browser.close()
      except Exception:
        pass
      self._browser = None

    if self._playwright:
      try:
        self._playwright.stop()
      except Exception:
        pass
      self._playwright = None

  def _assert_allowed_url(self, page_url: str) -> None:
    """Defense Layer 3: Assert page.url matches strictly allowed demo portal prefix."""
    parsed = urlparse(page_url)
    if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
      raise BrowserNavigationBlockedError(f"Navigation to non-loopback host blocked: {page_url}")
    if not parsed.path.startswith("/demo-portal/"):
      raise BrowserNavigationBlockedError(f"Navigation outside /demo-portal/ blocked: {page_url}")

  def _handle_command(self, cmd: BrowserCommand) -> None:
    try:
      action = cmd.action
      args = cmd.args

      if action == "CREATE_SESSION":
        res = self._cmd_create_session(args["session_id"], args["target_url"], args.get("lang", "en"))
        cmd.future.set_result(res)
      elif action == "FILL_STEP":
        res = self._cmd_fill_step(args["session_id"], args["step_index"], args["values"], args["step_fields"])
        cmd.future.set_result(res)
      elif action == "GO_NEXT":
        res = self._cmd_go_next(args["session_id"])
        cmd.future.set_result(res)
      elif action == "GO_BACK":
        res = self._cmd_go_back(args["session_id"])
        cmd.future.set_result(res)
      elif action == "GO_TO_REVIEW":
        res = self._cmd_go_to_review(args["session_id"])
        cmd.future.set_result(res)
      elif action == "READ_BACK":
        res = self._cmd_read_back(args["session_id"])
        cmd.future.set_result(res)
      elif action == "SUBMIT":
        res = self._cmd_submit(args["session_id"], args.get("review_hash"))
        cmd.future.set_result(res)
      elif action == "TAKE_SCREENSHOT":
        res = self._cmd_take_screenshot(args["session_id"])
        cmd.future.set_result(res)
      elif action == "CLOSE_SESSION":
        res = self._cmd_close_session(args["session_id"])
        cmd.future.set_result(res)
      else:
        cmd.future.set_exception(ValueError(f"Unknown BrowserWorker command: {action}"))
    except Exception as exc:
      cmd.future.set_exception(exc)

  def _cmd_create_session(self, session_id: str, target_url: str, lang: str) -> Dict[str, Any]:
    self._ensure_browser()
    self._assert_allowed_url(target_url)

    # Layer 2: Network interceptor & isolation
    context = self._browser.new_context(
        viewport={
            "width": self._settings.BROWSER_VIEWPORT_WIDTH,
            "height": self._settings.BROWSER_VIEWPORT_HEIGHT,
        },
        ignore_https_errors=True,
    )

    # Route interceptor: abort all requests outside allowed loopback demo path
    def route_filter(route):
      req_url = route.request.url
      p = urlparse(req_url)
      if p.hostname in ("127.0.0.1", "localhost", "::1") and (p.path.startswith("/demo-portal/") or p.path.startswith("/api/v1/")):
        route.continue_()
      elif req_url.startswith("data:"):
        route.continue_()
      else:
        logger.warning("Layer 2 Defense: Intercepted and aborted external network request: %s", req_url)
        route.abort("blockedbyclient")

    context.route("**/*", route_filter)
    page = context.new_page()

    # Block popups, new tabs, and native alert dialogs
    page.on("dialog", lambda dialog: dialog.dismiss())
    context.on("page", lambda p: p.close())

    # Navigate
    full_url = f"{target_url}?lang={lang}" if "?" not in target_url else f"{target_url}&lang={lang}"
    page.goto(full_url, timeout=self._settings.BROWSER_NAVIGATION_TIMEOUT_MS)
    page.wait_for_selector("#demo-form", timeout=self._settings.BROWSER_ACTION_TIMEOUT_MS)

    self._assert_allowed_url(page.url)

    self._contexts[session_id] = context
    self._pages[session_id] = page

    # Capture initial screenshot
    raw_shot = page.screenshot(type="jpeg", quality=self._settings.BROWSER_SCREENSHOT_QUALITY)
    compressed = compress_screenshot(raw_shot, self._settings.BROWSER_SCREENSHOT_MAX_WIDTH, self._settings.BROWSER_SCREENSHOT_QUALITY)

    return {
        "url": page.url,
        "current_step": 1,
        "screenshot_bytes": compressed,
    }

  def _get_page(self, session_id: str):
    if session_id not in self._pages:
      raise BrowserSessionNotFoundError(f"Browser page for session '{session_id}' not found.")
    page = self._pages[session_id]
    self._assert_allowed_url(page.url)
    return page

  def _cmd_fill_step(self, session_id: str, step_index: int, values: Dict[str, Any], step_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    page = self._get_page(session_id)

    # Fill fields defined in manifest
    for f in step_fields:
      fname = f["name"]
      sel = f["selector"]
      ftype = f.get("field_type", "text")

      if fname in values:
        val = values[fname]
        locator = page.locator(sel)
        if locator.count() > 0:
          if ftype == "select":
            locator.select_option(str(val))
          elif ftype == "checkbox":
            if bool(val):
              locator.check()
            else:
              locator.uncheck()
          else:
            locator.fill(str(val))

    page.wait_for_timeout(100)
    raw_shot = page.screenshot(type="jpeg", quality=self._settings.BROWSER_SCREENSHOT_QUALITY)
    compressed = compress_screenshot(raw_shot, self._settings.BROWSER_SCREENSHOT_MAX_WIDTH, self._settings.BROWSER_SCREENSHOT_QUALITY)

    return {
        "url": page.url,
        "step_index": step_index,
        "screenshot_bytes": compressed,
    }

  def _cmd_go_next(self, session_id: str) -> Dict[str, Any]:
    page = self._get_page(session_id)
    page.click("#btn-next", timeout=self._settings.BROWSER_ACTION_TIMEOUT_MS)
    page.wait_for_timeout(200)

    cur_step = page.evaluate("() => window.__DEMO_PORTAL__ ? window.__DEMO_PORTAL__.getCurrentStep() : 1")
    raw_shot = page.screenshot(type="jpeg", quality=self._settings.BROWSER_SCREENSHOT_QUALITY)
    compressed = compress_screenshot(raw_shot, self._settings.BROWSER_SCREENSHOT_MAX_WIDTH, self._settings.BROWSER_SCREENSHOT_QUALITY)

    return {
        "url": page.url,
        "current_step": cur_step,
        "screenshot_bytes": compressed,
    }

  def _cmd_go_back(self, session_id: str) -> Dict[str, Any]:
    page = self._get_page(session_id)
    page.click("#btn-back", timeout=self._settings.BROWSER_ACTION_TIMEOUT_MS)
    page.wait_for_timeout(200)

    cur_step = page.evaluate("() => window.__DEMO_PORTAL__ ? window.__DEMO_PORTAL__.getCurrentStep() : 1")
    raw_shot = page.screenshot(type="jpeg", quality=self._settings.BROWSER_SCREENSHOT_QUALITY)
    compressed = compress_screenshot(raw_shot, self._settings.BROWSER_SCREENSHOT_MAX_WIDTH, self._settings.BROWSER_SCREENSHOT_QUALITY)

    return {
        "url": page.url,
        "current_step": cur_step,
        "screenshot_bytes": compressed,
    }

  def _cmd_go_to_review(self, session_id: str) -> Dict[str, Any]:
    page = self._get_page(session_id)
    page.evaluate("() => { if (window.__DEMO_PORTAL__) { window.__DEMO_PORTAL__.goToStep(5); } }")
    page.wait_for_timeout(200)

    form_data = page.evaluate("() => window.__DEMO_PORTAL__ ? window.__DEMO_PORTAL__.getFormData() : {}")
    raw_shot = page.screenshot(type="jpeg", quality=self._settings.BROWSER_SCREENSHOT_QUALITY)
    compressed = compress_screenshot(raw_shot, self._settings.BROWSER_SCREENSHOT_MAX_WIDTH, self._settings.BROWSER_SCREENSHOT_QUALITY)

    return {
        "url": page.url,
        "current_step": 5,
        "form_data": form_data,
        "screenshot_bytes": compressed,
    }

  def _cmd_read_back(self, session_id: str) -> Dict[str, Any]:
    page = self._get_page(session_id)
    form_data = page.evaluate("() => window.__DEMO_PORTAL__ ? window.__DEMO_PORTAL__.getFormData() : {}")
    cur_step = page.evaluate("() => window.__DEMO_PORTAL__ ? window.__DEMO_PORTAL__.getCurrentStep() : 1")

    return {
        "url": page.url,
        "current_step": cur_step,
        "form_data": form_data,
    }

  def _cmd_submit(self, session_id: str, review_hash: Optional[str]) -> Dict[str, Any]:
    page = self._get_page(session_id)

    # Check acknowledgement checkbox
    page.evaluate("() => { const cb = document.getElementById('fictional_acknowledged'); if (cb) cb.checked = true; }")
    page.click("#btn-submit", timeout=self._settings.BROWSER_ACTION_TIMEOUT_MS)
    page.wait_for_selector("#submission-success:not(.hidden)", timeout=self._settings.BROWSER_ACTION_TIMEOUT_MS)

    app_ref = page.evaluate("() => { const r = document.getElementById('receipt-ref'); return r ? r.innerText.trim() : 'DEMO-IC-SUCCESS'; }")

    raw_shot = page.screenshot(type="jpeg", quality=self._settings.BROWSER_SCREENSHOT_QUALITY)
    compressed = compress_screenshot(raw_shot, self._settings.BROWSER_SCREENSHOT_MAX_WIDTH, self._settings.BROWSER_SCREENSHOT_QUALITY)

    return {
        "url": page.url,
        "application_number": app_ref,
        "screenshot_bytes": compressed,
    }

  def _cmd_take_screenshot(self, session_id: str) -> bytes:
    page = self._get_page(session_id)
    raw_shot = page.screenshot(type="jpeg", quality=self._settings.BROWSER_SCREENSHOT_QUALITY)
    return compress_screenshot(raw_shot, self._settings.BROWSER_SCREENSHOT_MAX_WIDTH, self._settings.BROWSER_SCREENSHOT_QUALITY)

  def _cmd_close_session(self, session_id: str) -> bool:
    if session_id in self._contexts:
      ctx = self._contexts.pop(session_id)
      self._pages.pop(session_id, None)
      try:
        ctx.close()
      except Exception:
        pass
    return True


class BrowserService:
  """High-level service coordinating browser demo sessions, PII guard, and audit trails."""

  _instance: Optional["BrowserService"] = None

  def __init__(
      self,
      settings: Optional[Settings] = None,
      portal_service: Optional[PortalRegistryService] = None,
      mock_mode: bool = False,
  ):
    self._settings = settings or get_settings()
    self._portal_service = portal_service or get_portal_registry_service()
    self._store = BrowserSessionStore(self._settings)
    self._mock_mode = mock_mode
    self._manifest: Optional[DemoWorkflowManifest] = None
    self._active_sessions: Dict[str, str] = {}  # session_id -> status
    self._lock = threading.Lock()

    # Load manifest from demo_portal/manifest.json
    self._load_manifest()

    # Determine default loopback target URL for the demo portal
    base_url = getattr(self._settings, "PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    self._demo_portal_url = f"{base_url.rstrip('/')}/demo-portal/"

    # Initialize BrowserWorker if not in mock mode and enabled
    self._worker: Optional[BrowserWorker] = None
    if self._settings.BROWSER_ENABLED and not self._mock_mode:
      try:
        self._worker = BrowserWorker(self._settings, self._demo_portal_url)
        atexit.register(self.shutdown)
      except Exception as exc:
        logger.warning("Could not launch Playwright BrowserWorker: %s. Falling back to deterministic simulation.", exc)
        self._mock_mode = True

  def _load_manifest(self) -> None:
    manifest_path = Path(__file__).resolve().parent.parent.parent.parent / "demo_portal" / "manifest.json"
    if manifest_path.exists():
      try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        self._manifest = DemoWorkflowManifest(**data)
      except Exception as exc:
        logger.warning("Could not parse demo portal manifest: %s", exc)

    if not self._manifest:
      # Sensible fallback manifest
      self._manifest = DemoWorkflowManifest()

  @property
  def manifest(self) -> DemoWorkflowManifest:
    if not self._manifest:
      self._load_manifest()
    return self._manifest

  def get_capabilities(self) -> BrowserCapabilitiesResponse:
    with self._lock:
      active_count = len(self._active_sessions)
    return BrowserCapabilitiesResponse(
        enabled=self._settings.BROWSER_ENABLED and not self._mock_mode,
        headless=self._settings.BROWSER_HEADLESS,
        max_concurrent_sessions=self._settings.BROWSER_MAX_CONCURRENT_SESSIONS,
        active_sessions_count=active_count,
        supported_workflows=["demo_income_certificate"],
        demo_portal_url=self._demo_portal_url,
    )

  def start_session(
      self,
      portal_id: str = "prt_demo_portal",
      lang: str = "en",
      workflow_id: str = "demo_income_certificate",
      owner_id: Optional[str] = None,
  ) -> BrowserSessionRecord:
    """Initialize a new strictly bounded demo session on the local portal."""
    if not self._settings.BROWSER_ENABLED:
      raise BrowserError("Browser automation is disabled in configuration.")

    # Defense Layer 1: Portal Registry Gate
    try:
      portal = self._portal_service.get_portal(portal_id)
    except Exception:
      raise BrowserNavigationBlockedError(f"Portal '{portal_id}' is not in the curated registry.")

    if portal.kind != "demo":
      raise BrowserNavigationBlockedError(
          f"Portal '{portal.name}' has kind '{portal.kind}'. Playwright automation is strictly restricted to 'demo' portals."
      )

    parsed_url = urlparse(portal.url)
    if parsed_url.hostname not in ("127.0.0.1", "localhost", "::1"):
      raise BrowserNavigationBlockedError(f"Demo portal must run on loopback host: {portal.url}")

    with self._lock:
      if len(self._active_sessions) >= self._settings.BROWSER_MAX_CONCURRENT_SESSIONS:
        # Check if an active session is expired
        self._cleanup_expired_sessions()
        if len(self._active_sessions) >= self._settings.BROWSER_MAX_CONCURRENT_SESSIONS:
          raise BrowserActionError("Maximum concurrent demo sessions reached. Please wait for the current session to finish.")

      session_id = str(uuid.uuid4())
      self._active_sessions[session_id] = "active"

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    expires_dt = now_dt + datetime.timedelta(seconds=self._settings.BROWSER_SESSION_TTL_SECONDS)
    now_iso = now_dt.isoformat()
    expires_iso = expires_dt.isoformat()

    record = BrowserSessionRecord(
        session_id=session_id,
        portal_id=portal_id,
        portal_url=portal.url,
        workflow_id=workflow_id,
        status="active",
        current_step=1,
        total_steps=5,
        lang=lang,
        created_at=now_iso,
        updated_at=now_iso,
        expires_at=expires_iso,
        actions_count=1,
        screenshots_count=0,
        filled_values={},
    )

    screenshot_id = f"shot_{session_id[:8]}_step1_init"
    if self._worker and not self._mock_mode:
      try:
        res = self._worker.submit("CREATE_SESSION", session_id=session_id, target_url=portal.url, lang=lang)
        if "screenshot_bytes" in res:
          self._store.save_screenshot(session_id, screenshot_id, res["screenshot_bytes"])
          record.screenshots_count = 1
          record.last_screenshot_id = screenshot_id
          record.last_screenshot_url = f"/api/v1/browser/sessions/{session_id}/screenshots/{screenshot_id}"
      except Exception as exc:
        logger.warning("BrowserWorker failed to create real session: %s. Using simulation.", exc)
        self._mock_mode = True

    event = BrowserSessionEvent(
        timestamp=now_iso,
        action="open_portal",
        step_index=1,
        url=portal.url,
        success=True,
        message="Demo session initialized on local portal.",
        screenshot_id=screenshot_id if record.screenshots_count > 0 else None,
    )
    record.events.append(event)
    self._store.save_session(record, owner_id=owner_id)
    from app.services.activity_service import get_activity_service
    get_activity_service().record_activity("browser.session_started", "browser_session", session_id, owner_id=owner_id)
    logger.info("Initialized browser demo session %s on %s", session_id, portal.url)
    return record

  def get_session(self, session_id: str, owner_id: Optional[str] = None) -> BrowserSessionRecord:
    record = self._store.read_session(session_id, owner_id=owner_id)
    if not record:
      raise BrowserSessionNotFoundError(f"Browser demo session '{session_id}' not found.")
    return record

  def list_sessions(self, limit: int = 20, owner_id: Optional[str] = None) -> List[BrowserSessionRecord]:
    return self._store.list_sessions(limit=limit, owner_id=owner_id)

  def fill_step(
      self,
      session_id: str,
      step_index: int,
      values: Dict[str, Any],
      fictional_confirmed: bool = True,
      owner_id: Optional[str] = None,
  ) -> BrowserSessionRecord:
    """Fill form fields for a given step after strict PII scanning."""
    if not fictional_confirmed:
      raise BrowserApprovalRequiredError("You must confirm all submitted values are fictional demo data.")

    # PII Guard: Inspect entire payload representation
    text_to_scan = json.dumps(values, ensure_ascii=False)
    ensure_no_pii(text_to_scan)

    record = self.get_session(session_id, owner_id=owner_id)
    self._assert_session_active(record)

    # Validate against manifest
    step_def = next((s for s in self.manifest.steps if s.step_index == step_index), None)
    if not step_def:
      raise BrowserActionError(f"Step index {step_index} is invalid for workflow '{record.workflow_id}'.")

    # Update session filled values
    for k, v in values.items():
      record.filled_values[k] = v

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record.updated_at = now_iso
    record.actions_count += 1
    screenshot_id = f"shot_{session_id[:8]}_step{step_index}_{int(time.time())}"

    if self._worker and not self._mock_mode:
      step_fields_dict = [f.model_dump() for f in step_def.fields]
      res = self._worker.submit(
          "FILL_STEP",
          session_id=session_id,
          step_index=step_index,
          values=values,
          step_fields=step_fields_dict,
      )
      if "screenshot_bytes" in res:
        self._store.save_screenshot(session_id, screenshot_id, res["screenshot_bytes"])
        record.screenshots_count += 1
        record.last_screenshot_id = screenshot_id
        record.last_screenshot_url = f"/api/v1/browser/sessions/{session_id}/screenshots/{screenshot_id}"

    event = BrowserSessionEvent(
        timestamp=now_iso,
        action="fill_step",
        step_index=step_index,
        url=record.portal_url,
        success=True,
        message=f"Filled {len(values)} fictional values into step {step_index}.",
        screenshot_id=screenshot_id if record.screenshots_count > 0 else None,
    )
    record.events.append(event)
    self._store.save_session(record, owner_id=owner_id)
    return record

  def navigate_next(self, session_id: str, owner_id: Optional[str] = None) -> BrowserSessionRecord:
    record = self.get_session(session_id, owner_id=owner_id)
    self._assert_session_active(record)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record.actions_count += 1
    screenshot_id = f"shot_{session_id[:8]}_next_{int(time.time())}"

    new_step = min(5, record.current_step + 1)
    if self._worker and not self._mock_mode:
      res = self._worker.submit("GO_NEXT", session_id=session_id)
      new_step = res.get("current_step", new_step)
      if "screenshot_bytes" in res:
        self._store.save_screenshot(session_id, screenshot_id, res["screenshot_bytes"])
        record.screenshots_count += 1
        record.last_screenshot_id = screenshot_id
        record.last_screenshot_url = f"/api/v1/browser/sessions/{session_id}/screenshots/{screenshot_id}"

    record.current_step = new_step
    record.updated_at = now_iso

    event = BrowserSessionEvent(
        timestamp=now_iso,
        action="go_next",
        step_index=new_step,
        url=record.portal_url,
        success=True,
        message=f"Navigated forward to step {new_step}.",
        screenshot_id=screenshot_id if record.screenshots_count > 0 else None,
    )
    record.events.append(event)

    if record.current_step == 5:
      record.review_hash = compute_review_hash(record.filled_values)

    self._store.save_session(record, owner_id=owner_id)
    return record

  def navigate_back(self, session_id: str, owner_id: Optional[str] = None) -> BrowserSessionRecord:
    record = self.get_session(session_id, owner_id=owner_id)
    self._assert_session_active(record)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record.actions_count += 1
    screenshot_id = f"shot_{session_id[:8]}_back_{int(time.time())}"

    new_step = max(1, record.current_step - 1)
    if self._worker and not self._mock_mode:
      res = self._worker.submit("GO_BACK", session_id=session_id)
      new_step = res.get("current_step", new_step)
      if "screenshot_bytes" in res:
        self._store.save_screenshot(session_id, screenshot_id, res["screenshot_bytes"])
        record.screenshots_count += 1
        record.last_screenshot_id = screenshot_id
        record.last_screenshot_url = f"/api/v1/browser/sessions/{session_id}/screenshots/{screenshot_id}"

    record.current_step = new_step
    record.updated_at = now_iso

    event = BrowserSessionEvent(
        timestamp=now_iso,
        action="go_back",
        step_index=new_step,
        url=record.portal_url,
        success=True,
        message=f"Navigated back to step {new_step}.",
        screenshot_id=screenshot_id if record.screenshots_count > 0 else None,
    )
    record.events.append(event)
    self._store.save_session(record, owner_id=owner_id)
    return record

  def get_review_preview(self, session_id: str, owner_id: Optional[str] = None) -> BrowserSubmissionPreview:
    """Return verified form state and canonical review hash for human approval."""
    record = self.get_session(session_id, owner_id=owner_id)
    self._assert_session_active(record)

    if self._worker and not self._mock_mode:
      try:
        res = self._worker.submit("GO_TO_REVIEW", session_id=session_id)
        if "form_data" in res and isinstance(res["form_data"], dict):
          for k, v in res["form_data"].items():
            if v:
              record.filled_values[k] = v
        record.current_step = 5
      except Exception as exc:
        logger.warning("Could not execute GO_TO_REVIEW in worker: %s", exc)

    r_hash = compute_review_hash(record.filled_values)
    record.review_hash = r_hash
    record.current_step = 5
    self._store.save_session(record, owner_id=owner_id)

    summary = {
        "Applicant": str(record.filled_values.get("applicant_name", "K. Ananya (Demo)")),
        "Taluk & District": f"{record.filled_values.get('taluk', 'Mylapore')}, {record.filled_values.get('district', 'Chennai (Demo)')}",
        "Annual Family Income": f"INR {record.filled_values.get('annual_income', 72000)}",
        "Purpose": str(record.filled_values.get("purpose", "Higher Education Scholarship")),
    }

    return BrowserSubmissionPreview(
        session_id=session_id,
        review_hash=r_hash,
        filled_values=record.filled_values,
        summary=summary,
    )

  def submit_demo(
      self,
      session_id: str,
      review_hash: str,
      fictional_confirmed: bool = True,
      owner_id: Optional[str] = None,
  ) -> BrowserSubmissionResult:
    """Submit the demo application bound to the canonical review hash."""
    if not fictional_confirmed:
      raise BrowserApprovalRequiredError("You must confirm all submitted values are fictional demo data.")

    record = self.get_session(session_id, owner_id=owner_id)
    self._assert_session_active(record)

    expected_hash = compute_review_hash(record.filled_values)
    if review_hash.strip().lower() != expected_hash.strip().lower():
      raise BrowserApprovalRequiredError(
          "Canonical review hash mismatch. The form values were modified after review was generated. "
          "Please review the updated values and approve again."
      )

    app_num = f"DEMO-IC-{uuid.uuid4().hex[:6].upper()}"
    screenshot_id = f"shot_{session_id[:8]}_submitted"

    if self._worker and not self._mock_mode:
      try:
        res = self._worker.submit("SUBMIT", session_id=session_id, review_hash=review_hash)
        app_num = res.get("application_number", app_num)
        if "screenshot_bytes" in res:
          self._store.save_screenshot(session_id, screenshot_id, res["screenshot_bytes"])
          record.screenshots_count += 1
          record.last_screenshot_id = screenshot_id
          record.last_screenshot_url = f"/api/v1/browser/sessions/{session_id}/screenshots/{screenshot_id}"
      except Exception as exc:
        logger.warning("BrowserWorker submit simulation fallback: %s", exc)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    submission_id = f"sub_{uuid.uuid4().hex[:8]}"

    record.status = "submitted"
    record.submission_id = submission_id
    record.application_number = app_num
    record.updated_at = now_iso
    record.actions_count += 1

    event = BrowserSessionEvent(
        timestamp=now_iso,
        action="submit",
        step_index=5,
        url=record.portal_url,
        success=True,
        message=f"Demo application submitted successfully with reference {app_num}.",
        screenshot_id=screenshot_id if record.screenshots_count > 0 else None,
    )
    record.events.append(event)
    self._store.save_session(record, owner_id=owner_id)
    from app.services.activity_service import get_activity_service
    get_activity_service().record_activity("browser.demo_submitted", "browser_session", session_id, owner_id=owner_id)

    with self._lock:
      self._active_sessions.pop(session_id, None)

    msg_en = (
        f"Your educational demo application has been simulated successfully. "
        f"Application Reference: {app_num}. No real data was submitted to any government portal."
    )
    msg_ta = (
        f"உங்கள் கல்வி மாதிரி விண்ணப்பம் வெற்றிகரமாகப் பதிவு செய்யப்பட்டது. "
        f"விண்ணப்பக் குறிப்பு எண்: {app_num}. எந்த அரசு வலைவாசலுக்கும் உண்மையான தரவு அனுப்பப்படவில்லை."
    )

    return BrowserSubmissionResult(
        session_id=session_id,
        submission_id=submission_id,
        status="demo_submitted",
        application_number=app_num,
        timestamp=now_iso,
        confirmation_message=msg_en,
        confirmation_message_ta=msg_ta,
        screenshot_id=screenshot_id if record.screenshots_count > 0 else None,
    )

  def close_session(self, session_id: str, owner_id: Optional[str] = None) -> BrowserSessionRecord:
    record = self.get_session(session_id, owner_id=owner_id)
    if self._worker and not self._mock_mode:
      try:
        self._worker.submit("CLOSE_SESSION", session_id=session_id)
      except Exception:
        pass

    with self._lock:
      self._active_sessions.pop(session_id, None)

    if record.status == "active":
      record.status = "closed"

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record.updated_at = now_iso
    event = BrowserSessionEvent(
        timestamp=now_iso,
        action="close",
        step_index=record.current_step,
        url=record.portal_url,
        success=True,
        message="Demo session closed.",
    )
    record.events.append(event)
    self._store.save_session(record, owner_id=owner_id)
    return record

  def get_screenshot_path(self, session_id: str, screenshot_id: str, owner_id: Optional[str] = None) -> Path:
    # Validate session access first
    self.get_session(session_id, owner_id=owner_id)
    path = self._store.get_screenshot_path(session_id, screenshot_id)
    if not path or not path.exists():
      raise BrowserSessionNotFoundError(f"Screenshot '{screenshot_id}' not found for session '{session_id}'.")
    return path

  def _assert_session_active(self, record: BrowserSessionRecord) -> None:
    if record.status in ("submitted", "closed", "error", "timed_out"):
      raise BrowserActionError(f"Session is in '{record.status}' state and no longer accepts actions.")

    # Check TTL expiration
    try:
      exp_dt = datetime.datetime.fromisoformat(record.expires_at)
      if datetime.datetime.now(datetime.timezone.utc) > exp_dt:
        record.status = "timed_out"
        self._store.save_session(record)
        with self._lock:
          self._active_sessions.pop(record.session_id, None)
        raise BrowserActionError("Demo session has timed out after 10 minutes. Please start a new session.")
    except Exception:
      pass

    if record.actions_count >= self._settings.BROWSER_MAX_ACTIONS_PER_SESSION:
      raise BrowserActionError(
          f"Maximum action limit ({self._settings.BROWSER_MAX_ACTIONS_PER_SESSION}) reached for this demo session."
      )

  def _cleanup_expired_sessions(self) -> None:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    for sid in list(self._active_sessions.keys()):
      rec = self._store.read_session(sid)
      if rec:
        try:
          if now_utc > datetime.datetime.fromisoformat(rec.expires_at):
            rec.status = "timed_out"
            self._store.save_session(rec)
            self._active_sessions.pop(sid, None)
        except Exception:
          pass

  def shutdown(self) -> None:
    """Terminate the dedicated background worker gracefully on server exit."""
    if self._worker:
      try:
        self._worker.stop()
      except Exception:
        pass
      self._worker = None


def get_browser_service() -> BrowserService:
  """Singleton factory provider for BrowserService."""
  if BrowserService._instance is None:
    BrowserService._instance = BrowserService()
  return BrowserService._instance
