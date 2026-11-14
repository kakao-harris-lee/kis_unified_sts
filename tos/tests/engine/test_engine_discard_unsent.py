"""``ProvisionalReservationLedger.discard_unsent`` + ``UnsentDiscardRef`` (2026-11-01"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from tos.engine import (
    CommitmentStep,
    EgressResultKind,
    EgressResultPayload,
    HaltReason,
    ProvisionalReservationLedger,
    RecordingEvidenceSink,
    UnsentDiscardReason,
    UnsentDiscardRef,
    run_commitment_flow,
)
from tos.engine.records import InstrumentKey, ProvisionalReservation
from tos.engine.state import FinalityProofRef
from tos.engine.vocabulary import EgressKnowledge, ResultDisposition
from tos.rcl import CapacityState

from ._engine_fixtures import (
    PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE,
    SCHEME,
    RecordingTransmit,
    admitting_stages,
    build_core,
    decision_tick,
    instrument_key,
    ordering,
)

_PROPOSAL = "proposal-unsent-1"
_ATTEMPT = "attempt-unsent-1"


def _ref(proposal_id: str = _PROPOSAL) -> UnsentDiscardRef:
    return UnsentDiscardRef(
        proposal_id=proposal_id,
        reason=UnsentDiscardReason.UNSENT_FLOW_NON_EXECUTION,
    )


def _committed_ledger() -> tuple[ProvisionalReservationLedger, InstrumentKey]:
    """A ledger holding exactly what a step-9 commit followed by a pre-send halt leaves behind."""
    ledger = ProvisionalReservationLedger(
        max_unresolved_send_per_scope=PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE
    )
    key = instrument_key()
    ledger.commit_unbound(key, proposal_id=_PROPOSAL)
    return ledger, key


def _outstanding(
    ledger: ProvisionalReservationLedger, key: InstrumentKey
) -> ProvisionalReservation:
    reservation = ledger.outstanding(key)
    assert reservation is not None
    return reservation


def test_not_sent_committed_unbound_is_discarded_and_the_scope_reopens() -> None:
    """§5 ① row 1: the exact state a step-9 commit + pre-send halt leaves behind."""
    ledger, key = _committed_ledger()
    held = _outstanding(ledger, key)
    assert held.capacity_state is CapacityState.COMMITTED_UNBOUND
    assert held.knowledge is EgressKnowledge.NOT_SENT
    assert ledger.admits_new_exposure(key) is False

    assert ledger.discard_unsent(_ref()) is True

    assert ledger.outstanding(key) is None
    assert ledger.outstanding_count(key) == 0
    assert ledger.admits_new_exposure(key) is True
    ledger.commit_unbound(key, proposal_id="proposal-unsent-2")
    assert _outstanding(ledger, key).proposal_id == "proposal-unsent-2"


def test_not_sent_attempt_bound_is_discarded() -> None:
    """§5 ① row 2: steps 12-14 bound an attempt, but the flow still halted before the send."""
    ledger, key = _committed_ledger()
    ledger.bind_attempt(key, attempt_id=_ATTEMPT)
    held = _outstanding(ledger, key)
    assert held.capacity_state is CapacityState.ATTEMPT_BOUND
    assert held.knowledge is EgressKnowledge.NOT_SENT

    assert ledger.discard_unsent(_ref()) is True
    assert ledger.outstanding(key) is None
    assert ledger.admits_new_exposure(key) is True


def test_potentially_live_is_refused_and_the_projection_is_unchanged() -> None:
    '§5 ① row 3: past ``mark_potentially_live`` the engine may not assume "not sent"'
    ledger, key = _committed_ledger()
    ledger.bind_attempt(key, attempt_id=_ATTEMPT)
    ledger.mark_potentially_live(key)
    before = _outstanding(ledger, key)

    assert ledger.discard_unsent(_ref()) is False

    after = _outstanding(ledger, key)
    assert after == before
    assert after.capacity_state is CapacityState.POTENTIALLY_LIVE
    assert after.knowledge is EgressKnowledge.SENT_UNCONFIRMED
    assert ledger.admits_new_exposure(key) is False


@pytest.mark.parametrize(
    ("kind", "expected_capacity"),
    [
        (EgressResultKind.FULL_FILL, CapacityState.POSITION_CONSUMED),
        (EgressResultKind.REJECT, CapacityState.RELEASE_PENDING_PROOF),
        (EgressResultKind.UNKNOWN, CapacityState.QUARANTINED_UNKNOWN),
    ],
)
def test_an_attempt_with_an_applied_egress_result_is_refused(
    kind: EgressResultKind, expected_capacity: CapacityState
) -> None:
    """§5 ① row 4: once the broker has answered this attempt, nothing here may drop it."""
    ledger, key = _committed_ledger()
    ledger.bind_attempt(key, attempt_id=_ATTEMPT)
    ledger.mark_potentially_live(key)
    fills = kind is EgressResultKind.FULL_FILL
    applied = ledger.apply_egress_result(
        EgressResultPayload(
            instrument_key=key,
            attempt_id=_ATTEMPT,
            kind=kind,
            filled_quantity=Decimal("1") if fills else None,
            remaining_quantity=Decimal("0") if fills else None,
        )
    )
    assert applied.disposition is ResultDisposition.APPLIED
    before = _outstanding(ledger, key)
    assert before.capacity_state is expected_capacity

    assert ledger.discard_unsent(_ref()) is False
    assert _outstanding(ledger, key) == before


def test_an_applied_result_refuses_the_discard_even_at_an_unadvanced_capacity_state() -> (
    None
):
    """The third gate on its own. An ``ACK`` leaves ``capacity_state`` at ``ATTEMPT_BOUND``"""
    ledger, key = _committed_ledger()
    ledger.bind_attempt(key, attempt_id=_ATTEMPT)
    applied = ledger.apply_egress_result(
        EgressResultPayload(
            instrument_key=key, attempt_id=_ATTEMPT, kind=EgressResultKind.ACK
        )
    )
    assert applied.disposition is ResultDisposition.APPLIED
    before = _outstanding(ledger, key)
    assert before.capacity_state is CapacityState.ATTEMPT_BOUND

    assert ledger.discard_unsent(_ref()) is False
    assert _outstanding(ledger, key) == before


def test_an_unknown_proposal_is_false() -> None:
    """§5 ① row 5: nothing matches — a recorded ``False``, never a raise."""
    ledger, key = _committed_ledger()
    assert ledger.discard_unsent(_ref("no-such-proposal")) is False
    assert _outstanding(ledger, key).proposal_id == _PROPOSAL


def test_a_double_discard_is_false_the_second_time() -> None:
    """§5 ① row 6: idempotent — the second call finds nothing to remove."""
    ledger, key = _committed_ledger()
    assert ledger.discard_unsent(_ref()) is True
    assert ledger.discard_unsent(_ref()) is False
    assert ledger.outstanding(key) is None


def test_a_discarded_attempt_may_be_committed_and_bound_again() -> None:
    """A never-sent attempt reached no broker, so it is NOT remembered as terminal: re-binding it"""
    ledger, key = _committed_ledger()
    ledger.bind_attempt(key, attempt_id=_ATTEMPT)
    assert ledger.discard_unsent(_ref()) is True

    ledger.commit_unbound(key, proposal_id=_PROPOSAL)
    ledger.bind_attempt(key, attempt_id=_ATTEMPT)
    assert _outstanding(ledger, key).attempt_id == _ATTEMPT


@pytest.mark.parametrize(
    "bogus",
    [
        _PROPOSAL,
        None,
        {"proposal_id": _PROPOSAL, "reason": "UNSENT_FLOW_NON_EXECUTION"},
        UnsentDiscardReason.UNSENT_FLOW_NON_EXECUTION,
        FinalityProofRef(
            attempt_id=_ATTEMPT,
            proof_digest="d",
            evidence_seq=1,
            resolution_generation=0,
        ),
    ],
)
def test_only_the_typed_token_is_accepted(bogus: Any) -> None:
    ledger, key = _committed_ledger()
    with pytest.raises(TypeError, match="UnsentDiscardRef"):
        ledger.discard_unsent(bogus)
    assert ledger.outstanding(key) is not None


def test_the_reason_is_a_closed_vocabulary() -> None:
    """A free-form cause cannot reach the kernel — the record a replay reads back is validated"""
    with pytest.raises(ValueError):
        UnsentDiscardRef.model_validate(
            {"proposal_id": _PROPOSAL, "reason": "whatever-I-like"}
        )


def _proposal():
    core, _ = build_core(transmit=RecordingTransmit())
    result = core.handle(decision_tick(sequence=1))
    assert result.pipeline is not None and result.pipeline.proposal is not None
    return result.pipeline.proposal


def test_the_974_block_clears_after_the_discard() -> None:
    """#974's own ``measure_974.py``, adapted: flow 1 commits at step 9 and halts at step 10;"""
    proposal = _proposal()
    key = instrument_key()
    ledger = ProvisionalReservationLedger(
        max_unresolved_send_per_scope=PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE
    )
    transmit = RecordingTransmit()
    halt_step = CommitmentStep.COMMITMENT_UNAVAILABILITY

    first = run_commitment_flow(
        proposal_id=_PROPOSAL,
        proposal=proposal,
        instrument_key=key,
        reference=ordering(sequence=1),
        stages=admitting_stages(unknown_steps=frozenset({halt_step})),
        transmit=transmit,
        ledger=ledger,
        sink=RecordingEvidenceSink(),
        scheme=SCHEME,
        event_id="event-1",
    )
    assert first.halt_step is halt_step
    assert first.halt_reason is HaltReason.STAGE_UNKNOWN
    assert transmit.attempts == []
    held = _outstanding(ledger, key)
    assert (held.capacity_state, held.knowledge, held.attempt_id) == (
        CapacityState.COMMITTED_UNBOUND,
        EgressKnowledge.NOT_SENT,
        None,
    )

    def _run(sequence: int, event_id: str):
        consulted: list[CommitmentStep] = []
        base = admitting_stages()

        def _spy(step: CommitmentStep):
            inner = base[step]

            def _call(request):
                consulted.append(step)
                return inner(request)

            return _call

        result = run_commitment_flow(
            proposal_id=f"{_PROPOSAL}-{sequence}",
            proposal=proposal,
            instrument_key=key,
            reference=ordering(sequence=sequence),
            stages={step: _spy(step) for step in base},
            transmit=transmit,
            ledger=ledger,
            sink=RecordingEvidenceSink(),
            scheme=SCHEME,
            event_id=event_id,
        )
        return result, consulted

    blocked, consulted = _run(2, "event-2")
    assert blocked.halt_step is CommitmentStep.LEDGER_VERIFICATION
    assert blocked.halt_reason is HaltReason.AT_MOST_ONE_EXPOSURE_HELD
    assert CommitmentStep.LEDGER_VERIFICATION not in consulted
    assert blocked.handed_off is False

    assert ledger.discard_unsent(_ref()) is True
    assert ledger.admits_new_exposure(key) is True

    admitted, consulted_after = _run(3, "event-3")
    assert admitted.halt_step is None
    assert admitted.handed_off is True
    assert CommitmentStep.LEDGER_VERIFICATION in consulted_after
    assert len(transmit.attempts) == 1
    assert _outstanding(ledger, key).capacity_state is CapacityState.POTENTIALLY_LIVE
