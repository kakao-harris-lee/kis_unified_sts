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
import json
import statistics
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


# Two real measurements of ONE commit (586c7bc2 on PR #851 -- a config YAML plus
# four docs files, none of them imported by anything in tests/performance/),
# taken as attempt 1 and attempt 2 of CI run 37101956657, twelve minutes apart.
# Every pair is (baseline median, current median) in seconds for the benchmarks
# that clear the 0.05s noise floor, read from each attempt's uploaded
# performance-report artifact against tests/performance/baselines.json. The
# runner factor is NOT hardcoded in these tests: these numbers produce it.
_HOT = (
    "tests/performance/test_orchestrator_hot_path_benchmark.py"
    "::TestOrchestratorHotPathBenchmark"
)
_SCAL = (
    "tests/performance/test_orchestrator_scalability.py" "::TestOrchestratorScalability"
)
_REDIS = "tests/performance/test_redis_load.py::TestRedisPositionStateCRUD"
_WS = "tests/performance/test_websocket_load.py::TestWebSocketLoad"

# Attempt 1: fourteen of the sixteen ratios sit in x1.01-x1.13 and the
# orchestrator scalability pair sits at x2.59/x2.78; factor x1.066.
PERF_RUN_37101956657_ATTEMPT_1 = {
    f"{_HOT}::test_entry_path_scalability_200_symbols": (0.1085, 0.1095),
    f"{_HOT}::test_aggregate_cost_reduction": (0.1080, 0.1092),
    f"{_HOT}::test_entry_path_100_symbols": (0.1260, 0.1281),
    f"{_WS}::test_sustained_load_5000_msgs": (14.1957, 14.6135),
    f"{_WS}::test_end_to_end_latency_100_msgs": (1.0798, 1.1132),
    f"{_WS}::test_end_to_end_latency_500_msgs": (1.4172, 1.4637),
    f"{_WS}::test_peak_load_1000_msgs": (1.7524, 1.8276),
    f"{_WS}::test_publish_throughput_1000_messages": (0.4360, 0.4711),
    f"{_REDIS}::test_position_read_all_throughput": (0.5294, 0.5570),
    f"{_REDIS}::test_concurrent_access_10_workers": (0.4245, 0.4591),
    f"{_REDIS}::test_position_write_throughput": (2.1525, 2.3590),
    f"{_REDIS}::test_position_read_throughput": (2.0181, 2.2257),
    f"{_REDIS}::test_concurrent_access_50_workers": (1.0515, 1.1668),
    f"{_REDIS}::test_latency_percentiles": (0.4076, 0.4599),
    f"{_SCAL}::test_memory_usage_scaling": (0.0803, 0.2081),  # x2.591
    f"{_SCAL}::test_scalability_summary": (0.0806, 0.2239),  # x2.778
}

# Attempt 2, same commit: the ratios span x0.39-x1.10 in at least three
# clusters (redis x0.39-x0.49, hot path x0.53-x0.54, scalability x1.06-x1.10)
# and the median lands on the middle one; factor x0.533. The same two
# orchestrator benchmarks that read x2.59/x2.78 above read x1.10/x1.06 here,
# on byte-identical code.
PERF_RUN_37101956657_ATTEMPT_2 = {
    f"{_HOT}::test_entry_path_scalability_200_symbols": (0.1085, 0.0579),
    f"{_HOT}::test_aggregate_cost_reduction": (0.1080, 0.0576),
    f"{_HOT}::test_entry_path_100_symbols": (0.1260, 0.0686),
    f"{_WS}::test_sustained_load_5000_msgs": (14.1957, 11.8334),
    f"{_WS}::test_end_to_end_latency_100_msgs": (1.0798, 1.0423),  # x0.965
    f"{_WS}::test_end_to_end_latency_500_msgs": (1.4172, 1.1816),
    f"{_WS}::test_peak_load_1000_msgs": (1.7524, 1.3493),
    f"{_WS}::test_publish_throughput_1000_messages": (0.4360, 0.1837),
    f"{_REDIS}::test_position_read_all_throughput": (0.5294, 0.2616),
    f"{_REDIS}::test_concurrent_access_10_workers": (0.4245, 0.1974),
    f"{_REDIS}::test_position_write_throughput": (2.1525, 0.8682),
    f"{_REDIS}::test_position_read_throughput": (2.0181, 0.8456),
    f"{_REDIS}::test_concurrent_access_50_workers": (1.0515, 0.4873),
    f"{_REDIS}::test_latency_percentiles": (0.4076, 0.1602),  # x0.393
    f"{_SCAL}::test_memory_usage_scaling": (0.0803, 0.0885),  # x1.102
    f"{_SCAL}::test_scalability_summary": (0.0806, 0.0856),  # x1.062
}

_SCALING = f"{_SCAL}::test_memory_usage_scaling"
_SUMMARY = f"{_SCAL}::test_scalability_summary"
_WS_100 = f"{_WS}::test_end_to_end_latency_100_msgs"


def _split(fixture: dict[str, tuple[float, float]]):
    """(baseline map, current map) from a (baseline, current) fixture."""
    return (
        {k: v[0] for k, v in fixture.items()},
        {k: v[1] for k, v in fixture.items()},
    )


def _judge(fixture: dict[str, tuple[float, float]]):
    """Run the real checker over a fixture: (statuses, comparisons, factor)."""
    checker = _checker()
    baseline, current = _split(fixture)
    factor = checker.runner_speed_factor(baseline, current)
    comps = checker.compare_metrics(baseline, current, factor)
    return _statuses(comps), comps, factor


class TestErrorNeedsBothRatios:
    """An error needs the raw AND the normalized ratio over the threshold.

    A runner factor below 1.0 divides a small raw change UP, so thresholding
    the normalized ratio alone let the normalizer manufacture an error out of a
    benchmark that was inside the threshold on the wall clock. Both fixtures
    here are one commit measured twice (CI run 37101956657).
    """

    def test_attempt_2_reaches_the_old_rules_error_branch(self):
        """Red proof: the fixture must still trip the rule being replaced.

        Without this, ``test_attempt_2_is_a_warning_not_an_error`` below could
        pass because the fixture stopped being a counterexample -- a changed
        baseline, noise floor or factor -- rather than because the new rule
        works.
        """
        checker = _checker()
        baseline, current = _split(PERF_RUN_37101956657_ATTEMPT_2)
        factor = checker.runner_speed_factor(baseline, current)
        raw = current[_SCALING] / baseline[_SCALING]
        normalized = raw / factor

        assert factor == pytest.approx(0.533, abs=0.005)
        # The old rule thresholded this number alone -> error.
        assert normalized >= checker.error_threshold
        assert normalized == pytest.approx(2.066, abs=0.01)
        # The wall clock never came close to it.
        assert raw < checker.error_threshold
        assert raw == pytest.approx(1.102, abs=0.005)

    def test_attempt_2_is_a_warning_not_an_error(self):
        """raw +10.2% / normalized +106.6% on a x0.53 factor -> warning."""
        statuses, _, factor = _judge(PERF_RUN_37101956657_ATTEMPT_2)
        assert factor == pytest.approx(0.533, abs=0.005)
        assert statuses[_SCALING] == "warning"
        assert "error" not in statuses.values()

    def test_attempt_1_still_errors_because_both_ratios_breach(self):
        """raw +177.8% / normalized +160.5% on a x1.07 factor -> still error.

        The new rule must not acquit this one: the pair is 2.6x the baseline on
        the wall clock while the other fourteen comparable ratios sit inside
        x1.01-x1.13.
        """
        statuses, _, factor = _judge(PERF_RUN_37101956657_ATTEMPT_1)
        assert factor == pytest.approx(1.066, abs=0.005)
        assert statuses[_SUMMARY] == "error"
        assert statuses[_SCALING] == "error"
        assert sorted(n for n, s in statuses.items() if s == "error") == sorted(
            [_SCALING, _SUMMARY]
        )

    def test_the_normalized_only_warning_path_is_unchanged(self):
        """Not fixed here: a benchmark 3.5% FASTER still warns at "+81.0%".

        The warning path still fires off the normalized ratio alone. Pinned so
        the next reader sees the remaining defect instead of assuming this
        change closed it.
        """
        statuses, comps, _ = _judge(PERF_RUN_37101956657_ATTEMPT_2)
        ws = next(c for c in comps if c.test_name == _WS_100)
        assert ws.change_percent == pytest.approx(-3.5, abs=0.1)
        assert ws.normalized_change_percent == pytest.approx(81.0, abs=0.5)
        assert statuses[_WS_100] == "warning"

    def test_message_names_the_ratio_that_breached_alone(self):
        _, comps, _ = _judge(PERF_RUN_37101956657_ATTEMPT_2)
        message = next(c for c in comps if c.test_name == _SCALING).message
        assert "UNCONFIRMED REGRESSION" in message
        assert "only the normalized ratio" in message
        assert "+10.2%" in message and "+106.6%" in message

    def test_a_slow_runner_breaching_on_raw_alone_is_also_a_warning(self):
        """The other half of "one alone": raw over, normalized under.

        Eight benchmarks 2.5x slower together is one slow runner, not eight
        regressions, so the factor is 2.5 and every normalized ratio is 1.0.
        """
        checker = _checker()
        baseline = {f"t{i}": 0.10 for i in range(8)}
        current = {f"t{i}": 0.25 for i in range(8)}
        factor = checker.runner_speed_factor(baseline, current)
        assert factor == pytest.approx(2.5)
        comps = checker.compare_metrics(baseline, current, factor)
        assert {c.status for c in comps} == {"warning"}
        assert all("only the raw ratio" in c.message for c in comps)

    def test_rule_is_a_no_op_when_nothing_is_normalized(self):
        """factor 1.0 -> the two ratios are one number -> the old verdict."""
        checker = _checker()
        baseline = {f"t{i}": 0.10 for i in range(8)}
        current = {f"t{i}": 0.10 for i in range(8)}
        current["t3"] = 0.22
        factor = checker.runner_speed_factor(baseline, current)
        assert factor == pytest.approx(1.0)
        statuses = _statuses(checker.compare_metrics(baseline, current, factor))
        assert statuses["t3"] == "error"

    def test_a_real_regression_under_the_raw_threshold_can_only_warn(self):
        """The cost of the rule, pinned so it is not discovered by surprise.

        The raw ratio is now NECESSARY, so on a runner twice as fast as the
        baseline's a genuine 1.9x regression is a warning and the build stays
        green. Accepted: the alternative is convicting on an estimator whose
        own spread inside one run is x0.39-x1.10 (attempt 2 above).
        """
        checker = _checker()
        baseline = {f"t{i}": 0.10 for i in range(8)}
        current = {f"t{i}": 0.05 for i in range(8)}
        current["t3"] = 0.19  # 1.9x raw, 3.8x once normalized
        factor = checker.runner_speed_factor(baseline, current)
        assert factor == pytest.approx(0.5)
        comp = next(
            c
            for c in checker.compare_metrics(baseline, current, factor)
            if c.test_name == "t3"
        )
        assert comp.normalized_change_percent == pytest.approx(280.0, abs=0.5)
        assert comp.status == "warning"


class TestComparableRatioBand:
    def test_band_shows_the_factor_was_not_common_mode(self):
        """Attempt 2's ratios span 2.8x, so its median is not a runner speed."""
        checker = _checker()
        _, comps, _ = _judge(PERF_RUN_37101956657_ATTEMPT_2)
        low, high, count = checker.comparable_ratio_band(comps)
        assert count == 16
        assert low == pytest.approx(0.393, abs=0.005)
        assert high == pytest.approx(1.102, abs=0.005)

    def test_band_is_tight_when_the_factor_is_common_mode(self):
        """Attempt 1: fourteen of sixteen inside x1.01-x1.13, two outliers."""
        checker = _checker()
        _, comps, _ = _judge(PERF_RUN_37101956657_ATTEMPT_1)
        low, high, count = checker.comparable_ratio_band(comps)
        assert count == 16
        assert low == pytest.approx(1.009, abs=0.005)
        assert high == pytest.approx(2.778, abs=0.005)

    def test_band_excludes_subfloor_benchmarks(self):
        checker = _checker()
        baseline = {f"t{i}": 0.10 for i in range(5)}
        baseline["tiny"] = 0.001
        current = {f"t{i}": 0.10 for i in range(5)}
        current["tiny"] = 0.05  # 50x, below the floor
        comps = checker.compare_metrics(baseline, current, 1.0)
        low, high, count = checker.comparable_ratio_band(comps)
        assert (count, low, high) == (5, 1.0, 1.0)

    def test_band_is_none_without_comparable_benchmarks(self):
        assert _checker().comparable_ratio_band([]) is None


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


# ---------------------------------------------------------------------------
# Median-of-N comparison, multi-sample baselines, provenance (#768, #796)
#
# The numbers below are the measured ones from #768: 10 re-runs of the
# `performance` job on a fixed head gave min 0.1217s / median 0.2755s /
# max 0.3800s for test_entry_path_100_symbols against a committed single-sample
# baseline of 0.1329s. Every test here that uses those values is asserting
# behaviour on the distribution that actually broke the check.
# ---------------------------------------------------------------------------

BenchmarkStats = _crmod.BenchmarkStats
SAMPLES_SCHEMA = _crmod.SAMPLES_SCHEMA
DEFAULT_MIN_BASELINE_ROUNDS = _crmod.DEFAULT_MIN_BASELINE_ROUNDS
collect_provenance = _crmod.collect_provenance

# Observed distribution of test_entry_path_100_symbols, run 10x on one head.
MEASURED_ROUNDS = [0.2755, 0.1764, 0.1217, 0.3800, 0.2405, 0.2952, 0.2825]
MEASURED_MEDIAN = 0.2755
# Sample standard deviation (Bessel-corrected, what statistics.stdev returns).
# #768's comment quotes 0.078 for the same seven points: that is the POPULATION
# sd. The checker reports the sample sd because n is small and the quantity of
# interest is the underlying measurement spread, not these seven points alone.
MEASURED_SD = 0.0842
LEGACY_BASELINE = 0.1329


def _report(durations: dict[str, float]) -> dict:
    """Build a minimal pytest-json-report document."""
    return {
        "created": 0.0,
        "summary": {"total": len(durations), "passed": len(durations), "skipped": 0},
        "tests": [
            {
                "nodeid": nodeid,
                "outcome": "passed",
                "setup": {"duration": 0.0},
                "call": {"duration": duration},
                "teardown": {"duration": 0.0},
            }
            for nodeid, duration in durations.items()
        ],
    }


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload))
    return path


def _write_rounds(tmp_path: Path, per_round: list[dict[str, float]]) -> list[Path]:
    return [
        _write_json(tmp_path / f"round-{i}.json", _report(durations))
        for i, durations in enumerate(per_round, start=1)
    ]


def _stats(samples) -> BenchmarkStats:
    return BenchmarkStats.from_values(samples)


class TestBenchmarkStats:
    def test_summarises_a_sample_set(self):
        stats = _stats(MEASURED_ROUNDS)
        assert stats.n == 7
        assert stats.median == pytest.approx(MEASURED_MEDIAN)
        assert stats.minimum == pytest.approx(0.1217)
        assert stats.maximum == pytest.approx(0.3800)
        assert stats.mean == pytest.approx(0.253, abs=5e-4)
        assert stats.stdev == pytest.approx(MEASURED_SD, abs=5e-4)

    def test_single_sample_has_no_measurable_spread(self):
        stats = _stats([LEGACY_BASELINE])
        assert stats.n == 1
        assert stats.median == pytest.approx(LEGACY_BASELINE)
        assert stats.minimum == stats.maximum == pytest.approx(LEGACY_BASELINE)
        # Not "stable" — unmeasurable. The report says so separately.
        assert stats.stdev == 0.0

    def test_as_dict_carries_every_statistic_and_the_raw_samples(self):
        payload = _stats([0.1, 0.2, 0.3]).as_dict()
        assert set(payload) == {"n", "median", "min", "max", "mean", "sd", "samples"}
        assert payload["samples"] == [0.1, 0.2, 0.3]
        assert payload["n"] == 3


class TestSampleLoading:
    def test_legacy_single_report_reads_as_one_round(self, tmp_path):
        checker = _checker()
        path = _write_json(tmp_path / "baselines.json", _report({"a": LEGACY_BASELINE}))
        stats, sources, _ = checker.load_sample_sets([path])
        assert stats["a"].n == 1
        assert stats["a"].median == pytest.approx(LEGACY_BASELINE)
        assert sources[0].kind == "pytest-json-report"
        assert sources[0].rounds == 1

    def test_several_round_reports_merge_into_one_sample_set(self, tmp_path):
        checker = _checker()
        paths = _write_rounds(tmp_path, [{"a": v} for v in MEASURED_ROUNDS])
        stats, sources, _ = checker.load_sample_sets(paths)
        assert stats["a"].n == 7
        assert sorted(stats["a"].samples) == sorted(MEASURED_ROUNDS)
        assert stats["a"].median == pytest.approx(MEASURED_MEDIAN)
        assert len(sources) == 7

    def test_samples_document_round_trips(self, tmp_path):
        checker = _checker()
        document = checker.build_samples_document(
            {"a": _stats(MEASURED_ROUNDS)}, collect_provenance(rounds=7)
        )
        path = _write_json(tmp_path / "current.json", document)
        stats, sources, _ = checker.load_sample_sets([path])
        assert stats["a"].n == 7
        assert stats["a"].median == pytest.approx(MEASURED_MEDIAN)
        assert sources[0].kind == "samples"
        assert sources[0].provenance["rounds"] == 7

    def test_samples_entry_without_raw_samples_is_rejected(self, tmp_path):
        """A stored median with no samples behind it cannot be re-aggregated."""
        checker = _checker()
        path = _write_json(
            tmp_path / "bad.json",
            {
                "schema": SAMPLES_SCHEMA,
                "provenance": {"rounds": 5},
                "benchmarks": {"a": {"n": 5, "median": 0.2}},
            },
        )
        with pytest.raises(ValueError, match="no 'samples' array"):
            checker.load_sample_sets([path])


class TestMedianComparison:
    def test_one_outlier_round_does_not_trip_the_error_threshold(self):
        """The defect #768 describes: a single unlucky draw failed the build.

        Five rounds where one is 3x the rest have a median at the rest. The old
        checker, handed that one round as the whole measurement, errored.
        """
        checker = _checker()
        baseline = {f"t{i}": _stats([0.10]) for i in range(5)}
        current = {f"t{i}": _stats([0.10]) for i in range(5)}
        current["t0"] = _stats([0.10, 0.10, 0.10, 0.11, 0.38])

        comparisons = checker.compare_metrics(baseline, current)
        assert _statuses(comparisons)["t0"] == "pass"
        # The same sample set judged by its worst round would be an error.
        worst_round_ratio = 0.38 / 0.10
        assert worst_round_ratio >= checker.error_threshold

    def test_median_not_mean_decides(self):
        """A mean is not robust: one 100x round would drag it over the line."""
        checker = _checker()
        baseline = {f"t{i}": _stats([0.10]) for i in range(5)}
        current = {f"t{i}": _stats([0.10]) for i in range(5)}
        current["t0"] = _stats([0.10, 0.10, 0.10, 0.10, 10.0])

        comparisons = checker.compare_metrics(baseline, current)
        assert _statuses(comparisons)["t0"] == "pass"
        assert current["t0"].mean / 0.10 >= checker.error_threshold

    def test_multi_sample_baseline_removes_the_lucky_draw_offset(self):
        """#768's root offset: the baseline was the bottom of the distribution.

        Against the 2026-05-30 single sample (0.1329s), today's median run
        (0.2755s) reads as a +107% regression. Against a baseline that is the
        median of the same distribution, it reads as no change.
        """
        checker = _checker()
        names = [f"t{i}" for i in range(5)]
        current = {n: _stats(MEASURED_ROUNDS) for n in names}

        lucky_baseline = {n: _stats([LEGACY_BASELINE]) for n in names}
        honest_baseline = {n: _stats(MEASURED_ROUNDS) for n in names}

        # Runner normalization is deliberately disabled here (factor 1.0) so the
        # comparison itself is under test, not the correction on top of it.
        lucky = checker.compare_metrics(lucky_baseline, current, runner_factor=1.0)
        honest = checker.compare_metrics(honest_baseline, current, runner_factor=1.0)

        assert all(c.status == "error" for c in lucky)
        assert all(c.status == "pass" for c in honest)
        assert lucky[0].change_percent == pytest.approx(107.3, abs=0.5)
        assert honest[0].change_percent == pytest.approx(0.0, abs=1e-9)

    def test_a_real_regression_is_still_flagged(self):
        """Medians must not blunt a genuine, sustained slowdown."""
        checker = _checker()
        baseline = {f"t{i}": _stats([0.10] * 5) for i in range(5)}
        current = {f"t{i}": _stats([0.10] * 5) for i in range(5)}
        current["t0"] = _stats([0.30, 0.31, 0.29, 0.30, 0.32])

        comparisons = checker.compare_metrics(baseline, current)
        statuses = _statuses(comparisons)
        assert statuses["t0"] == "error"
        assert all(statuses[f"t{i}"] == "pass" for i in range(1, 5))

    def test_comparison_records_the_spread(self):
        checker = _checker()
        baseline = {f"t{i}": _stats([0.10] * 5) for i in range(5)}
        current = {f"t{i}": _stats([0.10] * 5) for i in range(5)}
        current["t0"] = _stats(MEASURED_ROUNDS)

        comp = {c.test_name: c for c in checker.compare_metrics(baseline, current)}[
            "t0"
        ]
        assert comp.current_n == 7
        assert comp.baseline_n == 5
        assert comp.current_min == pytest.approx(0.1217)
        assert comp.current_max == pytest.approx(0.3800)
        assert comp.current_sd == pytest.approx(MEASURED_SD, abs=5e-4)


class TestSingleSampleBaselineWarning:
    def test_report_warns_when_the_baseline_is_one_draw(self, capsys):
        checker = _checker()
        baseline = {f"t{i}": _stats([0.10]) for i in range(5)}
        current = {f"t{i}": _stats([0.10] * 5) for i in range(5)}

        comparisons = checker.compare_metrics(baseline, current)
        assert len(checker.single_sample_baselines(comparisons)) == 5

        checker.print_report(comparisons)
        out = capsys.readouterr().out
        assert "SINGLE-SAMPLE BASELINE" in out
        assert "--write-baseline" in out

    def test_no_warning_once_the_baseline_has_rounds(self, capsys):
        checker = _checker()
        baseline = {f"t{i}": _stats([0.10] * 5) for i in range(5)}
        current = {f"t{i}": _stats([0.10] * 5) for i in range(5)}

        checker.print_report(checker.compare_metrics(baseline, current))
        out = capsys.readouterr().out
        assert "SINGLE-SAMPLE BASELINE" not in out
        assert "baseline n=5" in out

    def test_single_sample_current_is_also_called_out(self, capsys):
        checker = _checker()
        baseline = {f"t{i}": _stats([0.10] * 5) for i in range(5)}
        current = {f"t{i}": _stats([0.10]) for i in range(5)}

        checker.print_report(checker.compare_metrics(baseline, current))
        assert "SINGLE-SAMPLE CURRENT" in capsys.readouterr().out


class TestProvenance:
    def test_records_machine_time_and_commit(self):
        provenance = collect_provenance(rounds=5, role="baseline", note="hello")
        assert provenance["rounds"] == 5
        assert provenance["role"] == "baseline"
        assert provenance["note"] == "hello"
        assert provenance["timezone"] == "Asia/Seoul"
        # KST-native timestamps (CLAUDE.md: KST only).
        assert provenance["generated_at"].endswith("+09:00")
        for key in ("runner", "python", "platform", "commit", "cpu_count"):
            assert key in provenance

    def test_written_samples_carry_provenance(self, tmp_path):
        checker = _checker()
        out = tmp_path / "current.json"
        checker.write_samples(out, {"a": _stats(MEASURED_ROUNDS)}, role="current")
        document = json.loads(out.read_text())
        assert document["schema"] == SAMPLES_SCHEMA
        assert document["provenance"]["role"] == "current"
        assert document["provenance"]["rounds"] == 7
        assert document["benchmarks"]["a"]["median"] == pytest.approx(MEASURED_MEDIAN)


class TestBaselineWrite:
    def test_refuses_a_single_sample_baseline(self, tmp_path, capsys):
        checker = _checker()
        out = tmp_path / "baselines.json"
        written = checker.write_baseline(out, {"a": _stats([LEGACY_BASELINE])})
        assert written is False
        assert not out.exists()
        assert "refusing to write a baseline from n=1" in capsys.readouterr().out

    def test_refuses_an_empty_baseline(self, tmp_path):
        checker = _checker()
        out = tmp_path / "baselines.json"
        assert checker.write_baseline(out, {}) is False
        assert not out.exists()

    def test_writes_once_there_are_enough_rounds(self, tmp_path, capsys):
        checker = _checker()
        out = tmp_path / "baselines.json"
        samples = MEASURED_ROUNDS[:DEFAULT_MIN_BASELINE_ROUNDS]
        assert checker.write_baseline(out, {"a": _stats(samples)}) is True

        document = json.loads(out.read_text())
        assert document["provenance"]["role"] == "baseline"
        assert document["provenance"]["rounds"] == DEFAULT_MIN_BASELINE_ROUNDS
        assert "UNDER-SAMPLED" not in document["provenance"]["note"]

        # The stats a human pastes into the PR body are printed.
        out_text = capsys.readouterr().out
        assert f"n={DEFAULT_MIN_BASELINE_ROUNDS}" in out_text
        assert "median=" in out_text

        # And it reads back as a baseline with the same median.
        stats, _, _ = checker.load_sample_sets([out])
        assert stats["a"].median == pytest.approx(statistics.median(samples))

    def test_force_records_that_the_baseline_is_under_sampled(self, tmp_path):
        checker = _checker()
        out = tmp_path / "baselines.json"
        assert (
            checker.write_baseline(out, {"a": _stats([0.2, 0.3])}, force=True) is True
        )
        note = json.loads(out.read_text())["provenance"]["note"]
        assert "UNDER-SAMPLED" in note
        assert "n=2" in note


class TestMarkdownSummary:
    def test_table_shows_n_median_spread_and_verdict(self):
        checker = _checker()
        baseline = {f"tests/performance/t{i}.py::t": _stats([0.10]) for i in range(5)}
        current = {
            f"tests/performance/t{i}.py::t": _stats([0.10] * 5) for i in range(5)
        }
        markdown = checker.markdown_summary(
            checker.compare_metrics(baseline, current), runner_factor=1.0
        )
        assert "| --- |" in markdown
        assert "t0.py::t" in markdown
        assert "0.1000s (1)" in markdown  # baseline median (n)
        assert "0.1000s (5)" in markdown  # current median (n)
        assert "single sample" in markdown


class TestCli:
    def test_rounds_are_merged_and_written_as_samples(self, tmp_path, capsys):
        baseline = _write_json(
            tmp_path / "baselines.json",
            _report({f"t{i}": 0.10 for i in range(5)}),
        )
        rounds = _write_rounds(
            tmp_path, [{f"t{i}": v for i in range(5)} for v in MEASURED_ROUNDS]
        )
        samples_out = tmp_path / "current.json"

        exit_code = _crmod.main(
            [
                "--baseline",
                str(baseline),
                "--current",
                *[str(p) for p in rounds],
                "--write-samples",
                str(samples_out),
                "--warning-threshold",
                "1.5",
                "--error-threshold",
                "2.0",
                "--min-duration",
                "0.05",
            ]
        )

        document = json.loads(samples_out.read_text())
        assert document["benchmarks"]["t0"]["n"] == 7
        assert document["benchmarks"]["t0"]["median"] == pytest.approx(MEASURED_MEDIAN)
        # Every benchmark moved together, so runner normalization absorbs it.
        assert exit_code == 0
        assert "SINGLE-SAMPLE BASELINE" in capsys.readouterr().out

    def test_write_baseline_needs_no_baseline_input(self, tmp_path):
        current = _write_json(
            tmp_path / "current.json",
            _crmod.RegressionChecker().build_samples_document(
                {"a": _stats(MEASURED_ROUNDS)}, collect_provenance(rounds=7)
            ),
        )
        out = tmp_path / "baselines.json"
        assert (
            _crmod.main(["--current", str(current), "--write-baseline", str(out)]) == 0
        )
        assert json.loads(out.read_text())["provenance"]["role"] == "baseline"

    def test_write_baseline_from_too_few_rounds_exits_two(self, tmp_path):
        current = _write_json(tmp_path / "current.json", _report({"a": 0.2}))
        out = tmp_path / "baselines.json"
        assert (
            _crmod.main(["--current", str(current), "--write-baseline", str(out)]) == 2
        )
        assert not out.exists()

    def test_baseline_is_required_for_a_plain_comparison(self, tmp_path, capsys):
        current = _write_json(tmp_path / "current.json", _report({"a": 0.2}))
        assert _crmod.main(["--current", str(current)]) == 2
        assert "--baseline is required" in capsys.readouterr().out

    def test_markdown_summary_is_appended(self, tmp_path):
        baseline = _write_json(
            tmp_path / "baselines.json", _report({f"t{i}": 0.10 for i in range(5)})
        )
        current = _write_json(
            tmp_path / "current.json", _report({f"t{i}": 0.10 for i in range(5)})
        )
        summary = tmp_path / "summary.md"
        summary.write_text("existing\n")
        _crmod.main(
            [
                "--baseline",
                str(baseline),
                "--current",
                str(current),
                "--markdown-summary",
                str(summary),
            ]
        )
        text = summary.read_text()
        assert text.startswith("existing\n")
        assert "Performance regression check" in text


# Environment variables that make _runner_label() report a GitHub runner.
_GITHUB_ENV_VARS = (
    "GITHUB_ACTIONS",
    "ImageOS",
    "RUNNER_OS",
    "RUNNER_ARCH",
    "GITHUB_SHA",
    "GITHUB_REPOSITORY",
    "GITHUB_SERVER_URL",
    "GITHUB_RUN_ID",
)


@pytest.fixture
def local_machine(monkeypatch):
    """Force the local-machine branch of ``_runner_label()``.

    Without this the assertions below depend on where the suite happens to run:
    they passed locally and failed on CI, where GITHUB_ACTIONS is set. A test of
    provenance must not read its expected value from the ambient environment.
    """
    for var in _GITHUB_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


class TestRunnerLabel:
    def test_names_the_github_runner_image_in_actions(self, monkeypatch):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("ImageOS", "ubuntu24")
        monkeypatch.setenv("RUNNER_ARCH", "X64")
        assert _crmod._runner_label() == "github-actions-ubuntu24-X64"

    def test_falls_back_to_runner_os_without_image_os(self, monkeypatch):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.delenv("ImageOS", raising=False)
        monkeypatch.setenv("RUNNER_OS", "Linux")
        monkeypatch.setenv("RUNNER_ARCH", "X64")
        assert _crmod._runner_label() == "github-actions-Linux-X64"

    def test_names_the_host_off_actions(self, local_machine):
        assert _crmod._runner_label().startswith("local-")


class TestProvenanceFollowsTheMeasuringMachine:
    """A baseline must name the machine that produced the numbers.

    The documented workflow measures on a CI runner and writes the baseline from
    a human's checkout. If the file recorded the writer's machine it would be
    unusable as provenance — and provenance is the only reason #768 was
    diagnosable at all.
    """

    CI_PROVENANCE = {
        "generated_at": "2026-10-02T11:00:00+09:00",
        "timezone": "Asia/Seoul",
        "role": "current",
        "rounds": 5,
        "runner": "github-actions-ubuntu24-X64",
        "cpu_count": 4,
        "python": "3.11.9",
        "platform": "Linux-6.11.0-1018-azure-x86_64",
        "commit": "deadbeef",
        "repository": "kakao-harris-lee/kis_unified_sts",
        "workflow_run": "https://github.com/x/y/actions/runs/1",
    }

    def _ci_samples_file(self, tmp_path):
        checker = _checker()
        document = checker.build_samples_document(
            {"a": _stats(MEASURED_ROUNDS[:5])}, dict(self.CI_PROVENANCE)
        )
        return _write_json(tmp_path / "ci-current.json", document)

    def test_baseline_inherits_the_runner_that_measured(self, tmp_path, local_machine):
        current = self._ci_samples_file(tmp_path)
        out = tmp_path / "baselines.json"
        assert (
            _crmod.main(["--current", str(current), "--write-baseline", str(out)]) == 0
        )

        provenance = json.loads(out.read_text())["provenance"]
        assert provenance["runner"] == "github-actions-ubuntu24-X64"
        assert provenance["commit"] == "deadbeef"
        assert provenance["python"] == "3.11.9"
        assert provenance["generated_at"] == "2026-10-02T11:00:00+09:00"
        assert provenance["role"] == "baseline"
        # The aggregating machine is recorded separately, not as the measurer.
        assert provenance["aggregated_on"]["runner"].startswith("local-")

    def test_freshly_measured_rounds_describe_this_machine(
        self, tmp_path, local_machine
    ):
        rounds = _write_rounds(tmp_path, [{"a": v} for v in MEASURED_ROUNDS[:5]])
        out = tmp_path / "baselines.json"
        assert (
            _crmod.main(
                ["--current", *[str(p) for p in rounds], "--write-baseline", str(out)]
            )
            == 0
        )
        provenance = json.loads(out.read_text())["provenance"]
        assert "aggregated_on" not in provenance
        assert provenance["runner"].startswith("local-")

    def test_merging_several_samples_files_inherits_nothing(
        self, tmp_path, local_machine
    ):
        """Two samples files may come from different runners — neither wins."""
        checker = _checker()
        first = self._ci_samples_file(tmp_path)
        other = dict(self.CI_PROVENANCE, runner="github-actions-ubuntu22-X64")
        second = _write_json(
            tmp_path / "ci-current-2.json",
            checker.build_samples_document({"a": _stats(MEASURED_ROUNDS[:5])}, other),
        )
        out = tmp_path / "baselines.json"
        assert (
            _crmod.main(
                ["--current", str(first), str(second), "--write-baseline", str(out)]
            )
            == 0
        )
        provenance = json.loads(out.read_text())["provenance"]
        assert "aggregated_on" not in provenance
        assert provenance["runner"].startswith("local-")
        assert provenance["sources"] == ["ci-current.json", "ci-current-2.json"]
        assert provenance["rounds"] == 10


class TestUnderSampledReporting:
    def test_refusal_names_the_under_sampled_benchmarks(self, tmp_path, capsys):
        """A benchmark that failed in some rounds contributes fewer samples.

        One flaky round then blocks the whole baseline, so the refusal has to
        say which benchmark is short — otherwise the operator re-runs blind.
        """
        checker = _checker()
        stats = {f"ok{i}": _stats([0.1] * 5) for i in range(3)}
        stats["flaky"] = _stats([0.1, 0.1])
        assert checker.write_baseline(tmp_path / "b.json", stats) is False

        out = capsys.readouterr().out
        assert "Under-sampled benchmarks (1 of 4)" in out
        assert "n=2  flaky" in out
        assert "ok0" not in out

    def test_markdown_does_not_print_an_unmeasured_test_as_instant(self):
        checker = _checker()
        baseline = {f"t{i}": _stats([0.10] * 5) for i in range(5)}
        current = {f"t{i}": _stats([0.10] * 5) for i in range(1, 5)}
        markdown = checker.markdown_summary(checker.compare_metrics(baseline, current))
        missing = [line for line in markdown.splitlines() if "`t0`" in line]
        assert len(missing) == 1
        assert "not run" in missing[0]
        assert "0.0000s (0)" not in missing[0]

    def test_markdown_marks_a_new_benchmark_as_new(self):
        checker = _checker()
        baseline = {f"t{i}": _stats([0.10] * 5) for i in range(5)}
        current = dict(baseline)
        current["brand_new"] = _stats([0.10] * 5)
        markdown = checker.markdown_summary(checker.compare_metrics(baseline, current))
        row = [line for line in markdown.splitlines() if "`brand_new`" in line][0]
        assert "| new |" in row


class TestEmptyPathArguments:
    """`--markdown-summary "$GITHUB_STEP_SUMMARY"` with the variable unset.

    The documented CI command is meant to be copy-pasteable. An unset shell
    variable must not turn a passing regression check into exit 2.
    """

    def _files(self, tmp_path):
        return (
            _write_json(
                tmp_path / "baselines.json", _report({f"t{i}": 0.10 for i in range(5)})
            ),
            _write_json(
                tmp_path / "current.json", _report({f"t{i}": 0.10 for i in range(5)})
            ),
        )

    def test_empty_markdown_summary_is_ignored(self, tmp_path):
        baseline, current = self._files(tmp_path)
        assert (
            _crmod.main(
                [
                    "--baseline",
                    str(baseline),
                    "--current",
                    str(current),
                    "--markdown-summary",
                    "",
                ]
            )
            == 0
        )
        assert not (tmp_path / ".").joinpath("summary.md").exists()

    def test_empty_write_paths_are_ignored(self, tmp_path):
        baseline, current = self._files(tmp_path)
        assert (
            _crmod.main(
                [
                    "--baseline",
                    str(baseline),
                    "--current",
                    str(current),
                    "--write-samples",
                    "",
                    "--write-baseline",
                    "   ",
                ]
            )
            == 0
        )


def _outcomes(checker, paths):
    """Per-benchmark round tally — the third element of load_sample_sets()."""
    return checker.load_sample_sets(paths)[2]


def _report_with_outcomes(entries: dict[str, tuple[str, float]]) -> dict:
    """pytest-json-report where each test carries an explicit outcome."""
    return {
        "summary": {"total": len(entries)},
        "tests": [
            {
                "nodeid": nodeid,
                "outcome": outcome,
                "setup": {"duration": 0.0},
                "call": {"duration": duration},
                "teardown": {"duration": 0.0},
            }
            for nodeid, (outcome, duration) in entries.items()
        ],
    }


class TestRoundOutcomes:
    """A benchmark's own assertion is a single-sample timing comparison.

    `test_exit_path_50_symbols` asserts `improvement_pct >= -40` on one
    measurement; observed on CI run 36954483251 it produced -41.8% in one round
    of five and passed in the others. Failing the job on that reproduces #768
    one level down, so a minority of failing rounds is a warning and a majority
    is an error.
    """

    def _rounds(self, tmp_path, failing: int, total: int = 5):
        paths = []
        for i in range(1, total + 1):
            entries = {f"t{j}": ("passed", 0.10) for j in range(5)}
            entries["flaky"] = ("failed", 0.10) if i <= failing else ("passed", 0.10)
            paths.append(
                _write_json(
                    tmp_path / f"round-{i}.json", _report_with_outcomes(entries)
                )
            )
        return paths

    def test_minority_failure_is_a_warning_not_a_job_failure(self, tmp_path, capsys):
        checker = _checker()
        tally = _outcomes(checker, self._rounds(tmp_path, failing=1))
        assert tally["flaky"].failed == 1
        assert tally["flaky"].passed == 4
        assert tally["flaky"].is_majority_failure is False

        errors, warnings = checker.print_round_outcomes(tally)
        assert (errors, warnings) == (0, 1)
        out = capsys.readouterr().out
        assert "failed in 1 of 5 rounds" in out
        assert "minority" in out

    def test_majority_failure_is_an_error(self, tmp_path, capsys):
        checker = _checker()
        tally = _outcomes(checker, self._rounds(tmp_path, failing=3))
        assert tally["flaky"].is_majority_failure is True

        errors, warnings = checker.print_round_outcomes(tally)
        assert (errors, warnings) == (1, 0)
        assert "FAILED in 3 of 5 rounds" in capsys.readouterr().out

    def test_exactly_half_is_not_a_majority(self, tmp_path):
        checker = _checker()
        tally = _outcomes(checker, self._rounds(tmp_path, failing=2, total=4))
        assert tally["flaky"].failed == 2
        assert tally["flaky"].decided == 4
        assert tally["flaky"].is_majority_failure is False

    def test_a_test_skipped_in_every_round_is_not_a_failure(self, tmp_path, capsys):
        """The 12 redis/websocket benchmarks skip in CI. They are missing, not failing."""
        checker = _checker()
        paths = [
            _write_json(
                tmp_path / f"round-{i}.json",
                _report_with_outcomes({"redis_bench": ("skipped", 0.0)}),
            )
            for i in range(1, 6)
        ]
        tally = _outcomes(checker, paths)
        assert tally["redis_bench"].skipped == 5
        assert tally["redis_bench"].failed == 0
        assert checker.print_round_outcomes(tally) == (0, 0)
        assert capsys.readouterr().out == ""

    def test_samples_files_carry_no_outcomes(self, tmp_path):
        checker = _checker()
        doc = checker.build_samples_document(
            {"a": _stats(MEASURED_ROUNDS)}, collect_provenance(rounds=7)
        )
        path = _write_json(tmp_path / "current.json", doc)
        assert _outcomes(checker, [path]) == {}


class TestRoundOutcomesChangeTheExitCode:
    def _cli(self, tmp_path, failing: int):
        baseline = _write_json(
            tmp_path / "baselines.json",
            _report({**{f"t{j}": 0.10 for j in range(5)}, "flaky": 0.10}),
        )
        rounds = []
        for i in range(1, 6):
            entries = {f"t{j}": ("passed", 0.10) for j in range(5)}
            entries["flaky"] = ("failed", 0.10) if i <= failing else ("passed", 0.10)
            rounds.append(
                _write_json(
                    tmp_path / f"round-{i}.json", _report_with_outcomes(entries)
                )
            )
        return ["--baseline", str(baseline), "--current", *[str(p) for p in rounds]]

    def test_one_flaky_round_keeps_the_job_green(self, tmp_path):
        assert _crmod.main(self._cli(tmp_path, failing=1)) == 0

    def test_a_majority_of_failing_rounds_exits_two(self, tmp_path):
        assert _crmod.main(self._cli(tmp_path, failing=3)) == 2


def _aborted_report(exitcode: int = 2, collectors=None, tests=None) -> dict:
    """What pytest-json-report writes when the session aborts.

    The file still exists and still parses — which is exactly why its existence
    cannot be the check.
    """
    return {
        "exitcode": exitcode,
        "summary": {"total": 0},
        "collectors": (
            collectors
            if collectors is not None
            else [{"nodeid": "", "outcome": "passed", "result": []}]
        ),
        "tests": tests if tests is not None else [],
    }


class TestSessionProblems:
    """A suite that never ran must not report green.

    Before the N-round loop, a non-zero pytest exit failed the step directly.
    The loop swallows that exit, so the checker has to read pytest's own
    exitcode and collectors instead — otherwise an ImportError in one module
    aborts collection in all 5 rounds, every baseline entry becomes a
    non-fatal "Test not found" warning, and the job goes green having measured
    nothing.
    """

    def _aborted_rounds(self, tmp_path, n=5, **kwargs):
        return [
            _write_json(tmp_path / f"round-{i}.json", _aborted_report(**kwargs))
            for i in range(1, n + 1)
        ]

    def test_collection_abort_in_every_round_is_an_error(self, tmp_path):
        checker = _checker()
        paths = self._aborted_rounds(tmp_path)
        stats, sources, _ = checker.load_sample_sets(paths)
        assert stats == {}
        problems = checker.session_problems(sources, stats)
        assert len(problems) == 6  # one per round, plus "no benchmark"
        assert "pytest exited 2" in problems[0]
        assert "nothing to compare" in problems[-1]

    def test_the_cli_exits_two_rather_than_green(self, tmp_path, capsys):
        baseline = _write_json(
            tmp_path / "baselines.json", _report({f"t{i}": 0.10 for i in range(5)})
        )
        rounds = self._aborted_rounds(tmp_path)
        exit_code = _crmod.main(
            ["--baseline", str(baseline), "--current", *[str(p) for p in rounds]]
        )
        assert exit_code == 2
        out = capsys.readouterr().out
        assert "MEASUREMENT INVALID" in out
        # The old failure mode: 5 silent warnings and a green job.
        assert "✅ PASSED" not in out

    def test_a_failed_collector_is_an_error(self, tmp_path):
        checker = _checker()
        path = _write_json(
            tmp_path / "round-1.json",
            _aborted_report(
                exitcode=2,
                collectors=[
                    {
                        "nodeid": "tests/performance/test_redis_load.py",
                        "outcome": "failed",
                    }
                ],
            ),
        )
        stats, sources, _ = checker.load_sample_sets([path])
        problems = checker.session_problems(sources, stats)
        assert any(
            "collection failed for tests/performance/test_redis_load.py" in p
            for p in problems
        )

    def test_exitcode_one_is_a_completed_session_with_failures(self, tmp_path):
        """Exit 1 means tests ran and some failed — the majority rule judges that."""
        checker = _checker()
        payload = _report_with_outcomes({"a": ("failed", 0.1), "b": ("passed", 0.1)})
        payload["exitcode"] = 1
        path = _write_json(tmp_path / "round-1.json", payload)
        stats, sources, outcomes = checker.load_sample_sets([path])
        assert checker.session_problems(sources, stats) == []
        assert outcomes["a"].failed == 1

    def test_a_samples_file_is_not_checked_for_an_exitcode(self, tmp_path):
        checker = _checker()
        doc = checker.build_samples_document(
            {"a": _stats(MEASURED_ROUNDS)}, collect_provenance(rounds=7)
        )
        path = _write_json(tmp_path / "current.json", doc)
        stats, sources, _ = checker.load_sample_sets([path])
        assert checker.session_problems(sources, stats) == []

    def test_zero_benchmarks_alone_is_an_error(self, tmp_path):
        """A clean exit that collected nothing still measured nothing."""
        checker = _checker()
        payload = _report({})
        payload["exitcode"] = 0
        path = _write_json(tmp_path / "round-1.json", payload)
        stats, sources, _ = checker.load_sample_sets([path])
        assert checker.session_problems(sources, stats) == [
            "no benchmark produced a single passing sample — there is nothing to compare"
        ]


class TestVerdictIsPrintedOnce:
    """The printed verdict and the exit code must agree.

    Round-outcome errors used to be added after print_report() had already
    printed "✅ PASSED" and after markdown_summary() had been written, so the
    console and the step summary said pass while the job exited 2.
    """

    def _majority_failure(self):
        baseline = {f"t{i}": _stats([0.10] * 5) for i in range(5)}
        current = {f"t{i}": _stats([0.10] * 5) for i in range(5)}
        outcomes = {
            "t0": _crmod.RoundOutcomes(passed=2, failed=3),
        }
        return baseline, current, outcomes

    def test_console_verdict_reflects_a_round_outcome_error(self, capsys):
        checker = _checker()
        baseline, current, outcomes = self._majority_failure()
        comparisons = checker.compare_metrics(baseline, current)
        errors, _, _ = checker.print_report(comparisons, outcomes=outcomes)
        out = capsys.readouterr().out
        assert errors == 1
        assert "❌ FAILED" in out
        assert "✅ PASSED" not in out

    def test_markdown_shows_the_round_outcome_error(self):
        checker = _checker()
        baseline, current, outcomes = self._majority_failure()
        markdown = checker.markdown_summary(
            checker.compare_metrics(baseline, current), outcomes=outcomes
        )
        assert "Test outcomes across rounds" in markdown
        assert "🔴" in markdown
        assert "failed in 3 of 5 rounds" in markdown

    def test_session_problems_reach_both_outputs(self, capsys):
        checker = _checker()
        baseline = {f"t{i}": _stats([0.10] * 5) for i in range(5)}
        current = {f"t{i}": _stats([0.10] * 5) for i in range(5)}
        comparisons = checker.compare_metrics(baseline, current)
        errors, _, _ = checker.print_report(
            comparisons, session_problems=["round-1.json: pytest exited 2"]
        )
        assert errors == 1
        assert "MEASUREMENT INVALID" in capsys.readouterr().out
        markdown = checker.markdown_summary(
            comparisons, session_problems=["round-1.json: pytest exited 2"]
        )
        assert "Measurement invalid" in markdown


class TestProvenanceRoundsAndSources:
    def test_rounds_counts_sessions_not_the_thinnest_benchmark(self, tmp_path):
        """One benchmark failing one round must not relabel the file 'rounds: 4'."""
        checker = _checker()
        paths = []
        for i in range(1, 6):
            entries = {"ok": ("passed", 0.10)}
            entries["flaky"] = ("failed", 0.10) if i == 1 else ("passed", 0.10)
            paths.append(
                _write_json(
                    tmp_path / f"round-{i}.json", _report_with_outcomes(entries)
                )
            )
        stats, sources, _ = checker.load_sample_sets(paths)
        out = tmp_path / "current.json"
        checker.write_samples(out, stats, sources=sources)

        document = json.loads(out.read_text())
        assert document["provenance"]["rounds"] == 5
        assert document["benchmarks"]["flaky"]["n"] == 4
        assert document["benchmarks"]["ok"]["n"] == 5
        assert len(document["provenance"]["sources"]) == 5

    def test_reaggregation_keeps_the_original_round_chain(self, tmp_path):
        checker = _checker()
        rounds = _write_rounds(tmp_path, [{"a": v} for v in MEASURED_ROUNDS[:5]])
        current = tmp_path / "current.json"
        stats, sources, _ = checker.load_sample_sets(rounds)
        checker.write_samples(current, stats, sources=sources)

        out = tmp_path / "baselines.json"
        assert (
            _crmod.main(["--current", str(current), "--write-baseline", str(out)]) == 0
        )
        provenance = json.loads(out.read_text())["provenance"]
        assert provenance["rounds"] == 5
        assert provenance["sources"] == [f"round-{i}.json" for i in range(1, 6)]
        assert provenance["aggregated_on"]["from"] == ["current.json"]


class TestCommitProvenance:
    def test_perf_commit_sha_beats_the_merge_commit(self, monkeypatch):
        monkeypatch.setenv("GITHUB_SHA", "e" * 40)  # refs/pull/N/merge
        monkeypatch.setenv("PERF_COMMIT_SHA", "a" * 40)
        monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
        provenance = collect_provenance(rounds=5)
        assert provenance["commit"] == "a" * 40
        assert provenance["github_event"] == "pull_request"

    def test_falls_back_to_github_sha_then_git_head(self, monkeypatch):
        monkeypatch.delenv("PERF_COMMIT_SHA", raising=False)
        monkeypatch.setenv("GITHUB_SHA", "b" * 40)
        assert collect_provenance(rounds=5)["commit"] == "b" * 40
        monkeypatch.delenv("GITHUB_SHA", raising=False)
        assert isinstance(collect_provenance(rounds=5)["commit"], str)


# ----------------------------------------------------------------------
# Excluded benchmarks (#768 / #796 / #679)
# ----------------------------------------------------------------------

EXCLUDED_KEY = _crmod.EXCLUDED_KEY

LIVE_KIS_REASON = "needs a live KIS endpoint; unreachable from a CI runner"


def _baseline_document(
    durations: dict[str, float],
    excluded: dict | None = None,
    rounds: int = 7,
) -> dict:
    """A kis-perf-samples/v1 baseline with ``rounds`` identical samples each."""
    checker = _crmod.RegressionChecker()
    return checker.build_samples_document(
        {name: _stats([value] * rounds) for name, value in durations.items()},
        collect_provenance(rounds=rounds, role="baseline"),
        excluded,
    )


class TestExclusionParsing:
    def test_absent_section_means_nothing_is_excluded(self, tmp_path):
        checker = _checker()
        path = _write_json(tmp_path / "baselines.json", _report({"a": 0.2}))
        assert checker.load_exclusions([path]) == {}

    def test_plain_reason_strings_are_read(self):
        checker = _checker()
        document = _baseline_document({"a": 0.2}, {"b": LIVE_KIS_REASON})
        assert checker.extract_exclusions(document) == {"b": LIVE_KIS_REASON}

    def test_structured_reason_is_read(self):
        checker = _checker()
        document = _baseline_document({"a": 0.2})
        document[EXCLUDED_KEY] = {"b": {"reason": LIVE_KIS_REASON}}
        assert checker.extract_exclusions(document) == {"b": LIVE_KIS_REASON}

    def test_exclusion_without_a_reason_is_rejected(self):
        """A bare name is indistinguishable from a benchmark quietly dropped."""
        checker = _checker()
        document = _baseline_document({"a": 0.2})
        document[EXCLUDED_KEY] = {"b": ""}
        with pytest.raises(ValueError, match="no reason"):
            checker.extract_exclusions(document)

    def test_a_non_mapping_section_is_rejected(self):
        checker = _checker()
        document = _baseline_document({"a": 0.2})
        document[EXCLUDED_KEY] = ["b"]
        with pytest.raises(ValueError, match="must be a mapping"):
            checker.extract_exclusions(document)

    def test_a_benchmark_cannot_be_both_measured_and_excluded(self):
        checker = _checker()
        document = _baseline_document({"a": 0.2}, {"a": LIVE_KIS_REASON})
        with pytest.raises(ValueError, match="both measured and listed"):
            checker.extract_exclusions(document)

    def test_a_written_document_always_carries_the_section(self):
        document = _baseline_document({"a": 0.2})
        assert document[EXCLUDED_KEY] == {}


class TestExcludedBenchmarksAreNotCompared:
    def test_an_excluded_benchmark_produces_no_comparison_at_all(self):
        """The point of the section: no per-run noise for a declared absence.

        Undeclared, the same absence is an error (see
        ``TestAnUnmeasuredBaselineEntryIsAnError``). The exclusion is what
        turns "nobody noticed" into "somebody wrote down why".
        """
        checker = _checker()
        baseline = {"a": _stats([0.10] * 7), "b": _stats([0.20] * 7)}
        current = {"a": _stats([0.10] * 5)}

        without = _statuses(checker.compare_metrics(baseline, current))
        assert without["b"] == "error"

        with_exclusion = checker.compare_metrics(
            baseline, current, exclusions={"b": LIVE_KIS_REASON}
        )
        assert [c.test_name for c in with_exclusion] == ["a"]

    def test_an_excluded_name_is_not_reported_as_a_new_test(self):
        checker = _checker()
        comparisons = checker.compare_metrics(
            {"a": _stats([0.10] * 7)},
            {"a": _stats([0.10] * 5), "b": _stats([0.20] * 5)},
            exclusions={"b": LIVE_KIS_REASON},
        )
        assert [c.test_name for c in comparisons] == ["a"]


class TestStaleExclusionIsAnError:
    def test_an_excluded_benchmark_that_produced_samples_is_a_problem(self):
        """The concrete input this guard exists to catch.

        A baseline says ``b`` cannot be measured here; the run measured it
        five times. Silence would mean a benchmark that runs and is never
        checked — the failure mode the exclusion section is supposed to
        prevent, not create.
        """
        checker = _checker()
        problems = checker.exclusion_problems(
            {"b": LIVE_KIS_REASON}, {"b": _stats([0.2] * 5)}
        )
        assert len(problems) == 1
        assert "stale" in problems[0]
        assert "5 sample(s)" in problems[0]
        assert LIVE_KIS_REASON in problems[0]

    def test_an_exclusion_with_no_samples_is_silent(self):
        checker = _checker()
        assert checker.exclusion_problems({"b": LIVE_KIS_REASON}, {}) == []

    def test_it_changes_the_exit_code(self, tmp_path):
        baseline = _write_json(
            tmp_path / "baselines.json",
            _baseline_document(
                {f"t{i}": 0.10 for i in range(5)}, {"stale": LIVE_KIS_REASON}
            ),
        )
        current = _write_json(
            tmp_path / "current.json",
            _report({**{f"t{i}": 0.10 for i in range(5)}, "stale": 0.10}),
        )
        assert (
            _crmod.main(["--baseline", str(baseline), "--current", str(current)]) == 2
        )

    def test_a_live_exclusion_alone_keeps_the_run_green(self, tmp_path, capsys):
        baseline = _write_json(
            tmp_path / "baselines.json",
            _baseline_document(
                {f"t{i}": 0.10 for i in range(5)}, {"excluded_one": LIVE_KIS_REASON}
            ),
        )
        current = _write_json(
            tmp_path / "current.json", _report({f"t{i}": 0.10 for i in range(5)})
        )
        assert (
            _crmod.main(["--baseline", str(baseline), "--current", str(current)]) == 0
        )
        out = capsys.readouterr().out
        assert "EXCLUDED (1 not measured here)" in out
        assert "Test not found" not in out


class TestExclusionsSurviveRegeneration:
    def test_write_baseline_carries_the_exclusions_of_the_compared_baseline(
        self, tmp_path
    ):
        baseline_path = _write_json(
            tmp_path / "baselines.json",
            _baseline_document({"a": 0.10}, {"b": LIVE_KIS_REASON}),
        )
        current = _write_json(
            tmp_path / "current.json",
            _crmod.RegressionChecker().build_samples_document(
                {"a": _stats([0.10] * 7)}, collect_provenance(rounds=7)
            ),
        )
        out = tmp_path / "regenerated.json"
        assert (
            _crmod.main(
                [
                    "--baseline",
                    str(baseline_path),
                    "--current",
                    str(current),
                    "--write-baseline",
                    str(out),
                ]
            )
            == 0
        )
        assert json.loads(out.read_text())[EXCLUDED_KEY] == {"b": LIVE_KIS_REASON}

    def test_exclusions_from_supplies_them_without_a_comparison(self, tmp_path):
        source = _write_json(
            tmp_path / "old-baseline.json",
            _baseline_document({"a": 0.10}, {"b": LIVE_KIS_REASON}),
        )
        current = _write_json(
            tmp_path / "current.json",
            _crmod.RegressionChecker().build_samples_document(
                {"a": _stats([0.10] * 7)}, collect_provenance(rounds=7)
            ),
        )
        out = tmp_path / "regenerated.json"
        assert (
            _crmod.main(
                [
                    "--current",
                    str(current),
                    "--write-baseline",
                    str(out),
                    "--exclusions-from",
                    str(source),
                ]
            )
            == 0
        )
        assert json.loads(out.read_text())[EXCLUDED_KEY] == {"b": LIVE_KIS_REASON}

    def test_writing_a_self_contradictory_baseline_is_refused(self, tmp_path, capsys):
        """Carrying an exclusion for a benchmark the new samples contain.

        ``--force-baseline`` does not cover this: the result would be rejected
        by ``extract_exclusions`` on the next read, so writing it just moves
        the failure somewhere less legible.
        """
        source = _write_json(
            tmp_path / "old-baseline.json",
            _baseline_document({"a": 0.10}, {"b": LIVE_KIS_REASON}),
        )
        current = _write_json(
            tmp_path / "current.json",
            _crmod.RegressionChecker().build_samples_document(
                {"a": _stats([0.10] * 7), "b": _stats([0.20] * 7)},
                collect_provenance(rounds=7),
            ),
        )
        out = tmp_path / "regenerated.json"
        assert (
            _crmod.main(
                [
                    "--current",
                    str(current),
                    "--write-baseline",
                    str(out),
                    "--exclusions-from",
                    str(source),
                    "--force-baseline",
                ]
            )
            == 2
        )
        assert not out.exists()
        assert "contradicts its own samples" in capsys.readouterr().out


class TestExclusionsInTheMarkdownSummary:
    def test_the_table_names_each_exclusion_and_its_reason(self):
        checker = _checker()
        text = checker.markdown_summary(
            checker.compare_metrics({"a": _stats([0.1] * 7)}, {"a": _stats([0.1] * 5)}),
            exclusions={"b": LIVE_KIS_REASON},
        )
        assert "Excluded from this check (1)" in text
        assert LIVE_KIS_REASON in text

    def test_a_stale_exclusion_is_called_out(self):
        checker = _checker()
        text = checker.markdown_summary(
            [],
            exclusions={"b": LIVE_KIS_REASON},
            exclusion_problems=["b: ... stale ..."],
        )
        assert "Stale exclusion" in text


class TestAnUnmeasuredBaselineEntryIsAnError:
    """Every baseline entry must be measured or explicitly excluded.

    The third state -- present in the baseline, absent from the run, nobody
    told -- is what the CI job sat in for four months: twelve benchmarks
    skipped, twelve non-fatal warnings nobody read, green check (#768 / #796 /
    #679). Making it an error is what gives the empty ``excluded`` map teeth:
    with nothing excluded, all 25 benchmarks have to run.
    """

    def test_a_missing_benchmark_fails_the_check(self, tmp_path):
        baseline = _write_json(
            tmp_path / "baselines.json",
            _baseline_document({f"t{i}": 0.10 for i in range(6)}),
        )
        current = _write_json(
            tmp_path / "current.json", _report({f"t{i}": 0.10 for i in range(5)})
        )
        assert (
            _crmod.main(["--baseline", str(baseline), "--current", str(current)]) == 2
        )

    def test_the_message_names_both_ways_out(self):
        checker = _checker()
        comparison = next(
            c
            for c in checker.compare_metrics({"gone": _stats([0.2] * 7)}, {})
            if c.test_name == "gone"
        )
        assert comparison.status == "error"
        assert "NOT MEASURED" in comparison.message
        assert EXCLUDED_KEY in comparison.message

    def test_declaring_it_excluded_is_the_way_out(self, tmp_path):
        baseline = _write_json(
            tmp_path / "baselines.json",
            _baseline_document(
                {f"t{i}": 0.10 for i in range(5)}, {"gone": LIVE_KIS_REASON}
            ),
        )
        current = _write_json(
            tmp_path / "current.json", _report({f"t{i}": 0.10 for i in range(5)})
        )
        assert (
            _crmod.main(["--baseline", str(baseline), "--current", str(current)]) == 0
        )


# ----------------------------------------------------------------------
# Review round 1 — findings F1-F4, F7, F8
# ----------------------------------------------------------------------


class TestTheMeasurementSurvivesAnUnusableBaseline:
    """F1: --write-samples is what preserves the run; a baseline problem is not
    allowed to cost it.

    The CI job uploads current.json as the artifact an operator regenerates a
    baseline from. Before this, the carried-exclusion read happened first, so
    an absent or malformed baseline threw the measurement away on the way to
    reporting the baseline's own problem — a regression against main, where
    the write happened first.
    """

    def test_a_missing_baseline_still_writes_current_json(self, tmp_path, capsys):
        current = _write_json(tmp_path / "round-1.json", _report({"a": 0.2}))
        samples_out = tmp_path / "current.json"

        exit_code = _crmod.main(
            [
                "--baseline",
                str(tmp_path / "does-not-exist.json"),
                "--current",
                str(current),
                "--write-samples",
                str(samples_out),
            ]
        )

        assert exit_code == 2
        assert samples_out.exists()
        assert json.loads(samples_out.read_text())["benchmarks"]["a"]["n"] == 1
        out = capsys.readouterr().out
        assert "BASELINE UNREADABLE" in out
        assert "were still written" in out

    def test_a_malformed_exclusion_map_still_writes_current_json(self, tmp_path):
        bad = _baseline_document({"a": 0.2})
        bad[EXCLUDED_KEY] = {"b": ""}  # no reason -> rejected at load
        baseline = _write_json(tmp_path / "baselines.json", bad)
        current = _write_json(tmp_path / "round-1.json", _report({"a": 0.2}))
        samples_out = tmp_path / "current.json"

        assert (
            _crmod.main(
                [
                    "--baseline",
                    str(baseline),
                    "--current",
                    str(current),
                    "--write-samples",
                    str(samples_out),
                ]
            )
            == 2
        )
        assert samples_out.exists()

    def test_a_readable_baseline_is_unaffected(self, tmp_path):
        baseline = _write_json(
            tmp_path / "baselines.json", _baseline_document({"a": 0.10})
        )
        current = _write_json(tmp_path / "round-1.json", _report({"a": 0.10}))
        samples_out = tmp_path / "current.json"
        assert (
            _crmod.main(
                [
                    "--baseline",
                    str(baseline),
                    "--current",
                    str(current),
                    "--write-samples",
                    str(samples_out),
                ]
            )
            == 0
        )
        assert samples_out.exists()


class TestWrittenSamplesNeverContradictThemselves:
    """F2: a stamped exclusion for a benchmark the same file measures produces
    a document the script's own reader rejects."""

    def test_a_measured_name_is_not_stamped_into_current_json(self, tmp_path):
        baseline = _write_json(
            tmp_path / "baselines.json",
            _baseline_document(
                {f"t{i}": 0.10 for i in range(5)}, {"stale": LIVE_KIS_REASON}
            ),
        )
        # The run measures the excluded benchmark: a stale exclusion.
        current = _write_json(
            tmp_path / "round-1.json",
            _report({**{f"t{i}": 0.10 for i in range(5)}, "stale": 0.10}),
        )
        samples_out = tmp_path / "current.json"

        # Still exit 2 — the stale exclusion is an error, reported separately.
        assert (
            _crmod.main(
                [
                    "--baseline",
                    str(baseline),
                    "--current",
                    str(current),
                    "--write-samples",
                    str(samples_out),
                ]
            )
            == 2
        )

        document = json.loads(samples_out.read_text())
        assert "stale" in document["benchmarks"]
        assert "stale" not in document[EXCLUDED_KEY]

    def test_the_written_file_can_be_read_back(self, tmp_path):
        """The property that matters: no artifact the script refuses to load."""
        baseline = _write_json(
            tmp_path / "baselines.json",
            _baseline_document({"a": 0.10}, {"stale": LIVE_KIS_REASON}),
        )
        current = _write_json(
            tmp_path / "round-1.json", _report({"a": 0.10, "stale": 0.10})
        )
        samples_out = tmp_path / "current.json"
        _crmod.main(
            [
                "--baseline",
                str(baseline),
                "--current",
                str(current),
                "--write-samples",
                str(samples_out),
            ]
        )
        # Would raise "both measured and listed in 'excluded'" before the fix.
        checker = _checker()
        assert checker.load_exclusions([samples_out]) == {}

    def test_an_exclusion_with_no_samples_is_still_stamped(self, tmp_path):
        baseline = _write_json(
            tmp_path / "baselines.json",
            _baseline_document({"a": 0.10}, {"b": LIVE_KIS_REASON}),
        )
        current = _write_json(tmp_path / "round-1.json", _report({"a": 0.10}))
        samples_out = tmp_path / "current.json"
        _crmod.main(
            [
                "--baseline",
                str(baseline),
                "--current",
                str(current),
                "--write-samples",
                str(samples_out),
            ]
        )
        assert json.loads(samples_out.read_text())[EXCLUDED_KEY] == {
            "b": LIVE_KIS_REASON
        }


class TestEmptyExclusionsFromArgument:
    """F3: `--exclusions-from "$UNSET"` must be a no-op, not a TypeError."""

    def test_an_empty_argument_reads_as_absent(self, tmp_path):
        current = _write_json(
            tmp_path / "current.json",
            _crmod.RegressionChecker().build_samples_document(
                {"a": _stats([0.10] * 7)}, collect_provenance(rounds=7)
            ),
        )
        out = tmp_path / "baselines.json"
        assert (
            _crmod.main(
                [
                    "--current",
                    str(current),
                    "--write-baseline",
                    str(out),
                    "--exclusions-from",
                    "",
                ]
            )
            == 0
        )
        assert json.loads(out.read_text())[EXCLUDED_KEY] == {}

    def test_parse_args_strips_the_empty_entries(self):
        args = _crmod.parse_args(["--current", "c.json", "--exclusions-from", ""])
        assert args.exclusions_from is None

    def test_a_real_path_alongside_an_empty_one_survives(self):
        args = _crmod.parse_args(
            ["--current", "c.json", "--exclusions-from", "", "b.json"]
        )
        assert args.exclusions_from == [Path("b.json")]


class TestMergedBaselineExclusionConflicts:
    """F4: the overlap check has to run on the MERGE of several --baseline docs.

    `--baseline old.json new.json` where old.json measures X and new.json
    excludes X passes both per-document checks, and X was then dropped from
    the comparison with no error at all — the "measured and not checked" state
    the mechanism exists to forbid.
    """

    def test_measured_in_one_document_and_excluded_in_another_is_an_error(
        self, tmp_path, capsys
    ):
        old = _write_json(
            tmp_path / "old.json", _baseline_document({"a": 0.10, "x": 0.20})
        )
        new = _write_json(
            tmp_path / "new.json",
            _baseline_document({"b": 0.10}, {"x": LIVE_KIS_REASON}),
        )
        current = _write_json(
            tmp_path / "current.json", _report({"a": 0.10, "b": 0.10})
        )

        exit_code = _crmod.main(
            [
                "--baseline",
                str(old),
                str(new),
                "--current",
                str(current),
            ]
        )
        assert exit_code == 2
        out = capsys.readouterr().out
        assert "BASELINE SET CONTRADICTS ITSELF" in out
        assert "x" in out

    def test_the_check_is_silent_when_the_documents_agree(self, tmp_path):
        checker = _checker()
        assert (
            checker.merged_exclusion_conflicts(
                {"x": LIVE_KIS_REASON}, {"a": _stats([0.1])}
            )
            == []
        )

    def test_a_single_document_saying_both_is_still_rejected_at_load(self):
        checker = _checker()
        with pytest.raises(ValueError, match="both measured and listed"):
            checker.extract_exclusions(
                _baseline_document({"a": 0.2}, {"a": LIVE_KIS_REASON})
            )


class TestBaselineIsParsedOnce:
    """F7: three json.load calls and three identical log lines per check."""

    def test_the_normal_ci_invocation_reads_the_baseline_once(
        self, tmp_path, monkeypatch
    ):
        baseline = _write_json(
            tmp_path / "baselines.json",
            _baseline_document({f"t{i}": 0.10 for i in range(5)}),
        )
        current = _write_json(
            tmp_path / "round-1.json", _report({f"t{i}": 0.10 for i in range(5)})
        )

        reads: list[str] = []
        original = _crmod.RegressionChecker.load_metrics

        def _counting(self, json_path):
            reads.append(str(json_path))
            return original(self, json_path)

        monkeypatch.setattr(_crmod.RegressionChecker, "load_metrics", _counting)

        _crmod.main(
            [
                "--baseline",
                str(baseline),
                "--current",
                str(current),
                "--write-samples",
                str(tmp_path / "current.json"),
            ]
        )
        assert reads.count(str(baseline)) == 1


class TestMarkdownCellsAreEscaped:
    """F8: a reason is free text, so it will eventually contain a pipe."""

    def test_a_pipe_in_a_reason_does_not_add_a_column(self):
        checker = _checker()
        text = checker.markdown_summary(
            [], exclusions={"t": "needs live KIS | see #679"}
        )
        row = next(line for line in text.splitlines() if line.startswith("| `t`"))
        # 2 content cells -> 3 splits on an unescaped pipe would be 4.
        assert row.count("|") - row.count("\\|") == 3
        assert "\\|" in row

    def test_a_newline_in_a_reason_does_not_end_the_row(self):
        checker = _checker()
        text = checker.markdown_summary([], exclusions={"t": "line one\nline two"})
        rows = [line for line in text.splitlines() if line.startswith("| `t`")]
        assert len(rows) == 1
        assert "line one line two" in rows[0]

    def test_a_pipe_in_a_benchmark_id_is_escaped_too(self):
        """Parametrized ids can contain one: `test_x[a|b]`."""
        checker = _checker()
        text = checker.markdown_summary([], exclusions={"test_x[a|b]": "r"})
        row = next(line for line in text.splitlines() if "test_x" in line)
        assert "a\\|b" in row
