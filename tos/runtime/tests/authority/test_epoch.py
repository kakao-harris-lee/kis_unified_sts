"""``SafetyAuthorityEpochService`` tests (slice plan §1 item 1 + fault contracts)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import yaml
from tos.authority import AuthorityEpochState, AuthorityTransitionReason
from tos.rcl import CommandType, CommitEntry
from tos.workload import RuntimeIdentity
from tos_runtime.authority.epoch import (
    AuthorityConfigError,
    AuthorityEpochTransitionRefused,
    AuthorityRuntimeConfig,
    SafetyAuthorityEpochService,
    load_authority_config,
)
from tos_runtime.rcl.log import CommitLogCorruption, SqliteCommitLog
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
            max_clock_domain_conversion_uncertainty_ms=50,
            max_send_result_wait_ms=5000,
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


def test_witness_stays_false_on_an_immediate_repeat_call_after_expiry(
    epoch_service: SafetyAuthorityEpochService,
    time_service: TrustworthyTimeService,
    time_monotonic: FakeMonotonicSource,
) -> None:
    """2026-09-08 independent-review MEDIUM repro: expiring the window must
    NOT reset the baseline to "now" — an immediate second call (same
    time-service snapshot, no further ``evaluate()``) must stay ``False``,
    never flip back to ``True`` merely because the prior call reset the
    baseline against itself."""
    make_trusted(time_service)
    first = epoch_service.witness()
    assert first.present is True

    time_monotonic.value += 10_000
    time_service.evaluate()

    second = epoch_service.witness()
    assert second.present is False

    third = epoch_service.witness()  # immediately again — same snapshot
    assert third.present is False
    assert third.within_containment_bound is False


def test_witness_stays_false_forever_after_a_genuine_expiry(
    epoch_service: SafetyAuthorityEpochService,
    time_service: TrustworthyTimeService,
    time_monotonic: FakeMonotonicSource,
) -> None:
    """The frozen baseline never self-heals just because more time passes —
    a Safety Authority currentness bound is a one-way door once genuinely
    violated (method docstring)."""
    make_trusted(time_service)
    assert epoch_service.witness().present is True

    time_monotonic.value += 10_000
    time_service.evaluate()
    assert epoch_service.witness().present is False

    # Advancing further (and evaluating again) does not recover it — the
    # baseline is frozen at the original TRUE instant, and real elapsed time
    # only grows relative to it.
    time_monotonic.value += 10_000
    time_service.evaluate()
    assert epoch_service.witness().present is False


def test_witness_recovers_after_a_transient_log_failure(
    epoch_service: SafetyAuthorityEpochService,
    time_service: TrustworthyTimeService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A locked/unreachable log (``sqlite3.Error``) is a genuine failure —
    present=False while it lasts — but recovers to ``True`` once a read
    succeeds again, provided real elapsed time never exceeded the bound
    while the log was unreachable (2026-09-08 independent-review MEDIUM
    fix's "successful read after failure" contract)."""
    make_trusted(time_service)
    real_read = epoch_service._log.read_linearizable  # noqa: SLF001
    calls = {"n": 0}

    def failing_read(*args: object, **kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise sqlite3.OperationalError("database is locked")
        return real_read(*args, **kwargs)

    monkeypatch.setattr(
        epoch_service._log, "read_linearizable", failing_read
    )  # noqa: SLF001

    first = epoch_service.witness()
    assert first.present is False
    assert first.witness_source == "log_unreachable"

    second = epoch_service.witness()
    assert second.present is False  # still failing — stays False, not reset

    third = epoch_service.witness()  # the log becomes reachable again
    assert third.present is True


def test_witness_zero_bound_is_true_only_at_the_exact_read_instant(
    log: SqliteCommitLog,
    time_service: TrustworthyTimeService,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
) -> None:
    """``containment_bound_ms=0`` (never returned by
    :func:`load_authority_config`, which requires a positive int — see the
    config tests below; directly constructible here) is ``True`` only when
    age is exactly ``0`` (the read instant that established/re-confirmed the
    baseline) and ``False`` on every later call once monotonic time has
    moved on at all — the method docstring's documented ``bound=0`` shape."""
    make_trusted(time_service)
    zero_bound = AuthorityRuntimeConfig(containment_bound_ms=0)
    service = SafetyAuthorityEpochService(
        log,
        time_service,
        evidence_port,
        authority_domain="acct-main",
        writer_epoch=writer_epoch,
        config=zero_bound,
    )
    assert service.witness().present is True  # establishes the baseline, age 0
    assert service.witness().present is True  # same snapshot -> still age 0


# ============================================================================
# load_authority_config — named-TBD null containment_bound_ms refuses to start
# ============================================================================


def test_load_authority_config_null_bound_refuses_to_start(tmp_path: Path) -> None:
    path = tmp_path / "authority.yaml"
    path.write_text(
        yaml.safe_dump(
            {"containment_bound_ms": None, "trading_approval_policy_generation": 1}
        )
    )
    with pytest.raises(AuthorityConfigError):
        load_authority_config(path)


def test_load_authority_config_null_policy_generation_refuses_to_start(
    tmp_path: Path,
) -> None:
    path = tmp_path / "authority.yaml"
    path.write_text(
        yaml.safe_dump(
            {"containment_bound_ms": 250, "trading_approval_policy_generation": None}
        )
    )
    with pytest.raises(AuthorityConfigError):
        load_authority_config(path)


def test_load_authority_config_accepts_a_positive_bound(tmp_path: Path) -> None:
    path = tmp_path / "authority.yaml"
    path.write_text(
        yaml.safe_dump(
            {"containment_bound_ms": 250, "trading_approval_policy_generation": 3}
        )
    )
    config = load_authority_config(path)
    assert config.containment_bound_ms == 250
    assert config.trading_approval_policy_generation == 3


def test_load_authority_config_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(AuthorityConfigError):
        load_authority_config(tmp_path / "does-not-exist.yaml")


def test_example_config_ships_with_a_null_named_tbd_bound() -> None:
    """The shipped example must itself refuse to start unmodified (named-TBD)."""
    example = Path(__file__).resolve().parents[2] / "config" / "authority.example.yaml"
    with pytest.raises(AuthorityConfigError):
        load_authority_config(example)


# ============================================================================
# kernel round #1 §2.1 — CommandType switch + legacy-kind fail-closed refusal
# ============================================================================


def test_current_state_uses_the_new_advance_authority_epoch_command_type(
    epoch_service: SafetyAuthorityEpochService,
) -> None:
    """A freshly-committed transition is written under the new, dedicated
    ``ADVANCE_AUTHORITY_EPOCH`` member (kernel round #1 §1.1/§2.1) — the
    reported-gap ``ADVANCE_RESTORE_GENERATION`` reuse is resolved, not merely
    relabeled in a docstring."""
    epoch_service.transition(
        leader_identity="leader-1",
        transition_reason=AuthorityTransitionReason.SAFETY_AUTHORITY_FAILOVER,
    )
    view = epoch_service._log.read_linearizable(  # noqa: SLF001 - test-internal check
        writer_epoch=epoch_service._writer_epoch  # noqa: SLF001
    )
    kinds = {entry.kind for entry in view.entries if entry.command_id is not None}
    assert CommandType.ADVANCE_AUTHORITY_EPOCH in kinds
    assert CommandType.ADVANCE_RESTORE_GENERATION not in kinds


def test_current_state_raises_on_a_legacy_kind_entry_under_the_epoch_prefix(
    log: SqliteCommitLog,
    time_service: TrustworthyTimeService,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
    authority_config: AuthorityRuntimeConfig,
) -> None:
    """A prefix-matching entry committed under the OLD, legacy
    ``ADVANCE_RESTORE_GENERATION`` kind must never be silently skipped by
    :meth:`SafetyAuthorityEpochService.current_state` — skipping it would let
    the epoch floor regress toward 0 (fail-open). It must instead raise
    :class:`CommitLogCorruption` (kernel round #1 §2.1)."""
    legacy_entry = CommitEntry(
        command_id="authority-epoch-transition:acct-main:1",
        command_digest="legacy-digest",
        kind=CommandType.ADVANCE_RESTORE_GENERATION,
    )
    receipt = log.append_cas(legacy_entry, expected_seq=-1, writer_epoch=writer_epoch)
    from tos.rcl import AppendReceipt

    assert isinstance(receipt, AppendReceipt)

    service = SafetyAuthorityEpochService(
        log,
        time_service,
        evidence_port,
        authority_domain="acct-main",
        writer_epoch=writer_epoch,
        config=authority_config,
    )
    with pytest.raises(CommitLogCorruption):
        service.current_state()
