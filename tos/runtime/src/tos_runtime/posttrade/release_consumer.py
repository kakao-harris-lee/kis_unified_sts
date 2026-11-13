"""Consume durable finality evidence and release the RCL reservation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

from tos.canonical import CanonicalizationScheme
from tos.engine.records import EgressResultPayload, InstrumentKey
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
from tos.rcl import (
    AppendRefusal,
    CapacityReservationTransition,
    CapacityState,
    LogView,
    ReservationScope,
)
from tos.time.domains import HealthState

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.entry_discharge import (
    any_quantity_filled,
    entry_release_command_id,
    other_outstanding,
)
from tos_runtime.posttrade.entry_recovery import (
    discharge_entry,
    pending_recovery_attempt_ids,
    prepare_entry_discharge_pending,
    resume_entry_discharge,
)
from tos_runtime.posttrade.finality import ReleaseFinalityProducer
from tos_runtime.posttrade.rcl_history_cache import ReservationHistoryCache
from tos_runtime.posttrade.release_currentness import latest_release_is_conflict_free
from tos_runtime.posttrade.release_hold import (
    DISCHARGE_HOLD_REASONS as _DISCHARGE_HOLD_REASONS,
)
from tos_runtime.posttrade.release_hold import (
    ReleaseHoldReason,
    uncorroborated_hold_reason,
)
from tos_runtime.rcl.finality_witness import release_reservation
from tos_runtime.rcl.log import ReservationTransitionRefusal, SqliteCommitLog
from tos_runtime.rcl.projection import (
    ScopeReservation,
    SqliteReservationProjectionReader,
)
from tos_runtime.rcl.reservation_lookup import (
    reservation_id_for_attempt,
)
from tos_runtime.recon.evidence_reader import SqliteEvidenceReceiptReader
from tos_runtime.recon.ports import WitnessScope, WitnessUnavailable
from tos_runtime.recon.service import (
    ReconciliationClass,
    ReconciliationReport,
    ReconciliationService,
)
from tos_runtime.recovery.reconciliation import (  # noqa: SLF001
    FreshnessTimeReader,
    _build_freshness_marker,
)
from tos_runtime.time.service import TimeHealthReader
from tos_runtime.time.sources import MonotonicSource

__all__ = [
    "CAPACITY_RELEASE_HELD_KIND",
    "entry_release_command_id",
    "release_command_id",
    "CAPACITY_RELEASE_INTENT_KIND",
    "RELEASE_PROOF_OVERDUE_KIND",
    "FinalityConsumerPort",
    "FinalityConsumerTimeReader",
    "FinalityReleaseConsumer",
    "ReleaseConflictReader",
    "ReleaseHoldReason",
    "uncorroborated_hold_reason",
    "ReleaseOutcome",
    "ReleaseOutcomeLike",
]

_ECONOMIC_OBLIGATION_KIND = "ECONOMIC_OBLIGATION"
_POSTTRADE_FINALITY_PROOF_KIND = "POSTTRADE_FINALITY_PROOF"

CAPACITY_RELEASE_INTENT_KIND = "CAPACITY_RELEASE_INTENT"
CAPACITY_RELEASE_HELD_KIND = "CAPACITY_RELEASE_HELD"
RELEASE_PROOF_OVERDUE_KIND = "RELEASE_PROOF_OVERDUE"

_OVERDUE_ELIGIBLE_STATES: frozenset[CapacityState] = frozenset(
    {CapacityState.RELEASE_PENDING_PROOF, CapacityState.QUARANTINED_UNKNOWN}
)

_NON_EXECUTION_KINDS: frozenset[EgressResultKind] = frozenset(
    {
        EgressResultKind.CANCEL_ACK,
        EgressResultKind.EXPIRED,
        EgressResultKind.REJECT,
    }
)


def release_command_id(attempt_id: str) -> str:
    """The RCL idempotency key of ``attempt_id``'s release transition — the ONE spelling, so the"""
    return f"release-{attempt_id}"


class ReleaseOutcomeLike(Protocol):
    """Read-only result surface used by finality projection; frozen outcomes satisfy it."""

    @property
    def released(self) -> bool: ...
    @property
    def attempt_id(self) -> str: ...
    @property
    def proof_digest(self) -> str | None: ...
    @property
    def evidence_seq(self) -> int | None: ...
    @property
    def resolution_generation(self) -> int | None: ...


@dataclass(frozen=True)
class ReleaseOutcome:
    """Data-only result of one consume call; the engine maps committed releases into its state."""

    released: bool
    attempt_id: str
    proof_digest: str | None = None
    evidence_seq: int | None = None
    resolution_generation: int | None = None


class FinalityConsumerPort(Protocol):
    """The narrow read surface :func:`~tos_runtime.engine.finality_projection._project_release`"""

    def consume(self, payload: EgressResultPayload) -> ReleaseOutcomeLike:
        """Consume one genuinely-applied ``EGRESS_RESULT`` payload; see"""
        ...


class ReleaseConflictReader(Protocol):
    """The narrow read surface :mod:`tos_runtime.compose._dimension_readers`'s POST_TRADE"""

    def latest_release_is_conflict_free(self) -> bool:
        """See :meth:`FinalityReleaseConsumer.latest_release_is_conflict_free`'s own docstring."""
        ...


class FinalityConsumerTimeReader(TimeHealthReader, FreshnessTimeReader, Protocol):
    """The time health and freshness snapshot reads required by the release consumer."""


@dataclass(frozen=True)
class FinalityReleaseConsumer:
    """Bind this consumer to every collaborator :meth:`consume` needs (module docstring)."""

    rcl_log: SqliteCommitLog
    projection: SqliteReservationProjectionReader
    evidence_store: SqliteEvidenceStore
    inbox: SqliteEventInbox
    recon_service: ReconciliationService
    time_service: FinalityConsumerTimeReader
    finality_producer: ReleaseFinalityProducer
    scheme: CanonicalizationScheme
    monotonic_source: MonotonicSource
    account: str
    instrument: str
    release_proof_wait_ms: int
    _wait_start_ms: dict[tuple[str, int | None], int] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _history_cache: ReservationHistoryCache = field(
        default_factory=ReservationHistoryCache, init=False, repr=False, compare=False
    )

    def consume(self, payload: EgressResultPayload) -> ReleaseOutcome:
        """Attempt a release for one genuinely-``APPLIED`` ``EGRESS_RESULT`` payload."""
        reservation_id = self._reservation_id(payload.attempt_id)
        if reservation_id is None:
            if (
                payload.kind is EgressResultKind.FULL_FILL
                or payload.kind in _NON_EXECUTION_KINDS
            ):
                return self._hold(payload, None, ReleaseHoldReason.NO_RESERVATION)
            return ReleaseOutcome(released=False, attempt_id=payload.attempt_id)
        self._check_obligation_expiry(reservation_id=reservation_id)

        if payload.kind is EgressResultKind.FULL_FILL:
            return self._consume_full_fill(payload, reservation_id=reservation_id)
        if payload.kind in _NON_EXECUTION_KINDS:
            return self._consume_non_execution(payload, reservation_id=reservation_id)
        return ReleaseOutcome(released=False, attempt_id=payload.attempt_id)

    def pending_recovery_attempt_ids(self) -> tuple[str, ...]:
        """Close attempts whose own exact RCL release committed and still need entry recovery."""
        return pending_recovery_attempt_ids(self)

    def resume_entry_discharge(self, attempt_id: str) -> bool:
        """Re-corroborate one pending entry discharge using the snapshot currently being served."""
        return resume_entry_discharge(
            self,
            attempt_id,
            hold_reasons=_DISCHARGE_HOLD_REASONS,
        )

    def release_hold_reason(self, reason: str) -> ReleaseHoldReason:
        """Turn a bounded recovery reason code into the consumer's evidence vocabulary."""
        return ReleaseHoldReason(reason)

    def _reservation_id(self, attempt_id: str) -> str | None:
        """THIS attempt's own RCL reservation id, or ``None`` when none can be attributed."""
        return reservation_id_for_attempt(
            self.evidence_store,
            self.projection,
            account=self.account,
            instrument=self.instrument,
            attempt_id=attempt_id,
        )

    def latest_release_is_conflict_free(self) -> bool:
        """Whether this scope's MOST RECENT recorded post-trade release evidence is free of a"""
        return latest_release_is_conflict_free(
            self.evidence_store, account=self.account, instrument=self.instrument
        )

    def _consume_full_fill(
        self, payload: EgressResultPayload, *, reservation_id: str
    ) -> ReleaseOutcome:
        witness = self.inbox.finality_witness(payload.attempt_id)
        if witness is not True:
            return self._hold(payload, reservation_id, ReleaseHoldReason.NO_WITNESS)
        proof = self._reload_proof(
            payload.attempt_id, id_prefix=self.finality_producer.full_fill_proof_prefix
        )
        obligation = self._reload_obligation(
            payload.attempt_id,
            id_prefix=self.finality_producer.full_fill_obligation_prefix,
        )
        if proof is None or obligation is None:
            return self._hold(
                payload, reservation_id, ReleaseHoldReason.PROOF_NOT_RELOADED
            )
        report, corroborated = self._reconcile(payload)
        if report is None:
            return self._hold(
                payload, reservation_id, ReleaseHoldReason.RECONCILIATION_UNAVAILABLE
            )
        if not corroborated:
            return self._hold(
                payload,
                reservation_id,
                uncorroborated_hold_reason(report),
                detail=report.reason,
            )
        others = other_outstanding(
            self.projection,
            account=self.account,
            instrument=self.instrument,
            reservation_id=reservation_id,
        )
        if not others:
            return self._apply_gate4_and_release(
                payload,
                reservation_id=reservation_id,
                proof=proof,
                obligation=obligation,
                report_reason=report.reason,
                to_state=CapacityState.POSITION_CONSUMED,
            )
        if len(others) != 1 or others[0].state is not CapacityState.POSITION_CONSUMED:
            return self._hold(
                payload,
                reservation_id,
                ReleaseHoldReason.AMBIGUOUS_SCOPE_RESERVATIONS,
                detail=", ".join(f"{r.reservation_id}={r.state.value}" for r in others),
            )
        if not proof.proof_id:
            return self._hold(
                payload, reservation_id, ReleaseHoldReason.PROOF_NOT_RELOADED
            )
        pending = prepare_entry_discharge_pending(
            self,
            payload,
            close_reservation_id=reservation_id,
            entry=others[0],
            proof_id=proof.proof_id,
        )
        if pending is None:
            return self._hold(
                payload,
                reservation_id,
                ReleaseHoldReason.ENTRY_DISCHARGE_PENDING_UNAVAILABLE,
            )
        outcome = self._apply_gate4_and_release(
            payload,
            reservation_id=reservation_id,
            proof=proof,
            obligation=obligation,
            report_reason=report.reason,
            to_state=CapacityState.RELEASED,
            expected_reservation_last_seq=pending.close_last_seq,
            expected_reservation_state=pending.close_state,
        )
        if outcome.released:
            self._discharge_entry(payload, others[0], proof=proof, report=report)
        return outcome

    def _consume_non_execution(
        self, payload: EgressResultPayload, *, reservation_id: str
    ) -> ReleaseOutcome:
        if any_quantity_filled(
            self.evidence_store,
            account=self.account,
            instrument=self.instrument,
            attempt_id=payload.attempt_id,
        ):
            return self._hold(
                payload, reservation_id, ReleaseHoldReason.FILLED_QUANTITY_STILL_HELD
            )
        report, corroborated = self._reconcile(payload)
        if report is None:
            return self._hold(
                payload, reservation_id, ReleaseHoldReason.RECONCILIATION_UNAVAILABLE
            )
        if not corroborated:
            return self._hold(
                payload,
                reservation_id,
                uncorroborated_hold_reason(report),
                detail=report.reason,
            )
        produced = self.finality_producer.produce_non_execution(payload)
        if produced is None:
            return self._hold(
                payload,
                reservation_id,
                ReleaseHoldReason.NON_EXECUTION_PROOF_UNPRODUCIBLE,
            )
        self.evidence_store.append(
            produced.record.model_dump(mode="json"),
            kind=_ECONOMIC_OBLIGATION_KIND,
            record_class=_ECONOMIC_OBLIGATION_KIND,
        )
        self.evidence_store.append(
            produced.proof.model_dump(mode="json"),
            kind=_POSTTRADE_FINALITY_PROOF_KIND,
            record_class=_POSTTRADE_FINALITY_PROOF_KIND,
        )
        proof = self._reload_proof(
            payload.attempt_id,
            id_prefix=self.finality_producer.non_execution_proof_prefix,
        )
        obligation = self._reload_obligation(
            payload.attempt_id,
            id_prefix=self.finality_producer.non_execution_obligation_prefix,
        )
        if proof is None or obligation is None:
            return self._hold(
                payload, reservation_id, ReleaseHoldReason.PROOF_NOT_RELOADED
            )
        return self._apply_gate4_and_release(
            payload,
            reservation_id=reservation_id,
            proof=proof,
            obligation=obligation,
            report_reason=report.reason,
            to_state=CapacityState.RELEASED,
        )

    def _discharge_entry(
        self,
        payload: EgressResultPayload,
        entry: ScopeReservation,
        *,
        proof: PostTradeFinalityProof,
        report: ReconciliationReport,
    ) -> None:
        """Take the closed entry's reservation ``POSITION_CONSUMED -> RELEASED``."""
        discharge_entry(
            self,
            payload,
            entry,
            proof=proof,
            report=report,
            hold_reasons=_DISCHARGE_HOLD_REASONS,
        )

    def _reconcile(
        self, payload: EgressResultPayload
    ) -> tuple[ReconciliationReport | None, bool]:
        """Gate 3 (module docstring): a fresh :class:`~tos_runtime.recon.service"""
        attempt_id = payload.attempt_id
        instrument_key = InstrumentKey(account=self.account, instrument=self.instrument)
        scope = WitnessScope(
            account=self.account,
            instrument_keys=(instrument_key,),
            attempt_ids=(attempt_id,),
            order_dates=self._scope_receipt_dates(payload),
        )
        freshness = _build_freshness_marker(self.time_service)
        try:
            report = self.recon_service.reconcile(scope, freshness=freshness)
        except (
            Exception
        ):  # noqa: BLE001 -- fail-closed, mirrors recovery/reconciliation.py
            return None, False
        matched = any(
            classification.attempt_id == attempt_id
            and classification.classification is ReconciliationClass.MATCHED
            for classification in report.classifications
        )
        return report, bool(report.permits_capacity_release and matched)

    def _scope_receipt_dates(self, payload: EgressResultPayload) -> tuple[str, ...]:
        """Every trading date the scope's recorded receipts carry, plus ``payload``'s own."""
        scope = WitnessScope(
            account=self.account,
            instrument_keys=(
                InstrumentKey(account=self.account, instrument=self.instrument),
            ),
        )
        try:
            receipts = SqliteEvidenceReceiptReader(self.evidence_store).receipts(scope)
        except WitnessUnavailable:
            receipts = ()
        dates = {r.trading_date for r in receipts if r.trading_date is not None}
        if payload.trading_date is not None:
            dates.add(payload.trading_date)
        return tuple(sorted(dates))

    def _apply_gate4_and_release(
        self,
        payload: EgressResultPayload,
        *,
        reservation_id: str,
        proof: PostTradeFinalityProof,
        obligation: EconomicObligationRecord,
        report_reason: str | None,
        to_state: CapacityState,
        expected_reservation_last_seq: int | None = None,
        expected_reservation_state: CapacityState | None = None,
    ) -> ReleaseOutcome:
        reservation_scope = self._reservation_scope(reservation_id)
        if reservation_scope is None:
            return self._hold(payload, reservation_id, ReleaseHoldReason.NO_RESERVATION)
        target_scope = ObligationLegScope(
            leg=ObligationLegDirection.RECEIPT,
            account=reservation_scope.account,
            currency=self.finality_producer.config.currency,
            value_date=self.finality_producer.config.value_date,
            source_revision=self.finality_producer.config.source_revision,
            finality_class=FinalityDimensionKind.ORDER_FQP,
        )
        if not finality_proof_non_transferable(
            proof,
            target_scope,
            target_obligation_ref=obligation.obligation_id,
            target_obligation_version=obligation.obligation_version,
        ):
            return self._hold(
                payload, reservation_id, ReleaseHoldReason.PROOF_NOT_TRANSFERABLE
            )
        active_generation = self._active_generation(
            account=reservation_scope.account, instrument=reservation_scope.instrument
        )
        if not finality_proof_current(proof, active_generation):
            return self._hold(
                payload, reservation_id, ReleaseHoldReason.PROOF_NOT_CURRENT
            )
        return self._release(
            payload,
            reservation_id=reservation_id,
            proof=proof,
            report_reason=report_reason,
            to_state=to_state,
            resolution_generation=active_generation,
            expected_reservation_last_seq=expected_reservation_last_seq,
            expected_reservation_state=expected_reservation_state,
        )

    def _reservation_scope(self, reservation_id: str) -> ReservationScope | None:
        """The RCL log's OWN persisted :class:`~tos.rcl.ReservationScope` for ``reservation_id``"""
        for (
            row_reservation_id,
            _state,
            _last_seq,
            scope,
        ) in self.rcl_log.reservation_rows():
            if row_reservation_id == reservation_id:
                return scope
        return None

    def _active_generation(self, *, account: str, instrument: str) -> int | None:
        """The newest ``obligation_generation`` durably recorded across every"""
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
            (_ECONOMIC_OBLIGATION_KIND,),
        ).fetchall()
        newest: int | None = None
        for (payload_json,) in rows:
            decoded = json.loads(payload_json)["payload"]
            if (
                decoded.get("account_scope") != account
                or decoded.get("instrument_identity") != instrument
            ):
                continue
            generation = decoded.get("obligation_generation")
            if isinstance(generation, int) and (newest is None or generation > newest):
                newest = generation
        return newest

    def _release(
        self,
        payload: EgressResultPayload,
        *,
        reservation_id: str,
        proof: PostTradeFinalityProof,
        report_reason: str | None,
        to_state: CapacityState,
        resolution_generation: int | None,
        command_id: str | None = None,
        expected_reservation_last_seq: int | None = None,
        expected_reservation_state: CapacityState | None = None,
        expected_writer_epoch: int | None = None,
        expected_rcl_last_seq: int | None = None,
    ) -> ReleaseOutcome:
        snapshot = self._read_release_snapshot(
            payload,
            reservation_id=reservation_id,
            expected_reservation_last_seq=expected_reservation_last_seq,
            expected_reservation_state=expected_reservation_state,
            expected_writer_epoch=expected_writer_epoch,
            expected_rcl_last_seq=expected_rcl_last_seq,
        )
        if snapshot is None:
            return ReleaseOutcome(released=False, attempt_id=payload.attempt_id)
        current_state, view = snapshot
        expected_seq = -1 if view.last_seq is None else view.last_seq
        generation = 0 if resolution_generation is None else resolution_generation
        intent_receipt = self.evidence_store.append(
            {
                "attempt_id": payload.attempt_id,
                "reservation_id": reservation_id,
                "proof_id": proof.proof_id,
                "destination": to_state.value,
                "report_reason": report_reason,
                "resolution_generation": generation,
            },
            kind=CAPACITY_RELEASE_INTENT_KIND,
            record_class=CAPACITY_RELEASE_INTENT_KIND,
        )
        transition = CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=view.epoch,
            from_state=current_state,
            to_state=to_state,
            scope=ReservationScope(account=self.account, instrument=self.instrument),
        )
        command_digest = self.scheme.compute_digest(
            {"attempt_id": payload.attempt_id, "to_state": to_state.value}
        )
        try:
            receipt = release_reservation(
                self.rcl_log,
                transition,
                command_id=(
                    release_command_id(payload.attempt_id)
                    if command_id is None
                    else command_id
                ),
                command_digest=command_digest,
                expected_seq=expected_seq,
                proof=proof,
            )
        except ReservationTransitionRefusal as exc:
            return self._hold(
                payload,
                reservation_id,
                ReleaseHoldReason.RCL_TRANSITION_REFUSED,
                detail=str(exc),
            )
        if isinstance(receipt, AppendRefusal):
            return self._hold(
                payload,
                reservation_id,
                ReleaseHoldReason.RCL_TRANSITION_REFUSED,
                detail=f"{receipt.reason}: {receipt.detail}",
            )
        return ReleaseOutcome(
            released=True,
            attempt_id=payload.attempt_id,
            proof_digest=proof.proof_id,
            evidence_seq=intent_receipt.seq,
            resolution_generation=generation,
        )

    def _read_release_snapshot(
        self,
        payload: EgressResultPayload,
        *,
        reservation_id: str,
        expected_reservation_last_seq: int | None,
        expected_reservation_state: CapacityState | None,
        expected_writer_epoch: int | None,
        expected_rcl_last_seq: int | None,
    ) -> tuple[CapacityState, LogView] | None:
        current = self.projection.reservation_state(reservation_id)
        if current is None:
            self._hold(payload, reservation_id, ReleaseHoldReason.NO_RESERVATION)
            return None
        if (
            expected_reservation_state is not None
            and current is not expected_reservation_state
        ):
            self._hold(
                payload,
                reservation_id,
                ReleaseHoldReason.RCL_TRANSITION_REFUSED,
                detail="reservation state changed after pending entry discharge",
            )
            return None
        try:
            view = self.rcl_log.read_linearizable(
                writer_epoch=self.rcl_log.current_epoch()
            )
        except Exception as exc:  # noqa: BLE001 - stale epoch / unreadable log -> hold
            self._hold(
                payload,
                reservation_id,
                ReleaseHoldReason.RCL_TRANSITION_REFUSED,
                detail=f"RCL tip unreadable: {type(exc).__name__}",
            )
            return None
        if expected_writer_epoch is not None and view.epoch != expected_writer_epoch:
            detail = "RCL writer epoch changed after close history was read"
        elif (
            expected_writer_epoch is not None and expected_rcl_last_seq != view.last_seq
        ):
            detail = "RCL tip changed after close history was read"
        elif (
            expected_reservation_last_seq is not None
            and self.projection.reservation_last_seq(reservation_id)
            != expected_reservation_last_seq
        ):
            detail = "reservation sequence changed after pending entry discharge"
        else:
            return current, view
        self._hold(
            payload,
            reservation_id,
            ReleaseHoldReason.RCL_TRANSITION_REFUSED,
            detail=detail,
        )
        return None

    def _hold(
        self,
        payload: EgressResultPayload,
        reservation_id: str | None,
        reason: ReleaseHoldReason,
        *,
        detail: str | None = None,
    ) -> ReleaseOutcome:
        self.evidence_store.append(
            {
                "attempt_id": payload.attempt_id,
                "reservation_id": reservation_id,
                "reason": reason.value,
                "detail": detail,
            },
            kind=CAPACITY_RELEASE_HELD_KIND,
            record_class=CAPACITY_RELEASE_HELD_KIND,
        )
        return ReleaseOutcome(released=False, attempt_id=payload.attempt_id)

    def _reload_proof(
        self, attempt_id: str, *, id_prefix: str
    ) -> PostTradeFinalityProof | None:
        idempotency_key = f"{id_prefix}:{attempt_id}"
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq DESC",
            (_POSTTRADE_FINALITY_PROOF_KIND,),
        ).fetchall()
        for (payload_json,) in rows:
            decoded = json.loads(payload_json)["payload"]
            if decoded.get("idempotency_key") == idempotency_key:
                return PostTradeFinalityProof.model_validate(decoded)
        return None

    def _reload_obligation(
        self, attempt_id: str, *, id_prefix: str
    ) -> EconomicObligationRecord | None:
        idempotency_key = f"{id_prefix}:{attempt_id}"
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq DESC",
            (_ECONOMIC_OBLIGATION_KIND,),
        ).fetchall()
        for (payload_json,) in rows:
            decoded = json.loads(payload_json)["payload"]
            if decoded.get("idempotency_key") == idempotency_key:
                return EconomicObligationRecord.model_validate(decoded)
        return None

    def _check_obligation_expiry(self, *, reservation_id: str) -> None:
        if self.time_service.health_state is not HealthState.TRUSTED:
            return
        state = self.projection.reservation_state(reservation_id)
        if state not in _OVERDUE_ELIGIBLE_STATES:
            return
        occupancy_seq = self.projection.reservation_last_seq(reservation_id)
        marker_key = (reservation_id, occupancy_seq)
        now_ms = self.monotonic_source.now_ms()
        first_observed_ms = self._wait_start_ms.get(marker_key)
        if first_observed_ms is None:
            self._wait_start_ms[marker_key] = now_ms
            return
        if now_ms - first_observed_ms < self.release_proof_wait_ms:
            return
        if self._overdue_already_recorded(reservation_id, occupancy_seq=occupancy_seq):
            return
        self.evidence_store.append(
            {
                "reservation_id": reservation_id,
                "occupancy_seq": occupancy_seq,
                "state": state.value,
                "waited_ms": now_ms - first_observed_ms,
            },
            kind=RELEASE_PROOF_OVERDUE_KIND,
            record_class=RELEASE_PROOF_OVERDUE_KIND,
        )

    def _overdue_already_recorded(
        self, reservation_id: str, *, occupancy_seq: int | None
    ) -> bool:
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?",
            (RELEASE_PROOF_OVERDUE_KIND,),
        ).fetchall()
        for (payload_json,) in rows:
            decoded = json.loads(payload_json)["payload"]
            if (
                decoded.get("reservation_id") == reservation_id
                and decoded.get("occupancy_seq") == occupancy_seq
            ):
                return True
        return False
