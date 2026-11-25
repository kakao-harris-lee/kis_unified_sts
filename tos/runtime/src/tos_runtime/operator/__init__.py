"""``tos_runtime.operator`` — authority-neutral, read-only operator projection (TOS Phase 5 W4"""

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
