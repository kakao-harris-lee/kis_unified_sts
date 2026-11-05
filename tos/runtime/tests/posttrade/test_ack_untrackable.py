"""An ACK the fill observer cannot join to a broker row is refused VISIBLY.

Incident 2026-11-05 (CP-3 stock MOCK 005930, the first-ever MOCK order): the ACK carried an ODNO
but no ``trading_date``, and ``_tracked_attempts``'s ``isinstance(row["trading_date"], str)``
guard dropped it inside an ``and`` chain that short-circuited before the untrackable row was
written. Nothing was tracked, ``VTTC0081R`` was polled 0 times, no ``FILL_OBSERVED`` was emitted,
the RCL reservation stayed ``COMMITTED_UNBOUND`` — and no evidence row said any of it, for 6.5 h.

Hermetic: a ``tmp_path`` evidence file and a broker reader that fails the test if it is called.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from tos.engine.vocabulary import ResultDisposition
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.fill_observer import (
    FILL_OBSERVER_ACK_UNTRACKABLE_KIND,
    FillObserverConfig,
    KisMockFillObserver,
)
from tos_runtime.recon.ports import WitnessScope
from tos_runtime.recon.witness_kis import KisOrderRow
from tos_runtime.time.sources import ProcessMonotonicSource

from ..evidence.conftest import FixedKeyProvider

_ACCOUNT = "5000000001"
_INSTRUMENT = "005930"
_DATE = "20261105"
_ODNO = "0000012345"
_ATTEMPT = "attempt-d405"
_QTY = Decimal(1)


class _NoBroker:
    """``order_rows`` that must never be reached — nothing is trackable in these tests."""

    def order_rows(
        self,
        scope: WitnessScope,
        *,
        inquiry_date: str | None = None,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> tuple[str, tuple[KisOrderRow, ...]]:
        raise AssertionError(
            f"the broker was read for an untrackable ACK: {scope!r} {inquiry_date!r} "
            f"{deadline_expired!r}"
        )


def _store(tmp_path: Path, ack: dict[str, Any]) -> SqliteEvidenceStore:
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    instance.append(
        ack, kind="EGRESS_RESULT_CONSUMED", record_class="EGRESS_RESULT_CONSUMED"
    )
    instance.append(
        {"send_seal": {"attempt_id": _ATTEMPT, "outbound_quantity": str(_QTY)}},
        kind="SEND_SEALED",
        record_class="SEND_SEALED",
    )
    return instance


def _ack(**overrides: Any) -> dict[str, Any]:
    """The ACK row the transport records, minus whatever the test takes away."""
    row: dict[str, Any] = {
        "attempt_id": _ATTEMPT,
        "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
        "egress_result_kind": "ACK",
        "broker_execution_id": _ODNO,
        "trading_date": _DATE,
    }
    row.update(overrides)
    return {key: value for key, value in row.items() if value is not None}


def _observer(store: SqliteEvidenceStore) -> KisMockFillObserver:
    return KisMockFillObserver(
        config=FillObserverConfig(
            witness_fields={},
            poll_interval_ms=1,
            overdue_after_ms=600_000,
            finality_retry_interval_ms=60_000,
            prior_day_poll_interval_ms=60_000,
            poll_deadline_ms=10_000,
            witness_request_timeout_s=2.0,
            release_snapshot_max_age_ms=60_000,
        ),
        orders=_NoBroker(),
        evidence_store=store,
        result_sink=lambda _payload: ResultDisposition.APPLIED,
        reproject=lambda _payload: True,
        release_committed=lambda _a: False,
        engine_holds=lambda _a: True,
        today=lambda: _DATE,
        monotonic=ProcessMonotonicSource(),
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
    )


def _untrackable_rows(store: SqliteEvidenceStore) -> list[dict[str, Any]]:
    return [
        json.loads(payload_json).get("payload", {})
        for (payload_json,) in store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq",
            (FILL_OBSERVER_ACK_UNTRACKABLE_KIND,),
        )
    ]


@pytest.fixture
def undated(tmp_path: Path) -> Iterator[SqliteEvidenceStore]:
    instance = _store(tmp_path, _ack(trading_date=None))
    yield instance
    instance.close()


def test_an_undated_ack_is_refused_with_a_row_that_names_the_reason(
    undated: SqliteEvidenceStore,
) -> None:
    """The 2026-11-05 shape: an ODNO, no trading date. Nothing is tracked and nothing is read —
    an ODNO is a per-day sequence, so there is no date to walk and no date is invented — but the
    refusal is now ON the record. Mutation: drop the ``no_trading_date`` branch -> the ACK
    vanishes again, zero rows -> red."""
    observer = _observer(undated)
    assert observer.poll_once().polled is False
    (row,) = _untrackable_rows(undated)
    assert row["attempt_id"] == _ATTEMPT
    assert row["broker_execution_id"] == _ODNO
    assert row["reason"] == "no_trading_date"


def test_the_refusal_is_recorded_once_however_often_it_is_polled(
    undated: SqliteEvidenceStore,
) -> None:
    """Every pass re-derives the durable picture, so the row needs the same once-per-attempt
    dedup the all-zero-ODNO refusal has — otherwise one undated ACK fills the evidence file.
    """
    observer = _observer(undated)
    for _ in range(3):
        assert observer.poll_once().polled is False
    assert len(_untrackable_rows(undated)) == 1

    # A fresh observer over the same file re-derives everything from evidence: the durable row
    # it already finds is what stops a restart from writing a second one.
    assert _observer(undated).poll_once().polled is False
    assert len(_untrackable_rows(undated)) == 1
