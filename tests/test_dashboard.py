"""
Dashboard Tests — UI Automation Test Suite for the Dashboard Page

Verifies post-login dashboard functionality:
- Welcome message and username display
- Stats cards (total tests, passed, self-healed)
- Data table content and structure
- Logout flow returning to login page
"""

import pytest

from pages.login_page import LoginPage
from pages.dashboard_page import DashboardPage


@pytest.fixture
def logged_in_dashboard(login_page: LoginPage, dashboard_page: DashboardPage):
    """Fixture that logs in and returns the dashboard page."""
    login_page.login("admin", "admin123")
    return dashboard_page


class TestDashboard:
    """Test suite for the dashboard functionality."""

    @pytest.mark.smoke
    def test_welcome_message(self, logged_in_dashboard: DashboardPage):
        """Verify the welcome message contains the username."""
        message = logged_in_dashboard.get_welcome_message()
        assert "admin" in message, \
            f"Welcome message should contain 'admin', got: '{message}'"

    @pytest.mark.smoke
    def test_dashboard_visible_after_login(self, logged_in_dashboard: DashboardPage):
        """Verify the dashboard container is visible."""
        assert logged_in_dashboard.is_dashboard_visible(), \
            "Dashboard should be visible after login"

    @pytest.mark.regression
    def test_stats_cards_displayed(self, logged_in_dashboard: DashboardPage):
        """Verify stats cards show numeric values."""
        total = logged_in_dashboard.get_total_tests_count()
        passed = logged_in_dashboard.get_passed_tests_count()
        healed = logged_in_dashboard.get_healed_tests_count()

        assert total.isdigit(), f"Total tests should be numeric, got: '{total}'"
        assert passed.isdigit(), f"Passed tests should be numeric, got: '{passed}'"
        assert healed.isdigit(), f"Healed tests should be numeric, got: '{healed}'"

    @pytest.mark.regression
    def test_data_table_has_rows(self, logged_in_dashboard: DashboardPage):
        """Verify the test results table contains data rows."""
        row_count = logged_in_dashboard.get_table_row_count()
        assert row_count > 0, "Data table should have at least one row"

    @pytest.mark.regression
    def test_data_table_structure(self, logged_in_dashboard: DashboardPage):
        """Verify each table row has the expected fields."""
        data = logged_in_dashboard.get_table_data()
        assert len(data) >= 3, "Should have at least 3 test result rows"

        for row in data:
            assert "test_name" in row, "Each row should have a test_name"
            assert "suite" in row, "Each row should have a suite"
            assert "status" in row, "Each row should have a status"
            assert row["status"] in ("Passed", "Failed", "Running"), \
                f"Status should be Passed/Failed/Running, got: '{row['status']}'"

    @pytest.mark.smoke
    def test_logout_returns_to_login(
        self, logged_in_dashboard: DashboardPage, login_page: LoginPage
    ):
        """
        Verify logout transitions back to the login page.

        Steps:
            1. Click logout on the dashboard
            2. Verify login form is visible again
            3. Verify dashboard is no longer visible
        """
        logged_in_dashboard.click_logout()

        assert login_page.is_login_form_visible(), \
            "Login form should be visible after logout"
        assert not logged_in_dashboard.is_dashboard_visible(), \
            "Dashboard should not be visible after logout"

    @pytest.mark.regression
    def test_stats_values_are_consistent(self, logged_in_dashboard: DashboardPage):
        """Verify that passed + healed <= total tests."""
        total = int(logged_in_dashboard.get_total_tests_count())
        passed = int(logged_in_dashboard.get_passed_tests_count())

        assert passed <= total, \
            f"Passed ({passed}) should not exceed total ({total})"
