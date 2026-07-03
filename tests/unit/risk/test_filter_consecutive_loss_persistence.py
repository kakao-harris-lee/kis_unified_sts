"""Phase 3C C2 — ConsecutiveLossFilter soft-reduce persistence + floor policy.

Complements test_filter_consecutive_loss.py (whose legacy behaviour must
stay green). Thresholds: soft=4, hard=6. Time comes from
``signal.generated_at`` so no wall clock is involved.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from shared.decision.signal import Signal
from shared.risk.filters.consecutive_loss import ConsecutiveLossFilter
from shared.risk.state import RiskStateSnapshot

KST = ZoneInfo("Asia/Seoul")

T0 = datetime(2026, 7, 3, 10, 0, tzinfo=KST)
UNTIL = T0 + timedelta(days=14)

_SOFT = 4
_HARD = 6


def _signal(generated_at: datetime | None = T0) -> Signal:
    return Signal(
        setup_type="test_setup",
        direction="long",
        symbol="A05603",
        entry_price=360.0,
        stop_loss=355.0,
        take_profit=370.0,
        confidence=0.8,
        generated_at=generated_at,
    )


def _snapshot(losses: int = 0, until: str = "") -> RiskStateSnapshot:
    return RiskStateSnapshot(consecutive_losses=losses, size_reduce_until_kst=until)


def _filter(*, floor: bool = False) -> ConsecutiveLossFilter:
    return ConsecutiveLossFilter(
        soft_threshold=_SOFT, hard_threshold=_HARD, reduce_blocks_at_floor=floor
    )


# ---------------------------------------------------------------------------
# Persistence window — x0.5 survives wins for the full window
# ---------------------------------------------------------------------------


def test_open_window_reduces_even_after_streak_reset():
    """Wins reset the streak to 0 but the window keeps the reduction."""
    f = _filter()
    result = f.check(_signal(T0 + timedelta(days=5)), _snapshot(0, UNTIL.isoformat()))
    assert result.passed is True
    assert result.size_multiplier == 0.5


def test_window_active_on_day_13():
    f = _filter()
    result = f.check(
        _signal(T0 + timedelta(days=13, hours=23)), _snapshot(1, UNTIL.isoformat())
    )
    assert result.size_multiplier == 0.5


def test_window_expires_on_day_14_boundary():
    """Day 15 (>= until) reverts to full size — the window is half-open."""
    f = _filter()
    result = f.check(_signal(UNTIL), _snapshot(0, UNTIL.isoformat()))
    assert result.passed is True
    assert result.size_multiplier == 1.0


def test_window_expired_reverts_to_full_size():
    f = _filter()
    result = f.check(
        _signal(UNTIL + timedelta(days=1)), _snapshot(0, UNTIL.isoformat())
    )
    assert result.passed is True
    assert result.size_multiplier == 1.0


def test_naive_until_string_treated_as_kst():
    f = _filter()
    naive_until = (T0 + timedelta(days=14)).replace(tzinfo=None).isoformat()
    result = f.check(_signal(T0 + timedelta(days=5)), _snapshot(0, naive_until))
    assert result.size_multiplier == 0.5


def test_unparseable_until_is_ignored():
    f = _filter()
    result = f.check(_signal(), _snapshot(0, "not-a-timestamp"))
    assert result.passed is True
    assert result.size_multiplier == 1.0


def test_empty_until_keeps_legacy_behaviour():
    f = _filter()
    assert f.check(_signal(), _snapshot(3, "")).size_multiplier == 1.0
    assert f.check(_signal(), _snapshot(4, "")).size_multiplier == 0.5


def test_missing_generated_at_uses_wall_clock():
    """A far-future window must reduce even without a signal timestamp."""
    f = _filter()
    far_future = datetime(2999, 1, 1, tzinfo=KST).isoformat()
    result = f.check(_signal(generated_at=None), _snapshot(0, far_future))
    assert result.size_multiplier == 0.5


# ---------------------------------------------------------------------------
# Hard threshold precedence — unchanged by the window / floor policy
# ---------------------------------------------------------------------------


def test_hard_threshold_precedes_window_and_floor_policy():
    f = _filter(floor=True)
    result = f.check(_signal(), _snapshot(_HARD, UNTIL.isoformat()))
    assert result.passed is False
    assert result.skip_reason == "consecutive_losses_cooldown"


# ---------------------------------------------------------------------------
# Floor-at-1 policy — reduce_blocks_at_floor
# ---------------------------------------------------------------------------


def test_default_flag_is_false():
    f = ConsecutiveLossFilter(soft_threshold=_SOFT, hard_threshold=_HARD)
    assert f.reduce_blocks_at_floor is False


def test_floor_block_rejects_on_active_streak():
    f = _filter(floor=True)
    result = f.check(_signal(), _snapshot(_SOFT))
    assert result.passed is False
    assert result.skip_reason == "consecutive_losses_floor_block"


def test_floor_block_rejects_during_persisted_window():
    f = _filter(floor=True)
    result = f.check(_signal(T0 + timedelta(days=5)), _snapshot(0, UNTIL.isoformat()))
    assert result.passed is False
    assert result.skip_reason == "consecutive_losses_floor_block"


def test_floor_block_passes_when_no_reduction_active():
    f = _filter(floor=True)
    result = f.check(_signal(), _snapshot(0))
    assert result.passed is True
    assert result.size_multiplier == 1.0


def test_floor_false_keeps_reducing_instead_of_blocking():
    f = _filter(floor=False)
    result = f.check(_signal(), _snapshot(_SOFT))
    assert result.passed is True
    assert result.size_multiplier == 0.5
