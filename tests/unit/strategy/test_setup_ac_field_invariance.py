"""F-4 invariant: Setup A/C ignore vwap / atr_90th_percentile / current_spread_ticks.

The F-4 unification assembles ``MarketContext`` via a single
:func:`shared.decision.context.build_market_context` with one default policy for
the three fields that Setup A and Setup C provably never read
(``vwap``, ``atr_90th_percentile``, ``current_spread_ticks``).

This test LOCKS that premise: for both setups, two contexts that are identical on
every core/firing field but differ wildly on those three fields (0.0 vs 9999.0)
must produce equivalent signals. Each parametrized case is tuned so the setup
actually FIRES a real signal (not a weak ``None == None`` invariance), so any
future code that reads one of these fields inside A/C breaks loudly here.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from shared.decision.context import ScheduledEvent, build_market_context
from shared.decision.setups.event_reaction import SetupCEventReaction
from shared.decision.setups.gap_reversion import SetupAGapReversion
from shared.macro.base import MacroSnapshot

_KST = ZoneInfo("Asia/Seoul")

# The three fields F-4 claims Setup A/C never read. Two wildly different value
# sets — if any setup reads one of them, the resulting signal will differ.
_UNUSED_LO = {"vwap": 0.0, "atr_90th_percentile": 0.0, "current_spread_ticks": 0.0}
_UNUSED_HI = {
    "vwap": 9999.0,
    "atr_90th_percentile": 9999.0,
    "current_spread_ticks": 9999.0,
}


def _sig_tuple(sig: object) -> tuple | None:
    """Reduce a Signal to its trade-defining fields (or None)."""
    if sig is None:
        return None
    return (sig.direction, sig.entry_price, sig.stop_loss, sig.take_profit)


# ---------------------------------------------------------------------------
# Setup A — gap-reversion firing fixture (mirrors test_setup_a_gap_reversion happy path)
# ---------------------------------------------------------------------------


def _setup_a_core() -> dict:
    """Core (firing) MarketContext fields for a Setup A gap-down → short signal.

    prev_close=350, today_open=347 → gap_pct ≈ -0.857 % (gap-down, >= 0.2 %).
    SP500 -1.2 % (same direction, >= 0.3 %). current_price=348.5 →
    retrace = (348.5 - 347) / (350 - 347) = 0.50 ∈ [0.20, 0.70]. now=09:30 KST →
    30 min after open, within [10, 120]. Identical to the happy-path unit test.
    """
    return {
        "now": datetime(2026, 4, 23, 9, 30, tzinfo=_KST),
        "symbol": "A05603",
        "current_price": 348.5,
        "prev_close": 350.0,
        "today_open": 347.0,
        "atr_14": 1.0,
        "last_15min_high": 347.0,
        "last_15min_low": 345.5,
        "macro_overnight": MacroSnapshot(
            ts_ms=1_700_000_000_000,
            session="overnight_us_close",
            sp500_change_pct=-1.2,
        ),
    }


# ---------------------------------------------------------------------------
# Setup C — event-reaction firing fixture (mirrors test_setup_c long happy path)
# ---------------------------------------------------------------------------


def _setup_c_core() -> dict:
    """Core (firing) MarketContext fields for a Setup C long breakout signal.

    A tier-1 ScheduledEvent occurred 5 min before now (within window_minutes=15).
    current_price=350.30 > last_15min_high=350.00 and within buffer
    (0.5 ATR = 0.5). now=14:00 KST. Identical to the long happy-path unit test.
    """
    now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=_KST)
    event = ScheduledEvent(
        event_id="fomc_2026_may",
        event_type="FOMC_rate_decision",
        scheduled_at=now - timedelta(minutes=5.0),
        impact_tier=1,
    )
    return {
        "now": now,
        "symbol": "A05603",
        "current_price": 350.30,
        "prev_close": 349.0,
        "today_open": 349.5,
        "atr_14": 1.0,
        "last_15min_high": 350.0,
        "last_15min_low": 348.0,
        "scheduled_events": [event],
    }


# ---------------------------------------------------------------------------
# Parametrized invariance: each case must FIRE a real signal AND be invariant.
# A fresh setup instance per .check() call so Setup C's in-memory dedup tracker
# does not suppress the second invocation for the same event_id.
# ---------------------------------------------------------------------------

_CASES = [
    pytest.param(SetupAGapReversion, _setup_a_core, id="setup_a_gap_reversion"),
    pytest.param(SetupCEventReaction, _setup_c_core, id="setup_c_event_reaction"),
]


@pytest.mark.parametrize(("setup_cls", "core_factory"), _CASES)
def test_signal_invariant_to_unused_fields(setup_cls, core_factory) -> None:
    """Setup A/C signals are identical regardless of vwap/atr_90th/spread."""
    core = core_factory()

    ctx_lo = build_market_context(**core, **_UNUSED_LO)
    ctx_hi = build_market_context(**core, **_UNUSED_HI)

    # Fresh instances: a single setup instance must NOT carry state across the
    # two .check() calls (Setup C dedups by event_id after the first signal).
    sig_lo = _sig_tuple(setup_cls().check(ctx_lo))
    sig_hi = _sig_tuple(setup_cls().check(ctx_hi))

    # 1. Invariance: the three unused fields do not change the signal.
    assert sig_lo == sig_hi

    # 2. Strength: the fixture actually FIRES a real signal (not None == None),
    #    so invariance is proven on a genuine entry, not a trivial no-trade.
    assert sig_lo is not None, f"{setup_cls.__name__} fixture did not fire a signal"
