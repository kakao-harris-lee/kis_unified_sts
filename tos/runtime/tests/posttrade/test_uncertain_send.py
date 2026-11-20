"""Incident 2026-11-20 (d)/(e): an order POST whose answer named no order, judged by the broker."""

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
    UNPROVABLE_TIME,
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
_TOLERANCE_S = 5
_FOREIGN_MIN_AGE_S = 120

_SIDE_CODES = {"BUY": "02", "SELL": "01"}
_BUY = _SIDE_CODES["BUY"]

_SEND_STARTED = "112015"
_LATER = "112017"
_SKEWED = "112009"
_EARLIER = "093012"


def _row(
    *,
    odno: str,
    ord_dt: str = _DATE,
    ordered: Decimal = _QTY,
    pdno: str = _INSTRUMENT,
    side: str | None = _BUY,
    ord_tmd: str | None = _LATER,
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
        ord_tmd=ord_tmd,
        sll_buy_dvsn_cd=side,
    )


def _store(
    tmp_path: Path,
    *,
    result_kind: str = "TIMEOUT",
    trading_date: str | None = _DATE,
    send_started_time: str | None = _SEND_STARTED,
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
            "send_started_time": send_started_time,
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


def _reconciler(
    store: SqliteEvidenceStore,
    *,
    tolerance_s: int = _TOLERANCE_S,
    foreign_min_age_s: int = _FOREIGN_MIN_AGE_S,
) -> UncertainSendReconciler:
    def _record(kind: str, fields: dict[str, Any]) -> None:
        store.append(fields, kind=kind, record_class=kind)

    return UncertainSendReconciler(
        evidence_store=store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        settle_ms=_SETTLE_MS,
        ord_tmd_tolerance_s=tolerance_s,
        foreign_min_age_s=foreign_min_age_s,
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

    assert (
        reconciler.apply_read(
            send, (), read_started_ms=_T0 + _SETTLE_MS - 1, claimed=frozenset()
        )
        is None
    )
    assert (
        reconciler.apply_read(
            send, (), read_started_ms=_T0 + _SETTLE_MS, claimed=frozenset()
        )
        is None
    )
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


def test_an_earlier_order_of_the_same_shape_is_not_this_sends_order(
    store: SqliteEvidenceStore,
) -> None:
    """Issue #1127: one order placed BEFORE our POST, on our symbol, quantity and side."""
    reconciler = _reconciler(store)
    send = reconciler.due(_T0)
    assert send is not None and send.send_started_time == _SEND_STARTED
    rows = (_row(odno="0000001901", ord_tmd=_EARLIER),)

    for index in range(1, 3):
        assert reconciler.apply_read(
            send, rows, read_started_ms=_T0 + index * _SETTLE_MS, claimed=frozenset()
        ) in (None, NEVER_ACCEPTED)

    assert bound_sends(store) == {}, "an earlier order was adopted as ours"
    assert never_accepted_attempt_ids(store) == frozenset({_ATTEMPT})
    (verdict,) = [row for row in _verdicts(store) if row["outcome"] == NEVER_ACCEPTED]
    assert verdict["discarded_order_ids"] == ["0000001901"], verdict
    assert verdict["discarded_order_times"] == [_EARLIER], verdict
    assert verdict["foreign_min_age_s"] == _FOREIGN_MIN_AGE_S


def test_a_row_just_outside_the_tolerance_holds_and_is_never_released_over(
    store: SqliteEvidenceStore,
) -> None:
    """Review r1 HIGH: the skew case. Our OWN accepted order, stamped before our send start."""
    reconciler = _reconciler(store)
    send = reconciler.due(_T0)
    assert send is not None
    rows = (_row(odno="0000005101", ord_tmd=_SKEWED),)

    for index in range(1, 5):
        assert (
            reconciler.apply_read(
                send,
                rows,
                read_started_ms=_T0 + index * _SETTLE_MS,
                claimed=frozenset(),
            )
            is None
        )

    assert bound_sends(store) == {}
    assert (
        never_accepted_attempt_ids(store) == frozenset()
    ), "released over our own order"
    verdicts = _verdicts(store)
    assert [row["outcome"] for row in verdicts] == [UNPROVABLE_TIME]
    assert verdicts[0]["candidate_order_times"] == [_SKEWED], verdicts[0]
    assert verdicts[0]["discarded_order_ids"] == [], verdicts[0]


@pytest.mark.parametrize(
    ("age_s", "expected"),
    [
        (_FOREIGN_MIN_AGE_S + 1, NEVER_ACCEPTED),
        (_FOREIGN_MIN_AGE_S, None),
        (_TOLERANCE_S + 1, None),
    ],
)
def test_where_the_foreign_edge_sits(
    store: SqliteEvidenceStore, age_s: int, expected: str | None
) -> None:
    """Only STRICTLY older than ``foreign_min_age_s`` is somebody else's; the edge itself holds."""
    seconds = int(_SEND_STARTED[0:2]) * 3600 + int(_SEND_STARTED[2:4]) * 60
    seconds += int(_SEND_STARTED[4:6]) - age_s
    stamped = f"{seconds // 3600:02d}{seconds // 60 % 60:02d}{seconds % 60:02d}"
    reconciler = _reconciler(store)
    send = reconciler.due(_T0)
    assert send is not None

    outcomes = [
        reconciler.apply_read(
            send,
            (_row(odno="0000001901", ord_tmd=stamped),),
            read_started_ms=_T0 + index * _SETTLE_MS,
            claimed=frozenset(),
        )
        for index in range(1, 3)
    ]

    assert outcomes[-1] == expected, (stamped, outcomes)
    assert bound_sends(store) == {}
    assert (never_accepted_attempt_ids(store) == frozenset({_ATTEMPT})) is (
        expected == NEVER_ACCEPTED
    )


def test_a_tolerance_wide_enough_to_swallow_the_gap_admits_that_same_row(
    store: SqliteEvidenceStore,
) -> None:
    """The configured number, not the row, is what refuses it — and what the bug was."""
    gap_s = (int(_SEND_STARTED[0:2]) - int(_EARLIER[0:2])) * 3600 + 3600
    reconciler = _reconciler(
        store, tolerance_s=gap_s, foreign_min_age_s=gap_s + _FOREIGN_MIN_AGE_S
    )
    send = reconciler.due(_T0)
    assert send is not None

    outcome = reconciler.apply_read(
        send,
        (_row(odno="0000001901", ord_tmd=_EARLIER),),
        read_started_ms=_T0,
        claimed=frozenset(),
    )

    assert outcome == BOUND
    assert bound_sends(store) == {_ATTEMPT: ("0000001901", _DATE)}


def test_an_earlier_and_a_later_row_bind_the_later_one(
    store: SqliteEvidenceStore,
) -> None:
    """Two rows of the same shape, one before our send start and one after: only one is ours."""
    reconciler = _reconciler(store)
    send = reconciler.due(_T0)
    assert send is not None

    outcome = reconciler.apply_read(
        send,
        (
            _row(odno="0000001901", ord_tmd=_EARLIER),
            _row(odno="0000005101", ord_tmd=_LATER),
        ),
        read_started_ms=_T0,
        claimed=frozenset(),
    )

    assert outcome == BOUND
    assert bound_sends(store) == {_ATTEMPT: ("0000005101", _DATE)}


def test_a_row_stamped_inside_the_tolerance_is_still_ours(
    store: SqliteEvidenceStore,
) -> None:
    """The threshold is send start MINUS the configured slack, and it is inclusive."""
    reconciler = _reconciler(store)
    send = reconciler.due(_T0)
    assert send is not None
    at_threshold = f"{int(_SEND_STARTED) - _TOLERANCE_S:06d}"

    outcome = reconciler.apply_read(
        send,
        (_row(odno="0000005101", ord_tmd=at_threshold),),
        read_started_ms=_T0,
        claimed=frozenset(),
    )

    assert outcome == BOUND
    assert bound_sends(store) == {_ATTEMPT: ("0000005101", _DATE)}


def test_a_send_with_no_start_time_binds_nothing_and_releases_nothing(
    tmp_path: Path,
) -> None:
    """No recorded send start -> fail closed: the one matching row is unprovable, so we hold."""
    instance = _store(tmp_path, send_started_time=None)
    try:
        reconciler = _reconciler(instance)
        send = reconciler.due(_T0)
        assert send is not None and send.send_started_time is None

        for index in range(1, 4):
            assert (
                reconciler.apply_read(
                    send,
                    (_row(odno="0000005101"),),
                    read_started_ms=_T0 + index * _SETTLE_MS,
                    claimed=frozenset(),
                )
                is None
            )

        assert bound_sends(instance) == {}
        assert never_accepted_attempt_ids(instance) == frozenset()
        assert [row["outcome"] for row in _verdicts(instance)] == [UNPROVABLE_TIME]
        assert _verdicts(instance)[0]["send_started_time"] is None
        assert (
            uncertain_sends(instance, account=_ACCOUNT, instrument=_INSTRUMENT) != ()
        ), "an unprovable verdict must leave the send a target"
    finally:
        instance.close()


def test_a_row_with_no_broker_order_time_holds_instead_of_releasing(
    store: SqliteEvidenceStore,
) -> None:
    """A candidate row the broker printed no 주문시각 on cannot be placed either way."""
    reconciler = _reconciler(store)
    send = reconciler.due(_T0)
    assert send is not None
    rows = (_row(odno="0000005101", ord_tmd=None),)

    for index in range(1, 4):
        assert (
            reconciler.apply_read(
                send,
                rows,
                read_started_ms=_T0 + index * _SETTLE_MS,
                claimed=frozenset(),
            )
            is None
        )

    assert bound_sends(store) == {}
    assert never_accepted_attempt_ids(store) == frozenset()
    verdicts = _verdicts(store)
    assert [row["outcome"] for row in verdicts] == [UNPROVABLE_TIME]
    assert verdicts[0]["candidate_order_times"] == [None], verdicts[0]


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
    assert config.uncertain_send_ord_tmd_tolerance_s is None
    assert config.uncertain_send_foreign_min_age_s is None
    assert config.uncertain_send_side_codes == {}


def test_the_gate_needs_both_companions_and_a_bool(tmp_path: Path) -> None:
    """A gate whose window, time thresholds or side table is missing would run with that check"""
    on = load_fill_observer_config(
        _observer_yaml(
            tmp_path,
            uncertain_send_reconcile=True,
            uncertain_send_settle_ms=30_000,
            uncertain_send_ord_tmd_tolerance_s=_TOLERANCE_S,
            uncertain_send_foreign_min_age_s=_FOREIGN_MIN_AGE_S,
            uncertain_send_side_codes=_SIDE_CODES,
        )
    )
    assert on.uncertain_send_reconcile is True
    assert on.uncertain_send_settle_ms == 30_000
    assert on.uncertain_send_ord_tmd_tolerance_s == _TOLERANCE_S
    assert on.uncertain_send_foreign_min_age_s == _FOREIGN_MIN_AGE_S
    assert on.uncertain_send_side_codes == _SIDE_CODES

    with pytest.raises(FillObserverConfigError, match="uncertain_send_settle_ms"):
        load_fill_observer_config(
            _observer_yaml(
                tmp_path,
                uncertain_send_reconcile=True,
                uncertain_send_ord_tmd_tolerance_s=_TOLERANCE_S,
                uncertain_send_foreign_min_age_s=_FOREIGN_MIN_AGE_S,
                uncertain_send_side_codes=_SIDE_CODES,
            )
        )
    with pytest.raises(
        FillObserverConfigError, match="uncertain_send_ord_tmd_tolerance_s"
    ):
        load_fill_observer_config(
            _observer_yaml(
                tmp_path,
                uncertain_send_reconcile=True,
                uncertain_send_settle_ms=30_000,
                uncertain_send_foreign_min_age_s=_FOREIGN_MIN_AGE_S,
                uncertain_send_side_codes=_SIDE_CODES,
            )
        )
    with pytest.raises(
        FillObserverConfigError, match="uncertain_send_foreign_min_age_s"
    ):
        load_fill_observer_config(
            _observer_yaml(
                tmp_path,
                uncertain_send_reconcile=True,
                uncertain_send_settle_ms=30_000,
                uncertain_send_ord_tmd_tolerance_s=_TOLERANCE_S,
                uncertain_send_side_codes=_SIDE_CODES,
            )
        )
    with pytest.raises(FillObserverConfigError, match="uncertain_send_side_codes"):
        load_fill_observer_config(
            _observer_yaml(
                tmp_path,
                uncertain_send_reconcile=True,
                uncertain_send_settle_ms=30_000,
                uncertain_send_ord_tmd_tolerance_s=_TOLERANCE_S,
                uncertain_send_foreign_min_age_s=_FOREIGN_MIN_AGE_S,
            )
        )
    with pytest.raises(FillObserverConfigError, match="true or false"):
        load_fill_observer_config(
            _observer_yaml(tmp_path, uncertain_send_reconcile="yes")
        )


@pytest.mark.parametrize("foreign_min_age_s", [_TOLERANCE_S, _TOLERANCE_S - 1])
def test_a_foreign_edge_at_or_inside_the_tolerance_is_refused(
    tmp_path: Path, foreign_min_age_s: int
) -> None:
    """The unprovable band must exist, so the loader refuses a pair that collapses it."""
    with pytest.raises(
        FillObserverConfigError, match="uncertain_send_foreign_min_age_s"
    ):
        load_fill_observer_config(
            _observer_yaml(
                tmp_path,
                uncertain_send_reconcile=True,
                uncertain_send_settle_ms=30_000,
                uncertain_send_ord_tmd_tolerance_s=_TOLERANCE_S,
                uncertain_send_foreign_min_age_s=foreign_min_age_s,
                uncertain_send_side_codes=_SIDE_CODES,
            )
        )


@pytest.mark.parametrize(
    "codes", [{}, {"BUY": 2}, {"": "02"}, {"BUY": ""}, "02", ["02"]]
)
def test_a_malformed_side_table_is_refused(tmp_path: Path, codes: object) -> None:
    with pytest.raises(FillObserverConfigError, match="uncertain_send_side_codes"):
        load_fill_observer_config(
            _observer_yaml(tmp_path, uncertain_send_side_codes=codes)
        )
