"""D-E3-local harness records — fill, halt, and wiring-trace entries (design #33 §1.2/§4.3)."""

from __future__ import annotations

from pydantic import model_validator

from tos.backtest._base import (
    BacktestIntegrityError,
    CanonicalDecimal,
    FrozenModel,
    seal_performance_surface,
)
from tos.backtest.vocabulary import (
    FillSide,
    QuantityProvenance,
    ScenarioId,
    SettlementStatus,
)
from tos.engine import (
    CommitmentStep,
    EgressKnowledge,
    EgressResultKind,
    EventKind,
    HaltReason,
    InstrumentKey,
    OrderingAdmission,
)
from tos.ordering import OrderingEvent
from tos.rcl import CapacityState

__all__ = [
    "DEMONSTRATION_LABEL",
    "HaltRecord",
    "LocalFillRecord",
    "TraceEntry",
    "WiringTrace",
]

DEMONSTRATION_LABEL = "MECHANISM_PARITY_DEMONSTRATION_CLOSES_NO_EV"


class LocalFillRecord(FrozenModel):
    """One D-E3-local fill record — the only place an execution price exists (design #33 §4.3)."""

    attempt_id: str
    instrument_key: InstrumentKey
    scenario_id: ScenarioId | None = None
    decision_bar_index: int
    settlement_bar_index: int
    settlement_status: SettlementStatus
    result_kind: EgressResultKind | None = None
    side: FillSide
    quantity_provenance: QuantityProvenance = QuantityProvenance.SCENARIO_PARAMETER
    requested_quantity: CanonicalDecimal | None = None
    filled_quantity: CanonicalDecimal | None = None
    remaining_quantity: CanonicalDecimal | None = None
    reference_price: CanonicalDecimal | None = None
    execution_price: CanonicalDecimal | None = None
    slippage_component: CanonicalDecimal | None = None
    cost_component: CanonicalDecimal | None = None
    settlement_bar_close: CanonicalDecimal | None = None
    label: str = DEMONSTRATION_LABEL

    @model_validator(mode="after")
    def _fill_record_is_well_formed(self) -> LocalFillRecord:
        """Enforce the structural seals: no performance surface, causal settlement, honest ∅."""
        seal_performance_surface(type(self).__name__, type(self).model_fields)
        if not self.attempt_id.strip():
            raise BacktestIntegrityError(
                "LocalFillRecord.attempt_id must be concrete — a fill with no attempt identity "
                "cannot be correlated to the order it settles (design #31 §2.1(ii))"
            )
        if self.settlement_bar_index < self.decision_bar_index:
            raise BacktestIntegrityError(
                f"settlement_bar_index ({self.settlement_bar_index}) precedes decision_bar_index "
                f"({self.decision_bar_index}) — a fill settles at or after the decision that "
                "produced it; the reverse would be a fabricated execution (design #33 §3.6)"
            )
        if self.settlement_status is SettlementStatus.UNSETTLED_AT_STREAM_END:
            if self.result_kind is not None or self.filled_quantity is not None:
                raise BacktestIntegrityError(
                    "an unsettled fill carries no result kind and no magnitude — the bar stream "
                    "ended before its settlement bar arrived, and inventing a settlement would "
                    "manufacture data the run never had (design #33 §4.1)"
                )
        elif self.result_kind is None:
            raise BacktestIntegrityError(
                "a SETTLED fill must name the result kind it settled to — an unnamed settlement "
                "is a silent one (design #33 §4.2)"
            )
        if self.execution_price is not None and self.execution_price <= 0:
            raise BacktestIntegrityError(
                f"LocalFillRecord.execution_price must be positive (got {self.execution_price})"
            )
        return self


class HaltRecord(FrozenModel):
    """One fail-closed stop, recorded with its reason (design #33 §5.1 row 5 / §8-10)."""

    yield_sequence: int
    event_kind: EventKind
    bar_index: int | None = None
    instrument_key: InstrumentKey
    halt_reason: HaltReason
    halt_step: CommitmentStep | None = None
    detail: str | None = None
    label: str = DEMONSTRATION_LABEL

    @model_validator(mode="after")
    def _halt_record_is_well_formed(self) -> HaltRecord:
        """Seal the performance surface and require a non-negative yield coordinate."""
        seal_performance_surface(type(self).__name__, type(self).model_fields)
        if self.yield_sequence < 0:
            raise BacktestIntegrityError(
                f"HaltRecord.yield_sequence must be non-negative (got {self.yield_sequence})"
            )
        return self


class TraceEntry(FrozenModel):
    """One event of the wiring trace — what the core did with one yielded event (design #33 §6.1)."""

    yield_sequence: int
    event_kind: EventKind
    bar_index: int | None = None
    instrument_key: InstrumentKey
    ordering_admission: OrderingAdmission
    reference: OrderingEvent
    halt_reason: HaltReason | None = None
    halt_step: CommitmentStep | None = None
    handed_off: bool = False
    attempt_id: str | None = None
    egress_result_kind: EgressResultKind | None = None
    capacity_state: CapacityState | None = None
    knowledge: EgressKnowledge | None = None
    proposal_digest: str | None = None
    outcome_digest: str | None = None
    label: str = DEMONSTRATION_LABEL

    @model_validator(mode="after")
    def _trace_entry_is_well_formed(self) -> TraceEntry:
        """Seal the performance surface; a trace entry never carries an outcome judgement."""
        seal_performance_surface(type(self).__name__, type(self).model_fields)
        if self.yield_sequence < 0:
            raise BacktestIntegrityError(
                f"TraceEntry.yield_sequence must be non-negative (got {self.yield_sequence})"
            )
        return self


class WiringTrace(FrozenModel):
    """The ordered wiring trace of one run (design #33 §6.1) — the oracle's input artifact."""

    continuity_id: str
    entries: tuple[TraceEntry, ...] = ()
    label: str = DEMONSTRATION_LABEL

    @model_validator(mode="after")
    def _trace_is_ordered(self) -> WiringTrace:
        """Seal the performance surface and enforce strictly increasing yield coordinates."""
        seal_performance_surface(type(self).__name__, type(self).model_fields)
        if not self.continuity_id.strip():
            raise BacktestIntegrityError(
                "WiringTrace.continuity_id must be concrete — ordering coordinates are only "
                "comparable within one continuity (ordering/_ordering.py:112-127)"
            )
        previous: int | None = None
        for entry in self.entries:
            if previous is not None and entry.yield_sequence <= previous:
                raise BacktestIntegrityError(
                    f"WiringTrace entries must strictly increase in yield_sequence "
                    f"({previous} -> {entry.yield_sequence}) — the trace order **is** the "
                    "processing order (design #33 §3.4)"
                )
            previous = entry.yield_sequence
        return self
