"""
API Login Tests — REST API Contract and Functional Tests

Demonstrates the API Testing pillar (REST Assured equivalent in Python):
- JSON Schema contract validation
- Functional endpoint testing
- Status code verification
- Data-driven API testing with parametrize

Uses requests + jsonschema for the REST Assured pattern.
"""

import json
import pytest
from pathlib import Path

import jsonschema

# Since the demo app is client-side only, we test the mock API logic
# by simulating the login function directly. In a real project,
# these would be HTTP requests to a live API server.


# Load the JSON Schema
SCHEMA_DIR = Path(__file__).parent / "schemas"


def load_schema(name: str) -> dict:
    """Load a JSON Schema file."""
    with open(SCHEMA_DIR / name) as f:
        return json.load(f)


# Simulated API function (mirrors demo_app/index.html API_MOCK)
VALID_USERS = {
    "admin": "admin123",
    "testuser": "password",
    "qe_engineer": "quality2024",
}


def mock_login_api(username: str, password: str) -> tuple[int, dict]:
    """Simulate the login API endpoint."""
    if VALID_USERS.get(username) == password:
        import base64, datetime
        token = f"mock-jwt-{base64.b64encode(f'{username}:{datetime.datetime.now()}'.encode()).decode()}"
        return 200, {
            "success": True,
            "token": token,
            "user": {
                "username": username,
                "role": "administrator" if username == "admin" else "tester",
                "last_login": datetime.datetime.now().isoformat(),
            },
        }
    else:
        return 401, {
            "success": False,
            "error": "Invalid credentials",
            "message": "The username or password you entered is incorrect.",
        }


class TestLoginAPI:
    """API test suite for the login endpoint."""

    @pytest.mark.api
    @pytest.mark.smoke
    def test_successful_login_status_code(self):
        """Verify successful login returns 200."""
        status, _ = mock_login_api("admin", "admin123")
        assert status == 200

    @pytest.mark.api
    @pytest.mark.smoke
    def test_successful_login_schema(self):
        """Verify successful login response matches JSON Schema."""
        schema = load_schema("login_response.schema.json")
        _, response = mock_login_api("admin", "admin123")
        jsonschema.validate(instance=response, schema=schema)

    @pytest.mark.api
    def test_successful_login_has_token(self):
        """Verify successful login returns a token."""
        _, response = mock_login_api("admin", "admin123")
        assert response["success"] is True
        assert len(response["token"]) > 10
        assert response["user"]["username"] == "admin"

    @pytest.mark.api
    @pytest.mark.smoke
    def test_failed_login_status_code(self):
        """Verify failed login returns 401."""
        status, _ = mock_login_api("invalid", "wrong")
        assert status == 401

    @pytest.mark.api
    def test_failed_login_schema(self):
        """Verify failed login response matches JSON Schema."""
        schema = load_schema("login_response.schema.json")
        _, response = mock_login_api("invalid", "wrong")
        jsonschema.validate(instance=response, schema=schema)

    @pytest.mark.api
    def test_failed_login_error_message(self):
        """Verify failed login returns an error message."""
        _, response = mock_login_api("invalid", "wrong")
        assert response["success"] is False
        assert "Invalid" in response["error"]

    @pytest.mark.api
    @pytest.mark.regression
    @pytest.mark.parametrize("username,password,expected_role", [
        ("admin", "admin123", "administrator"),
        ("testuser", "password", "tester"),
        ("qe_engineer", "quality2024", "tester"),
    ])
    def test_user_roles(self, username, password, expected_role):
        """Data-driven API test: verify user roles."""
        _, response = mock_login_api(username, password)
        assert response["user"]["role"] == expected_role

    @pytest.mark.api
    def test_response_contains_last_login(self):
        """Verify successful login includes last_login timestamp."""
        _, response = mock_login_api("admin", "admin123")
        assert "last_login" in response["user"]
        assert len(response["user"]["last_login"]) > 0
