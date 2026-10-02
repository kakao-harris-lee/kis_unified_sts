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
        stats, sources = checker.load_sample_sets([path])
        assert stats["a"].n == 1
        assert stats["a"].median == pytest.approx(LEGACY_BASELINE)
        assert sources[0].kind == "pytest-json-report"
        assert sources[0].rounds == 1

    def test_several_round_reports_merge_into_one_sample_set(self, tmp_path):
        checker = _checker()
        paths = _write_rounds(tmp_path, [{"a": v} for v in MEASURED_ROUNDS])
        stats, sources = checker.load_sample_sets(paths)
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
        stats, sources = checker.load_sample_sets([path])
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
        stats, _ = checker.load_sample_sets([out])
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

    def test_baseline_inherits_the_runner_that_measured(self, tmp_path):
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

    def test_freshly_measured_rounds_describe_this_machine(self, tmp_path):
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

    def test_merging_several_samples_files_inherits_nothing(self, tmp_path):
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
