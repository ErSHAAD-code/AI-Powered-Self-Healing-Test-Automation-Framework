"""
Base LLM Provider — Abstract Interface for AI-Augmented Testing

Defines the contract that all LLM providers (Claude, Gemini, etc.) must
implement. This abstraction ensures that every AI feature in the framework
(locator healing, Gherkin generation, semantic API validation, ETL anomaly
detection, flaky test analysis, failure summarization) goes through a single,
consistent LLM interface.

Design Decisions:
- All providers return structured JSON (parsed dict), not raw text
- Built-in retry logic with exponential backoff
- Health-check method for failover support
- Token counting for cost tracking and context window management
"""

import json
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """
    Standardized response from any LLM provider.

    Attributes:
        content: Parsed JSON response from the LLM.
        raw_text: The raw text response before JSON parsing.
        model: Model identifier used for this request.
        provider: Provider name (e.g., "claude", "gemini").
        input_tokens: Number of input tokens consumed.
        output_tokens: Number of output tokens generated.
        latency_ms: Round-trip latency in milliseconds.
        success: Whether the request completed successfully.
        error: Error message if the request failed.
    """
    content: dict = field(default_factory=dict)
    raw_text: str = ""
    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    success: bool = True
    error: str = ""


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All AI-augmented features in the framework call LLM providers through
    this interface, ensuring consistent behavior, error handling, and
    fallback support across Claude, Gemini, and any future providers.
    """

    def __init__(
        self,
        model: str,
        max_tokens: int = 2048,
        temperature: float = 0.1,
        max_retries: int = 3,
        retry_delay_seconds: float = 2.0,
        request_timeout_seconds: float = 30.0,
    ):
        """
        Initialize the base provider.

        Args:
            model: Model identifier (e.g., "claude-sonnet-4-20250514").
            max_tokens: Maximum output tokens.
            temperature: Sampling temperature (low = deterministic).
            max_retries: Number of retry attempts on transient failures.
            retry_delay_seconds: Base delay between retries (exponential backoff).
            request_timeout_seconds: Timeout for individual API requests.
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.request_timeout_seconds = request_timeout_seconds

        self._provider_name = self.__class__.__name__.replace("Provider", "").lower()

    @property
    def provider_name(self) -> str:
        """Return the human-readable provider name."""
        return self._provider_name

    @abstractmethod
    def _send_request(
        self,
        prompt: str,
        system: str = "",
        response_format: Optional[dict] = None,
    ) -> LLMResponse:
        """
        Send a request to the LLM API (provider-specific implementation).

        Args:
            prompt: User prompt / message content.
            system: System prompt defining the LLM's role and constraints.
            response_format: Optional JSON schema hint for structured output.

        Returns:
            LLMResponse with parsed content or error details.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this provider is available and configured.

        Returns:
            True if the provider can accept requests, False otherwise.
        """
        ...

    def complete(
        self,
        prompt: str,
        system: str = "",
        response_format: Optional[dict] = None,
    ) -> LLMResponse:
        """
        Send a completion request with retry logic.

        This is the primary method all AI features should call. It handles:
        - Exponential backoff retries on transient failures
        - Latency measurement
        - Structured logging

        Args:
            prompt: User prompt.
            system: System prompt.
            response_format: Optional JSON schema for structured output.

        Returns:
            LLMResponse with the result or error information.
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                start_time = time.time()

                response = self._send_request(
                    prompt=prompt,
                    system=system,
                    response_format=response_format,
                )

                response.latency_ms = (time.time() - start_time) * 1000
                response.provider = self.provider_name
                response.model = self.model

                if response.success:
                    logger.info(
                        "LLM request succeeded: provider=%s, model=%s, "
                        "tokens_in=%d, tokens_out=%d, latency=%.0fms",
                        self.provider_name, self.model,
                        response.input_tokens, response.output_tokens,
                        response.latency_ms,
                    )
                    return response

                last_error = response.error
                logger.warning(
                    "LLM request failed (attempt %d/%d): %s",
                    attempt, self.max_retries, response.error,
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "LLM request exception (attempt %d/%d): %s",
                    attempt, self.max_retries, e,
                )

            # Exponential backoff
            if attempt < self.max_retries:
                delay = self.retry_delay_seconds * (2 ** (attempt - 1))
                logger.debug("Retrying in %.1f seconds...", delay)
                time.sleep(delay)

        # All retries exhausted
        logger.error(
            "LLM request failed after %d attempts: %s",
            self.max_retries, last_error,
        )
        return LLMResponse(
            success=False,
            error=f"All {self.max_retries} attempts failed. Last error: {last_error}",
            provider=self.provider_name,
            model=self.model,
        )

    @staticmethod
    def _extract_json(text: str) -> dict:
        """
        Extract JSON from LLM text output that may contain markdown fences.

        Handles common LLM output patterns:
        - Pure JSON
        - JSON wrapped in ```json ... ``` code fences
        - JSON embedded in surrounding text

        Args:
            text: Raw text from the LLM.

        Returns:
            Parsed dict from the JSON content.

        Raises:
            ValueError: If no valid JSON can be extracted.
        """
        text = text.strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code fences
        if "```" in text:
            # Find content between code fences
            parts = text.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:  # Odd indices are inside fences
                    # Remove language identifier (e.g., "json")
                    content = part.strip()
                    if content.startswith("json"):
                        content = content[4:].strip()
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        continue

        # Try to find JSON object in text
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not extract valid JSON from LLM response: {text[:200]}")
