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
  append is CAS-fenced on the tip read here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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


@dataclass(frozen=True)
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

    def __call__(self, snapshot: HeldPositionSnapshot) -> BrokerFlatVerdict:
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
        return self._release(rows[0][0], snapshot, epoch=epoch, last_seq=view.last_seq)

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
        else:
            if not isinstance(receipt, AppendRefusal):
                return BrokerFlatVerdict.RELEASED
            detail = f"{receipt.reason}: {receipt.detail}"
        self.evidence_store.append(
            {
                "reservation_id": reservation_id,
                "command_id": command_id,
                "detail": detail,
            },
            kind=BROKER_FLAT_RELEASE_HELD_KIND,
            record_class=BROKER_FLAT_RELEASE_HELD_KIND,
        )
        return BrokerFlatVerdict.RCL_REFUSED
