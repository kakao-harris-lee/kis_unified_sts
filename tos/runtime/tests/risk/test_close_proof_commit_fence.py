"""Step-9 CLOSE proof freshness and RCL CAS fencing (#1004)."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl import DecisionContextCapsuleRef, Proposer, build_proposal
from tos.engine.records import InstrumentKey, StageRequest
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos.rcl import (
    AppendRefusal,
    CapacityComponent,
    CapacityReservationTransition,
    CapacityState,
    CapacityVector,
    CommandType,
    CommitEntry,
    ReservationScope,
    TransitionCause,
)
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.reservation_identity import reservation_id_in_scope
from tos_runtime.risk.flow import ActionFlowGovernor
from tos_runtime.risk.ledger_stages import (
    AtomicCommitStage,
    CloseProofCommitFence,
)

from .conftest import grant_shaped_afg_inputs

_ENVELOPE = CapacityVector(
    components=(CapacityComponent(dimension_id="notional", magnitude=Decimal("250")),)
)
_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def _request(key: InstrumentKey, *, effect: str) -> StageRequest:
    return StageRequest(
        step=CommitmentStep.ATOMIC_COMMIT,
        instrument_key=key,
        proposal=build_proposal(
            scheme=_SCHEME,
            proposer=Proposer(strategy_id="close-fence", strategy_version="v1"),
            account=key.account,
            instrument=key.instrument,
            direction="LONG",
            position_effect=effect,
            quantity_basis="SHARES:1",
            rationale="close proof fence test",
            decision_context_capsule=DecisionContextCapsuleRef(
                capsule_id="capsule-close-fence", canonical_digest="digest-close-fence"
            ),
            dsl_version="1.0",
            config_version="1.0",
        ),
    )


def _permit(governor: ActionFlowGovernor):
    decision = governor.decide(grant_shaped_afg_inputs())
    return governor.build_permit(
        decision, permit_generation=1, command_identity="cmd-close-fence"
    )


def _reservation_id(request: StageRequest, permit: Any) -> str | None:
    return reservation_id_in_scope(request.instrument_key, permit.permit_id)


def _fence(
    request: StageRequest,
    *,
    writer_epoch: int,
    last_seq: int,
    **overrides: Any,
) -> CloseProofCommitFence:
    fields: dict[str, Any] = {
        "proposal_id": request.proposal.proposal_id,
        "account": request.instrument_key.account,
        "instrument": request.instrument_key.instrument,
        "attempt_ids": (),
        "as_of_generation": last_seq,
        "observed_at_generation": last_seq,
        "trading_date": "20261029",
        "age_origin_ms": 500,
        "rcl_writer_epoch": writer_epoch,
        "rcl_last_seq": last_seq,
        "verified_rcl_writer_epoch": writer_epoch,
        "verified_rcl_last_seq": last_seq,
        "current_now_ms": 700,
        "current_trading_date": "20261029",
        "max_age_ms": 300,
    }
    fields.update(overrides)
    return CloseProofCommitFence(**fields)


class _ConcurrentWriterLog:
    """Advance the same-epoch log after step 9 reads the proof tip, before its CAS."""

    def __init__(self, log: SqliteCommitLog, *, writer_epoch: int) -> None:
        self._log = log
        self._writer_epoch = writer_epoch
        self._advanced = False
        self.expected_seq: int | None = None

    def read_linearizable(self, *, writer_epoch: int):
        return self._log.read_linearizable(writer_epoch=writer_epoch)

    def apply_reservation_transition(self, transition, cause, **kwargs):
        self.expected_seq = kwargs["expected_seq"]
        if not self._advanced:
            view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
            concurrent = CapacityReservationTransition(
                reservation_id="concurrent-same-epoch",
                writer_epoch=self._writer_epoch,
                from_state=CapacityState.COMMITTED_UNBOUND,
                to_state=CapacityState.COMMITTED_UNBOUND,
                scope=ReservationScope(
                    account="other-account", instrument="other-symbol"
                ),
                committed_vector=_ENVELOPE,
            )
            self._log.apply_reservation_transition(
                concurrent,
                cause=TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
                command_type=CommandType.COMMIT_RESERVATION,
                command_id="concurrent-writer-command",
                command_digest="concurrent-writer-digest",
                expected_seq=-1 if view.last_seq is None else view.last_seq,
            )
            self._advanced = True
        return self._log.apply_reservation_transition(transition, cause, **kwargs)


def _stage(
    log,
    *,
    writer_epoch: int,
    governor: ActionFlowGovernor,
    fence_reader=None,
    position_effect: str = "CLOSE",
) -> AtomicCommitStage:
    permit = _permit(governor)
    return AtomicCommitStage(
        log,
        writer_epoch=writer_epoch,
        permit_provider=lambda _request: permit,
        reservation_id_provider=_reservation_id,
        time_permits_new_risk=lambda: True,
        effect_envelope_reader=lambda: _ENVELOPE,
        position_effect_reader=lambda: position_effect,
        close_proof_fence_reader=fence_reader,
    )


def _append_approval_entry(
    log: SqliteCommitLog, *, writer_epoch: int, seq: int
) -> None:
    result = log.append_cas(
        CommitEntry(
            command_id=f"approval-consume-{seq}",
            command_digest=f"approval-digest-{seq}",
            kind=CommandType.CONSUME_APPROVAL_DECISION,
        ),
        expected_seq=seq - 1,
        writer_epoch=writer_epoch,
    )
    assert not isinstance(result, AppendRefusal)


def test_close_without_step9_proof_fence_fails_closed(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    stage = _stage(log, writer_epoch=writer_epoch, governor=afg_governor)

    verdict = stage(_request(instrument_key, effect="CLOSE"))

    assert verdict.outcome is StageOutcome.UNKNOWN
    assert log.read_linearizable(writer_epoch=writer_epoch).last_seq is None


def test_open_commit_does_not_require_a_close_proof_fence(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    stage = _stage(
        log,
        writer_epoch=writer_epoch,
        governor=afg_governor,
        position_effect="OPEN",
    )

    verdict = stage(_request(instrument_key, effect="OPEN"))

    assert verdict.outcome is StageOutcome.ADMIT, verdict.reason


def test_close_commit_admits_on_an_exact_current_proof_fence(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    _append_approval_entry(log, writer_epoch=writer_epoch, seq=0)
    request = _request(instrument_key, effect="CLOSE")
    stage = _stage(
        log,
        writer_epoch=writer_epoch,
        governor=afg_governor,
        fence_reader=lambda _request: _fence(
            request, writer_epoch=writer_epoch, last_seq=0
        ),
    )

    verdict = stage(request)

    assert verdict.outcome is StageOutcome.ADMIT, verdict.reason
    assert log.read_linearizable(writer_epoch=writer_epoch).last_seq == 1


def test_close_commit_refuses_a_missing_proof_origin_tip(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    _append_approval_entry(log, writer_epoch=writer_epoch, seq=0)
    request = _request(instrument_key, effect="CLOSE")
    missing_tip = replace(
        _fence(request, writer_epoch=writer_epoch, last_seq=0), rcl_last_seq=None
    )
    stage = _stage(
        log,
        writer_epoch=writer_epoch,
        governor=afg_governor,
        fence_reader=lambda _request: missing_tip,
    )

    verdict = stage(request)

    assert verdict.outcome is StageOutcome.UNKNOWN
    assert log.read_linearizable(writer_epoch=writer_epoch).last_seq == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"account": "other-account"},
        {"instrument": "other-symbol"},
        {"proposal_id": "other-proposal"},
        {"attempt_ids": ("other-proposal",)},
        {"as_of_generation": 2},
        {"observed_at_generation": 2},
        {"trading_date": "20261028"},
        {"current_trading_date": "20261028"},
        {"age_origin_ms": 0, "current_now_ms": 301},
        {"age_origin_ms": 701, "current_now_ms": 700},
        {"max_age_ms": 0},
        {"rcl_writer_epoch": 0},
        {"rcl_last_seq": 1},
        {"verified_rcl_writer_epoch": 0},
        {"verified_rcl_last_seq": 1},
        {"rcl_last_seq": 1, "verified_rcl_last_seq": 0},
    ],
)
def test_close_fence_mismatch_or_staleness_fails_closed(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
    overrides: dict[str, object],
) -> None:
    _append_approval_entry(log, writer_epoch=writer_epoch, seq=0)
    request = _request(instrument_key, effect="CLOSE")
    stage = _stage(
        log,
        writer_epoch=writer_epoch,
        governor=afg_governor,
        fence_reader=lambda _request: _fence(
            request, writer_epoch=writer_epoch, last_seq=0, **overrides
        ),
    )

    verdict = stage(request)

    assert verdict.outcome is StageOutcome.UNKNOWN
    assert log.read_linearizable(writer_epoch=writer_epoch).last_seq == 0


def test_close_cas_uses_proof_tip_and_refuses_a_later_same_epoch_writer(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    _append_approval_entry(log, writer_epoch=writer_epoch, seq=0)
    request = _request(instrument_key, effect="CLOSE")
    raced_log = _ConcurrentWriterLog(log, writer_epoch=writer_epoch)
    stage = _stage(
        raced_log,
        writer_epoch=writer_epoch,
        governor=afg_governor,
        fence_reader=lambda _request: _fence(
            request, writer_epoch=writer_epoch, last_seq=0
        ),
    )

    verdict = stage(request)

    assert raced_log.expected_seq == 0, verdict.reason
    assert verdict.outcome is StageOutcome.UNKNOWN, verdict.reason
    assert log.read_linearizable(writer_epoch=writer_epoch).last_seq == 1


def test_close_cas_uses_verified_tip_after_approval_only_gap(
    log: SqliteCommitLog,
    writer_epoch: int,
    instrument_key: InstrumentKey,
    afg_governor: ActionFlowGovernor,
) -> None:
    """The one allowed step-4 approval consumption advances proof tip 5 to CAS tip 6."""
    for seq in range(7):
        _append_approval_entry(log, writer_epoch=writer_epoch, seq=seq)
    assert log.read_linearizable(writer_epoch=writer_epoch).last_seq == 6

    request = _request(instrument_key, effect="CLOSE")
    stage = _stage(
        log,
        writer_epoch=writer_epoch,
        governor=afg_governor,
        fence_reader=lambda _request: _fence(
            request,
            writer_epoch=writer_epoch,
            last_seq=5,
            verified_rcl_last_seq=6,
        ),
    )

    verdict = stage(request)

    assert verdict.outcome is StageOutcome.ADMIT, verdict.reason
    assert log.read_linearizable(writer_epoch=writer_epoch).last_seq == 7
