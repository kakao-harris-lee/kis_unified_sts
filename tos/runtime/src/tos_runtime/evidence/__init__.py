"""``tos_runtime.evidence`` — the durable Evidence Store runtime (design #40 D3)."""

from __future__ import annotations

from tos_runtime.evidence.backup import (
    BackupManifest,
    RestoreComparison,
    RestoredStore,
    backup,
    restore,
)
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.outbox import OutboxConsumer, OutboxDelivery, drain, enqueue
from tos_runtime.evidence.ports import EvidenceAppendPort
from tos_runtime.evidence.retention import RetentionPolicy, RetentionVerdict, tombstone
from tos_runtime.evidence.sinks import (
    EngineEvidenceSinkAdapter,
    GatewayEvidenceSinkAdapter,
)
from tos_runtime.evidence.store import (
    ChainVerification,
    EvidenceCorruption,
    InjectedCrash,
    KeyProvider,
    SqliteEvidenceStore,
)

__all__ = [
    "BackupManifest",
    "ChainVerification",
    "EmergencyAppendLog",
    "EngineEvidenceSinkAdapter",
    "EvidenceAppendPort",
    "EvidenceCorruption",
    "GatewayEvidenceSinkAdapter",
    "InjectedCrash",
    "KeyProvider",
    "OutboxConsumer",
    "OutboxDelivery",
    "RestoreComparison",
    "RestoredStore",
    "RetentionPolicy",
    "RetentionVerdict",
    "SqliteEvidenceStore",
    "backup",
    "drain",
    "enqueue",
    "record_halt",
    "restore",
    "tombstone",
]
