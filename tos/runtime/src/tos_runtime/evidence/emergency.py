"""The emergency append log + dual-path HALT recording (design #40 D3, §2 item 2).

:class:`EmergencyAppendLog` is a **separate file**, JSON Lines, with **zero
sqlite3 dependency** — a HALT/protective-action record must reach durable
storage even if the sqlite evidence store itself is the thing that is
failing (disk full on that volume, a locked file, a corrupt WAL). One
``append()`` call is one write + one ``flush()`` + one ``os.fsync()``: the
line is on stable storage before the call returns.

:func:`record_halt` writes to BOTH paths — the sqlite
:class:`~tos_runtime.evidence.store.SqliteEvidenceStore` (chained,
queryable, replayable) AND this emergency log (simple, sqlite-independent)
— and requires **both** to succeed. If either raises, :func:`record_halt`
propagates the exception rather than returning a receipt: a HALT record that
only reached one of the two paths is not a success, even though the sqlite
side, once committed, is durably and irreversibly recorded regardless (design
#40 §2 item 2 "하나라도 실패 = 예외 · 성공 과대 보고 금지").

**Both paths carry the SAME scrubbed payload (2026-09-08 independent-review
HIGH-1 fix).** An earlier revision wrote the RAW ``payload`` straight to the
JSONL line — only the sqlite side ever saw
:func:`~tos.evidence.scrub_secret_fields`, since ``secret_keys`` is
store-private. A plaintext secret therefore reached the emergency file even
though the sqlite copy was clean. :func:`record_halt` now calls
:meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.scrub_payload` FIRST
(the store's own ``secret_keys``, never a second, possibly-divergent list),
passes that ALREADY-scrubbed payload into :meth:`SqliteEvidenceStore.append`
(idempotent to re-scrub — see that method's own docstring), and writes the
SAME scrubbed object to the JSONL line. Both copies are therefore
byte-identical AND both are clean.

Only :data:`~tos.evidence.DurabilityClass.EMERGENCY_DURABLE` records are
accepted — :func:`record_halt` refuses any other durability class rather than
silently writing a non-emergency record through the emergency path.

Firewall: stdlib (``json``, ``os``) + ``tos.evidence``/``tos.workload`` +
``tos_runtime.evidence.store`` only.
"""

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
        """Bind to ``path`` — the file is created on first :meth:`append` if absent.

        Args:
            path: The JSONL file path. Parent directory must already exist.
        """
        self.path = path

    def append(self, record: Mapping[str, object]) -> None:
        """Write one JSON line and ``fsync`` before returning.

        Args:
            record: The record to serialize (``sort_keys=True`` for a
                deterministic line, matching this codebase's canonical-bytes
                convention elsewhere).

        Raises:
            OSError: If the write or ``fsync`` fails — propagated, never
                swallowed (this path exists specifically so a caller can
                trust that a returned call really reached stable storage).
        """
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
    """Durably record one HALT/protective-action event through BOTH paths.

    Args:
        store: The sqlite evidence store (chained, replayable path).
        emergency_log: The sqlite-independent JSONL path.
        payload: The HALT record's own fields.
        kind: The record kind (e.g. an engine ``HaltReason`` or gateway
            ``SendHaltReason`` value, as a string — caller vocabulary).
        record_class: The retention/durability class label.
        durability_class: Must be
            :data:`~tos.evidence.DurabilityClass.EMERGENCY_DURABLE` — any
            other value is refused (this path is reserved for emergency
            records, design #40 §2 item 2).
        runtime_identity: The issuing process's identity.

    Returns:
        The sqlite store's commit receipt — returned only after BOTH the
        sqlite append AND the emergency-log append have succeeded.

    Raises:
        ValueError: If ``durability_class`` is not ``EMERGENCY_DURABLE``.
        Exception: Whatever the failing path raised — the sqlite append's
            own exceptions propagate unchanged; the emergency-log append's
            ``OSError`` propagates unchanged too. Either way no receipt is
            ever returned to the caller on a partial success.
    """
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
