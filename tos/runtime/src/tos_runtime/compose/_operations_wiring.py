"""``apply_operations_wiring`` — TOS Phase 5 W4 §2 decisions 7/8/11 compose wiring."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tos_runtime.compose._types import ComposedRuntime, OperationsFacts
from tos_runtime.operations.backup_set import (
    MANIFEST_SUFFIX,
    BackupSetManifest,
    generation_number,
)
from tos_runtime.operations.schema_migrations import schema_version
from tos_runtime.operator.export import ProjectionExporter
from tos_runtime.operator.projection import (
    MAX_UNRESOLVED_STM_ALERT_SEQS,
    OperatorProjection,
)

__all__ = ["apply_operations_wiring"]

_MANIFEST_SUFFIX = MANIFEST_SUFFIX

_STM_ALERT_KIND = "STM_ALERT"

_STM_ALERT_ACKNOWLEDGED_KIND = "STM_ALERT_ACKNOWLEDGED"

_BACKUP_SET_OBSERVED_KIND = "BACKUP_SET_OBSERVED"
_OPERATOR_PROJECTION_ENABLED_KIND = "OPERATOR_PROJECTION_ENABLED"


def _highest_generation_manifest(backup_root: Path | None) -> BackupSetManifest | None:
    """The highest ``gen{N}{_MANIFEST_SUFFIX}`` manifest directly under ``backup_root``, or"""
    if backup_root is None or not backup_root.is_dir():
        return None
    best_generation: int | None = None
    best_path: Path | None = None
    for child in backup_root.iterdir():
        if not child.is_file():
            continue
        generation = generation_number(child.name, _MANIFEST_SUFFIX)
        if generation is None:
            continue
        if best_generation is None or generation > best_generation:
            best_generation, best_path = generation, child
    if best_path is None:
        return None
    return BackupSetManifest.model_validate_json(best_path.read_text())


def _observe_backup(
    composed: ComposedRuntime, backup_root: Path | None
) -> dict[str, object] | None:
    """Step 1 of the module docstring: find the latest manifest and append"""
    manifest = _highest_generation_manifest(backup_root)
    if manifest is None:
        return None
    manifest_digest = hashlib.sha256(
        manifest.model_dump_json().encode("utf-8")
    ).hexdigest()
    composed.evidence_store.append(
        {"generation": manifest.generation, "manifest_digest": manifest_digest},
        kind=_BACKUP_SET_OBSERVED_KIND,
        record_class=_BACKUP_SET_OBSERVED_KIND,
        runtime_identity=composed.identity,
    )
    return {
        "generation": manifest.generation,
        "age_monotonic_ns": None,
        "manifest_digest": manifest_digest,
    }


def _schema_versions_reader(
    composed: ComposedRuntime,
) -> Any:
    """A read callable for :attr:`~tos_runtime.compose._types.OperationsFacts.schema_versions`"""

    def _read() -> dict[str, int | None]:
        return {
            "evidence": schema_version(composed.evidence_store.path),
            "rcl": schema_version(composed.rcl_log.path),
            "inbox": schema_version(composed.inbox.path),
        }

    return _read


def _read_runtime(composed: ComposedRuntime) -> dict[str, object]:
    identity = composed.identity
    return {
        "cell_id": identity.cell_id,
        "runtime_generation": identity.runtime_generation,
        "process_nonce": identity.process_nonce,
        "code_digest": identity.code_digest,
    }


def _read_recovery(composed: ComposedRuntime) -> dict[str, object] | None:
    recovery = composed.recovery
    if recovery is None:
        return None
    return {
        "readiness_verdict": recovery.readiness_verdict.value,
        "reasons": [recovery.reason],
    }


def _read_driver(composed: ComposedRuntime) -> dict[str, object]:
    latched = composed.inbox.new_risk_halt()
    return {
        "wired": composed.driver is not None,
        "halt_latched": latched is not None,
        "halt_reason": None if latched is None else latched.get("reason"),
    }


def _read_time(composed: ComposedRuntime) -> dict[str, object]:
    return {"health": composed.time_service.health_state.value}


def _read_currentness(composed: ComposedRuntime) -> dict[str, object]:
    return {
        "pending_dimensions": [],
        "last_assemble_complete": composed.currentness_assembler.last_assemble_complete,
    }


def _read_rcl(composed: ComposedRuntime) -> dict[str, object]:
    view = composed.rcl_log.read_linearizable(writer_epoch=composed.writer_epoch)
    open_reservations = sum(1 for _ in composed.rcl_log.reservation_rows())
    return {"last_seq": view.last_seq, "open_reservations": open_reservations}


def _read_inbox(composed: ComposedRuntime) -> dict[str, object]:
    return {"unconsumed_count": composed.inbox.unconsumed_count}


def _read_evidence(composed: ComposedRuntime) -> dict[str, object]:
    tip_seq, chain_digest, key_generation = (
        composed.evidence_store.last_committed_excluding(frozenset({_STM_ALERT_KIND}))
    )
    return {
        "tip_seq_excluding_stm_alert": tip_seq,
        "chain_digest": chain_digest,
        "key_generation": key_generation,
    }


def _read_release(composed: ComposedRuntime) -> dict[str, object]:
    return {
        "admitted": composed.release_admitted,
        "software_deployment_ok": composed.release_admitted,
    }


def _read_operations(operations: OperationsFacts) -> dict[str, object]:
    return {
        "schema_versions": operations.schema_versions(),
        "last_backup": operations.last_backup(),
        "key_continuity": operations.key_continuity(),
        "dependency_admission": operations.dependency_admission(),
    }


def _read_unresolved_candidates(composed: ComposedRuntime) -> tuple[int, ...]:
    seqs = tuple(
        entry.seq
        for entry in composed.evidence_store.iter_entry_meta()
        if entry.kind == _STM_ALERT_KIND
    )
    return seqs[-MAX_UNRESOLVED_STM_ALERT_SEQS:]


def _read_resolved(composed: ComposedRuntime) -> tuple[int, ...]:
    """The seqs the operator projection's ``unresolved_stm_alert_seqs`` field excludes."""
    rows = composed.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ?",
        (_STM_ALERT_ACKNOWLEDGED_KIND,),
    ).fetchall()
    seqs: list[int] = []
    for (payload_json,) in rows:
        payload = json.loads(payload_json)["payload"]
        alert_seq = payload.get("alert_seq")
        if isinstance(alert_seq, int):
            seqs.append(alert_seq)
    return tuple(seqs)


def _build_projection(
    composed: ComposedRuntime,
    operations: OperationsFacts,
    *,
    read_export_status: Any,
) -> OperatorProjection:
    """Assemble the plan §2.7 :class:`~tos_runtime.operator.projection.OperatorProjection` from"""
    return OperatorProjection(
        read_runtime=lambda: _read_runtime(composed),
        read_recovery=lambda: _read_recovery(composed),
        read_driver=lambda: _read_driver(composed),
        read_time=lambda: _read_time(composed),
        read_currentness=lambda: _read_currentness(composed),
        read_rcl=lambda: _read_rcl(composed),
        read_inbox=lambda: _read_inbox(composed),
        read_evidence=lambda: _read_evidence(composed),
        read_release=lambda: _read_release(composed),
        read_operations=lambda: _read_operations(operations),
        read_unresolved_stm_alert_candidate_seqs=lambda: _read_unresolved_candidates(
            composed
        ),
        read_resolved_stm_alert_seqs=lambda: _read_resolved(composed),
        read_export_status=read_export_status,
    )


def apply_operations_wiring(
    composed: ComposedRuntime,
    *,
    projection_path: Path | None,
    backup_root: Path | None,
) -> ComposedRuntime:
    """Wire TOS Phase 5 W4's operations facts and (optionally) the operator projection onto an"""
    last_backup = _observe_backup(composed, backup_root)
    operations = OperationsFacts(
        schema_versions=_schema_versions_reader(composed),
        last_backup=lambda: last_backup,
        dependency_admission=lambda: composed.release_admitted,
        key_continuity=lambda: composed.evidence_store.key_continuity.verdict,
    )
    composed.operations = operations

    after_turn: Callable[[], None] | None = None
    if projection_path is not None:
        exporter_cell: list[ProjectionExporter] = []

        def _read_export_status() -> tuple[int, str | None]:
            if not exporter_cell:
                return (0, None)
            exporter_ref = exporter_cell[0]
            return (exporter_ref.failures, exporter_ref.last_error)

        projection = _build_projection(
            composed, operations, read_export_status=_read_export_status
        )
        exporter = ProjectionExporter(path=projection_path, projection=projection)
        exporter_cell.append(exporter)
        exporter.export()
        after_turn = exporter.as_after_turn_callback()
        path_digest = hashlib.sha256(str(projection_path).encode("utf-8")).hexdigest()
        composed.evidence_store.append(
            {"path_digest": path_digest},
            kind=_OPERATOR_PROJECTION_ENABLED_KIND,
            record_class=_OPERATOR_PROJECTION_ENABLED_KIND,
            runtime_identity=composed.identity,
        )
    _run_boot_unsent_release(composed)
    _bind_after_turn(composed, after_turn)
    return composed


def _run_boot_unsent_release(composed: ComposedRuntime) -> None:
    """#974 Q2's ONE boot pass (plan §3.3), placed here on purpose (review-1023 M1)."""
    if composed.driver is None or composed.unsent_release is None:
        return
    if composed.recovery is None or not composed.recovery.ready:
        return
    composed.unsent_release.run()


def _bind_after_turn(
    composed: ComposedRuntime, exporter_callback: Callable[[], None] | None
) -> None:
    """Bind the driver's ONE per-turn callback — this is the single site that does (#974 Q2)."""
    driver = composed.driver
    if driver is None:
        return
    passes: list[Callable[[], None]] = []
    if composed.unsent_release is not None:
        passes.append(composed.unsent_release)
    if exporter_callback is not None:
        passes.append(exporter_callback)
    if not passes:
        return

    def _after_turn() -> None:
        first_failure: BaseException | None = None
        for one_pass in passes:
            try:
                one_pass()
            except Exception as exc:  # noqa: BLE001 - isolated, then re-raised below
                if first_failure is None:
                    first_failure = exc
        if first_failure is not None:
            raise first_failure

    driver.bind_after_turn(_after_turn)
