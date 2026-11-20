"""Release a held entry reservation once the broker double-reads its instrument flat (2026-11-19).

Operator decision 2026-11-19 (option B): one position per symbol stays (step 8's no-pyramiding),
but an entry reservation whose position is already gone at the broker must not block the scope
for the rest of the day. The receipt-corroborated discharge (``entry_recovery``) can stay held
forever when the close proof stops transferring or the order inquiry keeps failing; this path
needs neither. It is opt-in per tenant (``fill_observer.yaml::broker_flat_release``) and runs on
the held-position double read the observer already polls, so its retry cadence is
``held_position_poll_interval_ms`` and a failed read simply waits for the next one.

It releases only when ALL hold, judged on the session-loop thread:

* (a) the scope's only outstanding RCL reservation is one ``POSITION_CONSUMED`` entry — i.e. a
  FULL_FILL with nothing remaining; any other outstanding reservation (an OPEN or CLOSE between
  step 8 and its release) refuses;
* (b) BOTH reads of the double observation succeeded, are complete and broker-independent, show
  the instrument at zero, belong to this scope and trading date, and are within
  ``held_position_max_age_ms``;
* (c) no TOS attempt for the scope is in flight: every sealed send has a terminal, matched result
  (``EvidencePositionReader``'s ``in_flight_*`` are zero);
* the RCL has not moved since the read was planned except by approval consumption, and the RCL
  append is CAS-fenced on the tip read here;
* (d) the flat result is CONFIRMED: a first qualifying flat poll whose read started at least
  ``settle_ms`` after this process first saw the entry consumed, then a second qualifying flat
  poll whose read started at least ``confirm_interval_ms`` later, with only approval consumption
  between their RCL tips. Any other verdict in between resets the first. This covers the mock
  account's fill-to-balance reflection lag (no published bound in the broker profile): a balance
  that has not yet reflected the entry's buy reads flat right after the FULL_FILL, and releasing
  on it would let the next OPEN buy a second lot while the first becomes an untracked orphan.

Only an RCL refusal or an RCL error ends a release attempt quietly (``BROKER_FLAT_RELEASE_HELD``);
an evidence-store append failure propagates, as it does from every other release writer here.
Every verdict other than ``RELEASED`` is recorded once per process as a
``BROKER_FLAT_RELEASE_HELD`` row so an operator can see why nothing released.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from tos.canonical import CanonicalizationScheme
from tos.rcl import (
    AppendRefusal,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
)

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.fill_fetch import HeldPositionSnapshot
from tos_runtime.rcl.log import ReservationTransitionRefusal, SqliteCommitLog
from tos_runtime.recon.ports import WitnessSnapshot
from tos_runtime.riskstate.held_position import RclTip

__all__ = [
    "BROKER_FLAT_RELEASE_COMMAND_PREFIX",
    "BROKER_FLAT_RELEASE_HELD_KIND",
    "BROKER_FLAT_RELEASE_KIND",
    "BrokerFlatRelease",
    "BrokerFlatVerdict",
    "broker_flat_release_command_id",
]

BROKER_FLAT_RELEASE_KIND = "BROKER_FLAT_RELEASE"
BROKER_FLAT_RELEASE_HELD_KIND = "BROKER_FLAT_RELEASE_HELD"
BROKER_FLAT_RELEASE_COMMAND_PREFIX = "broker-flat-release-"


def broker_flat_release_command_id(reservation_id: str) -> str:
    """The RCL idempotency key of ``reservation_id``'s broker-flat release — the ONE spelling."""
    return f"{BROKER_FLAT_RELEASE_COMMAND_PREFIX}{reservation_id}"


class BrokerFlatVerdict(StrEnum):
    """What one evaluation did; only ``RELEASED`` changed the RCL."""

    RELEASED = "RELEASED"
    READ_FAILED = "READ_FAILED"
    NOT_FLAT = "NOT_FLAT"
    STALE = "STALE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    IN_FLIGHT = "IN_FLIGHT"
    RCL_MOVED = "RCL_MOVED"
    RCL_REFUSED = "RCL_REFUSED"
    SETTLING = "SETTLING"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"


@dataclass(frozen=True)
class _FirstFlat:
    reservation_id: str
    tip: RclTip
    started_ms: int


def _flat(observation: object, instrument: str) -> bool | None:
    """``True`` flat, ``False`` held, ``None`` when the read is not a usable proof either way."""
    if (
        not isinstance(observation, WitnessSnapshot)
        or not observation.positions_complete
        or not observation.independent_of_evidence_store
    ):
        return None
    return not any(
        symbol == instrument and quantity != 0
        for symbol, quantity in observation.positions
    )


@dataclass
class BrokerFlatRelease:
    """Evaluate one published held-position double read (module docstring)."""

    rcl_log: SqliteCommitLog
    evidence_store: SqliteEvidenceStore
    scheme: CanonicalizationScheme
    account: str
    instrument: str
    today: Callable[[], str | None]
    now_ms: Callable[[], int]
    max_age_ms: int
    in_flight: Callable[[], bool]
    tip_compatible: Callable[[RclTip, RclTip], bool]
    settle_ms: int
    confirm_interval_ms: int
    _consumed_seen_ms: dict[str, int] = field(default_factory=dict, init=False)
    _first_flat: _FirstFlat | None = field(default=None, init=False)
    _noted: set[str] = field(default_factory=set, init=False)

    def __call__(self, snapshot: HeldPositionSnapshot) -> BrokerFlatVerdict:
        verdict = self._evaluate(snapshot)
        if verdict is not BrokerFlatVerdict.AWAITING_CONFIRMATION:
            self._first_flat = None
        if verdict not in (BrokerFlatVerdict.RELEASED, BrokerFlatVerdict.RCL_REFUSED):
            self._note(verdict)
        return verdict

    def _note(self, verdict: BrokerFlatVerdict) -> None:
        """One ``BROKER_FLAT_RELEASE_HELD`` row per verdict per process (an operator's why).

        A failed append propagates out of the observation pass (#1115 N3, recorded not changed):
        every writer on this path behaves that way — an evidence store that cannot take a row is
        not a condition under which this runtime keeps deciding — and the verdict it would have
        explained is a HOLD, so nothing is released by the raise. The ``_noted`` guard is set
        BEFORE the append on purpose: a store that refuses once refuses again, and retrying the
        same row each pass would turn one failure into a per-pass exception storm.
        """
        if verdict.value in self._noted:
            return
        self._noted.add(verdict.value)
        self.evidence_store.append(
            {
                "account": self.account,
                "instrument": self.instrument,
                "verdict": verdict.value,
                "settle_ms": self.settle_ms,
                "confirm_interval_ms": self.confirm_interval_ms,
            },
            kind=BROKER_FLAT_RELEASE_HELD_KIND,
            record_class=BROKER_FLAT_RELEASE_HELD_KIND,
        )

    def _evaluate(self, snapshot: HeldPositionSnapshot) -> BrokerFlatVerdict:
        verdict = self._read_verdict(snapshot)
        if verdict is not None:
            return verdict
        try:
            epoch = self.rcl_log.current_epoch()
            if epoch is None:
                return BrokerFlatVerdict.RCL_MOVED
            view = self.rcl_log.read_linearizable(writer_epoch=epoch)
            rows = tuple(
                (reservation_id, state)
                for reservation_id, state, _seq, scope in self.rcl_log.reservation_rows()
                if scope.account == self.account
                and scope.instrument == self.instrument
                and state is not CapacityState.RELEASED
            )
        except Exception:  # noqa: BLE001 - an unreadable RCL releases nothing
            return BrokerFlatVerdict.RCL_MOVED
        if not self._tip_unmoved(snapshot, RclTip(epoch, view.last_seq)):
            return BrokerFlatVerdict.RCL_MOVED
        if len(rows) != 1 or rows[0][1] is not CapacityState.POSITION_CONSUMED:
            return BrokerFlatVerdict.NOT_ELIGIBLE
        try:
            in_flight = self.in_flight()
        except Exception:  # noqa: BLE001 - unknown in-flight state is in flight
            in_flight = True
        if in_flight is not False:
            return BrokerFlatVerdict.IN_FLIGHT
        reservation_id = rows[0][0]
        if not self._confirmed(reservation_id, snapshot, RclTip(epoch, view.last_seq)):
            if self._first_flat is None:
                return BrokerFlatVerdict.SETTLING
            return BrokerFlatVerdict.AWAITING_CONFIRMATION
        return self._release(
            reservation_id, snapshot, epoch=epoch, last_seq=view.last_seq
        )

    def _confirmed(
        self, reservation_id: str, snapshot: HeldPositionSnapshot, current: RclTip
    ) -> bool:
        """(d): settle after the entry was first seen consumed, then a second flat poll."""
        started = snapshot.first_balance_read_started_ms
        assert started is not None  # _read_verdict refused a read without one
        seen = self._consumed_seen_ms.setdefault(reservation_id, self.now_ms())
        if started < seen + self.settle_ms:
            self._first_flat = None
            return False
        first = self._first_flat
        if (
            first is None
            or first.reservation_id != reservation_id
            or not self._compatible(first.tip, current)
        ):
            self._first_flat = _FirstFlat(reservation_id, current, started)
            return False
        return started - first.started_ms >= self.confirm_interval_ms

    def _read_verdict(self, snapshot: HeldPositionSnapshot) -> BrokerFlatVerdict | None:
        """(b): ``None`` when both reads prove this scope flat today and fresh enough."""
        first = _flat(snapshot.first, self.instrument)
        confirmation = _flat(snapshot.confirmation, self.instrument)
        if first is None or confirmation is None:
            return BrokerFlatVerdict.READ_FAILED
        if not (first and confirmation):
            return BrokerFlatVerdict.NOT_FLAT
        scope = snapshot.scope
        today = self.today()
        if (
            scope is None
            or scope.account != self.account
            or tuple(key.instrument for key in scope.instrument_keys)
            != (self.instrument,)
            or today is None
            or snapshot.today != today
        ):
            return BrokerFlatVerdict.STALE
        started = snapshot.first_balance_read_started_ms
        if (
            started is None
            or snapshot.confirmation_balance_read_started_ms is None
            or self.now_ms() - started > self.max_age_ms
        ):
            return BrokerFlatVerdict.STALE
        return None

    def _tip_unmoved(self, snapshot: HeldPositionSnapshot, current: RclTip) -> bool:
        """Nothing but approval consumption reached the RCL since the read was planned."""
        if snapshot.tip is None:
            return False
        try:
            original = RclTip(*snapshot.tip)
        except (TypeError, ValueError):
            return False
        return self._compatible(original, current)

    def _compatible(self, original: RclTip, current: RclTip) -> bool:
        if original == current:
            return True
        try:
            return self.tip_compatible(original, current) is True
        except Exception:  # noqa: BLE001 - an unprovable gap releases nothing
            return False

    def _release(
        self,
        reservation_id: str,
        snapshot: HeldPositionSnapshot,
        *,
        epoch: int,
        last_seq: int | None,
    ) -> BrokerFlatVerdict:
        command_id = broker_flat_release_command_id(reservation_id)
        self.evidence_store.append(
            {
                "reservation_id": reservation_id,
                "account": self.account,
                "instrument": self.instrument,
                "reason": BROKER_FLAT_RELEASE_KIND,
                "command_id": command_id,
                "trading_date": snapshot.today,
                "rcl_writer_epoch": epoch,
                "rcl_last_seq": last_seq,
                "first_balance_read_started_ms": snapshot.first_balance_read_started_ms,
                "confirmation_balance_read_started_ms": (
                    snapshot.confirmation_balance_read_started_ms
                ),
            },
            kind=BROKER_FLAT_RELEASE_KIND,
            record_class=BROKER_FLAT_RELEASE_KIND,
        )
        transition = CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=epoch,
            from_state=CapacityState.POSITION_CONSUMED,
            to_state=CapacityState.RELEASED,
            scope=ReservationScope(account=self.account, instrument=self.instrument),
        )
        try:
            receipt = self.rcl_log.apply_reservation_transition(
                transition,
                TransitionCause.FINAL_QUANTITY_PROOF,
                command_type=CommandType.RELEASE_RESERVATION,
                command_id=command_id,
                command_digest=self.scheme.compute_digest(
                    {
                        "reservation_id": reservation_id,
                        "to_state": CapacityState.RELEASED.value,
                        "cause": BROKER_FLAT_RELEASE_KIND,
                    }
                ),
                expected_seq=-1 if last_seq is None else last_seq,
                finality_witness=True,
            )
        except ReservationTransitionRefusal as exc:
            detail = str(exc)
        except (
            Exception
        ) as exc:  # noqa: BLE001 - an RCL error releases nothing; next poll retries
            detail = f"RCL append failed: {type(exc).__name__}: {exc}"
        else:
            if not isinstance(receipt, AppendRefusal):
                return BrokerFlatVerdict.RELEASED
            detail = f"{receipt.reason}: {receipt.detail}"
        self.evidence_store.append(
            {
                "account": self.account,
                "instrument": self.instrument,
                "verdict": BrokerFlatVerdict.RCL_REFUSED.value,
                "reservation_id": reservation_id,
                "command_id": command_id,
                "detail": detail,
            },
            kind=BROKER_FLAT_RELEASE_HELD_KIND,
            record_class=BROKER_FLAT_RELEASE_HELD_KIND,
        )
        return BrokerFlatVerdict.RCL_REFUSED
