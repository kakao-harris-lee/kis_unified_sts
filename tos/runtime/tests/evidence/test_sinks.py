"""``tos_runtime.evidence.sinks`` tests — kernel Protocol conformance + durability ordering."""

from __future__ import annotations

import pytest
from tos.egressgw.gateway import GatewayEvidenceSink
from tos.egressgw.records import GatewayEvidenceRecord
from tos.engine.records import EngineEvidenceRecord
from tos.engine.sink import EvidenceSink
from tos.engine.vocabulary import EvidenceKind
from tos_runtime.evidence.sinks import (
    EngineEvidenceSinkAdapter,
    GatewayEvidenceSinkAdapter,
)
from tos_runtime.evidence.store import SqliteEvidenceStore


def test_engine_adapter_satisfies_the_kernel_evidence_sink_protocol(
    store: SqliteEvidenceStore,
) -> None:
    adapter = EngineEvidenceSinkAdapter(store)
    assert isinstance(adapter, EvidenceSink)


def test_gateway_adapter_satisfies_the_kernel_gateway_evidence_sink_protocol(
    store: SqliteEvidenceStore,
) -> None:
    adapter = GatewayEvidenceSinkAdapter(store)
    assert isinstance(adapter, GatewayEvidenceSink)


def test_engine_adapter_durably_appends_and_resolves_record_class(
    store: SqliteEvidenceStore,
) -> None:
    adapter = EngineEvidenceSinkAdapter(
        store, record_class_by_kind={"FLOW_HALTED": "HALT_CLASS"}
    )
    adapter.record(
        EngineEvidenceRecord(kind=EvidenceKind.FLOW_HALTED, detail="halt detail")
    )
    metas = list(store.iter_entry_meta())
    assert len(metas) == 1
    assert metas[0].kind == "FLOW_HALTED"
    assert metas[0].record_class == "HALT_CLASS"


def test_engine_adapter_falls_back_to_kind_as_record_class_when_unmapped(
    store: SqliteEvidenceStore,
) -> None:
    adapter = EngineEvidenceSinkAdapter(store)
    adapter.record(EngineEvidenceRecord(kind=EvidenceKind.DECISION_WITHHELD))
    metas = list(store.iter_entry_meta())
    assert metas[0].record_class == "DECISION_WITHHELD"


def test_gateway_adapter_durably_appends_before_returning(
    store: SqliteEvidenceStore,
) -> None:
    adapter = GatewayEvidenceSinkAdapter(store)
    adapter.record(GatewayEvidenceRecord(kind="SEND_STARTED", attempt_id="attempt-1"))
    # by the time record() returned above, the receipt already existed —
    # last_committed() proves the durable commit already happened.
    last_seq, _, _ = store.last_committed()
    assert last_seq == 0


def test_gateway_adapter_appends_are_chained_and_verifiable(
    store: SqliteEvidenceStore,
) -> None:
    adapter = GatewayEvidenceSinkAdapter(store)
    adapter.record(GatewayEvidenceRecord(kind="SEND_STARTED", attempt_id="a1"))
    adapter.record(
        GatewayEvidenceRecord(kind="POTENTIALLY_LIVE_OBSERVED", attempt_id="a1")
    )
    assert store.verify({1: b"test-fixed-key-bytes"}) is True


def test_adapters_bind_runtime_identity_onto_every_record(
    store: SqliteEvidenceStore,
) -> None:
    from tos.workload import RuntimeIdentity

    identity = RuntimeIdentity(
        cell_id="cell-1", runtime_generation=0, process_nonce="nonce-1"
    )
    adapter = EngineEvidenceSinkAdapter(store, runtime_identity=identity)
    adapter.record(EngineEvidenceRecord(kind=EvidenceKind.FLOW_HALTED))
    row = store.connection.execute(
        "SELECT runtime_identity_json FROM entries WHERE seq = 0"
    ).fetchone()
    assert row[0] is not None
    assert "cell-1" in row[0]


# ---------------------------------------------------------------------------
# kernel round #1 §3 (lane B) — ``on_refusal`` observer
# ---------------------------------------------------------------------------


def test_on_refusal_is_called_for_send_refused(store: SqliteEvidenceStore) -> None:
    observed: list[GatewayEvidenceRecord] = []
    adapter = GatewayEvidenceSinkAdapter(store, on_refusal=observed.append)
    record = GatewayEvidenceRecord(kind="SEND_REFUSED", attempt_id="a1")
    adapter.record(record)
    assert observed == [record]


def test_on_refusal_is_not_called_for_other_kinds(store: SqliteEvidenceStore) -> None:
    observed: list[GatewayEvidenceRecord] = []
    adapter = GatewayEvidenceSinkAdapter(store, on_refusal=observed.append)
    adapter.record(GatewayEvidenceRecord(kind="SEND_STARTED", attempt_id="a1"))
    adapter.record(
        GatewayEvidenceRecord(kind="POTENTIALLY_LIVE_OBSERVED", attempt_id="a1")
    )
    assert observed == []


def test_on_refusal_runs_only_after_the_durable_append_commits(
    store: SqliteEvidenceStore,
) -> None:
    """The observer sees the record only AFTER ``store.append`` has already
    committed — evidence first, verification second (module docstring)."""
    seen_seq_at_call_time: list[int | None] = []

    def observer(_record: GatewayEvidenceRecord) -> None:
        last_seq, _, _ = store.last_committed()
        seen_seq_at_call_time.append(last_seq)

    adapter = GatewayEvidenceSinkAdapter(store, on_refusal=observer)
    adapter.record(GatewayEvidenceRecord(kind="SEND_REFUSED", attempt_id="a1"))
    # seq 0 is already committed by the time the observer ran.
    assert seen_seq_at_call_time == [0]


def test_on_refusal_exception_propagates(store: SqliteEvidenceStore) -> None:
    """An observer failure is never swallowed — the append itself already
    durably committed, but the caller must still see the failure."""

    def failing_observer(_record: GatewayEvidenceRecord) -> None:
        raise RuntimeError("obligation verification failed")

    adapter = GatewayEvidenceSinkAdapter(store, on_refusal=failing_observer)
    with pytest.raises(RuntimeError, match="obligation verification failed"):
        adapter.record(GatewayEvidenceRecord(kind="SEND_REFUSED", attempt_id="a1"))
    # the append itself still committed before the observer raised.
    last_seq, _, _ = store.last_committed()
    assert last_seq == 0


def test_no_on_refusal_configured_is_a_safe_default(
    store: SqliteEvidenceStore,
) -> None:
    """The default (``on_refusal=None``) sink behaves exactly as before this change."""
    adapter = GatewayEvidenceSinkAdapter(store)
    adapter.record(GatewayEvidenceRecord(kind="SEND_REFUSED", attempt_id="a1"))
    last_seq, _, _ = store.last_committed()
    assert last_seq == 0
