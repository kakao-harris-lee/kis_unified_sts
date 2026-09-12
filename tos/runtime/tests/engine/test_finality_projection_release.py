"""``tos_runtime.engine.finality_projection.project_finality`` — the kernel release call site
(kernel round #3 §2 decision 5, W2-K wiring, ``docs/plans/2026-09-12-tos-kernel-round-3-plan.md``).

The real compose e2e suite cannot exercise the SUCCESS path directly: its one synthetic broker
witness is never independent, so ``FinalityReleaseConsumer``'s own gate 3 never corroborates
there (``tests/compose/test_compose_root.py
::test_full_fill_hand_off_never_releases_rcl_capacity_end_to_end``). This file drives
``project_finality`` directly with a stub release consumer (matching
``tos_runtime.posttrade.release_consumer.FinalityReleaseConsumer.consume``'s own
``(payload) -> ReleaseOutcome`` shape) so the wiring itself — build a kernel
:class:`~tos.engine.state.FinalityProofRef` from a positively-released outcome and call
``ledger.release(ref)``, or record ``ENGINE_PROJECTION_RELEASE_SKIPPED`` evidence for every other
case — is proven independently of whether today's compose root can ever reach it for real.

Regime tag: authoring evidence only; closes no EV.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest
from tos.canonical import ArtifactIntegrityError
from tos.engine import EventResult
from tos.engine.records import EgressResultPayload, EngineEvent, InstrumentKey
from tos.engine.state import ProvisionalReservationLedger
from tos.engine.vocabulary import (
    EgressResultKind,
    EventKind,
    OrderingAdmission,
    ResultDisposition,
)
from tos.rcl import CapacityState
from tos_runtime.engine.finality_projection import (
    ENGINE_PROJECTION_RELEASE_SKIPPED_KIND,
    project_finality,
)
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore

_ACCOUNT = "acct-fp"
_INSTRUMENT = "101S07"
_ATTEMPT = "attempt-fp-1"
_KEY = InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT)


class _NullFinalityProducer:
    """A finality producer that never produces — isolates this file's tests from
    ``SyntheticFinalityProducer``'s own config/scheme plumbing, which
    ``tests/posttrade/test_release_consumer.py`` already covers directly."""

    def produce(self, payload: EgressResultPayload) -> None:
        del payload
        return None


@dataclass(frozen=True)
class _StubOutcome:
    """A hand-built stand-in for ``tos_runtime.posttrade.release_consumer.ReleaseOutcome`` — the
    exact shape :meth:`FinalityReleaseConsumer.consume` returns."""

    released: bool
    attempt_id: str
    proof_digest: str | None = None
    evidence_seq: int | None = None
    resolution_generation: int | None = None


class _StubConsumer:
    """A release consumer that always returns one canned outcome — isolates ``project_finality``
    from every gate ``FinalityReleaseConsumer`` itself implements (already covered directly by
    ``tests/posttrade/test_release_consumer.py``)."""

    def __init__(self, outcome: _StubOutcome) -> None:
        self._outcome = outcome

    def consume(self, payload: EgressResultPayload) -> _StubOutcome:
        del payload
        return self._outcome


def _live_ledger() -> ProvisionalReservationLedger:
    ledger = ProvisionalReservationLedger(max_unresolved_send_per_scope=1)
    ledger.commit_unbound(_KEY, proposal_id="proposal-fp-1")
    ledger.bind_attempt(_KEY, attempt_id=_ATTEMPT)
    ledger.mark_potentially_live(_KEY)
    return ledger


def _full_fill_event_and_payload() -> (
    tuple[EngineEvent, EventResult, EgressResultPayload]
):
    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT,
        kind=EgressResultKind.FULL_FILL,
        filled_quantity=Decimal("1"),
        remaining_quantity=Decimal("0"),
    )
    event = EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
    result = EventResult(
        kind=EventKind.EGRESS_RESULT,
        instrument_key=_KEY,
        ordering=OrderingAdmission.MONOTONE,
        result_disposition=ResultDisposition.APPLIED,
    )
    return event, result, payload


def _release_skipped_count(evidence_store: SqliteEvidenceStore) -> int:
    return evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?",
        (ENGINE_PROJECTION_RELEASE_SKIPPED_KIND,),
    ).fetchone()[0]


def test_a_released_outcome_releases_the_kernel_ledger_too(
    evidence_store: SqliteEvidenceStore, inbox: SqliteEventInbox
) -> None:
    ledger = _live_ledger()
    event, result, payload = _full_fill_event_and_payload()
    ledger.apply_egress_result(payload)
    assert ledger.outstanding(_KEY).capacity_state is CapacityState.POSITION_CONSUMED

    consumer = _StubConsumer(
        _StubOutcome(
            released=True,
            attempt_id=_ATTEMPT,
            proof_digest="proof-digest-1",
            evidence_seq=7,
            resolution_generation=3,
        )
    )
    project_finality(
        event,
        result,
        inbox=inbox,
        evidence_store=evidence_store,
        finality_producer=_NullFinalityProducer(),
        release_consumer=consumer,
        ledger=ledger,
    )

    # (kernel round #3 §2 decision 5b) RELEASED returns the scope — outstanding() no longer
    # reports a released reservation at all, and the scope is admitted again.
    assert ledger.outstanding(_KEY) is None
    assert ledger.admits_new_exposure(_KEY) is True
    assert _release_skipped_count(evidence_store) == 0


def test_a_new_attempt_is_admitted_on_the_same_scope_after_project_finality_releases(
    evidence_store: SqliteEvidenceStore, inbox: SqliteEventInbox
) -> None:
    """(kernel round #3 §2 decision 5b — team-lead disposition on the K-3 flag: reopening the
    scope after release is W2-K's whole purpose, Phase 5 §10:114) The compose e2e path cannot
    reach this: its one synthetic broker witness is never independent, so a real release never
    actually happens there (module docstring). This drives the SAME real kernel ledger
    ``project_finality`` mutates directly, proving the engine's own ``admits_new_exposure`` —
    not a test-local stand-in — reopens the scope once ``project_finality`` has released it.
    """
    ledger = _live_ledger()
    event, result, payload = _full_fill_event_and_payload()
    ledger.apply_egress_result(payload)
    assert (
        ledger.admits_new_exposure(_KEY) is False
    )  # occupied — the ordinary at-most-one gate

    consumer = _StubConsumer(
        _StubOutcome(
            released=True,
            attempt_id=_ATTEMPT,
            proof_digest="proof-digest-new-attempt",
            evidence_seq=9,
            resolution_generation=1,
        )
    )
    project_finality(
        event,
        result,
        inbox=inbox,
        evidence_store=evidence_store,
        finality_producer=_NullFinalityProducer(),
        release_consumer=consumer,
        ledger=ledger,
    )

    assert ledger.admits_new_exposure(_KEY) is True
    fresh = ledger.commit_unbound(_KEY, proposal_id="proposal-fp-2")
    assert fresh.capacity_state is CapacityState.COMMITTED_UNBOUND
    bound = ledger.bind_attempt(_KEY, attempt_id="attempt-fp-2")
    assert bound.attempt_id == "attempt-fp-2"
    # The released attempt itself stays terminal even now that the scope has moved on.
    with pytest.raises(ArtifactIntegrityError, match="already reached RELEASED"):
        ledger.bind_attempt(_KEY, attempt_id=_ATTEMPT)


def test_a_held_outcome_records_release_skipped(
    evidence_store: SqliteEvidenceStore, inbox: SqliteEventInbox
) -> None:
    ledger = _live_ledger()
    event, result, payload = _full_fill_event_and_payload()
    ledger.apply_egress_result(payload)

    consumer = _StubConsumer(_StubOutcome(released=False, attempt_id=_ATTEMPT))
    project_finality(
        event,
        result,
        inbox=inbox,
        evidence_store=evidence_store,
        finality_producer=_NullFinalityProducer(),
        release_consumer=consumer,
        ledger=ledger,
    )

    assert ledger.outstanding(_KEY).capacity_state is CapacityState.POSITION_CONSUMED
    assert _release_skipped_count(evidence_store) == 1


def test_a_kernel_side_refusal_records_release_skipped_even_though_rcl_released(
    evidence_store: SqliteEvidenceStore, inbox: SqliteEventInbox
) -> None:
    """The RCL said released, but the kernel's own ``release()`` gate refuses (here: the token
    names an attempt this ledger never held) — recorded, never silently dropped."""
    ledger = _live_ledger()
    event, result, payload = _full_fill_event_and_payload()
    ledger.apply_egress_result(payload)

    consumer = _StubConsumer(
        _StubOutcome(
            released=True,
            attempt_id="no-such-attempt",
            proof_digest="proof-digest-2",
            evidence_seq=1,
            resolution_generation=1,
        )
    )
    project_finality(
        event,
        result,
        inbox=inbox,
        evidence_store=evidence_store,
        finality_producer=_NullFinalityProducer(),
        release_consumer=consumer,
        ledger=ledger,
    )

    assert ledger.outstanding(_KEY).capacity_state is CapacityState.POSITION_CONSUMED
    assert _release_skipped_count(evidence_store) == 1


def test_no_release_consumer_never_touches_the_ledger_or_evidence(
    evidence_store: SqliteEvidenceStore, inbox: SqliteEventInbox
) -> None:
    """``release_consumer=None`` (module docstring's pre-W2-R degrade path) must not itself
    record a skip — there was nothing to attempt."""
    ledger = _live_ledger()
    event, result, payload = _full_fill_event_and_payload()
    ledger.apply_egress_result(payload)

    project_finality(
        event,
        result,
        inbox=inbox,
        evidence_store=evidence_store,
        finality_producer=_NullFinalityProducer(),
        release_consumer=None,
        ledger=ledger,
    )

    assert ledger.outstanding(_KEY).capacity_state is CapacityState.POSITION_CONSUMED
    assert _release_skipped_count(evidence_store) == 0
