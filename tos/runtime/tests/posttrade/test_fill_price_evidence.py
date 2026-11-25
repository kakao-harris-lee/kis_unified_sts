"""``FILL_OBSERVED`` carries the broker's own execution price, or says it has none."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from tos.engine.vocabulary import EgressResultKind, ResultDisposition
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.fill_observer import (
    FILL_OBSERVED_KIND,
    FillObserverConfig,
    KisMockFillObserver,
)
from tos_runtime.recon.ports import WitnessScope
from tos_runtime.recon.witness_kis import KisOrderRow
from tos_runtime.time.sources import ProcessMonotonicSource

from ..evidence.conftest import FixedKeyProvider

_ACCOUNT = "5020591501"
_INSTRUMENT = "005930"
_DATE = "20261117"
_ODNO = "0000007012"
_ATTEMPT = "attempt-price-7f21"
_QTY = Decimal(1)

_AVG_PRVS = "193300"
_TOT_CCLD_AMT = "193300"


class _Broker:
    """A 주식일별주문체결조회 double: the same rows for whatever date is asked."""

    def __init__(self, rows: tuple[KisOrderRow, ...]) -> None:
        self._rows = rows

    def order_rows(
        self,
        scope: WitnessScope,
        *,
        inquiry_date: str | None = None,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> tuple[str, tuple[KisOrderRow, ...]]:
        del scope, deadline_expired
        return inquiry_date or _DATE, self._rows


def _row(
    *,
    odno: str = _ODNO,
    avg_prvs: str | None = _AVG_PRVS,
    tot_ccld_amt: str | None = _TOT_CCLD_AMT,
    ord_qty: str = format(_QTY, "f"),
    pdno: str = _INSTRUMENT,
) -> KisOrderRow:
    """One fully filled row, parsed the one way the witness parses a wire row."""
    return KisOrderRow.from_wire(
        {
            "ord_dt": _DATE,
            "odno": odno,
            "orgn_odno": "0000000000",
            "pdno": pdno,
            "ord_qty": ord_qty,
            "tot_ccld_qty": format(_QTY, "f"),
            "rmn_qty": "0",
            "rjct_qty": "0",
            "cncl_yn": "N",
            **({} if avg_prvs is None else {"avg_prvs": avg_prvs}),
            **({} if tot_ccld_amt is None else {"tot_ccld_amt": tot_ccld_amt}),
        }
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqliteEvidenceStore]:
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    instance.append(
        {
            "attempt_id": _ATTEMPT,
            "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
            "egress_result_kind": "ACK",
            "broker_execution_id": _ODNO,
            "trading_date": _DATE,
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )
    instance.append(
        {"send_seal": {"attempt_id": _ATTEMPT, "outbound_quantity": str(_QTY)}},
        kind="SEND_SEALED",
        record_class="SEND_SEALED",
    )
    yield instance
    instance.close()


def _observer(
    store: SqliteEvidenceStore, rows: tuple[KisOrderRow, ...]
) -> KisMockFillObserver:
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
        orders=_Broker(rows),
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


def _observed(store: SqliteEvidenceStore) -> list[dict[str, Any]]:
    return [
        json.loads(payload_json)["payload"]
        for (payload_json,) in store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq",
            (FILL_OBSERVED_KIND,),
        )
    ]


def test_a_fill_records_the_brokers_own_execution_price(
    store: SqliteEvidenceStore,
) -> None:
    """The 11-17 BUY: sealed at 193,400, filled at 193,300 — the record now says which."""
    observer = _observer(store, (_row(),))

    report = observer.poll_once()

    assert [(k, d) for _a, k, d in report.emitted] == [
        (EgressResultKind.FULL_FILL, ResultDisposition.APPLIED)
    ]
    (observed,) = _observed(store)
    assert observed["avg_execution_price"] == _AVG_PRVS
    assert observed["executed_amount"] == _TOT_CCLD_AMT
    assert (observed["filled_quantity"], observed["remaining_quantity"]) == ("1", "0")
    assert (observed["kind"], observed["reason"]) == ("FULL_FILL", "filled")


def test_a_broker_row_without_a_price_records_both_keys_as_null(
    store: SqliteEvidenceStore,
) -> None:
    """Every row the observer met before KIS printed a price takes this path: the keys are"""
    observer = _observer(store, (_row(avg_prvs=None, tot_ccld_amt=None),))

    assert observer.poll_once().emitted != ()

    (observed,) = _observed(store)
    assert (observed["avg_execution_price"], observed["executed_amount"]) == (
        None,
        None,
    )
    assert observed["kind"] == "FULL_FILL"


def test_ambiguous_rows_claim_no_price(store: SqliteEvidenceStore) -> None:
    """Two rows under one ODNO decide nothing, so neither row's price is attributed either."""
    observer = _observer(store, (_row(), _row(avg_prvs="999999")))

    assert observer.poll_once().emitted != ()

    (observed,) = _observed(store)
    assert (observed["kind"], observed["reason"]) == ("UNKNOWN", "ambiguous_rows")
    assert (observed["avg_execution_price"], observed["executed_amount"]) == (
        None,
        None,
    )


@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    [
        ({"ord_qty": "2"}, "ordered_quantity_mismatch"),
        ({"pdno": "000660"}, "instrument_mismatch"),
    ],
    ids=["ordered-quantity", "instrument"],
)
def test_an_unknown_verdict_claims_no_price_even_from_a_single_row(
    store: SqliteEvidenceStore, overrides: dict[str, str], expected_reason: str
) -> None:
    """review-1121 L2: an ``UNKNOWN`` row contradicts the attempt — quoting its price as"""
    observer = _observer(store, (_row(**overrides),))

    assert observer.poll_once().emitted != ()

    (observed,) = _observed(store)
    assert (observed["kind"], observed["reason"]) == ("UNKNOWN", expected_reason)
    assert (observed["avg_execution_price"], observed["executed_amount"]) == (
        None,
        None,
    )


def test_a_stored_row_written_before_the_price_keys_still_loads(
    tmp_path: Path,
) -> None:
    """The 2026-11-13 lesson: a persisted row re-validated against a changed model broke every"""
    path = tmp_path / "evidence.sqlite3"
    keys = {1: b"test-fixed-key-bytes"}
    old = {
        "attempt_id": _ATTEMPT,
        "broker_execution_id": _ODNO,
        "trading_date": _DATE,
        "kind": "FULL_FILL",
        "filled_quantity": "1",
        "remaining_quantity": "0",
        "reason": "filled",
    }
    store = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    try:
        store.append(old, kind=FILL_OBSERVED_KIND, record_class=FILL_OBSERVED_KIND)
        digest = store.connection.execute(
            "SELECT entry_digest FROM entries ORDER BY seq DESC LIMIT 1"
        ).fetchone()[0]
    finally:
        store.close()

    reopened = SqliteEvidenceStore(path, key_provider=FixedKeyProvider())
    try:
        reopened.verify_or_raise(keys)
        (loaded,) = _observed(reopened)
        assert loaded == old
        assert "avg_execution_price" not in loaded
        assert "executed_amount" not in loaded
        assert (
            reopened.connection.execute(
                "SELECT entry_digest FROM entries ORDER BY seq DESC LIMIT 1"
            ).fetchone()[0]
            == digest
        )
    finally:
        reopened.close()
