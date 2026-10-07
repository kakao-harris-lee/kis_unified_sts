"""JSONL records -> a validated ``tos.backtest`` bar stream.

Part of the CP-3 B1b runner (``cp3`` package). The runner was one module until the
2026-10-08 review: at 1,820 lines it broke ``config/tos_size_budget.yaml``'s
1,000-line module cap and its 100-line function cap three times over, and
registering four day-one exceptions against a budget whose own header calls
registration "가시성, 면허가 아니라" would have been the wrong answer for NEW code.
So the module was decomposed along the seams it already had, and
``tos/runtime/cp3`` was added to that budget's ``scope`` so the caps are actually
enforced here (the review's fourth gate).

Firewall: ``tos.*`` + ``tos_runtime.*`` + stdlib + ``pyyaml`` only. No
``shared.*``, no clock, no RNG, no ``subprocess``, no network. Intra-package
imports are RELATIVE — the allowlist does not name ``cp3``, so an absolute
``import cp3.…`` from a file under ``tos/`` is a TOS-FW-A violation while a
relative import carries no absolute name for the gate to classify.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from tos.backtest import Bar, BarStream, validate_bar_stream

from ._base import Cp3RunnerRefusal
from .contract import FieldRecord

__all__ = ["build_bars"]

# ===========================================================================
# Bars
# ===========================================================================


def _price(value: int | bool | str, *, field_key: str, raw_event_id: str) -> Decimal:
    """Map one ×100 integer minor-unit price onto the ``Bar``'s Decimal.

    **The mapping, stated once.** ``Bar``'s price fields are
    :data:`~tos.canonical.CanonicalDecimal` — a ``Decimal`` normalized at
    validation time so numerically-equal magnitudes share one digest. B1a
    publishes prices as *index points × 100* integers (``multiplier: 100``,
    ``scale: hundredths``, ``quantization: half_up``). The inverse is an exact
    decimal scale shift, ``Decimal(x).scaleb(-2)`` — **never** a float divide
    and never ``Decimal(x) / 100``: ``scaleb`` performs no division and so
    cannot round, which keeps the bar a lossless function of the integer and
    keeps the digest a function of the integer too.

    The integers stay the DSL-visible form: the policy compares ``z_x1000`` and
    the other integer fields, never these Decimals (``tos.dsl`` ordering
    comparisons are numeric and B1a exposes minor units precisely so an ordering
    comparison is integral — design #32 §2.5).

    Raises:
        Cp3RunnerRefusal: The value is not a plain ``int``.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise Cp3RunnerRefusal(
            f"{raw_event_id}: field {field_key!r} must be an int price in "
            f"hundredths, got {type(value).__name__}"
        )
    return Decimal(value).scaleb(-2)


def build_bars(
    records: Sequence[FieldRecord],
) -> tuple[BarStream, dict[int, FieldRecord]]:
    """Build the validated bar stream plus the ``bar_index -> record`` side table.

    ``bar_index`` is the record's position in the file (0-based, strictly
    increasing) and ``timestamp_coordinate`` is ``as_of_ms`` verbatim — the
    opaque injected coordinate ``tos.backtest`` asks for, never a clock read.
    ``session_token`` is B1a's KST session date, carried through opaquely (no
    market hours are read from it).

    Args:
        records: The validated field records, in file order.

    Returns:
        ``(bars, by_bar_index)``. The side table keeps the nine indicator
        fields (and the six bar fields) addressable by ``bar_index`` without
        putting them on the ``Bar``, which carries no field surface.

    Raises:
        Cp3RunnerRefusal: A record's prices do not form a well-formed bar
            (inverted range, open/close outside it, a non-positive price, a
            negative volume, a blank session token) — the reason is ``Bar``'s
            own validator's, re-raised with the offending ``raw_event_id``.
    """
    bars: list[Bar] = []
    by_bar_index: dict[int, FieldRecord] = {}
    for bar_index, record in enumerate(records):
        fields = record.fields
        volume = fields["volume"]
        if isinstance(volume, bool) or not isinstance(volume, int):
            raise Cp3RunnerRefusal(
                f"{record.raw_event_id}: field 'volume' must be an int, got "
                f"{type(volume).__name__}"
            )
        session_token = fields["session_token"]
        if not isinstance(session_token, str):
            raise Cp3RunnerRefusal(
                f"{record.raw_event_id}: field 'session_token' must be a str, got "
                f"{type(session_token).__name__}"
            )
        try:
            bar = Bar(
                bar_index=bar_index,
                timestamp_coordinate=record.as_of_ms,
                open_price=_price(
                    fields["open_x100"],
                    field_key="open_x100",
                    raw_event_id=record.raw_event_id,
                ),
                high_price=_price(
                    fields["high_x100"],
                    field_key="high_x100",
                    raw_event_id=record.raw_event_id,
                ),
                low_price=_price(
                    fields["low_x100"],
                    field_key="low_x100",
                    raw_event_id=record.raw_event_id,
                ),
                close_price=_price(
                    fields["close_x100"],
                    field_key="close_x100",
                    raw_event_id=record.raw_event_id,
                ),
                volume=Decimal(volume),
                session_token=session_token,
            )
        except ValueError as exc:  # ArtifactIntegrityError / ValidationError
            raise Cp3RunnerRefusal(
                f"{record.raw_event_id}: not a well-formed Bar: {exc}"
            ) from exc
        bars.append(bar)
        by_bar_index[bar_index] = record
    return validate_bar_stream(bars), by_bar_index
