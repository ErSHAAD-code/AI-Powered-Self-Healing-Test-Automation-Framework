"""
LLM Provider Factory — Unified Entry Point for All AI Features

Implements the Factory + Singleton pattern to ensure every AI-augmented
module in the framework (locator healing, Gherkin generation, semantic
API validation, ETL anomaly detection, flaky test analysis, failure
summarization) accesses LLM capabilities through a single, consistent
entry point.

Key behaviors:
- Reads primary/fallback provider configuration from config.yaml
- Returns the primary provider if available, falls back to the secondary
- Provides a MockProvider for testing when no API keys are configured
- Thread-safe singleton: one factory instance across the entire test run
"""

import os
import logging
import threading
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

from ai_core.llm.base_provider import BaseLLMProvider, LLMResponse
from ai_core.llm.claude_provider import ClaudeProvider
from ai_core.llm.gemini_provider import GeminiProvider

load_dotenv()

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "config.yaml"


class MockLLMProvider(BaseLLMProvider):
    """
    Mock LLM provider for testing and demo purposes.

    Returns pre-defined responses that simulate realistic LLM output
    for self-healing locator suggestions. Used when no real API keys
    are configured, allowing the framework to demonstrate its
    architecture end-to-end without incurring API costs.
    """

    def __init__(self, **kwargs):
        super().__init__(model="mock-v1", **kwargs)

    def is_available(self) -> bool:
        return True

    def _send_request(
        self,
        prompt: str,
        system: str = "",
        response_format: Optional[dict] = None,
    ) -> LLMResponse:
        """Return a mock response based on prompt content analysis."""
        logger.info("MockLLMProvider: generating mock response")

        # Adjust mock response based on prompt content
        prompt_lower = prompt.lower()

        if "#password" in prompt_lower or "'password'" in prompt_lower or "password input" in prompt_lower:
            mock_content = {
                "candidates": [
                    {
                        "selector": "#user-password-input",
                        "strategy": "css",
                        "confidence": 0.95,
                        "reasoning": "Mock: Found password input field after mutation."
                    },
                    {
                        "selector": "input[type='password']",
                        "strategy": "css",
                        "confidence": 0.88,
                        "reasoning": "Mock: Fallback password input field."
                    }
                ]
            }
        elif "#login-button" in prompt_lower or "'login-button'" in prompt_lower or "login submit button" in prompt_lower:
            mock_content = {
                "candidates": [
                    {
                        "selector": "#btn-signin-primary",
                        "strategy": "css",
                        "confidence": 0.95,
                        "reasoning": "Mock: Found mutated signin button ID."
                    },
                    {
                        "selector": "button[type='submit']",
                        "strategy": "css",
                        "confidence": 0.90,
                        "reasoning": "Mock: Fallback to generic submit button selector."
                    }
                ]
            }
        elif "#username" in prompt_lower or "'username'" in prompt_lower or "username input" in prompt_lower:
            mock_content = {
                "candidates": [
                    {
                        "selector": "#user-email-input",
                        "strategy": "css",
                        "confidence": 0.95,
                        "reasoning": "Mock: Found input field with email/username id after mutation."
                    },
                    {
                        "selector": "input[type='text']",
                        "strategy": "css",
                        "confidence": 0.88,
                        "reasoning": "Mock: Fallback text input field."
                    }
                ]
            }
        else:
            # Default mock response for locator healing
            mock_content = {
                "candidates": [
                    {
                        "selector": "button[type='submit']",
                        "strategy": "css",
                        "confidence": 0.85,
                        "reasoning": "Mock: Fallback generic element selector."
                    }
                ]
            }

        if "gherkin" in prompt_lower or "feature" in prompt_lower:
            mock_content = {
                "feature": "Feature: Login Functionality\n"
                           "  Scenario: Successful login\n"
                           "    Given the user is on the login page\n"
                           "    When the user enters valid credentials\n"
                           "    Then the user should see the dashboard",
                "scenarios_count": 1,
            }
        elif "semantic" in prompt_lower or "api" in prompt_lower:
            mock_content = {
                "is_valid": True,
                "confidence": 0.88,
                "reasoning": "Mock: API response structure and values appear "
                             "semantically correct for a login endpoint.",
                "concerns": [],
            }
        elif "anomaly" in prompt_lower or "etl" in prompt_lower:
            mock_content = {
                "anomalies_detected": False,
                "confidence": 0.90,
                "summary": "Mock: No significant data anomalies detected in "
                           "the source-to-target reconciliation.",
                "anomalies": [],
            }
        elif "flaky" in prompt_lower:
            mock_content = {
                "classification": "timing",
                "confidence": 0.75,
                "reasoning": "Mock: Test failure pattern suggests a race condition "
                             "or timing-dependent assertion.",
                "recommendation": "Add explicit waits before the assertion.",
            }
        elif "failure" in prompt_lower or "root cause" in prompt_lower:
            mock_content = {
                "root_cause": "Mock: Element not found due to dynamic ID change "
                              "after recent UI refactoring.",
                "confidence": 0.80,
                "suggested_fix": "Update the locator to use a more stable "
                                 "attribute like data-testid.",
            }

        import json
        raw_text = json.dumps(mock_content, indent=2)

        return LLMResponse(
            content=mock_content,
            raw_text=raw_text,
            model="mock-v1",
            provider="mock",
            input_tokens=len(prompt.split()),
            output_tokens=len(raw_text.split()),
            success=True,
        )


class LLMProviderFactory:
    """
    Singleton factory for creating and managing LLM provider instances.

    Ensures all AI-augmented modules share a single provider configuration
    and avoids creating multiple client instances. Supports automatic
    failover from primary (Claude) to fallback (Gemini) provider.

    Usage:
        provider = LLMProviderFactory.get_provider()
        response = provider.complete(
            prompt="Analyze this broken locator...",
            system="You are a test automation expert...",
        )
    """

    _instance: Optional["LLMProviderFactory"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._primary: Optional[BaseLLMProvider] = None
        self._fallback: Optional[BaseLLMProvider] = None
        self._mock = MockLLMProvider()
        self._config = self._load_config()
        self._initialize_providers()

    @classmethod
    def get_instance(cls) -> "LLMProviderFactory":
        """Get or create the singleton factory instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton (useful for testing)."""
        with cls._lock:
            cls._instance = None

    @staticmethod
    def _load_config() -> dict:
        """Load LLM configuration from config.yaml."""
        try:
            with open(_CONFIG_PATH, "r") as f:
                config = yaml.safe_load(f)
            return config.get("llm", {})
        except FileNotFoundError:
            logger.warning("Config file not found at %s, using defaults", _CONFIG_PATH)
            return {}

    def _initialize_providers(self):
        """Create provider instances based on configuration."""
        llm_config = self._config

        # Claude configuration
        claude_config = llm_config.get("claude", {})
        self._primary = ClaudeProvider(
            model=os.getenv("CLAUDE_MODEL", claude_config.get("model", "claude-sonnet-4-20250514")),
            max_tokens=claude_config.get("max_tokens", 2048),
            temperature=claude_config.get("temperature", 0.1),
            max_retries=llm_config.get("max_retries", 3),
            retry_delay_seconds=llm_config.get("retry_delay_seconds", 2),
            request_timeout_seconds=llm_config.get("request_timeout_seconds", 30),
        )

        # Gemini configuration
        gemini_config = llm_config.get("gemini", {})
        self._fallback = GeminiProvider(
            model=os.getenv("GEMINI_MODEL", gemini_config.get("model", "gemini-2.0-flash")),
            max_tokens=gemini_config.get("max_tokens", 2048),
            temperature=gemini_config.get("temperature", 0.1),
            max_retries=llm_config.get("max_retries", 3),
            retry_delay_seconds=llm_config.get("retry_delay_seconds", 2),
            request_timeout_seconds=llm_config.get("request_timeout_seconds", 30),
        )

        # Determine configured order
        primary_name = os.getenv(
            "LLM_PRIMARY_PROVIDER",
            llm_config.get("primary_provider", "claude")
        ).lower()

        if primary_name == "gemini":
            # Swap primary and fallback
            self._primary, self._fallback = self._fallback, self._primary

        logger.info(
            "LLM providers initialized: primary=%s, fallback=%s",
            self._primary.provider_name,
            self._fallback.provider_name,
        )

    @classmethod
    def get_provider(cls) -> BaseLLMProvider:
        """
        Get the best available LLM provider.

        Returns providers in priority order:
        1. Primary provider (Claude by default) if API key is configured
        2. Fallback provider (Gemini by default) if primary is unavailable
        3. MockProvider if no API keys are configured (demo/testing mode)

        Returns:
            An initialized BaseLLMProvider instance.
        """
        factory = cls.get_instance()

        if factory._primary and factory._primary.is_available():
            logger.debug("Using primary provider: %s", factory._primary.provider_name)
            return factory._primary

        if factory._fallback and factory._fallback.is_available():
            logger.info(
                "Primary provider unavailable, falling back to: %s",
                factory._fallback.provider_name,
            )
            return factory._fallback

        logger.warning(
            "No LLM API keys configured. Using MockProvider for demo/testing. "
            "Set ANTHROPIC_API_KEY or GOOGLE_API_KEY in .env for real AI features."
        )
        return factory._mock
