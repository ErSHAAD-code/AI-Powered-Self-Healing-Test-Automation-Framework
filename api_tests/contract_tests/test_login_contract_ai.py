"""
AI-Augmented API Contract Tests — Semantic Response Validation

Goes beyond JSON Schema validation: uses the LLM to check whether
API responses are semantically and business-logic correct.
"""

import pytest
from ai_core.api_contract_check.semantic_response_validator import SemanticResponseValidator


class TestLoginContractAI:
    """AI-augmented contract tests for the login API."""

    @pytest.fixture
    def validator(self):
        return SemanticResponseValidator()

    @pytest.mark.api
    @pytest.mark.ai
    def test_successful_login_semantic_validity(self, validator):
        """Verify successful login response is semantically correct."""
        response = {
            "success": True,
            "token": "mock-jwt-YWRtaW46MTcyNjMwMDAwMA==",
            "user": {
                "username": "admin",
                "role": "administrator",
                "last_login": "2024-09-14T12:00:00Z",
            },
        }

        result = validator.validate(
            endpoint="POST /api/login",
            response=response,
            expected_behavior="Successful login returns JWT token and user profile",
            status_code=200,
        )

        assert result.get("is_valid", True), \
            f"Semantic validation concerns: {result.get('concerns', [])}"

    @pytest.mark.api
    @pytest.mark.ai
    def test_failed_login_semantic_validity(self, validator):
        """Verify failed login response is semantically correct."""
        response = {
            "success": False,
            "error": "Invalid credentials",
            "message": "The username or password you entered is incorrect.",
        }

        result = validator.validate(
            endpoint="POST /api/login",
            response=response,
            expected_behavior="Failed login returns error message, no token",
            status_code=401,
        )

        assert result.get("is_valid", True), \
            f"Semantic validation concerns: {result.get('concerns', [])}"
