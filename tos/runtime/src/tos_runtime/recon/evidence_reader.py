"""``SqliteEvidenceReceiptReader`` — the concrete
:class:`~tos_runtime.recon.ports.EvidenceReceiptReader` adapter (TOS Phase 5 W1 close-out, GAP
1). :mod:`tos_runtime.recon.ports`'s own module docstring names this exact gap verbatim: "the
evidence-receipt side is :class:`EvidenceReceiptReader`, defined here ... this package ships no
concrete implementation of it (out of this lane's file list); a future lane wires one the same
way :mod:`tos_runtime.recon.witness_synthetic` reads the evidence store directly." This module is
that future lane.

**Read path — mirrors :mod:`tos_runtime.recon.witness_synthetic` exactly (same store, same
seam).** The durable ``EGRESS_RESULT_CONSUMED`` (applied) / ``RESULT_UNMATCHED`` (recorded but
not applied) evidence rows (:class:`tos.engine.records.EngineEvidenceRecord`, appended by
:class:`~tos_runtime.evidence.sinks.EngineEvidenceSinkAdapter`) already carry ``attempt_id`` /
``instrument_key`` / ``egress_result_kind`` / ``filled_quantity`` / ``remaining_quantity`` /
``broker_execution_id`` directly (see that model's own field docstrings). This reader issues a
plain, read-only ``SELECT ... FROM entries WHERE kind IN (...)`` over the store's own public
``.connection`` property — the exact same seam :mod:`tos_runtime.evidence.backup` and
:mod:`tos_runtime.recon.witness_synthetic` already reuse for the identical reason (the store
exposes no "read entries by kind, with payload" method of its own). It never calls
``store.append`` — read-only throughout.

**``finality_proof_recorded`` — the one non-trivial join.** A separately recorded
``POSTTRADE_FINALITY_PROOF`` evidence row (:class:`tos.posttrade.records.PostTradeFinalityProof`,
appended by :meth:`~tos_runtime.engine.driver.EngineDriver._project_finality` right after
:meth:`~tos_runtime.posttrade.finality.SyntheticFinalityProducer.produce` succeeds) carries no
``attempt_id`` field of its own — ADR-002-024 §11 line 320-326's covered set for this artifact is
obligation identity/version/leg/scope/amount/class/generation/``does_not_prove`` only (measured
directly against ``tos/src/tos/posttrade/records.py``'s own ``_COVERED_FIELDS``). The one durable
thread back to the attempt is :class:`~tos_runtime.posttrade.finality.SyntheticFinalityProducer`'s
own ``idempotency_key`` literal, ``f"synthetic-fqp-proof:{payload.attempt_id}"``
(``tos_runtime/posttrade/finality.py``, verbatim, cited not re-derived) — this reader strips that
exact prefix to recover the attempt id a proof was issued for.

**Disclosed coupling (measured, not assumed).** This ties ``finality_proof_recorded``'s
correctness to that literal prefix staying stable. A future producer that changes its own
idempotency-key format without updating this reader would silently stop being DETECTED here — it
would never be falsely reported as recorded (parsing a key that no longer matches the prefix
simply excludes that attempt from the proven set), which is the fail-closed direction, but the
coupling itself is real and is recorded here rather than hidden.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``json``, ``sqlite3``) +
``tos_runtime.evidence.store`` + ``tos_runtime.recon.ports`` only. No ``os.environ``, no
network, no writer call.
"""

from __future__ import annotations

import json
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

#: The two ``EvidenceKind`` members carrying a re-injected egress result's own reported
#: magnitudes (:mod:`tos_runtime.recon.witness_synthetic`'s own module docstring — the identical
#: pair, cited as plain strings for the same reason that module gives).
_EGRESS_RESULT_KINDS: frozenset[str] = frozenset(
    {"EGRESS_RESULT_CONSUMED", "RESULT_UNMATCHED"}
)
_FINALITY_PROOF_KIND = "POSTTRADE_FINALITY_PROOF"
#: The exact literal :class:`~tos_runtime.posttrade.finality.SyntheticFinalityProducer.produce`
#: uses to derive a proof's own ``idempotency_key`` (``tos_runtime/posttrade/finality.py``,
#: verbatim ``f"synthetic-fqp-proof:{payload.attempt_id}"``) — cited, not re-derived, so a drift
#: there is a visible grep target, not a hidden assumption (module docstring's "disclosed
#: coupling").
_FINALITY_PROOF_IDEMPOTENCY_PREFIX = "synthetic-fqp-proof:"


def _to_decimal(value: object) -> Decimal | None:
    """Best-effort ``Decimal`` coercion for a JSON-decoded numeric field (mirrors
    :func:`tos_runtime.recon.witness_synthetic._to_decimal` exactly — same store, same
    ``json.dumps``/``json.loads`` round-trip)."""
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
    """Whether ``payload``'s instrument key falls within ``scope`` — never filtered by
    ``attempt_id`` (:meth:`~tos_runtime.recon.ports.EvidenceReceiptReader.receipts`'s own
    docstring: a receipt for an attempt outside ``scope.attempt_ids`` is the "receipt-only"
    classification, not something to drop; mirrors
    :func:`tos_runtime.recon.witness_synthetic._in_scope` exactly)."""
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


class SqliteEvidenceReceiptReader:
    """A :class:`~tos_runtime.recon.ports.EvidenceReceiptReader` over the evidence store's own
    ``EGRESS_RESULT_CONSUMED`` / ``RESULT_UNMATCHED`` rows (module docstring) — the concrete
    adapter :mod:`tos_runtime.recon.ports`'s own docstring says this package ships none of.
    """

    def __init__(self, store: SqliteEvidenceStore) -> None:
        """Bind this reader to a store.

        Args:
            store: The durable evidence store this reader reads (read-only — module docstring).
        """
        self._store = store

    def _read_kind(self, kinds: frozenset[str]) -> list[dict[str, object]]:
        """Read every matching entry's scrubbed payload, in commit (``seq``) order.

        Raises:
            WitnessUnavailable: If the underlying sqlite query fails (a locked or corrupt file)
                — never silently returned as "nothing recorded" (mirrors
                :meth:`tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness._read_rows`
                exactly for the identical failure mode over the identical store).
        """
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
        """Every ``attempt_id`` with a durably recorded ``POSTTRADE_FINALITY_PROOF`` (module
        docstring's "the one non-trivial join")."""
        attempts: set[str] = set()
        for row in self._read_kind(frozenset({_FINALITY_PROOF_KIND})):
            key = row.get("idempotency_key")
            if isinstance(key, str) and key.startswith(
                _FINALITY_PROOF_IDEMPOTENCY_PREFIX
            ):
                attempts.add(key[len(_FINALITY_PROOF_IDEMPOTENCY_PREFIX) :])
        return frozenset(attempts)

    def receipts(self, scope: WitnessScope) -> tuple[EgressReceiptObservation, ...]:
        """Return every recorded ``EGRESS_RESULT`` receipt observation within ``scope``
        (:meth:`~tos_runtime.recon.ports.EvidenceReceiptReader.receipts`'s own contract — never
        filtered down to only ``scope.attempt_ids``).

        Raises:
            WitnessUnavailable: If the underlying evidence-store query fails — an empty tuple
                here would collapse "genuinely nothing recorded" and "could not read" into the
                same observation, which :mod:`tos_runtime.recon.ports`'s own module docstring
                treats as unsafe for the analogous witness path; this reader holds the evidence
                store to the identical standard.
        """
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
                )
            )
        return tuple(observations)
