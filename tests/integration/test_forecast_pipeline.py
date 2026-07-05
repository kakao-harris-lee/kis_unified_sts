"""Integration tests for forecasting service main loop."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest


def _fake_vol_forecast():
    from shared.forecasting.models import VolForecast

    return VolForecast(
        asof=datetime.now(UTC),
        horizon_minutes=15,
        forecast_pct=18.0,
        forecast_atr_equivalent=3.0,
        regime_percentile=50.0,
        model_version="har_rv_v1",
        confidence=0.3,
    )


def _make_service(cfg, tmp_path, redis):
    from services.forecasting.main import ForecastingService

    storage = MagicMock()
    tax_path = tmp_path / "event_taxonomy.yaml"
    tax_path.write_text("events: []\nunknown_match_score: 40")
    return ForecastingService(
        config=cfg,
        redis_client=redis,
        storage_client=storage,
        taxonomy_path=tax_path,
        llm_client=None,
    )


@pytest.fixture
def cfg(tmp_path):
    yaml_path = tmp_path / "forecasting.yaml"
    yaml_path.write_text("""
forecasting:
  publisher_enabled: true
  forecast_loop_interval_seconds: 1
  forecast_redis_ttl_seconds: 120
  horizon_minutes: 15
  har_rv:
    refit_hour_kst: 15
    refit_minute_kst: 35
    history_days: 60
    holdout_days: 7
    min_r2_oos: 0.0
    consecutive_fail_disable_threshold: 7
  event_scorer:
    default_ttl_minutes: 30
    rule_first: true
    llm_fallback_enabled: false
    neutral_score_on_failure: 50
""")
    from shared.forecasting.config import ForecastingConfig

    return ForecastingConfig.from_yaml(str(yaml_path))


def test_read_current_close_accepts_canonical_tick_schema(cfg, tmp_path):
    redis = MagicMock()
    redis.xrevrange = MagicMock(
        return_value=[
            (
                b"1700000000000-0",
                {
                    b"schema_version": b"1",
                    b"asset": b"futures",
                    b"symbol": b"101V3000",
                    b"price": b"350.5",
                    b"timestamp": b"1700000000.0",
                },
            )
        ]
    )
    service = _make_service(cfg, tmp_path, redis)

    assert service._read_current_close() == 350.5


def test_read_current_close_preserves_legacy_close_priority(cfg, tmp_path):
    redis = MagicMock()
    redis.xrevrange = MagicMock(
        return_value=[
            (
                b"1700000000000-0",
                {
                    b"symbol": b"101V3000",
                    b"close": b"350.5",
                    b"current_price": b"351.5",
                    b"price": b"352.5",
                },
            )
        ]
    )
    service = _make_service(cfg, tmp_path, redis)

    assert service._read_current_close() == 350.5


@pytest.mark.asyncio
async def test_service_start_starts_forecast_loop(cfg, tmp_path):
    redis = MagicMock()
    redis.get = MagicMock(return_value=None)
    redis.set = MagicMock()
    redis.publish = MagicMock()
    # The forecast loop reads the current futures mark from the tick stream
    # (market_ingest republishes it); supply one so a forecast is produced.
    redis.xrevrange = MagicMock(
        return_value=[
            (b"1700000000000-0", {b"symbol": b"101V3000", b"close": b"350.5"})
        ]
    )
    # pubsub returns an object that returns None for get_message (no events)
    pubsub_obj = MagicMock()
    pubsub_obj.get_message = MagicMock(return_value=None)
    pubsub_obj.subscribe = MagicMock()
    pubsub_obj.unsubscribe = MagicMock()
    pubsub_obj.close = MagicMock()
    redis.pubsub = MagicMock(return_value=pubsub_obj)

    service = _make_service(cfg, tmp_path, redis)

    # Mock forecaster fit so no historical data needed
    service._forecaster = MagicMock()
    service._forecaster.forecast = MagicMock(return_value=_fake_vol_forecast())
    service._forecaster._coefficients = MagicMock()  # treat as fit

    # Run for 2 ticks
    task = asyncio.create_task(service.start())
    await asyncio.sleep(2.5)
    await service.stop()
    await asyncio.wait_for(task, timeout=5)

    # Forecast was published at least once
    assert any(c.args[0] == "forecast:vol:current" for c in redis.set.call_args_list)


@pytest.mark.asyncio
async def test_service_stop_cancels_tasks(cfg, tmp_path):
    redis = MagicMock()
    redis.set = MagicMock()
    pubsub_obj = MagicMock()
    pubsub_obj.get_message = MagicMock(return_value=None)
    pubsub_obj.subscribe = MagicMock()
    pubsub_obj.unsubscribe = MagicMock()
    pubsub_obj.close = MagicMock()
    redis.pubsub = MagicMock(return_value=pubsub_obj)

    service = _make_service(cfg, tmp_path, redis)
    service._forecaster = MagicMock()
    service._forecaster._coefficients = MagicMock()
    service._forecaster.forecast = MagicMock(return_value=_fake_vol_forecast())

    task = asyncio.create_task(service.start())
    await asyncio.sleep(0.5)
    await service.stop()
    await asyncio.wait_for(task, timeout=5)
    # No raise = good
