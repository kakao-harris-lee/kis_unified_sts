"""Unit tests for scripts/performance/check_regression.py.

Focus: the runner-speed normalization that divides out common-mode CI-runner
slowness (a globally slow shared runner shifts every test's current/baseline
ratio up together) before applying regression thresholds, so it does not
masquerade as a per-test regression — the dominant source of flaky perf
failures. Real single-test regressions must still be flagged.

The script is not an importable package, so it is loaded by file path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "performance"
    / "check_regression.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("check_regression", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass can resolve cls.__module__ in sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_crmod = _load_module()
RegressionChecker = _crmod.RegressionChecker
MIN_NORMALIZATION_SAMPLES = _crmod.MIN_NORMALIZATION_SAMPLES


def _checker() -> RegressionChecker:
    # Same thresholds the CI workflow uses.
    return RegressionChecker(
        warning_threshold=1.5, error_threshold=2.0, min_duration=0.05
    )


def _statuses(comparisons) -> dict[str, str]:
    return {c.test_name: c.status for c in comparisons}


class TestRunnerSpeedFactor:
    def test_is_median_of_comparable_ratios(self):
        checker = _checker()
        baseline = {f"t{i}": 0.10 for i in range(5)}
        # ratios 1.2, 1.3, 1.4, 1.5, 1.6 -> median 1.4
        current = {"t0": 0.12, "t1": 0.13, "t2": 0.14, "t3": 0.15, "t4": 0.16}
        assert checker.runner_speed_factor(baseline, current) == pytest.approx(1.4)

    def test_excludes_subfloor_and_missing_tests(self):
        checker = _checker()  # min_duration 0.05
        baseline = {
            "big0": 0.10,
            "big1": 0.10,
            "big2": 0.10,
            "big3": 0.10,
            "big4": 0.10,
            "tiny": 0.001,  # below the noise floor -> excluded
            "gone": 0.10,  # absent from current -> excluded
        }
        current = {
            "big0": 0.20,
            "big1": 0.20,
            "big2": 0.20,
            "big3": 0.20,
            "big4": 0.20,
            "tiny": 0.10,  # 100x, but sub-floor must not pull the factor
        }
        # Only the 5 above-floor tests (all 2.0x) count -> median 2.0.
        assert checker.runner_speed_factor(baseline, current) == pytest.approx(2.0)

    def test_falls_back_to_one_below_sample_floor(self):
        checker = _checker()
        n = MIN_NORMALIZATION_SAMPLES - 1
        baseline = {f"t{i}": 0.10 for i in range(n)}
        current = {f"t{i}": 0.20 for i in range(n)}
        assert checker.runner_speed_factor(baseline, current) == 1.0


class TestNormalizedRegressionGate:
    def test_globally_slow_runner_flags_nothing(self):
        """Every test 1.4x slower (slow runner, no real regression) -> all pass."""
        checker = _checker()
        baseline = {f"t{i}": 0.10 for i in range(8)}
        current = {f"t{i}": 0.14 for i in range(8)}
        factor = checker.runner_speed_factor(baseline, current)
        assert factor == pytest.approx(1.4)
        comps = checker.compare_metrics(baseline, current, factor)
        assert all(c.status == "pass" for c in comps)

    def test_single_genuine_regression_is_flagged(self):
        """One test 2.2x while the runner is otherwise normal -> error."""
        checker = _checker()
        baseline = {f"t{i}": 0.10 for i in range(8)}
        current = {f"t{i}": 0.10 for i in range(8)}
        current["t3"] = 0.22  # genuine 2.2x regression
        factor = checker.runner_speed_factor(baseline, current)
        assert factor == pytest.approx(1.0)  # median unmoved by one outlier
        statuses = _statuses(checker.compare_metrics(baseline, current, factor))
        assert statuses["t3"] == "error"
        assert all(s != "error" for k, s in statuses.items() if k != "t3")

    def test_slow_runner_plus_outlier_is_warning_not_error(self):
        """The #395 shape: runner ~1.15x slow + one CPU microbench at 2.25x.

        After dividing out the 1.15x common-mode factor the spike is ~1.96x — a
        non-fatal warning, not a build-failing error.
        """
        checker = _checker()
        ratios = [
            0.87,
            0.96,
            1.00,
            1.08,
            1.10,
            1.11,
            1.11,
            1.14,
            1.16,
            1.27,
            1.29,
            1.36,
            1.38,
            1.44,
            1.50,
        ]
        baseline = {f"t{i}": 0.10 for i in range(len(ratios))}
        current = {f"t{i}": 0.10 * r for i, r in enumerate(ratios)}
        spiker = "spiker"
        baseline[spiker] = 0.10
        current[spiker] = 0.10 * 2.25
        factor = checker.runner_speed_factor(baseline, current)
        assert factor == pytest.approx(1.15, abs=0.01)
        statuses = _statuses(checker.compare_metrics(baseline, current, factor))
        assert statuses[spiker] == "warning"  # 2.25/1.15 ~= 1.96 < 2.0
        assert all(s != "error" for s in statuses.values())

    def test_subfloor_regression_is_exempt(self):
        checker = _checker()
        baseline = {f"t{i}": 0.10 for i in range(5)}
        baseline["tiny"] = 0.001
        current = {f"t{i}": 0.10 for i in range(5)}
        current["tiny"] = 0.05  # 50x but below the floor
        factor = checker.runner_speed_factor(baseline, current)
        comps = checker.compare_metrics(baseline, current, factor)
        tiny = next(c for c in comps if c.test_name == "tiny")
        assert tiny.status == "pass"
        assert "BELOW FLOOR" in tiny.message


class TestExtractDurations:
    def test_sums_phases_for_passed_tests_only(self):
        checker = _checker()
        metrics = {
            "tests": [
                {
                    "nodeid": "a",
                    "outcome": "passed",
                    "setup": {"duration": 0.01},
                    "call": {"duration": 0.10},
                    "teardown": {"duration": 0.01},
                },
                {"nodeid": "b", "outcome": "failed", "call": {"duration": 0.5}},
                {"nodeid": "c", "outcome": "skipped"},
            ]
        }
        durations = checker.extract_test_durations(metrics)
        assert durations == {"a": pytest.approx(0.12)}
