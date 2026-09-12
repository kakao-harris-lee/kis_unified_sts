"""Compose e2e tests for :func:`tos_runtime.compose._operations_wiring.apply_operations_wiring`
(TOS Phase 5 W4 plan §2 decisions 7-11).

Mirrors ``test_compose_root.py``'s own ``_compose`` helper (module docstring there: writes the
band-reversion strategy file, synthetic transport, ``"non-live-test"`` label) — duplicated here,
not imported, so this module can thread ``projection_path``/``backup_root`` through without
touching a file another lane owns.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.operations.backup_set import (
    BackupSetManifest,
    EvidenceBackupFacts,
    InboxBackupFacts,
    RclBackupFacts,
)

from . import _fixtures as fx
from .conftest import write_approval_file
from .test_compose_root import _action_flow_inputs, _aggregate_inputs

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
        "safety_mesh",
        "currentness",
        "rcl",
        "inbox",
        "evidence",
        "release",
        "protective",
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
    return compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=_aggregate_inputs,
        action_flow_inputs_provider=_action_flow_inputs,
        projection_path=projection_path,
        backup_root=backup_root,
    )


def _kind_count(evidence_store, kind: str) -> int:
    return sum(1 for entry in evidence_store.iter_entry_meta() if entry.kind == kind)


def _reach_admitted_send(runtime, custody_root: Path) -> None:
    """Drive ``fx.crossing_event()`` twice — once to construct the proposal/intent, then
    again with a real approval file written so the flow ADMITs all the way through
    ACTION_FLOW_DECISION to an actual send attempt (mirrors ``test_compose_root.py``'s own
    ``test_engine_steps_admit_for_real_and_reach_the_transport``). Needed because a single
    pass halts at INDEPENDENT_APPROVAL (UNKNOWN, no approval file yet) — never reaching the
    protective/currentness-proof code paths a bare ``run_once`` call does not exercise.
    """
    event = fx.crossing_event()
    results = runtime.run_once((event,))
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    assert proposal_digest is not None
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    write_approval_file(
        custody_root,
        proposal_digest=proposal_digest,
        environment_label="non-live-test",
        approved_intent_envelope_digest=construction.intent.canonical_digest,
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


# -- projection_path=None: no file, no evidence ------------------------------


def test_boot_without_projection_path_writes_no_file_and_no_evidence(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "would_be_projection.json"
    runtime = _compose(config_dir, data_dir, custody_root)

    assert runtime.operations is not None
    assert not projection_path.exists()
    assert _kind_count(runtime.evidence_store, "OPERATOR_PROJECTION_ENABLED") == 0


# -- projection_path given: file, schema, generation, evidence ---------------


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
    """team-lead Phase B directive: ``export.failures``/``export.last_error`` fold a
    :class:`~tos_runtime.operator.export.ProjectionExporter`'s own write-side failures into the
    SAME document's export field. Drives one genuine write failure (an unwritable projection
    directory) then restores write access and asserts the NEXT successful export reports it.
    """
    projection_dir = tmp_path / "projection_dir"
    projection_dir.mkdir()
    projection_path = projection_dir / "operator_projection.json"

    runtime = _compose(
        config_dir, data_dir, custody_root, projection_path=projection_path
    )
    assert runtime.driver is not None

    os.chmod(projection_dir, 0o500)
    try:
        runtime.run_once((fx.crossing_event(seq=101),))
    finally:
        os.chmod(projection_dir, 0o700)

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
    assert document["currentness"]["pending_dimensions"] == [
        "CONTEXT",
        "CRITICAL_INPUT",
        "EGRESS_IDENTITY",
    ]


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


# -- disclosed gaps: safety_mesh.services / protective.last_verdict stay None ---


def test_safety_mesh_is_reported_null_before_the_coordinator_s_first_refresh(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Boot itself never drives a tick through the Coordinator (``build_safety_mesh``'s own
    warm-up ``monitoring_service.clear()`` call bypasses the tick cell entirely) — so
    ``safety_mesh_peek()`` genuinely has nothing to report yet. This is the honest
    "nothing observed yet" case, not the disclosed-gap case (see the sibling test below for
    the real, populated case after a tick)."""
    projection_path = tmp_path / "operator_projection.json"
    _compose(config_dir, data_dir, custody_root, projection_path=projection_path)

    document = json.loads(projection_path.read_text())
    safety_mesh = document["safety_mesh"]
    assert safety_mesh["snapshot_generation"] is None
    assert set(safety_mesh["services"]) == {"spg", "wdr", "sir", "stm"}
    for service in safety_mesh["services"].values():
        assert service["clear"] is None
        assert service["reasons"] == []


def test_safety_mesh_reports_the_real_snapshot_after_a_processed_tick(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "operator_projection.json"
    runtime = _compose(
        config_dir, data_dir, custody_root, projection_path=projection_path
    )

    _reach_admitted_send(runtime, custody_root)

    document = json.loads(projection_path.read_text())
    safety_mesh = document["safety_mesh"]
    assert safety_mesh["snapshot_generation"] is not None
    assert set(safety_mesh["services"]) == {"spg", "wdr", "sir", "stm"}
    for service in safety_mesh["services"].values():
        assert service["clear"] is not None
        assert isinstance(service["reasons"], list)


def test_protective_last_verdict_is_reported_null_before_any_real_evaluation(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """``ProtectiveActionService.verdict()`` is never called during boot (only a real tick's
    ``ActionFlowGovernor`` reaches it, via ``protective_classification_digest``) — the honest
    "no evaluation happened yet" case, not the disclosed-gap case (see the sibling test below
    for the real, populated case after a tick)."""
    projection_path = tmp_path / "operator_projection.json"
    _compose(config_dir, data_dir, custody_root, projection_path=projection_path)

    document = json.loads(projection_path.read_text())
    assert document["protective"]["last_verdict"] is None


def test_protective_last_verdict_reports_the_real_verdict_after_a_processed_tick(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    projection_path = tmp_path / "operator_projection.json"
    runtime = _compose(
        config_dir, data_dir, custody_root, projection_path=projection_path
    )

    _reach_admitted_send(runtime, custody_root)

    document = json.loads(projection_path.read_text())
    last_verdict = document["protective"]["last_verdict"]
    assert last_verdict is not None
    assert set(last_verdict) == {
        "derestriction_admissible",
        "capacity_exhausted",
        "classification",
        "unevaluated",
        "reasons",
        "protective_classification_digest",
    }


# -- backup-set observation ---------------------------------------------------


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


# -- operations.schema_versions / dependency_admission / key_continuity -------


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
    """The evidence store's own boot-time continuity check (module docstring of
    ``OperationsFacts.key_continuity``) — always ``CONTINUOUS`` for a runtime that exists to be
    read from at all (any other verdict means the store's constructor already raised).
    """
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


# -- alerts: nothing has ever been resolved (no producer exists yet) ---------


def test_alerts_delivery_owner_and_unresolved_seq_list_shape(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Boot itself emits ONE genuine ``STM_ALERT`` (``_safety_wiring.build_safety_mesh``'s own
    "boot-time warm-up" — the monitoring service's FIRST-ever observation is honestly
    ``source_continuity_present=None``/UNKNOWN, which alerts) — so a freshly-composed runtime's
    ``unresolved_stm_alert_seqs`` is NOT empty; this test pins the shape (a list of ints, matching
    real evidence rows), never a specific count coupled to this service's own internal policy.
    """
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
