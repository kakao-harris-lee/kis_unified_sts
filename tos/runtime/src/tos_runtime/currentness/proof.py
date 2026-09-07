"""``EgressCurrentnessProofIssuer`` — per-attempt Egress Currentness Proof issuance.

Design #40 §5 order 6, lane R item 2
(`docs/plans/2026-09-08-tos-phase2-runtime-slice3-authority-risk-currentness-
compose-plan.md` §3 item 2). Realizes ``issue_egress_currentness_proof(attempt)``:
the nonce is a real random token (``secrets.token_hex``), the ``committed_
revision`` is the RCL ``last_seq`` observed **at issue time**, the issuance
itself is a durable RCL entry (so a later revision advance can revoke it by
making :func:`~tos.cur.predicates.proof_admissible` observe a stale
``committed_revision``), and the issuer never returns a proof it has not
first self-checked with ``proof_admissible``.

**Reported gap, not a silent invention (slice plan §5 "새 CommandType 이
필요하면 커널 편집 대신 보고").** No ``tos.rcl.CommandType`` member names
"issue an Egress Currentness Proof" — ``tos.cur`` (ADR-002-024) is not among
the 16 ADR-002-012 §10 / ADR-002-002 §27 commands the closed enum
enumerates, and the register's own module docstring frames the enum as a
"semantic-equivalence" vocabulary, not a closed literal one (ADR-012 §10 line
292). ``AUTHORIZE_TRANSMISSION_CAPABILITY`` is reused here as the nearest
existing label: both this proof and the real ``TransmissionCapability``
record (:mod:`tos_runtime.currentness.stages`) are per-attempt send-boundary
authorization facts that gate the same ``SendBoundaryContext``. The two
remain distinguishable by ``command_id``/``payload_digest`` — never by
``kind`` alone. A dedicated ``CommandType`` member is the more precise fix;
this module does not add one (kernel edit is out of this lane's scope).
"""

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
    proof_admissible,
)
from tos.engine.records import AttemptRequest
from tos.rcl import AppendRefusal, CommandType, CommitEntry
from tos.rcl.commitlog import CommitLog, WriterEpoch

__all__ = ["EgressCurrentnessProofIssuer", "Item16Fields"]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: See the module docstring's "Reported gap" note.
_PROOF_ISSUANCE_KIND = CommandType.AUTHORIZE_TRANSMISSION_CAPABILITY


@dataclass(frozen=True)
class Item16Fields:
    """``SendBoundaryContext`` item 16 (currentness) — the two fields this
    lane owns.

    ``restrictive_latch_state``/``worst_credible_capacity`` are deliberately
    excluded: the Local Restrictive Latch state machine is egress-owned
    (``tos.cur.__init__`` "Local Restrictive Latch stays egress-owned... cur
    consumes the resolved latch as an injected bool") and this lane takes no
    ``tos.egress`` import (out of lane R's assigned scope, per the slice plan
    §3 item split). The composition root wires those two fields from the
    egress lane directly.
    """

    egress_currentness_proof: EgressCurrentnessProof | None
    egress_currentness_result: ProofResult | None


class EgressCurrentnessProofIssuer:
    """Issues + durably records one :class:`~tos.cur.EgressCurrentnessProof`
    per attempt, and answers ``SendBoundaryContext`` item 16 for it later.

    Args:
        log: The injected RCL ``CommitLog`` port.
        writer_epoch: The Writer Epoch this process holds.
        scheme: The canonicalization scheme.
        nonce_factory: Produces the per-issuance nonce — defaults to
            ``secrets.token_hex(16)`` (a real random token). Overridable only
            so a test can force a nonce collision and observe the RCL log's
            own duplicate-command refusal (fault contract "nonce reuse
            refused by the log"); production callers should never override
            this.
    """

    def __init__(
        self,
        log: CommitLog,
        *,
        writer_epoch: WriterEpoch,
        scheme: CanonicalizationScheme = _SCHEME,
        nonce_factory: Callable[[], str] = lambda: secrets.token_hex(16),
    ) -> None:
        self._log = log
        self._writer_epoch = writer_epoch
        self._scheme = scheme
        self._nonce_factory = nonce_factory
        self._issued: dict[str, EgressCurrentnessProof] = {}

    def issue(
        self,
        attempt: AttemptRequest,
        *,
        vector_id: str,
        vector_digest: str,
        result: ProofResult,
        bound_generations: tuple[int, ...] = (),
        restrictive_floors: tuple[int, ...] = (),
        egress_coordinates: EgressProofCoordinateSet | None = None,
        max_claim_to_send_bound_ms: int | None = None,
    ) -> EgressCurrentnessProof | None:
        """Issue one proof for ``attempt``, durably record it, and self-check
        it with :func:`~tos.cur.predicates.proof_admissible` before returning.

        Args:
            attempt: The bound :class:`~tos.engine.records.AttemptRequest`
                (step 12's own artifact) this proof is issued for.
            vector_id: The complete :class:`~tos.cur.SafetyCurrentnessVector`
                this proof attests against.
            vector_digest: That vector's ``canonical_digest``.
            result: The conformance result the *caller* establishes (this
                issuer does not decide currentness itself — see the module
                docstring; only ``ProofResult.CURRENT`` can ever be
                admissible, per ``proof_admissible``).
            bound_generations: Per-owner bound generations (§12 line 308).
            restrictive_floors: Per-owner restrictive floors (§12 line 308).
            egress_coordinates: The injected egress-scope coordinate mirror,
                including the egress-owned ``local_latch_clear`` bool — a
                ``None``/default here (no positively-clear latch) makes the
                proof self-check fail, by design (fail-closed).
            max_claim_to_send_bound_ms: The injected Profile-INSTANCE bound
                (``B_capability_claim_to_send``, VER-002 — null in Phase 2).

        Returns:
            The issued, self-admissible proof, or ``None`` when: no Writer
            Epoch has been acquired, the durable RCL append is refused, or
            the freshly-issued proof fails its own ``proof_admissible``
            self-check (e.g. ``egress_coordinates.local_latch_clear`` is not
            positively ``True``).
        """
        view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        if (
            not view.epoch
        ):  # None or 0 (unacquired sentinel, tos_runtime.rcl.log.SqliteCommitLog.current_epoch)
            return None
        last_seq = view.last_seq
        revision = CurrentnessRevision(
            revision_id=f"rev-{view.epoch}-{last_seq}", commit_index=last_seq
        )

        nonce = self._nonce_factory()
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
            vector_id=vector_id,
            vector_digest=vector_digest,
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

        expected_seq = -1 if last_seq is None else last_seq
        entry = CommitEntry(
            # The RCL idempotency key is the NONCE itself, not the proof id —
            # single-use is enforced by the log's own command_id UNIQUE
            # constraint (fault contract "nonce reuse refused by the log"),
            # mirroring how tos.rcl.log's own module docstring describes
            # TransmissionCapability nonce single-use enforcement.
            command_id=f"currentness-proof-nonce-{nonce}",
            command_digest=proof.canonical_digest,
            kind=_PROOF_ISSUANCE_KIND,
            payload_digest=proof.canonical_digest,
        )
        receipt = self._log.append_cas(
            entry, expected_seq=expected_seq, writer_epoch=self._writer_epoch
        )
        if isinstance(receipt, AppendRefusal):
            return None

        if not proof_admissible(proof):
            return None

        self._issued[attempt.attempt_id] = proof
        return proof

    def item16_fields(self, attempt_id: str) -> Item16Fields:
        """``SendBoundaryContext`` item 16 fields for the proof last issued +
        admitted for ``attempt_id`` (``None``/``None`` if none was, or the
        issued one failed its self-check and was refused)."""
        proof = self._issued.get(attempt_id)
        return Item16Fields(
            egress_currentness_proof=proof,
            egress_currentness_result=proof.result if proof is not None else None,
        )
