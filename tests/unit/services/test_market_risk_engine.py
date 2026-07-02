"""Unit tests for services.market_risk_engine (unified roadmap Phase 1).

Hermetic: fakeredis (sync, decode_responses), ParquetMarketStructureStore on
tmp_path, stub calendar/ledger/notifier. Covers the §4.3 Redis publication
contract (field names + TTLs), close-row score persistence idempotency, band
state fallback, band-transition audit/alerts, degraded-entry alerts, session
filtering, and HAR-RV vol injection.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import fakeredis
import pytest

from services.market_risk_engine.main import run_mode
from shared.risk.market_risk_score import (
    BAND_COLUMN,
    REGIME_COLUMN,
    SCORE_COLUMN,
    SCORE_EMA_COLUMN,
    MarketRiskConfig,
)
from shared.storage.market_structure_store import ParquetMarketStructureStore

TRADE_DAY = date(2026, 7, 2)  # Thursday, KRX market day
CLOSE_TS = datetime(2026, 7, 2, 18, 45)
INTRADAY_TS = datetime(2026, 7, 2, 10, 30)

_CONTRACT_FIELDS = {
    "score",
    "score_ema3",
    "band",
    "regime",
    "degraded",
    "coverage_ratio",
    "missing_components",
    "asof_ts",
    "kind",
    "components",
}


class _AlwaysOpenCalendar:
    def is_market_day(self, _day: date) -> bool:
        return True


class _ClosedCalendar:
    def is_market_day(self, _day: date) -> bool:
        return False


class FakeLedger:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record_risk_event(self, event) -> str:
        self.events.append(dict(event))
        return "risk-1"


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send_message(self, message: str, **_kwargs) -> None:
        self.messages.append(message)


@pytest.fixture
def redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def store(tmp_path):
    return ParquetMarketStructureStore(tmp_path / "market")


@pytest.fixture
def config():
    return MarketRiskConfig(
        engine={
            "window_days": 240,
            "min_periods": 3,
            "zscore_clip": 2.0,
            "ema_span": 3,
            "min_coverage_ratio": 0.6,
            "band_source": "raw",
        },
        components={
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
        unified_regime={"trend_column": "k200_ret_20d"},
    )


def _seed_history(store, days: int = 8, **extra_columns) -> None:
    """Weekday close rows ending the day before TRADE_DAY."""
    written = 0
    day = TRADE_DAY - timedelta(days=1)
    rows: list[tuple[date, float]] = []
    while written < days:
        if day.weekday() < 5:
            rows.append((day, float(days - written)))
            written += 1
        day -= timedelta(days=1)
    for row_day, value in rows:
        row = {
            "asof_ts": datetime(row_day.year, row_day.month, row_day.day, 18, 40),
            "flow_cum": value,
            "usdkrw": 1300.0 + value,
            "k200_ret_20d": 1.0,
        }
        for column, val in extra_columns.items():
            row[column] = val
        store.replace_day(row_day, "close", row)


def _risky_row() -> dict:
    return {
        "asof_ts": datetime(2026, 7, 2, 18, 40),
        "flow_cum": -10_000.0,  # far below history → flow sub ~high
        "usdkrw": 9_999.0,  # far above history → fx sub ~high
        "k200_ret_20d": -5.0,
    }


def _run(mode, *, store, redis, config, now, ledger=None, notifier=None):
    return run_mode(
        mode,
        store=store,
        redis=redis,
        config=config,
        now=now,
        calendar=_AlwaysOpenCalendar(),
        ledger=ledger or FakeLedger(),
        notifier=notifier or FakeNotifier(),
    )


# ---------------------------------------------------------------------------
# §4.3 Redis contract
# ---------------------------------------------------------------------------


class TestRedisContract:
    def test_latest_hash_fields_and_ttl(self, redis, store, config):
        _seed_history(store)
        store.replace_day(TRADE_DAY, "close", _risky_row())

        assert _run("close", store=store, redis=redis, config=config, now=CLOSE_TS) == 0

        latest = redis.hgetall(config.redis.latest_key)
        assert set(latest) == _CONTRACT_FIELDS
        assert latest["kind"] == "close"
        assert latest["degraded"] == "false"
        assert float(latest["score"]) > 85.0
        assert float(latest["score_ema3"]) > 85.0
        assert latest["band"] == "CRITICAL"
        assert latest["regime"] == "RISK_OFF"
        assert float(latest["coverage_ratio"]) == pytest.approx(1.0)
        assert json.loads(latest["missing_components"]) == []
        # asof_ts is naive-KST ISO.
        assert latest["asof_ts"] == CLOSE_TS.isoformat()
        ttl = redis.ttl(config.redis.latest_key)
        assert 0 < ttl <= config.redis.latest_ttl_seconds

    def test_components_payload_shape(self, redis, store, config):
        _seed_history(store)
        store.replace_day(TRADE_DAY, "close", _risky_row())
        _run("close", store=store, redis=redis, config=config, now=CLOSE_TS)

        components = json.loads(redis.hgetall(config.redis.latest_key)["components"])
        assert set(components) == {"flow", "fx"}
        for payload in components.values():
            assert set(payload) == {"sub", "weight", "contribution", "raw", "asof"}
            assert payload["sub"] is not None
            assert payload["contribution"] is not None
            assert payload["asof"]
        assert components["flow"]["weight"] == 60
        assert components["flow"]["raw"]["flow_cum"] == -10_000.0
        total = sum(payload["contribution"] for payload in components.values())
        assert total == pytest.approx(
            float(redis.hgetall(config.redis.latest_key)["score"]), abs=0.01
        )

    def test_stream_event_fields_and_ttl(self, redis, store, config):
        _seed_history(store)
        store.replace_day(TRADE_DAY, "close", _risky_row())
        _run("close", store=store, redis=redis, config=config, now=CLOSE_TS)

        entries = redis.xrange(config.redis.stream_key)
        assert len(entries) == 1
        event = entries[0][1]
        assert set(event) == {"kind", "score", "band", "band_changed", "prev_band"}
        assert event["kind"] == "close"
        assert event["band"] == "CRITICAL"
        assert event["band_changed"] == "false"  # initial adoption, no transition
        assert event["prev_band"] == ""
        ttl = redis.ttl(config.redis.stream_key)
        assert 0 < ttl <= config.redis.stream_ttl_seconds

    def test_regime_daily_written_on_close_only(self, redis, store, config):
        _seed_history(store)
        store.replace_day(TRADE_DAY, "close", _risky_row())
        _run("close", store=store, redis=redis, config=config, now=CLOSE_TS)

        payload = json.loads(redis.get(config.redis.regime_daily_key))
        assert set(payload) == {"date", "regime", "score", "band"}
        assert payload["date"] == TRADE_DAY.isoformat()
        assert payload["band"] == "CRITICAL"
        assert payload["regime"] == "RISK_OFF"
        assert payload["score"] > 85.0
        ttl = redis.ttl(config.redis.regime_daily_key)
        assert 0 < ttl <= config.redis.regime_daily_ttl_seconds

    def test_intraday_does_not_touch_regime_daily_or_parquet(
        self, redis, store, config
    ):
        _seed_history(store)
        redis.hset(
            config.redis.structure_latest_key,
            mapping={
                "trade_date": TRADE_DAY.isoformat(),
                "snapshot": "premarket",
                "flow_cum": "-10000.0",
                "usdkrw": "9999.0",
                "k200_ret_20d": "-5.0",
            },
        )
        _run("intraday", store=store, redis=redis, config=config, now=INTRADAY_TS)

        assert redis.hgetall(config.redis.latest_key)["kind"] == "intraday"
        assert redis.get(config.redis.regime_daily_key) is None
        frame = store.read_range(TRADE_DAY, TRADE_DAY)
        assert frame.empty  # Redis-only: nothing persisted for the day

    def test_band_state_written_with_ttl(self, redis, store, config):
        _seed_history(store)
        store.replace_day(TRADE_DAY, "close", _risky_row())
        _run("close", store=store, redis=redis, config=config, now=CLOSE_TS)

        state = redis.hgetall(config.redis.band_state_key)
        assert state["band"] == "CRITICAL"
        assert state["degraded"] == "false"
        ttl = redis.ttl(config.redis.band_state_key)
        assert 0 < ttl <= config.redis.band_state_ttl_seconds


# ---------------------------------------------------------------------------
# Parquet close-row score persistence
# ---------------------------------------------------------------------------


class TestClosePersistence:
    def test_close_writes_score_columns_idempotently(self, redis, store, config):
        _seed_history(store)
        store.replace_day(TRADE_DAY, "close", _risky_row())

        _run("close", store=store, redis=redis, config=config, now=CLOSE_TS)
        frame = store.read_range(TRADE_DAY, TRADE_DAY, snapshot="close")
        assert len(frame) == 1
        first = frame.iloc[0].to_dict()
        assert first[SCORE_COLUMN] > 85.0
        assert first[SCORE_EMA_COLUMN] > 85.0
        assert first[BAND_COLUMN] == "CRITICAL"
        assert first[REGIME_COLUMN] == "RISK_OFF"
        assert bool(first["degraded"]) is False
        assert first["sub_flow"] > 85.0
        # Original collector columns survive the merge.
        assert first["flow_cum"] == -10_000.0
        assert bool(first["finalized"]) is True

        _run("close", store=store, redis=redis, config=config, now=CLOSE_TS)
        frame = store.read_range(TRADE_DAY, TRADE_DAY, snapshot="close")
        assert len(frame) == 1
        second = frame.iloc[0].to_dict()
        assert second[SCORE_COLUMN] == pytest.approx(first[SCORE_COLUMN])
        assert second[BAND_COLUMN] == first[BAND_COLUMN]

    def test_premarket_publishes_without_persisting_scores(self, redis, store, config):
        _seed_history(store)
        store.replace_day(
            TRADE_DAY,
            "premarket",
            {
                "asof_ts": datetime(2026, 7, 2, 8, 0),
                "flow_cum": -10_000.0,
                "usdkrw": 9_999.0,
                "k200_ret_20d": -5.0,
            },
        )
        now = datetime(2026, 7, 2, 8, 5)
        _run("premarket", store=store, redis=redis, config=config, now=now)

        assert redis.hgetall(config.redis.latest_key)["kind"] == "premarket"
        frame = store.read_range(TRADE_DAY, TRADE_DAY, snapshot="premarket")
        assert len(frame) == 1
        assert SCORE_COLUMN not in frame.columns


# ---------------------------------------------------------------------------
# Hysteresis state / transitions / alerts / audit
# ---------------------------------------------------------------------------


class TestTransitionsAndAlerts:
    def _seed_state(self, redis, config, band="LOW"):
        redis.hset(
            config.redis.band_state_key,
            mapping={
                "band": band,
                "pending_band": "",
                "pending_count": "0",
                "degraded": "false",
            },
        )

    def test_band_transition_records_ledger_and_alerts(self, redis, store, config):
        _seed_history(store)
        store.replace_day(TRADE_DAY, "close", _risky_row())
        self._seed_state(redis, config, band="LOW")
        ledger = FakeLedger()
        notifier = FakeNotifier()

        _run(
            "close",
            store=store,
            redis=redis,
            config=config,
            now=CLOSE_TS,
            ledger=ledger,
            notifier=notifier,
        )

        event = redis.xrange(config.redis.stream_key)[0][1]
        assert event["band_changed"] == "true"
        assert event["prev_band"] == "LOW"
        assert event["band"] == "CRITICAL"

        assert len(ledger.events) == 1
        recorded = ledger.events[0]
        assert recorded["event_type"] == "market_risk_band_transition"
        assert recorded["asset_class"] == "cross_asset"
        assert recorded["severity"] == "critical"
        assert recorded["prev_band"] == "LOW"
        assert recorded["band"] == "CRITICAL"

        assert len(notifier.messages) == 1
        assert "band change" in notifier.messages[0]
        assert "LOW → CRITICAL" in notifier.messages[0]

    def test_non_notify_transition_is_audited_but_silent(self, redis, store, config):
        _seed_history(store)
        # Mid-range values → score ≈ 50 → NEUTRAL (well beyond LOW+buffer).
        store.replace_day(
            TRADE_DAY,
            "close",
            {
                "asof_ts": datetime(2026, 7, 2, 18, 40),
                "flow_cum": 4.5,
                "usdkrw": 1304.5,
                "k200_ret_20d": 1.0,
            },
        )
        self._seed_state(redis, config, band="LOW")
        ledger = FakeLedger()
        notifier = FakeNotifier()

        _run(
            "close",
            store=store,
            redis=redis,
            config=config,
            now=CLOSE_TS,
            ledger=ledger,
            notifier=notifier,
        )

        event = redis.xrange(config.redis.stream_key)[0][1]
        assert event["band_changed"] == "true"
        assert event["band"] == "NEUTRAL"
        assert len(ledger.events) == 1  # audit always
        assert notifier.messages == []  # LOW→NEUTRAL not in notify_bands

    def test_degraded_entry_alerts_once(self, redis, store, config):
        # No structure inputs at all → score None → degraded.
        notifier = FakeNotifier()
        _run(
            "close",
            store=store,
            redis=redis,
            config=config,
            now=CLOSE_TS,
            notifier=notifier,
        )
        latest = redis.hgetall(config.redis.latest_key)
        assert latest["degraded"] == "true"
        assert latest["score"] == ""
        assert json.loads(latest["missing_components"]) == ["flow", "fx"]
        assert len(notifier.messages) == 1
        assert "DEGRADED" in notifier.messages[0]

        # Second run: still degraded but no re-alert (edge-triggered).
        repeat = FakeNotifier()
        _run(
            "close",
            store=store,
            redis=redis,
            config=config,
            now=CLOSE_TS,
            notifier=repeat,
        )
        assert repeat.messages == []

    def test_band_state_falls_back_to_close_rows(self, redis, store, config):
        # Redis state expired: previous band/EMA re-seeded from close rows.
        _seed_history(store, risk_band="LOW", risk_score_ema3=20.0)
        store.replace_day(TRADE_DAY, "close", _risky_row())
        notifier = FakeNotifier()

        _run(
            "close",
            store=store,
            redis=redis,
            config=config,
            now=CLOSE_TS,
            notifier=notifier,
        )

        event = redis.xrange(config.redis.stream_key)[0][1]
        assert event["prev_band"] == "LOW"
        assert event["band_changed"] == "true"
        latest = redis.hgetall(config.redis.latest_key)
        score = float(latest["score"])
        # EMA blends against the stored 20.0 seed: 0.5*score + 0.5*20.
        assert float(latest["score_ema3"]) == pytest.approx(
            0.5 * score + 10.0, abs=0.01
        )


# ---------------------------------------------------------------------------
# Scheduling guards
# ---------------------------------------------------------------------------


class TestSchedulingGuards:
    def test_non_market_day_skips(self, redis, store, config):
        rc = run_mode(
            "close",
            store=store,
            redis=redis,
            config=config,
            now=CLOSE_TS,
            calendar=_ClosedCalendar(),
            ledger=FakeLedger(),
            notifier=FakeNotifier(),
        )
        assert rc == 0
        assert redis.hgetall(config.redis.latest_key) == {}

    def test_intraday_outside_session_skips(self, redis, store, config):
        rc = _run(
            "intraday",
            store=store,
            redis=redis,
            config=config,
            now=datetime(2026, 7, 2, 16, 0),
        )
        assert rc == 0
        assert redis.hgetall(config.redis.latest_key) == {}

    def test_unknown_mode_rejected(self, redis, store, config):
        with pytest.raises(ValueError, match="unknown market-risk mode"):
            run_mode("weekly", store=store, redis=redis, config=config)


# ---------------------------------------------------------------------------
# HAR-RV vol injection
# ---------------------------------------------------------------------------


class TestVolInjection:
    @pytest.fixture
    def vol_config(self):
        return MarketRiskConfig(
            engine={
                "window_days": 240,
                "min_periods": 3,
                "zscore_clip": 2.0,
                "ema_span": 3,
                "min_coverage_ratio": 0.5,
                "band_source": "raw",
            },
            components={
                "vol": {
                    "weight": 100,
                    "signals": [
                        {
                            "column": "har_rv_pred",
                            "kind": "numeric",
                            "method": "percentile",
                            "direction": "high_is_risk",
                            "weight": 1.0,
                        }
                    ],
                }
            },
        )

    def _seed_vol_history(self, store):
        day = TRADE_DAY - timedelta(days=1)
        values = [10.0, 11.0, 12.0, 13.0, 14.0]
        index = 0
        while index < len(values):
            if day.weekday() < 5:
                store.replace_day(
                    day,
                    "close",
                    {
                        "asof_ts": datetime(day.year, day.month, day.day, 18, 40),
                        "har_rv_pred": values[index],
                    },
                )
                index += 1
            day -= timedelta(days=1)

    def test_vol_forecast_injected_and_persisted(self, redis, store, vol_config):
        from shared.forecasting.models import VolForecast

        self._seed_vol_history(store)
        store.replace_day(TRADE_DAY, "close", {"asof_ts": datetime(2026, 7, 2, 18, 40)})
        forecast_asof = datetime(2026, 7, 2, 15, 30)
        redis.set(
            vol_config.redis.vol_forecast_key,
            VolForecast(
                asof=forecast_asof,
                horizon_minutes=15,
                forecast_pct=45.0,
                forecast_atr_equivalent=1.2,
                regime_percentile=99.0,
                model_version="test",
                confidence=0.8,
            ).to_json(),
        )

        _run("close", store=store, redis=redis, config=vol_config, now=CLOSE_TS)

        latest = redis.hgetall(vol_config.redis.latest_key)
        assert latest["degraded"] == "false"
        components = json.loads(latest["components"])
        assert components["vol"]["raw"]["har_rv_pred"] == 45.0
        assert components["vol"]["asof"] == forecast_asof.isoformat()
        assert components["vol"]["sub"] > 85.0  # 45 is a fresh maximum

        # The raw input is persisted so the rolling vol history accumulates.
        frame = store.read_range(TRADE_DAY, TRADE_DAY, snapshot="close")
        assert frame.iloc[0]["har_rv_pred"] == 45.0

    def test_stale_vol_forecast_ignored(self, redis, store, vol_config):
        from shared.forecasting.models import VolForecast

        self._seed_vol_history(store)
        store.replace_day(TRADE_DAY, "close", {"asof_ts": datetime(2026, 7, 2, 18, 40)})
        redis.set(
            vol_config.redis.vol_forecast_key,
            VolForecast(
                asof=CLOSE_TS - timedelta(days=3),
                horizon_minutes=15,
                forecast_pct=45.0,
                forecast_atr_equivalent=1.2,
                regime_percentile=99.0,
                model_version="test",
                confidence=0.8,
            ).to_json(),
        )

        _run("close", store=store, redis=redis, config=vol_config, now=CLOSE_TS)

        latest = redis.hgetall(vol_config.redis.latest_key)
        assert latest["degraded"] == "true"
        assert json.loads(latest["missing_components"]) == ["vol"]


# ---------------------------------------------------------------------------
# Shipped config file sanity (config/market_risk.yaml)
# ---------------------------------------------------------------------------


class TestShippedConfig:
    def test_yaml_parses_with_roadmap_weights(self):
        import yaml

        path = Path(__file__).resolve().parents[3] / "config" / "market_risk.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        config = MarketRiskConfig(**data)

        weights = {name: spec.weight for name, spec in config.components.items()}
        assert weights == {
            "foreign_fut": 25,
            "basis": 15,
            "usdkrw": 15,
            "program": 10,
            "oi": 10,
            "overseas": 10,
            "vol": 10,
            "trend": 5,
        }
        assert [band.name for band in config.ordered_bands()] == [
            "LOW",
            "NEUTRAL",
            "ELEVATED",
            "HIGH",
            "CRITICAL",
        ]
        assert config.engine.window_days == 240
        assert config.hysteresis.buffer_points == 5.0
        assert config.redis.latest_key == "market:risk:latest"
        assert config.redis.stream_key == "stream:market.risk"
        assert config.redis.regime_daily_key == "regime:unified:daily"
