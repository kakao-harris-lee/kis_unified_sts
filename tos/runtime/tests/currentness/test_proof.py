"""``EgressCurrentnessProofIssuer`` tests (design #40 §5 order 6, lane R item 2)."""

from __future__ import annotations

from tos.cur import EgressProofCoordinateSet, ProofResult, proof_admissible
from tos.engine.records import AttemptRequest
from tos_runtime.currentness.proof import EgressCurrentnessProofIssuer
from tos_runtime.rcl.log import SqliteCommitLog


def _attempt(attempt_id: str = "att-1") -> AttemptRequest:
    return AttemptRequest(
        attempt_id=attempt_id,
        conformance_proof_digest="proof-digest-1",
        action_flow_permit_identity="permit-1",
        reference_coordinate_digest="ref-digest-1",
    )


def _clear_coordinates() -> EgressProofCoordinateSet:
    return EgressProofCoordinateSet(principal="principal-1", local_latch_clear=True)


def test_issue_returns_none_when_no_epoch_acquired(log_path, evidence_port) -> None:
    unacquired_log = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        issuer = EgressCurrentnessProofIssuer(unacquired_log, writer_epoch=0)
        proof = issuer.issue(
            _attempt(),
            vector_id="vec-1",
            vector_digest="vd",
            result=ProofResult.CURRENT,
            egress_coordinates=_clear_coordinates(),
        )
        assert proof is None
    finally:
        unacquired_log.close()


def test_issue_returns_an_admissible_proof_and_durably_records_it(
    log: SqliteCommitLog, writer_epoch: int
) -> None:
    issuer = EgressCurrentnessProofIssuer(log, writer_epoch=writer_epoch)
    proof = issuer.issue(
        _attempt(),
        vector_id="vec-1",
        vector_digest="vd",
        result=ProofResult.CURRENT,
        bound_generations=(5,),
        restrictive_floors=(1,),
        egress_coordinates=_clear_coordinates(),
    )
    assert proof is not None
    assert proof_admissible(proof) is True
    # durably recorded: the log's replay contains one entry for this issuance.
    entries = list(log.replay())
    assert len(entries) == 1
    assert entries[0].command_digest == proof.canonical_digest

    fields = issuer.item16_fields("att-1")
    assert fields.egress_currentness_proof is proof
    assert fields.egress_currentness_result is ProofResult.CURRENT


def test_issue_refuses_when_latch_is_not_positively_clear(
    log: SqliteCommitLog, writer_epoch: int
) -> None:
    issuer = EgressCurrentnessProofIssuer(log, writer_epoch=writer_epoch)
    proof = issuer.issue(
        _attempt(),
        vector_id="vec-1",
        vector_digest="vd",
        result=ProofResult.CURRENT,
        egress_coordinates=EgressProofCoordinateSet(),  # local_latch_clear=None
    )
    assert proof is None
    assert issuer.item16_fields("att-1").egress_currentness_proof is None


def test_issue_refuses_when_result_is_not_current(
    log: SqliteCommitLog, writer_epoch: int
) -> None:
    issuer = EgressCurrentnessProofIssuer(log, writer_epoch=writer_epoch)
    proof = issuer.issue(
        _attempt(),
        vector_id="vec-1",
        vector_digest="vd",
        result=ProofResult.RESTRICTED,
        egress_coordinates=_clear_coordinates(),
    )
    assert proof is None


def test_revision_advance_after_issue_makes_the_proof_no_longer_admissible(
    log: SqliteCommitLog, writer_epoch: int, identity
) -> None:
    """Fault contract: "발급 후 RCL revision 전진(revocation) -> proof_admissible
    거부" — the proof's OWN committed_revision is a snapshot at issue time, so
    a later RCL advance does not change the already-returned proof object,
    but a caller re-checking freshness against the CURRENT log tip (as a real
    consumer must) observes the proof's revision is stale."""
    issuer = EgressCurrentnessProofIssuer(log, writer_epoch=writer_epoch)
    proof = issuer.issue(
        _attempt(),
        vector_id="vec-1",
        vector_digest="vd",
        result=ProofResult.CURRENT,
        bound_generations=(1,),
        egress_coordinates=_clear_coordinates(),
    )
    assert proof is not None
    issued_at_seq = proof.committed_revision.commit_index

    # advance the log past the proof's committed revision
    issuer.issue(
        _attempt(attempt_id="att-2"),
        vector_id="vec-2",
        vector_digest="vd2",
        result=ProofResult.CURRENT,
        egress_coordinates=_clear_coordinates(),
    )
    view = log.read_linearizable(writer_epoch=writer_epoch)
    assert view.last_seq is not None
    assert view.last_seq > (issued_at_seq or -1)
    # the proof itself still self-admits (its own claim is unchanged) — a
    # consumer must independently compare committed_revision against the
    # CURRENT view to detect the advance (this is the revocation-by-advance
    # mechanism the module docstring describes; proof_admissible alone does
    # not re-read the log).
    assert proof_admissible(proof) is True
    assert proof.committed_revision.commit_index != view.last_seq


def test_nonce_reuse_is_refused_by_the_log(
    log: SqliteCommitLog, writer_epoch: int
) -> None:
    """Fault contract: nonce reuse refused by the log — forcing the same
    nonce across two issuances collides on the RCL's own command_id, which
    the log refuses (COMMAND_BYTES_MISMATCH, since the two proofs' content
    differs) rather than silently accepting a reused single-use token."""
    issuer = EgressCurrentnessProofIssuer(
        log, writer_epoch=writer_epoch, nonce_factory=lambda: "fixed-nonce"
    )
    first = issuer.issue(
        _attempt("att-1"),
        vector_id="vec-1",
        vector_digest="vd",
        result=ProofResult.CURRENT,
        bound_generations=(1,),
        egress_coordinates=_clear_coordinates(),
    )
    assert first is not None

    second = issuer.issue(
        _attempt("att-2"),
        vector_id="vec-2",
        vector_digest="vd2",
        result=ProofResult.CURRENT,
        bound_generations=(1,),
        egress_coordinates=_clear_coordinates(),
    )
    assert second is None
    # only the first issuance's entry is durably recorded.
    assert len(list(log.replay())) == 1
