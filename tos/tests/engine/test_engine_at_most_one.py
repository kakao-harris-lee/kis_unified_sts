"""§7.2-9 — at-most-one re-entrancy deny (design #31 §4.4, MAJOR-1).

The design's target: *"미해소 POTENTIALLY_LIVE reservation 존재 시 동일 instrument 2차 flow의
capacity-stage deny … send 요청↔EGRESS_RESULT 사이 2차 DECISION_TICK가 겹치는 노출을 못 만듦"*, with the
``MAX_unresolved_send_per_scope 1`` violation mutation killed.

The window this closes is real even in a synchronous core: one event is processed to completion,
but the *result* of a send arrives as a **later event**, so a second ``DECISION_TICK`` for the same
instrument can legitimately arrive between the hand-off and the ``EGRESS_RESULT`` (design #31
§2.1(iv)). Without the retention that second flow would create an overlapping economic effect.

Two further properties keep the seal honest:

* the bound is **injected**, not literal — a configuration of ``2`` really admits two, which proves
  the deny is a comparison against the injected ``MAX_unresolved_send_per_scope`` and not a
  hard-coded "one" (design #31 §8);
* the deny is a **restrictive-only observation** of the engine's own projection: it never creates
  headroom (RFC-002 §9.1:558), and the ledger offers no way to make room.

**Honest scope (design #31 §4.4).** This provisional retention does not claim the real ledger's
fencing-epoch / CAS atomicity — concurrency authority stays with the RCL runtime. It is the
provisional mirror of SAFE-021, not SAFE-021 itself.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

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


def test_a_second_tick_between_send_and_result_is_denied_at_the_capacity_stage() -> None:
    """(§7.2-9) The re-entrancy window is closed: no overlapping exposure can be created."""
    transmit = RecordingTransmit()
    core, sink = build_core(transmit=transmit)

    first = core.handle(decision_tick(sequence=1))
    assert first.flow is not None and first.flow.handed_off is True
    assert len(transmit.attempts) == 1

    # ... no EGRESS_RESULT has arrived yet; a second tick for the same instrument shows up.
    second = core.handle(decision_tick(sequence=2, capsule=issue_capsule()))

    assert second.flow is not None
    assert second.flow.handed_off is False
    assert second.halt_reason is HaltReason.AT_MOST_ONE_EXPOSURE_HELD
    assert len(transmit.attempts) == 1, "a second attempt must never leave the core"

    halts = [r for r in sink.records if r.halt_reason is HaltReason.AT_MOST_ONE_EXPOSURE_HELD]
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
    """(§8) A configured bound of 2 admits a second exposure — the deny is a real comparison.

    This is the ``MAX_unresolved_send_per_scope`` mutation in its honest form: if the engine had
    hard-coded "one", raising the injected bound would change nothing. (Slice #1's register value
    is 1; this test only proves the value is *consumed*, it does not endorse 2.)
    """
    ledger = ProvisionalReservationLedger(max_unresolved_send_per_scope=2)
    key = instrument_key()
    assert ledger.admits_new_exposure(key) is True
    ledger.commit_unbound(key, proposal_id="prop-1")
    assert ledger.outstanding_count(key) == 1
    # The slice projects at most one reservation per scope, so a bound of 2 still leaves room.
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
    core._ledger = ledger  # noqa: SLF001 - the observing transmit needs the same projection
    core.handle(decision_tick(sequence=1))

    assert observed == [CapacityState.POTENTIALLY_LIVE], (
        "the projection must already be POTENTIALLY_LIVE when the attempt leaves the core "
        "(ADR-002-002 §11.4 step 16; INV-005:168)"
    )


def test_the_retention_survives_every_terminal_result_kind() -> None:
    """(§4.4) Whatever the send boundary reports, the scope stays occupied in this slice."""
    for kind, fills in (
        (EgressResultKind.ACK, {}),
        (EgressResultKind.REJECT, {}),
        (EgressResultKind.UNKNOWN, {}),
        (EgressResultKind.TIMEOUT, {}),
    ):
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
        assert second.halt_reason is HaltReason.AT_MOST_ONE_EXPOSURE_HELD, (
            f"a {kind.value} result must not free the scope — release is the RCL's act"
        )
        assert len(transmit.attempts) == 1


# ---------------------------------------------------------------------------
# design #35 §5.2/§5.3 — the read-only held-position observation
# ---------------------------------------------------------------------------


def test_the_consumed_magnitude_accessor_reads_the_projection_and_changes_nothing() -> None:
    """(design #35 §5.2/§5.3) The observation is a read; the RCL boundary is untouched.

    ``outstanding_consumed_magnitude`` exists so a position-closing derivation can be sized from
    the position that actually exists. Reading is neither serialization nor mutation, so RFC-002
    §9.1:557 (the RCL is the sole such authority) is untouched and §9.1:558 ("producer-local
    counters SHALL NOT create headroom") is untouched too — which is asserted here rather than
    assumed: every capacity observable is compared before and after repeated reads.
    """
    transmit = RecordingTransmit()
    core, _ = build_core(transmit=transmit)
    key = instrument_key()

    # ∅ both ways: nothing outstanding is an absent observation, not a zero.
    assert core.ledger.outstanding(key) is None
    assert core.ledger.outstanding_consumed_magnitude(key) is None

    first = core.handle(decision_tick(sequence=1))
    assert first.flow is not None and first.flow.attempt is not None
    # outstanding but unfilled is *also* absent — a send that has not settled consumed nothing.
    assert core.ledger.outstanding(key) is not None
    assert core.ledger.outstanding_consumed_magnitude(key) is None

    core.handle(
        EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=key,
                attempt_id=first.flow.attempt.attempt_id,
                kind=EgressResultKind.FULL_FILL,
                filled_quantity=7,
                remaining_quantity=0,
                reference=ordering(2),
            ),
        )
    )

    before = core.ledger.outstanding(key)
    assert before is not None
    assert core.ledger.outstanding_consumed_magnitude(key) == before.filled_quantity

    # ★ the read is idempotent and inert: nothing about the projection moves, however often it
    #   is asked, and the scope stays exactly as occupied as it was.
    for _ in range(5):
        assert core.ledger.outstanding_consumed_magnitude(key) == before.filled_quantity
    after = core.ledger.outstanding(key)
    assert after == before
    assert after is not None
    assert after.capacity_state is CapacityState.POSITION_CONSUMED
    assert core.ledger.outstanding_count(key) == 1
    assert core.ledger.admits_new_exposure(key) is False


def test_the_accessor_is_not_a_release_path_under_any_of_the_four_forbidden_names() -> None:
    """(design #35 §5.3) A read accessor was added; no release path was.

    The projection deliberately has no ``release`` / ``free`` / ``clear`` / ``reset`` — releasing
    capacity is the RCL's act (RFC-002 §9.1:557) and a producer-local counter may not create
    headroom (§9.1:558). The accessor is none of those, and the absence is grepped rather than
    asserted in prose (the #27 anti-phantom discipline).
    """
    ledger = ProvisionalReservationLedger(max_unresolved_send_per_scope=1)
    for name in ("release", "free", "clear", "reset"):
        assert not hasattr(ledger, name)
    assert hasattr(ledger, "outstanding_consumed_magnitude")

    mutators = {
        name
        for name in dir(ledger)
        if not name.startswith("_")
        and any(token in name for token in ("release", "free", "clear", "reset"))
    }
    assert mutators == set()
    assert CapacityState.RELEASED not in PROJECTION_ORDER


def test_every_stage_request_carries_the_two_observations_restrictively() -> None:
    """(design #35 §4.2/§5.2) Both additive slots default to absent, never to a stand-in value.

    …and the sequencer really offers them to **every** step, so a stage that needs one does not
    have to reach for the ledger itself — which is precisely how the projection stays the engine's.
    """
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
                filled_quantity=7,
                remaining_quantity=0,
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
    # replay the *same* projection state by filling this core's scope the same way
    started = watched.handle(decision_tick(sequence=1))
    assert started.flow is not None and started.flow.attempt is not None
    watched.handle(
        EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=key,
                attempt_id=started.flow.attempt.attempt_id,
                kind=EgressResultKind.FULL_FILL,
                filled_quantity=7,
                remaining_quantity=0,
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
