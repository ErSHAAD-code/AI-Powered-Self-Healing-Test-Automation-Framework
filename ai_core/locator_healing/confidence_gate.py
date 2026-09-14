"""
Confidence Gate — Threshold-Based Healing Decision Engine

Applies configurable confidence thresholds to determine how the framework
should handle a healed locator:

  >= auto_apply_threshold (0.85): AUTO-HEAL — use the healed locator,
      continue the test, and mark the step as "HEALED" in the report.

  >= review_threshold (0.60):     SUGGEST REVIEW — fail the test but
      log the suggested replacement locator for human review.

  < review_threshold (0.60):      REJECT — normal test failure, no AI
      noise added. The LLM was not confident enough to help.

This three-tier approach balances automation speed with safety: only
high-confidence healings are applied automatically, while medium-confidence
suggestions still provide value by guiding manual debugging.
"""

import logging
from enum import Enum
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "config.yaml"


class HealingDecision(Enum):
    """
    The three possible outcomes of the confidence gate evaluation.
    """
    AUTO_HEAL = "auto_heal"       # Apply automatically, mark as HEALED
    SUGGEST_REVIEW = "suggest"     # Fail test, log suggestion for human review
    REJECT = "reject"              # Normal failure, LLM not confident enough


@dataclass
class GateResult:
    """
    Result of a confidence gate evaluation.

    Attributes:
        decision: The healing decision (AUTO_HEAL, SUGGEST_REVIEW, REJECT).
        confidence: The confidence score that was evaluated.
        threshold_applied: Which threshold triggered this decision.
        message: Human-readable explanation of the decision.
    """
    decision: HealingDecision
    confidence: float
    threshold_applied: str
    message: str


class ConfidenceGate:
    """
    Evaluates healing candidates against configurable confidence thresholds.

    Reads thresholds from config.yaml and provides a clear, auditable
    decision for each healing attempt. All decisions are logged for
    inclusion in the healing report.

    Usage:
        gate = ConfidenceGate()
        result = gate.evaluate(confidence=0.92)
        if result.decision == HealingDecision.AUTO_HEAL:
            # Apply the healed locator and continue
            ...
    """

    def __init__(
        self,
        auto_apply_threshold: Optional[float] = None,
        review_threshold: Optional[float] = None,
    ):
        """
        Initialize the confidence gate with thresholds.

        If thresholds are not provided, they are loaded from config.yaml.

        Args:
            auto_apply_threshold: Minimum confidence for auto-healing (default: 0.85).
            review_threshold: Minimum confidence for suggesting review (default: 0.60).
        """
        config = self._load_config()

        self.auto_apply_threshold = (
            auto_apply_threshold
            if auto_apply_threshold is not None
            else config.get("auto_apply_threshold", 0.85)
        )
        self.review_threshold = (
            review_threshold
            if review_threshold is not None
            else config.get("review_threshold", 0.60)
        )

        # Validate thresholds
        if self.auto_apply_threshold <= self.review_threshold:
            logger.warning(
                "auto_apply_threshold (%.2f) should be greater than "
                "review_threshold (%.2f)",
                self.auto_apply_threshold, self.review_threshold,
            )

        logger.info(
            "ConfidenceGate initialized: auto_apply=%.2f, review=%.2f",
            self.auto_apply_threshold, self.review_threshold,
        )

    @staticmethod
    def _load_config() -> dict:
        """Load healing thresholds from config.yaml."""
        try:
            with open(_CONFIG_PATH, "r") as f:
                config = yaml.safe_load(f)
            return config.get("healing", {})
        except FileNotFoundError:
            logger.warning("Config file not found, using default thresholds")
            return {}

    def evaluate(self, confidence: float) -> GateResult:
        """
        Evaluate a confidence score against the thresholds.

        Args:
            confidence: The confidence score from the candidate validator
                       (0.0 to 1.0).

        Returns:
            GateResult with the decision, applied threshold, and message.
        """
        if confidence >= self.auto_apply_threshold:
            result = GateResult(
                decision=HealingDecision.AUTO_HEAL,
                confidence=confidence,
                threshold_applied=f"auto_apply >= {self.auto_apply_threshold}",
                message=(
                    f"AUTO-HEAL: Confidence {confidence:.2f} meets auto-apply "
                    f"threshold ({self.auto_apply_threshold:.2f}). "
                    f"Applying healed locator automatically."
                ),
            )
            logger.info(result.message)
            return result

        elif confidence >= self.review_threshold:
            result = GateResult(
                decision=HealingDecision.SUGGEST_REVIEW,
                confidence=confidence,
                threshold_applied=f"review >= {self.review_threshold}",
                message=(
                    f"SUGGEST REVIEW: Confidence {confidence:.2f} meets review "
                    f"threshold ({self.review_threshold:.2f}) but not auto-apply "
                    f"({self.auto_apply_threshold:.2f}). "
                    f"Failing test, logging suggestion for human review."
                ),
            )
            logger.info(result.message)
            return result

        else:
            result = GateResult(
                decision=HealingDecision.REJECT,
                confidence=confidence,
                threshold_applied=f"below review < {self.review_threshold}",
                message=(
                    f"REJECT: Confidence {confidence:.2f} is below review "
                    f"threshold ({self.review_threshold:.2f}). "
                    f"Normal test failure, no AI suggestion provided."
                ),
            )
            logger.info(result.message)
            return result
