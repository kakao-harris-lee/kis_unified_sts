"""§8-5 — the converter's structural no-look-ahead + the D-E2 / time slots (design #33 §3.3/§3.5/§3.6).

ADR-DEV-010 BTE-INV-004:137-139 requires every indicator and input to be bounded by the current
context timestamp, and §8:182-184 makes look-ahead a **disqualifier**. The design's answer is not a
rule the converter follows but a shape it has: it is a generator that pulls one bar, emits that
bar's tick, and keeps no reference to any bar. The tests here measure that mechanically — how many
bars had been pulled from the source when tick *k* was yielded, and what the converter is holding
afterwards — so a mutation that materialises the stream (``bars = tuple(bars)``) or peeks ahead is
caught rather than argued about.

The two injected slots are also pinned: the D-E2 resolver slot resolves **no value** in slice #1
(the mechanism runs, the decision starves — design #33 §3.5), and every time coordinate is derived
from the bar's own opaque coordinate with no clock call anywhere (§3.3).

Regime tag: orchestration authoring evidence only; closes no EV (design #33 §1.1).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from tos.backtest import (
    BacktestIntegrityError,
    Bar,
    ProvisionalContextResolver,
    reference_bars,
    resolved_value_surface_absent,
)
from tos.engine import (
    DecisionContextResolver,
    DecisionTickPayload,
    TimeAdmissionInputs,
    time_admits,
)
from tos.ordering import OrderingEvent

from ._backtest_fixtures import (
    INTEGRITY_ERRORS,
    build_converter,
    instrument_key,
    issue_capsule,
    time_projection,
)


class _CountingSource:
    """A bar source that records how many bars have been pulled."""

    def __init__(self, bars: tuple[Bar, ...]) -> None:
        self.pulled = 0
        self._bars = bars

    def __iter__(self) -> Iterator[Bar]:
        """Yield bars one at a time, counting each pull."""
        for bar in self._bars:
            self.pulled += 1
            yield bar


def test_the_converter_consumes_a_strict_prefix() -> None:
    """(§3.6/§8-5) When tick *k* is yielded, exactly *k+1* bars have been pulled — never more.

    This is the structural form of "bounded by the current context timestamp": the converter cannot
    have used bar *t+1* to build bar *t*'s decision input, because bar *t+1* has not been read yet.
    A mutation that buffers the stream first (``tuple(bars)``) pulls every bar before the first
    tick and fails here immediately.
    """
    source = _CountingSource(reference_bars(5))
    converter = build_converter()
    for index, tick in enumerate(converter.stream(source)):
        assert source.pulled == index + 1, (
            f"tick {index} was produced after {source.pulled} bar pulls — a converter that has "
            "already read a future bar can express look-ahead (ADR-DEV-010 §8:182-184)"
        )
        assert tick.bar.bar_index == index


def test_the_converter_retains_no_bar_between_ticks() -> None:
    """(§3.1/§3.6) The converter's own state holds no bar — not the current one, not a window."""
    converter = build_converter()
    stream = converter.stream(reference_bars(4))
    next(stream)
    next(stream)
    held = [
        f"{name}={value!r}"
        for name, value in vars(converter).items()
        if isinstance(value, Bar)
        or (
            isinstance(value, (list, tuple, set, dict))
            and any(isinstance(item, Bar) for item in value)
        )
    ]
    assert held == [], (
        f"the converter retains bar state {held} — retained bars are what makes look-ahead "
        "expressible in the first place (design #33 §3.6)"
    )


def test_exactly_one_tick_per_bar_in_stream_order() -> None:
    """(§3.1) One ``DECISION_TICK`` per bar, in order — no coalescing, no duplication."""
    bars = reference_bars(4)
    ticks = list(build_converter().stream(bars))
    assert len(ticks) == len(bars)
    assert [tick.bar.bar_index for tick in ticks] == [0, 1, 2, 3]
    assert all(tick.payload.instrument_key == instrument_key() for tick in ticks)


def test_the_converter_leaves_the_causal_coordinate_to_the_driver() -> None:
    """(§3.4 MAJOR-1) The converter stamps no ordering coordinate — the driver owns it.

    Binding the coordinate here, to anything bar-derived, is the defect the v1.1 revision removed:
    the engine's global ``_last_reference`` gate compares against the last *admitted event*, not the
    triggering tick, so a bar-coupled coordinate produces a false ``REVERSED`` on next-bar
    settlement (design #33 §3.4).
    """
    ticks = list(build_converter().stream(reference_bars(3)))
    assert all(tick.payload.reference == OrderingEvent() for tick in ticks)


def test_the_provisional_resolver_satisfies_the_engine_slot_and_resolves_no_value() -> None:
    """(§3.5) The D-E2 plug is honoured structurally, and slice #1 binds the SnapshotRef only.

    Anti-phantom (design #33 §0.5): the absence claim is read off the shipped structure rather than
    asserted in prose — a slice-1 payload reaches the snapshot only through
    :class:`~tos.capsule.SnapshotRef`, whose entire surface is ``snapshot_id`` +
    ``canonical_digest``.
    """
    resolver = ProvisionalContextResolver()
    assert isinstance(resolver, DecisionContextResolver)

    payload = resolver(issue_capsule(), instrument_key=instrument_key())
    assert isinstance(payload, DecisionTickPayload)
    assert resolved_value_surface_absent(payload) is True
    assert payload.capsule.critical_input_snapshot.canonical_digest == "sd-bt"
    assert payload.time == TimeAdmissionInputs()
    assert resolver.authority_label == "NON_AUTHORITATIVE_PROVISIONAL"


def test_the_resolver_slot_is_really_injected_not_hardcoded() -> None:
    """(§3.5/§7.4 (a)) A different resolver is used verbatim — the D-E2 forward seam is a slot."""
    calls: list[str] = []

    def _recording_resolver(capsule, *, instrument_key):  # noqa: ANN001, ANN202
        calls.append(capsule.capsule_id or "")
        return DecisionTickPayload(instrument_key=instrument_key, capsule=capsule)

    converter = build_converter(resolver=_recording_resolver)
    list(converter.stream(reference_bars(3)))
    assert len(calls) == 3, "the injected resolver must be the one the converter calls"


def test_a_missing_capsule_is_a_stop_never_an_implied_empty_context() -> None:
    """(RFC-003 §7:201-204) A missing Decision Context forbids a decision — fail-closed."""
    converter = build_converter()
    converter._capsule_source = lambda _bar: None  # noqa: SLF001 - the absent-context injection
    with pytest.raises(BacktestIntegrityError, match="no Decision Context"):
        list(converter.stream(reference_bars(1)))


def test_time_coordinates_are_bar_derived_and_positively_admit() -> None:
    """(§3.3) Every coordinate is a function of the bar's own coordinate plus injected bounds."""
    projection = time_projection()
    bars = reference_bars(3)
    for bar in bars:
        inputs = projection.project(bar)
        assert inputs.uncertainty_interval is not None
        assert inputs.uncertainty_interval.lo == bar.timestamp_coordinate
        assert inputs.uncertainty_interval.hi == bar.timestamp_coordinate + 2
        assert inputs.session_context is not None
        assert inputs.session_context.boundary_value == bar.timestamp_coordinate - 10
        admitted, reason = time_admits(inputs)
        assert admitted is True, reason


def test_the_projection_advances_with_the_bar() -> None:
    """(§3.3) Different bars produce different time frames — the projection is not a constant."""
    projection = time_projection()
    first, second = reference_bars(2)
    assert projection.project(first) != projection.project(second)


def test_an_ill_formed_injected_bound_is_refused() -> None:
    """(§3.3/§10) A negative bound is not a bound, and a zero boundary lag straddles the window."""
    with pytest.raises(INTEGRITY_ERRORS, match="must be non-negative"):
        time_projection(max_age_bound=-1)
    with pytest.raises(INTEGRITY_ERRORS, match="boundary_lag"):
        time_projection(boundary_lag=0)


def test_a_denying_time_frame_withholds_the_decision() -> None:
    """(§3.3) The injected time surface really gates: an untrusted clock denies (fail-closed)."""
    from tos.time import HealthState

    inputs = time_projection(health_state=HealthState.UNTRUSTED).project(
        reference_bars(1)[0]
    )
    admitted, reason = time_admits(inputs)
    assert admitted is False
    assert reason is not None and "TRUSTED" in reason
