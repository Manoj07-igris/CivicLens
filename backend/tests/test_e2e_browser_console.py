"""E2E Browser Console and React Warning Regression Test.
Fails if any of the application routes logs a console error or React warning.
Marked with @pytest.mark.browser so it can be run selectively or as part of full suite.
"""

import pytest

ROUTES = [
    "/",
    "/login",
    "/signup",
    "/forgot-password",
    "/reset-password",
    "/terms",
    "/privacy",
    "/dashboard",
    "/assistant",
    "/documents",
    "/compare",
    "/verify",
    "/services",
    "/grievance",
    "/settings",
]

BASE_URL = "http://localhost:5173"


@pytest.mark.browser
def test_no_react_warnings_or_console_errors():
    """Verify that visiting all routes in English and Tamil produces zero React warnings or console errors."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("Playwright is not installed in the active environment.")

    console_warnings = []
    console_errors = []

    def on_console(msg):
        text = msg.text
        # Ignore expected anonymous 401s on initial /auth/me checks
        if "401" in text or "Unauthorized" in text:
            return
        if msg.type == "error":
            console_errors.append(f"[{msg.type}] {text}")
        elif msg.type == "warning":
            if "Warning:" in text or "validateDOMNesting" in text or "non-boolean" in text:
                console_warnings.append(f"[{msg.type}] {text}")

    def on_page_error(exc):
        console_errors.append(f"[pageerror] {exc}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.on("console", on_console)
        page.on("pageerror", on_page_error)

        for route in ROUTES:
            page.goto(f"{BASE_URL}{route}", wait_until="networkidle")
            page.wait_for_timeout(300)

            # Test Tamil toggle if present
            ta_btn = page.locator("button:has-text('தமிழ்')").first
            if ta_btn.is_visible():
                ta_btn.click()
                page.wait_for_timeout(250)
                en_btn = page.locator("button:has-text('English')").first
                if en_btn.is_visible():
                    en_btn.click()
                    page.wait_for_timeout(200)

        browser.close()

    assert len(console_warnings) == 0, f"React warnings found: {console_warnings}"
    assert len(console_errors) == 0, f"Console errors found: {console_errors}"
