"""Unit tests for DailyBiasProvider."""
from __future__ import annotations
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo
from shared.decision.daily_bias import DailyBiasProvider, bias_from_context

def test_strong_bullish_maps_to_long(): assert bias_from_context("STRONG_BULLISH", confidence=0.7) == "long"
def test_bullish_maps_to_long(): assert bias_from_context("BULLISH", confidence=0.7) == "long"
def test_strong_bearish_maps_to_short(): assert bias_from_context("STRONG_BEARISH", confidence=0.7) == "short"
def test_bearish_maps_to_short(): assert bias_from_context("BEARISH", confidence=0.7) == "short"
def test_neutral_maps_to_flat(): assert bias_from_context("NEUTRAL", confidence=0.7) == "flat"
def test_low_confidence_maps_to_flat(): assert bias_from_context("STRONG_BULLISH", confidence=0.3, bias_min_confidence=0.5) == "flat"
def test_confidence_exactly_at_threshold_passes(): assert bias_from_context("BULLISH", confidence=0.5, bias_min_confidence=0.5) == "long"
def test_non_long_regime_converts_long_to_flat(): assert bias_from_context("STRONG_BULLISH", confidence=0.8, non_long_regimes=["BEAR_STRONG"], regime="BEAR_STRONG") == "flat"
def test_non_long_regime_does_not_affect_short(): assert bias_from_context("STRONG_BEARISH", confidence=0.8, non_long_regimes=["BEAR_STRONG"], regime="BEAR_STRONG") == "short"
def test_non_long_regime_not_matching_passes_through(): assert bias_from_context("BULLISH", confidence=0.8, non_long_regimes=["BEAR_STRONG"], regime="BULL_STRONG") == "long"

def _fake_context(name="BULLISH", confidence=0.7):
    ctx = MagicMock(); ctx.confidence = confidence; ctx.overall_signal.name = name; ctx.regime = "NEUTRAL"; return ctx
def _now_kst(): return datetime(2026, 6, 21, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

def test_compute_and_persist_first_call():
    import fakeredis, json
    r = fakeredis.FakeRedis(); p = DailyBiasProvider(bias_min_confidence=0.5)
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(r, None)):
        assert p.get_or_compute_bias(_fake_context("BULLISH", 0.8), _now_kst()) == "long"
    stored = json.loads(r.get("trading:futures:daily_bias")); assert stored["bias"] == "long" and "computed_at" in stored
def test_idempotent_second_call_reads_redis():
    import fakeredis, json
    r = fakeredis.FakeRedis(); r.set("trading:futures:daily_bias", json.dumps({"bias": "short", "computed_at": "2026-06-21T10:00:00+09:00", "date": "2026-06-21"}), ex=3600)
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(r, None)):
        assert DailyBiasProvider(0.5).get_or_compute_bias(_fake_context("BULLISH", 0.9), _now_kst()) == "short"
def test_stale_date_forces_recompute():
    import fakeredis, json
    r = fakeredis.FakeRedis(); r.set("trading:futures:daily_bias", json.dumps({"bias": "short", "computed_at": "2026-06-20T10:00:00+09:00", "date": "2026-06-20"}), ex=3600)
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(r, None)):
        assert DailyBiasProvider(0.5).get_or_compute_bias(_fake_context("STRONG_BULLISH", 0.9), _now_kst()) == "long"
def test_redis_unavailable_falls_back_to_flat():
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(None, None)):
        assert DailyBiasProvider(0.5).get_or_compute_bias(_fake_context("BULLISH", 0.9), _now_kst()) == "flat"
def test_no_context_returns_flat():
    import fakeredis
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(fakeredis.FakeRedis(), None)):
        assert DailyBiasProvider(0.5).get_or_compute_bias(None, _now_kst()) == "flat"
def test_ttl_set_to_eod():
    import fakeredis
    r = fakeredis.FakeRedis()
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(r, None)):
        DailyBiasProvider(0.5).get_or_compute_bias(_fake_context("BULLISH", 0.8), _now_kst())
    assert r.ttl("trading:futures:daily_bias") > 0


# ---------------------------------------------------------------------------
# I2: intraday bias refresh for flat → directional upgrade
# ---------------------------------------------------------------------------

def _stale_flat_payload(minutes_old: int = 65, date_str: str = "2026-06-21") -> str:
    """Return a Redis JSON payload representing a stale flat bias."""
    import json
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    computed_at = _now_kst() - timedelta(minutes=minutes_old)
    return json.dumps({"bias": "flat", "computed_at": computed_at.isoformat(), "date": date_str})


def _non_flat_payload(bias: str = "long", minutes_old: int = 10, date_str: str = "2026-06-21") -> str:
    """Return a Redis JSON payload representing a recent non-flat bias."""
    import json
    from datetime import timedelta
    computed_at = _now_kst() - timedelta(minutes=minutes_old)
    return json.dumps({"bias": bias, "computed_at": computed_at.isoformat(), "date": date_str})


def test_flat_bias_refreshes_after_window():
    """Stale flat bias (> bias_refresh_minutes ago) is re-evaluated when context upgrades."""
    import fakeredis, json
    r = fakeredis.FakeRedis()
    # Seed a flat bias computed 65 minutes ago.
    r.set("trading:futures:daily_bias", _stale_flat_payload(minutes_old=65), ex=3600)
    # New context has STRONG_BULLISH with high confidence → should upgrade to long.
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(r, None)):
        result = DailyBiasProvider(bias_min_confidence=0.5, bias_refresh_minutes=60).get_or_compute_bias(
            _fake_context("STRONG_BULLISH", 0.9), _now_kst()
        )
    assert result == "long", f"Expected 'long' after stale flat refresh, got {result!r}"
    # Verify Redis was updated with the new directional bias.
    stored = json.loads(r.get("trading:futures:daily_bias"))
    assert stored["bias"] == "long"


def test_flat_bias_within_refresh_window_is_not_recomputed():
    """A flat bias computed less than bias_refresh_minutes ago stays flat (no recompute)."""
    import fakeredis
    r = fakeredis.FakeRedis()
    # Seed a fresh flat bias computed only 10 minutes ago (well within 60-min window).
    r.set("trading:futures:daily_bias", _stale_flat_payload(minutes_old=10), ex=3600)
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(r, None)):
        result = DailyBiasProvider(bias_min_confidence=0.5, bias_refresh_minutes=60).get_or_compute_bias(
            _fake_context("STRONG_BULLISH", 0.9), _now_kst()
        )
    # Within window → stays flat regardless of context.
    assert result == "flat", f"Expected cached 'flat', got {result!r}"


def test_non_flat_bias_never_refreshed():
    """A non-flat directional bias (long/short) is sticky: never re-evaluated intraday."""
    import fakeredis, json
    r = fakeredis.FakeRedis()
    # Seed a 'long' bias computed 3 hours ago.
    r.set("trading:futures:daily_bias", _non_flat_payload(bias="long", minutes_old=180), ex=3600)
    # Context now says STRONG_BEARISH — must NOT flip to short.
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(r, None)):
        result = DailyBiasProvider(bias_min_confidence=0.5, bias_refresh_minutes=60).get_or_compute_bias(
            _fake_context("STRONG_BEARISH", 0.95), _now_kst()
        )
    assert result == "long", f"Expected sticky 'long', got {result!r}"
    # Redis must still hold the original long value.
    stored = json.loads(r.get("trading:futures:daily_bias"))
    assert stored["bias"] == "long"


def test_flat_refresh_low_confidence_stays_flat():
    """Stale flat bias re-evaluated with low-confidence context stays flat."""
    import fakeredis
    r = fakeredis.FakeRedis()
    r.set("trading:futures:daily_bias", _stale_flat_payload(minutes_old=90), ex=3600)
    # Low-confidence context → bias_from_context returns 'flat'.
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(r, None)):
        result = DailyBiasProvider(bias_min_confidence=0.5, bias_refresh_minutes=60).get_or_compute_bias(
            _fake_context("STRONG_BULLISH", 0.3), _now_kst()  # conf < min_confidence
        )
    assert result == "flat", f"Expected 'flat' (low confidence), got {result!r}"


def test_bias_refresh_minutes_default_preserves_backward_compat():
    """Default bias_refresh_minutes=60 wires through: existing callers with no explicit arg work."""
    from shared.decision.daily_bias import DailyBiasProvider as _P
    p = _P(bias_min_confidence=0.5)
    assert p._bias_refresh_minutes == 60
