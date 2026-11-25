"""``SyntheticLedgerWitness`` — the Phase 5 ``BrokerWitness`` over the synthetic transport."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from decimal import Decimal

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.recon.ports import (
    WitnessOrder,
    WitnessOrderState,
    WitnessScope,
    WitnessSnapshot,
    WitnessUnavailable,
)

__all__ = ["EGRESS_KIND_TO_WITNESS_STATE", "SyntheticLedgerWitness"]

_EGRESS_RESULT_KINDS: frozenset[str] = frozenset(
    {"EGRESS_RESULT_CONSUMED", "RESULT_UNMATCHED"}
)

EGRESS_KIND_TO_WITNESS_STATE: Mapping[str, WitnessOrderState] = {
    "ACK": WitnessOrderState.ACKED,
    "FULL_FILL": WitnessOrderState.FILLED,
    "PARTIAL_FILL": WitnessOrderState.PARTIAL,
    "CANCEL_ACK": WitnessOrderState.CANCELLED,
    "EXPIRED": WitnessOrderState.CANCELLED,
    "REJECT": WitnessOrderState.CANCELLED,
    "TIMEOUT": WitnessOrderState.UNKNOWN,
    "UNKNOWN": WitnessOrderState.UNKNOWN,
}


def _to_decimal(value: object) -> Decimal | None:
    """Best-effort ``Decimal`` coercion for a JSON-decoded numeric field."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (str, int, float)):
        try:
            return Decimal(str(value))
        except (ValueError, ArithmeticError):
            return None
    return None


def _in_scope(payload: Mapping[str, object], scope: WitnessScope) -> bool:
    """Whether ``payload``'s instrument key falls within ``scope`` (account + optional"""
    instrument_key = payload.get("instrument_key")
    if not isinstance(instrument_key, Mapping):
        return False
    if instrument_key.get("account") != scope.account:
        return False
    if not scope.instrument_keys:
        return True
    return any(
        instrument_key.get("instrument") == key.instrument
        for key in scope.instrument_keys
    )


class SyntheticLedgerWitness:
    """A :class:`~tos_runtime.recon.ports.BrokerWitness` over the evidence store's own"""

    def __init__(
        self,
        store: SqliteEvidenceStore,
        *,
        kinds: frozenset[str] = _EGRESS_RESULT_KINDS,
        provenance: str = "synthetic-ledger",
    ) -> None:
        """Bind this witness to a store."""
        self._store = store
        self._kinds = kinds
        self._provenance = provenance

    def _read_rows(self) -> list[dict[str, object]]:
        """Read every matching entry's scrubbed payload, in commit (``seq``) order."""
        placeholders = ",".join("?" for _ in self._kinds)
        query = (
            f"SELECT payload_json FROM entries WHERE kind IN ({placeholders}) "
            "ORDER BY seq ASC"
        )
        try:
            cursor = self._store.connection.execute(query, tuple(self._kinds))
            raw_rows = cursor.fetchall()
        except sqlite3.Error as exc:
            raise WitnessUnavailable(
                f"SyntheticLedgerWitness: evidence store query failed: {exc}"
            ) from exc
        payloads: list[dict[str, object]] = []
        for (payload_json,) in raw_rows:
            decoded = json.loads(payload_json)
            payload = decoded.get("payload", decoded)
            if isinstance(payload, dict):
                payloads.append(payload)
        return payloads

    def _order_from_payload(self, payload: Mapping[str, object]) -> WitnessOrder:
        kind = payload.get("egress_result_kind")
        state = EGRESS_KIND_TO_WITNESS_STATE.get(
            kind if isinstance(kind, str) else "", WitnessOrderState.UNKNOWN
        )
        attempt_id = payload.get("attempt_id")
        broker_execution_id = payload.get("broker_execution_id")
        return WitnessOrder(
            attempt_id=attempt_id if isinstance(attempt_id, str) else None,
            broker_execution_id=(
                broker_execution_id if isinstance(broker_execution_id, str) else None
            ),
            quantity=_to_decimal(payload.get("filled_quantity")),
            remaining=_to_decimal(payload.get("remaining_quantity")),
            state=state,
        )

    def observe(self, scope: WitnessScope) -> WitnessSnapshot:
        """Reconstruct a :class:`WitnessSnapshot` from the evidence store's recorded"""
        rows = self._read_rows()
        orders = tuple(
            self._order_from_payload(row) for row in rows if _in_scope(row, scope)
        )
        return WitnessSnapshot(
            observed_at_generation=scope.as_of_generation,
            orders=orders,
            positions=(),
            cash=None,
            provenance=self._provenance,
            independent_of_evidence_store=False,
        )
