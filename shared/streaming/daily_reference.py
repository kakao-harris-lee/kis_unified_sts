"""Futures prev_close read-model — one REST value, republished once per trade day.

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
widening the credential surface into the decoupled daemons.  Both producers —
the orchestrator's session start and market-ingest's once-per-trade-day loop
(``services/market_ingest/main.py::_daily_reference_loop``) — go through
:func:`prefetch_and_publish_futures_daily_references`, so they cannot drift onto
different endpoints, guards, or payloads.

Redis layout (DB 1, per project convention)
-------------------------------------------
``futures:daily_reference:{symbol}``
    HASH ``{prev_close, source, asof_ts, producer}``.  ``asof_ts`` is KST
    ISO-8601 (``+09:00``) — the consumer accepts the value only while
    ``asof_ts`` falls on the current KST trade date, so a surviving key from a
    previous session can never be read as today's reference.

TTL is configuration, not a literal: ``config/futures_contract.yaml``
``daily_reference.ttl_seconds`` (86400 = this repo's default operational TTL,
CLAUDE.md), read through :func:`load_daily_reference_config`.  The TTL only
garbage-collects the key of a producer that stopped publishing; freshness is
the consumer's KST-date check on ``asof_ts``, not the TTL.

Fail-open polarity
------------------
Publishing is additive and best-effort: :func:`publish_futures_daily_reference`
swallows every Redis failure (WARNING + ``False``), matching the convention of
the sibling publishers in this package (``DataFreshnessTracker``,
``VolatilityReferencePublisher``).  A publish failure must never perturb the
trading path that produced the value.
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from shared.strategy.market_time import is_trading_day_kst, now_kst, to_kst

logger = logging.getLogger(__name__)

#: Redis key template for the per-symbol daily reference hash.
FUTURES_DAILY_REFERENCE_KEY = "futures:daily_reference:{symbol}"

#: ``source`` value for a value read from the KIS REST current-price endpoint
#: (``FHMIF10000000`` → ``futs_prdy_clpr``).  A second source (e.g. a daily
#: bar) would carry its own tag so the consumer's INFO line stays diagnostic.
SOURCE_KIS_REST = "kis_rest"

_CONFIG_FILE = "futures_contract.yaml"
_CONFIG_SECTION = "daily_reference"
# Fallbacks only — the values in ``config/futures_contract.yaml`` are the
# source of truth; these keep a missing/unreadable config from publishing a key
# with no TTL or polling KIS REST in a tight loop.
_DEFAULT_TTL_SECONDS = 86_400
_DEFAULT_POLL_SECONDS = 60.0
_DEFAULT_OPEN_OFFSET_MINUTES = 0
# Floor for ``poll_seconds``: a retry loop faster than this during a KIS outage
# would spend the REST rate budget (EGW00201) the tick fallback also needs.
_MIN_POLL_SECONDS = 60.0


@dataclass(frozen=True)
class DailyReferenceConfig:
    """Validated ``config/futures_contract.yaml::daily_reference`` section."""

    ttl_seconds: int = _DEFAULT_TTL_SECONDS
    poll_seconds: float = _DEFAULT_POLL_SECONDS
    open_offset_minutes: int = _DEFAULT_OPEN_OFFSET_MINUTES


@dataclass(frozen=True)
class DailyReferenceSchedule:
    """When market-ingest may (re)publish the day's reference.

    Attributes:
        poll_seconds: Interval between publish checks (and failure retries).
        publish_from: KST wall-clock time from which today's reference may be
            stamped — futures regular open minus ``open_offset_minutes``.
            Earlier, KIS may still report the close from two sessions back.
    """

    poll_seconds: float
    publish_from: time

    def is_due(self, now: datetime) -> bool:
        """True on a KRX trading day at or after :attr:`publish_from` (KST)."""
        kst_now = to_kst(now)
        return kst_now.time() >= self.publish_from and is_trading_day_kst(kst_now)


@dataclass(frozen=True)
class DailyReferencePrefetchResult:
    """Outcome of one prefetch → publish pass.

    Attributes:
        prev_closes: Every symbol whose REST value was usable, published or not
            (the orchestrator's in-process cache must not depend on Redis).
        published: The subset actually written to Redis.
    """

    prev_closes: dict[str, float]
    published: frozenset[str]

    def published_all(self, symbols: Iterable[str]) -> bool:
        """True when every one of ``symbols`` was written to Redis."""
        return set(symbols) <= self.published


def daily_reference_key(symbol: str) -> str:
    """Redis key holding ``symbol``'s daily reference hash."""
    return FUTURES_DAILY_REFERENCE_KEY.format(symbol=symbol)


def is_usable_prev_close(value: float) -> bool:
    """A prev_close worth publishing or trusting: finite and positive.

    ``nan``/``inf`` slip past a bare ``<= 0`` check and would surface in Setup A
    as a misleading ``retrace_out_of_band(nan)`` rejection instead of
    ``no_prev_close``.
    """
    return math.isfinite(value) and value > 0


def load_daily_reference_config() -> DailyReferenceConfig:
    """Read the ``daily_reference`` section; every gap falls back with a WARNING.

    A missing file, a missing section, a missing key, or an invalid value all
    log and use the fallback — none is silent, because a silently defaulted TTL
    is exactly how a key ends up with a lifetime nobody configured.
    """
    section = _load_config_section()
    return DailyReferenceConfig(
        ttl_seconds=int(
            _setting(section, "ttl_seconds", _DEFAULT_TTL_SECONDS, minimum=1)
        ),
        poll_seconds=float(
            _setting(
                section,
                "poll_seconds",
                _DEFAULT_POLL_SECONDS,
                minimum=_MIN_POLL_SECONDS,
            )
        ),
        open_offset_minutes=int(
            _setting(
                section,
                "open_offset_minutes",
                _DEFAULT_OPEN_OFFSET_MINUTES,
                minimum=0,
            )
        ),
    )


def load_daily_reference_schedule(
    config: DailyReferenceConfig | None = None,
) -> DailyReferenceSchedule:
    """Build the publish schedule from YAML.

    ``publish_from`` = ``config/market_schedule.yaml::futures.regular.open``
    minus ``daily_reference.open_offset_minutes`` (clamped at midnight).
    """
    from shared.decision.context import _load_futures_open_from_config

    cfg = config or load_daily_reference_config()
    hour, minute = _load_futures_open_from_config()
    minutes = max(0, hour * 60 + minute - cfg.open_offset_minutes)
    return DailyReferenceSchedule(
        poll_seconds=cfg.poll_seconds,
        publish_from=time(minutes // 60, minutes % 60),
    )


async def fetch_futures_prev_close(kis_client: Any, symbol: str) -> float:
    """REST-fetch ``symbol``'s previous-session close (0.0 when absent).

    The single place that knows *which* KIS call carries prev_close.

    Raises whatever the KIS client raises —
    :func:`prefetch_and_publish_futures_daily_references` turns that into a
    per-symbol WARNING.
    """
    price = await kis_client._get_futures_price(symbol)
    return float((price or {}).get("prev_close", 0) or 0)


def publish_futures_daily_reference(
    redis: Any,
    *,
    symbol: str,
    prev_close: float,
    source: str,
    producer: str,
    asof: datetime | None = None,
    ttl_seconds: int | None = None,
) -> bool:
    """Publish ``symbol``'s prev_close read-model atomically. Never raises.

    ``DEL`` + ``HSET`` + ``EXPIRE`` go through one ``MULTI/EXEC`` pipeline, so
    the hash can never exist without its TTL (separate calls left a TTL ``-1``
    key when the connection dropped between them) and no field from an earlier
    writer survives.  Sync client only; async callers run it in a worker thread
    (see :func:`prefetch_and_publish_futures_daily_references`).

    Args:
        redis: SYNC Redis client.
        symbol: Trading symbol the value belongs to (e.g. ``A05609``).
        prev_close: Previous-session close; non-finite or non-positive values
            are refused (a 0.0 reference is exactly the blind state this model
            fixes).
        source: Where the number came from — see :data:`SOURCE_KIS_REST`.
        producer: Publishing process, for operator triage of a stale key.
        asof: Observation time; defaults to now (KST). Naive means KST.
        ttl_seconds: Override the configured TTL; ``None`` reads
            :func:`load_daily_reference_config`.

    Returns:
        ``True`` when the hash was written, ``False`` on refusal or failure.
    """
    if not is_usable_prev_close(prev_close):
        logger.warning(
            "daily_reference publish refused for %s: prev_close=%s is not "
            "finite and positive",
            symbol,
            prev_close,
        )
        return False
    moment = to_kst(asof or now_kst())
    ttl = (
        ttl_seconds
        if ttl_seconds is not None
        else load_daily_reference_config().ttl_seconds
    )
    key = daily_reference_key(symbol)
    payload = {
        "prev_close": str(float(prev_close)),
        "source": source,
        "asof_ts": moment.isoformat(),
        "producer": producer,
    }
    try:
        pipe = redis.pipeline(transaction=True)
        pipe.delete(key)
        pipe.hset(key, mapping=payload)
        pipe.expire(key, ttl)
        pipe.execute()
    except Exception as e:
        logger.warning("daily_reference publish failed for %s: %s", symbol, e)
        return False
    logger.info(
        "daily_reference published: %s prev_close=%s source=%s producer=%s "
        "asof=%s ttl=%ds",
        symbol,
        payload["prev_close"],
        source,
        producer,
        payload["asof_ts"],
        ttl,
    )
    return True


async def prefetch_and_publish_futures_daily_references(
    kis_client: Any,
    symbols: Sequence[str],
    *,
    producer: str,
    redis: Any | None = None,
    asof: datetime | None = None,
) -> DailyReferencePrefetchResult:
    """REST-fetch each symbol's prev_close, then publish the usable ones.

    The one fetch → guard → publish path shared by both futures producers.
    Per-symbol failures (KIS error, non-finite or non-positive value) log a
    WARNING and skip that symbol only.  Redis is resolved once per call and
    every Redis command runs in a worker thread, so a slow or down Redis never
    stalls the caller's event loop.

    Args:
        kis_client: KIS REST client with futures credentials.
        symbols: Trading symbols to fetch.
        producer: ``producer`` field of the hash (compose service name).
        redis: SYNC Redis client; ``None`` resolves the shared
            ``RedisClient`` singleton (DB 1) inside the worker thread.
        asof: Observation time stamped on every hash; defaults to now (KST).

    Returns:
        The usable values and which of them reached Redis.
    """
    prev_closes: dict[str, float] = {}
    for symbol in symbols:
        try:
            value = await fetch_futures_prev_close(kis_client, symbol)
        except Exception as e:
            logger.warning(
                "prev_close prefetch failed for %s: %s — Setup A will skip",
                symbol,
                e,
            )
            continue
        if not is_usable_prev_close(value):
            logger.warning(
                "prev_close prefetch returned %s for %s — Setup A will skip",
                value,
                symbol,
            )
            continue
        prev_closes[symbol] = value
    if not prev_closes:
        return DailyReferencePrefetchResult(prev_closes={}, published=frozenset())
    published = await asyncio.to_thread(
        _publish_all,
        redis,
        prev_closes,
        producer=producer,
        asof=to_kst(asof or now_kst()),
    )
    return DailyReferencePrefetchResult(prev_closes=prev_closes, published=published)


def _publish_all(
    redis: Any | None,
    prev_closes: dict[str, float],
    *,
    producer: str,
    asof: datetime,
) -> frozenset[str]:
    """Resolve Redis once and publish every value (worker thread)."""
    client = redis
    if client is None:
        try:
            from shared.streaming.client import RedisClient

            client = RedisClient.get_client()
        except Exception as e:
            logger.warning(
                "daily_reference publish failed for %s: Redis unavailable: %s",
                ", ".join(prev_closes),
                e,
            )
            return frozenset()
    ttl = load_daily_reference_config().ttl_seconds
    return frozenset(
        symbol
        for symbol, value in prev_closes.items()
        if publish_futures_daily_reference(
            client,
            symbol=symbol,
            prev_close=value,
            source=SOURCE_KIS_REST,
            producer=producer,
            asof=asof,
            ttl_seconds=ttl,
        )
    )


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
    if not is_usable_prev_close(prev_close):
        return None
    return {
        "prev_close": prev_close,
        "source": fields.get("source", ""),
        "asof_ts": fields.get("asof_ts", ""),
        "producer": fields.get("producer", ""),
    }


def _load_config_section() -> dict[str, Any] | None:
    """The ``daily_reference`` mapping, or ``None`` (after a WARNING)."""
    try:
        from shared.config.loader import ConfigLoader

        raw = ConfigLoader.load(_CONFIG_FILE)
    except Exception as e:
        logger.warning(
            "%s unreadable (%s); daily_reference uses its fallback settings",
            _CONFIG_FILE,
            e,
        )
        return None
    section = raw.get(_CONFIG_SECTION) if isinstance(raw, dict) else None
    if not isinstance(section, dict):
        logger.warning(
            "%s has no %s section; daily_reference uses its fallback settings "
            "(ttl_seconds=%d)",
            _CONFIG_FILE,
            _CONFIG_SECTION,
            _DEFAULT_TTL_SECONDS,
        )
        return None
    return section


def _setting(
    section: dict[str, Any] | None,
    name: str,
    default: float,
    *,
    minimum: float,
) -> float:
    """One numeric setting, or ``default`` with a WARNING when missing/invalid.

    ``section is None`` was already reported by :func:`_load_config_section`.
    """
    if section is None:
        return default
    raw = section.get(name)
    if raw is None:
        logger.warning(
            "%s::%s.%s is missing; using %s",
            _CONFIG_FILE,
            _CONFIG_SECTION,
            name,
            default,
        )
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = math.nan
    if not math.isfinite(value) or value < minimum:
        logger.warning(
            "%s::%s.%s=%r is invalid (must be >= %s); using %s",
            _CONFIG_FILE,
            _CONFIG_SECTION,
            name,
            raw,
            minimum,
            default,
        )
        return default
    return value


def _as_text(value: Any) -> str:
    """Decode a Redis field/value that may arrive as bytes."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
