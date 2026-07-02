"""Market Risk Score library tests (shared/risk/market_risk_score.py).

Hermetic: pure functions plus a tmp_path Parquet store for hindcast. Covers
sub-score normalization (percentile / clipped z-score / categorical),
missing-component renormalization + coverage, EMA smoothing, band boundaries,
transition hysteresis, unified-regime mapping, and hindcast look-ahead
freedom + idempotent close-row writes.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from shared.risk.market_risk_score import (
    BAND_COLUMN,
    DEGRADED_COLUMN,
    REGIME_COLUMN,
    SCORE_COLUMN,
    SCORE_EMA_COLUMN,
    BandState,
    MarketRiskConfig,
    apply_hysteresis,
    band_for,
    compose_score,
    compute_component,
    compute_market_risk,
    ema_update,
    hindcast,
    map_unified_regime,
    percentile_score,
    risk_row_fields,
    seed_state_from_records,
    zscore_score,
)
from shared.storage.market_structure_store import ParquetMarketStructureStore

DAY = date(2026, 7, 2)


def _config(**overrides) -> MarketRiskConfig:
    """Small two-component config with permissive history requirements."""
    data = {
        "engine": {
            "window_days": 240,
            "min_periods": 3,
            "zscore_clip": 2.0,
            "ema_span": 3,
            "min_coverage_ratio": 0.6,
            "band_source": "raw",
        },
        "components": {
            "flow": {
                "weight": 60,
                "signals": [
                    {
                        "column": "flow_cum",
                        "kind": "numeric",
                        "method": "percentile",
                        "direction": "low_is_risk",
                        "weight": 1.0,
                    }
                ],
            },
            "fx": {
                "weight": 40,
                "signals": [
                    {
                        "column": "usdkrw",
                        "kind": "numeric",
                        "method": "percentile",
                        "direction": "high_is_risk",
                        "weight": 1.0,
                    }
                ],
            },
        },
        "unified_regime": {"trend_column": "k200_ret_20d"},
    }
    data.update(overrides)
    return MarketRiskConfig(**data)


def _history(days: int, **columns) -> list[dict]:
    """`days` rows ending the day before DAY; column values are sequences."""
    rows = []
    for offset in range(days):
        row = {"trade_date": DAY - timedelta(days=days - offset)}
        for column, values in columns.items():
            row[column] = values[offset]
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Normalization primitives
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_percentile_of_new_maximum(self):
        window = [float(v) for v in range(1, 10)]
        assert percentile_score(window, 10.0) == pytest.approx(95.0)

    def test_percentile_midrank_ties(self):
        window = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
        # value 5 ties the existing 5: (4 less + 0.5*2 equal) / 10.
        assert percentile_score(window, 5.0) == pytest.approx(50.0)

    def test_percentile_of_new_minimum(self):
        window = [float(v) for v in range(1, 10)]
        assert percentile_score(window, 0.0) == pytest.approx(5.0)

    def test_zscore_clips_to_bounds(self):
        window = [-1.0, 1.0, -1.0, 1.0]  # mean 0, std 1
        assert zscore_score(window, 10.0, clip=2.0) == pytest.approx(100.0)
        assert zscore_score(window, -10.0, clip=2.0) == pytest.approx(0.0)

    def test_zscore_center_and_scale(self):
        window = [-1.0, 1.0, -1.0, 1.0]
        assert zscore_score(window, 0.0, clip=2.0) == pytest.approx(50.0)
        assert zscore_score(window, 1.0, clip=2.0) == pytest.approx(75.0)

    def test_zscore_zero_std_is_neutral(self):
        assert zscore_score([5.0, 5.0, 5.0], 9.0, clip=2.0) == pytest.approx(50.0)


class TestComponentComputation:
    def test_direction_inversion_low_is_risk(self):
        config = _config()
        history = _history(5, flow_cum=[1.0, 2.0, 3.0, 4.0, 5.0])
        component = compute_component(
            "flow",
            config.components["flow"],
            {"flow_cum": -10.0},
            history,
            config.engine,
            asof=None,
        )
        # New minimum → percentile ~8.3 → low_is_risk inverts to ~91.7.
        assert component.sub == pytest.approx(100.0 - 100.0 * 0.5 / 6.0)

    def test_insufficient_history_marks_signal_missing(self):
        config = _config()
        history = _history(2, flow_cum=[1.0, 2.0])  # < min_periods=3
        component = compute_component(
            "flow",
            config.components["flow"],
            {"flow_cum": 5.0},
            history,
            config.engine,
            asof=None,
        )
        assert component.sub is None
        assert component.signals[0].reason == "insufficient_history"

    def test_missing_value_marks_signal_missing(self):
        config = _config()
        history = _history(5, flow_cum=[1.0, 2.0, 3.0, 4.0, 5.0])
        component = compute_component(
            "flow",
            config.components["flow"],
            {},
            history,
            config.engine,
            asof=None,
        )
        assert component.sub is None
        assert component.signals[0].reason == "missing"

    def test_signal_renormalization_within_component(self):
        config = _config(
            components={
                "combo": {
                    "weight": 100,
                    "signals": [
                        {
                            "column": "a",
                            "direction": "high_is_risk",
                            "weight": 0.5,
                        },
                        {
                            "column": "b",
                            "direction": "high_is_risk",
                            "weight": 0.5,
                        },
                    ],
                }
            }
        )
        history = _history(5, a=[1.0, 2.0, 3.0, 4.0, 5.0], b=[1.0, 2.0, 3.0, 4.0, 5.0])
        component = compute_component(
            "combo",
            config.components["combo"],
            {"a": 10.0},  # b missing → component = a's sub alone
            history,
            config.engine,
            asof=None,
        )
        assert component.sub == pytest.approx(100.0 * 5.5 / 6.0)

    def test_categorical_mapping_and_unknown_label(self):
        config = _config(
            components={
                "oi": {
                    "weight": 100,
                    "signals": [
                        {
                            "column": "oi_price_signal",
                            "kind": "categorical",
                            "mapping": {"new_shorts": 100, "neutral": 50},
                            "weight": 1.0,
                        }
                    ],
                }
            }
        )
        spec = config.components["oi"]
        risky = compute_component(
            "oi", spec, {"oi_price_signal": "new_shorts"}, [], config.engine, None
        )
        assert risky.sub == pytest.approx(100.0)

        unknown = compute_component(
            "oi", spec, {"oi_price_signal": "sideways"}, [], config.engine, None
        )
        assert unknown.sub is None
        assert unknown.signals[0].reason == "unmapped_label"

    def test_categorical_magnitude_scaling_toward_neutral(self):
        config = _config(
            components={
                "oi": {
                    "weight": 100,
                    "signals": [
                        {
                            "column": "oi_price_signal",
                            "kind": "categorical",
                            "mapping": {"new_shorts": 100},
                            "magnitude_column": "oi_chg",
                            "weight": 1.0,
                        }
                    ],
                }
            }
        )
        spec = config.components["oi"]
        history = _history(5, oi_chg=[100.0, -200.0, 300.0, -400.0, 500.0])
        # Tiny |OI change| → intensity ~0 → sub pulled to ~50.
        weak = compute_component(
            "oi",
            spec,
            {"oi_price_signal": "new_shorts", "oi_chg": 1.0},
            history,
            config.engine,
            None,
        )
        # intensity = percentile(|1| vs [100..500]) = 8.33% → 50 + 50*0.0833.
        assert weak.sub == pytest.approx(50.0 + 50.0 * (0.5 / 6.0))
        assert weak.sub < 60.0
        # Huge |OI change| → intensity ~1 → sub near the mapped 100.
        strong = compute_component(
            "oi",
            spec,
            {"oi_price_signal": "new_shorts", "oi_chg": 10_000.0},
            history,
            config.engine,
            None,
        )
        assert strong.sub > 90.0


# ---------------------------------------------------------------------------
# Score composition / coverage / EMA
# ---------------------------------------------------------------------------


class TestComposeScore:
    def _components(self, config, row, history):
        return {
            name: compute_component(name, spec, row, history, config.engine, None)
            for name, spec in config.components.items()
        }

    def test_full_coverage_weighted_mean(self):
        config = _config()
        history = _history(
            5,
            flow_cum=[1.0, 2.0, 3.0, 4.0, 5.0],
            usdkrw=[1300.0, 1310.0, 1320.0, 1330.0, 1340.0],
        )
        components = self._components(
            config, {"flow_cum": -10.0, "usdkrw": 1400.0}, history
        )
        score, coverage, missing = compose_score(components, config)
        expected_sub = 100.0 * 5.5 / 6.0  # both components land at ~91.7
        assert score == pytest.approx(expected_sub)
        assert coverage == pytest.approx(1.0)
        assert missing == []
        contributions = [component.contribution for component in components.values()]
        assert sum(contributions) == pytest.approx(score)

    def test_missing_component_renormalizes_weights(self):
        config = _config()
        history = _history(5, flow_cum=[1.0, 2.0, 3.0, 4.0, 5.0])
        components = self._components(config, {"flow_cum": -10.0}, history)
        score, coverage, missing = compose_score(components, config)
        # fx (weight 40) missing → score equals flow's sub alone.
        assert score == pytest.approx(100.0 * 5.5 / 6.0)
        assert coverage == pytest.approx(0.6)
        assert missing == ["fx"]

    def test_all_missing_yields_none_score(self):
        config = _config()
        components = self._components(config, {}, [])
        score, coverage, missing = compose_score(components, config)
        assert score is None
        assert coverage == 0.0
        assert missing == ["flow", "fx"]


class TestEma:
    def test_seeds_with_first_value(self):
        assert ema_update(None, 60.0, span=3) == pytest.approx(60.0)

    def test_span3_alpha_half(self):
        assert ema_update(60.0, 80.0, span=3) == pytest.approx(70.0)

    def test_longer_span_smooths_more(self):
        assert ema_update(60.0, 80.0, span=9) == pytest.approx(64.0)


# ---------------------------------------------------------------------------
# Bands / hysteresis / regime
# ---------------------------------------------------------------------------


class TestBands:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (0.0, "LOW"),
            (29.0, "LOW"),
            (29.5, "LOW"),
            (30.0, "NEUTRAL"),
            (54.9, "NEUTRAL"),
            (55.0, "ELEVATED"),
            (69.9, "ELEVATED"),
            (70.0, "HIGH"),
            (84.9, "HIGH"),
            (85.0, "CRITICAL"),
            (100.0, "CRITICAL"),
        ],
    )
    def test_default_band_boundaries(self, score, expected):
        assert band_for(score, _config()) == expected


class TestHysteresis:
    def test_initial_adoption_is_not_a_transition(self):
        band, changed, state = apply_hysteresis(40.0, BandState(), _config())
        assert band == "NEUTRAL"
        assert changed is False
        assert state.band == "NEUTRAL"

    def test_within_buffer_holds_previous_band(self):
        config = _config()
        state = BandState(band="NEUTRAL")
        band, changed, state = apply_hysteresis(57.0, state, config)
        # 57 is only 2 points beyond the 55 boundary → pending, not confirmed.
        assert band == "NEUTRAL"
        assert changed is False
        assert state.pending_band == "ELEVATED"
        assert state.pending_count == 1

    def test_second_consecutive_observation_confirms(self):
        config = _config()
        state = BandState(band="NEUTRAL")
        _, changed, state = apply_hysteresis(57.0, state, config)
        assert changed is False
        band, changed, state = apply_hysteresis(58.0, state, config)
        assert band == "ELEVATED"
        assert changed is True
        assert state.band == "ELEVATED"
        assert state.pending_band is None

    def test_jump_beyond_buffer_confirms_immediately(self):
        config = _config()
        band, changed, state = apply_hysteresis(76.0, BandState(band="NEUTRAL"), config)
        # 76 exceeds the 55 boundary by 21 > 5 → immediate HIGH.
        assert band == "HIGH"
        assert changed is True
        assert state.band == "HIGH"

    def test_downward_transition_uses_lower_bound(self):
        config = _config()
        # From HIGH, 68 is only 2 below the 70 lower bound → hold.
        band, changed, state = apply_hysteresis(68.0, BandState(band="HIGH"), config)
        assert band == "HIGH"
        assert changed is False
        assert state.pending_band == "ELEVATED"
        # 60 is 10 below → immediate drop.
        band, changed, _ = apply_hysteresis(60.0, BandState(band="HIGH"), config)
        assert band == "ELEVATED"
        assert changed is True

    def test_return_to_previous_band_clears_pending(self):
        config = _config()
        state = BandState(band="NEUTRAL")
        _, _, state = apply_hysteresis(57.0, state, config)
        band, changed, state = apply_hysteresis(50.0, state, config)
        assert band == "NEUTRAL"
        assert changed is False
        assert state.pending_band is None
        assert state.pending_count == 0

    def test_none_score_holds_state(self):
        config = _config()
        band, changed, state = apply_hysteresis(
            None,
            BandState(band="HIGH", pending_band="CRITICAL", pending_count=1),
            config,
        )
        assert band == "HIGH"
        assert changed is False
        assert state.pending_band == "CRITICAL"


class TestUnifiedRegime:
    def test_neutral_band_splits_on_trend(self):
        config = _config()
        assert map_unified_regime("NEUTRAL", "up", config) == "RISK_ON"
        assert map_unified_regime("NEUTRAL", "down", config) == "NEUTRAL"
        assert map_unified_regime("NEUTRAL", "unknown", config) == "NEUTRAL"

    def test_high_band_is_risk_off_regardless_of_trend(self):
        config = _config()
        assert map_unified_regime("HIGH", "up", config) == "RISK_OFF"
        assert map_unified_regime("CRITICAL", "down", config) == "RISK_OFF"

    def test_none_band_maps_to_none(self):
        assert map_unified_regime(None, "up", _config()) is None


# ---------------------------------------------------------------------------
# Full computation
# ---------------------------------------------------------------------------


class TestComputeMarketRisk:
    def test_degraded_below_coverage_threshold(self):
        config = _config()
        history = _history(5, usdkrw=[1300.0, 1310.0, 1320.0, 1330.0, 1340.0])
        # Only fx (weight 40/100 = 0.4 < 0.6) available → degraded.
        result, state = compute_market_risk(
            current_row={"usdkrw": 1400.0},
            history=history,
            config=config,
            trade_date=DAY,
            kind="close",
            prev_ema=None,
            band_state=BandState(),
        )
        assert result.degraded is True
        assert result.degraded_entered is True
        assert result.coverage_ratio == pytest.approx(0.4)
        assert result.missing_components == ["flow"]
        assert state.degraded is True

    def test_history_at_or_after_trade_date_rejected(self):
        config = _config()
        history = [{"trade_date": DAY, "flow_cum": 1.0}]
        with pytest.raises(ValueError, match="look-ahead"):
            compute_market_risk(
                current_row={"flow_cum": 1.0},
                history=history,
                config=config,
                trade_date=DAY,
                kind="close",
                prev_ema=None,
                band_state=BandState(),
            )

    def test_ema_and_band_source(self):
        config = _config(
            engine={
                "window_days": 240,
                "min_periods": 3,
                "zscore_clip": 2.0,
                "ema_span": 3,
                "min_coverage_ratio": 0.6,
                "band_source": "ema",
            }
        )
        history = _history(
            5,
            flow_cum=[1.0, 2.0, 3.0, 4.0, 5.0],
            usdkrw=[1300.0, 1310.0, 1320.0, 1330.0, 1340.0],
        )
        result, _ = compute_market_risk(
            current_row={"flow_cum": -10.0, "usdkrw": 1400.0},
            history=history,
            config=config,
            trade_date=DAY,
            kind="close",
            prev_ema=20.0,
            band_state=BandState(band="LOW"),
        )
        expected_raw = 100.0 * 5.5 / 6.0
        assert result.score == pytest.approx(expected_raw)
        assert result.score_ema == pytest.approx(0.5 * expected_raw + 0.5 * 20.0)
        # Band derives from the EMA (≈55.8 → ELEVATED), not the raw ~91.7.
        assert result.raw_band == "ELEVATED"

    def test_risk_row_fields_contract(self):
        config = _config()
        history = _history(
            5,
            flow_cum=[1.0, 2.0, 3.0, 4.0, 5.0],
            usdkrw=[1300.0, 1310.0, 1320.0, 1330.0, 1340.0],
        )
        result, _ = compute_market_risk(
            current_row={
                "flow_cum": -10.0,
                "usdkrw": 1400.0,
                "k200_ret_20d": -3.2,
            },
            history=history,
            config=config,
            trade_date=DAY,
            kind="close",
            prev_ema=None,
            band_state=BandState(),
        )
        fields = risk_row_fields(result)
        assert fields[SCORE_COLUMN] == pytest.approx(result.score)
        assert fields[SCORE_EMA_COLUMN] == pytest.approx(result.score_ema)
        assert fields[BAND_COLUMN] == "CRITICAL"
        assert fields[REGIME_COLUMN] == "RISK_OFF"
        assert fields[DEGRADED_COLUMN] is False
        assert fields["sub_flow"] == pytest.approx(100.0 * 5.5 / 6.0)
        assert fields["sub_fx"] == pytest.approx(100.0 * 5.5 / 6.0)


# ---------------------------------------------------------------------------
# Hindcast (look-ahead freedom + write idempotency)
# ---------------------------------------------------------------------------


def _hindcast_store(tmp_path) -> ParquetMarketStructureStore:
    return ParquetMarketStructureStore(tmp_path / "market")


def _seed_close_rows(store, values, start=date(2026, 6, 1)):
    days = []
    day = start
    for value in values:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        store.replace_day(
            day,
            "close",
            {
                "asof_ts": datetime(day.year, day.month, day.day, 18, 40),
                "flow_cum": value,
                "usdkrw": 1300.0 + value,
                "k200_ret_20d": 1.0,
            },
        )
        days.append(day)
        day += timedelta(days=1)
    return days


class TestHindcast:
    def test_scores_are_free_of_look_ahead(self, tmp_path):
        config = _config()
        store = _hindcast_store(tmp_path)
        days = _seed_close_rows(store, [float(v) for v in range(1, 13)])
        target = days[7]

        baseline = hindcast(store, config, target, target)
        assert len(baseline) == 1
        assert baseline[0].score is not None

        # Rewrite every FUTURE row with extreme values; day-8 must not move.
        for day in days[8:]:
            store.replace_day(
                day,
                "close",
                {
                    "asof_ts": datetime(day.year, day.month, day.day, 18, 40),
                    "flow_cum": -9_999.0,
                    "usdkrw": 9_999.0,
                    "k200_ret_20d": -99.0,
                },
            )
        recomputed = hindcast(store, config, target, target)
        assert recomputed[0].score == pytest.approx(baseline[0].score)
        assert recomputed[0].components["flow"].sub == pytest.approx(
            baseline[0].components["flow"].sub
        )

    def test_window_uses_only_prior_rows(self, tmp_path):
        config = _config()
        store = _hindcast_store(tmp_path)
        days = _seed_close_rows(store, [float(v) for v in range(1, 11)])

        results = hindcast(store, config, days[5], days[-1])
        by_day = {result.trade_date: result for result in results}
        # flow_cum rises monotonically: each day is a fresh maximum vs its
        # PRIOR window → low_is_risk percentile stays pinned near 0 risk.
        for day in days[5:]:
            flow = by_day[day].components["flow"]
            assert flow.sub is not None
            assert flow.sub < 15.0

    def test_early_days_degrade_without_history(self, tmp_path):
        config = _config()
        store = _hindcast_store(tmp_path)
        days = _seed_close_rows(store, [float(v) for v in range(1, 7)])

        results = hindcast(store, config, days[0], days[-1])
        assert results[0].score is None
        assert results[0].degraded is True
        assert results[-1].score is not None

    def test_write_persists_and_is_idempotent(self, tmp_path):
        config = _config()
        store = _hindcast_store(tmp_path)
        days = _seed_close_rows(store, [float(v) for v in range(1, 11)])

        first = hindcast(store, config, days[0], days[-1], write=True)
        frame = store.read_range(days[-1], days[-1], snapshot="close")
        assert len(frame) == 1
        row = frame.iloc[0].to_dict()
        assert row[SCORE_COLUMN] == pytest.approx(first[-1].score)
        assert row[SCORE_EMA_COLUMN] == pytest.approx(first[-1].score_ema)
        assert row[BAND_COLUMN] == first[-1].band
        assert row[REGIME_COLUMN] == first[-1].regime
        # Original raw columns survive the merge.
        assert row["flow_cum"] == 10.0
        assert row["usdkrw"] == 1310.0

        second = hindcast(store, config, days[0], days[-1], write=True)
        frame = store.read_range(days[-1], days[-1], snapshot="close")
        assert len(frame) == 1
        assert frame.iloc[0][SCORE_COLUMN] == pytest.approx(second[-1].score)
        assert [r.score for r in second] == pytest.approx([r.score for r in first])

    def test_seed_state_from_written_history(self, tmp_path):
        config = _config()
        store = _hindcast_store(tmp_path)
        days = _seed_close_rows(store, [float(v) for v in range(1, 11)])
        hindcast(store, config, days[0], days[-1], write=True)

        frame = store.read_range(days[0], days[-1], snapshot="close")
        from shared.risk.market_risk_score import history_records

        prev_ema, state = seed_state_from_records(history_records(frame))
        assert prev_ema is not None
        assert state.band is not None

    def test_invalid_range_rejected(self, tmp_path):
        store = _hindcast_store(tmp_path)
        with pytest.raises(ValueError, match="start"):
            hindcast(store, _config(), DAY, DAY - timedelta(days=1))
