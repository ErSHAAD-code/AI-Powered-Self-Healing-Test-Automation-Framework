"""
ETL Reconciler — Source-to-Target Data Validation Engine

Implements the source-to-target reconciliation pattern used in ETL
testing / database validation. Loads source and target datasets,
applies configurable validation rules, and reports discrepancies.

Part of the ETL/Database Validation pillar.

Supports rule types:
- row_count: Verify row count match with optional tolerance
- key_match: Verify all source keys exist in target
- column_match: Compare column values (exact or within tolerance)
- derived_column: Validate computed/derived columns
- column_format: Validate date/string format patterns
"""

import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import yaml
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class RuleResult:
    """Result of a single reconciliation rule check."""
    rule_name: str
    rule_type: str
    passed: bool
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class ReconciliationReport:
    """Complete reconciliation report."""
    pipeline_name: str
    source_row_count: int
    target_row_count: int
    rules_total: int
    rules_passed: int
    rules_failed: int
    pass_rate: float
    results: list[RuleResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pipeline_name": self.pipeline_name,
            "source_row_count": self.source_row_count,
            "target_row_count": self.target_row_count,
            "rules_total": self.rules_total,
            "rules_passed": self.rules_passed,
            "rules_failed": self.rules_failed,
            "pass_rate": self.pass_rate,
            "results": [
                {
                    "rule_name": r.rule_name,
                    "rule_type": r.rule_type,
                    "passed": r.passed,
                    "message": r.message,
                    "details": r.details,
                }
                for r in self.results
            ],
        }


class ETLReconciler:
    """
    Source-to-target ETL reconciliation engine.

    Usage:
        reconciler = ETLReconciler("etl_validation/reconciliation_rules.yaml")
        report = reconciler.reconcile()
        assert report.rules_failed == 0, f"ETL failures: {report.rules_failed}"
    """

    def __init__(self, rules_path: Optional[str] = None):
        self.rules_path = Path(rules_path or "etl_validation/reconciliation_rules.yaml")
        self.config = self._load_rules()
        self.source_df: Optional[pd.DataFrame] = None
        self.target_df: Optional[pd.DataFrame] = None

    def _load_rules(self) -> dict:
        """Load reconciliation rules from YAML."""
        with open(self.rules_path) as f:
            return yaml.safe_load(f).get("reconciliation", {})

    def reconcile(self) -> ReconciliationReport:
        """
        Execute the full reconciliation pipeline.

        Returns:
            ReconciliationReport with all rule results.
        """
        # Load data
        source_file = self.config.get("source", {}).get("file", "")
        target_file = self.config.get("target", {}).get("file", "")
        source_key = self.config.get("source", {}).get("key_column", "")
        target_key = self.config.get("target", {}).get("key_column", "")

        self.source_df = pd.read_csv(source_file)
        self.target_df = pd.read_csv(target_file)

        logger.info(
            "Loaded source (%d rows) and target (%d rows)",
            len(self.source_df), len(self.target_df),
        )

        # Execute rules
        rules = self.config.get("rules", [])
        results: list[RuleResult] = []

        for rule in rules:
            rule_type = rule.get("type", "")
            try:
                if rule_type == "row_count":
                    results.append(self._check_row_count(rule))
                elif rule_type == "key_match":
                    results.append(self._check_key_match(rule, source_key, target_key))
                elif rule_type == "column_match":
                    results.append(self._check_column_match(rule, source_key, target_key))
                elif rule_type == "derived_column":
                    results.append(self._check_derived_column(rule, source_key, target_key))
                elif rule_type == "column_format":
                    results.append(self._check_column_format(rule))
                else:
                    results.append(RuleResult(
                        rule_name=rule.get("name", "Unknown"),
                        rule_type=rule_type,
                        passed=False,
                        message=f"Unknown rule type: {rule_type}",
                    ))
            except Exception as e:
                results.append(RuleResult(
                    rule_name=rule.get("name", "Unknown"),
                    rule_type=rule_type,
                    passed=False,
                    message=f"Rule execution error: {e}",
                ))

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed

        report = ReconciliationReport(
            pipeline_name=self.config.get("name", "Unknown"),
            source_row_count=len(self.source_df),
            target_row_count=len(self.target_df),
            rules_total=len(results),
            rules_passed=passed,
            rules_failed=failed,
            pass_rate=passed / len(results) if results else 0.0,
            results=results,
        )

        logger.info(
            "Reconciliation complete: %d/%d rules passed (%.1f%%)",
            passed, len(results), report.pass_rate * 100,
        )

        return report

    def _check_row_count(self, rule: dict) -> RuleResult:
        """Check source vs target row count."""
        tolerance = rule.get("tolerance_percent", 0) / 100
        source_count = len(self.source_df)
        target_count = len(self.target_df)
        diff = abs(source_count - target_count)
        max_diff = source_count * tolerance

        passed = diff <= max_diff
        return RuleResult(
            rule_name=rule.get("name", "Row Count"),
            rule_type="row_count",
            passed=passed,
            message=f"Source: {source_count}, Target: {target_count}, Diff: {diff}",
            details={"source": source_count, "target": target_count, "diff": diff},
        )

    def _check_key_match(self, rule: dict, source_key: str, target_key: str) -> RuleResult:
        """Check that all source keys exist in target."""
        source_keys = set(self.source_df[source_key])
        target_keys = set(self.target_df[target_key])
        missing = source_keys - target_keys

        passed = len(missing) == 0
        return RuleResult(
            rule_name=rule.get("name", "Key Match"),
            rule_type="key_match",
            passed=passed,
            message=f"Missing keys: {len(missing)}" + (f" -> {missing}" if missing else ""),
            details={"missing_keys": list(missing)},
        )

    def _check_column_match(self, rule: dict, source_key: str, target_key: str) -> RuleResult:
        """Compare column values between source and target."""
        source_col = rule.get("source_column", "")
        target_col = rule.get("target_column", "")
        tolerance = rule.get("tolerance_percent", 0) / 100

        merged = self.source_df.merge(
            self.target_df,
            left_on=source_key,
            right_on=target_key,
            suffixes=("_src", "_tgt"),
        )

        src_vals = merged[f"{source_col}_src"] if f"{source_col}_src" in merged.columns else merged[source_col]
        tgt_vals = merged[f"{target_col}_tgt"] if f"{target_col}_tgt" in merged.columns else merged[target_col]

        if rule.get("data_type") == "numeric":
            mismatches = abs(src_vals - tgt_vals) > (abs(src_vals) * tolerance)
        elif rule.get("case_sensitive", True):
            mismatches = src_vals != tgt_vals
        else:
            mismatches = src_vals.str.lower() != tgt_vals.str.lower()

        mismatch_count = mismatches.sum()
        passed = mismatch_count == 0

        return RuleResult(
            rule_name=rule.get("name", f"Column Match: {source_col}"),
            rule_type="column_match",
            passed=passed,
            message=f"{mismatch_count} mismatches in '{source_col}' out of {len(merged)} rows",
            details={"mismatches": int(mismatch_count), "total": len(merged)},
        )

    def _check_derived_column(self, rule: dict, source_key: str, target_key: str) -> RuleResult:
        """Validate a derived/computed column in the target."""
        target_col = rule.get("target_column", "")
        formula = rule.get("formula", "")
        tolerance = rule.get("tolerance_percent", 0) / 100

        merged = self.source_df.merge(
            self.target_df,
            left_on=source_key,
            right_on=target_key,
            suffixes=("_src", "_tgt"),
        )

        # Evaluate the formula (e.g., "quantity * unit_price")
        try:
            # Use source columns for the formula
            computed = merged.eval(formula.replace(
                "quantity", "quantity_src"
            ).replace(
                "unit_price", "unit_price_src"
            ))
        except Exception:
            computed = merged.eval(formula)

        target_vals = merged[f"{target_col}_tgt"] if f"{target_col}_tgt" in merged.columns else merged[target_col]
        mismatches = abs(computed - target_vals) > (abs(computed) * tolerance)
        mismatch_count = mismatches.sum()

        return RuleResult(
            rule_name=rule.get("name", f"Derived: {target_col}"),
            rule_type="derived_column",
            passed=mismatch_count == 0,
            message=f"{mismatch_count} mismatches in derived column '{target_col}'",
            details={"mismatches": int(mismatch_count), "formula": formula},
        )

    def _check_column_format(self, rule: dict) -> RuleResult:
        """Validate column format (dates, patterns)."""
        target_col = rule.get("target_column", "")
        expected_format = rule.get("expected_format", "")

        column = self.target_df[target_col]

        if "YYYY-MM-DD" in expected_format:
            try:
                pd.to_datetime(column, format="%Y-%m-%d")
                invalid_count = 0
            except Exception:
                invalid_count = column.apply(
                    lambda x: pd.to_datetime(x, format="%Y-%m-%d", errors="coerce")
                ).isna().sum()
        else:
            invalid_count = 0

        return RuleResult(
            rule_name=rule.get("name", f"Format: {target_col}"),
            rule_type="column_format",
            passed=invalid_count == 0,
            message=f"{invalid_count} invalid format entries in '{target_col}'",
            details={"invalid_count": int(invalid_count), "expected_format": expected_format},
        )
