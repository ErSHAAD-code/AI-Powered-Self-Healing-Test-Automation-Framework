"""
Login Tests — UI Automation Test Suite for the Login Page

Demonstrates:
- Page Object Model (POM) with self-healing SmartElement
- Data-driven testing with pytest.mark.parametrize
- Smoke and regression test categorization
- Positive and negative test scenarios
"""

import pytest

from pages.login_page import LoginPage
from pages.dashboard_page import DashboardPage


class TestLogin:
    """Test suite for the login functionality."""

    @pytest.mark.smoke
    def test_valid_login(self, login_page: LoginPage, dashboard_page: DashboardPage):
        """
        Verify that a user can log in with valid credentials.

        Steps:
            1. Navigate to the login page
            2. Enter valid username and password
            3. Click the login button
            4. Verify the dashboard is displayed with correct username
        """
        login_page.login("admin", "admin123")

        assert dashboard_page.is_dashboard_visible(), \
            "Dashboard should be visible after successful login"
        assert dashboard_page.get_display_name() == "admin", \
            "Display name should match the logged-in user"

    @pytest.mark.smoke
    def test_invalid_login(self, login_page: LoginPage):
        """
        Verify that invalid credentials show an error message.

        Steps:
            1. Enter invalid credentials
            2. Click login
            3. Verify error message is displayed
        """
        login_page.login("invalid_user", "wrong_password")

        assert login_page.is_error_visible(), \
            "Error message should be visible after failed login"
        assert "Invalid" in login_page.get_error_message(), \
            "Error message should mention invalid credentials"

    @pytest.mark.regression
    def test_empty_username(self, login_page: LoginPage, dashboard_page: DashboardPage):
        """
        Verify login fails with empty username.

        The HTML5 required attribute should prevent form submission,
        so the dashboard should NOT appear.
        """
        login_page.enter_password("admin123")
        login_page.click_login()

        assert not dashboard_page.is_dashboard_visible(), \
            "Dashboard should not appear with empty username"

    @pytest.mark.regression
    def test_empty_password(self, login_page: LoginPage, dashboard_page: DashboardPage):
        """Verify login fails with empty password."""
        login_page.enter_username("admin")
        login_page.click_login()

        assert not dashboard_page.is_dashboard_visible(), \
            "Dashboard should not appear with empty password"

    @pytest.mark.regression
    @pytest.mark.parametrize("username,password", [
        ("admin", "admin123"),
        ("testuser", "password"),
        ("qe_engineer", "quality2024"),
    ])
    def test_data_driven_login(
        self,
        login_page: LoginPage,
        dashboard_page: DashboardPage,
        username: str,
        password: str,
    ):
        """
        Data-driven test: verify login works for all valid user accounts.

        Uses pytest parametrize for data-driven testing across multiple
        credential sets — a key automation framework feature.
        """
        login_page.login(username, password)

        assert dashboard_page.is_dashboard_visible(), \
            f"Dashboard should be visible for user '{username}'"
        assert dashboard_page.get_display_name() == username, \
            f"Display name should be '{username}'"

    @pytest.mark.smoke
    def test_login_page_title(self, login_page: LoginPage):
        """Verify the login page title is correct."""
        title = login_page.get_title()
        assert "Demo" in title, \
            f"Page title should contain 'Demo', got: '{title}'"

    @pytest.mark.regression
    def test_login_form_elements_visible(self, login_page: LoginPage):
        """Verify all login form elements are present and visible."""
        assert login_page.is_login_form_visible(), \
            "Login form should be visible"
        assert login_page.is_login_button_visible(), \
            "Login button should be visible"

    @pytest.mark.regression
    def test_login_page_app_title(self, login_page: LoginPage):
        """Verify the application title text on the login page."""
        title_text = login_page.get_title_text()
        assert "Automation Platform" in title_text, \
            f"App title should contain 'Automation Platform', got: '{title_text}'"
