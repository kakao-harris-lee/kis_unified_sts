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
   verdict (``composed.release_admitted`` — the SAME fact, not re-derived), and the evidence
   store's own boot-time key-continuity verdict (``composed.evidence_store.key_continuity`` — see
   :class:`~tos_runtime.compose._types.OperationsFacts`'s own docstring for why this can only ever
   read ``CONTINUOUS`` on a runtime that exists to be read from at all). Stored on
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

**``currentness.last_assemble_complete`` — retained, never re-evaluated.** The
``safety_mesh`` and ``protective`` field groups that used to sit beside it went with plan
S2-a, along with the services that produced them.

- ``currentness.last_assemble_complete`` reads
  :attr:`~tos_runtime.currentness.vector.CurrentnessAssembler.last_assemble_complete`, retained
  by that class's own :meth:`~tos_runtime.currentness.vector.CurrentnessAssembler.assemble` —
  ``None`` before the first call, or whenever that call refused to issue a vector at all.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``hashlib``, ``pathlib``) +
``tos_runtime.*`` only. No ``shared.*``, no ``tos.staterestore`` (composite-state stays
kernel-owned and untouched here, per :mod:`tos_runtime.operations.backup_set`'s own docstring).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tos_runtime.compose._pending_dimensions import PENDING_DIMENSION_KEYS
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

#: Imported, no longer duplicated: :mod:`tos_runtime.operations.backup_set` exports
#: ``MANIFEST_SUFFIX`` as of the cold-backup wave, so the reason the literal used to be copied
#: here ("do not import a leading-underscore name") no longer applies. The writer and this
#: boot-time observer now read one constant, which is what a suffix change needs them to do.
_MANIFEST_SUFFIX = MANIFEST_SUFFIX

#: Duplicated from :mod:`tos_runtime.compose._monitor_wiring` (a private module constant there) —
#: the evidence ``kind`` :class:`~tos_runtime.safety.monitoring.MonitoringService` emits, which
#: :meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.last_committed_excluding` must exclude
#: for the SAME self-perturbation reason that module's own docstring documents, and which the
#: alert-candidate reader below filters FOR (the two uses are symmetric: one excludes the kind
#: from a staleness read, the other selects only that kind).
_STM_ALERT_KIND = "STM_ALERT"

#: Duplicated from :mod:`tos_runtime.safety.ack` (its own
#: ``EVIDENCE_KIND_STM_ALERT_ACKNOWLEDGED`` — public there, but this module does not import
#: :mod:`tos_runtime.safety.ack` to avoid a compose-wiring -> safety-package coupling this
#: read-only reader does not otherwise need; same duplicate-literal discipline as
#: ``_STM_ALERT_KIND`` immediately above). Runtime operations wiring plan §2 decision 4/8.
_STM_ALERT_ACKNOWLEDGED_KIND = "STM_ALERT_ACKNOWLEDGED"

_BACKUP_SET_OBSERVED_KIND = "BACKUP_SET_OBSERVED"
_OPERATOR_PROJECTION_ENABLED_KIND = "OPERATOR_PROJECTION_ENABLED"


def _highest_generation_manifest(backup_root: Path | None) -> BackupSetManifest | None:
    """The highest ``gen{N}{_MANIFEST_SUFFIX}`` manifest directly under ``backup_root``, or
    ``None`` when ``backup_root`` is ``None``, does not exist, or holds no manifest.

    The scan itself is :func:`tos_runtime.operations.backup_set.generation_number` — public
    and shared as of the cold-backup wave, so the ``gen{N}`` naming is parsed in ONE place.
    This function used to re-implement it (the helper it mirrored was private); a renaming of
    the scheme would then have been silent here, and a scan that recognizes nothing reports
    "no backup" rather than failing (review round 2, F6)."""
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


def _read_currentness(composed: ComposedRuntime) -> dict[str, object]:
    return {
        "pending_dimensions": [key.name for key in PENDING_DIMENSION_KEYS],
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
    # Same fact both fields (module docstring of OperationsFacts.dependency_admission —
    # composed.release_admitted IS the STAGE B software_deployment_ok verdict).
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


def _read_resolved(composed: ComposedRuntime) -> tuple[int, ...]:
    """The seqs the operator projection's ``unresolved_stm_alert_seqs`` field excludes.

    **Runtime operations wiring plan (2026-09-13) §2 decision 4/8.** There is still no
    ``STM_ALERT_RESOLVED`` producer anywhere in this runtime, and there never will be — ADR-002-028
    :159/:187/:191/:388/:511 is explicit that acknowledgement is not resolution, containment,
    incident closure, recovery readiness, or re-arm. What DOES exist now is
    :func:`tos_runtime.safety.ack.acknowledge_alert`'s own ``STM_ALERT_ACKNOWLEDGED`` producer — a
    single-operator confirmation-of-receipt, nothing more. This reader returns every ``alert_seq``
    named by an ``STM_ALERT_ACKNOWLEDGED`` row (a direct payload read, since
    ``iter_entry_meta`` carries no payload — mirrors
    ``tos_runtime.safety.rearm.ReArmWorkflow._prior_consumptions``'s own
    ``SELECT payload_json FROM entries WHERE kind = ?`` idiom). The exported JSON field name
    (``unresolved_stm_alert_seqs``, schema v1) is UNCHANGED — only its meaning is now precisely
    "not yet acknowledged", never "not yet fixed/closed" (see
    :mod:`tos_runtime.operator.projection`'s own "alert ownership" docstring section).
    """
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
        key_continuity=lambda: composed.evidence_store.key_continuity.verdict,
    )
    composed.operations = operations

    after_turn: Callable[[], None] | None = None
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
    """#974 Q2's ONE boot pass (plan §3.3), placed here on purpose (review-1023 M1).

    **Why not in ``apply_release_wiring``, where it was.** That runs BEFORE
    :func:`~tos_runtime.compose._recovery_wiring.apply_recovery_barrier`, so a boot whose barrier
    then held would already have committed an RCL ``RELEASED`` transition — against that
    module's own invariant, "A HOLD verdict never releases capacity … There is no code path left
    that could touch capacity". The released reservation is, by the predicate, one that never
    reached the venue, so no broker exposure followed; the invariant is the thing that was wrong.

    Two positive gates, both required. The barrier must have ADMITTED
    (:attr:`~tos_runtime.recovery.barrier.RecoveryVerdict.ready`, the identity-checked bool that
    module computes once so no caller re-derives it with a bare truthiness test), and a driver
    must still be attached — a HOLD detaches it, so the second gate alone would already be
    enough, and both are here because this is the invariant's own edge.

    The replay-verdict precondition review-1022 item 3 asks for is upheld further up the call
    graph: ``compose_paper_runtime`` only reaches this wiring if ``_finalize`` returned, and
    ``_finalize``'s boot replay raises ``EngineReplayDiverged`` on anything but ``ok``. That same
    replay has rebuilt the live core's reservation projection (#944), so the pass's ledger
    cross-check sees the real held entry.

    Args:
        composed: The post-barrier runtime.
    """
    if composed.driver is None or composed.unsent_release is None:
        return
    if composed.recovery is None or not composed.recovery.ready:
        return
    composed.unsent_release.run()


def _bind_after_turn(
    composed: ComposedRuntime, exporter_callback: Callable[[], None] | None
) -> None:
    """Bind the driver's ONE per-turn callback — this is the single site that does (#974 Q2).

    The driver holds one :meth:`~tos_runtime.engine.driver.EngineDriver.bind_after_turn` slot and
    this wiring runs last, so composing here is what lets two independent per-turn passes coexist
    without the driver growing a second seam. Both are optional and the composition is explicit:

    * :attr:`~tos_runtime.compose._types.ComposedRuntime.unsent_release` runs FIRST — it is the
      one that can change state (a never-sent reservation's release), and the operator projection
      is a read of that state, so exporting before it would publish a document one turn stale.
    * the operator projection exporter runs second, only when ``projection_path`` was given.

    **A raising pass never silences the one after it (review-1023 LOW-3).** Each pass runs in
    its own ``try``, so a release pass that throws on every turn — an ``evidence_store.append``
    failure, or ``apply_reservation_transition`` raising something other than
    ``ReservationTransitionRefusal`` — still leaves the exporter to publish. That matters
    specifically because the exporter is what makes the failure visible at all: it exports
    :attr:`~tos_runtime.engine.driver.EngineDriver.after_turn_failures` /
    ``after_turn_last_error``, so a composition where the thrower suppressed the publisher would
    hide its own breakage from the operator.

    The first exception is then RE-RAISED, after every pass has run. That is what keeps it
    counted: :meth:`~tos_runtime.engine.driver.EngineDriver._fire_after_turn` catches and counts
    whatever comes out of the bound callback, and swallowing it here would reset
    ``after_turn_failures`` to a permanent zero — a silent failure, which is the opposite of
    what LOW-3 asked for. The count the exporter publishes is therefore one turn behind the
    failure, exactly as the exporter already reports its own write failures.

    Args:
        composed: The runtime being wired; a ``None`` ``driver`` (the recovery barrier held it
            back) binds nothing at all, since a detached driver processes no turns.
        exporter_callback: The operator projection exporter's own callback, or ``None``.
    """
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
