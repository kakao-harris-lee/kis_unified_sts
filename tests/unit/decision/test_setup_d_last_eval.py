"""Tests for Setup D's two read-only observability surfaces."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from shared.decision.context import MarketContext
from shared.decision.setups.vwap_reversion import SetupDConfig, SetupDVWAPReversion

KST = ZoneInfo("Asia/Seoul")


def _ctx(
    *,
    now_hhmm: tuple[int, int] = (11, 0),
    current_price: float,
    vwap: float,
    atr_14: float = 2.0,
) -> MarketContext:
    return MarketContext(
        now=datetime(2026, 3, 10, now_hhmm[0], now_hhmm[1], tzinfo=KST),
        symbol="101S6000",
        current_price=current_price,
        prev_close=vwap,
        today_open=vwap,
        vwap=vwap,
        atr_14=atr_14,
        atr_90th_percentile=atr_14,
        last_15min_high=current_price,
        last_15min_low=current_price,
        current_spread_ticks=1.0,
        macro_overnight=None,
        scheduled_events=[],
        market_open_hour=8,
        market_open_minute=45,
    )


def test_vwap_extension_z_is_the_signed_atr_scaled_distance() -> None:
    assert SetupDVWAPReversion.vwap_extension_z(404.0, 400.0, 2.0) == pytest.approx(2.0)
    assert SetupDVWAPReversion.vwap_extension_z(396.0, 400.0, 2.0) == pytest.approx(
        -2.0
    )
    up = SetupDVWAPReversion.vwap_extension_z(403.6, 400.0, 2.0)
    down = SetupDVWAPReversion.vwap_extension_z(396.4, 400.0, 2.0)
    assert up == pytest.approx(-down)


def test_vwap_extension_z_refuses_a_zero_atr_instead_of_fabricating() -> None:
    """At atr == 0 the extension is undefined; a fabricated extreme is worse."""
    with pytest.raises(ZeroDivisionError):
        SetupDVWAPReversion.vwap_extension_z(404.0, 400.0, 0.0)


def test_check_uses_the_accessor_for_both_z_and_prev_z() -> None:
    """``prev_z`` goes through the same definition, so "the ONE definition" holds."""
    config = SetupDConfig(
        min_atr_ratio=0.0,
        reversal_confirm_enabled=True,
        reversal_confirm_requires_price_turn=True,
        reversal_confirm_atr_mult=0.0,
        min_confidence=0.0,
        range_warmup_bars=1,
    )
    setup = SetupDVWAPReversion(config=config)
    setup.check(_ctx(current_price=410.0, vwap=400.0))
    signal = setup.check(_ctx(current_price=404.0, vwap=400.0))

    assert signal is not None
    evaluated = setup.last_eval
    prev_close = evaluated["prev_close"]
    assert prev_close == pytest.approx(410.0)
    assert evaluated["z"] == pytest.approx(
        SetupDVWAPReversion.vwap_extension_z(404.0, 400.0, 2.0)
    )
    assert evaluated["prev_z"] == pytest.approx(
        SetupDVWAPReversion.vwap_extension_z(float(prev_close), 400.0, 2.0)
    )
    assert evaluated["reversal_z_improvement"] == pytest.approx(
        abs(float(evaluated["prev_z"])) - abs(float(evaluated["z"]))
    )


GATE_KEYS = ("hi_vol", "stall_ok", "reversal_ok")


def test_last_eval_after_an_after_cutoff_bar_has_no_gate_keys() -> None:
    """Past the cutoff ``check`` returns at step 1, so no gate has a value."""
    setup = SetupDVWAPReversion(config=SetupDConfig())
    signal = setup.check(_ctx(now_hhmm=(15, 0), current_price=404.0, vwap=400.0))

    assert signal is None
    assert setup.last_reject_reason is not None
    assert setup.last_reject_reason.startswith("after_cutoff")
    assert setup.last_eval["entry_window"] is False
    for key in GATE_KEYS:
        assert key not in setup.last_eval, key
    assert "inputs_usable" not in setup.last_eval


def test_last_eval_after_a_before_window_bar_has_no_gate_keys() -> None:
    setup = SetupDVWAPReversion(config=SetupDConfig())
    setup.check(_ctx(now_hhmm=(8, 50), current_price=404.0, vwap=400.0))
    assert setup.last_reject_reason is not None
    assert setup.last_reject_reason.startswith("before_window")
    assert setup.last_eval["entry_window"] is False
    for key in GATE_KEYS:
        assert key not in setup.last_eval, key


def test_last_eval_after_a_fired_bar_has_every_gate_key() -> None:
    config = SetupDConfig(
        min_atr_ratio=0.0,
        reversal_confirm_enabled=False,
        min_confidence=0.0,
    )
    setup = SetupDVWAPReversion(config=config)
    signal = setup.check(_ctx(current_price=404.0, vwap=400.0))

    assert signal is not None
    assert setup.last_reject_reason is None
    evaluated = setup.last_eval
    assert evaluated["entry_window"] is True
    assert evaluated["inputs_usable"] is True
    for key in GATE_KEYS:
        assert evaluated[key] is True, key
    assert evaluated["extreme"] is True
    assert evaluated["direction"] == "short"
    assert evaluated["confidence_ok"] is True
    assert evaluated["fired"] is True


def test_last_eval_records_an_in_window_reject_without_clearing_entry_window() -> None:
    """A vol-gate reject keeps ``entry_window`` true — the D5 premise."""
    config = SetupDConfig(min_atr_ratio=0.9, vol_warmup_bars=2, vol_window_bars=10)
    setup = SetupDVWAPReversion(config=config)
    setup.check(_ctx(current_price=400.0, vwap=400.0, atr_14=5.0))
    setup.check(_ctx(current_price=400.0, vwap=400.0, atr_14=5.0))
    signal = setup.check(_ctx(current_price=404.0, vwap=400.0, atr_14=0.5))

    assert signal is None
    assert setup.last_reject_reason is not None
    assert setup.last_reject_reason.startswith("vol_below_gate")
    evaluated = setup.last_eval
    assert evaluated["entry_window"] is True
    assert evaluated["hi_vol"] is False
    for key in ("stall_ok", "reversal_ok"):
        assert key not in evaluated, key


def test_last_eval_is_replaced_per_call_not_accumulated() -> None:
    """Each call starts a fresh trace, so a stale key cannot survive a bar."""
    config = SetupDConfig(
        min_atr_ratio=0.0, reversal_confirm_enabled=False, min_confidence=0.0
    )
    setup = SetupDVWAPReversion(config=config)
    setup.check(_ctx(current_price=404.0, vwap=400.0))
    assert "fired" in setup.last_eval

    setup.check(_ctx(now_hhmm=(15, 0), current_price=404.0, vwap=400.0))
    assert "fired" not in setup.last_eval
    assert setup.last_eval["entry_window"] is False
