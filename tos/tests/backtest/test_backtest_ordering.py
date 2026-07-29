"""§8-1 — the driver-owned monotone yield-order counter (design #33 §3.4, MAJOR-1).

The design's v1.1 revision replaced a ``bar_index``-coupled coordinate scheme with a **driver-owned
global yield-order counter**, and the reason is a property of the shipped engine, not a preference:

* the core holds **one** global ``_last_reference`` (``core.py:246``);
* it compares every incoming event against it (``core.py:280``) — against the *last admitted event*,
  never against the triggering tick;
* it updates it for **every** non-``REVERSED`` event (``core.py:301``), and line 301 runs *before*
  the handler, so even a tick that immediately halts at the capacity stage advances the gate.

Under a ``2i / 2i+1`` scheme a next-bar settlement is processed as ``tick_0(0), tick_1(2),
egress_0(1)``, and ``compare_order(1, 2)`` is ``BEFORE`` — the re-injected fill is refused as a
**false ``REVERSED``** and the run silently loses its settlement. This module proves both halves:
the rejected scheme really does produce that false halt, and the shipped driver really does not.

Regime tag: orchestration authoring evidence only; closes no EV (design #33 §1.1).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.backtest import (
    BacktestIntegrityError,
    FillMode,
    FillParameters,
    FillSide,
    SettlementPolicy,
    YieldOrderCounter,
    reference_bars,
)
from tos.engine import (
    EgressResultKind,
    EgressResultPayload,
    EngineEvent,
    EventKind,
    HaltReason,
    OrderingAdmission,
    ordering_admission,
)
from tos.ordering import Ordering, OrderingEvent, compare_order

from ._backtest_fixtures import (
    INTEGRITY_ERRORS,
    build_core,
    build_driver,
    build_fill_model,
    instrument_key,
)


def _next_bar_parameters() -> FillParameters:
    """An acknowledging band that settles on the **next** bar (the MAJOR-1 sequence)."""
    return FillParameters(
        mode=FillMode.ACKNOWLEDGE,
        side=FillSide.BUY,
        settlement=SettlementPolicy.NEXT_BAR,
    )


# ---------------------------------------------------------------------------
# the counter itself
# ---------------------------------------------------------------------------


def test_the_counter_is_strictly_increasing_on_one_continuity() -> None:
    """(§3.4) Coordinates are strictly increasing and share one continuity — so they compare."""
    counter = YieldOrderCounter(continuity_id="c-0")
    references = [counter.next_reference() for _ in range(5)]
    sequences = [reference.source_native_sequence for reference in references]
    assert sequences == [1, 2, 3, 4, 5]
    assert {reference.source_continuity_id for reference in references} == {"c-0"}
    assert counter.issued == 5
    for earlier, later in zip(references, references[1:]):
        assert compare_order(later, earlier) is Ordering.AFTER


def test_the_counter_offers_no_way_back() -> None:
    """(§3.4) There is no reset / rewind / set method — a counter that goes back is the defect."""
    counter = YieldOrderCounter(continuity_id="c-0")
    for forbidden in ("reset", "rewind", "set_sequence", "seek", "decrement"):
        assert not hasattr(counter, forbidden), (
            f"YieldOrderCounter exposes {forbidden!r} — the invariant 'coordinate order ≡ "
            "processing order' only holds if the counter cannot move backwards (design #33 §3.4)"
        )


def test_the_counter_uses_no_wall_clock_interval_for_ordering() -> None:
    """(§3.4 정직) ``time_lo`` / ``time_hi`` stay unset — trustworthy-time does not order here."""
    reference = YieldOrderCounter(continuity_id="c-0").next_reference()
    assert reference.time_lo is None
    assert reference.time_hi is None
    assert reference.quorum_commit_index is None
    assert reference.egress_journal_sequence is None


def test_an_unnamed_continuity_is_refused() -> None:
    """(§3.4) Source-native sequences only compare inside a named continuity."""
    with pytest.raises(BacktestIntegrityError, match="continuity_id must be concrete"):
        YieldOrderCounter(continuity_id="  ")


# ---------------------------------------------------------------------------
# the rejected bar-coupled scheme — why the counter exists
# ---------------------------------------------------------------------------


def test_the_rejected_bar_coupled_scheme_produces_a_false_reversed_halt() -> None:
    """(§3.4 MAJOR-1) ``2i / 2i+1`` really does break next-bar settlement — measured, not argued.

    The processing order is ``tick_0, tick_1, egress_0``; under the rejected scheme their
    coordinates are ``0, 2, 1``. The engine's gate compares the re-injected result against the last
    *admitted* event (``tick_1``, coordinate 2), so ``compare_order(1, 2) is BEFORE`` and the result
    is refused as ``EVENT_ORDER_REVERSED`` — the settlement silently disappears.
    """

    def _bar_coupled(bar_index: int, *, is_egress: bool) -> OrderingEvent:
        sequence = 2 * bar_index + (1 if is_egress else 0)
        return OrderingEvent(
            event_id=f"bar-coupled-{sequence}",
            source_continuity_id="bar-coupled",
            source_native_sequence=sequence,
        )

    tick_0 = _bar_coupled(0, is_egress=False)
    tick_1 = _bar_coupled(1, is_egress=False)
    egress_0 = _bar_coupled(0, is_egress=True)

    assert ordering_admission(None, tick_0) is OrderingAdmission.MONOTONE
    assert ordering_admission(tick_0, tick_1) is OrderingAdmission.MONOTONE
    assert ordering_admission(tick_1, egress_0) is OrderingAdmission.REVERSED, (
        "the rejected bar-coupled scheme must produce the false REVERSED the design removed"
    )

    # ... and the core really halts on it, refusing the settlement outright.
    fill_model = build_fill_model(_next_bar_parameters())
    fill_model.bind_settlement_context(reference_bars(1)[0])
    core, _ = build_core(transmit=fill_model)
    first = core.handle(
        EngineEvent(
            kind=EventKind.DECISION_TICK,
            decision_tick=_tick_payload(reference=tick_0),
        )
    )
    assert first.flow is not None and first.flow.attempt is not None
    core.handle(
        EngineEvent(
            kind=EventKind.DECISION_TICK, decision_tick=_tick_payload(reference=tick_1)
        )
    )
    refused = core.handle(
        EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=instrument_key(),
                attempt_id=first.flow.attempt.attempt_id,
                kind=EgressResultKind.ACK,
                reference=egress_0,
            ),
        )
    )
    assert refused.halt_reason is HaltReason.EVENT_ORDER_REVERSED
    assert refused.ordering is OrderingAdmission.REVERSED


def _tick_payload(*, reference: OrderingEvent):  # noqa: ANN202 - a local builder
    """A ``DECISION_TICK`` payload carrying an explicitly supplied coordinate."""
    from tos.backtest import ProvisionalContextResolver

    from ._backtest_fixtures import issue_capsule, time_projection

    payload = ProvisionalContextResolver()(
        issue_capsule(), instrument_key=instrument_key()
    )
    return payload.model_copy(
        update={
            "time": time_projection().project(reference_bars(1)[0]),
            "reference": reference,
        }
    )


# ---------------------------------------------------------------------------
# the shipped driver
# ---------------------------------------------------------------------------


def test_next_bar_settlement_is_monotone_end_to_end() -> None:
    """(§8-1) The mandated next-bar sequence ``tick_0, tick_1, egress_0`` admits MONOTONE throughout.

    This is the property the whole MAJOR-1 revision exists for. A mutation that couples the
    coordinate to ``bar_index`` turns the third entry into a ``REVERSED`` halt and fails here.
    """
    fill_model = build_fill_model(_next_bar_parameters())
    driver = build_driver(fill_model)
    core, _ = build_core(transmit=fill_model)
    run = driver.run(core, reference_bars(2))

    kinds = [entry.event_kind for entry in run.trace.entries]
    assert kinds == [
        EventKind.DECISION_TICK,
        EventKind.DECISION_TICK,
        EventKind.EGRESS_RESULT,
    ], "the interleaving must be tick_0, tick_1, egress_0 for a next-bar settlement"

    admissions = [entry.ordering_admission for entry in run.trace.entries]
    assert admissions == [OrderingAdmission.MONOTONE] * 3
    assert all(entry.halt_reason is not HaltReason.EVENT_ORDER_REVERSED for entry in run.trace.entries)

    sequences = [entry.reference.source_native_sequence for entry in run.trace.entries]
    assert sequences == [1, 2, 3]


def test_the_coordinate_is_decoupled_from_the_bar_index() -> None:
    """(§3.4) The coordinate follows *yield order*; the bar index is recorded separately.

    On a next-bar settlement the third event's coordinate (3) belongs to the settlement bar (1),
    while the second event's coordinate (2) also belongs to bar 1 — two events, one bar, distinct
    coordinates. That is the decoupling in one observation.
    """
    fill_model = build_fill_model(_next_bar_parameters())
    driver = build_driver(fill_model)
    core, _ = build_core(transmit=fill_model)
    run = driver.run(core, reference_bars(2))

    pairs = [
        (entry.reference.source_native_sequence, entry.bar_index)
        for entry in run.trace.entries
    ]
    assert pairs == [(1, 0), (2, 1), (3, 1)]


def test_same_bar_settlement_is_monotone_too() -> None:
    """(§8-1) The same counter serves same-bar settlement — no branch, no special case."""
    parameters = FillParameters(
        mode=FillMode.ACKNOWLEDGE, side=FillSide.BUY, settlement=SettlementPolicy.SAME_BAR
    )
    fill_model = build_fill_model(parameters)
    driver = build_driver(fill_model)
    core, _ = build_core(transmit=fill_model)
    run = driver.run(core, reference_bars(2))

    kinds = [entry.event_kind for entry in run.trace.entries]
    assert kinds == [
        EventKind.DECISION_TICK,
        EventKind.EGRESS_RESULT,
        EventKind.DECISION_TICK,
    ]
    assert [entry.ordering_admission for entry in run.trace.entries] == (
        [OrderingAdmission.MONOTONE] * 3
    )
    assert [entry.reference.source_native_sequence for entry in run.trace.entries] == [1, 2, 3]


def test_the_trace_order_is_the_processing_order() -> None:
    """(§3.4 invariant) Trace entries strictly increase in yield sequence, and match the coordinate."""
    fill_model = build_fill_model(_next_bar_parameters())
    driver = build_driver(fill_model)
    core, _ = build_core(transmit=fill_model)
    run = driver.run(core, reference_bars(3))

    yields = [entry.yield_sequence for entry in run.trace.entries]
    assert yields == sorted(set(yields))
    for entry in run.trace.entries:
        assert entry.reference.source_native_sequence == entry.yield_sequence, (
            "the recorded yield coordinate and the event's ordering coordinate are the same "
            "number — coordinate order ≡ processing order (design #33 §3.4)"
        )


def test_a_trace_out_of_order_is_unconstructable() -> None:
    """(§6.1) The trace model itself refuses a non-increasing order — the seal is structural."""
    from tos.backtest import TraceEntry, WiringTrace

    def _entry(sequence: int) -> TraceEntry:
        return TraceEntry(
            yield_sequence=sequence,
            event_kind=EventKind.DECISION_TICK,
            instrument_key=instrument_key(),
            ordering_admission=OrderingAdmission.MONOTONE,
            reference=OrderingEvent(source_native_sequence=sequence),
        )

    with pytest.raises(INTEGRITY_ERRORS, match="strictly increase"):
        WiringTrace(continuity_id="c-0", entries=(_entry(2), _entry(1)))


def test_a_trace_with_an_equal_coordinate_is_unconstructable() -> None:
    """(§3.4/§6.1) Two entries sharing one coordinate are refused — **equality**, not just decrease.

    Adversarial review MINOR-1: the strict-decrease case above ``(2, 1)`` leaves the boundary in
    ``records.py:241`` (``entry.yield_sequence <= previous``) untested, so weakening it to ``<``
    survived the whole suite. Equality is not a hypothetical shape — it is the exact signature of a
    **duplicated yield-order coordinate**, i.e. the counter handing the same ``source_native_sequence``
    to two events. That defect is precisely what the strict ``<=`` boundary exists to catch, because
    :func:`~tos.ordering.compare_order` returns ``AMBIGUOUS`` for equal coordinates rather than an
    order, and the core *admits* an ambiguous pair (``core.py:174-181``) — so the engine would not
    refuse it and ``WiringTrace`` is the independent backstop.
    """
    from tos.backtest import TraceEntry, WiringTrace

    def _entry(sequence: int) -> TraceEntry:
        return TraceEntry(
            yield_sequence=sequence,
            event_kind=EventKind.DECISION_TICK,
            instrument_key=instrument_key(),
            ordering_admission=OrderingAdmission.MONOTONE,
            reference=OrderingEvent(source_native_sequence=sequence),
        )

    with pytest.raises(INTEGRITY_ERRORS, match="strictly increase"):
        WiringTrace(continuity_id="c-0", entries=(_entry(2), _entry(2)))


def test_every_run_of_the_counter_advances_across_repeated_runs() -> None:
    """(§3.4) A second run on the same driver continues the counter — it never restarts.

    Restarting would let a later event carry an earlier coordinate, which is the same false-REVERSED
    failure by another route.
    """
    fill_model = build_fill_model(_next_bar_parameters())
    driver = build_driver(fill_model)
    core, _ = build_core(transmit=fill_model)
    first = driver.run(core, reference_bars(1))
    second = driver.run(core, reference_bars(1))

    first_sequences = [entry.yield_sequence for entry in first.trace.entries]
    second_sequences = [entry.yield_sequence for entry in second.trace.entries]
    assert first_sequences and second_sequences
    assert min(second_sequences) > max(first_sequences)


def test_ordering_of_a_partial_fill_run_is_monotone() -> None:
    """(§8-1) A magnitude-carrying settlement orders exactly like a magnitude-free one."""
    parameters = FillParameters(
        mode=FillMode.SETTLE,
        side=FillSide.BUY,
        settlement=SettlementPolicy.NEXT_BAR,
        scenario_quantity=Decimal(800),
        participation_cap_fraction=Decimal("0.5"),
        slippage_bps=Decimal(5),
        cost_per_unit=Decimal("0.02"),
        limit_reference_price=Decimal(100),
        price_band_fraction=Decimal("0.05"),
    )
    fill_model = build_fill_model(parameters)
    driver = build_driver(fill_model)
    core, _ = build_core(transmit=fill_model)
    run = driver.run(core, reference_bars(2))

    assert [entry.ordering_admission for entry in run.trace.entries] == (
        [OrderingAdmission.MONOTONE] * 3
    )
    assert run.fill_records[0].result_kind is EgressResultKind.PARTIAL_FILL
