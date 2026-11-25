"""Integrity regressions for durable close-history joins and receipts."""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.rcl import (
    AppendRefusal,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade import entry_recovery as entry_recovery_module
from tos_runtime.posttrade.close_history import (
    CloseHistoryRefusal,
    durable_close_history,
)
from tos_runtime.posttrade.entry_discharge import entry_release_command_id
from tos_runtime.rcl.reservation_lookup import attempt_id_for_reservation

from . import test_release_consumer as cycle
from .conftest import Rig


def test_foreign_scope_receipt_for_same_attempt_refuses_close_history(
    rig: Rig,
) -> None:
    payload = cycle._arrange_close(
        rig,
        close_filled=Decimal("4"),
        close_remaining=Decimal("0"),
    )
    consumer = cycle._cycle_consumer(
        rig,
        witness=cycle._CycleWitness(
            positions=((cycle._INSTRUMENT, Decimal("6")),),
            close_quantity=Decimal("4"),
        ),
    )
    consumer.consume(payload)

    entry_reservation_id = cycle._entry_reservation_id()
    original = durable_close_history(
        rig.rcl_log,
        rig.evidence_store,
        account=cycle._ACCOUNT,
        instrument=cycle._INSTRUMENT,
        entry_reservation_id=entry_reservation_id,
    )
    assert original.proven
    assert original.prior_quantity == Decimal("4")

    rig.evidence_store.append(
        {
            "attempt_id": cycle._CLOSE_ATTEMPT,
            "instrument_key": {"account": "other-account", "instrument": "OTHER"},
            "egress_result_kind": "FULL_FILL",
            "filled_quantity": "99",
            "remaining_quantity": "0",
            "broker_execution_id": "foreign-exec",
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )
    conflicted = durable_close_history(
        rig.rcl_log,
        rig.evidence_store,
        account=cycle._ACCOUNT,
        instrument=cycle._INSTRUMENT,
        entry_reservation_id=entry_reservation_id,
    )
    assert conflicted.refusal is CloseHistoryRefusal.FILL_UNPROVEN
    assert conflicted.prior_quantity is None


def test_inverse_reservation_join_requires_unambiguous_forward_permit(
    evidence_store: SqliteEvidenceStore,
) -> None:
    cycle._record_join(
        evidence_store,
        attempt_id=cycle._ENTRY_ATTEMPT,
        permit_identity=cycle._ENTRY_PERMIT,
    )
    evidence_store.append(
        {
            "kind": "FLOW_STEP_ADMITTED",
            "step": "ATOMIC_COMMIT",
            "event_id": f"evt-{cycle._ENTRY_ATTEMPT}",
            "bound_identity": "another-permit",
        },
        kind="FLOW_STEP_ADMITTED",
        record_class="FLOW_STEP_ADMITTED",
    )

    assert (
        attempt_id_for_reservation(evidence_store, cycle._ENTRY_PERMIT)
        == cycle._ENTRY_ATTEMPT
    )
    from tos_runtime.posttrade.close_history import _attempt_for_reservation

    assert (
        _attempt_for_reservation(
            evidence_store,
            reservation_id=cycle._entry_reservation_id(),
            account=cycle._ACCOUNT,
            instrument=cycle._INSTRUMENT,
        )
        is None
    )


def test_concurrent_rcl_commit_after_history_snapshot_holds_entry_release(
    rig: Rig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = cycle._arrange_close(
        rig,
        close_filled=cycle._ENTRY_QTY,
        close_remaining=Decimal("0"),
    )
    original_reader = entry_recovery_module.durable_close_history

    def reconstruct_then_commit(*args, **kwargs):
        history = original_reader(*args, **kwargs)
        assert history.proven
        assert history.rcl_writer_epoch is not None
        assert history.rcl_last_seq is not None
        epoch = history.rcl_writer_epoch
        view = rig.rcl_log.read_linearizable(writer_epoch=epoch)
        assert view.last_seq == history.rcl_last_seq
        concurrent = rig.rcl_log.apply_reservation_transition(
            CapacityReservationTransition(
                reservation_id="resv-concurrent-scope-OTHER-close-history-test",
                writer_epoch=epoch,
                from_state=CapacityState.COMMITTED_UNBOUND,
                to_state=CapacityState.COMMITTED_UNBOUND,
                scope=ReservationScope(account="concurrent-scope", instrument="OTHER"),
            ),
            TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
            command_type=CommandType.COMMIT_RESERVATION,
            command_id="cmd-concurrent-after-close-history",
            command_digest="concurrent-close-history-test",
            expected_seq=history.rcl_last_seq,
        )
        assert not isinstance(concurrent, AppendRefusal)
        return history

    monkeypatch.setattr(
        entry_recovery_module,
        "durable_close_history",
        reconstruct_then_commit,
    )
    consumer = cycle._cycle_consumer(
        rig,
        witness=cycle._CycleWitness(),
    )

    consumer.consume(payload)

    entry_reservation_id = cycle._entry_reservation_id()
    projection = cycle.SqliteReservationProjectionReader(rig.rcl_log)
    assert (
        projection.reservation_state(entry_reservation_id)
        is CapacityState.POSITION_CONSUMED
    )
    assert not rig.rcl_log.command_committed(
        entry_release_command_id(cycle._CLOSE_ATTEMPT)
    )
