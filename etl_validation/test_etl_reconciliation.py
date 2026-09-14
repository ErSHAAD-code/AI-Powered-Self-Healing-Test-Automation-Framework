"""
ETL Reconciliation Tests — Source-to-Target Validation Test Suite

Exercises the ETL reconciler against sample data and validates all
reconciliation rules pass. Also demonstrates AI-augmented anomaly
detection for catching issues beyond rule-based checks.
"""

import pytest
from etl_validation.reconciler import ETLReconciler


class TestETLReconciliation:
    """Test suite for ETL source-to-target validation."""

    @pytest.fixture
    def reconciler(self):
        return ETLReconciler("etl_validation/reconciliation_rules.yaml")

    @pytest.mark.etl
    @pytest.mark.smoke
    def test_reconciliation_runs_successfully(self, reconciler):
        """Verify the reconciliation pipeline completes without errors."""
        report = reconciler.reconcile()
        assert report.rules_total > 0, "Should have at least one rule"

    @pytest.mark.etl
    def test_row_count_matches(self, reconciler):
        """Verify source and target have the same row count."""
        report = reconciler.reconcile()
        assert report.source_row_count == report.target_row_count, \
            f"Row count mismatch: source={report.source_row_count}, target={report.target_row_count}"

    @pytest.mark.etl
    def test_all_rules_pass(self, reconciler):
        """Verify all reconciliation rules pass."""
        report = reconciler.reconcile()
        failed_rules = [r for r in report.results if not r.passed]

        assert len(failed_rules) == 0, \
            f"{len(failed_rules)} rules failed:\n" + \
            "\n".join(f"  - {r.rule_name}: {r.message}" for r in failed_rules)

    @pytest.mark.etl
    def test_key_completeness(self, reconciler):
        """Verify all source keys exist in the target."""
        report = reconciler.reconcile()
        key_rules = [r for r in report.results if r.rule_type == "key_match"]

        for rule in key_rules:
            assert rule.passed, f"Key completeness failed: {rule.message}"

    @pytest.mark.etl
    def test_derived_columns_correct(self, reconciler):
        """Verify derived/computed columns are calculated correctly."""
        report = reconciler.reconcile()
        derived_rules = [r for r in report.results if r.rule_type == "derived_column"]

        for rule in derived_rules:
            assert rule.passed, f"Derived column check failed: {rule.message}"

    @pytest.mark.etl
    @pytest.mark.ai
    def test_ai_anomaly_detection(self, reconciler):
        """Use AI to detect anomalies beyond rule-based checks."""
        from ai_core.anomaly_detection.etl_anomaly_detector import ETLAnomalyDetector

        report = reconciler.reconcile()
        detector = ETLAnomalyDetector()

        result = detector.analyze(
            reconciliation_stats=report.to_dict(),
            context="Daily orders ETL pipeline — expects exact match between source and target"
        )

        # Log any detected anomalies for review
        if result.get("anomalies_detected"):
            for anomaly in result.get("anomalies", []):
                pytest.warns(
                    UserWarning,
                    match=f"ETL Anomaly: {anomaly.get('description', 'Unknown')}",
                )
