"""
Healing Engine — Self-Healing Locator Orchestrator

The central orchestrator for the AI-powered self-healing pipeline. When a
test locator breaks (NoSuchElement, Timeout), this engine coordinates:

1. DOM Context Extraction — trim the live page HTML for LLM input
2. LLM Prompt Construction — build a structured prompt with broken locator,
   DOM context, and element intent description
3. LLM Invocation — via the shared LLMProviderFactory (Claude / Gemini / Mock)
4. Candidate Validation — verify each LLM suggestion against the live page
5. Confidence Gate — apply threshold-based healing decision
6. Repository Persistence — cache the result for future runs

This is the core self-healing pipeline that differentiates the framework
from traditional Selenium/Playwright test suites.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from playwright.sync_api import Page

from ai_core.llm.provider_factory import LLMProviderFactory
from ai_core.locator_healing.dom_context_extractor import DOMContextExtractor
from ai_core.locator_healing.candidate_validator import (
    CandidateValidator, ValidatedCandidate,
)
from ai_core.locator_healing.confidence_gate import (
    ConfidenceGate, HealingDecision, GateResult,
)
from ai_core.locator_healing.locator_repository import LocatorRepository

logger = logging.getLogger(__name__)


@dataclass
class HealingResult:
    """
    Complete result of a healing attempt.

    Attributes:
        success: Whether the healing produced a usable replacement.
        decision: The confidence gate decision (AUTO_HEAL, SUGGEST, REJECT).
        healed_selector: The replacement selector (if successful).
        healed_strategy: The strategy for the replacement selector.
        confidence: Final validated confidence score.
        reasoning: LLM reasoning for the suggestion.
        original_selector: The selector that broke.
        original_strategy: Strategy of the broken selector.
        candidates: All validated candidates from the LLM.
        gate_result: Full confidence gate evaluation result.
        llm_provider: Which LLM provider was used.
        llm_model: Which model was used.
        llm_latency_ms: API call latency.
        cached: Whether this result came from the repository cache.
        error: Error message if the healing pipeline itself failed.
    """
    success: bool = False
    decision: Optional[HealingDecision] = None
    healed_selector: str = ""
    healed_strategy: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    original_selector: str = ""
    original_strategy: str = ""
    candidates: list = field(default_factory=list)
    gate_result: Optional[GateResult] = None
    llm_provider: str = ""
    llm_model: str = ""
    llm_latency_ms: float = 0.0
    cached: bool = False
    error: str = ""


# System prompt for the LLM — defines its role and output format
HEALING_SYSTEM_PROMPT = """You are an expert test automation engineer specializing in 
Playwright and Selenium locator strategies. Your task is to analyze a broken UI locator 
and suggest replacement selectors based on the current DOM structure.

RULES:
1. Analyze the broken selector and understand what element it was trying to target.
2. Study the provided DOM fragment to find the element.
3. Return ONLY valid JSON with your suggestions.
4. Prefer stable selectors: data-testid > id > aria-label > role > css class > xpath.
5. Each candidate must include a confidence score (0.0-1.0) reflecting how certain 
   you are that the selector correctly targets the intended element.
6. Provide reasoning for each suggestion.

OUTPUT FORMAT (strict JSON, no markdown):
{
  "candidates": [
    {
      "selector": "<css-or-xpath-selector>",
      "strategy": "css|xpath|text|role",
      "confidence": 0.0-1.0,
      "reasoning": "<why this selector targets the right element>"
    }
  ]
}"""


class HealingEngine:
    """
    Orchestrates the self-healing locator pipeline.

    Flow:
        broken_locator + page -> [cache check] -> [DOM extraction]
        -> [LLM call] -> [candidate validation] -> [confidence gate]
        -> [persist] -> HealingResult

    Usage:
        engine = HealingEngine()
        result = engine.heal(
            page=playwright_page,
            broken_selector="#old-login-btn",
            strategy="css",
            element_intent="The submit button on the login form",
            test_name="test_login_valid_credentials",
        )
        if result.success:
            page.locator(result.healed_selector).click()
    """

    def __init__(
        self,
        dom_extractor: Optional[DOMContextExtractor] = None,
        confidence_gate: Optional[ConfidenceGate] = None,
        repository: Optional[LocatorRepository] = None,
    ):
        """
        Initialize the healing engine.

        All dependencies are optional and default to production instances.
        Pass custom instances for testing.

        Args:
            dom_extractor: Custom DOMContextExtractor (default: auto-configured).
            confidence_gate: Custom ConfidenceGate (default: auto-configured).
            repository: Custom LocatorRepository (default: auto-configured).
        """
        self.dom_extractor = dom_extractor or DOMContextExtractor()
        self.confidence_gate = confidence_gate or ConfidenceGate()
        self.repository = repository or LocatorRepository()

    def heal(
        self,
        page: Page,
        broken_selector: str,
        strategy: str = "css",
        element_intent: str = "",
        test_name: Optional[str] = None,
    ) -> HealingResult:
        """
        Attempt to heal a broken locator.

        This is the main entry point for the self-healing pipeline.

        Args:
            page: Playwright Page with the live DOM.
            broken_selector: The CSS/XPath selector that failed.
            strategy: Locator strategy ("css", "xpath", "text", "role").
            element_intent: Human-readable description of what the element
                          should be (e.g., "login submit button").
            test_name: Name of the test that triggered healing.

        Returns:
            HealingResult with the outcome.
        """
        page_url = page.url

        logger.info(
            "=== HEALING PIPELINE START ===\n"
            "  Broken selector: '%s' (strategy: %s)\n"
            "  Element intent: '%s'\n"
            "  Page URL: %s\n"
            "  Test: %s",
            broken_selector, strategy, element_intent, page_url, test_name,
        )

        # Step 0: Check repository cache
        cached_result = self._check_cache(
            page, broken_selector, strategy, page_url
        )
        if cached_result:
            return cached_result

        # Step 1: Extract DOM context
        try:
            page_html = page.content()
            dom_context = self.dom_extractor.extract(
                page_html, broken_selector, strategy
            )
        except Exception as e:
            logger.error("DOM extraction failed: %s", e)
            return HealingResult(
                success=False,
                original_selector=broken_selector,
                original_strategy=strategy,
                error=f"DOM extraction failed: {e}",
            )

        # Step 2: Build prompt and call LLM
        try:
            llm_response = self._call_llm(
                broken_selector, strategy, dom_context, element_intent
            )
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return HealingResult(
                success=False,
                original_selector=broken_selector,
                original_strategy=strategy,
                error=f"LLM call failed: {e}",
            )

        if not llm_response.success:
            logger.error("LLM returned error: %s", llm_response.error)
            return HealingResult(
                success=False,
                original_selector=broken_selector,
                original_strategy=strategy,
                error=f"LLM error: {llm_response.error}",
            )

        # Step 3: Parse and validate candidates
        candidates_raw = llm_response.content.get("candidates", [])
        if not candidates_raw:
            logger.warning("LLM returned no candidates")
            return HealingResult(
                success=False,
                original_selector=broken_selector,
                original_strategy=strategy,
                error="LLM returned no candidates",
            )

        validator = CandidateValidator(page)
        validated = validator.validate_candidates(candidates_raw)

        if not validated or validated[0].final_score == 0.0:
            logger.warning("No valid candidates after validation")
            return HealingResult(
                success=False,
                original_selector=broken_selector,
                original_strategy=strategy,
                candidates=[self._candidate_to_dict(c) for c in validated],
                error="No valid candidates found on the live page",
            )

        # Step 4: Apply confidence gate to the best candidate
        best = validated[0]
        gate_result = self.confidence_gate.evaluate(best.final_score)

        # Step 5: Build result
        result = HealingResult(
            success=(gate_result.decision == HealingDecision.AUTO_HEAL),
            decision=gate_result.decision,
            healed_selector=best.selector,
            healed_strategy=best.strategy,
            confidence=best.final_score,
            reasoning=best.reasoning,
            original_selector=broken_selector,
            original_strategy=strategy,
            candidates=[self._candidate_to_dict(c) for c in validated],
            gate_result=gate_result,
            llm_provider=llm_response.provider,
            llm_model=llm_response.model,
            llm_latency_ms=llm_response.latency_ms,
            cached=False,
        )

        # Step 6: Persist to repository
        self._persist_result(result, test_name, page_url, element_intent)

        logger.info(
            "=== HEALING PIPELINE COMPLETE ===\n"
            "  Decision: %s\n"
            "  Healed: '%s' -> '%s'\n"
            "  Confidence: %.3f\n"
            "  Provider: %s (%s)\n"
            "  Latency: %.0f ms",
            gate_result.decision.value,
            broken_selector, best.selector,
            best.final_score,
            llm_response.provider, llm_response.model,
            llm_response.latency_ms,
        )

        return result

    def _check_cache(
        self, page: Page, selector: str, strategy: str, page_url: str
    ) -> Optional[HealingResult]:
        """Check the repository cache for a previously healed locator."""
        try:
            cached = self.repository.lookup(selector, strategy, page_url)
            if cached is None:
                return None

            # Verify the cached healed locator still works on the live page
            healed = cached["healed_selector"]
            validator = CandidateValidator(page)
            validated = validator.validate_candidates([{
                "selector": healed,
                "strategy": cached.get("healed_strategy", "css"),
                "confidence": cached["confidence"],
                "reasoning": f"Cached healing from {cached['original_heal_date']}",
            }])

            if validated and validated[0].is_found:
                logger.info(
                    "Cache HIT and validated: '%s' -> '%s'",
                    selector, healed,
                )
                return HealingResult(
                    success=True,
                    decision=HealingDecision.AUTO_HEAL,
                    healed_selector=healed,
                    healed_strategy=cached.get("healed_strategy", "css"),
                    confidence=cached["confidence"],
                    reasoning=cached["reasoning"],
                    original_selector=selector,
                    original_strategy=strategy,
                    cached=True,
                )
            else:
                logger.info(
                    "Cache HIT but validation failed for '%s', "
                    "proceeding with fresh healing",
                    healed,
                )
                return None

        except Exception as e:
            logger.warning("Cache lookup failed: %s", e)
            return None

    def _call_llm(
        self,
        broken_selector: str,
        strategy: str,
        dom_context: str,
        element_intent: str,
    ):
        """Build the prompt and invoke the LLM provider."""
        provider = LLMProviderFactory.get_provider()

        prompt = (
            f"A UI test locator has broken. Analyze the DOM and suggest "
            f"replacement selectors.\n\n"
            f"BROKEN LOCATOR:\n"
            f"  Selector: {broken_selector}\n"
            f"  Strategy: {strategy}\n"
            f"  Element Intent: {element_intent or 'Not specified'}\n\n"
            f"CURRENT DOM FRAGMENT:\n"
            f"```html\n{dom_context}\n```\n\n"
            f"Suggest up to 3 replacement selectors, ordered by confidence."
        )

        response_format = {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "selector": {"type": "string"},
                            "strategy": {"type": "string", "enum": ["css", "xpath", "text", "role"]},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "reasoning": {"type": "string"},
                        },
                        "required": ["selector", "strategy", "confidence", "reasoning"],
                    },
                },
            },
            "required": ["candidates"],
        }

        return provider.complete(
            prompt=prompt,
            system=HEALING_SYSTEM_PROMPT,
            response_format=response_format,
        )

    def _persist_result(
        self,
        result: HealingResult,
        test_name: Optional[str],
        page_url: str,
        element_intent: str,
    ):
        """Save the healing result to the locator repository."""
        try:
            self.repository.save(
                original_selector=result.original_selector,
                original_strategy=result.original_strategy,
                healed_selector=result.healed_selector if result.success else None,
                healed_strategy=result.healed_strategy if result.success else None,
                confidence=result.confidence,
                reasoning=result.reasoning,
                decision=result.decision.value if result.decision else "error",
                test_name=test_name,
                page_url=page_url,
                element_intent=element_intent,
                llm_provider=result.llm_provider,
                llm_model=result.llm_model,
                llm_latency_ms=result.llm_latency_ms,
            )
        except Exception as e:
            logger.error("Failed to persist healing result: %s", e)

    @staticmethod
    def _candidate_to_dict(candidate: ValidatedCandidate) -> dict:
        """Convert a ValidatedCandidate to a serializable dict."""
        return {
            "selector": candidate.selector,
            "strategy": candidate.strategy,
            "confidence": candidate.confidence,
            "reasoning": candidate.reasoning,
            "is_found": candidate.is_found,
            "is_visible": candidate.is_visible,
            "final_score": candidate.final_score,
            "match_count": candidate.match_count,
            "element_tag": candidate.element_tag,
            "element_text": candidate.element_text,
        }
