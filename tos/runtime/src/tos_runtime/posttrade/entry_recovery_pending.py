"""Strict parsing and scoped access for durable entry-discharge pending records."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from tos.rcl import CapacityState

from tos_runtime.evidence.store import SqliteEvidenceStore

ENTRY_DISCHARGE_PENDING_KIND = "ENTRY_DISCHARGE_PENDING"


@dataclass(frozen=True)
class EntryDischargePending:
    seq: int
    attempt_id: str
    close_reservation_id: str
    close_last_seq: int
    close_state: CapacityState
    entry_reservation_id: str
    entry_last_seq: int
    account: str
    instrument: str
    proof_id: str
    payload: Mapping[str, object]

    @property
    def identity(self) -> tuple[object, ...]:
        return (
            self.attempt_id,
            self.close_reservation_id,
            self.close_last_seq,
            self.close_state.value,
            self.entry_reservation_id,
            self.entry_last_seq,
            self.account,
            self.instrument,
            self.proof_id,
            json.dumps(dict(self.payload), sort_keys=True, separators=(",", ":")),
        )


def strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate evidence key")
        result[key] = value
    return result


def _from_row(row: tuple[object, ...]) -> EntryDischargePending:
    seq, payload_json = row
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        raise ValueError("invalid pending sequence")
    if not isinstance(payload_json, (str, bytes, bytearray)):
        raise ValueError("invalid pending payload encoding")
    decoded = json.loads(payload_json, object_pairs_hook=strict_object)
    payload = decoded.get("payload") if isinstance(decoded, dict) else None
    if not isinstance(payload, dict):
        raise ValueError("pending payload is malformed")
    attempt_id, close_id = payload.get("attempt_id"), payload.get(
        "close_reservation_id"
    )
    close_seq, state_value = payload.get("close_last_seq"), payload.get("close_state")
    entry_id, entry_seq = payload.get("entry_reservation_id"), payload.get(
        "entry_last_seq"
    )
    account, instrument = payload.get("account"), payload.get("instrument")
    proof_id, egress_payload = payload.get("proof_id"), payload.get("egress_payload")
    if (
        not isinstance(attempt_id, str)
        or not attempt_id
        or not isinstance(close_id, str)
        or not close_id
        or isinstance(close_seq, bool)
        or not isinstance(close_seq, int)
        or close_seq < 0
        or not isinstance(state_value, str)
        or not isinstance(entry_id, str)
        or not entry_id
        or isinstance(entry_seq, bool)
        or not isinstance(entry_seq, int)
        or entry_seq < 0
        or not isinstance(account, str)
        or not account
        or not isinstance(instrument, str)
        or not instrument
        or not isinstance(proof_id, str)
        or not proof_id
        or not isinstance(egress_payload, dict)
    ):
        raise ValueError("pending binding is incomplete")
    try:
        state = CapacityState(state_value)
    except ValueError as exc:
        raise ValueError("pending close state is invalid") from exc
    return EntryDischargePending(
        seq,
        attempt_id,
        close_id,
        close_seq,
        state,
        entry_id,
        entry_seq,
        account,
        instrument,
        proof_id,
        egress_payload,
    )


def pending_items(
    store: SqliteEvidenceStore, *, account: str, instrument: str
) -> tuple[EntryDischargePending, ...] | None:
    try:
        rows = store.connection.execute(
            "SELECT seq, payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
            (ENTRY_DISCHARGE_PENDING_KIND,),
        ).fetchall()
        parsed = tuple(_from_row(row) for row in rows)
    except Exception:  # noqa: BLE001 - a partial or ambiguous queue is not actionable
        return None
    grouped: dict[str, list[EntryDischargePending]] = {}
    for item in parsed:
        if item.account == account and item.instrument == instrument:
            grouped.setdefault(item.attempt_id, []).append(item)
    result = [
        items[-1] for items in grouped.values() if len({x.identity for x in items}) == 1
    ]
    return tuple(sorted(result, key=lambda item: item.seq))
