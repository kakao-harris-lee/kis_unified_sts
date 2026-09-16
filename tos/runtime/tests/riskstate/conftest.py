"""Hermetic fixtures for ``tos_runtime.riskstate`` tests (``tmp_path`` only, no external
network, no ambient env — same discipline as ``tos/runtime/tests/venue/conftest.py`` and
``tos/runtime/tests/rcl/conftest.py``).

Evidence-row seed helpers write through the store's own ``append`` with the SAME payload SHAPE
the runtime emits (never through the full pydantic ``GatewayEvidenceRecord``/
``EngineEvidenceRecord`` models, which require many fields this suite's reads never touch) —
cited against the emitting code at each helper's own docstring.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, CanonicalizationScheme, get_scheme
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog

SCHEME: CanonicalizationScheme = get_scheme(EV_L1_PROVISIONAL_VERSION)


class FixedKeyProvider:
    """A :class:`~tos_runtime.evidence.store.KeyProvider` test double — fixed bytes (mirrors
    ``tos/runtime/tests/venue/conftest.py``'s own re-declared double; cross-suite imports are
    forbidden per that module's convention)."""

    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes-riskstate-suite")

    def generations(self) -> tuple[int, ...]:
        return (1,)

    def key_for(self, generation: int) -> bytes:
        del generation
        return b"test-fixed-key-bytes-riskstate-suite"


@pytest.fixture
def key_provider() -> KeyProvider:
    return FixedKeyProvider()


@pytest.fixture
def evidence_store(tmp_path: Path, key_provider: KeyProvider):
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=key_provider
    )
    yield instance
    instance.close()


@pytest.fixture
def inbox(tmp_path: Path):
    instance = SqliteEventInbox(tmp_path / "inbox.sqlite3", scheme=SCHEME)
    yield instance
    instance.close()


@pytest.fixture
def rcl_log(tmp_path: Path, evidence_store: SqliteEvidenceStore):
    instance = SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=evidence_store)
    yield instance
    instance.close()


def seed_send_sealed(
    store: SqliteEvidenceStore,
    *,
    attempt_id: str,
    account: str,
    instrument: str,
    side: str,
    quantity: str,
    event_id: str,
    causal_predecessor_ids: tuple[str, ...] = (),
) -> None:
    """Append one ``SEND_SEALED`` row with the SAME field names
    ``tos.egressgw.records.GatewayEvidenceRecord.model_dump(mode="json")`` produces
    (``tos/src/tos/egressgw/records.py:606-661``) for the sub-fields this suite's readers
    touch: ``kind``, ``attempt_id``, ``send_seal.instrument_key``
    (``tos/src/tos/egressgw/seal.py:184``), ``send_seal.outbound_side``/``.outbound_quantity``
    (``seal.py:217-219``), and ``send_seal.reference`` (an ``OrderingEvent`` —
    ``tos/src/tos/ordering/_ordering.py:59-68`` — carrying ``event_id``/
    ``causal_predecessor_ids``). Mirrors
    :meth:`~tos_runtime.evidence.sinks.GatewayEvidenceSinkAdapter.record`'s own call:
    ``store.append(record.model_dump(mode="json"), kind=record.kind,
    record_class=record.kind)``. Every OTHER ``GatewayEvidenceRecord``/``SendSeal`` field this
    suite's readers never touch is omitted — the store accepts any JSON-native mapping.
    """
    payload = {
        "kind": "SEND_SEALED",
        "attempt_id": attempt_id,
        "send_seal": {
            "attempt_id": attempt_id,
            "instrument_key": {"account": account, "instrument": instrument},
            "outbound_side": side,
            "outbound_quantity": quantity,
            "reference": {
                "event_id": event_id,
                "causal_predecessor_ids": list(causal_predecessor_ids),
            },
        },
    }
    store.append(payload, kind="SEND_SEALED", record_class="SEND_SEALED")


def seed_egress_result(
    store: SqliteEvidenceStore,
    *,
    kind: str,
    attempt_id: str,
    account: str,
    instrument: str,
    filled_quantity: str | None,
    result_disposition: str | None = None,
) -> None:
    """Append one ``EGRESS_RESULT_CONSUMED``/``RESULT_UNMATCHED`` row with the SAME field
    names ``tos.engine.records.EngineEvidenceRecord.model_dump(mode="json")`` produces for the
    sub-fields :mod:`tos_runtime.recon.witness_synthetic` /
    :mod:`tos_runtime.recon.evidence_reader` (and this suite's own readers) touch:
    ``attempt_id``, ``instrument_key``, ``egress_result_kind``, ``filled_quantity``,
    ``remaining_quantity``, ``result_disposition`` — cited against
    :class:`~tos_runtime.recon.ports.EgressReceiptObservation`'s own field list AND
    ``tos/src/tos/engine/core.py:705-720`` (the exact ``RESULT_UNMATCHED`` payload shape,
    including ``result_disposition``, the kernel emits for a non-``APPLIED`` disposition).
    Mirrors :meth:`~tos_runtime.evidence.sinks.EngineEvidenceSinkAdapter.record`'s own call:
    ``store.append(record.model_dump(mode="json"), kind=record.kind.value, ...)``.

    Args:
        kind: ``"EGRESS_RESULT_CONSUMED"`` or ``"RESULT_UNMATCHED"`` (the two durable kinds
            this suite's readers distinguish).
        filled_quantity: ``None`` for a zero-fill terminal outcome (e.g. a plain ACK/CANCEL) —
            a positively recorded absence, not an unread field.
        result_disposition: One of ``tos.engine.vocabulary.ResultDisposition``'s string values
            (e.g. ``"DUPLICATE"``) — only meaningful for ``kind="RESULT_UNMATCHED"``
            (``core.py:713``); ``None`` when the caller does not need it (every pre-existing
            call site).
    """
    payload = {
        "attempt_id": attempt_id,
        "instrument_key": {"account": account, "instrument": instrument},
        "egress_result_kind": "FULL_FILL" if filled_quantity is not None else "ACK",
        "filled_quantity": filled_quantity,
        "remaining_quantity": None,
        "result_disposition": result_disposition,
    }
    store.append(payload, kind=kind, record_class=kind)


def seed_recovery_marker(
    store: SqliteEvidenceStore, *, kind: str, event_id: str
) -> None:
    """Append one restart-recovery marker row with the SAME field shape
    ``EngineDriver._handle_interrupted_event`` emits
    (``tos_runtime/engine/driver.py:517-535``: ``{"event_id": event_id, ...}``, appended via
    either ``record_halt`` — for ``HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND`` — or
    ``evidence_store.append`` directly — for ``DECISION_TICK_DROPPED_ON_RECOVERY`` — both of
    which route through the SAME ``SqliteEvidenceStore.append`` this helper calls directly).

    Args:
        kind: ``"DECISION_TICK_DROPPED_ON_RECOVERY"`` or
            ``"HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND"``.
        event_id: The interrupted row's own content-addressed ``event_id``
            (:func:`tos.engine.records.event_identity`) — the SAME id
            :class:`~tos_runtime.engine.inbox.InboxReceipt.event_id` carries for that row.
    """
    store.append({"event_id": event_id}, kind=kind, record_class=kind)
