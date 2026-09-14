"""
ETL Anomaly Detector — AI-Augmented Data Quality Validation

Feeds source-to-target reconciliation statistics to the LLM to identify
data drift, outliers, and anomalies that rule-based checks would miss.
Traditional ETL validation catches exact mismatches (row counts, column
values), but this module detects subtler issues like distribution shifts,
unexpected correlations, and business-logic violations.

Part of the ETL/Database Validation pillar.
Uses the shared ai_core/llm/provider_factory.py — no ad-hoc LLM calls.
"""

import logging
from typing import Optional

from ai_core.llm.provider_factory import LLMProviderFactory

logger = logging.getLogger(__name__)

ETL_ANOMALY_SYSTEM_PROMPT = """You are a data quality engineer expert. Analyze the 
ETL reconciliation statistics and identify anomalies that rule-based checks might miss.

Look for:
1. Distribution shifts between source and target
2. Unexpected NULL/missing value patterns
3. Statistical outliers in numeric columns
4. Temporal anomalies (gaps in dates, future dates)
5. Business-logic violations (e.g., negative quantities, impossible totals)
6. Data drift from historical baselines

OUTPUT FORMAT (strict JSON):
{
  "anomalies_detected": true/false,
  "confidence": 0.0-1.0,
  "summary": "Overall data quality assessment",
  "anomalies": [
    {
      "column": "affected_column",
      "type": "distribution_shift|outlier|null_pattern|temporal|business_logic|drift",
      "description": "Detailed description of the anomaly",
      "severity": "high|medium|low",
      "recommendation": "Suggested action"
    }
  ]
}"""


class ETLAnomalyDetector:
    """
    Detects anomalies in ETL reconciliation results using LLM analysis.

    Usage:
        detector = ETLAnomalyDetector()
        result = detector.analyze(
            reconciliation_stats={
                "source_row_count": 10000,
                "target_row_count": 9998,
                "match_rate": 0.998,
                "column_stats": {
                    "amount": {"mean_diff": 0.02, "null_rate_source": 0.01, "null_rate_target": 0.05},
                    "date": {"min_source": "2024-01-01", "max_target": "2025-12-31"}
                }
            },
            context="Daily sales ETL pipeline, expected to have exact row count match"
        )
    """

    def analyze(
        self,
        reconciliation_stats: dict,
        context: str = "",
        historical_baseline: Optional[dict] = None,
    ) -> dict:
        """
        Analyze ETL reconciliation stats for anomalies.

        Args:
            reconciliation_stats: Dict with source/target counts, match rates,
                                  column-level statistics.
            context: Business context for the ETL pipeline.
            historical_baseline: Previous run stats for drift detection.

        Returns:
            Dict with anomalies_detected, confidence, summary, anomalies list.
        """
        provider = LLMProviderFactory.get_provider()

        import json
        prompt = (
            f"Analyze these ETL reconciliation statistics for anomalies:\n\n"
            f"RECONCILIATION STATS:\n{json.dumps(reconciliation_stats, indent=2, default=str)}\n\n"
        )
        if context:
            prompt += f"BUSINESS CONTEXT:\n{context}\n\n"
        if historical_baseline:
            prompt += f"HISTORICAL BASELINE:\n{json.dumps(historical_baseline, indent=2, default=str)}\n\n"

        prompt += "Identify any data quality anomalies, drift, or concerns."

        response = provider.complete(
            prompt=prompt,
            system=ETL_ANOMALY_SYSTEM_PROMPT,
        )

        if not response.success:
            logger.error("ETL anomaly detection failed: %s", response.error)
            return {
                "anomalies_detected": False,
                "confidence": 0.0,
                "summary": f"Analysis unavailable: {response.error}",
                "anomalies": [],
            }

        return response.content
