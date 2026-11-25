"""``project_finality`` — the driver's post-trade finality-projection hook (TOS Phase 5 W2-R;"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tos.engine import EventResult
from tos.engine.records import EgressResultPayload, EngineEvent
from tos.engine.state import FinalityProofRef, ProvisionalReservationLedger
from tos.engine.vocabulary import EgressResultKind, EventKind, ResultDisposition

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.finality import (
    FinalityProducerPort,
    ReleaseFinalityProducer,
)
from tos_runtime.rcl.finality_witness import finality_witness_for

if TYPE_CHECKING:
    from tos_runtime.posttrade.release_consumer import FinalityConsumerPort

__all__ = [
    "ECONOMIC_OBLIGATION_KIND",
    "ENGINE_PROJECTION_RELEASED_KIND",
    "ENGINE_PROJECTION_RELEASE_SKIPPED_KIND",
    "FINALITY_REPROJECTED_KIND",
    "POSTTRADE_FINALITY_PROOF_KIND",
    "project_finality",
    "project_recovered_finality",
]

ECONOMIC_OBLIGATION_KIND = "ECONOMIC_OBLIGATION"
POSTTRADE_FINALITY_PROOF_KIND = "POSTTRADE_FINALITY_PROOF"
ENGINE_PROJECTION_RELEASE_SKIPPED_KIND = "ENGINE_PROJECTION_RELEASE_SKIPPED"
ENGINE_PROJECTION_RELEASED_KIND = "ENGINE_PROJECTION_RELEASED"
FINALITY_REPROJECTED_KIND = "FINALITY_REPROJECTED"
_RECOVERABLE_KINDS = frozenset(
    {
        EgressResultKind.FULL_FILL,
        EgressResultKind.CANCEL_ACK,
        EgressResultKind.EXPIRED,
        EgressResultKind.REJECT,
    }
)


def project_finality(
    event: EngineEvent,
    result: EventResult,
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    finality_producer: FinalityProducerPort,
    release_consumer: FinalityConsumerPort | None,
    ledger: ProvisionalReservationLedger,
) -> None:
    """For a genuinely-applied ``FULL_FILL``, produce a SYNTHETIC post-trade finality proof, then"""
    if event.kind is not EventKind.EGRESS_RESULT:
        return
    if result.result_disposition is not ResultDisposition.APPLIED:
        return
    payload = event.egress_result
    assert payload is not None

    _record_fill_proof(
        payload,
        inbox=inbox,
        evidence_store=evidence_store,
        finality_producer=finality_producer,
    )
    _project_release(
        payload,
        evidence_store=evidence_store,
        release_consumer=release_consumer,
        ledger=ledger,
    )


def _project_release(
    payload: EgressResultPayload,
    *,
    evidence_store: SqliteEvidenceStore,
    release_consumer: FinalityConsumerPort | None,
    ledger: ProvisionalReservationLedger,
) -> bool:
    """The release-trigger call site (TOS Phase 5 W2-R; kernel round #3 §2 decision 5 W2-K),"""
    if release_consumer is None:
        return False
    outcome = release_consumer.consume(payload)
    released_locally = False
    if (
        outcome.released
        and outcome.proof_digest is not None
        and outcome.evidence_seq is not None
        and outcome.resolution_generation is not None
    ):
        ref = FinalityProofRef(
            attempt_id=outcome.attempt_id,
            proof_digest=outcome.proof_digest,
            evidence_seq=outcome.evidence_seq,
            resolution_generation=outcome.resolution_generation,
        )
        released_locally = ledger.release(ref)
        if released_locally:
            evidence_store.append(
                {
                    "attempt_id": ref.attempt_id,
                    "proof_digest": ref.proof_digest,
                    "evidence_seq": ref.evidence_seq,
                    "resolution_generation": ref.resolution_generation,
                },
                kind=ENGINE_PROJECTION_RELEASED_KIND,
                record_class=ENGINE_PROJECTION_RELEASED_KIND,
            )
    if not released_locally:
        evidence_store.append(
            {"attempt_id": outcome.attempt_id, "rcl_released": outcome.released},
            kind=ENGINE_PROJECTION_RELEASE_SKIPPED_KIND,
            record_class=ENGINE_PROJECTION_RELEASE_SKIPPED_KIND,
        )
    return outcome.released


def _record_fill_proof(
    payload: EgressResultPayload,
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    finality_producer: FinalityProducerPort,
) -> None:
    """The durable witness row, plus the obligation/proof evidence when the producer issued one"""
    produced = finality_producer.produce(payload)
    if produced is not None:
        evidence_store.append(
            produced.record.model_dump(mode="json"),
            kind=ECONOMIC_OBLIGATION_KIND,
            record_class=ECONOMIC_OBLIGATION_KIND,
        )
        evidence_store.append(
            produced.proof.model_dump(mode="json"),
            kind=POSTTRADE_FINALITY_PROOF_KIND,
            record_class=POSTTRADE_FINALITY_PROOF_KIND,
        )
    witness = finality_witness_for(None if produced is None else produced.proof)
    inbox.record_finality_witness(payload.attempt_id, witness)


def project_recovered_finality(
    payload: EgressResultPayload,
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    finality_producer: ReleaseFinalityProducer,
    release_consumer: FinalityConsumerPort,
    ledger: ProvisionalReservationLedger,
    reason: str,
) -> bool | None:
    """Re-run finality for a terminal result the engine recorded whose release has not committed"""
    if payload.kind not in _RECOVERABLE_KINDS:
        return None
    if payload.kind is EgressResultKind.FULL_FILL:
        if _fill_proof_durable(evidence_store, finality_producer, payload.attempt_id):
            if inbox.finality_witness(payload.attempt_id) is not True:
                inbox.record_finality_witness(payload.attempt_id, True)
        else:
            _record_fill_proof(
                payload,
                inbox=inbox,
                evidence_store=evidence_store,
                finality_producer=finality_producer,
            )
    released = _project_release(
        payload,
        evidence_store=evidence_store,
        release_consumer=release_consumer,
        ledger=ledger,
    )
    evidence_store.append(
        {
            "attempt_id": payload.attempt_id,
            "egress_result_kind": payload.kind.value,
            "broker_execution_id": payload.broker_execution_id,
            "reason": reason,
            "rcl_released": released,
        },
        kind=FINALITY_REPROJECTED_KIND,
        record_class=FINALITY_REPROJECTED_KIND,
    )
    return released


def _fill_proof_durable(
    evidence_store: SqliteEvidenceStore,
    producer: ReleaseFinalityProducer,
    attempt_id: str,
) -> bool:
    """Both the obligation and the proof row of ``attempt_id``'s fill are durable (the release"""
    wanted = {
        ECONOMIC_OBLIGATION_KIND: f"{producer.full_fill_obligation_prefix}:{attempt_id}",
        POSTTRADE_FINALITY_PROOF_KIND: f"{producer.full_fill_proof_prefix}:{attempt_id}",
    }
    for kind, key in wanted.items():
        rows = evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?", (kind,)
        ).fetchall()
        if not any(
            json.loads(row[0]).get("payload", {}).get("idempotency_key") == key
            for row in rows
        ):
            return False
    return True
