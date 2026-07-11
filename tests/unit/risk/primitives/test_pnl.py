"""Unit + differential tests for ``shared.risk.primitives.pnl``.

Differential contract: the primitives must be bit-for-bit equal to the 9
legacy ``_calc_profit_pct`` / ``_calc_profit_amount`` static-method copies
(read-only imports; the exit classes are NOT rewired in P4-a).
"""

from __future__ import annotations

import pytest

from shared.models.position import PositionSide
from shared.risk.primitives.pnl import profit_amount, profit_pct
from shared.strategy.exit.atr_dynamic import ATRDynamicExit
from shared.strategy.exit.mean_reversion_exit import MeanReversionExit
from shared.strategy.exit.momentum_decay import MomentumDecayExit
from shared.strategy.exit.setup_target_exit import SetupTargetExit
from shared.strategy.exit.technical_consensus_exit import TechnicalConsensusExit
from shared.strategy.exit.three_stage import ThreeStageExit
from shared.strategy.exit.track_a_exit import TrackAExit
from shared.strategy.exit.trix_golden_exit import TrixGoldenExit
from shared.strategy.exit.williams_r_exit import WilliamsRExit
from tests.unit.risk.primitives.helpers import make_position

# 9 legacy copies (read-only): guarded == early-return 0.0 on entry_price <= 0.
GUARDED_LEGACY = [ATRDynamicExit, TechnicalConsensusExit, TrixGoldenExit]
UNGUARDED_LEGACY = [
    MeanReversionExit,
    MomentumDecayExit,
    SetupTargetExit,
    ThreeStageExit,
    TrackAExit,
    WilliamsRExit,
]
ALL_LEGACY = GUARDED_LEGACY + UNGUARDED_LEGACY

SIDES = [PositionSide.LONG, PositionSide.SHORT]
ENTRIES = [70.0, 100.0, 250.5, 70000.0]
MOVE_FACTORS = [0.85, 0.95, 1.0, 1.001, 1.12]
QUANTITIES = [1, 3, 250]


class TestProfitPctUnit:
    """Direct behavior of profit_pct."""

    def test_long_gain(self) -> None:
        pos = make_position(PositionSide.LONG, 100.0)
        assert profit_pct(pos, 105.0) == pytest.approx(0.05)

    def test_long_loss(self) -> None:
        pos = make_position(PositionSide.LONG, 100.0)
        assert profit_pct(pos, 97.0) == pytest.approx(-0.03)

    def test_short_gain(self) -> None:
        pos = make_position(PositionSide.SHORT, 100.0)
        assert profit_pct(pos, 95.0) == pytest.approx(0.05)

    def test_short_loss(self) -> None:
        pos = make_position(PositionSide.SHORT, 100.0)
        assert profit_pct(pos, 103.0) == pytest.approx(-0.03)

    @pytest.mark.parametrize("side", SIDES)
    @pytest.mark.parametrize("entry", [0.0, -1.0])
    def test_entry_price_guard_returns_zero(
        self, side: PositionSide, entry: float
    ) -> None:
        """entry_price <= 0 → 0.0 (Position.profit_rate convention)."""
        pos = make_position(side, entry)
        assert profit_pct(pos, 100.0) == 0.0

    @pytest.mark.parametrize("entry", ENTRIES)
    @pytest.mark.parametrize("factor", MOVE_FACTORS)
    def test_long_short_antisymmetry(self, entry: float, factor: float) -> None:
        """Same entry/current: LONG pct == -SHORT pct (futures symmetry)."""
        current = entry * factor
        long_pos = make_position(PositionSide.LONG, entry)
        short_pos = make_position(PositionSide.SHORT, entry)
        assert profit_pct(long_pos, current) == pytest.approx(
            -profit_pct(short_pos, current)
        )

    @pytest.mark.parametrize("entry", ENTRIES)
    @pytest.mark.parametrize("delta_pct", [0.001, 0.02, 0.1])
    def test_mirror_move_symmetry(self, entry: float, delta_pct: float) -> None:
        """LONG up-move profit == SHORT equal down-move profit."""
        long_pos = make_position(PositionSide.LONG, entry)
        short_pos = make_position(PositionSide.SHORT, entry)
        up = entry * (1 + delta_pct)
        down = entry * (1 - delta_pct)
        assert profit_pct(long_pos, up) == pytest.approx(profit_pct(short_pos, down))


class TestProfitAmountUnit:
    """Direct behavior of profit_amount."""

    def test_long_amount(self) -> None:
        pos = make_position(PositionSide.LONG, 100.0, quantity=10)
        assert profit_amount(pos, 105.0) == pytest.approx(50.0)

    def test_short_amount(self) -> None:
        pos = make_position(PositionSide.SHORT, 100.0, quantity=10)
        assert profit_amount(pos, 105.0) == pytest.approx(-50.0)

    @pytest.mark.parametrize("entry", ENTRIES)
    @pytest.mark.parametrize("factor", MOVE_FACTORS)
    @pytest.mark.parametrize("quantity", QUANTITIES)
    def test_long_short_antisymmetry(
        self, entry: float, factor: float, quantity: int
    ) -> None:
        current = entry * factor
        long_pos = make_position(PositionSide.LONG, entry, quantity=quantity)
        short_pos = make_position(PositionSide.SHORT, entry, quantity=quantity)
        assert profit_amount(long_pos, current) == pytest.approx(
            -profit_amount(short_pos, current)
        )


class TestDifferentialProfitPct:
    """profit_pct == legacy _calc_profit_pct on the full grid (entry > 0)."""

    @pytest.mark.parametrize("legacy_cls", ALL_LEGACY)
    @pytest.mark.parametrize("side", SIDES)
    @pytest.mark.parametrize("entry", ENTRIES)
    @pytest.mark.parametrize("factor", MOVE_FACTORS)
    def test_grid_equivalence(
        self,
        legacy_cls: type,
        side: PositionSide,
        entry: float,
        factor: float,
    ) -> None:
        pos = make_position(side, entry)
        current = entry * factor
        assert profit_pct(pos, current) == legacy_cls._calc_profit_pct(pos, current)

    @pytest.mark.parametrize("legacy_cls", GUARDED_LEGACY)
    @pytest.mark.parametrize("side", SIDES)
    def test_zero_entry_matches_guarded_legacy(
        self, legacy_cls: type, side: PositionSide
    ) -> None:
        """Guarded copies (atr_dynamic 등) return 0.0 — primitive matches."""
        pos = make_position(side, 0.0)
        assert profit_pct(pos, 100.0) == 0.0
        assert legacy_cls._calc_profit_pct(pos, 100.0) == 0.0

    @pytest.mark.parametrize("legacy_cls", UNGUARDED_LEGACY)
    @pytest.mark.parametrize("side", SIDES)
    def test_zero_entry_formerly_unguarded_now_guarded(
        self, legacy_cls: type, side: PositionSide
    ) -> None:
        """Formerly-unguarded copies now delegate to the guarded primitive (P4-b).

        Before P4-b these copies raised ``ZeroDivisionError`` on entry == 0.
        The P4-b substitution rewires them to :func:`profit_pct`, unifying on
        the guarded behavior (0.0, matching ``Position.profit_rate``). This
        edge is unreachable in production (entry price is always > 0); the test
        pins that the deliberate, documented unification has landed.
        """
        pos = make_position(side, 0.0)
        assert legacy_cls._calc_profit_pct(pos, 100.0) == 0.0
        assert profit_pct(pos, 100.0) == 0.0


class TestDifferentialProfitAmount:
    """profit_amount == legacy _calc_profit_amount on the full grid."""

    @pytest.mark.parametrize("legacy_cls", ALL_LEGACY)
    @pytest.mark.parametrize("side", SIDES)
    @pytest.mark.parametrize("entry", ENTRIES)
    @pytest.mark.parametrize("factor", MOVE_FACTORS)
    @pytest.mark.parametrize("quantity", QUANTITIES)
    def test_grid_equivalence(
        self,
        legacy_cls: type,
        side: PositionSide,
        entry: float,
        factor: float,
        quantity: int,
    ) -> None:
        pos = make_position(side, entry, quantity=quantity)
        current = entry * factor
        assert profit_amount(pos, current) == legacy_cls._calc_profit_amount(
            pos, current
        )

    @pytest.mark.parametrize("legacy_cls", ALL_LEGACY)
    @pytest.mark.parametrize("side", SIDES)
    def test_zero_entry_equivalence(self, legacy_cls: type, side: PositionSide) -> None:
        """profit_amount has no division — all 9 copies agree at entry == 0."""
        pos = make_position(side, 0.0, quantity=5)
        assert profit_amount(pos, 100.0) == legacy_cls._calc_profit_amount(pos, 100.0)
