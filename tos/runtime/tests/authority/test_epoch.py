"""``SafetyAuthorityEpochService`` tests (slice plan §1 item 1 + fault contracts)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.authority import (
    AuthorityEpochState,
    AuthorityEpochTransitionRecord,
    AuthorityTransitionReason,
)
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
from tos_runtime.time.service import TrustworthyTimeService
from tos_runtime.time.sources import ReferenceObservation

from .conftest import (
    FakeEvidenceAppendPort,
    FakeMonotonicSource,
    _time_config,
    make_trusted,
)


def _epoch_service(
    log: SqliteCommitLog,
    time_service: TrustworthyTimeService,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
    config: AuthorityRuntimeConfig,
    *,
    authority_domain: str = "acct-main",
) -> SafetyAuthorityEpochService:
    """This suite's standard service construction — only the varying parts are arguments."""
    return SafetyAuthorityEpochService(
        log,
        time_service,
        evidence_port,
        authority_domain=authority_domain,
        writer_epoch=writer_epoch,
        config=config,
    )


def _failover(
    service: SafetyAuthorityEpochService, *, leader_identity: str = "leader-1"
) -> AuthorityEpochTransitionRecord:
    """Commit one ``SAFETY_AUTHORITY_FAILOVER`` transition."""
    return service.transition(
        leader_identity=leader_identity,
        transition_reason=AuthorityTransitionReason.SAFETY_AUTHORITY_FAILOVER,
    )


def test_current_state_is_all_none_before_any_transition(
    epoch_service: SafetyAuthorityEpochService,
) -> None:
    state = epoch_service.current_state()
    assert state == AuthorityEpochState()
    assert epoch_service.current_epoch() is None


def test_transition_commits_and_current_state_reflects_it(
    epoch_service: SafetyAuthorityEpochService,
) -> None:
    record = _failover(epoch_service)
    assert record.old_epoch == 0
    assert record.new_epoch == 1

    state = epoch_service.current_state()
    assert state.authority_domain == "acct-main"
    assert state.current_epoch_floor == 1


def test_second_transition_strictly_advances_the_epoch_floor(
    epoch_service: SafetyAuthorityEpochService,
) -> None:
    _failover(epoch_service)
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
    service_a = _epoch_service(
        log,
        time_service,
        evidence_port,
        writer_epoch,
        authority_config,
        authority_domain="acct-a",
    )
    service_b = _epoch_service(
        log,
        time_service,
        evidence_port,
        writer_epoch,
        authority_config,
        authority_domain="acct-b",
    )
    _failover(service_a, leader_identity="leader-a")
    assert service_a.current_epoch() == 1
    assert service_b.current_epoch() is None


def test_epoch_current_helper_reads_through_current_state(
    epoch_service: SafetyAuthorityEpochService,
) -> None:
    assert epoch_service.epoch_current(1) is False
    _failover(epoch_service)
    assert epoch_service.epoch_current(1) is True
    assert epoch_service.epoch_current(0) is False


def test_stale_epoch_read_yields_fenced_state_not_a_raised_exception(
    log_path: Path,
    log: SqliteCommitLog,
    time_service: TrustworthyTimeService,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
    identity: RuntimeIdentity,
    authority_config: AuthorityRuntimeConfig,
) -> None:
    service = _epoch_service(
        log, time_service, evidence_port, writer_epoch, authority_config
    )
    make_trusted(time_service)
    second = SqliteCommitLog(log_path, evidence_port=FakeEvidenceAppendPort())
    try:
        second.acquire_epoch(identity)
        state = service.current_state()
        assert state == AuthorityEpochState()

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
    service = _epoch_service(
        log, time_service, evidence_port, writer_epoch, authority_config
    )
    second = SqliteCommitLog(log_path, evidence_port=FakeEvidenceAppendPort())
    try:
        second.acquire_epoch(identity)
        with pytest.raises(AuthorityEpochTransitionRefused):
            _failover(service)
    finally:
        second.close()


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
        config=_time_config(),
        identity=identity,
        evidence=evidence_port,
    )
    service = _epoch_service(
        log, unstarted_time, evidence_port, writer_epoch, authority_config
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
    service = _epoch_service(
        log, time_service, evidence_port, writer_epoch, authority_config
    )
    time_service.evaluate()
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
    service = _epoch_service(
        log, time_service, evidence_port, writer_epoch, unconfigured
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
    assert first.present is True

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

    time_monotonic.value += 100
    time_service.evaluate()

    second = epoch_service.witness()
    assert second.present is True
    assert second.within_containment_bound is True


def test_witness_stays_false_on_an_immediate_repeat_call_after_expiry(
    epoch_service: SafetyAuthorityEpochService,
    time_service: TrustworthyTimeService,
    time_monotonic: FakeMonotonicSource,
) -> None:
    """2026-09-08 independent-review MEDIUM repro: expiring the window must"""
    make_trusted(time_service)
    first = epoch_service.witness()
    assert first.present is True

    time_monotonic.value += 10_000
    time_service.evaluate()

    second = epoch_service.witness()
    assert second.present is False

    third = epoch_service.witness()
    assert third.present is False
    assert third.within_containment_bound is False


def test_witness_stays_false_forever_after_a_genuine_expiry(
    epoch_service: SafetyAuthorityEpochService,
    time_service: TrustworthyTimeService,
    time_monotonic: FakeMonotonicSource,
) -> None:
    """The frozen baseline never self-heals just because more time passes —"""
    make_trusted(time_service)
    assert epoch_service.witness().present is True

    time_monotonic.value += 10_000
    time_service.evaluate()
    assert epoch_service.witness().present is False

    time_monotonic.value += 10_000
    time_service.evaluate()
    assert epoch_service.witness().present is False


def test_witness_recovers_after_a_transient_log_failure(
    epoch_service: SafetyAuthorityEpochService,
    time_service: TrustworthyTimeService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A locked/unreachable log (``sqlite3.Error``) is a genuine failure —"""
    make_trusted(time_service)
    real_read = epoch_service._log.read_linearizable  # noqa: SLF001
    calls = {"n": 0}

    def failing_read(*args: Any, **kwargs: Any) -> object:
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
    assert second.present is False

    third = epoch_service.witness()
    assert third.present is True


def test_witness_zero_bound_is_true_only_at_the_exact_read_instant(
    log: SqliteCommitLog,
    time_service: TrustworthyTimeService,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
) -> None:
    """``containment_bound_ms=0`` (never returned by"""
    make_trusted(time_service)
    zero_bound = AuthorityRuntimeConfig(containment_bound_ms=0)
    service = _epoch_service(log, time_service, evidence_port, writer_epoch, zero_bound)
    assert service.witness().present is True
    assert service.witness().present is True


def _authority_config_file(
    tmp_path: Path, *, containment_bound_ms: int | None, policy_generation: int | None
) -> Path:
    """Write one ``authority.yaml`` carrying exactly these two fields."""
    path = tmp_path / "authority.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "containment_bound_ms": containment_bound_ms,
                "trading_approval_policy_generation": policy_generation,
            }
        )
    )
    return path


@pytest.mark.parametrize(
    ("containment_bound_ms", "policy_generation"),
    [(None, 1), (250, None)],
    ids=["null-bound", "null-policy-generation"],
)
def test_load_authority_config_refuses_to_start_on_a_null_field(
    tmp_path: Path, containment_bound_ms: int | None, policy_generation: int | None
) -> None:
    path = _authority_config_file(
        tmp_path,
        containment_bound_ms=containment_bound_ms,
        policy_generation=policy_generation,
    )
    with pytest.raises(AuthorityConfigError):
        load_authority_config(path)


def test_load_authority_config_accepts_a_positive_bound(tmp_path: Path) -> None:
    path = _authority_config_file(
        tmp_path, containment_bound_ms=250, policy_generation=3
    )
    config = load_authority_config(path)
    assert config.containment_bound_ms == 250
    assert config.trading_approval_policy_generation == 3


def test_load_authority_config_leaves_the_optional_use_count_absent(
    tmp_path: Path,
) -> None:
    """An absent ``standing_approval_max_uses_per_action`` is ``None``, never a value."""
    path = _authority_config_file(
        tmp_path, containment_bound_ms=250, policy_generation=1
    )
    assert load_authority_config(path).standing_approval_max_uses_per_action is None


def test_load_authority_config_reads_the_optional_use_count(tmp_path: Path) -> None:
    path = _authority_config_file(
        tmp_path, containment_bound_ms=250, policy_generation=1
    )
    path.write_text(
        path.read_text() + "standing_approval_max_uses_per_action: 390\n",
        encoding="utf-8",
    )
    assert load_authority_config(path).standing_approval_max_uses_per_action == 390


@pytest.mark.parametrize("value", ["null", "0", "-1", "'390'", "true"])
def test_load_authority_config_refuses_a_present_but_unusable_use_count(
    tmp_path: Path, value: str
) -> None:
    """Present-and-invalid is fail-closed, so a typo never silently becomes one use."""
    path = _authority_config_file(
        tmp_path, containment_bound_ms=250, policy_generation=1
    )
    path.write_text(
        path.read_text() + f"standing_approval_max_uses_per_action: {value}\n",
        encoding="utf-8",
    )
    with pytest.raises(AuthorityConfigError, match="standing_approval_max_uses"):
        load_authority_config(path)


def test_load_authority_config_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(AuthorityConfigError):
        load_authority_config(tmp_path / "does-not-exist.yaml")


def test_example_config_ships_with_a_null_named_tbd_bound() -> None:
    """The shipped example must itself refuse to start unmodified (named-TBD)."""
    example = Path(__file__).resolve().parents[2] / "config" / "authority.example.yaml"
    with pytest.raises(AuthorityConfigError):
        load_authority_config(example)


def test_current_state_uses_the_new_advance_authority_epoch_command_type(
    epoch_service: SafetyAuthorityEpochService,
) -> None:
    """A freshly-committed transition is written under the new, dedicated"""
    _failover(epoch_service)
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
    """A prefix-matching entry committed under the OLD, legacy"""
    legacy_entry = CommitEntry(
        command_id="authority-epoch-transition:acct-main:1",
        command_digest="legacy-digest",
        kind=CommandType.ADVANCE_RESTORE_GENERATION,
    )
    receipt = log.append_cas(legacy_entry, expected_seq=-1, writer_epoch=writer_epoch)
    from tos.rcl import AppendReceipt

    assert isinstance(receipt, AppendReceipt)

    service = _epoch_service(
        log, time_service, evidence_port, writer_epoch, authority_config
    )
    with pytest.raises(CommitLogCorruption):
        service.current_state()
