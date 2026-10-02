#!/usr/bin/env python3
"""
Performance Regression Checker

Compares current performance test results against a baseline and fails the build
when a benchmark has genuinely regressed.

Why medians of N rounds (2026-10-02, issues #768 / #796)
--------------------------------------------------------
The original check compared ONE sample of each benchmark against ONE committed
baseline sample. Re-running the `performance` job 10x on a fixed head (identical
code) gave, for ``test_entry_path_100_symbols``:

    n=7 usable | min 0.1217s | median 0.2755s | max 0.3800s | sd 0.0842s
    baseline (2026-05-30, a single sample): 0.1329s
    -> 3.1x spread; 3 of 10 jobs red with byte-identical code.

(#768's comment quotes sd 0.078 for the same seven points: that is the
population sd. This file reports the sample sd, ``statistics.stdev``.)

Two things are wrong, and they are not the same thing:

1. The *current* value was one draw, and that draw always carried the cold first
   round (see the phase table below).
2. The *baseline* is also one draw, with no recorded spread, so whatever offset
   it carries is arbitrary.

So this script compares the MEDIAN of N current rounds against the MEDIAN of the
baseline's rounds, and records n/min/max/sd so a reader can see the spread
instead of guessing at it. Both input shapes are accepted (``extract_samples``):
a legacy single-run pytest-json-report still works, read as n=1, and the report
then carries an explicit single-sample warning.

What the spread actually was (measured 2026-10-02, PR #842 CI run 36953158113)
------------------------------------------------------------------------------
Five rounds in one job, per phase, for ``test_entry_path_100_symbols``:

    round   setup     call      total
    1       0.2138s   0.1102s   0.3241s   <- cold
    2       0.0182s   0.1087s   0.1271s
    3       0.0180s   0.1085s   0.1266s
    4       0.0180s   0.1072s   0.1254s
    5       0.0182s   0.1063s   0.1248s

``call`` -- the part that actually runs the benchmark -- spans 3.7%. The whole
spread is in ``setup``: 12x between the first round and the rest. This test is
the first of the session, so it absorbs one-time process warm-up in its own
setup phase, and ``extract_test_durations`` SUMS setup + call + teardown. The
old check ran pytest once, so it bought that cold setup every single time, and
how expensive the cold setup is varies by runner (0.03s on the 2026-05-30
baseline runner, 0.21s here). That is where #768's 3.1x came from: cold-start
variance, not benchmark variance.

Taking the median of N rounds pushes the cold round to 1-in-N and drops it.
Measured consequence: with the SAME 2026-05-30 single-sample baseline, the
median of 5 rounds reads -4.7%, and the job is green.

Comparing call-only would remove the cold-start component at the source. It is
deliberately not done here: the median already removes the symptom, and
changing the metric would invalidate every existing baseline entry at the same
time as everything else changed.

What repetition does and does not fix
-------------------------------------
Repeating inside one job shrinks the *within-job* component of the noise (the
cold round above, an unlucky GC, a scheduler hiccup). It does NOT shrink the
*between-runner* component: all N rounds share one runner, so a globally slow
runner shifts all of them together. That component is what
``runner_speed_factor`` targets, and what a multi-sample baseline keeps from
being an arbitrary offset.

Runner-speed normalization (#397) and its measured limit
--------------------------------------------------------
``runner_speed_factor`` divides out the median current/baseline ratio across all
comparable benchmarks, so a uniformly slow runner does not read as a per-test
regression. The direction is right, but it does not absorb this benchmark's
spread: on 2026-10-01 two runs with nearly identical RAW values landed 63 points
apart after correction.

    raw +152.3%  runner x1.12  ->  +126.0%   (run 36868546962)
    raw +153.9%  runner x0.88  ->  +189.6%   (run 36876551928)

The factor is estimated from the same noisy samples it corrects, so at n=1 per
benchmark it injects variance of its own. Medians of N rounds are what damp
that; the factor is kept because the common-mode effect it targets is real.

Usage:
    # Compare 5 in-job rounds against the committed baseline
    python scripts/performance/check_regression.py \
        --baseline tests/performance/baselines.json \
        --current tests/performance/rounds/round-*.json \
        --write-samples tests/performance/current.json

    # Regenerate a baseline from a samples file with n >= 5
    python scripts/performance/check_regression.py \
        --current tests/performance/current.json \
        --write-baseline tests/performance/baselines.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import statistics
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

# Minimum number of comparable (non-exempt) tests required before median
# runner-speed normalization kicks in. Below this the median is too unstable,
# so we fall back to raw ratios (factor 1.0).
MIN_NORMALIZATION_SAMPLES = 5

# Minimum rounds a baseline must be built from. A single-sample baseline is one
# draw from a wide distribution -- exactly the defect #768 traced -- so writing
# one requires --force-baseline and says so in the file's provenance.
DEFAULT_MIN_BASELINE_ROUNDS = 5

# Schema marker for the multi-sample format this script reads and writes.
SAMPLES_SCHEMA = "kis-perf-samples/v1"

# Provenance fields that describe WHERE a measurement was taken. When samples
# are re-aggregated on a different machine (the usual case: CI runner measures,
# a human's checkout writes the baseline), these are inherited from the source
# so the file does not claim the aggregating machine produced the numbers.
MEASUREMENT_PROVENANCE_KEYS = (
    "generated_at",
    "timezone",
    "runner",
    "cpu_count",
    "python",
    "platform",
    "commit",
    "repository",
    "workflow_run",
)

# Project rule: timestamps are KST-native (CLAUDE.md, "Timezone: KST ONLY").
KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class BenchmarkStats:
    """Per-benchmark sample set and its summary statistics.

    ``samples`` holds one wall-clock duration (seconds) per round. Everything
    downstream compares ``median``; ``n``/``minimum``/``maximum``/``stdev``
    exist so a report reader can see how wide the measurement was rather than
    inferring stability from a single number.
    """

    samples: tuple[float, ...]

    @classmethod
    def from_values(cls, values: Iterable[float]) -> BenchmarkStats:
        return cls(tuple(float(v) for v in values))

    @property
    def n(self) -> int:
        return len(self.samples)

    @property
    def median(self) -> float:
        return statistics.median(self.samples) if self.samples else 0.0

    @property
    def minimum(self) -> float:
        return min(self.samples) if self.samples else 0.0

    @property
    def maximum(self) -> float:
        return max(self.samples) if self.samples else 0.0

    @property
    def mean(self) -> float:
        return statistics.fmean(self.samples) if self.samples else 0.0

    @property
    def stdev(self) -> float:
        # statistics.stdev needs at least two points; a single round has no
        # measurable spread (which is the problem, not a reason to pretend).
        return statistics.stdev(self.samples) if self.n >= 2 else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "median": self.median,
            "min": self.minimum,
            "max": self.maximum,
            "mean": self.mean,
            "sd": self.stdev,
            "samples": list(self.samples),
        }


def _as_stats(value: BenchmarkStats | float | int | Sequence[float]) -> BenchmarkStats:
    """Coerce a duration, a sample sequence, or stats into ``BenchmarkStats``.

    Callers that still pass plain ``dict[str, float]`` (the pre-2026-10 API)
    keep working: a bare float is read as a one-round sample set.
    """
    if isinstance(value, BenchmarkStats):
        return value
    if isinstance(value, (int, float)):
        return BenchmarkStats.from_values([float(value)])
    return BenchmarkStats.from_values(value)


def _as_stats_map(
    metrics: dict[str, BenchmarkStats | float | int | Sequence[float]],
) -> dict[str, BenchmarkStats]:
    return {name: _as_stats(value) for name, value in metrics.items()}


@dataclass
class MetricComparison:
    """Comparison result for a single metric.

    ``baseline_value`` / ``current_value`` are the MEDIANS of their sample sets
    (identical to the raw value when n=1), so the field meaning is unchanged for
    legacy single-sample inputs.
    """

    test_name: str
    metric_name: str
    baseline_value: float
    current_value: float
    change_percent: float
    status: str  # "pass", "warning", "error"
    message: str
    baseline_n: int = 1
    current_n: int = 1
    baseline_min: float = 0.0
    baseline_max: float = 0.0
    current_min: float = 0.0
    current_max: float = 0.0
    current_sd: float = 0.0
    normalized_change_percent: float = 0.0


@dataclass
class SampleSource:
    """Where one loaded sample file came from, for provenance reporting."""

    path: Path
    kind: str  # "pytest-json-report" or "samples"
    rounds: int
    provenance: dict[str, Any] = field(default_factory=dict)


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
            min_duration: Tests whose baseline median duration is below this many
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

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_metrics(self, json_path: Path) -> dict[str, Any]:
        """
        Load a metrics document (pytest-json-report or perf-samples).

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

        if isinstance(data, dict) and data.get("schema") == SAMPLES_SCHEMA:
            benchmarks = data.get("benchmarks") or {}
            rounds = data.get("provenance", {}).get("rounds")
            self.logger.info(
                "Loaded samples from %s: %d benchmarks, rounds=%s",
                json_path,
                len(benchmarks),
                rounds,
            )
        else:
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
        Extract test durations from a pytest-json-report document.

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

    def extract_samples(self, metrics: dict[str, Any]) -> dict[str, list[float]]:
        """Extract per-benchmark sample arrays from either supported format.

        A ``kis-perf-samples/v1`` document carries its rounds explicitly. A
        pytest-json-report is one round, so every benchmark yields a one-element
        array -- which is how a legacy baseline keeps working while still being
        visibly n=1 in the report.
        """
        if isinstance(metrics, dict) and metrics.get("schema") == SAMPLES_SCHEMA:
            samples: dict[str, list[float]] = {}
            for name, entry in (metrics.get("benchmarks") or {}).items():
                raw = (entry or {}).get("samples")
                if not raw:
                    raise ValueError(
                        f"{SAMPLES_SCHEMA} entry '{name}' has no 'samples' array; "
                        "the file cannot be used (medians must come from real "
                        "samples, not from a stored summary)"
                    )
                samples[name] = [float(v) for v in raw]
            return samples

        return {
            name: [value]
            for name, value in self.extract_test_durations(metrics).items()
        }

    def load_sample_sets(
        self, paths: Sequence[Path]
    ) -> tuple[dict[str, BenchmarkStats], list[SampleSource]]:
        """Load and merge one or more report/samples files into sample arrays.

        Several ``--current round-1.json round-2.json ...`` files merge into one
        sample array per benchmark; a single samples file is used as-is.
        """
        merged: dict[str, list[float]] = {}
        sources: list[SampleSource] = []

        for path in paths:
            data = self.load_metrics(path)
            is_samples = isinstance(data, dict) and data.get("schema") == SAMPLES_SCHEMA
            per_file = self.extract_samples(data)
            for name, values in per_file.items():
                merged.setdefault(name, []).extend(values)
            sources.append(
                SampleSource(
                    path=path,
                    kind="samples" if is_samples else "pytest-json-report",
                    rounds=max((len(v) for v in per_file.values()), default=0),
                    provenance=data.get("provenance", {}) if is_samples else {},
                )
            )

        stats = {name: BenchmarkStats.from_values(v) for name, v in merged.items()}
        return stats, sources

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def runner_speed_factor(
        self,
        baseline_metrics: dict[str, Any],
        current_metrics: dict[str, Any],
    ) -> float:
        """Estimate the runner's common-mode speed relative to the baseline run.

        A shared GitHub-hosted runner can be globally slower (or faster) than the
        instance the baseline was captured on, which shifts *every* test's
        current/baseline ratio in the same direction together. Dividing each
        ratio by this common factor before thresholding separates "this test
        regressed" from "this whole runner is slow" -- the latter being a real
        source of flaky failures on shared CI.

        The factor is the median current/baseline ratio of MEDIANS across all
        comparable tests (present in both runs, baseline at or above the noise
        floor). The median is robust: a minority of genuinely regressed tests
        barely moves it, so real regressions still stand out after
        normalization. Returns 1.0 (no normalization) when there are too few
        samples to be stable.

        Known limit (measured 2026-10-01, see the module docstring): with n=1 per
        benchmark the factor is itself estimated from noise, and two runs with
        nearly identical raw values came out 63 points apart after correction.
        Medians of N rounds reduce that; the factor alone does not.

        Args:
            baseline_metrics: Baseline durations or ``BenchmarkStats``
            current_metrics: Current durations or ``BenchmarkStats``

        Returns:
            Median runner-speed ratio, or 1.0 when below the sample floor.
        """
        baseline = _as_stats_map(baseline_metrics)
        current = _as_stats_map(current_metrics)

        ratios = []
        for name, base in baseline.items():
            cur = current.get(name)
            if cur is None:
                continue
            if base.median >= self.min_duration and base.median > 0 and cur.median > 0:
                ratios.append(cur.median / base.median)

        if len(ratios) < MIN_NORMALIZATION_SAMPLES:
            return 1.0
        return statistics.median(ratios)

    def compare_metrics(
        self,
        baseline_metrics: dict[str, Any],
        current_metrics: dict[str, Any],
        runner_factor: float = 1.0,
    ) -> list[MetricComparison]:
        """
        Compare baseline and current metrics, median against median.

        Args:
            baseline_metrics: Baseline durations or ``BenchmarkStats``
            current_metrics: Current durations or ``BenchmarkStats``
            runner_factor: Common-mode runner-speed ratio to divide out before
                applying thresholds (see ``runner_speed_factor``). 1.0 disables
                normalization.

        Returns:
            List of metric comparisons
        """
        baseline = _as_stats_map(baseline_metrics)
        current = _as_stats_map(current_metrics)
        comparisons = []

        # Check all baseline tests
        for test_name, base in baseline.items():
            baseline_value = base.median

            if test_name not in current:
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
                        baseline_n=base.n,
                        current_n=0,
                        baseline_min=base.minimum,
                        baseline_max=base.maximum,
                    )
                )
                continue

            cur = current[test_name]
            current_value = cur.median

            # Calculate percentage change
            # Positive change means performance degradation (slower)
            if baseline_value > 0:
                ratio = current_value / baseline_value
                change_percent = (ratio - 1.0) * 100
            else:
                ratio = 1.0
                change_percent = 0.0

            common = {
                "baseline_n": base.n,
                "current_n": cur.n,
                "baseline_min": base.minimum,
                "baseline_max": base.maximum,
                "current_min": cur.minimum,
                "current_max": cur.maximum,
                "current_sd": cur.stdev,
            }

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
                        normalized_change_percent=change_percent,
                        **common,
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

            # Determine status (thresholds apply to the runner-normalized ratio
            # of medians)
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
                    normalized_change_percent=norm_change,
                    **common,
                )
            )

        # Check for new tests in current run
        for test_name, cur in current.items():
            if test_name not in baseline:
                comparisons.append(
                    MetricComparison(
                        test_name=test_name,
                        metric_name="duration",
                        baseline_value=0.0,
                        current_value=cur.median,
                        change_percent=0.0,
                        status="pass",
                        message="New test (not in baseline)",
                        baseline_n=0,
                        current_n=cur.n,
                        current_min=cur.minimum,
                        current_max=cur.maximum,
                        current_sd=cur.stdev,
                    )
                )

        return comparisons

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    @staticmethod
    def single_sample_baselines(
        comparisons: Sequence[MetricComparison],
    ) -> list[MetricComparison]:
        """Comparisons whose BASELINE is a single sample (n=1).

        A one-shot baseline is one draw from the runner's distribution. #768
        measured what that costs: the committed 2026-05-30 baseline (0.1329s)
        sits near the bottom of the same runner's present-day distribution
        (median 0.2755s), so a median run reads as +107% with no code change.
        """
        return [c for c in comparisons if c.baseline_n == 1 and c.baseline_value > 0]

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

        baseline_rounds = sorted({c.baseline_n for c in comparisons if c.baseline_n})
        current_rounds = sorted({c.current_n for c in comparisons if c.current_n})

        print("\n" + "=" * 80)
        print("PERFORMANCE REGRESSION REPORT")
        print("=" * 80)
        print(
            f"Total: {len(comparisons)} tests | "
            f"Errors: {num_errors} | Warnings: {num_warnings} | Pass: {num_passed}"
        )
        print(
            f"Rounds per benchmark: baseline n={_fmt_rounds(baseline_rounds)} | "
            f"current n={_fmt_rounds(current_rounds)} "
            f"(medians are compared)"
        )
        if abs(runner_factor - 1.0) >= 0.001:
            print(
                f"Runner speed factor: x{runner_factor:.2f} "
                f"(durations normalized to this before thresholding)"
            )

        single = self.single_sample_baselines(comparisons)
        if single:
            self.logger.warning(
                "Baseline is a single sample (n=1) for %d of %d benchmarks",
                len(single),
                len(comparisons),
            )
            print("-" * 80)
            print(
                f"⚠️  SINGLE-SAMPLE BASELINE: n=1 for {len(single)} of "
                f"{len(comparisons)} benchmarks."
            )
            print(
                "    One draw from a wide distribution is not a baseline — it is "
                "a coin flip\n"
                "    with extra steps (#768). Regenerate from >=5 rounds:\n"
                "      check_regression.py --current <samples.json> "
                "--write-baseline tests/performance/baselines.json"
            )
        single_current = [c for c in comparisons if c.current_n == 1]
        if single_current:
            print(
                f"⚠️  SINGLE-SAMPLE CURRENT: n=1 for {len(single_current)} "
                f"benchmarks — pass several rounds to --current."
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
                _print_comparison(comp)

        # Print warnings
        if warnings:
            print("\n⚠️  WARNINGS (Performance Degradation):")
            print("-" * 80)
            for comp in sorted(warnings, key=lambda x: x.change_percent, reverse=True):
                _print_comparison(comp)

        # Print improvements
        if improvements:
            print("\n✅ IMPROVEMENTS:")
            print("-" * 80)
            for comp in sorted(improvements, key=lambda x: x.change_percent):
                _print_comparison(comp, with_message=False)

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

    def markdown_summary(
        self,
        comparisons: Sequence[MetricComparison],
        runner_factor: float = 1.0,
    ) -> str:
        """Render the comparison as a Markdown table (for $GITHUB_STEP_SUMMARY).

        The point of #768 is that nobody reads a red check they cannot interpret.
        The table puts n, median, min-max and sd next to the verdict so the
        reader can tell "this run was noisy" from "this benchmark regressed".
        """
        icons = {"error": "🔴", "warning": "⚠️", "pass": "✅"}
        lines = [
            "### Performance regression check",
            "",
            f"Runner speed factor: `x{runner_factor:.2f}` · "
            f"thresholds warn `{(self.warning_threshold - 1) * 100:.0f}%` / "
            f"error `{(self.error_threshold - 1) * 100:.0f}%` · medians compared",
            "",
            "| | Benchmark | base median (n) | cur median (n) | cur min–max | cur sd | change (norm) |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        order = {"error": 0, "warning": 1, "pass": 2}
        for comp in sorted(
            comparisons, key=lambda c: (order.get(c.status, 3), -c.change_percent)
        ):
            name = comp.test_name.replace("tests/performance/", "")
            if comp.current_n == 0:
                # Never measured in this run (missing, or failed in every
                # round). Printing 0.0000s here would read as "instant".
                lines.append(
                    f"| {icons.get(comp.status, '')} | `{name}` | "
                    f"{comp.baseline_value:.4f}s ({comp.baseline_n}) | "
                    "not run | – | – | – |"
                )
                continue
            baseline_cell = (
                f"{comp.baseline_value:.4f}s ({comp.baseline_n})"
                if comp.baseline_n
                else "new"
            )
            lines.append(
                f"| {icons.get(comp.status, '')} | `{name}` | "
                f"{baseline_cell} | "
                f"{comp.current_value:.4f}s ({comp.current_n}) | "
                f"{comp.current_min:.4f}–{comp.current_max:.4f}s | "
                f"{comp.current_sd:.4f}s | "
                f"{comp.change_percent:+.1f}% ({comp.normalized_change_percent:+.1f}%) |"
            )
        if self.single_sample_baselines(comparisons):
            lines += [
                "",
                "> ⚠️ The baseline is a **single sample** (n=1). Regenerate it from "
                ">=5 rounds — see `docs/performance_slas.md`.",
            ]
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Writing samples / baselines
    # ------------------------------------------------------------------

    def build_samples_document(
        self,
        stats: dict[str, BenchmarkStats],
        provenance: dict[str, Any],
    ) -> dict[str, Any]:
        """Assemble a ``kis-perf-samples/v1`` document."""
        return {
            "schema": SAMPLES_SCHEMA,
            "provenance": provenance,
            "benchmarks": {name: s.as_dict() for name, s in sorted(stats.items())},
        }

    def write_samples(
        self,
        path: Path,
        stats: dict[str, BenchmarkStats],
        role: str = "current",
        note: str = "",
        sources: Sequence[SampleSource] | None = None,
        measured_provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write the aggregated samples (with provenance) to ``path``.

        ``measured_provenance`` is the provenance of a samples file being
        re-aggregated. The usual baseline workflow measures on a CI runner and
        writes the file from a human's checkout, so without this the file would
        name the wrong machine -- and a baseline that misattributes its hardware
        is how #768 stayed undiagnosed for four months.
        """
        rounds = min((s.n for s in stats.values()), default=0)
        provenance = collect_provenance(rounds=rounds, role=role, note=note)
        if measured_provenance:
            inherited = {
                key: measured_provenance[key]
                for key in MEASUREMENT_PROVENANCE_KEYS
                if key in measured_provenance
            }
            provenance["aggregated_on"] = {
                "runner": provenance["runner"],
                "at": provenance["generated_at"],
            }
            provenance.update(inherited)
        if sources:
            provenance["sources"] = [s.path.name for s in sources]
        document = self.build_samples_document(stats, provenance)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(document, f, indent=2)
            f.write("\n")
        self.logger.info(
            "Wrote %s (%d benchmarks, rounds=%d) to %s",
            role,
            len(stats),
            rounds,
            path,
        )
        return document

    def write_baseline(
        self,
        path: Path,
        stats: dict[str, BenchmarkStats],
        min_rounds: int = DEFAULT_MIN_BASELINE_ROUNDS,
        force: bool = False,
        note: str = "",
        sources: Sequence[SampleSource] | None = None,
        measured_provenance: dict[str, Any] | None = None,
    ) -> bool:
        """Write a new baseline, refusing one that is too thinly sampled.

        Returns True when the baseline was written. A baseline built from fewer
        than ``min_rounds`` rounds is the exact defect #768 traced, so it is
        refused unless ``force`` is set (and the file then records that).
        """
        if not stats:
            print("\n❌ ERROR: refusing to write an empty baseline (no benchmarks)")
            self.logger.error("Refusing to write an empty baseline")
            return False

        rounds = min(s.n for s in stats.values())
        if rounds < min_rounds and not force:
            thin = sorted(
                ((name, st.n) for name, st in stats.items() if st.n < min_rounds),
                key=lambda item: item[1],
            )
            print(
                f"\n❌ ERROR: refusing to write a baseline from n={rounds} "
                f"round(s); {min_rounds} required.\n"
                "   A single-sample baseline is one draw from a wide "
                "distribution (#768).\n"
                f"   Under-sampled benchmarks ({len(thin)} of {len(stats)}) — a "
                "benchmark that FAILED in some rounds\n"
                "   contributes no sample for them:"
            )
            for name, n in thin[:10]:
                print(f"     n={n}  {name}")
            if len(thin) > 10:
                print(f"     ... and {len(thin) - 10} more")
            print(
                "   Re-measure with more rounds, or pass --force-baseline to "
                "record an under-sampled one."
            )
            self.logger.error(
                "Refusing to write baseline: rounds=%d < min_rounds=%d (%d "
                "under-sampled benchmarks)",
                rounds,
                min_rounds,
                len(thin),
            )
            return False

        full_note = note
        if rounds < min_rounds:
            warning = (
                f"UNDER-SAMPLED: written with --force-baseline from n={rounds} "
                f"rounds (minimum {min_rounds})."
            )
            full_note = f"{note} {warning}".strip()

        self.write_samples(
            path,
            stats,
            role="baseline",
            note=full_note,
            sources=sources,
            measured_provenance=measured_provenance,
        )
        print(f"\n📝 Baseline written to {path} (rounds={rounds})")
        print("   Per-benchmark statistics (paste into the PR body):")
        for name, s in sorted(stats.items()):
            print(
                f"   {name}\n"
                f"     n={s.n} median={s.median:.4f}s min={s.minimum:.4f}s "
                f"max={s.maximum:.4f}s sd={s.stdev:.4f}s"
            )
        return True

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def check_regression(
        self,
        baseline_path: Path | Sequence[Path] | None,
        current_path: Path | Sequence[Path],
        write_samples: Path | None = None,
        write_baseline: Path | None = None,
        min_baseline_rounds: int = DEFAULT_MIN_BASELINE_ROUNDS,
        force_baseline: bool = False,
        provenance_note: str = "",
        markdown_summary: Path | None = None,
    ) -> int:
        """
        Check for performance regressions.

        Args:
            baseline_path: Baseline metrics JSON (or several). ``None`` skips the
                comparison, which is only valid together with a write option.
            current_path: Current metrics JSON, or the N per-round reports to
                merge into one sample set per benchmark.
            write_samples: Write the aggregated current samples here.
            write_baseline: Write the aggregated current samples here as a new
                baseline (refused below ``min_baseline_rounds``).
            min_baseline_rounds: Rounds required to write a baseline.
            force_baseline: Write an under-sampled baseline anyway.
            provenance_note: Free-text note stored in written files.
            markdown_summary: Append a Markdown table of the comparison here.

        Returns:
            Exit code (0 = pass, 1 = warning, 2 = error)
        """
        try:
            current_paths = _as_paths(current_path)
            current_stats, current_sources = self.load_sample_sets(current_paths)

            # Only a single already-aggregated samples file carries an
            # unambiguous measurement machine. Merging several of them (possibly
            # from different runners) has none, so nothing is inherited.
            measured_provenance = None
            if len(current_sources) == 1 and current_sources[0].kind == "samples":
                measured_provenance = current_sources[0].provenance or None

            if write_samples is not None:
                self.write_samples(
                    write_samples,
                    current_stats,
                    role="current",
                    note=provenance_note,
                    sources=current_sources,
                    measured_provenance=measured_provenance,
                )

            if write_baseline is not None:
                written = self.write_baseline(
                    write_baseline,
                    current_stats,
                    min_rounds=min_baseline_rounds,
                    force=force_baseline,
                    note=provenance_note,
                    sources=current_sources,
                    measured_provenance=measured_provenance,
                )
                if not written:
                    return 2

            if baseline_path is None:
                self.logger.info("No baseline given; skipping comparison")
                return 0

            baseline_stats, _ = self.load_sample_sets(_as_paths(baseline_path))

            self.logger.info(
                "Comparing %d baseline tests vs %d current tests",
                len(baseline_stats),
                len(current_stats),
            )

            # Estimate the runner's common-mode speed and divide it out, so a
            # globally slow CI runner does not masquerade as a regression.
            runner_factor = self.runner_speed_factor(baseline_stats, current_stats)
            self.logger.info("Runner speed factor (median ratio): x%.3f", runner_factor)

            # Compare metrics
            comparisons = self.compare_metrics(
                baseline_stats, current_stats, runner_factor
            )

            # Print report
            num_errors, num_warnings, num_passed = self.print_report(
                comparisons, runner_factor
            )

            if markdown_summary is not None:
                markdown_summary.parent.mkdir(parents=True, exist_ok=True)
                with open(markdown_summary, "a") as f:
                    f.write(self.markdown_summary(comparisons, runner_factor))

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


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _optional_path(value: str) -> Path | None:
    """Treat an empty argument as absent.

    The documented CI command passes ``--markdown-summary "$GITHUB_STEP_SUMMARY"``.
    Copied into a local shell that variable is unset, and ``Path("")`` is
    ``Path(".")`` -- a directory, so writing to it raises and the whole check
    exits 2. Failing a regression check over a missing summary file is a
    papercut, not a signal.
    """
    value = value.strip()
    return Path(value) if value else None


def _as_paths(value: Path | Sequence[Path]) -> list[Path]:
    if isinstance(value, (str, Path)):
        return [Path(value)]
    return [Path(p) for p in value]


def _fmt_rounds(rounds: Sequence[int]) -> str:
    if not rounds:
        return "0"
    if len(rounds) == 1:
        return str(rounds[0])
    return f"{min(rounds)}-{max(rounds)}"


def _print_comparison(comp: MetricComparison, with_message: bool = True) -> None:
    print(f"  {comp.test_name}")
    print(
        f"    Baseline: {comp.baseline_value:.4f}s (n={comp.baseline_n}) | "
        f"Current: {comp.current_value:.4f}s (n={comp.current_n}) | "
        f"Change: {comp.change_percent:+.1f}%"
    )
    if comp.current_n > 1:
        print(
            f"    Current spread: min {comp.current_min:.4f}s / "
            f"max {comp.current_max:.4f}s / sd {comp.current_sd:.4f}s"
        )
    if with_message:
        print(f"    {comp.message}")
    print()


def _git_head() -> str:
    """Best-effort HEAD sha; empty string when git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _runner_label() -> str:
    """Identify the machine the samples were taken on.

    Baselines are only comparable against the same class of machine, so the
    label is part of the provenance a human checks before trusting a baseline.
    """
    if os.environ.get("GITHUB_ACTIONS") == "true":
        # ImageOS is GitHub's own spelling (e.g. "ubuntu24"); uppercasing it
        # would read a variable that does not exist.
        image = (
            os.environ.get("ImageOS")  # noqa: SIM112
            or os.environ.get("RUNNER_OS")
            or "unknown"
        )
        arch = os.environ.get("RUNNER_ARCH", "")
        return f"github-actions-{image}-{arch}".rstrip("-")
    return f"local-{platform.node()}"


def _workflow_run_url() -> str:
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return ""


def collect_provenance(
    rounds: int,
    role: str = "current",
    note: str = "",
) -> dict[str, Any]:
    """Describe where and when a sample set was taken.

    Without this a baseline is an unattributable number: #768 only became
    diagnosable because the 2026-05-30 file happened to record its hardware and
    source run.
    """
    return {
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "timezone": "Asia/Seoul",
        "role": role,
        "rounds": rounds,
        "runner": _runner_label(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "commit": os.environ.get("GITHUB_SHA") or _git_head(),
        "repository": os.environ.get("GITHUB_REPOSITORY", ""),
        "workflow_run": _workflow_run_url(),
        "note": note,
    }


def configure_logger() -> logging.Logger:
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    return logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Check for performance regressions by comparing test results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare N in-job rounds (medians) against the committed baseline
  python scripts/performance/check_regression.py \\
      --baseline tests/performance/baselines.json \\
      --current tests/performance/rounds/round-*.json \\
      --write-samples tests/performance/current.json

  # Use custom thresholds
  python scripts/performance/check_regression.py \\
      --baseline baseline.json \\
      --current current.json \\
      --warning-threshold 1.3 \\
      --error-threshold 2.0

  # Regenerate the baseline from a samples file with n >= 5
  python scripts/performance/check_regression.py \\
      --current tests/performance/current.json \\
      --write-baseline tests/performance/baselines.json

Exit Codes:
  0 - No regressions detected
  1 - Performance degradation (warnings)
  2 - Performance regression (errors), or a refused baseline write
        """,
    )

    parser.add_argument(
        "--baseline",
        type=Path,
        nargs="+",
        action="extend",
        default=None,
        help=(
            "Baseline metrics JSON (pytest-json-report or kis-perf-samples/v1). "
            "Optional only when --write-baseline/--write-samples is given."
        ),
    )

    parser.add_argument(
        "--current",
        type=Path,
        nargs="+",
        action="extend",
        required=True,
        help=(
            "Current metrics JSON. Pass the N per-round reports (e.g. "
            "rounds/round-*.json) to compare medians instead of one sample."
        ),
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
            "Exempt tests whose baseline median duration is below this many "
            "seconds from ratio checks (default: 0.0 = check all). Sub-tens-of-ms "
            "durations are noise-dominated on shared CI runners."
        ),
    )

    parser.add_argument(
        "--write-samples",
        type=_optional_path,
        default=None,
        help=(
            "Write the aggregated current samples (n/median/min/max/sd + "
            "provenance) to this path, for upload as a CI artifact."
        ),
    )

    parser.add_argument(
        "--write-baseline",
        type=_optional_path,
        default=None,
        help=(
            "Write the aggregated current samples to this path as a new "
            "baseline. Refused below --min-baseline-rounds."
        ),
    )

    parser.add_argument(
        "--min-baseline-rounds",
        type=int,
        default=DEFAULT_MIN_BASELINE_ROUNDS,
        help=(
            f"Rounds required to write a baseline (default: "
            f"{DEFAULT_MIN_BASELINE_ROUNDS})."
        ),
    )

    parser.add_argument(
        "--force-baseline",
        action="store_true",
        help=(
            "Write a baseline even below --min-baseline-rounds. The file records "
            "that it is under-sampled."
        ),
    )

    parser.add_argument(
        "--provenance-note",
        type=str,
        default="",
        help="Free-text note stored in the provenance of written files.",
    )

    parser.add_argument(
        "--markdown-summary",
        type=_optional_path,
        default=None,
        help=(
            "Append a Markdown table of the comparison to this file "
            "(e.g. $GITHUB_STEP_SUMMARY)."
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

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point."""
    args = parse_args(argv)

    # Configure logging
    logger = configure_logger()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    if (
        args.baseline is None
        and args.write_baseline is None
        and args.write_samples is None
    ):
        print(
            "\n❌ ERROR: --baseline is required unless --write-baseline or --write-samples is given"
        )
        return 2

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
    exit_code = checker.check_regression(
        args.baseline,
        args.current,
        write_samples=args.write_samples,
        write_baseline=args.write_baseline,
        min_baseline_rounds=args.min_baseline_rounds,
        force_baseline=args.force_baseline,
        provenance_note=args.provenance_note,
        markdown_summary=args.markdown_summary,
    )
    if exit_code == 1 and not args.fail_on_warning:
        return 0
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
