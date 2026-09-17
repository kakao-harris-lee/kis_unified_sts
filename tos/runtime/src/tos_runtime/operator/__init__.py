"""``tos_runtime.operator`` — authority-neutral, read-only operator projection (TOS Phase 5 W4
plan §2 decisions 7-8; ADR-DEV-014 ``OBS-INV-001..006``).

**Structural write-port rule (plan §2 decision 8a).** Nothing under this package may import
``tos_runtime.transport``, ``tos_runtime.rcl``, ``tos_runtime.engine.driver``,
``tos_runtime.evidence.store``, or ``tos.egressgw`` — this package only ever RECEIVES already-
computed values through zero-argument read callables; it never stores, sends, reserves, commits,
or clears anything itself. See ``tests/operator/test_no_write_port.py`` for the AST-import-scan
and negative-grep proof of this, plus a synthetic-string self-test proving the negative-grep
regex is not vacuously passing.
"""

from __future__ import annotations

from tos_runtime.operator.export import ProjectionExporter
from tos_runtime.operator.projection import (
    MAX_UNRESOLVED_STM_ALERT_SEQS,
    SCHEMA_VERSION,
    OperatorProjection,
)

__all__ = [
    "OperatorProjection",
    "ProjectionExporter",
    "SCHEMA_VERSION",
    "MAX_UNRESOLVED_STM_ALERT_SEQS",
]
