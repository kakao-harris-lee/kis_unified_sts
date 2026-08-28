"""§5 — the multi-symbol (N-lane) extension (design #37).

Multi-symbol is **N per-instrument lanes on one continuity**, and the whole contract turns on that
choice rather than on new machinery. The engine core is not modified at all: its single global
``_last_reference`` (``core.py:246``/``:280``/``:301``) is exactly right when every event in the run
shares a continuity, because ``compare_order`` then resolves *every* adjacent pair — cross-lane
pairs included — by ``source_native_sequence``.

The rejected alternative is measured here rather than argued (T1). Per-symbol continuities make each
cross-lane adjacent pair ``same_continuity=False`` (``_ordering.py:112-126``), so the pair falls
through to ``AMBIGUOUS`` and the core *admits* it while overwriting the global slot — ordering
detection switched off precisely at the boundary multi-symbol introduces. A symbol's regression can
then hide behind another symbol's coordinate. The adopted model has strictly more detection, and
"every admission is MONOTONE" is that superiority observable **without** constructing a regression
at all (T2).

The one genuinely new wiring problem is the ``Transmit`` slot. The core has exactly one
(``core.py:216``/``:243``) and the ``AttemptRequest`` crossing it carries no instrument and no scope
(``records.py:347-351``), so no lane can be recovered *from the attempt*. The driver occupies the
slot and demultiplexes onto the lane it is **currently processing**, which is sound only because the
core processes one event to completion before pulling the next (``core.py:1-3``). T10 is the
executable form of that: every fill carries its own lane's key, and collapsing the lanes onto one
shared fill band is caught rather than shipped.

Regime tag: orchestration authoring evidence only; closes no EV (design #33 §1.1 / #37 §5).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from tos.backtest import (
    BacktestIntegrityError,
    Bar,
    FillMode,
    FillParameters,
    FillSide,
    MultiSymbolBacktestDriver,
    SettlementPolicy,
    merge_bar_streams,
    multi_symbol_trace_document,
    validate_bar_stream_mapping,
)
from tos.engine import (
    EngineEvent,
    EventKind,
    HaltReason,
    OrderingAdmission,
    ordering_admission,
)
from tos.ordering import OrderingEvent

from ._backtest_fixtures import (
    INSTRUMENT,
    INSTRUMENT_B,
    INTEGRITY_ERRORS,
    build_converter,
    build_core,
    build_fill_model,
    build_multi_symbol_driver,
    capsule_source_for,
    instrument_key,
    lane_strategy,
    offset_bars,
    registry_with_all,
    vector_policy,
)

KEY_A = instrument_key(instrument=INSTRUMENT)
KEY_B = instrument_key(instrument=INSTRUMENT_B)


def _ack(settlement: SettlementPolicy = SettlementPolicy.SAME_BAR) -> FillParameters:
    """A magnitude-free acknowledging band on the given settlement policy."""
    return FillParameters(
        mode=FillMode.ACKNOWLEDGE, side=FillSide.BUY, settlement=settlement
    )


def _settle(settlement: SettlementPolicy = SettlementPolicy.SAME_BAR) -> FillParameters:
    """A magnitude-carrying band, so a lane's fill record holds a price of its own."""
    return FillParameters(
        mode=FillMode.SETTLE,
        side=FillSide.BUY,
        settlement=settlement,
        scenario_quantity=Decimal(10),
        participation_cap_fraction=Decimal("0.5"),
        slippage_bps=Decimal(5),
        cost_per_unit=Decimal("0.02"),
        limit_reference_price=Decimal(100),
        price_band_fraction=Decimal("0.05"),
    )


def _interleaved_run(*, bar_count: int = 2, settle: bool = False):  # noqa: ANN202 - local runner
    """Two lanes whose **settlements interleave** — the shape T5 / T10 need.

    Lane ``ES`` settles on the *next* bar, lane ``NQ`` on the *same* bar, and ``NQ``'s coordinates
    sit between ``ES``'s. So ``NQ``'s settlement lands **between** ``ES``'s hand-off and ``ES``'s
    settlement, and the global settlement order (``NQ``, then ``ES``) is the reverse of the lane
    declaration order (``ES``, then ``NQ``). Without that reversal a lane-concatenated
    ``fill_records`` would be indistinguishable from the contracted one and the mutation would
    survive (design #37 §3.3 / §5-T5).
    """
    parameters = _settle if settle else _ack
    driver, _converters, fill_models = build_multi_symbol_driver(
        [
            (INSTRUMENT, parameters(SettlementPolicy.NEXT_BAR)),
            (INSTRUMENT_B, parameters(SettlementPolicy.SAME_BAR)),
        ]
    )
    core, sink = build_core(
        registry=registry_with_all(lane_strategy(INSTRUMENT), lane_strategy(INSTRUMENT_B)),
        transmit=driver,
    )
    run = driver.run(
        core,
        {
            KEY_A: offset_bars(bar_count, coordinate_offset=0),
            KEY_B: offset_bars(bar_count, coordinate_offset=30),
        },
    )
    return run, driver, core, fill_models, sink


def _sequential_run():  # noqa: ANN202 - a local runner
    """Two lanes that do **not** overlap in time: every ``ES`` bar precedes every ``NQ`` bar.

    This is the halt-isolation shape: ``ES`` has already halted at its capacity seal before ``NQ``
    is ever ticked, so ``NQ``'s hand-off succeeding is unambiguous evidence that one lane's halt
    does not kill the next (design #37 §3.5 / §5-T4).
    """
    driver, _converters, fill_models = build_multi_symbol_driver(
        [(INSTRUMENT, _ack()), (INSTRUMENT_B, _ack())]
    )
    core, sink = build_core(
        registry=registry_with_all(lane_strategy(INSTRUMENT), lane_strategy(INSTRUMENT_B)),
        transmit=driver,
    )
    run = driver.run(
        core,
        {
            KEY_A: offset_bars(2, coordinate_offset=0),
            KEY_B: offset_bars(2, coordinate_offset=1000),
        },
    )
    return run, driver, core, fill_models, sink


# ---------------------------------------------------------------------------
# T1 — the stream-model contrast, measured on the shipped vocabulary
# ---------------------------------------------------------------------------


def _coordinate(continuity: str, sequence: int) -> OrderingEvent:
    """One ordering coordinate on a named continuity."""
    return OrderingEvent(
        event_id=f"{continuity}-{sequence}",
        source_continuity_id=continuity,
        source_native_sequence=sequence,
    )


def test_one_continuity_still_catches_a_symbols_own_regression() -> None:
    """(§1.1/§1.2) A ⊃ B, half one: on a single continuity the regression is ``REVERSED``.

    ``A@5 → B@6 → A@3``. Because all three share a continuity, ``compare_order`` reaches the
    ``source_native_sequence`` branch for every pair, so ``3`` after ``6`` is positively refused.
    """
    a_first = _coordinate("shared", 5)
    b_second = _coordinate("shared", 6)
    a_regressed = _coordinate("shared", 3)

    assert ordering_admission(None, a_first) is OrderingAdmission.MONOTONE
    assert ordering_admission(a_first, b_second) is OrderingAdmission.MONOTONE
    assert ordering_admission(b_second, a_regressed) is OrderingAdmission.REVERSED


def test_per_symbol_continuities_hide_the_same_regression_as_ambiguous() -> None:
    """(§1.1) A ⊃ B, half two: per-symbol continuities turn the *same* sequence fail-open.

    The core holds **one** global slot, so symbol B's coordinate overwrites symbol A's
    (``core.py:280``/``:301``). With per-symbol continuities the comparison that would catch A's
    regression is never made — ``same_continuity`` is ``False`` (``_ordering.py:112-126``) — and the
    pair degrades to ``AMBIGUOUS``, which the core *admits* (M6). That is the fail-open the adopted
    model does not introduce in the first place, rather than one it defends against.
    """
    a_first = _coordinate("continuity-a", 5)
    b_second = _coordinate("continuity-b", 6)
    a_regressed = _coordinate("continuity-a", 3)

    assert ordering_admission(a_first, b_second) is OrderingAdmission.AMBIGUOUS
    assert ordering_admission(b_second, a_regressed) is OrderingAdmission.AMBIGUOUS, (
        "a per-symbol-continuity model would let symbol A go backwards behind symbol B's "
        "coordinate — the detection gap design #37 §1.1 measures"
    )


# ---------------------------------------------------------------------------
# T2 — the mutation targets on the driver surface
# ---------------------------------------------------------------------------


def test_every_cross_lane_admission_is_monotone() -> None:
    """(§5-T2 mutant A) One continuity ⇒ **every** adjacent pair is orderable, cross-lane included.

    The killing observation for "assign each lane its own continuity": that mutation leaves the run
    working and the trace well-formed, but every cross-lane adjacent pair degrades to ``AMBIGUOUS``.
    No regression has to be constructed for the difference to show — which is what makes the
    detection-superiority claim non-vacuous (design #37 §1.2).
    """
    run, _driver, _core, _models, _sink = _interleaved_run()

    lanes = [entry.instrument_key.instrument for entry in run.trace.entries]
    assert len(set(lanes)) == 2, "the fixture must really interleave two lanes"
    assert any(
        first != second for first, second in zip(lanes, lanes[1:])
    ), "at least one adjacent pair must be cross-lane, or the observation is vacuous"

    assert [entry.ordering_admission for entry in run.trace.entries] == (
        [OrderingAdmission.MONOTONE] * len(run.trace.entries)
    )
    assert {entry.reference.source_continuity_id for entry in run.trace.entries} == {
        run.trace.continuity_id
    }


# ---------------------------------------------------------------------------
# T3 / T4 — per-scope independence, N-entry dispatch, halt isolation
# ---------------------------------------------------------------------------


def test_a_saturated_lane_does_not_deny_its_neighbour() -> None:
    """(§5-T3) The at-most-one seal is **per scope**: ``ES`` holding one does not block ``NQ``.

    A ledger keyed globally instead of per scope (``state.py:137``) would deny the second lane's
    first hand-off outright, which is the mutation this pins.
    """
    run, _driver, core, fill_models, _sink = _interleaved_run()

    assert len(fill_models[KEY_A].handoffs) == 1
    assert len(fill_models[KEY_B].handoffs) == 1
    assert run.handoff_count == 2

    first_ticks = [
        entry
        for entry in run.trace.entries
        if entry.event_kind is EventKind.DECISION_TICK and entry.bar_index == 0
    ]
    assert [entry.halt_reason for entry in first_ticks] == [None, None], (
        "both lanes' opening ticks must be admitted — the reservation projection is keyed by "
        "scope, and one scope's occupancy is not the other's"
    )
    assert core.ledger.admits_new_exposure(KEY_A) is False
    assert core.ledger.admits_new_exposure(KEY_B) is False


def test_a_tick_evaluates_only_its_own_lanes_strategy() -> None:
    """(§5-T4 / M4 EXTEND) N registry entries, and each tick reaches exactly one of them.

    A dispatch that ran every entry regardless of key would run ``NQ``'s strategy on an ``ES`` tick
    and halt with ``EVENT_STRATEGY_KEY_MISMATCH`` (``pipeline.py:254-260``) — recorded here as an
    absence *and* as the positive fact that each result carries its own lane's key.
    """
    run, _driver, _core, _models, _sink = _sequential_run()

    for entry, result in zip(run.trace.entries, run.event_results):
        assert result.instrument_key == entry.instrument_key
    assert all(
        entry.halt_reason is not HaltReason.EVENT_STRATEGY_KEY_MISMATCH
        for entry in run.trace.entries
    )
    handed_off = [entry.instrument_key.instrument for entry in run.trace.entries if entry.handed_off]
    assert handed_off == [INSTRUMENT, INSTRUMENT_B], (
        "each lane hands off exactly once, under its own key"
    )


def test_one_lanes_halt_does_not_kill_the_following_lane() -> None:
    """(§3.5) ``ES`` halts at its capacity seal, and ``NQ`` is still replayed normally afterwards.

    The core produces an ``EventResult`` per event and never stops the stream (``core.py:253-262``),
    so a halt is *this event's* outcome, not the run's. With the sequential fixture every ``ES`` bar
    precedes every ``NQ`` bar, so ``NQ``'s hand-off happens strictly after ``ES``'s halt.
    """
    run, _driver, _core, fill_models, _sink = _sequential_run()

    es_halts = [halt for halt in run.halts if halt.instrument_key == KEY_A]
    assert [halt.halt_reason for halt in es_halts] == [
        HaltReason.AT_MOST_ONE_EXPOSURE_HELD
    ]
    nq_handoff = next(
        entry
        for entry in run.trace.entries
        if entry.handed_off and entry.instrument_key == KEY_B
    )
    assert nq_handoff.yield_sequence > es_halts[0].yield_sequence
    assert len(fill_models[KEY_B].handoffs) == 1


# ---------------------------------------------------------------------------
# T5 — one total order, byte-identical replay, and the fill-record order
# ---------------------------------------------------------------------------


def test_the_multi_symbol_trace_is_one_total_order() -> None:
    """(§5-T5 / M10 EXTEND, mutant B) One counter ⇒ ``native == yield``, unique and ascending.

    The killing observation for "give each lane its own native counter": the identity breaks the
    moment two lanes issue the same sequence number.
    """
    run, _driver, _core, _models, _sink = _interleaved_run()

    yields = [entry.yield_sequence for entry in run.trace.entries]
    assert yields == sorted(yields)
    assert len(set(yields)) == len(yields), "the coordinate is globally unique across lanes"
    for entry in run.trace.entries:
        assert entry.reference.source_native_sequence == entry.yield_sequence


def test_fill_records_follow_the_global_settlement_order() -> None:
    """(§5-T5 MAJOR-N2) ``fill_records`` order == its settlements' ``yield_sequence`` order.

    The discriminating assertion. Reproducing a run twice cannot catch a lane-grouped
    ``fill_records`` — both runs group it identically — so the order is joined against an
    independent witness instead: each settled record's ``attempt_id`` is matched to the
    ``EGRESS_RESULT`` trace entry that carries it, and those coordinates must ascend.

    Scope of the join is stated as narrowly as it is true: only **settled** fills have an
    ``EGRESS_RESULT`` entry at all. ``unsettled_fill_records`` carry no result kind
    (``records.py:126``) and are ordered by a separately declared rule.
    """
    run, _driver, _core, _models, _sink = _interleaved_run()

    settled_entries = [
        entry for entry in run.trace.entries if entry.egress_result_kind is not None
    ]
    coordinates = {entry.attempt_id: entry.yield_sequence for entry in settled_entries}
    assert len(coordinates) == len(settled_entries) >= 2, (
        "the join needs at least two distinctly-identified settlements, from different lanes"
    )
    assert run.unsettled_fill_records == ()

    observed = [coordinates[record.attempt_id] for record in run.fill_records]
    assert observed == sorted(observed), (
        f"fill_records order {observed} is not the global settlement order — concatenating each "
        "lane's own records at the end of the run loses it, and LocalFillRecord has no global "
        "order field to rebuild it from (design #37 §3.3)"
    )

    lanes_in_settlement_order = [
        record.instrument_key.instrument for record in run.fill_records
    ]
    assert lanes_in_settlement_order == [INSTRUMENT_B, INSTRUMENT], (
        "the fixture's settlement order must differ from the lane declaration order, or a "
        "lane-concatenated implementation would pass this test by coincidence"
    )


def test_the_oracle_identity_does_not_depend_on_lane_declaration_order() -> None:
    """(§1.6) Two behaviourally identical runs must share one oracle identity.

    Lane declaration order is the caller's wiring choice, not a property of the replay: the merge
    is a total order on ``(timestamp_coordinate, account, instrument)``, so declaring the same two
    lanes the other way round produces the same events, the same trace and the same fills. If the
    artifact emitted ``instrument_keys`` in declaration order, that caller choice would leak into
    the digest and split one run's identity in two — so it is emitted in key order, and this pins
    it.

    The run object itself deliberately keeps declaration order; that is asserted here too, so the
    fix cannot be "sort everywhere" (which would erase how the run was wired).
    """
    def _run(order: tuple[str, str]):  # noqa: ANN202 - a local runner
        driver, _converters, _models = build_multi_symbol_driver(
            [(order[0], _ack()), (order[1], _ack())]
        )
        core, _sink = build_core(
            registry=registry_with_all(lane_strategy(INSTRUMENT), lane_strategy(INSTRUMENT_B)),
            transmit=driver,
        )
        return driver.run(
            core,
            {
                KEY_A: offset_bars(2, coordinate_offset=0),
                KEY_B: offset_bars(2, coordinate_offset=30),
            },
        )

    declared_forwards = _run((INSTRUMENT, INSTRUMENT_B))
    declared_backwards = _run((INSTRUMENT_B, INSTRUMENT))

    assert declared_forwards.instrument_keys == (KEY_A, KEY_B)
    assert declared_backwards.instrument_keys == (KEY_B, KEY_A), (
        "the run records how it was wired — declaration order is not sorted away"
    )
    assert multi_symbol_trace_document(declared_forwards) == multi_symbol_trace_document(
        declared_backwards
    ), (
        "two runs identical in behaviour produced different oracle artifacts — a caller's lane "
        "declaration order leaked into the hashed document (design #37 §1.6)"
    )
    assert [
        (record.instrument_key, record.attempt_id) for record in declared_forwards.fill_records
    ] == [
        (record.instrument_key, record.attempt_id) for record in declared_backwards.fill_records
    ]


def test_the_unsettled_records_are_ordered_by_lane_key() -> None:
    """(§3.5) The unsettled tail has no settlement to be ordered by, so its order is declared.

    Lanes in ``(account, instrument)`` order, each lane's pending fills in staging order. Both lanes
    settle on the *next* bar and each stream ends on the bar that hands off, so nothing settles.
    """
    driver, _converters, _models = build_multi_symbol_driver(
        [
            (INSTRUMENT_B, _ack(SettlementPolicy.NEXT_BAR)),
            (INSTRUMENT, _ack(SettlementPolicy.NEXT_BAR)),
        ]
    )
    core, _sink = build_core(
        registry=registry_with_all(lane_strategy(INSTRUMENT), lane_strategy(INSTRUMENT_B)),
        transmit=driver,
    )
    run = driver.run(
        core,
        {
            KEY_B: offset_bars(1, coordinate_offset=30),
            KEY_A: offset_bars(1, coordinate_offset=0),
        },
    )

    assert run.fill_records == ()
    assert [
        record.instrument_key.instrument for record in run.unsettled_fill_records
    ] == [INSTRUMENT, INSTRUMENT_B], (
        "declared lane order here is (NQ, ES); the unsettled tail is ordered by key, not by how "
        "the caller happened to build the mapping"
    )


def test_the_oracle_artifact_names_every_lane_and_keeps_its_narrow_scope() -> None:
    """(§3.5) The N-lane artifact is the single-symbol one with ``instrument_keys``, nothing more."""
    run, _driver, _core, _models, _sink = _interleaved_run(settle=True)
    document = multi_symbol_trace_document(run)

    assert set(document) == {
        "artifact_type",
        "label",
        "closes_no_ev",
        "oracle_scope",
        "numeric_decision_agreement",
        "instrument_keys",
        "scenario_id",
        "bars_consumed",
        "events_yielded",
        "trace",
        "halts",
    }
    assert document["artifact_type"] == "tos.backtest.multi_symbol_wiring_trace"
    assert document["oracle_scope"] == "STRUCTURAL_WIRING_AGREEMENT_ONLY"
    assert document["numeric_decision_agreement"] == "DEFERRED_PENDING_D_E2_VALUE_SURFACE"
    assert document["instrument_keys"] == [
        {"account": key.account, "instrument": key.instrument}
        for key in sorted(
            run.instrument_keys, key=lambda item: (item.account, item.instrument)
        )
    ]
    assert run.fill_records[0].execution_price is not None, "the run really did price a fill"
    serialized = repr(document)
    for forbidden in ("execution_price", "filled_quantity", "slippage", "cost_component"):
        assert forbidden not in serialized, (
            f"the N-lane oracle artifact leaked {forbidden!r} — its scope is the single-symbol "
            "artifact's, and widening it to N lanes widens nothing else (design #33 §6.2)"
        )


# ---------------------------------------------------------------------------
# T6 — the merge: determinism, tie-break, order preservation, no look-ahead
# ---------------------------------------------------------------------------


def test_two_symbols_sharing_a_coordinate_are_ordered_by_instrument_key() -> None:
    """(§3.3) The tie-break is ``(account, instrument)`` — never mapping insertion order.

    The lanes are declared ``NQ`` first on purpose: an implementation that fell back on insertion
    order would emit ``NQ`` first and fail here, while one that sorted by key emits ``ES`` first.
    """
    lanes = [
        (KEY_B, offset_bars(2, coordinate_offset=0)),
        (KEY_A, offset_bars(2, coordinate_offset=0)),
    ]
    merged = merge_bar_streams(lanes)

    assert [(key.instrument, bar.bar_index) for key, bar in merged] == [
        (INSTRUMENT, 0),
        (INSTRUMENT_B, 0),
        (INSTRUMENT, 1),
        (INSTRUMENT_B, 1),
    ]
    assert merge_bar_streams(list(reversed(lanes))) == merged, (
        "the merge is a pure function of the lanes' content — declaring them in the other order "
        "must not change the interleave (design #37 §1.6)"
    )


def test_the_merge_preserves_each_lanes_own_order() -> None:
    """(§3.3) The merge interleaves; it never reorders inside a stream."""
    merged = merge_bar_streams(
        [
            (KEY_A, offset_bars(3, coordinate_offset=0)),
            (KEY_B, offset_bars(3, coordinate_offset=30)),
        ]
    )
    for key in (KEY_A, KEY_B):
        lane = [bar.bar_index for merged_key, bar in merged if merged_key == key]
        assert lane == [0, 1, 2]
    assert [bar.timestamp_coordinate for _key, bar in merged] == sorted(
        bar.timestamp_coordinate for _key, bar in merged
    )


def test_a_repeated_lane_key_is_refused() -> None:
    """(§3.3) A repeated key makes the tie-break non-total, so it is refused rather than resolved."""
    with pytest.raises(BacktestIntegrityError, match="repeat an instrument key"):
        merge_bar_streams(
            [
                (KEY_A, offset_bars(1, coordinate_offset=0)),
                (KEY_A, offset_bars(1, coordinate_offset=30)),
            ]
        )


def test_the_non_decreasing_check_really_detects_a_reordered_stream() -> None:
    """(§3.3, both ways) The merged-order assertion is a detector, not decoration.

    Its input is the merge's own output, so a clean merge can never trip it — which would make
    "green" unfalsifiable. A deliberately reordered sequence is planted straight into the check
    instead, exactly the discipline the planted-escape canaries use.
    """
    from tos.backtest.bars import _assert_merged_non_decreasing

    ordered = merge_bar_streams([(KEY_A, offset_bars(3, coordinate_offset=0))])
    _assert_merged_non_decreasing(ordered)

    with pytest.raises(BacktestIntegrityError, match="not non-decreasing"):
        _assert_merged_non_decreasing(list(reversed(ordered)))


def test_each_lanes_converter_stays_prefix_bounded() -> None:
    """(§3.3) The frontier reads ordering metadata only; no lane's converter sees a future bar.

    The merge compares ``timestamp_coordinate`` and nothing else, and each lane's tick is still
    built from that lane's own current bar — so ADR-DEV-010 BTE-INV-004 holds unchanged. Observed
    structurally: a lane's converted tick carries exactly the bar the merge placed at that position.
    """
    lanes = [
        (KEY_A, offset_bars(2, coordinate_offset=0)),
        (KEY_B, offset_bars(2, coordinate_offset=30)),
    ]
    merged = merge_bar_streams(lanes)
    converters = {
        KEY_A: build_converter(key=KEY_A, source=capsule_source_for(INSTRUMENT)),
        KEY_B: build_converter(key=KEY_B, source=capsule_source_for(INSTRUMENT_B)),
    }
    streams = {key: iter(converters[key].stream(stream)) for key, stream in lanes}

    for key, bar in merged:
        tick = next(streams[key])
        assert tick.bar is bar, (
            "a lane's converter must produce the tick for the bar the merge placed here — nothing "
            "downstream may reorder a lane's own stream"
        )
        assert tick.payload.instrument_key == key


# ---------------------------------------------------------------------------
# T7 — VECTOR is a different axis and stays closed
# ---------------------------------------------------------------------------


def test_a_vector_outcome_is_still_refused_under_multi_symbol_wiring() -> None:
    """(§1.5 / M1 regression) N per-instrument lanes do **not** open ``PortfolioVector`` folding.

    Multi-symbol here is N scalar per-instrument decisions; a vector outcome is one strategy
    claiming N instruments at once, which is a separate, untouched axis (``pipeline.py:329-340``).
    """
    driver, _converters, _models = build_multi_symbol_driver(
        [(INSTRUMENT, _ack()), (INSTRUMENT_B, _ack())]
    )
    core, _sink = build_core(
        registry=registry_with_all(
            lane_strategy(INSTRUMENT, policy=vector_policy(INSTRUMENT)),
            lane_strategy(INSTRUMENT_B),
        ),
        transmit=driver,
    )
    run = driver.run(
        core,
        {
            KEY_A: offset_bars(1, coordinate_offset=0),
            KEY_B: offset_bars(1, coordinate_offset=30),
        },
    )

    vector_halts = [halt for halt in run.halts if halt.instrument_key == KEY_A]
    assert [halt.halt_reason for halt in vector_halts] == [
        HaltReason.VECTOR_OUTCOME_UNSUPPORTED
    ]
    assert run.handoff_count == 1, "the vector lane hands off nothing; the scalar lane still does"


# ---------------------------------------------------------------------------
# T10 — the single-Transmit-slot demux (the C1 seam)
# ---------------------------------------------------------------------------


def test_every_fill_is_stamped_with_its_own_lanes_key() -> None:
    """(§3.2 / §5-T10) Each ``LocalFillRecord`` carries the lane that produced it.

    The killing observation for "share one fill model across lanes": a shared band stamps every
    staged fill with its single ``instrument_key`` (``fills.py:372``/``:452``) and matches
    settlements by a lane-local ``bar_index`` (``fills.py:473-474``), so the contamination is
    silent. Both lanes must actually settle for this to bite, which the interleaved fixture ensures.
    """
    run, _driver, _core, fill_models, _sink = _interleaved_run(settle=True)

    assert {record.instrument_key for record in run.fill_records} == {KEY_A, KEY_B}
    for key, model in fill_models.items():
        for record in model.records:
            assert record.instrument_key == key
    for entry in run.trace.entries:
        if entry.egress_result_kind is not None:
            matching = [
                record
                for record in run.fill_records
                if record.attempt_id == entry.attempt_id
            ]
            assert [record.instrument_key for record in matching] == [entry.instrument_key], (
                "the re-injected result and the D-E3-local record must name the same lane — a "
                "shared fill band would give them one key between them"
            )


def test_a_hand_off_with_no_bound_lane_is_fail_closed() -> None:
    """(§3.2 MINOR-N4) Called outside a tick, the demux refuses rather than guessing a lane.

    Unreachable on the nominal path — the core completes each event before pulling the next — so it
    is exercised directly. The engine's own treatment of the raise is inherited, not re-invented:
    the sequencer records ``TRANSMIT_RAISED`` and leaves the reservation ``POTENTIALLY_LIVE``
    (``sequencer.py:534-545``), the same handling an unbound settlement context already gets.
    """
    driver, _converters, _models = build_multi_symbol_driver([(INSTRUMENT, _ack())])
    assert driver.current_instrument_key is None

    from tos.engine import AttemptRequest

    attempt = AttemptRequest(
        attempt_id="attempt-unbound",
        conformance_proof_digest="proof",
        action_flow_permit_identity="permit",
        reference_coordinate_digest="coord",
    )
    with pytest.raises(BacktestIntegrityError, match="no lane was bound"):
        driver(attempt)


def test_the_transmit_raise_becomes_a_recorded_halt() -> None:
    """(§3.2) The fail-closed demux really lands on the sequencer's ``TRANSMIT_RAISED`` path.

    A lane whose fill band never had a settlement context bound raises from inside the hand-off, and
    the engine records the stop with its reason rather than losing it — the path the unbound-lane
    refusal inherits (``fills.py:441-446`` → ``sequencer.py:534-545``).
    """
    fill_model = build_fill_model(_ack(), key=KEY_A)
    core, _sink = build_core(
        registry=registry_with_all(lane_strategy(INSTRUMENT)), transmit=fill_model
    )
    converter = build_converter(key=KEY_A, source=capsule_source_for(INSTRUMENT))
    tick = next(converter.stream(offset_bars(1, coordinate_offset=0)))
    result = core.handle(
        EngineEvent(
            kind=EventKind.DECISION_TICK,
            decision_tick=tick.payload.model_copy(
                update={"reference": OrderingEvent(source_native_sequence=1)}
            ),
        )
    )
    assert result.halt_reason is HaltReason.TRANSMIT_RAISED


# ---------------------------------------------------------------------------
# T9 — the forward obligation, observed rather than asserted
# ---------------------------------------------------------------------------


def test_two_continuities_conflate_in_the_cores_single_slot() -> None:
    """(§1.4 FORWARD-OBLIGATION-MS1) Why a live multi-symbol ingest owes a single continuity.

    The core holds one ``_last_reference`` and overwrites it for every admitted event, so a stream
    carrying two continuities loses the per-continuity history entirely. The backtest driver never
    produces one — but a live ``EventSource`` could, which is exactly why the obligation is named as
    a **new** forward obligation rather than reported as already ratified.
    """
    core, _sink = build_core(registry=registry_with_all(lane_strategy(INSTRUMENT)))
    converter = build_converter(key=KEY_A, source=capsule_source_for(INSTRUMENT))
    ticks = list(converter.stream(offset_bars(3, coordinate_offset=0)))

    def _handle(reference: OrderingEvent, index: int):  # noqa: ANN202 - a local runner
        return core.handle(
            EngineEvent(
                kind=EventKind.DECISION_TICK,
                decision_tick=ticks[index].payload.model_copy(
                    update={"reference": reference}
                ),
            )
        )

    assert _handle(_coordinate("live-a", 5), 0).ordering is OrderingAdmission.MONOTONE
    assert _handle(_coordinate("live-b", 6), 1).ordering is OrderingAdmission.AMBIGUOUS
    regressed = _handle(_coordinate("live-a", 3), 2)
    assert regressed.ordering is OrderingAdmission.AMBIGUOUS
    assert regressed.halt_reason is not HaltReason.EVENT_ORDER_REVERSED, (
        "the regression is admitted — the global slot now holds continuity B's coordinate, so "
        "continuity A's own history is simply gone (design #37 §1.4)"
    )


# ---------------------------------------------------------------------------
# ∅ both ways, at the mapping layer
# ---------------------------------------------------------------------------


def test_a_missing_stream_mapping_is_fail_closed() -> None:
    """(§3.6) ``None`` is MISSING — never an implied empty run."""
    with pytest.raises(BacktestIntegrityError, match="mapping is missing"):
        validate_bar_stream_mapping(None)


def test_a_lane_with_a_missing_stream_is_fail_closed() -> None:
    """(§3.6) A declared lane handed ``None`` is MISSING, not an empty lane."""
    with pytest.raises(BacktestIntegrityError, match="is missing"):
        validate_bar_stream_mapping({KEY_A: None})


def test_an_explicitly_empty_lane_is_a_defined_empty_lane() -> None:
    """(§3.6) ``()`` is a *defined* empty lane — zero ticks, no failure."""
    assert validate_bar_stream_mapping({KEY_A: ()}) == ((KEY_A, ()),)


def test_an_empty_mapping_is_a_defined_zero_lane_run() -> None:
    """(§3.6) ``{}`` is a defined zero-lane run, and it still carries its injected continuity.

    ``WiringTrace`` refuses a blank continuity id (``records.py:234-238``), so even a run with no
    lanes at all records the concrete continuity the driver was wired with.
    """
    driver = MultiSymbolBacktestDriver(
        converters={}, fill_models={}, continuity_id="empty-multi-symbol-run"
    )
    core, _sink = build_core(registry=registry_with_all(lane_strategy(INSTRUMENT)))
    run = driver.run(core, {})

    assert run.instrument_keys == ()
    assert run.bars_consumed == 0
    assert run.events_yielded == 0
    assert run.event_results == ()
    assert run.trace.entries == ()
    assert run.trace.continuity_id == "empty-multi-symbol-run"
    assert run.fill_records == ()
    assert run.unsettled_fill_records == ()
    assert run.handoff_count == 0
    assert run.closes_no_ev is True


def test_a_declared_lane_without_a_stream_is_refused() -> None:
    """(§3.6) The stream mapping and the declared lanes must correspond exactly, both ways."""
    driver, _converters, _models = build_multi_symbol_driver([(INSTRUMENT, _ack())])
    core, _sink = build_core(
        registry=registry_with_all(lane_strategy(INSTRUMENT)), transmit=driver
    )
    with pytest.raises(BacktestIntegrityError, match="do not correspond"):
        driver.run(core, {})


def test_a_stream_for_an_undeclared_lane_is_refused() -> None:
    """(§3.6) The other direction: a stream with no lane to replay it is fail-closed."""
    driver, _converters, _models = build_multi_symbol_driver([(INSTRUMENT, _ack())])
    core, _sink = build_core(
        registry=registry_with_all(lane_strategy(INSTRUMENT)), transmit=driver
    )
    with pytest.raises(BacktestIntegrityError, match="do not correspond"):
        driver.run(
            core,
            {
                KEY_A: offset_bars(1, coordinate_offset=0),
                KEY_B: offset_bars(1, coordinate_offset=30),
            },
        )


# ---------------------------------------------------------------------------
# lane wiring — structural derivation over assertion
# ---------------------------------------------------------------------------


def test_half_a_lane_is_refused() -> None:
    """(§3.2) A lane is a converter **and** a fill band; either alone is refused."""
    converter = build_converter(key=KEY_A, source=capsule_source_for(INSTRUMENT))
    with pytest.raises(INTEGRITY_ERRORS, match="lane sets disagree"):
        MultiSymbolBacktestDriver(
            converters={KEY_A: converter}, fill_models={}, continuity_id="c-0"
        )
    with pytest.raises(INTEGRITY_ERRORS, match="lane sets disagree"):
        MultiSymbolBacktestDriver(
            converters={},
            fill_models={KEY_A: build_fill_model(_ack(), key=KEY_A)},
            continuity_id="c-0",
        )


def test_a_converter_filed_under_the_wrong_key_is_refused() -> None:
    """(§3.2) The lane key is the scope the converter declares, never one asserted beside it."""
    converter = build_converter(key=KEY_A, source=capsule_source_for(INSTRUMENT))
    with pytest.raises(INTEGRITY_ERRORS, match="declares the scope"):
        MultiSymbolBacktestDriver(
            converters={KEY_B: converter},
            fill_models={KEY_B: build_fill_model(_ack(), key=KEY_B)},
            continuity_id="c-0",
        )


def test_an_unnamed_continuity_is_refused_for_a_multi_symbol_run() -> None:
    """(§3.4 / M9) N lanes still share **one named** continuity — a blank one is refused."""
    with pytest.raises(BacktestIntegrityError, match="continuity_id must be concrete"):
        MultiSymbolBacktestDriver(converters={}, fill_models={}, continuity_id="   ")


def test_a_second_different_core_is_refused_for_a_multi_symbol_run() -> None:
    """(§2.4) The single-core seal is the N-lane driver's too — one core for every lane."""
    from tos.backtest import CoreReinstantiationError

    driver, _converters, _models = build_multi_symbol_driver([(INSTRUMENT, _ack())])
    first, _sink = build_core(
        registry=registry_with_all(lane_strategy(INSTRUMENT)), transmit=driver
    )
    driver.run(first, {KEY_A: offset_bars(1, coordinate_offset=0)})
    assert driver.bound_core is first

    second, _sink_b = build_core(
        registry=registry_with_all(lane_strategy(INSTRUMENT)), transmit=driver
    )
    with pytest.raises(CoreReinstantiationError, match="already bound"):
        driver.run(second, {KEY_A: offset_bars(1, coordinate_offset=0)})


# ---------------------------------------------------------------------------
# property — arbitrary lane counts and interleaves
# ---------------------------------------------------------------------------


@settings(max_examples=25, deadline=None)
@given(
    bar_counts=st.lists(st.integers(min_value=0, max_value=3), min_size=1, max_size=3),
    offsets=st.lists(st.integers(min_value=0, max_value=90), min_size=1, max_size=3),
)
def test_any_interleave_stays_one_orderable_stream(
    bar_counts: list[int], offsets: list[int]
) -> None:
    """(§5 property) For any lane count and any interleave: zero ``AMBIGUOUS``, one total order.

    A probabilistic detector over the shapes the fixed canaries pin at one point each. The
    deterministic regressions stay owned by T2 / T5 / T10 — hypothesis widens the evidence, it does
    not carry it.
    """
    instruments = ["ES", "NQ", "CL"][: min(len(bar_counts), len(offsets))]
    lanes = [(name, _ack()) for name in instruments]
    driver, _converters, _models = build_multi_symbol_driver(lanes)
    core, _sink = build_core(
        registry=registry_with_all(*(lane_strategy(name) for name in instruments)),
        transmit=driver,
    )
    streams = {
        instrument_key(instrument=name): offset_bars(
            bar_counts[index], coordinate_offset=offsets[index]
        )
        for index, name in enumerate(instruments)
    }
    run = driver.run(core, streams)

    assert all(
        entry.ordering_admission is OrderingAdmission.MONOTONE
        for entry in run.trace.entries
    )
    assert {entry.reference.source_continuity_id for entry in run.trace.entries} <= {
        run.trace.continuity_id
    }
    yields = [entry.yield_sequence for entry in run.trace.entries]
    assert yields == sorted(set(yields))
    for entry in run.trace.entries:
        assert entry.reference.source_native_sequence == entry.yield_sequence


def test_the_merged_order_is_non_decreasing_for_any_interleave() -> None:
    """(§3.3 / §5-T6) The merged coordinate sequence never goes backwards — checked on the helper."""
    for offset in (0, 30, 60, 90):
        merged = merge_bar_streams(
            [
                (KEY_A, offset_bars(3, coordinate_offset=0)),
                (KEY_B, offset_bars(3, coordinate_offset=offset)),
            ]
        )
        coordinates = [bar.timestamp_coordinate for _key, bar in merged]
        assert coordinates == sorted(coordinates)
        assert len(merged) == 6
        assert isinstance(merged[0][1], Bar)
