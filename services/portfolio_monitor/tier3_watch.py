"""Tier 3 opportunity-capital watch (Phase 5A — watch/alert ONLY).

Runs inside the daily portfolio monitor right after the equity snapshot
(08:50/19:00 KST cron). Computes the KOSPI drawdown from its rolling peak
over the ``market_structure_daily`` close history and publishes the FIXED
5E-UI Redis contract ``portfolio:tier3:watch`` (hash, TTL 24h):

* ``kospi_close`` / ``kospi_peak`` — latest close and rolling-window peak
  (source column config-driven; the dataset currently carries ``k200_close``).
* ``drawdown`` — FRACTION (Phase 3 unit decision: ``-0.16`` = −16%).
* ``trigger_threshold`` — from ``fund_movement.tier3_activation``
  (설계서 §1.2, default −0.15). Inclusive: drawdown exactly at the threshold
  triggers (설계서 "고점 대비 −15% **이상** 하락").
* ``triggered`` — ``"true"``/``"false"``.
* ``asof_ts`` — KST-naive ISO timestamp.

On the triggered RISING EDGE (previous publish not triggered → now triggered)
one Telegram advisory fires through the existing notifier channel. The message
always states that Tier 3 activation judgment and execution are MANUAL — no
automated buying exists anywhere on this path. Insufficient history → nothing
is published (the previous hash ages out via its TTL) and the gap is logged.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from shared.portfolio.config import PortfolioConfig, Tier3WatchConfig

logger = logging.getLogger(__name__)

#: (start, end) -> [(trade_date, close), ...] oldest→newest.
ClosesProvider = Callable[[date, date], Sequence[tuple[date, float]]]

#: Calendar-days per trading-day cushion for the history read window
#: (KRX ≈ 248 trading days/year → 1.6 covers weekends/holidays comfortably).
_CALENDAR_PER_TRADING_DAY = 1.6
_CALENDAR_BUFFER_DAYS = 14


@dataclass(frozen=True)
class Tier3Watch:
    """One evaluated Tier 3 watch snapshot (published to Redis)."""

    kospi_close: float
    kospi_peak: float
    drawdown: float  # fraction (≤ 0), -0.16 == -16%
    trigger_threshold: float
    triggered: bool
    asof_ts: datetime


@dataclass
class Tier3RunContext:
    """Injected dependencies for one Tier 3 watch run (hermetic-testable)."""

    config: PortfolioConfig
    closes_provider: ClosesProvider
    notifier: Any | None = None


def _default_closes_provider(watch: Tier3WatchConfig) -> ClosesProvider:
    """(trade_date, close) pairs from market_structure_daily close rows."""

    def _read(start: date, end: date) -> list[tuple[date, float]]:
        from services.portfolio_monitor.hedge_advisor import _frame_to_closes
        from shared.storage.market_structure_store import (
            create_market_structure_store,
        )

        frame = create_market_structure_store().read_range(
            start=start, end=end, snapshot="close"
        )
        return _frame_to_closes(frame, "trade_date", watch.close_column)

    return _read


def default_tier3_context(config: PortfolioConfig) -> Tier3RunContext:
    """Build the production run context (real Parquet store + notifier)."""
    watch = config.monitor.tier3_watch
    notifier = None
    if watch.alerts_enabled:
        try:
            from shared.notification.telegram import notifier_for_domain

            notifier = notifier_for_domain(config.monitor.alerts.domain)
        except Exception as exc:  # noqa: BLE001 — alerts must not block the watch
            logger.warning("tier3 telegram notifier unavailable: %s", exc)
    return Tier3RunContext(
        config=config,
        closes_provider=_default_closes_provider(watch),
        notifier=notifier,
    )


# ---------------------------------------------------------------------------
# Evaluation (pure)
# ---------------------------------------------------------------------------


def evaluate_tier3_watch(
    closes: Sequence[tuple[date, float]],
    *,
    trade_date: date,
    peak_window_days: int,
    trigger_threshold: float,
    asof_ts: datetime,
) -> Tier3Watch | None:
    """Fold the close history into a watch snapshot (None when insufficient).

    ``closes`` may arrive unordered; rows after ``trade_date`` are excluded
    (no look-ahead) and the rolling peak covers the last ``peak_window_days``
    rows INCLUDING the latest close.
    """
    usable = sorted(
        (day, float(close))
        for day, close in closes
        if day is not None and day <= trade_date and close and close > 0
    )
    if not usable:
        return None
    window = usable[-peak_window_days:]
    kospi_close = window[-1][1]
    kospi_peak = max(close for _, close in window)
    drawdown = (kospi_close - kospi_peak) / kospi_peak if kospi_peak > 0 else 0.0
    return Tier3Watch(
        kospi_close=kospi_close,
        kospi_peak=kospi_peak,
        drawdown=drawdown,
        trigger_threshold=trigger_threshold,
        # Inclusive: exactly -15% counts as "고점 대비 -15% 이상 하락".
        triggered=drawdown <= trigger_threshold,
        asof_ts=asof_ts,
    )


# ---------------------------------------------------------------------------
# Publication + rising-edge alert
# ---------------------------------------------------------------------------


def _fmt(value: float) -> str:
    return f"{float(value):.4f}"


def publish_watch(redis: Any, watch_cfg: Tier3WatchConfig, watch: Tier3Watch) -> None:
    """Publish ``portfolio:tier3:watch`` — FIXED 5E-UI contract, do not rename."""
    fields = {
        "kospi_close": _fmt(watch.kospi_close),
        "kospi_peak": _fmt(watch.kospi_peak),
        "drawdown": _fmt(watch.drawdown),
        "trigger_threshold": _fmt(watch.trigger_threshold),
        "triggered": "true" if watch.triggered else "false",
        "asof_ts": watch.asof_ts.isoformat(),
    }
    # delete-then-hset so stale fields from a previous publish never linger.
    redis.delete(watch_cfg.redis_key)
    redis.hset(watch_cfg.redis_key, mapping=fields)
    redis.expire(watch_cfg.redis_key, watch_cfg.ttl_seconds)


def _previously_triggered(redis: Any, key: str) -> bool:
    """Triggered state of the previous publish (missing hash → False)."""
    try:
        return (redis.hget(key, "triggered") or "") == "true"
    except Exception as exc:  # noqa: BLE001 — edge detection degrades, not kills
        logger.warning("tier3 previous-state read failed: %s", exc)
        return False


def alert_message(watch: Tier3Watch, tranches: int) -> str:
    """Telegram advisory text — activation judgment/execution stay MANUAL."""
    return (
        "<b>Tier 3 발동 조건 도달 (watch)</b>\n"
        f"KOSPI 프록시 {watch.kospi_close:,.2f}"
        f" · 롤링 고점 {watch.kospi_peak:,.2f}\n"
        f"드로다운 {watch.drawdown:.2%}"
        f" (트리거 {watch.trigger_threshold:.0%})\n"
        f"규칙: 코어 논거 미훼손 확인 후 {tranches}분할 투입 (설계서 §1.2)\n"
        "※ 발동 판단·집행은 수동입니다 — 자동 매수는 존재하지 않습니다."
    )


def _dispatch_alert(notifier: Any, message: str) -> None:
    if notifier is None:
        return

    async def _send() -> None:
        await notifier.send_message(message, is_critical=True)

    try:
        asyncio.run(_send())
    except Exception as exc:  # noqa: BLE001 — alerts must not fail the run
        logger.warning("tier3 watch telegram alert failed: %s", exc)


# ---------------------------------------------------------------------------
# One-shot run (called by services.portfolio_monitor.main.run_snapshot)
# ---------------------------------------------------------------------------


def run_tier3_watch(
    *,
    context: Tier3RunContext,
    redis: Any,
    trade_date: date,
    now: datetime,
) -> Tier3Watch | None:
    """Compute + publish + (rising-edge) alert one Tier 3 watch snapshot.

    Watch/alert only: Redis publication, Telegram text, and logs are the only
    side effects — nothing on this path ever places an order.
    """
    config = context.config
    watch_cfg = config.monitor.tier3_watch
    if not watch_cfg.enabled:
        logger.info("tier3 watch disabled (config/portfolio.yaml)")
        return None

    activation = config.fund_movement.tier3_activation
    lookback = timedelta(
        days=int(watch_cfg.peak_window_days * _CALENDAR_PER_TRADING_DAY)
        + _CALENDAR_BUFFER_DAYS
    )
    try:
        closes = list(context.closes_provider(trade_date - lookback, trade_date))
    except Exception as exc:  # noqa: BLE001 — a broken store degrades, not kills
        logger.warning("tier3 close-history read failed: %s", exc)
        closes = []

    watch = evaluate_tier3_watch(
        closes,
        trade_date=trade_date,
        peak_window_days=watch_cfg.peak_window_days,
        trigger_threshold=activation.kospi_drawdown_from_peak,
        asof_ts=now,
    )
    if watch is None:
        logger.warning(
            "tier3 watch: no usable %s history up to %s — nothing published",
            watch_cfg.close_column,
            trade_date.isoformat(),
        )
        return None

    was_triggered = _previously_triggered(redis, watch_cfg.redis_key)
    publish_watch(redis, watch_cfg, watch)

    logger.info(
        "tier3 watch %s: close=%.2f peak=%.2f drawdown=%.4f threshold=%.4f"
        " triggered=%s (prev=%s)",
        trade_date,
        watch.kospi_close,
        watch.kospi_peak,
        watch.drawdown,
        watch.trigger_threshold,
        watch.triggered,
        was_triggered,
    )

    if watch.triggered and not was_triggered and watch_cfg.alerts_enabled:
        _dispatch_alert(context.notifier, alert_message(watch, activation.tranches))

    return watch
