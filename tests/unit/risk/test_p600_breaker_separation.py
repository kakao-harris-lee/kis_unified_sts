"""#600 regression pin — loss-breaker tier separation survives P4-d dedup.

P4-d extracted the *predicate math* shared by the kill-switch conditions and
the risk filters into ``shared.risk.primitives.breakers`` (behavior-0). This
test pins the properties #600 depends on, so a *future* refactor that tries to
merge decisions (not just math) is caught:

1. **Consecutive tiers are three distinct levels.** The filter's soft
   (size-reduce) and hard (block) thresholds are *below* the catastrophic
   kill threshold. #600's lesson — the loss-streak breaker is catastrophic-only
   because it structurally conflicts with mean reversion — requires that a
   streak which trips the soft/hard *filter* does NOT trip the *catastrophic
   kill*. Merging soft into the catastrophic path would regress this.

2. **Loss boundary operators stay split.** The catastrophic kill fires *at*
   the limit (inclusive ``>=``); the soft MDD filter fires only *beyond* it
   (strict ``<``). At exactly the limit the catastrophic condition trips while
   the soft filter passes.

These are *independent literal* expectations (thresholds/booleans restated
here), not values read back from the primitive — so the pin is not tautological.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.kill_switch.main import (
    ConsecutiveLossesCondition,
    DailyLossCondition,
    MonthlyLossCondition,
    WeeklyLossCondition,
)
from shared.decision.signal import Signal
from shared.risk.filters.consecutive_loss import ConsecutiveLossFilter
from shared.risk.filters.daily_mdd import DailyMDDFilter
from shared.risk.filters.weekly_mdd import WeeklyMDDFilter
from shared.risk.state import RiskStateSnapshot

EQUITY = 100_000_000.0

# Tier thresholds (config/risk.yaml + a #600 catastrophic-only kill level).
SOFT = 4  # filter: halve size
HARD = 6  # filter: block entry
CATASTROPHIC = 10  # kill: force-flatten (#600 catastrophic-only, > HARD)


def _signal() -> Signal:
    return Signal(
        setup_type="test",
        direction="long",
        symbol="A05603",
        entry_price=360.0,
        stop_loss=355.0,
        take_profit=370.0,
        confidence=0.8,
    )


class TestConsecutiveTierSeparation:
    """soft < hard < catastrophic must remain three distinct levels."""

    @pytest.mark.parametrize("streak", range(0, 13))
    def test_grid_0_to_12(self, streak: int) -> None:
        filt = ConsecutiveLossFilter(soft_threshold=SOFT, hard_threshold=HARD)
        kill = ConsecutiveLossesCondition(threshold=CATASTROPHIC)

        filt_result = filt.check(
            _signal(), RiskStateSnapshot(consecutive_losses=streak)
        )
        kill_trips = kill.check(snapshot=SimpleNamespace(consecutive_losses=streak))

        # Filter tier — independent expectations restated from the thresholds.
        if streak < SOFT:
            assert filt_result.passed is True
            assert filt_result.size_multiplier == 1.0
        elif streak < HARD:
            assert filt_result.passed is True
            assert filt_result.size_multiplier == 0.5  # soft: size-reduce, not block
        else:
            assert filt_result.passed is False  # hard: block

        # Kill tier — catastrophic-only, fires only at/above CATASTROPHIC.
        assert kill_trips is (streak >= CATASTROPHIC)

        # THE #600 pin: a streak that blocks the soft/hard filter must NOT
        # trip the catastrophic kill until it reaches the (higher) kill level.
        if HARD <= streak < CATASTROPHIC:
            assert filt_result.passed is False and kill_trips is False

    def test_catastrophic_strictly_above_hard(self) -> None:
        """The tiers are ordered; merging them would break #600."""
        assert SOFT < HARD < CATASTROPHIC


class TestLossBoundaryOperatorSeparation:
    """Catastrophic kill = inclusive (>=); soft MDD filter = strict (<)."""

    @pytest.mark.parametrize(
        ("kill_cls", "limit", "pnl_attr"),
        [
            (DailyLossCondition, 0.03, "daily_pnl_krw"),
            (WeeklyLossCondition, 0.07, "weekly_pnl_krw"),
            (MonthlyLossCondition, 0.15, "monthly_pnl_krw"),
        ],
    )
    def test_kill_inclusive_trips_at_exact_limit(
        self, kill_cls: type, limit: float, pnl_attr: str
    ) -> None:
        cond = kill_cls(limit_pct=limit, equity_krw=EQUITY)
        boundary_loss = -EQUITY * limit  # exactly at the limit
        assert cond.check(snapshot=SimpleNamespace(**{pnl_attr: boundary_loss})) is True
        # One KRW inside the limit → no trip.
        assert (
            cond.check(snapshot=SimpleNamespace(**{pnl_attr: boundary_loss + 1.0}))
            is False
        )

    @pytest.mark.parametrize(
        ("filter_cls", "limit_kw", "pnl_attr"),
        [
            (DailyMDDFilter, "daily_mdd_limit_pct", "daily_pnl_krw"),
            (WeeklyMDDFilter, "weekly_mdd_limit_pct", "weekly_pnl_krw"),
        ],
    )
    def test_soft_filter_strict_passes_at_exact_limit(
        self, filter_cls: type, limit_kw: str, pnl_attr: str
    ) -> None:
        limit = 0.03
        filt = filter_cls(account_equity_krw=EQUITY, **{limit_kw: limit})
        boundary_loss = -EQUITY * limit  # exactly at the limit
        snap = RiskStateSnapshot(**{pnl_attr: boundary_loss})
        # Strict: equality passes.
        assert filt.check(_signal(), snap).passed is True
        # One KRW beyond → reject.
        beyond = RiskStateSnapshot(**{pnl_attr: boundary_loss - 1.0})
        assert filt.check(_signal(), beyond).passed is False

    def test_catastrophic_trips_where_soft_filter_still_passes(self) -> None:
        """At the exact daily limit: kill flattens, soft filter still admits."""
        limit = 0.03
        boundary_loss = -EQUITY * limit
        kill = DailyLossCondition(limit_pct=limit, equity_krw=EQUITY)
        soft = DailyMDDFilter(account_equity_krw=EQUITY, daily_mdd_limit_pct=limit)

        assert kill.check(snapshot=SimpleNamespace(daily_pnl_krw=boundary_loss)) is True
        assert (
            soft.check(_signal(), RiskStateSnapshot(daily_pnl_krw=boundary_loss)).passed
            is True
        )
