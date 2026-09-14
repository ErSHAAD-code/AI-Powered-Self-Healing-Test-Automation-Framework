"""
Login Page — Page Object for the Demo Application Login Form

Implements the Page Object Model (POM) pattern for the login page,
using SmartElement wrappers for all element interactions. This means
every locator on this page is self-healing-capable.

Demonstrates data-driven testing support through parameterized
login methods that accept different credential sets.
"""

import logging

from playwright.sync_api import Page

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class LoginPage(BasePage):
    """
    Page Object for the demo application login form.

    Locators are defined as class-level selectors and wrapped with
    SmartElement via smart_find() at interaction time, enabling
    automatic self-healing if the DOM changes.

    Supported test scenarios:
    - Valid login with different user roles
    - Invalid credentials error handling
    - Empty field validation
    - UI element verification
    """

    # === Locator Definitions (CSS selectors) ===
    _TITLE = "#app-title"
    _USERNAME_INPUT = "#username"
    _PASSWORD_INPUT = "#password"
    _LOGIN_BUTTON = "#login-button"
    _ERROR_MESSAGE = "#error-message"
    _LOGIN_FORM = "#login-form"
    _LOGIN_CONTAINER = "#login-container"

    def __init__(self, page: Page, base_url: str = ""):
        """
        Initialize the LoginPage.

        Args:
            page: Playwright Page instance.
            base_url: Base URL for the demo application.
        """
        super().__init__(page, base_url)
        logger.debug("LoginPage initialized")

    def navigate_to_login(self):
        """Navigate to the login page."""
        self.navigate("/")
        logger.info("Navigated to login page")

    def enter_username(self, username: str):
        """
        Enter a username into the username field.

        Args:
            username: The username to enter.
        """
        self.smart_find(
            self._USERNAME_INPUT,
            intent="Username input field on the login form",
        ).fill(username)
        logger.debug("Entered username: %s", username)

    def enter_password(self, password: str):
        """
        Enter a password into the password field.

        Args:
            password: The password to enter.
        """
        self.smart_find(
            self._PASSWORD_INPUT,
            intent="Password input field on the login form",
        ).fill(password)
        logger.debug("Entered password: ***")

    def click_login(self):
        """Click the login/submit button."""
        self.smart_find(
            self._LOGIN_BUTTON,
            intent="Login submit button on the login form",
        ).click()
        logger.info("Clicked login button")

    def login(self, username: str, password: str):
        """
        Perform a complete login flow.

        Data-driven testing: accepts any credential pair, enabling
        parameterized test execution with different user roles.

        Args:
            username: Login username.
            password: Login password.
        """
        self.enter_username(username)
        self.enter_password(password)
        self.click_login()
        logger.info("Login attempt completed for user: %s", username)

    def get_error_message(self) -> str:
        """
        Get the error message text (if displayed).

        Returns:
            Error message text, or empty string if not visible.
        """
        try:
            element = self.smart_find(
                self._ERROR_MESSAGE,
                intent="Error message displayed after failed login",
            )
            text = element.text_content()
            return text.strip() if text else ""
        except Exception:
            return ""

    def is_error_visible(self) -> bool:
        """Check if the error message is currently visible."""
        try:
            # Check if the error message has the 'visible' class
            locator = self.page.locator(self._ERROR_MESSAGE)
            classes = locator.get_attribute("class") or ""
            return "visible" in classes
        except Exception:
            return False

    def get_title_text(self) -> str:
        """Get the application title text."""
        return (
            self.smart_find(
                self._TITLE,
                intent="Application title heading on the login page",
            ).text_content()
            or ""
        ).strip()

    def is_login_form_visible(self) -> bool:
        """Check if the login form is displayed."""
        return self.is_element_visible(self._LOGIN_CONTAINER)

    def is_login_button_visible(self) -> bool:
        """Check if the login button is visible."""
        return self.is_element_visible(self._LOGIN_BUTTON)
