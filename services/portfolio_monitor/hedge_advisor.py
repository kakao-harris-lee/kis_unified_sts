"""Hedge advisor runner (Phase 4A — advisory ONLY, no automated orders).

Glue between the pure hedge math (:mod:`shared.portfolio.hedge`) and the
runtime surfaces, executed by the daily portfolio monitor (08:50/19:00 KST
cron) right after the equity snapshot:

1. Read market inputs from Redis DB 1: ``market:structure:latest``
   (``fut_close`` + ``asof_ts`` freshness) and ``market:risk:latest``
   (``band``/``score``).
2. Read Track B/C open positions from the trading-state hashes (same source
   the dashboard risk-exposure board consumes).
3. Estimate per-symbol β from Parquet daily bars vs ``market_structure_daily``
   ``k200_close`` rows, then compute the hedge advice.
4. Publish the FIXED 4B-UI Redis contract: ``portfolio:hedge:latest`` hash
   (TTL 24h) + ``stream:portfolio.hedge`` (maxlen + 24h expire).
5. Append RuntimeLedger ``hedge_advice`` history ONLY on advisory_active
   transitions or recommended-contract changes (no per-run duplicates).
6. Telegram advisory on the advisory_active rising edge — the message always
   states it is a recommendation, never an automated order.

HARD CONSTRAINT: this module (and everything it imports for the hedge path)
must never import ``shared.execution`` or any order/position-mutating path.
A unit test pins that absence on the full import graph.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from shared.portfolio.hedge import (
    BetaEstimate,
    HedgeAdvice,
    HedgeAdviceV2,
    HedgeAdvisorConfig,
    advice_v2_to_latest_fields,
    compute_hedge_advice,
    compute_hedge_advice_v2,
    estimate_beta,
    is_price_fresh,
    product_multipliers,
    side_sign,
    verify_product_spec,
)

logger = logging.getLogger(__name__)

PositionsProvider = Callable[[], Sequence[Mapping[str, Any]]]
#: (symbol, start, end) -> [(date, close), ...]
DailyClosesProvider = Callable[[str, date, date], Sequence[tuple[date, float]]]
#: (start, end) -> [(date, k200_close), ...]
MarketClosesProvider = Callable[[date, date], Sequence[tuple[date, float]]]


# ---------------------------------------------------------------------------
# Run context (dependency injection point; defaults built by _cli)
# ---------------------------------------------------------------------------


@dataclass
class HedgeRunContext:
    """Injected dependencies for one hedge advisory run (hermetic-testable)."""

    config: HedgeAdvisorConfig
    execution_specs: Mapping[str, Any]
    stock_positions_provider: PositionsProvider
    futures_positions_provider: PositionsProvider
    daily_closes_provider: DailyClosesProvider
    market_closes_provider: MarketClosesProvider
    notifier: Any | None = None
    extra_missing: list[str] = field(default_factory=list)


def _default_positions_provider(asset_class: str) -> PositionsProvider:
    """Open positions from the trading-state hash (read-only reader)."""

    def _read() -> Sequence[Mapping[str, Any]]:
        from shared.streaming.trading_state import TradingStateReader

        return TradingStateReader(asset_class).get_positions()

    return _read


def _default_daily_closes_provider() -> DailyClosesProvider:
    """(date, close) pairs from the Parquet stock daily bars."""

    def _read(symbol: str, start: date, end: date) -> list[tuple[date, float]]:
        from shared.storage.market_data_store import create_market_data_store

        frame = create_market_data_store(asset_class="stock").get_daily_bars(
            symbol, start=start, end=end
        )
        return _frame_to_closes(frame, "datetime", "close")

    return _read


def _default_market_closes_provider() -> MarketClosesProvider:
    """(date, k200_close) pairs from market_structure_daily close rows."""

    def _read(start: date, end: date) -> list[tuple[date, float]]:
        from shared.storage.market_structure_store import (
            create_market_structure_store,
        )

        frame = create_market_structure_store().read_range(
            start=start, end=end, snapshot="close"
        )
        return _frame_to_closes(frame, "trade_date", "k200_close")

    return _read


def _frame_to_closes(
    frame: Any, date_column: str, value_column: str
) -> list[tuple[date, float]]:
    """Best-effort (date, close) extraction from a store DataFrame."""
    closes: list[tuple[date, float]] = []
    if frame is None or getattr(frame, "empty", True):
        return closes
    if value_column not in getattr(frame, "columns", []):
        return closes
    for _, row in frame.iterrows():
        raw_day = row.get(date_column)
        raw_value = row.get(value_column)
        day = _coerce_date(raw_day)
        if day is None or raw_value is None:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if value == value and value > 0:  # NaN guard without numpy import
            closes.append((day, value))
    return closes


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "to_pydatetime"):  # pandas.Timestamp
        try:
            return value.to_pydatetime().date()
        except (TypeError, ValueError):
            return None
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def default_hedge_context(
    config: HedgeAdvisorConfig | None = None,
) -> HedgeRunContext:
    """Build the production run context (real Redis-state/Parquet sources)."""
    from shared.config.loader import ConfigLoader

    config = config or HedgeAdvisorConfig.load_or_default()
    execution_yaml = ConfigLoader.load("execution.yaml")
    execution_specs = (
        execution_yaml.get("futures_contract_spec", {})
        if isinstance(execution_yaml, dict)
        else {}
    )
    notifier = None
    if config.alerts.enabled:
        try:
            from shared.notification.telegram import notifier_for_domain

            notifier = notifier_for_domain(config.alerts.domain)
        except Exception as exc:  # noqa: BLE001 — alerts must not block advice
            logger.warning("hedge telegram notifier unavailable: %s", exc)

    return HedgeRunContext(
        config=config,
        execution_specs=execution_specs,
        stock_positions_provider=_default_positions_provider("stock"),
        futures_positions_provider=_default_positions_provider("futures"),
        daily_closes_provider=_default_daily_closes_provider(),
        market_closes_provider=_default_market_closes_provider(),
        notifier=notifier,
    )


# ---------------------------------------------------------------------------
# Market inputs (Redis DB 1 hashes published by upstream engines)
# ---------------------------------------------------------------------------


def _parse_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _parse_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_int(value: Any) -> int | None:
    result = _parse_float(value)
    return None if result is None else int(result)


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _parse_str(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in {"true", "1", "yes"}:
        return True
    if lowered in {"false", "0", "no"}:
        return False
    return None


def _parse_kst_naive(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed


def read_market_inputs(
    redis: Any, config: HedgeAdvisorConfig, now: datetime
) -> tuple[float | None, bool, str | None, float | None]:
    """(futures_price, price_fresh, band, score) from the published hashes."""
    structure: Mapping[str, Any] = {}
    risk: Mapping[str, Any] = {}
    try:
        structure = redis.hgetall(config.redis.structure_latest_key) or {}
    except Exception as exc:  # noqa: BLE001 — degraded, not fatal
        logger.warning("market structure read failed: %s", exc)
    try:
        risk = redis.hgetall(config.redis.risk_latest_key) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("market risk read failed: %s", exc)

    futures_price = _parse_float(structure.get("fut_close"))
    price_asof = _parse_kst_naive(structure.get("asof_ts"))
    fresh = is_price_fresh(price_asof, now, config.advisory.futures_price_max_age_hours)
    band = str(risk.get("band") or "").strip() or None
    score = _parse_float(risk.get("score"))
    return futures_price, fresh, band, score


# ---------------------------------------------------------------------------
# β inputs
# ---------------------------------------------------------------------------


def build_betas(
    context: HedgeRunContext,
    stock_positions: Sequence[Mapping[str, Any]],
    trade_date: date,
) -> dict[str, BetaEstimate]:
    """Per-symbol β estimates for the held Track B spot longs."""
    config = context.config
    start = trade_date - timedelta(days=config.beta.lookback_calendar_days)
    symbols = sorted(
        {
            str(position.get("code", "")).strip()
            for position in stock_positions
            if str(position.get("code", "")).strip()
            and side_sign(position.get("side", "long")) > 0
        }
    )
    if not symbols:
        return {}

    try:
        market_closes = list(context.market_closes_provider(start, trade_date))
    except Exception as exc:  # noqa: BLE001 — β degrades to the fallback
        logger.warning("k200 close history read failed: %s", exc)
        market_closes = []

    betas: dict[str, BetaEstimate] = {}
    for symbol in symbols:
        try:
            closes = list(context.daily_closes_provider(symbol, start, trade_date))
        except Exception as exc:  # noqa: BLE001
            logger.warning("daily bars read failed for %s: %s", symbol, exc)
            closes = []
        betas[symbol] = estimate_beta(closes, market_closes, config.beta)
    return betas


# ---------------------------------------------------------------------------
# Publication + history + alert
# ---------------------------------------------------------------------------


def read_operational_inputs(
    redis: Any, config: HedgeAdvisorConfig
) -> tuple[dict[str, Any], dict[str, Any]]:
    """(contract, margin) hashes from the Phase A/B read-models (read-only).

    Read as plain Redis hashes — this keeps the advisory-only import guard
    intact (no order-path import). A missing/failed read returns ``{}`` and the
    v2 layer degrades to a no-op recommendation.
    """
    contract: dict[str, Any] = {}
    margin: dict[str, Any] = {}
    try:
        contract = dict(redis.hgetall(config.redis.contract_latest_key) or {})
    except Exception as exc:  # noqa: BLE001 — degraded, not fatal
        logger.warning("futures contract read failed: %s", exc)
    try:
        margin = dict(redis.hgetall(config.redis.margin_latest_key) or {})
    except Exception as exc:  # noqa: BLE001
        logger.warning("futures margin read failed: %s", exc)
    return contract, margin


def build_advice_v2(
    advice: HedgeAdvice,
    config: HedgeAdvisorConfig,
    contract: Mapping[str, Any],
    margin: Mapping[str, Any],
) -> HedgeAdviceV2:
    """Fold the base advice + Phase A/B hashes into a v2 feasibility view.

    No published depth/slippage read-model exists yet, so
    ``estimated_slippage_ticks`` is None (the liquidity branch is skipped).
    """
    return compute_hedge_advice_v2(
        base=advice,
        config=config,
        roll_state=_parse_str(contract.get("roll_state")),
        hedge_front_allowed=_parse_bool(contract.get("hedge_front_allowed")),
        margin_risk_level=_parse_str(margin.get("risk_level")),
        margin_usage_pct=_parse_float(margin.get("margin_usage_pct")),
        max_additional_contracts=_parse_int(margin.get("max_additional_contracts")),
        per_contract_initial_margin_krw=_parse_float(
            margin.get("per_contract_initial_margin_krw")
        ),
        account_equity_krw=_parse_float(margin.get("account_equity_krw")),
        initial_margin_required_krw=_parse_float(
            margin.get("initial_margin_required_krw")
        ),
        estimated_slippage_ticks=None,
        contract_state_present=bool(contract),
        margin_state_present=bool(margin),
    )


def publish_advice(
    redis: Any, config: HedgeAdvisorConfig, advice: HedgeAdviceV2
) -> None:
    """Publish ``portfolio:hedge:latest`` + ``stream:portfolio.hedge``.

    Base 18 field names are a FIXED contract with the 4B UI lane; the 9 v2
    fields are append-only (existing consumers unaffected).
    """
    fields = advice_v2_to_latest_fields(advice)
    redis_cfg = config.redis
    # delete-then-hset so stale fields from a previous publish never linger.
    redis.delete(redis_cfg.latest_key)
    redis.hset(redis_cfg.latest_key, mapping=fields)
    redis.expire(redis_cfg.latest_key, redis_cfg.latest_ttl_seconds)

    redis.xadd(
        redis_cfg.stream_key,
        fields,
        maxlen=redis_cfg.stream_maxlen,
        approximate=True,
    )
    redis.expire(redis_cfg.stream_key, redis_cfg.stream_ttl_seconds)


def _last_advice_state(ledger: Any) -> tuple[bool, int]:
    """(advisory_active, recommended) of the last history row.

    Missing history reads as the (inactive, 0) baseline so a first run that
    produces no actionable advice records nothing.
    """
    try:
        rows = ledger.query_hedge_advice({})
    except Exception as exc:  # noqa: BLE001 — history loss degrades, not kills
        logger.warning("hedge advice history read failed: %s", exc)
        return False, 0
    if not rows:
        return False, 0
    last = rows[-1]
    return bool(last.get("advisory_active")), int(
        last.get("recommended_short_contracts") or 0
    )


def record_advice_if_changed(
    ledger: Any, advice: HedgeAdvice, trade_date: date
) -> tuple[bool, bool]:
    """Append history only on transitions/changes.

    Returns ``(recorded, newly_active)`` — ``newly_active`` drives the
    one-shot Telegram advisory.
    """
    prev_active, prev_recommended = _last_advice_state(ledger)
    changed = (
        advice.advisory_active != prev_active
        or advice.recommended_short_contracts != prev_recommended
    )
    newly_active = advice.advisory_active and not prev_active
    if not changed:
        return False, False

    ledger.record_hedge_advice(
        {
            "trade_date": trade_date.isoformat(),
            "asof_ts": advice.asof_ts.isoformat(),
            "product": advice.product,
            "advisory_active": advice.advisory_active,
            "recommended_short_contracts": advice.recommended_short_contracts,
            "net_beta_exposure": advice.net_beta_exposure,
            "beta_notional": advice.beta_notional,
            "stock_long_notional": advice.stock_long_notional,
            "portfolio_beta": advice.portfolio_beta,
            "futures_net_contracts": advice.futures_net_contracts,
            "futures_net_notional": advice.futures_net_notional,
            "futures_price": advice.futures_price,
            "residual_exposure_after": advice.residual_exposure_after,
            "band": advice.band,
            "score": advice.score,
            "reason": advice.reason,
            "degraded": advice.degraded,
            "missing_components": list(advice.missing_components),
        }
    )
    return True, newly_active


def advisory_message(advice: HedgeAdvice) -> str:
    """Telegram advisory text — explicitly a recommendation, never an order."""
    score_text = "" if advice.score is None else f" (score {advice.score:.0f})"
    return (
        "<b>헤지 권고 (advisory)</b>\n"
        f"밴드 {advice.band or '-'}{score_text}"
        f" · 넷 β-노출 ₩{advice.net_beta_exposure:,.0f}\n"
        f"권고: 미니 KOSPI200 선물 {advice.recommended_short_contracts}계약 숏"
        f" (잔여 노출 ₩{advice.residual_exposure_after:,.0f})\n"
        f"근거: {advice.reason}\n"
        "※ 본 메시지는 권고일 뿐이며 자동 주문은 절대 실행되지 않습니다."
    )


def _dispatch_alert(notifier: Any, message: str) -> None:
    if notifier is None:
        return

    async def _send() -> None:
        await notifier.send_message(message, is_critical=True)

    try:
        asyncio.run(_send())
    except Exception as exc:  # noqa: BLE001 — alerts must not fail the run
        logger.warning("hedge advisory telegram alert failed: %s", exc)


# ---------------------------------------------------------------------------
# One-shot run (called by services.portfolio_monitor.main.run_snapshot)
# ---------------------------------------------------------------------------


def run_hedge_advice(
    *,
    context: HedgeRunContext,
    ledger: Any,
    redis: Any,
    trade_date: date,
    now: datetime,
) -> HedgeAdvice | None:
    """Compute + publish + ledger + alert one hedge advisory (see module doc).

    Never places orders, never mutates positions — Redis publication, ledger
    history, Telegram text, and logs are the only side effects.
    """
    config = context.config
    if not config.enabled:
        logger.info("hedge advisor disabled (config/hedge_advisor.yaml)")
        return None

    # Product parameter cross-check — a wrong contract size must fail loudly.
    verify_product_spec(config, context.execution_specs)
    multipliers = product_multipliers(config, context.execution_specs)

    extra_missing: list[str] = list(context.extra_missing)

    def _positions(
        provider: PositionsProvider, label: str
    ) -> Sequence[Mapping[str, Any]]:
        try:
            return provider()
        except Exception as exc:  # noqa: BLE001 — degraded, not fatal
            logger.warning("%s positions read failed: %s", label, exc)
            extra_missing.append(label)
            return []

    stock_positions = _positions(context.stock_positions_provider, "stock_positions")
    futures_positions = _positions(
        context.futures_positions_provider, "futures_positions"
    )

    futures_price, price_fresh, band, score = read_market_inputs(redis, config, now)
    betas = build_betas(context, stock_positions, trade_date)

    advice = compute_hedge_advice(
        config=config,
        stock_positions=stock_positions,
        futures_positions=futures_positions,
        betas=betas,
        multipliers=multipliers,
        futures_price=futures_price,
        futures_price_fresh=price_fresh,
        band=band,
        score=score,
        asof_ts=now,
        extra_missing=extra_missing,
    )

    logger.info(
        "hedge advice %s: active=%s recommended=%d net=%.0f (beta_notional=%.0f"
        " futures_net=%.0f price=%s band=%s) degraded=%s missing=%s",
        trade_date,
        advice.advisory_active,
        advice.recommended_short_contracts,
        advice.net_beta_exposure,
        advice.beta_notional,
        advice.futures_net_notional,
        advice.futures_price,
        advice.band,
        advice.degraded,
        json.dumps(list(advice.missing_components), ensure_ascii=False),
    )

    # HedgeAdvisorV2 feasibility layer — read the Phase A/B operational
    # read-models (plain hashes; no order-path import) and publish the base
    # 18 fields + 9 append-only v2 fields.
    contract, margin = read_operational_inputs(redis, config)
    advice_v2 = build_advice_v2(advice, config, contract, margin)
    logger.info(
        "hedge advice v2 %s: target_ratio=%s current_ratio=%s delta=%d"
        " feasibility=%s operator_action=%s roll_adj=%s",
        trade_date,
        advice_v2.target_hedge_ratio,
        (
            "-"
            if advice_v2.current_hedge_ratio is None
            else f"{advice_v2.current_hedge_ratio:.2f}"
        ),
        advice_v2.delta_short_contracts,
        advice_v2.execution_feasibility,
        advice_v2.operator_action,
        advice_v2.roll_adjustment,
    )

    publish_advice(redis, config, advice_v2)

    try:
        recorded, newly_active = record_advice_if_changed(ledger, advice, trade_date)
    except Exception as exc:  # noqa: BLE001 — history must not fail the publish
        logger.warning("hedge advice history append failed: %s", exc)
        recorded, newly_active = False, False

    if newly_active and config.alerts.enabled:
        _dispatch_alert(context.notifier, advisory_message(advice))
    if recorded:
        logger.info("hedge advice history row appended (newly_active=%s)", newly_active)

    return advice
