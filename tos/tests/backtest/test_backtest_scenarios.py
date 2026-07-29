"""§5.1 — the mandated scenario set, end-to-end through one core (design #33 §5.1/§8-2/§8-4).

Every row of the design's §5.1 table is replayed here against **the** shipped engine, and every
terminal shape is asserted against the engine's own ``EventResult`` / reservation projection rather
than against a harness restatement of it (RFC-010 §6 원칙 1:183-185 — tests are evidence, not
authority).

Two rows carry more than their share:

* **row A (ACK)** is the MINOR-2 addition. It exists because ``ACK`` advances the *knowledge* axis to
  ``ACKNOWLEDGED`` while leaving the *capacity* projection untouched (``state.py:77`` maps it to
  ``None``) — an axis distinction that a suite covering only fills would never exercise, and that
  ``UNKNOWN`` (``vocabulary.py:149``) would silently blur.
* **row 6 (at-most-one firing)** is the design's reframing (§2.3). The no-release constraint is not
  apologised for: a multi-bar run positively demonstrates that bar 1's entry is realized and bars 2+
  are refused at the capacity stage with ``AT_MOST_ONE_EXPOSURE_HELD``, so no overlapping economic
  effect can be created. One realized entry plus N−1 exact denials — all recorded.

Rows 3-6 are failure / boundary paths, which RFC-010 §6 원칙 4:193-196 makes first-class: "passing
the nominal path proves nothing about failure."

Regime tag: orchestration authoring evidence only; closes no EV (design #33 §1.1).
"""

from __future__ import annotations

import pytest
from tos.backtest import (
    MANDATED_SCENARIO_IDS,
    MANDATED_SCENARIOS,
    ScenarioId,
    SettlementStatus,
    scenario_for,
)
from tos.dsl import TargetKind
from tos.engine import (
    CommitmentStep,
    EgressKnowledge,
    EgressResultKind,
    EventKind,
    HaltReason,
)
from tos.rcl import CapacityState

from ._backtest_fixtures import instrument_key, run_scenario

# ---------------------------------------------------------------------------
# the contract itself
# ---------------------------------------------------------------------------


def test_every_mandated_scenario_id_has_exactly_one_spec() -> None:
    """(§5.1) The closed id set and the shipped spec list agree — no unrealized mandated row."""
    declared = [spec.scenario_id for spec in MANDATED_SCENARIOS]
    assert declared == list(MANDATED_SCENARIO_IDS)
    assert set(declared) == set(ScenarioId)
    for scenario_id in ScenarioId:
        assert scenario_for(scenario_id).scenario_id is scenario_id


def test_a_spec_carries_no_expected_outcome_field() -> None:
    """(§5.1) Inputs only: an expectation stored beside the input and compared to itself proves nothing."""
    from tos.backtest import ScenarioSpec

    field_names = set(ScenarioSpec.model_fields)
    assert not [
        name
        for name in field_names
        if name.startswith("expected") or name.endswith("_expected")
    ], f"ScenarioSpec leaked an expectation field: {sorted(field_names)}"


def test_every_scenario_replays_and_yields_at_least_one_event() -> None:
    """(§5.1) The whole mandated set is runnable — the per-row assertions below are not vacuous."""
    for spec in MANDATED_SCENARIOS:
        run, _core, _fill_model, _sink = run_scenario(spec)
        assert run.bars_consumed == spec.bar_count
        assert run.events_yielded >= 1
        assert run.scenario_id is spec.scenario_id
        assert run.closes_no_ev is True


# ---------------------------------------------------------------------------
# row A — entry → ACK (MINOR-2: the knowledge axis, distinct from UNKNOWN)
# ---------------------------------------------------------------------------


def test_row_a_ack_advances_knowledge_without_touching_capacity() -> None:
    """(§5.1 row A) ACK ⇒ knowledge ACKNOWLEDGED, capacity unchanged at POTENTIALLY_LIVE.

    ``state.py:77`` maps ACK to ``(ACKNOWLEDGED, None)`` — the ``None`` is the capacity projection
    *not moving*. That is a different axis from ``UNKNOWN`` (``vocabulary.py:149``), which also
    leaves capacity alone but establishes no knowledge at all.
    """
    run, core, _fill_model, _sink = run_scenario(scenario_for(ScenarioId.ENTRY_ACK))

    assert run.halts == ()
    assert run.handoff_count == 1
    (fill,) = run.fill_records
    assert fill.result_kind is EgressResultKind.ACK
    assert fill.settlement_status is SettlementStatus.SETTLED

    reservation = core.ledger.outstanding(instrument_key())
    assert reservation is not None
    assert reservation.knowledge is EgressKnowledge.ACKNOWLEDGED
    assert reservation.capacity_state is CapacityState.POTENTIALLY_LIVE

    egress_entries = [
        entry for entry in run.trace.entries if entry.event_kind is EventKind.EGRESS_RESULT
    ]
    assert [entry.knowledge for entry in egress_entries] == [EgressKnowledge.ACKNOWLEDGED]


def test_ack_and_unknown_are_distinguishable_on_the_knowledge_axis() -> None:
    """(§5.1 MINOR-2) The two share a capacity state but never a knowledge state."""
    _, ack_core, _, _ = run_scenario(scenario_for(ScenarioId.ENTRY_ACK))
    _, unknown_core, _, _ = run_scenario(scenario_for(ScenarioId.ENTRY_UNKNOWN))

    ack = ack_core.ledger.outstanding(instrument_key())
    unknown = unknown_core.ledger.outstanding(instrument_key())
    assert ack is not None and unknown is not None
    assert ack.capacity_state is unknown.capacity_state is CapacityState.POTENTIALLY_LIVE
    assert ack.knowledge is EgressKnowledge.ACKNOWLEDGED
    assert unknown.knowledge is EgressKnowledge.UNKNOWN
    assert ack.knowledge is not unknown.knowledge


# ---------------------------------------------------------------------------
# rows 1-4 — the fill kinds and their projections
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("scenario_id", "kind", "capacity", "knowledge"),
    [
        (
            ScenarioId.ENTRY_FULL_FILL,
            EgressResultKind.FULL_FILL,
            CapacityState.POSITION_CONSUMED,
            EgressKnowledge.FILLED,
        ),
        (
            ScenarioId.ENTRY_PARTIAL_FILL,
            EgressResultKind.PARTIAL_FILL,
            CapacityState.PARTIALLY_CONSUMED,
            EgressKnowledge.PARTIALLY_FILLED,
        ),
        (
            ScenarioId.ENTRY_REJECT,
            EgressResultKind.REJECT,
            CapacityState.RELEASE_PENDING_PROOF,
            EgressKnowledge.REJECTED,
        ),
        (
            ScenarioId.ENTRY_UNKNOWN,
            EgressResultKind.UNKNOWN,
            CapacityState.POTENTIALLY_LIVE,
            EgressKnowledge.UNKNOWN,
        ),
        (
            ScenarioId.ENTRY_TIMEOUT,
            EgressResultKind.TIMEOUT,
            CapacityState.POTENTIALLY_LIVE,
            EgressKnowledge.UNKNOWN,
        ),
    ],
)
def test_each_result_kind_reaches_its_exact_projection(
    scenario_id: ScenarioId,
    kind: EgressResultKind,
    capacity: CapacityState,
    knowledge: EgressKnowledge,
) -> None:
    """(§5.1 rows 1-4 / §8-2) The re-injected result transitions the projection per ``state.py:76-86``."""
    run, core, _fill_model, _sink = run_scenario(scenario_for(scenario_id))
    (fill,) = run.fill_records
    assert fill.result_kind is kind

    reservation = core.ledger.outstanding(instrument_key())
    assert reservation is not None
    assert reservation.capacity_state is capacity
    assert reservation.knowledge is knowledge


def test_row_2_partial_carries_the_remaining_magnitude_into_the_projection() -> None:
    """(§5.1 row 2) A partial stays a partial all the way into the reservation projection."""
    run, core, _fill_model, _sink = run_scenario(
        scenario_for(ScenarioId.ENTRY_PARTIAL_FILL)
    )
    (fill,) = run.fill_records
    reservation = core.ledger.outstanding(instrument_key())
    assert reservation is not None
    assert reservation.filled_quantity == fill.filled_quantity
    assert reservation.remaining_quantity == fill.remaining_quantity
    assert reservation.remaining_quantity is not None
    assert reservation.remaining_quantity > 0


def test_row_3_reject_leaves_the_scope_occupied() -> None:
    """(§5.1 row 3 / §2.1) Even a proven rejection frees nothing — release is the RCL's act.

    ``RELEASE_PENDING_PROOF`` is the *most* consumed rank in the projection order (``state.py:64``),
    not a release: ``RELEASED`` is absent from the vocabulary entirely (``state.py:57``).
    """
    _run, core, _fill_model, _sink = run_scenario(scenario_for(ScenarioId.ENTRY_REJECT))
    assert core.ledger.admits_new_exposure(instrument_key()) is False
    for forbidden in ("release", "free", "clear"):
        assert not hasattr(core.ledger, forbidden), (
            f"the projection exposes {forbidden!r} — releasing capacity is the RCL's "
            "(RFC-002 §9.1:557); a producer-local release would create headroom (:558)"
        )


# ---------------------------------------------------------------------------
# row 5 — fail-closed halt
# ---------------------------------------------------------------------------


def test_row_5_a_stage_deny_stops_the_flow_and_hands_off_nothing() -> None:
    """(§5.1 row 5 / §8-10) A venue INADMISSIBLE deny is a recorded stop, never a skip."""
    run, core, fill_model, _sink = run_scenario(
        scenario_for(ScenarioId.FAIL_CLOSED_HALT)
    )

    assert run.handoff_count == 0
    assert fill_model.handoffs == ()
    assert run.fill_records == ()
    (halt,) = run.halts
    assert halt.halt_reason is HaltReason.STAGE_DENIED
    assert halt.halt_step is CommitmentStep.VENUE_ADMISSIBILITY_DECISION
    assert halt.detail is not None and "INADMISSIBLE" in halt.detail
    # nothing was committed, so the scope is still free — a halt is not a reservation.
    assert core.ledger.outstanding(instrument_key()) is None


# ---------------------------------------------------------------------------
# row 6 — the at-most-one seal FIRING (the positive demonstration, §2.3)
# ---------------------------------------------------------------------------


def test_row_6_one_realized_entry_plus_n_minus_one_exact_denials() -> None:
    """(§5.1 row 6 / §2.3 / §8-4) The seal firing is demonstrated **positively**, not lamented.

    Three bars, one core: bar 1 realizes the entry and hands off exactly once; bars 2 and 3 are
    refused at the capacity stage with ``AT_MOST_ONE_EXPOSURE_HELD``, so no overlapping economic
    effect is ever created (the provisional mirror of SAFE-021).
    """
    spec = scenario_for(ScenarioId.AT_MOST_ONE_FIRING)
    run, _core, fill_model, _sink = run_scenario(spec)

    assert run.bars_consumed == 3
    assert run.handoff_count == 1, "exactly one attempt may ever leave the core"
    assert len(fill_model.handoffs) == 1

    denials = [
        halt for halt in run.halts if halt.halt_reason is HaltReason.AT_MOST_ONE_EXPOSURE_HELD
    ]
    assert len(denials) == spec.bar_count - 1
    assert [halt.bar_index for halt in denials] == [1, 2]
    for halt in denials:
        assert halt.halt_step is CommitmentStep.LEDGER_VERIFICATION, (
            "the deny happens at the capacity stage — before any further stage runs and before "
            "any attempt is created (sequencer.py:382-401)"
        )


def test_row_6_denials_are_recorded_with_their_reason() -> None:
    """(§8-10) A restrictive termination without a recorded reason is a silent stop, not a safe one."""
    run, _core, _fill_model, _sink = run_scenario(
        scenario_for(ScenarioId.AT_MOST_ONE_FIRING)
    )
    for halt in run.halts:
        assert halt.detail is not None
        assert "at-most-one" in halt.detail or "overlapping economic effect" in halt.detail


def test_row_6_the_denied_bars_still_advance_the_causal_gate() -> None:
    """(§3.4) A capacity-halted tick still updates ``_last_reference`` (``core.py:301`` before the handler).

    This is precisely why the coordinate must be a yield-order counter: the halted ticks are part of
    the ordering sequence whether or not their flow completed.
    """
    run, _core, _fill_model, _sink = run_scenario(
        scenario_for(ScenarioId.AT_MOST_ONE_FIRING)
    )
    sequences = [entry.reference.source_native_sequence for entry in run.trace.entries]
    assert sequences == sorted(set(sequences))
    assert len(sequences) == run.events_yielded


# ---------------------------------------------------------------------------
# row 7 — flat-only (a single order, not a round trip)
# ---------------------------------------------------------------------------


def test_row_7_an_explicit_flat_is_a_single_order_not_a_round_trip() -> None:
    """(§5.1 row 7 / §2.5) A flat-only run on a fresh scope is NIT-3 consistent."""
    spec = scenario_for(ScenarioId.FLAT_ONLY)
    assert spec.target_kind is TargetKind.FLAT

    run, _core, _fill_model, _sink = run_scenario(spec)
    assert run.handoff_count == 1
    (fill,) = run.fill_records
    assert fill.result_kind is EgressResultKind.FULL_FILL

    proposals = [
        result.pipeline.proposal
        for result in run.event_results
        if result.pipeline is not None and result.pipeline.proposal is not None
    ]
    assert len(proposals) == 1
    assert proposals[0].target_kind is TargetKind.FLAT
    assert proposals[0].quantity_basis == "ZERO_POSITION", (
        "an Explicit Flat is a zero-position action, structurally distinct from a No-Action "
        "(ADR-DEV-007 §7; SOS-INV-001)"
    )


def test_no_scenario_ever_sends_twice_on_one_scope() -> None:
    """(§2.2/NIT-3) Across the **whole** mandated set, at most one hand-off per run."""
    for spec in MANDATED_SCENARIOS:
        run, _core, _fill_model, _sink = run_scenario(spec)
        assert run.handoff_count <= 1, (
            f"{spec.scenario_id.value} handed off {run.handoff_count} attempts — a slice-1 scope "
            "admits at most one for the lifetime of the projection (state.py:28-29)"
        )
