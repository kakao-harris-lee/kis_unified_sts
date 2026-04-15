"""Trading State Bus — Redis-backed shared state between orchestrator and dashboard.

The orchestrator (CLI process) publishes trading state to Redis.
The dashboard (Docker container) reads it back for display.

Redis Keys (all in DB1):
    trading:{asset}:status          — HASH   (orchestrator status snapshot)
    trading:{asset}:positions       — HASH   (field=position_id, value=JSON)
    trading:{asset}:trades          — LIST   (most recent first, max 500)
    trading:{asset}:signals         — LIST   (most recent first, max 200)
    trading:{asset}:market_context  — STRING (LLM market analysis JSON)
"""

from __future__ import annotations

import json
import logging
import os
import time as _time
from datetime import date, datetime, timezone
from typing import Any

import redis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------

_KEY_STATUS = "trading:{asset}:status"
_KEY_POSITIONS = "trading:{asset}:positions"
_KEY_TRADES = "trading:{asset}:trades"
_KEY_SIGNALS = "trading:{asset}:signals"
_KEY_CANDLE_CACHE = "trading:{asset}:candle_cache"
_KEY_MARKET_CONTEXT = "trading:{asset}:market_context"
_KEY_RUNNING_TOTALS = "trading:{asset}:running_totals"
_KEY_EQUITY_TIMELINE = "trading:{asset}:equity_timeline"

MAX_TRADES = 500
MAX_SIGNALS = 200
STATUS_TTL_SECONDS = 86400  # 24h — auto-expire if orchestrator dies
RUNNING_TOTALS_TTL_SECONDS = 60 * 60 * 24 * 30   # 30 days
EQUITY_TIMELINE_TTL_SECONDS = 60 * 60 * 24 * 400  # ~13 months


def _key(template: str, asset: str) -> str:
    base = template.format(asset=asset)
    suffix = os.getenv("TRADING_STATE_KEY_SUFFIX", "").strip()
    if not suffix:
        return base
    safe_suffix = "".join(ch for ch in suffix if ch.isalnum() or ch in ("_", "-", ":"))
    return f"{base}:{safe_suffix}" if safe_suffix else base


def _get_redis() -> redis.Redis:
    """Get the shared Redis client singleton."""
    from shared.streaming.client import RedisClient
    return RedisClient.get_client()


def _tz_aware_iso(dt: datetime | None) -> str:
    """Return a tz-aware ISO-8601 string for *dt*.

    If *dt* is None, falls back to the current UTC time.
    If *dt* is naive (no tzinfo), assumes UTC and attaches it.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Publisher (used by orchestrator)
# ---------------------------------------------------------------------------

class TradingStatePublisher:
    """Publishes trading state to Redis.

    All methods are fire-and-forget: they log errors but never raise,
    so the orchestrator is not disrupted by Redis failures.
    """

    def __init__(self, asset_class: str) -> None:
        self._asset = asset_class
        self._last_position_publish = 0.0
        self._last_status_publish = 0.0

    # -- Status ---------------------------------------------------------------

    def publish_status(self, status: dict[str, Any]) -> None:
        """Publish orchestrator status snapshot as a HASH."""
        try:
            r = _get_redis()
            key = _key(_KEY_STATUS, self._asset)
            flat: dict[str, str] = {}
            for k, v in status.items():
                flat[k] = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
            pipe = r.pipeline(transaction=False)
            pipe.delete(key)
            if flat:
                pipe.hset(key, mapping=flat)
            pipe.expire(key, STATUS_TTL_SECONDS)
            pipe.execute()
        except Exception:
            logger.debug("Failed to publish status to Redis", exc_info=True)

    # -- Positions ------------------------------------------------------------

    def publish_position_opened(self, position: Any) -> None:
        """Add a newly opened position to the positions hash."""
        try:
            r = _get_redis()
            key = _key(_KEY_POSITIONS, self._asset)
            data = self._serialize_position(position)
            pipe = r.pipeline(transaction=False)
            pipe.hset(key, position.id, json.dumps(data))
            pipe.expire(key, STATUS_TTL_SECONDS)
            pipe.execute()
        except Exception:
            logger.debug("Failed to publish position open", exc_info=True)

    def publish_position_closed(self, position: Any) -> None:
        """Remove from positions hash and push to trades list."""
        try:
            r = _get_redis()
            pos_key = _key(_KEY_POSITIONS, self._asset)
            trades_key = _key(_KEY_TRADES, self._asset)
            data = self._serialize_closed_position(position)
            pipe = r.pipeline(transaction=False)
            pipe.hdel(pos_key, position.id)
            pipe.expire(pos_key, STATUS_TTL_SECONDS)
            pipe.lpush(trades_key, json.dumps(data))
            pipe.ltrim(trades_key, 0, MAX_TRADES - 1)
            pipe.expire(trades_key, STATUS_TTL_SECONDS)
            pipe.execute()
        except Exception:
            logger.debug("Failed to publish position close", exc_info=True)

    def publish_positions_update(self, positions: list[Any], throttle: float = 2.0) -> None:
        """Publish a full open-position snapshot (throttled).

        Replaces the entire positions hash to prevent stale position IDs
        from lingering across restarts or profile runs.
        """
        now = _time.monotonic()
        if now - self._last_position_publish < throttle:
            return
        self._last_position_publish = now
        try:
            r = _get_redis()
            key = _key(_KEY_POSITIONS, self._asset)
            pipe = r.pipeline(transaction=False)
            pipe.delete(key)
            mapping: dict[str, str] = {}
            for pos in positions:
                data = self._serialize_position(pos)
                mapping[str(pos.id)] = json.dumps(data)
            if mapping:
                pipe.hset(key, mapping=mapping)
            pipe.expire(key, STATUS_TTL_SECONDS)
            pipe.execute()
        except Exception:
            logger.debug("Failed to publish positions update", exc_info=True)

    # -- Signals --------------------------------------------------------------

    def publish_signal(
        self,
        signal: Any,
        signal_type: str,
        executed: bool,
    ) -> None:
        """Push a signal event to the signals list."""
        try:
            r = _get_redis()
            key = _key(_KEY_SIGNALS, self._asset)
            data = {
                "id": getattr(signal, "id", "") or "",
                "symbol": getattr(signal, "code", ""),
                "name": getattr(signal, "name", "") or "",
                "side": signal_type,
                "signal_type": signal_type,
                "strategy": getattr(signal, "strategy", ""),
                "price": float(getattr(signal, "price", 0) or getattr(signal, "exit_price", 0) or 0),
                "confidence": float(getattr(signal, "confidence", 0) or 0),
                "timestamp": _tz_aware_iso(getattr(signal, "timestamp", None)),
                "executed": executed,
                "reason": (
                    getattr(signal, "reason", "").value
                    if hasattr(getattr(signal, "reason", ""), "value")
                    else str(getattr(signal, "reason", ""))
                ),
                "stage": getattr(signal, "stage", ""),
            }
            pipe = r.pipeline(transaction=False)
            pipe.lpush(key, json.dumps(data))
            pipe.ltrim(key, 0, MAX_SIGNALS - 1)
            pipe.expire(key, STATUS_TTL_SECONDS)
            pipe.execute()
        except Exception:
            logger.debug("Failed to publish signal", exc_info=True)

    # -- Market Context -------------------------------------------------------

    def publish_market_context(self, context: Any) -> None:
        """Publish LLM market analysis context as a JSON string.

        Args:
            context: MarketContext instance from shared.llm.market_context
        """
        try:
            r = _get_redis()
            key = _key(_KEY_MARKET_CONTEXT, self._asset)
            # Use to_dict() method if available, otherwise assume it's already a dict
            data = context.to_dict() if hasattr(context, "to_dict") else context
            pipe = r.pipeline(transaction=False)
            pipe.set(key, json.dumps(data))
            pipe.expire(key, STATUS_TTL_SECONDS)
            pipe.execute()
        except Exception:
            logger.debug("Failed to publish market context", exc_info=True)

    # -- Raw dict methods (for non-orchestrator publishers like RL paper trader) -

    def publish_raw_position(self, position_id: str, data: dict) -> None:
        """Add/update a position from a plain dict."""
        try:
            r = _get_redis()
            key = _key(_KEY_POSITIONS, self._asset)
            pipe = r.pipeline(transaction=False)
            pipe.hset(key, position_id, json.dumps(data))
            pipe.expire(key, STATUS_TTL_SECONDS)
            pipe.execute()
        except Exception:
            logger.debug("Failed to publish raw position", exc_info=True)

    def remove_position(self, position_id: str) -> None:
        """Remove a single position by ID."""
        try:
            r = _get_redis()
            key = _key(_KEY_POSITIONS, self._asset)
            r.hdel(key, position_id)
        except Exception:
            logger.debug("Failed to remove position", exc_info=True)

    def publish_raw_trade(self, data: dict) -> None:
        """Push a trade record from a plain dict."""
        try:
            r = _get_redis()
            key = _key(_KEY_TRADES, self._asset)
            pipe = r.pipeline(transaction=False)
            pipe.lpush(key, json.dumps(data))
            pipe.ltrim(key, 0, MAX_TRADES - 1)
            pipe.expire(key, STATUS_TTL_SECONDS)
            pipe.execute()
        except Exception:
            logger.debug("Failed to publish raw trade", exc_info=True)

    def publish_raw_signal(self, data: dict) -> None:
        """Push a signal record from a plain dict."""
        try:
            r = _get_redis()
            key = _key(_KEY_SIGNALS, self._asset)
            pipe = r.pipeline(transaction=False)
            pipe.lpush(key, json.dumps(data))
            pipe.ltrim(key, 0, MAX_SIGNALS - 1)
            pipe.expire(key, STATUS_TTL_SECONDS)
            pipe.execute()
        except Exception:
            logger.debug("Failed to publish raw signal", exc_info=True)

    # -- Cleanup --------------------------------------------------------------

    def clear_all(self) -> None:
        """Remove all keys for this asset class."""
        try:
            r = _get_redis()
            pipe = r.pipeline(transaction=False)
            for tmpl in (_KEY_STATUS, _KEY_POSITIONS, _KEY_TRADES, _KEY_SIGNALS, _KEY_MARKET_CONTEXT):
                pipe.delete(_key(tmpl, self._asset))
            pipe.execute()
        except Exception:
            logger.debug("Failed to clear trading state", exc_info=True)

    def publish_candle_cache(self, candle_data: dict[str, list[dict]]) -> None:
        """Persist indicator candles to Redis for fast restart recovery.

        Args:
            candle_data: {symbol: [{open, high, low, close, volume, minute}, ...]}
        """
        try:
            r = _get_redis()
            key = _key(_KEY_CANDLE_CACHE, self._asset)
            pipe = r.pipeline(transaction=False)
            pipe.delete(key)
            mapping = {sym: json.dumps(candles) for sym, candles in candle_data.items()}
            if mapping:
                pipe.hset(key, mapping=mapping)
                pipe.expire(key, STATUS_TTL_SECONDS)  # 24h TTL
            pipe.execute()
        except Exception:
            logger.debug("Failed to publish candle cache", exc_info=True)

    # -- Serialization helpers ------------------------------------------------

    @staticmethod
    def _serialize_position(pos: Any) -> dict:
        return {
            "id": pos.id,
            "code": pos.code,
            "name": getattr(pos, "name", ""),
            "side": pos.side.value if hasattr(pos.side, "value") else str(pos.side),
            "quantity": pos.quantity,
            "entry_price": pos.entry_price,
            "current_price": pos.current_price,
            "unrealized_pnl": getattr(pos, "unrealized_pnl", 0.0),
            "pnl_pct": getattr(pos, "profit_pct", 0.0),
            "entry_time": _tz_aware_iso(pos.entry_time) if isinstance(pos.entry_time, datetime) else str(pos.entry_time),
            "strategy": getattr(pos, "strategy", ""),
            "state": pos.state.value if hasattr(pos.state, "value") else str(pos.state),
            "highest_price": getattr(pos, "highest_price", pos.entry_price),
            "lowest_price": getattr(pos, "lowest_price", pos.entry_price),
            "fee_rate": getattr(pos, "fee_rate", 0.0),
            "stop_price": getattr(pos, "stop_price", None),
        }

    @staticmethod
    def _serialize_closed_position(pos: Any) -> dict:
        return {
            "id": pos.id,
            "symbol": pos.code,
            "name": getattr(pos, "name", ""),
            "side": pos.side.value if hasattr(pos.side, "value") else str(pos.side),
            "quantity": pos.quantity,
            "entry_price": pos.entry_price,
            "exit_price": getattr(pos, "exit_price", None) or pos.current_price,
            "pnl": getattr(pos, "unrealized_pnl", 0.0),
            "pnl_pct": getattr(pos, "profit_pct", 0.0),
            "strategy": getattr(pos, "strategy", ""),
            "entry_time": _tz_aware_iso(pos.entry_time) if isinstance(pos.entry_time, datetime) else str(pos.entry_time),
            "exit_time": _tz_aware_iso(getattr(pos, "exit_time", None)),
            "exit_reason": getattr(pos, "exit_reason", None) or "",
        }

    # -- Cross-session cumulative counters ------------------------------------

    def increment_running_totals(
        self, *, pnl: float, trades: int = 1, win: bool = False
    ) -> None:
        """Increment session-independent cumulative counters in Redis.

        Uses HINCRBYFLOAT / HINCRBY so concurrent updates are atomic.
        The key persists for 30 days; each update resets the TTL.
        """
        try:
            r = _get_redis()
            key = _key(_KEY_RUNNING_TOTALS, self._asset)
            pipe = r.pipeline(transaction=False)
            pipe.hincrbyfloat(key, "total_pnl", pnl)
            pipe.hincrby(key, "total_trades", trades)
            if win:
                pipe.hincrby(key, "total_wins", 1)
            pipe.expire(key, RUNNING_TOTALS_TTL_SECONDS)
            pipe.execute()
        except Exception:
            logger.debug("Failed to increment running totals in Redis", exc_info=True)

    def publish_equity_snapshot(
        self,
        *,
        as_of: date,
        cash_balance: float,
        open_positions_value: float,
        closed_pnl: float,
    ) -> None:
        """Append one daily equity datapoint to a sorted set keyed by date.

        Score = UTC midnight timestamp of *as_of*, so ``ZRANGE`` returns
        entries in chronological order.  Writing the same date twice
        overwrites the previous entry (ZADD upsert semantics).
        """
        try:
            r = _get_redis()
            key = _key(_KEY_EQUITY_TIMELINE, self._asset)
            total_equity = cash_balance + open_positions_value + closed_pnl
            snapshot = {
                "date": as_of.isoformat(),
                "cash_balance": cash_balance,
                "open_positions_value": open_positions_value,
                "closed_pnl": closed_pnl,
                "total_equity": total_equity,
            }
            score = datetime.combine(as_of, datetime.min.time()).replace(
                tzinfo=timezone.utc
            ).timestamp()
            r.zadd(key, {json.dumps(snapshot): score})
            r.expire(key, EQUITY_TIMELINE_TTL_SECONDS)
        except Exception:
            logger.debug("Failed to publish equity snapshot to Redis", exc_info=True)


# ---------------------------------------------------------------------------
# Reader (used by dashboard)
# ---------------------------------------------------------------------------

class TradingStateReader:
    """Reads trading state from Redis.

    All methods return safe defaults on Redis failure.
    """

    def __init__(self, asset_class: str) -> None:
        self._asset = asset_class

    def get_status(self) -> dict[str, Any]:
        """Read orchestrator status hash."""
        try:
            r = _get_redis()
            raw = r.hgetall(_key(_KEY_STATUS, self._asset))
            if not raw:
                return {}
            result: dict[str, Any] = {}
            for k, v in raw.items():
                try:
                    result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    result[k] = v
            return result
        except Exception:
            logger.debug("Failed to read status from Redis", exc_info=True)
            return {}

    def get_positions(self) -> list[dict[str, Any]]:
        """Read all open positions."""
        try:
            r = _get_redis()
            raw = r.hgetall(_key(_KEY_POSITIONS, self._asset))
            if not raw:
                return []
            positions = []
            for _pid, v in raw.items():
                try:
                    positions.append(json.loads(v))
                except (json.JSONDecodeError, TypeError):
                    pass
            return positions
        except Exception:
            logger.debug("Failed to read positions from Redis", exc_info=True)
            return []

    def get_trades(self, start: int = 0, count: int = 50) -> list[dict[str, Any]]:
        """Read recent trades (most recent first)."""
        try:
            r = _get_redis()
            raw_list = r.lrange(_key(_KEY_TRADES, self._asset), start, start + count - 1)
            trades = []
            for raw in raw_list:
                try:
                    trades.append(json.loads(raw))
                except (json.JSONDecodeError, TypeError):
                    pass
            return trades
        except Exception:
            logger.debug("Failed to read trades from Redis", exc_info=True)
            return []

    def get_trades_count(self) -> int:
        """Get total trades count."""
        try:
            r = _get_redis()
            return r.llen(_key(_KEY_TRADES, self._asset))
        except Exception:
            return 0

    def get_signals(self, start: int = 0, count: int = 50) -> list[dict[str, Any]]:
        """Read recent signals (most recent first)."""
        try:
            r = _get_redis()
            raw_list = r.lrange(_key(_KEY_SIGNALS, self._asset), start, start + count - 1)
            signals = []
            for raw in raw_list:
                try:
                    signals.append(json.loads(raw))
                except (json.JSONDecodeError, TypeError):
                    pass
            return signals
        except Exception:
            logger.debug("Failed to read signals from Redis", exc_info=True)
            return []

    def get_signals_count(self) -> int:
        """Get total signals count."""
        try:
            r = _get_redis()
            return r.llen(_key(_KEY_SIGNALS, self._asset))
        except Exception:
            return 0

    def remove_position(self, position_id: str) -> None:
        """Remove a single position from Redis positions HASH."""
        try:
            r = _get_redis()
            key = _key(_KEY_POSITIONS, self._asset)
            r.hdel(key, position_id)
        except Exception:
            logger.debug("Failed to remove position from Redis", exc_info=True)

    def get_candle_cache(self) -> dict[str, list[dict]]:
        """Load cached candles from Redis for indicator prewarm."""
        try:
            r = _get_redis()
            key = _key(_KEY_CANDLE_CACHE, self._asset)
            raw = r.hgetall(key)
            if not raw:
                return {}
            return {sym: json.loads(candles) for sym, candles in raw.items()}
        except Exception:
            logger.debug("Failed to read candle cache from Redis", exc_info=True)
            return {}

    def get_market_context(self) -> Any | None:
        """Read LLM market analysis context from Redis.

        Returns:
            MarketContext instance if available, None otherwise.
        """
        try:
            r = _get_redis()
            key = _key(_KEY_MARKET_CONTEXT, self._asset)
            raw = r.get(key)
            if not raw:
                return None
            data = json.loads(raw)
            # Import here to avoid circular dependency
            from shared.llm.market_context import MarketContext
            return MarketContext.from_dict(data)
        except Exception:
            logger.debug("Failed to read market context from Redis", exc_info=True)
            return None

    # -- Cross-session cumulative counters ------------------------------------

    def get_running_totals(self) -> dict[str, float]:
        """Return cumulative session-independent counters.

        Returns:
            dict with keys ``total_pnl`` (float), ``total_trades`` (int),
            ``total_wins`` (int).  All values default to zero when the key
            has not been written yet.
        """
        try:
            r = _get_redis()
            key = _key(_KEY_RUNNING_TOTALS, self._asset)
            raw = r.hgetall(key) or {}
            return {
                "total_pnl": float(raw.get("total_pnl", 0.0) or 0.0),
                "total_trades": int(raw.get("total_trades", 0) or 0),
                "total_wins": int(raw.get("total_wins", 0) or 0),
            }
        except Exception:
            logger.debug("Failed to read running totals from Redis", exc_info=True)
            return {"total_pnl": 0.0, "total_trades": 0, "total_wins": 0}

    def get_equity_timeline(self, days: int = 30) -> list[dict]:
        """Return recent daily equity snapshots in chronological order.

        Args:
            days: Maximum number of most-recent entries to return.

        Returns:
            List of dicts with keys ``date``, ``cash_balance``,
            ``open_positions_value``, ``closed_pnl``, ``total_equity``.
            Oldest entry first.
        """
        try:
            r = _get_redis()
            key = _key(_KEY_EQUITY_TIMELINE, self._asset)
            raw = r.zrange(key, -days, -1, withscores=False) or []
            return [json.loads(s) for s in raw]
        except Exception:
            logger.debug("Failed to read equity timeline from Redis", exc_info=True)
            return []
