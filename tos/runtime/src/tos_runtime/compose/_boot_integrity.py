"""``tos_runtime.compose`` boot-time integrity helpers — split out of"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import fields
from pathlib import Path

from tos.canonical import CanonicalizationScheme
from tos.workload import RuntimeIdentity

from tos_runtime.brokercap import BrokerScopesConfig, InstanceDocument
from tos_runtime.compose._egress_coordinates import EgressCoordinatesConfig
from tos_runtime.compose._risk_attestations import RiskAttestations
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.replay import ReplayableCore, ReplayVerdict, replay_engine
from tos_runtime.engine.replay_releases import RclCommitted
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import CommitLogCorruption, SqliteCommitLog
from tos_runtime.strategy.bindings import LoadedStrategyBindings
from tos_runtime.strategy.loader import LoadedStrategies

__all__ = [
    "RISK_ATTESTATIONS_CONFIG_NAME",
    "EGRESS_COORDINATES_CONFIG_NAME",
    "BROKER_SCOPES_CONFIG_NAME",
    "EngineReplayDiverged",
    "verify_rcl_log_or_halt",
    "verify_engine_replay_or_halt",
    "record_operator_attested_inputs",
]


class EngineReplayDiverged(RuntimeError):
    """Raised by :func:`verify_engine_replay_or_halt` when the independent re-derivation over"""


RISK_ATTESTATIONS_CONFIG_NAME = "risk_attestations.yaml"
EGRESS_COORDINATES_CONFIG_NAME = "egress_coordinates.yaml"
BROKER_SCOPES_CONFIG_NAME = "broker_scopes.yaml"

_ATTESTED_INPUTS_EVIDENCE_KIND = "OPERATOR_ATTESTED_INPUTS"

_REPLAY_RECEIPTS_UNVERIFIABLE_KIND = "REPLAY_RECEIPTS_UNVERIFIABLE"

_RECEIPT_FINGERPRINT_MISSING_REASON = "RECEIPT_FINGERPRINT_MISSING"


def verify_rcl_log_or_halt(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    identity: RuntimeIdentity,
) -> None:
    """Independently re-verify the RCL log's own replay at boot, before any"""
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
    rcl_committed: RclCommitted | None = None,
) -> ReplayVerdict:
    """Independently re-derive the last ``window_events`` admitted events (TOS Phase 3 Wave 1"""
    verdict = replay_engine(
        inbox,
        evidence_store,
        emergency_log,
        build_core,
        scheme=scheme,
        window_events=window_events,
        rcl_committed=rcl_committed,
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
    """One row for ``broker_scopes.yaml``'s active-scope name + digest, plus"""
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
                "source_file_digest": broker_scopes.instance_sha256
                or hashlib.sha256(broker_scopes.instance_path.read_bytes()).hexdigest(),
            }
        )
    return rows


def _extra_config_file_coordinates(
    extra_config_files: tuple[Path, ...],
) -> list[dict[str, str]]:
    """One row per ``extra_config_files`` entry (T2 lane C) — split out of"""
    return [
        {
            "name": path.name,
            "source_file": path.name,
            "source_file_digest": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in extra_config_files
    ]


def record_operator_attested_inputs(
    config_dir: Path,
    evidence_store: SqliteEvidenceStore,
    identity: RuntimeIdentity,
    risk_attestations: RiskAttestations,
    egress_coordinates: EgressCoordinatesConfig,
    loaded_strategies: LoadedStrategies | None = None,
    loaded_bindings: LoadedStrategyBindings | None = None,
    *,
    broker_scopes: BrokerScopesConfig | None = None,
    instance_document: InstanceDocument | None = None,
    extra_config_files: tuple[Path, ...] = (),
) -> None:
    """Durably record ONE evidence entry enumerating every config-attested"""
    coordinates: list[dict[str, str]] = []
    for path, prefix, dataclass_type in (
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
        assert loaded_bindings.sha256_digest is not None
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
    coordinates.extend(_extra_config_file_coordinates(extra_config_files))
    evidence_store.append(
        {"attested_coordinates": coordinates},
        kind=_ATTESTED_INPUTS_EVIDENCE_KIND,
        record_class=_ATTESTED_INPUTS_EVIDENCE_KIND,
        runtime_identity=identity,
    )
