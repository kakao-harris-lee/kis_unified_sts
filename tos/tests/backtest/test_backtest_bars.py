"""§3.1 — the pure ``Bar`` model + ∅-both-ways stream validation (design #33 §3.1/§13).

A bar is pure typed data with no loader behind it: parquet / duckdb ingestion is out-of-tree
because ``numpy`` / ``pandas`` are outside the firewall (design #33 §0.2-8). What this module proves
is that the *model* refuses the shapes a fill model could otherwise exploit — an inverted range, a
close outside its own range, a negative volume — and that the stream discipline distinguishes a
**missing** stream from an **explicitly empty** one in both directions (the #17/#26 ∅ defect class).

Regime tag: orchestration authoring evidence only; closes no EV (design #33 §1.1).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.backtest import (
    BacktestIntegrityError,
    Bar,
    reference_bars,
    settlement_price,
    validate_bar_stream,
)

from ._backtest_fixtures import INTEGRITY_ERRORS


def _bar(**overrides: object) -> Bar:
    """A well-formed reference bar with the given overrides."""
    base: dict[str, object] = {
        "bar_index": 0,
        "timestamp_coordinate": 60,
        "open_price": Decimal(100),
        "high_price": Decimal(101),
        "low_price": Decimal(99),
        "close_price": Decimal(100),
        "volume": Decimal(1000),
        "session_token": "session-0",
    }
    base.update(overrides)
    return Bar(**base)  # type: ignore[arg-type]


def test_a_well_formed_bar_constructs() -> None:
    """(§3.1) The happy shape exists — the negative tests below are not vacuous."""
    bar = _bar()
    assert bar.bar_index == 0
    assert bar.close_price == Decimal(100)


def test_an_inverted_range_is_refused() -> None:
    """(§3.1) high < low would let a fill quote a price the market never printed."""
    with pytest.raises(INTEGRITY_ERRORS, match="below Bar.low_price"):
        _bar(high_price=Decimal(98))


@pytest.mark.parametrize("field", ["open_price", "close_price"])
def test_a_print_outside_its_own_range_is_refused(field: str) -> None:
    """(§3.1) The range must contain the prints it brackets — both ends, both fields."""
    with pytest.raises(INTEGRITY_ERRORS, match="falls outside"):
        _bar(**{field: Decimal(200)})
    with pytest.raises(INTEGRITY_ERRORS, match="falls outside"):
        _bar(**{field: Decimal(1)})


@pytest.mark.parametrize(
    "field", ["open_price", "high_price", "low_price", "close_price"]
)
def test_a_non_positive_price_is_not_a_price(field: str) -> None:
    """(§3.1) Zero / negative prices are refused rather than silently clamped."""
    with pytest.raises(INTEGRITY_ERRORS, match="must be positive"):
        _bar(**{field: Decimal(0)})


def test_a_negative_volume_and_index_are_refused() -> None:
    """(§3.1) Ill-formed magnitudes are refused; a participation cap needs a real volume."""
    with pytest.raises(INTEGRITY_ERRORS, match="volume must be non-negative"):
        _bar(volume=Decimal(-1))
    with pytest.raises(INTEGRITY_ERRORS, match="bar_index must be non-negative"):
        _bar(bar_index=-1)


def test_an_unlabelled_session_is_not_a_session() -> None:
    """(§3.1) The opaque session token must be concrete — "" is not a session."""
    with pytest.raises(INTEGRITY_ERRORS, match="session_token"):
        _bar(session_token="   ")


def test_a_missing_stream_is_fail_closed_but_an_empty_stream_is_a_defined_run() -> None:
    """(§13 ∅ 양방향) MISSING and EXPLICIT_EMPTY are distinguished in **both** directions.

    Over-rejecting an explicit empty is exactly as wrong as vacuously admitting a missing one — the
    #17/#26 defect class the series has now hit twice.
    """
    with pytest.raises(BacktestIntegrityError, match="missing"):
        validate_bar_stream(None)
    assert validate_bar_stream([]) == ()
    assert reference_bars(0) == ()


def test_a_non_monotone_stream_is_refused_rather_than_sorted() -> None:
    """(§3.1) A replay consumes bars in causal order; silently sorting would fabricate one."""
    first = _bar(bar_index=0, timestamp_coordinate=60)
    duplicate_index = _bar(bar_index=0, timestamp_coordinate=120)
    with pytest.raises(BacktestIntegrityError, match="bar_index must strictly increase"):
        validate_bar_stream([first, duplicate_index])

    stalled_time = _bar(bar_index=1, timestamp_coordinate=60)
    with pytest.raises(
        BacktestIntegrityError, match="timestamp_coordinate must strictly increase"
    ):
        validate_bar_stream([first, stalled_time])


def test_the_reference_profile_is_a_valid_monotone_stream() -> None:
    """(§5.1) The mandated scenarios' synthetic profile really passes the stream discipline."""
    bars = reference_bars(4)
    assert [bar.bar_index for bar in bars] == [0, 1, 2, 3]
    assert validate_bar_stream(bars) == bars
    coordinates = [bar.timestamp_coordinate for bar in bars]
    assert coordinates == sorted(set(coordinates))


def test_a_negative_reference_bar_count_is_not_an_empty_stream() -> None:
    """(§13) ∅ is explicit, never inferred from an ill-formed input."""
    with pytest.raises(BacktestIntegrityError, match="not an empty stream"):
        reference_bars(-1)


def test_the_settlement_basis_is_a_print_of_the_settlement_bar() -> None:
    """(§4.3) Both bases are prints of the bar itself — never an interpolation, never the better."""
    bar = _bar(open_price=Decimal("99.5"), close_price=Decimal("100.5"))
    assert settlement_price(bar, use_open=True) == bar.open_price
    assert settlement_price(bar, use_open=False) == bar.close_price
