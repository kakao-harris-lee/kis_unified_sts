"""The pure ``Bar`` model + stream validation (design #33 §3.1)."""

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

BarStream = tuple["Bar", ...]


class Bar(FrozenModel):
    """One broker-agnostic OHLCV bar (design #33 §3.1) — pure typed data, injected."""

    bar_index: int
    timestamp_coordinate: int
    open_price: CanonicalDecimal
    high_price: CanonicalDecimal
    low_price: CanonicalDecimal
    close_price: CanonicalDecimal
    volume: CanonicalDecimal
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
    """Validate and freeze an injected bar stream (design #33 §3.1, ∅ both ways)."""
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
    """Validate a multi-symbol ``InstrumentKey -> bar stream`` mapping (design #37 §3.6)."""
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
    """Fail closed unless the merged coordinate sequence is non-decreasing (design #37 §3.3)."""
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
    """Deterministically interleave validated lanes into one replay order (design #37 §3.3)."""
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
    """The settlement-bar reference price a deterministic fill is built from (design #33 §4.3)."""
    return bar.open_price if use_open else bar.close_price
