"""The deterministic paper fill model — a ``Transmit`` band with zero RNG (design #33 §4)."""

from __future__ import annotations

from collections.abc import Iterable, Sized
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable

from pydantic import model_validator

from tos.backtest._base import (
    BacktestIntegrityError,
    CanonicalDecimal,
    FrozenModel,
    seal_performance_surface,
)
from tos.backtest.bars import Bar, settlement_price
from tos.backtest.records import LocalFillRecord
from tos.backtest.vocabulary import (
    ExecutionPriceBasis,
    FillMode,
    FillSide,
    QuantityProvenance,
    ScenarioId,
    SettlementPolicy,
    SettlementStatus,
    settleable_result_kinds,
)
from tos.engine import (
    AttemptRequest,
    EgressResultKind,
    EgressResultPayload,
    InstrumentKey,
    SendHandoff,
)

__all__ = [
    "DeterministicFillModel",
    "EgressResultSource",
    "FillParameters",
    "GatewayResultReinjector",
    "RetainedEgressResults",
    "SettledFill",
    "StagedFill",
]

_BASIS_POINT_DENOMINATOR = Decimal(10000)


class FillParameters(FrozenModel):
    """Every injected scalar the fill model consumes (design #33 §10 — hardcoded numbers: 0)."""

    mode: FillMode
    side: FillSide
    settlement: SettlementPolicy = SettlementPolicy.SAME_BAR
    price_basis: ExecutionPriceBasis = ExecutionPriceBasis.CLOSE
    scenario_quantity: CanonicalDecimal | None = None
    participation_cap_fraction: CanonicalDecimal | None = None
    slippage_bps: CanonicalDecimal | None = None
    cost_per_unit: CanonicalDecimal | None = None
    limit_reference_price: CanonicalDecimal | None = None
    price_band_fraction: CanonicalDecimal | None = None

    @model_validator(mode="after")
    def _parameters_are_complete_for_the_mode(self) -> FillParameters:
        """Require exactly the parameters the mode consumes — absence is never a default."""
        seal_performance_surface(type(self).__name__, type(self).model_fields)
        settle_only = (
            "scenario_quantity",
            "participation_cap_fraction",
            "slippage_bps",
            "cost_per_unit",
            "limit_reference_price",
            "price_band_fraction",
        )
        if self.mode is not FillMode.SETTLE:
            present = [name for name in settle_only if getattr(self, name) is not None]
            if present:
                raise BacktestIntegrityError(
                    f"FillParameters mode={self.mode} must carry no settlement magnitude or price "
                    f"parameter (got {present}) — ACK / UNKNOWN / TIMEOUT carry no fill magnitude "
                    "(records.py:201-207; design #33 §4.2)"
                )
            return self
        missing = [name for name in settle_only if getattr(self, name) is None]
        if missing:
            raise BacktestIntegrityError(
                f"FillParameters mode=SETTLE requires every injected settlement parameter (missing "
                f"{missing}) — an unestablished bound is not a bound, and defaulting one here "
                "would be a hardcoded number (design #33 §10)"
            )
        if self.scenario_quantity is None or self.scenario_quantity <= 0:
            raise BacktestIntegrityError(
                f"FillParameters.scenario_quantity must be positive (got {self.scenario_quantity})"
            )
        cap = self.participation_cap_fraction
        if cap is None or cap <= 0 or cap > 1:
            raise BacktestIntegrityError(
                f"FillParameters.participation_cap_fraction must lie in (0, 1] (got {cap}) — a cap "
                "above 1 would let the model fill more than the settlement bar traded"
            )
        for name in ("slippage_bps", "cost_per_unit", "price_band_fraction"):
            value: CanonicalDecimal | None = getattr(self, name)
            if value is None or value < 0:
                raise BacktestIntegrityError(
                    f"FillParameters.{name} must be non-negative (got {value}) — a negative "
                    "slippage / cost would be an optimistic execution assumption, which is an "
                    "ADR-DEV-010 §8:189-190 disqualifier"
                )
        if self.limit_reference_price is None or self.limit_reference_price <= 0:
            raise BacktestIntegrityError(
                "FillParameters.limit_reference_price must be positive (got "
                f"{self.limit_reference_price})"
            )
        return self


@dataclass(frozen=True)
class StagedFill:
    """A pending fill, staged at hand-off and awaiting its settlement bar (design #33 §4.1)."""

    attempt_id: str
    instrument_key: InstrumentKey
    decision_bar_index: int
    settlement_bar_index: int
    parameters: FillParameters


@dataclass(frozen=True)
class SettledFill:
    """A settled fill — the engine payload to re-inject plus the D-E3-local record (§4.3)."""

    payload: EgressResultPayload
    record: LocalFillRecord


class _SettledEgressResult(Protocol):
    """The minimal shape the driver reads off one settled item (``driver.py:429``)."""

    @property
    def payload(self) -> EgressResultPayload:
        """The engine payload the driver re-injects as an ``EGRESS_RESULT`` event."""


@runtime_checkable
class EgressResultSource(Protocol):
    """The exact surface :class:`~tos.backtest.driver.BacktestDriver` drains (design #35 §2.1)."""

    def bind_settlement_context(self, bar: Bar) -> None:
        """Bind the bar whose ``DECISION_TICK`` the driver is about to yield."""

    def settle_due(self, bar: Bar) -> Iterable[_SettledEgressResult]:
        """The results whose settlement coordinate is ``bar`` — re-injected by the driver."""

    def unsettled_records(self) -> tuple[LocalFillRecord, ...]:
        """The D-E3-local records for anything still unsettled when the stream ends."""

    @property
    def records(self) -> tuple[LocalFillRecord, ...]:
        """The D-E3-local fill records produced so far, in settlement order."""

    @property
    def handoffs(self) -> Sized:
        """Every attempt handed to this source — the driver takes only its length."""


@runtime_checkable
class RetainedEgressResults(Protocol):
    """The send boundary's retained-result surface, declared **locally** (design #35 §2.1)."""

    @property
    def results(self) -> tuple[EgressResultPayload, ...]:
        """Every egress result the send boundary has produced so far, in production order."""


@dataclass(frozen=True)
class _RetainedResult:
    """One retained gateway result, presented on the shape the driver drains."""

    payload: EgressResultPayload


class GatewayResultReinjector:
    """Re-inject a send boundary's retained results into the driver (design #35 §2.1)."""

    def __init__(self, *, source: RetainedEgressResults) -> None:
        """Wire the adapter over a retained-result source."""
        self._source = source
        self._drained = 0

    @property
    def drained(self) -> int:
        """How many retained results have already been handed to the driver (observation)."""
        return self._drained

    def bind_settlement_context(self, bar: Bar) -> None:
        """Accept the driver's settlement binding and do nothing with it."""

    def settle_due(self, bar: Bar) -> tuple[_RetainedResult, ...]:
        """Hand over every result the source retained since the last drain."""
        del bar
        retained = self._source.results
        produced = retained[self._drained :]
        self._drained = len(retained)
        return tuple(_RetainedResult(payload=payload) for payload in produced)

    def unsettled_records(self) -> tuple[LocalFillRecord, ...]:
        """Always ``()`` — the adapter owns no D-E3-local fill record (design #35 §7-2)."""
        return ()

    @property
    def records(self) -> tuple[LocalFillRecord, ...]:
        """Always ``()`` — see :meth:`unsettled_records`."""
        return ()

    @property
    def handoffs(self) -> tuple[EgressResultPayload, ...]:
        """The retained results, exposed only so the driver can take their count."""
        return tuple(self._source.results)


class DeterministicFillModel:
    """⚠ NON-AUTHORITATIVE synthetic ``Transmit`` band — stages fills, sends nothing (§4.1)."""

    def __init__(
        self,
        *,
        instrument_key: InstrumentKey,
        parameters: FillParameters,
        scenario_id: ScenarioId | None = None,
    ) -> None:
        """Wire the fill band."""
        self._instrument_key = instrument_key
        self._parameters = parameters
        self._scenario_id = scenario_id
        self._context_bar: Bar | None = None
        self._pending: list[StagedFill] = []
        self._handoffs: list[AttemptRequest] = []
        self._records: list[LocalFillRecord] = []

    @property
    def parameters(self) -> FillParameters:
        """The injected parameters (immutable)."""
        return self._parameters

    @property
    def handoffs(self) -> tuple[AttemptRequest, ...]:
        """Every attempt handed to this band, in order — nothing was ever transmitted."""
        return tuple(self._handoffs)

    @property
    def records(self) -> tuple[LocalFillRecord, ...]:
        """Every D-E3-local fill record produced so far, in settlement order."""
        return tuple(self._records)

    @property
    def pending(self) -> tuple[StagedFill, ...]:
        """The staged fills still awaiting their settlement bar."""
        return tuple(self._pending)

    def bind_settlement_context(self, bar: Bar) -> None:
        """Bind the current bar as the settlement context for the tick about to be yielded."""
        self._context_bar = bar

    def __call__(self, attempt: AttemptRequest) -> SendHandoff:
        """Stage a synthetic fill for ``attempt`` and return the hand-off at once."""
        bar = self._context_bar
        if bar is None:
            raise BacktestIntegrityError(
                "no settlement context is bound — the driver binds the current bar before every "
                "tick, and a hand-off without one has no settlement coordinate (design #33 §4.1)"
            )
        offset = 1 if self._parameters.settlement is SettlementPolicy.NEXT_BAR else 0
        self._handoffs.append(attempt)
        self._pending.append(
            StagedFill(
                attempt_id=attempt.attempt_id,
                instrument_key=self._instrument_key,
                decision_bar_index=bar.bar_index,
                settlement_bar_index=bar.bar_index + offset,
                parameters=self._parameters,
            )
        )
        return SendHandoff(
            accepted_for_transmission=True, handoff_reference=attempt.attempt_id
        )

    def settle_due(self, bar: Bar) -> tuple[SettledFill, ...]:
        """Settle every staged fill whose settlement bar is ``bar`` (design #33 §4.1)."""
        due = [
            staged
            for staged in self._pending
            if staged.settlement_bar_index == bar.bar_index
        ]
        if not due:
            return ()
        self._pending = [
            staged
            for staged in self._pending
            if staged.settlement_bar_index != bar.bar_index
        ]
        settled = tuple(self._settle_one(staged, bar) for staged in due)
        self._records.extend(item.record for item in settled)
        return settled

    def unsettled_records(self) -> tuple[LocalFillRecord, ...]:
        """Record every still-pending fill as ``UNSETTLED_AT_STREAM_END`` (design #33 §4.1)."""
        return tuple(
            LocalFillRecord(
                attempt_id=staged.attempt_id,
                instrument_key=staged.instrument_key,
                scenario_id=self._scenario_id,
                decision_bar_index=staged.decision_bar_index,
                settlement_bar_index=staged.settlement_bar_index,
                settlement_status=SettlementStatus.UNSETTLED_AT_STREAM_END,
                side=staged.parameters.side,
                quantity_provenance=QuantityProvenance.SCENARIO_PARAMETER,
                requested_quantity=staged.parameters.scenario_quantity,
            )
            for staged in self._pending
        )

    def _settle_one(self, staged: StagedFill, bar: Bar) -> SettledFill:
        """Resolve one staged fill against its settlement bar — pure, RNG-free (design #33 §4.2)."""
        parameters = staged.parameters
        if parameters.mode is FillMode.ACKNOWLEDGE:
            return self._non_magnitude_fill(staged, bar, EgressResultKind.ACK)
        if parameters.mode is FillMode.REPORT_UNKNOWN:
            return self._non_magnitude_fill(staged, bar, EgressResultKind.UNKNOWN)
        if parameters.mode is FillMode.REPORT_TIMEOUT:
            return self._non_magnitude_fill(staged, bar, EgressResultKind.TIMEOUT)
        if parameters.mode is FillMode.REPORT_CANCEL_ACK:
            return self._non_magnitude_fill(staged, bar, EgressResultKind.CANCEL_ACK)
        if parameters.mode is FillMode.REPORT_EXPIRED:
            return self._non_magnitude_fill(staged, bar, EgressResultKind.EXPIRED)
        return self._settled_fill(staged, bar)

    def _non_magnitude_fill(
        self, staged: StagedFill, bar: Bar, kind: EgressResultKind
    ) -> SettledFill:
        """Build an ACK / UNKNOWN / TIMEOUT result — no magnitude, no execution price."""
        self._assert_kind_allowed(staged, kind)
        return SettledFill(
            payload=EgressResultPayload(
                instrument_key=staged.instrument_key,
                attempt_id=staged.attempt_id,
                kind=kind,
            ),
            record=LocalFillRecord(
                attempt_id=staged.attempt_id,
                instrument_key=staged.instrument_key,
                scenario_id=self._scenario_id,
                decision_bar_index=staged.decision_bar_index,
                settlement_bar_index=staged.settlement_bar_index,
                settlement_status=SettlementStatus.SETTLED,
                result_kind=kind,
                side=staged.parameters.side,
                settlement_bar_close=bar.close_price,
            ),
        )

    def _settled_fill(self, staged: StagedFill, bar: Bar) -> SettledFill:
        """Build a REJECT / FULL_FILL / PARTIAL_FILL result from the settlement bar (§4.2/§4.3)."""
        parameters = staged.parameters
        basis = settlement_price(
            bar, use_open=parameters.price_basis is ExecutionPriceBasis.OPEN
        )
        reference: Decimal = parameters.limit_reference_price  # type: ignore[assignment]
        band: Decimal = parameters.price_band_fraction  # type: ignore[assignment]
        if abs(basis - reference) > reference * band:
            self._assert_kind_allowed(staged, EgressResultKind.REJECT)
            return SettledFill(
                payload=EgressResultPayload(
                    instrument_key=staged.instrument_key,
                    attempt_id=staged.attempt_id,
                    kind=EgressResultKind.REJECT,
                ),
                record=LocalFillRecord(
                    attempt_id=staged.attempt_id,
                    instrument_key=staged.instrument_key,
                    scenario_id=self._scenario_id,
                    decision_bar_index=staged.decision_bar_index,
                    settlement_bar_index=staged.settlement_bar_index,
                    settlement_status=SettlementStatus.SETTLED,
                    result_kind=EgressResultKind.REJECT,
                    side=parameters.side,
                    requested_quantity=parameters.scenario_quantity,
                    reference_price=basis,
                    settlement_bar_close=bar.close_price,
                ),
            )

        requested: Decimal = parameters.scenario_quantity  # type: ignore[assignment]
        cap_fraction: Decimal = parameters.participation_cap_fraction  # type: ignore[assignment]
        available = bar.volume * cap_fraction
        if available <= 0:
            raise BacktestIntegrityError(
                f"the settlement bar {bar.bar_index} offers no participation capacity "
                f"(volume={bar.volume}, cap={cap_fraction}) — slice #1 does not invent a result "
                "kind for an unfillable bar; the closed EgressResultKind vocabulary has no member "
                "for 'nothing happened' and fabricating one would be a phantom (design #33 §4.2)"
            )
        filled = requested if requested <= available else available
        remaining = requested - filled
        kind = (
            EgressResultKind.PARTIAL_FILL
            if remaining > 0
            else EgressResultKind.FULL_FILL
        )
        self._assert_kind_allowed(staged, kind)

        sign = Decimal(1) if parameters.side is FillSide.BUY else Decimal(-1)
        slippage_bps: Decimal = parameters.slippage_bps  # type: ignore[assignment]
        slippage = basis * slippage_bps / _BASIS_POINT_DENOMINATOR
        execution = basis + sign * slippage
        if execution <= 0:
            raise BacktestIntegrityError(
                f"the injected slippage ({slippage_bps} bps) drives the execution price to "
                f"{execution} on bar {bar.bar_index} — a non-positive execution price is not a "
                "price (design #33 §4.3)"
            )
        cost_per_unit: Decimal = parameters.cost_per_unit  # type: ignore[assignment]
        return SettledFill(
            payload=EgressResultPayload(
                instrument_key=staged.instrument_key,
                attempt_id=staged.attempt_id,
                kind=kind,
                filled_quantity=filled,
                remaining_quantity=remaining,
            ),
            record=LocalFillRecord(
                attempt_id=staged.attempt_id,
                instrument_key=staged.instrument_key,
                scenario_id=self._scenario_id,
                decision_bar_index=staged.decision_bar_index,
                settlement_bar_index=staged.settlement_bar_index,
                settlement_status=SettlementStatus.SETTLED,
                result_kind=kind,
                side=parameters.side,
                requested_quantity=requested,
                filled_quantity=filled,
                remaining_quantity=remaining,
                reference_price=basis,
                execution_price=execution,
                slippage_component=slippage,
                cost_component=cost_per_unit * filled,
                settlement_bar_close=bar.close_price,
            ),
        )

    @staticmethod
    def _assert_kind_allowed(staged: StagedFill, kind: EgressResultKind) -> None:
        """Positive-membership check of a derived kind against its mode's closed set (§4.2)."""
        allowed = settleable_result_kinds(staged.parameters.mode)
        if kind not in allowed:
            raise BacktestIntegrityError(
                f"fill mode {staged.parameters.mode} may not produce {kind} (allowed: "
                f"{sorted(member.value for member in allowed)}) — a mode that could produce any "
                "kind would make the injected mode meaningless (design #33 §4.2)"
            )
