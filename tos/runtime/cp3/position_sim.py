"""Replay's simulated position and its one fill model (plan P4 §2 D7)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from tos.canonical import (
    EV_L1_PROVISIONAL_VERSION,
    ArtifactIntegrityError,
    CanonicalizationScheme,
    get_scheme,
)
from tos.dsl import (
    PositionContext,
    PositionSide,
    ScalarValue,
    flat_position_context,
    project_position_context,
)
from tos_runtime.compose._construction_config import (
    CONSTRUCTION_CONFIG_NAME,
    ConstructionConfigError,
    load_construction_config,
)
from tos_runtime.compose._marketfeed_wiring import (
    MarketFeedConfigError,
    load_position_context_config,
)
from tos_runtime.marketfeed.ports import PositionContextReason
from tos_runtime.venue import (
    ORDER_CONSTRUCTION_POLICY_CONFIG_NAME,
    VenuePolicyConfigError,
    load_order_construction_policy,
)

from ._base import Cp3RunnerRefusal

__all__ = [
    "CARRIES_ACROSS_SESSIONS",
    "DECLARED_UNIT_SOURCE",
    "DEFAULT_UNIT_SOURCE",
    "ENTRY_PRICE_BASIS",
    "FILL_MODEL",
    "POSITION_MODE_RECORDED",
    "POSITION_MODE_SIMULATED",
    "SCHEME",
    "PositionSimulation",
    "RoundTrip",
    "SimulationConfig",
    "load_simulation_config",
]

SCHEME: CanonicalizationScheme = get_scheme(EV_L1_PROVISIONAL_VERSION)

POSITION_MODE_SIMULATED = "simulated"

POSITION_MODE_RECORDED = "recorded"

ENTRY_PRICE_BASIS = "ORDER"

FILL_MODEL = (
    "체결 모델 하나: ACTION · FLAT 결정은 그 봉의 price_field_key 값에 전량 체결되고, "
    "그 결과 포지션은 다음 봉부터 보인다(라이브도 그 봉의 결정 전에 포지션을 읽는다)."
)

CARRIES_ACROSS_SESSIONS = (
    "시뮬레이션 포지션은 세션 경계에서 초기화되지 않는다 — 주식 스윙은 라이브에서도 "
    "다음 날로 넘어가고 bars_held 는 벽시계로 센다(계획 §11 #3)."
)

DECLARED_UNIT_SOURCE = "order_construction_policy risk_budget/per_unit_risk"

DEFAULT_UNIT_SOURCE = "replay default (one unit)"

ACTION_KIND = "ACTION"

FLAT_KIND = "FLAT"

_DEFAULT_UNIT = 1

_SOURCE_REF_PREFIX = "replay:"

_UNREADABLE_POLICY: tuple[type[Exception], ...] = (
    VenuePolicyConfigError,
    ArtifactIntegrityError,
    OSError,
    ValueError,
)


@dataclass(frozen=True)
class SimulationConfig:
    """What the tree declares that the simulated position stands on."""

    price_field_key: str
    bar_interval_ms: int
    held_qty: int
    held_qty_source: str

    def as_json(self) -> dict[str, object]:
        """The facts the report publishes so a reader can check the fill model."""
        return {
            "price_field_key": self.price_field_key,
            "bar_interval_ms": self.bar_interval_ms,
            "held_qty": self.held_qty,
            "held_qty_source": self.held_qty_source,
            "entry_price_basis": ENTRY_PRICE_BASIS,
            "fill_model": FILL_MODEL,
            "carries_across_sessions": CARRIES_ACROSS_SESSIONS,
        }


@dataclass(frozen=True)
class RoundTrip:
    """One simulated round trip — the fill pair the hypothetical PnL also counts."""

    entry_raw_event_id: str
    entry_time_kst: str
    entry_rule_id: str | None
    entry_price: int
    exit_raw_event_id: str
    exit_time_kst: str
    exit_rule_id: str | None
    exit_price: int
    bars_held: int
    unrealized: int
    unrealized_bp: int

    def as_json(self) -> dict[str, object]:
        """One round trip as JSON-native fields."""
        return {
            "entry_raw_event_id": self.entry_raw_event_id,
            "entry_time_kst": self.entry_time_kst,
            "entry_rule_id": self.entry_rule_id,
            "entry_price": self.entry_price,
            "exit_raw_event_id": self.exit_raw_event_id,
            "exit_time_kst": self.exit_time_kst,
            "exit_rule_id": self.exit_rule_id,
            "exit_price": self.exit_price,
            "bars_held": self.bars_held,
            "unrealized": self.unrealized,
            "unrealized_bp": self.unrealized_bp,
        }


@dataclass(frozen=True)
class _OpenFill:
    """The simulated entry a later FLAT decision closes."""

    raw_event_id: str
    time_kst: str
    rule_id: str | None
    price: int
    as_of_ms: int


def _exact_positive_int(value: object) -> int | None:
    """``value`` as a positive int, only when it already IS one (no coercion)."""
    if type(value) is not int or value <= 0:
        return None
    return value


def _declared_unit(
    config_dir: Path, *, scheme: CanonicalizationScheme
) -> tuple[int, str]:
    """The quantity one simulated fill holds, and where that number came from."""
    path = config_dir / ORDER_CONSTRUCTION_POLICY_CONFIG_NAME
    try:
        bound = load_order_construction_policy(
            path, scheme=scheme
        ).construction_rules.sizing_bound
    except _UNREADABLE_POLICY:
        return _DEFAULT_UNIT, DEFAULT_UNIT_SOURCE
    budget, per_unit = bound.risk_budget, bound.per_unit_risk
    if budget is None or per_unit is None or per_unit == 0:
        return _DEFAULT_UNIT, DEFAULT_UNIT_SOURCE
    # SAFETY: only an EXACT positive integer quotient is taken — replay holds no envelope, admitted price or venue constraint, so rounding a fractional quotient here would be a second sizing model whose held_qty a rule can read and disagree with what live sends
    raw: Decimal = Decimal(budget) / Decimal(per_unit)
    if raw <= 0 or raw != raw.to_integral_value():
        return _DEFAULT_UNIT, DEFAULT_UNIT_SOURCE
    return int(raw), DECLARED_UNIT_SOURCE


def load_simulation_config(
    config_dir: Path, *, scheme: CanonicalizationScheme = SCHEME
) -> SimulationConfig | None:
    """This tree's declared position inputs, or ``None`` when it does not enable them."""
    try:
        declared = load_position_context_config(config_dir)
    except MarketFeedConfigError as exc:
        raise Cp3RunnerRefusal(
            f"{config_dir}: position_context refused — {exc}"
        ) from exc
    if declared is None or not declared.enabled:
        return None
    try:
        construction = load_construction_config(config_dir / CONSTRUCTION_CONFIG_NAME)
    except ConstructionConfigError as exc:
        raise Cp3RunnerRefusal(
            f"{config_dir}: construction.yaml refused — {exc}"
        ) from exc
    price_field_key = construction.price_field_key
    if price_field_key is None:
        raise Cp3RunnerRefusal(
            f"{config_dir}: position_context.enabled is true but construction.yaml declares "
            "no price_field_key — the bar price a position's unrealized figure is taken from "
            "must be the SAME admitted value the order's limit price is"
        )
    assert declared.bar_interval_ms is not None
    held_qty, source = _declared_unit(config_dir, scheme=scheme)
    return SimulationConfig(
        price_field_key=price_field_key,
        bar_interval_ms=declared.bar_interval_ms,
        held_qty=held_qty,
        held_qty_source=source,
    )


class PositionSimulation:
    """Carries one simulated position across the replayed bars, in journal order."""

    def __init__(
        self,
        config: SimulationConfig,
        *,
        side: PositionSide,
        scheme: CanonicalizationScheme = SCHEME,
    ) -> None:
        """Bind the simulation to the tree's declared inputs and its one ACTION direction."""
        self._config = config
        self._side = side
        self._scheme = scheme
        self._open: _OpenFill | None = None
        self._round_trips: list[RoundTrip] = []

    @property
    def round_trips(self) -> tuple[RoundTrip, ...]:
        """Every round trip the simulated fills closed, oldest first."""
        return tuple(self._round_trips)

    @property
    def open_fill(self) -> dict[str, object] | None:
        """The still-open simulated entry at the end of the replay, or ``None``."""
        held = self._open
        if held is None:
            return None
        return {
            "entry_raw_event_id": held.raw_event_id,
            "entry_time_kst": held.time_kst,
            "entry_rule_id": held.rule_id,
            "entry_price": held.price,
        }

    def price_of(self, values: Mapping[str, ScalarValue]) -> int | None:
        """This bar's declared price field as a positive int, or ``None``."""
        return _exact_positive_int(values.get(self._config.price_field_key))

    def context(
        self, *, price: int | None, as_of_ms: int, raw_event_id: str
    ) -> tuple[PositionContext | None, str | None]:
        """``(this bar's position context, absence reason)`` — never a partial context."""
        if price is None:
            # SAFETY: an unusable price leaves the namespace absent and the simulated state untouched, exactly as live's PRICE_FIELD_UNUSABLE does — projecting the previous bar's price here would publish an unrealized figure no bar ever showed
            return None, PositionContextReason.PRICE_FIELD_UNUSABLE.value
        held = self._open
        if held is None:
            return self._flat(as_of_ms=as_of_ms, raw_event_id=raw_event_id)
        return self._projected(held, price=price, as_of_ms=as_of_ms)

    def _flat(
        self, *, as_of_ms: int, raw_event_id: str
    ) -> tuple[PositionContext | None, str | None]:
        """The proven-flat context for one replayed bar, via the kernel's own constructor."""
        try:
            return (
                flat_position_context(
                    source_ref=f"{_SOURCE_REF_PREFIX}{raw_event_id}",
                    as_of=as_of_ms,
                    scheme=self._scheme,
                ),
                None,
            )
        except ArtifactIntegrityError:
            return None, PositionContextReason.PROJECTION_REFUSED.value

    def _projected(
        self, held: _OpenFill, *, price: int, as_of_ms: int
    ) -> tuple[PositionContext | None, str | None]:
        """``held``'s context at ``price``, via the kernel's own projection (plan P4 §2 D4)."""
        try:
            return (
                project_position_context(
                    side=self._side,
                    held_qty=self._config.held_qty,
                    entry_price=held.price,
                    entry_price_basis=ENTRY_PRICE_BASIS,
                    entry_as_of=held.as_of_ms,
                    price=price,
                    as_of=as_of_ms,
                    bar_interval_ms=self._config.bar_interval_ms,
                    source_ref=f"{_SOURCE_REF_PREFIX}{held.raw_event_id}",
                    scheme=self._scheme,
                ),
                None,
            )
        except ArtifactIntegrityError:
            return None, PositionContextReason.PROJECTION_REFUSED.value

    def apply(
        self,
        *,
        decision_kind: str | None,
        rule_id: str | None,
        price: int | None,
        as_of_ms: int,
        raw_event_id: str,
        time_kst: str,
    ) -> None:
        """Fill this bar's decision at ``price`` — the result is visible from the NEXT bar."""
        if price is None or decision_kind is None:
            return
        held = self._open
        if decision_kind == ACTION_KIND and held is None:
            self._open = _OpenFill(
                raw_event_id=raw_event_id,
                time_kst=time_kst,
                rule_id=rule_id,
                price=price,
                as_of_ms=as_of_ms,
            )
            return
        if decision_kind != FLAT_KIND or held is None:
            # SAFETY: ACTION while held and FLAT while flat are both no-ops — live halts the second entry at the capacity stage (AT_MOST_ONE_EXPOSURE_HELD) and sends no exit with nothing to close, so stacking here would invent a round trip and a position size the kernel would never have produced
            return
        projected, _absent = self._projected(held, price=price, as_of_ms=as_of_ms)
        self._open = None
        self._round_trips.append(
            RoundTrip(
                entry_raw_event_id=held.raw_event_id,
                entry_time_kst=held.time_kst,
                entry_rule_id=held.rule_id,
                entry_price=held.price,
                exit_raw_event_id=raw_event_id,
                exit_time_kst=time_kst,
                exit_rule_id=rule_id,
                exit_price=price,
                bars_held=0 if projected is None else int(projected.bars_held or 0),
                unrealized=0 if projected is None else int(projected.unrealized or 0),
                unrealized_bp=(
                    0 if projected is None else int(projected.unrealized_bp or 0)
                ),
            )
        )
