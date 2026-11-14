"""``EgressCurrentnessProofIssuer`` — per-attempt Egress Currentness Proof issuance."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass

from tos.canonical import (
    EV_L1_PROVISIONAL_VERSION,
    CanonicalizationScheme,
    get_scheme,
)
from tos.cur import (
    CurrentnessRevision,
    EgressCurrentnessProof,
    EgressProofCoordinateSet,
    ProofResult,
    SafetyCurrentnessVector,
    proof_admissible,
)
from tos.engine.records import AttemptRequest
from tos.rcl import AppendRefusal, CommandType, CommitEntry
from tos.rcl.commitlog import CommitLog, WriterEpoch

__all__ = ["EgressCurrentnessProofIssuer", "Item16Fields"]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_PROOF_ISSUANCE_KIND = CommandType.ISSUE_EGRESS_CURRENTNESS_PROOF


@dataclass(frozen=True)
class Item16Fields:
    """``SendBoundaryContext`` item 16 (currentness) — the two fields this"""

    egress_currentness_proof: EgressCurrentnessProof | None
    egress_currentness_result: ProofResult | None


def _effective_seq(last_seq: int | None) -> int:
    """The log's own "empty" sentinel (``-1``, ``SqliteCommitLog.append_cas``'s"""
    return -1 if last_seq is None else last_seq


class EgressCurrentnessProofIssuer:
    """Issues + durably records one :class:`~tos.cur.EgressCurrentnessProof`"""

    def __init__(
        self,
        log: CommitLog,
        *,
        writer_epoch: WriterEpoch,
        is_complete: Callable[[SafetyCurrentnessVector], bool],
        scheme: CanonicalizationScheme = _SCHEME,
        nonce_factory: Callable[[], str] = lambda: secrets.token_hex(16),
    ) -> None:
        self._log = log
        self._writer_epoch = writer_epoch
        self._is_complete = is_complete
        self._scheme = scheme
        self._nonce_factory = nonce_factory
        self._issued: dict[str, EgressCurrentnessProof] = {}

    def _construct_proof(
        self,
        attempt: AttemptRequest,
        vector: SafetyCurrentnessVector,
        *,
        revision: CurrentnessRevision,
        nonce: str,
        bound_generations: tuple[int, ...],
        restrictive_floors: tuple[int, ...],
        egress_coordinates: EgressProofCoordinateSet | None,
        max_claim_to_send_bound_ms: int | None,
    ) -> EgressCurrentnessProof:
        """Build the (not-yet-appended) proof content — split out of"""
        result = (
            ProofResult.CURRENT if self._is_complete(vector) else ProofResult.UNKNOWN
        )
        coordinates = (
            egress_coordinates
            if egress_coordinates is not None
            else EgressProofCoordinateSet()
        )
        proof = EgressCurrentnessProof.issue(
            scheme=self._scheme,
            proof_id=f"ecp-{attempt.attempt_id}-{nonce[:12]}",
            nonce=nonce,
            single_use_consumed=False,
            is_expired=False,
            issue_revision=revision,
            vector_id=vector.vector_id,
            vector_digest=vector.canonical_digest,
            committed_revision=revision,
            bound_generations=bound_generations,
            restrictive_floors=restrictive_floors,
            egress_coordinates=coordinates,
            capability_claim_command=attempt.attempt_id,
            send_started_revision=revision,
            max_claim_to_send_bound_ms=max_claim_to_send_bound_ms,
            result=result,
        )
        assert isinstance(proof, EgressCurrentnessProof)
        return proof

    def _prepare_revision(self) -> tuple[int, CurrentnessRevision] | None:
        """Read the log tip and derive the revision THIS entry will commit"""
        view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        if not view.epoch:
            return None
        effective_seq = _effective_seq(view.last_seq)
        committed_seq = effective_seq + 1
        revision = CurrentnessRevision(
            revision_id=f"rev-{view.epoch}-{committed_seq}", commit_index=committed_seq
        )
        return effective_seq, revision

    def issue(
        self,
        attempt: AttemptRequest,
        vector: SafetyCurrentnessVector,
        *,
        bound_generations: tuple[int, ...] = (),
        restrictive_floors: tuple[int, ...] = (),
        egress_coordinates: EgressProofCoordinateSet | None = None,
        max_claim_to_send_bound_ms: int | None = None,
    ) -> EgressCurrentnessProof | None:
        """Issue one proof for ``attempt`` against ``vector``, durably record"""
        prepared = self._prepare_revision()
        if prepared is None:
            return None
        effective_seq, revision = prepared
        nonce = self._nonce_factory()
        proof = self._construct_proof(
            attempt,
            vector,
            revision=revision,
            nonce=nonce,
            bound_generations=bound_generations,
            restrictive_floors=restrictive_floors,
            egress_coordinates=egress_coordinates,
            max_claim_to_send_bound_ms=max_claim_to_send_bound_ms,
        )
        if not proof_admissible(proof):
            return None

        entry = CommitEntry(
            command_id=f"currentness-proof-nonce-{nonce}",
            command_digest=proof.canonical_digest,
            kind=_PROOF_ISSUANCE_KIND,
            payload_digest=proof.canonical_digest,
        )
        receipt = self._log.append_cas(
            entry, expected_seq=effective_seq, writer_epoch=self._writer_epoch
        )
        if isinstance(receipt, AppendRefusal):
            return None
        assert receipt.seq == effective_seq + 1

        self._issued[attempt.attempt_id] = proof
        return proof

    def item16_fields(self, attempt_id: str) -> Item16Fields:
        """``SendBoundaryContext`` item 16 fields for the proof last issued +"""
        proof = self._issued.get(attempt_id)
        if proof is None:
            return Item16Fields(
                egress_currentness_proof=None, egress_currentness_result=None
            )

        view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        current_seq = _effective_seq(view.last_seq)
        issued_seq = (
            proof.committed_revision.commit_index
            if proof.committed_revision is not None
            else None
        )
        if issued_seq is None or current_seq > issued_seq:
            proof = proof.model_copy(update={"is_expired": True})

        return Item16Fields(
            egress_currentness_proof=proof,
            egress_currentness_result=proof.result,
        )
