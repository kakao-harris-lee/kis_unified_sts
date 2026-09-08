"""``CurrentnessAssembler`` tests (design #40 §5 order 6, lane R item 1).

Covers the independent review fix of 39dd3993 (MEDIUM-A: owner verdicts are
copied via ``DimensionReport``, never authored by this assembler; MEDIUM-B:
an empty log is honestly not-established, never a ``-1`` placeholder).
"""

from __future__ import annotations

from tos.cur import MANDATED_DIMENSION_FLOOR, DimensionKey, vector_complete
from tos.time import HealthState
from tos.workload import RuntimeIdentity
from tos_runtime.currentness.vector import (
    CurrentnessAssembler,
    DimensionReport,
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
    authority_dimension_reader=lambda: None,
    action_flow_dimension_reader=lambda: None,
) -> CurrentnessAssembler:
    return CurrentnessAssembler(
        log,
        time_service,
        writer_epoch=writer_epoch,
        policy=policy,
        mandated=frozenset({DimensionKey.COMMIT_LOG, DimensionKey.TRUSTWORTHY_TIME}),
        authority_dimension_reader=authority_dimension_reader,
        action_flow_dimension_reader=action_flow_dimension_reader,
    )


def _seed_one_entry(log: SqliteCommitLog, writer_epoch: int) -> None:
    """Durably commit one arbitrary entry so the log is no longer empty —
    used by tests that need COMMIT_LOG genuinely established (MEDIUM-B)."""
    from tos.rcl import CommandType, CommitEntry

    receipt = log.append_cas(
        CommitEntry(
            command_id="seed-1",
            command_digest="seed-digest",
            kind=CommandType.COMMIT_RESERVATION,
        ),
        expected_seq=-1,
        writer_epoch=writer_epoch,
    )
    from tos.rcl import AppendReceipt

    assert isinstance(receipt, AppendReceipt)


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
# MEDIUM-B: an empty log is honestly not-established, never a -1 placeholder
# ============================================================================


def test_commit_log_dimension_is_not_established_on_an_empty_log(
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
    commit_log_dim = next(
        d for d in vector.dimensions if d.dimension_key is DimensionKey.COMMIT_LOG
    )
    assert commit_log_dim.positively_established is False
    assert commit_log_dim.bound_generation is None


def test_commit_log_dimension_is_established_once_something_is_committed(
    log: SqliteCommitLog,
    trusted_time_service: FakeTimeService,
    writer_epoch: int,
    complete_policy,
) -> None:
    _seed_one_entry(log, writer_epoch)
    assembler = _assembler(
        log, trusted_time_service, writer_epoch=writer_epoch, policy=complete_policy
    )
    vector = assembler.assemble()
    assert vector is not None
    commit_log_dim = next(
        d for d in vector.dimensions if d.dimension_key is DimensionKey.COMMIT_LOG
    )
    assert commit_log_dim.positively_established is True
    assert commit_log_dim.bound_generation == 0


def test_an_empty_log_never_yields_a_complete_vector_even_with_every_other_dimension_present(
    log: SqliteCommitLog,
    trusted_time_service: FakeTimeService,
    writer_epoch: int,
    full_floor_policy,
) -> None:
    """Synthesizes every other mandated dimension (as the "reachability"
    test in test_proof.py does) but does NOT seed the log — COMMIT_LOG alone
    must keep the vector incomplete, proving the empty-log fix is not a
    no-op next to the other 20 dimensions."""
    from tos.cur import CurrentnessDimension

    assembler = _assembler(
        log, trusted_time_service, writer_epoch=writer_epoch, policy=full_floor_policy
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
    vector = assembler.assemble(extra_dimensions=extra)
    assert vector is not None
    assert assembler.is_complete(vector) is False


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
# MEDIUM-A: injected DimensionReport readers are copied, never authored
# ============================================================================


def test_authority_dimension_reader_report_is_copied_verbatim(
    log: SqliteCommitLog,
    trusted_time_service: FakeTimeService,
    writer_epoch: int,
    complete_policy,
) -> None:
    report = DimensionReport(
        bound_generation=3, positively_established=True, restrictive_floor=2
    )
    assembler = _assembler(
        log,
        trusted_time_service,
        writer_epoch=writer_epoch,
        policy=complete_policy,
        authority_dimension_reader=lambda: report,
    )
    vector = assembler.assemble()
    assert vector is not None
    dim = next(
        d for d in vector.dimensions if d.dimension_key is DimensionKey.SAFETY_AUTHORITY
    )
    # every field is the OWNER's own report, never re-derived/defaulted here.
    assert dim.bound_generation == 3
    assert dim.positively_established is True
    assert dim.restrictive_floor == 2


def test_authority_dimension_reader_false_verdict_is_honored_not_overridden(
    log: SqliteCommitLog,
    trusted_time_service: FakeTimeService,
    writer_epoch: int,
    complete_policy,
) -> None:
    """The whole point of MEDIUM-A: an owner reporting NOT established must
    stay NOT established — this assembler must never force it True because
    a bound_generation happens to be present."""
    report = DimensionReport(
        bound_generation=3, positively_established=False, restrictive_floor=0
    )
    assembler = _assembler(
        log,
        trusted_time_service,
        writer_epoch=writer_epoch,
        policy=complete_policy,
        authority_dimension_reader=lambda: report,
    )
    vector = assembler.assemble()
    assert vector is not None
    dim = next(
        d for d in vector.dimensions if d.dimension_key is DimensionKey.SAFETY_AUTHORITY
    )
    assert dim.positively_established is False


def test_authority_dimension_reader_none_omits_the_dimension(
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
        authority_dimension_reader=lambda: None,
    )
    vector = assembler.assemble()
    assert vector is not None
    keys = {d.dimension_key for d in vector.dimensions}
    assert DimensionKey.SAFETY_AUTHORITY not in keys


def test_action_flow_dimension_reader_report_is_copied_verbatim(
    log: SqliteCommitLog,
    trusted_time_service: FakeTimeService,
    writer_epoch: int,
    complete_policy,
) -> None:
    report = DimensionReport(
        bound_generation=7, positively_established=True, restrictive_floor=0
    )
    assembler = _assembler(
        log,
        trusted_time_service,
        writer_epoch=writer_epoch,
        policy=complete_policy,
        action_flow_dimension_reader=lambda: report,
    )
    vector = assembler.assemble()
    assert vector is not None
    dim = next(
        d for d in vector.dimensions if d.dimension_key is DimensionKey.ACTION_FLOW
    )
    assert dim.bound_generation == 7
    assert dim.positively_established is True
