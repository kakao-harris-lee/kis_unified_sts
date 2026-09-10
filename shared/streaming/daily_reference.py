"""Futures prev_close read-model — one REST value, published once per session.

Why this module exists
----------------------
The decoupled futures decision-engine has **no MarketDataProvider and no KIS
credentials** by design (F-9), so it derived ``prev_close`` from the parquet
daily bars.  Those bars only exist for the *training* symbols
(``101S6000`` / ``krx_kospi200f_continuous``, stale since 2026-06-25) — never
for the *trading* symbol (``A01609`` / ``A05609``).  Setup A was therefore
permanently blind: ``no_prev_close`` on every evaluation and one WARNING per
minute (830 lines on 2026-09-10).

The monolithic orchestrator already has the number: it REST-fetches
``FHMIF10000000.futs_prdy_clpr`` once per symbol at session start
(``services/trading/orchestrator.py::_prefetch_futures_daily_reference``).
This module publishes that same value as a small Redis hash so the
decision-engine reads the **identical** number the monolith uses, without
widening the credential surface into the decoupled daemons.

Redis layout (DB 1, per project convention)
-------------------------------------------
``futures:daily_reference:{symbol}``
    HASH ``{prev_close, source, asof_ts, producer}``.  ``asof_ts`` is KST
    ISO-8601 (``+09:00``) — the consumer accepts the value only while
    ``asof_ts`` falls on the current KST trade date, so a surviving key from a
    previous session can never be read as today's reference.

TTL is configuration, not a literal: ``config/futures_contract.yaml``
``daily_reference.ttl_seconds`` (86400 = this repo's default operational TTL,
CLAUDE.md).  Both publishers read it through :func:`load_daily_reference_ttl_seconds`,
so there is exactly one bound.

Fail-open polarity
------------------
Publishing is additive and best-effort: :func:`publish_futures_daily_reference`
swallows every Redis failure (WARNING + ``False``), matching the convention of
the sibling publishers in this package (``DataFreshnessTracker``,
``VolatilityReferencePublisher``).  A publish failure must never perturb the
trading path that produced the value.
"""

from __future__ import annotations

import inspect
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

#: Redis key template for the per-symbol daily reference hash.
FUTURES_DAILY_REFERENCE_KEY = "futures:daily_reference:{symbol}"

#: ``source`` value for a value read from the KIS REST current-price endpoint
#: (``FHMIF10000000`` → ``futs_prdy_clpr``).  A second source (e.g. a daily
#: bar) would carry its own tag so the consumer's INFO line stays diagnostic.
SOURCE_KIS_REST = "kis_rest"

_CONFIG_FILE = "futures_contract.yaml"
_CONFIG_SECTION = "daily_reference"
#: Fallback only — the configured value in ``config/futures_contract.yaml``
#: is the source of truth; this keeps a missing/unreadable config from
#: publishing a key with no TTL at all.
_DEFAULT_TTL_SECONDS = 86_400


def daily_reference_key(symbol: str) -> str:
    """Redis key holding ``symbol``'s daily reference hash."""
    return FUTURES_DAILY_REFERENCE_KEY.format(symbol=symbol)


def load_daily_reference_ttl_seconds() -> int:
    """TTL for the read-model, from ``config/futures_contract.yaml``.

    Read by BOTH publishers so the key can never be written with two different
    lifetimes.  Falls back to the repo default operational TTL (24 h) when the
    config file is absent or unreadable.
    """
    try:
        from shared.config.loader import ConfigLoader

        raw = ConfigLoader.load(_CONFIG_FILE)
        section = raw.get(_CONFIG_SECTION, {}) if isinstance(raw, dict) else {}
        ttl = int(section.get("ttl_seconds", _DEFAULT_TTL_SECONDS))
    except Exception:
        logger.warning(
            "%s::%s.ttl_seconds unreadable; using the %ds default operational TTL",
            _CONFIG_FILE,
            _CONFIG_SECTION,
            _DEFAULT_TTL_SECONDS,
        )
        return _DEFAULT_TTL_SECONDS
    if ttl <= 0:
        logger.warning(
            "%s::%s.ttl_seconds=%s is not positive; using %ds",
            _CONFIG_FILE,
            _CONFIG_SECTION,
            ttl,
            _DEFAULT_TTL_SECONDS,
        )
        return _DEFAULT_TTL_SECONDS
    return ttl


async def fetch_futures_prev_close(kis_client: Any, symbol: str) -> float:
    """REST-fetch ``symbol``'s previous-session close (0.0 when absent).

    The single place that knows *which* KIS call carries prev_close, shared by
    the orchestrator's session-start prefetch and the market-ingest daemon so
    the two producers can never drift onto different endpoints or fields.

    Raises whatever the KIS client raises — each caller decides its own
    "prefetch failed" policy (both log a WARNING and skip the symbol).
    """
    price = await kis_client._get_futures_price(symbol)
    return float((price or {}).get("prev_close", 0) or 0)


async def publish_futures_daily_reference(
    redis: Any,
    *,
    symbol: str,
    prev_close: float,
    source: str,
    producer: str,
    asof: datetime | None = None,
    ttl_seconds: int | None = None,
) -> bool:
    """Publish ``symbol``'s prev_close read-model. Never raises.

    Accepts a sync or an async Redis client: every command result that is
    awaitable is awaited, so the same helper serves the orchestrator's sync
    singleton and any daemon holding only ``redis.asyncio``.

    Args:
        redis: Redis client (sync or async).
        symbol: Trading symbol the value belongs to (e.g. ``A05609``).
        prev_close: Previous-session close; non-positive values are refused
            (a 0.0 reference is exactly the blind state this model fixes).
        source: Where the number came from — see :data:`SOURCE_KIS_REST`.
        producer: Publishing process, for operator triage of a stale key.
        asof: Observation time; defaults to now (KST).
        ttl_seconds: Override the configured TTL (tests); ``None`` reads
            :func:`load_daily_reference_ttl_seconds`.

    Returns:
        ``True`` when the hash was written, ``False`` on refusal or failure.
    """
    if prev_close <= 0:
        logger.warning(
            "daily_reference publish refused for %s: prev_close=%s is not positive",
            symbol,
            prev_close,
        )
        return False
    moment = asof or datetime.now(KST)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=KST)
    ttl = ttl_seconds if ttl_seconds is not None else load_daily_reference_ttl_seconds()
    key = daily_reference_key(symbol)
    payload = {
        "prev_close": str(float(prev_close)),
        "source": source,
        "asof_ts": moment.astimezone(KST).isoformat(),
        "producer": producer,
    }
    try:
        result = redis.hset(key, mapping=payload)
        if inspect.isawaitable(result):
            await result
        result = redis.expire(key, ttl)
        if inspect.isawaitable(result):
            await result
    except Exception as e:
        logger.warning("daily_reference publish failed for %s: %s", symbol, e)
        return False
    logger.info(
        "daily_reference published: %s prev_close=%s source=%s asof=%s ttl=%ds",
        symbol,
        payload["prev_close"],
        source,
        payload["asof_ts"],
        ttl,
    )
    return True


def read_futures_daily_reference(redis: Any, symbol: str) -> dict[str, Any] | None:
    """Read ``symbol``'s daily reference hash (sync client). Never raises.

    Returns:
        ``{"prev_close": float, "source": str, "asof_ts": str, "producer": str}``
        or ``None`` when the key is absent, unreadable, or carries no usable
        ``prev_close``.  Freshness (``asof_ts`` on the current KST trade date)
        is the caller's judgement — see
        ``services/decision_engine/daily_reference.py``.
    """
    try:
        raw = redis.hgetall(daily_reference_key(symbol))
    except Exception as e:
        logger.debug("daily_reference read failed for %s: %s", symbol, e)
        return None
    if not raw:
        return None
    fields = {_as_text(k): _as_text(v) for k, v in raw.items()}
    try:
        prev_close = float(fields.get("prev_close", "") or 0)
    except (TypeError, ValueError):
        logger.debug(
            "daily_reference for %s has an unparseable prev_close=%r",
            symbol,
            fields.get("prev_close"),
        )
        return None
    if prev_close <= 0:
        return None
    return {
        "prev_close": prev_close,
        "source": fields.get("source", ""),
        "asof_ts": fields.get("asof_ts", ""),
        "producer": fields.get("producer", ""),
    }


def _as_text(value: Any) -> str:
    """Decode a Redis field/value that may arrive as bytes."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
