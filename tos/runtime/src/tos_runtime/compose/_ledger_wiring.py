"""Ledger verification, atomic commit and unavailability stage wiring.

These steps were split from ``compose._wiring`` for the module size budget.
The composition root passes scenario-specific readers through unchanged;
in particular, the close-proof fence reader stays bound to step 9.
"""

from __future__ import annotations

from collections.abc import Callable

from tos.egressgw import EconomicEffectStage, OrderConstructionStage
from tos.engine import StageRequest

from tos_runtime.compose._attempt_arm import attempt_position_effect
from tos_runtime.compose.context import (
    RecordingActionFlowGovernor,
    VerdictRecorder,
    make_permit_provider,
)
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.rcl.reservation_identity import reservation_id_in_scope
from tos_runtime.risk.ledger_stages import (
    AtomicCommitStage,
    CloseProofCommitFence,
    CommitmentUnavailabilityStage,
    LedgerVerificationStage,
    SyntheticCloseEntryFence,
)


def _build_ledger_stages(
    *,
    rcl_log: SqliteCommitLog,
    projection: SqliteReservationProjectionReader,
    writer_epoch: int,
    flow_governor: RecordingActionFlowGovernor,
    construction_stage: OrderConstructionStage,
    economic_stage: EconomicEffectStage,
    generation_provider: Callable[[StageRequest], int],
    time_gate: Callable[[], bool],
    close_proof_fence_reader: Callable[
        [StageRequest], CloseProofCommitFence | SyntheticCloseEntryFence | None
    ],
) -> tuple[LedgerVerificationStage, VerdictRecorder, CommitmentUnavailabilityStage]:
    """Wire steps 8 (Ledger Verification), 9 (Atomic Commit) and 10
    (Commitment Unavailability).

    The three share the #966 reservation identity: step 9 mints the id from
    the permit it binds, and steps 8/10 read the same scope/row back — see
    :mod:`tos_runtime.rcl.reservation_identity`.
    """
    step8_stage = LedgerVerificationStage(
        rcl_log,
        projection,
        writer_epoch=writer_epoch,
        # #966: admission depends on whether this attempt opens or closes a position (the
        # stage's own docstring table), read off the arm step 2 selected.
        position_effect_reader=lambda: attempt_position_effect(construction_stage),
    )
    step9_recorder = VerdictRecorder(
        AtomicCommitStage(
            rcl_log,
            writer_epoch=writer_epoch,
            permit_provider=make_permit_provider(
                flow_governor,
                permit_generation_provider=generation_provider,
                command_identity_provider=lambda request: (
                    request.proposal.canonical_digest or ""
                ),
            ),
            reservation_id_provider=lambda request, permit: reservation_id_in_scope(
                request.instrument_key, permit.permit_id
            ),
            time_permits_new_risk=time_gate,
            effect_envelope_reader=lambda: economic_stage.envelope,
            position_effect_reader=lambda: attempt_position_effect(construction_stage),
            close_proof_fence_reader=close_proof_fence_reader,
        )
    )
    return step8_stage, step9_recorder, CommitmentUnavailabilityStage(projection)
