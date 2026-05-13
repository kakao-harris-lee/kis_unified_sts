"""Tests for forecast Redis + ClickHouse publisher."""
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from shared.forecasting.forecast_publisher import ForecastPublisher
from shared.forecasting.models import EventScore, VolForecast


@pytest.fixture
def redis_mock():
    r = MagicMock()
    r.set = MagicMock(return_value=True)
    r.publish = MagicMock(return_value=1)
    return r


@pytest.fixture
def ch_mock():
    c = MagicMock()
    c.execute = MagicMock()
    return c


def _make_vf(forecast_pct=18.0):
    return VolForecast(
        asof=datetime.now(UTC),
        horizon_minutes=15,
        forecast_pct=forecast_pct,
        forecast_atr_equivalent=3.0,
        regime_percentile=50.0,
        model_version="har_rv_v1",
        confidence=0.3,
    )


def test_publish_vol_sets_redis_with_ttl(redis_mock, ch_mock):
    pub = ForecastPublisher(redis=redis_mock, clickhouse=ch_mock, vol_ttl_s=120)
    vf = _make_vf()
    pub.publish_vol_forecast(vf)
    redis_mock.set.assert_called_once()
    args, kwargs = redis_mock.set.call_args
    assert args[0] == "forecast:vol:current"
    assert kwargs.get("ex") == 120 or (len(args) >= 3 and args[2] == 120)


def test_publish_vol_inserts_clickhouse(redis_mock, ch_mock):
    pub = ForecastPublisher(redis=redis_mock, clickhouse=ch_mock, vol_ttl_s=120)
    vf = _make_vf()
    pub.publish_vol_forecast(vf)
    ch_mock.execute.assert_called_once()
    sql = ch_mock.execute.call_args[0][0]
    assert "kospi.vol_forecasts" in sql
    assert "INSERT" in sql.upper()


def test_publish_vol_skips_nan(redis_mock, ch_mock):
    pub = ForecastPublisher(redis=redis_mock, clickhouse=ch_mock, vol_ttl_s=120)
    vf = _make_vf(forecast_pct=float("nan"))
    pub.publish_vol_forecast(vf)
    redis_mock.set.assert_not_called()
    ch_mock.execute.assert_not_called()


def test_publish_vol_handles_redis_failure(redis_mock, ch_mock):
    redis_mock.set.side_effect = RuntimeError("redis down")
    pub = ForecastPublisher(redis=redis_mock, clickhouse=ch_mock, vol_ttl_s=120)
    vf = _make_vf()
    # Should not raise — log + continue
    pub.publish_vol_forecast(vf)
    # ClickHouse still attempted
    ch_mock.execute.assert_called_once()


def test_publish_event_publishes_pubsub_and_persists(redis_mock, ch_mock):
    pub = ForecastPublisher(redis=redis_mock, clickhouse=ch_mock, vol_ttl_s=120)
    es = EventScore(
        asof=datetime.now(UTC),
        impact_score=85,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    pub.publish_event_score(es)
    redis_mock.publish.assert_called_once_with("forecasting:events", es.to_json())
    # also SET forecast:event:latest
    set_calls = [c for c in redis_mock.set.call_args_list if c.args[0] == "forecast:event:latest"]
    assert len(set_calls) == 1
    ch_mock.execute.assert_called_once()
    sql = ch_mock.execute.call_args[0][0]
    assert "kospi.event_scores" in sql


def test_publish_event_handles_clickhouse_failure(redis_mock, ch_mock):
    ch_mock.execute.side_effect = RuntimeError("clickhouse down")
    pub = ForecastPublisher(redis=redis_mock, clickhouse=ch_mock, vol_ttl_s=120)
    es = EventScore(
        asof=datetime.now(UTC),
        impact_score=85,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    # Redis publish still happens, ClickHouse failure logged
    pub.publish_event_score(es)
    redis_mock.publish.assert_called_once()
