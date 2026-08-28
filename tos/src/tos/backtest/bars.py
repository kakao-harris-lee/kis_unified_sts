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

**Multi-symbol input lives here too** (design #37 §3.1/§3.3). A ``Bar`` carries no instrument, so a
multi-symbol replay is a **mapping** ``InstrumentKey -> bar stream`` and the symbol attribution is
the mapping key. :func:`validate_bar_stream_mapping` lifts the ∅-both-ways judgement to the mapping
layer, and :func:`merge_bar_streams` interleaves the validated lanes on the total order
``(timestamp_coordinate, account, instrument)``. That merge is **in-tree on purpose**: its
determinism is what makes a multi-symbol replay byte-identical, and pushing it out to the caller
would move that guarantee from ``tos.backtest`` to caller discipline (design #37 §3.3).

What the merge can and cannot enforce is stated honestly (design #37 §3.6/§9). It enforces (i)
per-lane strictly-increasing coordinates — reused verbatim from :func:`validate_bar_stream` — and
(ii) a non-decreasing coordinate across the merged output. It cannot enforce that two symbols'
``timestamp_coordinate`` values are **comparable at all**: the coordinate is an opaque injected
integer with no structural predicate to test, so a single cross-symbol time coordinate system is
**caller discipline** and a detection-free residual risk (design #37 §7-7).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #33 §0.3). No clock, no RNG, no numpy or
pandas anywhere in this package.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import model_validator

from tos.backtest._base import (
    BacktestIntegrityError,
    CanonicalDecimal,
    FrozenModel,
    seal_performance_surface,
)
from tos.engine import InstrumentKey

__all__ = [
    "Bar",
    "BarStream",
    "merge_bar_streams",
    "settlement_price",
    "validate_bar_stream",
    "validate_bar_stream_mapping",
]

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


def validate_bar_stream_mapping(
    streams: Mapping[InstrumentKey, Sequence[Bar] | None] | None,
) -> tuple[tuple[InstrumentKey, BarStream], ...]:
    """Validate a multi-symbol ``InstrumentKey -> bar stream`` mapping (design #37 §3.6).

    The single-symbol ∅ judgement (``None`` fail-closed, ``()`` a defined empty run) is lifted to
    the mapping layer **in both directions**: a missing *mapping* is fail-closed, an explicitly
    empty mapping is a defined zero-lane run, a missing *lane stream* is fail-closed, and an
    explicitly empty lane stream is a defined empty lane. Each lane is validated by
    :func:`validate_bar_stream` itself, so the per-lane strictly-increasing rule is reused rather
    than restated.

    Args:
        streams: The injected per-lane bar streams. ``None`` is a **missing** mapping; ``{}`` is an
            explicitly empty one.

    Returns:
        The validated lanes as ``(key, stream)`` pairs **in the mapping's own iteration order**.

    Raises:
        BacktestIntegrityError: If the mapping is missing, if a lane stream is missing, or if any
            lane stream is not causally ordered.
    """
    if streams is None:
        raise BacktestIntegrityError(
            "a multi-symbol bar stream mapping is missing — MISSING is fail-closed, materially "
            "different from an explicitly empty mapping, which is a defined zero-lane run "
            "(design #37 §3.6; the #17/#26 ∅ 양방향 discipline)"
        )
    lanes: list[tuple[InstrumentKey, BarStream]] = []
    for key, stream in streams.items():
        if stream is None:
            raise BacktestIntegrityError(
                f"the bar stream for lane {(key.account, key.instrument)} is missing — a declared "
                "lane with no stream is fail-closed, materially different from a lane declared "
                "with an explicitly empty stream (design #37 §3.6)"
            )
        lanes.append((key, validate_bar_stream(stream)))
    return tuple(lanes)


def _assert_merged_non_decreasing(merged: Sequence[tuple[InstrumentKey, Bar]]) -> None:
    """Fail closed unless the merged coordinate sequence is non-decreasing (design #37 §3.3).

    The one global ordering claim the merge is allowed to make. It is deliberately
    **non-decreasing** rather than strictly increasing: two symbols may legitimately carry the same
    ``timestamp_coordinate``, and the tie is broken by ``(account, instrument)`` — a strict check
    would refuse a well-formed input.

    Args:
        merged: The merged ``(key, bar)`` sequence.

    Raises:
        BacktestIntegrityError: If a later item carries an earlier coordinate — a merge that
            reorders time is not a merge, and admitting one would hand the engine a stream whose
            order the input never had.
    """
    previous: int | None = None
    for _key, bar in merged:
        if previous is not None and bar.timestamp_coordinate < previous:
            raise BacktestIntegrityError(
                "the merged multi-symbol stream is not non-decreasing in timestamp_coordinate "
                f"({previous} -> {bar.timestamp_coordinate}) — the merge preserves the injected "
                "time order and never fabricates one (design #37 §3.3)"
            )
        previous = bar.timestamp_coordinate


def merge_bar_streams(
    lanes: Sequence[tuple[InstrumentKey, BarStream]],
) -> tuple[tuple[InstrumentKey, Bar], ...]:
    """Deterministically interleave validated lanes into one replay order (design #37 §3.3).

    The merge is a **pure function of its inputs** on the total order
    ``(bar.timestamp_coordinate, key.account, key.instrument)``. The tie-break is what makes it a
    total order and therefore what makes a multi-symbol replay byte-identical: two symbols sharing a
    coordinate are ordered by their instrument key, never by mapping insertion or dict iteration
    (design #37 §1.6).

    **Not look-ahead** (design #37 §3.3, ADR-DEV-010 BTE-INV-004). The frontier holds at most one
    pending bar *per lane* and compares only their ordering metadata; no future bar enters any
    decision, and each lane's converter still sees only its own current bar.

    Args:
        lanes: The validated ``(key, stream)`` pairs — normally
            :func:`validate_bar_stream_mapping`'s output.

    Returns:
        The merged ``(key, bar)`` pairs. Lane-internal order is preserved exactly; the merge never
        reorders within a stream.

    Raises:
        BacktestIntegrityError: If a lane key repeats — a repeated key makes the tie-break
            non-total and the merge non-deterministic — or if the merged coordinate sequence is not
            non-decreasing.
    """
    keys = [key for key, _stream in lanes]
    if len(set(keys)) != len(keys):
        raise BacktestIntegrityError(
            "the lanes handed to merge_bar_streams repeat an instrument key — the merge order "
            "(timestamp_coordinate, account, instrument) is only a total order when the keys are "
            "distinct, and a repeated key would make the interleave non-deterministic "
            "(design #37 §3.3)"
        )
    cursors = [0] * len(lanes)
    merged: list[tuple[InstrumentKey, Bar]] = []
    remaining = sum(len(stream) for _key, stream in lanes)
    for _step in range(remaining):
        chosen: int | None = None
        chosen_order: tuple[int, str, str] | None = None
        for index, (key, stream) in enumerate(lanes):
            cursor = cursors[index]
            if cursor >= len(stream):
                continue
            order = (stream[cursor].timestamp_coordinate, key.account, key.instrument)
            if chosen_order is None or order < chosen_order:
                chosen, chosen_order = index, order
        if chosen is None:  # pragma: no cover - the loop runs exactly `remaining` times
            raise BacktestIntegrityError(
                "the multi-symbol merge exhausted its lanes early — the frontier and the bar count "
                "disagree (design #37 §3.3)"
            )
        key, stream = lanes[chosen]
        merged.append((key, stream[cursors[chosen]]))
        cursors[chosen] += 1
    _assert_merged_non_decreasing(merged)
    return tuple(merged)


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
