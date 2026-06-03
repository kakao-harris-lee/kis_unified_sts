#!/usr/bin/env python3
"""
Performance Regression Checker

Compares current performance test results against baseline metrics to detect regressions.
Exits with non-zero code if performance has degraded beyond acceptable thresholds.

Usage:
    python scripts/performance/check_regression.py --baseline tests/performance/baselines.json --current tests/performance/baselines.json
    python scripts/performance/check_regression.py --baseline baseline.json --current current.json --warning-threshold 1.2 --error-threshold 1.5
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Minimum number of comparable (non-exempt) tests required before median
# runner-speed normalization kicks in. Below this the median is too unstable,
# so we fall back to raw ratios (factor 1.0).
MIN_NORMALIZATION_SAMPLES = 5


@dataclass
class MetricComparison:
    """Comparison result for a single metric."""

    test_name: str
    metric_name: str
    baseline_value: float
    current_value: float
    change_percent: float
    status: str  # "pass", "warning", "error"
    message: str


class RegressionChecker:
    """Check for performance regressions by comparing test results."""

    def __init__(
        self,
        warning_threshold: float = 1.2,
        error_threshold: float = 1.5,
        min_duration: float = 0.0,
        logger: logging.Logger | None = None,
    ):
        """
        Initialize regression checker.

        Args:
            warning_threshold: Threshold for warning (e.g., 1.2 = 20% degradation)
            error_threshold: Threshold for error (e.g., 1.5 = 50% degradation)
            min_duration: Tests whose baseline duration is below this many
                seconds are exempt from ratio checks. Wall-clock durations in
                the sub-tens-of-ms range are dominated by scheduler/CPU noise on
                shared CI runners, so their ratios are meaningless (a 0.4ms test
                hitting 0.6ms is "+50%" but not a real regression).
            logger: Optional logger instance
        """
        self.warning_threshold = warning_threshold
        self.error_threshold = error_threshold
        self.min_duration = min_duration
        self.logger = logger or logging.getLogger(__name__)

    def load_metrics(self, json_path: Path) -> dict[str, Any]:
        """
        Load metrics from pytest-json-report output.

        Args:
            json_path: Path to JSON report file

        Returns:
            Dictionary of test metrics

        Raises:
            FileNotFoundError: If JSON file doesn't exist
            json.JSONDecodeError: If JSON is invalid
        """
        if not json_path.exists():
            raise FileNotFoundError(f"Metrics file not found: {json_path}")

        with open(json_path) as f:
            data = json.load(f)

        self.logger.info(
            "Loaded metrics from %s: %d tests, %d passed, %d skipped",
            json_path,
            data.get("summary", {}).get("total", 0),
            data.get("summary", {}).get("passed", 0),
            data.get("summary", {}).get("skipped", 0),
        )

        return data

    def extract_test_durations(self, metrics: dict[str, Any]) -> dict[str, float]:
        """
        Extract test durations from metrics.

        Args:
            metrics: Metrics dictionary from pytest-json-report

        Returns:
            Dictionary mapping test_nodeid to total duration
        """
        durations = {}

        for test in metrics.get("tests", []):
            if test.get("outcome") != "passed":
                # Skip failed or skipped tests
                continue

            nodeid = test.get("nodeid", "")
            if not nodeid:
                continue

            # Sum up setup + call + teardown durations
            total_duration = 0.0
            for phase in ["setup", "call", "teardown"]:
                phase_data = test.get(phase, {})
                if isinstance(phase_data, dict):
                    total_duration += phase_data.get("duration", 0.0)

            durations[nodeid] = total_duration

        return durations

    def runner_speed_factor(
        self,
        baseline_metrics: dict[str, float],
        current_metrics: dict[str, float],
    ) -> float:
        """Estimate the runner's common-mode speed relative to the baseline run.

        A shared GitHub-hosted runner can be globally slower (or faster) than the
        instance the baseline was captured on, which shifts *every* test's
        current/baseline ratio in the same direction together. Dividing each
        ratio by this common factor before thresholding separates "this test
        regressed" from "this whole runner is slow" — the latter being the
        dominant source of flaky failures on shared CI.

        The factor is the median current/baseline ratio across all comparable
        tests (present in both runs, baseline at or above the noise floor). The
        median is robust: a minority of genuinely regressed tests barely moves
        it, so real regressions still stand out after normalization. Returns 1.0
        (no normalization) when there are too few samples to be stable.

        Args:
            baseline_metrics: Baseline test durations
            current_metrics: Current test durations

        Returns:
            Median runner-speed ratio, or 1.0 when below the sample floor.
        """
        ratios = [
            current_metrics[name] / base
            for name, base in baseline_metrics.items()
            if base >= self.min_duration
            and base > 0
            and current_metrics.get(name, 0.0) > 0
        ]
        if len(ratios) < MIN_NORMALIZATION_SAMPLES:
            return 1.0
        return statistics.median(ratios)

    def compare_metrics(
        self,
        baseline_metrics: dict[str, float],
        current_metrics: dict[str, float],
        runner_factor: float = 1.0,
    ) -> list[MetricComparison]:
        """
        Compare baseline and current metrics.

        Args:
            baseline_metrics: Baseline test durations
            current_metrics: Current test durations
            runner_factor: Common-mode runner-speed ratio to divide out before
                applying thresholds (see ``runner_speed_factor``). 1.0 disables
                normalization.

        Returns:
            List of metric comparisons
        """
        comparisons = []

        # Check all baseline tests
        for test_name, baseline_value in baseline_metrics.items():
            if test_name not in current_metrics:
                # Test missing in current run
                comparisons.append(
                    MetricComparison(
                        test_name=test_name,
                        metric_name="duration",
                        baseline_value=baseline_value,
                        current_value=0.0,
                        change_percent=0.0,
                        status="warning",
                        message="Test not found in current results",
                    )
                )
                continue

            current_value = current_metrics[test_name]

            # Calculate percentage change
            # Positive change means performance degradation (slower)
            if baseline_value > 0:
                ratio = current_value / baseline_value
                change_percent = (ratio - 1.0) * 100
            else:
                ratio = 1.0
                change_percent = 0.0

            # Exempt sub-floor tests: their wall-clock durations are too small
            # for the ratio to be meaningful (noise-dominated on shared CI).
            if 0 < baseline_value < self.min_duration:
                comparisons.append(
                    MetricComparison(
                        test_name=test_name,
                        metric_name="duration",
                        baseline_value=baseline_value,
                        current_value=current_value,
                        change_percent=change_percent,
                        status="pass",
                        message=(
                            f"BELOW FLOOR ({self.min_duration * 1000:.0f}ms): "
                            f"{change_percent:+.1f}% ignored (noise-dominated)"
                        ),
                    )
                )
                continue

            # Divide out the runner's common-mode speed before thresholding, so a
            # globally slow runner (every ratio shifted up together) does not
            # masquerade as a per-test regression.
            norm_ratio = ratio / runner_factor if runner_factor > 0 else ratio
            norm_change = (norm_ratio - 1.0) * 100
            normalized = abs(runner_factor - 1.0) >= 0.001
            suffix = (
                f" (raw {change_percent:+.1f}%, runner x{runner_factor:.2f})"
                if normalized
                else ""
            )

            # Determine status (thresholds apply to the runner-normalized ratio)
            if norm_ratio >= self.error_threshold:
                status = "error"
                message = (
                    f"REGRESSION: {norm_change:+.1f}% slower "
                    f"(threshold: {(self.error_threshold - 1) * 100:.0f}%){suffix}"
                )
            elif norm_ratio >= self.warning_threshold:
                status = "warning"
                message = (
                    f"WARNING: {norm_change:+.1f}% slower "
                    f"(threshold: {(self.warning_threshold - 1) * 100:.0f}%){suffix}"
                )
            else:
                status = "pass"
                if change_percent < -5:
                    message = f"IMPROVEMENT: {change_percent:+.1f}% faster"
                else:
                    message = f"OK: {change_percent:+.1f}% change"

            comparisons.append(
                MetricComparison(
                    test_name=test_name,
                    metric_name="duration",
                    baseline_value=baseline_value,
                    current_value=current_value,
                    change_percent=change_percent,
                    status=status,
                    message=message,
                )
            )

        # Check for new tests in current run
        for test_name in current_metrics:
            if test_name not in baseline_metrics:
                comparisons.append(
                    MetricComparison(
                        test_name=test_name,
                        metric_name="duration",
                        baseline_value=0.0,
                        current_value=current_metrics[test_name],
                        change_percent=0.0,
                        status="pass",
                        message="New test (not in baseline)",
                    )
                )

        return comparisons

    def print_report(
        self,
        comparisons: list[MetricComparison],
        runner_factor: float = 1.0,
    ) -> tuple[int, int, int]:
        """
        Print detailed regression report.

        Args:
            comparisons: List of metric comparisons
            runner_factor: Common-mode runner-speed ratio that was divided out
                (shown in the header when it deviates from 1.0).

        Returns:
            Tuple of (num_errors, num_warnings, num_passed)
        """
        num_errors = sum(1 for c in comparisons if c.status == "error")
        num_warnings = sum(1 for c in comparisons if c.status == "warning")
        num_passed = sum(1 for c in comparisons if c.status == "pass")

        print("\n" + "=" * 80)
        print("PERFORMANCE REGRESSION REPORT")
        print("=" * 80)
        print(
            f"Total: {len(comparisons)} tests | "
            f"Errors: {num_errors} | Warnings: {num_warnings} | Pass: {num_passed}"
        )
        if abs(runner_factor - 1.0) >= 0.001:
            print(
                f"Runner speed factor: x{runner_factor:.2f} "
                f"(durations normalized to this before thresholding)"
            )
        print("=" * 80)

        # Group by status
        errors = [c for c in comparisons if c.status == "error"]
        warnings = [c for c in comparisons if c.status == "warning"]
        improvements = [
            c for c in comparisons if c.status == "pass" and c.change_percent < -5
        ]
        stable = [
            c for c in comparisons if c.status == "pass" and c.change_percent >= -5
        ]

        # Print errors first
        if errors:
            print("\n🔴 ERRORS (Performance Regression):")
            print("-" * 80)
            for comp in sorted(errors, key=lambda x: x.change_percent, reverse=True):
                print(f"  {comp.test_name}")
                print(
                    f"    Baseline: {comp.baseline_value:.4f}s | "
                    f"Current: {comp.current_value:.4f}s | "
                    f"Change: {comp.change_percent:+.1f}%"
                )
                print(f"    {comp.message}")
                print()

        # Print warnings
        if warnings:
            print("\n⚠️  WARNINGS (Performance Degradation):")
            print("-" * 80)
            for comp in sorted(warnings, key=lambda x: x.change_percent, reverse=True):
                print(f"  {comp.test_name}")
                print(
                    f"    Baseline: {comp.baseline_value:.4f}s | "
                    f"Current: {comp.current_value:.4f}s | "
                    f"Change: {comp.change_percent:+.1f}%"
                )
                print(f"    {comp.message}")
                print()

        # Print improvements
        if improvements:
            print("\n✅ IMPROVEMENTS:")
            print("-" * 80)
            for comp in sorted(improvements, key=lambda x: x.change_percent):
                print(f"  {comp.test_name}")
                print(
                    f"    Baseline: {comp.baseline_value:.4f}s | "
                    f"Current: {comp.current_value:.4f}s | "
                    f"Change: {comp.change_percent:+.1f}%"
                )
                print()

        # Print summary of stable tests
        if stable:
            print(f"\n📊 STABLE: {len(stable)} tests with no significant change")

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(
            f"Thresholds: Warning={round((self.warning_threshold - 1) * 100)}%, Error={round((self.error_threshold - 1) * 100)}%"
        )

        if num_errors > 0:
            print(f"❌ FAILED: {num_errors} performance regression(s) detected")
            return num_errors, num_warnings, num_passed
        elif num_warnings > 0:
            print(f"⚠️  WARNING: {num_warnings} performance degradation(s) detected")
            return num_errors, num_warnings, num_passed
        else:
            print("✅ PASSED: No performance regressions detected")
            return num_errors, num_warnings, num_passed

    def check_regression(
        self,
        baseline_path: Path,
        current_path: Path,
    ) -> int:
        """
        Check for performance regressions.

        Args:
            baseline_path: Path to baseline metrics JSON
            current_path: Path to current metrics JSON

        Returns:
            Exit code (0 = pass, 1 = warning, 2 = error)
        """
        try:
            # Load metrics
            baseline_data = self.load_metrics(baseline_path)
            current_data = self.load_metrics(current_path)

            # Extract test durations
            baseline_durations = self.extract_test_durations(baseline_data)
            current_durations = self.extract_test_durations(current_data)

            self.logger.info(
                "Comparing %d baseline tests vs %d current tests",
                len(baseline_durations),
                len(current_durations),
            )

            # Estimate the runner's common-mode speed and divide it out, so a
            # globally slow CI runner does not masquerade as a regression.
            runner_factor = self.runner_speed_factor(
                baseline_durations, current_durations
            )
            self.logger.info("Runner speed factor (median ratio): x%.3f", runner_factor)

            # Compare metrics
            comparisons = self.compare_metrics(
                baseline_durations, current_durations, runner_factor
            )

            # Print report
            num_errors, num_warnings, num_passed = self.print_report(
                comparisons, runner_factor
            )

            # Determine exit code
            if num_errors > 0:
                self.logger.error(
                    "Performance regression detected (%d errors)", num_errors
                )
                return 2
            elif num_warnings > 0:
                self.logger.warning(
                    "Performance degradation detected (%d warnings)", num_warnings
                )
                return 1
            else:
                self.logger.info("No performance regressions detected")
                return 0

        except Exception as e:
            self.logger.error("Error checking regression: %s", e, exc_info=True)
            print(f"\n❌ ERROR: {e}")
            return 2


def configure_logger() -> logging.Logger:
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    return logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Check for performance regressions by comparing test results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare current results against baseline
  python scripts/performance/check_regression.py \\
      --baseline tests/performance/baselines.json \\
      --current tests/performance/current.json

  # Use custom thresholds
  python scripts/performance/check_regression.py \\
      --baseline baseline.json \\
      --current current.json \\
      --warning-threshold 1.3 \\
      --error-threshold 2.0

Exit Codes:
  0 - No regressions detected
  1 - Performance degradation (warnings)
  2 - Performance regression (errors)
        """,
    )

    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Path to baseline metrics JSON file (pytest-json-report format)",
    )

    parser.add_argument(
        "--current",
        type=Path,
        required=True,
        help="Path to current metrics JSON file (pytest-json-report format)",
    )

    parser.add_argument(
        "--warning-threshold",
        type=float,
        default=1.2,
        help="Warning threshold multiplier (default: 1.2 = 20%% degradation)",
    )

    parser.add_argument(
        "--error-threshold",
        type=float,
        default=1.5,
        help="Error threshold multiplier (default: 1.5 = 50%% degradation)",
    )

    parser.add_argument(
        "--min-duration",
        type=float,
        default=0.0,
        help=(
            "Exempt tests whose baseline duration is below this many seconds "
            "from ratio checks (default: 0.0 = check all). Sub-tens-of-ms "
            "durations are noise-dominated on shared CI runners."
        ),
    )

    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help=(
            "Exit non-zero (1) when there are warnings. By default only errors "
            "(exit 2) fail the run; warnings are informational, so transient CI "
            "variance does not break the build."
        ),
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Configure logging
    logger = configure_logger()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Create checker
    checker = RegressionChecker(
        warning_threshold=args.warning_threshold,
        error_threshold=args.error_threshold,
        min_duration=args.min_duration,
        logger=logger,
    )

    # Check for regressions. check_regression() returns 2 (errors), 1 (warnings),
    # or 0. Warnings are informational by default so transient CI runner variance
    # does not fail the build — only real regressions (errors) do.
    exit_code = checker.check_regression(args.baseline, args.current)
    if exit_code == 1 and not args.fail_on_warning:
        return 0
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
