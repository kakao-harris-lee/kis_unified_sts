"""The durable CLOSE quantity bound of this scope's open entry (#1011, #1012 L3).

**Why this exists.** A CLOSE may reduce aggregate risk only up to a quantity something
independent proves is actually held. On a KIS stock boot that something is the broker: the
held-position proof :mod:`tos_runtime.riskstate.held_position` issues. A
``SYNTHETIC_FUTURES_ORDER`` boot has no broker to ask — ``cp3-setup-d-long``,
``cp3-setup-d-short`` and ``paper`` carry no ``fill_observer.yaml``, so that reader is ``None``
and every CLOSE answered ``PROVIDER_NOT_CONFIGURED``. Step 6 then stayed ``UNKNOWN`` forever:
once a synthetic entry reached ``POSITION_CONSUMED`` no CLOSE could pass, step 8 refused every
OPEN over that outstanding row, and the scope was sealed until the contract month rolled.

**What is independent on a synthetic transport.** The evidence store IS the broker there — the
fills it records are the only execution that ever happened. So the honest bound is the one the
post-trade side already proves for discharge: the entry's own terminal FULL_FILL quantity, less
the closes already proven against it (:func:`~tos_runtime.posttrade.close_history
.durable_close_history`), compared through the shared
:func:`~tos_runtime.risk.close_quantity.close_within_entry`. No new proof surface, no second
spelling of the arithmetic.

**Fail-closed, every clause.** The scope must hold EXACTLY ONE outstanding reservation and it
must be at ``POSITION_CONSUMED`` — the same shape step 8 admits a CLOSE over — so a competing
outstanding CLOSE, a mid-flight row, or no entry at all refuses here rather than picking one.
Any close-history refusal (an unproven entry fill, an unproven or ambiguous prior close, an
unreadable RCL snapshot) is returned as a reason and leaves every quantity ``None``, which the
risk-state service reads as UNKNOWN. Nothing here ever returns a quantity it could not prove,
and nothing here writes.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.engine.records`` /
``tos.rcl`` + ``tos_runtime.{evidence.store, posttrade.close_history, rcl.*, risk.*}`` only. No
``shared.*``, no write call of any kind.
"""

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

#: ``_close_effect_audit``'s ``proof_status`` for a CLOSE the durable bound admits — the SAME
#: spelling the broker-held path uses, because both mean "this exact quantity was proven".
CLOSE_BOUND_ACCEPTED = "PROOF_ACCEPTED"
#: The proposed quantity is concrete but does not fit the proven entry remainder.
CLOSE_BOUND_EXCEEDS_ENTRY = "QUANTITY_EXCEEDS_ENTRY"
#: The bound is proven but the proposed quantity is not (step 2 derived none).
CLOSE_BOUND_QUANTITY_UNKNOWN = "QUANTITY_UNKNOWN"
#: The durable entry bound itself could not be established; the reason is in the audit row.
CLOSE_BOUND_UNPROVEN = "ENTRY_BOUND_UNPROVEN"


class CloseAuthoritySource(StrEnum):
    """What a boot's CLOSE quantity bound is allowed to rest on.

    Selected once, at the composition root, from the boot's transport kind — never from a tree
    name. A ``kis-mock`` boot reaches a real broker, so the holding it reports bounds the close
    (and, since #1012 L3, the TOS entry remainder bounds it further — shares held outside TOS
    are not TOS capacity). A ``synthetic`` boot reaches nothing, so its own durable evidence is
    the only honest source.
    """

    #: KIS stock: a fresh, complete, independent, per-attempt broker holding proof, capped by
    #: what remains of the TOS entry.
    BROKER_HELD_PROOF = "BROKER_HELD_PROOF"
    #: Synthetic transport: the durable entry fill less its proven closes, and nothing else.
    DURABLE_EVIDENCE = "DURABLE_EVIDENCE"


class CloseBoundRefusal(StrEnum):
    """This module's own reasons a bound could not be read (close-history reasons pass
    through under their own :class:`~tos_runtime.posttrade.close_history.CloseHistoryRefusal`
    spelling, so an audit row never loses which layer refused)."""

    #: The reservation projection could not be read at all.
    SCOPE_READ_FAILED = "SCOPE_READ_FAILED"
    #: The scope does not hold exactly one outstanding ``POSITION_CONSUMED`` entry.
    ENTRY_NOT_SOLE_CONSUMED_POSITION = "ENTRY_NOT_SOLE_CONSUMED_POSITION"
    #: The durable close history raised rather than returning a typed refusal.
    HISTORY_READ_FAILED = "HISTORY_READ_FAILED"
    #: The history reported no refusal but left a required quantity or RCL coordinate absent.
    HISTORY_INCOMPLETE = "HISTORY_INCOMPLETE"
    #: No bound reader was wired into the risk-state service at all.
    READER_NOT_CONFIGURED = "READER_NOT_CONFIGURED"
    #: The wired reader raised, or returned something that is not an :class:`EntryCloseBound`.
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
        """Whether ``current`` is a second reading of the SAME entry, at a tip no older.

        The synthetic counterpart of
        :meth:`~tos_runtime.riskstate.held_position.HeldPositionCell.validate_consumed`: the
        identity and the magnitudes must be byte-identical, and the re-read must come from the
        same writer epoch at a sequence at or after the one step 6 read. The re-read's tip is
        what the fence then carries, so an advance between step 6 and step 9 is tolerated
        exactly as the broker-held path tolerates it — and step 9 still pins the commit to that
        re-read tip.
        """
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
    """Reads one scope's open-entry bound off the RCL projection + durable close history.

    Holds no state of its own: every :meth:`read` is a fresh reservation-projection read and a
    fresh fenced close-history snapshot, so two reads of the same attempt genuinely observe the
    store twice (what :meth:`EntryCloseBound.revalidates` depends on).
    """

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
        """The scope's proven open-entry bound, or a typed refusal (module docstring).

        **A partially-filled entry has no bound here, and that is permanent** (review-1015 L2):
        :func:`~tos_runtime.posttrade.close_history.durable_close_history` proves an entry only
        through a TERMINAL ``FULL_FILL`` receipt, so an entry left at ``PARTIAL_FILL`` refuses
        with ``ENTRY_FILL_UNPROVEN`` and every CLOSE of that scope stays UNKNOWN for as long as
        the row lives. Nothing produces that shape today — the synthetic fill policy fills 100%
        — and the same receipt is what #966's discharge already requires, so relaxing it here
        alone would let a close be credited against a quantity discharge cannot account for.
        If a partial synthetic fill ever becomes reachable, this is the refusal to revisit.
        """
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
    """The risk credit a synthetic CLOSE of ``proposed`` earns, plus its audit status.

    Returns ``(None, reason)`` for every case the bound does not positively admit — an
    unproven bound, an absent proposed quantity, or one that does not fit the remainder — so
    the caller's ``max_credible_command_effect`` stays ``None`` and step 6 answers UNKNOWN.
    """
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
    """Step 9's fence for a synthetic CLOSE, or ``None`` when the re-read does not bind.

    ``bound`` is what step 6 granted against; ``current`` is the independent re-read taken as
    the fence is minted. Both must name the same entry with the same magnitudes
    (:meth:`EntryCloseBound.revalidates`), and the fence carries the RE-READ's RCL coordinate —
    which step 9 then requires to equal its own linearizable view.

    ``granted_proposal_id`` is the id STEP 6 derived this credit for. It must equal the step-9
    request's own, and it — not the request's — is what the fence carries, mirroring the broker
    path's ``proof.proposal_id`` (review-1015 L1). Minting the fence from the request's id would
    make :func:`~tos_runtime.risk.close_fence.synthetic_close_fence_valid` compare a value with
    itself.
    """
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
