"""``apply_operations_wiring`` — TOS Phase 5 W4 §2 decisions 7/8/11 compose wiring.

Called from :func:`~tos_runtime.compose.root.compose_paper_runtime`, immediately after
``apply_recovery_barrier`` (module docstring of that function: the earliest point every durable
fact this wiring reads — the evidence store, the RCL log, the inbox, :attr:`ComposedRuntime
.release_admitted`, :attr:`ComposedRuntime.recovery` — already exists). Three things happen here,
all read-only over an already-composed runtime:

1. **Backup-set observation** (plan §2 decision 11 (a)): find the highest ``gen*`` manifest under
   an operator-supplied ``backup_root`` (if any) and append one ``BACKUP_SET_OBSERVED`` evidence
   record at boot. **``age_monotonic_ns`` is always ``None``** — a manifest's own
   ``created_at_monotonic_ns`` was stamped by a DIFFERENT process's monotonic clock (the CLI's
   ``backup-set`` invocation), and :class:`~tos_runtime.time.sources.MonotonicSource` values are
   never comparable across process boundaries (design #40 D1.1's own monotonic-clock discipline);
   no trusted wall-clock source exists either (plan §2.7 "벽시계 값 비노출" decision stands), so
   this fact stays honestly absent rather than computed from two incomparable readings.
2. **``OperationsFacts`` construction** (plan §2 decision 11 (b)/(c)/(d)): schema versions of the
   three runtime-owned stores, the backup fact from step 1, the STAGE B dependency-admission
   verdict (``composed.release_admitted`` — the SAME fact, not re-derived), and a ``key_continuity``
   placeholder (TOS Phase 5 W4 lane e3 had not landed when this wiring was authored — see
   :class:`~tos_runtime.compose._types.OperationsFacts`'s own docstring). Stored on
   :attr:`~tos_runtime.compose._types.ComposedRuntime.operations`.
3. **Operator-projection wiring** (plan §2 decisions 7/8, when ``projection_path`` is given): build
   an :class:`~tos_runtime.operator.projection.OperatorProjection` from read callables over
   ``composed`` only (never a write method — see ``tests/operator/test_no_write_port.py``'s own
   structural proof, which this module's callables must satisfy in spirit even though that test
   only scans the ``operator/`` package itself), export it once at boot, bind its exporter to
   :meth:`~tos_runtime.engine.driver.EngineDriver.bind_after_turn` (only when a driver is actually
   wired — the recovery barrier may have held it back), and append one
   ``OPERATOR_PROJECTION_ENABLED`` evidence record (a digest of the path, never the path string
   itself, which could carry an operator's own home-directory username). **The exported
   ``export.failures``/``export.last_error`` fields combine BOTH failure sources** (team-lead
   Phase B directive): the projection's own read-callable failures for THIS build, summed with
   the :class:`~tos_runtime.operator.export.ProjectionExporter`'s own accumulated write-side
   failures (a prior export cycle's atomic-write error, which the exporter itself never raises —
   see that class's own docstring). ``last_error`` prefers the exporter's own message when both
   sides have one (a write failure is necessarily the NEWER of the two, discovered only on the
   NEXT build after it happened). The two-step construction this needs — the exporter cannot
   exist until the projection does, but the projection needs to read the exporter's counters — is
   a one-element list cell filled in immediately after the exporter is built, before ``export()``
   ever runs (see this function's own body).

**Two disclosed gaps this wiring cannot close without editing a file outside this lane's
ownership (team-lead Phase B directive: report rather than add new surface elsewhere).**

- ``safety_mesh.services`` stays ``None`` for every one of the four services. The only retained,
  once-per-tick evaluation is :mod:`tos_runtime.compose._safety_wiring`'s private
  ``_SafetyMeshTickCell``/``_current_tick_snapshot`` pair — neither is exported, and the only
  exported entry point, :attr:`~tos_runtime.compose._safety_wiring._SafetyMesh
  .refresh_tick_snapshot`, is the Coordinator's own UNCONDITIONAL per-tick refresh: calling it
  again here would be a SECOND ``.clear()``/``.dimension_report()`` round within the same tick —
  exactly the self-perturbation :class:`~tos_runtime.compose._safety_wiring.SafetyMeshSnapshot`'s
  own docstring exists to prevent (and MONITORING's continuity tracking is stateful, so a second
  call is not even idempotent). Closing this honestly needs a new, read-only "peek the last
  snapshot without refreshing" accessor on ``_safety_wiring.py`` — out of this lane's file
  ownership for Phase B.
- ``protective.last_verdict`` stays ``None``. :meth:`~tos_runtime.safety.protective
  .ProtectiveActionService.verdict` both evaluates fresh AND appends a ``PROTECTIVE_VERDICT``
  evidence record on every call (no retained, side-effect-free accessor exists) — calling it from
  a read-only projection would make OBSERVATION itself durably mutate state, the same class of
  self-perturbation bug the STM_ALERT precedent already forbids. Closing this honestly needs a
  retained "last verdict" cache on ``ProtectiveActionService`` itself — also out of this lane's
  file ownership for Phase B.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``hashlib``, ``pathlib``) +
``tos_runtime.*`` only. No ``shared.*``, no ``tos.staterestore`` (composite-state stays
kernel-owned and untouched here, per :mod:`tos_runtime.operations.backup_set`'s own docstring).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from tos_runtime.compose._pending_dimensions import PENDING_DIMENSION_KEYS
from tos_runtime.compose._types import ComposedRuntime, OperationsFacts
from tos_runtime.operations.backup_set import BackupSetManifest
from tos_runtime.operations.schema_migrations import schema_version
from tos_runtime.operator.export import ProjectionExporter
from tos_runtime.operator.projection import (
    MAX_UNRESOLVED_STM_ALERT_SEQS,
    OperatorProjection,
)

__all__ = ["apply_operations_wiring"]

#: Duplicated from :mod:`tos_runtime.operations.backup_set` (a private module constant there,
#: not exported) — the SAME "duplicate the literal, do not import a leading-underscore name"
#: discipline that module's own docstring already applies to filenames shared with
#: ``tos_runtime.compose``/``tos_runtime.recovery``.
_MANIFEST_SUFFIX = ".set.manifest.json"

#: Duplicated from :mod:`tos_runtime.compose._safety_wiring` (a private module constant there) —
#: the evidence ``kind`` :class:`~tos_runtime.safety.monitoring.MonitoringService` emits, which
#: :meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.last_committed_excluding` must exclude
#: for the SAME self-perturbation reason that module's own docstring documents, and which the
#: alert-candidate reader below filters FOR (the two uses are symmetric: one excludes the kind
#: from a staleness read, the other selects only that kind).
_STM_ALERT_KIND = "STM_ALERT"

_BACKUP_SET_OBSERVED_KIND = "BACKUP_SET_OBSERVED"
_OPERATOR_PROJECTION_ENABLED_KIND = "OPERATOR_PROJECTION_ENABLED"

#: plan §2 decision 7's schema-pinned service identities (spg/wdr/sir/stm — see each service's
#: own ``_IDENTITY`` constant: ``safety-profile-service-spg-v1`` /
#: ``deviation-service-wdr-v1`` / ``incident-service-sir-v1`` / ``monitoring-service-stm-v1``).
_SAFETY_MESH_SERVICE_KEYS: tuple[str, ...] = ("spg", "wdr", "sir", "stm")


def _highest_generation_manifest(backup_root: Path | None) -> BackupSetManifest | None:
    """The highest ``gen{N}{_MANIFEST_SUFFIX}`` manifest directly under ``backup_root``, or
    ``None`` when ``backup_root`` is ``None``, does not exist, or holds no manifest — mirrors
    :func:`tos_runtime.operations.backup_set._highest_existing_generation`'s own scan logic
    (re-implemented here rather than imported: that helper is a private, leading-underscore
    name — see this module's own docstring on why literals are duplicated rather than reaching
    into another module's private surface)."""
    if backup_root is None or not backup_root.is_dir():
        return None
    best_generation: int | None = None
    best_path: Path | None = None
    for child in backup_root.iterdir():
        if not child.is_file():
            continue
        name = child.name
        if not (name.startswith("gen") and name.endswith(_MANIFEST_SUFFIX)):
            continue
        middle = name[len("gen") : -len(_MANIFEST_SUFFIX)]
        if not middle.isdigit():
            continue
        generation = int(middle)
        if best_generation is None or generation > best_generation:
            best_generation, best_path = generation, child
    if best_path is None:
        return None
    return BackupSetManifest.model_validate_json(best_path.read_text())


def _observe_backup(
    composed: ComposedRuntime, backup_root: Path | None
) -> dict[str, object] | None:
    """Step 1 of the module docstring: find the latest manifest and append
    ``BACKUP_SET_OBSERVED`` once at boot. Returns the ``last_backup`` fact dict (module docstring
    — ``age_monotonic_ns`` always ``None``), or ``None`` when no manifest was found."""
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
) -> Any:  # Callable[[], dict[str, int | None]]
    """A read callable for :attr:`~tos_runtime.compose._types.OperationsFacts.schema_versions`
    — reads each store's ``PRAGMA user_version`` FRESH on every call (never cached), via
    :func:`~tos_runtime.operations.schema_migrations.schema_version`, which opens and closes its
    own connection (safe against the store's own connection being open elsewhere)."""

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
    # RecoveryVerdict.reason is a single, already-joined summary string (module docstring of
    # tos_runtime.recovery.barrier — several individual reasons folded with "; ") — kept as the
    # sole element of the list rather than re-split on a delimiter this module does not own the
    # format of.
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


def _read_safety_mesh(composed: ComposedRuntime) -> dict[str, object]:
    # See this module's own docstring "disclosed gaps" section — no safe, non-mutating
    # per-service peek exists yet.
    del composed  # unused — kept for a uniform Callable[[ComposedRuntime], ...] reader shape
    return {
        "snapshot_generation": None,
        "services": {
            key: {"clear": None, "reasons": []} for key in _SAFETY_MESH_SERVICE_KEYS
        },
    }


def _read_currentness(composed: ComposedRuntime) -> dict[str, object]:
    del composed  # unused — see above
    return {
        "pending_dimensions": [key.name for key in PENDING_DIMENSION_KEYS],
        # No retained "did the last assemble() complete" flag exists on
        # CurrentnessAssembler — calling assemble() here to find out would be a second,
        # independent evaluation of a currentness vector outside its own tick (the same
        # self-perturbation class this module's docstring already flags for safety_mesh).
        "last_assemble_complete": None,
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
    # Same fact both fields (module docstring of OperationsFacts.dependency_admission —
    # composed.release_admitted IS the STAGE B software_deployment_ok verdict).
    return {
        "admitted": composed.release_admitted,
        "software_deployment_ok": composed.release_admitted,
    }


def _read_protective(composed: ComposedRuntime) -> dict[str, object]:
    # See this module's own docstring "disclosed gaps" section.
    del composed  # unused — see _read_safety_mesh
    return {"last_verdict": None}


def _read_operations(operations: OperationsFacts) -> dict[str, object]:
    return {
        "schema_versions": operations.schema_versions(),
        "last_backup": operations.last_backup(),
        "key_continuity": operations.key_continuity(),
        "dependency_admission": operations.dependency_admission(),
    }


def _read_unresolved_candidates(composed: ComposedRuntime) -> tuple[int, ...]:
    # Linear scan (tos_runtime.engine.driver._find_consumed_receipt's own precedent notes this
    # is "acceptable at this wave's scale" for a similarly-shaped full-store read) — the newest
    # MAX_UNRESOLVED_STM_ALERT_SEQS STM_ALERT seqs, oldest-first input already guaranteed by
    # iter_entry_meta's own ORDER BY seq ASC.
    seqs = tuple(
        entry.seq
        for entry in composed.evidence_store.iter_entry_meta()
        if entry.kind == _STM_ALERT_KIND
    )
    return seqs[-MAX_UNRESOLVED_STM_ALERT_SEQS:]


def _read_resolved() -> tuple[int, ...]:
    # No STM_ALERT_RESOLVED producer exists anywhere in this runtime yet (plan §6 confirmation
    # point ⑧) — an honest "nothing has ever been resolved", not a failure.
    return ()


def _build_projection(
    composed: ComposedRuntime,
    operations: OperationsFacts,
    *,
    read_export_status: Any,
) -> OperatorProjection:
    """Assemble the plan §2.7 :class:`~tos_runtime.operator.projection.OperatorProjection` from
    read callables over ``composed`` — never a write method (module docstring). Each field
    group's own logic lives in a module-level ``_read_*`` function (above) so this function
    itself stays a plain wiring list.

    Args:
        read_export_status: Forwarded to :class:`~tos_runtime.operator.projection
            .OperatorProjection`'s own ``read_export_status`` — folds a
            :class:`~tos_runtime.operator.export.ProjectionExporter`'s write-side
            ``failures``/``last_error`` into this SAME document's ``export`` field (see
            :func:`apply_operations_wiring`'s own docstring for the two-step construction this
            requires).
    """
    return OperatorProjection(
        read_runtime=lambda: _read_runtime(composed),
        read_recovery=lambda: _read_recovery(composed),
        read_driver=lambda: _read_driver(composed),
        read_time=lambda: _read_time(composed),
        read_safety_mesh=lambda: _read_safety_mesh(composed),
        read_currentness=lambda: _read_currentness(composed),
        read_rcl=lambda: _read_rcl(composed),
        read_inbox=lambda: _read_inbox(composed),
        read_evidence=lambda: _read_evidence(composed),
        read_release=lambda: _read_release(composed),
        read_protective=lambda: _read_protective(composed),
        read_operations=lambda: _read_operations(operations),
        read_unresolved_stm_alert_candidate_seqs=lambda: _read_unresolved_candidates(
            composed
        ),
        read_resolved_stm_alert_seqs=_read_resolved,
        read_export_status=read_export_status,
    )


def apply_operations_wiring(
    composed: ComposedRuntime,
    *,
    projection_path: Path | None,
    backup_root: Path | None,
) -> ComposedRuntime:
    """Wire TOS Phase 5 W4's operations facts and (optionally) the operator projection onto an
    already-fully-composed ``composed`` (module docstring).

    Args:
        composed: The just-``apply_recovery_barrier``'d runtime — mutated in place and
            returned; :attr:`~tos_runtime.compose._types.ComposedRuntime.operations` is always
            set on return.
        projection_path: Where the operator projection JSON is exported, or ``None`` to disable
            export entirely (module docstring point 3) — never a default path fabricated when
            omitted (plan §2 decision 9's own "exporter 미결선 = 파일 없음" discipline).
        backup_root: Where to look for the latest durable-set backup manifest, or ``None`` to
            skip backup observation entirely (module docstring point 1).

    Returns:
        ``composed`` itself.
    """
    last_backup = _observe_backup(composed, backup_root)
    operations = OperationsFacts(
        schema_versions=_schema_versions_reader(composed),
        last_backup=lambda: last_backup,
        dependency_admission=lambda: composed.release_admitted,
        key_continuity=lambda: None,
    )
    composed.operations = operations

    if projection_path is not None:
        # Two-step construction (team-lead Phase B directive: fold the exporter's own
        # write-side failures/last_error into the SAME document's export field): the exporter
        # cannot be built until the projection exists (ProjectionExporter's own constructor
        # takes ``projection``), but the projection's ``read_export_status`` needs to read the
        # exporter's counters — a 1-element list acts as a late-bound cell the projection's
        # closure reads through, filled in immediately after the exporter is actually built (a
        # build BEFORE that point can only ever happen via the same `export()` call below, which
        # runs strictly after the cell is filled).
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
        if composed.driver is not None:
            composed.driver.bind_after_turn(exporter.as_after_turn_callback())
        path_digest = hashlib.sha256(str(projection_path).encode("utf-8")).hexdigest()
        composed.evidence_store.append(
            {"path_digest": path_digest},
            kind=_OPERATOR_PROJECTION_ENABLED_KIND,
            record_class=_OPERATOR_PROJECTION_ENABLED_KIND,
            runtime_identity=composed.identity,
        )
    return composed
