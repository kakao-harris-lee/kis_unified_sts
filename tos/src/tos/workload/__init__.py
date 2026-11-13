"""Runtime workload identity — pure kernel records + predicates (design #40 D4, kernel side)."""

from __future__ import annotations

from tos.workload.predicates import environment_label_consistent
from tos.workload.records import RuntimeIdentity

__all__ = [
    "RuntimeIdentity",
    "environment_label_consistent",
]
