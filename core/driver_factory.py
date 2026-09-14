"""
Driver Factory Module — Hybrid Framework (Playwright + Selenium Adapter)

Provides a unified interface for creating browser instances using Playwright
as the primary engine, with a thin Selenium WebDriver adapter for legacy
compatibility. Implements the Factory Pattern for browser instantiation and
the Context Manager pattern for clean resource teardown.

Part of the Page Object Model (POM) hybrid automation framework.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

import yaml
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Load configuration
_CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"


def _load_config() -> dict:
    """Load the central configuration file."""
    with open(_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


class DriverFactory:
    """
    Factory class for creating browser driver instances.

    Supports Playwright (chromium, firefox, webkit) as the primary automation
    engine and provides a Selenium adapter for projects that require WebDriver
    API compatibility.

    Usage (Context Manager — recommended):
        with DriverFactory.create_page() as page:
            page.goto("https://example.com")

    Usage (Manual lifecycle):
        factory = DriverFactory()
        factory.start()
        page = factory.new_page()
        # ... test logic ...
        factory.stop()
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize DriverFactory with optional configuration override.

        Args:
            config: Optional dict overriding config.yaml values.
                    Keys: type, headless, timeout_ms, viewport
        """
        full_config = _load_config()
        browser_config = full_config.get("browser", {})

        if config:
            browser_config.update(config)

        self.browser_type: str = browser_config.get("type", "chromium")
        self.headless: bool = browser_config.get(
            "headless",
            os.getenv("HEADLESS", "true").lower() == "true"
        )
        self.timeout_ms: int = browser_config.get("timeout_ms", 30000)
        self.viewport: dict = browser_config.get(
            "viewport", {"width": 1280, "height": 720}
        )
        self.screenshot_on_failure: bool = browser_config.get(
            "screenshot_on_failure", True
        )
        self.screenshot_dir: str = browser_config.get(
            "screenshot_dir", "reports/screenshots"
        )

        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

        logger.info(
            "DriverFactory initialized: browser=%s, headless=%s",
            self.browser_type, self.headless
        )

    def start(self) -> "DriverFactory":
        """
        Start the Playwright engine and launch the browser.

        Returns:
            self for method chaining.
        """
        self._playwright = sync_playwright().start()

        launcher = getattr(self._playwright, self.browser_type, None)
        if launcher is None:
            raise ValueError(
                f"Unsupported browser type: {self.browser_type}. "
                f"Choose from: chromium, firefox, webkit"
            )

        self._browser = launcher.launch(headless=self.headless)
        self._context = self._browser.new_context(
            viewport=self.viewport
        )
        self._context.set_default_timeout(self.timeout_ms)

        logger.info(
            "Browser launched: %s (headless=%s)", self.browser_type, self.headless
        )
        return self

    def new_page(self) -> Page:
        """
        Create and return a new Playwright Page instance.

        Returns:
            Playwright Page object.

        Raises:
            RuntimeError: If start() has not been called.
        """
        if self._context is None:
            raise RuntimeError(
                "DriverFactory not started. Call start() first or use "
                "the context manager: 'with DriverFactory.create_page() as page:'"
            )
        page = self._context.new_page()
        logger.debug("New page created")
        return page

    def stop(self):
        """Tear down browser, context, and Playwright engine."""
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        logger.info("Browser and Playwright engine stopped")

    @staticmethod
    @contextmanager
    def create_page(config: Optional[dict] = None):
        """
        Context manager that yields a ready-to-use Playwright Page.

        Automatically handles startup and teardown.

        Args:
            config: Optional configuration overrides.

        Yields:
            Playwright Page object.

        Example:
            with DriverFactory.create_page({"headless": False}) as page:
                page.goto("http://localhost:8000")
                assert page.title() == "Enterprise Test Automation Demo"
        """
        factory = DriverFactory(config)
        factory.start()
        page = factory.new_page()
        try:
            yield page
        finally:
            factory.stop()


class SeleniumAdapter:
    """
    Thin adapter providing Selenium WebDriver-like API over Playwright.

    This adapter allows legacy test code written for Selenium to run on
    the Playwright engine with minimal changes. It maps common Selenium
    methods (get, find_element, quit) to their Playwright equivalents.

    Usage:
        driver = SeleniumAdapter()
        driver.get("https://example.com")
        element = driver.find_element("id", "username")
        element.send_keys("admin")
        driver.quit()
    """

    def __init__(self, config: Optional[dict] = None):
        self._factory = DriverFactory(config)
        self._factory.start()
        self._page = self._factory.new_page()

    @property
    def page(self) -> Page:
        """Access the underlying Playwright Page object."""
        return self._page

    def get(self, url: str):
        """Navigate to a URL (Selenium-style)."""
        self._page.goto(url)

    def find_element(self, by: str, value: str):
        """
        Find an element using Selenium-style locator strategies.

        Args:
            by: Locator strategy — "id", "css", "xpath", "name", "class", "text"
            value: Locator value.

        Returns:
            Playwright Locator object (supports .click(), .fill(), etc.)
        """
        strategy_map = {
            "id": lambda v: self._page.locator(f"#{v}"),
            "css": lambda v: self._page.locator(v),
            "xpath": lambda v: self._page.locator(f"xpath={v}"),
            "name": lambda v: self._page.locator(f"[name='{v}']"),
            "class": lambda v: self._page.locator(f".{v}"),
            "text": lambda v: self._page.get_by_text(v),
        }

        locator_fn = strategy_map.get(by.lower().replace("_", "").replace(" ", ""))
        if locator_fn is None:
            raise ValueError(f"Unsupported locator strategy: {by}")

        return locator_fn(value)

    @property
    def title(self) -> str:
        """Get the page title (Selenium-style property)."""
        return self._page.title()

    @property
    def current_url(self) -> str:
        """Get the current URL."""
        return self._page.url

    def quit(self):
        """Tear down the browser (Selenium-style)."""
        self._factory.stop()
