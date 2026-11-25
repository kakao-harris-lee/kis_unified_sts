"""Recovery-barrier compose wiring (TOS Phase 5 W1; plan §2 decision 2)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tos.canonical import CanonicalizationScheme

from tos_runtime.compose._engine_wiring import (
    ENGINE_DRIVER_CONFIG_NAME,
    load_engine_driver_config,
)
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.evidence.emergency import record_halt
from tos_runtime.recon.ports import BrokerWitness
from tos_runtime.recovery import (
    RecoveryBarrier,
    RecoveryInputs,
    assemble_recovery_inputs,
)
from tos_runtime.recovery.composite_state_writer import COMPOSITE_STATE_STORE_FILE_NAME
from tos_runtime.recovery.readiness import ReadinessVerdict

__all__ = ["COMPOSITE_STATE_STORE_FILE_NAME", "apply_recovery_barrier"]

_RECOVERY_BARRIER_KIND = "RECOVERY_BARRIER"
_RECOVERY_BARRIER_HOLD_KIND = "RECOVERY_BARRIER_HOLD"


def _inputs_digest(inputs: RecoveryInputs) -> str:
    """A stable sha256 over every field of ``inputs`` — the "inputs digest" the plan's own"""
    view = {
        "rcl_writer_epoch": inputs.rcl_writer_epoch,
        "rcl_runtime_generation": inputs.rcl_runtime_generation,
        "open_reservation_ids": sorted(
            reservation.reservation_id for reservation in inputs.open_reservations
        ),
        "evidence_tip_seq": inputs.evidence_tip_seq,
        "evidence_tip_key_generation": inputs.evidence_tip_key_generation,
        "legacy_receipt_event_ids": list(inputs.legacy_receipts.event_ids),
        "inbox_unconsumed_count": inputs.inbox_unconsumed_count,
        "possibly_live_event_ids": sorted(
            attempt.event_id for attempt in inputs.possibly_live_attempts
        ),
        "composite_state_incomplete_attempt_ids": list(
            inputs.composite_state_incomplete_attempt_ids
        ),
        "custody_environment_label": inputs.custody_environment_label,
        "custody_manifest_digest": inputs.custody_manifest_digest,
    }
    canonical = json.dumps(view, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def apply_recovery_barrier(
    runtime: ComposedRuntime,
    *,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    scheme: CanonicalizationScheme,
    witness: BrokerWitness | None = None,
) -> ComposedRuntime:
    """Assemble the recovery inputs, fold them via the kernel, and hold or admit ``runtime``."""
    engine_driver_config = load_engine_driver_config(
        config_dir / ENGINE_DRIVER_CONFIG_NAME
    )
    instrument_key = runtime.context_resolver.instrument_key
    inputs = assemble_recovery_inputs(
        rcl_log=runtime.rcl_log,
        evidence_store=runtime.evidence_store,
        inbox=runtime.inbox,
        scheme=scheme,
        window_events=engine_driver_config.replay_window_events,
        custody_root=custody_root,
        composite_state_store_path=data_dir / COMPOSITE_STATE_STORE_FILE_NAME,
        time_service=runtime.time_service,
        account=instrument_key.account,
        instrument=instrument_key.instrument,
        witness=witness,
    )
    verdict = RecoveryBarrier.verdict(inputs)

    runtime.evidence_store.append(
        {
            "readiness_verdict": verdict.readiness_verdict.value,
            "reason": verdict.reason,
            "possibly_live_count": len(inputs.possibly_live_attempts),
            "legacy_receipt_count": inputs.legacy_receipts.count,
            "inputs_digest": _inputs_digest(inputs),
        },
        kind=_RECOVERY_BARRIER_KIND,
        record_class=_RECOVERY_BARRIER_KIND,
        runtime_identity=runtime.identity,
    )
    runtime.recovery = verdict

    if verdict.readiness_verdict is ReadinessVerdict.READY:
        return runtime

    record_halt(
        runtime.evidence_store,
        runtime.emergency_log,
        payload={
            "reason": verdict.reason,
            "possibly_live_event_ids": sorted(
                attempt.event_id for attempt in inputs.possibly_live_attempts
            ),
            "legacy_receipt_event_ids": list(inputs.legacy_receipts.event_ids),
        },
        kind=_RECOVERY_BARRIER_HOLD_KIND,
        record_class=_RECOVERY_BARRIER_HOLD_KIND,
        runtime_identity=runtime.identity,
    )
    runtime.driver = None
    return runtime
