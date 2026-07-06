"""FuturesMarketContextV2 — structured futures context for strategies/gates.

Design doc: docs/plans/2026-07-05-futures-market-context-hedge-risk-hardening.md
§4.3. This is NOT the LLM narrative ``shared.decision.context.MarketContext``:
it is a structured snapshot composed from the existing read-models (Phase A
contract state + market structure + Market Risk Score + Phase B margin), so
strategy/gate code can read one futures-operational context instead of stitching
four Redis hashes.

Naming discipline (§3.2): the composite 0-100 Market Risk Score is exposed as
``market_risk_score`` here — deliberately distinct from the LLM MarketContext's
own ``risk_score``.

Pure/derived-only: :func:`build_futures_context` computes NO market data; it
labels + folds already-published inputs. Redis/stream glue lives in
:mod:`services.futures_context.main`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from shared.utils.coercion import to_bool as _to_bool
from shared.utils.coercion import to_float as _to_float
from shared.utils.coercion import to_int as _to_int
from shared.utils.coercion import to_text as _text

#: Schema version published in the ``futures:context:latest`` contract.
FUTURES_CONTEXT_SCHEMA_VERSION = 1

BasisRegime = Literal[
    "deep_backwardation", "backwardation", "fair", "contango", "deep_contango"
]
ForeignFlowRegime = Literal["strong_sell", "sell", "neutral", "buy", "strong_buy"]


@dataclass(frozen=True)
class BasisRegimeThresholds:
    """Basis-regime classification bands (index points from fair value)."""

    fair_band_points: float
    deep_band_points: float


@dataclass(frozen=True)
class ForeignFlowThresholds:
    """Foreign-flow-regime classification bands (net contracts)."""

    neutral_qty: float
    strong_qty: float


@dataclass(frozen=True)
class FuturesMarketContextV2:
    """One structured futures context snapshot (published; never executed)."""

    schema_version: int
    product: str
    # contract (Phase A)
    front_symbol: str | None
    days_to_expiry: int | None
    roll_state: str | None
    new_entry_front_allowed: bool | None
    # basis
    basis: float | None
    basis_dev: float | None
    basis_dev_ma5: float | None
    basis_regime: BasisRegime | None
    carry_pressure: float | None
    # OI
    fut_oi_qty: float | None
    fut_oi_change: float | None
    oi_price_signal: str | None
    # foreign flow
    fut_foreign_net_qty: float | None
    fut_foreign_net_qty_cum20: float | None
    foreign_flow_regime: ForeignFlowRegime | None
    # risk score (composite Market Risk Score — NOT the LLM risk_score)
    market_risk_score: float | None
    market_risk_band: str | None
    unified_regime: str | None
    # margin (Phase B)
    margin_usage_pct: float | None
    liquidation_buffer_ticks: float | None
    margin_risk_level: str | None
    # execution
    tick_value_krw: float | None
    spread_ticks: float | None
    depth_ratio: float | None
    slippage_guard_state: str | None
    # health
    degraded: bool
    missing_components: tuple[str, ...]
    asof_ts: datetime


def classify_basis_regime(
    basis_dev: float | None, thresholds: BasisRegimeThresholds
) -> BasisRegime | None:
    """Label ``basis_dev`` (futures − fair value) into a basis regime.

    Positive dev = futures rich vs fair (contango pressure); negative =
    backwardation. ``|dev|`` within ``fair_band_points`` is ``fair``.
    """
    if basis_dev is None:
        return None
    if abs(basis_dev) < thresholds.fair_band_points:
        return "fair"
    if basis_dev > 0:
        return (
            "deep_contango" if basis_dev >= thresholds.deep_band_points else "contango"
        )
    return (
        "deep_backwardation"
        if basis_dev <= -thresholds.deep_band_points
        else "backwardation"
    )


def carry_pressure(basis_dev: float | None, days_to_expiry: int | None) -> float | None:
    """Basis deviation amplified as expiry approaches (annualization proxy).

    ``basis_dev`` must converge to zero by expiry, so the same deviation is a
    stronger daily carry pull the fewer days remain. Returns ``basis_dev``
    scaled by ``1 + 1/max(days_to_expiry, 1)``; None when either input is None.
    A non-positive ``days_to_expiry`` (expiry day) uses the strongest scale.

    The ``1 + 1/dte`` factor is a fixed mathematical normalization (the
    convergence-to-expiry proxy), NOT a tunable — deliberately not config-driven.
    """
    if basis_dev is None or days_to_expiry is None:
        return None
    dte = max(days_to_expiry, 1)
    return basis_dev * (1.0 + 1.0 / dte)


def classify_foreign_flow_regime(
    net_qty: float | None, thresholds: ForeignFlowThresholds
) -> ForeignFlowRegime | None:
    """Label today's foreign futures net contracts into a flow regime."""
    if net_qty is None:
        return None
    if abs(net_qty) < thresholds.neutral_qty:
        return "neutral"
    if net_qty > 0:
        return "strong_buy" if net_qty >= thresholds.strong_qty else "buy"
    return "strong_sell" if net_qty <= -thresholds.strong_qty else "sell"


def build_futures_context(
    *,
    product: str,
    contract: Mapping[str, Any] | None,
    structure: Mapping[str, Any] | None,
    risk: Mapping[str, Any] | None,
    margin: Mapping[str, Any] | None,
    tick_value_krw: float | None,
    basis_thresholds: BasisRegimeThresholds,
    foreign_thresholds: ForeignFlowThresholds,
    asof_ts: datetime,
    extra_missing: tuple[str, ...] = (),
) -> FuturesMarketContextV2:
    """Fold the four upstream read-models into one structured context.

    Each upstream input is optional: a missing/empty hash adds its name to
    ``missing_components`` and leaves its fields None — the context is always
    published (plan §C validation: upstream key loss degrades, never blocks).
    """
    missing: list[str] = list(extra_missing)
    contract = contract or {}
    structure = structure or {}
    risk = risk or {}
    margin = margin or {}
    if not contract:
        missing.append("contract")
    if not structure:
        missing.append("structure")
    if not risk:
        missing.append("risk")
    if not margin:
        missing.append("margin")

    # --- contract (Phase A) ---------------------------------------------
    front_symbol = _text(contract.get("front_symbol"))
    days_to_expiry = _to_int(contract.get("days_to_expiry"))
    roll_state = _text(contract.get("roll_state"))
    new_entry_front_allowed = _to_bool(contract.get("new_entry_front_allowed"))

    # --- basis -----------------------------------------------------------
    basis = _to_float(structure.get("basis"))
    basis_dev = _to_float(structure.get("basis_dev"))
    basis_dev_ma5 = _to_float(structure.get("basis_dev_ma5"))
    basis_regime = classify_basis_regime(basis_dev, basis_thresholds)
    carry = carry_pressure(basis_dev, days_to_expiry)

    # --- OI --------------------------------------------------------------
    fut_oi_qty = _to_float(structure.get("fut_oi_qty"))
    fut_oi_change = _to_float(structure.get("fut_oi_change"))
    oi_price_signal = _text(structure.get("oi_price_signal"))

    # --- foreign flow ----------------------------------------------------
    fut_foreign_net_qty = _to_float(structure.get("fut_foreign_net_qty"))
    fut_foreign_net_qty_cum20 = _to_float(structure.get("fut_foreign_net_qty_cum20"))
    foreign_flow_regime = classify_foreign_flow_regime(
        fut_foreign_net_qty, foreign_thresholds
    )

    # --- risk score (composite; NOT the LLM risk_score) -----------------
    market_risk_score = _to_float(risk.get("score"))
    market_risk_band = _text(risk.get("band"))
    unified_regime = _text(risk.get("regime"))

    # --- margin (Phase B) ------------------------------------------------
    margin_usage_pct = _to_float(margin.get("margin_usage_pct"))
    liquidation_buffer_ticks = _to_float(margin.get("liquidation_buffer_ticks"))
    margin_risk_level = _text(margin.get("risk_level"))

    # --- execution -------------------------------------------------------
    # Only tick_value_krw has a read-model source today (contract spec). The
    # slippage guard is a per-quote runtime check with no published snapshot,
    # so spread/depth/guard-state are recorded missing rather than faked.
    if tick_value_krw is None:
        missing.append("tick_value")
    missing.append("slippage_snapshot")  # no published slippage read-model yet

    degraded = bool(missing)

    return FuturesMarketContextV2(
        schema_version=FUTURES_CONTEXT_SCHEMA_VERSION,
        product=product,
        front_symbol=front_symbol,
        days_to_expiry=days_to_expiry,
        roll_state=roll_state,
        new_entry_front_allowed=new_entry_front_allowed,
        basis=basis,
        basis_dev=basis_dev,
        basis_dev_ma5=basis_dev_ma5,
        basis_regime=basis_regime,
        carry_pressure=carry,
        fut_oi_qty=fut_oi_qty,
        fut_oi_change=fut_oi_change,
        oi_price_signal=oi_price_signal,
        fut_foreign_net_qty=fut_foreign_net_qty,
        fut_foreign_net_qty_cum20=fut_foreign_net_qty_cum20,
        foreign_flow_regime=foreign_flow_regime,
        market_risk_score=market_risk_score,
        market_risk_band=market_risk_band,
        unified_regime=unified_regime,
        margin_usage_pct=margin_usage_pct,
        liquidation_buffer_ticks=liquidation_buffer_ticks,
        margin_risk_level=margin_risk_level,
        tick_value_krw=tick_value_krw,
        spread_ticks=None,
        depth_ratio=None,
        slippage_guard_state=None,
        degraded=degraded,
        missing_components=tuple(missing),
        asof_ts=asof_ts,
    )


def context_trace_payload(fields: Mapping[str, Any]) -> dict[str, Any]:
    """Compact futures-context trace for a decision candidate (fixed keys).

    Reads the already-published ``futures:context:latest`` hash fields (a raw
    Redis mapping) into a small trace payload attached to entry candidates in
    the decision engine — observational only (shadow), never gating. Keys are
    frozen with the /signals trace lane. Absent inputs yield None values.
    """
    return {
        "roll_state": _text(fields.get("roll_state")),
        "days_to_expiry": _to_int(fields.get("days_to_expiry")),
        "new_entry_front_allowed": _to_bool(fields.get("new_entry_front_allowed")),
        "basis_regime": _text(fields.get("basis_regime")),
        "carry_pressure": _to_float(fields.get("carry_pressure")),
        "foreign_flow_regime": _text(fields.get("foreign_flow_regime")),
        "market_risk_band": _text(fields.get("market_risk_band")),
        "margin_risk_level": _text(fields.get("margin_risk_level")),
        "margin_usage_pct": _to_float(fields.get("margin_usage_pct")),
        "degraded": _to_bool(fields.get("degraded")),
        "asof_ts": _text(fields.get("asof_ts")),
    }


def _fmt(value: float | None) -> str:
    """Absent values publish as "" (repo null marker)."""
    return "" if value is None else f"{float(value):.4f}"


def context_to_fields(context: FuturesMarketContextV2) -> dict[str, str]:
    """Flatten a context into the ``futures:context:latest`` hash."""
    return {
        "schema_version": str(context.schema_version),
        "product": context.product,
        "front_symbol": context.front_symbol or "",
        "days_to_expiry": (
            "" if context.days_to_expiry is None else str(context.days_to_expiry)
        ),
        "roll_state": context.roll_state or "",
        "new_entry_front_allowed": (
            ""
            if context.new_entry_front_allowed is None
            else ("true" if context.new_entry_front_allowed else "false")
        ),
        "basis": _fmt(context.basis),
        "basis_dev": _fmt(context.basis_dev),
        "basis_dev_ma5": _fmt(context.basis_dev_ma5),
        "basis_regime": context.basis_regime or "",
        "carry_pressure": _fmt(context.carry_pressure),
        "fut_oi_qty": _fmt(context.fut_oi_qty),
        "fut_oi_change": _fmt(context.fut_oi_change),
        "oi_price_signal": context.oi_price_signal or "",
        "fut_foreign_net_qty": _fmt(context.fut_foreign_net_qty),
        "fut_foreign_net_qty_cum20": _fmt(context.fut_foreign_net_qty_cum20),
        "foreign_flow_regime": context.foreign_flow_regime or "",
        "market_risk_score": _fmt(context.market_risk_score),
        "market_risk_band": context.market_risk_band or "",
        "unified_regime": context.unified_regime or "",
        "margin_usage_pct": _fmt(context.margin_usage_pct),
        "liquidation_buffer_ticks": _fmt(context.liquidation_buffer_ticks),
        "margin_risk_level": context.margin_risk_level or "",
        "tick_value_krw": _fmt(context.tick_value_krw),
        "spread_ticks": _fmt(context.spread_ticks),
        "depth_ratio": _fmt(context.depth_ratio),
        "slippage_guard_state": context.slippage_guard_state or "",
        "degraded": "true" if context.degraded else "false",
        "missing_components": json.dumps(
            list(context.missing_components), ensure_ascii=False
        ),
        "asof_ts": context.asof_ts.isoformat(),
    }
