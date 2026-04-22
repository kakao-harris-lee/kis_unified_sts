"""Macro overnight batch collector — run via cron."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

from services.monitoring.metrics import record_macro_collected

logger = logging.getLogger(__name__)


async def _publish_snapshot(redis: Any, stream: str, maxlen: int, snap) -> None:
    payload = {
        "ts_ms": snap.ts_ms,
        "session": snap.session,
        "sp500_close": snap.sp500_close,
        "sp500_change_pct": snap.sp500_change_pct,
        "nasdaq_close": snap.nasdaq_close,
        "nasdaq_change_pct": snap.nasdaq_change_pct,
        "eurex_kospi_close": snap.eurex_kospi_close,
        "eurex_kospi_change_pct": snap.eurex_kospi_change_pct,
        "usdkrw": snap.usdkrw,
        "usdkrw_change_pct": snap.usdkrw_change_pct,
        "dxy": snap.dxy,
        "us10y_yield": snap.us10y_yield,
        "vix": snap.vix,
        "collected_from_json": json.dumps(snap.collected_from),
    }
    fields = {k: ("" if v is None else str(v)) for k, v in payload.items()}
    await redis.xadd(stream, fields, maxlen=maxlen, approximate=True)


_CH_INSERT = (
    "INSERT INTO kospi.macro_overnight "
    "(ts, session, sp500_close, sp500_change_pct, nasdaq_close, nasdaq_change_pct, "
    "eurex_kospi_close, eurex_kospi_change_pct, usdkrw, usdkrw_change_pct, dxy, "
    "us10y_yield, vix, collected_from) VALUES"
)


async def _write_ch(ch_client: Any, snap) -> None:
    row = (
        datetime.fromtimestamp(snap.ts_ms / 1000, tz=UTC).replace(tzinfo=None),
        snap.session,
        snap.sp500_close or 0.0,
        snap.sp500_change_pct or 0.0,
        snap.nasdaq_close or 0.0,
        snap.nasdaq_change_pct or 0.0,
        snap.eurex_kospi_close,
        snap.eurex_kospi_change_pct,
        snap.usdkrw or 0.0,
        snap.usdkrw_change_pct or 0.0,
        snap.dxy,
        snap.us10y_yield,
        snap.vix,
        snap.collected_from,
    )
    await ch_client.execute(_CH_INSERT, [row])


async def collect_us_session(
    *,
    redis: Any,
    ch_client: Any,
    yahoo_source: Any,
    stream: str,
    maxlen: int,
) -> int:
    snap = await yahoo_source.fetch_us_close_snapshot()
    await _publish_snapshot(redis, stream, maxlen, snap)
    await _write_ch(ch_client, snap)
    record_macro_collected(snap.session)
    return 0


async def collect_fx_session(
    *,
    redis: Any,
    ch_client: Any,
    ecos_source: Any,
    stream: str,
    maxlen: int,
) -> int:
    snap = await ecos_source.fetch_fx_snapshot()
    await _publish_snapshot(redis, stream, maxlen, snap)
    await _write_ch(ch_client, snap)
    record_macro_collected(snap.session)
    return 0


async def _cli(session_kind: str) -> int:
    import aiohttp
    import redis.asyncio as aioredis

    from shared.db.client import AsyncClickHouseClient
    from shared.db.config import ClickHouseConfig
    from shared.macro.sources.ecos import ECOSSource
    from shared.macro.sources.yahoo import YahooMacroSource

    stream = "stream:macro.overnight"
    maxlen = 5000
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    r = aioredis.from_url(redis_url)
    ch = AsyncClickHouseClient(ClickHouseConfig.from_env(database="kospi"))
    await ch.connect()

    try:
        if session_kind == "us":
            rc = await collect_us_session(
                redis=r,
                ch_client=ch,
                yahoo_source=YahooMacroSource(),
                stream=stream,
                maxlen=maxlen,
            )
        elif session_kind == "fx":
            ecos_key = os.environ["ECOS_API_KEY"]
            async with aiohttp.ClientSession() as session:
                rc = await collect_fx_session(
                    redis=r,
                    ch_client=ch,
                    ecos_source=ECOSSource(api_key=ecos_key, session=session),
                    stream=stream,
                    maxlen=maxlen,
                )
        else:
            print(f"unknown session: {session_kind}", file=sys.stderr)
            rc = 2
    finally:
        await r.aclose()
        await ch.close()
    return rc


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    p = argparse.ArgumentParser()
    p.add_argument("session", choices=["us", "fx"])
    args = p.parse_args()
    return asyncio.run(_cli(args.session))


if __name__ == "__main__":
    sys.exit(main())
