"""``tos_runtime.evidence`` — the durable Evidence Store runtime (design #40 D3).

Realizes design doc #40's D3 decision in full
(``docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-decisions.md``
§D3.1-D3.4) per the slice plan
(``docs/plans/2026-09-08-tos-phase2-runtime-slice1-time-evidence-plan.md`` §2,
lane L). This package **implements** the kernel's pure Protocol seams
(:mod:`tos.evidence`'s :class:`~tos.evidence.chain.Sha256HmacChainScheme`,
:func:`~tos.evidence.scrub.scrub_secret_fields`,
:func:`~tos.evidence.retention.retention_deletable`,
:class:`~tos.evidence.retention.Tombstone`,
:func:`~tos.evidence.chain.verify_chain`; the sink Protocols
:class:`tos.engine.sink.EvidenceSink` and
:class:`tos.egressgw.gateway.GatewayEvidenceSink`) — it never edits the
kernel. No kernel diff is part of this slice.

Public surface groups by module:

* :mod:`tos_runtime.evidence.ports` — :class:`~tos_runtime.evidence.ports.EvidenceAppendPort`,
  the cross-lane seam lane K's Trustworthy Time service depends on.
* :mod:`tos_runtime.evidence.store` — :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`,
  the append-only, chained, durable evidence log (§2 item 1).
* :mod:`tos_runtime.evidence.emergency` — :class:`~tos_runtime.evidence.emergency.EmergencyAppendLog`
  + :func:`~tos_runtime.evidence.emergency.record_halt` (§2 item 2).
* :mod:`tos_runtime.evidence.outbox` — same-transaction outbox enqueue +
  at-least-once ``drain`` (§2 item 3).
* :mod:`tos_runtime.evidence.backup` — sqlite ``Connection.backup``-based
  backup/restore, always landing a new, non-live generation (§2 item 4).
* :mod:`tos_runtime.evidence.retention` — the retention-policy loader +
  judgement-only evaluation (§2 item 5).
* :mod:`tos_runtime.evidence.sinks` — kernel sink adapters (§2 item 6).

Firewall (tools/tos_firewall_check.py R1, runtime scope): stdlib (including
``sqlite3``, ``hashlib``, ``hmac``, ``secrets``, ``os``, ``json``) + ``pydantic``
+ ``pyyaml`` (``yaml``) + ``tos.*`` + ``tos_runtime.*`` only. No ``shared.*``, no
``subprocess``, no ``socket``/network egress, no ``os.environ`` read.
"""

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
    EvidenceCorruption,
    InjectedCrash,
    KeyProvider,
    SqliteEvidenceStore,
)

__all__ = [
    "BackupManifest",
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
