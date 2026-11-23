"""Hermetic tests for :mod:`tos_runtime.posttrade.partial_fill` (#980)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos_runtime.posttrade.partial_fill import (
    ResultQuantity,
    cancelled_partial_quantity,
)

_PARTIAL_4_OF_6 = ResultQuantity(
    kind="PARTIAL_FILL", filled=Decimal("4"), remaining=Decimal("2")
)
_CANCEL_4_OF_6 = ResultQuantity(
    kind="CANCEL_ACK", filled=Decimal("4"), remaining=Decimal("2")
)


@pytest.mark.parametrize("terminal_kind", ["CANCEL_ACK", "EXPIRED", "REJECT"])
def test_every_non_execution_kind_finalises_the_partial_fill(
    terminal_kind: str,
) -> None:
    assert cancelled_partial_quantity(
        (_PARTIAL_4_OF_6,), terminal_kind=terminal_kind
    ) == Decimal("4")


def test_the_terminal_receipt_may_carry_the_cumulative_quantity_too() -> None:
    """The kernel writes the projection's quantities onto the CANCEL_ACK receipt as well."""
    assert cancelled_partial_quantity(
        (_PARTIAL_4_OF_6, _CANCEL_4_OF_6), terminal_kind="CANCEL_ACK"
    ) == Decimal("4")


def test_successive_partials_report_the_last_cumulative() -> None:
    assert cancelled_partial_quantity(
        (
            ResultQuantity(
                kind="PARTIAL_FILL", filled=Decimal("1"), remaining=Decimal("5")
            ),
            _PARTIAL_4_OF_6,
        ),
        terminal_kind="CANCEL_ACK",
    ) == Decimal("4")


@pytest.mark.parametrize(
    "terminal_kind", ["ACK", "PARTIAL_FILL", "FULL_FILL", "UNKNOWN", "TIMEOUT", None]
)
def test_a_non_terminal_kind_proves_nothing(terminal_kind: str | None) -> None:
    assert (
        cancelled_partial_quantity((_PARTIAL_4_OF_6,), terminal_kind=terminal_kind)
        is None
    )


def test_no_partial_fill_proves_nothing() -> None:
    assert (
        cancelled_partial_quantity(
            (ResultQuantity(kind="ACK", filled=None, remaining=None),),
            terminal_kind="CANCEL_ACK",
        )
        is None
    )


def test_a_full_fill_in_the_series_proves_nothing() -> None:
    """A fully filled order is the fill path's business, not a cancelled remainder's."""
    assert (
        cancelled_partial_quantity(
            (
                _PARTIAL_4_OF_6,
                ResultQuantity(
                    kind="FULL_FILL", filled=Decimal("6"), remaining=Decimal("0")
                ),
            ),
            terminal_kind="CANCEL_ACK",
        )
        is None
    )


@pytest.mark.parametrize(
    "contradiction",
    [
        ResultQuantity(kind="CANCEL_ACK", filled=Decimal("3"), remaining=Decimal("2")),
        ResultQuantity(kind="CANCEL_ACK", filled=Decimal("7"), remaining=Decimal("2")),
        ResultQuantity(
            kind="PARTIAL_FILL", filled=Decimal("5"), remaining=Decimal("4")
        ),
        ResultQuantity(kind="PARTIAL_FILL", filled=Decimal("5"), remaining=None),
        ResultQuantity(
            kind="PARTIAL_FILL", filled=Decimal("6"), remaining=Decimal("0")
        ),
        ResultQuantity(kind="PARTIAL_FILL", filled=None, remaining=Decimal("1")),
    ],
)
def test_a_contradicting_receipt_proves_nothing(contradiction: ResultQuantity) -> None:
    assert (
        cancelled_partial_quantity(
            (_PARTIAL_4_OF_6, contradiction), terminal_kind="CANCEL_ACK"
        )
        is None
    )


def test_a_zero_fill_proves_nothing() -> None:
    assert (
        cancelled_partial_quantity(
            (
                ResultQuantity(
                    kind="PARTIAL_FILL", filled=Decimal("0"), remaining=Decimal("6")
                ),
            ),
            terminal_kind="CANCEL_ACK",
        )
        is None
    )


def test_a_fully_filled_series_proves_nothing() -> None:
    """``filled == authorized`` is a FULL_FILL by another name — consuming it here would"""
    assert (
        cancelled_partial_quantity(
            (
                _PARTIAL_4_OF_6,
                ResultQuantity(
                    kind="CANCEL_ACK", filled=Decimal("6"), remaining=Decimal("0")
                ),
            ),
            terminal_kind="CANCEL_ACK",
        )
        is None
    )


def test_a_fill_after_the_order_was_closed_proves_nothing() -> None:
    """#1160 review MEDIUM-1: a late, unmatched PARTIAL_FILL must not raise the cumulative"""
    assert (
        cancelled_partial_quantity(
            (
                _PARTIAL_4_OF_6,
                _CANCEL_4_OF_6,
                ResultQuantity(
                    kind="PARTIAL_FILL", filled=Decimal("5"), remaining=Decimal("1")
                ),
                ResultQuantity(kind="CANCEL_ACK", filled=None, remaining=None),
            ),
            terminal_kind="CANCEL_ACK",
        )
        is None
    )


@pytest.mark.parametrize("closing_kind", ["CANCEL_ACK", "EXPIRED", "REJECT"])
def test_any_non_execution_receipt_closes_the_series(closing_kind: str) -> None:
    """Every non-execution kind closes the order, not just the one that ends the series."""
    assert (
        cancelled_partial_quantity(
            (
                _PARTIAL_4_OF_6,
                ResultQuantity(kind=closing_kind, filled=None, remaining=None),
                ResultQuantity(
                    kind="PARTIAL_FILL", filled=Decimal("5"), remaining=Decimal("1")
                ),
            ),
            terminal_kind="CANCEL_ACK",
        )
        is None
    )


def test_a_non_finite_quantity_proves_nothing() -> None:
    assert (
        cancelled_partial_quantity(
            (
                ResultQuantity(
                    kind="PARTIAL_FILL", filled=Decimal("NaN"), remaining=Decimal("2")
                ),
            ),
            terminal_kind="CANCEL_ACK",
        )
        is None
    )
