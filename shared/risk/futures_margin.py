"""Futures margin / liquidation-buffer / stress-loss math — pure computation.

Design doc: docs/plans/2026-07-05-futures-market-context-hedge-risk-hardening.md
§4.2. This module is deterministic and I/O-free: callers inject open futures
positions, the account equity (broker snapshot or config fallback), per-product
contract + margin specs, a reference price, and per-symbol ATR. Redis/ledger/
Telegram glue lives in :mod:`services.futures_margin_risk.main`.

It models what the stop-distance position sizer does NOT: account margin usage,
the liquidation buffer, and stress loss under adverse moves — so new-entry
sizing (Phase C/E) and hedge feasibility (Phase D) can read a real margin state.

Long/short symmetry: margin, buffer, and stress loss depend on |quantity| (a
short and a long of the same size consume the same margin and lose the same
amount on an equally adverse move), preserving the repo's futures symmetry rule.

Fail policy (plan §2.5): the caller passes ``snapshot_ok`` (was the account
snapshot fresh?) and ``fail_closed`` (live). A missing/stale snapshot in live
(fail_closed) forces ``risk_level=critical``; in paper it only marks the state
``degraded`` and computes best-effort from the config fallback equity.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from shared.utils.coercion import to_float as _to_float

#: Schema version published in the ``futures:risk:latest`` contract.
MARGIN_RISK_SCHEMA_VERSION = 1

#: Risk levels, low → high (index = severity ordinal).
RISK_LEVELS: tuple[str, ...] = (
    "ok",
    "watch",
    "reduce_only",
    "block_new_entries",
    "critical",
)


def _level_max(*levels: str) -> str:
    """Return the most severe of the given risk levels."""
    return max(levels, key=RISK_LEVELS.index)


@dataclass(frozen=True)
class MarginProductSpec:
    """Contract + margin parameters for one product (from config + exec spec).

    ``multiplier_krw_per_point`` / ``tick_size_points`` come from the single
    source of contract constants (``config/execution.yaml``); the margin rates
    and stress gap come from ``config/futures_margin.yaml``.
    """

    multiplier_krw_per_point: float
    tick_size_points: float
    initial_margin_rate: float
    maintenance_margin_rate: float
    stress_gap_points: float
    symbol_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class MarginThresholds:
    """Margin-usage and liquidation-buffer escalation thresholds."""

    watch_margin_usage_pct: float
    reduce_only_margin_usage_pct: float
    block_new_entries_margin_usage_pct: float
    critical_margin_usage_pct: float
    watch_liquidation_buffer_ticks: float
    critical_liquidation_buffer_ticks: float


@dataclass(frozen=True)
class FuturesMarginRiskState:
    """One evaluated margin-risk snapshot (published + ledgered; NEVER executed)."""

    schema_version: int
    account_equity_krw: float
    cash_available_krw: float | None
    initial_margin_required_krw: float
    maintenance_margin_required_krw: float
    margin_usage_pct: float
    maintenance_buffer_krw: float
    maintenance_buffer_pct: float
    liquidation_buffer_points: float | None
    liquidation_buffer_ticks: float | None
    stress_loss_1atr_krw: float | None
    stress_loss_2atr_krw: float | None
    stress_loss_gap_krw: float
    max_additional_contracts: int | None
    # Reference-product per-contract initial margin (KRW). Published so the
    # advisory-only hedge lane can size "margin after hedge" without importing
    # the order path or re-deriving the margin rate (Phase D feasibility).
    per_contract_initial_margin_krw: float | None
    risk_level: str
    degraded: bool
    missing_components: tuple[str, ...]
    asof_ts: datetime


def spec_for_symbol(
    symbol: str, product_specs: Mapping[str, MarginProductSpec]
) -> MarginProductSpec | None:
    """Resolve a held futures symbol to its product spec by prefix (or None)."""
    code = str(symbol or "").strip()
    if not code:
        return None
    for spec in product_specs.values():
        if code.startswith(spec.symbol_prefixes):
            return spec
    return None


def compute_margin_risk(
    *,
    positions: Sequence[Mapping[str, Any]],
    product_specs: Mapping[str, MarginProductSpec],
    reference_product: str,
    account_equity_krw: float | None,
    cash_available_krw: float | None,
    reference_price: float | None,
    atr_by_symbol: Mapping[str, float] | None,
    thresholds: MarginThresholds,
    snapshot_ok: bool,
    fail_closed: bool,
    asof_ts: datetime,
    extra_missing: Sequence[str] = (),
) -> FuturesMarginRiskState:
    """Fold positions + account state into one :class:`FuturesMarginRiskState`.

    Args:
        positions: Open futures positions (``code``/``side``/``quantity``/
            ``current_price``); each valued with its OWN product multiplier.
        product_specs: Product key → :class:`MarginProductSpec`.
        reference_product: Product key used for tick-size / per-contract sizing
            (``max_additional_contracts``, ``liquidation_buffer_ticks``).
        account_equity_krw: Broker account equity, or the config fallback when
            the snapshot is unavailable; None → treated as missing.
        cash_available_krw: Order-available cash, or None.
        reference_price: Current reference-product index price (for
            per-contract margin sizing); None → ``max_additional_contracts``
            is None.
        atr_by_symbol: Per-symbol ATR (index points) for stress loss; a missing
            symbol drops that leg from the ATR stress figures (recorded).
        thresholds: Usage/buffer escalation thresholds.
        snapshot_ok: Was the account snapshot fresh and present?
        fail_closed: Live semantics — a bad snapshot forces ``critical``.
        asof_ts: KST-naive evaluation timestamp.
        extra_missing: Upstream coverage entries (e.g. provider failures).
    """
    missing: list[str] = list(extra_missing)
    atr_by_symbol = atr_by_symbol or {}

    ref_spec = product_specs.get(reference_product)
    if ref_spec is None:
        raise ValueError(f"no product spec for reference_product={reference_product!r}")

    # --- Per-position margin + sensitivity folds ------------------------
    initial_margin = 0.0
    maintenance_margin = 0.0
    point_sensitivity_krw = 0.0  # KRW lost per 1pt aligned adverse move (|qty|)
    stress_gap_krw = 0.0
    stress_1atr_krw = 0.0
    atr_covered = True
    have_positions = False

    for position in positions:
        quantity = _to_float(position.get("quantity"))
        price = _to_float(position.get("current_price"))
        if quantity is None or price is None or quantity <= 0 or price <= 0:
            continue
        symbol = str(position.get("code", "")).strip()
        spec = spec_for_symbol(symbol, product_specs)
        if spec is None:
            missing.append(f"margin_product:{symbol or 'unknown'}")
            continue
        have_positions = True
        notional = quantity * price * spec.multiplier_krw_per_point
        initial_margin += notional * spec.initial_margin_rate
        maintenance_margin += notional * spec.maintenance_margin_rate
        # |qty| * multiplier: adverse move loss per point, side-independent.
        sensitivity = quantity * spec.multiplier_krw_per_point
        point_sensitivity_krw += sensitivity
        stress_gap_krw += sensitivity * spec.stress_gap_points
        atr = _to_float(atr_by_symbol.get(symbol))
        if atr is None:
            atr_covered = False
            missing.append(f"atr:{symbol or 'unknown'}")
        else:
            stress_1atr_krw += sensitivity * atr

    # --- Account equity + fallback / fail policy ------------------------
    equity = _to_float(account_equity_krw)
    if equity is None or equity <= 0:
        missing.append("account_equity")
        equity = 0.0
    if not snapshot_ok:
        missing.append("account_snapshot_stale")

    degraded = bool(missing) or not snapshot_ok

    # --- Usage + buffers ------------------------------------------------
    margin_usage_pct = initial_margin / equity if equity > 0 else 0.0
    maintenance_buffer_krw = equity - maintenance_margin
    maintenance_buffer_pct = maintenance_buffer_krw / equity if equity > 0 else 0.0

    liquidation_buffer_points: float | None = None
    liquidation_buffer_ticks: float | None = None
    if point_sensitivity_krw > 0:
        liquidation_buffer_points = maintenance_buffer_krw / point_sensitivity_krw
        liquidation_buffer_ticks = (
            liquidation_buffer_points / ref_spec.tick_size_points
            if ref_spec.tick_size_points > 0
            else None
        )

    # --- Stress loss ----------------------------------------------------
    # The ``* 2.0`` is the fixed "2 ATR adverse move" scenario baked into the
    # published field name ``stress_loss_2atr_krw`` — not a tunable multiplier.
    stress_loss_1atr: float | None = stress_1atr_krw if atr_covered else None
    stress_loss_2atr: float | None = stress_1atr_krw * 2.0 if atr_covered else None
    # When ATR coverage is partial, expose what we could sum but mark degraded.
    if not atr_covered and have_positions:
        stress_loss_1atr = None
        stress_loss_2atr = None

    # --- Max additional contracts (reference product) -------------------
    max_additional_contracts: int | None = None
    per_contract_initial_margin: float | None = None
    ref_price = _to_float(reference_price)
    if ref_price is not None and ref_price > 0:
        per_contract_initial_margin = (
            ref_price * ref_spec.multiplier_krw_per_point * ref_spec.initial_margin_rate
        )
        if per_contract_initial_margin > 0 and equity > 0:
            headroom = (
                thresholds.block_new_entries_margin_usage_pct * equity - initial_margin
            )
            max_additional_contracts = max(
                int(math.floor(headroom / per_contract_initial_margin)), 0
            )
    else:
        missing.append("reference_price")

    # --- Risk level -----------------------------------------------------
    risk_level = _classify_level(
        margin_usage_pct=margin_usage_pct,
        liquidation_buffer_ticks=liquidation_buffer_ticks,
        stress_loss_1atr_krw=stress_loss_1atr,
        maintenance_buffer_krw=maintenance_buffer_krw,
        thresholds=thresholds,
        have_positions=have_positions,
    )

    # Fail-closed (live) with a bad snapshot overrides everything.
    if not snapshot_ok and fail_closed:
        risk_level = "critical"

    return FuturesMarginRiskState(
        schema_version=MARGIN_RISK_SCHEMA_VERSION,
        account_equity_krw=equity,
        cash_available_krw=_to_float(cash_available_krw),
        initial_margin_required_krw=initial_margin,
        maintenance_margin_required_krw=maintenance_margin,
        margin_usage_pct=margin_usage_pct,
        maintenance_buffer_krw=maintenance_buffer_krw,
        maintenance_buffer_pct=maintenance_buffer_pct,
        liquidation_buffer_points=liquidation_buffer_points,
        liquidation_buffer_ticks=liquidation_buffer_ticks,
        stress_loss_1atr_krw=stress_loss_1atr,
        stress_loss_2atr_krw=stress_loss_2atr,
        stress_loss_gap_krw=stress_gap_krw,
        max_additional_contracts=max_additional_contracts,
        per_contract_initial_margin_krw=per_contract_initial_margin,
        risk_level=risk_level,
        degraded=degraded,
        missing_components=tuple(missing),
        asof_ts=asof_ts,
    )


def _classify_level(
    *,
    margin_usage_pct: float,
    liquidation_buffer_ticks: float | None,
    stress_loss_1atr_krw: float | None,
    maintenance_buffer_krw: float,
    thresholds: MarginThresholds,
    have_positions: bool,
) -> str:
    """Map usage / buffer / stress inputs to a risk level (see RISK_LEVELS)."""
    if not have_positions:
        return "ok"

    if margin_usage_pct >= thresholds.critical_margin_usage_pct:
        level = "critical"
    elif margin_usage_pct >= thresholds.block_new_entries_margin_usage_pct:
        level = "block_new_entries"
    elif margin_usage_pct >= thresholds.reduce_only_margin_usage_pct:
        level = "reduce_only"
    elif margin_usage_pct >= thresholds.watch_margin_usage_pct:
        level = "watch"
    else:
        level = "ok"

    # Stress loss exceeding the maintenance buffer → at least reduce_only
    # (a single ATR adverse move would breach maintenance margin; plan §5.3).
    if (
        stress_loss_1atr_krw is not None
        and stress_loss_1atr_krw > maintenance_buffer_krw
    ):
        level = _level_max(level, "reduce_only")

    # Liquidation buffer escalation.
    if liquidation_buffer_ticks is not None:
        if liquidation_buffer_ticks < thresholds.critical_liquidation_buffer_ticks:
            level = _level_max(level, "block_new_entries")
        elif liquidation_buffer_ticks < thresholds.watch_liquidation_buffer_ticks:
            level = _level_max(level, "watch")

    return level


# ---------------------------------------------------------------------------
# Redis contract mapping (futures:risk:latest)
# ---------------------------------------------------------------------------


def _fmt(value: float | None) -> str:
    """Absent values publish as "" (repo null marker)."""
    return "" if value is None else f"{float(value):.4f}"


def margin_state_to_fields(state: FuturesMarginRiskState) -> dict[str, str]:
    """Flatten a margin-risk state into the ``futures:risk:latest`` hash."""
    return {
        "schema_version": str(state.schema_version),
        "account_equity_krw": _fmt(state.account_equity_krw),
        "cash_available_krw": _fmt(state.cash_available_krw),
        "initial_margin_required_krw": _fmt(state.initial_margin_required_krw),
        "maintenance_margin_required_krw": _fmt(state.maintenance_margin_required_krw),
        "margin_usage_pct": _fmt(state.margin_usage_pct),
        "maintenance_buffer_krw": _fmt(state.maintenance_buffer_krw),
        "maintenance_buffer_pct": _fmt(state.maintenance_buffer_pct),
        "liquidation_buffer_points": _fmt(state.liquidation_buffer_points),
        "liquidation_buffer_ticks": _fmt(state.liquidation_buffer_ticks),
        "stress_loss_1atr_krw": _fmt(state.stress_loss_1atr_krw),
        "stress_loss_2atr_krw": _fmt(state.stress_loss_2atr_krw),
        "stress_loss_gap_krw": _fmt(state.stress_loss_gap_krw),
        "max_additional_contracts": (
            ""
            if state.max_additional_contracts is None
            else str(state.max_additional_contracts)
        ),
        "per_contract_initial_margin_krw": _fmt(state.per_contract_initial_margin_krw),
        "risk_level": state.risk_level,
        "degraded": "true" if state.degraded else "false",
        "missing_components": json.dumps(
            list(state.missing_components), ensure_ascii=False
        ),
        "asof_ts": state.asof_ts.isoformat(),
    }
