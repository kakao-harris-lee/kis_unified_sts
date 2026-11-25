"""19-step commitment-flow order mutation matrix (Phase 3 wave 3 slice F; plan §3.2/§5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from tos.engine import sequencer as sequencer_module
from tos.engine import standins as standins_module
from tos.engine import vocabulary as vocabulary_module
from tos.engine.vocabulary import COMMITMENT_FLOW_ORDER, CommitmentStep

from ..egressgw._egressgw_fixtures import build_gateway, happy_context
from ._engine_fixtures import admitting_stages, build_core, decision_tick

_ADR_002_002_SECTION_11_ORDER: tuple[CommitmentStep, ...] = (
    CommitmentStep.DECISION_PROPOSAL,
    CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION,
    CommitmentStep.VENUE_ADMISSIBILITY_DECISION,
    CommitmentStep.INDEPENDENT_APPROVAL,
    CommitmentStep.ECONOMIC_EFFECT_ENVELOPE,
    CommitmentStep.AGGREGATE_RISK_DECISION,
    CommitmentStep.ACTION_FLOW_DECISION,
    CommitmentStep.LEDGER_VERIFICATION,
    CommitmentStep.ATOMIC_COMMIT,
    CommitmentStep.COMMITMENT_UNAVAILABILITY,
    CommitmentStep.ORDER_CONFORMANCE_PROOF,
    CommitmentStep.ATTEMPT_REQUEST,
    CommitmentStep.ATTEMPT_BIND_VERIFICATION,
    CommitmentStep.TRANSMISSION_CAPABILITY,
    CommitmentStep.SEND_BOUNDARY_VERIFICATION,
    CommitmentStep.SEND_STARTED_DURABLE,
    CommitmentStep.POTENTIALLY_LIVE_TRANSITION,
    CommitmentStep.NETWORK_CALL,
    CommitmentStep.EVIDENCE_RECORD,
)

assert len(_ADR_002_002_SECTION_11_ORDER) == 19
assert set(_ADR_002_002_SECTION_11_ORDER) == set(CommitmentStep)


class _DerivationUnreachable(Exception):
    """The production derivation formula itself cannot be recomputed for this order."""


@dataclass(frozen=True)
class _Derived:
    """The vocabulary.py-derived structures recomputed for one candidate order."""

    send_boundary_steps: frozenset[CommitmentStep]
    sequenced_steps: tuple[CommitmentStep, ...]
    coordinator_realized_steps: frozenset[CommitmentStep]
    injected_stage_steps: tuple[CommitmentStep, ...]
    step_numbers: dict[CommitmentStep, int]


_COORDINATOR_REALIZED_STEPS: frozenset[CommitmentStep] = frozenset(
    {CommitmentStep.DECISION_PROPOSAL, CommitmentStep.ATTEMPT_REQUEST}
)


def _derive(order: tuple[CommitmentStep, ...]) -> _Derived:
    """Recompute ``SEND_BOUNDARY_STEPS`` / ``SEQUENCED_STEPS`` / ``INJECTED_STAGE_STEPS`` for"""
    try:
        boundary_start = order.index(CommitmentStep.SEND_BOUNDARY_VERIFICATION)
    except ValueError as exc:
        raise _DerivationUnreachable(
            "COMMITMENT_FLOW_ORDER.index(SEND_BOUNDARY_VERIFICATION) raised ValueError for "
            f"this mutated order ({exc}) — vocabulary.py's own formula (lines 237-238) cannot "
            "locate the Send Boundary anchor, so SEND_BOUNDARY_STEPS/SEQUENCED_STEPS/"
            "INJECTED_STAGE_STEPS cannot be recomputed and this mutation cannot be patched "
            "through to the sequencer at all"
        ) from exc
    send_boundary = frozenset(order[boundary_start:])
    sequenced = tuple(step for step in order if step not in send_boundary)
    injected = tuple(
        step for step in sequenced if step not in _COORDINATOR_REALIZED_STEPS
    )
    step_numbers = {step: number for number, step in enumerate(order, start=1)}
    return _Derived(
        send_boundary_steps=send_boundary,
        sequenced_steps=sequenced,
        coordinator_realized_steps=_COORDINATOR_REALIZED_STEPS,
        injected_stage_steps=injected,
        step_numbers=step_numbers,
    )


def _fingerprint(result: Any) -> tuple[Any, ...]:
    """A canonical, order-sensitive fingerprint of one ``EventResult`` (the sequencer's outcome"""
    flow = result.flow
    if flow is None:
        return ("NO_FLOW", result.halt_reason)
    verdict_trace = tuple(
        (verdict.step, verdict.outcome, verdict.bound_digest, verdict.bound_identity)
        for verdict in flow.verdicts
    )
    return (
        "FLOW",
        flow.handed_off,
        flow.halt_step,
        flow.halt_reason,
        verdict_trace,
        None if flow.attempt is None else flow.attempt.attempt_id,
        None if flow.handoff is None else flow.handoff.accepted_for_transmission,
    )


def _run_variant(order: tuple[CommitmentStep, ...]) -> tuple[Any, ...]:
    """Patch every alias :func:`_derive` can reach for ``order``, run one clean ``DECISION_TICK``"""
    try:
        derived = _derive(order)
    except _DerivationUnreachable as exc:
        return ("UNREACHABLE", str(exc))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sequencer_module, "SEQUENCED_STEPS", derived.sequenced_steps)
        mp.setattr(sequencer_module, "SEND_BOUNDARY_STEPS", derived.send_boundary_steps)
        mp.setattr(
            sequencer_module,
            "COORDINATOR_REALIZED_STEPS",
            derived.coordinator_realized_steps,
        )
        mp.setattr(
            standins_module, "INJECTED_STAGE_STEPS", derived.injected_stage_steps
        )
        mp.setattr(vocabulary_module, "COMMITMENT_FLOW_ORDER", order)
        mp.setattr(vocabulary_module, "SEQUENCED_STEPS", derived.sequenced_steps)
        mp.setattr(
            vocabulary_module, "SEND_BOUNDARY_STEPS", derived.send_boundary_steps
        )
        mp.setattr(
            vocabulary_module,
            "COORDINATOR_REALIZED_STEPS",
            derived.coordinator_realized_steps,
        )
        mp.setattr(
            vocabulary_module, "INJECTED_STAGE_STEPS", derived.injected_stage_steps
        )
        mp.setattr(vocabulary_module, "_STEP_NUMBERS", derived.step_numbers)
        try:
            core, _sink = build_core(stages=admitting_stages())
            result = core.handle(decision_tick(sequence=1))
        except (
            Exception
        ) as exc:  # noqa: BLE001 - an uncaught raise IS a detector signal here
            return ("RAISED", type(exc).__name__, str(exc))
    return _fingerprint(result)


_STEP_MOMENT_MULTIPLICITY: dict[CommitmentStep, int] = {
    CommitmentStep.SEND_BOUNDARY_VERIFICATION: 2,
    CommitmentStep.SEND_STARTED_DURABLE: 1,
    CommitmentStep.POTENTIALLY_LIVE_TRANSITION: 1,
    CommitmentStep.NETWORK_CALL: 1,
    CommitmentStep.EVIDENCE_RECORD: 1,
}

_GATEWAY_OBSERVABLE_STEPS: frozenset[CommitmentStep] = frozenset(
    _STEP_MOMENT_MULTIPLICITY
)


def _gateway_projection(
    order: tuple[CommitmentStep, ...],
) -> tuple[CommitmentStep, ...]:
    """Expand every observable occurrence in ``order`` by its :data:`_STEP_MOMENT_MULTIPLICITY`,"""
    projected: list[CommitmentStep] = []
    for step in order:
        multiplicity = _STEP_MOMENT_MULTIPLICITY.get(step)
        if multiplicity is not None:
            projected.extend([step] * multiplicity)
    return tuple(projected)


def _run_gateway_happy_path_steps() -> tuple[CommitmentStep, ...]:
    """Drive one real, fully-admitting send through :class:`BrokerEgressGateway`, reusing the"""
    attempt, context = happy_context()
    gateway, sink = build_gateway(attempt=attempt, context=context)
    handoff = gateway(attempt)
    assert handoff.accepted_for_transmission is True, (
        "the egressgw suite's own happy-path fixture must accept the send — got "
        f"{handoff!r}; a failure here means that fixture's shape changed, not that a mutation "
        "was caught"
    )
    collapsed: list[CommitmentStep] = []
    previous_kind: str | None = None
    for record in sink.records:
        assert record.step is not None, (
            f"gateway record kind={record.kind!r} was never stamped with a step — KW3-GW "
            "(records.py:608-639) should have made every non-SEND_REFUSED kind on the happy "
            "path carry one"
        )
        if record.kind == "VERIFY_ITEM" and previous_kind == "VERIFY_ITEM":
            previous_kind = record.kind
            continue
        collapsed.append(record.step)
        previous_kind = record.kind
    return tuple(collapsed)


def _adjacent_swaps() -> list[tuple[str, tuple[CommitmentStep, ...]]]:
    """The 18 adjacent-pair swaps (19 steps -> 18 adjacencies; the plan's "13" is arithmetic"""
    variants: list[tuple[str, tuple[CommitmentStep, ...]]] = []
    for index in range(len(COMMITMENT_FLOW_ORDER) - 1):
        order = list(COMMITMENT_FLOW_ORDER)
        order[index], order[index + 1] = order[index + 1], order[index]
        variants.append((f"swap_{index + 1}_{index + 2}", tuple(order)))
    return variants


def _omissions() -> list[tuple[str, tuple[CommitmentStep, ...]]]:
    """The 19 single-step omissions."""
    variants: list[tuple[str, tuple[CommitmentStep, ...]]] = []
    for index, step in enumerate(COMMITMENT_FLOW_ORDER):
        order = list(COMMITMENT_FLOW_ORDER)
        del order[index]
        variants.append((f"omit_{index + 1}_{step.value}", tuple(order)))
    return variants


def _duplications() -> list[tuple[str, tuple[CommitmentStep, ...]]]:
    """The 19 single-step duplications (the duplicate immediately follows the original)."""
    variants: list[tuple[str, tuple[CommitmentStep, ...]]] = []
    for index, step in enumerate(COMMITMENT_FLOW_ORDER):
        order = list(COMMITMENT_FLOW_ORDER)
        order.insert(index + 1, step)
        variants.append((f"dup_{index + 1}_{step.value}", tuple(order)))
    return variants


_ALL_VARIANTS: tuple[tuple[str, tuple[CommitmentStep, ...]], ...] = tuple(
    _adjacent_swaps() + _omissions() + _duplications()
)


def test_the_matrix_has_exactly_fifty_six_variants() -> None:
    """(§3.2 correction) 18 adjacent swaps + 19 omissions + 19 duplications = 56, not the plan's"""
    assert len(_adjacent_swaps()) == 18
    assert len(_omissions()) == 19
    assert len(_duplications()) == 19
    assert len(_ALL_VARIANTS) == 56
    assert (
        len({name for name, _order in _ALL_VARIANTS}) == 56
    ), "variant names must be unique"


_EXPECTED_ORDER_PIN_ONLY: frozenset[str] = frozenset()

_EXPECTED_UNREACHABLE: frozenset[str] = frozenset(
    {"omit_15_SEND_BOUNDARY_VERIFICATION"}
)


def _classify(
    name: str,
    order: tuple[CommitmentStep, ...],
    control: tuple[Any, ...],
    gateway_control: tuple[CommitmentStep, ...],
) -> tuple[bool, bool, bool, bool]:
    """Run all three detectors for one variant."""
    mutant = _run_variant(order)
    order_pin_red = tuple(order) != _ADR_002_002_SECTION_11_ORDER
    e2e_red = mutant != control
    gateway_red = _gateway_projection(order) != gateway_control
    unreachable = mutant[0] == "UNREACHABLE"
    del name
    return order_pin_red, e2e_red, gateway_red, unreachable


def test_order_mutation_matrix_has_zero_survivors() -> None:
    """(plan §3.2/§5 «순서 뮤테이션 매트릭스 생존 0») The load-bearing assertion."""
    control = _run_variant(COMMITMENT_FLOW_ORDER)
    assert control[0] == "FLOW" and control[1] is True, (
        f"the control (unmutated order, run through the identical patch-and-execute harness) "
        f"must hand off cleanly — a failure here means the harness itself is broken, not that a "
        f"mutation was caught: {control!r}"
    )
    gateway_control = _run_gateway_happy_path_steps()
    assert gateway_control == _gateway_projection(COMMITMENT_FLOW_ORDER), (
        "the gateway's real, unmutated stamped-step sequence must match the ADR anchor's own "
        f"expanded projection onto the observable steps — gateway={gateway_control!r} "
        f"anchor_projection={_gateway_projection(COMMITMENT_FLOW_ORDER)!r} (this re-derives "
        "test_egressgw_gateway.py::test_the_baseline_send_records_the_commitment_step_"
        "sequence_exactly through this module's own expansion, as a cross-check)"
    )

    survivors: list[str] = []
    anchor_sanity_failures: list[str] = []
    unreachable: list[str] = []
    for name, order in _ALL_VARIANTS:
        order_pin_red, e2e_red, gateway_red, is_unreachable = _classify(
            name, order, control, gateway_control
        )
        if is_unreachable:
            unreachable.append(name)
        if not order_pin_red:
            anchor_sanity_failures.append(name)
        if not e2e_red and not gateway_red:
            survivors.append(name)

    assert not anchor_sanity_failures, (
        f"{len(anchor_sanity_failures)} variant(s) did not even differ from the independently-"
        "transcribed ADR anchor — the variant generator produced a non-mutation (a bug in "
        f"_adjacent_swaps/_omissions/_duplications, not a caught mutation): {anchor_sanity_failures}"
    )
    assert not survivors, (
        f"{len(survivors)}/{len(_ALL_VARIANTS)} order-mutation variants survived BOTH executable "
        f"detectors (run_commitment_flow e2e AND gateway execution order) — plan §3.2/§5 «생존 0» "
        f"requires 0: {survivors}"
    )
    assert set(survivors) == _EXPECTED_ORDER_PIN_ONLY, (
        "the survivor set (caught by neither executable detector) drifted from the expected set "
        f"— actual={sorted(survivors)} expected={sorted(_EXPECTED_ORDER_PIN_ONLY)}"
    )
    assert set(unreachable) == _EXPECTED_UNREACHABLE, (
        f"the set of variants whose derivation formula itself raises drifted — "
        f"actual={sorted(unreachable)} expected={sorted(_EXPECTED_UNREACHABLE)}"
    )
