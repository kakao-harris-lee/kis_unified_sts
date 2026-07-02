"""Macro overnight batch collector — run via cron."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

from services.monitoring.metrics import record_macro_collected
from shared.config.runtime_defaults import redis_url_from_env
from shared.macro.base import MACRO_FLOAT_FIELDS

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400  # Project Redis TTL policy (memory: stream keys 24h)


async def _publish_snapshot(redis: Any, stream: str, maxlen: int, snap) -> None:
    # MACRO_FLOAT_FIELDS is the shared writer/reader schema — keeps this
    # payload in lockstep with read_latest_macro_snapshot (additive-only).
    payload: dict[str, Any] = {"ts_ms": snap.ts_ms, "session": snap.session}
    for f in MACRO_FLOAT_FIELDS:
        payload[f] = getattr(snap, f)
    payload["collected_from_json"] = json.dumps(snap.collected_from)
    fields = {k: ("" if v is None else str(v)) for k, v in payload.items()}
    await redis.xadd(stream, fields, maxlen=maxlen, approximate=True)
    await redis.expire(stream, _STREAM_TTL_SECONDS)


async def collect_us_session(
    *,
    redis: Any,
    archive_client: Any,
    yahoo_source: Any,
    stream: str,
    maxlen: int,
) -> int:
    _ = archive_client
    snap = await yahoo_source.fetch_us_close_snapshot()
    await _publish_snapshot(redis, stream, maxlen, snap)
    record_macro_collected(snap.session)
    return 0


async def collect_premarket_session(
    *,
    redis: Any,
    archive_client: Any,
    yahoo_source: Any,
    stream: str,
    maxlen: int,
) -> int:
    _ = archive_client
    snap = await yahoo_source.fetch_premarket_snapshot()
    await _publish_snapshot(redis, stream, maxlen, snap)
    record_macro_collected(snap.session)
    return 0


async def collect_fx_session(
    *,
    redis: Any,
    archive_client: Any,
    ecos_source: Any,
    stream: str,
    maxlen: int,
) -> int:
    _ = archive_client
    snap = await ecos_source.fetch_fx_snapshot()
    await _publish_snapshot(redis, stream, maxlen, snap)
    record_macro_collected(snap.session)
    return 0


async def _cli(session_kind: str) -> int:
    import os

    import aiohttp
    import redis.asyncio as aioredis

    from shared.macro.config import MacroCollectorConfig
    from shared.macro.sources.ecos import ECOSSource
    from shared.macro.sources.yahoo import YahooMacroSource

    cfg = MacroCollectorConfig.from_yaml()
    stream = cfg.redis_stream
    maxlen = cfg.redis_maxlen
    redis_url = redis_url_from_env()
    r = aioredis.from_url(redis_url)

    try:
        if session_kind == "us":
            rc = await collect_us_session(
                redis=r,
                archive_client=None,
                yahoo_source=YahooMacroSource(ticker_map=cfg.yahoo_symbols),
                stream=stream,
                maxlen=maxlen,
            )
        elif session_kind == "premarket":
            rc = await collect_premarket_session(
                redis=r,
                archive_client=None,
                yahoo_source=YahooMacroSource(ticker_map=cfg.yahoo_symbols),
                stream=stream,
                maxlen=maxlen,
            )
        elif session_kind == "fx":
            ecos_key = os.environ["ECOS_API_KEY"]
            async with aiohttp.ClientSession() as session:
                rc = await collect_fx_session(
                    redis=r,
                    archive_client=None,
                    ecos_source=ECOSSource(api_key=ecos_key, session=session),
                    stream=stream,
                    maxlen=maxlen,
                )
        else:
            print(f"unknown session: {session_kind}", file=sys.stderr)
            rc = 2
    finally:
        await r.aclose()
    return rc


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    p = argparse.ArgumentParser()
    p.add_argument("session", choices=["us", "fx", "premarket"])
    args = p.parse_args()
    return asyncio.run(_cli(args.session))


if __name__ == "__main__":
    sys.exit(main())
