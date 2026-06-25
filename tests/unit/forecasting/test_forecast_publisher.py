"""Tests for forecast Redis publisher."""

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
    r.lpush = MagicMock(return_value=1)
    r.ltrim = MagicMock(return_value=True)
    r.expire = MagicMock(return_value=True)
    return r


@pytest.fixture
def storage_mock():
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


def test_publish_vol_sets_redis_with_ttl(redis_mock, storage_mock):
    pub = ForecastPublisher(
        redis=redis_mock, storage_client=storage_mock, vol_ttl_s=120
    )
    vf = _make_vf()
    pub.publish_vol_forecast(vf)
    redis_mock.set.assert_called_once()
    args, kwargs = redis_mock.set.call_args
    assert args[0] == "forecast:vol:current"
    assert kwargs.get("ex") == 120 or (len(args) >= 3 and args[2] == 120)


def test_publish_vol_does_not_write_storage(redis_mock, storage_mock):
    pub = ForecastPublisher(
        redis=redis_mock, storage_client=storage_mock, vol_ttl_s=120
    )
    vf = _make_vf()
    pub.publish_vol_forecast(vf)
    storage_mock.execute.assert_not_called()


def test_publish_vol_works_without_storage(redis_mock):
    pub = ForecastPublisher(redis=redis_mock, storage_client=None, vol_ttl_s=120)
    vf = _make_vf()
    pub.publish_vol_forecast(vf)

    redis_mock.set.assert_called_once()


def test_publish_vol_skips_nan(redis_mock, storage_mock):
    pub = ForecastPublisher(
        redis=redis_mock, storage_client=storage_mock, vol_ttl_s=120
    )
    vf = _make_vf(forecast_pct=float("nan"))
    pub.publish_vol_forecast(vf)
    redis_mock.set.assert_not_called()
    storage_mock.execute.assert_not_called()


def test_publish_vol_handles_redis_failure(redis_mock, storage_mock):
    redis_mock.set.side_effect = RuntimeError("redis down")
    pub = ForecastPublisher(
        redis=redis_mock, storage_client=storage_mock, vol_ttl_s=120
    )
    vf = _make_vf()
    # Should not raise — log + continue
    pub.publish_vol_forecast(vf)
    storage_mock.execute.assert_not_called()


def test_publish_event_publishes_pubsub_and_sets_latest(redis_mock, storage_mock):
    pub = ForecastPublisher(
        redis=redis_mock, storage_client=storage_mock, vol_ttl_s=120
    )
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
    set_calls = [
        c for c in redis_mock.set.call_args_list if c.args[0] == "forecast:event:latest"
    ]
    assert len(set_calls) == 1
    storage_mock.execute.assert_not_called()


def test_publish_event_retains_bounded_history_with_ttl(redis_mock, storage_mock):
    pub = ForecastPublisher(
        redis=redis_mock,
        storage_client=storage_mock,
        vol_ttl_s=120,
        event_history_key="forecast:event:history",
        event_history_maxlen=2,
        event_history_ttl_s=86_400,
    )
    es = EventScore(
        asof=datetime.now(UTC),
        impact_score=85,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )

    pub.publish_event_score(es)

    redis_mock.lpush.assert_called_once_with("forecast:event:history", es.to_json())
    redis_mock.ltrim.assert_called_once_with("forecast:event:history", 0, 1)
    redis_mock.expire.assert_called_once_with("forecast:event:history", 86_400)
    storage_mock.execute.assert_not_called()


def test_publish_event_works_without_storage(redis_mock):
    pub = ForecastPublisher(redis=redis_mock, storage_client=None, vol_ttl_s=120)
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
    set_calls = [
        c for c in redis_mock.set.call_args_list if c.args[0] == "forecast:event:latest"
    ]
    assert len(set_calls) == 1


def test_publish_event_ignores_storage_client(redis_mock, storage_mock):
    storage_mock.execute.side_effect = RuntimeError("storage down")
    pub = ForecastPublisher(
        redis=redis_mock, storage_client=storage_mock, vol_ttl_s=120
    )
    es = EventScore(
        asof=datetime.now(UTC),
        impact_score=85,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    # Redis publish still happens; storage client is ignored.
    pub.publish_event_score(es)
    redis_mock.publish.assert_called_once()
    storage_mock.execute.assert_not_called()
