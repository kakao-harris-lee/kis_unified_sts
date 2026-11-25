"""Hermetic fixtures for ``tos_runtime.riskstate`` tests (``tmp_path`` only, no external"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, CanonicalizationScheme, get_scheme
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog

SCHEME: CanonicalizationScheme = get_scheme(EV_L1_PROVISIONAL_VERSION)


class FixedKeyProvider:
    """A :class:`~tos_runtime.evidence.store.KeyProvider` test double — fixed bytes (mirrors"""

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
    """Append one ``SEND_SEALED`` row with the SAME field names"""
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
    egress_result_kind: str | None = None,
    remaining_quantity: str | None = None,
    broker_execution_id: str | None = None,
) -> None:
    """Append one ``EGRESS_RESULT_CONSUMED``/``RESULT_UNMATCHED`` row with the SAME field"""
    if egress_result_kind is None:
        egress_result_kind = "FULL_FILL" if filled_quantity is not None else "ACK"
    payload = {
        "attempt_id": attempt_id,
        "instrument_key": {"account": account, "instrument": instrument},
        "egress_result_kind": egress_result_kind,
        "filled_quantity": filled_quantity,
        "remaining_quantity": remaining_quantity,
        "result_disposition": result_disposition,
        "broker_execution_id": broker_execution_id,
    }
    store.append(payload, kind=kind, record_class=kind)


def seed_recovery_marker(
    store: SqliteEvidenceStore,
    *,
    kind: str,
    event_id: str,
    handling_started_evidence_seq: int | None = None,
) -> None:
    """Append one restart-recovery marker row with the SAME field shape"""
    payload: dict[str, object] = {"event_id": event_id}
    if handling_started_evidence_seq is not None:
        payload["handling_started_evidence_seq"] = handling_started_evidence_seq
    store.append(payload, kind=kind, record_class=kind)
