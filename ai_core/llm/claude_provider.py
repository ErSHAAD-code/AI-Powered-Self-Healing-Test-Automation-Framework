"""
Claude LLM Provider — Primary AI Provider for the Framework

Implements the BaseLLMProvider interface using the Anthropic Claude API.
Claude serves as the primary LLM for all AI-augmented testing features:
- Self-healing locator generation
- Gherkin/BDD feature file generation
- Semantic API response validation
- ETL anomaly detection
- Flaky test root cause classification
- Failure summarization / RCA

Uses Claude's structured output capabilities to ensure reliable JSON responses
for programmatic consumption by the testing framework.
"""

import os
import logging
from typing import Optional

from ai_core.llm.base_provider import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class ClaudeProvider(BaseLLMProvider):
    """
    Anthropic Claude LLM provider.

    Primary provider for the AI-augmented testing framework. Uses the
    Anthropic Python SDK to communicate with Claude models.

    Configuration:
        - API key: ANTHROPIC_API_KEY environment variable
        - Model: Configurable, defaults to claude-sonnet-4-20250514
        - Temperature: Low (0.1) for deterministic, structured outputs
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 2048,
        temperature: float = 0.1,
        max_retries: int = 3,
        retry_delay_seconds: float = 2.0,
        request_timeout_seconds: float = 30.0,
    ):
        super().__init__(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            request_timeout_seconds=request_timeout_seconds,
        )
        self._api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._client = None

    def _get_client(self):
        """Lazy-initialize the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(
                    api_key=self._api_key,
                    timeout=self.request_timeout_seconds,
                )
            except ImportError:
                raise ImportError(
                    "The 'anthropic' package is required for ClaudeProvider. "
                    "Install it with: pip install anthropic"
                )
        return self._client

    def is_available(self) -> bool:
        """
        Check if Claude is available (API key is configured).

        Returns:
            True if ANTHROPIC_API_KEY is set and non-empty.
        """
        available = bool(self._api_key and self._api_key.startswith("sk-ant-"))
        if not available:
            logger.debug(
                "ClaudeProvider not available: ANTHROPIC_API_KEY not set or invalid format (must start with sk-ant-)"
            )
        return available

    def _send_request(
        self,
        prompt: str,
        system: str = "",
        response_format: Optional[dict] = None,
    ) -> LLMResponse:
        """
        Send a completion request to the Claude API.

        Args:
            prompt: User message content.
            system: System prompt for role/constraint definition.
            response_format: Optional JSON schema hint (included in system prompt).

        Returns:
            LLMResponse with parsed JSON content.
        """
        client = self._get_client()

        # Build system prompt with JSON schema hint if provided
        full_system = system or ""
        if response_format:
            schema_hint = (
                "\n\nYou MUST respond with valid JSON matching this schema. "
                "Do NOT include any text outside the JSON object.\n"
                f"Schema: {response_format}"
            )
            full_system += schema_hint

        try:
            # Build message parameters
            params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }

            if full_system:
                params["system"] = full_system

            response = client.messages.create(**params)

            # Extract text content from response
            raw_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    raw_text += block.text

            # Parse JSON from the response
            try:
                content = self._extract_json(raw_text)
            except ValueError as e:
                logger.warning("Failed to parse JSON from Claude response: %s", e)
                content = {"raw_response": raw_text}

            return LLMResponse(
                content=content,
                raw_text=raw_text,
                model=self.model,
                provider="claude",
                input_tokens=getattr(response.usage, "input_tokens", 0),
                output_tokens=getattr(response.usage, "output_tokens", 0),
                success=True,
            )

        except Exception as e:
            error_msg = f"Claude API error: {str(e)}"
            logger.error(error_msg)
            return LLMResponse(
                success=False,
                error=error_msg,
                provider="claude",
                model=self.model,
            )
