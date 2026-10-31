"""Crash recovery for the close-own-release / entry-discharge boundary.

Pending rows discover work only. Exact committed RCL transitions, reservation
versions, quantity history, fresh proof/report gates, and a snapshot-fenced CAS
authorize completion. The caller serves a prefetched snapshot; no broker I/O
runs here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tos.engine.records import EgressResultPayload
from tos.engine.vocabulary import EgressResultKind
from tos.posttrade import (
    EconomicObligationRecord,
    FinalityDimensionKind,
    ObligationLegDirection,
    ObligationLegScope,
    PostTradeFinalityProof,
    finality_proof_current,
    finality_proof_non_transferable,
)
from tos.rcl import CapacityState, CommandType, TransitionCause

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.close_history import (
    CloseHistoryResult,
    durable_close_history,
)
from tos_runtime.posttrade.entry_discharge import (
    DischargeRefusal,
    entry_discharge_refusal,
    entry_release_command_id,
)
from tos_runtime.posttrade.entry_recovery_pending import (
    ENTRY_DISCHARGE_PENDING_KIND,
    EntryDischargePending,
)
from tos_runtime.posttrade.entry_recovery_pending import (
    pending_items as _pending_items,
)
from tos_runtime.posttrade.entry_recovery_pending import (
    strict_object as _strict_object,
)
from tos_runtime.rcl.log import ReservationTransitionRecord, SqliteCommitLog
from tos_runtime.rcl.projection import ScopeReservation
from tos_runtime.recon.service import (
    ReconciliationReport,
    witness_independence_collapsed,
)

if TYPE_CHECKING:
    from tos_runtime.posttrade.release_consumer import (
        FinalityReleaseConsumer,
        ReleaseHoldReason,
    )

ENTRY_DISCHARGE_RECOVERY_HELD_KIND = "ENTRY_DISCHARGE_RECOVERY_HELD"
_RELEASE_HELD_KIND = "CAPACITY_RELEASE_HELD"
_PENDING_HELD_REASON = "ENTRY_DISCHARGE_PENDING"


@dataclass(frozen=True)
class RecoveryInputs:
    item: EntryDischargePending
    payload: EgressResultPayload
    proof: PostTradeFinalityProof
    obligation: EconomicObligationRecord
    report: ReconciliationReport | None
    corroborated: bool
    history: CloseHistoryResult


def _transition_for_command(
    rcl_log: SqliteCommitLog, command_id: str
) -> tuple[ReservationTransitionRecord, int, str | None] | None:
    try:
        commit = rcl_log.committed_command(command_id)
        if commit is None:
            return None
        history = rcl_log.reservation_transition_history(
            writer_epoch=rcl_log.current_epoch()
        )
    except Exception:  # noqa: BLE001 - unavailable or corrupt RCL is not authorization
        return None
    matches = tuple(row for row in history.transitions if row.command_id == command_id)
    if len(matches) != 1 or matches[0].seq != commit[0]:
        return None
    return matches[0], commit[0], commit[1]


def _committed_release_matches(
    consumer: FinalityReleaseConsumer,
    *,
    attempt_id: str,
    reservation_id: str,
    from_state: CapacityState | None,
    account: str,
    instrument: str,
    command_id: str,
) -> tuple[ReservationTransitionRecord, int] | None:
    match = _transition_for_command(consumer.rcl_log, command_id)
    if match is None:
        return None
    row, seq, digest = match
    expected_digest = consumer.scheme.compute_digest(
        {"attempt_id": attempt_id, "to_state": CapacityState.RELEASED.value}
    )
    if (
        digest != expected_digest
        or row.kind is not CommandType.RELEASE_RESERVATION
        or row.reservation_id != reservation_id
        or (from_state is not None and row.from_state is not from_state)
        or row.to_state is not CapacityState.RELEASED
        or row.scope.account != account
        or row.scope.instrument != instrument
        or row.cause is not TransitionCause.FINAL_QUANTITY_PROOF
        or row.finality_witness is not True
    ):
        return None
    return row, seq


def _valid_close_commit(
    consumer: FinalityReleaseConsumer, item: EntryDischargePending
) -> tuple[ReservationTransitionRecord, int] | None:
    match = _committed_release_matches(
        consumer,
        attempt_id=item.attempt_id,
        reservation_id=item.close_reservation_id,
        from_state=item.close_state,
        account=item.account,
        instrument=item.instrument,
        command_id=f"release-{item.attempt_id}",
    )
    if match is None or match[1] <= item.close_last_seq:
        return None
    return match


def _valid_entry_commit(
    consumer: FinalityReleaseConsumer, item: EntryDischargePending
) -> tuple[ReservationTransitionRecord, int] | None:
    return _committed_release_matches(
        consumer,
        attempt_id=item.attempt_id,
        reservation_id=item.entry_reservation_id,
        from_state=CapacityState.POSITION_CONSUMED,
        account=item.account,
        instrument=item.instrument,
        command_id=entry_release_command_id(item.attempt_id),
    )


def _entry_already_released(
    consumer: FinalityReleaseConsumer, item: EntryDischargePending
) -> bool:
    if (
        consumer.projection.reservation_state(item.entry_reservation_id)
        is not CapacityState.RELEASED
    ):
        return False
    pending = _pending_items(
        consumer.evidence_store,
        account=item.account,
        instrument=item.instrument,
    )
    if pending is None:
        return False
    return any(
        candidate.entry_reservation_id == item.entry_reservation_id
        and _valid_close_commit(consumer, candidate) is not None
        and _valid_entry_commit(consumer, candidate) is not None
        for candidate in pending
    )


def _scope_has_no_new_attempt(
    consumer: FinalityReleaseConsumer,
    item: EntryDischargePending,
    *,
    history: CloseHistoryResult,
) -> bool:
    try:
        snapshot = consumer.rcl_log.reservation_transition_history(
            writer_epoch=consumer.rcl_log.current_epoch()
        )
    except Exception:  # noqa: BLE001 - incomplete RCL history is not discharge evidence
        return False
    if snapshot.writer_epoch != getattr(
        history, "rcl_writer_epoch", None
    ) or snapshot.last_seq != getattr(history, "rcl_last_seq", None):
        return False
    first_seq: dict[str, int] = {}
    for row in snapshot.transitions:
        if row.scope.account != item.account or row.scope.instrument != item.instrument:
            continue
        first_seq.setdefault(row.reservation_id, row.seq)
    return not any(
        reservation_id not in {item.entry_reservation_id, item.close_reservation_id}
        and seq > item.close_last_seq
        for reservation_id, seq in first_seq.items()
    )


def _has_pending_binding(
    store: SqliteEvidenceStore, *, attempt_id: str, entry_reservation_id: str
) -> bool:
    try:
        rows = store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
            (_RELEASE_HELD_KIND,),
        ).fetchall()
        for (raw,) in rows:
            decoded = json.loads(raw, object_pairs_hook=_strict_object)
            payload = decoded.get("payload") if isinstance(decoded, dict) else None
            if isinstance(payload, dict) and (
                payload.get("attempt_id"),
                payload.get("reservation_id"),
                payload.get("reason"),
            ) == (attempt_id, entry_reservation_id, _PENDING_HELD_REASON):
                return True
    except Exception:  # noqa: BLE001 - failed reads are treated as no existing link
        return False
    return False


def _pending_binding_payload(
    consumer: FinalityReleaseConsumer,
    payload: EgressResultPayload,
    *,
    close_reservation_id: str,
    entry: ScopeReservation,
    proof_id: str,
) -> dict[str, object] | None:
    close_scope = consumer._reservation_scope(close_reservation_id)
    entry_scope = consumer._reservation_scope(entry.reservation_id)
    close_state = consumer.projection.reservation_state(close_reservation_id)
    close_last_seq = consumer.projection.reservation_last_seq(close_reservation_id)
    if (
        entry.state is not CapacityState.POSITION_CONSUMED
        or entry.last_seq < 0
        or entry.reservation_id == close_reservation_id
        or close_scope is None
        or close_scope.account != consumer.account
        or close_scope.instrument != consumer.instrument
        or close_state is None
        or close_last_seq is None
        or close_last_seq < 0
        or entry_scope is None
        or entry_scope.account != consumer.account
        or entry_scope.instrument != consumer.instrument
        or consumer.projection.reservation_last_seq(entry.reservation_id)
        != entry.last_seq
    ):
        return None
    return {
        "attempt_id": payload.attempt_id,
        "close_reservation_id": close_reservation_id,
        "close_last_seq": close_last_seq,
        "close_state": close_state.value,
        "entry_reservation_id": entry.reservation_id,
        "entry_last_seq": entry.last_seq,
        "account": consumer.account,
        "instrument": consumer.instrument,
        "proof_id": proof_id,
        "egress_payload": payload.model_dump(mode="json"),
    }


def _persist_pending_binding(
    consumer: FinalityReleaseConsumer,
    payload: EgressResultPayload,
    entry: ScopeReservation,
    item_payload: dict[str, object],
) -> EntryDischargePending | None:
    existing = _pending_items(
        consumer.evidence_store,
        account=consumer.account,
        instrument=consumer.instrument,
    )
    if existing is None:
        return None
    same_attempt = tuple(
        item for item in existing if item.attempt_id == payload.attempt_id
    )
    if same_attempt:
        expected = (
            item_payload["attempt_id"],
            item_payload["close_reservation_id"],
            item_payload["close_last_seq"],
            item_payload["close_state"],
            item_payload["entry_reservation_id"],
            item_payload["entry_last_seq"],
            item_payload["account"],
            item_payload["instrument"],
            item_payload["proof_id"],
            json.dumps(
                item_payload["egress_payload"], sort_keys=True, separators=(",", ":")
            ),
        )
        if same_attempt[-1].identity != expected:
            return None
    else:
        try:
            consumer.evidence_store.append(
                item_payload,
                kind=ENTRY_DISCHARGE_PENDING_KIND,
                record_class=ENTRY_DISCHARGE_PENDING_KIND,
            )
        except (
            Exception
        ):  # noqa: BLE001 - no close release without durable recovery evidence
            return None
    if not _has_pending_binding(
        consumer.evidence_store,
        attempt_id=payload.attempt_id,
        entry_reservation_id=entry.reservation_id,
    ):
        try:
            consumer.evidence_store.append(
                {
                    "attempt_id": payload.attempt_id,
                    "reservation_id": entry.reservation_id,
                    "reason": _PENDING_HELD_REASON,
                    "detail": "entry discharge awaits committed close release and recovery gates",
                },
                kind=_RELEASE_HELD_KIND,
                record_class=_RELEASE_HELD_KIND,
            )
        except (
            Exception
        ):  # noqa: BLE001 - no close release without durable link evidence
            return None
    if same_attempt:
        return same_attempt[-1]
    refreshed = _pending_items(
        consumer.evidence_store,
        account=consumer.account,
        instrument=consumer.instrument,
    )
    if refreshed is None:
        return None
    return next(
        (item for item in refreshed if item.attempt_id == payload.attempt_id), None
    )


def prepare_entry_discharge_pending(
    consumer: FinalityReleaseConsumer,
    payload: EgressResultPayload,
    *,
    close_reservation_id: str,
    entry: ScopeReservation,
    proof_id: str,
) -> EntryDischargePending | None:
    item_payload = _pending_binding_payload(
        consumer,
        payload,
        close_reservation_id=close_reservation_id,
        entry=entry,
        proof_id=proof_id,
    )
    if item_payload is None:
        return None
    return _persist_pending_binding(consumer, payload, entry, item_payload)


def pending_recovery_attempt_ids(
    consumer: FinalityReleaseConsumer,
) -> tuple[str, ...]:
    items = _pending_items(
        consumer.evidence_store,
        account=consumer.account,
        instrument=consumer.instrument,
    )
    if items is None:
        return ()
    pending: list[str] = []
    for item in items:
        if _valid_close_commit(consumer, item) is None:
            continue
        if consumer._reservation_id(item.attempt_id) != item.close_reservation_id:
            continue
        entry_scope = consumer._reservation_scope(item.entry_reservation_id)
        if (
            entry_scope is None
            or entry_scope.account != item.account
            or entry_scope.instrument != item.instrument
        ):
            continue
        if _valid_entry_commit(consumer, item) is not None or _entry_already_released(
            consumer, item
        ):
            continue
        pending.append(item.attempt_id)
    return tuple(pending)


def _history_signature(history: CloseHistoryResult) -> tuple[object, ...]:
    return (
        history.entry_attempt_id,
        str(history.entry_quantity) if history.entry_quantity is not None else None,
        str(history.prior_quantity) if history.prior_quantity is not None else None,
        str(history.current_quantity) if history.current_quantity is not None else None,
        str(history.total_quantity) if history.total_quantity is not None else None,
        history.refusal.value if history.refusal is not None else None,
        getattr(history, "rcl_writer_epoch", None),
        getattr(history, "rcl_last_seq", None),
    )


def _report_signature(report: object | None, corroborated: bool) -> tuple[object, ...]:
    if report is None:
        return (False, corroborated)
    classifications = tuple(
        (row.attempt_id, row.classification.value)
        for row in getattr(report, "classifications", ())
    )
    positions = tuple(
        (symbol, str(quantity))
        for symbol, quantity in getattr(report, "observed_positions", ())
    )
    return (
        bool(getattr(report, "permits_capacity_release", False)),
        corroborated,
        getattr(report, "reason", None),
        classifications,
        positions,
        bool(getattr(report, "observed_positions_complete", False)),
    )


def _recovery_hold_seen(
    store: SqliteEvidenceStore,
    *,
    attempt_id: str,
    entry_reservation_id: str,
    signature: tuple[object, ...],
) -> bool:
    try:
        rows = store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq DESC",
            (ENTRY_DISCHARGE_RECOVERY_HELD_KIND,),
        ).fetchall()
        for (raw,) in rows:
            decoded = json.loads(raw, object_pairs_hook=_strict_object)
            payload = decoded.get("payload") if isinstance(decoded, dict) else None
            if isinstance(payload, dict) and (
                payload.get("attempt_id"),
                payload.get("entry_reservation_id"),
            ) == (attempt_id, entry_reservation_id):
                return bool(
                    payload.get("signature")
                    == json.loads(json.dumps(signature, separators=(",", ":")))
                )
    except Exception:  # noqa: BLE001 - fail closed by allowing a conservative retry
        return False
    return False


def _record_recovery_hold(
    consumer: FinalityReleaseConsumer,
    *,
    payload: EgressResultPayload,
    item: EntryDischargePending,
    reason: str,
    detail: str,
    signature: tuple[object, ...],
) -> None:
    if _recovery_hold_seen(
        consumer.evidence_store,
        attempt_id=item.attempt_id,
        entry_reservation_id=item.entry_reservation_id,
        signature=signature,
    ):
        return
    consumer._hold(
        payload,
        item.entry_reservation_id,
        consumer.release_hold_reason(reason),
        detail=detail,
    )
    _append_recovery_marker(consumer, item=item, reason=reason, signature=signature)


def _append_recovery_marker(
    consumer: FinalityReleaseConsumer,
    *,
    item: EntryDischargePending,
    reason: str,
    signature: tuple[object, ...],
) -> None:
    consumer.evidence_store.append(
        {
            "attempt_id": item.attempt_id,
            "entry_reservation_id": item.entry_reservation_id,
            "reason": reason,
            "signature": json.loads(json.dumps(signature, separators=(",", ":"))),
        },
        kind=ENTRY_DISCHARGE_RECOVERY_HELD_KIND,
        record_class=ENTRY_DISCHARGE_RECOVERY_HELD_KIND,
    )


def _discharge(
    consumer: FinalityReleaseConsumer,
    item: EntryDischargePending,
    payload: EgressResultPayload,
    *,
    proof: PostTradeFinalityProof,
    report: ReconciliationReport,
    hold_reasons: Mapping[DischargeRefusal, ReleaseHoldReason],
    expected_entry_last_seq: int | None,
) -> bool:
    history = durable_close_history(
        consumer.rcl_log,
        consumer.evidence_store,
        account=consumer.account,
        instrument=consumer.instrument,
        entry_reservation_id=item.entry_reservation_id,
        current_attempt_id=payload.attempt_id,
        current_reservation_id=consumer._reservation_id(payload.attempt_id),
    )
    refusal = entry_discharge_refusal(
        payload,
        entry_quantity=history.entry_quantity,
        prior_closed=history.prior_quantity,
        report=report,
        instrument=consumer.instrument,
    )
    if history.current_quantity != payload.filled_quantity:
        refusal = DischargeRefusal.QUANTITY_UNPROVEN
    if refusal is not None:
        consumer._hold(
            payload,
            item.entry_reservation_id,
            hold_reasons[refusal],
            detail=(
                f"entry attempt={history.entry_attempt_id} final_quantity={history.entry_quantity} "
                f"history_refusal={history.refusal} prior_closed={history.prior_quantity} "
                f"vs close filled={payload.filled_quantity} "
                f"remaining={payload.remaining_quantity}; "
                f"observed_positions={getattr(report, 'observed_positions', ())}"
            ),
        )
        return False
    if not _scope_has_no_new_attempt(consumer, item, history=history):
        consumer._hold(
            payload,
            item.entry_reservation_id,
            consumer.release_hold_reason("AMBIGUOUS_SCOPE_RESERVATIONS"),
            detail="a newer or unbound reservation exists in the entry scope",
        )
        return False
    history_epoch = getattr(history, "rcl_writer_epoch", None)
    history_tip = getattr(history, "rcl_last_seq", None)
    if history_epoch is None or history_tip is None:
        consumer._hold(
            payload,
            item.entry_reservation_id,
            hold_reasons[DischargeRefusal.QUANTITY_UNPROVEN],
            detail="close history did not provide an exact RCL writer fence",
        )
        return False
    outcome = consumer._release(
        payload,
        reservation_id=item.entry_reservation_id,
        proof=proof,
        report_reason=getattr(report, "reason", None),
        to_state=CapacityState.RELEASED,
        resolution_generation=consumer._active_generation(
            account=consumer.account, instrument=consumer.instrument
        ),
        command_id=entry_release_command_id(payload.attempt_id),
        expected_reservation_last_seq=expected_entry_last_seq,
        expected_reservation_state=CapacityState.POSITION_CONSUMED,
        expected_writer_epoch=history_epoch,
        expected_rcl_last_seq=history_tip,
    )
    return outcome.released


def discharge_entry(
    consumer: FinalityReleaseConsumer,
    payload: EgressResultPayload,
    entry: ScopeReservation,
    *,
    proof: PostTradeFinalityProof,
    report: ReconciliationReport,
    hold_reasons: Mapping[DischargeRefusal, ReleaseHoldReason],
) -> None:
    pending = _pending_items(
        consumer.evidence_store,
        account=consumer.account,
        instrument=consumer.instrument,
    )
    item = next(
        (
            candidate
            for candidate in pending or ()
            if candidate.attempt_id == payload.attempt_id
            and candidate.entry_reservation_id == entry.reservation_id
        ),
        None,
    )
    if item is None:
        return
    _discharge(
        consumer,
        item,
        payload,
        proof=proof,
        report=report,
        hold_reasons=hold_reasons,
        expected_entry_last_seq=item.entry_last_seq,
    )


def _recovery_history(
    consumer: FinalityReleaseConsumer, item: EntryDischargePending
) -> CloseHistoryResult:
    return durable_close_history(
        consumer.rcl_log,
        consumer.evidence_store,
        account=consumer.account,
        instrument=consumer.instrument,
        entry_reservation_id=item.entry_reservation_id,
        current_attempt_id=item.attempt_id,
        current_reservation_id=item.close_reservation_id,
    )


def _load_recovery_inputs(
    consumer: FinalityReleaseConsumer, item: EntryDischargePending
) -> RecoveryInputs | None:
    if consumer._reservation_id(item.attempt_id) != item.close_reservation_id:
        return None
    entry_scope = consumer._reservation_scope(item.entry_reservation_id)
    if (
        entry_scope is None
        or entry_scope.account != item.account
        or entry_scope.instrument != item.instrument
    ):
        return None
    try:
        payload = EgressResultPayload.model_validate(dict(item.payload))
    except Exception:  # noqa: BLE001 - pending payload alone is never trusted
        return None
    if (
        payload.attempt_id != item.attempt_id
        or payload.instrument_key.account != item.account
        or payload.instrument_key.instrument != item.instrument
        or payload.kind is not EgressResultKind.FULL_FILL
    ):
        return None
    if (
        consumer.projection.reservation_state(item.entry_reservation_id)
        is not CapacityState.POSITION_CONSUMED
        or consumer.projection.reservation_last_seq(item.entry_reservation_id)
        != item.entry_last_seq
    ):
        signature = (
            "entry-version-changed",
            item.entry_last_seq,
            consumer.projection.reservation_state(item.entry_reservation_id),
            consumer.projection.reservation_last_seq(item.entry_reservation_id),
        )
        _record_recovery_hold(
            consumer,
            payload=payload,
            item=item,
            reason="ENTRY_QUANTITY_UNPROVEN",
            detail="entry reservation state or sequence changed after pending was recorded",
            signature=signature,
        )
        return None
    if consumer.inbox.finality_witness(item.attempt_id) is not True:
        history = _recovery_history(consumer, item)
        _record_recovery_hold(
            consumer,
            payload=payload,
            item=item,
            reason="NO_WITNESS",
            detail="durable finality witness is not true",
            signature=(_history_signature(history), ("no-finality-witness",)),
        )
        return None
    proof = consumer._reload_proof(
        item.attempt_id,
        id_prefix=consumer.finality_producer.full_fill_proof_prefix,
    )
    obligation = consumer._reload_obligation(
        item.attempt_id,
        id_prefix=consumer.finality_producer.full_fill_obligation_prefix,
    )
    if proof is None or obligation is None or proof.proof_id != item.proof_id:
        history = _recovery_history(consumer, item)
        _record_recovery_hold(
            consumer,
            payload=payload,
            item=item,
            reason="PROOF_NOT_RELOADED",
            detail="pending close proof or obligation could not be reloaded exactly",
            signature=(_history_signature(history), ("proof-not-reloaded",)),
        )
        return None
    report, corroborated = consumer._reconcile(payload)
    history = _recovery_history(consumer, item)
    return RecoveryInputs(
        item=item,
        payload=payload,
        proof=proof,
        obligation=obligation,
        report=report,
        corroborated=corroborated,
        history=history,
    )


def _report_and_quantity_admit(
    consumer: FinalityReleaseConsumer, inputs: RecoveryInputs
) -> bool:
    item, payload, report = inputs.item, inputs.payload, inputs.report
    history_signature = _history_signature(inputs.history)
    report_signature = _report_signature(report, inputs.corroborated)
    if not inputs.corroborated or report is None:
        signature = (history_signature, report_signature)
        if _recovery_hold_seen(
            consumer.evidence_store,
            attempt_id=item.attempt_id,
            entry_reservation_id=item.entry_reservation_id,
            signature=signature,
        ):
            return False
        # #1011 §3.5: the recovery pass records the SAME split the release path does
        # (`release_consumer.uncorroborated_hold_reason`), through the one shared
        # predicate — a split that reached only the release path would leave this pass
        # reporting a conflict the witness never found.
        if report is None:
            reason = "RECONCILIATION_UNAVAILABLE"
        elif witness_independence_collapsed(report):
            reason = "WITNESS_NOT_INDEPENDENT"
        else:
            reason = "NOT_CORROBORATED"
        _record_recovery_hold(
            consumer,
            payload=payload,
            item=item,
            reason=reason,
            detail=getattr(report, "reason", None) or reason,
            signature=signature,
        )
        return False
    refusal = entry_discharge_refusal(
        payload,
        entry_quantity=inputs.history.entry_quantity,
        prior_closed=inputs.history.prior_quantity,
        report=report,
        instrument=consumer.instrument,
    )
    if inputs.history.current_quantity != payload.filled_quantity:
        refusal = DischargeRefusal.QUANTITY_UNPROVEN
    if refusal is None:
        return True
    signature = (history_signature, ("quantity",))
    if not _recovery_hold_seen(
        consumer.evidence_store,
        attempt_id=item.attempt_id,
        entry_reservation_id=item.entry_reservation_id,
        signature=signature,
    ):
        _record_recovery_hold(
            consumer,
            payload=payload,
            item=item,
            reason="ENTRY_QUANTITY_UNPROVEN",
            detail=(
                f"entry quantity history refused={inputs.history.refusal}; "
                f"entry={inputs.history.entry_quantity} prior={inputs.history.prior_quantity} "
                f"current={inputs.history.current_quantity}"
            ),
            signature=signature,
        )
    return False


def _proof_gate_admits(
    consumer: FinalityReleaseConsumer, inputs: RecoveryInputs
) -> bool:
    item, payload = inputs.item, inputs.payload
    scope = consumer._reservation_scope(item.close_reservation_id)
    if scope is None:
        reason = "NO_RESERVATION"
    else:
        target = ObligationLegScope(
            leg=ObligationLegDirection.RECEIPT,
            account=scope.account,
            currency=consumer.finality_producer.config.currency,
            value_date=consumer.finality_producer.config.value_date,
            source_revision=consumer.finality_producer.config.source_revision,
            finality_class=FinalityDimensionKind.ORDER_FQP,
        )
        if not finality_proof_non_transferable(
            inputs.proof,
            target,
            target_obligation_ref=inputs.obligation.obligation_id,
            target_obligation_version=inputs.obligation.obligation_version,
        ):
            reason = "PROOF_NOT_TRANSFERABLE"
        elif not finality_proof_current(
            inputs.proof,
            consumer._active_generation(
                account=scope.account, instrument=scope.instrument
            ),
        ):
            reason = "PROOF_NOT_CURRENT"
        else:
            return True
    signature = (
        _history_signature(inputs.history),
        _report_signature(inputs.report, inputs.corroborated),
        reason,
    )
    if not _recovery_hold_seen(
        consumer.evidence_store,
        attempt_id=item.attempt_id,
        entry_reservation_id=item.entry_reservation_id,
        signature=signature,
    ):
        _record_recovery_hold(
            consumer,
            payload=payload,
            item=item,
            reason=reason,
            detail="reloaded close proof no longer passes current scope gates",
            signature=signature,
        )
    return False


def _release_recovered_entry(
    consumer: FinalityReleaseConsumer,
    inputs: RecoveryInputs,
    *,
    hold_reasons: Mapping[DischargeRefusal, ReleaseHoldReason],
) -> bool:
    item, payload = inputs.item, inputs.payload
    history_signature = _history_signature(inputs.history)
    report_signature = _report_signature(inputs.report, inputs.corroborated)
    signature = (history_signature, report_signature, "RCL_TRANSITION_REFUSED")
    if _recovery_hold_seen(
        consumer.evidence_store,
        attempt_id=item.attempt_id,
        entry_reservation_id=item.entry_reservation_id,
        signature=signature,
    ):
        return False
    report = inputs.report
    if report is None:
        return False
    released = _discharge(
        consumer,
        item,
        payload,
        proof=inputs.proof,
        report=report,
        hold_reasons=hold_reasons,
        expected_entry_last_seq=item.entry_last_seq,
    )
    if released or _valid_entry_commit(consumer, item) is not None:
        return True
    _append_recovery_marker(
        consumer,
        item=item,
        reason="RCL_TRANSITION_REFUSED",
        signature=signature,
    )
    return False


def resume_entry_discharge(
    consumer: FinalityReleaseConsumer,
    attempt_id: str,
    *,
    hold_reasons: Mapping[DischargeRefusal, ReleaseHoldReason],
) -> bool:
    """Re-corroborate and resume one pending close while a fresh snapshot is served."""
    items = _pending_items(
        consumer.evidence_store,
        account=consumer.account,
        instrument=consumer.instrument,
    )
    matches = tuple(item for item in items or () if item.attempt_id == attempt_id)
    if len(matches) != 1:
        return False
    item = matches[0]
    if _valid_close_commit(consumer, item) is None:
        return False
    if _valid_entry_commit(consumer, item) is not None or _entry_already_released(
        consumer, item
    ):
        return True
    inputs = _load_recovery_inputs(consumer, item)
    if inputs is None or not _report_and_quantity_admit(consumer, inputs):
        return False
    if not _proof_gate_admits(consumer, inputs):
        return False
    return _release_recovered_entry(consumer, inputs, hold_reasons=hold_reasons)
