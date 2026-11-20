"""Resolve an order POST whose answer named no order, from the broker's own daily history.

Incident 2026-11-20 shapes (d) and (e): the order POST timed out, or answered HTTP 500. Either
way ``KisMockTransport`` returns a result with no ``broker_execution_id``, the engine quarantines
the reservation (``QUARANTINED_UNKNOWN`` / ``UNKNOWN``), the RCL reservation stays
``COMMITTED_UNBOUND``, and every later OPEN halts at step 8 over
``MAX_unresolved_send_per_scope``. The gateway's ``UNCERTAIN_SEND`` row already records
``start_reconciliation=True``; this module is that reconciliation. GET only — it never sends.

It reads 주식일별주문체결조회 (``VTTC0081R``) for the trading date the send itself was stamped
with (``TRANSPORT_SEND``'s own ``trading_date``) and judges the rows against what the send
sealed:

* **exactly one** unclaimed candidate row -> ``bound``. The ODNO is written to evidence and the
  fill observer tracks the attempt from the next pass, so the ordinary fill/finality path runs
  (a FULL_FILL resolves the quarantine to ``POSITION_CONSUMED``).
* **no** candidate row, on :data:`CONFIRMING_EMPTY_READS` consecutive reads at least
  ``settle_ms`` apart, the first of them at least ``settle_ms`` after this process first saw the
  uncertain send -> ``never_accepted``. The reservation is then given back through the existing
  never-sent release pass (``unsent_release``) under its own cause. The settle window is the
  same device ``broker_flat_release`` (d) uses, for the same reason: the mock account publishes
  no bound on how soon an accepted order appears in its own history, and releasing on a history
  that has not caught up yet would let the next OPEN send a second order for the same position.
* **more than one** candidate, or a failed read -> held. Nothing is written that changes a
  decision, the hold stands, and the next poll asks again.

A candidate is more than "an order on that date": it must name this instrument, carry the
attempt's own sealed outbound quantity, not carry the ``sll_buy_dvsn_cd`` of the OTHER side
(``uncertain_send_side_codes``; a row with no code is "unknown", never a refusal), and fall on
an (ODNO, date) pair no OTHER attempt's dated receipt already claims — the same four-part rule
issue #1096's dateless-ACK recovery uses, minus the ODNO it does not have.

**And it must be stamped no earlier than our own send (issue #1127).** Those four parts say
nothing about WHEN the order was placed, so one earlier order of the same shape on the same
day — a manual MOCK flatten, or an order an archived leaf placed before this one booted — was
a lone candidate and got bound to our attempt: an order we never sent recorded as our ACK,
with the reservation tied to its ODNO. The broker stamps 주문시각 (``ord_tmd``) when it
accepts an order, so a row OUR POST created cannot carry a stamp earlier than the instant that
POST started (``TRANSPORT_SEND``'s own ``send_started_time``), less
``uncertain_send_ord_tmd_tolerance_s`` of slack for the field's 1-second resolution and for
host-vs-broker clock skew. Three answers, not two:

* stamped at or after that threshold -> a candidate, judged by the counts above;
* stamped strictly before it -> somebody else's order. Dropped, so the date reads as the
  empty history it is for THIS send;
* **unprovable** (the row carries no stamp, or our own send carries none) -> held. It can
  never be bound, and it keeps an empty-read proof from completing, because an order that
  might be ours must not be released as never accepted.
"""

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
    "NEVER_ACCEPTED",
    "UNCERTAIN_SEND_RECONCILED_KIND",
    "UNPROVABLE_TIME",
    "UncertainSend",
    "UncertainSendReconciler",
    "apply_uncertain_read",
    "bound_sends",
    "never_accepted_attempt_ids",
    "rows_by_send_time",
    "uncertain_sends",
]

UNCERTAIN_SEND_RECONCILED_KIND = "UNCERTAIN_SEND_RECONCILED"

BOUND = "bound"
NEVER_ACCEPTED = "never_accepted"
AMBIGUOUS = "ambiguous"
#: A row this send could own that no clock can place against our own send start (issue #1127).
#: Like :data:`AMBIGUOUS` it is a NOTE: it settles nothing, so the send stays a target and the
#: next poll asks again. Only ``bound`` / ``never_accepted`` end a reconciliation.
UNPROVABLE_TIME = "unprovable_time"

#: Consecutive empty reads required before "the broker never accepted it" is believed.
CONFIRMING_EMPTY_READS = 2

#: The result kinds that establish no knowledge: an answer that named no order.
_UNCERTAIN_RESULT_KINDS = frozenset({"TIMEOUT", "UNKNOWN"})

_CONSUMED_KIND = "EGRESS_RESULT_CONSUMED"
_SEND_SEALED_KIND = "SEND_SEALED"
_TRANSPORT_SEND_KIND = "TRANSPORT_SEND"

#: ``TRANSPORT_SEND``'s own send-start wall time (``HHMMSS`` in the calendar timezone — KST
#: here), stamped by the transport before the POST (``SendStamp.started_time``).
_SEND_STARTED_FIELD = "send_started_time"

#: The threshold clamp :func:`_shifted_back` stops at: no broker stamp on the send's own
#: trading date can be earlier than that date's own start.
_DAY_START = "000000"

#: ``(odno_key, trading_date, attempt_id)`` of every DATED receipt, as the fill observer builds
#: it. A pair another attempt claims is never a candidate for this one.
ClaimedOrderDays = frozenset[tuple[str, str, str]]

#: ``outbound_side`` token -> the ``sll_buy_dvsn_cd`` the broker prints for it. CONFIG, never a
#: constant here: a side is a policy-carried token everywhere in this runtime
#: (``tests/test_no_side_literals.py``), and the code is the broker's spelling of it, not ours.
SideCodes = Mapping[str, str]

Recorder = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True)
class UncertainSend:
    """One send whose answer named no order, and what it sealed."""

    attempt_id: str
    trading_date: str
    side: str | None
    quantity: Decimal | None
    #: The transport's own send-start wall time (``HHMMSS``), or ``None`` when the send
    #: recorded none — then no row is provably ours and nothing binds (issue #1127).
    send_started_time: str | None


def _hhmmss(value: object) -> str | None:
    """One 주문시각-shaped stamp, through the broker-row parser #1126 already uses for it.

    ``KisOrderRow.from_wire`` is where this runtime decides what a 주문시각 is (six digits;
    anything else is ``None``). Our own send stamp is written in that same shape by the same
    transport that reads the broker's, so the same code validates both rather than a second
    copy of the rule.
    """
    return KisOrderRow.from_wire({"ord_tmd": value}).ord_tmd


def _shifted_back(stamp: str, seconds: int) -> str:
    """``stamp`` (``HHMMSS``, already validated) ``seconds`` earlier, clamped to the day start.

    The clamp keeps the threshold inside the one day being compared: a tolerance that would
    push it into the previous day admits every row on this date instead of refusing rows that
    cannot exist (no KRX order is placed at 00:00).
    """
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


def candidate_rows(
    send: UncertainSend,
    rows: tuple[KisOrderRow, ...],
    *,
    instrument: str,
    claimed: ClaimedOrderDays,
    side_codes: SideCodes,
) -> tuple[KisOrderRow, ...]:
    """The rows on ``send``'s date that this send could own (the four parts above).

    Identity only — WHEN the broker placed each one is :func:`rows_by_send_time`'s question,
    and both must answer before a row is a candidate.
    """
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
) -> tuple[tuple[KisOrderRow, ...], tuple[KisOrderRow, ...]]:
    """``(eligible, unprovable)`` of ``rows`` against our own send start (issue #1127).

    ``rows`` are already the four-part candidates. The broker stamps 주문시각 when it accepts
    an order, so a row OUR POST created cannot be stamped before that POST started, less
    ``tolerance_s``. A row stamped strictly before the threshold is somebody else's and is in
    neither tuple — dropped, so the date reads as the empty history it is for this send. A row
    with no stamp, and every row when the send itself has no start stamp, is ``unprovable``:
    never bound, and never released as never-accepted either (module docstring).

    Both stamps are wall times on ``send.trading_date``: the caller has already refused every
    row whose ``ord_dt`` is another date, so the comparison is within one day and lexical
    ordering of two ``HHMMSS`` strings is chronological.
    """
    threshold = (
        None
        if send.send_started_time is None
        else _shifted_back(send.send_started_time, tolerance_s)
    )
    eligible: list[KisOrderRow] = []
    unprovable: list[KisOrderRow] = []
    for row in rows:
        if threshold is None or row.ord_tmd is None:
            unprovable.append(row)
        elif row.ord_tmd >= threshold:
            eligible.append(row)
    return tuple(eligible), tuple(unprovable)


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
    #: ``fill_observer.yaml::uncertain_send_ord_tmd_tolerance_s`` — how far before our own send
    #: start a broker 주문시각 may still be ours (issue #1127).
    ord_tmd_tolerance_s: int
    side_codes: SideCodes
    record: Recorder
    _first_seen_ms: dict[str, int] = field(default_factory=dict, init=False)
    _empty_reads: dict[str, list[int]] = field(default_factory=dict, init=False)
    _noted: set[tuple[str, str]] = field(default_factory=set, init=False)

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
            return None
        send = sends[0]
        self._first_seen_ms.setdefault(send.attempt_id, now_ms)
        return send

    def apply_read(
        self,
        send: UncertainSend,
        rows: tuple[KisOrderRow, ...],
        *,
        read_started_ms: int,
        claimed: ClaimedOrderDays,
    ) -> str | None:
        """Judge one date's rows; the recorded outcome, or ``None`` when the hold stands."""
        matched = candidate_rows(
            send,
            rows,
            instrument=self.instrument,
            claimed=claimed,
            side_codes=self.side_codes,
        )
        eligible, unprovable = rows_by_send_time(
            send, matched, tolerance_s=self.ord_tmd_tolerance_s
        )
        if unprovable:
            self._empty_reads.pop(send.attempt_id, None)
            self._note(send, UNPROVABLE_TIME, unprovable)
            return None
        if len(eligible) > 1:
            self._empty_reads.pop(send.attempt_id, None)
            self._note(send, AMBIGUOUS, eligible)
            return None
        if len(eligible) == 1:
            self._empty_reads.pop(send.attempt_id, None)
            return self._write(send, BOUND, odno=eligible[0].odno)
        if not self._empty_settled(send, read_started_ms):
            return None
        return self._write(send, NEVER_ACCEPTED, odno=None)

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
        self, send: UncertainSend, outcome: str, matched: tuple[KisOrderRow, ...]
    ) -> None:
        """One row per (attempt, outcome) per process for a verdict that changes nothing."""
        signature = (send.attempt_id, outcome)
        if signature in self._noted:
            return
        self._noted.add(signature)
        self._row(send, outcome, odno=None, matched=matched)

    def _write(self, send: UncertainSend, outcome: str, *, odno: str | None) -> str:
        self._row(send, outcome, odno=odno, matched=())
        return outcome

    def _row(
        self,
        send: UncertainSend,
        outcome: str,
        *,
        odno: str | None,
        matched: tuple[KisOrderRow, ...],
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
                # What the time rule judged this verdict with (issue #1127): our own send
                # start, the slack it allowed, and each candidate's broker 주문시각 — the
                # three numbers an operator needs to read a hold they did not expect.
                "send_started_time": send.send_started_time,
                "ord_tmd_tolerance_s": self.ord_tmd_tolerance_s,
                "candidate_order_times": [row.ord_tmd for row in matched],
            },
        )
