"""Market Risk Score (0-100) composition library — unified roadmap Phase 1 §4.

Pure scoring logic for the cross-asset market risk indicator built on the
``market_structure_daily`` close-row time series
(:mod:`shared.storage.market_structure_store`). Eight components (§4.1) are
normalized against a rolling window (percentile or clipped z-score, higher =
riskier), blended by configured weights with missing-component
renormalization, smoothed with a daily EMA, and mapped to bands (§4.2) with
transition hysteresis plus a Unified Regime (RISK_ON/NEUTRAL/RISK_OFF).

Every weight, window, band boundary, buffer, mapping, and coverage threshold
comes from ``config/market_risk.yaml`` (:class:`MarketRiskConfig`) — no
hardcoded thresholds. The score is SHADOW-ONLY in Phase 1: nothing in this
module may be wired into strategy/gate/execution paths (Phase 2 scope).

Naming: this is ``market_risk_score`` — distinct from the LLM
``MarketContext.risk_score`` static RiskMode mapping (roadmap O8).

Look-ahead safety: normalization windows are built exclusively from close
rows with ``trade_date`` strictly before the day being scored;
:func:`hindcast` threads EMA/hysteresis state forward in date order so a
recomputed history never sees future data.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, ClassVar, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator

from shared.config.base import ServiceConfigBase
from shared.config.loader import ConfigNotFoundError

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

# Parquet close-row column contract (market_structure_daily DDL, roadmap
# §4.3): sub_* / risk_score / risk_band / unified_regime / degraded. These are
# schema names shared with the backfill/dashboard lanes, not tunables.
SCORE_COLUMN = "risk_score"
SCORE_EMA_COLUMN = "risk_score_ema3"
BAND_COLUMN = "risk_band"
REGIME_COLUMN = "unified_regime"
DEGRADED_COLUMN = "degraded"
COVERAGE_COLUMN = "risk_coverage_ratio"
MISSING_COLUMN = "risk_missing_components"
RISK_ASOF_COLUMN = "risk_asof_ts"
SUB_COLUMN_PREFIX = "sub_"

_TREND_UP = "up"
_TREND_DOWN = "down"
_TREND_UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Configuration (config/market_risk.yaml)
# ---------------------------------------------------------------------------


class MarketRiskEngineSettings(BaseModel):
    """Normalization windows, smoothing, and coverage policy."""

    window_days: int = Field(default=240, gt=1)
    min_periods: int = Field(default=20, gt=0)
    zscore_clip: float = Field(default=3.0, gt=0.0)
    ema_span: int = Field(default=3, ge=1)
    min_coverage_ratio: float = Field(default=0.6, ge=0.0, le=1.0)
    band_source: Literal["ema", "raw"] = Field(default="ema")

    @model_validator(mode="after")
    def _validate_periods(self) -> MarketRiskEngineSettings:
        if self.min_periods > self.window_days:
            raise ValueError("engine.min_periods must be <= engine.window_days")
        return self


class SignalSpec(BaseModel):
    """One input signal inside a component."""

    column: str
    kind: Literal["numeric", "categorical"] = Field(default="numeric")
    method: Literal["percentile", "zscore"] = Field(default="percentile")
    direction: Literal["high_is_risk", "low_is_risk"] = Field(default="high_is_risk")
    mapping: dict[str, float] = Field(default_factory=dict)
    magnitude_column: str | None = Field(default=None)
    weight: float = Field(default=1.0, gt=0.0)

    @model_validator(mode="after")
    def _validate_kind(self) -> SignalSpec:
        if self.kind == "categorical" and not self.mapping:
            raise ValueError(f"categorical signal {self.column!r} requires a mapping")
        for label, sub in self.mapping.items():
            if not 0.0 <= float(sub) <= 100.0:
                raise ValueError(f"mapping[{label!r}] must be within 0..100, got {sub}")
        return self


class ComponentSpec(BaseModel):
    """A weighted component composed of one or more signals."""

    weight: float = Field(gt=0.0)
    signals: list[SignalSpec] = Field(min_length=1)


def _default_components() -> dict[str, ComponentSpec]:
    """Mirror of the shipped config/market_risk.yaml components section."""
    numeric = SignalSpec.model_validate
    return {
        "foreign_fut": ComponentSpec(
            weight=25,
            signals=[
                numeric(
                    {
                        "column": "fut_foreign_net_qty_cum20",
                        "direction": "low_is_risk",
                        "weight": 0.7,
                    }
                ),
                numeric(
                    {
                        "column": "fut_foreign_net_qty",
                        "direction": "low_is_risk",
                        "weight": 0.3,
                    }
                ),
            ],
        ),
        "basis": ComponentSpec(
            weight=15,
            signals=[
                numeric(
                    {
                        "column": "basis_dev_ma5",
                        "direction": "low_is_risk",
                        "weight": 0.6,
                    }
                ),
                numeric(
                    {"column": "basis_dev", "direction": "low_is_risk", "weight": 0.4}
                ),
            ],
        ),
        "usdkrw": ComponentSpec(
            weight=15,
            signals=[
                numeric(
                    {"column": "usdkrw", "direction": "high_is_risk", "weight": 0.5}
                ),
                numeric(
                    {
                        "column": "usdkrw_ret_5d",
                        "method": "zscore",
                        "direction": "high_is_risk",
                        "weight": 0.5,
                    }
                ),
            ],
        ),
        "program": ComponentSpec(
            weight=10,
            signals=[
                numeric(
                    {
                        "column": "prog_net_val",
                        "direction": "low_is_risk",
                        "weight": 1.0,
                    }
                )
            ],
        ),
        "oi": ComponentSpec(
            weight=10,
            signals=[
                SignalSpec(
                    column="oi_price_signal",
                    kind="categorical",
                    mapping={
                        "new_shorts": 100.0,
                        "long_liquidation": 70.0,
                        "neutral": 50.0,
                        "short_covering": 35.0,
                        "new_longs": 15.0,
                    },
                    magnitude_column="fut_oi_change",
                    weight=1.0,
                )
            ],
        ),
        "overseas": ComponentSpec(
            weight=10,
            signals=[
                numeric(
                    {
                        "column": "es_futures_change_pct",
                        "method": "zscore",
                        "direction": "low_is_risk",
                        "weight": 0.4,
                    }
                ),
                numeric(
                    {
                        "column": "nq_futures_change_pct",
                        "method": "zscore",
                        "direction": "low_is_risk",
                        "weight": 0.3,
                    }
                ),
                numeric(
                    {
                        "column": "sox_change_pct",
                        "method": "zscore",
                        "direction": "low_is_risk",
                        "weight": 0.3,
                    }
                ),
            ],
        ),
        "vol": ComponentSpec(
            weight=10,
            signals=[
                numeric(
                    {
                        "column": "har_rv_pred",
                        "direction": "high_is_risk",
                        "weight": 1.0,
                    }
                )
            ],
        ),
        "trend": ComponentSpec(
            weight=5,
            signals=[
                SignalSpec(
                    column="k200_ma_alignment",
                    kind="categorical",
                    mapping={"bearish": 100.0, "mixed": 50.0, "bullish": 0.0},
                    weight=0.5,
                ),
                numeric(
                    {
                        "column": "k200_ret_20d",
                        "direction": "low_is_risk",
                        "weight": 0.5,
                    }
                ),
            ],
        ),
    }


class BandSpec(BaseModel):
    """Inclusive [min, max] score band."""

    name: str
    min: float = Field(ge=0.0)
    max: float = Field(le=100.0)

    @model_validator(mode="after")
    def _validate_range(self) -> BandSpec:
        if self.min > self.max:
            raise ValueError(f"band {self.name!r}: min must be <= max")
        return self


def _default_bands() -> list[BandSpec]:
    return [
        BandSpec(name="LOW", min=0, max=29),
        BandSpec(name="NEUTRAL", min=30, max=54),
        BandSpec(name="ELEVATED", min=55, max=69),
        BandSpec(name="HIGH", min=70, max=84),
        BandSpec(name="CRITICAL", min=85, max=100),
    ]


class HysteresisSettings(BaseModel):
    """Band flapping guard (§4.2)."""

    buffer_points: float = Field(default=5.0, ge=0.0)
    confirm_consecutive: int = Field(default=2, ge=1)


class UnifiedRegimeSettings(BaseModel):
    """Band + index-trend sign → unified regime mapping."""

    trend_column: str = Field(default="k200_ret_20d")
    mapping: dict[str, dict[str, str]] = Field(
        default_factory=lambda: {
            "LOW": {"up": "RISK_ON", "down": "RISK_ON", "unknown": "RISK_ON"},
            "NEUTRAL": {"up": "RISK_ON", "down": "NEUTRAL", "unknown": "NEUTRAL"},
            "ELEVATED": {"up": "NEUTRAL", "down": "NEUTRAL", "unknown": "NEUTRAL"},
            "HIGH": {"up": "RISK_OFF", "down": "RISK_OFF", "unknown": "RISK_OFF"},
            "CRITICAL": {"up": "RISK_OFF", "down": "RISK_OFF", "unknown": "RISK_OFF"},
        }
    )


class MarketRiskRedisSettings(BaseModel):
    """Redis DB 1 publication contract (§4.3; fixed with the 1c UI lane)."""

    latest_key: str = Field(default="market:risk:latest")
    latest_ttl_seconds: int = Field(default=86400, gt=0)
    stream_key: str = Field(default="stream:market.risk")
    stream_maxlen: int = Field(default=5000, gt=0)
    stream_ttl_seconds: int = Field(default=86400, gt=0)
    regime_daily_key: str = Field(default="regime:unified:daily")
    regime_daily_ttl_seconds: int = Field(default=172800, gt=0)
    band_state_key: str = Field(default="market:risk:band_state")
    band_state_ttl_seconds: int = Field(default=172800, gt=0)
    structure_latest_key: str = Field(default="market:structure:latest")
    vol_forecast_key: str = Field(default="forecast:vol:current")


class MarketRiskRunnerSettings(BaseModel):
    """One-shot runner behavior (services/market_risk_engine)."""

    intraday_session_start: str = Field(default="09:00")
    intraday_session_end: str = Field(default="15:30")
    history_lookback_days: int = Field(default=420, gt=0)
    vol_forecast_max_age_seconds: int = Field(default=86400, gt=0)

    @field_validator("intraday_session_start", "intraday_session_end")
    @classmethod
    def _validate_hhmm(cls, value: str) -> str:
        from datetime import time

        time.fromisoformat(value)
        return value


class MarketRiskAlertSettings(BaseModel):
    """Telegram band-transition / degraded alerts."""

    enabled: bool = Field(default=True)
    domain: str = Field(default="briefing")
    notify_bands: list[str] = Field(default_factory=lambda: ["HIGH", "CRITICAL"])
    notify_on_degraded: bool = Field(default=True)


class MarketRiskConfig(ServiceConfigBase):
    """Top-level config loaded from ``config/market_risk.yaml``."""

    _default_config_file: ClassVar[str] = "market_risk.yaml"

    engine: MarketRiskEngineSettings = Field(default_factory=MarketRiskEngineSettings)
    components: dict[str, ComponentSpec] = Field(default_factory=_default_components)
    bands: list[BandSpec] = Field(default_factory=_default_bands)
    hysteresis: HysteresisSettings = Field(default_factory=HysteresisSettings)
    unified_regime: UnifiedRegimeSettings = Field(default_factory=UnifiedRegimeSettings)
    redis: MarketRiskRedisSettings = Field(default_factory=MarketRiskRedisSettings)
    runner: MarketRiskRunnerSettings = Field(default_factory=MarketRiskRunnerSettings)
    alerts: MarketRiskAlertSettings = Field(default_factory=MarketRiskAlertSettings)

    @model_validator(mode="after")
    def _validate_bands(self) -> MarketRiskConfig:
        if not self.components:
            raise ValueError("components must not be empty")
        ordered = sorted(self.bands, key=lambda band: band.min)
        for prev, current in zip(ordered, ordered[1:]):
            if current.min <= prev.max:
                raise ValueError(f"bands {prev.name!r} and {current.name!r} overlap")
        names = [band.name for band in self.bands]
        if len(set(names)) != len(names):
            raise ValueError("band names must be unique")
        unknown = [name for name in self.unified_regime.mapping if name not in names]
        if unknown:
            raise ValueError(f"unified_regime.mapping has unknown bands: {unknown}")
        return self

    @classmethod
    def load_or_default(cls, path: str | None = None) -> MarketRiskConfig:
        """Load from YAML when available, otherwise return validated defaults."""
        try:
            return cls.from_yaml(path)
        except ConfigNotFoundError:
            return cls()

    def ordered_bands(self) -> list[BandSpec]:
        """Bands sorted by lower bound (ascending risk)."""
        return sorted(self.bands, key=lambda band: band.min)


# ---------------------------------------------------------------------------
# Results / state
# ---------------------------------------------------------------------------


@dataclass
class SignalResult:
    """Outcome of normalizing a single signal."""

    column: str
    sub: float | None
    raw: Any
    weight: float
    reason: str | None = None


@dataclass
class ComponentResult:
    """Outcome of one weighted component."""

    name: str
    weight: float
    sub: float | None
    contribution: float | None
    raw: dict[str, Any]
    asof: str | None
    signals: list[SignalResult] = field(default_factory=list)

    def contract_payload(self) -> dict[str, Any]:
        """Per-component payload for the ``components`` hash field (§4.3)."""
        return {
            "sub": None if self.sub is None else round(self.sub, 4),
            "weight": self.weight,
            "contribution": (
                None if self.contribution is None else round(self.contribution, 4)
            ),
            "raw": self.raw,
            "asof": self.asof,
        }


@dataclass
class BandState:
    """Hysteresis + degraded edge state threaded between computations."""

    band: str | None = None
    pending_band: str | None = None
    pending_count: int = 0
    degraded: bool = False


@dataclass
class MarketRiskResult:
    """One full market-risk computation."""

    trade_date: date
    kind: str
    score: float | None
    score_ema: float | None
    raw_band: str | None
    band: str | None
    prev_band: str | None
    band_changed: bool
    regime: str | None
    degraded: bool
    degraded_entered: bool
    coverage_ratio: float
    missing_components: list[str]
    components: dict[str, ComponentResult]
    asof_ts: datetime

    def components_payload(self) -> dict[str, dict[str, Any]]:
        return {
            name: component.contract_payload()
            for name, component in self.components.items()
        }


# ---------------------------------------------------------------------------
# Value / history helpers
# ---------------------------------------------------------------------------


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    return not (isinstance(value, float) and math.isnan(value))


def _as_float(value: Any) -> float | None:
    if not _is_present(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def history_records(history: Any) -> list[dict[str, Any]]:
    """Normalize history to date-sorted row dicts.

    Accepts a pandas DataFrame (``store.read_range`` output) or a sequence of
    mappings. Rows without a parseable ``trade_date`` are dropped.
    """
    if history is None:
        return []
    if hasattr(history, "to_dict") and hasattr(history, "empty"):
        rows = [] if history.empty else history.to_dict("records")
    elif isinstance(history, Sequence):
        rows = [dict(row) for row in history]
    else:  # pragma: no cover - defensive
        raise TypeError(f"unsupported history type: {type(history)!r}")

    dated: list[tuple[date, dict[str, Any]]] = []
    for row in rows:
        day = _coerce_date(row.get("trade_date"))
        if day is None:
            continue
        dated.append((day, dict(row)))
    dated.sort(key=lambda item: item[0])
    return [row for _, row in dated]


def column_window(
    records: Sequence[Mapping[str, Any]], column: str, window_days: int
) -> list[float]:
    """Last ``window_days`` non-null float values of ``column`` (oldest→newest)."""
    values: list[float] = []
    for row in records:
        parsed = _as_float(row.get(column))
        if parsed is not None:
            values.append(parsed)
    return values[-max(int(window_days), 1) :]


# ---------------------------------------------------------------------------
# Normalization primitives
# ---------------------------------------------------------------------------


def percentile_score(window: Sequence[float], value: float) -> float:
    """Percentile (0-100) of ``value`` within ``window`` + itself (mid-rank ties)."""
    population = [*window, value]
    less = sum(1 for item in population if item < value)
    equal = sum(1 for item in population if item == value)
    return 100.0 * (less + 0.5 * equal) / len(population)


def zscore_score(window: Sequence[float], value: float, clip: float) -> float:
    """Clipped z-score of ``value`` vs ``window`` stats mapped to 0..100 (50=mean)."""
    n = len(window)
    if n == 0:
        return 50.0
    mean = sum(window) / n
    variance = sum((item - mean) ** 2 for item in window) / n
    std = math.sqrt(variance)
    if std <= 0.0:
        return 50.0
    z = max(min((value - mean) / std, clip), -clip)
    return 50.0 + 50.0 * z / clip


def _oriented(sub: float, direction: str) -> float:
    score = sub if direction == "high_is_risk" else 100.0 - sub
    return min(max(score, 0.0), 100.0)


def _numeric_signal(
    spec: SignalSpec,
    value: Any,
    records: Sequence[Mapping[str, Any]],
    engine: MarketRiskEngineSettings,
) -> SignalResult:
    parsed = _as_float(value)
    if parsed is None:
        return SignalResult(spec.column, None, None, spec.weight, "missing")
    window = column_window(records, spec.column, engine.window_days)
    if len(window) < engine.min_periods:
        return SignalResult(
            spec.column, None, parsed, spec.weight, "insufficient_history"
        )
    if spec.method == "percentile":
        base = percentile_score(window, parsed)
    else:
        base = zscore_score(window, parsed, engine.zscore_clip)
    return SignalResult(
        spec.column, _oriented(base, spec.direction), parsed, spec.weight
    )


def _categorical_signal(
    spec: SignalSpec,
    row: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    engine: MarketRiskEngineSettings,
) -> SignalResult:
    value = row.get(spec.column)
    if not _is_present(value):
        return SignalResult(spec.column, None, None, spec.weight, "missing")
    label = str(value)
    mapped = spec.mapping.get(label)
    if mapped is None:
        return SignalResult(spec.column, None, label, spec.weight, "unmapped_label")

    sub = float(mapped)
    if spec.magnitude_column:
        magnitude = _as_float(row.get(spec.magnitude_column))
        if magnitude is not None:
            window = [
                abs(item)
                for item in column_window(
                    records, spec.magnitude_column, engine.window_days
                )
            ]
            if len(window) >= engine.min_periods:
                intensity = percentile_score(window, abs(magnitude)) / 100.0
                sub = 50.0 + (sub - 50.0) * intensity
    return SignalResult(spec.column, min(max(sub, 0.0), 100.0), label, spec.weight)


# ---------------------------------------------------------------------------
# Component / score composition
# ---------------------------------------------------------------------------


def compute_component(
    name: str,
    spec: ComponentSpec,
    row: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    engine: MarketRiskEngineSettings,
    asof: str | None,
) -> ComponentResult:
    """Blend a component's signals (missing signals renormalize within it)."""
    signals: list[SignalResult] = []
    for spec_signal in spec.signals:
        if spec_signal.kind == "categorical":
            signals.append(_categorical_signal(spec_signal, row, records, engine))
        else:
            signals.append(
                _numeric_signal(
                    spec_signal, row.get(spec_signal.column), records, engine
                )
            )

    available = [signal for signal in signals if signal.sub is not None]
    raw = {signal.column: signal.raw for signal in signals}
    if not available:
        return ComponentResult(name, spec.weight, None, None, raw, asof, signals)

    total_weight = sum(signal.weight for signal in available)
    sub = sum(signal.sub * signal.weight for signal in available) / total_weight
    return ComponentResult(name, spec.weight, sub, None, raw, asof, signals)


def compose_score(
    components: Mapping[str, ComponentResult], config: MarketRiskConfig
) -> tuple[float | None, float, list[str]]:
    """Weighted score with missing-component renormalization.

    Returns ``(score, coverage_ratio, missing_components)``. Coverage is
    weight-based (missing a 25-point component degrades more than a 5-point
    one); ``score`` is ``None`` when every component is missing. Contribution
    (points of the final score) is filled in on each available component.
    """
    total_weight = sum(spec.weight for spec in config.components.values())
    available = [
        component for component in components.values() if component.sub is not None
    ]
    missing = sorted(
        name for name, component in components.items() if component.sub is None
    )
    if total_weight <= 0 or not available:
        return None, 0.0, missing

    available_weight = sum(component.weight for component in available)
    score = (
        sum(component.sub * component.weight for component in available)
        / available_weight
    )
    for component in available:
        component.contribution = component.sub * component.weight / available_weight
    coverage = available_weight / total_weight
    return min(max(score, 0.0), 100.0), coverage, missing


def ema_update(previous: float | None, value: float, span: int) -> float:
    """EMA step (seeds with ``value`` when no previous smoothed value exists)."""
    if previous is None:
        return value
    alpha = 2.0 / (span + 1.0)
    return alpha * value + (1.0 - alpha) * previous


# ---------------------------------------------------------------------------
# Bands / hysteresis / regime
# ---------------------------------------------------------------------------


def band_for(score: float, config: MarketRiskConfig) -> str:
    """Raw band for a score — the highest band whose lower bound is reached.

    Bands are keyed on their lower bounds so fractional scores inside the
    integer gaps of the configured ranges (e.g. 29.5 between 0-29 and 30-54)
    resolve to the band below the next boundary.
    """
    ordered = config.ordered_bands()
    selected = ordered[0]
    for band in ordered:
        if score >= band.min:
            selected = band
    return selected.name


def _band_index(name: str, config: MarketRiskConfig) -> int:
    for index, band in enumerate(config.ordered_bands()):
        if band.name == name:
            return index
    raise ValueError(f"unknown band {name!r}")


def apply_hysteresis(
    score: float | None, state: BandState, config: MarketRiskConfig
) -> tuple[str | None, bool, BandState]:
    """Confirm/hold band transitions (§4.2).

    A transition confirms immediately when the score exceeds the boundary of
    the previous band by more than ``buffer_points``; otherwise the same raw
    band must be observed on ``confirm_consecutive`` consecutive computations.
    Returns ``(confirmed_band, band_changed, new_state)`` — ``state`` is not
    mutated.
    """
    hysteresis = config.hysteresis
    if score is None:
        # No score (all components missing): hold the previous state.
        return (
            state.band,
            False,
            BandState(
                band=state.band,
                pending_band=state.pending_band,
                pending_count=state.pending_count,
                degraded=state.degraded,
            ),
        )

    raw = band_for(score, config)
    previous = state.band
    if previous is None:
        return raw, False, BandState(band=raw, degraded=state.degraded)
    if raw == previous:
        return previous, False, BandState(band=previous, degraded=state.degraded)

    # Boundary crossed when leaving the previous band: the lower bound of the
    # band directly above it (moving up) or its own lower bound (moving down).
    ordered_bands = config.ordered_bands()
    prev_index = _band_index(previous, config)
    moving_up = _band_index(raw, config) > prev_index
    if moving_up:
        boundary = ordered_bands[prev_index + 1].min
        exceed = score - boundary
    else:
        boundary = ordered_bands[prev_index].min
        exceed = boundary - score

    if exceed > hysteresis.buffer_points:
        return raw, True, BandState(band=raw, degraded=state.degraded)

    pending_count = state.pending_count + 1 if state.pending_band == raw else 1
    if pending_count >= hysteresis.confirm_consecutive:
        return raw, True, BandState(band=raw, degraded=state.degraded)
    return (
        previous,
        False,
        BandState(
            band=previous,
            pending_band=raw,
            pending_count=pending_count,
            degraded=state.degraded,
        ),
    )


def trend_direction(row: Mapping[str, Any], config: MarketRiskConfig) -> str:
    """Sign of the configured trend column: up / down / unknown."""
    value = _as_float(row.get(config.unified_regime.trend_column))
    if value is None or value == 0.0:
        return _TREND_UNKNOWN
    return _TREND_UP if value > 0 else _TREND_DOWN


def map_unified_regime(
    band: str | None, trend: str, config: MarketRiskConfig
) -> str | None:
    """Band + trend sign → RISK_ON/NEUTRAL/RISK_OFF (mapping from YAML)."""
    if band is None:
        return None
    row = config.unified_regime.mapping.get(band)
    if not row:
        return None
    return row.get(trend) or row.get(_TREND_UNKNOWN)


# ---------------------------------------------------------------------------
# Full computation
# ---------------------------------------------------------------------------


def compute_market_risk(
    *,
    current_row: Mapping[str, Any],
    history: Any,
    config: MarketRiskConfig,
    trade_date: date,
    kind: str,
    prev_ema: float | None,
    band_state: BandState,
    component_asof: Mapping[str, str] | None = None,
    asof_ts: datetime | None = None,
) -> tuple[MarketRiskResult, BandState]:
    """Compute one market-risk observation.

    ``history`` must contain only close rows with ``trade_date`` strictly
    before ``trade_date`` (the caller owns look-ahead hygiene; ``hindcast``
    below does this slicing internally). ``prev_ema`` is the last CONFIRMED
    daily EMA. Returns the result plus the advanced hysteresis state.
    """
    records = history_records(history)
    if any(_coerce_date(row.get("trade_date")) >= trade_date for row in records):
        raise ValueError(
            "history contains rows at/after the scored trade_date (look-ahead)"
        )

    asof = asof_ts or datetime.now(KST).replace(tzinfo=None)
    row_asof = current_row.get("asof_ts")
    if _is_present(row_asof):
        default_asof = (
            row_asof.isoformat() if hasattr(row_asof, "isoformat") else str(row_asof)
        )
    else:
        default_asof = asof.isoformat()
    asof_overrides = dict(component_asof or {})

    components: dict[str, ComponentResult] = {}
    for name, spec in config.components.items():
        components[name] = compute_component(
            name,
            spec,
            current_row,
            records,
            config.engine,
            asof_overrides.get(name, default_asof),
        )

    score, coverage, missing = compose_score(components, config)
    degraded = score is None or coverage < config.engine.min_coverage_ratio
    degraded_entered = degraded and not band_state.degraded

    score_ema = (
        None if score is None else ema_update(prev_ema, score, config.engine.ema_span)
    )
    band_input = score_ema if config.engine.band_source == "ema" else score
    raw_band = None if band_input is None else band_for(band_input, config)

    previous_band = band_state.band
    confirmed, changed, next_state = apply_hysteresis(band_input, band_state, config)
    next_state.degraded = degraded

    regime = map_unified_regime(confirmed, trend_direction(current_row, config), config)

    result = MarketRiskResult(
        trade_date=trade_date,
        kind=kind,
        score=score,
        score_ema=score_ema,
        raw_band=raw_band,
        band=confirmed,
        prev_band=previous_band,
        band_changed=changed,
        regime=regime,
        degraded=degraded,
        degraded_entered=degraded_entered,
        coverage_ratio=coverage,
        missing_components=missing,
        components=components,
        asof_ts=asof,
    )
    return result, next_state


def risk_row_fields(result: MarketRiskResult) -> dict[str, Any]:
    """Parquet close-row score columns for a result (None values omitted)."""
    fields: dict[str, Any] = {
        SCORE_COLUMN: result.score,
        SCORE_EMA_COLUMN: result.score_ema,
        BAND_COLUMN: result.band,
        REGIME_COLUMN: result.regime,
        DEGRADED_COLUMN: bool(result.degraded),
        COVERAGE_COLUMN: result.coverage_ratio,
        MISSING_COLUMN: list(result.missing_components),
        RISK_ASOF_COLUMN: result.asof_ts,
    }
    for name, component in result.components.items():
        if component.sub is not None:
            fields[f"{SUB_COLUMN_PREFIX}{name}"] = component.sub
    return {key: value for key, value in fields.items() if value is not None}


# ---------------------------------------------------------------------------
# Hindcast (§4.4 backtest/ex-post validation)
# ---------------------------------------------------------------------------


def seed_state_from_records(
    records: Sequence[Mapping[str, Any]],
) -> tuple[float | None, BandState]:
    """Recover (prev_ema, band state) from prior close rows' score columns."""
    prev_ema: float | None = None
    band: str | None = None
    degraded = False
    for row in records:
        ema = _as_float(row.get(SCORE_EMA_COLUMN))
        if ema is not None:
            prev_ema = ema
        stored_band = row.get(BAND_COLUMN)
        if _is_present(stored_band):
            band = str(stored_band)
            stored_degraded = row.get(DEGRADED_COLUMN)
            degraded = bool(stored_degraded) if _is_present(stored_degraded) else False
    return prev_ema, BandState(band=band, degraded=degraded)


def hindcast(
    store: Any,
    config: MarketRiskConfig,
    start: date,
    end: date,
    *,
    write: bool = False,
) -> list[MarketRiskResult]:
    """Recompute daily score/band/regime over backfilled close rows (§4.4).

    Walks close rows in date order; each day's normalization window sees only
    rows strictly before that day (no look-ahead), and EMA/hysteresis state is
    threaded in-memory. With ``write=True`` the score columns are merged back
    into each existing close row via idempotent ``replace_day``.
    """
    if start > end:
        raise ValueError("hindcast start must be <= end")

    from datetime import timedelta

    lookback = timedelta(days=config.runner.history_lookback_days)
    frame = store.read_range(start - lookback, end, snapshot="close")
    records = history_records(frame)

    before_start = [
        row for row in records if _coerce_date(row.get("trade_date")) < start
    ]
    prev_ema, state = seed_state_from_records(before_start)

    results: list[MarketRiskResult] = []
    for index, row in enumerate(records):
        day = _coerce_date(row.get("trade_date"))
        if day is None or day < start or day > end:
            continue
        history = records[:index]
        result, state = compute_market_risk(
            current_row=row,
            history=history,
            config=config,
            trade_date=day,
            kind="hindcast",
            prev_ema=prev_ema,
            band_state=state,
        )
        if result.score_ema is not None:
            prev_ema = result.score_ema
        results.append(result)

        if write:
            base = {key: value for key, value in row.items() if _is_present(value)}
            base.update(risk_row_fields(result))
            store.replace_day(day, "close", base)
            # Keep in-memory records consistent with what was persisted so
            # later days window over the same values a re-run would see.
            records[index] = base

    return results
