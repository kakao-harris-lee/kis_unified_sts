import datetime as dt
from unittest.mock import MagicMock


def _vf_json(asof_iso, regime_percentile, fresh_age_s=60):
    """Build a VolForecast JSON blob the live reader can parse."""
    import json
    return json.dumps({
        "asof": asof_iso,
        "horizon_minutes": 15,
        "forecast_pct": 18.0,
        "forecast_atr_equivalent": 3.0,
        "regime_percentile": regime_percentile,
        "model_version": "har_rv_v1",
        "confidence": 0.3,
    })


def test_latest_vol_at_returns_redis_vol_when_fresh():
    from shared.strategy.gates.live_inputs import LiveVolInputs
    redis = MagicMock()
    asof = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=30)
    redis.get.return_value = _vf_json(asof.isoformat(), 72.5)
    cli = MagicMock()
    inp = LiveVolInputs(redis=redis, ch_client=cli)
    result = inp.latest_vol_at(dt.datetime(2026, 5, 22, 9, 0, 0))
    assert result is not None
    ts_naive, regime_pct = result
    assert regime_pct == 72.5
    assert ts_naive.tzinfo is None  # tz-stripped for bisect-style consumers


def test_latest_vol_at_returns_none_when_redis_empty():
    from shared.strategy.gates.live_inputs import LiveVolInputs
    redis = MagicMock()
    redis.get.return_value = None
    inp = LiveVolInputs(redis=redis, ch_client=MagicMock())
    assert inp.latest_vol_at(dt.datetime(2026, 5, 22, 9, 0, 0)) is None


def test_latest_vol_at_returns_none_when_stale():
    from shared.strategy.gates.live_inputs import LiveVolInputs
    redis = MagicMock()
    # asof is 5 minutes old vs now → exceeds 120s default max_age_s
    old = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=5)
    redis.get.return_value = _vf_json(old.isoformat(), 72.5)
    inp = LiveVolInputs(redis=redis, ch_client=MagicMock())
    now = dt.datetime(2026, 5, 22, 9, 0, 0)
    assert inp.latest_vol_at(now) is None  # stale → PERMISSIVE


def test_latest_vol_at_swallows_redis_exception():
    from shared.strategy.gates.live_inputs import LiveVolInputs
    redis = MagicMock()
    redis.get.side_effect = RuntimeError("redis down")
    inp = LiveVolInputs(redis=redis, ch_client=MagicMock())
    # MUST NOT raise — degrade to None
    assert inp.latest_vol_at(dt.datetime(2026, 5, 22, 9, 0, 0)) is None


def test_events_within_queries_ch_and_filters_window():
    from shared.strategy.gates.live_inputs import LiveVolInputs
    cli = MagicMock()
    cli.execute.return_value = [
        (dt.datetime(2026, 5, 22, 9, 5), 85),
        (dt.datetime(2026, 5, 22, 8, 50), 90),
    ]
    inp = LiveVolInputs(redis=MagicMock(), ch_client=cli)
    out = inp.events_within(dt.datetime(2026, 5, 22, 9, 10), 15)
    # CH SELECT handled the filtering; both rows are returned as-is
    assert len(out) == 2
    assert out[0][1] == 85
    assert out[1][1] == 90


def test_events_within_swallows_ch_exception():
    from shared.strategy.gates.live_inputs import LiveVolInputs
    cli = MagicMock()
    cli.execute.side_effect = RuntimeError("ch down")
    inp = LiveVolInputs(redis=MagicMock(), ch_client=cli)
    assert inp.events_within(dt.datetime(2026, 5, 22, 9, 0), 15) == []


def test_macro_for_always_returns_none_in_live():
    # Live EntryContext has no macro_overnight; LiveVolInputs returns None
    # → RegimeGate's require_overnight_us_direction flag degrades PERMISSIVE.
    from shared.strategy.gates.live_inputs import LiveVolInputs
    inp = LiveVolInputs(redis=MagicMock(), ch_client=MagicMock())
    assert inp.macro_for(dt.date(2026, 5, 22)) is None
