"""``OperatorProjection`` — an authority-neutral, read-only JSON snapshot of runtime state"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import Any

__all__ = ["OperatorProjection", "SCHEMA_VERSION", "MAX_UNRESOLVED_STM_ALERT_SEQS"]

SCHEMA_VERSION = 1

MAX_UNRESOLVED_STM_ALERT_SEQS = 50

_ALERT_DELIVERY_OWNER = "legacy alert-manager (outside tos_runtime)"

ReadCallable = Callable[[], Any]

_GROUP_FIELDS: tuple[str, ...] = (
    "runtime",
    "recovery",
    "driver",
    "time",
    "currentness",
    "rcl",
    "inbox",
    "evidence",
    "release",
    "operations",
)


class OperatorProjection:
    """Builds the plan §2.7 operator-projection JSON document from read callables only."""

    def __init__(
        self,
        *,
        read_runtime: ReadCallable,
        read_recovery: ReadCallable,
        read_driver: ReadCallable,
        read_time: ReadCallable,
        read_currentness: ReadCallable,
        read_rcl: ReadCallable,
        read_inbox: ReadCallable,
        read_evidence: ReadCallable,
        read_release: ReadCallable,
        read_operations: ReadCallable,
        read_unresolved_stm_alert_candidate_seqs: ReadCallable,
        read_resolved_stm_alert_seqs: ReadCallable,
        read_export_status: Callable[[], tuple[int, str | None]] | None = None,
    ) -> None:
        self._readers: dict[str, ReadCallable] = {
            "runtime": read_runtime,
            "recovery": read_recovery,
            "driver": read_driver,
            "time": read_time,
            "currentness": read_currentness,
            "rcl": read_rcl,
            "inbox": read_inbox,
            "evidence": read_evidence,
            "release": read_release,
            "operations": read_operations,
        }
        self._read_candidate_seqs = read_unresolved_stm_alert_candidate_seqs
        self._read_resolved_seqs = read_resolved_stm_alert_seqs
        self._read_export_status = read_export_status
        self._generation = 0

    def build(self) -> dict[str, Any]:
        """Assemble one operator-projection document."""
        self._generation += 1
        read_failures = 0
        last_error: str | None = None

        def _read(name: str, callback: ReadCallable) -> Any:
            nonlocal read_failures, last_error
            try:
                return callback()
            except (
                Exception
            ) as exc:  # noqa: BLE001 - a broken reader yields None, never a crash
                read_failures += 1
                last_error = f"{name}: {exc!r}"
                return None

        groups: dict[str, Any] = {
            name: _read(name, reader) for name, reader in self._readers.items()
        }

        candidates = _read(
            "alerts.unresolved_stm_alert_candidate_seqs", self._read_candidate_seqs
        )
        resolved = _read("alerts.resolved_stm_alert_seqs", self._read_resolved_seqs)
        unresolved = _unresolved_seqs(candidates, resolved)

        if self._read_export_status is not None:
            try:
                exporter_failures, exporter_last_error = self._read_export_status()
            except (
                Exception
            ) as exc:  # noqa: BLE001 - a broken status read never crashes a build
                read_failures += 1
                if last_error is None:
                    last_error = f"export_status: {exc!r}"
            else:
                read_failures += exporter_failures
                if exporter_last_error is not None:
                    last_error = exporter_last_error

        document: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "projection_generation": self._generation,
            "exported_at_monotonic_ns": time.monotonic_ns(),
            "non_authorizing": True,
        }
        for name in _GROUP_FIELDS:
            document[name] = groups[name]
        document["alerts"] = {
            "unresolved_stm_alert_seqs": unresolved,
            "delivery_owner": _ALERT_DELIVERY_OWNER,
        }
        document["export"] = {"failures": read_failures, "last_error": last_error}
        return document


def _unresolved_seqs(
    candidates: Iterable[int] | None, resolved: Iterable[int] | None
) -> list[int] | None:
    'Derive ``alerts.unresolved_stm_alert_seqs`` (module docstring\'s "alert ownership"'
    if candidates is None:
        return None
    resolved_set = set(resolved) if resolved is not None else set()
    unresolved = [seq for seq in candidates if seq not in resolved_set]
    return unresolved[:MAX_UNRESOLVED_STM_ALERT_SEQS]
