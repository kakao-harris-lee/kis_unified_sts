"""Golden-master pin for ``RiskManager.can_open_position`` (P4-h2 behavior-0).

Written *before* the P4-h2 breaker-delegation refactor and expected to stay
**green unmodified** afterwards, proving the refactor is behavior-0.

``can_open_position`` is a short-circuit chain of independent gates. This suite
freezes its full *decision surface* — the returned ``bool`` **and** the block
state it latches (``is_blocked`` + ``block_reason``) — across a grid that walks
each gate's boundary (threshold, ±1) and the gate-ordering precedence.

Every expected value is **hand-derived from the gate arithmetic**, never read
back from the code, so a boundary-operator, sign, or ordering regression is
actually caught.

Gate order enforced by the current code (a delegation must not reorder it):

    1. is_blocked            → returns False, keeps existing reason
    2. daily-loss fraction   → auto-blocks DAILY_LOSS_LIMIT       (PRESERVED)
    3. consecutive losses    → auto-blocks CONSECUTIVE_LOSSES      (DELEGATED)
    4. daily-loss in points  → auto-blocks DAILY_LOSS_LIMIT_POINTS (PRESERVED)
    5. max total positions   → returns False, NO latch             (PRESERVED)
    6. per-asset positions   → returns False, NO latch             (PRESERVED)
    7. critical drawdown     → returns False, NO latch             (PRESERVED)

P4-h2 delegates ONLY gate 3's ``>=`` comparison to
``shared.risk.primitives.breakers.consecutive_exceeds`` (exact integer
boundary). Gate 2 stays inline: the manager compares a *percent-space*
``daily_pnl_pct`` (``(pnl/capital)*100``) against a percent limit, and its
production branch reads a **pre-derived stored** ``state.daily_pnl_pct`` that
can diverge from ``daily_pnl/capital`` (cases ``E4``/``E5``) — neither is representable
by the fraction-space ``loss_fraction_exceeds`` primitive without changing the
float-rounding path / re-deriving, so forcing it would break behavior-0.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from shared.risk.config import RiskConfig
from shared.risk.manager import RiskManager
from shared.risk.models import AssetExposure, BlockReason, DrawdownLevel


@dataclass
class Case:
    """One ``can_open_position`` scenario with a hand-derived expectation."""

    id: str
    asset_class: str = "stock"

    # --- config knobs -----------------------------------------------------
    daily_loss_limit_pct: float = 5.0
    max_total_positions: int = 20
    max_consecutive_losses: int = 0  # 0 = disabled
    daily_loss_limit_points: float = 0.0  # 0 = disabled
    stock_max_positions: int | None = None  # override asset_limits["stock"]
    clear_asset_limits: bool = False

    # --- daily-loss test/direct interface (both set -> test-attr path) ----
    test_daily_pnl: float | None = None
    test_initial_capital: float | None = None

    # --- state knobs ------------------------------------------------------
    pre_blocked_reason: BlockReason | None = None
    consecutive_losses: int = 0
    daily_realized_pnl: float = 0.0
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    drawdown_level: DrawdownLevel = DrawdownLevel.SAFE

    # --- metrics knobs ----------------------------------------------------
    total_positions: int = 0
    stock_position_count: int = 0
    futures_position_count: int = 0

    # --- hand-derived expectation ----------------------------------------
    expect_result: bool = True
    expect_blocked: bool = False
    expect_reason: str | None = None


def _build(case: Case) -> RiskManager:
    cfg = RiskConfig(
        daily_loss_limit_pct=case.daily_loss_limit_pct,
        max_total_positions=case.max_total_positions,
        initial_capital=10_000_000,
        max_consecutive_losses=case.max_consecutive_losses,
        daily_loss_limit_points=case.daily_loss_limit_points,
    )
    if case.clear_asset_limits:
        cfg.asset_limits.clear()
    elif case.stock_max_positions is not None:
        cfg.asset_limits["stock"].max_positions = case.stock_max_positions

    mgr = RiskManager(cfg)

    if case.pre_blocked_reason is not None:
        mgr.state.block_trading(case.pre_blocked_reason)

    mgr.state.consecutive_losses = case.consecutive_losses
    mgr.state.daily_realized_pnl = case.daily_realized_pnl
    mgr.state.daily_pnl = case.daily_pnl
    mgr.state.daily_pnl_pct = case.daily_pnl_pct
    mgr.state.drawdown_level = case.drawdown_level

    if case.test_daily_pnl is not None:
        mgr._daily_pnl = case.test_daily_pnl
    if case.test_initial_capital is not None:
        mgr._initial_capital = case.test_initial_capital

    mgr.metrics.total_positions = case.total_positions
    if case.stock_position_count:
        mgr.metrics.exposure_by_asset["stock"] = AssetExposure(
            "stock", position_count=case.stock_position_count
        )
    if case.futures_position_count:
        mgr.metrics.exposure_by_asset["futures"] = AssetExposure(
            "futures", position_count=case.futures_position_count
        )
    return mgr


CASES: list[Case] = [
    # ---- Group A: all clear ---------------------------------------------
    Case("A1-clear-stock", expect_result=True),
    Case("A2-clear-futures", asset_class="futures", expect_result=True),
    # ---- Group B: is_blocked (gate 1) short-circuits everything ----------
    Case(
        "B1-preblocked-manual",
        pre_blocked_reason=BlockReason.MANUAL,
        expect_result=False,
        expect_blocked=True,
        expect_reason="manual",
    ),
    Case(
        "B2-preblocked-wins-over-consecutive",
        pre_blocked_reason=BlockReason.MANUAL,
        max_consecutive_losses=3,
        consecutive_losses=5,
        expect_result=False,
        expect_blocked=True,
        expect_reason="manual",
    ),
    # ---- Group C: consecutive-loss gate (DELEGATED) ----------------------
    Case(
        "C1-consec-below",
        max_consecutive_losses=3,
        consecutive_losses=2,
        expect_result=True,
    ),
    Case(
        "C2-consec-at-threshold",
        max_consecutive_losses=3,
        consecutive_losses=3,
        expect_result=False,
        expect_blocked=True,
        expect_reason="consecutive_losses",
    ),
    Case(
        "C3-consec-above-threshold",
        max_consecutive_losses=3,
        consecutive_losses=4,
        expect_result=False,
        expect_blocked=True,
        expect_reason="consecutive_losses",
    ),
    Case(
        "C4-consec-disabled-zero",
        max_consecutive_losses=0,
        consecutive_losses=10,
        expect_result=True,
    ),
    Case(
        "C5-consec-at-one",
        max_consecutive_losses=1,
        consecutive_losses=1,
        expect_result=False,
        expect_blocked=True,
        expect_reason="consecutive_losses",
    ),
    Case(
        "C6-consec-zero-streak",
        max_consecutive_losses=3,
        consecutive_losses=0,
        expect_result=True,
    ),
    # ---- Group D: daily-loss fraction, test-attr path (PRESERVED) --------
    Case(
        "D1-dl-testattr-within",
        test_daily_pnl=-400_000,
        test_initial_capital=10_000_000,
        expect_result=True,
    ),
    Case(
        "D2-dl-testattr-at-limit",
        test_daily_pnl=-500_000,
        test_initial_capital=10_000_000,
        expect_result=True,
    ),  # -5% == limit passes
    Case(
        "D3-dl-testattr-breach",
        test_daily_pnl=-600_000,
        test_initial_capital=10_000_000,
        expect_result=False,
        expect_blocked=True,
        expect_reason="daily_loss_limit",
    ),
    Case(
        "D4-dl-testattr-zero-capital",
        test_daily_pnl=-100_000,
        test_initial_capital=0,
        expect_result=True,
    ),  # safe default at cap<=0
    Case(
        "D5-dl-testattr-positive",
        test_daily_pnl=500_000,
        test_initial_capital=10_000_000,
        expect_result=True,
    ),
    Case(
        "D6-dl-testattr-just-beyond-limit",
        test_daily_pnl=-500_001,  # -5.00001% < -5% (strict boundary)
        test_initial_capital=10_000_000,
        expect_result=False,
        expect_blocked=True,
        expect_reason="daily_loss_limit",
    ),
    # ---- Group E: daily-loss fraction, state path (PRESERVED) ------------
    Case("E1-dl-state-within", daily_pnl_pct=-4.0, expect_result=True),
    Case("E2-dl-state-at-limit", daily_pnl_pct=-5.0, expect_result=True),
    Case(
        "E3-dl-state-breach",
        daily_pnl_pct=-6.0,
        expect_result=False,
        expect_blocked=True,
        expect_reason="daily_loss_limit",
    ),
    # E4/E5 pin that the state path reads the STORED daily_pnl_pct, NOT a fresh
    # daily_pnl/capital division: daily_pnl=-9M (=-90%) but the stored pct is
    # within limit -> pass. This is exactly what a naive loss_fraction_exceeds
    # delegation (re-deriving pnl/capital) would break.
    #
    # E4 uses stored pct = 0.0. That is a weak witness: 0.0 is also what a
    # daily-reset / ignore-state bug would leave behind, so "passed" does not
    # by itself prove the STORED value was consumed.
    Case(
        "E4-dl-state-reads-stored-pct-not-daily-pnl",
        daily_pnl=-9_000_000,
        daily_pnl_pct=0.0,
        expect_result=True,
    ),
    # E5 is the strong witness: a NONZERO within-limit stored pct that cannot be
    # confused with a reset/ignore sentinel. limit=3.0% so the gate compares
    # daily_pnl_pct >= -3.0. Stored pct=-1.0 -> -1.0 >= -3.0 -> True (pass),
    # while a naive re-derivation from daily_pnl would give -9M/10M = -90% ->
    # -90.0 >= -3.0 -> False (block). The two paths give OPPOSITE results, so a
    # green here proves the stored pct (-1.0), not daily_pnl, drives the gate.
    Case(
        "E5-dl-state-nonzero-stored-pct-beats-daily-pnl-rederive",
        daily_loss_limit_pct=3.0,
        daily_pnl=-9_000_000,  # -90% if naively re-derived -> would block
        daily_pnl_pct=-1.0,  # stored, within -3.0% limit -> passes
        expect_result=True,
        expect_blocked=False,
        expect_reason=None,
    ),
    # ---- Group F: daily-loss in points (PRESERVED) -----------------------
    Case(
        "F1-dlp-within",
        daily_loss_limit_points=30.0,
        daily_realized_pnl=-20.0,
        expect_result=True,
    ),
    Case(
        "F2-dlp-at-threshold",
        daily_loss_limit_points=30.0,
        daily_realized_pnl=-30.0,  # -30 <= -30 fires (inclusive)
        expect_result=False,
        expect_blocked=True,
        expect_reason="daily_loss_limit_points",
    ),
    Case(
        "F3-dlp-beyond",
        daily_loss_limit_points=30.0,
        daily_realized_pnl=-35.0,
        expect_result=False,
        expect_blocked=True,
        expect_reason="daily_loss_limit_points",
    ),
    Case(
        "F4-dlp-disabled-zero",
        daily_loss_limit_points=0.0,
        daily_realized_pnl=-500.0,
        expect_result=True,
    ),
    # ---- Group G: max total positions (PRESERVED, no latch) --------------
    Case(
        "G1-mtp-at",
        max_total_positions=3,
        total_positions=3,
        expect_result=False,
        expect_blocked=False,
        expect_reason=None,
    ),
    Case("G2-mtp-below", max_total_positions=3, total_positions=2, expect_result=True),
    Case(
        "G3-mtp-above",
        max_total_positions=3,
        total_positions=5,
        expect_result=False,
        expect_blocked=False,
        expect_reason=None,
    ),
    # ---- Group H: per-asset positions (PRESERVED, no latch) --------------
    Case(
        "H1-pa-at",
        stock_max_positions=2,
        total_positions=2,
        stock_position_count=2,
        expect_result=False,
        expect_blocked=False,
    ),
    Case(
        "H2-pa-below",
        stock_max_positions=2,
        total_positions=1,
        stock_position_count=1,
        expect_result=True,
    ),
    Case(
        "H3-pa-cleared-failopen",
        asset_class="crypto",
        clear_asset_limits=True,
        expect_result=True,
    ),
    Case(
        "H4-pa-futures-ok-while-stock-full",
        asset_class="futures",
        stock_max_positions=2,
        total_positions=2,
        stock_position_count=2,
        expect_result=True,
    ),
    # ---- Group I: critical drawdown (PRESERVED, no latch) ----------------
    Case(
        "I1-dd-critical",
        drawdown_level=DrawdownLevel.CRITICAL,
        expect_result=False,
        expect_blocked=False,
        expect_reason=None,
    ),
    Case("I2-dd-warning", drawdown_level=DrawdownLevel.WARNING, expect_result=True),
    Case("I3-dd-danger", drawdown_level=DrawdownLevel.DANGER, expect_result=True),
    # ---- Group J: gate-ordering precedence (must not be reordered) -------
    Case(
        "J1-daily-loss-frac-beats-consecutive",
        test_daily_pnl=-600_000,
        test_initial_capital=10_000_000,
        max_consecutive_losses=3,
        consecutive_losses=5,
        expect_result=False,
        expect_blocked=True,
        expect_reason="daily_loss_limit",  # gate 2 before gate 3
    ),
    Case(
        "J2-consecutive-beats-points",
        max_consecutive_losses=3,
        consecutive_losses=3,
        daily_loss_limit_points=30.0,
        daily_realized_pnl=-100.0,
        expect_result=False,
        expect_blocked=True,
        expect_reason="consecutive_losses",  # gate 3 before gate 4
    ),
    Case(
        "J3-points-beats-max-total",
        daily_loss_limit_points=30.0,
        daily_realized_pnl=-40.0,
        max_total_positions=3,
        total_positions=5,
        expect_result=False,
        expect_blocked=True,
        expect_reason="daily_loss_limit_points",  # gate 4 before gate 5
    ),
    Case(
        "J4-daily-loss-frac-beats-critical-drawdown",
        daily_pnl_pct=-6.0,
        drawdown_level=DrawdownLevel.CRITICAL,
        expect_result=False,
        expect_blocked=True,
        expect_reason="daily_loss_limit",  # gate 2 latches before gate 7
    ),
]


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_can_open_position_decision_surface(case: Case) -> None:
    mgr = _build(case)

    result = mgr.can_open_position(case.asset_class)

    reason = mgr.state.block_reason.value if mgr.state.block_reason else None
    assert result is case.expect_result, f"{case.id}: result"
    assert mgr.state.is_blocked is case.expect_blocked, f"{case.id}: is_blocked"
    assert reason == case.expect_reason, f"{case.id}: block_reason"
