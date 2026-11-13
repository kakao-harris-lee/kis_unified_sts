"""The mandated single-order scenario contract (design #33 §5.1) + a reference bar profile."""

from __future__ import annotations

from decimal import Decimal

from pydantic import model_validator

from tos.backtest._base import (
    BacktestIntegrityError,
    FrozenModel,
    seal_performance_surface,
)
from tos.backtest.bars import Bar, BarStream, validate_bar_stream
from tos.backtest.fills import FillParameters
from tos.backtest.vocabulary import (
    MANDATED_SCENARIO_IDS,
    ExecutionPriceBasis,
    FillMode,
    FillSide,
    ScenarioId,
    SettlementPolicy,
)
from tos.dsl import TargetKind
from tos.engine import CommitmentStep

__all__ = [
    "MANDATED_SCENARIOS",
    "REFERENCE_BASE_PRICE",
    "REFERENCE_VOLUME",
    "ScenarioSpec",
    "reference_bars",
    "scenario_for",
]

REFERENCE_BASE_PRICE = Decimal(100)
REFERENCE_VOLUME = Decimal(1000)
_REFERENCE_COORDINATE_STEP = 60
_REFERENCE_SESSION_TOKEN = "reference-session"

_PROVISIONAL_PARTICIPATION_CAP = Decimal("0.5")
_PROVISIONAL_SLIPPAGE_BPS = Decimal(5)
_PROVISIONAL_COST_PER_UNIT = Decimal("0.02")
_PROVISIONAL_PRICE_BAND_FRACTION = Decimal("0.05")
_PROVISIONAL_FULL_QUANTITY = Decimal(10)
_PROVISIONAL_PARTIAL_QUANTITY = Decimal(800)
_PROVISIONAL_OUT_OF_BAND_REFERENCE = Decimal(50)


def reference_bars(count: int) -> BarStream:
    """Build ``count`` bars of the synthetic reference profile (design #33 §3.1)."""
    if count < 0:
        raise BacktestIntegrityError(
            f"reference_bars(count={count}) — a negative count is not an empty stream; ∅ is "
            "explicit, never inferred from an ill-formed input (design #33 §13)"
        )
    bars = [
        Bar(
            bar_index=index,
            timestamp_coordinate=(index + 1) * _REFERENCE_COORDINATE_STEP,
            open_price=REFERENCE_BASE_PRICE + index,
            high_price=REFERENCE_BASE_PRICE + index + 1,
            low_price=REFERENCE_BASE_PRICE + index - 1,
            close_price=REFERENCE_BASE_PRICE + index,
            volume=REFERENCE_VOLUME,
            session_token=_REFERENCE_SESSION_TOKEN,
        )
        for index in range(count)
    ]
    return validate_bar_stream(bars)


class ScenarioSpec(FrozenModel):
    """One mandated scenario's **inputs** (design #33 §5.1) — never its expected verdict."""

    scenario_id: ScenarioId
    intent: str
    bar_count: int
    target_kind: TargetKind
    fill_parameters: FillParameters
    denied_steps: tuple[CommitmentStep, ...] = ()
    unknown_steps: tuple[CommitmentStep, ...] = ()
    denial_reason: str | None = None

    @model_validator(mode="after")
    def _scenario_is_well_formed(self) -> ScenarioSpec:
        """Seal the performance surface and require a runnable, non-contradictory scenario."""
        seal_performance_surface(type(self).__name__, type(self).model_fields)
        if self.bar_count <= 0:
            raise BacktestIntegrityError(
                f"ScenarioSpec.bar_count must be positive (got {self.bar_count}) — a mandated "
                "scenario that replays nothing demonstrates nothing"
            )
        if not self.intent.strip():
            raise BacktestIntegrityError(
                "ScenarioSpec.intent must be non-empty — a scenario records what it demonstrates"
            )
        if self.denied_steps and not (self.denial_reason or "").strip():
            raise BacktestIntegrityError(
                "a denying scenario must carry its denial reason — a stop without a recorded "
                "reason is a silent one, not a fail-closed one (design #33 §8-10)"
            )
        overlap = set(self.denied_steps) & set(self.unknown_steps)
        if overlap:
            raise BacktestIntegrityError(
                f"steps {sorted(step.value for step in overlap)} are declared both denying and "
                "unknown — DENY and UNKNOWN are distinct restrictive outcomes and must stay "
                "distinguishable in the recorded halt reason (sequencer.py:463-476)"
            )
        return self


def _settle_parameters(
    *,
    quantity: Decimal,
    settlement: SettlementPolicy = SettlementPolicy.SAME_BAR,
    reference_price: Decimal = REFERENCE_BASE_PRICE,
) -> FillParameters:
    """Build a complete ``SETTLE`` parameter set from the provisional injected constants."""
    return FillParameters(
        mode=FillMode.SETTLE,
        side=FillSide.BUY,
        settlement=settlement,
        price_basis=ExecutionPriceBasis.CLOSE,
        scenario_quantity=quantity,
        participation_cap_fraction=_PROVISIONAL_PARTICIPATION_CAP,
        slippage_bps=_PROVISIONAL_SLIPPAGE_BPS,
        cost_per_unit=_PROVISIONAL_COST_PER_UNIT,
        limit_reference_price=reference_price,
        price_band_fraction=_PROVISIONAL_PRICE_BAND_FRACTION,
    )


def _bare_parameters(mode: FillMode) -> FillParameters:
    """Build a magnitude-free parameter set for ACK / UNKNOWN / TIMEOUT (records.py:201-207)."""
    return FillParameters(mode=mode, side=FillSide.BUY)


MANDATED_SCENARIOS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        scenario_id=ScenarioId.ENTRY_ACK,
        intent=(
            "row A — entry → ACK: knowledge advances to ACKNOWLEDGED while the capacity "
            "projection is unchanged (state.py:77 maps ACK to None), which is a different axis "
            "from UNKNOWN (vocabulary.py:145 vs :149)"
        ),
        bar_count=1,
        target_kind=TargetKind.ACTION,
        fill_parameters=_bare_parameters(FillMode.ACKNOWLEDGE),
    ),
    ScenarioSpec(
        scenario_id=ScenarioId.ENTRY_FULL_FILL,
        intent="row 1 — entry → FULL_FILL: POSITION_CONSUMED / FILLED",
        bar_count=1,
        target_kind=TargetKind.ACTION,
        fill_parameters=_settle_parameters(quantity=_PROVISIONAL_FULL_QUANTITY),
    ),
    ScenarioSpec(
        scenario_id=ScenarioId.ENTRY_PARTIAL_FILL,
        intent=(
            "row 2 — entry → PARTIAL_FILL: PARTIALLY_CONSUMED / PARTIALLY_FILLED, remaining > 0, "
            "and the already-filled part is never re-requested (RFC-005 §11:338-339)"
        ),
        bar_count=1,
        target_kind=TargetKind.ACTION,
        fill_parameters=_settle_parameters(quantity=_PROVISIONAL_PARTIAL_QUANTITY),
    ),
    ScenarioSpec(
        scenario_id=ScenarioId.ENTRY_REJECT,
        intent=(
            "row 3 — entry → REJECT: RELEASE_PENDING_PROOF / REJECTED, and the scope stays "
            "occupied because release is the RCL's act (state.py:22/:83)"
        ),
        bar_count=1,
        target_kind=TargetKind.ACTION,
        fill_parameters=_settle_parameters(
            quantity=_PROVISIONAL_FULL_QUANTITY,
            reference_price=_PROVISIONAL_OUT_OF_BAND_REFERENCE,
        ),
    ),
    ScenarioSpec(
        scenario_id=ScenarioId.ENTRY_UNKNOWN,
        intent=(
            "row 4a — entry → UNKNOWN: the capacity projection stays POTENTIALLY_LIVE and nothing "
            "is resubmitted (RFC-005 §11:325-327)"
        ),
        bar_count=1,
        target_kind=TargetKind.ACTION,
        fill_parameters=_bare_parameters(FillMode.REPORT_UNKNOWN),
    ),
    ScenarioSpec(
        scenario_id=ScenarioId.ENTRY_TIMEOUT,
        intent=(
            "row 4b — entry → TIMEOUT: the same conservatism as UNKNOWN; a timeout is never read "
            "as a rejection (RFC-002 §10.7:722)"
        ),
        bar_count=1,
        target_kind=TargetKind.ACTION,
        fill_parameters=_bare_parameters(FillMode.REPORT_TIMEOUT),
    ),
    ScenarioSpec(
        scenario_id=ScenarioId.FAIL_CLOSED_HALT,
        intent=(
            "row 5 — a venue INADMISSIBLE stage deny stops the flow: nothing is handed off and the "
            "halt is recorded with its reason (the wiring's only safety value, 완주 §2:45-47)"
        ),
        bar_count=1,
        target_kind=TargetKind.ACTION,
        fill_parameters=_bare_parameters(FillMode.ACKNOWLEDGE),
        denied_steps=(CommitmentStep.VENUE_ADMISSIBILITY_DECISION,),
        denial_reason="provisional stand-in reports the candidate command INADMISSIBLE",
    ),
    ScenarioSpec(
        scenario_id=ScenarioId.AT_MOST_ONE_FIRING,
        intent=(
            "row 6 — multi-bar: bar 1 realizes the entry, bars 2+ are denied at the capacity stage "
            "with AT_MOST_ONE_EXPOSURE_HELD. The seal firing is a positive safety demonstration, "
            "not a limitation (design #33 §2.3)"
        ),
        bar_count=3,
        target_kind=TargetKind.ACTION,
        fill_parameters=_bare_parameters(FillMode.ACKNOWLEDGE),
    ),
    ScenarioSpec(
        scenario_id=ScenarioId.FLAT_ONLY,
        intent=(
            "row 7 — a flat-only run on a fresh scope: an Explicit Flat is a single order, not a "
            "round trip; the round trip waits for the RCL release path (design #33 §2.5)"
        ),
        bar_count=1,
        target_kind=TargetKind.FLAT,
        fill_parameters=_settle_parameters(quantity=_PROVISIONAL_FULL_QUANTITY),
    ),
)


def scenario_for(scenario_id: ScenarioId) -> ScenarioSpec:
    """Return the mandated scenario spec for ``scenario_id`` — positive membership (design #33 §5.1)."""
    for spec in MANDATED_SCENARIOS:
        if spec.scenario_id is scenario_id:
            return spec
    raise BacktestIntegrityError(
        f"no mandated scenario spec is declared for {scenario_id!r} — every member of the closed "
        f"set {[member.value for member in MANDATED_SCENARIO_IDS]} must be realized "
        "(design #33 §5.1)"
    )
