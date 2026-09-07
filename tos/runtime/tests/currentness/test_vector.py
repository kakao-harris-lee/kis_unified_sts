"""``CurrentnessAssembler`` tests (design #40 §5 order 6, lane R item 1)."""

from __future__ import annotations

from tos.authority import AuthorityEpochState
from tos.cur import DimensionKey, vector_complete
from tos.time import HealthState
from tos.workload import RuntimeIdentity
from tos_runtime.currentness.vector import (
    CurrentnessAssembler,
    SingleNodeCommitCertificate,
)
from tos_runtime.rcl.log import SqliteCommitLog

from .conftest import FakeTimeService, clean_snapshot


def _assembler(
    log: SqliteCommitLog,
    time_service: FakeTimeService,
    *,
    writer_epoch: int,
    policy,
    authority_epoch_reader=lambda: None,
    permit_seq_reader=lambda: None,
) -> CurrentnessAssembler:
    return CurrentnessAssembler(
        log,
        time_service,
        writer_epoch=writer_epoch,
        policy=policy,
        mandated=frozenset({DimensionKey.COMMIT_LOG, DimensionKey.TRUSTWORTHY_TIME}),
        authority_epoch_reader=authority_epoch_reader,
        permit_seq_reader=permit_seq_reader,
    )


# ============================================================================
# fault contract: non-TRUSTED time snapshot refuses vector assembly
# ============================================================================


def test_assemble_refuses_when_time_not_started(
    log: SqliteCommitLog,
    not_started_time_service: FakeTimeService,
    writer_epoch: int,
    complete_policy,
) -> None:
    assembler = _assembler(
        log, not_started_time_service, writer_epoch=writer_epoch, policy=complete_policy
    )
    assert assembler.assemble() is None


def test_assemble_refuses_when_time_snapshot_not_trusted(
    log: SqliteCommitLog,
    writer_epoch: int,
    complete_policy,
) -> None:
    time_service = FakeTimeService(
        snapshot=clean_snapshot(health_state=HealthState.UNTRUSTED)
    )
    assembler = _assembler(
        log, time_service, writer_epoch=writer_epoch, policy=complete_policy
    )
    assert assembler.assemble() is None


def test_assemble_refuses_when_no_epoch_acquired(
    log_path, evidence_port, trusted_time_service, complete_policy
) -> None:
    from tos.workload import RuntimeIdentity as _RI  # noqa: F401 (import kept local)

    unacquired_log = SqliteCommitLog(log_path, evidence_port=evidence_port)
    try:
        assembler = _assembler(
            unacquired_log, trusted_time_service, writer_epoch=0, policy=complete_policy
        )
        assert assembler.assemble() is None
        assert assembler.commit_certificate() is None
    finally:
        unacquired_log.close()


# ============================================================================
# successful assembly + kernel-predicate-judged completeness
# ============================================================================


def test_assemble_issues_a_digest_verified_vector(
    log: SqliteCommitLog,
    trusted_time_service: FakeTimeService,
    writer_epoch: int,
    complete_policy,
) -> None:
    assembler = _assembler(
        log, trusted_time_service, writer_epoch=writer_epoch, policy=complete_policy
    )
    vector = assembler.assemble()
    assert vector is not None
    assert vector.canonical_digest is not None
    dimension_keys = {d.dimension_key for d in vector.dimensions}
    assert DimensionKey.COMMIT_LOG in dimension_keys
    assert DimensionKey.TRUSTWORTHY_TIME in dimension_keys


def test_narrow_mandate_is_floored_up_by_the_kernel_and_still_fails(
    log: SqliteCommitLog,
    trusted_time_service: FakeTimeService,
    writer_epoch: int,
    complete_policy,
) -> None:
    """``vector_complete`` floors its ``mandated`` argument to at least
    ``MANDATED_DIMENSION_FLOOR`` regardless of what the caller asks for (§5.1
    v1.1 MINOR-1: "a caller may require more but never fewer") — so even a
    policy that declares only the two dimensions this lane can supply, and a
    mandate that asks for only those two, still fails, because the kernel
    silently widens the mandate to the full ~21-member floor. This is the
    correct, honest behavior — ``is_complete`` is a thin call-through and
    must agree with the kernel exactly, never a local override that appears
    to "achieve" completeness the kernel itself would refuse."""
    assembler = _assembler(
        log, trusted_time_service, writer_epoch=writer_epoch, policy=complete_policy
    )
    vector = assembler.assemble()
    assert vector is not None
    assert assembler.is_complete(vector) is False
    assert (
        vector_complete(
            vector,
            complete_policy,
            frozenset({DimensionKey.COMMIT_LOG, DimensionKey.TRUSTWORTHY_TIME}),
        )
        is False
    )


def test_vector_is_honestly_incomplete_under_the_full_mandated_floor(
    log: SqliteCommitLog,
    trusted_time_service: FakeTimeService,
    writer_epoch: int,
    full_floor_policy,
) -> None:
    """This lane owns only a few of the ~20 §9 dimensions — the assembled
    vector legitimately fails ``vector_complete`` against the real mandated
    floor until the owning lanes are composed in (module docstring)."""
    assembler = _assembler(
        log, trusted_time_service, writer_epoch=writer_epoch, policy=full_floor_policy
    )
    vector = assembler.assemble()
    assert vector is not None
    assert assembler.is_complete(vector) is False


def test_extra_dimensions_are_included_in_the_assembled_vector(
    log: SqliteCommitLog,
    trusted_time_service: FakeTimeService,
    writer_epoch: int,
    complete_policy,
) -> None:
    from tos.cur import CurrentnessDimension, CurrentnessRevision

    extra = CurrentnessDimension(
        dimension_key=DimensionKey.EGRESS_IDENTITY,
        owner_identity="test-owner",
        bound_generation=1,
        bound_digest="d",
        restrictive_floor=0,
        positively_established=True,
        at_revision=CurrentnessRevision(revision_id="rev-x", commit_index=0),
    )
    assembler = _assembler(
        log, trusted_time_service, writer_epoch=writer_epoch, policy=complete_policy
    )
    vector = assembler.assemble(extra_dimensions=(extra,))
    assert vector is not None
    assert DimensionKey.EGRESS_IDENTITY in {d.dimension_key for d in vector.dimensions}


# ============================================================================
# item3_fields — commitment_epoch_current via the kernel predicate only
# ============================================================================


def test_item3_fields_reports_current_when_epoch_matches(
    log: SqliteCommitLog,
    trusted_time_service: FakeTimeService,
    writer_epoch: int,
    complete_policy,
) -> None:
    assembler = _assembler(
        log, trusted_time_service, writer_epoch=writer_epoch, policy=complete_policy
    )
    fields = assembler.item3_fields()
    assert fields.commitment_epoch_current is True


def test_item3_fields_reports_not_current_after_a_newer_epoch_is_acquired(
    log: SqliteCommitLog,
    trusted_time_service: FakeTimeService,
    writer_epoch: int,
    identity: RuntimeIdentity,
    complete_policy,
) -> None:
    stale_epoch = writer_epoch
    log.acquire_epoch(identity)  # advances current_epoch() past stale_epoch
    assembler = _assembler(
        log, trusted_time_service, writer_epoch=stale_epoch, policy=complete_policy
    )
    fields = assembler.item3_fields()
    assert fields.commitment_epoch_current is False


# ============================================================================
# commit_certificate — never a QuorumCommitCertificate
# ============================================================================


def test_commit_certificate_is_a_single_node_certificate_never_a_quorum_one(
    log: SqliteCommitLog,
    trusted_time_service: FakeTimeService,
    writer_epoch: int,
    complete_policy,
) -> None:
    assembler = _assembler(
        log, trusted_time_service, writer_epoch=writer_epoch, policy=complete_policy
    )
    certificate = assembler.commit_certificate()
    assert certificate is not None
    assert isinstance(certificate, SingleNodeCommitCertificate)
    assert type(certificate).__name__ != "QuorumCommitCertificate"
    assert certificate.writer_epoch == writer_epoch
    assert certificate.digest is not None


# ============================================================================
# injected authority-epoch / permit-seq readers wire into the vector
# ============================================================================


def test_authority_epoch_reader_contributes_a_safety_authority_dimension(
    log: SqliteCommitLog,
    trusted_time_service: FakeTimeService,
    writer_epoch: int,
    complete_policy,
) -> None:
    state = AuthorityEpochState(authority_domain="TRADING", current_epoch_floor=3)
    assembler = _assembler(
        log,
        trusted_time_service,
        writer_epoch=writer_epoch,
        policy=complete_policy,
        authority_epoch_reader=lambda: state,
    )
    vector = assembler.assemble()
    assert vector is not None
    keys = {d.dimension_key for d in vector.dimensions}
    assert DimensionKey.SAFETY_AUTHORITY in keys


def test_permit_seq_reader_contributes_an_action_flow_dimension(
    log: SqliteCommitLog,
    trusted_time_service: FakeTimeService,
    writer_epoch: int,
    complete_policy,
) -> None:
    assembler = _assembler(
        log,
        trusted_time_service,
        writer_epoch=writer_epoch,
        policy=complete_policy,
        permit_seq_reader=lambda: 7,
    )
    vector = assembler.assemble()
    assert vector is not None
    keys = {d.dimension_key for d in vector.dimensions}
    assert DimensionKey.ACTION_FLOW in keys
