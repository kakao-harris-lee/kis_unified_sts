"""§7.2-9 — at-most-one re-entrancy deny (design #31 §4.4, MAJOR-1)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from tos.canonical import ArtifactIntegrityError
from tos.engine import (
    PROJECTION_ORDER,
    CommitmentStep,
    EgressResultKind,
    EgressResultPayload,
    EngineEvent,
    EventKind,
    HaltReason,
    ProvisionalReservationLedger,
    StageRequest,
)
from tos.rcl import CapacityState

from ._engine_fixtures import (
    PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE,
    RecordingTransmit,
    admitting_stages,
    build_core,
    decision_tick,
    engine_configuration,
    instrument_key,
    issue_capsule,
    ordering,
)


def test_a_second_tick_between_send_and_result_is_denied_at_the_capacity_stage() -> (
    None
):
    """(§7.2-9) The re-entrancy window is closed: no overlapping exposure can be created."""
    transmit = RecordingTransmit()
    core, sink = build_core(transmit=transmit)

    first = core.handle(decision_tick(sequence=1))
    assert first.flow is not None and first.flow.handed_off is True
    assert len(transmit.attempts) == 1

    second = core.handle(decision_tick(sequence=2, capsule=issue_capsule()))

    assert second.flow is not None
    assert second.flow.handed_off is False
    assert second.halt_reason is HaltReason.AT_MOST_ONE_EXPOSURE_HELD
    assert len(transmit.attempts) == 1, "a second attempt must never leave the core"

    halts = [
        r for r in sink.records if r.halt_reason is HaltReason.AT_MOST_ONE_EXPOSURE_HELD
    ]
    assert len(halts) == 1
    assert halts[0].detail is not None
    assert "POTENTIALLY_LIVE" in halts[0].detail


def test_the_deny_happens_at_the_capacity_stage_not_later() -> None:
    """(§4.4) The stop is at step 8 — before any further stage or attempt creation."""
    from tos.engine import CommitmentStep

    transmit = RecordingTransmit()
    core, _ = build_core(transmit=transmit)
    core.handle(decision_tick(sequence=1))
    second = core.handle(decision_tick(sequence=2, capsule=issue_capsule()))

    assert second.flow is not None
    assert second.flow.halt_step is CommitmentStep.LEDGER_VERIFICATION
    assert second.flow.attempt is None


def test_the_bound_is_injected_not_hardcoded() -> None:
    """(§8) A configured bound of 2 admits a second exposure — the deny is a real comparison."""
    ledger = ProvisionalReservationLedger(max_unresolved_send_per_scope=2)
    key = instrument_key()
    assert ledger.admits_new_exposure(key) is True
    ledger.commit_unbound(key, proposal_id="prop-1")
    assert ledger.outstanding_count(key) == 1
    assert ledger.admits_new_exposure(key) is True

    strict = ProvisionalReservationLedger(
        max_unresolved_send_per_scope=PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE
    )
    strict.commit_unbound(key, proposal_id="prop-1")
    assert strict.admits_new_exposure(key) is False


def test_a_zero_bound_denies_the_very_first_exposure() -> None:
    """(§8) The comparison is strict: a bound of 0 admits nothing at all (fail-closed)."""
    ledger = ProvisionalReservationLedger(max_unresolved_send_per_scope=0)
    assert ledger.admits_new_exposure(instrument_key()) is False
    with pytest.raises(ArtifactIntegrityError, match="at-most-one"):
        ledger.commit_unbound(instrument_key(), proposal_id="prop-1")


def test_a_negative_bound_is_not_a_bound() -> None:
    """(§8) An ill-formed injected bound is refused rather than silently clamped."""
    with pytest.raises(ArtifactIntegrityError, match="non-negative"):
        ProvisionalReservationLedger(max_unresolved_send_per_scope=-1)
    with pytest.raises(Exception, match="non-negative"):
        engine_configuration(max_unresolved_send_per_scope=-1)


def test_the_ledger_itself_refuses_an_overlapping_commit() -> None:
    """(§4.4 defence in depth) Even bypassing the step-8 pre-check, the projection fails closed."""
    ledger = ProvisionalReservationLedger(
        max_unresolved_send_per_scope=PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE
    )
    key = instrument_key()
    ledger.commit_unbound(key, proposal_id="prop-1")
    with pytest.raises(ArtifactIntegrityError, match="at-most-one"):
        ledger.commit_unbound(key, proposal_id="prop-2")


def test_a_different_scope_is_unaffected() -> None:
    """(§4.4) The retention is per (account, instrument) scope, not global."""
    from tos.engine import InstrumentKey

    ledger = ProvisionalReservationLedger(
        max_unresolved_send_per_scope=PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE
    )
    ledger.commit_unbound(instrument_key(), proposal_id="prop-1")
    other = InstrumentKey(account="acct-1", instrument="NQ")
    assert ledger.admits_new_exposure(other) is True


def test_the_projection_reaches_potentially_live_before_the_hand_off() -> None:
    """(§4.4 / ADR-002-002 §11.4 step 16) SEND_STARTED is projected *before* the external call."""
    observed: list[CapacityState | None] = []

    class _ObservingTransmit:
        """Records the projection state as seen from inside the send-boundary call."""

        def __init__(self, ledger: ProvisionalReservationLedger) -> None:
            self._ledger = ledger
            self.attempts: list[object] = []

        def __call__(self, attempt):  # noqa: ANN001, ANN204
            self.attempts.append(attempt)
            reservation = self._ledger.outstanding(instrument_key())
            observed.append(None if reservation is None else reservation.capacity_state)
            from tos.engine import SendHandoff

            return SendHandoff(accepted_for_transmission=True)

    ledger = ProvisionalReservationLedger(
        max_unresolved_send_per_scope=PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE
    )
    transmit = _ObservingTransmit(ledger)
    core, _ = build_core(transmit=transmit)
    core._ledger = (
        ledger  # noqa: SLF001 - the observing transmit needs the same projection
    )
    core.handle(decision_tick(sequence=1))

    assert observed == [CapacityState.POTENTIALLY_LIVE], (
        "the projection must already be POTENTIALLY_LIVE when the attempt leaves the core "
        "(ADR-002-002 §11.4 step 16; INV-005:168)"
    )


def test_the_retention_survives_every_terminal_result_kind() -> None:
    """(§4.4) Whatever the send boundary reports, the scope stays occupied in this slice."""
    cases: tuple[tuple[EgressResultKind, dict[str, Any]], ...] = (
        (EgressResultKind.ACK, {}),
        (EgressResultKind.REJECT, {}),
        (EgressResultKind.UNKNOWN, {}),
        (EgressResultKind.TIMEOUT, {}),
    )
    for kind, fills in cases:
        transmit = RecordingTransmit()
        core, _ = build_core(transmit=transmit)
        first = core.handle(decision_tick(sequence=1))
        assert first.flow is not None and first.flow.attempt is not None
        core.handle(
            EngineEvent(
                kind=EventKind.EGRESS_RESULT,
                egress_result=EgressResultPayload(
                    instrument_key=instrument_key(),
                    attempt_id=first.flow.attempt.attempt_id,
                    kind=kind,
                    reference=ordering(2),
                    **fills,
                ),
            )
        )
        second = core.handle(decision_tick(sequence=3, capsule=issue_capsule()))
        assert (
            second.halt_reason is HaltReason.AT_MOST_ONE_EXPOSURE_HELD
        ), f"a {kind.value} result must not free the scope — release is the RCL's act"
        assert len(transmit.attempts) == 1


def test_the_consumed_magnitude_accessor_reads_the_projection_and_changes_nothing() -> (
    None
):
    """(design #35 §5.2/§5.3) The observation is a read; the RCL boundary is untouched."""
    transmit = RecordingTransmit()
    core, _ = build_core(transmit=transmit)
    key = instrument_key()

    assert core.ledger.outstanding(key) is None
    assert core.ledger.outstanding_consumed_magnitude(key) is None

    first = core.handle(decision_tick(sequence=1))
    assert first.flow is not None and first.flow.attempt is not None
    assert core.ledger.outstanding(key) is not None
    assert core.ledger.outstanding_consumed_magnitude(key) is None

    core.handle(
        EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=key,
                attempt_id=first.flow.attempt.attempt_id,
                kind=EgressResultKind.FULL_FILL,
                filled_quantity=Decimal(7),
                remaining_quantity=Decimal(0),
                reference=ordering(2),
            ),
        )
    )

    before = core.ledger.outstanding(key)
    assert before is not None
    assert core.ledger.outstanding_consumed_magnitude(key) == before.filled_quantity

    for _ in range(5):
        assert core.ledger.outstanding_consumed_magnitude(key) == before.filled_quantity
    after = core.ledger.outstanding(key)
    assert after == before
    assert after is not None
    assert after.capacity_state is CapacityState.POSITION_CONSUMED
    assert core.ledger.outstanding_count(key) == 1
    assert core.ledger.admits_new_exposure(key) is False


def test_the_accessor_is_a_read_and_release_is_the_only_gated_mutator() -> None:
    """(design #35 §5.3; kernel round #3 §2 decision 5) A read accessor was added; ``free`` /"""
    ledger = ProvisionalReservationLedger(max_unresolved_send_per_scope=1)
    assert hasattr(ledger, "release")
    for name in ("free", "clear", "reset"):
        assert not hasattr(ledger, name)
    assert hasattr(ledger, "outstanding_consumed_magnitude")

    mutators = {
        name
        for name in dir(ledger)
        if not name.startswith("_")
        and any(token in name for token in ("release", "free", "clear", "reset"))
    }
    assert mutators == {"release"}, (
        f"exactly one gated mutator spelling should exist ('release'), got {mutators!r} — a "
        "second one would be an unreviewed, ungated new mutation surface"
    )
    assert CapacityState.RELEASED in PROJECTION_ORDER
    with pytest.raises(TypeError):
        ledger.release("EGRESS_RESULT")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ledger.release(EgressResultKind.FULL_FILL)  # type: ignore[arg-type]


def test_every_stage_request_carries_the_two_observations_restrictively() -> None:
    """(design #35 §4.2/§5.2) Both additive slots default to absent, never to a stand-in value."""
    key = instrument_key()
    core, _ = build_core(transmit=RecordingTransmit())
    first = core.handle(decision_tick(sequence=1))
    assert first.pipeline is not None and first.pipeline.proposal is not None

    bare = StageRequest(
        step=CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION,
        instrument_key=key,
        proposal=first.pipeline.proposal,
    )
    assert bare.value_view is None
    assert bare.held_position_magnitude is None

    assert first.flow is not None and first.flow.attempt is not None
    core.handle(
        EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=key,
                attempt_id=first.flow.attempt.attempt_id,
                kind=EgressResultKind.FULL_FILL,
                filled_quantity=Decimal(7),
                remaining_quantity=Decimal(0),
                reference=ordering(2),
            ),
        )
    )

    seen: list[StageRequest] = []

    def recording(stage: Any) -> Any:
        def call(request: StageRequest) -> Any:
            seen.append(request)
            return stage(request)

        return call

    watched, _ = build_core(
        transmit=RecordingTransmit(),
        stages={step: recording(stage) for step, stage in admitting_stages().items()},
        sink=None,
    )
    started = watched.handle(decision_tick(sequence=1))
    assert started.flow is not None and started.flow.attempt is not None
    watched.handle(
        EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=key,
                attempt_id=started.flow.attempt.attempt_id,
                kind=EgressResultKind.FULL_FILL,
                filled_quantity=Decimal(7),
                remaining_quantity=Decimal(0),
                reference=ordering(2),
            ),
        )
    )
    seen.clear()
    watched.handle(decision_tick(sequence=3, capsule=issue_capsule()))
    assert seen, "the second flow must have reached at least one injected stage"
    assert all(
        request.held_position_magnitude == 7 for request in seen
    ), "every stage sees the observed held position, not just the one that consumes it"
