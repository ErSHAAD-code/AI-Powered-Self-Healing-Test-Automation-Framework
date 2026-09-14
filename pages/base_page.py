"""
Base Page — Foundation for the Page Object Model (POM) Pattern

Provides common functionality shared across all page objects:
- SmartElement creation (self-healing element wrapper)
- Navigation helpers
- Wait utilities
- Screenshot capture
- Structured logging

All page objects inherit from BasePage, ensuring consistent
self-healing behavior and test infrastructure integration
across the entire UI automation suite.
"""

import logging
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page

from core.smart_element import SmartElement

logger = logging.getLogger(__name__)


class BasePage:
    """
    Base class for the Page Object Model (POM).

    Provides a self-healing-aware foundation for all page objects.
    Each page object inherits from BasePage and uses smart_find()
    to create SmartElement instances that automatically heal
    broken locators.

    Usage:
        class LoginPage(BasePage):
            def __init__(self, page):
                super().__init__(page)
                self._username = "#username"
                self._password = "#password"
                self._login_btn = "#login-button"

            def login(self, user, password):
                self.smart_find(self._username, intent="Username input").fill(user)
                self.smart_find(self._password, intent="Password input").fill(password)
                self.smart_find(self._login_btn, intent="Login button").click()
    """

    def __init__(self, page: Page, base_url: str = ""):
        """
        Initialize the base page.

        Args:
            page: Playwright Page instance.
            base_url: Base URL for the application under test.
        """
        self.page = page
        self.base_url = base_url
        self._test_name: Optional[str] = None

    def set_test_name(self, name: str):
        """Set the current test name for healing context."""
        self._test_name = name

    def smart_find(
        self,
        selector: str,
        strategy: str = "css",
        intent: str = "",
        timeout_ms: int = 5000,
    ) -> SmartElement:
        """
        Create a SmartElement with self-healing capabilities.

        This is the primary method page objects should use to interact
        with elements. It creates a SmartElement that will automatically
        attempt self-healing if the selector is broken.

        Args:
            selector: CSS or XPath selector.
            strategy: Locator strategy ("css", "xpath", "text", "role").
            intent: Human-readable description of the element's purpose.
            timeout_ms: Timeout for element location (ms).

        Returns:
            SmartElement instance ready for interaction.
        """
        return SmartElement(
            page=self.page,
            selector=selector,
            strategy=strategy,
            intent=intent,
            test_name=self._test_name,
            timeout_ms=timeout_ms,
        )

    def navigate(self, path: str = ""):
        """
        Navigate to a URL (relative to base_url or absolute).

        Args:
            path: URL path or full URL.
        """
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        logger.info("Navigating to: %s", url)
        self.page.goto(url, wait_until="domcontentloaded")

    def get_title(self) -> str:
        """Get the current page title."""
        return self.page.title()

    def get_url(self) -> str:
        """Get the current page URL."""
        return self.page.url

    def wait_for_load(self, timeout_ms: int = 30000):
        """Wait for the page to finish loading."""
        self.page.wait_for_load_state("networkidle", timeout=timeout_ms)

    def take_screenshot(self, name: str = "screenshot") -> str:
        """
        Capture a screenshot and save it.

        Args:
            name: Filename base for the screenshot.

        Returns:
            Path to the saved screenshot file.
        """
        screenshot_dir = Path("reports/screenshots")
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        path = screenshot_dir / f"{name}.png"
        self.page.screenshot(path=str(path), full_page=True)

        logger.info("Screenshot saved: %s", path)
        return str(path)

    def is_element_visible(self, selector: str, strategy: str = "css") -> bool:
        """
        Check if an element is visible without triggering healing.

        Args:
            selector: CSS or XPath selector.
            strategy: Locator strategy.

        Returns:
            True if the element is visible.
        """
        try:
            if strategy == "xpath":
                return self.page.locator(f"xpath={selector}").is_visible()
            return self.page.locator(selector).is_visible()
        except Exception:
            return False

    def wait_for_element(
        self,
        selector: str,
        strategy: str = "css",
        state: str = "visible",
        timeout_ms: int = 10000,
    ):
        """
        Wait for an element to reach a specific state.

        Args:
            selector: CSS or XPath selector.
            strategy: Locator strategy.
            state: Target state ("visible", "hidden", "attached", "detached").
            timeout_ms: Maximum wait time in milliseconds.
        """
        if strategy == "xpath":
            locator = self.page.locator(f"xpath={selector}")
        else:
            locator = self.page.locator(selector)

        locator.wait_for(state=state, timeout=timeout_ms)
