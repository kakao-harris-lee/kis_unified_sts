"""Futures margin-risk publisher — one-shot / short-interval, run via scheduler.

Publishes ``futures:risk:latest`` (hash, TTL 15m) + ``stream:futures.risk`` so
FuturesMarketContextV2 (Phase C) and HedgeAdvisorV2 (Phase D) can read account
margin usage, the liquidation buffer, and stress loss. Read-only: no order path
is touched.

Inputs are dependency-injected (hermetic-testable) with config fallbacks:

* futures positions ← trading-state hash (same reader the hedge lane uses).
* account equity ← injected broker-snapshot provider; the first version falls
  back to ``config/futures_margin.yaml::fallback_account_equity_krw`` and marks
  the snapshot NOT ok (KIS futures balance is REST-unstable / mock-unsupported).
  In live (fail_closed) a bad snapshot forces ``risk_level=critical``; in paper
  it only marks the state degraded.
* reference price ← ``market:structure:latest`` ``fut_close``.
* per-symbol ATR ← injected provider (default empty → gap stress only).

Contract constants (multiplier, tick) come from
``config/execution.yaml::futures_contract_spec`` (single source); only margin
rates + stress gap come from the margin YAML.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from services.futures_margin_risk.config import FuturesMarginConfig
from shared.config.runtime_defaults import redis_url_from_env
from shared.risk.futures_margin import (
    FuturesMarginRiskState,
    MarginProductSpec,
    MarginThresholds,
    compute_margin_risk,
    margin_state_to_fields,
)
from shared.risk.product_specs import (
    build_product_specs,
    load_execution_contract_specs,
)
from shared.utils.coercion import to_float as _parse_float

# ``build_product_specs`` moved to ``shared/risk/product_specs.py`` (P5-3 F3) so
# both this publisher and ``services/risk_filter``'s leverage wiring import it
# from the shared seam (no service→service dependency). Re-exported here to keep
# ``from services.futures_margin_risk.main import build_product_specs`` working.
__all__ = ["build_product_specs"]

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

PositionsProvider = Callable[[], Sequence[Mapping[str, Any]]]
#: () -> (account_equity_krw, cash_available_krw, snapshot_ok)
AccountSnapshotProvider = Callable[[], tuple[float | None, float | None, bool]]
ATRProvider = Callable[[Sequence[str]], Mapping[str, float]]


def _now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Run context (dependency injection point; defaults built by _cli)
# ---------------------------------------------------------------------------


@dataclass
class MarginRunContext:
    """Injected dependencies for one margin-risk run (hermetic-testable)."""

    config: FuturesMarginConfig
    product_specs: Mapping[str, MarginProductSpec]
    positions_provider: PositionsProvider
    account_snapshot_provider: AccountSnapshotProvider
    atr_provider: ATRProvider
    fail_closed: bool = False
    notifier: Any | None = None
    ledger: Any | None = None
    extra_missing: list[str] = field(default_factory=list)


def _thresholds(config: FuturesMarginConfig) -> MarginThresholds:
    t = config.thresholds
    return MarginThresholds(
        watch_margin_usage_pct=t.watch_margin_usage_pct,
        reduce_only_margin_usage_pct=t.reduce_only_margin_usage_pct,
        block_new_entries_margin_usage_pct=t.block_new_entries_margin_usage_pct,
        critical_margin_usage_pct=t.critical_margin_usage_pct,
        watch_liquidation_buffer_ticks=t.watch_liquidation_buffer_ticks,
        critical_liquidation_buffer_ticks=t.critical_liquidation_buffer_ticks,
    )


# ---------------------------------------------------------------------------
# Default providers (production wiring)
# ---------------------------------------------------------------------------


def _default_positions_provider() -> PositionsProvider:
    def _read() -> Sequence[Mapping[str, Any]]:
        from shared.streaming.trading_state import TradingStateReader

        return TradingStateReader("futures").get_positions()

    return _read


def _config_fallback_account_provider(
    config: FuturesMarginConfig,
) -> AccountSnapshotProvider:
    """Config-equity fallback provider (snapshot_ok=False → degraded/critical).

    The first version does NOT call the KIS futures balance endpoint (REST-
    unstable, mock-unsupported); it returns the configured fallback equity and
    flags the snapshot as not-ok so paper degrades and live fails closed. A
    real broker snapshot provider can be injected later without touching math.
    """

    def _read() -> tuple[float | None, float | None, bool]:
        return config.fallback_account_equity_krw, None, False

    return _read


def _empty_atr_provider() -> ATRProvider:
    def _read(_symbols: Sequence[str]) -> Mapping[str, float]:
        return {}

    return _read


def default_margin_context(
    config: FuturesMarginConfig | None = None,
) -> MarginRunContext:
    """Build the production run context (real trading-state / config fallback)."""
    config = config or FuturesMarginConfig.load_or_default()
    execution_specs = load_execution_contract_specs()
    product_specs = build_product_specs(config, execution_specs)

    fail_closed = _resolve_fail_closed()

    notifier = None
    if config.alerts.enabled:
        try:
            from shared.notification.telegram import notifier_for_domain

            notifier = notifier_for_domain(config.alerts.domain)
        except Exception as exc:  # noqa: BLE001 — alerts must not block the run
            logger.warning("margin-risk telegram notifier unavailable: %s", exc)

    return MarginRunContext(
        config=config,
        product_specs=product_specs,
        positions_provider=_default_positions_provider(),
        account_snapshot_provider=_config_fallback_account_provider(config),
        atr_provider=_empty_atr_provider(),
        fail_closed=fail_closed,
        notifier=notifier,
        ledger=_default_ledger(),
    )


def _default_ledger() -> Any | None:
    """Runtime ledger for escalation audit (None on any failure — non-fatal)."""
    try:
        from shared.storage import SQLiteRuntimeLedger
        from shared.storage.config import StorageConfig

        storage = StorageConfig.load_or_default()
        return SQLiteRuntimeLedger(storage.runtime_storage.sqlite)
    except Exception as exc:  # noqa: BLE001 — audit must not fail the run
        logger.warning("runtime ledger unavailable: %s", exc)
        return None


def _resolve_fail_closed() -> bool:
    """Live semantics when ``config/futures_live.yaml::enabled`` is true."""
    try:
        from shared.execution.live_mode_guard import LiveModeGuard

        return bool(LiveModeGuard.from_yaml().enabled)
    except Exception as exc:  # noqa: BLE001 — default to paper (fail-open) on error
        logger.warning("live-mode resolution failed, assuming paper: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Reference price (market:structure:latest fut_close)
# ---------------------------------------------------------------------------


def read_reference_price(redis: Any) -> float | None:
    """Reference-product index price from ``market:structure:latest`` fut_close."""
    try:
        structure = redis.hgetall("market:structure:latest") or {}
    except Exception as exc:  # noqa: BLE001 — degraded, not fatal
        logger.warning("market structure read failed: %s", exc)
        return None
    return _parse_float(structure.get("fut_close"))


# ---------------------------------------------------------------------------
# Publication + audit + alert
# ---------------------------------------------------------------------------


def publish_state(
    redis: Any, config: FuturesMarginConfig, state: FuturesMarginRiskState
) -> None:
    """Publish ``futures:risk:latest`` (hash) + ``stream:futures.risk``."""
    fields = margin_state_to_fields(state)
    redis_cfg = config.redis
    redis.delete(redis_cfg.latest_key)
    redis.hset(redis_cfg.latest_key, mapping=fields)
    redis.expire(redis_cfg.latest_key, redis_cfg.latest_ttl_seconds)

    event = {
        "risk_level": state.risk_level,
        "margin_usage_pct": f"{state.margin_usage_pct:.4f}",
        "degraded": "true" if state.degraded else "false",
        "asof_ts": state.asof_ts.isoformat(),
    }
    redis.xadd(
        redis_cfg.stream_key, event, maxlen=redis_cfg.stream_maxlen, approximate=True
    )
    redis.expire(redis_cfg.stream_key, redis_cfg.stream_ttl_seconds)


#: Redis key holding the last-published risk level (escalation dedup, 24h TTL).
_PREV_LEVEL_KEY = "futures:risk:prev_level"
_PREV_LEVEL_TTL_SECONDS = 86400

#: Risk levels at/above which an escalation is audited + alerted.
_ESCALATION_LEVELS = frozenset({"reduce_only", "block_new_entries", "critical"})


def _read_prev_level(redis: Any) -> str | None:
    try:
        return redis.get(_PREV_LEVEL_KEY) or None
    except Exception as exc:  # noqa: BLE001 — dedup loss degrades, not kills
        logger.warning("prev risk level read failed: %s", exc)
        return None


def _write_prev_level(redis: Any, level: str) -> None:
    try:
        redis.set(_PREV_LEVEL_KEY, level, ex=_PREV_LEVEL_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001
        logger.warning("prev risk level write failed: %s", exc)


def record_escalation_if_changed(
    ledger: Any, state: FuturesMarginRiskState, prev_level: str | None
) -> bool:
    """Audit a risk-level ESCALATION to reduce_only+ (rising edge only).

    Returns ``newly_escalated`` (drives the one-shot Telegram advisory). No
    ledger row is written on de-escalation or an unchanged level.
    """
    from shared.risk.futures_margin import RISK_LEVELS

    curr_idx = RISK_LEVELS.index(state.risk_level)
    prev_idx = RISK_LEVELS.index(prev_level) if prev_level in RISK_LEVELS else 0
    newly_escalated = state.risk_level in _ESCALATION_LEVELS and curr_idx > prev_idx
    if not newly_escalated:
        return False
    if ledger is None:
        return True
    try:
        ledger.record_risk_event(
            {
                "idempotency_key": (
                    f"futures_margin:{state.asof_ts.date().isoformat()}"
                    f":{prev_level or 'ok'}:{state.risk_level}"
                ),
                "event_type": "futures_margin_risk_escalation",
                "asset_class": "futures",
                "severity": "critical" if state.risk_level == "critical" else "warning",
                "prev_level": prev_level or "ok",
                "risk_level": state.risk_level,
                "margin_usage_pct": state.margin_usage_pct,
                "maintenance_buffer_krw": state.maintenance_buffer_krw,
                "liquidation_buffer_ticks": state.liquidation_buffer_ticks,
                "stress_loss_1atr_krw": state.stress_loss_1atr_krw,
                "degraded": state.degraded,
                "asof_ts": state.asof_ts.isoformat(),
            }
        )
    except Exception as exc:  # noqa: BLE001 — audit must not fail the run
        logger.warning("margin risk ledger record failed: %s", exc)
    return True


def escalation_message(state: FuturesMarginRiskState) -> str:
    """Telegram advisory text for a margin-risk escalation (advisory, not order)."""
    buf = (
        "-"
        if state.liquidation_buffer_ticks is None
        else f"{state.liquidation_buffer_ticks:.0f}틱"
    )
    return (
        "<b>선물 증거금 리스크 상향 (advisory)</b>\n"
        f"level {state.risk_level} · usage {state.margin_usage_pct:.1%}\n"
        f"유지증거금 버퍼 ₩{state.maintenance_buffer_krw:,.0f}"
        f" · 청산 버퍼 {buf}\n"
        "※ 본 메시지는 관찰용 권고이며 자동 주문/청산은 실행되지 않습니다."
    )


def _dispatch_alert(notifier: Any, message: str) -> None:
    if notifier is None:
        return

    async def _send() -> None:
        await notifier.send_message(message, is_critical=True)

    try:
        asyncio.run(_send())
    except Exception as exc:  # noqa: BLE001 — alerts must not fail the run
        logger.warning("margin-risk telegram alert failed: %s", exc)


# ---------------------------------------------------------------------------
# One-shot run
# ---------------------------------------------------------------------------


def run_margin_risk(
    *,
    context: MarginRunContext,
    redis: Any,
    now: datetime | None = None,
) -> FuturesMarginRiskState | None:
    """Compute + publish one margin-risk snapshot (see module doc)."""
    config = context.config
    if not config.enabled:
        logger.info("futures margin risk disabled (config)")
        return None

    current = now or _now_kst()
    extra_missing: list[str] = list(context.extra_missing)

    try:
        positions = list(context.positions_provider())
    except Exception as exc:  # noqa: BLE001 — degraded, not fatal
        logger.warning("futures positions read failed: %s", exc)
        positions = []
        extra_missing.append("futures_positions")

    try:
        equity, cash, snapshot_ok = context.account_snapshot_provider()
    except Exception as exc:  # noqa: BLE001
        logger.warning("account snapshot read failed: %s", exc)
        equity, cash, snapshot_ok = config.fallback_account_equity_krw, None, False

    symbols = sorted(
        {str(p.get("code", "")).strip() for p in positions if p.get("code")}
    )
    try:
        atr_by_symbol = dict(context.atr_provider(symbols))
    except Exception as exc:  # noqa: BLE001
        logger.warning("atr provider failed: %s", exc)
        atr_by_symbol = {}

    reference_price = read_reference_price(redis)

    state = compute_margin_risk(
        positions=positions,
        product_specs=context.product_specs,
        reference_product=config.reference_spec_key,
        account_equity_krw=equity,
        cash_available_krw=cash,
        reference_price=reference_price,
        atr_by_symbol=atr_by_symbol,
        thresholds=_thresholds(config),
        snapshot_ok=snapshot_ok,
        fail_closed=context.fail_closed,
        asof_ts=current,
        extra_missing=extra_missing,
    )

    logger.info(
        "futures margin risk: level=%s usage=%.3f maint_buffer=%.0f"
        " liq_buffer_ticks=%s stress_1atr=%s max_add=%s degraded=%s missing=%s",
        state.risk_level,
        state.margin_usage_pct,
        state.maintenance_buffer_krw,
        (
            "-"
            if state.liquidation_buffer_ticks is None
            else f"{state.liquidation_buffer_ticks:.1f}"
        ),
        (
            "-"
            if state.stress_loss_1atr_krw is None
            else f"{state.stress_loss_1atr_krw:.0f}"
        ),
        state.max_additional_contracts,
        state.degraded,
        json.dumps(list(state.missing_components), ensure_ascii=False),
    )

    try:
        publish_state(redis, config, state)
    except Exception:  # noqa: BLE001
        logger.exception("futures margin risk publish failed")
        return state

    # Escalation audit + advisory (rising edge to reduce_only+; deduped via a
    # Redis prev-level key so re-runs at the same level don't re-alert).
    prev_level = _read_prev_level(redis)
    newly_escalated = record_escalation_if_changed(context.ledger, state, prev_level)
    _write_prev_level(redis, state.risk_level)
    if newly_escalated and config.alerts.enabled:
        _dispatch_alert(context.notifier, escalation_message(state))

    return state


def _cli(_args: argparse.Namespace) -> int:
    config = FuturesMarginConfig.load_or_default()

    import redis as redis_lib

    redis_client = redis_lib.Redis.from_url(redis_url_from_env(), decode_responses=True)
    try:
        context = default_margin_context(config)
        run_margin_risk(context=context, redis=redis_client)
        return 0
    finally:
        redis_client.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(description="Futures margin-risk publisher")
    parser.add_argument(
        "mode",
        nargs="?",
        default="intraday",
        choices=("premarket", "intraday", "close"),
        help="one-shot mode (informational; TTL is fixed short for account state)",
    )
    args = parser.parse_args()
    return _cli(args)


if __name__ == "__main__":
    sys.exit(main())
