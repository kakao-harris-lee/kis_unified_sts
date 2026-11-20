"""Incident 2026-11-20 (d)/(e): an order POST whose answer named no order, judged by the broker.

``KisMockTransport`` returns a result with no ``broker_execution_id`` when the POST times out or
answers HTTP 500, so the engine quarantines the reservation and nothing identifies the order at
the broker. These tests pin what
:class:`~tos_runtime.posttrade.uncertain_send.UncertainSendReconciler` does with the 주식일별
주문체결조회 rows for the send's own trading date: exactly one candidate binds it, an empty
history proves a non-send only after the settle window, and anything less certain holds.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.fill_observer_config import (
    FillObserverConfigError,
    load_fill_observer_config,
)
from tos_runtime.posttrade.uncertain_send import (
    AMBIGUOUS,
    BOUND,
    NEVER_ACCEPTED,
    UNCERTAIN_SEND_RECONCILED_KIND,
    UncertainSendReconciler,
    bound_sends,
    never_accepted_attempt_ids,
    uncertain_sends,
)
from tos_runtime.recon.witness_kis import KisOrderRow

from ..evidence.conftest import FixedKeyProvider

_ACCOUNT = "5020591501"
_INSTRUMENT = "005930"
_ATTEMPT = "attempt-afg-permit-11b2"
_DATE = "20261120"
_QTY = Decimal(2)
_SETTLE_MS = 30_000
_T0 = 1_700_000_000_000

#: The tenant tree's own ``uncertain_send_side_codes``: 매수 ``02`` / 매도 ``01``.
_SIDE_CODES = {"BUY": "02", "SELL": "01"}
_BUY = _SIDE_CODES["BUY"]


def _row(
    *,
    odno: str,
    ord_dt: str = _DATE,
    ordered: Decimal = _QTY,
    pdno: str = _INSTRUMENT,
    side: str | None = _BUY,
) -> KisOrderRow:
    return KisOrderRow(
        odno=odno,
        orgn_odno=None,
        ord_dt=ord_dt,
        pdno=pdno,
        ord_qty=ordered,
        tot_ccld_qty=ordered,
        rmn_qty=Decimal(0),
        rjct_qty=Decimal(0),
        cancelled=False,
        sll_buy_dvsn_cd=side,
    )


def _store(
    tmp_path: Path,
    *,
    result_kind: str = "TIMEOUT",
    trading_date: str | None = _DATE,
    side: str = "BUY",
) -> SqliteEvidenceStore:
    """The durable picture one uncertain send leaves: a seal, a stamped send, a blind receipt."""
    store = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    store.append(
        {
            "attempt_id": _ATTEMPT,
            "send_seal": {
                "attempt_id": _ATTEMPT,
                "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
                "outbound_side": side,
                "outbound_quantity": str(_QTY),
            },
        },
        kind="SEND_SEALED",
        record_class="SEND_SEALED",
    )
    store.append(
        {
            "attempt_id": _ATTEMPT,
            "kind": result_kind,
            "trading_date": trading_date,
        },
        kind="TRANSPORT_SEND",
        record_class="TRANSPORT_SEND",
    )
    store.append(
        {
            "attempt_id": _ATTEMPT,
            "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
            "egress_result_kind": result_kind,
            "broker_execution_id": None,
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )
    return store


def _reconciler(store: SqliteEvidenceStore) -> UncertainSendReconciler:
    def _record(kind: str, fields: dict[str, Any]) -> None:
        store.append(fields, kind=kind, record_class=kind)

    return UncertainSendReconciler(
        evidence_store=store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        settle_ms=_SETTLE_MS,
        side_codes=_SIDE_CODES,
        record=_record,
    )


def _verdicts(store: SqliteEvidenceStore) -> list[dict[str, Any]]:
    rows = store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq",
        (UNCERTAIN_SEND_RECONCILED_KIND,),
    ).fetchall()
    return [json.loads(payload_json)["payload"] for (payload_json,) in rows]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqliteEvidenceStore]:
    instance = _store(tmp_path)
    yield instance
    instance.close()


def test_one_unclaimed_candidate_binds_the_send_to_that_order(
    store: SqliteEvidenceStore,
) -> None:
    reconciler = _reconciler(store)
    send = reconciler.due(_T0)
    assert send is not None and send.trading_date == _DATE
    assert send.side == "BUY" and send.quantity == _QTY

    outcome = reconciler.apply_read(
        send,
        (_row(odno="0000005101"),),
        read_started_ms=_T0,
        claimed=frozenset(),
    )

    assert outcome == BOUND
    assert bound_sends(store) == {_ATTEMPT: ("0000005101", _DATE)}
    # Bound is settled: the send is no longer a reconciliation target.
    assert uncertain_sends(store, account=_ACCOUNT, instrument=_INSTRUMENT) == ()


def test_two_candidates_stay_held_and_are_recorded_once(
    store: SqliteEvidenceStore,
) -> None:
    """>1 row this send could own is fail-closed: nothing binds, nothing releases, we retry."""
    reconciler = _reconciler(store)
    rows = (_row(odno="0000005101"), _row(odno="0000005102"))

    for pass_index in range(3):
        send = reconciler.due(_T0 + pass_index * _SETTLE_MS * 2)
        assert send is not None, "an ambiguous send stays a target"
        assert (
            reconciler.apply_read(
                send,
                rows,
                read_started_ms=_T0 + pass_index * _SETTLE_MS * 2,
                claimed=frozenset(),
            )
            is None
        )

    assert bound_sends(store) == {}
    assert never_accepted_attempt_ids(store) == frozenset()
    verdicts = _verdicts(store)
    assert [row["outcome"] for row in verdicts] == [AMBIGUOUS]
    assert verdicts[0]["candidate_order_ids"] == ["0000005101", "0000005102"]


def test_an_empty_history_releases_only_after_two_settled_reads(
    store: SqliteEvidenceStore,
) -> None:
    reconciler = _reconciler(store)
    send = reconciler.due(_T0)
    assert send is not None

    # Too soon after the first sighting: the broker may simply not show it yet.
    assert (
        reconciler.apply_read(
            send, (), read_started_ms=_T0 + _SETTLE_MS - 1, claimed=frozenset()
        )
        is None
    )
    # First qualifying empty read — one is not two.
    assert (
        reconciler.apply_read(
            send, (), read_started_ms=_T0 + _SETTLE_MS, claimed=frozenset()
        )
        is None
    )
    # A second read inside the window does not count either.
    assert (
        reconciler.apply_read(
            send, (), read_started_ms=_T0 + _SETTLE_MS + 1, claimed=frozenset()
        )
        is None
    )
    assert _verdicts(store) == []

    assert (
        reconciler.apply_read(
            send, (), read_started_ms=_T0 + 2 * _SETTLE_MS, claimed=frozenset()
        )
        == NEVER_ACCEPTED
    )
    assert never_accepted_attempt_ids(store) == frozenset({_ATTEMPT})


def test_a_candidate_seen_between_two_empty_reads_resets_the_window(
    store: SqliteEvidenceStore,
) -> None:
    """The settle window proves ABSENCE; one sighting of a candidate ends that proof."""
    reconciler = _reconciler(store)
    send = reconciler.due(_T0)
    assert send is not None
    assert (
        reconciler.apply_read(
            send, (), read_started_ms=_T0 + _SETTLE_MS, claimed=frozenset()
        )
        is None
    )
    assert (
        reconciler.apply_read(
            send,
            (_row(odno="0000005101"), _row(odno="0000005102")),
            read_started_ms=_T0 + 2 * _SETTLE_MS,
            claimed=frozenset(),
        )
        is None
    )

    assert (
        reconciler.apply_read(
            send, (), read_started_ms=_T0 + 3 * _SETTLE_MS, claimed=frozenset()
        )
        is None
    ), "the empty run restarted at the sighting"
    assert (
        reconciler.apply_read(
            send, (), read_started_ms=_T0 + 4 * _SETTLE_MS, claimed=frozenset()
        )
        == NEVER_ACCEPTED
    )


@pytest.mark.parametrize(
    ("rows", "claimed", "why"),
    [
        ((), frozenset(), "no row at all"),
        (
            (_row(odno="0000005101", ord_dt="20261119"),),
            frozenset(),
            "another trading date",
        ),
        ((_row(odno="0000005101", pdno="000660"),), frozenset(), "another instrument"),
        (
            (_row(odno="0000005101", ordered=Decimal(7)),),
            frozenset(),
            "not the sealed quantity",
        ),
        (
            (_row(odno="0000005101", side=_SIDE_CODES["SELL"]),),
            frozenset(),
            "the opposite side",
        ),
        (
            (_row(odno="0000005101"),),
            frozenset({("5101", _DATE, "attempt-someone-else")}),
            "another attempt's own order",
        ),
    ],
)
def test_a_row_this_send_cannot_own_is_not_a_candidate(
    store: SqliteEvidenceStore,
    rows: tuple[KisOrderRow, ...],
    claimed: frozenset[tuple[str, str, str]],
    why: str,
) -> None:
    """Each non-candidate reads as an EMPTY history: it settles into a release, never a bind."""
    reconciler = _reconciler(store)
    send = reconciler.due(_T0)
    assert send is not None
    for index in range(1, 3):
        reconciler.apply_read(
            send, rows, read_started_ms=_T0 + index * _SETTLE_MS, claimed=claimed
        )
    assert bound_sends(store) == {}, why
    assert never_accepted_attempt_ids(store) == frozenset({_ATTEMPT}), why


def test_a_send_with_no_stamped_trading_date_is_never_a_target(tmp_path: Path) -> None:
    """Without the date the transport stamped, there is no history to ask about: fail closed."""
    instance = _store(tmp_path, trading_date=None)
    try:
        assert uncertain_sends(instance, account=_ACCOUNT, instrument=_INSTRUMENT) == ()
        assert _reconciler(instance).due(_T0) is None
    finally:
        instance.close()


def test_a_numbered_result_is_not_an_uncertain_send(tmp_path: Path) -> None:
    """An ACK names its order; only a result that named none is this module's business."""
    instance = _store(tmp_path)
    try:
        instance.append(
            {
                "attempt_id": _ATTEMPT,
                "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
                "egress_result_kind": "ACK",
                "broker_execution_id": "0000005101",
                "trading_date": _DATE,
            },
            kind="EGRESS_RESULT_CONSUMED",
            record_class="EGRESS_RESULT_CONSUMED",
        )
        assert uncertain_sends(instance, account=_ACCOUNT, instrument=_INSTRUMENT) == ()
    finally:
        instance.close()


def test_another_scopes_uncertain_send_is_not_this_scopes_business(
    store: SqliteEvidenceStore,
) -> None:
    assert uncertain_sends(store, account=_ACCOUNT, instrument="000660") == ()
    assert uncertain_sends(store, account="9999999999", instrument=_INSTRUMENT) == ()


# --------------------------------------------------------------------- the config gate


def _observer_yaml(tmp_path: Path, **extra: object) -> Path:
    """A minimal valid ``fill_observer.yaml`` plus whatever this case sets."""
    raw: dict[str, object] = {
        "order_inquiry_tr_id": "VTTC0081R",
        "order_inquiry_path": "/o",
        "balance_tr_id": "VTTC8434R",
        "balance_path": "/b",
        "max_pages": 10,
        "poll_interval_ms": 3000,
        "witness_request_timeout_s": 2.0,
        "poll_deadline_ms": 1500,
        "overdue_after_ms": 600000,
        "finality_retry_interval_ms": 60000,
        "prior_day_poll_interval_ms": 600000,
        "release_snapshot_max_age_ms": 6000,
        **extra,
    }
    path = tmp_path / "fill_observer.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def test_the_reconciliation_is_off_when_its_keys_are_absent(tmp_path: Path) -> None:
    """The pre-11-20 behaviour is what a tree that says nothing gets."""
    config = load_fill_observer_config(_observer_yaml(tmp_path))
    assert config.uncertain_send_reconcile is False
    assert config.uncertain_send_settle_ms is None
    assert config.uncertain_send_side_codes == {}


def test_the_gate_needs_both_companions_and_a_bool(tmp_path: Path) -> None:
    """A gate whose window or side table is missing would run with that check silently off."""
    on = load_fill_observer_config(
        _observer_yaml(
            tmp_path,
            uncertain_send_reconcile=True,
            uncertain_send_settle_ms=30_000,
            uncertain_send_side_codes=_SIDE_CODES,
        )
    )
    assert on.uncertain_send_reconcile is True
    assert on.uncertain_send_settle_ms == 30_000
    assert on.uncertain_send_side_codes == _SIDE_CODES

    with pytest.raises(FillObserverConfigError, match="uncertain_send_settle_ms"):
        load_fill_observer_config(
            _observer_yaml(
                tmp_path,
                uncertain_send_reconcile=True,
                uncertain_send_side_codes=_SIDE_CODES,
            )
        )
    with pytest.raises(FillObserverConfigError, match="uncertain_send_side_codes"):
        load_fill_observer_config(
            _observer_yaml(
                tmp_path,
                uncertain_send_reconcile=True,
                uncertain_send_settle_ms=30_000,
            )
        )
    with pytest.raises(FillObserverConfigError, match="true or false"):
        load_fill_observer_config(
            _observer_yaml(tmp_path, uncertain_send_reconcile="yes")
        )


@pytest.mark.parametrize(
    "codes", [{}, {"BUY": 2}, {"": "02"}, {"BUY": ""}, "02", ["02"]]
)
def test_a_malformed_side_table_is_refused(tmp_path: Path, codes: object) -> None:
    with pytest.raises(FillObserverConfigError, match="uncertain_send_side_codes"):
        load_fill_observer_config(
            _observer_yaml(tmp_path, uncertain_send_side_codes=codes)
        )
