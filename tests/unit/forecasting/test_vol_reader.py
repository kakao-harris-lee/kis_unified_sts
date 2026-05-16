from datetime import UTC, datetime

from shared.forecasting.models import VolForecast
from shared.forecasting.vol_reader import read_latest_vol_forecast


class _FakeRedis:
    def __init__(self, value):
        self._value = value

    def get(self, key):  # noqa: ARG002
        return self._value


def _vf_json() -> str:
    return VolForecast(
        asof=datetime(2026, 5, 16, 0, 0, tzinfo=UTC),
        horizon_minutes=15,
        forecast_pct=18.5,
        forecast_atr_equivalent=1.2,
        regime_percentile=72.0,
        model_version="har_rv_v1",
        confidence=0.4,
    ).to_json()


def test_returns_none_when_key_absent():
    assert read_latest_vol_forecast(_FakeRedis(None)) is None


def test_returns_none_on_garbage():
    assert read_latest_vol_forecast(_FakeRedis("not-json")) is None


def test_parses_vol_forecast():
    vf = read_latest_vol_forecast(_FakeRedis(_vf_json()))
    assert vf is not None
    assert vf.regime_percentile == 72.0
    assert vf.forecast_atr_equivalent == 1.2


def test_redis_error_returns_none():
    class _Boom:
        def get(self, key):  # noqa: ARG002
            raise RuntimeError("redis down")

    assert read_latest_vol_forecast(_Boom()) is None
