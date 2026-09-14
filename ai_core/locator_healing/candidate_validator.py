"""
Candidate Validator — Live Browser Verification of LLM-Suggested Locators

After the LLM returns candidate selectors for a broken locator, this
module validates each candidate against the live browser page. It checks
whether the selector actually finds an element, whether that element is
visible and interactive, and re-ranks the candidates accordingly.

This prevents the framework from blindly trusting LLM suggestions —
only candidates that resolve to real, visible elements are accepted.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from playwright.sync_api import Page

logger = logging.getLogger(__name__)


@dataclass
class ValidatedCandidate:
    """
    A single validated locator candidate.

    Attributes:
        selector: CSS or XPath selector string.
        strategy: Locator strategy ("css", "xpath", "text", "role").
        confidence: LLM-assigned confidence (0.0 - 1.0).
        reasoning: LLM reasoning for this candidate.
        is_found: Whether the selector found an element on the page.
        is_visible: Whether the found element is visible.
        is_enabled: Whether the found element is enabled/interactive.
        element_tag: HTML tag name of the found element.
        element_text: Text content of the found element.
        match_count: Number of elements matching this selector.
        final_score: Combined score after validation (0.0 - 1.0).
    """
    selector: str = ""
    strategy: str = "css"
    confidence: float = 0.0
    reasoning: str = ""
    is_found: bool = False
    is_visible: bool = False
    is_enabled: bool = False
    element_tag: str = ""
    element_text: str = ""
    match_count: int = 0
    final_score: float = 0.0


class CandidateValidator:
    """
    Validates LLM-generated locator candidates against the live browser page.

    Validation pipeline for each candidate:
    1. Try to locate the element using the suggested selector
    2. Check visibility and interactability
    3. Collect element metadata (tag, text, match count)
    4. Compute a final score combining LLM confidence + validation results
    5. Re-rank all candidates by final score

    This ensures that only selectors pointing to real, visible elements
    are accepted by the confidence gate.
    """

    # Weights for final score computation
    WEIGHT_LLM_CONFIDENCE = 0.5
    WEIGHT_IS_FOUND = 0.2
    WEIGHT_IS_VISIBLE = 0.15
    WEIGHT_IS_UNIQUE = 0.1
    WEIGHT_IS_ENABLED = 0.05

    def __init__(self, page: Page, timeout_ms: int = 3000):
        """
        Initialize the candidate validator.

        Args:
            page: Playwright Page instance for live element verification.
            timeout_ms: Timeout for each candidate check (ms).
        """
        self.page = page
        self.timeout_ms = timeout_ms

    def validate_candidates(
        self, candidates: list[dict]
    ) -> list[ValidatedCandidate]:
        """
        Validate and re-rank a list of LLM-generated candidates.

        Args:
            candidates: List of candidate dicts from the LLM, each containing:
                - selector: The suggested selector string
                - strategy: Locator strategy (css, xpath, text, role)
                - confidence: LLM confidence score (0.0 - 1.0)
                - reasoning: LLM reasoning for this suggestion

        Returns:
            Sorted list of ValidatedCandidate objects (highest score first).
        """
        validated = []

        for candidate in candidates:
            result = self._validate_single(candidate)
            validated.append(result)
            logger.debug(
                "Candidate validated: selector='%s', found=%s, visible=%s, "
                "score=%.3f",
                result.selector, result.is_found, result.is_visible,
                result.final_score,
            )

        # Sort by final score descending
        validated.sort(key=lambda c: c.final_score, reverse=True)

        logger.info(
            "Validated %d candidates, best: selector='%s' (score=%.3f)",
            len(validated),
            validated[0].selector if validated else "none",
            validated[0].final_score if validated else 0.0,
        )

        return validated

    def _validate_single(self, candidate: dict) -> ValidatedCandidate:
        """
        Validate a single candidate selector against the live page.

        Args:
            candidate: Dict with selector, strategy, confidence, reasoning.

        Returns:
            ValidatedCandidate with validation results.
        """
        result = ValidatedCandidate(
            selector=candidate.get("selector", ""),
            strategy=candidate.get("strategy", "css"),
            confidence=candidate.get("confidence", 0.0),
            reasoning=candidate.get("reasoning", ""),
        )

        if not result.selector:
            result.final_score = 0.0
            return result

        try:
            locator = self._create_locator(result.selector, result.strategy)

            # Check how many elements match
            result.match_count = locator.count()
            result.is_found = result.match_count > 0

            if result.is_found:
                # Use the first matching element
                first = locator.first

                # Check visibility
                try:
                    result.is_visible = first.is_visible()
                except Exception:
                    result.is_visible = False

                # Check if enabled/interactive
                try:
                    result.is_enabled = first.is_enabled()
                except Exception:
                    result.is_enabled = True  # Assume enabled if can't check

                # Get element metadata
                try:
                    result.element_tag = first.evaluate("el => el.tagName.toLowerCase()")
                except Exception:
                    result.element_tag = ""

                try:
                    text = first.evaluate("el => el.textContent")
                    result.element_text = (text or "").strip()[:100]
                except Exception:
                    result.element_text = ""

        except Exception as e:
            logger.debug(
                "Candidate validation failed for '%s': %s",
                result.selector, e,
            )
            result.is_found = False

        # Compute final score
        result.final_score = self._compute_score(result)

        return result

    def _create_locator(self, selector: str, strategy: str):
        """
        Create a Playwright locator based on the strategy.

        Args:
            selector: Selector string.
            strategy: One of "css", "xpath", "text", "role".

        Returns:
            Playwright Locator object.
        """
        strategy = strategy.lower()

        if strategy == "xpath":
            return self.page.locator(f"xpath={selector}")
        elif strategy == "text":
            return self.page.get_by_text(selector)
        elif strategy == "role":
            # Parse role and name from selector like "button:Sign In"
            parts = selector.split(":", 1)
            role = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 else None
            if name:
                return self.page.get_by_role(role, name=name)
            return self.page.get_by_role(role)
        else:
            # Default: CSS selector
            return self.page.locator(selector)

    def _compute_score(self, candidate: ValidatedCandidate) -> float:
        """
        Compute a weighted final score for a validated candidate.

        Score formula:
            final = (llm_confidence * 0.5) +
                    (is_found * 0.2) +
                    (is_visible * 0.15) +
                    (is_unique * 0.1) +
                    (is_enabled * 0.05)

        Args:
            candidate: ValidatedCandidate with validation results.

        Returns:
            Final score between 0.0 and 1.0.
        """
        score = candidate.confidence * self.WEIGHT_LLM_CONFIDENCE

        if candidate.is_found:
            score += self.WEIGHT_IS_FOUND

        if candidate.is_visible:
            score += self.WEIGHT_IS_VISIBLE

        # Uniqueness bonus: exactly 1 match is ideal
        if candidate.match_count == 1:
            score += self.WEIGHT_IS_UNIQUE
        elif candidate.match_count > 1:
            # Partial credit for multiple matches
            score += self.WEIGHT_IS_UNIQUE * 0.3

        if candidate.is_enabled:
            score += self.WEIGHT_IS_ENABLED

        return min(score, 1.0)
