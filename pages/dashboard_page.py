"""
Dashboard Page — Page Object for the Demo Application Dashboard

Implements the Page Object Model (POM) for the post-login dashboard,
covering navigation bar, welcome banner, stats cards, data table,
and logout functionality. All interactions use SmartElement for
self-healing support.
"""

import logging
from typing import Optional

from playwright.sync_api import Page

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class DashboardPage(BasePage):
    """
    Page Object for the demo application dashboard (post-login view).

    Covers:
    - Welcome banner with username display
    - Stats cards (total tests, passed, self-healed)
    - Test results data table
    - Navigation bar with logout
    """

    # === Locator Definitions ===
    _DASHBOARD_CONTAINER = "#dashboard-container"
    _WELCOME_MESSAGE = "#welcome-message"
    _USER_DISPLAY_NAME = "#user-display-name"
    _LOGOUT_BUTTON = "#logout-button"
    _NAV_DASHBOARD = "#nav-dashboard"
    _NAV_TESTS = "#nav-tests"
    _NAV_REPORTS = "#nav-reports"

    # Stats cards
    _TOTAL_TESTS = "#total-tests"
    _PASSED_TESTS = "#passed-tests"
    _HEALED_TESTS = "#healed-tests"

    # Data table
    _TEST_RESULTS_TABLE = "#test-results-table"
    _TEST_RESULTS_BODY = "#test-results-body"

    def __init__(self, page: Page, base_url: str = ""):
        super().__init__(page, base_url)
        logger.debug("DashboardPage initialized")

    def is_dashboard_visible(self) -> bool:
        """Check if the dashboard is currently displayed."""
        try:
            locator = self.page.locator(self._DASHBOARD_CONTAINER)
            classes = locator.get_attribute("class") or ""
            return "active" in classes
        except Exception:
            return False

    def get_welcome_message(self) -> str:
        """
        Get the welcome message text.

        Returns:
            Welcome message string (e.g., "Welcome back, admin!").
        """
        return (
            self.smart_find(
                self._WELCOME_MESSAGE,
                intent="Welcome message banner showing the logged-in username",
            ).text_content()
            or ""
        ).strip()

    def get_display_name(self) -> str:
        """
        Get the displayed username.

        Returns:
            Username shown in the welcome banner.
        """
        return (
            self.smart_find(
                self._USER_DISPLAY_NAME,
                intent="Username display in the welcome banner",
            ).text_content()
            or ""
        ).strip()

    def get_total_tests_count(self) -> str:
        """Get the total tests stat value."""
        return (
            self.smart_find(
                self._TOTAL_TESTS,
                intent="Total tests count in the stats card",
            ).text_content()
            or ""
        ).strip()

    def get_passed_tests_count(self) -> str:
        """Get the passed tests stat value."""
        return (
            self.smart_find(
                self._PASSED_TESTS,
                intent="Passed tests count in the stats card",
            ).text_content()
            or ""
        ).strip()

    def get_healed_tests_count(self) -> str:
        """Get the self-healed tests stat value."""
        return (
            self.smart_find(
                self._HEALED_TESTS,
                intent="Self-healed tests count in the stats card",
            ).text_content()
            or ""
        ).strip()

    def get_table_row_count(self) -> int:
        """
        Get the number of rows in the test results table.

        Returns:
            Number of data rows (excluding header).
        """
        rows = self.page.locator(f"{self._TEST_RESULTS_BODY} tr")
        return rows.count()

    def get_table_data(self) -> list[dict]:
        """
        Extract all data from the test results table.

        Returns:
            List of dicts with keys: test_name, suite, duration, status.
        """
        rows = self.page.locator(f"{self._TEST_RESULTS_BODY} tr")
        data = []

        for i in range(rows.count()):
            row = rows.nth(i)
            cells = row.locator("td")

            if cells.count() >= 4:
                data.append({
                    "test_name": (cells.nth(0).text_content() or "").strip(),
                    "suite": (cells.nth(1).text_content() or "").strip(),
                    "duration": (cells.nth(2).text_content() or "").strip(),
                    "status": (cells.nth(3).text_content() or "").strip(),
                })

        return data

    def click_logout(self):
        """Click the logout button."""
        self.smart_find(
            self._LOGOUT_BUTTON,
            intent="Logout button in the navigation bar",
        ).click()
        logger.info("Clicked logout button")

    def click_nav_dashboard(self):
        """Click the Dashboard nav link."""
        self.smart_find(self._NAV_DASHBOARD, intent="Dashboard nav link").click()

    def click_nav_tests(self):
        """Click the Tests nav link."""
        self.smart_find(self._NAV_TESTS, intent="Tests nav link").click()

    def click_nav_reports(self):
        """Click the Reports nav link."""
        self.smart_find(self._NAV_REPORTS, intent="Reports nav link").click()
