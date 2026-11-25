"""The durable CLOSE quantity bound of this scope's open entry (#1011, #1012 L3)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from tos.engine.records import InstrumentKey, StageRequest
from tos.rcl import CapacityState

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.close_history import durable_close_history
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import (
    ReservationProjectionReader,
    outstanding_reservations,
)
from tos_runtime.risk.close_quantity import close_within_entry
from tos_runtime.risk.ledger_stages import SyntheticCloseEntryFence

__all__ = [
    "CloseAuthoritySource",
    "CloseBoundRefusal",
    "DurableEntryCloseBoundReader",
    "EntryCloseBound",
    "synthetic_close_effect",
    "synthetic_close_fence",
]

CLOSE_BOUND_ACCEPTED = "PROOF_ACCEPTED"
CLOSE_BOUND_EXCEEDS_ENTRY = "QUANTITY_EXCEEDS_ENTRY"
CLOSE_BOUND_QUANTITY_UNKNOWN = "QUANTITY_UNKNOWN"
CLOSE_BOUND_UNPROVEN = "ENTRY_BOUND_UNPROVEN"


class CloseAuthoritySource(StrEnum):
    """What a boot's CLOSE quantity bound is allowed to rest on."""

    BROKER_HELD_PROOF = "BROKER_HELD_PROOF"
    DURABLE_EVIDENCE = "DURABLE_EVIDENCE"


class CloseBoundRefusal(StrEnum):
    """This module's own reasons a bound could not be read (close-history reasons pass"""

    SCOPE_READ_FAILED = "SCOPE_READ_FAILED"
    ENTRY_NOT_SOLE_CONSUMED_POSITION = "ENTRY_NOT_SOLE_CONSUMED_POSITION"
    HISTORY_READ_FAILED = "HISTORY_READ_FAILED"
    HISTORY_INCOMPLETE = "HISTORY_INCOMPLETE"
    READER_NOT_CONFIGURED = "READER_NOT_CONFIGURED"
    READER_UNUSABLE = "READER_UNUSABLE"


@dataclass(frozen=True)
class EntryCloseBound:
    """The proven open-entry magnitudes of one scope, or a refusal with every quantity absent."""

    account: str
    instrument: str
    entry_reservation_id: str | None
    entry_attempt_id: str | None
    entry_quantity: Decimal | None
    prior_closed: Decimal | None
    rcl_writer_epoch: int | None
    rcl_last_seq: int | None
    refusal: str | None

    @property
    def proven(self) -> bool:
        """Whether every required fact was positively established."""
        return self.refusal is None

    @property
    def remaining(self) -> Decimal | None:
        """The part of the entry no proven close has discharged yet, or ``None`` if unknown."""
        if self.entry_quantity is None or self.prior_closed is None:
            return None
        return self.entry_quantity - self.prior_closed

    def revalidates(self, current: EntryCloseBound) -> bool:
        """Whether ``current`` is a second reading of the SAME entry, at a tip no older."""
        if not (self.proven and current.proven):
            return False
        if (
            self.account,
            self.instrument,
            self.entry_reservation_id,
            self.entry_attempt_id,
            self.entry_quantity,
            self.prior_closed,
        ) != (
            current.account,
            current.instrument,
            current.entry_reservation_id,
            current.entry_attempt_id,
            current.entry_quantity,
            current.prior_closed,
        ):
            return False
        if (
            type(self.rcl_writer_epoch) is not int
            or current.rcl_writer_epoch != self.rcl_writer_epoch
            or type(self.rcl_last_seq) is not int
            or type(current.rcl_last_seq) is not int
        ):
            return False
        return current.rcl_last_seq >= self.rcl_last_seq


class DurableEntryCloseBoundReader:
    """Reads one scope's open-entry bound off the RCL projection + durable close history."""

    def __init__(
        self,
        *,
        rcl_log: SqliteCommitLog,
        evidence_store: SqliteEvidenceStore,
        projection: ReservationProjectionReader,
        account: str,
        instrument: str,
    ) -> None:
        self._rcl_log = rcl_log
        self._evidence_store = evidence_store
        self._projection = projection
        self._account = account
        self._instrument = instrument

    def _refused(
        self, reason: str, *, entry_reservation_id: str | None = None
    ) -> EntryCloseBound:
        return EntryCloseBound(
            account=self._account,
            instrument=self._instrument,
            entry_reservation_id=entry_reservation_id,
            entry_attempt_id=None,
            entry_quantity=None,
            prior_closed=None,
            rcl_writer_epoch=None,
            rcl_last_seq=None,
            refusal=reason,
        )

    def read(self) -> EntryCloseBound:
        """The scope's proven open-entry bound, or a typed refusal (module docstring)."""
        key = InstrumentKey(account=self._account, instrument=self._instrument)
        try:
            rows = self._projection.scope_reservations(key)
        except Exception:  # noqa: BLE001 - an unreadable projection proves nothing
            return self._refused(CloseBoundRefusal.SCOPE_READ_FAILED)
        outstanding = outstanding_reservations(rows)
        if (
            len(outstanding) != 1
            or outstanding[0].state is not CapacityState.POSITION_CONSUMED
        ):
            return self._refused(CloseBoundRefusal.ENTRY_NOT_SOLE_CONSUMED_POSITION)
        entry_reservation_id = outstanding[0].reservation_id
        try:
            history = durable_close_history(
                self._rcl_log,
                self._evidence_store,
                account=self._account,
                instrument=self._instrument,
                entry_reservation_id=entry_reservation_id,
            )
        except Exception:  # noqa: BLE001 - an unreadable history proves nothing
            return self._refused(
                CloseBoundRefusal.HISTORY_READ_FAILED,
                entry_reservation_id=entry_reservation_id,
            )
        if history.refusal is not None:
            return self._refused(
                history.refusal.value, entry_reservation_id=entry_reservation_id
            )
        if (
            history.entry_quantity is None
            or history.prior_quantity is None
            or history.rcl_writer_epoch is None
            or history.rcl_last_seq is None
        ):
            return self._refused(
                CloseBoundRefusal.HISTORY_INCOMPLETE,
                entry_reservation_id=entry_reservation_id,
            )
        return EntryCloseBound(
            account=self._account,
            instrument=self._instrument,
            entry_reservation_id=entry_reservation_id,
            entry_attempt_id=history.entry_attempt_id,
            entry_quantity=history.entry_quantity,
            prior_closed=history.prior_quantity,
            rcl_writer_epoch=history.rcl_writer_epoch,
            rcl_last_seq=history.rcl_last_seq,
            refusal=None,
        )


def synthetic_close_effect(
    bound: EntryCloseBound, proposed: Decimal | None
) -> tuple[Decimal | None, str]:
    """The risk credit a synthetic CLOSE of ``proposed`` earns, plus its audit status."""
    if not bound.proven:
        return None, CLOSE_BOUND_UNPROVEN
    bounded = close_within_entry(bound.entry_quantity, bound.prior_closed, proposed)
    if bounded is True and proposed is not None:
        return -proposed, CLOSE_BOUND_ACCEPTED
    if bounded is False:
        return None, CLOSE_BOUND_EXCEEDS_ENTRY
    return None, CLOSE_BOUND_QUANTITY_UNKNOWN


def synthetic_close_fence(
    request: StageRequest,
    *,
    bound: EntryCloseBound,
    current: EntryCloseBound,
    proposed: Decimal,
    granted_proposal_id: str,
) -> SyntheticCloseEntryFence | None:
    """Step 9's fence for a synthetic CLOSE, or ``None`` when the re-read does not bind."""
    proposal_id = getattr(request.proposal, "proposal_id", None)
    if (
        type(proposal_id) is not str
        or not proposal_id
        or type(granted_proposal_id) is not str
        or granted_proposal_id != proposal_id
    ):
        return None
    if not bound.revalidates(current):
        return None
    if (
        current.account != request.instrument_key.account
        or current.instrument != request.instrument_key.instrument
    ):
        return None
    reservation_id = current.entry_reservation_id
    entry_quantity = current.entry_quantity
    prior_closed = current.prior_closed
    writer_epoch = current.rcl_writer_epoch
    last_seq = current.rcl_last_seq
    if (
        type(reservation_id) is not str
        or type(entry_quantity) is not Decimal
        or type(prior_closed) is not Decimal
        or type(proposed) is not Decimal
        or type(writer_epoch) is not int
        or type(last_seq) is not int
    ):
        return None
    if close_within_entry(entry_quantity, prior_closed, proposed) is not True:
        return None
    return SyntheticCloseEntryFence(
        proposal_id=granted_proposal_id,
        account=current.account,
        instrument=current.instrument,
        entry_reservation_id=reservation_id,
        entry_quantity=entry_quantity,
        prior_closed=prior_closed,
        proposed_quantity=proposed,
        rcl_writer_epoch=writer_epoch,
        rcl_last_seq=last_seq,
    )
