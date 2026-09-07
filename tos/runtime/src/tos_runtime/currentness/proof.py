"""``EgressCurrentnessProofIssuer`` — per-attempt Egress Currentness Proof issuance.

Design #40 §5 order 6, lane R item 2
(`docs/plans/2026-09-08-tos-phase2-runtime-slice3-authority-risk-currentness-
compose-plan.md` §3 item 2). Realizes ``issue_egress_currentness_proof(attempt)``:
the nonce is a real random token (``secrets.token_hex``), the ``committed_
revision`` is the RCL ``last_seq`` observed **at issue time**, the issuance
itself is a durable RCL entry (so a later revision advance can revoke it —
see :meth:`EgressCurrentnessProofIssuer.item16_fields`), and the issuer never
returns a *freshly issued* proof it has not first self-checked with
``proof_admissible``.

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

**Review fix (independent review of 39dd3993, HIGH-1/HIGH-2).**

* HIGH-1: a proof's ``committed_revision`` is a snapshot written once at
  issue time and never re-read — so a naive accessor that just replays the
  stored object would let a proof outlive the RCL revision it was issued
  against, silently defeating the "revocation by revision advance" fault
  contract. :meth:`EgressCurrentnessProofIssuer.item16_fields` now re-reads
  the log's *current* ``last_seq`` on every call and, if it has advanced past
  the proof's ``committed_revision``, returns a ``model_copy`` with
  ``is_expired=True`` (never ``None``): the proof stays visible for evidence
  / audit (a caller can still see *which* proof was denied and why), but
  ``proof_admissible`` on that copy refuses (``is_expired`` is excluded from
  the covered digest, §2.3 — the ``tos_runtime.time.service`` anchor-ratchet
  precedent for mutating a non-covered lifecycle field via ``model_copy``).
* HIGH-2: :meth:`EgressCurrentnessProofIssuer.issue` no longer accepts a free
  ``result``/``vector_id``/``vector_digest`` from the caller — a caller could
  otherwise assert ``CURRENT`` for an incomplete or unrelated vector and
  item 16 would honor it. It now takes the actual
  :class:`~tos.cur.SafetyCurrentnessVector` and derives ``vector_id``/
  ``vector_digest`` from it, and derives ``result`` from the injected
  ``is_complete`` callable (``tos_runtime.currentness.vector.
  CurrentnessAssembler.is_complete`` in production —
  :func:`~tos.cur.predicates.vector_complete` underneath, never re-derived
  here): ``CURRENT`` only when ``is_complete(vector)`` is ``True``, else
  ``ProofResult.UNKNOWN`` (never ``RESTRICTED`` — this issuer holds no
  restrictive-floor breach evidence of its own, so ``UNKNOWN`` is the honest
  member; §6 CUR-INV-011 "Unknown ... blocks new risk"). Because
  ``vector_complete`` floors the mandate to
  ``MANDATED_DIMENSION_FLOOR`` (~21 dimensions, §5.1 v1.1 MINOR-1) regardless
  of what is passed in, a ``CURRENT`` result is reachable **only** once the
  composition root supplies every mandated dimension this lane alone cannot
  (spg profile, deviation, incident, monitoring, release, post-trade,
  critical input, context, constraint, construction, trading approval,
  aggregate risk, egress identity — ``tos_runtime.currentness.vector``'s own
  module docstring lists the same set) — this module does **not** weaken
  that floor to make ``CURRENT`` easier to reach.
* LOW-C (addendum): :meth:`EgressCurrentnessProofIssuer.issue` used to append
  the durable RCL entry *before* the ``proof_admissible`` self-check, so a
  refused candidate (e.g. an incomplete vector, or an unclear latch) still
  burned a durable ``AUTHORIZE_TRANSMISSION_CAPABILITY`` entry and consumed
  its nonce. The self-check now runs on the candidate proof first; only an
  admissible candidate ever reaches ``append_cas``.
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
    SafetyCurrentnessVector,
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


def _effective_seq(last_seq: int | None) -> int:
    """The log's own "empty" sentinel (``-1``, ``SqliteCommitLog.append_cas``'s
    own ``expected_seq=-1`` convention) — a concrete, ORDERED value rather
    than ``None``, matching ``tos_runtime.currentness.vector``'s own
    convention so the two modules' revisions compare consistently."""
    return -1 if last_seq is None else last_seq


class EgressCurrentnessProofIssuer:
    """Issues + durably records one :class:`~tos.cur.EgressCurrentnessProof`
    per attempt, and answers ``SendBoundaryContext`` item 16 for it later.

    Args:
        log: The injected RCL ``CommitLog`` port.
        writer_epoch: The Writer Epoch this process holds.
        is_complete: Whether a :class:`~tos.cur.SafetyCurrentnessVector` is
            complete — in production, ``CurrentnessAssembler.is_complete``
            (a thin call-through to :func:`~tos.cur.predicates.
            vector_complete`, module docstring HIGH-2); injected here rather
            than importing ``CurrentnessAssembler`` directly so a test can
            supply a trivial double without constructing a full assembler.
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
        """Build the (not-yet-appended) proof content — split out of
        :meth:`issue` to stay under the module size budget. ``result`` is
        derived from ``self._is_complete(vector)`` (module docstring HIGH-2),
        never a caller-supplied claim."""
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
        """Read the log tip and derive the revision THIS entry will commit
        at — split out of :meth:`issue` to stay under the module size
        budget.

        `effective_seq` is the tip AS OBSERVED (pre-append) — the CAS fence
        for this entry's own append. The proof's ``committed_revision`` must
        instead name the seq THIS ENTRY ITSELF lands at (``effective_seq +
        1``), not the pre-append tip, or :meth:`item16_fields`'
        revocation-by-advance check would see the proof's own append as an
        "advance past" its own revision and revoke it immediately, on the
        very next read (independent review of 39dd3993, HIGH-1 follow-up).

        Returns:
            ``(effective_seq, revision)``, or ``None`` when no Writer Epoch
            has been acquired.
        """
        view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        if (
            not view.epoch
        ):  # None or 0 (unacquired sentinel, tos_runtime.rcl.log.SqliteCommitLog.current_epoch)
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
        """Issue one proof for ``attempt`` against ``vector``, durably record
        it, and self-check it with :func:`~tos.cur.predicates.proof_admissible`
        before returning.

        ``vector_id``/``vector_digest``/``result`` are never free caller
        inputs (module docstring HIGH-2): ``vector_id``/``vector_digest`` are
        read off ``vector`` itself, and ``result`` is derived from the
        injected ``is_complete(vector)``. The admissibility self-check runs
        on the CANDIDATE proof *before* any durable RCL append (LOW-C) — a
        refused proof never burns a durable entry or its nonce.

        Args:
            attempt: The bound :class:`~tos.engine.records.AttemptRequest`
                (step 12's own artifact) this proof is issued for.
            vector: The :class:`~tos.cur.SafetyCurrentnessVector` this proof
                attests against.
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
            Epoch has been acquired, the candidate fails its own
            ``proof_admissible`` self-check (e.g. ``vector`` is incomplete,
            so ``result`` is ``UNKNOWN`` not ``CURRENT``, or
            ``egress_coordinates.local_latch_clear`` is not positively
            ``True``), or the durable RCL append is refused.
        """
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
            entry, expected_seq=effective_seq, writer_epoch=self._writer_epoch
        )
        if isinstance(receipt, AppendRefusal):
            return None
        # The CAS fence guarantees this entry landed exactly where predicted —
        # a defensive re-assertion, not a trust boundary (a mismatch here
        # would mean the CAS fence itself is broken, a lower-layer defect).
        assert receipt.seq == effective_seq + 1

        self._issued[attempt.attempt_id] = proof
        return proof

    def item16_fields(self, attempt_id: str) -> Item16Fields:
        """``SendBoundaryContext`` item 16 fields for the proof last issued +
        admitted for ``attempt_id``.

        Re-reads the log's *current* ``last_seq`` on every call (never trusts
        the proof's own stored ``committed_revision`` as still current —
        module docstring HIGH-1): if the log has advanced past the revision
        the proof was issued against, the returned proof is a ``model_copy``
        with ``is_expired=True`` (excluded from the covered digest, §2.3, so
        this does not forge the digest-bound artifact) — ``proof_admissible``
        on that copy refuses. The proof is still returned (never collapsed to
        ``None``) so a consumer can see *which* proof was revoked and why,
        preserving the evidence trail rather than erasing it.

        Returns:
            ``Item16Fields`` with both fields ``None`` if nothing was issued
            (or admitted) for ``attempt_id``.
        """
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
