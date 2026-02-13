"""Trading State Bus — Redis-backed shared state between orchestrator and dashboard.

The orchestrator (CLI process) publishes trading state to Redis.
The dashboard (Docker container) reads it back for display.

Redis Keys (all in DB1):
    trading:{asset}:status     — HASH   (orchestrator status snapshot)
    trading:{asset}:positions  — HASH   (field=position_id, value=JSON)
    trading:{asset}:trades     — LIST   (most recent first, max 500)
    trading:{asset}:signals    — LIST   (most recent first, max 200)
"""

from __future__ import annotations

import json
import logging
import time as _time
from datetime import datetime
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

MAX_TRADES = 500
MAX_SIGNALS = 200
STATUS_TTL_SECONDS = 86400  # 24h — auto-expire if orchestrator dies


def _key(template: str, asset: str) -> str:
    return template.format(asset=asset)


def _get_redis() -> redis.Redis:
    """Get the shared Redis client singleton."""
    from shared.streaming.client import RedisClient
    return RedisClient.get_client()


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
            r.hset(key, position.id, json.dumps(data))
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
            pipe.lpush(trades_key, json.dumps(data))
            pipe.ltrim(trades_key, 0, MAX_TRADES - 1)
            pipe.execute()
        except Exception:
            logger.debug("Failed to publish position close", exc_info=True)

    def publish_positions_update(self, positions: list[Any], throttle: float = 2.0) -> None:
        """Bulk-update all position prices (throttled)."""
        now = _time.monotonic()
        if now - self._last_position_publish < throttle:
            return
        self._last_position_publish = now
        try:
            r = _get_redis()
            key = _key(_KEY_POSITIONS, self._asset)
            pipe = r.pipeline(transaction=False)
            for pos in positions:
                data = self._serialize_position(pos)
                pipe.hset(key, pos.id, json.dumps(data))
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
                "timestamp": datetime.now().isoformat(),
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
            pipe.execute()
        except Exception:
            logger.debug("Failed to publish signal", exc_info=True)

    # -- Raw dict methods (for non-orchestrator publishers like RL paper trader) -

    def publish_raw_position(self, position_id: str, data: dict) -> None:
        """Add/update a position from a plain dict."""
        try:
            r = _get_redis()
            key = _key(_KEY_POSITIONS, self._asset)
            r.hset(key, position_id, json.dumps(data))
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
            pipe.execute()
        except Exception:
            logger.debug("Failed to publish raw signal", exc_info=True)

    # -- Cleanup --------------------------------------------------------------

    def clear_all(self) -> None:
        """Remove all keys for this asset class."""
        try:
            r = _get_redis()
            pipe = r.pipeline(transaction=False)
            for tmpl in (_KEY_STATUS, _KEY_POSITIONS, _KEY_TRADES, _KEY_SIGNALS):
                pipe.delete(_key(tmpl, self._asset))
            pipe.execute()
        except Exception:
            logger.debug("Failed to clear trading state", exc_info=True)

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
            "entry_time": pos.entry_time.isoformat() if isinstance(pos.entry_time, datetime) else str(pos.entry_time),
            "strategy": getattr(pos, "strategy", ""),
            "state": pos.state.value if hasattr(pos.state, "value") else str(pos.state),
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
            "entry_time": pos.entry_time.isoformat() if isinstance(pos.entry_time, datetime) else str(pos.entry_time),
            "exit_time": datetime.now().isoformat(),
            "exit_reason": getattr(pos, "exit_reason", None) or "",
        }


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
