"""KRX night-futures (KOSPI200) close capture — one-shot, run via scheduler.

Roadmap O9 (Wave 2e): the KRX night derivatives session (18:00 → next-day
06:00 KST) has no REST quote path, so this collector subscribes the realtime
WebSocket H0MFCNT0 (KRX야간선물 실시간종목체결, [실시간-064]) during the
configured capture window (default 05:50–06:00 KST) and publishes the LAST
trade before the 06:00 close to Redis DB 1 as
``market:structure:night_close`` (hash, TTL 24h) for the pre-open Market Risk
Score. Zero trades inside the window → key is NOT published (warning only).

Pure market-data collection — no order path is touched. One-shot CLI in the
services/macro_overnight_collector mold; scheduled at 05:48 KST in
deploy/scheduler.crontab so connect/subscribe are warm before the window.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Any

from services.night_futures_collector.config import NightCloseCaptureConfig
from shared.config.runtime_defaults import redis_url_from_env
from shared.kis.auth import KISAuthConfig
from shared.kis.websocket import KISWebSocketAdapter, NightFuturesTrade
from shared.strategy.market_time import KST

logger = logging.getLogger(__name__)

# Exit code for configuration/environment problems (missing creds, started
# after the window already closed) — distinct from runtime failures (1).
EXIT_CONFIG_ERROR = 64


class NightCloseCapture:
    """Tracks the last trade received inside the capture window.

    Frames arrive in wire order, so "last received inside the window" is the
    night close candidate; every later in-window trade overwrites it.
    """

    def __init__(self, window_start: datetime, window_end: datetime) -> None:
        self.window_start = window_start
        self.window_end = window_end
        self.last_trade: NightFuturesTrade | None = None
        self.trades_seen = 0

    def on_trade(self, trade: NightFuturesTrade) -> None:
        received = datetime.fromtimestamp(trade.timestamp, tz=KST)
        if not (self.window_start <= received < self.window_end):
            return
        self.trades_seen += 1
        self.last_trade = trade


def _resolve_asof_ts(trade: NightFuturesTrade, capture_date: datetime) -> str:
    """KST ISO timestamp of the captured trade.

    Prefers the exchange trade clock (bsop_hour, HHMMSS KST) composed onto the
    capture date; falls back to the local receive time.
    """
    if trade.trade_time is not None:
        try:
            return datetime(
                capture_date.year,
                capture_date.month,
                capture_date.day,
                int(trade.trade_time[0:2]),
                int(trade.trade_time[2:4]),
                int(trade.trade_time[4:6]),
                tzinfo=KST,
            ).isoformat()
        except ValueError:
            pass
    return datetime.fromtimestamp(trade.timestamp, tz=KST).isoformat()


def build_snapshot_fields(
    trade: NightFuturesTrade,
    config: NightCloseCaptureConfig,
    capture_date: datetime,
) -> dict[str, str]:
    """Redis hash payload for the night-close snapshot.

    ``close`` is always present (the parser drops price-less records);
    optional confirmed fields degrade to "" when absent in the frame.
    """

    def _s(value: float | None) -> str:
        return "" if value is None else str(value)

    return {
        "close": str(trade.price),
        "mrkt_basis": _s(trade.market_basis),
        "dprt": _s(trade.disparity_rate),
        "open_interest": _s(trade.open_interest),
        "acml_vol": _s(trade.cumulative_volume),
        "asof_ts": _resolve_asof_ts(trade, capture_date),
        "product_code": trade.symbol or config.product_code,
    }


def publish_night_close(
    redis_client: Any, config: NightCloseCaptureConfig, fields: dict[str, str]
) -> None:
    """HSET the snapshot hash and apply the configured TTL (Redis DB 1)."""
    redis_client.hset(config.redis_key, mapping=fields)
    redis_client.expire(config.redis_key, config.redis_ttl_seconds)


def run_capture(
    config: NightCloseCaptureConfig,
    *,
    adapter: Any,
    redis_client: Any,
    now: datetime | None = None,
) -> int:
    """Subscribe during the capture window, then publish the last trade.

    Args:
        config: Capture window + publication settings.
        adapter: KISWebSocketAdapter-compatible object (injectable for tests).
        redis_client: Sync Redis client bound to DB 1.
        now: Aware KST "now" override (tests); defaults to datetime.now(KST).

    Returns:
        0 on success (including the zero-trade/no-publish case),
        EXIT_CONFIG_ERROR when started after the window already closed,
        1 on WS connect/subscribe failure.
    """
    now = now if now is not None else datetime.now(KST)
    window_start, window_end = config.window_bounds(now)
    if now >= window_end:
        logger.error(
            "night close capture started after window end (%s >= %s KST) — "
            "check the 05:48 scheduler entry",
            now.isoformat(),
            window_end.isoformat(),
        )
        return EXIT_CONFIG_ERROR

    capture = NightCloseCapture(window_start, window_end)
    try:
        adapter.connect()
        adapter.subscribe_night_trades(
            [config.tr_key], capture.on_trade, until=window_end.timestamp()
        )
    except Exception:
        logger.exception("night futures WS capture failed (tr_key=%s)", config.tr_key)
        return 1
    finally:
        try:
            adapter.disconnect()
        except Exception:  # noqa: BLE001 — teardown must not mask the capture result
            logger.warning("night futures WS disconnect failed", exc_info=True)

    if capture.last_trade is None:
        logger.warning(
            "no night futures trades in capture window %s–%s KST (tr_key=%s); "
            "NOT publishing %s (holiday or halted session?)",
            config.window_start_kst,
            config.window_end_kst,
            config.tr_key,
            config.redis_key,
        )
        return 0

    fields = build_snapshot_fields(capture.last_trade, config, window_end)
    publish_night_close(redis_client, config, fields)
    logger.info(
        "published %s: close=%s basis=%s dprt=%s oi=%s vol=%s asof=%s "
        "(trades_in_window=%d)",
        config.redis_key,
        fields["close"],
        fields["mrkt_basis"],
        fields["dprt"],
        fields["open_interest"],
        fields["acml_vol"],
        fields["asof_ts"],
        capture.trades_seen,
    )
    return 0


def _build_adapter() -> KISWebSocketAdapter | None:
    """Build the WS adapter from env creds; None when creds are missing.

    The night feed exists on the REAL WS endpoint only (KIS 모의투자 serves no
    futures realtime feed — same policy as the day futures feed), so is_real
    is always True. This is a market-data-only path; no orders are placed.
    """
    app_key = os.environ.get("KIS_FUTURES_APP_KEY", "")
    app_secret = os.environ.get("KIS_FUTURES_APP_SECRET", "")
    if not app_key or not app_secret:
        return None
    return KISWebSocketAdapter(
        KISAuthConfig(app_key=app_key, app_secret=app_secret, is_real=True)
    )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    config = NightCloseCaptureConfig.from_yaml()
    if not config.enabled:
        logger.info("night close capture disabled (config/night_futures.yaml)")
        return 0

    adapter = _build_adapter()
    if adapter is None:
        logger.error(
            "KIS_FUTURES_APP_KEY / KIS_FUTURES_APP_SECRET not set — cannot "
            "capture night futures close"
        )
        return EXIT_CONFIG_ERROR

    import redis as redis_lib

    redis_client = redis_lib.Redis.from_url(redis_url_from_env(), decode_responses=True)
    try:
        return run_capture(config, adapter=adapter, redis_client=redis_client)
    finally:
        redis_client.close()


if __name__ == "__main__":
    sys.exit(main())
