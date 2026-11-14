"""tos_runtime.riskstate.position — single-source, conservative position observation"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from decimal import Decimal

from tos.engine import FILL_RESULT_KINDS, TERMINAL_RESULT_KINDS
from tos.position import (
    ConsumedResult,
    PositionObservation,
    classify_sealed_sends,
    conservative_current_usage,
    in_flight_overlap_effect,
    worst_credible_directional_usage,
)
from tos.position import (
    SealedSend as _SealedSend,
)

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.recon.ports import WitnessUnavailable

__all__ = [
    "PositionObservation",
    "worst_credible_directional_usage",
    "conservative_current_usage",
    "in_flight_overlap_effect",
    "EvidencePositionReader",
]

_SEND_SEALED_KIND = "SEND_SEALED"

_TERMINAL_RESULT_TOKENS: frozenset[str] = frozenset(
    kind.value for kind in TERMINAL_RESULT_KINDS
)


_FILL_RESULT_TOKENS: frozenset[str] = frozenset(
    kind.value for kind in FILL_RESULT_KINDS
)


def _read_kind_payloads_with_seq(
    store: SqliteEvidenceStore, kind: str
) -> list[tuple[int, dict[str, object]]]:
    """Read every matching entry's ``(seq, scrubbed payload)``, in commit (``seq``) order — the exact"""
    try:
        cursor = store.connection.execute(
            "SELECT seq, payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
            (kind,),
        )
        rows = cursor.fetchall()
    except sqlite3.Error as exc:
        raise WitnessUnavailable(
            f"EvidencePositionReader: evidence store query failed for kind={kind!r}: {exc}"
        ) from exc
    payloads: list[tuple[int, dict[str, object]]] = []
    for seq, payload_json in rows:
        decoded = json.loads(payload_json)
        payload = decoded.get("payload", decoded)
        if isinstance(payload, dict):
            payloads.append((seq, payload))
    return payloads


def _read_kind_payloads(
    store: SqliteEvidenceStore, kind: str
) -> list[dict[str, object]]:
    return [payload for _, payload in _read_kind_payloads_with_seq(store, kind)]


def _to_decimal(value: object) -> Decimal | None:
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


_ResultSignature = tuple[object, Decimal | None, Decimal | None, object]


def _applied_signature(payload: Mapping[str, object]) -> _ResultSignature | None:
    """The applied result's own payload signature, rebuilt from its ``EGRESS_RESULT_CONSUMED``"""
    kind = payload.get("egress_result_kind")
    execution_id = payload.get("broker_execution_id")
    if kind not in _FILL_RESULT_TOKENS:
        return (kind, None, None, execution_id)
    filled = _to_decimal(payload.get("filled_quantity"))
    remaining = _to_decimal(payload.get("remaining_quantity"))
    if filled is None or remaining is None:
        return None
    return (kind, filled, remaining, execution_id)


def _unmatched_signature(payload: Mapping[str, object]) -> _ResultSignature | None:
    """A ``RESULT_UNMATCHED`` row's signature — that row copies all four fields from the refused"""
    kind = payload.get("egress_result_kind")
    filled = _to_decimal(payload.get("filled_quantity"))
    remaining = _to_decimal(payload.get("remaining_quantity"))
    if kind in _FILL_RESULT_TOKENS:
        if filled is None or remaining is None:
            return None
    elif filled is not None or remaining is not None:
        return None
    return (kind, filled, remaining, payload.get("broker_execution_id"))


def _seal_in_scope(
    seal: Mapping[str, object], *, account: str, instrument: str
) -> bool:
    """Whether a ``SEND_SEALED`` row's ``send_seal.instrument_key`` matches this reader's"""
    instrument_key = seal.get("instrument_key")
    if not isinstance(instrument_key, Mapping):
        return False
    return (
        instrument_key.get("account") == account
        and instrument_key.get("instrument") == instrument
    )


def _read_sealed_sends(
    store: SqliteEvidenceStore, *, account: str, instrument: str
) -> tuple[_SealedSend, ...]:
    """Every durably recorded ``SEND_SEALED`` row's ``(attempt_id, outbound_side,"""
    sealed: list[_SealedSend] = []
    for payload in _read_kind_payloads(store, _SEND_SEALED_KIND):
        attempt_id = payload.get("attempt_id")
        if not isinstance(attempt_id, str):
            continue
        seal = payload.get("send_seal")
        if not isinstance(seal, dict) or not _seal_in_scope(
            seal, account=account, instrument=instrument
        ):
            continue
        raw_side = seal.get("outbound_side")
        side = raw_side if isinstance(raw_side, str) else None
        quantity = _to_decimal(seal.get("outbound_quantity"))
        sealed.append(_SealedSend(attempt_id=attempt_id, side=side, quantity=quantity))
    return tuple(sealed)


def _in_scope(payload: Mapping[str, object], *, account: str, instrument: str) -> bool:
    """Whether an ``EngineEvidenceRecord``-shaped payload's ``instrument_key`` matches this"""
    instrument_key = payload.get("instrument_key")
    if not isinstance(instrument_key, Mapping):
        return False
    return (
        instrument_key.get("account") == account
        and instrument_key.get("instrument") == instrument
    )


class EvidencePositionReader:
    """Folds the durable evidence store into one :class:`PositionObservation` for a single"""

    def __init__(
        self,
        evidence_store: SqliteEvidenceStore,
        *,
        account: str,
        instrument: str,
        buy_side_token: str,
        sell_side_token: str,
    ) -> None:
        """Bind this reader to a store, scope, and the two recognized side tokens."""
        self._store = evidence_store
        self._account = account
        self._instrument = instrument
        self._buy_side_token = buy_side_token
        self._sell_side_token = sell_side_token

    def _read_terminal_results(
        self,
    ) -> tuple[dict[str, ConsumedResult], set[str], list[str]]:
        """Read the two terminal-result evidence kinds within scope (module docstring's"""
        consumed_payloads = [
            (seq, payload)
            for seq, payload in _read_kind_payloads_with_seq(
                self._store, "EGRESS_RESULT_CONSUMED"
            )
            if _in_scope(payload, account=self._account, instrument=self._instrument)
        ]
        unmatched_payloads = [
            (seq, payload)
            for seq, payload in _read_kind_payloads_with_seq(
                self._store, "RESULT_UNMATCHED"
            )
            if _in_scope(payload, account=self._account, instrument=self._instrument)
        ]
        consumed_by_attempt: dict[str, ConsumedResult] = {}
        latest_consumed_seq: dict[str, int] = {}
        applied_signatures: dict[str, set[_ResultSignature]] = {}
        unmatched_attempts: set[str] = set()
        for seq, payload in consumed_payloads:
            attempt_id = payload.get("attempt_id")
            if not isinstance(attempt_id, str):
                continue
            latest_consumed_seq[attempt_id] = seq
            signature = _applied_signature(payload)
            if signature is not None:
                applied_signatures.setdefault(attempt_id, set()).add(signature)
            raw_kind = payload.get("egress_result_kind")
            consumed_by_attempt[attempt_id] = ConsumedResult(
                result_kind=raw_kind if isinstance(raw_kind, str) else None,
                filled_quantity=_to_decimal(payload.get("filled_quantity")),
                remaining_quantity=_to_decimal(payload.get("remaining_quantity")),
            )
        for seq, payload in unmatched_payloads:
            if payload.get("result_disposition") == "DUPLICATE":
                continue
            attempt_id = payload.get("attempt_id")
            if not isinstance(attempt_id, str):
                continue
            latest = consumed_by_attempt.get(attempt_id)
            if latest is None:
                unmatched_attempts.add(attempt_id)
                continue
            fill_covered = (
                _to_decimal(payload.get("filled_quantity")) or Decimal(0)
            ) <= (latest.filled_quantity or Decimal(0))
            superseded = seq < latest_consumed_seq[attempt_id]
            unmatched_signature = _unmatched_signature(payload)
            replayed = unmatched_signature is not None and (
                unmatched_signature in applied_signatures.get(attempt_id, set())
            )
            if not (fill_covered and (superseded or replayed)):
                unmatched_attempts.add(attempt_id)
        sources: list[str] = []
        if consumed_payloads:
            sources.append("evidence:EGRESS_RESULT_CONSUMED")
        if unmatched_payloads:
            sources.append("evidence:RESULT_UNMATCHED")
        return consumed_by_attempt, unmatched_attempts, sources

    def observe(self) -> PositionObservation:
        """Fold the durable evidence into one :class:`PositionObservation` (module docstring's"""
        sealed = _read_sealed_sends(
            self._store, account=self._account, instrument=self._instrument
        )
        consumed_by_attempt, unmatched_attempts, result_sources = (
            self._read_terminal_results()
        )
        (
            confirmed_net,
            unknown_buy,
            unknown_sell,
            in_flight_buy,
            in_flight_sell,
            attempts_seen,
        ) = classify_sealed_sends(
            sealed,
            consumed_by_attempt=consumed_by_attempt,
            unmatched_attempts=unmatched_attempts,
            buy_side_token=self._buy_side_token,
            sell_side_token=self._sell_side_token,
            terminal_result_kinds=_TERMINAL_RESULT_TOKENS,
        )
        sources: list[str] = []
        if sealed:
            sources.append(f"evidence:{_SEND_SEALED_KIND}")
        sources.extend(result_sources)

        return PositionObservation(
            scope_key=f"{self._account}::{self._instrument}",
            confirmed_net=confirmed_net,
            unknown_buy=unknown_buy,
            unknown_sell=unknown_sell,
            in_flight_buy=in_flight_buy,
            in_flight_sell=in_flight_sell,
            attempts_seen=attempts_seen,
            sources=tuple(sources),
        )
