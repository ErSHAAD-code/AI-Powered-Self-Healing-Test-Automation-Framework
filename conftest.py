"""
PyTest Fixtures — Test Infrastructure Configuration

Provides shared fixtures for the entire test suite:
- Local HTTP server serving the demo application
- Playwright browser/page lifecycle management
- Page Object instantiation (LoginPage, DashboardPage)
- Healing event collection and reporting hooks
- Test run history recording for flaky detection
"""

import os
import sys
import json
import time
import logging
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from datetime import datetime
from functools import partial

import pytest
from playwright.sync_api import sync_playwright

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pages.login_page import LoginPage
from pages.dashboard_page import DashboardPage
from core.smart_element import get_healing_events, clear_healing_events

logger = logging.getLogger(__name__)


# =============================================================================
# Demo App HTTP Server
# =============================================================================

class QuietHTTPHandler(SimpleHTTPRequestHandler):
    """HTTP handler that suppresses access logs."""

    def log_message(self, format, *args):
        pass  # Suppress noisy HTTP logs during tests


def _start_demo_server(port: int = 8000) -> HTTPServer:
    """Start a local HTTP server serving the demo application."""
    demo_dir = str(PROJECT_ROOT / "demo_app")
    handler = partial(QuietHTTPHandler, directory=demo_dir)

    server = HTTPServer(("localhost", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    logger.info("Demo server started at http://localhost:%d", port)
    return server


# =============================================================================
# Session-Scoped Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def demo_server():
    """Start the demo application HTTP server for the test session."""
    server = _start_demo_server(port=8000)
    yield server
    server.shutdown()
    logger.info("Demo server shut down")


@pytest.fixture(scope="session")
def base_url():
    """Base URL for the demo application."""
    return "http://localhost:8000"


@pytest.fixture(scope="session")
def playwright_instance():
    """Create a Playwright instance for the session."""
    pw = sync_playwright().start()
    yield pw
    pw.stop()


@pytest.fixture(scope="session")
def browser(playwright_instance):
    """Launch a browser for the test session."""
    headless = os.getenv("HEADLESS", "true").lower() == "true"
    browser = playwright_instance.chromium.launch(headless=headless)
    yield browser
    browser.close()


# =============================================================================
# Function-Scoped Fixtures (per test)
# =============================================================================

@pytest.fixture
def context(browser):
    """Create a new browser context for each test (isolation)."""
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    ctx.set_default_timeout(15000)
    yield ctx
    ctx.close()


@pytest.fixture
def page(context, demo_server, base_url):
    """Create a new page and navigate to the demo app."""
    pg = context.new_page()
    pg.goto(base_url)
    yield pg
    pg.close()


@pytest.fixture
def login_page(page, base_url) -> LoginPage:
    """Provide an initialized LoginPage instance."""
    lp = LoginPage(page, base_url)
    return lp


@pytest.fixture
def dashboard_page(page, base_url) -> DashboardPage:
    """Provide an initialized DashboardPage instance."""
    return DashboardPage(page, base_url)


# =============================================================================
# Healing Event Hooks
# =============================================================================

@pytest.fixture(autouse=True)
def track_healing_events(request):
    """Track healing events for each test."""
    test_name = request.node.name
    yield
    events = get_healing_events()
    if events:
        logger.info(
            "Test '%s' triggered %d healing event(s)",
            test_name, len(events),
        )


def pytest_sessionstart(session):
    """Clear healing events at session start."""
    clear_healing_events()


def pytest_sessionfinish(session, exitstatus):
    """Generate healing report at session end."""
    events = get_healing_events()
    if events:
        logger.info(
            "Session complete: %d total healing events", len(events)
        )
        reports_dir = Path("reports")
        reports_dir.mkdir(parents=True, exist_ok=True)

        events_file = reports_dir / "healing_events.json"
        with open(events_file, "w") as f:
            json.dump(events, f, indent=2, default=str)

        logger.info("Healing events saved to: %s", events_file)


# =============================================================================
# Test Run History Recording (for flaky test detection)
# =============================================================================

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Record test results for flaky test detection."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        result = {
            "test_name": item.name,
            "test_path": str(item.fspath),
            "outcome": report.outcome,
            "duration": report.duration,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if report.failed and report.longrepr:
            result["error"] = str(report.longrepr)[:500]

        history_dir = Path("data")
        history_dir.mkdir(parents=True, exist_ok=True)

        history_file = history_dir / "test_run_log.jsonl"
        with open(history_file, "a") as f:
            f.write(json.dumps(result) + "\n")
