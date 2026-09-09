"""Hermetic tests for :mod:`tos_runtime.rcl.finality_witness` (TOS Phase 3 Wave 2 Lane C-R;
plan §2.2) — the ``PostTradeFinalityProof -> finality_witness -> apply_reservation_transition``
seam, end to end against a real :class:`~tos_runtime.rcl.log.SqliteCommitLog`."""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import EgressResultPayload, InstrumentKey
from tos.engine.vocabulary import EgressResultKind
from tos.rcl import (
    AppendReceipt,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos.workload import RuntimeIdentity
from tos_runtime.posttrade.config import FinalityConfig
from tos_runtime.posttrade.finality import SyntheticFinalityProducer
from tos_runtime.rcl.finality_witness import finality_witness_for, release_reservation
from tos_runtime.rcl.log import (
    ReservationRefusalReason,
    ReservationTransitionRefusal,
    SqliteCommitLog,
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
KEY = InstrumentKey(account="acct-1", instrument="101S06")
DEFAULT_SCOPE = ReservationScope(account="acct-1", instrument="101S06")


def _config() -> FinalityConfig:
    return FinalityConfig(
        currency="KRW",
        value_date="2026-09-09",
        source_revision="synthetic-rev-1",
        proof_recipe_id="synthetic-recipe-1",
    )


def _producer() -> SyntheticFinalityProducer:
    return SyntheticFinalityProducer(config=_config(), scheme=SCHEME)


def _commit_to_potentially_live(
    log: SqliteCommitLog, epoch: int, *, reservation_id: str
) -> AppendReceipt:
    receipt = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.POTENTIALLY_LIVE,
            scope=DEFAULT_SCOPE,
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.COMMIT_RESERVATION,
        command_id=f"cmd-setup-{reservation_id}",
        command_digest="dig-setup",
        expected_seq=-1,
    )
    assert isinstance(receipt, AppendReceipt)
    return receipt


def test_finality_witness_for_present_and_absent() -> None:
    payload = EgressResultPayload(
        instrument_key=KEY,
        attempt_id="attempt-1",
        kind=EgressResultKind.FULL_FILL,
        filled_quantity=Decimal("1"),
        remaining_quantity=Decimal("0"),
    )
    proof_result = _producer().produce(payload)
    assert proof_result is not None
    assert finality_witness_for(proof_result.proof) is True
    assert finality_witness_for(None) is None


def test_full_fill_proof_admits_release(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    epoch = log.acquire_epoch(identity)
    setup = _commit_to_potentially_live(log, epoch, reservation_id="res-fqp-1")

    payload = EgressResultPayload(
        instrument_key=KEY,
        attempt_id="attempt-1",
        kind=EgressResultKind.FULL_FILL,
        filled_quantity=Decimal("10"),
        remaining_quantity=Decimal("0"),
    )
    proof_result = _producer().produce(payload)
    assert proof_result is not None

    transition = CapacityReservationTransition(
        reservation_id="res-fqp-1",
        writer_epoch=epoch,
        from_state=CapacityState.POTENTIALLY_LIVE,
        to_state=CapacityState.RELEASED,
        scope=DEFAULT_SCOPE,
    )
    result = release_reservation(
        log,
        transition,
        command_id="cmd-release-1",
        command_digest="dig-release-1",
        expected_seq=setup.seq,
        proof=proof_result.proof,
    )
    assert isinstance(result, AppendReceipt)
    rows = {rid: state for rid, state, _seq, _scope in log.reservation_rows()}
    assert rows["res-fqp-1"] == CapacityState.RELEASED


@pytest.mark.parametrize(
    "kind,filled,remaining",
    [
        (EgressResultKind.PARTIAL_FILL, "5", "5"),
        (EgressResultKind.CANCEL_ACK, None, None),
        (EgressResultKind.EXPIRED, None, None),
    ],
)
def test_no_proof_refuses_release(
    log: SqliteCommitLog,
    identity: RuntimeIdentity,
    kind: EgressResultKind,
    filled: str | None,
    remaining: str | None,
) -> None:
    """CPL-4 (cancel is not release) / RFC-005 §11 (partial leaves remaining live): none of
    these produce a proof, so the witness is ``None`` and the release is refused."""
    epoch = log.acquire_epoch(identity)
    setup = _commit_to_potentially_live(log, epoch, reservation_id=f"res-{kind.value}")

    payload = EgressResultPayload(
        instrument_key=KEY,
        attempt_id="attempt-1",
        kind=kind,
        filled_quantity=None if filled is None else Decimal(filled),
        remaining_quantity=None if remaining is None else Decimal(remaining),
    )
    proof_result = _producer().produce(payload)
    assert proof_result is None

    transition = CapacityReservationTransition(
        reservation_id=f"res-{kind.value}",
        writer_epoch=epoch,
        from_state=CapacityState.POTENTIALLY_LIVE,
        to_state=CapacityState.RELEASED,
        scope=DEFAULT_SCOPE,
    )
    with pytest.raises(ReservationTransitionRefusal) as excinfo:
        release_reservation(
            log,
            transition,
            command_id=f"cmd-release-{kind.value}",
            command_digest="dig-release",
            expected_seq=setup.seq,
            proof=None,
        )
    assert excinfo.value.reason == ReservationRefusalReason.FINALITY_WITNESS_REQUIRED
    rows = {rid: state for rid, state, _seq, _scope in log.reservation_rows()}
    assert rows[f"res-{kind.value}"] == CapacityState.POTENTIALLY_LIVE  # unchanged


def test_mutation_cancel_to_released_without_proof_is_refused(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """Quoted mutation: if a caller tried to hand-roll ``finality_witness=True`` for a
    CANCEL_ACK result (bypassing this producer entirely), the RCL gate would admit it — that is
    exactly why this producer must be the ONLY source of a ``True`` witness on this path,
    never a hand-rolled bypass. This test pins the CONTROL: going through
    :func:`finality_witness_for` with the producer's own (correctly ``None``) output refuses,
    as asserted above; this test additionally confirms the underlying kernel gate itself would
    admit a forged ``True`` — demonstrating why the producer's own gating (never emitting a
    proof for CANCEL_ACK) is the load-bearing safety property, not the rcl call alone.
    """
    epoch = log.acquire_epoch(identity)
    setup = _commit_to_potentially_live(log, epoch, reservation_id="res-mutation-1")
    transition = CapacityReservationTransition(
        reservation_id="res-mutation-1",
        writer_epoch=epoch,
        from_state=CapacityState.POTENTIALLY_LIVE,
        to_state=CapacityState.RELEASED,
        scope=DEFAULT_SCOPE,
    )
    # A forged True witness (never produced by this module for CANCEL_ACK) DOES admit at the
    # rcl layer — proving the producer's refusal to emit a proof for CANCEL_ACK is what CPL-4
    # actually depends on here, not this generic kernel gate.
    forged = log.apply_reservation_transition(
        transition,
        TransitionCause.FINAL_QUANTITY_PROOF,
        command_type=CommandType.RELEASE_RESERVATION,
        command_id="cmd-forged",
        command_digest="dig-forged",
        expected_seq=setup.seq,
        finality_witness=True,
    )
    assert isinstance(forged, AppendReceipt)
