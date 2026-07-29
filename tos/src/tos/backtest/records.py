"""D-E3-local harness records — fill, halt, and wiring-trace entries (design #33 §1.2/§4.3).

What a slice-1 backtest is allowed to produce is enumerated by design #33 §1.2: (a) an event-flow
trace, (b) fail-closed halt records, (c) a single-entry fill record carrying the quantity and the
**D-E3-local** execution price, and (d) the out-of-tree differential wiring-agreement artifact.
Every one of them is a *mechanism / parity demonstration* and **closes no EV**.

Two structural positions carry the design's weight:

* **the execution price lives here, not in the engine** (design #33 §4.3 B4).
  ``EgressResultPayload`` is quantity-only — its fields are ``instrument_key`` / ``attempt_id`` /
  ``kind`` / ``filled_quantity`` / ``remaining_quantity`` / ``reference`` (``records.py:186-191``),
  with no price — and ``ProvisionalReservation`` holds no PnL either (``records.py:389-409``). The
  engine core is a capacity/commitment machine, not a position ledger, so slippage, cost, and the
  fill price are D-E3's own record. Adding a price field to the engine would be over-realization of
  a ratified boundary (design #33 §0.2-1/§0.2-3).
* **no performance surface** (design #33 §1.2 B1). Every record here runs its own field names
  through :func:`~tos.backtest._base.seal_performance_surface`, so a ``sharpe_ratio``,
  ``net_return``, or ``admissibility_verdict`` field makes the model unconstructable. A single-run
  slice backtest is disqualified by ADR-DEV-010 §8:191-192 — the harness's answer is to have
  nowhere to put the claim, not a disclaimer promising not to make it. That extends to the raw
  material: a settlement close is recorded because the *fill* needs its own basis, and downstream
  mark-to-market reconstruction from it is explicitly outside the harness's claim and is itself a
  new single-run backtest, equally disqualified (design #33 §1.2 MINOR-1).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #33 §0.3). No clock, no RNG.
"""

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

#: The label every D-E3 artifact carries. Not a disclaimer standing in for a structural seal — the
#: structural seals are the absent performance fields and the absent authority — but the honest
#: regime tag the series requires on every provisional artifact (design #33 §1.1/§0.4).
DEMONSTRATION_LABEL = "MECHANISM_PARITY_DEMONSTRATION_CLOSES_NO_EV"


class LocalFillRecord(FrozenModel):
    """One D-E3-local fill record — the only place an execution price exists (design #33 §4.3).

    ⚠ **Synthetic band, not a broker.** The magnitudes and the price come from the injected
    deterministic fill model, never from a venue; ``quantity_provenance`` records that the magnitude
    is a *scenario parameter*, because slice #1's flow carries no concrete quantity at all
    (``proposal.py:120-135`` has no share count and no price; concrete construction is a provisional
    stand-in). Labelling it is the difference between an honest harness output and a fabricated
    execution report.

    Cost realism (ADR-DEV-010 §7:159-161 / BTE-INV-002) is realized *structurally* here in the sense
    that slippage and cost are applied from injected parameters and are never optimistic — the cost
    **apparatus definition** itself is RFC-005 §9 / RFC-006 §11's to own (ADR §9.5:211), and D-E3
    only consumes it.
    """

    attempt_id: str
    instrument_key: InstrumentKey
    scenario_id: ScenarioId | None = None
    #: The bar whose ``DECISION_TICK`` produced the attempt (the decision coordinate).
    decision_bar_index: int
    #: The bar the fill settles on (equal to, or after, the decision bar — §3.6 execution realism).
    settlement_bar_index: int
    settlement_status: SettlementStatus
    result_kind: EgressResultKind | None = None
    side: FillSide
    quantity_provenance: QuantityProvenance = QuantityProvenance.SCENARIO_PARAMETER
    requested_quantity: CanonicalDecimal | None = None
    filled_quantity: CanonicalDecimal | None = None
    remaining_quantity: CanonicalDecimal | None = None
    #: The settlement bar's chosen basis print, before slippage.
    reference_price: CanonicalDecimal | None = None
    #: The D-E3-local execution price — reference price plus the injected slippage component.
    execution_price: CanonicalDecimal | None = None
    slippage_component: CanonicalDecimal | None = None
    cost_component: CanonicalDecimal | None = None
    #: The settlement bar's close, recorded as raw material only (design #33 §1.2 MINOR-1).
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
    """One fail-closed stop, recorded with its reason (design #33 §5.1 row 5 / §8-10).

    RFC-010 §6 원칙 4:193-196 makes failure paths first-class: "passing the nominal path proves
    nothing about failure". A halt without a recorded reason is not a fail-closed stop, it is a
    silent one — so ``halt_reason`` is required and the engine's own closed
    :class:`~tos.engine.HaltReason` vocabulary is reused rather than re-authored.
    """

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
    """One event of the wiring trace — what the core did with one yielded event (design #33 §6.1).

    The trace is the harness's serialisable artifact: the out-of-tree differential comparator reads
    *this*, and no process ever imports both ``tos.backtest`` and ``shared.backtest`` (design #33
    §6.1 alternative B). Its scope is **structural wiring**, not numerics and never performance:
    bar cadence ↔ tick emission, the structural path to a proposal-emit versus a no-action, and the
    fail-closed halt points (design #33 §6.2 ①). The numeric entry-decision agreement layer is gated
    on D-E2's value surface (§6.2 ②) and is not claimed here.

    ``yield_sequence`` is the driver's global yield-order coordinate, which is also what the event's
    ``source_native_sequence`` carries — the trace therefore records processing order directly,
    decoupled from ``bar_index`` (design #33 §3.4).
    """

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
    """The ordered wiring trace of one run (design #33 §6.1) — the oracle's input artifact.

    Ordered by construction and re-checked here: the entries' ``yield_sequence`` values must be
    strictly increasing, which is the trace-level restatement of the design's ordering invariant
    (좌표 순서 ≡ 처리 순서, design #33 §3.4). A trace whose order is not the processing order would
    make every downstream comparison meaningless.
    """

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
