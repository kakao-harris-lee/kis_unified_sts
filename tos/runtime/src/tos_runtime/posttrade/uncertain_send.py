"""Resolve an order POST whose answer named no order, from the broker's own daily history."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.fill_fetch import FetchResult, odno_key
from tos_runtime.recon.ports import WitnessUnavailable
from tos_runtime.recon.witness_kis import KisOrderRow

__all__ = [
    "AMBIGUOUS",
    "BOUND",
    "CONFIRMING_EMPTY_READS",
    "LATE_CANDIDATE_HALT_REASON",
    "NEVER_ACCEPTED",
    "UNCERTAIN_SEND_LATE_CANDIDATE_KIND",
    "UNCERTAIN_SEND_RECONCILED_KIND",
    "UNKNOWN_SIDE_CODE",
    "UNPROVABLE_TIME",
    "UncertainSend",
    "UncertainSendReconciler",
    "apply_uncertain_read",
    "bound_sends",
    "late_candidate_attempt_ids",
    "never_accepted_attempt_ids",
    "released_sends",
    "rows_by_send_time",
    "uncertain_sends",
]

UNCERTAIN_SEND_RECONCILED_KIND = "UNCERTAIN_SEND_RECONCILED"
UNCERTAIN_SEND_LATE_CANDIDATE_KIND = "UNCERTAIN_SEND_LATE_CANDIDATE"
LATE_CANDIDATE_HALT_REASON = "NEW_RISK_HALTED_BY_LATE_UNCERTAIN_SEND_CANDIDATE"

BOUND = "bound"
NEVER_ACCEPTED = "never_accepted"
AMBIGUOUS = "ambiguous"
UNPROVABLE_TIME = "unprovable_time"
UNKNOWN_SIDE_CODE = "unknown_side_code"

CONFIRMING_EMPTY_READS = 2

_UNCERTAIN_RESULT_KINDS = frozenset({"TIMEOUT", "UNKNOWN"})

_CONSUMED_KIND = "EGRESS_RESULT_CONSUMED"
_SEND_SEALED_KIND = "SEND_SEALED"
_TRANSPORT_SEND_KIND = "TRANSPORT_SEND"

_SEND_STARTED_FIELD = "send_started_time"

_DAY_START = "000000"

ClaimedOrderDays = frozenset[tuple[str, str, str]]

SideCodes = Mapping[str, str]

Recorder = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True)
class UncertainSend:
    """One send whose answer named no order, and what it sealed."""

    attempt_id: str
    trading_date: str
    side: str | None
    quantity: Decimal | None
    send_started_time: str | None
    released: bool = False


def _hhmmss(value: object) -> str | None:
    """One 주문시각-shaped stamp, through the broker-row parser #1126 already uses for it."""
    return KisOrderRow.from_wire({"ord_tmd": value}).ord_tmd


def _shifted_back(stamp: str, seconds: int) -> str:
    """``stamp`` (``HHMMSS``, already validated) ``seconds`` earlier, clamped to the day start."""
    shifted = int(stamp[0:2]) * 3600 + int(stamp[2:4]) * 60 + int(stamp[4:6]) - seconds
    if shifted <= 0:
        return _DAY_START
    return f"{shifted // 3600:02d}{shifted // 60 % 60:02d}{shifted % 60:02d}"


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _payloads(store: SqliteEvidenceStore, kind: str) -> list[dict[str, Any]]:
    rows = store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
    ).fetchall()
    payloads: list[dict[str, Any]] = []
    for (payload_json,) in rows:
        payload = json.loads(payload_json).get("payload", {})
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _sealed(
    store: SqliteEvidenceStore, *, account: str, instrument: str
) -> dict[str, tuple[str | None, Decimal | None]]:
    """``attempt_id -> (outbound_side, outbound_quantity)`` for this scope's sealed sends."""
    sealed: dict[str, tuple[str | None, Decimal | None]] = {}
    for payload in _payloads(store, _SEND_SEALED_KIND):
        attempt_id = payload.get("attempt_id")
        seal = payload.get("send_seal")
        if not isinstance(attempt_id, str) or not isinstance(seal, dict):
            continue
        key = seal.get("instrument_key")
        if not isinstance(key, dict) or (
            key.get("account") != account or key.get("instrument") != instrument
        ):
            continue
        side = seal.get("outbound_side")
        sealed[attempt_id] = (
            side if isinstance(side, str) else None,
            _decimal(seal.get("outbound_quantity")),
        )
    return sealed


def _send_stamps(store: SqliteEvidenceStore) -> dict[str, tuple[str, str | None]]:
    """``attempt_id -> (trading_date, send_started_time)`` as stamped at send start."""
    stamps: dict[str, tuple[str, str | None]] = {}
    for payload in _payloads(store, _TRANSPORT_SEND_KIND):
        attempt_id = payload.get("attempt_id")
        date = payload.get("trading_date")
        if isinstance(attempt_id, str) and isinstance(date, str) and date:
            stamps[attempt_id] = (date, _hhmmss(payload.get(_SEND_STARTED_FIELD)))
    return stamps


def _uncertain_attempt_ids(
    store: SqliteEvidenceStore, *, account: str, instrument: str
) -> list[str]:
    """Attempts whose every consumed receipt in this scope named no order, the last uncertain."""
    last_kind: dict[str, str] = {}
    numbered: set[str] = set()
    order: list[str] = []
    for payload in _payloads(store, _CONSUMED_KIND):
        key = payload.get("instrument_key")
        attempt_id = payload.get("attempt_id")
        if not isinstance(attempt_id, str) or not isinstance(key, dict):
            continue
        if key.get("account") != account or key.get("instrument") != instrument:
            continue
        if attempt_id not in last_kind:
            order.append(attempt_id)
        kind = payload.get("egress_result_kind")
        last_kind[attempt_id] = kind if isinstance(kind, str) else ""
        if isinstance(payload.get("broker_execution_id"), str):
            numbered.add(attempt_id)
    return [
        attempt_id
        for attempt_id in order
        if attempt_id not in numbered
        and last_kind[attempt_id] in _UNCERTAIN_RESULT_KINDS
    ]


def _verdicts(store: SqliteEvidenceStore) -> dict[str, dict[str, Any]]:
    """The newest recorded verdict per attempt."""
    verdicts: dict[str, dict[str, Any]] = {}
    for payload in _payloads(store, UNCERTAIN_SEND_RECONCILED_KIND):
        attempt_id = payload.get("attempt_id")
        if isinstance(attempt_id, str):
            verdicts[attempt_id] = payload
    return verdicts


def bound_sends(store: SqliteEvidenceStore) -> dict[str, tuple[str, str]]:
    """``attempt_id -> (broker_execution_id, trading_date)`` for every bound uncertain send."""
    bound: dict[str, tuple[str, str]] = {}
    for attempt_id, payload in _verdicts(store).items():
        odno = payload.get("broker_execution_id")
        date = payload.get("trading_date")
        if (
            payload.get("outcome") == BOUND
            and isinstance(odno, str)
            and (isinstance(date, str))
        ):
            bound[attempt_id] = (odno, date)
    return bound


def late_candidate_attempt_ids(store: SqliteEvidenceStore) -> frozenset[str]:
    """Every released send a late candidate has ALREADY halted this tenant for."""
    # SAFETY: 운영자가 재무장한 뒤 같은 날 다시 부팅하면 그 행이 또 보인다 — 거기서 또 래치하면 재무장이 영원히 되감긴다 (#1164 리뷰 L2)
    return frozenset(
        attempt_id
        for payload in _payloads(store, UNCERTAIN_SEND_LATE_CANDIDATE_KIND)
        if isinstance(attempt_id := payload.get("attempt_id"), str)
    )


def never_accepted_attempt_ids(store: SqliteEvidenceStore) -> frozenset[str]:
    """Every attempt a completed reconciliation proved the broker never accepted."""
    return frozenset(
        attempt_id
        for attempt_id, payload in _verdicts(store).items()
        if payload.get("outcome") == NEVER_ACCEPTED
    )


def uncertain_sends(
    store: SqliteEvidenceStore, *, account: str, instrument: str
) -> tuple[UncertainSend, ...]:
    """This scope's unresolved uncertain sends, each with the date and seal it needs."""
    sealed = _sealed(store, account=account, instrument=instrument)
    stamps = _send_stamps(store)
    settled = {
        attempt_id
        for attempt_id, payload in _verdicts(store).items()
        if payload.get("outcome") in (BOUND, NEVER_ACCEPTED)
    }
    sends: list[UncertainSend] = []
    for attempt_id in _uncertain_attempt_ids(
        store, account=account, instrument=instrument
    ):
        stamp = stamps.get(attempt_id)
        seal = sealed.get(attempt_id)
        if stamp is None or seal is None or attempt_id in settled:
            continue
        sends.append(
            UncertainSend(
                attempt_id=attempt_id,
                trading_date=stamp[0],
                side=seal[0],
                quantity=seal[1],
                send_started_time=stamp[1],
            )
        )
    return tuple(sends)


def released_sends(
    store: SqliteEvidenceStore, *, trading_date: str
) -> tuple[UncertainSend, ...]:
    """``trading_date``'s never_accepted verdicts, rebuilt from their own durable rows."""
    # SAFETY: 해제 뒤에도 그 날의 주문내역을 계속 본다 — 30 s 창 두 번으로 «미접수» 를 적고 풀어준 뒤 늦게 반영된 주문이 보이면 그 예약은 이미 두 번 나갔다 (#1129)
    sends: list[UncertainSend] = []
    for attempt_id, payload in _verdicts(store).items():
        if payload.get("outcome") != NEVER_ACCEPTED:
            continue
        date = payload.get("trading_date")
        quantity = _decimal(payload.get("sealed_quantity"))
        if date != trading_date or quantity is None:
            continue
        side = payload.get("sealed_side")
        started = payload.get(_SEND_STARTED_FIELD)
        sends.append(
            UncertainSend(
                attempt_id=attempt_id,
                trading_date=trading_date,
                side=side if isinstance(side, str) else None,
                quantity=quantity,
                send_started_time=started if isinstance(started, str) else None,
                released=True,
            )
        )
    return tuple(sends)


def candidate_rows(
    send: UncertainSend,
    rows: tuple[KisOrderRow, ...],
    *,
    instrument: str,
    claimed: ClaimedOrderDays,
    side_codes: SideCodes,
) -> tuple[KisOrderRow, ...]:
    """The rows on ``send``'s date that this send could own (the four parts above)."""
    taken = {
        (claimed_key, date)
        for claimed_key, date, owner in claimed
        if owner != send.attempt_id
    }
    if send.quantity is None:
        return ()
    wanted_code = None if send.side is None else side_codes.get(send.side)
    matched: list[KisOrderRow] = []
    for row in rows:
        key = odno_key(row.odno)
        if key is None or row.ord_dt != send.trading_date:
            continue
        if row.pdno != instrument or row.ord_qty != send.quantity:
            continue
        row_code = (row.sll_buy_dvsn_cd or "").strip()
        if row_code and wanted_code is not None and row_code != wanted_code:
            continue
        if (key, send.trading_date) in taken:
            continue
        matched.append(row)
    return tuple(matched)


def rows_by_send_time(
    send: UncertainSend,
    rows: tuple[KisOrderRow, ...],
    *,
    tolerance_s: int,
    foreign_min_age_s: int,
    discard_foreign: bool = True,
) -> tuple[tuple[KisOrderRow, ...], tuple[KisOrderRow, ...], tuple[KisOrderRow, ...]]:
    """``(eligible, unprovable, foreign)`` of ``rows`` against our send start (issue #1127)."""
    started = send.send_started_time
    eligible: list[KisOrderRow] = []
    unprovable: list[KisOrderRow] = []
    foreign: list[KisOrderRow] = []
    if started is None:
        return (), tuple(rows), ()
    ours_from = _shifted_back(started, tolerance_s)
    foreign_before = _shifted_back(started, foreign_min_age_s)
    for row in rows:
        if row.ord_tmd is None:
            unprovable.append(row)
        elif row.ord_tmd >= ours_from:
            eligible.append(row)
        elif row.ord_tmd < foreign_before and discard_foreign:
            foreign.append(row)
        else:
            # SAFETY: 증명 불가 행은 bind 도 never_accepted 도 막는다 — 우리 것일 수 있는 주문을 풀면 다음 OPEN 이 중복 송신한다 (#1127)
            unprovable.append(row)
    return tuple(eligible), tuple(unprovable), tuple(foreign)


def apply_uncertain_read(
    reconciler: UncertainSendReconciler | None,
    send: UncertainSend | None,
    result: FetchResult,
    *,
    claimed: ClaimedOrderDays,
) -> str | None:
    """APPLY one FETCH's uncertain-send read, or nothing when it has none to judge."""
    read = result.uncertain_send_read
    planned = result.plan.uncertain_send_read
    if reconciler is None or send is None or read is None or planned is None:
        return None
    rows, read_started_ms = read
    if isinstance(rows, WitnessUnavailable) or planned[0] != send.trading_date:
        return None
    return reconciler.apply_read(
        send, rows, read_started_ms=read_started_ms, claimed=claimed
    )


@dataclass
class UncertainSendReconciler:
    """Judge one uncertain send per read against the broker's own history (module docstring)."""

    evidence_store: SqliteEvidenceStore
    account: str
    instrument: str
    settle_ms: int
    ord_tmd_tolerance_s: int
    foreign_min_age_s: int
    side_codes: SideCodes
    record: Recorder
    today: Callable[[], str | None] | None = None
    halt: Recorder | None = None
    broker_clock_corroborated: Callable[[], bool] | None = None
    _first_seen_ms: dict[str, int] = field(default_factory=dict, init=False)
    _empty_reads: dict[str, list[int]] = field(default_factory=dict, init=False)
    _noted: set[tuple[str, str, tuple[str, ...]]] = field(
        default_factory=set, init=False
    )
    _last_watch_ms: dict[str, int] = field(default_factory=dict, init=False)
    _halted: set[str] = field(default_factory=set, init=False)
    _foreign_discard_admitted: bool = field(default=True, init=False)

    def due(self, now_ms: int) -> UncertainSend | None:
        """The one uncertain send this FETCH may read for, or ``None``. Never raises."""
        try:
            sends = uncertain_sends(
                self.evidence_store, account=self.account, instrument=self.instrument
            )
        except Exception:  # noqa: BLE001 - an unreadable store reconciles nothing
            return None
        live = {send.attempt_id for send in sends}
        for attempt_id in [key for key in self._first_seen_ms if key not in live]:
            self._first_seen_ms.pop(attempt_id, None)
            self._empty_reads.pop(attempt_id, None)
        if not sends:
            return self._due_watch(now_ms)
        send = sends[0]
        self._first_seen_ms.setdefault(send.attempt_id, now_ms)
        return send

    def _due_watch(self, now_ms: int) -> UncertainSend | None:
        """The one released send whose same-day recheck is due, or ``None`` (issue #1129)."""
        if self.today is None or self.halt is None:
            return None
        try:
            today = self.today()
            watched = (
                ()
                if today is None
                else released_sends(self.evidence_store, trading_date=today)
            )
            halted = late_candidate_attempt_ids(self.evidence_store)
        except Exception:  # noqa: BLE001 - an unreadable store rechecks nothing
            return None
        for send in watched:
            if send.attempt_id in self._halted or send.attempt_id in halted:
                continue
            last = self._last_watch_ms.get(send.attempt_id)
            if last is not None and now_ms - last < self.settle_ms:
                continue
            self._last_watch_ms[send.attempt_id] = now_ms
            return send
        return None

    def apply_read(
        self,
        send: UncertainSend,
        rows: tuple[KisOrderRow, ...],
        *,
        read_started_ms: int,
        claimed: ClaimedOrderDays,
    ) -> str | None:
        """Judge one date's rows; the recorded outcome, or ``None`` when the hold stands."""
        if send.side is not None and self.side_codes.get(send.side) is None:
            # SAFETY: 설정에 그 side 의 브로커 코드가 없으면 방향 필터가 조용히 꺼진다 — 반대 방향 주문에 bind 하거나, 우리 주문을 못 보고 never_accepted 로 풀어 두 번 보낸다 (#1129 LOW 8)
            self._note(send, UNKNOWN_SIDE_CODE, ())
            return None
        matched = candidate_rows(
            send,
            rows,
            instrument=self.instrument,
            claimed=claimed,
            side_codes=self.side_codes,
        )
        self._foreign_discard_admitted = self._discard_foreign()
        eligible, unprovable, foreign = rows_by_send_time(
            send,
            matched,
            tolerance_s=self.ord_tmd_tolerance_s,
            foreign_min_age_s=self.foreign_min_age_s,
            discard_foreign=self._foreign_discard_admitted,
        )
        if send.released:
            return self._judge_released(send, eligible + unprovable)
        if unprovable:
            self._empty_reads.pop(send.attempt_id, None)
            self._note(send, UNPROVABLE_TIME, unprovable, foreign=foreign)
            return None
        if len(eligible) > 1:
            self._empty_reads.pop(send.attempt_id, None)
            self._note(send, AMBIGUOUS, eligible, foreign=foreign)
            return None
        if len(eligible) == 1:
            self._empty_reads.pop(send.attempt_id, None)
            return self._write(send, BOUND, odno=eligible[0].odno, foreign=foreign)
        if not self._empty_settled(send, read_started_ms):
            return None
        return self._write(send, NEVER_ACCEPTED, odno=None, foreign=foreign)

    def _discard_foreign(self) -> bool:
        """May a row older than ``foreign_min_age_s`` be called somebody else's? (issue #1138)"""
        # SAFETY: 호스트 시계가 브로커보다 그만큼 앞서면 우리 주문이 «남의 것» 으로 버려지고 never_accepted → 해제 → 두 번째 주문이 된다 — 스큐를 재서 증명하지 못하면 버리지 않는다
        if self.broker_clock_corroborated is None:
            return True
        try:
            return self.broker_clock_corroborated() is True
        except Exception:  # noqa: BLE001 - an unmeasurable clock discards nothing
            return False

    def _replacement_unresolved(self) -> bool:
        """Did another send go uncertain between this watch's PLAN and its APPLY? (#1164 M1)"""
        # SAFETY: 그 대체 송신의 행은 아직 ODNO 를 claim 하지 않아 해제된 송신의 «늦은 후보» 로 보인다 — 여기서 래치하면 멀쩡한 tenant 를 거짓으로 멈춘다. 미뤄도 다음 감시 읽기가 다시 판정한다
        try:
            return bool(
                uncertain_sends(
                    self.evidence_store,
                    account=self.account,
                    instrument=self.instrument,
                )
            )
        except Exception:  # noqa: BLE001 - an unreadable store defers, never halts
            return True

    def _judge_released(
        self, send: UncertainSend, late: tuple[KisOrderRow, ...]
    ) -> str | None:
        """A same-day read of an already released send: any row it could own halts (#1129)."""
        if not late or send.attempt_id in self._halted or self.halt is None:
            return None
        if self._replacement_unresolved():
            return None
        self._halted.add(send.attempt_id)
        self.halt(
            UNCERTAIN_SEND_LATE_CANDIDATE_KIND,
            {
                "attempt_id": send.attempt_id,
                "trading_date": send.trading_date,
                "sealed_side": send.side,
                "sealed_quantity": (
                    None if send.quantity is None else format(send.quantity, "f")
                ),
                "send_started_time": send.send_started_time,
                "settle_ms": self.settle_ms,
                "candidate_order_ids": [row.odno for row in late],
                "candidate_order_times": [row.ord_tmd for row in late],
            },
        )
        return UNCERTAIN_SEND_LATE_CANDIDATE_KIND

    def _empty_settled(self, send: UncertainSend, read_started_ms: int) -> bool:
        """``CONFIRMING_EMPTY_READS`` empty reads, ``settle_ms`` apart, after the first sighting."""
        first_seen = self._first_seen_ms.get(send.attempt_id)
        if first_seen is None or read_started_ms - first_seen < self.settle_ms:
            return False
        reads = self._empty_reads.setdefault(send.attempt_id, [])
        if reads and read_started_ms - reads[-1] < self.settle_ms:
            return False
        reads.append(read_started_ms)
        return len(reads) >= CONFIRMING_EMPTY_READS

    def _note(
        self,
        send: UncertainSend,
        outcome: str,
        matched: tuple[KisOrderRow, ...],
        *,
        foreign: tuple[KisOrderRow, ...] = (),
    ) -> None:
        """One row per (attempt, outcome, rows seen) per process for a verdict that changes"""
        # SAFETY: (attempt, outcome) 만으로 묶으면 결과가 UNPROVABLE_TIME 에 머무는 동안 버려진 행이 바뀌어도 기록되지 않아 감사에서 사라진다 (#1138 LOW)
        rows = tuple(sorted(f"{row.odno}" for row in matched + foreign))
        signature = (send.attempt_id, outcome, rows)
        if signature in self._noted:
            return
        self._noted.add(signature)
        self._row(send, outcome, odno=None, matched=matched, foreign=foreign)

    def _write(
        self,
        send: UncertainSend,
        outcome: str,
        *,
        odno: str | None,
        foreign: tuple[KisOrderRow, ...] = (),
    ) -> str:
        self._row(send, outcome, odno=odno, matched=(), foreign=foreign)
        return outcome

    def _row(
        self,
        send: UncertainSend,
        outcome: str,
        *,
        odno: str | None,
        matched: tuple[KisOrderRow, ...],
        foreign: tuple[KisOrderRow, ...] = (),
    ) -> None:
        self.record(
            UNCERTAIN_SEND_RECONCILED_KIND,
            {
                "attempt_id": send.attempt_id,
                "outcome": outcome,
                "broker_execution_id": odno,
                "trading_date": send.trading_date,
                "sealed_side": send.side,
                "sealed_quantity": (
                    None if send.quantity is None else format(send.quantity, "f")
                ),
                "candidate_order_ids": [row.odno for row in matched],
                "settle_ms": self.settle_ms,
                "send_started_time": send.send_started_time,
                "ord_tmd_tolerance_s": self.ord_tmd_tolerance_s,
                "foreign_min_age_s": self.foreign_min_age_s,
                "candidate_order_times": [row.ord_tmd for row in matched],
                "discarded_order_ids": [row.odno for row in foreign],
                "discarded_order_times": [row.ord_tmd for row in foreign],
                "foreign_discard_admitted": self._foreign_discard_admitted,
            },
        )
