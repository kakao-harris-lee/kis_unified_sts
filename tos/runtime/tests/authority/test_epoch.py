"""``SafetyAuthorityEpochService`` tests (slice plan §1 item 1 + fault contracts)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tos.authority import AuthorityEpochState, AuthorityTransitionReason
from tos.workload import RuntimeIdentity
from tos_runtime.authority.epoch import (
    AuthorityConfigError,
    AuthorityEpochTransitionRefused,
    AuthorityRuntimeConfig,
    SafetyAuthorityEpochService,
    load_authority_config,
)
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.service import TrustworthyTimeService
from tos_runtime.time.sources import ReferenceObservation

from .conftest import FakeEvidenceAppendPort, FakeMonotonicSource, make_trusted

# ============================================================================
# current_state() — derived from the log, no cache
# ============================================================================


def test_current_state_is_all_none_before_any_transition(
    epoch_service: SafetyAuthorityEpochService,
) -> None:
    state = epoch_service.current_state()
    assert state == AuthorityEpochState()
    assert epoch_service.current_epoch() is None


def test_transition_commits_and_current_state_reflects_it(
    epoch_service: SafetyAuthorityEpochService,
) -> None:
    record = epoch_service.transition(
        leader_identity="leader-1",
        transition_reason=AuthorityTransitionReason.SAFETY_AUTHORITY_FAILOVER,
    )
    assert record.old_epoch == 0
    assert record.new_epoch == 1

    state = epoch_service.current_state()
    assert state.authority_domain == "acct-main"
    assert state.current_epoch_floor == 1


def test_second_transition_strictly_advances_the_epoch_floor(
    epoch_service: SafetyAuthorityEpochService,
) -> None:
    epoch_service.transition(
        leader_identity="leader-1",
        transition_reason=AuthorityTransitionReason.SAFETY_AUTHORITY_FAILOVER,
    )
    second = epoch_service.transition(
        leader_identity="leader-2",
        transition_reason=AuthorityTransitionReason.LOSS_OF_LEADER_OWNERSHIP,
    )
    assert second.old_epoch == 1
    assert second.new_epoch == 2
    assert epoch_service.current_epoch() == 2


def test_current_state_is_domain_scoped(
    log: SqliteCommitLog,
    time_service: TrustworthyTimeService,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
    authority_config: AuthorityRuntimeConfig,
) -> None:
    """A transition committed for one domain is invisible to another domain's service."""
    service_a = SafetyAuthorityEpochService(
        log,
        time_service,
        evidence_port,
        authority_domain="acct-a",
        writer_epoch=writer_epoch,
        config=authority_config,
    )
    service_b = SafetyAuthorityEpochService(
        log,
        time_service,
        evidence_port,
        authority_domain="acct-b",
        writer_epoch=writer_epoch,
        config=authority_config,
    )
    service_a.transition(
        leader_identity="leader-a",
        transition_reason=AuthorityTransitionReason.SAFETY_AUTHORITY_FAILOVER,
    )
    assert service_a.current_epoch() == 1
    assert service_b.current_epoch() is None


def test_epoch_current_helper_reads_through_current_state(
    epoch_service: SafetyAuthorityEpochService,
) -> None:
    assert epoch_service.epoch_current(1) is False  # no epoch issued yet — fenced
    epoch_service.transition(
        leader_identity="leader-1",
        transition_reason=AuthorityTransitionReason.SAFETY_AUTHORITY_FAILOVER,
    )
    assert epoch_service.epoch_current(1) is True
    assert epoch_service.epoch_current(0) is False  # stale


# ============================================================================
# fault: epoch read failure -> UNKNOWN/fenced state
# ============================================================================


def test_stale_epoch_read_yields_fenced_state_not_a_raised_exception(
    log_path: Path,
    log: SqliteCommitLog,
    time_service: TrustworthyTimeService,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
    identity: RuntimeIdentity,
    authority_config: AuthorityRuntimeConfig,
) -> None:
    service = SafetyAuthorityEpochService(
        log,
        time_service,
        evidence_port,
        authority_domain="acct-main",
        writer_epoch=writer_epoch,
        config=authority_config,
    )
    make_trusted(time_service)
    # A second handle acquires a strictly-greater writer epoch, invalidating
    # `service`'s own `writer_epoch` for every subsequent read.
    second = SqliteCommitLog(log_path, evidence_port=FakeEvidenceAppendPort())
    try:
        second.acquire_epoch(identity)
        state = service.current_state()
        assert state == AuthorityEpochState()  # fenced, not a raised exception

        witness = service.witness()
        assert witness.present is False
        assert witness.witness_source == "stale_epoch_read"
    finally:
        second.close()


def test_transition_raises_on_stale_writer_epoch(
    log_path: Path,
    log: SqliteCommitLog,
    time_service: TrustworthyTimeService,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
    identity: RuntimeIdentity,
    authority_config: AuthorityRuntimeConfig,
) -> None:
    service = SafetyAuthorityEpochService(
        log,
        time_service,
        evidence_port,
        authority_domain="acct-main",
        writer_epoch=writer_epoch,
        config=authority_config,
    )
    second = SqliteCommitLog(log_path, evidence_port=FakeEvidenceAppendPort())
    try:
        second.acquire_epoch(identity)
        with pytest.raises(AuthorityEpochTransitionRefused):
            service.transition(
                leader_identity="leader-1",
                transition_reason=AuthorityTransitionReason.SAFETY_AUTHORITY_FAILOVER,
            )
    finally:
        second.close()


# ============================================================================
# witness() — online currentness (fault: snapshot expired -> present False)
# ============================================================================


def test_witness_present_false_before_time_service_started(
    log: SqliteCommitLog,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
    identity: RuntimeIdentity,
    authority_config: AuthorityRuntimeConfig,
) -> None:
    class _Reader:
        def read(self) -> ReferenceObservation:
            return ReferenceObservation(reachable=True, healthy=True)

    unstarted_time = TrustworthyTimeService(
        monotonic=FakeMonotonicSource(1_000),
        references=[_Reader()],
        config=TrustworthyTimeConfig(
            max_time_source_precision_ms=5,
            max_time_transport_and_queue_uncertainty_ms=10,
            max_time_conservative_freshness_age_ms=1000,
            max_future_timestamp_tolerance_ms=200,
            max_process_suspension_ms=0,
            max_time_source_disagreement_ms=50,
            min_time_independent_reference_count=1,
            tz_db_version="2026a",
            trading_calendar_version="cal-1",
            verification_profile_version="vp-0",
            safety_profile_version="sp-0",
        ),
        identity=identity,
        evidence=evidence_port,
    )
    service = SafetyAuthorityEpochService(
        log,
        unstarted_time,
        evidence_port,
        authority_domain="acct-main",
        writer_epoch=writer_epoch,
        config=authority_config,
    )
    witness = service.witness()
    assert witness.present is False
    assert witness.witness_source == "time_service_not_started"


def test_witness_present_false_when_time_not_yet_trusted(
    log: SqliteCommitLog,
    time_service: TrustworthyTimeService,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
    authority_config: AuthorityRuntimeConfig,
) -> None:
    service = SafetyAuthorityEpochService(
        log,
        time_service,
        evidence_port,
        authority_domain="acct-main",
        writer_epoch=writer_epoch,
        config=authority_config,
    )
    time_service.evaluate()  # UNINITIALIZED -> SYNCHRONIZING only
    witness = service.witness()
    assert witness.present is False
    assert witness.witness_source == "time_health_not_trusted"


def test_witness_present_true_when_trusted_and_log_reachable(
    epoch_service: SafetyAuthorityEpochService, time_service: TrustworthyTimeService
) -> None:
    make_trusted(time_service)
    witness = epoch_service.witness()
    assert witness.present is True
    assert witness.within_containment_bound is True


def test_witness_present_false_when_containment_bound_unconfigured(
    log: SqliteCommitLog,
    time_service: TrustworthyTimeService,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
) -> None:
    make_trusted(time_service)
    unconfigured = AuthorityRuntimeConfig(containment_bound_ms=None)
    service = SafetyAuthorityEpochService(
        log,
        time_service,
        evidence_port,
        authority_domain="acct-main",
        writer_epoch=writer_epoch,
        config=unconfigured,
    )
    witness = service.witness()
    assert witness.present is False
    assert witness.witness_source == "containment_bound_unconfigured"


def test_witness_expires_beyond_the_containment_bound(
    epoch_service: SafetyAuthorityEpochService,
    time_service: TrustworthyTimeService,
    time_monotonic: FakeMonotonicSource,
) -> None:
    make_trusted(time_service)
    first = epoch_service.witness()
    assert first.present is True  # baseline established

    # Advance the clock well beyond the configured 500ms bound and re-evaluate
    # so the time service's own snapshot reflects the new "now".
    time_monotonic.value += 10_000
    time_service.evaluate()

    second = epoch_service.witness()
    assert second.present is False
    assert second.within_containment_bound is False


def test_witness_stays_present_within_the_containment_bound(
    epoch_service: SafetyAuthorityEpochService,
    time_service: TrustworthyTimeService,
    time_monotonic: FakeMonotonicSource,
) -> None:
    make_trusted(time_service)
    first = epoch_service.witness()
    assert first.present is True

    time_monotonic.value += 100  # well inside the 500ms bound
    time_service.evaluate()

    second = epoch_service.witness()
    assert second.present is True
    assert second.within_containment_bound is True


# ============================================================================
# load_authority_config — named-TBD null containment_bound_ms refuses to start
# ============================================================================


def test_load_authority_config_null_bound_refuses_to_start(tmp_path: Path) -> None:
    path = tmp_path / "authority.yaml"
    path.write_text(yaml.safe_dump({"containment_bound_ms": None}))
    with pytest.raises(AuthorityConfigError):
        load_authority_config(path)


def test_load_authority_config_accepts_a_positive_bound(tmp_path: Path) -> None:
    path = tmp_path / "authority.yaml"
    path.write_text(yaml.safe_dump({"containment_bound_ms": 250}))
    config = load_authority_config(path)
    assert config.containment_bound_ms == 250


def test_load_authority_config_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(AuthorityConfigError):
        load_authority_config(tmp_path / "does-not-exist.yaml")


def test_example_config_ships_with_a_null_named_tbd_bound() -> None:
    """The shipped example must itself refuse to start unmodified (named-TBD)."""
    example = Path(__file__).resolve().parents[2] / "config" / "authority.example.yaml"
    with pytest.raises(AuthorityConfigError):
        load_authority_config(example)
