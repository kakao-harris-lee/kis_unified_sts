"""Unit + golden tests for ``shared.risk.primitives.pnl``.

Test contract (post P4-b): the primitives are pinned to **independent
golden values** — expected results are restated from the spec formula
(``(current - entry) / entry`` etc.) or written as literal constants, never
read back from an exit class.

    Why not differential vs the 9 legacy ``_calc_profit_pct`` /
    ``_calc_profit_amount`` copies? P4-b rewired those copies to *delegate* to
    these primitives, so ``primitive(x) == LegacyClass._calc_profit_pct(x)``
    became a tautology (``f(x) == f(x)``) that cannot fail and provided no
    independent cross-check. The grids below keep the same input width but
    compare against a hand-derived formula so a sign/denominator regression in
    the primitive is actually caught.

The ``entry <= 0`` guard-unification tests are the deliberate exception: they
call the legacy copies but assert against the independent literal ``0.0`` to
pin that P4-b unified the formerly-``ZeroDivisionError`` copies onto the
guarded ``0.0`` behavior. ``0.0`` is a golden constant there, not a value read
from the primitive, so those tests are not tautological.
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

# Legacy copies grouped only for the entry <= 0 guard-unification tests:
# guarded copies early-return 0.0; formerly-unguarded copies now delegate to
# the guarded primitive (P4-b) and also return 0.0.
GUARDED_LEGACY = [ATRDynamicExit, TechnicalConsensusExit, TrixGoldenExit]
UNGUARDED_LEGACY = [
    MeanReversionExit,
    MomentumDecayExit,
    SetupTargetExit,
    ThreeStageExit,
    TrackAExit,
    WilliamsRExit,
]

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


class TestProfitPctGolden:
    """profit_pct pinned to the independent ratio formula (entry > 0)."""

    @pytest.mark.parametrize("side", SIDES)
    @pytest.mark.parametrize("entry", ENTRIES)
    @pytest.mark.parametrize("factor", MOVE_FACTORS)
    def test_grid_golden(
        self,
        side: PositionSide,
        entry: float,
        factor: float,
    ) -> None:
        """Golden = ``(current - entry) / entry`` (LONG) / mirror (SHORT).

        The expected value is restated from the documented spec, not read back
        from any exit class, so a sign or denominator regression in the
        primitive is caught (the old ``== LegacyClass._calc_profit_pct(...)``
        form became tautological once P4-b made those copies delegate here).
        """
        pos = make_position(side, entry)
        current = entry * factor
        if side == PositionSide.LONG:
            expected = (current - entry) / entry
        else:
            expected = (entry - current) / entry
        assert profit_pct(pos, current) == pytest.approx(expected)

    @pytest.mark.parametrize("legacy_cls", GUARDED_LEGACY)
    @pytest.mark.parametrize("side", SIDES)
    def test_zero_entry_matches_guarded_legacy(
        self, legacy_cls: type, side: PositionSide
    ) -> None:
        """Guarded copies (atr_dynamic 등) return 0.0 — primitive matches.

        Expected is the independent literal ``0.0`` (not a value read from the
        primitive), so this pins the guard behavior rather than a tautology.
        """
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
        pins that the deliberate, documented unification has landed. Expected
        is the independent literal ``0.0``.
        """
        pos = make_position(side, 0.0)
        assert legacy_cls._calc_profit_pct(pos, 100.0) == 0.0
        assert profit_pct(pos, 100.0) == 0.0


class TestProfitAmountGolden:
    """profit_amount pinned to the independent amount formula."""

    @pytest.mark.parametrize("side", SIDES)
    @pytest.mark.parametrize("entry", ENTRIES)
    @pytest.mark.parametrize("factor", MOVE_FACTORS)
    @pytest.mark.parametrize("quantity", QUANTITIES)
    def test_grid_golden(
        self,
        side: PositionSide,
        entry: float,
        factor: float,
        quantity: int,
    ) -> None:
        """Golden = ``(current - entry) * qty`` (LONG) / mirror (SHORT)."""
        pos = make_position(side, entry, quantity=quantity)
        current = entry * factor
        if side == PositionSide.LONG:
            expected = (current - entry) * quantity
        else:
            expected = (entry - current) * quantity
        assert profit_amount(pos, current) == pytest.approx(expected)

    @pytest.mark.parametrize("side", SIDES)
    def test_zero_entry_golden(self, side: PositionSide) -> None:
        """profit_amount has no division — entry == 0 is well-defined.

        entry == 0, qty == 5, current == 100 → LONG = +500, SHORT = -500.
        Independent literals (formerly compared against the legacy copies,
        which is now a delegation tautology).
        """
        pos = make_position(side, 0.0, quantity=5)
        current = 100.0
        expected = current * 5 if side == PositionSide.LONG else -current * 5
        assert profit_amount(pos, current) == pytest.approx(expected)
