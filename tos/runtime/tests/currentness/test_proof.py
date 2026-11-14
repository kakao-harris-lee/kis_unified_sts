"""``EgressCurrentnessProofIssuer`` tests (design #40 §5 order 6, lane R item 2)."""

from __future__ import annotations

from tos.cur import (
    MANDATED_DIMENSION_FLOOR,
    CurrentnessDimension,
    DimensionKey,
    EgressProofCoordinateSet,
    ProofResult,
    SafetyCurrentnessVector,
    proof_admissible,
)
from tos.engine.records import AttemptRequest
from tos_runtime.currentness.proof import EgressCurrentnessProofIssuer
from tos_runtime.currentness.vector import CurrentnessAssembler
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


def _partial_vector(
    log: SqliteCommitLog, writer_epoch: int, policy
) -> SafetyCurrentnessVector:
    """A vector this lane alone can assemble (2 of the ~21 mandated"""
    from .conftest import FakeTimeService, clean_snapshot

    assembler = CurrentnessAssembler(
        log,
        FakeTimeService(snapshot=clean_snapshot()),
        writer_epoch=writer_epoch,
        policy=policy,
        mandated=frozenset({DimensionKey.COMMIT_LOG, DimensionKey.TRUSTWORTHY_TIME}),
        dimension_readers={},
    )
    vector = assembler.assemble()
    assert vector is not None
    return vector


def _seed_one_entry(log: SqliteCommitLog, writer_epoch: int) -> None:
    """Durably commit one arbitrary entry so the log is no longer empty —"""
    from tos.rcl import AppendReceipt, CommandType, CommitEntry

    receipt = log.append_cas(
        CommitEntry(
            command_id="seed-1",
            command_digest="seed-digest",
            kind=CommandType.COMMIT_RESERVATION,
        ),
        expected_seq=-1,
        writer_epoch=writer_epoch,
    )
    assert isinstance(receipt, AppendReceipt)


def _bare_vector() -> SafetyCurrentnessVector:
    """A minimally-issued vector — content is irrelevant for the tests that"""
    from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
    from tos.cur import CurrentnessRevision

    issued = SafetyCurrentnessVector.issue(
        scheme=get_scheme(EV_L1_PROVISIONAL_VERSION),
        vector_id="vec-bare",
        currentness_revision=CurrentnessRevision(
            revision_id="rev-bare", commit_index=0
        ),
        policy_id="pol-bare",
        policy_generation=1,
        vector_digest="vd-bare",
    )
    assert isinstance(issued, SafetyCurrentnessVector)
    return issued


def test_issue_returns_none_when_no_epoch_acquired(log_path, evidence_port) -> None:
    unacquired_log = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        issuer = EgressCurrentnessProofIssuer(
            unacquired_log, writer_epoch=0, is_complete=lambda _v: True
        )
        proof = issuer.issue(
            _attempt(),
            _bare_vector(),
            egress_coordinates=_clear_coordinates(),
        )
        assert proof is None
    finally:
        unacquired_log.close()


def test_issue_produces_current_result_and_admits_when_vector_is_complete(
    log: SqliteCommitLog, writer_epoch: int, complete_policy
) -> None:
    vector = _partial_vector(log, writer_epoch, complete_policy)
    issuer = EgressCurrentnessProofIssuer(
        log, writer_epoch=writer_epoch, is_complete=lambda _v: True
    )
    proof = issuer.issue(
        _attempt(),
        vector,
        bound_generations=(1,),
        egress_coordinates=_clear_coordinates(),
    )
    assert proof is not None
    assert proof.result is ProofResult.CURRENT
    assert proof.vector_id == vector.vector_id
    assert proof.vector_digest == vector.canonical_digest
    assert proof_admissible(proof) is True


def test_issue_uses_the_new_issue_egress_currentness_proof_command_type(
    log: SqliteCommitLog, writer_epoch: int, complete_policy
) -> None:
    """Kernel round #1 §1.1/§2.1: proof issuance writes under the dedicated"""
    from tos.rcl import CommandType

    vector = _partial_vector(log, writer_epoch, complete_policy)
    issuer = EgressCurrentnessProofIssuer(
        log, writer_epoch=writer_epoch, is_complete=lambda _v: True
    )
    proof = issuer.issue(
        _attempt(),
        vector,
        bound_generations=(1,),
        egress_coordinates=_clear_coordinates(),
    )
    assert proof is not None
    view = log.read_linearizable(writer_epoch=writer_epoch)
    kinds = {entry.kind for entry in view.entries if entry.command_id is not None}
    assert CommandType.ISSUE_EGRESS_CURRENTNESS_PROOF in kinds


def test_issue_produces_unknown_result_and_refuses_when_vector_is_incomplete(
    log: SqliteCommitLog, writer_epoch: int, complete_policy
) -> None:
    """``is_complete`` returning ``False`` (the honest case for any vector"""
    vector = _partial_vector(log, writer_epoch, complete_policy)
    issuer = EgressCurrentnessProofIssuer(
        log, writer_epoch=writer_epoch, is_complete=lambda _v: False
    )
    proof = issuer.issue(
        _attempt(),
        vector,
        bound_generations=(1,),
        egress_coordinates=_clear_coordinates(),
    )
    assert proof is None
    assert issuer.item16_fields("att-1").egress_currentness_proof is None


def test_issue_refuses_when_latch_is_not_positively_clear(
    log: SqliteCommitLog, writer_epoch: int, complete_policy
) -> None:
    vector = _partial_vector(log, writer_epoch, complete_policy)
    issuer = EgressCurrentnessProofIssuer(
        log, writer_epoch=writer_epoch, is_complete=lambda _v: True
    )
    proof = issuer.issue(
        _attempt(),
        vector,
        egress_coordinates=EgressProofCoordinateSet(),
    )
    assert proof is None
    assert list(log.replay()) == []


def test_issue_refuses_without_appending_when_result_is_unknown(
    log: SqliteCommitLog, writer_epoch: int, complete_policy
) -> None:
    """Same LOW-C guarantee for the (more common in Phase 2) UNKNOWN-result"""
    vector = _partial_vector(log, writer_epoch, complete_policy)
    issuer = EgressCurrentnessProofIssuer(
        log, writer_epoch=writer_epoch, is_complete=lambda _v: False
    )
    proof = issuer.issue(
        _attempt(),
        vector,
        bound_generations=(1,),
        egress_coordinates=_clear_coordinates(),
    )
    assert proof is None
    assert list(log.replay()) == []


def test_nonce_reuse_is_refused_by_the_log(
    log: SqliteCommitLog, writer_epoch: int, complete_policy
) -> None:
    """Fault contract: nonce reuse refused by the log — forcing the same"""
    vector = _partial_vector(log, writer_epoch, complete_policy)
    issuer = EgressCurrentnessProofIssuer(
        log,
        writer_epoch=writer_epoch,
        is_complete=lambda _v: True,
        nonce_factory=lambda: "fixed-nonce",
    )
    first = issuer.issue(
        _attempt("att-1"),
        vector,
        bound_generations=(1,),
        egress_coordinates=_clear_coordinates(),
    )
    assert first is not None

    second = issuer.issue(
        _attempt("att-2"),
        vector,
        bound_generations=(1,),
        egress_coordinates=_clear_coordinates(),
    )
    assert second is None
    assert len(list(log.replay())) == 1


def test_item16_fields_control_no_advance_is_admissible(
    log: SqliteCommitLog, writer_epoch: int, complete_policy
) -> None:
    vector = _partial_vector(log, writer_epoch, complete_policy)
    issuer = EgressCurrentnessProofIssuer(
        log, writer_epoch=writer_epoch, is_complete=lambda _v: True
    )
    proof = issuer.issue(
        _attempt("att-1"),
        vector,
        bound_generations=(1,),
        egress_coordinates=_clear_coordinates(),
    )
    assert proof is not None

    fields = issuer.item16_fields("att-1")
    assert fields.egress_currentness_proof is not None
    assert fields.egress_currentness_proof.is_expired is False
    assert proof_admissible(fields.egress_currentness_proof) is True


def test_item16_fields_revokes_after_the_log_advances(
    log: SqliteCommitLog, writer_epoch: int, complete_policy
) -> None:
    vector = _partial_vector(log, writer_epoch, complete_policy)
    issuer = EgressCurrentnessProofIssuer(
        log, writer_epoch=writer_epoch, is_complete=lambda _v: True
    )
    proof = issuer.issue(
        _attempt("att-1"),
        vector,
        bound_generations=(1,),
        egress_coordinates=_clear_coordinates(),
    )
    assert proof is not None
    assert proof.is_expired is False

    second_vector = _partial_vector(log, writer_epoch, complete_policy)
    second = issuer.issue(
        _attempt("att-2"),
        second_vector,
        bound_generations=(1,),
        egress_coordinates=_clear_coordinates(),
    )
    assert second is not None

    fields = issuer.item16_fields("att-1")
    assert fields.egress_currentness_proof is not None
    assert fields.egress_currentness_proof.is_expired is True
    assert proof_admissible(fields.egress_currentness_proof) is False
    assert fields.egress_currentness_result is ProofResult.CURRENT
    assert proof.is_expired is False


def test_a_fully_populated_vector_reaches_current_and_is_admissible(
    log: SqliteCommitLog, writer_epoch: int, full_floor_policy
) -> None:
    """Proves the CURRENT path is actually reachable, not merely injectable:"""
    from .conftest import FakeTimeService, clean_snapshot

    _seed_one_entry(log, writer_epoch)
    assembler = CurrentnessAssembler(
        log,
        FakeTimeService(snapshot=clean_snapshot()),
        writer_epoch=writer_epoch,
        policy=full_floor_policy,
        mandated=frozenset({DimensionKey.COMMIT_LOG, DimensionKey.TRUSTWORTHY_TIME}),
        dimension_readers={},
    )
    partial = assembler.assemble()
    assert partial is not None
    revision = partial.currentness_revision

    remaining = MANDATED_DIMENSION_FLOOR - {
        DimensionKey.COMMIT_LOG,
        DimensionKey.TRUSTWORTHY_TIME,
    }
    extra = tuple(
        CurrentnessDimension(
            dimension_key=key,
            owner_identity=f"test-owner-{key.value}",
            bound_generation=1,
            bound_digest=f"digest-{key.value}",
            restrictive_floor=0,
            positively_established=True,
            at_revision=revision,
        )
        for key in remaining
    )
    complete_vector = assembler.assemble(extra_dimensions=extra)
    assert complete_vector is not None
    assert assembler.is_complete(complete_vector) is True

    issuer = EgressCurrentnessProofIssuer(
        log, writer_epoch=writer_epoch, is_complete=assembler.is_complete
    )
    proof = issuer.issue(
        _attempt("att-full"),
        complete_vector,
        bound_generations=(1,),
        egress_coordinates=_clear_coordinates(),
    )
    assert proof is not None
    assert proof.result is ProofResult.CURRENT
    assert proof_admissible(proof) is True

    fields = issuer.item16_fields("att-full")
    assert fields.egress_currentness_result is ProofResult.CURRENT
    assert proof_admissible(fields.egress_currentness_proof) is True
