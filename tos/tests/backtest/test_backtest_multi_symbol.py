"""§5 — the multi-symbol (N-lane) extension (design #37)."""

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


def _interleaved_run(
    *, bar_count: int = 2, settle: bool = False
):  # noqa: ANN202 - local runner
    """Two lanes whose **settlements interleave** — the shape T5 / T10 need."""
    parameters = _settle if settle else _ack
    driver, _converters, fill_models = build_multi_symbol_driver(
        [
            (INSTRUMENT, parameters(SettlementPolicy.NEXT_BAR)),
            (INSTRUMENT_B, parameters(SettlementPolicy.SAME_BAR)),
        ]
    )
    core, sink = build_core(
        registry=registry_with_all(
            lane_strategy(INSTRUMENT), lane_strategy(INSTRUMENT_B)
        ),
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
    """Two lanes that do **not** overlap in time: every ``ES`` bar precedes every ``NQ`` bar."""
    driver, _converters, fill_models = build_multi_symbol_driver(
        [(INSTRUMENT, _ack()), (INSTRUMENT_B, _ack())]
    )
    core, sink = build_core(
        registry=registry_with_all(
            lane_strategy(INSTRUMENT), lane_strategy(INSTRUMENT_B)
        ),
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


def _coordinate(continuity: str, sequence: int) -> OrderingEvent:
    """One ordering coordinate on a named continuity."""
    return OrderingEvent(
        event_id=f"{continuity}-{sequence}",
        source_continuity_id=continuity,
        source_native_sequence=sequence,
    )


def test_one_continuity_still_catches_a_symbols_own_regression() -> None:
    """(§1.1/§1.2) A ⊃ B, half one: on a single continuity the regression is ``REVERSED``."""
    a_first = _coordinate("shared", 5)
    b_second = _coordinate("shared", 6)
    a_regressed = _coordinate("shared", 3)

    assert ordering_admission(None, a_first) is OrderingAdmission.MONOTONE
    assert ordering_admission(a_first, b_second) is OrderingAdmission.MONOTONE
    assert ordering_admission(b_second, a_regressed) is OrderingAdmission.REVERSED


def test_per_symbol_continuities_hide_the_same_regression_as_ambiguous() -> None:
    """(§1.1) A ⊃ B, half two: per-symbol continuities turn the *same* sequence fail-open."""
    a_first = _coordinate("continuity-a", 5)
    b_second = _coordinate("continuity-b", 6)
    a_regressed = _coordinate("continuity-a", 3)

    assert ordering_admission(a_first, b_second) is OrderingAdmission.AMBIGUOUS
    assert ordering_admission(b_second, a_regressed) is OrderingAdmission.AMBIGUOUS, (
        "a per-symbol-continuity model would let symbol A go backwards behind symbol B's "
        "coordinate — the detection gap design #37 §1.1 measures"
    )


def test_every_cross_lane_admission_is_monotone() -> None:
    """(§5-T2 mutant A) One continuity ⇒ **every** adjacent pair is orderable, cross-lane included."""
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


def test_a_saturated_lane_does_not_deny_its_neighbour() -> None:
    """(§5-T3) The at-most-one seal is **per scope**: ``ES`` holding one does not block ``NQ``."""
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
    """(§5-T4 / M4 EXTEND) N registry entries, and each tick reaches exactly one of them."""
    run, _driver, _core, _models, _sink = _sequential_run()

    for entry, result in zip(run.trace.entries, run.event_results):
        assert result.instrument_key == entry.instrument_key
    assert all(
        entry.halt_reason is not HaltReason.EVENT_STRATEGY_KEY_MISMATCH
        for entry in run.trace.entries
    )
    handed_off = [
        entry.instrument_key.instrument
        for entry in run.trace.entries
        if entry.handed_off
    ]
    assert handed_off == [
        INSTRUMENT,
        INSTRUMENT_B,
    ], "each lane hands off exactly once, under its own key"


def test_one_lanes_halt_does_not_kill_the_following_lane() -> None:
    """(§3.5) ``ES`` halts at its capacity seal, and ``NQ`` is still replayed normally afterwards."""
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


def test_the_multi_symbol_trace_is_one_total_order() -> None:
    """(§5-T5 / M10 EXTEND, mutant B) One counter ⇒ ``native == yield``, unique and ascending."""
    run, _driver, _core, _models, _sink = _interleaved_run()

    yields = [entry.yield_sequence for entry in run.trace.entries]
    assert yields == sorted(yields)
    assert len(set(yields)) == len(
        yields
    ), "the coordinate is globally unique across lanes"
    for entry in run.trace.entries:
        assert entry.reference.source_native_sequence == entry.yield_sequence


def test_fill_records_follow_the_global_settlement_order() -> None:
    """(§5-T5 MAJOR-N2) ``fill_records`` order == its settlements' ``yield_sequence`` order."""
    run, _driver, _core, _models, _sink = _interleaved_run()

    settled_entries = [
        entry for entry in run.trace.entries if entry.egress_result_kind is not None
    ]
    coordinates = {entry.attempt_id: entry.yield_sequence for entry in settled_entries}
    assert (
        len(coordinates) == len(settled_entries) >= 2
    ), "the join needs at least two distinctly-identified settlements, from different lanes"
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
    """(§1.6) Two behaviourally identical runs must share one oracle identity."""

    def _run(order: tuple[str, str]):  # noqa: ANN202 - a local runner
        driver, _converters, _models = build_multi_symbol_driver(
            [(order[0], _ack()), (order[1], _ack())]
        )
        core, _sink = build_core(
            registry=registry_with_all(
                lane_strategy(INSTRUMENT), lane_strategy(INSTRUMENT_B)
            ),
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
    assert declared_backwards.instrument_keys == (
        KEY_B,
        KEY_A,
    ), "the run records how it was wired — declaration order is not sorted away"
    assert multi_symbol_trace_document(
        declared_forwards
    ) == multi_symbol_trace_document(declared_backwards), (
        "two runs identical in behaviour produced different oracle artifacts — a caller's lane "
        "declaration order leaked into the hashed document (design #37 §1.6)"
    )
    assert [
        (record.instrument_key, record.attempt_id)
        for record in declared_forwards.fill_records
    ] == [
        (record.instrument_key, record.attempt_id)
        for record in declared_backwards.fill_records
    ]


def test_the_unsettled_records_are_ordered_by_lane_key() -> None:
    """(§3.5) The unsettled tail has no settlement to be ordered by, so its order is declared."""
    driver, _converters, _models = build_multi_symbol_driver(
        [
            (INSTRUMENT_B, _ack(SettlementPolicy.NEXT_BAR)),
            (INSTRUMENT, _ack(SettlementPolicy.NEXT_BAR)),
        ]
    )
    core, _sink = build_core(
        registry=registry_with_all(
            lane_strategy(INSTRUMENT), lane_strategy(INSTRUMENT_B)
        ),
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
    assert (
        document["numeric_decision_agreement"] == "DEFERRED_PENDING_D_E2_VALUE_SURFACE"
    )
    assert document["instrument_keys"] == [
        {"account": key.account, "instrument": key.instrument}
        for key in sorted(
            run.instrument_keys, key=lambda item: (item.account, item.instrument)
        )
    ]
    assert (
        run.fill_records[0].execution_price is not None
    ), "the run really did price a fill"
    serialized = repr(document)
    for forbidden in (
        "execution_price",
        "filled_quantity",
        "slippage",
        "cost_component",
    ):
        assert forbidden not in serialized, (
            f"the N-lane oracle artifact leaked {forbidden!r} — its scope is the single-symbol "
            "artifact's, and widening it to N lanes widens nothing else (design #33 §6.2)"
        )


def test_two_symbols_sharing_a_coordinate_are_ordered_by_instrument_key() -> None:
    """(§3.3) The tie-break is ``(account, instrument)`` — never mapping insertion order."""
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
    """(§3.3, both ways) The merged-order assertion is a detector, not decoration."""
    from tos.backtest.bars import _assert_merged_non_decreasing

    ordered = merge_bar_streams([(KEY_A, offset_bars(3, coordinate_offset=0))])
    _assert_merged_non_decreasing(ordered)

    with pytest.raises(BacktestIntegrityError, match="not non-decreasing"):
        _assert_merged_non_decreasing(list(reversed(ordered)))


def test_each_lanes_converter_stays_prefix_bounded() -> None:
    """(§3.3) The frontier reads ordering metadata only; no lane's converter sees a future bar."""
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


def test_a_vector_outcome_is_still_refused_under_multi_symbol_wiring() -> None:
    """(§1.5 / M1 regression) N per-instrument lanes do **not** open ``PortfolioVector`` folding."""
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
    assert (
        run.handoff_count == 1
    ), "the vector lane hands off nothing; the scalar lane still does"


def test_every_fill_is_stamped_with_its_own_lanes_key() -> None:
    """(§3.2 / §5-T10) Each ``LocalFillRecord`` carries the lane that produced it."""
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
            assert [record.instrument_key for record in matching] == [
                entry.instrument_key
            ], (
                "the re-injected result and the D-E3-local record must name the same lane — a "
                "shared fill band would give them one key between them"
            )


def test_a_hand_off_with_no_bound_lane_is_fail_closed() -> None:
    """(§3.2 MINOR-N4) Called outside a tick, the demux refuses rather than guessing a lane."""
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
    """(§3.2) The fail-closed demux really lands on the sequencer's ``TRANSMIT_RAISED`` path."""
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


def test_two_continuities_conflate_in_the_cores_single_slot() -> None:
    """(§1.4 FORWARD-OBLIGATION-MS1) Why a live multi-symbol ingest owes a single continuity."""
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
    """(§3.6) ``{}`` is a defined zero-lane run, and it still carries its injected continuity."""
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


@settings(max_examples=25, deadline=None)
@given(
    bar_counts=st.lists(st.integers(min_value=0, max_value=3), min_size=1, max_size=3),
    offsets=st.lists(st.integers(min_value=0, max_value=90), min_size=1, max_size=3),
)
def test_any_interleave_stays_one_orderable_stream(
    bar_counts: list[int], offsets: list[int]
) -> None:
    """(§5 property) For any lane count and any interleave: zero ``AMBIGUOUS``, one total order."""
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
