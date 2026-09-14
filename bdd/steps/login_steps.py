"""
Login BDD Step Definitions — pytest-bdd Steps for Login Feature

Maps Gherkin steps from login.feature to Page Object Model interactions.
Demonstrates the BDD testing pillar with Given/When/Then step definitions
wired to the self-healing SmartElement infrastructure.
"""

import pytest
from pytest_bdd import scenarios, given, when, then, parsers

from pages.login_page import LoginPage
from pages.dashboard_page import DashboardPage

# Load all scenarios from the feature file
scenarios("login.feature")


# =============================================================================
# Given Steps
# =============================================================================

@given("the user is on the login page")
def user_on_login_page(login_page: LoginPage):
    """Verify the login page is displayed."""
    assert login_page.is_login_form_visible(), "Login form should be visible"


# =============================================================================
# When Steps
# =============================================================================

@when(parsers.parse('the user enters username "{username}"'))
def enter_username(login_page: LoginPage, username: str):
    """Enter a username into the login form."""
    login_page.enter_username(username)


@when(parsers.parse('the user enters password "{password}"'))
def enter_password(login_page: LoginPage, password: str):
    """Enter a password into the login form."""
    login_page.enter_password(password)


@when("the user clicks the login button")
def click_login(login_page: LoginPage):
    """Click the login button."""
    login_page.click_login()


@when("the user clicks the logout button")
def click_logout(dashboard_page: DashboardPage):
    """Click the logout button on the dashboard."""
    dashboard_page.click_logout()


# =============================================================================
# Then Steps
# =============================================================================

@then("the dashboard should be visible")
def dashboard_visible(dashboard_page: DashboardPage):
    """Verify the dashboard is displayed."""
    assert dashboard_page.is_dashboard_visible(), \
        "Dashboard should be visible after login"


@then("the dashboard should not be visible")
def dashboard_not_visible(dashboard_page: DashboardPage):
    """Verify the dashboard is NOT displayed."""
    assert not dashboard_page.is_dashboard_visible(), \
        "Dashboard should not be visible"


@then(parsers.parse('the welcome message should contain "{text}"'))
def welcome_contains(dashboard_page: DashboardPage, text: str):
    """Verify the welcome message contains expected text."""
    message = dashboard_page.get_welcome_message()
    assert text in message, \
        f"Welcome message should contain '{text}', got: '{message}'"


@then(parsers.parse('the displayed username should be "{username}"'))
def display_name_matches(dashboard_page: DashboardPage, username: str):
    """Verify the displayed username matches."""
    name = dashboard_page.get_display_name()
    assert name == username, \
        f"Display name should be '{username}', got: '{name}'"


@then("the error message should be visible")
def error_visible(login_page: LoginPage):
    """Verify the error message is displayed."""
    assert login_page.is_error_visible(), \
        "Error message should be visible after failed login"


@then(parsers.parse('the error message should contain "{text}"'))
def error_contains(login_page: LoginPage, text: str):
    """Verify the error message contains expected text."""
    message = login_page.get_error_message()
    assert text in message, \
        f"Error message should contain '{text}', got: '{message}'"


@then("the login form should be visible")
def login_form_visible(login_page: LoginPage):
    """Verify the login form is displayed."""
    assert login_page.is_login_form_visible(), \
        "Login form should be visible"
