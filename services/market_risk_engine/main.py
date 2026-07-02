"""Market Risk Score engine — run via cron (KST-native, one-shot).

Three cron modes (deploy/scheduler.crontab), mirroring the
market_structure_collector one-shot pattern:

* ``premarket`` (08:05 KST, after the 08:00 structure collector): scores the
  day's ``premarket`` row (pre-open knowledge only) and publishes to Redis.
* ``intraday`` (every 30 min, 09:00-15:30 KST; session window in config):
  re-scores the current ``market:structure:latest`` hash — Redis-only, no
  Parquet writes (intraday provisional values never reach the daily store).
* ``close`` (18:45 KST, after the 18:40 close collector): the confirmed daily
  computation — publishes Redis, writes ``regime:unified:daily``, and merges
  the score columns back into the day's Parquet ``close`` row (idempotent
  replace-day).

Plus ``hindcast`` (`--start/--end/--write`, also reachable via ``--hindcast``)
for §4.4 ex-post validation over backfilled history — look-ahead-free by
construction (see :func:`shared.risk.market_risk_score.hindcast`).

Shadow-only (Phase 1): outputs feed Redis/Parquet/dashboard/Telegram; nothing
here gates or sizes any strategy path. Band transitions are audited via
``RuntimeLedger.record_risk_event`` and alerted through the existing
``shared/notification/telegram`` channel helpers (no new alert infra).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from shared.config.runtime_defaults import redis_url_from_env
from shared.risk.market_risk_score import (
    BandState,
    MarketRiskConfig,
    MarketRiskResult,
    compute_market_risk,
    hindcast,
    history_records,
    risk_row_fields,
    seed_state_from_records,
)

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

_SNAPSHOT_CLOSE = "close"
_SNAPSHOT_PREMARKET = "premarket"
_MODES = ("premarket", "intraday", "close")

# Fixed Redis contract field name (Phase 1c UI lane): the smoothed score is
# published as ``score_ema3`` regardless of the configured ema_span.
_EMA_FIELD = "score_ema3"


def _now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    return not (isinstance(value, float) and value != value)


def _fmt(value: float | None) -> str:
    return "" if value is None else f"{float(value):.4f}"


# ---------------------------------------------------------------------------
# Current-row acquisition
# ---------------------------------------------------------------------------


def _parse_structure_hash(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse the flattened ``market:structure:latest`` hash back into a row.

    Numeric strings become floats; empty strings (the collector's null
    marker) are dropped; everything else (labels, dates, JSON) stays str.
    """
    row: dict[str, Any] = {}
    for key, value in raw.items():
        name = str(key)
        text = str(value)
        if not text:
            continue
        try:
            row[name] = float(text)
        except ValueError:
            row[name] = text
    return row


def _read_structure_latest(redis: Any, config: MarketRiskConfig) -> dict[str, Any]:
    try:
        raw = redis.hgetall(config.redis.structure_latest_key)
    except Exception as exc:  # noqa: BLE001 — degraded Redis must not kill the run
        logger.warning("market:structure:latest read failed: %s", exc)
        return {}
    if not raw:
        return {}
    return _parse_structure_hash(dict(raw))


def _read_store_row(store: Any, day: date, snapshot: str) -> dict[str, Any]:
    frame = store.read_range(day, day, snapshot=snapshot)
    records = history_records(frame)
    if not records:
        return {}
    return {key: value for key, value in records[0].items() if _is_present(value)}


def load_current_row(
    mode: str, day: date, store: Any, redis: Any, config: MarketRiskConfig
) -> tuple[dict[str, Any], date]:
    """Resolve the row to score plus its effective trade date."""
    if mode == "intraday":
        row = _read_structure_latest(redis, config)
        if row:
            parsed = day
            effective = row.get("trade_date")
            if _is_present(effective):
                try:
                    parsed = date.fromisoformat(str(effective)[:10])
                except ValueError:
                    logger.warning(
                        "unparseable trade_date in latest hash: %r", effective
                    )
            return row, parsed
        return _read_store_row(store, day, _SNAPSHOT_PREMARKET), day

    snapshot = _SNAPSHOT_PREMARKET if mode == "premarket" else _SNAPSHOT_CLOSE
    row = _read_store_row(store, day, snapshot)
    if row:
        return row, day
    logger.warning(
        "no %s row stored for %s; falling back to market:structure:latest",
        snapshot,
        day,
    )
    return _read_structure_latest(redis, config), day


# ---------------------------------------------------------------------------
# HAR-RV vol input (forecast:vol:current → har_rv_pred)
# ---------------------------------------------------------------------------


def inject_vol_forecast(
    row: dict[str, Any], redis: Any, config: MarketRiskConfig, now: datetime
) -> tuple[dict[str, Any], dict[str, str]]:
    """Merge ``har_rv_pred`` from the HAR-RV forecast into ``row``.

    Returns ``(injected_columns, component_asof)`` so close mode can persist
    the raw input alongside the score columns (the rolling vol history then
    accumulates forward in the daily store).
    """
    if _is_present(row.get("har_rv_pred")):
        return {}, {}
    from shared.forecasting.vol_reader import read_latest_vol_forecast

    forecast = read_latest_vol_forecast(redis)
    if forecast is None:
        return {}, {}
    asof = forecast.asof
    if asof.tzinfo is not None:
        asof = asof.astimezone(KST).replace(tzinfo=None)
    age = (now - asof).total_seconds()
    if age < 0 or age > config.runner.vol_forecast_max_age_seconds:
        logger.info("vol forecast too old for har_rv_pred (age=%.0fs)", age)
        return {}, {}
    injected = {"har_rv_pred": float(forecast.forecast_pct)}
    row.update(injected)
    return injected, {"vol": asof.isoformat()}


# ---------------------------------------------------------------------------
# Hysteresis state (Redis, with durable Parquet fallback)
# ---------------------------------------------------------------------------


def read_band_state(
    redis: Any, config: MarketRiskConfig, history: Any
) -> tuple[float | None, BandState]:
    """Previous (daily EMA, band state) — Redis first, close-row fallback.

    The Redis state key has a 48h TTL; after long weekends/holidays it may be
    gone, so the previous band/EMA are re-seeded from the last close rows'
    score columns (same rebuild pattern as the collector's cum20 window).
    """
    records = history_records(history)
    prev_ema, seeded = seed_state_from_records(records)

    try:
        raw = redis.hgetall(config.redis.band_state_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("band state read failed: %s", exc)
        raw = {}
    if not raw:
        return prev_ema, seeded

    data = {str(key): str(value) for key, value in dict(raw).items()}
    band = data.get("band") or None
    pending = data.get("pending_band") or None
    try:
        pending_count = int(data.get("pending_count") or 0)
    except ValueError:
        pending_count = 0
    degraded = data.get("degraded") == "true"
    return prev_ema, BandState(
        band=band or seeded.band,
        pending_band=pending,
        pending_count=pending_count,
        degraded=degraded,
    )


def write_band_state(redis: Any, config: MarketRiskConfig, state: BandState) -> None:
    key = config.redis.band_state_key
    mapping = {
        "band": state.band or "",
        "pending_band": state.pending_band or "",
        "pending_count": str(int(state.pending_count)),
        "degraded": "true" if state.degraded else "false",
        "updated_at": _now_kst().isoformat(),
    }
    redis.delete(key)
    redis.hset(key, mapping=mapping)
    redis.expire(key, config.redis.band_state_ttl_seconds)


# ---------------------------------------------------------------------------
# Publication (§4.3 contract — field names fixed with the 1c UI lane)
# ---------------------------------------------------------------------------


def publish_result(
    redis: Any, config: MarketRiskConfig, result: MarketRiskResult
) -> None:
    """Publish ``market:risk:latest`` (hash) + ``stream:market.risk`` (stream)."""
    latest = {
        "score": _fmt(result.score),
        _EMA_FIELD: _fmt(result.score_ema),
        "band": result.band or "",
        "regime": result.regime or "",
        "degraded": "true" if result.degraded else "false",
        "coverage_ratio": _fmt(result.coverage_ratio),
        "missing_components": json.dumps(result.missing_components, ensure_ascii=False),
        "asof_ts": result.asof_ts.isoformat(),
        "kind": result.kind,
        "components": json.dumps(result.components_payload(), ensure_ascii=False),
    }
    latest_key = config.redis.latest_key
    # delete-then-hset so stale fields from a previous publish never linger.
    redis.delete(latest_key)
    redis.hset(latest_key, mapping=latest)
    redis.expire(latest_key, config.redis.latest_ttl_seconds)

    event = {
        "kind": result.kind,
        "score": _fmt(result.score),
        "band": result.band or "",
        "band_changed": "true" if result.band_changed else "false",
        "prev_band": result.prev_band or "",
    }
    stream_key = config.redis.stream_key
    redis.xadd(stream_key, event, maxlen=config.redis.stream_maxlen, approximate=True)
    redis.expire(stream_key, config.redis.stream_ttl_seconds)


def publish_regime_daily(
    redis: Any, config: MarketRiskConfig, result: MarketRiskResult
) -> None:
    """Close-confirmed unified regime (``regime:unified:daily``, TTL 48h)."""
    payload = json.dumps(
        {
            "date": result.trade_date.isoformat(),
            "regime": result.regime,
            "score": None if result.score is None else round(result.score, 4),
            "band": result.band,
        },
        ensure_ascii=False,
    )
    redis.set(
        config.redis.regime_daily_key,
        payload,
        ex=config.redis.regime_daily_ttl_seconds,
    )


# ---------------------------------------------------------------------------
# Audit + alerts (reuse existing ledger/telegram paths — no new infra)
# ---------------------------------------------------------------------------


def record_band_transition(
    ledger: Any, result: MarketRiskResult, config: MarketRiskConfig
) -> None:
    """Audit a confirmed band transition via RuntimeLedger.record_risk_event."""
    top_band = config.ordered_bands()[-1].name
    if result.band == top_band:
        severity = "critical"
    elif result.band in config.alerts.notify_bands:
        severity = "warning"
    else:
        severity = "info"
    ledger.record_risk_event(
        {
            "idempotency_key": (
                f"market_risk:band:{result.trade_date.isoformat()}"
                f":{result.kind}:{result.prev_band}:{result.band}"
            ),
            "event_type": "market_risk_band_transition",
            "asset_class": "cross_asset",
            "severity": severity,
            "prev_band": result.prev_band,
            "band": result.band,
            "score": result.score,
            _EMA_FIELD: result.score_ema,
            "regime": result.regime,
            "kind": result.kind,
            "trade_date": result.trade_date.isoformat(),
            "coverage_ratio": result.coverage_ratio,
            "degraded": result.degraded,
        }
    )


def alert_messages(result: MarketRiskResult, config: MarketRiskConfig) -> list[str]:
    """Telegram messages owed for this result (band transition / degraded)."""
    alerts = config.alerts
    if not alerts.enabled:
        return []
    messages: list[str] = []
    if result.band_changed and (
        result.band in alerts.notify_bands or result.prev_band in alerts.notify_bands
    ):
        messages.append(
            "<b>Market Risk band change</b>\n"
            f"{result.prev_band or '-'} → {result.band}"
            f" (score {_fmt(result.score) or '-'},"
            f" ema {_fmt(result.score_ema) or '-'})\n"
            f"regime: {result.regime or '-'}"
            f" · coverage {result.coverage_ratio:.0%}"
            f" · kind {result.kind}"
        )
    if result.degraded_entered and alerts.notify_on_degraded:
        missing = ", ".join(result.missing_components) or "-"
        messages.append(
            "<b>Market Risk DEGRADED</b>\n"
            f"coverage {result.coverage_ratio:.0%}"
            f" &lt; {config.engine.min_coverage_ratio:.0%}"
            f" · kind {result.kind}\n"
            f"missing: {missing}"
        )
    return messages


def _dispatch_alerts(notifier: Any, messages: list[str]) -> None:
    if notifier is None or not messages:
        return

    async def _send_all() -> None:
        for message in messages:
            await notifier.send_message(message, is_critical=True)

    try:
        asyncio.run(_send_all())
    except Exception as exc:  # noqa: BLE001 — alerts must not fail the run
        logger.warning("market-risk telegram alert failed: %s", exc)


def _default_ledger() -> Any | None:
    try:
        from shared.storage import SQLiteRuntimeLedger
        from shared.storage.config import StorageConfig

        storage = StorageConfig.load_or_default()
        return SQLiteRuntimeLedger(storage.runtime_storage.sqlite)
    except Exception as exc:  # noqa: BLE001 — audit must not fail the run
        logger.warning("runtime ledger unavailable: %s", exc)
        return None


def _default_notifier(config: MarketRiskConfig) -> Any | None:
    if not config.alerts.enabled:
        return None
    try:
        from shared.notification.telegram import notifier_for_domain

        return notifier_for_domain(config.alerts.domain)
    except Exception as exc:  # noqa: BLE001
        logger.warning("telegram notifier unavailable: %s", exc)
        return None


# ---------------------------------------------------------------------------
# One-shot run
# ---------------------------------------------------------------------------


def _in_intraday_session(now: datetime, config: MarketRiskConfig) -> bool:
    start = time.fromisoformat(config.runner.intraday_session_start)
    end = time.fromisoformat(config.runner.intraday_session_end)
    return start <= now.time() <= end


def run_mode(
    mode: str,
    *,
    store: Any,
    redis: Any,
    config: MarketRiskConfig,
    trade_date: date | None = None,
    now: datetime | None = None,
    calendar: Any = None,
    ledger: Any = None,
    notifier: Any = None,
) -> int:
    """Execute one engine mode (premarket / intraday / close)."""
    if mode not in _MODES:
        raise ValueError(f"unknown market-risk mode {mode!r}")

    current_time = now or _now_kst()
    day = trade_date or current_time.date()

    if calendar is None:
        from shared.calendar import MarketCalendar

        calendar = MarketCalendar()
    if not calendar.is_market_day(day):
        logger.info("%s is not a market day; skipping %s run", day, mode)
        return 0
    if mode == "intraday" and not _in_intraday_session(current_time, config):
        logger.info("%s outside intraday session window; skipping", current_time.time())
        return 0

    row, effective_day = load_current_row(mode, day, store, redis, config)
    if not row:
        logger.warning("no market-structure inputs available for %s (%s)", day, mode)

    injected_columns, component_asof = inject_vol_forecast(
        row, redis, config, current_time
    )

    history = store.read_range(
        effective_day - timedelta(days=config.runner.history_lookback_days),
        effective_day - timedelta(days=1),
        snapshot=_SNAPSHOT_CLOSE,
    )
    prev_ema, state = read_band_state(redis, config, history)

    result, next_state = compute_market_risk(
        current_row=row,
        history=history,
        config=config,
        trade_date=effective_day,
        kind=mode,
        prev_ema=prev_ema,
        band_state=state,
        component_asof=component_asof,
        asof_ts=current_time,
    )

    publish_result(redis, config, result)
    write_band_state(redis, config, next_state)

    if mode == "close":
        publish_regime_daily(redis, config, result)
        _write_close_row(store, effective_day, result, injected_columns)

    if result.band_changed:
        active_ledger = ledger if ledger is not None else _default_ledger()
        if active_ledger is not None:
            try:
                record_band_transition(active_ledger, result, config)
            except Exception as exc:  # noqa: BLE001 — audit must not fail the run
                logger.warning("band transition ledger record failed: %s", exc)

    messages = alert_messages(result, config)
    if messages:
        _dispatch_alerts(
            notifier if notifier is not None else _default_notifier(config), messages
        )

    logger.info(
        "market-risk %s: date=%s score=%s ema=%s band=%s regime=%s degraded=%s"
        " coverage=%.3f missing=%s",
        mode,
        effective_day,
        _fmt(result.score) or "-",
        _fmt(result.score_ema) or "-",
        result.band,
        result.regime,
        result.degraded,
        result.coverage_ratio,
        result.missing_components,
    )
    return 0


def _write_close_row(
    store: Any,
    day: date,
    result: MarketRiskResult,
    injected_columns: dict[str, float] | None = None,
) -> None:
    """Merge score columns into the existing close row (idempotent).

    Injected raw inputs (e.g. har_rv_pred from the vol forecast) are persisted
    alongside the score so the rolling normalization history accumulates.
    """
    base = _read_store_row(store, day, _SNAPSHOT_CLOSE)
    if not base:
        logger.warning("no close row stored for %s; score columns not persisted", day)
        return
    if injected_columns:
        base.update(injected_columns)
    base.update(risk_row_fields(result))
    store.replace_day(day, _SNAPSHOT_CLOSE, base)


# ---------------------------------------------------------------------------
# Hindcast CLI (§4.4)
# ---------------------------------------------------------------------------


def run_hindcast(
    *,
    store: Any,
    config: MarketRiskConfig,
    start: date,
    end: date,
    write: bool,
) -> int:
    results = hindcast(store, config, start, end, write=write)
    if not results:
        print(f"hindcast: no close rows in {start}..{end}")
        return 1

    bands: dict[str, int] = {}
    transitions: list[str] = []
    degraded_days = 0
    for result in results:
        if result.band:
            bands[result.band] = bands.get(result.band, 0) + 1
        if result.degraded:
            degraded_days += 1
        if result.band_changed:
            transitions.append(
                f"{result.trade_date.isoformat()}: {result.prev_band} → {result.band}"
                f" (score {_fmt(result.score)}, ema {_fmt(result.score_ema)})"
            )

    print(
        f"hindcast {start}..{end}: {len(results)} days scored,"
        f" degraded={degraded_days}, written={'yes' if write else 'no'}"
    )
    print(f"band distribution: {bands}")
    print(f"band transitions ({len(transitions)}):")
    for line in transitions:
        print(f"  {line}")
    if results:
        last = results[-1]
        print(
            f"last day {last.trade_date}: score={_fmt(last.score)}"
            f" ema={_fmt(last.score_ema)} band={last.band} regime={last.regime}"
        )
    return 0


# ---------------------------------------------------------------------------
# CLI glue
# ---------------------------------------------------------------------------


def _cli(args: argparse.Namespace) -> int:
    from shared.storage.market_structure_store import create_market_structure_store

    config = MarketRiskConfig.load_or_default()
    store = create_market_structure_store()

    mode = "hindcast" if args.hindcast else args.mode
    if mode == "hindcast":
        if args.start is None or args.end is None:
            print("hindcast requires --start and --end", file=sys.stderr)
            return 2
        return run_hindcast(
            store=store,
            config=config,
            start=date.fromisoformat(args.start),
            end=date.fromisoformat(args.end),
            write=args.write,
        )

    import redis as redis_lib

    redis_client = redis_lib.Redis.from_url(redis_url_from_env(), decode_responses=True)
    try:
        return run_mode(mode, store=store, redis=redis_client, config=config)
    finally:
        redis_client.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(description="Market Risk Score engine")
    parser.add_argument(
        "mode",
        nargs="?",
        choices=[*_MODES, "hindcast"],
        help="one-shot mode (or use --hindcast)",
    )
    parser.add_argument(
        "--hindcast", action="store_true", help="recompute historical daily scores"
    )
    parser.add_argument("--start", help="hindcast start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="hindcast end date (YYYY-MM-DD)")
    parser.add_argument(
        "--write",
        action="store_true",
        help="hindcast: merge score columns into Parquet close rows",
    )
    args = parser.parse_args()
    if args.mode is None and not args.hindcast:
        parser.error("a mode is required (premarket|intraday|close|hindcast)")
    return _cli(args)


if __name__ == "__main__":
    sys.exit(main())
