"""The emergency append log + dual-path HALT recording (design #40 D3, §2 item 2)."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

from tos.evidence import DurabilityClass, EvidenceAppendReceipt
from tos.workload import RuntimeIdentity

from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["EmergencyAppendLog", "record_halt"]


class EmergencyAppendLog:
    """A JSONL, sqlite-independent, fsync'd append log for emergency records."""

    def __init__(self, path: Path) -> None:
        """Bind to ``path`` — the file is created on first :meth:`append` if absent."""
        self.path = path

    def append(self, record: Mapping[str, object]) -> None:
        """Write one JSON line and ``fsync`` before returning."""
        line = json.dumps(record, sort_keys=True, separators=(",", ":"))
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def record_halt(
    store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    *,
    payload: Mapping[str, object],
    kind: str,
    record_class: str,
    durability_class: DurabilityClass = DurabilityClass.EMERGENCY_DURABLE,
    runtime_identity: RuntimeIdentity | None = None,
) -> EvidenceAppendReceipt:
    """Durably record one HALT/protective-action event through BOTH paths."""
    if durability_class is not DurabilityClass.EMERGENCY_DURABLE:
        raise ValueError(
            "record_halt refuses a non-EMERGENCY_DURABLE durability_class "
            f"(got {durability_class!r}) — this path is reserved for "
            "HALT / protective-action records (design #40 §2 item 2)"
        )
    scrubbed_payload, masked_keys = store.scrub_payload(payload)
    receipt = store.append(
        scrubbed_payload,
        kind=kind,
        record_class=record_class,
        runtime_identity=runtime_identity,
    )
    emergency_log.append(
        {
            "seq": receipt.seq,
            "segment_id": receipt.segment_id,
            "chain_digest": receipt.chain_digest,
            "key_generation": receipt.key_generation,
            "kind": kind,
            "record_class": record_class,
            "durability_class": durability_class.value,
            "payload": scrubbed_payload,
            "masked_keys": list(masked_keys),
        }
    )
    return receipt
