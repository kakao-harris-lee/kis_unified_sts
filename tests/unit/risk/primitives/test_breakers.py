"""Unit tests for ``shared.risk.primitives.breakers`` (P4-d).

Pins the shared loss-breaker predicates to independent golden values (spec
formulae / literal constants), never read back from a consumer — so a sign,
denominator, or boundary-operator regression is actually caught.

Two consumer families share these predicates with different boundary/guard
arguments:

* kill-switch conditions → ``inclusive=True`` (at-or-beyond) +
  ``equity_nonpositive="safe"`` (``equity <= 0`` never trips).
* MDD filters → ``inclusive=False`` (strict) + ``equity_nonpositive="raise"``
  (guardless division; ``equity == 0`` raises).
"""

from __future__ import annotations

import pytest

from shared.risk.primitives.breakers import consecutive_exceeds, loss_fraction_exceeds

# 100M equity, 3% limit → boundary loss = -3,000,000 KRW.
EQUITY = 100_000_000.0
LIMIT = 0.03
BOUNDARY_LOSS = -EQUITY * LIMIT  # exactly at the limit


class TestLossFractionBoundary:
    """The inclusive flag is the ONLY difference between kill and filter."""

    def test_kill_inclusive_trips_exactly_at_limit(self) -> None:
        """Kill-switch: loss == limit fires (``>=``)."""
        assert (
            loss_fraction_exceeds(
                BOUNDARY_LOSS,
                EQUITY,
                LIMIT,
                inclusive=True,
                equity_nonpositive="safe",
            )
            is True
        )

    def test_filter_strict_passes_exactly_at_limit(self) -> None:
        """MDD filter: loss == limit does NOT fire (strict ``<``)."""
        assert (
            loss_fraction_exceeds(
                BOUNDARY_LOSS,
                EQUITY,
                LIMIT,
                inclusive=False,
                equity_nonpositive="raise",
            )
            is False
        )

    def test_both_trip_one_krw_beyond_limit(self) -> None:
        beyond = BOUNDARY_LOSS - 1.0
        assert (
            loss_fraction_exceeds(
                beyond, EQUITY, LIMIT, inclusive=True, equity_nonpositive="safe"
            )
            is True
        )
        assert (
            loss_fraction_exceeds(
                beyond, EQUITY, LIMIT, inclusive=False, equity_nonpositive="raise"
            )
            is True
        )

    def test_neither_trips_within_limit(self) -> None:
        within = BOUNDARY_LOSS + 1.0  # smaller loss
        assert (
            loss_fraction_exceeds(
                within, EQUITY, LIMIT, inclusive=True, equity_nonpositive="safe"
            )
            is False
        )
        assert (
            loss_fraction_exceeds(
                within, EQUITY, LIMIT, inclusive=False, equity_nonpositive="raise"
            )
            is False
        )


class TestLossFractionSign:
    """A loss is negative pnl; a profit must never trip."""

    @pytest.mark.parametrize("inclusive", [True, False])
    def test_profit_never_trips(self, inclusive: bool) -> None:
        mode = "safe" if inclusive else "raise"
        assert (
            loss_fraction_exceeds(
                +5_000_000.0,
                EQUITY,
                LIMIT,
                inclusive=inclusive,
                equity_nonpositive=mode,
            )
            is False
        )

    def test_zero_pnl_never_trips(self) -> None:
        assert (
            loss_fraction_exceeds(
                0.0, EQUITY, LIMIT, inclusive=True, equity_nonpositive="safe"
            )
            is False
        )
        assert (
            loss_fraction_exceeds(
                0.0, EQUITY, LIMIT, inclusive=False, equity_nonpositive="raise"
            )
            is False
        )

    def test_golden_fraction_matches_hand_derived(self) -> None:
        """-4,000,000 / 100M = -0.04; loss magnitude 0.04 > 0.03 → trip."""
        pnl = -4_000_000.0
        # Independent restatement of the intended math, not read from the fn.
        loss_magnitude = -(pnl / EQUITY)
        assert loss_magnitude == pytest.approx(0.04)
        assert (
            loss_fraction_exceeds(
                pnl, EQUITY, LIMIT, inclusive=True, equity_nonpositive="safe"
            )
            is True
        )


class TestLossFractionEquityNonPositive:
    """``equity <= 0`` handling must reproduce each consumer's prior behavior."""

    @pytest.mark.parametrize("equity", [0.0, -1.0, -100.0])
    @pytest.mark.parametrize("inclusive", [True, False])
    def test_safe_returns_false(self, equity: float, inclusive: bool) -> None:
        """kill-switch guard: ``equity <= 0`` never trips."""
        assert (
            loss_fraction_exceeds(
                -50_000_000.0,
                equity,
                LIMIT,
                inclusive=inclusive,
                equity_nonpositive="safe",
            )
            is False
        )

    def test_raise_zero_equity_raises_zero_division(self) -> None:
        """MDD filter behavior: guardless ``pnl / 0`` raises ZeroDivisionError."""
        with pytest.raises(ZeroDivisionError):
            loss_fraction_exceeds(
                -1.0, 0.0, LIMIT, inclusive=False, equity_nonpositive="raise"
            )

    def test_raise_negative_equity_computes_without_raising(self) -> None:
        """MDD filter behavior: ``equity < 0`` divides (sign-flipped), no raise.

        pnl=-100, equity=-1000 → loss_fraction = +0.1 → ``0.1 < -0.03`` False.
        """
        assert (
            loss_fraction_exceeds(
                -100.0, -1000.0, LIMIT, inclusive=False, equity_nonpositive="raise"
            )
            is False
        )

    def test_invalid_mode_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="equity_nonpositive"):
            loss_fraction_exceeds(
                -1.0,
                EQUITY,
                LIMIT,
                inclusive=True,
                equity_nonpositive="bogus",  # type: ignore[arg-type]
            )


class TestConsecutiveExceeds:
    """Raw ``>=`` threshold comparison (default inclusive)."""

    @pytest.mark.parametrize(
        ("count", "threshold", "expected"),
        [
            (5, 6, False),
            (6, 6, True),  # inclusive boundary: equal fires
            (7, 6, True),
            (0, 1, False),
            (10, 10, True),
        ],
    )
    def test_inclusive_default(
        self, count: int, threshold: int, expected: bool
    ) -> None:
        assert consecutive_exceeds(count, threshold) is expected

    @pytest.mark.parametrize(
        ("count", "threshold", "expected"),
        [
            (6, 6, False),  # strict: equal does NOT fire
            (7, 6, True),
        ],
    )
    def test_strict_variant(self, count: int, threshold: int, expected: bool) -> None:
        assert consecutive_exceeds(count, threshold, inclusive=False) is expected
