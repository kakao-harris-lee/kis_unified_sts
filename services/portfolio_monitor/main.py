"""Portfolio equity snapshot batch + unified monthly-MDD monitor (Phase 3B).

One-shot cron entrypoint (deploy/scheduler.crontab, 19:00 KST after the 18:45
market-risk close run), mirroring the ``services/market_risk_engine`` one-shot
pattern. Roadmap: docs/plans/2026-07-02-unified-investment-system-roadmap.md
§5.5; design doc §7.

Per run (KST trade date):

1. Compute Track B/C equity — ``capital_base`` (config/portfolio.yaml) +
   cumulative realized PnL (RuntimeLedger trades, ``track_id`` tags) +
   open-position unrealized PnL (trading-state positions hash, best-effort).
   Track A is optional pre-Phase 5 (missing → coverage recorded).
2. Evaluate the KST-month drawdown vs the month peak and map it to a breaker
   stage (NORMAL/REDUCE/HALT_NEW/FULL_STOP) with the intra-month latch.
3. Persist the daily row to RuntimeLedger ``portfolio_equity_daily``
   (idempotent upsert by trade_date).
4. Publish the FIXED 3D-UI Redis contract: ``portfolio:equity:latest`` hash
   (TTL 24h) + ``stream:portfolio.equity`` (maxlen + 24h expire, carries
   stage-transition events).
5. On stage transitions (shadow/enforce): RuntimeLedger ``record_risk_event``
   audit + Telegram alert via the existing notifier channel.
6. Enforcement (``circuit_breaker.mode=enforce`` ONLY — shadow/off never act):
   FULL_STOP trips the existing kill-switch sentinel file (path from
   ``config/kill_switch.yaml`` via KillSwitchConfig — no parallel mechanism)
   and sets the existing ``futures:live:suspended`` flag (LiveModeGuard key).
   REDUCE/HALT_NEW enforcement rides the RiskFilterLayer ``portfolio_mdd``
   filter, which reads the published hash.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from shared.portfolio.config import (
    TRACK_CORE,
    TRACK_FUTURES,
    TRACK_STOCK,
    PortfolioConfig,
)
from shared.portfolio.equity import (
    STAGE_FULL_STOP,
    STAGE_HALT_NEW,
    STAGE_REDUCE,
    PortfolioEquitySnapshot,
    TrackEquity,
    compute_track_equity,
    evaluate_snapshot,
    month_key,
    track_label,
)

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

_MODE_OFF = "off"
_MODE_ENFORCE = "enforce"

#: Track id → trading-state asset class for the unrealized-PnL source.
_TRACK_ASSET_CLASSES: dict[str, str] = {
    TRACK_STOCK: "stock",
    TRACK_FUTURES: "futures",
}

PositionsProvider = Callable[[], Sequence[Mapping[str, Any]]]


def _now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def _fmt(value: float | None) -> str:
    """Fixed contract null marker: absent values publish as ""."""
    return "" if value is None else f"{float(value):.4f}"


# ---------------------------------------------------------------------------
# Equity computation
# ---------------------------------------------------------------------------


def _default_positions_provider(asset_class: str) -> PositionsProvider:
    """Open positions with unrealized_pnl from the trading-state hash.

    Same per-position fields the dashboard risk-exposure board consumes
    (shared/streaming/trading_state.py) — no duplicate pricing logic here.
    """

    def _read() -> Sequence[Mapping[str, Any]]:
        from shared.streaming.trading_state import TradingStateReader

        return TradingStateReader(asset_class).get_positions()

    return _read


def _prior_rows(ledger: Any, trade_date: date) -> list[dict[str, Any]]:
    """Stored daily rows strictly before *trade_date* (idempotent re-runs)."""
    try:
        rows = ledger.query_portfolio_equity_daily(
            {"end": trade_date.isoformat(), "limit": 0}
        )
    except Exception as exc:  # noqa: BLE001 — history loss degrades, not kills
        logger.warning("portfolio_equity_daily history read failed: %s", exc)
        return []
    return [
        row for row in rows if str(row.get("trade_date", "")) < trade_date.isoformat()
    ]


def _fallback_equity(rows: Sequence[Mapping[str, Any]], track_id: str) -> float | None:
    """Last stored equity for a track (used when the pnl query fails)."""
    column = f"{track_label(track_id)}_equity"
    for row in reversed(rows):
        value = row.get(column)
        if value is not None:
            return float(value)
    return None


def compute_tracks(
    *,
    config: PortfolioConfig,
    ledger: Any,
    prior_rows: Sequence[Mapping[str, Any]],
    positions_providers: Mapping[str, PositionsProvider] | None = None,
) -> dict[str, TrackEquity]:
    """Compute equity for all three tracks (A optional pre-Phase 5)."""
    providers = dict(positions_providers or {})
    for track_id, asset_class in _TRACK_ASSET_CLASSES.items():
        providers.setdefault(track_id, _default_positions_provider(asset_class))

    tracks: dict[str, TrackEquity] = {}
    for track_id in (TRACK_CORE, TRACK_STOCK, TRACK_FUTURES):
        tracks[track_id] = compute_track_equity(
            track_id=track_id,
            capital_base=config.capital_base.for_track(track_id),
            ledger=ledger,
            positions_provider=providers.get(track_id),
            fallback_equity=_fallback_equity(prior_rows, track_id),
        )
    return tracks


# ---------------------------------------------------------------------------
# Persistence + publication (§3 fixed Redis contract with the 3D UI lane)
# ---------------------------------------------------------------------------


def persist_snapshot(ledger: Any, snapshot: PortfolioEquitySnapshot) -> None:
    ledger.record_portfolio_equity_daily(
        {
            "trade_date": snapshot.trade_date.isoformat(),
            "track_a_equity": snapshot.track_a_equity,
            "track_b_equity": snapshot.track_b_equity,
            "track_c_equity": snapshot.track_c_equity,
            "total_equity": snapshot.total_equity,
            "month_start_equity": snapshot.month_start_equity,
            "month_peak_equity": snapshot.month_peak_equity,
            "monthly_mdd_pct": snapshot.monthly_mdd_pct,
            "stage": snapshot.stage,
            "mode": snapshot.mode,
            "degraded": snapshot.degraded,
            "missing_components": list(snapshot.missing_components),
            "raw_stage": snapshot.raw_stage,
            "prev_stage": snapshot.prev_stage,
            "latched": snapshot.latched,
            "asof_ts": snapshot.asof_ts.isoformat(),
        }
    )


def publish_snapshot(
    redis: Any, config: PortfolioConfig, snapshot: PortfolioEquitySnapshot
) -> None:
    """Publish ``portfolio:equity:latest`` (hash) + ``stream:portfolio.equity``.

    Hash field names are a FIXED contract with the 3D UI lane — do not rename.
    """
    redis_cfg = config.monitor.redis
    latest = {
        "total_equity": _fmt(snapshot.total_equity),
        "track_b_equity": _fmt(snapshot.track_b_equity),
        "track_c_equity": _fmt(snapshot.track_c_equity),
        "track_a_equity": _fmt(snapshot.track_a_equity),
        "month_start_equity": _fmt(snapshot.month_start_equity),
        "month_peak_equity": _fmt(snapshot.month_peak_equity),
        "monthly_mdd_pct": _fmt(snapshot.monthly_mdd_pct),
        "stage": snapshot.stage,
        "mode": snapshot.mode,
        "degraded": "true" if snapshot.degraded else "false",
        "missing_components": json.dumps(
            list(snapshot.missing_components), ensure_ascii=False
        ),
        "asof_ts": snapshot.asof_ts.isoformat(),
    }
    # delete-then-hset so stale fields from a previous publish never linger.
    redis.delete(redis_cfg.latest_key)
    redis.hset(redis_cfg.latest_key, mapping=latest)
    redis.expire(redis_cfg.latest_key, redis_cfg.latest_ttl_seconds)

    event = {
        "trade_date": snapshot.trade_date.isoformat(),
        "total_equity": _fmt(snapshot.total_equity),
        "monthly_mdd_pct": _fmt(snapshot.monthly_mdd_pct),
        "stage": snapshot.stage,
        "prev_stage": snapshot.prev_stage or "",
        "stage_changed": "true" if snapshot.stage_changed else "false",
        "mode": snapshot.mode,
        "degraded": "true" if snapshot.degraded else "false",
    }
    redis.xadd(
        redis_cfg.stream_key,
        event,
        maxlen=redis_cfg.stream_maxlen,
        approximate=True,
    )
    redis.expire(redis_cfg.stream_key, redis_cfg.stream_ttl_seconds)


# ---------------------------------------------------------------------------
# Audit + alerts (existing ledger/telegram channels — no new infra)
# ---------------------------------------------------------------------------


def _stage_severity_label(stage: str) -> str:
    if stage == STAGE_FULL_STOP:
        return "critical"
    if stage in (STAGE_HALT_NEW, STAGE_REDUCE):
        return "warning"
    return "info"


def record_stage_transition(ledger: Any, snapshot: PortfolioEquitySnapshot) -> None:
    """Audit a stage transition via RuntimeLedger.record_risk_event."""
    ledger.record_risk_event(
        {
            "idempotency_key": (
                f"portfolio_mdd:stage:{snapshot.trade_date.isoformat()}"
                f":{snapshot.effective_prev_stage}:{snapshot.stage}"
            ),
            "event_type": "portfolio_mdd_stage_transition",
            "asset_class": "cross_asset",
            "severity": _stage_severity_label(snapshot.stage),
            "prev_stage": snapshot.prev_stage,
            "stage": snapshot.stage,
            "raw_stage": snapshot.raw_stage,
            "latched": snapshot.latched,
            "monthly_mdd_pct": snapshot.monthly_mdd_pct,
            "total_equity": snapshot.total_equity,
            "month_peak_equity": snapshot.month_peak_equity,
            "mode": snapshot.mode,
            "trade_date": snapshot.trade_date.isoformat(),
            "degraded": snapshot.degraded,
        }
    )


def alert_messages(
    snapshot: PortfolioEquitySnapshot, config: PortfolioConfig
) -> list[str]:
    """Telegram messages owed for this snapshot (stage transitions only)."""
    alerts = config.monitor.alerts
    if not alerts.enabled or not snapshot.stage_changed:
        return []
    notify = set(alerts.notify_stages)
    if snapshot.stage not in notify and snapshot.effective_prev_stage not in notify:
        return []
    mode_note = {
        _MODE_ENFORCE: "enforce — Track B/C entry gating ACTIVE",
        "shadow": "shadow — observe-only, no enforcement",
        _MODE_OFF: "off",
    }.get(snapshot.mode, snapshot.mode)
    latch_note = " (latched)" if snapshot.latched else ""
    return [
        "<b>Portfolio MDD stage change</b>\n"
        f"{snapshot.effective_prev_stage} → {snapshot.stage}{latch_note}\n"
        f"monthly MDD {snapshot.monthly_mdd_pct:.2%}"
        f" · total ₩{snapshot.total_equity:,.0f}"
        f" · peak ₩{snapshot.month_peak_equity:,.0f}\n"
        f"mode: {mode_note}"
    ]


def _dispatch_alerts(notifier: Any, messages: list[str]) -> None:
    if notifier is None or not messages:
        return

    async def _send_all() -> None:
        for message in messages:
            await notifier.send_message(message, is_critical=True)

    try:
        asyncio.run(_send_all())
    except Exception as exc:  # noqa: BLE001 — alerts must not fail the run
        logger.warning("portfolio-monitor telegram alert failed: %s", exc)


# ---------------------------------------------------------------------------
# FULL_STOP enforcement (existing kill-switch sentinel + suspend flag — reuse)
# ---------------------------------------------------------------------------


def default_sentinel_path() -> str:
    """Kill-switch sentinel path from config/kill_switch.yaml (reused, not new).

    Imports the existing loader (services/kill_switch/config.py) so the path
    stays a single constant owned by the kill-switch config; falls back to the
    loader's own default when the YAML is unavailable.
    """
    from services.kill_switch.config import KillSwitchConfig

    try:
        return KillSwitchConfig.from_yaml().sentinel_path
    except Exception:  # noqa: BLE001 — missing YAML → loader defaults
        return KillSwitchConfig().sentinel_path


def default_suspend_key() -> str:
    """``futures:live:suspended`` key from the existing LiveModeGuard config."""
    from shared.execution.live_mode_guard import LiveModeGuard

    try:
        return LiveModeGuard.from_yaml().suspend_key
    except Exception:  # noqa: BLE001
        return LiveModeGuard().suspend_key


def trip_full_stop(
    *,
    redis: Any,
    ledger: Any,
    snapshot: PortfolioEquitySnapshot,
    sentinel_path: str,
    suspend_key: str,
) -> list[str]:
    """Trip the existing kill-switch mechanisms for a FULL_STOP stage.

    Reuses (never reimplements) the two existing latches:

    * kill-switch sentinel file — order_router/kill_switch refuse to operate
      while it exists; operator clears it manually after the monthly review.
    * ``futures:live:suspended`` Redis flag — LiveModeGuard fail-closed read.
      Intentionally NO TTL: it is the pre-existing operator-latched flag.

    Returns the list of actions actually performed (for logging/tests).
    """
    actions: list[str] = []

    path = Path(sentinel_path)
    if path.exists():
        logger.info("kill-switch sentinel already present at %s", path)
    else:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "reason=portfolio_mdd_full_stop\n"
                f"details=monthly_mdd_pct={snapshot.monthly_mdd_pct:.4f}"
                f" trade_date={snapshot.trade_date.isoformat()}"
                f" total_equity={snapshot.total_equity:.0f}\n"
            )
            actions.append("sentinel_written")
            logger.critical("PORTFOLIO FULL_STOP: sentinel written at %s", path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("sentinel write failed at %s: %s", path, exc)

    try:
        redis.set(suspend_key, "1")
        actions.append("suspend_flag_set")
        logger.critical("PORTFOLIO FULL_STOP: %s flag set", suspend_key)
    except Exception as exc:  # noqa: BLE001
        logger.exception("suspend flag set failed (%s): %s", suspend_key, exc)

    try:
        ledger.record_risk_event(
            {
                "idempotency_key": (
                    f"portfolio_mdd:full_stop_trip:{snapshot.trade_date.isoformat()}"
                ),
                "event_type": "portfolio_mdd_full_stop_trip",
                "asset_class": "cross_asset",
                "severity": "critical",
                "actions": actions,
                "sentinel_path": str(path),
                "suspend_key": suspend_key,
                "monthly_mdd_pct": snapshot.monthly_mdd_pct,
                "total_equity": snapshot.total_equity,
                "trade_date": snapshot.trade_date.isoformat(),
            }
        )
    except Exception as exc:  # noqa: BLE001 — audit must not fail the trip
        logger.warning("full-stop trip audit failed: %s", exc)

    return actions


# ---------------------------------------------------------------------------
# One-shot run
# ---------------------------------------------------------------------------


def run_snapshot(
    *,
    config: PortfolioConfig,
    ledger: Any,
    redis: Any,
    positions_providers: Mapping[str, PositionsProvider] | None = None,
    calendar: Any = None,
    notifier: Any = None,
    trade_date: date | None = None,
    now: datetime | None = None,
    dry_run: bool = False,
    sentinel_path: str | None = None,
    suspend_key: str | None = None,
) -> int:
    """Execute one daily snapshot run (see module docstring)."""
    current_time = now or _now_kst()
    day = trade_date or current_time.date()

    if calendar is None:
        from shared.calendar import MarketCalendar

        calendar = MarketCalendar()
    if not calendar.is_market_day(day):
        logger.info("%s is not a market day; skipping portfolio snapshot", day)
        return 0

    mode = config.circuit_breaker.mode
    prior_rows = _prior_rows(ledger, day)
    tracks = compute_tracks(
        config=config,
        ledger=ledger,
        prior_rows=prior_rows,
        positions_providers=positions_providers,
    )
    snapshot = evaluate_snapshot(
        trade_date=day,
        tracks=tracks,
        month_history=prior_rows,
        stages=config.circuit_breaker.monthly_mdd_stages,
        stage_latch=config.circuit_breaker.stage_latch,
        mode=mode,
        asof_ts=current_time,
    )

    logger.info(
        "portfolio snapshot %s (month %s): total=%.0f b=%s c=%s a=%s"
        " start=%.0f peak=%.0f mdd=%.4f stage=%s (raw=%s prev=%s latched=%s)"
        " mode=%s degraded=%s missing=%s",
        day,
        month_key(day),
        snapshot.total_equity,
        _fmt(snapshot.track_b_equity) or "-",
        _fmt(snapshot.track_c_equity) or "-",
        _fmt(snapshot.track_a_equity) or "-",
        snapshot.month_start_equity,
        snapshot.month_peak_equity,
        snapshot.monthly_mdd_pct,
        snapshot.stage,
        snapshot.raw_stage,
        snapshot.prev_stage,
        snapshot.latched,
        snapshot.mode,
        snapshot.degraded,
        list(snapshot.missing_components),
    )

    if dry_run:
        logger.info("dry-run: no persist/publish/actions")
        return 0

    persist_snapshot(ledger, snapshot)
    publish_snapshot(redis, config, snapshot)

    if snapshot.stage_changed and mode != _MODE_OFF:
        try:
            record_stage_transition(ledger, snapshot)
        except Exception as exc:  # noqa: BLE001 — audit must not fail the run
            logger.warning("stage transition audit failed: %s", exc)
        _dispatch_alerts(notifier, alert_messages(snapshot, config))

    # Enforcement is strictly opt-in: shadow/off NEVER trip anything.
    if mode == _MODE_ENFORCE and snapshot.stage == STAGE_FULL_STOP:
        trip_full_stop(
            redis=redis,
            ledger=ledger,
            snapshot=snapshot,
            sentinel_path=sentinel_path or default_sentinel_path(),
            suspend_key=suspend_key or default_suspend_key(),
        )

    return 0


# ---------------------------------------------------------------------------
# CLI glue
# ---------------------------------------------------------------------------


def _default_ledger() -> Any:
    from shared.storage import SQLiteRuntimeLedger
    from shared.storage.config import StorageConfig

    storage = StorageConfig.load_or_default()
    return SQLiteRuntimeLedger(storage.runtime_storage.sqlite)


def _default_notifier(config: PortfolioConfig) -> Any | None:
    if not config.monitor.alerts.enabled:
        return None
    try:
        from shared.notification.telegram import notifier_for_domain

        return notifier_for_domain(config.monitor.alerts.domain)
    except Exception as exc:  # noqa: BLE001
        logger.warning("telegram notifier unavailable: %s", exc)
        return None


def _cli(args: argparse.Namespace) -> int:
    import redis as redis_lib

    from shared.config.runtime_defaults import redis_url_from_env

    config = PortfolioConfig.load_or_default()
    ledger = _default_ledger()
    redis_client = redis_lib.Redis.from_url(redis_url_from_env(), decode_responses=True)
    try:
        return run_snapshot(
            config=config,
            ledger=ledger,
            redis=redis_client,
            notifier=_default_notifier(config),
            trade_date=date.fromisoformat(args.date) if args.date else None,
            dry_run=args.dry_run,
        )
    finally:
        redis_client.close()
        ledger.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Portfolio equity snapshot + unified monthly-MDD monitor"
    )
    parser.add_argument(
        "--date", help="KST trade date override (YYYY-MM-DD, default: today)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="compute + log only; no ledger write, Redis publish, or actions",
    )
    return _cli(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
