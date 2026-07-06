"""Cross-asset hedge advisor — pure computation (Phase 4A, advisory ONLY).

Roadmap §5.4: net the Track B stock long β-exposure against the signed
futures exposure and recommend a MINI KOSPI200 short-contract count. The
output of this module (and of the whole hedge lane) is Redis state, ledger
history, Telegram text, and logs — **never orders**. This module must not
import ``shared.execution`` or any order path; unit tests pin that absence
on the full import graph.

Everything here is deterministic and I/O-free: callers inject positions,
close series, contract specs, and market inputs. Redis/ledger/Telegram glue
lives in :mod:`services.portfolio_monitor.hedge_advisor`.

Formulas (config-driven, no magic numbers):

* ``β_i``: OLS slope of symbol daily returns vs K200 daily returns over the
  last ``beta.window_trading_days`` aligned observations (cov/var); clipped
  to ``[clip_min, clip_max]``; ``default_beta`` fallback below
  ``min_observations`` (coverage recorded).
* ``beta_notional = Σ long_notional_i × β_i`` (Track B spot longs).
* ``futures_net_notional = Σ signed_qty × price × multiplier(held product)``
  — the multiplier follows the HELD product (full or mini), resolved by
  symbol prefix from ``config/execution.yaml::futures_contract_spec``.
* ``net_beta_exposure = beta_notional + futures_net_notional``.
* Recommendation (only when ``net_beta_exposure > 0`` and the futures price
  is fresh): ``floor(net / (fut_price × mini_multiplier))`` (rounding policy
  config; floor prevents over-hedging). ``net <= 0`` → 0 (never recommend
  adding longs).
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, model_validator

from shared.config.base import ServiceConfigBase
from shared.config.loader import ConfigNotFoundError

logger = logging.getLogger(__name__)

#: Fixed product identifier published in the Redis contract (4B UI lane).
HEDGE_PRODUCT_MINI_KOSPI200 = "mini_kospi200"


# ---------------------------------------------------------------------------
# Configuration (config/hedge_advisor.yaml)
# ---------------------------------------------------------------------------


class HedgeProductConfig(BaseModel):
    """Hedge instrument parameters (mini KOSPI200 — roadmap O4 decision).

    ``multiplier_krw_per_point``/``tick_size_points`` are declared here for
    the hedge contract's own math but are cross-checked at runtime against
    ``config/execution.yaml::futures_contract_spec[execution_spec_key]`` via
    :func:`verify_product_spec` — the execution YAML stays the single source
    of contract constants without this lane importing ``shared.execution``.
    """

    name: str = Field(default=HEDGE_PRODUCT_MINI_KOSPI200)
    execution_spec_key: str = Field(default="kospi200_mini")
    multiplier_krw_per_point: int = Field(default=50_000, gt=0)
    tick_size_points: float = Field(default=0.02, gt=0)
    cross_check_execution_spec: bool = Field(default=True)


class HedgeFuturesProductRef(BaseModel):
    """Symbol-prefix mapping for one held futures product."""

    symbol_prefixes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_prefixes(self) -> HedgeFuturesProductRef:
        cleaned = [str(p).strip() for p in self.symbol_prefixes if str(p).strip()]
        if not cleaned:
            raise ValueError("symbol_prefixes must not be empty")
        self.symbol_prefixes = cleaned
        return self


def _default_futures_products() -> dict[str, HedgeFuturesProductRef]:
    # Prefixes mirror shared/instruments/futures.py (A05/105 mini, A01/101
    # full); multiplier VALUES always come from config/execution.yaml.
    return {
        "kospi200_mini": HedgeFuturesProductRef(symbol_prefixes=["A05", "105"]),
        "kospi200_full": HedgeFuturesProductRef(symbol_prefixes=["A01", "101"]),
    }


class HedgeFuturesExposureConfig(BaseModel):
    """Held-futures product resolution (full positions may coexist)."""

    products: dict[str, HedgeFuturesProductRef] = Field(
        default_factory=_default_futures_products
    )


class BetaEstimationConfig(BaseModel):
    """β regression knobs — window, floor, clipping, fallback."""

    window_trading_days: int = Field(default=120, gt=1)
    min_observations: int = Field(default=60, gt=1)
    clip_min: float = Field(default=0.0)
    clip_max: float = Field(default=3.0)
    default_beta: float = Field(default=1.0)
    lookback_calendar_days: int = Field(default=260, gt=0)

    @model_validator(mode="after")
    def _validate_bounds(self) -> BetaEstimationConfig:
        if self.clip_min > self.clip_max:
            raise ValueError("beta clip_min must be <= clip_max")
        if self.min_observations > self.window_trading_days:
            raise ValueError("beta min_observations must be <= window_trading_days")
        return self


class HedgeAdvisoryConfig(BaseModel):
    """Advisory activation and rounding policy."""

    trigger_band: str = Field(default="HIGH")
    band_order: list[str] = Field(
        default_factory=lambda: ["LOW", "NEUTRAL", "ELEVATED", "HIGH", "CRITICAL"]
    )
    rounding: Literal["floor", "nearest", "ceil"] = Field(default="floor")
    futures_price_max_age_hours: float = Field(default=24.0, gt=0)

    @model_validator(mode="after")
    def _validate_trigger(self) -> HedgeAdvisoryConfig:
        if self.trigger_band not in self.band_order:
            raise ValueError(
                f"trigger_band {self.trigger_band!r} not in band_order {self.band_order}"
            )
        return self


class HedgeRedisConfig(BaseModel):
    """Redis publication contract (FIXED with the 4B UI lane) + input keys."""

    latest_key: str = Field(default="portfolio:hedge:latest")
    latest_ttl_seconds: int = Field(default=86400, gt=0)
    stream_key: str = Field(default="stream:portfolio.hedge")
    stream_maxlen: int = Field(default=5000, gt=0)
    stream_ttl_seconds: int = Field(default=86400, gt=0)
    structure_latest_key: str = Field(default="market:structure:latest")
    risk_latest_key: str = Field(default="market:risk:latest")
    # HedgeAdvisorV2 operational read-models (Phase A/B; read-only inputs).
    contract_latest_key: str = Field(default="futures:contract:latest")
    margin_latest_key: str = Field(default="futures:risk:latest")


class HedgeAlertsConfig(BaseModel):
    """Telegram advisory alerts (advisory_active rising edge only)."""

    enabled: bool = Field(default=True)
    domain: str = Field(default="briefing")


class HedgeRiskAdjustmentConfig(BaseModel):
    """HedgeAdvisorV2 target ratio + feasibility constraints (append-only).

    Introduced by docs/plans/2026-07-05-futures-market-context-hedge-risk-
    hardening.md §4.4/§6. Everything here is advisory-only: it shapes the v2
    recommendation (target hedge ratio, margin cap, roll/slippage feasibility)
    but never places an order. Absent config → validated defaults, so the base
    18-field lane is unaffected when the section is missing.
    """

    # Target hedge ratio (0-1) keyed by market-risk band. A band absent here
    # falls back to 0.0 (no hedge). Band names must match advisory.band_order.
    target_hedge_ratio_by_band: dict[str, float] = Field(
        default_factory=lambda: {
            "LOW": 0.0,
            "NEUTRAL": 0.0,
            "ELEVATED": 0.25,
            "HIGH": 0.50,
            "CRITICAL": 0.75,
        }
    )
    # Above this estimated entry slippage, cap the delta or mark limited.
    max_estimated_slippage_ticks: float = Field(default=2.0, gt=0)
    # When true, a missing/stale margin or contract read forces degraded=0.
    require_margin_state: bool = Field(default=True)
    require_contract_state: bool = Field(default=True)

    @model_validator(mode="after")
    def _validate_ratios(self) -> HedgeRiskAdjustmentConfig:
        for band, ratio in self.target_hedge_ratio_by_band.items():
            if not 0.0 <= ratio <= 1.0:
                raise ValueError(
                    f"target_hedge_ratio_by_band[{band}]={ratio} must be in [0, 1]"
                )
        return self


class HedgeAdvisorConfig(ServiceConfigBase):
    """Top-level hedge advisor config from ``config/hedge_advisor.yaml``."""

    _default_config_file: ClassVar[str] = "hedge_advisor.yaml"

    enabled: bool = Field(default=True)
    product: HedgeProductConfig = Field(default_factory=HedgeProductConfig)
    futures_exposure: HedgeFuturesExposureConfig = Field(
        default_factory=HedgeFuturesExposureConfig
    )
    beta: BetaEstimationConfig = Field(default_factory=BetaEstimationConfig)
    advisory: HedgeAdvisoryConfig = Field(default_factory=HedgeAdvisoryConfig)
    redis: HedgeRedisConfig = Field(default_factory=HedgeRedisConfig)
    alerts: HedgeAlertsConfig = Field(default_factory=HedgeAlertsConfig)
    risk_adjustment: HedgeRiskAdjustmentConfig = Field(
        default_factory=HedgeRiskAdjustmentConfig
    )

    @classmethod
    def load_or_default(cls, path: str | None = None) -> HedgeAdvisorConfig:
        """Load from YAML when available, otherwise return validated defaults."""
        try:
            return cls.from_yaml(path)
        except ConfigNotFoundError:
            return cls()


# ---------------------------------------------------------------------------
# Contract-spec cross-check (config/execution.yaml stays the single source)
# ---------------------------------------------------------------------------


def verify_product_spec(
    config: HedgeAdvisorConfig, execution_specs: Mapping[str, Any]
) -> None:
    """Cross-check the hedge product against the execution contract spec.

    ``execution_specs`` is the raw ``futures_contract_spec`` mapping from
    ``config/execution.yaml`` (loaded by the caller via ConfigLoader — this
    module never imports ``shared.execution``). Raises ``ValueError`` on any
    mismatch so a wrong contract size can never silently shape advice.
    """
    product = config.product
    if not product.cross_check_execution_spec:
        return
    spec = execution_specs.get(product.execution_spec_key)
    if not isinstance(spec, Mapping):
        raise ValueError(
            "config/execution.yaml::futures_contract_spec."
            f"{product.execution_spec_key} missing — cannot verify hedge product"
        )
    multiplier = spec.get("multiplier_krw_per_point")
    tick = spec.get("tick_size_points")
    if multiplier is None or int(multiplier) != int(product.multiplier_krw_per_point):
        raise ValueError(
            f"hedge product multiplier {product.multiplier_krw_per_point} != "
            f"execution spec {multiplier} ({product.execution_spec_key})"
        )
    if tick is None or abs(float(tick) - float(product.tick_size_points)) > 1e-12:
        raise ValueError(
            f"hedge product tick {product.tick_size_points} != "
            f"execution spec {tick} ({product.execution_spec_key})"
        )


def product_multipliers(
    config: HedgeAdvisorConfig, execution_specs: Mapping[str, Any]
) -> dict[str, float]:
    """Multiplier per configured held-product key, from the execution spec."""
    multipliers: dict[str, float] = {}
    for key in config.futures_exposure.products:
        spec = execution_specs.get(key)
        if isinstance(spec, Mapping) and spec.get("multiplier_krw_per_point"):
            multipliers[key] = float(spec["multiplier_krw_per_point"])
        else:
            logger.warning("futures_contract_spec.%s missing multiplier", key)
    return multipliers


def multiplier_for_symbol(
    symbol: str,
    config: HedgeAdvisorConfig,
    multipliers: Mapping[str, float],
) -> float | None:
    """Resolve a held futures symbol to its product multiplier (or None).

    Prefix semantics match ``shared.execution.contract_spec.resolve_contract_spec``
    (documented parity — that module is an order-path import this lane must
    not take).
    """
    code = str(symbol or "").strip()
    if not code:
        return None
    for key, ref in config.futures_exposure.products.items():
        if key in multipliers and code.startswith(tuple(ref.symbol_prefixes)):
            return multipliers[key]
    return None


# ---------------------------------------------------------------------------
# β estimation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BetaEstimate:
    """One symbol's β with observation count and fallback flag."""

    beta: float
    observations: int
    fallback: bool


def compute_returns(
    closes: Sequence[tuple[date, float]],
) -> list[tuple[date, float]]:
    """Simple daily returns from a (date, close) series (unsorted OK).

    Non-positive/invalid closes are dropped; returns are computed between
    consecutive *remaining* days, keyed by the later day.
    """
    cleaned: list[tuple[date, float]] = []
    for day, close in closes:
        try:
            value = float(close)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value) or value <= 0 or day is None:
            continue
        cleaned.append((day, value))
    cleaned.sort(key=lambda item: item[0])
    returns: list[tuple[date, float]] = []
    for (_, prev), (day, curr) in zip(cleaned, cleaned[1:], strict=False):
        returns.append((day, curr / prev - 1.0))
    return returns


def estimate_beta(
    symbol_closes: Sequence[tuple[date, float]],
    market_closes: Sequence[tuple[date, float]],
    config: BetaEstimationConfig,
) -> BetaEstimate:
    """β = cov(r_i, r_m) / var(r_m) over the last ``window_trading_days``
    date-aligned observations, clipped; ``default_beta`` fallback when the
    aligned sample is smaller than ``min_observations`` (coverage recorded
    by the caller) or the market variance is degenerate.
    """
    symbol_returns = dict(compute_returns(symbol_closes))
    market_returns = dict(compute_returns(market_closes))
    common = sorted(set(symbol_returns) & set(market_returns))
    window = common[-config.window_trading_days :]
    if len(window) < config.min_observations:
        return BetaEstimate(
            beta=config.default_beta, observations=len(window), fallback=True
        )

    xs = [market_returns[day] for day in window]
    ys = [symbol_returns[day] for day in window]
    n = float(len(window))
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs) / n
    if var_x <= 0.0:
        return BetaEstimate(
            beta=config.default_beta, observations=len(window), fallback=True
        )
    cov_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / n
    beta = cov_xy / var_x
    beta = min(max(beta, config.clip_min), config.clip_max)
    return BetaEstimate(beta=beta, observations=len(window), fallback=False)


# ---------------------------------------------------------------------------
# Exposure + advice
# ---------------------------------------------------------------------------


def side_sign(side: Any) -> float:
    """+1 long/buy, -1 short/sell — parity with the dashboard risk-exposure
    board (services/dashboard/routes/trading.py::_side_sign)."""
    return -1.0 if str(side).strip().lower() in {"short", "sell"} else 1.0


def _to_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def is_price_fresh(
    price_asof: datetime | None, now: datetime, max_age_hours: float
) -> bool:
    """True when the futures price timestamp is within the freshness bound.

    Both timestamps are KST-naive (repo convention). A missing or future-
    dated ``price_asof`` is treated as stale (fail-safe: no recommendation).
    """
    if price_asof is None:
        return False
    age = now - price_asof
    return timedelta(0) <= age <= timedelta(hours=max_age_hours)


@dataclass(frozen=True)
class HedgeAdvice:
    """One evaluated hedge advisory (published + ledgered; NEVER executed)."""

    product: str
    multiplier: int
    futures_price: float | None
    stock_long_notional: float
    portfolio_beta: float | None
    beta_notional: float
    futures_net_contracts: int
    futures_net_notional: float
    net_beta_exposure: float
    recommended_short_contracts: int
    residual_exposure_after: float
    band: str | None
    score: float | None
    advisory_active: bool
    reason: str
    degraded: bool
    missing_components: tuple[str, ...]
    asof_ts: datetime


def _round_contracts(raw: float, policy: str) -> int:
    if policy == "ceil":
        return max(int(math.ceil(raw)), 0)
    if policy == "nearest":
        return max(int(math.floor(raw + 0.5)), 0)
    # floor (default): never over-hedge.
    return max(int(math.floor(raw)), 0)


def compute_hedge_advice(
    *,
    config: HedgeAdvisorConfig,
    stock_positions: Sequence[Mapping[str, Any]],
    futures_positions: Sequence[Mapping[str, Any]],
    betas: Mapping[str, BetaEstimate],
    multipliers: Mapping[str, float],
    futures_price: float | None,
    futures_price_fresh: bool,
    band: str | None,
    score: float | None,
    asof_ts: datetime,
    extra_missing: Sequence[str] = (),
) -> HedgeAdvice:
    """Fold positions + βs + market inputs into one :class:`HedgeAdvice`.

    Args:
        config: Hedge advisor configuration.
        stock_positions: Track B open positions (trading-state hash rows:
            ``code``/``side``/``quantity``/``current_price``). Only longs
            contribute (stock pipeline is long-only by rule).
        futures_positions: Track C open positions; signed by ``side``, each
            valued with its OWN product multiplier (full or mini).
        betas: Symbol → :class:`BetaEstimate` (missing symbol → default β,
            coverage recorded).
        multipliers: Product key → KRW-per-point (from execution spec).
        futures_price: Mini-K200-equivalent index price (``fut_close`` from
            ``market:structure:latest``); None when absent.
        futures_price_fresh: Caller-evaluated freshness (see
            :func:`is_price_fresh`). Stale/absent → recommendation SKIPPED
            and the run marked degraded.
        band: Current market-risk band (``market:risk:latest``), or None.
        score: Current market-risk score, or None.
        asof_ts: KST-naive evaluation timestamp.
        extra_missing: Upstream coverage entries (e.g. provider failures).
    """
    missing: list[str] = list(extra_missing)
    beta_cfg = config.beta

    # --- Track B spot long β-notional -----------------------------------
    stock_long_notional = 0.0
    beta_notional = 0.0
    for position in stock_positions:
        if side_sign(position.get("side", "long")) < 0:
            continue  # stock pipeline is long-only; ignore anomalous shorts
        quantity = _to_float(position.get("quantity"))
        price = _to_float(position.get("current_price"))
        if quantity is None or price is None or quantity <= 0 or price <= 0:
            continue
        symbol = str(position.get("code", "")).strip()
        notional = price * quantity
        estimate = betas.get(symbol)
        if estimate is None:
            estimate = BetaEstimate(
                beta=beta_cfg.default_beta, observations=0, fallback=True
            )
        if estimate.fallback:
            missing.append(f"beta:{symbol or 'unknown'}")
        stock_long_notional += notional
        beta_notional += notional * estimate.beta

    portfolio_beta = (
        beta_notional / stock_long_notional if stock_long_notional > 0 else None
    )

    # --- Track C futures signed notional (held-product multiplier) ------
    futures_net_contracts = 0
    futures_net_notional = 0.0
    for position in futures_positions:
        quantity = _to_float(position.get("quantity"))
        price = _to_float(position.get("current_price"))
        if quantity is None or price is None or quantity <= 0 or price <= 0:
            continue
        symbol = str(position.get("code", "")).strip()
        multiplier = multiplier_for_symbol(symbol, config, multipliers)
        if multiplier is None:
            missing.append(f"futures_product:{symbol or 'unknown'}")
            continue
        sign = side_sign(position.get("side", "long"))
        futures_net_contracts += int(sign * quantity)
        futures_net_notional += sign * quantity * price * multiplier

    net_beta_exposure = beta_notional + futures_net_notional

    # --- Market inputs coverage -----------------------------------------
    if band is None or band not in config.advisory.band_order:
        if band is not None:
            logger.warning("unknown market-risk band %r", band)
        band = band if band in config.advisory.band_order else None
        missing.append("risk_band")
    if score is None:
        missing.append("risk_score")

    hedge_multiplier = int(config.product.multiplier_krw_per_point)
    price_ok = futures_price is not None and futures_price > 0 and futures_price_fresh
    if not price_ok:
        missing.append("futures_price")

    # --- Recommendation ---------------------------------------------------
    fmt_krw = "{:,.0f}".format
    base = (
        f"β-notional ₩{fmt_krw(beta_notional)}"
        f" (stock long ₩{fmt_krw(stock_long_notional)}"
        f" × weighted β {portfolio_beta:.2f})"
        if portfolio_beta is not None
        else f"β-notional ₩{fmt_krw(beta_notional)} (no stock longs)"
    )
    base += (
        f" + futures net ₩{fmt_krw(futures_net_notional)}"
        f" ({futures_net_contracts} contracts)"
        f" = net β-exposure ₩{fmt_krw(net_beta_exposure)}"
    )

    if not price_ok:
        recommended = 0
        residual = net_beta_exposure
        reason = (
            f"{base}; futures price stale/unavailable —"
            " recommendation skipped (degraded)"
        )
    elif net_beta_exposure > 0:
        contract_value = float(futures_price) * hedge_multiplier
        raw = net_beta_exposure / contract_value
        recommended = _round_contracts(raw, config.advisory.rounding)
        residual = net_beta_exposure - recommended * contract_value
        reason = (
            f"{base}; ₩{fmt_krw(net_beta_exposure)}"
            f" ÷ ({futures_price:.2f}pt × ₩{hedge_multiplier:,}/pt)"
            f" = {raw:.2f} → {config.advisory.rounding}"
            f" → {recommended} mini short contract(s),"
            f" residual ₩{fmt_krw(residual)}"
        )
    else:
        recommended = 0
        residual = net_beta_exposure
        reason = (
            f"{base}; net β-exposure <= 0 — no hedge needed"
            " (0 contracts; long add-on is never recommended)"
        )

    # --- Advisory activation ----------------------------------------------
    order = config.advisory.band_order
    band_triggered = band is not None and order.index(band) >= order.index(
        config.advisory.trigger_band
    )
    advisory_active = bool(band_triggered and recommended >= 1)

    return HedgeAdvice(
        product=config.product.name,
        multiplier=hedge_multiplier,
        futures_price=float(futures_price) if futures_price is not None else None,
        stock_long_notional=stock_long_notional,
        portfolio_beta=portfolio_beta,
        beta_notional=beta_notional,
        futures_net_contracts=futures_net_contracts,
        futures_net_notional=futures_net_notional,
        net_beta_exposure=net_beta_exposure,
        recommended_short_contracts=recommended,
        residual_exposure_after=residual,
        band=band,
        score=score,
        advisory_active=advisory_active,
        reason=reason,
        degraded=bool(missing),
        missing_components=tuple(missing),
        asof_ts=asof_ts,
    )


# ---------------------------------------------------------------------------
# Redis contract mapping (FIXED with the 4B UI lane — do not rename fields)
# ---------------------------------------------------------------------------


def _fmt(value: float | None) -> str:
    """Fixed contract null marker: absent values publish as ""."""
    return "" if value is None else f"{float(value):.4f}"


def advice_to_latest_fields(advice: HedgeAdvice) -> dict[str, str]:
    """``portfolio:hedge:latest`` hash mapping — FIXED 4B UI contract."""
    import json

    return {
        "product": advice.product,
        "multiplier": str(advice.multiplier),
        "futures_price": _fmt(advice.futures_price),
        "stock_long_notional": _fmt(advice.stock_long_notional),
        "portfolio_beta": _fmt(advice.portfolio_beta),
        "beta_notional": _fmt(advice.beta_notional),
        "futures_net_contracts": str(advice.futures_net_contracts),
        "futures_net_notional": _fmt(advice.futures_net_notional),
        "net_beta_exposure": _fmt(advice.net_beta_exposure),
        "recommended_short_contracts": str(advice.recommended_short_contracts),
        "residual_exposure_after": _fmt(advice.residual_exposure_after),
        "band": advice.band or "",
        "score": _fmt(advice.score),
        "advisory_active": "true" if advice.advisory_active else "false",
        "reason": advice.reason,
        "degraded": "true" if advice.degraded else "false",
        "missing_components": json.dumps(
            list(advice.missing_components), ensure_ascii=False
        ),
        "asof_ts": advice.asof_ts.isoformat(),
    }


# ---------------------------------------------------------------------------
# HedgeAdvisorV2 — append-only feasibility layer (advisory ONLY, no orders)
# ---------------------------------------------------------------------------
#
# docs/plans/2026-07-05-futures-market-context-hedge-risk-hardening.md §4.4:
# constrain the recommended contract count by a target hedge ratio (band-
# driven), the margin cap, roll state, and an estimated-slippage limit. This
# layer WRAPS the base HedgeAdvice and adds 9 append-only fields; the fixed
# 18-field contract above is never changed. Everything remains advisory:
# still no order path, still Redis/ledger/Telegram only.
#
# Inputs are dependency-injected (the roll/margin state come from the Phase A/B
# Redis read-models, read as plain hashes by the runner — this module still
# imports NO order path). ``estimated_slippage_ticks`` is injected too; there
# is no published depth/slippage read-model yet, so the runner passes None and
# the liquidity branch is simply skipped (recorded), mirroring the honest-
# coverage rule used across this hardening.

ExecutionFeasibility = Literal[
    "feasible",
    "limited_by_margin",
    "limited_by_liquidity",
    "blocked_by_roll",
    "degraded",
]
OperatorAction = Literal[
    "none",
    "review",
    "place_manual_hedge",
    "reduce_existing_hedge",
    "roll_position",
]
RollAdjustment = Literal["none", "use_next", "close_front_first", "manual_review"]

#: Roll states (Phase A) that block ADDING front hedge contracts.
_ROLL_BLOCKS_FRONT_ADD = frozenset({"roll_required", "expired"})
#: Margin risk levels (Phase B) that suppress auto-recommending MORE hedge.
_MARGIN_SUPPRESSES_ADD = frozenset({"reduce_only", "block_new_entries", "critical"})


@dataclass(frozen=True)
class HedgeAdviceV2:
    """Base advice + feasibility-constrained v2 recommendation (advisory ONLY)."""

    base: HedgeAdvice
    target_hedge_ratio: float | None
    current_hedge_ratio: float | None
    delta_short_contracts: int
    max_contracts_by_margin: int | None
    margin_after_hedge_pct: float | None
    estimated_slippage_ticks: float | None
    roll_adjustment: RollAdjustment
    execution_feasibility: ExecutionFeasibility
    operator_action: OperatorAction


def target_hedge_ratio_for_band(
    band: str | None, config: HedgeRiskAdjustmentConfig
) -> float | None:
    """Band → target hedge ratio (0-1); None when the band is unknown/absent."""
    if band is None:
        return None
    return config.target_hedge_ratio_by_band.get(band)


def current_hedge_ratio(
    beta_notional: float, futures_net_notional: float
) -> float | None:
    """Fraction of the spot β-notional already offset by SHORT futures.

    Futures net notional is signed (short negative): a short offsets the long
    β-exposure, so the covered fraction is ``-futures_net_notional /
    beta_notional``. Net-long futures (adding exposure) clamp to 0.0. None when
    there is no β-notional to hedge.
    """
    if beta_notional <= 0:
        return None
    return max(-futures_net_notional / beta_notional, 0.0) + 0.0  # normalize -0.0


def _roll_adjustment_for_state(
    roll_state: str | None, needs_add: bool
) -> tuple[RollAdjustment, bool]:
    """(roll_adjustment, blocks_add) for a Phase A roll state.

    Only ADDING front contracts is roll-constrained; reducing an existing
    hedge is always allowed (it de-risks). ``expired`` recommends closing the
    front first; ``roll_required`` recommends using the next contract.
    """
    if not needs_add or roll_state not in _ROLL_BLOCKS_FRONT_ADD:
        return "none", False
    if roll_state == "expired":
        return "close_front_first", True
    return "use_next", True


def compute_hedge_advice_v2(
    *,
    base: HedgeAdvice,
    config: HedgeAdvisorConfig,
    roll_state: str | None,
    hedge_front_allowed: bool | None,
    margin_risk_level: str | None,
    margin_usage_pct: float | None,
    max_additional_contracts: int | None,
    per_contract_initial_margin_krw: float | None,
    account_equity_krw: float | None,
    initial_margin_required_krw: float | None,
    estimated_slippage_ticks: float | None,
    contract_state_present: bool,
    margin_state_present: bool,
) -> HedgeAdviceV2:
    """Constrain the base recommendation by target ratio / margin / roll / slippage.

    Pure and I/O-free. The runner reads the Phase A ``futures:contract:latest``
    and Phase B ``futures:risk:latest`` hashes and passes their fields here;
    this function places no orders and imports no execution path.

    Feasibility precedence (most severe first): ``degraded`` (a required state
    is missing) → ``blocked_by_roll`` → ``limited_by_margin`` → subject to
    ``limited_by_liquidity`` → ``feasible``.
    """
    ra = config.risk_adjustment
    contract_value = None
    if base.futures_price and base.futures_price > 0:
        contract_value = base.futures_price * base.multiplier

    # --- target vs current ratio ----------------------------------------
    target_ratio = target_hedge_ratio_for_band(base.band, ra)
    curr_ratio = current_hedge_ratio(base.beta_notional, base.futures_net_notional)

    # --- required-state gating (fail-safe: degrade to no-op) ------------
    degraded_missing = False
    if ra.require_contract_state and not contract_state_present:
        degraded_missing = True
    if ra.require_margin_state and not margin_state_present:
        degraded_missing = True

    # --- raw delta contracts to reach the target ratio ------------------
    # target short notional = target_ratio * beta_notional; current short
    # notional = -futures_net_notional. delta_notional > 0 → add shorts.
    raw_delta = 0
    if (
        target_ratio is not None
        and contract_value
        and contract_value > 0
        and base.beta_notional > 0
    ):
        target_short_notional = target_ratio * base.beta_notional
        current_short_notional = -base.futures_net_notional
        delta_notional = target_short_notional - current_short_notional
        raw_delta = int(delta_notional / contract_value)  # trunc toward zero

    needs_add = raw_delta > 0
    roll_adjustment, roll_blocks = _roll_adjustment_for_state(roll_state, needs_add)
    if hedge_front_allowed is False and needs_add:
        roll_blocks = True
        if roll_adjustment == "none":
            roll_adjustment = "manual_review"

    # --- feasibility folding --------------------------------------------
    feasibility: ExecutionFeasibility = "feasible"
    applied_delta = raw_delta
    max_by_margin = max_additional_contracts

    if degraded_missing:
        feasibility = "degraded"
        applied_delta = 0
    elif needs_add and roll_blocks:
        feasibility = "blocked_by_roll"
        applied_delta = 0
    elif needs_add and margin_risk_level in _MARGIN_SUPPRESSES_ADD:
        # Margin stress: never auto-recommend MORE hedge; operator reviews
        # (reducing the underlying risk position is preferred — plan §4.4).
        feasibility = "limited_by_margin"
        applied_delta = 0
    elif needs_add and max_by_margin is not None and raw_delta > max_by_margin:
        feasibility = "limited_by_margin"
        applied_delta = max_by_margin

    # Slippage limit (only meaningful when an estimate is supplied AND we are
    # still adding after the checks above). No published depth read-model yet,
    # so the runner passes None → this branch is skipped.
    if (
        applied_delta > 0
        and estimated_slippage_ticks is not None
        and estimated_slippage_ticks > ra.max_estimated_slippage_ticks
    ):
        feasibility = "limited_by_liquidity"
        applied_delta = 0

    # --- margin after the (capped) recommendation -----------------------
    margin_after_pct = _margin_after_hedge_pct(
        applied_delta=applied_delta,
        margin_usage_pct=margin_usage_pct,
        per_contract_initial_margin_krw=per_contract_initial_margin_krw,
        initial_margin_required_krw=initial_margin_required_krw,
        account_equity_krw=account_equity_krw,
    )

    operator_action = _operator_action(
        raw_delta=raw_delta,
        applied_delta=applied_delta,
        feasibility=feasibility,
        target_ratio=target_ratio,
    )

    return HedgeAdviceV2(
        base=base,
        target_hedge_ratio=target_ratio,
        current_hedge_ratio=curr_ratio,
        delta_short_contracts=applied_delta,
        max_contracts_by_margin=max_by_margin,
        margin_after_hedge_pct=margin_after_pct,
        estimated_slippage_ticks=estimated_slippage_ticks,
        roll_adjustment=roll_adjustment,
        execution_feasibility=feasibility,
        operator_action=operator_action,
    )


def _margin_after_hedge_pct(
    *,
    applied_delta: int,
    margin_usage_pct: float | None,
    per_contract_initial_margin_krw: float | None,
    initial_margin_required_krw: float | None,
    account_equity_krw: float | None,
) -> float | None:
    """Predicted margin usage after applying ``applied_delta`` hedge contracts.

    Adding shorts consumes margin; reducing frees it. None when the margin
    inputs are unavailable.
    """
    if (
        margin_usage_pct is None
        or per_contract_initial_margin_krw is None
        or account_equity_krw is None
        or account_equity_krw <= 0
    ):
        return None
    added_margin = applied_delta * per_contract_initial_margin_krw
    if initial_margin_required_krw is not None:
        return (initial_margin_required_krw + added_margin) / account_equity_krw
    return margin_usage_pct + added_margin / account_equity_krw


def _operator_action(
    *,
    raw_delta: int,
    applied_delta: int,
    feasibility: ExecutionFeasibility,
    target_ratio: float | None,
) -> OperatorAction:
    """Map the constrained recommendation to an operator-facing action."""
    if feasibility == "degraded":
        return "review"
    if raw_delta < 0:
        # Over-hedged relative to target → reduce the existing short hedge.
        return "reduce_existing_hedge"
    if raw_delta == 0:
        return "none"
    # raw_delta > 0 (wants more hedge):
    if feasibility == "blocked_by_roll":
        return "roll_position"
    if feasibility in ("limited_by_margin", "limited_by_liquidity"):
        return "review"
    if applied_delta > 0:
        return "place_manual_hedge"
    return "review"


def advice_v2_to_latest_fields(advice_v2: HedgeAdviceV2) -> dict[str, str]:
    """``portfolio:hedge:latest`` hash — base 18 fields + 9 append-only v2 fields.

    The base 18 keys are byte-identical to :func:`advice_to_latest_fields`
    (fixed 4B UI contract); the v2 keys are additive, so existing consumers are
    unaffected and v2-aware consumers get the feasibility view.
    """
    fields = advice_to_latest_fields(advice_v2.base)
    fields.update(
        {
            "target_hedge_ratio": _fmt(advice_v2.target_hedge_ratio),
            "current_hedge_ratio": _fmt(advice_v2.current_hedge_ratio),
            "delta_short_contracts": str(advice_v2.delta_short_contracts),
            "max_contracts_by_margin": (
                ""
                if advice_v2.max_contracts_by_margin is None
                else str(advice_v2.max_contracts_by_margin)
            ),
            "margin_after_hedge_pct": _fmt(advice_v2.margin_after_hedge_pct),
            "estimated_slippage_ticks": _fmt(advice_v2.estimated_slippage_ticks),
            "roll_adjustment": advice_v2.roll_adjustment,
            "execution_feasibility": advice_v2.execution_feasibility,
            "operator_action": advice_v2.operator_action,
        }
    )
    return fields
