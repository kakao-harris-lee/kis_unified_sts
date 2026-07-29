"""The deterministic paper fill model — a ``Transmit`` band with zero RNG (design #33 §4).

**The fill model is not a sender.** It implements the engine's injected
:class:`~tos.engine.Transmit` interface (``sequencer.py:103-116``), which RFC-002 §10.8:763 requires
*not* be a general-purpose live-order method exposed to a backtest. What it does is stage a
synthetic result; the actual send boundary is D-E4's (design #33 §4.1).

**Transmit does not return a fill** (design #33 §16 재실측 2). ``transmit(attempt)`` returns a
:class:`~tos.engine.SendHandoff` — a hand-off acknowledgement — and the *order result* arrives later
as a separate ``EGRESS_RESULT`` event. The model therefore carries two responsibilities:

1. **stage** — on the hand-off, record the pending fill against the settlement coordinate the driver
   bound synchronously just before the tick (design #33 §4.1);
2. **settle** — when the driver reaches the settlement bar, resolve the pending fill into an
   ``EgressResultPayload`` plus a D-E3-local :class:`~tos.backtest.records.LocalFillRecord`.

**Correlation is trivial, and that is NIT-3's gift** (design #33 §4.5). ``AttemptRequest`` carries
digests only — no economics — so the model must know *which* order a fill belongs to. The
at-most-one retention guarantees a scope holds at most one outstanding attempt (``state.py:163-177``
/ ``:197-229``), so the correlation is unique without any order book or matching engine. The
无-release constraint is here an asset, not a limitation.

**Determinism** (design #33 §4.4). There is no ``random`` / ``secrets`` / ``uuid`` / clock anywhere:
every decision is a pure function of ``(settlement bar, injected parameters)``. The seed slot
RFC-003 §10:360-363 would require for a *stochastic* slippage model is a **forward seam and stays
unused**, but the discipline is stated now: a future stochastic model must be reproducible from a
recorded seed and recorded response, and that artifact must be part of the decision evidence.

**Structural derivation over self-report** (design #33 §4.2). The model never *declares* a partial:
it computes the filled and remaining magnitudes and lets them decide, and
``EgressResultPayload._fill_shape_consistent`` (``records.py:193-230``) independently re-derives the
same distinction and rejects a contradiction. Two independent derivations, no label to trust.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #33 §0.3). No clock, no RNG, no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

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

__all__ = ["DeterministicFillModel", "FillParameters", "SettledFill", "StagedFill"]

#: Basis-point denominator. A named constant, not a magic literal: the *values* (slippage bps, caps)
#: are all injected (design #33 §10), while this is the unit definition the injected value is
#: expressed in.
_BASIS_POINT_DENOMINATOR = Decimal(10000)


class FillParameters(FrozenModel):
    """Every injected scalar the fill model consumes (design #33 §10 — hardcoded numbers: 0).

    ⚠ **Provisional values.** The cost apparatus these parameterise is defined by RFC-005 §9 /
    RFC-006 §11 (ADR-DEV-010 §9.5:211), not here, and it is not yet defined — so the injected
    slippage / participation / cost values are provisional and every output built on them is
    provisional (design #33 §1.1/§10).

    The magnitude is a **scenario parameter**: slice #1's flow carries no concrete quantity
    (``proposal.py:120-135``; concrete Order Construction is a provisional stand-in), so pretending
    the quantity was derived from the decision would be a phantom (design #33 §4.3).

    ∅ discipline: only :attr:`FillMode.SETTLE` carries a magnitude, mirroring
    ``EgressResultPayload``'s own rule that non-fill kinds carry none (``records.py:201-207``).
    """

    mode: FillMode
    side: FillSide
    settlement: SettlementPolicy = SettlementPolicy.SAME_BAR
    price_basis: ExecutionPriceBasis = ExecutionPriceBasis.CLOSE
    #: The scenario's requested magnitude (``SETTLE`` only).
    scenario_quantity: CanonicalDecimal | None = None
    #: The injected participation cap as a fraction of the settlement bar's volume (``SETTLE``).
    participation_cap_fraction: CanonicalDecimal | None = None
    #: The injected slippage in basis points, always applied **against** the taker (``SETTLE``).
    slippage_bps: CanonicalDecimal | None = None
    #: The injected per-unit cost (``SETTLE``).
    cost_per_unit: CanonicalDecimal | None = None
    #: The injected reference price the deterministic rejection predicate is measured against.
    limit_reference_price: CanonicalDecimal | None = None
    #: The injected acceptable fractional deviation from ``limit_reference_price``; a settlement
    #: basis outside the band is a deterministic ``REJECT`` (design #33 §4.2 "주입 거부 조건").
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


class DeterministicFillModel:
    """⚠ NON-AUTHORITATIVE synthetic ``Transmit`` band — stages fills, sends nothing (§4.1).

    Lifecycle, driven entirely by the driver so the whole run stays synchronous and deterministic:

    1. :meth:`bind_settlement_context` — the driver binds the current bar **before** yielding that
       bar's tick, because ``AttemptRequest`` carries no economics and the model cannot read the
       settlement bar off it (design #33 §4.1 "정산 컨텍스트 바인딩");
    2. ``__call__`` — the engine's step-14 hand-off stages the pending fill and returns a
       :class:`~tos.engine.SendHandoff` immediately (never blocking, never sending);
    3. :meth:`settle_due` — the driver drains the fills whose settlement bar has arrived;
    4. :meth:`unsettled_records` — anything still pending when the stream ends is recorded as
       ``UNSETTLED_AT_STREAM_END``, never as a fabricated settlement.
    """

    def __init__(
        self,
        *,
        instrument_key: InstrumentKey,
        parameters: FillParameters,
        scenario_id: ScenarioId | None = None,
    ) -> None:
        """Wire the fill band.

        Args:
            instrument_key: The scope every staged fill is bound to.
            parameters: The injected deterministic parameters.
            scenario_id: The mandated scenario this band realizes, recorded on each fill record.
        """
        self._instrument_key = instrument_key
        self._parameters = parameters
        self._scenario_id = scenario_id
        self._context_bar: Bar | None = None
        self._pending: list[StagedFill] = []
        self._handoffs: list[AttemptRequest] = []
        self._records: list[LocalFillRecord] = []

    # -- observation ---------------------------------------------------------

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

    # -- driver-bound lifecycle ----------------------------------------------

    def bind_settlement_context(self, bar: Bar) -> None:
        """Bind the current bar as the settlement context for the tick about to be yielded.

        Args:
            bar: The bar whose ``DECISION_TICK`` the driver is about to yield.
        """
        self._context_bar = bar

    def __call__(self, attempt: AttemptRequest) -> SendHandoff:
        """Stage a synthetic fill for ``attempt`` and return the hand-off at once.

        Args:
            attempt: The engine's step-12 content-addressed attempt request.

        Returns:
            The :class:`~tos.engine.SendHandoff`. Its polarity is positive
            (``accepted_for_transmission is True`` only records an accepted hand-off), and the
            reservation projection is already conservatively ``POTENTIALLY_LIVE`` before this call
            (``sequencer.py:531``; ADR-002-002 §11.4 step 16).

        Raises:
            BacktestIntegrityError: If no settlement context is bound — a fill with no settlement
                coordinate is not a fill. The sequencer converts the raise into a recorded
                ``TRANSMIT_RAISED`` halt with the reservation left ``POTENTIALLY_LIVE``, which is
                the fail-closed outcome (``sequencer.py:534-545``).
        """
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
        """Settle every staged fill whose settlement bar is ``bar`` (design #33 §4.1).

        Args:
            bar: The bar the driver has just ticked.

        Returns:
            The settled fills, in staging order. Fills whose settlement bar has not arrived stay
            pending — the model never settles early, because settling on the decision bar when the
            injected policy says ``NEXT_BAR`` would silently change the execution model.
        """
        due = [
            staged for staged in self._pending if staged.settlement_bar_index == bar.bar_index
        ]
        if not due:
            return ()
        self._pending = [
            staged for staged in self._pending if staged.settlement_bar_index != bar.bar_index
        ]
        settled = tuple(self._settle_one(staged, bar) for staged in due)
        self._records.extend(item.record for item in settled)
        return settled

    def unsettled_records(self) -> tuple[LocalFillRecord, ...]:
        """Record every still-pending fill as ``UNSETTLED_AT_STREAM_END`` (design #33 §4.1).

        Returns:
            One record per pending fill, carrying **no** result kind and **no** magnitude. The bar
            stream ended before their settlement bar arrived; inventing a settlement price from a
            bar that does not exist would manufacture data the run never had.
        """
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

    # -- deterministic settlement rules --------------------------------------

    def _settle_one(self, staged: StagedFill, bar: Bar) -> SettledFill:
        """Resolve one staged fill against its settlement bar — pure, RNG-free (design #33 §4.2)."""
        parameters = staged.parameters
        if parameters.mode is FillMode.ACKNOWLEDGE:
            return self._non_magnitude_fill(staged, bar, EgressResultKind.ACK)
        if parameters.mode is FillMode.REPORT_UNKNOWN:
            return self._non_magnitude_fill(staged, bar, EgressResultKind.UNKNOWN)
        if parameters.mode is FillMode.REPORT_TIMEOUT:
            return self._non_magnitude_fill(staged, bar, EgressResultKind.TIMEOUT)
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
        # ★ the deterministic rejection predicate (design #33 §4.2 "가격 밴드 밖").
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
        # ★ structural derivation: the magnitudes decide partial vs full — never a declared label.
        # ``EgressResultPayload._fill_shape_consistent`` re-derives the same thing independently
        # (records.py:221-229), so a defect here fails closed at construction.
        kind = (
            EgressResultKind.PARTIAL_FILL if remaining > 0 else EgressResultKind.FULL_FILL
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
