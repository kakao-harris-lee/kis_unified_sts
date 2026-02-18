"""Edge case tests for OpeningVolumeSurgeEntry.

Covers the change_pct=0 fix: previously `data.get("change_pct") or data.get("change_percent")`
treated 0 as falsy and fell through to the change_percent/change fallback.
The fix uses an explicit `is None` check so that 0 is honoured as a real value.
"""
import pytest
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def _make_strategy(*, min_change_pct: float = 1.0, **kwargs):
    from shared.strategy.entry.opening_volume_surge import (
        OpeningVolumeSurgeEntry,
        OpeningVolumeSurgeConfig,
    )

    config = OpeningVolumeSurgeConfig(
        only_first_minutes=30,
        market_open_hour=9,
        market_open_minute=0,
        volume_multiplier=1.0,
        min_change_pct=min_change_pct,
        require_above_open=False,  # keep other filters permissive
        min_range_position=0.0,
        min_day_range_pct=0.0,
        **kwargs,
    )
    return OpeningVolumeSurgeEntry(config)


def _make_context(market_data: dict, *, minutes_after_open: float = 5.0):
    from shared.strategy.base import EntryContext

    ts = datetime(2026, 2, 18, 9, 0, 0, tzinfo=KST)
    import datetime as dt_module

    ts = ts + dt_module.timedelta(minutes=minutes_after_open)
    return EntryContext(market_data=market_data, timestamp=ts)


# ---------------------------------------------------------------------------
# Minimal market data that would pass all filters *except* the change_pct gate.
# Volume >= prev_day_volume * 1.0 to pass the volume trigger.
# Prices form a valid range with close in the upper portion.
# ---------------------------------------------------------------------------
_BASE_DATA = {
    "code": "005930",
    "name": "Samsung",
    "volume": 1_000_000,
    "prev_day_volume": 500_000,  # vol_ratio = 2.0 → passes volume trigger
    "close": 100.0,
    "open": 98.0,
    "high": 102.0,
    "low": 96.0,
    # change_pct intentionally omitted here; set per test
}


@pytest.mark.asyncio
async def test_ovs_change_pct_zero_not_treated_as_none():
    """change_pct=0 must be read as 0, not fall through to the change fallback.

    With the old `or` pattern, change_pct=0 would be falsy and the code would
    fall through to check change_percent, then compute from change.  With the
    explicit `is None` fix, 0 is kept as-is.

    Verification: min_change_pct defaults to 1.0, so a change_pct=0 should
    fail the `change_pct < min_change_pct` guard → generate() returns None.
    We also confirm via the metadata path that 0 was not replaced by a larger
    value derived from `change` (which would have caused a spurious signal if
    change happened to be non-zero and unit conversion pushed it above 1.0).
    """
    strategy = _make_strategy(min_change_pct=1.0, change_input_unit="percent")

    data = {
        **_BASE_DATA,
        "change_pct": 0,       # the bug: 0 was treated as falsy
        "change_percent": 5.0,  # fallback — must NOT be used
        "change": 5.0,          # raw fallback — must NOT be used
    }
    context = _make_context(data)
    signal = await strategy.generate(context)

    # 0 < min_change_pct (1.0) → no signal.
    # If the old bug were present, change_percent=5.0 would be picked up and a
    # signal would be emitted (5.0 >= 1.0).
    assert signal is None, (
        "Expected None because change_pct=0 is below min_change_pct=1.0. "
        "If a signal was returned, the old `or`-based fallback is still active."
    )


@pytest.mark.asyncio
async def test_ovs_change_pct_zero_used_not_change_percent():
    """Confirm change_pct=0 shadows change_percent even when change_percent > threshold.

    Mirror of the above: we lower min_change_pct to -1.0 so that 0 would pass
    the gate.  Then we verify a signal IS produced — meaning the code accepted
    change_pct=0 as-is and did not use the larger change_percent value (which
    would also pass, but the key invariant is that 0 was kept, not substituted).
    """
    # min_change_pct = -1.0 so that change_pct=0 passes (0 >= -1.0)
    strategy = _make_strategy(min_change_pct=-1.0, change_input_unit="percent")

    data = {
        **_BASE_DATA,
        "change_pct": 0,
        "change_percent": 99.0,  # must NOT influence the path
        "change": 99.0,
    }
    context = _make_context(data)
    signal = await strategy.generate(context)

    # change_pct=0 passes the gate (-1.0), so we expect a signal.
    assert signal is not None, (
        "Expected a signal when change_pct=0 and min_change_pct=-1.0. "
        "The code should accept 0 explicitly rather than falling to a fallback."
    )
    # The metadata must carry exactly 0.0 as change_pct, not 99.0.
    assert signal.metadata["change_pct"] == pytest.approx(0.0), (
        f"change_pct in metadata should be 0.0, got {signal.metadata['change_pct']}. "
        "The fallback value (99.0) must not have been used."
    )


@pytest.mark.asyncio
async def test_ovs_change_pct_none_falls_through_to_change_percent():
    """When change_pct is absent (None), change_percent should be the fallback."""
    strategy = _make_strategy(min_change_pct=1.0, change_input_unit="percent")

    data = {
        **_BASE_DATA,
        # change_pct intentionally absent → None from .get()
        "change_percent": 3.0,  # fallback should be used
    }
    context = _make_context(data)
    signal = await strategy.generate(context)

    # change_percent=3.0 >= min_change_pct=1.0 → signal expected
    assert signal is not None, (
        "When change_pct is absent, change_percent should be used as fallback."
    )
    assert signal.metadata["change_pct"] == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_ovs_both_absent_uses_change_field():
    """When both change_pct and change_percent are absent, fall back to change field."""
    strategy = _make_strategy(
        min_change_pct=1.0,
        change_input_unit="percent",  # change field is treated as percent directly
    )

    data = {
        **_BASE_DATA,
        # neither change_pct nor change_percent present
        "change": 2.5,  # used as percent directly (change_input_unit="percent")
    }
    context = _make_context(data)
    signal = await strategy.generate(context)

    # change=2.5 as percent >= 1.0 → signal expected
    assert signal is not None, (
        "When both change_pct and change_percent are absent, 'change' should be used."
    )
    assert signal.metadata["change_pct"] == pytest.approx(2.5)
