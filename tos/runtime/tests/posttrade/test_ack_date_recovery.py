"""Issue #1096: a dateless ACK's trading date is recovered from the broker, or stays refused.

The incident (2026-11-13, stock MOCK R4): order ``0000007012`` filled in full at the broker, but
its ``EGRESS_RESULT_CONSUMED`` ACK row carried no ``trading_date`` key, so every boot dropped the
attempt from the tracked set (``FILL_OBSERVER_ACK_UNTRACKABLE no_trading_date``), its entry
reservation stayed ``COMMITTED_UNBOUND`` and the ARE limit of 1 stayed saturated. These tests fix
the shape: the broker's 주식일별주문체결조회 over a bounded window of trading dates carries that
ODNO on exactly one date, so the date is recovered and the fill is observed; zero matches, more
than one, a date another attempt's dated receipt already owns, a quantity that is not the seal's,
or any failed read inside the window all keep the old refusal.

The window is read ONE date per pass (review-1105 M1/M2), so a scan of N dates takes N polls.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from tos.engine.vocabulary import EgressResultKind, ResultDisposition
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.fill_ack_date_recovery import (
    AMBIGUOUS,
    FILL_OBSERVER_ACK_DATE_RECOVERY_KIND,
    NO_MATCH,
    RECOVERED,
)
from tos_runtime.posttrade.fill_observer import (
    FILL_OBSERVED_KIND,
    FILL_OBSERVER_ACK_UNTRACKABLE_KIND,
    FILL_OBSERVER_UNATTRIBUTED_KIND,
    FillObserverConfig,
    KisMockFillObserver,
)
from tos_runtime.recon.ports import WitnessScope, WitnessUnavailable
from tos_runtime.recon.witness_kis import KisOrderRow
from tos_runtime.time.sources import ProcessMonotonicSource

from ..evidence.conftest import FixedKeyProvider

_ACCOUNT = "5020591501"
_INSTRUMENT = "005930"
_ODNO = "0000007012"
_ATTEMPT = "attempt-afg-permit-c5a4"
_QTY = Decimal(1)

_TODAY = "20261116"
_ACK_DATE = "20261113"
#: The tenant calendar's five most recent trading dates ending at ``_TODAY`` (11-14 Sat, 11-15 Sun).
_WINDOW = ("20261110", "20261111", "20261112", _ACK_DATE, _TODAY)

_LOOKBACK = 5


def _row(
    *,
    odno: str = _ODNO,
    ord_dt: str,
    ordered: str = "1",
    filled: str = "1",
    remaining: str = "0",
    pdno: str = _INSTRUMENT,
) -> KisOrderRow:
    return KisOrderRow(
        odno=odno,
        orgn_odno=None,
        ord_dt=ord_dt,
        pdno=pdno,
        ord_qty=Decimal(ordered),
        tot_ccld_qty=Decimal(filled),
        rmn_qty=Decimal(remaining),
        rjct_qty=Decimal("0"),
        cancelled=False,
    )


class _Broker:
    """A 주식일별주문체결조회 double: one date's rows per call, and every call is recorded."""

    def __init__(
        self,
        rows_by_date: dict[str, tuple[KisOrderRow, ...]],
        *,
        unavailable: frozenset[str] = frozenset(),
    ) -> None:
        self._rows_by_date = rows_by_date
        self._unavailable = unavailable
        self.read_dates: list[str] = []

    def order_rows(
        self,
        scope: WitnessScope,
        *,
        inquiry_date: str | None = None,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> tuple[str, tuple[KisOrderRow, ...]]:
        del scope, deadline_expired
        assert inquiry_date is not None
        self.read_dates.append(inquiry_date)
        if inquiry_date in self._unavailable:
            raise WitnessUnavailable(f"fixture: {inquiry_date} cannot be read")
        return inquiry_date, self._rows_by_date.get(inquiry_date, ())


def _ack(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "attempt_id": _ATTEMPT,
        "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
        "egress_result_kind": "ACK",
        "broker_execution_id": _ODNO,
    }
    row.update(overrides)
    return row


def _undated_store(
    tmp_path: Path, *, extra: list[dict[str, Any]] | None = None
) -> SqliteEvidenceStore:
    """The incident's durable picture: an ACK with an ODNO and NO ``trading_date`` key."""
    store = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    store.append(
        _ack(), kind="EGRESS_RESULT_CONSUMED", record_class="EGRESS_RESULT_CONSUMED"
    )
    for row in extra or ():
        store.append(
            row, kind="EGRESS_RESULT_CONSUMED", record_class="EGRESS_RESULT_CONSUMED"
        )
    store.append(
        {"send_seal": {"attempt_id": _ATTEMPT, "outbound_quantity": str(_QTY)}},
        kind="SEND_SEALED",
        record_class="SEND_SEALED",
    )
    return store


def _observer(
    store: SqliteEvidenceStore,
    broker: _Broker,
    *,
    recovery: bool = True,
    released: frozenset[str] = frozenset(),
) -> KisMockFillObserver:
    return KisMockFillObserver(
        config=FillObserverConfig(
            witness_fields={},
            poll_interval_ms=1,
            overdue_after_ms=600_000,
            finality_retry_interval_ms=60_000,
            prior_day_poll_interval_ms=600_000,
            poll_deadline_ms=10_000,
            witness_request_timeout_s=2.0,
            release_snapshot_max_age_ms=60_000,
            ack_date_recovery_lookback_trading_days=_LOOKBACK if recovery else None,
        ),
        orders=broker,
        evidence_store=store,
        result_sink=lambda _payload: ResultDisposition.APPLIED,
        reproject=lambda _payload: True,
        release_committed=lambda attempt_id: attempt_id in released,
        engine_holds=lambda _a: True,
        today=lambda: _TODAY,
        monotonic=ProcessMonotonicSource(),
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        trading_dates_back=(lambda count: _WINDOW[-count:]) if recovery else None,
    )


def _scan(observer: KisMockFillObserver, *, polls: int = len(_WINDOW)) -> None:
    """Drive a whole window: one date is read per pass (review-1105 M1/M2)."""
    for _ in range(polls):
        assert observer.poll_once().polled is False


def _rows(store: SqliteEvidenceStore, kind: str) -> list[dict[str, Any]]:
    return [
        json.loads(payload_json).get("payload", {})
        for (payload_json,) in store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq",
            (kind,),
        )
    ]


@pytest.fixture
def undated(tmp_path: Path) -> Iterator[SqliteEvidenceStore]:
    store = _undated_store(tmp_path)
    yield store
    store.close()


def test_one_matching_date_recovers_the_ack_and_the_fill_is_then_observed(
    undated: SqliteEvidenceStore,
) -> None:
    """The incident shape end to end: scan, recover 11-13, track, observe the FULL_FILL."""
    broker = _Broker({_ACK_DATE: (_row(ord_dt=_ACK_DATE),)})
    observer = _observer(undated, broker)

    _scan(observer)
    assert broker.read_dates == list(_WINDOW)
    (verdict,) = _rows(undated, FILL_OBSERVER_ACK_DATE_RECOVERY_KIND)
    assert verdict["outcome"] == RECOVERED
    assert verdict["trading_date"] == _ACK_DATE
    assert verdict["attempt_id"] == _ATTEMPT
    assert verdict["broker_execution_id"] == _ODNO
    assert verdict["scanned_dates"] == list(_WINDOW)
    # The scan's own rows are never mistaken for orphan orders.
    assert _rows(undated, FILL_OBSERVER_UNATTRIBUTED_KIND) == []

    report = observer.poll_once()
    assert report.polled is True
    assert report.emitted == (
        (_ATTEMPT, EgressResultKind.FULL_FILL, ResultDisposition.APPLIED),
    )
    (observed,) = _rows(undated, FILL_OBSERVED_KIND)
    assert observed["trading_date"] == _ACK_DATE
    assert observed["broker_execution_id"] == _ODNO
    assert observed["filled_quantity"] == "1"
    assert observed["remaining_quantity"] == "0"


def test_one_date_is_read_per_pass_and_no_verdict_lands_before_the_window_closes(
    undated: SqliteEvidenceStore,
) -> None:
    """review-1105 M1/M2: a scan never occupies a FETCH with the whole window at once."""
    broker = _Broker({_ACK_DATE: (_row(ord_dt=_ACK_DATE),)})
    observer = _observer(undated, broker)
    for index in range(len(_WINDOW)):
        assert observer.poll_once().polled is False
        assert broker.read_dates == list(_WINDOW[: index + 1])
        expected = 1 if index == len(_WINDOW) - 1 else 0
        assert len(_rows(undated, FILL_OBSERVER_ACK_DATE_RECOVERY_KIND)) == expected


def test_a_pass_with_fill_work_to_do_does_not_also_scan(tmp_path: Path) -> None:
    """review-1105 M1: a scan read in a FETCH that also reads fills would age the release

    snapshot that FETCH prefetches (6 s bound) and hold a perfectly good fill's release. The scan
    is planned only into an otherwise-idle FETCH, so the two never share a pass.
    """
    store = _undated_store(
        tmp_path, extra=[_ack(attempt_id="attempt-live", trading_date=_TODAY)]
    )
    store.append(
        {"send_seal": {"attempt_id": "attempt-live", "outbound_quantity": "1"}},
        kind="SEND_SEALED",
        record_class="SEND_SEALED",
    )
    try:
        broker = _Broker({_ACK_DATE: (_row(ord_dt=_ACK_DATE),)})
        observer = _observer(store, broker)
        assert observer.poll_once().polled is True
        assert broker.read_dates == [_TODAY]
        assert _rows(store, FILL_OBSERVER_ACK_DATE_RECOVERY_KIND) == []
    finally:
        store.close()


def test_a_pass_whose_holdings_refresh_is_due_does_not_also_scan(
    undated: SqliteEvidenceStore,
) -> None:
    """review-1105 M2: the holdings proof's validity (20 s) leaves no room for a scan to defer

    its refresh, so a due refresh wins the pass outright and the scan waits for an idle one.
    """
    broker = _Broker({_ACK_DATE: (_row(ord_dt=_ACK_DATE),)})
    observer = _observer(undated, broker)
    observer.config = replace(
        observer.config,
        held_position_poll_interval_ms=1,
        held_position_max_age_ms=2,
    )
    observer.publish_held_position_snapshot = lambda _snapshot: None
    observer.mark_held_position_pending = lambda _scope: 1
    observer.held_position_tip = lambda: (0, 0)
    observer.held_position_eligible = lambda: True

    assert observer.poll_once().polled is False
    assert broker.read_dates == []
    assert _rows(undated, FILL_OBSERVER_ACK_DATE_RECOVERY_KIND) == []

    # Once the refresh is no longer due, the very next pass starts the scan.
    observer.held_position_eligible = lambda: False
    assert observer.poll_once().polled is False
    assert broker.read_dates == [_WINDOW[0]]


def test_a_recovered_date_survives_the_next_boot(
    undated: SqliteEvidenceStore,
) -> None:
    """The recovery is durable evidence, so a fresh observer tracks the attempt without rescanning."""
    _scan(_observer(undated, _Broker({_ACK_DATE: (_row(ord_dt=_ACK_DATE),)})))

    second = _Broker({_ACK_DATE: (_row(ord_dt=_ACK_DATE),)})
    report = _observer(undated, second).poll_once()
    assert report.polled is True
    assert second.read_dates == [_ACK_DATE]
    assert report.emitted[0][1] is EgressResultKind.FULL_FILL
    assert len(_rows(undated, FILL_OBSERVER_ACK_DATE_RECOVERY_KIND)) == 1


def test_no_matching_date_keeps_the_attempt_refused(
    undated: SqliteEvidenceStore,
) -> None:
    """Nothing in the window carries the ODNO: the ACK stays untracked, no result is guessed."""
    observer = _observer(
        undated, _Broker({_ACK_DATE: (_row(odno="0000009999", ord_dt=_ACK_DATE),)})
    )

    _scan(observer)
    (verdict,) = _rows(undated, FILL_OBSERVER_ACK_DATE_RECOVERY_KIND)
    assert verdict["outcome"] == NO_MATCH
    assert verdict["trading_date"] is None
    assert verdict["matched_dates"] == []
    (untrackable,) = _rows(undated, FILL_OBSERVER_ACK_UNTRACKABLE_KIND)
    assert untrackable["reason"] == "no_trading_date"

    # A later boot rescans and reaches the same verdict — recorded once, not once per scan.
    rescan = _observer(undated, _Broker({}))
    _scan(rescan)
    assert rescan.poll_once().emitted == ()
    assert len(_rows(undated, FILL_OBSERVER_ACK_DATE_RECOVERY_KIND)) == 1
    assert _rows(undated, FILL_OBSERVED_KIND) == []


def test_the_same_odno_on_two_dates_is_ambiguous_and_stays_refused(
    undated: SqliteEvidenceStore,
) -> None:
    """Two dates could each be the ACK's: choosing one would bind a reservation to a guess."""
    observer = _observer(
        undated,
        _Broker(
            {
                "20261112": (_row(ord_dt="20261112"),),
                _ACK_DATE: (_row(ord_dt=_ACK_DATE),),
            }
        ),
    )

    _scan(observer)
    (verdict,) = _rows(undated, FILL_OBSERVER_ACK_DATE_RECOVERY_KIND)
    assert verdict["outcome"] == AMBIGUOUS
    assert verdict["trading_date"] is None
    assert verdict["matched_dates"] == ["20261112", _ACK_DATE]
    assert observer.poll_once().emitted == ()


def test_a_day_another_attempts_dated_receipt_owns_is_not_a_candidate(
    tmp_path: Path,
) -> None:
    """review-1105 M3: a KIS mock ODNO is a daily counter, so the same digits recur on other days.

    Here the true date (11-10) is the ONLY unclaimed one: 11-12 carries the same digits but a
    DATED ACK of another attempt already owns that (odno, day), so recovering onto it would have
    bound this reservation to that attempt's order and orphaned it. The claimed day is dropped,
    the remaining match is unique, and the recovery lands on the right day.
    """
    other = "attempt-other"
    store = _undated_store(
        tmp_path,
        extra=[
            _ack(attempt_id=other, trading_date="20261112"),
            _ack(
                attempt_id=other,
                trading_date="20261112",
                egress_result_kind="FULL_FILL",
                filled_quantity="1",
                remaining_quantity="0",
            ),
        ],
    )
    try:
        observer = _observer(
            store,
            _Broker(
                {
                    "20261110": (_row(ord_dt="20261110"),),
                    "20261112": (_row(ord_dt="20261112"),),
                }
            ),
            released=frozenset({other}),
        )
        _scan(observer)
        (verdict,) = _rows(store, FILL_OBSERVER_ACK_DATE_RECOVERY_KIND)
        assert verdict["outcome"] == RECOVERED
        assert verdict["trading_date"] == "20261110"
        assert verdict["matched_dates"] == ["20261110"]
    finally:
        store.close()


def test_a_row_whose_ordered_quantity_is_not_the_seal_is_not_a_match(
    undated: SqliteEvidenceStore,
) -> None:
    """review-1105 M3: the attempt's own SEND_SEALED outbound quantity must corroborate the row."""
    observer = _observer(
        undated,
        _Broker({_ACK_DATE: (_row(ord_dt=_ACK_DATE, ordered="7", filled="7"),)}),
    )
    _scan(observer)
    (verdict,) = _rows(undated, FILL_OBSERVER_ACK_DATE_RECOVERY_KIND)
    assert verdict["outcome"] == NO_MATCH


def test_a_date_that_cannot_be_read_records_no_verdict_at_all(
    undated: SqliteEvidenceStore,
) -> None:
    """A window with a hole cannot tell "on no other date" from "we did not look"."""
    broker = _Broker(
        {_ACK_DATE: (_row(ord_dt=_ACK_DATE),)}, unavailable=frozenset({"20261111"})
    )
    observer = _observer(undated, broker)
    _scan(observer)
    assert _rows(undated, FILL_OBSERVER_ACK_DATE_RECOVERY_KIND) == []
    # The abandoned window stops reading rather than limping on with a hole in it.
    assert broker.read_dates == ["20261110", "20261111"]


def test_a_row_for_another_instrument_is_not_a_match(
    undated: SqliteEvidenceStore,
) -> None:
    observer = _observer(
        undated, _Broker({_ACK_DATE: (_row(ord_dt=_ACK_DATE, pdno="000660"),)})
    )
    _scan(observer)
    (verdict,) = _rows(undated, FILL_OBSERVER_ACK_DATE_RECOVERY_KIND)
    assert verdict["outcome"] == NO_MATCH


def test_without_the_configured_window_the_broker_is_never_read(
    undated: SqliteEvidenceStore,
) -> None:
    """The pre-#1096 behaviour is the default: no config, no calendar, no scan."""
    broker = _Broker({_ACK_DATE: (_row(ord_dt=_ACK_DATE),)})
    assert _observer(undated, broker, recovery=False).poll_once().polled is False
    assert broker.read_dates == []
    assert _rows(undated, FILL_OBSERVER_ACK_DATE_RECOVERY_KIND) == []
    (untrackable,) = _rows(undated, FILL_OBSERVER_ACK_UNTRACKABLE_KIND)
    assert untrackable["reason"] == "no_trading_date"
