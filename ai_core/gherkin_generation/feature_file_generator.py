"""
Feature File Generator — AI-Powered Gherkin/BDD Generation

Converts plain-English feature descriptions into complete Gherkin
.feature files using the shared LLM provider abstraction. This bridges
the gap between business stakeholders (who describe requirements in
natural language) and the BDD test automation suite (which requires
structured Gherkin syntax).

Part of the Behavior-Driven Development (BDD) testing pillar.
Uses the shared ai_core/llm/provider_factory.py — no ad-hoc LLM calls.
"""

import logging
from pathlib import Path
from typing import Optional

from ai_core.llm.provider_factory import LLMProviderFactory

logger = logging.getLogger(__name__)

GHERKIN_SYSTEM_PROMPT = """You are a BDD expert. Convert the user's plain-English 
feature description into a complete, valid Gherkin .feature file.

RULES:
1. Use proper Gherkin syntax: Feature, Background, Scenario/Scenario Outline, 
   Given/When/Then/And/But
2. Include realistic, testable steps
3. Use Scenario Outline with Examples tables for data-driven scenarios
4. Add tags (@smoke, @regression, etc.) where appropriate
5. Keep scenarios focused and independent
6. Return ONLY valid JSON with the generated feature content

OUTPUT FORMAT:
{
  "feature_name": "Feature name",
  "feature_content": "Full Gherkin .feature file content as a string",
  "scenarios_count": <number>,
  "tags": ["list", "of", "tags", "used"]
}"""


class FeatureFileGenerator:
    """
    Generates Gherkin .feature files from plain-English descriptions.

    Usage:
        generator = FeatureFileGenerator()
        result = generator.generate(
            description="User login with valid and invalid credentials",
            context="Web application with username/password form"
        )
        # result.feature_content contains the complete .feature file
    """

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir or "bdd/features")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        description: str,
        context: str = "",
        save_to_file: Optional[str] = None,
    ) -> dict:
        """
        Generate a Gherkin feature file from a plain-English description.

        Args:
            description: What the feature should test (plain English).
            context: Additional context about the application.
            save_to_file: Optional filename to save the .feature file.

        Returns:
            Dict with feature_name, feature_content, scenarios_count, tags.
        """
        provider = LLMProviderFactory.get_provider()

        prompt = f"Generate a Gherkin .feature file for:\n\n"
        prompt += f"FEATURE DESCRIPTION:\n{description}\n\n"
        if context:
            prompt += f"APPLICATION CONTEXT:\n{context}\n\n"
        prompt += "Include at least 3 scenarios covering happy path, error cases, and edge cases."

        response = provider.complete(
            prompt=prompt,
            system=GHERKIN_SYSTEM_PROMPT,
        )

        if not response.success:
            logger.error("Feature generation failed: %s", response.error)
            return {"error": response.error}

        result = response.content

        # Save to file if requested
        if save_to_file and "feature_content" in result:
            output_path = self.output_dir / save_to_file
            with open(output_path, "w") as f:
                f.write(result["feature_content"])
            logger.info("Feature file saved: %s", output_path)
            result["saved_to"] = str(output_path)

        return result
