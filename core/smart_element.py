"""
Smart Element — Self-Healing Element Wrapper for Playwright

The bridge between Page Objects and the AI healing pipeline. SmartElement
wraps Playwright locator interactions with automatic self-healing:

1. Try the primary locator
2. On failure, check the locator repository for a cached healing
3. On cache miss, invoke the HealingEngine for live LLM-based healing
4. Apply the confidence gate decision (auto-heal, suggest, or fail)
5. Log all healing events for the unified report

This transparent wrapper means test code never calls the healing engine
directly — it simply uses SmartElement.find() and healing happens
automatically when needed.

Part of the Page Object Model (POM) hybrid framework architecture.
"""

import logging
from typing import Optional

from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeout

from ai_core.locator_healing.healing_engine import HealingEngine, HealingResult
from ai_core.locator_healing.confidence_gate import HealingDecision

logger = logging.getLogger(__name__)

# Global list to collect healing events during a test session
# Used by conftest.py and the reporting module
_healing_events: list[dict] = []


def get_healing_events() -> list[dict]:
    """Get all healing events from the current session."""
    return _healing_events.copy()


def clear_healing_events():
    """Clear healing events (called at the start of each test session)."""
    _healing_events.clear()


class SmartElement:
    """
    Self-healing element wrapper that transparently recovers from broken locators.

    SmartElement provides the same API as a standard Playwright Locator
    (click, fill, text_content, is_visible, etc.) but adds automatic
    self-healing when the primary locator fails.

    Usage in Page Objects:
        class LoginPage(BasePage):
            def click_login(self):
                btn = SmartElement(
                    self.page,
                    selector="#login-btn",
                    strategy="css",
                    intent="Login submit button",
                )
                btn.find().click()

    The find() method:
    1. Tries the primary selector
    2. On failure: checks cache → calls HealingEngine → applies result
    3. Returns a valid Playwright Locator or raises an error
    """

    def __init__(
        self,
        page: Page,
        selector: str,
        strategy: str = "css",
        intent: str = "",
        test_name: Optional[str] = None,
        healing_engine: Optional[HealingEngine] = None,
        timeout_ms: int = 5000,
    ):
        """
        Initialize a SmartElement.

        Args:
            page: Playwright Page instance.
            selector: Primary CSS/XPath selector.
            strategy: Locator strategy ("css", "xpath", "text", "role").
            intent: Human-readable description of the element's purpose.
            test_name: Name of the test using this element.
            healing_engine: Custom HealingEngine (default: shared instance).
            timeout_ms: Timeout for element location attempts (ms).
        """
        self.page = page
        self.selector = selector
        self.strategy = strategy
        self.intent = intent
        self.test_name = test_name
        self.timeout_ms = timeout_ms

        self._engine = healing_engine or HealingEngine()
        self._locator: Optional[Locator] = None
        self._healed: bool = False
        self._healing_result: Optional[HealingResult] = None

    def find(self) -> Locator:
        """
        Find the element, self-healing if the primary locator fails.

        Returns:
            Playwright Locator pointing to the element.

        Raises:
            ElementNotFoundError: If the element cannot be found and
                                  healing was not successful.
        """
        # Step 1: Try the primary locator
        try:
            locator = self._create_locator(self.selector, self.strategy)
            locator.wait_for(state="attached", timeout=self.timeout_ms)

            logger.debug(
                "Element found with primary locator: '%s'", self.selector
            )
            self._locator = locator
            return locator

        except (PlaywrightTimeout, Exception) as primary_error:
            logger.warning(
                "Primary locator failed: '%s' — %s. Initiating self-healing...",
                self.selector, type(primary_error).__name__,
            )

        # Step 2: Invoke the healing engine
        healing_result = self._engine.heal(
            page=self.page,
            broken_selector=self.selector,
            strategy=self.strategy,
            element_intent=self.intent,
            test_name=self.test_name,
        )

        self._healing_result = healing_result

        # Record the healing event for reporting
        self._record_healing_event(healing_result)

        # Step 3: Apply the confidence gate decision
        if healing_result.success and healing_result.decision == HealingDecision.AUTO_HEAL:
            # Auto-heal: use the healed locator
            healed_locator = self._create_locator(
                healing_result.healed_selector,
                healing_result.healed_strategy,
            )
            self._locator = healed_locator
            self._healed = True

            logger.info(
                "✅ SELF-HEALED: '%s' -> '%s' (confidence=%.2f)\n"
                "   Reasoning: %s",
                self.selector,
                healing_result.healed_selector,
                healing_result.confidence,
                healing_result.reasoning,
            )

            return healed_locator

        elif healing_result.decision == HealingDecision.SUGGEST_REVIEW:
            # Suggest review: fail the test but log the suggestion
            suggestion = (
                f"🔍 HEALING SUGGESTION (needs human review):\n"
                f"   Broken:  '{self.selector}'\n"
                f"   Suggest: '{healing_result.healed_selector}'\n"
                f"   Confidence: {healing_result.confidence:.2f}\n"
                f"   Reasoning: {healing_result.reasoning}"
            )
            logger.warning(suggestion)
            raise ElementNotFoundError(
                f"Element not found: '{self.selector}'. "
                f"AI suggested '{healing_result.healed_selector}' "
                f"(confidence={healing_result.confidence:.2f}) "
                f"but it needs human review.",
                healing_result=healing_result,
            )

        else:
            # Reject: normal failure
            raise ElementNotFoundError(
                f"Element not found: '{self.selector}'. "
                f"AI healing confidence too low ({healing_result.confidence:.2f}).",
                healing_result=healing_result,
            )

    def click(self, **kwargs):
        """Find the element and click it."""
        self.find().click(**kwargs)

    def fill(self, value: str, **kwargs):
        """Find the element and fill it with text."""
        self.find().fill(value, **kwargs)

    def text_content(self) -> Optional[str]:
        """Find the element and return its text content."""
        return self.find().text_content()

    def inner_text(self) -> str:
        """Find the element and return its inner text."""
        return self.find().inner_text()

    def is_visible(self) -> bool:
        """Check if the element is visible (without healing)."""
        try:
            locator = self._create_locator(self.selector, self.strategy)
            return locator.is_visible()
        except Exception:
            return False

    def get_attribute(self, name: str) -> Optional[str]:
        """Find the element and get an attribute value."""
        return self.find().get_attribute(name)

    @property
    def was_healed(self) -> bool:
        """Whether this element was auto-healed during find()."""
        return self._healed

    @property
    def healing_result(self) -> Optional[HealingResult]:
        """The healing result, if healing was triggered."""
        return self._healing_result

    def _create_locator(self, selector: str, strategy: str) -> Locator:
        """Create a Playwright locator from a selector and strategy."""
        strategy = strategy.lower()

        if strategy == "xpath":
            return self.page.locator(f"xpath={selector}")
        elif strategy == "text":
            return self.page.get_by_text(selector)
        elif strategy == "role":
            parts = selector.split(":", 1)
            role = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 else None
            if name:
                return self.page.get_by_role(role, name=name)
            return self.page.get_by_role(role)
        else:
            return self.page.locator(selector)

    def _record_healing_event(self, result: HealingResult):
        """Record a healing event for the session report."""
        event = {
            "original_selector": result.original_selector,
            "original_strategy": result.original_strategy,
            "healed_selector": result.healed_selector,
            "healed_strategy": result.healed_strategy,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
            "decision": result.decision.value if result.decision else "error",
            "test_name": self.test_name,
            "element_intent": self.intent,
            "page_url": self.page.url,
            "llm_provider": result.llm_provider,
            "llm_model": result.llm_model,
            "cached": result.cached,
            "success": result.success,
        }
        _healing_events.append(event)


class ElementNotFoundError(Exception):
    """
    Raised when an element cannot be found and healing was insufficient.

    Carries the healing result for reporting purposes.
    """

    def __init__(self, message: str, healing_result: Optional[HealingResult] = None):
        super().__init__(message)
        self.healing_result = healing_result
