"""``SqliteEvidenceReceiptReader`` — the concrete"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping
from decimal import Decimal

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.recon.ports import (
    EgressReceiptObservation,
    WitnessScope,
    WitnessUnavailable,
)

__all__ = ["SqliteEvidenceReceiptReader"]

_EGRESS_RESULT_KINDS: frozenset[str] = frozenset(
    {"EGRESS_RESULT_CONSUMED", "RESULT_UNMATCHED"}
)
_FINALITY_PROOF_KIND = "POSTTRADE_FINALITY_PROOF"
_FINALITY_PROOF_IDEMPOTENCY_PREFIXES: tuple[str, ...] = (
    "synthetic-fqp-proof:",
    "broker-fqp-proof:",
)


def _to_decimal(value: object) -> Decimal | None:
    """Best-effort ``Decimal`` coercion for a JSON-decoded numeric field (mirrors"""
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
    """Whether ``payload``'s instrument key falls within ``scope`` — never filtered by"""
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


_YYYYMMDD = re.compile(r"[0-9]{8}")


def _yyyymmdd_or_none(value: object) -> str | None:
    """A recorded ``trading_date`` token, or ``None`` when absent (every receipt recorded before"""
    if isinstance(value, str) and _YYYYMMDD.fullmatch(value) is not None:
        return value
    return None


class SqliteEvidenceReceiptReader:
    """A :class:`~tos_runtime.recon.ports.EvidenceReceiptReader` over the evidence store's own"""

    def __init__(self, store: SqliteEvidenceStore) -> None:
        """Bind this reader to a store."""
        self._store = store

    def _read_kind(self, kinds: frozenset[str]) -> list[dict[str, object]]:
        """Read every matching entry's scrubbed payload, in commit (``seq``) order."""
        placeholders = ",".join("?" for _ in kinds)
        query = (
            f"SELECT payload_json FROM entries WHERE kind IN ({placeholders}) "
            "ORDER BY seq ASC"
        )
        try:
            cursor = self._store.connection.execute(query, tuple(kinds))
            raw_rows = cursor.fetchall()
        except sqlite3.Error as exc:
            raise WitnessUnavailable(
                f"SqliteEvidenceReceiptReader: evidence store query failed: {exc}"
            ) from exc
        payloads: list[dict[str, object]] = []
        for (payload_json,) in raw_rows:
            decoded = json.loads(payload_json)
            payload = decoded.get("payload", decoded)
            if isinstance(payload, dict):
                payloads.append(payload)
        return payloads

    def _attempts_with_finality_proof(self) -> frozenset[str]:
        """Every ``attempt_id`` with a durably recorded ``POSTTRADE_FINALITY_PROOF`` (module"""
        attempts: set[str] = set()
        for row in self._read_kind(frozenset({_FINALITY_PROOF_KIND})):
            key = row.get("idempotency_key")
            if not isinstance(key, str):
                continue
            for prefix in _FINALITY_PROOF_IDEMPOTENCY_PREFIXES:
                if key.startswith(prefix):
                    attempts.add(key[len(prefix) :])
        return frozenset(attempts)

    def receipts(self, scope: WitnessScope) -> tuple[EgressReceiptObservation, ...]:
        """Return every recorded ``EGRESS_RESULT`` receipt observation within ``scope``"""
        proven = self._attempts_with_finality_proof()
        observations: list[EgressReceiptObservation] = []
        for row in self._read_kind(_EGRESS_RESULT_KINDS):
            if not _in_scope(row, scope):
                continue
            instrument_key = row.get("instrument_key")
            account = (
                instrument_key.get("account")
                if isinstance(instrument_key, Mapping)
                else None
            )
            instrument = (
                instrument_key.get("instrument")
                if isinstance(instrument_key, Mapping)
                else None
            )
            attempt_id = row.get("attempt_id")
            attempt_id = attempt_id if isinstance(attempt_id, str) else None
            egress_result_kind = row.get("egress_result_kind")
            broker_execution_id = row.get("broker_execution_id")
            observations.append(
                EgressReceiptObservation(
                    attempt_id=attempt_id,
                    account=account if isinstance(account, str) else None,
                    instrument=instrument if isinstance(instrument, str) else None,
                    egress_result_kind=(
                        egress_result_kind
                        if isinstance(egress_result_kind, str)
                        else None
                    ),
                    broker_execution_id=(
                        broker_execution_id
                        if isinstance(broker_execution_id, str)
                        else None
                    ),
                    filled_quantity=_to_decimal(row.get("filled_quantity")),
                    remaining_quantity=_to_decimal(row.get("remaining_quantity")),
                    finality_proof_recorded=(
                        attempt_id is not None and attempt_id in proven
                    ),
                    source_ref="evidence-egress-result",
                    trading_date=_yyyymmdd_or_none(row.get("trading_date")),
                )
            )
        return tuple(observations)
