"""Compose e2e tests for :func:`tos_runtime.compose._operations_wiring.apply_operations_wiring`"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
import yaml
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.operations.backup_set import (
    BackupSetManifest,
    EvidenceBackupFacts,
    InboxBackupFacts,
    RclBackupFacts,
)

from . import _fixtures as fx
from .conftest import approve_constructed_intent
from .test_compose_root import (
    _action_flow_inputs_for,
    _aggregate_inputs,
    _LiveRuntimeFacts,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_TOP_LEVEL_KEYS = frozenset(
    (
        "schema_version",
        "projection_generation",
        "exported_at_monotonic_ns",
        "non_authorizing",
        "runtime",
        "recovery",
        "driver",
        "time",
        "currentness",
        "rcl",
        "inbox",
        "evidence",
        "release",
        "operations",
        "alerts",
        "export",
    )
)

_MANIFEST_SUFFIX = ".set.manifest.json"


def _compose(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    *,
    projection_path: Path | None = None,
    backup_root: Path | None = None,
):
    fx.write_band_strategy_file(config_dir)
    facts = _LiveRuntimeFacts()
    runtime = compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=_aggregate_inputs,
        action_flow_inputs_provider=_action_flow_inputs_for(facts),
        projection_path=projection_path,
        backup_root=backup_root,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
    )
    facts.runtime = runtime
    return runtime


def _kind_count(evidence_store, kind: str) -> int:
    return sum(1 for entry in evidence_store.iter_entry_meta() if entry.kind == kind)


def _reach_admitted_send(runtime, custody_root: Path) -> None:
    """Drive ``fx.crossing_event()`` twice — once to construct the proposal/intent, then"""
    event = fx.crossing_event()
    results = runtime.run_once((event,))
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    assert proposal_digest is not None
    approve_constructed_intent(
        runtime,
        custody_root,
        proposal_digest=proposal_digest,
    )
    runtime.run_once((event,))


def _write_manifest(backup_root: Path, generation: int) -> BackupSetManifest:
    manifest = BackupSetManifest(
        generation=generation,
        created_at_monotonic_ns=123,
        files={"evidence": None, "rcl": None, "inbox": None, "composite_state": None},
        source_paths={
            "evidence": "evidence.sqlite3",
            "rcl": "rcl.sqlite3",
            "inbox": "inbox.sqlite3",
            "composite_state": "composite_state.sqlite3",
        },
        evidence=EvidenceBackupFacts(
            last_seq=None, chain_digest="", key_generation=None, event_consumed_count=0
        ),
        rcl=RclBackupFacts(last_seq=None, writer_epoch=None),
        inbox=InboxBackupFacts(last_seq=None, unconsumed_count=0),
    )
    backup_root.mkdir(parents=True, exist_ok=True)
    (backup_root / f"gen{generation}{_MANIFEST_SUFFIX}").write_text(
        manifest.model_dump_json(indent=2)
    )
    return manifest


def test_boot_without_projection_path_writes_no_file_and_no_evidence(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "would_be_projection.json"
    runtime = _compose(config_dir, data_dir, custody_root)

    assert runtime.operations is not None
    assert not projection_path.exists()
    assert _kind_count(runtime.evidence_store, "OPERATOR_PROJECTION_ENABLED") == 0


def test_boot_with_projection_path_exports_a_file(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "operator_projection.json"
    _compose(config_dir, data_dir, custody_root, projection_path=projection_path)

    assert projection_path.is_file()


def test_exported_document_matches_the_pinned_key_set(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "operator_projection.json"
    _compose(config_dir, data_dir, custody_root, projection_path=projection_path)

    document = json.loads(projection_path.read_text())
    assert set(document) == _TOP_LEVEL_KEYS
    assert document["schema_version"] == 1
    assert document["non_authorizing"] is True


def test_operator_projection_enabled_evidence_appended_exactly_once(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "operator_projection.json"
    runtime = _compose(
        config_dir, data_dir, custody_root, projection_path=projection_path
    )

    assert _kind_count(runtime.evidence_store, "OPERATOR_PROJECTION_ENABLED") == 1


def test_projection_generation_increments_after_a_processed_event(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "operator_projection.json"
    runtime = _compose(
        config_dir, data_dir, custody_root, projection_path=projection_path
    )
    first_generation = json.loads(projection_path.read_text())["projection_generation"]

    runtime.run_once((fx.crossing_event(),))

    second_generation = json.loads(projection_path.read_text())["projection_generation"]
    assert second_generation > first_generation


def test_export_field_combines_an_earlier_write_failure_into_the_next_successful_export(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """team-lead Phase B directive: ``export.failures``/``export.last_error`` fold a"""
    projection_dir = tmp_path / "projection_dir"
    projection_dir.mkdir()
    projection_path = projection_dir / "operator_projection.json"

    runtime = _compose(
        config_dir, data_dir, custody_root, projection_path=projection_path
    )
    assert runtime.driver is not None

    projection_path.unlink(missing_ok=True)
    projection_path.mkdir()
    try:
        runtime.run_once((fx.crossing_event(seq=101),))
    finally:
        projection_path.rmdir()

    runtime.run_once((fx.crossing_event(seq=102),))

    document = json.loads(projection_path.read_text())
    assert document["export"]["failures"] >= 1
    assert document["export"]["last_error"] is not None


def test_currentness_last_assemble_complete_is_null_before_any_assemble_call(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "operator_projection.json"
    _compose(config_dir, data_dir, custody_root, projection_path=projection_path)

    document = json.loads(projection_path.read_text())
    assert document["currentness"]["last_assemble_complete"] is None
    assert document["currentness"]["pending_dimensions"] == []


def test_currentness_last_assemble_complete_reports_a_real_bool_after_a_processed_tick(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "operator_projection.json"
    runtime = _compose(
        config_dir, data_dir, custody_root, projection_path=projection_path
    )

    _reach_admitted_send(runtime, custody_root)

    document = json.loads(projection_path.read_text())
    assert isinstance(document["currentness"]["last_assemble_complete"], bool)


def test_recovery_field_reflects_the_real_readiness_verdict(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "operator_projection.json"
    runtime = _compose(
        config_dir, data_dir, custody_root, projection_path=projection_path
    )

    document = json.loads(projection_path.read_text())
    assert runtime.recovery is not None
    assert (
        document["recovery"]["readiness_verdict"]
        == runtime.recovery.readiness_verdict.value
    )
    assert document["recovery"]["reasons"] == [runtime.recovery.reason]


def test_driver_field_reflects_a_wired_driver(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "operator_projection.json"
    runtime = _compose(
        config_dir, data_dir, custody_root, projection_path=projection_path
    )

    document = json.loads(projection_path.read_text())
    assert document["driver"]["wired"] is (runtime.driver is not None)
    assert document["driver"]["halt_latched"] is False
    assert document["driver"]["halt_reason"] is None


def test_evidence_field_reports_a_real_tip(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "operator_projection.json"
    _compose(config_dir, data_dir, custody_root, projection_path=projection_path)

    document = json.loads(projection_path.read_text())
    assert document["evidence"]["tip_seq_excluding_stm_alert"] is not None
    assert isinstance(document["evidence"]["chain_digest"], str)


def test_release_admitted_and_software_deployment_ok_are_the_same_fact(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "operator_projection.json"
    runtime = _compose(
        config_dir, data_dir, custody_root, projection_path=projection_path
    )

    document = json.loads(projection_path.read_text())
    assert document["release"]["admitted"] is runtime.release_admitted
    assert document["release"]["software_deployment_ok"] is runtime.release_admitted


def test_backup_set_observed_evidence_appears_when_a_manifest_exists(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    backup_root = tmp_path / "backups"
    manifest = _write_manifest(backup_root, generation=7)
    projection_path = tmp_path / "operator_projection.json"

    runtime = _compose(
        config_dir,
        data_dir,
        custody_root,
        projection_path=projection_path,
        backup_root=backup_root,
    )

    assert _kind_count(runtime.evidence_store, "BACKUP_SET_OBSERVED") == 1
    document = json.loads(projection_path.read_text())
    last_backup = document["operations"]["last_backup"]
    assert last_backup is not None
    assert last_backup["generation"] == manifest.generation
    assert last_backup["age_monotonic_ns"] is None
    assert isinstance(last_backup["manifest_digest"], str)


def test_backup_set_observed_picks_the_highest_generation(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    backup_root = tmp_path / "backups"
    _write_manifest(backup_root, generation=1)
    _write_manifest(backup_root, generation=3)
    _write_manifest(backup_root, generation=2)
    projection_path = tmp_path / "operator_projection.json"

    _compose(
        config_dir,
        data_dir,
        custody_root,
        projection_path=projection_path,
        backup_root=backup_root,
    )

    document = json.loads(projection_path.read_text())
    assert document["operations"]["last_backup"]["generation"] == 3


def test_no_backup_root_means_no_evidence_and_null_last_backup(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "operator_projection.json"

    runtime = _compose(
        config_dir, data_dir, custody_root, projection_path=projection_path
    )

    assert _kind_count(runtime.evidence_store, "BACKUP_SET_OBSERVED") == 0
    document = json.loads(projection_path.read_text())
    assert document["operations"]["last_backup"] is None


def test_empty_backup_root_means_no_evidence_and_null_last_backup(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    backup_root = tmp_path / "empty_backups"
    backup_root.mkdir()
    projection_path = tmp_path / "operator_projection.json"

    runtime = _compose(
        config_dir,
        data_dir,
        custody_root,
        projection_path=projection_path,
        backup_root=backup_root,
    )

    assert _kind_count(runtime.evidence_store, "BACKUP_SET_OBSERVED") == 0
    document = json.loads(projection_path.read_text())
    assert document["operations"]["last_backup"] is None


def test_operations_schema_versions_are_populated_ints(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "operator_projection.json"
    _compose(config_dir, data_dir, custody_root, projection_path=projection_path)

    document = json.loads(projection_path.read_text())
    schema_versions = document["operations"]["schema_versions"]
    assert set(schema_versions) == {"evidence", "rcl", "inbox"}
    for value in schema_versions.values():
        assert isinstance(value, int)


def test_operations_dependency_admission_matches_release_admitted(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "operator_projection.json"
    runtime = _compose(
        config_dir, data_dir, custody_root, projection_path=projection_path
    )

    document = json.loads(projection_path.read_text())
    assert document["operations"]["dependency_admission"] is runtime.release_admitted


def test_operations_key_continuity_reports_the_real_boot_time_verdict(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """The evidence store's own boot-time continuity check (module docstring of"""
    projection_path = tmp_path / "operator_projection.json"
    runtime = _compose(
        config_dir, data_dir, custody_root, projection_path=projection_path
    )

    document = json.loads(projection_path.read_text())
    assert (
        document["operations"]["key_continuity"]
        == runtime.evidence_store.key_continuity.verdict
        == "CONTINUOUS"
    )


def test_alerts_delivery_owner_and_unresolved_seq_list_shape(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """A freshly-composed runtime emits NO ``STM_ALERT`` at boot any more."""
    projection_path = tmp_path / "operator_projection.json"
    runtime = _compose(
        config_dir, data_dir, custody_root, projection_path=projection_path
    )

    document = json.loads(projection_path.read_text())
    assert document["alerts"]["delivery_owner"] == (
        "legacy alert-manager (outside tos_runtime)"
    )
    unresolved = document["alerts"]["unresolved_stm_alert_seqs"]
    assert isinstance(unresolved, list)
    assert all(isinstance(seq, int) for seq in unresolved)
    real_stm_alert_seqs = [
        entry.seq
        for entry in runtime.evidence_store.iter_entry_meta()
        if entry.kind == "STM_ALERT"
    ]
    assert unresolved == real_stm_alert_seqs[-50:]


def test_acknowledging_an_alert_removes_it_from_the_unresolved_list(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Runtime operations wiring plan (2026-09-13) §2 decision 4/8:"""
    from tos_runtime.compose._monitor_wiring import build_monitor_owners
    from tos_runtime.safety.ack import acknowledge_alert
    from tos_runtime.time.sources import ProcessMonotonicSource

    projection_path = tmp_path / "operator_projection.json"
    runtime = _compose(
        config_dir, data_dir, custody_root, projection_path=projection_path
    )

    monitor_config = tmp_path / "monitor-config"
    monitor_config.mkdir()
    shutil.copy(
        config_dir / "monitor_coverage.yaml", monitor_config / "monitor_coverage.yaml"
    )
    raw = yaml.safe_load(
        (monitor_config / "monitor_coverage.yaml").read_text(encoding="utf-8")
    )
    raw["coverage"]["bounds"]["max_inbox_unconsumed"] = 0
    (monitor_config / "monitor_coverage.yaml").write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )
    owners = build_monitor_owners(
        monitor_config,
        evidence_store=runtime.evidence_store,
        monotonic_source=ProcessMonotonicSource(),
    )
    owners.inbox_cell.inbox = runtime.inbox
    runtime.inbox.enqueue(fx.crossing_event())
    assert owners.monitoring.healthy() is False

    real_stm_alert_seqs = [
        entry.seq
        for entry in runtime.evidence_store.iter_entry_meta()
        if entry.kind == "STM_ALERT"
    ]
    assert real_stm_alert_seqs, "the monitor must have emitted a real STM_ALERT"
    target_seq = real_stm_alert_seqs[0]

    approvals_dir = tmp_path / "approvals"
    ack_path = approvals_dir / "alerts" / f"{target_seq}.yaml"
    ack_path.parent.mkdir(parents=True, exist_ok=True)
    ack_path.write_text(
        "environment_label: non-live-test\n"
        "principal_id: alice\n"
        "acknowledged_at_label: shift-handover-1\n"
    )
    os.chmod(ack_path, 0o600)

    outcome = acknowledge_alert(
        evidence_store=runtime.evidence_store,
        approvals_dir=approvals_dir,
        alert_seq=target_seq,
        environment_label="non-live-test",
        expected_owner_uid=os.getuid(),
    )
    assert outcome.acknowledged is True

    new_risk_halt_before = runtime.inbox.new_risk_halt()

    runtime.run_once((fx.crossing_event(),))

    document = json.loads(projection_path.read_text())
    unresolved = document["alerts"]["unresolved_stm_alert_seqs"]
    assert target_seq not in unresolved
    assert runtime.inbox.new_risk_halt() == new_risk_halt_before
