"""``SyntheticLedgerWitness`` — the Phase 5 ``BrokerWitness`` over the synthetic transport.

**No ledger to read (measured).** ``tos.brokeradapter.synthetic.SyntheticPaperTransport``
is, by its own module docstring, "network 0, credentials 0, route 0" and
"**Deterministic by construction** ... no clock, no RNG, no ambient state" — it is a pure
function from an :class:`~tos.engine.records.AttemptRequest` plus an injected
:class:`~tos.brokeradapter.synthetic.SyntheticFillPolicy` to an
:class:`~tos.engine.records.EgressResultPayload`. It keeps **no durable record of what it
"accepted"** at all; there is no synthetic-transport-side ledger this witness could read.

**The durable source that actually exists.** What the runtime durably keeps is the
*driver's re-injected result*, once applied: ``tos.engine.records.EngineEvidenceRecord``
entries of kind ``EGRESS_RESULT_CONSUMED`` (applied) or ``RESULT_UNMATCHED`` (recorded but
not applied — Phase 3 A-K-2), each carrying ``attempt_id`` /
``instrument_key`` / ``egress_result_kind`` / ``filled_quantity`` / ``remaining_quantity`` /
``broker_execution_id`` (see that model's own field docstrings). These are appended by
``tos_runtime.evidence.sinks.EngineEvidenceSinkAdapter`` into the same
:class:`~tos_runtime.evidence.store.SqliteEvidenceStore` every other evidence record lives
in. This witness reconstructs :class:`~tos_runtime.recon.ports.WitnessOrder` rows from
exactly those rows — it invents no separate ledger.

**Read path.** :class:`~tos_runtime.evidence.store.SqliteEvidenceStore` exposes no
"read entries by kind, with payload" method of its own (only ``replay()``/
``iter_entry_meta()``, both meta/digest-only). Rather than add one to a module this
package does not own, this witness reuses the store's own public ``.connection``
property — the exact same seam ``tos_runtime.evidence.backup`` already reuses for its own
read (``store.connection.backup(dest_conn)``) — and issues a plain, read-only
``SELECT ... FROM entries WHERE kind IN (...)`` against it.

**⚠ Phase 5 independence caveat (disclosed, not hidden).** This witness's ``provenance``
is ``"synthetic-ledger"`` precisely because it reads the *same* durable evidence store as
the evidence-receipt path (:class:`~tos_runtime.recon.ports.EvidenceReceiptReader`) reads.
:class:`~tos_runtime.recon.service.ReconciliationService` still assigns this witness path
its own distinct independence-class label (module docstring of ``service.py``) — the
kernel's ``tos.recon`` predicates treat independence as an *injected* judgment they never
compute themselves (``tos/src/tos/recon/state.py`` docstring) — but a CORROBORATED verdict
built only from ``{RCL, EVIDENCE_RECEIPT, BROKER_WITNESS=this class}`` for a
capacity-releasing field does **not yet** reflect genuine broker-independent corroboration,
because two of those three paths are byte-derived from the one store. This becomes
substantively independent only once a real (e.g. KIS) ``BrokerWitness`` — reading an
actual broker-side ledger — replaces this class (Phase 5 plan §2 decision 3: "KIS 는
후속"). Every :class:`~tos_runtime.recon.ports.WitnessSnapshot` this witness returns
carries ``provenance="synthetic-ledger"`` so this limitation stays visible to any
downstream consumer or reviewer, never silently indistinguishable from a real read.

Firewall: stdlib (``json``, ``sqlite3``) + ``tos_runtime.evidence.store`` +
``tos_runtime.recon.ports`` only. No ``os.environ``, no network, no writer call (this
module never calls ``store.append`` — read-only throughout).
"""

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

__all__ = ["SyntheticLedgerWitness"]

#: The two ``EvidenceKind`` members (``tos.engine.vocabulary.EvidenceKind``) that carry a
#: re-injected egress result's own reported magnitudes (module docstring). Named as plain
#: strings — this module does not import ``tos.engine.vocabulary`` just for these two
#: literals, matching ``tos_runtime.evidence.sinks``'s own kind-is-a-string convention.
_EGRESS_RESULT_KINDS: frozenset[str] = frozenset(
    {"EGRESS_RESULT_CONSUMED", "RESULT_UNMATCHED"}
)

#: ``EgressResultKind`` (``tos.engine.vocabulary``) -> :class:`WitnessOrderState`. Any
#: value absent from this map (including ``None``) falls back to ``UNKNOWN`` — fail-closed,
#: never a silent KeyError and never a guessed "probably fine" state.
_EGRESS_KIND_TO_WITNESS_STATE: Mapping[str, WitnessOrderState] = {
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
    """Best-effort ``Decimal`` coercion for a JSON-decoded numeric field.

    ``SqliteEvidenceStore`` round-trips payloads through ``json.dumps``/``json.loads``
    (module docstring's "read path"), so a ``CanonicalDecimal`` written as a string
    (pydantic's own JSON mode) comes back as ``str``; a bare ``int``/``float`` is accepted
    too. ``None`` and any other type pass through as ``None`` (fail-closed — never a
    fabricated zero standing in for an absent magnitude).
    """
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
    """Whether ``payload``'s instrument key falls within ``scope`` (account + optional
    instrument narrowing) — never filtered by ``attempt_id`` (module docstring: orphan
    detection needs unfiltered orders)."""
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
    """A :class:`~tos_runtime.recon.ports.BrokerWitness` over the evidence store's own
    recorded ``EGRESS_RESULT`` facts (module docstring) — Phase 5's only concrete
    ``BrokerWitness`` (plan §2 decision 3).
    """

    def __init__(
        self,
        store: SqliteEvidenceStore,
        *,
        kinds: frozenset[str] = _EGRESS_RESULT_KINDS,
        provenance: str = "synthetic-ledger",
    ) -> None:
        """Bind this witness to a store.

        Args:
            store: The durable evidence store this witness reads (read-only — see module
                docstring).
            kinds: The evidence ``kind`` values considered (defaults to the two
                ``EGRESS_RESULT``-bearing kinds named in the module docstring).
            provenance: The honesty label stamped on every returned snapshot (module
                docstring's independence caveat) — never overridden to claim a genuine
                broker read from this class.
        """
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
        state = _EGRESS_KIND_TO_WITNESS_STATE.get(
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
        """Reconstruct a :class:`WitnessSnapshot` from the evidence store's recorded
        ``EGRESS_RESULT`` facts within ``scope`` (module docstring).

        Raises:
            WitnessUnavailable: If the underlying evidence store query fails (e.g. a
                locked or corrupt sqlite file) — never returned as an empty snapshot.
        """
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
        )
