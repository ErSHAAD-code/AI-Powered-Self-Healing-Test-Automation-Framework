"""
Flaky Test Analyzer — AI-Powered Test Stability Classification

Mines the test run history database for tests that flip between pass
and fail across runs, then asks the LLM to classify the likely root
cause: timing/race condition, environment dependency, or real bug.

Uses the shared ai_core/llm/provider_factory.py — no ad-hoc LLM calls.
"""

import json
import logging
from pathlib import Path
from typing import Optional
from collections import defaultdict

from ai_core.llm.provider_factory import LLMProviderFactory

logger = logging.getLogger(__name__)

FLAKY_SYSTEM_PROMPT = """You are a test stability expert. Analyze the test execution 
history and classify why each flaky test is failing intermittently.

CLASSIFICATION CATEGORIES:
- "timing": Race condition, async wait issues, animation timing
- "environment": Environment-dependent (OS, browser version, network)  
- "data_dependency": Depends on external data or state from other tests
- "real_bug": Actual application bug that manifests intermittently
- "resource": Resource contention (memory, CPU, file locks)

OUTPUT FORMAT (strict JSON):
{
  "flaky_tests": [
    {
      "test_name": "name",
      "classification": "timing|environment|data_dependency|real_bug|resource",
      "confidence": 0.0-1.0,
      "reasoning": "Why this classification was chosen",
      "recommendation": "Suggested fix",
      "pass_rate": 0.0-1.0,
      "total_runs": <number>
    }
  ],
  "summary": "Overall flaky test analysis"
}"""


class FlakyAnalyzer:
    """
    Analyzes test run history to detect and classify flaky tests.

    Usage:
        analyzer = FlakyAnalyzer()
        results = analyzer.analyze(min_runs=5, max_pass_rate=0.95)
    """

    def __init__(self, history_file: Optional[str] = None):
        self.history_file = Path(history_file or "data/test_run_log.jsonl")

    def analyze(
        self,
        min_runs: int = 3,
        max_pass_rate: float = 0.95,
        min_pass_rate: float = 0.05,
    ) -> dict:
        """
        Analyze test history for flaky tests and classify root causes.

        Args:
            min_runs: Minimum runs needed to consider a test.
            max_pass_rate: Tests passing more than this are stable.
            min_pass_rate: Tests passing less than this are consistently failing.

        Returns:
            Dict with flaky_tests list and summary.
        """
        # Load and aggregate history
        history = self._load_history()
        flaky_candidates = self._find_flaky_tests(
            history, min_runs, max_pass_rate, min_pass_rate
        )

        if not flaky_candidates:
            return {
                "flaky_tests": [],
                "summary": "No flaky tests detected. All tests are stable.",
            }

        # Ask LLM to classify
        provider = LLMProviderFactory.get_provider()

        prompt = (
            "Analyze these flaky tests and classify their root causes:\n\n"
            f"{json.dumps(flaky_candidates, indent=2)}\n\n"
            "For each test, determine why it's flaking and suggest a fix."
        )

        response = provider.complete(
            prompt=prompt,
            system=FLAKY_SYSTEM_PROMPT,
        )

        if not response.success:
            logger.error("Flaky analysis failed: %s", response.error)
            return {
                "flaky_tests": flaky_candidates,
                "summary": f"LLM classification unavailable: {response.error}",
            }

        return response.content

    def _load_history(self) -> list[dict]:
        """Load test run history from JSONL file."""
        if not self.history_file.exists():
            logger.warning("No test history file found: %s", self.history_file)
            return []

        records = []
        with open(self.history_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        return records

    def _find_flaky_tests(
        self,
        history: list[dict],
        min_runs: int,
        max_pass_rate: float,
        min_pass_rate: float,
    ) -> list[dict]:
        """Identify tests with inconsistent pass/fail patterns."""
        test_results = defaultdict(list)

        for record in history:
            name = record.get("test_name", "")
            outcome = record.get("outcome", "")
            if name and outcome:
                test_results[name].append({
                    "outcome": outcome,
                    "duration": record.get("duration", 0),
                    "error": record.get("error", ""),
                    "timestamp": record.get("timestamp", ""),
                })

        flaky = []
        for name, runs in test_results.items():
            total = len(runs)
            if total < min_runs:
                continue

            passed = sum(1 for r in runs if r["outcome"] == "passed")
            pass_rate = passed / total

            if min_pass_rate < pass_rate < max_pass_rate:
                # This test is flaky
                errors = [r["error"] for r in runs if r.get("error")]
                flaky.append({
                    "test_name": name,
                    "total_runs": total,
                    "passed": passed,
                    "failed": total - passed,
                    "pass_rate": round(pass_rate, 3),
                    "recent_errors": errors[-3:],  # Last 3 errors
                })

        return flaky
