"""The pure ``Bar`` model + stream validation (design #33 §3.1).

A :class:`Bar` is **pure typed data**: broker-agnostic OHLCV plus an opaque injected time
coordinate. There is no loader here — parquet / duckdb / pandas ingestion is deliberately
**out-of-tree** (design #33 §0.2-8/§3.1), because ``numpy`` / ``pandas`` are outside the firewall
and because a harness that reads files is no longer a pure function of its inputs. The harness is
handed a ``tuple[Bar, ...]``.

``timestamp_coordinate`` is the design's "bar이 실어 오는 좌표" (design #33 §3.3): an **opaque
injected integer**, never a clock read. :mod:`tos.time` is itself clock-free, so the whole freshness
judgement stays a pure function of injected values, and replay reproduces exactly (design #33 §5.2).
It is *not* the causal-ordering coordinate — that is the driver's yield-order counter, deliberately
decoupled from the bar index (design #33 §3.4 MAJOR-1).

∅ **both ways** (the #17/#26 lesson, design #33 §13). An explicitly empty bar stream is a *defined*
empty run — zero ticks, zero fills, no failure — whereas a missing stream (``None``) is fail-closed.
Collapsing the two in either direction is the defect: over-rejecting an explicit empty is as wrong
as vacuously admitting a missing one.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #33 §0.3). No clock, no RNG, no numpy or
pandas anywhere in this package.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import model_validator

from tos.backtest._base import (
    BacktestIntegrityError,
    CanonicalDecimal,
    FrozenModel,
    seal_performance_surface,
)

__all__ = ["Bar", "BarStream", "settlement_price", "validate_bar_stream"]

#: An ordered, validated bar stream. A plain tuple: the harness never mutates it, and holding it as
#: a tuple is what lets the causal converter prove it consumes a **prefix** (design #33 §3.6).
BarStream = tuple["Bar", ...]


class Bar(FrozenModel):
    """One broker-agnostic OHLCV bar (design #33 §3.1) — pure typed data, injected.

    Every magnitude is a :data:`~tos.canonical.CanonicalDecimal`, so numerically-equal inputs share
    one digest and a replay trace is byte-identical (design #33 §5.2). ``session_token`` is an
    **opaque** session identifier: no market hours, no venue calendar, and no KIS/KRX fact appears
    here — broker capability belongs in injected brokercap values (D-E4), never in a bar
    (project memory ``tos-spec-broker-agnostic``).

    The OHLC relations are enforced structurally rather than assumed: a bar whose high is below its
    low, or whose open/close sit outside the range, is not a bar at all, and admitting one would let
    a fill model quote an execution price the market never printed.
    """

    #: The bar's position in its stream (0-based, strictly increasing across the stream).
    bar_index: int
    #: The opaque injected close-of-bar time coordinate — never a wall-clock read (§3.3).
    timestamp_coordinate: int
    open_price: CanonicalDecimal
    high_price: CanonicalDecimal
    low_price: CanonicalDecimal
    close_price: CanonicalDecimal
    volume: CanonicalDecimal
    #: An opaque session identifier (no market hours are read from it — broker-agnostic).
    session_token: str

    @model_validator(mode="after")
    def _bar_is_well_formed(self) -> Bar:
        """Enforce the index / magnitude / OHLC-range invariants (fail-closed)."""
        seal_performance_surface(type(self).__name__, type(self).model_fields)
        if self.bar_index < 0:
            raise BacktestIntegrityError(
                f"Bar.bar_index must be non-negative (got {self.bar_index}) — a bar with no "
                "position in the stream cannot be ordered against its neighbours"
            )
        if not self.session_token.strip():
            raise BacktestIntegrityError(
                "Bar.session_token must be a concrete opaque token — an unlabelled session is not "
                "a session (design #33 §3.1)"
            )
        if self.volume < 0:
            raise BacktestIntegrityError(
                f"Bar.volume must be non-negative (got {self.volume})"
            )
        for name in ("open_price", "high_price", "low_price", "close_price"):
            value: CanonicalDecimal = getattr(self, name)
            if value <= 0:
                raise BacktestIntegrityError(
                    f"Bar.{name} must be positive (got {value}) — a non-positive price is not a "
                    "price"
                )
        if self.high_price < self.low_price:
            raise BacktestIntegrityError(
                f"Bar.high_price ({self.high_price}) is below Bar.low_price ({self.low_price}) — "
                "an inverted range would let a fill quote a price the market never printed"
            )
        for name in ("open_price", "close_price"):
            value = getattr(self, name)
            if value > self.high_price or value < self.low_price:
                raise BacktestIntegrityError(
                    f"Bar.{name} ({value}) falls outside [low={self.low_price}, "
                    f"high={self.high_price}] — the range must contain the prints it brackets"
                )
        return self


def validate_bar_stream(bars: Sequence[Bar] | None) -> BarStream:
    """Validate and freeze an injected bar stream (design #33 §3.1, ∅ both ways).

    Args:
        bars: The injected bars. ``None`` is a **missing** stream and is fail-closed; ``()`` is an
            explicitly **empty** stream and is a defined empty run (design #33 §13).

    Returns:
        The frozen :data:`BarStream` in the supplied order.

    Raises:
        BacktestIntegrityError: If the stream is missing, or if ``bar_index`` /
            ``timestamp_coordinate`` are not both strictly increasing — a non-monotone stream is
            not a causal replay, and silently sorting it would fabricate an order the input never
            had.
    """
    if bars is None:
        raise BacktestIntegrityError(
            "a bar stream is missing — MISSING is fail-closed, materially different from an "
            "explicitly empty stream, which is a defined empty run (design #33 §13; the #17/#26 "
            "∅ 양방향 discipline)"
        )
    stream = tuple(bars)
    previous: Bar | None = None
    for bar in stream:
        if previous is not None:
            if bar.bar_index <= previous.bar_index:
                raise BacktestIntegrityError(
                    f"bar_index must strictly increase ({previous.bar_index} -> {bar.bar_index}) — "
                    "a replay consumes bars in causal order and never reorders them"
                )
            if bar.timestamp_coordinate <= previous.timestamp_coordinate:
                raise BacktestIntegrityError(
                    "timestamp_coordinate must strictly increase "
                    f"({previous.timestamp_coordinate} -> {bar.timestamp_coordinate}) — a "
                    "non-advancing time coordinate would make freshness unjudgeable (§3.3)"
                )
        previous = bar
    return stream


def settlement_price(bar: Bar, *, use_open: bool) -> CanonicalDecimal:
    """The settlement-bar reference price a deterministic fill is built from (design #33 §4.3).

    Args:
        bar: The settlement bar.
        use_open: Whether the injected basis is the bar's open (otherwise its close).

    Returns:
        The chosen price. Both choices are prints of the settlement bar itself — the model never
        interpolates, and never picks the better of the two (an optimistic execution assumption is
        an ADR-DEV-010 §8:189-190 disqualifier).
    """
    return bar.open_price if use_open else bar.close_price
