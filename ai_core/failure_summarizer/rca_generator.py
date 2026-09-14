"""
RCA Generator — AI-Powered Root Cause Analysis for Test Failures

On any test failure, combines the stack trace, screenshot path, and
relevant logs into a prompt for the LLM, which returns a 2-3 sentence
plain-English root cause hypothesis. This is displayed in the test
report next to the raw error, making failure triage faster.

Uses the shared ai_core/llm/provider_factory.py — no ad-hoc LLM calls.
"""

import logging
from typing import Optional

from ai_core.llm.provider_factory import LLMProviderFactory

logger = logging.getLogger(__name__)

RCA_SYSTEM_PROMPT = """You are a test failure analyst. Given a test failure with 
stack trace, logs, and context, provide a concise root cause analysis.

RULES:
1. Write 2-3 sentences explaining the most likely root cause
2. Be specific — don't say "something went wrong"
3. Suggest the most likely fix
4. Consider common causes: locator changes, timing issues, data problems, environment

OUTPUT FORMAT (strict JSON):
{
  "root_cause": "2-3 sentence plain-English root cause hypothesis",
  "confidence": 0.0-1.0,
  "category": "locator|timing|data|environment|assertion|infrastructure|unknown",
  "suggested_fix": "Specific action to resolve the failure",
  "related_component": "Component or module likely at fault"
}"""


class RCAGenerator:
    """
    Generates root cause analysis for test failures.

    Usage:
        rca = RCAGenerator()
        analysis = rca.analyze(
            test_name="test_login_valid_credentials",
            error_message="TimeoutError: Timeout 5000ms exceeded.",
            stack_trace="...",
            screenshot_path="reports/screenshots/failure.png",
            test_code="page.locator('#login-btn').click()"
        )
        print(analysis["root_cause"])
    """

    def analyze(
        self,
        test_name: str,
        error_message: str,
        stack_trace: str = "",
        screenshot_path: Optional[str] = None,
        test_code: str = "",
        logs: str = "",
    ) -> dict:
        """
        Analyze a test failure and generate a root cause hypothesis.

        Args:
            test_name: Name of the failed test.
            error_message: The error/exception message.
            stack_trace: Full stack trace.
            screenshot_path: Path to failure screenshot (for reference).
            test_code: Relevant test code that failed.
            logs: Recent log entries related to the failure.

        Returns:
            Dict with root_cause, confidence, category, suggested_fix.
        """
        provider = LLMProviderFactory.get_provider()

        prompt = f"Analyze this test failure:\n\n"
        prompt += f"TEST: {test_name}\n"
        prompt += f"ERROR: {error_message}\n\n"

        if stack_trace:
            # Trim stack trace to avoid token overflow
            prompt += f"STACK TRACE (last 30 lines):\n"
            lines = stack_trace.strip().split("\n")
            prompt += "\n".join(lines[-30:]) + "\n\n"

        if test_code:
            prompt += f"RELEVANT CODE:\n{test_code}\n\n"

        if logs:
            prompt += f"RECENT LOGS:\n{logs[-1000:]}\n\n"

        if screenshot_path:
            prompt += f"SCREENSHOT: {screenshot_path} (not visible, for reference)\n\n"

        prompt += "What is the most likely root cause and fix?"

        response = provider.complete(
            prompt=prompt,
            system=RCA_SYSTEM_PROMPT,
        )

        if not response.success:
            return {
                "root_cause": f"RCA unavailable: {response.error}",
                "confidence": 0.0,
                "category": "unknown",
                "suggested_fix": "Manual investigation required",
            }

        return response.content
