"""``tos_runtime.compose`` boot-time integrity helpers — split out of
``_wiring.py`` purely for the size budget (tools/tos_size_budget.py file-
level limit); no behavioural difference from having them inline there.
:func:`~tos_runtime.compose._wiring._boot_services` calls both, right after
the RCL log / risk-and-currentness phases build (design #40 §5 order 3-6).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import fields
from pathlib import Path

from tos.canonical import CanonicalizationScheme
from tos.workload import RuntimeIdentity

from tos_runtime.brokercap import BrokerScopesConfig, InstanceDocument
from tos_runtime.compose._egress_attestations import EgressAttestations
from tos_runtime.compose._egress_coordinates import EgressCoordinatesConfig
from tos_runtime.compose._risk_attestations import RiskAttestations
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.replay import ReplayableCore, ReplayVerdict, replay_engine
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import CommitLogCorruption, SqliteCommitLog
from tos_runtime.strategy.bindings import LoadedStrategyBindings
from tos_runtime.strategy.loader import LoadedStrategies

__all__ = [
    "EGRESS_ATTESTATIONS_CONFIG_NAME",
    "RISK_ATTESTATIONS_CONFIG_NAME",
    "EGRESS_COORDINATES_CONFIG_NAME",
    "BROKER_SCOPES_CONFIG_NAME",
    "EngineReplayDiverged",
    "verify_rcl_log_or_halt",
    "verify_engine_replay_or_halt",
    "record_operator_attested_inputs",
]


class EngineReplayDiverged(RuntimeError):
    """Raised by :func:`verify_engine_replay_or_halt` when the independent re-derivation over
    the durable event inbox (:mod:`tos_runtime.engine.replay`) diverges from the recorded outcome
    for at least one compared event (TOS Phase 3 Wave 1 Lane A-R, plan §1.1 "재생 digest 동일").

    Each individual divergence is already durably recorded by :func:`~tos_runtime.engine.replay
    .replay_engine` itself (both evidence paths, via ``record_halt``) BEFORE this is ever raised —
    raising here only refuses to hand back a runtime over a replay that failed, mirroring
    :func:`verify_rcl_log_or_halt`'s own "never a silent halt" contract.
    """


EGRESS_ATTESTATIONS_CONFIG_NAME = "egress_attestations.yaml"
RISK_ATTESTATIONS_CONFIG_NAME = "risk_attestations.yaml"
#: Same config file name ``_wiring.py``/``_egress_coordinates.py`` use for
#: the egress-coordinates config (TOS Phase 4 작업 6 §2.1).
EGRESS_COORDINATES_CONFIG_NAME = "egress_coordinates.yaml"
#: Same config file name ``_wiring.py``/``tos_runtime.brokercap.scopes`` use
#: for the broker-scopes config (TOS Phase 4 plan §2 decisions 1-2/4).
BROKER_SCOPES_CONFIG_NAME = "broker_scopes.yaml"

#: The evidence kind/record class for the operator-attested-inputs
#: provenance record (re-review finding F4, 2026-09-08).
_ATTESTED_INPUTS_EVIDENCE_KIND = "OPERATOR_ATTESTED_INPUTS"

#: Re-review finding R1 (2026-09-09): the NON-halt evidence kind recorded when boot proceeds but
#: at least one receipt's flow fingerprint was unverifiable (a pre-CR6 receipt) — see
#: :func:`verify_engine_replay_or_halt`'s own docstring.
_REPLAY_RECEIPTS_UNVERIFIABLE_KIND = "REPLAY_RECEIPTS_UNVERIFIABLE"

#: The exact reason string :mod:`tos_runtime.engine.replay` appends to
#: ``ReplayVerdict.uncompared_halt_reasons`` for an unverifiable-fingerprint receipt — matched
#: here to recover the event ids without duplicating the label.
_RECEIPT_FINGERPRINT_MISSING_REASON = "RECEIPT_FINGERPRINT_MISSING"


def verify_rcl_log_or_halt(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    identity: RuntimeIdentity,
) -> None:
    """Independently re-verify the RCL log's own replay at boot, before any
    Stage is wired (re-review finding F1, 2026-09-08): compose must never
    hand back a runtime over a corrupt log. On
    :class:`~tos_runtime.rcl.log.CommitLogCorruption`, durably records one
    ``RCL_CORRUPTION_ALERT`` (both evidence paths, via
    :func:`~tos_runtime.evidence.emergency.record_halt`) before re-raising
    — never a silent halt, never a swallowed exception."""
    try:
        rcl_log.verify_replay()
    except CommitLogCorruption as exc:
        record_halt(
            evidence_store,
            emergency_log,
            payload={"detail": str(exc)},
            kind="RCL_CORRUPTION_ALERT",
            record_class="RCL_CORRUPTION_ALERT",
            runtime_identity=identity,
        )
        raise


def verify_engine_replay_or_halt(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    build_core: Callable[[], ReplayableCore],
    *,
    scheme: CanonicalizationScheme,
    window_events: int,
) -> ReplayVerdict:
    """Independently re-derive the last ``window_events`` admitted events (TOS Phase 3 Wave 1
    Lane A-R, plan §1.1) and refuse to hand back a runtime if any diverges from its recorded
    outcome. Mirrors :func:`verify_rcl_log_or_halt`'s own placement discipline: run at boot,
    before the runtime this composes is handed back to any caller.

    Each individual divergence is already durably recorded (both evidence paths) by
    :func:`~tos_runtime.engine.replay.replay_engine` itself before this function ever raises.

    Re-review finding R1 (2026-09-09): when at least one ``DECISION_TICK`` receipt carried no
    flow fingerprint to verify (a pre-CR6 receipt —
    :attr:`~tos_runtime.engine.replay.ReplayVerdict.has_unverifiable_receipts`), this durably
    records a NON-halt ``REPLAY_RECEIPTS_UNVERIFIABLE`` evidence row naming the count and event
    ids — a legacy receipt is not evidence of divergence (the digest half WAS compared for it),
    so it never blocks the boot, and this runtime never auto-upgrades old receipts; the fact is
    simply made durable and visible rather than silently discarded.

    Re-review #2 finding S2 (2026-09-09): this row is appended BEFORE the divergence check below,
    never after — a boot that has BOTH a genuine divergence and an unverifiable legacy receipt
    must not lose the second fact just because the first one raises. The diagnostic case that
    most needs every available fact is exactly the one an append-after-raise would have silently
    dropped it for.

    Raises:
        EngineReplayDiverged: If at least one compared event's replay state was not ``MATCH``.
    """
    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        build_core,
        scheme=scheme,
        window_events=window_events,
    )
    if verdict.has_unverifiable_receipts:
        unverifiable_event_ids = [
            event_id
            for event_id, reason in verdict.uncompared_halt_reasons
            if reason == _RECEIPT_FINGERPRINT_MISSING_REASON
        ]
        evidence_store.append(
            {"count": len(unverifiable_event_ids), "event_ids": unverifiable_event_ids},
            kind=_REPLAY_RECEIPTS_UNVERIFIABLE_KIND,
            record_class=_REPLAY_RECEIPTS_UNVERIFIABLE_KIND,
        )
    if not verdict.ok:
        raise EngineReplayDiverged(
            f"engine replay diverged for {len(verdict.diverged)} of "
            f"{verdict.total_compared} compared events: {verdict.diverged!r}"
        )
    return verdict


def _broker_scopes_coordinates(
    config_dir: Path,
    broker_scopes: BrokerScopesConfig | None,
    instance_document: InstanceDocument | None,
) -> list[dict[str, str]]:
    """One row for ``broker_scopes.yaml``'s active-scope name + digest, plus
    one more for the bound INSTANCE document's own file digest when loaded
    (TOS Phase 4 plan §2 decision 4) — split out of
    :func:`record_operator_attested_inputs` purely for the size budget."""
    if broker_scopes is None:
        return []
    rows = [
        {
            "name": broker_scopes.active_scope.name,
            "source_file": BROKER_SCOPES_CONFIG_NAME,
            "source_file_digest": hashlib.sha256(
                (config_dir / BROKER_SCOPES_CONFIG_NAME).read_bytes()
            ).hexdigest(),
        }
    ]
    if instance_document is not None and broker_scopes.instance_path is not None:
        rows.append(
            {
                "name": (
                    f"{instance_document.environment}:"
                    f"{instance_document.artifact_id}"
                ),
                "source_file": broker_scopes.instance_path.name,
                "source_file_digest": hashlib.sha256(
                    broker_scopes.instance_path.read_bytes()
                ).hexdigest(),
            }
        )
    return rows


def record_operator_attested_inputs(
    config_dir: Path,
    evidence_store: SqliteEvidenceStore,
    identity: RuntimeIdentity,
    egress_attestations: EgressAttestations,
    risk_attestations: RiskAttestations,
    egress_coordinates: EgressCoordinatesConfig,
    loaded_strategies: LoadedStrategies | None = None,
    loaded_bindings: LoadedStrategyBindings | None = None,
    *,
    broker_scopes: BrokerScopesConfig | None = None,
    instance_document: InstanceDocument | None = None,
) -> None:
    """Durably record ONE evidence entry enumerating every config-attested
    coordinate name (items 6/12/16 + the step 6/7 admission witnesses + the
    egress-coordinate/capsule-terminus-stand-in inputs, TOS Phase 4 작업 6
    §2.1) and its source config file's own digest — re-review reviewer Q3,
    F4 (2026-09-08): "the attestations enter SendBoundaryContext as bare
    kernel-typed fields, identical in shape to derived verdicts". This
    record is what lets an auditor tell attested from derived downstream.

    ``broker_scopes``/``instance_document`` (TOS Phase 4 plan §2 decision 4)
    add the active-scope + bound-INSTANCE rows via
    :func:`_broker_scopes_coordinates` — both ``None`` are legitimate.

    ``loaded_strategies`` (TOS Phase 3 슬라이스 D-R ``[D-R-2]``, plan §1.2
    item 3) adds one row per admitted strategy file — ``name``/
    ``source_file`` both the file's own name, ``source_file_digest`` the
    SAME sha256 :meth:`~tos_runtime.strategy.loader.load_strategies` already
    computed while loading it (never re-hashed here); ``None`` when the
    file source was not used (an injected registry, or the legacy neither-
    present empty default — :mod:`tos_runtime.strategy.resolve`).

    ``loaded_bindings`` (``[D-R-3c]``, finding #9 disposition) adds ONE more
    row for ``strategy_bindings.yaml`` itself, the same way, but ONLY when
    the file actually exists (:attr:`~tos_runtime.strategy.bindings.
    LoadedStrategyBindings.present`) — its absence is a normal, typed state
    (module docstring of :mod:`tos_runtime.strategy.bindings`), not
    something to attest.

    Never re-derives ``config_dir``'s file names independently elsewhere —
    this is the ONE place that reads all three attestation/coordinate config
    files' raw bytes for digesting, kept next to where the rest of boot
    already reads them (``_wiring._boot_services``).
    """
    coordinates: list[dict[str, str]] = []
    for path, prefix, dataclass_type in (
        (
            config_dir / EGRESS_ATTESTATIONS_CONFIG_NAME,
            EGRESS_ATTESTATIONS_CONFIG_NAME,
            type(egress_attestations),
        ),
        (
            config_dir / RISK_ATTESTATIONS_CONFIG_NAME,
            RISK_ATTESTATIONS_CONFIG_NAME,
            type(risk_attestations),
        ),
        (
            config_dir / EGRESS_COORDINATES_CONFIG_NAME,
            EGRESS_COORDINATES_CONFIG_NAME,
            type(egress_coordinates),
        ),
    ):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        for field in fields(dataclass_type):
            coordinates.append(
                {
                    "name": field.name,
                    "source_file": prefix,
                    "source_file_digest": digest,
                }
            )
    if loaded_strategies is not None:
        for entry in loaded_strategies.strategies:
            coordinates.append(
                {
                    "name": entry.path.name,
                    "source_file": entry.path.name,
                    "source_file_digest": entry.sha256_digest,
                }
            )
    if loaded_bindings is not None and loaded_bindings.present:
        assert loaded_bindings.sha256_digest is not None  # present implies a digest
        coordinates.append(
            {
                "name": loaded_bindings.path.name,
                "source_file": loaded_bindings.path.name,
                "source_file_digest": loaded_bindings.sha256_digest,
            }
        )
    coordinates.extend(
        _broker_scopes_coordinates(config_dir, broker_scopes, instance_document)
    )
    evidence_store.append(
        {"attested_coordinates": coordinates},
        kind=_ATTESTED_INPUTS_EVIDENCE_KIND,
        record_class=_ATTESTED_INPUTS_EVIDENCE_KIND,
        runtime_identity=identity,
    )
