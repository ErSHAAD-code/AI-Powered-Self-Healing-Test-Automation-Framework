"""
Synthetic Data Generator — AI-Powered Test Data Generation

Generates realistic, context-aware test data using the shared LLM provider.
Produces structured datasets (user profiles, transactions, etc.) that
respect business rules and constraints, enabling comprehensive data-driven
testing without relying on production data.
"""

import json
import logging
from typing import Optional

from ai_core.llm.provider_factory import LLMProviderFactory

logger = logging.getLogger(__name__)

DATA_GEN_SYSTEM_PROMPT = """You are a test data engineer. Generate realistic synthetic 
test data based on the schema and constraints provided.

RULES:
1. Data must be realistic but not contain real PII
2. Respect all constraints (types, ranges, enums, relationships)
3. Include edge cases: empty strings, boundary values, special characters
4. Return valid JSON array

OUTPUT FORMAT:
{
  "data": [<array of generated records>],
  "record_count": <number>,
  "edge_cases_included": ["description of each edge case"]
}"""


class SyntheticDataGenerator:
    """Generates synthetic test data using LLM analysis of schemas."""

    def generate(
        self,
        schema: dict,
        count: int = 10,
        constraints: str = "",
    ) -> dict:
        """
        Generate synthetic test data matching a schema.

        Args:
            schema: JSON schema or field descriptions.
            count: Number of records to generate.
            constraints: Business rules and constraints.

        Returns:
            Dict with data array, record_count, edge_cases_included.
        """
        provider = LLMProviderFactory.get_provider()

        prompt = (
            f"Generate {count} synthetic test records:\n\n"
            f"SCHEMA:\n{json.dumps(schema, indent=2)}\n\n"
        )
        if constraints:
            prompt += f"CONSTRAINTS:\n{constraints}\n\n"

        prompt += "Include at least 2 edge case records."

        response = provider.complete(
            prompt=prompt,
            system=DATA_GEN_SYSTEM_PROMPT,
        )

        if not response.success:
            return {"data": [], "record_count": 0, "error": response.error}

        return response.content
