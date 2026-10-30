"""The step-6 CLOSE fences step 9 rebinds before it commits, and their pure checks.

Extracted from :mod:`tos_runtime.risk.ledger_stages` to keep that module under the repo's
1000-line module size budget (``tools/tos_size_budget.py``) — the same pure decomposition
discipline :mod:`tos_runtime.posttrade.entry_discharge` was split out of ``release_consumer.py``
under. Nothing here judges, writes, or reads a store: every function is a predicate over an
already-built record, so each refusal is directly testable against a concrete input with no
stage and no log (:func:`~tos_runtime.risk.ledger_stages.verdict_for_scope`'s own convention).

**Two fences, never one widened to cover both.** Which one a boot produces is decided once, at
the composition root, from the transport kind:

* :class:`CloseProofCommitFence` — a KIS boot's broker-held position proof, whose currentness
  is a reading age against a trusted clock and a trading date (#1004);
* :class:`SyntheticCloseEntryFence` — a ``SYNTHETIC_FUTURES_ORDER`` boot's durable entry bound,
  whose currentness is an exact RCL revision, because the evidence store IS that boot's broker
  and it has no clock-aged broker reading to carry (#1011).

The stage dispatches on the record's exact type, so neither set of checks is ever relaxed to
accommodate the other.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.engine.records``
+ ``tos.rcl`` + ``tos_runtime.risk.close_quantity`` only. No ``shared.*``, no store handle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from tos.engine.records import StageRequest
from tos.rcl import LogView

from tos_runtime.risk.close_quantity import close_within_entry

__all__ = [
    "CloseProofCommitFence",
    "SyntheticCloseEntryFence",
    "close_proof_fence_matches_request",
    "close_proof_fence_matches_view",
    "synthetic_close_fence_valid",
    "valid_close_proof_date",
]

_CLOSE_PROOF_DATE = re.compile(r"[0-9]{8}")


@dataclass(frozen=True)
class CloseProofCommitFence:
    """The step-6 CLOSE proof facts step 9 must bind and revalidate before commit.

    The composition root builds this from the exact consumed held-position proof and the same
    trusted clock/configuration used to validate that proof. Keeping this runtime-only record
    local to the stage package avoids introducing a kernel type or import edge.
    """

    proposal_id: str
    account: str
    instrument: str
    attempt_ids: tuple[str, ...]
    as_of_generation: int
    observed_at_generation: int
    trading_date: str
    age_origin_ms: int
    rcl_writer_epoch: int
    rcl_last_seq: int | None
    verified_rcl_writer_epoch: int
    verified_rcl_last_seq: int | None
    current_now_ms: int
    current_trading_date: str | None
    max_age_ms: int


@dataclass(frozen=True)
class SyntheticCloseEntryFence:
    """The step-6 synthetic CLOSE bound facts step 9 must rebind before commit (#1011).

    A ``SYNTHETIC_FUTURES_ORDER`` boot has no broker to hold a position, so there is no
    held-position proof to carry and :class:`CloseProofCommitFence`'s broker-reading currentness
    fields (trading date, reading age) have nothing behind them. What IS current for that
    transport is the durable pair this record carries: the entry's proven FULL_FILL quantity and
    the proven prior closes attached to it, read at an exact RCL ``(writer_epoch, last_seq)``.
    The risk-state service derives these at step 6 and re-derives them independently before
    handing this over, so step 9's own check below is the second reading of the same facts —
    the same two-reading shape the broker-held path takes.
    """

    proposal_id: str
    account: str
    instrument: str
    entry_reservation_id: str
    entry_quantity: Decimal
    prior_closed: Decimal
    proposed_quantity: Decimal
    rcl_writer_epoch: int
    rcl_last_seq: int


def valid_close_proof_date(value: object) -> bool:
    """Accept only a real Gregorian ``YYYYMMDD`` trading date."""
    if not isinstance(value, str) or _CLOSE_PROOF_DATE.fullmatch(value) is None:
        return False
    try:
        return datetime.strptime(value, "%Y%m%d").strftime("%Y%m%d") == value
    except ValueError:
        return False


def close_proof_fence_matches_request(
    fence: CloseProofCommitFence, request: StageRequest
) -> bool:
    """Validate the consumed step-6 proof's exact scope and currentness fields."""
    proposal_id = getattr(request.proposal, "proposal_id", None)
    if (
        type(proposal_id) is not str
        or not proposal_id
        or type(fence.proposal_id) is not str
        or fence.proposal_id != proposal_id
        or type(fence.account) is not str
        or fence.account != request.instrument_key.account
        or type(fence.instrument) is not str
        or fence.instrument != request.instrument_key.instrument
        or type(fence.attempt_ids) is not tuple
        or fence.attempt_ids != ()
    ):
        return False
    if (
        type(fence.as_of_generation) is not int
        or fence.as_of_generation < 0
        or type(fence.observed_at_generation) is not int
        or fence.observed_at_generation != fence.as_of_generation
        or type(fence.rcl_last_seq) is not int
        or fence.rcl_last_seq < 0
        or fence.as_of_generation != fence.rcl_last_seq
    ):
        return False
    if (
        not valid_close_proof_date(fence.trading_date)
        or not valid_close_proof_date(fence.current_trading_date)
        or fence.current_trading_date != fence.trading_date
    ):
        return False
    if (
        type(fence.age_origin_ms) is not int
        or fence.age_origin_ms < 0
        or type(fence.current_now_ms) is not int
        or fence.current_now_ms < fence.age_origin_ms
        or type(fence.max_age_ms) is not int
        or fence.max_age_ms <= 0
        or fence.current_now_ms - fence.age_origin_ms > fence.max_age_ms
    ):
        return False
    return not (
        type(fence.rcl_writer_epoch) is not int
        or fence.rcl_writer_epoch < 0
        or type(fence.verified_rcl_writer_epoch) is not int
        or fence.verified_rcl_writer_epoch != fence.rcl_writer_epoch
        or type(fence.verified_rcl_last_seq) is not int
        or fence.verified_rcl_last_seq < fence.rcl_last_seq
    )


def close_proof_fence_matches_view(
    fence: CloseProofCommitFence, *, writer_epoch: int, view: LogView
) -> bool:
    """Require both the proof's RCL epoch and tip to match step 9's linearizable read."""
    return (
        fence.rcl_writer_epoch == writer_epoch
        and fence.verified_rcl_writer_epoch == writer_epoch
        and view.epoch == fence.verified_rcl_writer_epoch
        and view.last_seq == fence.verified_rcl_last_seq
    )


def synthetic_close_fence_valid(
    fence: SyntheticCloseEntryFence,
    request: StageRequest,
    *,
    writer_epoch: int,
    view: LogView,
) -> bool:
    """Whether a synthetic CLOSE bound still binds this exact proposal, scope and RCL revision.

    Every clause is required — identity, arithmetic, and revision:

    * the fence names THIS proposal and THIS ``(account, instrument)`` scope;
    * the quantities are concrete, positive and still fit
      (:func:`~tos_runtime.risk.close_quantity.close_within_entry`), so a bound derived against
      a different entry can never authorize this close;
    * the RCL revision it was read at is the one step 9 is committing against — same writer
      epoch, same tip. A same-epoch writer that commits between step 6 and here therefore moves
      the tip and this refuses, rather than closing against a stale entry history.
    """
    proposal_id = getattr(request.proposal, "proposal_id", None)
    if (
        type(proposal_id) is not str
        or not proposal_id
        or type(fence.proposal_id) is not str
        or fence.proposal_id != proposal_id
        or type(fence.account) is not str
        or fence.account != request.instrument_key.account
        or type(fence.instrument) is not str
        or fence.instrument != request.instrument_key.instrument
        or type(fence.entry_reservation_id) is not str
        or not fence.entry_reservation_id
    ):
        return False
    quantities = (fence.entry_quantity, fence.prior_closed, fence.proposed_quantity)
    if any(type(value) is not Decimal for value in quantities):
        return False
    if (
        fence.proposed_quantity <= 0
        or close_within_entry(
            fence.entry_quantity, fence.prior_closed, fence.proposed_quantity
        )
        is not True
    ):
        return False
    return not (
        type(fence.rcl_writer_epoch) is not int
        or fence.rcl_writer_epoch != writer_epoch
        or type(fence.rcl_last_seq) is not int
        or fence.rcl_last_seq < 0
        or view.epoch != fence.rcl_writer_epoch
        or view.last_seq != fence.rcl_last_seq
    )
