"""Unit tests for early-session trend confirmation in screener."""

from __future__ import annotations

from datetime import datetime

import pytest

from services.screener import (
    KST,
    ScreenerConfig,
    _apply_trend_confirmation,
    _code_set_signature,
    _evaluate_bull_trend_profile,
    _in_trend_confirmation_window,
    _normalize_scores_for_codes,
    _should_publish_snapshot,
)


def _default_eval_kwargs() -> dict[str, float]:
    return {
        "min_return_pct": 0.35,
        "min_positive_ratio": 0.57,
        "min_rising_lows_ratio": 0.50,
        "max_pullback_pct": 0.45,
        "max_single_bar_volume_share_limit": 0.55,
    }


def test_evaluate_bull_trend_profile_passes_persistent_uptrend():
    bars = [
        {"open": 100.0, "high": 100.9, "low": 99.8, "close": 100.6, "volume": 1000},
        {"open": 100.6, "high": 101.4, "low": 100.4, "close": 101.1, "volume": 1200},
        {"open": 101.1, "high": 101.8, "low": 100.9, "close": 101.5, "volume": 1100},
        {"open": 101.5, "high": 102.1, "low": 101.2, "close": 101.9, "volume": 1300},
    ]
    result = _evaluate_bull_trend_profile(bars, **_default_eval_kwargs())
    assert result["passed"] is True
    assert result["reason"] == "confirmed"


def test_evaluate_bull_trend_profile_rejects_single_bar_volume_spike():
    bars = [
        {"open": 100.0, "high": 100.8, "low": 99.9, "close": 100.6, "volume": 9000},
        {"open": 100.6, "high": 101.2, "low": 100.4, "close": 101.0, "volume": 400},
        {"open": 101.0, "high": 101.6, "low": 100.8, "close": 101.3, "volume": 350},
        {"open": 101.3, "high": 101.9, "low": 101.0, "close": 101.6, "volume": 300},
    ]
    result = _evaluate_bull_trend_profile(bars, **_default_eval_kwargs())
    assert result["passed"] is False
    assert result["reason"] == "single_bar_volume_spike"


def test_evaluate_bull_trend_profile_rejects_deep_pullback():
    bars = [
        {"open": 100.0, "high": 102.0, "low": 99.9, "close": 101.5, "volume": 1000},
        {"open": 101.5, "high": 103.0, "low": 101.2, "close": 102.6, "volume": 1200},
        {"open": 102.6, "high": 104.0, "low": 102.0, "close": 103.5, "volume": 1100},
        {"open": 103.5, "high": 104.5, "low": 101.0, "close": 102.1, "volume": 1300},
    ]
    result = _evaluate_bull_trend_profile(bars, **_default_eval_kwargs())
    assert result["passed"] is False
    assert result["reason"] == "deep_pullback"


def test_in_trend_confirmation_window():
    assert (
        _in_trend_confirmation_window(
            datetime(2026, 3, 2, 9, 3, 0, tzinfo=KST),
            7,
        )
        is False
    )
    assert (
        _in_trend_confirmation_window(
            datetime(2026, 3, 2, 9, 8, 0, tzinfo=KST),
            7,
        )
        is True
    )
    assert (
        _in_trend_confirmation_window(
            datetime(2026, 3, 2, 15, 25, 0, tzinfo=KST),
            7,
        )
        is False
    )


def test_normalize_scores_for_codes():
    scores = {"A": 0.3, "B": 0.6, "C": 0.15}
    normalized = _normalize_scores_for_codes(scores, ["A", "B"])
    assert normalized["B"] == 1.0
    assert normalized["A"] == 0.5


def test_screener_config_defaults_rate_limit_friendly():
    cfg = ScreenerConfig()

    assert cfg.interval_seconds == 5.0
    assert cfg.publish_heartbeat_seconds == 60.0


def test_code_set_signature_ignores_order_churn():
    assert _code_set_signature(["005930", "000660"]) == _code_set_signature(
        ["000660", "005930"]
    )


def test_should_publish_snapshot_on_change_or_heartbeat():
    assert _should_publish_snapshot(
        signature="A",
        last_signature=None,
        now=10.0,
        last_publish_time=0.0,
        heartbeat_seconds=60.0,
    )
    assert (
        _should_publish_snapshot(
            signature="A",
            last_signature="A",
            now=59.0,
            last_publish_time=0.0,
            heartbeat_seconds=60.0,
        )
        is False
    )
    assert _should_publish_snapshot(
        signature="A",
        last_signature="A",
        now=60.0,
        last_publish_time=0.0,
        heartbeat_seconds=60.0,
    )


class _DummyKISClient:
    def __init__(self, bars_by_code: dict[str, list[dict[str, float]]]):
        self.bars_by_code = bars_by_code
        self.is_rate_limited = False

    async def get_minute_bars(self, code: str, count: int = 30):
        return self.bars_by_code.get(code, [])[:count]


class _RateLimitedKISClient:
    is_rate_limited = True

    def __init__(self):
        self.calls = 0

    async def get_minute_bars(self, _code: str, _count: int = 30):
        self.calls += 1
        return []


@pytest.mark.asyncio
async def test_apply_trend_confirmation_filters_unconfirmed_codes():
    bars_pass = [
        {"open": 100.0, "high": 100.8, "low": 99.8, "close": 100.5, "volume": 1000},
        {"open": 100.5, "high": 101.2, "low": 100.3, "close": 101.0, "volume": 1000},
        {"open": 101.0, "high": 101.8, "low": 100.9, "close": 101.6, "volume": 1000},
    ]
    bars_fail = [
        {"open": 100.0, "high": 100.3, "low": 99.5, "close": 99.9, "volume": 1000},
        {"open": 99.9, "high": 100.0, "low": 99.3, "close": 99.5, "volume": 1000},
        {"open": 99.5, "high": 99.7, "low": 99.0, "close": 99.2, "volume": 1000},
    ]
    client = _DummyKISClient({"000001": bars_pass, "000002": bars_fail})
    config = ScreenerConfig().model_copy(
        update={
            "trend_confirm_enabled": True,
            "trend_confirm_max_scan_codes": 2,
            "trend_confirm_bar_count": 3,
            "trend_confirm_fail_open": False,
        }
    )
    filtered, diagnostics = await _apply_trend_confirmation(
        codes=["000001", "000002"],
        info_by_code={},
        config=config,
        kis_client=client,  # type: ignore[arg-type]
        cache={},
    )
    assert filtered == ["000001"]
    assert diagnostics["000001"]["passed"] is True
    assert diagnostics["000002"]["passed"] is False


@pytest.mark.asyncio
async def test_apply_trend_confirmation_keeps_unscanned_codes():
    bars_pass = [
        {"open": 100.0, "high": 100.8, "low": 99.8, "close": 100.5, "volume": 1000},
        {"open": 100.5, "high": 101.2, "low": 100.3, "close": 101.0, "volume": 1000},
        {"open": 101.0, "high": 101.8, "low": 100.9, "close": 101.6, "volume": 1000},
    ]
    bars_fail = [
        {"open": 100.0, "high": 100.3, "low": 99.5, "close": 99.9, "volume": 1000},
        {"open": 99.9, "high": 100.0, "low": 99.3, "close": 99.5, "volume": 1000},
        {"open": 99.5, "high": 99.7, "low": 99.0, "close": 99.2, "volume": 1000},
    ]
    client = _DummyKISClient({"000001": bars_pass, "000002": bars_fail})
    config = ScreenerConfig().model_copy(
        update={
            "trend_confirm_enabled": True,
            "trend_confirm_max_scan_codes": 2,
            "trend_confirm_bar_count": 3,
            "trend_confirm_fail_open": False,
        }
    )
    filtered, diagnostics = await _apply_trend_confirmation(
        codes=["000001", "000002", "000003"],
        info_by_code={},
        config=config,
        kis_client=client,  # type: ignore[arg-type]
        cache={},
    )
    assert filtered == ["000001", "000003"]
    assert diagnostics["000001"]["passed"] is True
    assert diagnostics["000002"]["passed"] is False
    assert "000003" not in diagnostics


@pytest.mark.asyncio
async def test_apply_trend_confirmation_stops_when_kis_is_rate_limited():
    client = _RateLimitedKISClient()
    config = ScreenerConfig().model_copy(
        update={
            "trend_confirm_enabled": True,
            "trend_confirm_max_scan_codes": 2,
            "trend_confirm_fail_open": True,
        }
    )

    filtered, diagnostics = await _apply_trend_confirmation(
        codes=["000001", "000002", "000003"],
        info_by_code={},
        config=config,
        kis_client=client,  # type: ignore[arg-type]
        cache={},
    )

    assert client.calls == 0
    assert filtered == ["000001", "000002", "000003"]
    assert diagnostics["000001"]["reason"] == "kis_rate_limited"
