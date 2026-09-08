"""Kernel evidence-sink adapters over the durable store (design #40 D3, §2 item 6).

:class:`EngineEvidenceSinkAdapter` satisfies :class:`tos.engine.sink.EvidenceSink`;
:class:`GatewayEvidenceSinkAdapter` satisfies
:class:`tos.egressgw.gateway.GatewayEvidenceSink`. Both Protocols declare
``record(...) -> None`` — the durability contract
(ADR-002-016 :19, design #34's own gateway module docstring: "gateway 는
sink.record 반환값을 보지 않으므로 «record 가 반환되면 durable» 계약을 어댑터가
보장") is therefore upheld **procedurally**, not through a return value the
Protocol has no room for: each adapter's ``record()`` calls
:meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.append` — synchronous,
raises on any failure, returns only after a durable commit — and only THEN
returns ``None`` to its caller. By the time
``BrokerEgressGateway.__call__``'s ``SEND_STARTED`` call to this adapter
returns, the receipt already existed; the adapter simply never had a channel
to hand it back through; that is exactly the ADR gap this module closes.

**``on_refusal`` observer (kernel round #1 §3, lane B).**
:class:`GatewayEvidenceSinkAdapter` accepts an optional ``on_refusal``
callback, invoked AFTER the durable ``store.append`` returns, and only for a
``kind == "SEND_REFUSED"`` record. This sink stays evidence-only — it never
itself writes to the rcl log; the observer is how
``tos_runtime.rcl.obligation.CapacityObligationRecorder`` gets a chance to
verify a refusal's preserved-capacity obligation without this adapter
knowing anything about rcl. An exception the observer raises is NOT caught
here — it propagates to the gateway's own caller, the same "never a silent
stop" reasoning ``BrokerEgressGateway._halt``'s own docstring gives for why
its halt path itself never swallows a failure: an obligation the observer
could not verify is not a success either.

**Contract change (independent review finding #8).** Before ``on_refusal``
existed, ``GatewayEvidenceSinkAdapter.record`` could raise only from the
``store.append`` call itself — the refusal path could not raise for any
OTHER reason. With ``on_refusal`` wired (as it is in every compose root that
constructs :class:`~tos_runtime.rcl.obligation.CapacityObligationRecorder`),
a failure inside the observer — e.g.
:class:`~tos_runtime.rcl.projection.SqliteReservationProjectionReader`
hitting a locked or unreachable sqlite database — now ALSO propagates out
of this ``record()`` call and, transitively, out of
:meth:`~tos.egressgw.gateway.BrokerEgressGateway.__call__` for a refused
send. This is deliberate and fail-closed, consistent with the "never a
silent stop" reasoning above: a ``SEND_REFUSED`` whose preserved-capacity
obligation this process could not verify is not something the caller should
be told succeeded (silently) either. It is still a genuine behavior change
callers of the gateway need to be aware of.

Firewall: stdlib + ``tos.engine``/``tos.egressgw``/``tos.workload`` +
``tos_runtime.evidence.store`` only.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from tos.egressgw.records import GatewayEvidenceRecord
from tos.engine.records import EngineEvidenceRecord
from tos.workload import RuntimeIdentity

from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["EngineEvidenceSinkAdapter", "GatewayEvidenceSinkAdapter"]


#: The default record_class label when a caller-supplied ``record_class_by_kind``
#: mapping has no entry for a given kind — reuses the kind string itself
#: rather than inventing an unconfigured taxonomy (CLAUDE.md "configuration-
#: driven only": a caller who wants a real per-class taxonomy supplies the
#: mapping; this default only keeps every record classifiable, never silently
#: dropped).
def _resolve_record_class(kind: str, record_class_by_kind: Mapping[str, str]) -> str:
    """Resolve ``kind`` to a record_class label via the injected mapping."""
    return record_class_by_kind.get(kind, kind)


class EngineEvidenceSinkAdapter:
    """Durable :class:`tos.engine.sink.EvidenceSink` over a
    :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`."""

    def __init__(
        self,
        store: SqliteEvidenceStore,
        *,
        record_class_by_kind: Mapping[str, str] | None = None,
        runtime_identity: RuntimeIdentity | None = None,
    ) -> None:
        """Bind this adapter to a store.

        Args:
            store: The durable evidence store every record is appended into.
            record_class_by_kind: Injected ``EvidenceKind`` value ->
                record_class mapping; a missing entry falls back to the kind
                string itself (never hard-coded).
            runtime_identity: Bound onto every record this adapter appends.
        """
        self._store = store
        self._record_class_by_kind = dict(record_class_by_kind or {})
        self._runtime_identity = runtime_identity

    def record(self, record: EngineEvidenceRecord) -> None:
        """Durably append one engine evidence record (design #31 §12-5 Protocol).

        Returns only after :meth:`SqliteEvidenceStore.append` durably
        commits — raises on any failure, never swallows one.
        """
        kind = record.kind.value
        self._store.append(
            record.model_dump(mode="json"),
            kind=kind,
            record_class=_resolve_record_class(kind, self._record_class_by_kind),
            runtime_identity=self._runtime_identity,
        )


class GatewayEvidenceSinkAdapter:
    """Durable :class:`tos.egressgw.gateway.GatewayEvidenceSink` over a
    :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`.

    See the module docstring for how the ``SEND_STARTED`` /
    "record returns only after the receipt" contract is upheld through a
    ``-> None`` Protocol.
    """

    def __init__(
        self,
        store: SqliteEvidenceStore,
        *,
        record_class_by_kind: Mapping[str, str] | None = None,
        runtime_identity: RuntimeIdentity | None = None,
        on_refusal: Callable[[GatewayEvidenceRecord], None] | None = None,
    ) -> None:
        """Bind this adapter to a store.

        Args:
            store: The durable evidence store every record is appended into.
            record_class_by_kind: Injected gateway ``kind`` string ->
                record_class mapping (e.g. ``"SEND_STARTED"`` ->
                ``"SEND_STARTED_CLASS"``); a missing entry falls back to the
                kind string itself.
            runtime_identity: Bound onto every record this adapter appends.
            on_refusal: Optional observer invoked AFTER the durable append
                returns, only for a ``kind == "SEND_REFUSED"`` record (module
                docstring's "``on_refusal`` observer"). This sink never
                itself writes to the rcl log; an exception the observer
                raises propagates unchanged.
        """
        self._store = store
        self._record_class_by_kind = dict(record_class_by_kind or {})
        self._runtime_identity = runtime_identity
        self._on_refusal = on_refusal

    def record(self, record: GatewayEvidenceRecord) -> None:
        """Durably append one gateway evidence record (design #34 §4.6 Protocol).

        Blocks until the durable commit completes: by the time this call
        returns to ``BrokerEgressGateway.__call__``, the receipt already
        existed, upholding the ``SEND_STARTED``/first-byte durability
        ordering the gateway's own Protocol return type cannot express.

        The injected ``on_refusal`` observer, if any, runs only AFTER this
        durable append has already committed, and only for a
        ``kind == "SEND_REFUSED"`` record — evidence first, verification
        second, never the other way around. Whatever the observer raises
        propagates out of this call, and transitively out of
        ``BrokerEgressGateway.__call__``, uncaught (module docstring's
        "contract change" — the refusal path could not raise for this
        reason before ``on_refusal`` was wired).
        """
        self._store.append(
            record.model_dump(mode="json"),
            kind=record.kind,
            record_class=_resolve_record_class(record.kind, self._record_class_by_kind),
            runtime_identity=self._runtime_identity,
        )
        if self._on_refusal is not None and record.kind == "SEND_REFUSED":
            self._on_refusal(record)
