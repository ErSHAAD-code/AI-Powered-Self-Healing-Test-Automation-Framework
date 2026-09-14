"""
Healing Report Generator — AI-Augmented Test Report Dashboard

Generates a professional HTML report summarizing all self-healing
events from the test run. The report includes:
- Healing summary statistics (total, auto-healed, suggested, rejected)
- Detailed healing event cards with before/after selectors
- Confidence scores and LLM reasoning
- Provider and latency metadata
- Visual status indicators

Uses Jinja2 templating for the HTML output.
"""

import json
import logging
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from ai_core.locator_healing.locator_repository import LocatorRepository

logger = logging.getLogger(__name__)


class HealingReportGenerator:
    """
    Generates HTML reports for self-healing locator events.

    Sources data from:
    1. Session healing events (passed directly)
    2. Locator repository (historical data from SQLite)

    Output: A single HTML file with a professional dashboard layout.
    """

    def __init__(
        self,
        template_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        self.template_dir = Path(template_dir or "reporting/templates")
        self.output_dir = Path(output_dir or "reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        healing_events: Optional[list[dict]] = None,
        output_filename: str = "healing_report.html",
        open_browser: bool = False,
    ) -> str:
        """
        Generate the healing report HTML.

        Args:
            healing_events: List of healing event dicts from the session.
                          If None, loads from the locator repository.
            output_filename: Output HTML filename.
            open_browser: Whether to open the report in the default browser.

        Returns:
            Path to the generated report file.
        """
        # Load healing data
        if healing_events is None:
            try:
                repo = LocatorRepository()
                healing_events = repo.get_all_healings()
            except Exception as e:
                logger.warning("Could not load from repository: %s", e)
                healing_events = []

        # Also try loading from session events file
        session_file = self.output_dir / "healing_events.json"
        if session_file.exists() and not healing_events:
            with open(session_file) as f:
                healing_events = json.load(f)

        # Compute statistics
        stats = self._compute_stats(healing_events)

        # Render template
        env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True,
        )

        template = env.get_template("unified_report.html.j2")
        html = template.render(
            title="AI Self-Healing Report",
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            stats=stats,
            events=healing_events,
        )

        # Write output
        output_path = self.output_dir / output_filename
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info("Healing report generated: %s", output_path)

        if open_browser:
            webbrowser.open(f"file://{output_path.resolve()}")

        return str(output_path)

    @staticmethod
    def _compute_stats(events: list[dict]) -> dict:
        """Compute aggregate statistics from healing events."""
        total = len(events)
        auto_healed = sum(1 for e in events if e.get("decision") == "auto_heal")
        suggested = sum(1 for e in events if e.get("decision") == "suggest")
        rejected = sum(1 for e in events if e.get("decision") == "reject")
        cached = sum(1 for e in events if e.get("cached") or e.get("is_cached_hit"))

        avg_confidence = 0.0
        if total > 0:
            confidences = [e.get("confidence", 0) for e in events]
            avg_confidence = sum(confidences) / len(confidences)

        return {
            "total": total,
            "auto_healed": auto_healed,
            "suggested": suggested,
            "rejected": rejected,
            "cached_hits": cached,
            "heal_rate": f"{(auto_healed / total * 100):.1f}" if total > 0 else "0.0",
            "avg_confidence": f"{avg_confidence:.2f}",
        }
