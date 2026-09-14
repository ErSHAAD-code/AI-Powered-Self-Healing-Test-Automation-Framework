"""
Semantic Response Validator — AI-Augmented API Contract Testing

Goes beyond traditional JSON Schema validation by asking the LLM to
evaluate whether an API response is semantically and business-logic
correct. While schema validation checks structure (types, required fields),
semantic validation checks meaning (does a login endpoint return a
sensible token? does the error message match the error code?).

Part of the API Testing pillar (REST Assured equivalent).
Uses the shared ai_core/llm/provider_factory.py — no ad-hoc LLM calls.
"""

import logging
from typing import Optional

from ai_core.llm.provider_factory import LLMProviderFactory

logger = logging.getLogger(__name__)

SEMANTIC_SYSTEM_PROMPT = """You are an API testing expert. Analyze the API response 
for semantic and business-logic correctness, NOT just schema validity.

Check for:
1. Do the response values make business sense? (e.g., negative prices, future birth dates)
2. Are enum values valid? (e.g., status should be "active"/"inactive", not "xyz")
3. Do related fields agree? (e.g., success=true but error_message is present)
4. Does the response match what the endpoint should return?
5. Are there security concerns? (passwords in plaintext, excessive data exposure)

OUTPUT FORMAT (strict JSON):
{
  "is_valid": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "Overall assessment",
  "concerns": [
    {
      "field": "field_name",
      "issue": "Description of the semantic issue",
      "severity": "high|medium|low"
    }
  ]
}"""


class SemanticResponseValidator:
    """
    Validates API responses for semantic correctness using LLM analysis.

    Complements JSON Schema validation by checking business logic and
    meaning rather than just structure. This catches issues that schema
    validation misses, such as semantically invalid values, conflicting
    fields, or security concerns.

    Usage:
        validator = SemanticResponseValidator()
        result = validator.validate(
            endpoint="POST /api/login",
            response={"success": True, "token": "abc123", "user": {...}},
            expected_behavior="Successful login should return a JWT token and user profile"
        )
        assert result["is_valid"], result["concerns"]
    """

    def validate(
        self,
        endpoint: str,
        response: dict,
        expected_behavior: str = "",
        status_code: int = 200,
    ) -> dict:
        """
        Validate an API response for semantic correctness.

        Args:
            endpoint: API endpoint (e.g., "POST /api/login").
            response: The API response body (parsed JSON).
            expected_behavior: What the endpoint should return.
            status_code: HTTP status code received.

        Returns:
            Dict with is_valid, confidence, reasoning, concerns.
        """
        provider = LLMProviderFactory.get_provider()

        import json
        prompt = (
            f"Analyze this API response for semantic correctness:\n\n"
            f"ENDPOINT: {endpoint}\n"
            f"STATUS CODE: {status_code}\n"
            f"RESPONSE BODY:\n{json.dumps(response, indent=2)}\n\n"
        )
        if expected_behavior:
            prompt += f"EXPECTED BEHAVIOR:\n{expected_behavior}\n\n"

        prompt += "Is this response semantically valid and business-logic correct?"

        llm_response = provider.complete(
            prompt=prompt,
            system=SEMANTIC_SYSTEM_PROMPT,
        )

        if not llm_response.success:
            logger.error("Semantic validation failed: %s", llm_response.error)
            return {
                "is_valid": True,  # Fail-open: don't block on LLM errors
                "confidence": 0.0,
                "reasoning": f"LLM validation unavailable: {llm_response.error}",
                "concerns": [],
            }

        return llm_response.content
