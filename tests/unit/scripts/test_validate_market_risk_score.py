"""Hermetic tests for scripts/validation/validate_market_risk_score.py.

Synthetic Parquet fixtures in tmp_path; no network, no Redis, no repo data.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd
import pytest

from scripts.validation.market_risk_common import ValidationSettings
from scripts.validation.validate_market_risk_score import (
    band_runs,
    build_report,
    compute_forward_returns,
    episode_rows,
    flapping_metrics,
    main,
    permutation_pvalue,
    threshold_analysis,
)
from shared.storage.market_structure_store import ParquetMarketStructureStore


def _trading_days(start: date, count: int) -> list[date]:
    days: list[date] = []
    cursor = start
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _settings(**overrides) -> ValidationSettings:
    defaults = {
        "thresholds": [70.0],
        "horizons_days": [1],
        "permutation_iterations": 400,
        "permutation_seed": 7,
    }
    defaults.update(overrides)
    return ValidationSettings(**defaults)


def _score_fixture_rows() -> tuple[list[date], list[dict]]:
    """10 trading days; scores >= 70 on indices 2 and 5 precede -5% days."""
    days = _trading_days(date(2026, 6, 1), 10)
    returns = [-0.05 if i in (2, 5) else 0.02 for i in range(9)]
    prices = [100.0]
    for ret in returns:
        prices.append(prices[-1] * (1.0 + ret))
    rows = []
    for i, day in enumerate(days):
        rows.append(
            {
                "trade_date": day,
                "kospi_close": prices[i],
                "risk_score_ema3": 80.0 if i in (2, 5) else 10.0,
                "risk_band": "HIGH" if i in (2, 5) else "LOW",
                "unified_regime": "RISK_OFF" if i in (2, 5) else "RISK_ON",
                "degraded": False,
                "coverage_ratio": 1.0,
            }
        )
    return days, rows


@pytest.fixture
def store(tmp_path):
    return ParquetMarketStructureStore(tmp_path / "market")


class TestForwardReturns:
    def test_known_values(self):
        days = _trading_days(date(2026, 6, 1), 3)
        frame = pd.DataFrame({"trade_date": days, "kospi_close": [100.0, 110.0, 121.0]})
        out = compute_forward_returns(frame, "kospi_close", [1])
        assert out["fwd_1d"].iloc[0] == pytest.approx(0.10)
        assert out["fwd_1d"].iloc[1] == pytest.approx(0.10)
        assert pd.isna(out["fwd_1d"].iloc[2])

    def test_missing_prices_are_skipped(self):
        days = _trading_days(date(2026, 6, 1), 4)
        frame = pd.DataFrame(
            {"trade_date": days, "kospi_close": [100.0, None, 121.0, 133.1]}
        )
        out = compute_forward_returns(frame, "kospi_close", [1])
        # The missing day is dropped: horizon counts available close rows.
        assert list(out["trade_date"]) == [days[0], days[2], days[3]]
        assert out["fwd_1d"].iloc[0] == pytest.approx(0.21)


class TestThresholdAnalysis:
    def test_known_distribution(self):
        _days, rows = _score_fixture_rows()
        frame = pd.DataFrame(rows)
        settings = _settings()
        forward = compute_forward_returns(frame, "kospi_close", [1])
        merged = forward.merge(
            frame[["trade_date", "risk_score_ema3", "degraded"]], on="trade_date"
        )
        (result,) = threshold_analysis(
            merged,
            score_column="risk_score_ema3",
            degraded_column="degraded",
            settings=settings,
        )
        assert result["flagged"]["count"] == 2
        assert result["all"]["count"] == 9
        assert result["flagged"]["mean"] == pytest.approx(-0.05)
        assert result["flagged"]["median"] == pytest.approx(-0.05)
        assert result["all"]["mean"] == pytest.approx((7 * 0.02 - 2 * 0.05) / 9)
        assert result["all"]["median"] == pytest.approx(0.02)
        assert result["delta_mean"] == pytest.approx(-0.05 - (7 * 0.02 - 2 * 0.05) / 9)
        # exact one-sided p is 1/C(9,2) ~ 0.028; permutation approximates it
        assert result["p_value_one_sided"] < 0.1

    def test_degraded_days_are_not_flagged(self):
        _days, rows = _score_fixture_rows()
        rows[5]["degraded"] = True
        frame = pd.DataFrame(rows)
        forward = compute_forward_returns(frame, "kospi_close", [1])
        merged = forward.merge(
            frame[["trade_date", "risk_score_ema3", "degraded"]], on="trade_date"
        )
        (result,) = threshold_analysis(
            merged,
            score_column="risk_score_ema3",
            degraded_column="degraded",
            settings=_settings(exclude_degraded=True),
        )
        assert result["flagged"]["count"] == 1


class TestPermutationPvalue:
    def test_separated_distributions_have_small_p(self):
        p = permutation_pvalue([-5.0, -5.0, -5.0], [5.0] * 7, 500, seed=1)
        assert p is not None and p < 0.05

    def test_identical_distributions_have_large_p(self):
        p = permutation_pvalue([1.0, 2.0, 3.0], [1.0, 2.0, 3.0] * 2, 500, seed=1)
        assert p is not None and p > 0.2

    def test_empty_group_returns_none(self):
        assert permutation_pvalue([], [1.0], 100, seed=1) is None


class TestFlapping:
    BANDS = ["LOW", "LOW", "ELEVATED", "HIGH", "ELEVATED", "HIGH", "HIGH", "NEUTRAL"]

    def test_band_runs_compress_and_drop_missing(self):
        assert band_runs(["LOW", None, "LOW", float("nan"), "HIGH"]) == [
            ("LOW", 2),
            ("HIGH", 1),
        ]

    def test_metrics_counts(self):
        metrics = flapping_metrics(self.BANDS, [["ELEVATED", "HIGH"]])
        assert metrics["observed_days"] == 8
        assert metrics["transitions"] == 5
        assert metrics["round_trips"] == {"ELEVATED<->HIGH": 2}
        assert metrics["dwell"]["LOW"] == {
            "runs": 1,
            "mean_days": 2.0,
            "median_days": 2.0,
            "min_days": 2,
            "max_days": 2,
        }
        assert metrics["dwell"]["HIGH"]["runs"] == 2
        assert metrics["dwell"]["HIGH"]["mean_days"] == pytest.approx(1.5)
        assert metrics["transitions_per_20d"] == pytest.approx(5 / 8 * 20)

    def test_empty_sequence(self):
        metrics = flapping_metrics([], [["ELEVATED", "HIGH"]])
        assert metrics["transitions"] == 0
        assert metrics["transitions_per_20d"] is None


class TestEpisodes:
    def test_prior_close_and_premarket_scores(self, store):
        store.replace_day(
            date(2026, 7, 1),
            "close",
            {"risk_score_ema3": 70.5, "risk_band": "HIGH", "kospi_close": 400.0},
        )
        store.replace_day(
            date(2026, 7, 2),
            "close",
            {"risk_score_ema3": 88.0, "risk_band": "CRITICAL", "kospi_close": 380.0},
        )
        store.replace_day(
            date(2026, 7, 2),
            "premarket",
            {"risk_score_ema3": 76.0, "risk_band": "HIGH"},
        )
        close = store.read_range(snapshot="close")
        premarket = store.read_range(snapshot="premarket")
        (row,) = episode_rows(close, premarket, _settings(episodes=["2026-07-02"]))
        assert row["prior_close"]["trade_date"] == "2026-07-01"
        assert row["prior_close"]["score"] == pytest.approx(70.5)
        assert row["premarket"]["score"] == pytest.approx(76.0)
        assert row["close"]["score"] == pytest.approx(88.0)

    def test_missing_rows_reported_as_none(self, store):
        store.replace_day(
            date(2026, 7, 2),
            "close",
            {"risk_score_ema3": 88.0, "kospi_close": 380.0},
        )
        close = store.read_range(snapshot="close")
        (row,) = episode_rows(close, None, _settings(episodes=["2026-07-02"]))
        assert row["prior_close"] is None
        assert row["premarket"] is None


class TestBuildReport:
    def test_none_when_no_scores(self, store):
        store.replace_day(date(2026, 7, 1), "close", {"kospi_close": 400.0})
        frame = store.read_range(snapshot="close")
        assert build_report(frame, None, _settings()) is None

    def test_price_column_fallback_to_k200_close(self, store):
        days = _trading_days(date(2026, 6, 1), 3)
        for i, day in enumerate(days):
            store.replace_day(
                day,
                "close",
                {"risk_score_ema3": 10.0, "k200_close": 100.0 + i},
            )
        frame = store.read_range(snapshot="close")
        report = build_report(frame, None, _settings(episodes=[]))
        assert report is not None
        assert report["price_column"] == "k200_close"
        assert report["score_column"] == "risk_score_ema3"


class TestMainCli:
    def test_end_to_end_writes_reports(self, store, tmp_path, capsys):
        days, rows = _score_fixture_rows()
        for row in rows:
            store.replace_day(row["trade_date"], "close", row)
        out_dir = tmp_path / "reports"

        rc = main(
            [
                "--parquet-root",
                str(store.root),
                "--out-dir",
                str(out_dir),
                "--tag",
                "unit",
            ]
        )

        assert rc == 0
        json_path = out_dir / "market_risk_validation_unit.json"
        md_path = out_dir / "market_risk_validation_unit.md"
        assert json_path.exists() and md_path.exists()
        report = json.loads(json_path.read_text())
        assert report["status"] == "ok"
        assert report["close_rows"] == 10
        assert {"discrimination", "flapping", "episodes"} <= set(report)
        assert "Threshold discrimination" in capsys.readouterr().out

    def test_insufficient_data_path(self, tmp_path, capsys):
        rc = main(
            [
                "--parquet-root",
                str(tmp_path / "empty"),
                "--out-dir",
                str(tmp_path / "reports"),
            ]
        )
        assert rc == 0
        assert "insufficient data" in capsys.readouterr().out
        assert not (tmp_path / "reports").exists()
