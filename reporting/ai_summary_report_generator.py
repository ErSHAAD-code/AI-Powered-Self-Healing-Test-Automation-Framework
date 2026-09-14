"""
AI Summary Report Generator — Unified Dashboard Across All Test Pillars

Aggregates results from all testing pillars into one unified HTML report:
- UI/BDD test results with healing events
- API contract test results with semantic validation
- ETL reconciliation results with anomaly detection
- Performance regression results
- Flaky test analysis
- AI failure summaries (RCA)
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from jinja2 import Environment, FileSystemLoader

from ai_core.locator_healing.locator_repository import LocatorRepository

logger = logging.getLogger(__name__)


class AISummaryReportGenerator:
    """
    Generates the unified AI-augmented test report dashboard.

    Aggregates data from all testing pillars and AI modules into
    a single, comprehensive HTML report.
    """

    def __init__(
        self,
        template_dir: str = "reporting/templates",
        output_dir: str = "reports",
    ):
        self.template_dir = Path(template_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        test_results: Optional[dict] = None,
        healing_events: Optional[list] = None,
        etl_report: Optional[dict] = None,
        performance_metrics: Optional[dict] = None,
        flaky_analysis: Optional[dict] = None,
        rca_summaries: Optional[list] = None,
        output_filename: str = "unified_report.html",
    ) -> str:
        """Generate the unified report."""
        # Load healing events from various sources
        if healing_events is None:
            healing_events = self._load_healing_events()

        # Build report data
        report_data = {
            "title": "AI-Powered Self-Healing Framework — Unified Report",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stats": self._compute_healing_stats(healing_events),
            "events": healing_events,
            "test_results": test_results or {},
            "etl_report": etl_report or {},
            "performance": performance_metrics or {},
            "flaky": flaky_analysis or {},
            "rca": rca_summaries or [],
        }

        # Render template
        env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True,
        )
        template = env.get_template("unified_report.html.j2")
        html = template.render(**report_data)

        output_path = self.output_dir / output_filename
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info("Unified report generated: %s", output_path)
        return str(output_path)

    def _load_healing_events(self) -> list:
        """Load healing events from session file or repository."""
        events_file = self.output_dir / "healing_events.json"
        if events_file.exists():
            with open(events_file) as f:
                return json.load(f)
        try:
            repo = LocatorRepository()
            return repo.get_all_healings()
        except Exception:
            return []

    @staticmethod
    def _compute_healing_stats(events: list) -> dict:
        """Compute healing statistics for the report."""
        total = len(events)
        auto_healed = sum(1 for e in events if e.get("decision") == "auto_heal")
        suggested = sum(1 for e in events if e.get("decision") == "suggest")
        rejected = sum(1 for e in events if e.get("decision") == "reject")

        avg_conf = 0.0
        if total > 0:
            avg_conf = sum(e.get("confidence", 0) for e in events) / total

        return {
            "total": total,
            "auto_healed": auto_healed,
            "suggested": suggested,
            "rejected": rejected,
            "cached_hits": sum(1 for e in events if e.get("cached")),
            "heal_rate": f"{(auto_healed / total * 100):.1f}" if total > 0 else "0.0",
            "avg_confidence": f"{avg_conf:.2f}",
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generator = AISummaryReportGenerator()
    out_path = generator.generate()
    print(f"Unified AI summary report generated at: {out_path}")
