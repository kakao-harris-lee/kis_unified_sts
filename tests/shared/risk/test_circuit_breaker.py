"""Tests for the futures risk circuit breakers (RC5).

Two futures-native breakers halt new entries when a losing streak develops,
independent of the KRW %-of-capital daily-loss model (which is mis-scaled for a
single futures contract whose notional is ~30x the risk capital):

  * consecutive-loss halt — stop entries after N consecutive losing closes
    (unit-free; directly targets the 2026-07-07 churn: 11 near-consecutive
    losing longs into a -4.9% downtrend).
  * daily-loss-in-points cap — stop entries when cumulative realized PnL for the
    session drops to -X (in the position's native PnL unit = index points for
    futures), avoiding the points-vs-KRW mismatch.

Both are config-driven and DISABLED by default (0), so existing behavior is
unchanged unless explicitly enabled. Both reset on the daily reset.
"""

from __future__ import annotations

import pytest

from shared.risk.config import RiskConfig
from shared.risk.manager import RiskManager
from shared.risk.models import BlockReason


def _mgr(**overrides: object) -> RiskManager:
    cfg = RiskConfig(
        daily_loss_limit_pct=5.0,
        max_total_positions=20,
        initial_capital=10_000_000,
        **overrides,
    )
    return RiskManager(cfg)


# ---------------------------------------------------------------------------
# Consecutive-loss breaker
# ---------------------------------------------------------------------------


def test_consecutive_losses_block_after_threshold():
    mgr = _mgr(max_consecutive_losses=3)
    for _ in range(3):
        mgr.record_realized_pnl(-5.0)  # points
    assert mgr.can_open_position("futures") is False
    assert mgr.state.block_reason == BlockReason.CONSECUTIVE_LOSSES


def test_two_consecutive_losses_do_not_block():
    mgr = _mgr(max_consecutive_losses=3)
    mgr.record_realized_pnl(-5.0)
    mgr.record_realized_pnl(-5.0)
    assert mgr.can_open_position("futures") is True


def test_win_resets_consecutive_losses():
    mgr = _mgr(max_consecutive_losses=3)
    mgr.record_realized_pnl(-5.0)
    mgr.record_realized_pnl(-5.0)
    mgr.record_realized_pnl(+20.0)  # win resets the streak
    mgr.record_realized_pnl(-5.0)
    mgr.record_realized_pnl(-5.0)
    assert mgr.state.consecutive_losses == 2
    assert mgr.can_open_position("futures") is True


def test_consecutive_losses_disabled_when_zero():
    mgr = _mgr(max_consecutive_losses=0)  # disabled
    for _ in range(6):
        mgr.record_realized_pnl(-5.0)
    assert mgr.can_open_position("futures") is True


# ---------------------------------------------------------------------------
# Daily-loss-in-points breaker
# ---------------------------------------------------------------------------


def test_daily_loss_points_blocks_when_breached():
    mgr = _mgr(daily_loss_limit_points=30.0)
    mgr.record_realized_pnl(-20.0)
    assert mgr.can_open_position("futures") is True  # -20 > -30
    mgr.record_realized_pnl(-15.0)  # cumulative -35 <= -30
    assert mgr.can_open_position("futures") is False
    assert mgr.state.block_reason == BlockReason.DAILY_LOSS_LIMIT_POINTS


def test_daily_loss_points_disabled_when_zero():
    mgr = _mgr(daily_loss_limit_points=0.0)  # disabled
    mgr.record_realized_pnl(-500.0)  # huge points loss, but breaker off
    assert mgr.can_open_position("futures") is True


# ---------------------------------------------------------------------------
# Daily reset clears the streak and unblocks
# ---------------------------------------------------------------------------


def test_daily_reset_clears_streak_and_unblocks():
    mgr = _mgr(max_consecutive_losses=3)
    for _ in range(3):
        mgr.record_realized_pnl(-5.0)
    assert mgr.can_open_position("futures") is False
    mgr.reset_daily()
    assert mgr.state.consecutive_losses == 0
    assert mgr.state.is_blocked is False
    assert mgr.can_open_position("futures") is True


# ---------------------------------------------------------------------------
# Config defaults / parsing
# ---------------------------------------------------------------------------


def test_config_defaults_disabled():
    cfg = RiskConfig()
    assert cfg.max_consecutive_losses == 0
    assert cfg.daily_loss_limit_points == pytest.approx(0.0)


def test_config_from_dict_parses_new_fields():
    cfg = RiskConfig.from_dict(
        {"max_consecutive_losses": 3, "daily_loss_limit_points": 30.0}
    )
    assert cfg.max_consecutive_losses == 3
    assert cfg.daily_loss_limit_points == pytest.approx(30.0)
