"""
Gemini LLM Provider — Fallback AI Provider for the Framework

Implements the BaseLLMProvider interface using the Google Gemini API.
Gemini serves as the fallback LLM when Claude is unavailable (API key
missing, rate-limited, or experiencing outages).

All AI features (healing, Gherkin generation, semantic validation, etc.)
transparently fall back to Gemini through the LLMProviderFactory without
any module-specific code changes.
"""

import os
import logging
from typing import Optional

from ai_core.llm.base_provider import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini LLM provider.

    Fallback provider for the AI-augmented testing framework. Uses the
    Google Generative AI Python SDK.

    Configuration:
        - API key: GOOGLE_API_KEY environment variable
        - Model: Configurable, defaults to gemini-2.0-flash
        - Temperature: Low (0.1) for deterministic outputs
    """

    def __init__(
        self,
        model: str = "gemini-3.6-flash",
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
        self._api_key = os.getenv("GOOGLE_API_KEY", "")
        self._model_instance = None

    def _get_model(self):
        """Lazy-initialize the Gemini generative model."""
        if self._model_instance is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self._api_key)
                self._model_instance = genai.GenerativeModel(
                    model_name=self.model,
                    generation_config=genai.GenerationConfig(
                        max_output_tokens=self.max_tokens,
                        temperature=self.temperature,
                    ),
                )
            except ImportError:
                raise ImportError(
                    "The 'google-generativeai' package is required for GeminiProvider. "
                    "Install it with: pip install google-generativeai"
                )
        return self._model_instance

    def is_available(self) -> bool:
        """
        Check if Gemini is available (API key is configured).

        Returns:
            True if GOOGLE_API_KEY is set and non-empty.
        """
        available = bool(self._api_key and not self._api_key.startswith("your_"))
        if not available:
            logger.debug(
                "GeminiProvider not available: GOOGLE_API_KEY not set or is placeholder"
            )
        return available

    def _send_request(
        self,
        prompt: str,
        system: str = "",
        response_format: Optional[dict] = None,
    ) -> LLMResponse:
        """
        Send a completion request to the Gemini API.

        Args:
            prompt: User message content.
            system: System instruction for role/constraint definition.
            response_format: Optional JSON schema hint (included in prompt).

        Returns:
            LLMResponse with parsed JSON content.
        """
        model = self._get_model()

        # Build the full prompt with system instruction and schema hint
        full_prompt_parts = []

        if system:
            full_prompt_parts.append(f"System Instructions:\n{system}\n")

        if response_format:
            full_prompt_parts.append(
                "You MUST respond with valid JSON matching this schema. "
                "Do NOT include any text outside the JSON object.\n"
                f"Schema: {response_format}\n"
            )

        full_prompt_parts.append(prompt)
        full_prompt = "\n".join(full_prompt_parts)

        try:
            response = model.generate_content(full_prompt)

            raw_text = response.text if response.text else ""

            # Parse JSON from the response
            try:
                content = self._extract_json(raw_text)
            except ValueError as e:
                logger.warning("Failed to parse JSON from Gemini response: %s", e)
                content = {"raw_response": raw_text}

            # Extract token counts if available
            input_tokens = 0
            output_tokens = 0
            if hasattr(response, "usage_metadata"):
                usage = response.usage_metadata
                input_tokens = getattr(usage, "prompt_token_count", 0)
                output_tokens = getattr(usage, "candidates_token_count", 0)

            return LLMResponse(
                content=content,
                raw_text=raw_text,
                model=self.model,
                provider="gemini",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                success=True,
            )

        except Exception as e:
            error_msg = f"Gemini API error: {str(e)}"
            logger.error(error_msg)
            return LLMResponse(
                success=False,
                error=error_msg,
                provider="gemini",
                model=self.model,
            )
