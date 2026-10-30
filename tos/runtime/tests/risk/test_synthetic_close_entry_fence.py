"""Step 9's SYNTHETIC CLOSE branch — the dispatch and the races (#1011, review-1015 M1).

``test_close_proof_commit_fence.py`` covers the broker-held fence; this file covers the
``SyntheticCloseEntryFence`` branch :meth:`~tos_runtime.risk.ledger_stages.AtomicCommitStage
._expected_seq` takes BEFORE it, driving the real stage against a real
:class:`~tos_runtime.rcl.log.SqliteCommitLog`. Until this file existed, nothing drove step 9
with a synthetic fence at all: the only coverage was a direct call to the predicate.

The stage helpers come from the sibling broker-fence module (same package), so both branches
are exercised through the SAME stage construction and the same concurrent-writer double — a
difference in outcome is then a difference in the branch, not in the harness.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from tos.engine.records import InstrumentKey, StageRequest
from tos.engine.vocabulary import StageOutcome
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.risk.close_fence import SyntheticCloseEntryFence
from tos_runtime.risk.flow import ActionFlowGovernor

from .test_close_proof_commit_fence import (
    _append_approval_entry,
    _ConcurrentWriterLog,
    _request,
    _stage,
)


def _synthetic_fence(
    request: StageRequest,
    *,
    writer_epoch: int,
    last_seq: int,
    **overrides: Any,
) -> SyntheticCloseEntryFence:
    """A fence shaped exactly as ``RiskStateService._synthetic_close_fence`` mints one."""
    fields: dict[str, Any] = {
        "proposal_id": request.proposal.proposal_id,
        "account": request.instrument_key.account,
        "instrument": request.instrument_key.instrument,
        "entry_reservation_id": "resv-synthetic-entry",
        "entry_quantity": Decimal("2"),
        "prior_closed": Decimal("1"),
        "proposed_quantity": Decimal("1"),
        "rcl_writer_epoch": writer_epoch,
        "rcl_last_seq": last_seq,
    }
    fields.update(overrides)
    return SyntheticCloseEntryFence(**fields)


def test_synthetic_close_commits_at_the_fence_tip(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    """A current synthetic fence admits, and the CAS coordinate is the fence's own tip."""
    _append_approval_entry(log, writer_epoch=writer_epoch, seq=0)
    request = _request(instrument_key, effect="CLOSE")
    stage = _stage(
        log,
        writer_epoch=writer_epoch,
        governor=afg_governor,
        fence_reader=lambda _request: _synthetic_fence(
            request, writer_epoch=writer_epoch, last_seq=0
        ),
    )

    verdict = stage(request)

    assert verdict.outcome is StageOutcome.ADMIT, verdict.reason
    assert log.read_linearizable(writer_epoch=writer_epoch).last_seq == 1


def test_synthetic_close_refuses_when_the_tip_moved_after_the_fence_was_read(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    """Anything committed between the bound re-read and step 9's view refuses the commit.

    Concrete input: the fence names tip 0, the log is at tip 1 when step 9 reads it. The PR
    body claims a tip advance is tolerated only when the fence itself was re-read at the newer
    tip; this is the other half of that claim — a fence carrying the OLDER tip is refused, so a
    reservation that landed in between can never be closed over.
    """
    _append_approval_entry(log, writer_epoch=writer_epoch, seq=0)
    _append_approval_entry(log, writer_epoch=writer_epoch, seq=1)
    request = _request(instrument_key, effect="CLOSE")
    stage = _stage(
        log,
        writer_epoch=writer_epoch,
        governor=afg_governor,
        fence_reader=lambda _request: _synthetic_fence(
            request, writer_epoch=writer_epoch, last_seq=0
        ),
    )

    verdict = stage(request)

    assert verdict.outcome is StageOutcome.UNKNOWN, verdict.reason
    assert "another RCL revision" in (verdict.reason or "")
    assert log.read_linearizable(writer_epoch=writer_epoch).last_seq == 1


def test_synthetic_close_cas_refuses_a_later_same_epoch_writer(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    """A commit that lands AFTER step 9's view loses the CAS rather than overwriting it.

    The fence's tip is the CAS coordinate, so a same-epoch writer that slips in between the
    view and the append yields ``SEQ_MISMATCH`` → UNKNOWN. Same double, same assertion shape
    as the broker fence's own race test.
    """
    _append_approval_entry(log, writer_epoch=writer_epoch, seq=0)
    request = _request(instrument_key, effect="CLOSE")
    raced_log = _ConcurrentWriterLog(log, writer_epoch=writer_epoch)
    stage = _stage(
        raced_log,
        writer_epoch=writer_epoch,
        governor=afg_governor,
        fence_reader=lambda _request: _synthetic_fence(
            request, writer_epoch=writer_epoch, last_seq=0
        ),
    )

    verdict = stage(request)

    assert raced_log.expected_seq == 0, verdict.reason
    assert verdict.outcome is StageOutcome.UNKNOWN, verdict.reason
    assert log.read_linearizable(writer_epoch=writer_epoch).last_seq == 1


@pytest.mark.parametrize(
    ("overrides", "why"),
    [
        ({"rcl_writer_epoch": 0}, "a different writer epoch"),
        ({"proposal_id": "other-proposal"}, "another proposal's bound"),
        ({"account": "other-account"}, "another account's bound"),
        ({"instrument": "other-symbol"}, "another instrument's bound"),
        ({"entry_reservation_id": ""}, "no entry reservation named"),
        ({"prior_closed": Decimal("2")}, "closes already fill the entry"),
        ({"proposed_quantity": Decimal("2")}, "the quantity exceeds the entry"),
        ({"proposed_quantity": Decimal("0")}, "a zero-quantity close"),
        ({"rcl_last_seq": 1}, "a tip the view does not hold"),
    ],
)
def test_synthetic_close_fence_mismatch_fails_closed(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
    overrides: dict[str, Any],
    why: str,
) -> None:
    """Each clause of the synthetic fence check, one concrete failing fence at a time."""
    _append_approval_entry(log, writer_epoch=writer_epoch, seq=0)
    request = _request(instrument_key, effect="CLOSE")
    stage = _stage(
        log,
        writer_epoch=writer_epoch,
        governor=afg_governor,
        fence_reader=lambda _request: _synthetic_fence(
            request, writer_epoch=writer_epoch, last_seq=0, **overrides
        ),
    )

    verdict = stage(request)

    assert verdict.outcome is StageOutcome.UNKNOWN, (why, verdict.reason)
    assert log.read_linearizable(writer_epoch=writer_epoch).last_seq == 0


def test_a_synthetic_fence_never_satisfies_the_broker_branch(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    """The two fence records are dispatched by exact type, not by duck typing.

    A ``SyntheticCloseEntryFence`` carries none of the broker fence's currentness fields, so if
    step 9 ever fell through to the broker branch with one, the attribute reads would be the
    only thing standing between it and a commit. This pins the branch instead: an object that
    is neither exact type is UNKNOWN, with the broker branch's own wording.
    """
    _append_approval_entry(log, writer_epoch=writer_epoch, seq=0)
    request = _request(instrument_key, effect="CLOSE")
    stage = _stage(
        log,
        writer_epoch=writer_epoch,
        governor=afg_governor,
        fence_reader=lambda _request: ("not", "a", "fence"),
    )

    verdict = stage(request)

    assert verdict.outcome is StageOutcome.UNKNOWN
    assert "missing or has an invalid type" in (verdict.reason or "")
    assert log.read_linearizable(writer_epoch=writer_epoch).last_seq == 0
