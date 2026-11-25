"""Kernel evidence-sink adapters over the durable store (design #40 D3, §2 item 6)."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from tos.egressgw.records import GatewayEvidenceRecord
from tos.engine.records import EngineEvidenceRecord
from tos.workload import RuntimeIdentity

from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["EngineEvidenceSinkAdapter", "GatewayEvidenceSinkAdapter"]


def _resolve_record_class(kind: str, record_class_by_kind: Mapping[str, str]) -> str:
    """Resolve ``kind`` to a record_class label via the injected mapping."""
    return record_class_by_kind.get(kind, kind)


class EngineEvidenceSinkAdapter:
    """Durable :class:`tos.engine.sink.EvidenceSink` over a"""

    def __init__(
        self,
        store: SqliteEvidenceStore,
        *,
        record_class_by_kind: Mapping[str, str] | None = None,
        runtime_identity: RuntimeIdentity | None = None,
    ) -> None:
        """Bind this adapter to a store."""
        self._store = store
        self._record_class_by_kind = dict(record_class_by_kind or {})
        self._runtime_identity = runtime_identity

    def record(self, record: EngineEvidenceRecord) -> None:
        """Durably append one engine evidence record (design #31 §12-5 Protocol)."""
        kind = record.kind.value
        self._store.append(
            record.model_dump(mode="json"),
            kind=kind,
            record_class=_resolve_record_class(kind, self._record_class_by_kind),
            runtime_identity=self._runtime_identity,
        )


class GatewayEvidenceSinkAdapter:
    """Durable :class:`tos.egressgw.gateway.GatewayEvidenceSink` over a"""

    def __init__(
        self,
        store: SqliteEvidenceStore,
        *,
        record_class_by_kind: Mapping[str, str] | None = None,
        runtime_identity: RuntimeIdentity | None = None,
        on_refusal: Callable[[GatewayEvidenceRecord], None] | None = None,
        on_record: Callable[[GatewayEvidenceRecord], None] | None = None,
    ) -> None:
        """Bind this adapter to a store."""
        self._store = store
        self._record_class_by_kind = dict(record_class_by_kind or {})
        self._runtime_identity = runtime_identity
        self._on_refusal = on_refusal
        self._on_record = on_record

    def record(self, record: GatewayEvidenceRecord) -> None:
        """Durably append one gateway evidence record (design #34 §4.6 Protocol)."""
        self._store.append(
            record.model_dump(mode="json"),
            kind=record.kind,
            record_class=_resolve_record_class(record.kind, self._record_class_by_kind),
            runtime_identity=self._runtime_identity,
        )
        if self._on_record is not None:
            self._on_record(record)
        if self._on_refusal is not None and record.kind == "SEND_REFUSED":
            self._on_refusal(record)
