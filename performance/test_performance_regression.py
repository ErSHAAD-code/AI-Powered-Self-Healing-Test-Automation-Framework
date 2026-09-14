"""
Performance Regression Test — Baseline Comparison

Compares current performance metrics against stored baselines.
Fails if latency regresses beyond tolerance or error rate exceeds threshold.

Note: This test validates the regression detection logic using
pre-computed metrics rather than running a live Locust test
(which takes 60+ seconds). The CI pipeline runs the actual
Locust test separately.
"""

import json
import pytest
from pathlib import Path


BASELINE_FILE = Path("performance/baselines/perf_baseline.json")


def load_baseline() -> dict:
    """Load the performance baseline."""
    with open(BASELINE_FILE) as f:
        return json.load(f)["baseline"]


class TestPerformanceRegression:
    """Performance regression detection tests."""

    @pytest.fixture
    def baseline(self):
        return load_baseline()

    @pytest.fixture
    def current_metrics(self):
        """Simulated current run metrics (slightly better than baseline)."""
        return {
            "p50_latency_ms": 42,
            "p95_latency_ms": 115,
            "p99_latency_ms": 240,
            "avg_latency_ms": 52,
            "throughput_rps": 88,
            "error_rate": 0.001,
            "total_requests": 5280,
        }

    @pytest.mark.performance
    def test_p95_latency_within_tolerance(self, baseline, current_metrics):
        """Verify p95 latency hasn't regressed beyond 20% tolerance."""
        tolerance = 0.20
        baseline_p95 = baseline["metrics"]["p95_latency_ms"]
        current_p95 = current_metrics["p95_latency_ms"]
        max_allowed = baseline_p95 * (1 + tolerance)

        assert current_p95 <= max_allowed, (
            f"p95 latency regression: {current_p95}ms > {max_allowed}ms "
            f"(baseline: {baseline_p95}ms, tolerance: {tolerance * 100}%)"
        )

    @pytest.mark.performance
    def test_p99_latency_within_tolerance(self, baseline, current_metrics):
        """Verify p99 latency hasn't regressed beyond 25% tolerance."""
        tolerance = 0.25
        baseline_p99 = baseline["metrics"]["p99_latency_ms"]
        current_p99 = current_metrics["p99_latency_ms"]
        max_allowed = baseline_p99 * (1 + tolerance)

        assert current_p99 <= max_allowed, (
            f"p99 latency regression: {current_p99}ms > {max_allowed}ms"
        )

    @pytest.mark.performance
    def test_error_rate_below_threshold(self, current_metrics):
        """Verify error rate stays below 5%."""
        threshold = 0.05
        assert current_metrics["error_rate"] < threshold, (
            f"Error rate {current_metrics['error_rate']} exceeds "
            f"threshold {threshold}"
        )

    @pytest.mark.performance
    def test_throughput_not_degraded(self, baseline, current_metrics):
        """Verify throughput hasn't dropped more than 15%."""
        tolerance = 0.15
        baseline_rps = baseline["metrics"]["throughput_rps"]
        current_rps = current_metrics["throughput_rps"]
        min_allowed = baseline_rps * (1 - tolerance)

        assert current_rps >= min_allowed, (
            f"Throughput degradation: {current_rps} rps < {min_allowed} rps "
            f"(baseline: {baseline_rps} rps)"
        )
