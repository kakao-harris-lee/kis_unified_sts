"""Recovery-barrier compose wiring (TOS Phase 5 W1; plan §2 decision 2).

Called from :func:`~tos_runtime.compose.root.compose_paper_runtime` immediately after
``_finalize`` returns a fully-wired :class:`~tos_runtime.compose._types.ComposedRuntime` — the
earliest point at which the durable RCL log / evidence store / inbox this barrier reads all
exist.

**Reported deviation from the plan's literal "부팅 전 장벽" / "compose 는 ... 사이에 결선한다"
placement.** The durable inbox this barrier's own possibly-live / legacy-receipt reads depend on
does not exist until :func:`~tos_runtime.compose._engine_wiring.wire_engine_and_driver` builds it
INSIDE ``_finalize`` — there is no earlier point in ``compose_paper_runtime`` at which those
durable facts are even constructible (mirrors ``root.py``'s own documented "release admission
FIRST" reported deviation — a real constraint, not a convenience). The substantive ordering the
plan actually requires is fully preserved: this module's own evidence record is appended before
``compose_paper_runtime`` ever returns to any caller, and a HOLD verdict detaches the driver so no
caller can reach ``EngineCore.handle`` at all (:meth:`~tos_runtime.compose._types.ComposedRuntime
.run_once`'s own :class:`~tos_runtime.compose._types.RecoveryBarrierHeld` refusal) — no event of
the new boot is ever consumed before the ``RECOVERY_BARRIER`` record exists.

**Why a separate module, not a block inside ``_finalize``.** ``_wiring.py``'s own size-budget
ceiling (``config/tos_size_budget.yaml`` — registered at 1197 lines) must not grow; this mirrors
exactly how :mod:`tos_runtime.compose._engine_wiring` /
:mod:`tos_runtime.compose._boot_integrity` were themselves split out of ``_wiring.py`` for the
identical reason (their own module docstrings).

**Capacity discipline (plan §2 decision 2's "재무장 0 · 용량 반환 0").** A HOLD verdict never
releases capacity and never re-arms anything — not via an explicit "clear" call this module
declines to make, but structurally: the driver (the only component in this runtime that can ever
call ``core.handle``/drain the gateway/mutate an RCL reservation) is simply never wired onto the
returned runtime. There is no code path left that could touch capacity.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``hashlib``, ``json``,
``pathlib``) + ``tos.*`` + ``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tos.canonical import CanonicalizationScheme
from tos.sbr.vocabulary import ReadinessVerdict

from tos_runtime.compose._engine_wiring import (
    ENGINE_DRIVER_CONFIG_NAME,
    load_engine_driver_config,
)
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.evidence.emergency import record_halt
from tos_runtime.recovery import (
    RecoveryBarrier,
    RecoveryInputs,
    assemble_recovery_inputs,
)

__all__ = ["COMPOSITE_STATE_STORE_FILE_NAME", "apply_recovery_barrier"]

#: The evidence kind for the always-recorded verdict record (plan §2 decision 2's own literal
#: name: "evidence record RECOVERY_BARRIER{verdict, reason, possibly_live_count,
#: legacy_receipt_count, inputs digest}").
_RECOVERY_BARRIER_KIND = "RECOVERY_BARRIER"
#: The dual-path HALT kind recorded ADDITIONALLY when the verdict is not READY (plan §2 decision
#: 2's own "정지 사유 evidence") — mirrors every other boot-time halt in this compose root
#: (``verify_rcl_log_or_halt``/``verify_engine_replay_or_halt``, ``_boot_integrity.py``).
_RECOVERY_BARRIER_HOLD_KIND = "RECOVERY_BARRIER_HOLD"
#: Where a per-data-dir ``tos.staterestore`` composite-state store would live — a SEPARATE sqlite
#: file from both the evidence store and the inbox (the same D3 failure-domain-separation
#: discipline every other durable file in this runtime follows).
COMPOSITE_STATE_STORE_FILE_NAME = "composite_state.sqlite3"


def _inputs_digest(inputs: RecoveryInputs) -> str:
    """A stable sha256 over every field of ``inputs`` — the "inputs digest" the plan's own
    ``RECOVERY_BARRIER`` record literal names, so a later audit can tell whether two boots saw
    the identical durable facts without re-deriving them by hand."""
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
) -> ComposedRuntime:
    """Assemble the recovery inputs, fold them via the kernel, and hold or admit ``runtime``.

    Args:
        runtime: The just-``_finalize``d :class:`~tos_runtime.compose._types.ComposedRuntime` —
            mutated and returned; its ``.driver`` is still real on entry.
        config_dir: The SAME directory :func:`~tos_runtime.compose.root.compose_paper_runtime`
            was given — read again here only for ``engine_driver.yaml``'s own
            ``replay_window_events`` bound, so this barrier's legacy-receipt gate covers exactly
            the same window the boot-time replay check already verified.
        data_dir: The SAME directory ``compose_paper_runtime`` was given — for the composite-
            state store path (:data:`COMPOSITE_STATE_STORE_FILE_NAME`).
        custody_root: The SAME directory ``compose_paper_runtime`` was given — for the read-only
            custody-manifest identity read.
        scheme: The SAME canonicalization scheme this runtime composed with.

    Returns:
        ``runtime`` itself: :attr:`~tos_runtime.compose._types.ComposedRuntime.recovery` is
        always set; :attr:`~tos_runtime.compose._types.ComposedRuntime.driver` is set to
        ``None`` (never released, never re-armed — module docstring) whenever the verdict is not
        :attr:`~tos.sbr.vocabulary.ReadinessVerdict.READY`.
    """
    engine_driver_config = load_engine_driver_config(
        config_dir / ENGINE_DRIVER_CONFIG_NAME
    )
    inputs = assemble_recovery_inputs(
        rcl_log=runtime.rcl_log,
        evidence_store=runtime.evidence_store,
        inbox=runtime.inbox,
        scheme=scheme,
        window_events=engine_driver_config.replay_window_events,
        custody_root=custody_root,
        composite_state_store_path=data_dir / COMPOSITE_STATE_STORE_FILE_NAME,
    )
    verdict = RecoveryBarrier.verdict(inputs)

    # Durable BEFORE anything else this function does (plan §2 decision 2's own record literal)
    # -- and, by construction, before the new boot's driver (not yet wired onto `runtime` at all
    # until the READY return below) could ever consume an event.
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
    # Module docstring's capacity discipline: detaching the driver, not an explicit release/
    # re-arm call this module declines to make, is what makes "never release, never re-arm"
    # structural rather than a promise.
    runtime.driver = None
    return runtime
