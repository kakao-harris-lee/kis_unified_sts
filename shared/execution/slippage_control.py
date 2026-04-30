"""Futures slippage control state machine.

Implements a configuration-driven entry guard for KOSPI200 mini futures:
- Liquidity/spread filter
- Passive limit-first execution plan
- Timeout -> retry/cancel decision
- Volatility spike filter
- Cross-asset spread filter
- Time-window filter
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RetryPolicy(str, Enum):
    """Retry behavior after passive timeout."""

    MARKET_ONCE = "market_once"
    ABORT = "abort"


class ExecutionState(str, Enum):
    """State machine states for entry execution."""

    NEW = "new"
    FILTERING = "filtering"
    BLOCKED = "blocked"
    PASSIVE_ORDER_SUBMITTED = "passive_order_submitted"
    PASSIVE_TIMEOUT = "passive_timeout"
    RETRY_ORDER_SUBMITTED = "retry_order_submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"


class ExecutionAction(str, Enum):
    """Next action from state evaluation."""

    BLOCK = "block"
    PASSIVE_LIMIT = "passive_limit"
    RETRY_MARKET = "retry_market"
    CANCEL = "cancel"


@dataclass(frozen=True)
class TimeWindow:
    """Simple intraday time window."""

    start: time
    end: time

    def contains(self, current: time) -> bool:
        if self.start <= self.end:
            return self.start <= current <= self.end
        # Overnight window (e.g. 23:55~00:10).
        return current >= self.start or current <= self.end

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimeWindow:
        start = _parse_hhmm(str(data.get("start", "")).strip())
        end = _parse_hhmm(str(data.get("end", "")).strip())
        return cls(start=start, end=end)


@dataclass
class OrderBookSnapshot:
    """Normalized top-of-book snapshot used by slippage guard."""

    symbol: str
    bid_price_1: float
    ask_price_1: float
    bid_qty_1: float
    ask_qty_1: float
    last_price: float
    timestamp: datetime

    @property
    def spread(self) -> float:
        return self.ask_price_1 - self.bid_price_1

    @property
    def mid_price(self) -> float:
        return (self.ask_price_1 + self.bid_price_1) / 2.0

    def spread_ticks(self, tick_size: float) -> float:
        if tick_size <= 0:
            return 0.0
        return self.spread / tick_size

    def available_qty(self, is_buy: bool) -> float:
        return self.ask_qty_1 if is_buy else self.bid_qty_1

    def entry_price(self, is_buy: bool) -> float:
        return self.ask_price_1 if is_buy else self.bid_price_1


@dataclass
class StateTransition:
    """Execution state transition record."""

    state: ExecutionState
    at: datetime
    reason: str = ""


@dataclass
class EntryDecision:
    """State-machine decision for an entry step."""

    action: ExecutionAction
    state: ExecutionState
    reason: str = ""
    target_price: float | None = None
    spread_ticks: float | None = None
    price_deviation_ticks: float | None = None
    quote: OrderBookSnapshot | None = None
    transitions: list[StateTransition] = field(default_factory=list)


@dataclass
class SlippageControlConfig:
    """Configuration for futures slippage control."""

    enabled: bool = False
    tick_size: float = 0.02
    max_spread_ticks: int = 1
    min_depth_multiplier: float = 3.0
    passive_timeout_seconds: float = 0.7
    retry_policy: RetryPolicy = RetryPolicy.MARKET_ONCE
    max_price_deviation_ticks: int = 2
    max_signal_age_seconds: float = 2.0
    volatility_window_ticks: int = 20
    volatility_spike_multiplier: float = 2.5
    volatility_cooldown_seconds: float = 2.0
    cross_asset_enabled: bool = True
    cross_asset_symbol: str = "101S6000"
    cross_asset_max_spread_ticks: int = 2
    blocked_time_windows: list[TimeWindow] = field(default_factory=list)
    event_time_windows: list[TimeWindow] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlippageControlConfig:
        if not isinstance(data, dict):
            return cls()

        volatility = (
            data.get("volatility", {})
            if isinstance(data.get("volatility"), dict)
            else {}
        )
        cross_asset = (
            data.get("cross_asset", {})
            if isinstance(data.get("cross_asset"), dict)
            else {}
        )

        blocked = _parse_windows(data.get("blocked_time_windows"))
        events = _parse_windows(data.get("event_time_windows"))
        if not events:
            events = _parse_windows(data.get("event_blackout_windows"))

        retry_policy_raw = (
            str(data.get("retry_policy", RetryPolicy.MARKET_ONCE.value)).strip().lower()
        )
        if retry_policy_raw not in {item.value for item in RetryPolicy}:
            retry_policy_raw = RetryPolicy.MARKET_ONCE.value

        return cls(
            enabled=_to_bool(data.get("enabled", False)),
            tick_size=float(data.get("tick_size", 0.02)),
            max_spread_ticks=int(data.get("max_spread_ticks", 1)),
            min_depth_multiplier=float(data.get("min_depth_multiplier", 3.0)),
            passive_timeout_seconds=float(data.get("passive_timeout_seconds", 0.7)),
            retry_policy=RetryPolicy(retry_policy_raw),
            max_price_deviation_ticks=int(data.get("max_price_deviation_ticks", 2)),
            max_signal_age_seconds=float(data.get("max_signal_age_seconds", 2.0)),
            volatility_window_ticks=int(volatility.get("window_ticks", 20)),
            volatility_spike_multiplier=float(volatility.get("spike_multiplier", 2.5)),
            volatility_cooldown_seconds=float(volatility.get("cooldown_seconds", 2.0)),
            cross_asset_enabled=_to_bool(
                cross_asset.get("enabled", True), default=True
            ),
            cross_asset_symbol=str(cross_asset.get("reference_symbol", "101S6000")),
            cross_asset_max_spread_ticks=int(cross_asset.get("max_spread_ticks", 2)),
            blocked_time_windows=blocked,
            event_time_windows=events,
        )


def parse_orderbook_snapshot(
    symbol: str,
    payload: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> OrderBookSnapshot | None:
    """Parse real-time market payload into an orderbook snapshot."""
    if not isinstance(payload, dict):
        return None

    bid = _to_float(payload.get("bid_price_1"))
    ask = _to_float(payload.get("ask_price_1"))
    if bid <= 0 or ask <= 0 or ask < bid:
        return None

    bid_qty = _to_float(payload.get("bid_qty_1"))
    ask_qty = _to_float(payload.get("ask_qty_1"))

    close = _to_float(payload.get("close"))
    if close <= 0:
        close = _to_float(payload.get("current_price"))
    if close <= 0:
        close = (ask + bid) / 2.0

    timestamp = (
        _parse_timestamp(payload.get("timestamp")) or now or datetime.now(timezone.utc)
    )

    return OrderBookSnapshot(
        symbol=symbol,
        bid_price_1=bid,
        ask_price_1=ask,
        bid_qty_1=bid_qty,
        ask_qty_1=ask_qty,
        last_price=close,
        timestamp=timestamp,
    )


def compute_adverse_slippage_ticks(
    *,
    signal_price: float,
    fill_price: float,
    is_buy: bool,
    tick_size: float,
) -> float:
    """Compute adverse slippage in ticks (positive = worse fill)."""
    if tick_size <= 0:
        return 0.0
    adverse = (fill_price - signal_price) if is_buy else (signal_price - fill_price)
    return adverse / tick_size


class FuturesSlippageController:
    """State-machine based slippage controller for futures entries."""

    def __init__(self, config: SlippageControlConfig):
        self.config = config
        self._last_trade_price: dict[str, float] = {}
        self._recent_abs_moves: dict[str, deque[float]] = {}
        self._cooldown_until: dict[str, datetime] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.config.enabled)

    def register_trade_tick(
        self, symbol: str, price: float, timestamp: datetime | None = None
    ) -> None:
        """Register trade tick for volatility baseline."""
        if price <= 0:
            return
        ts = timestamp or datetime.now(timezone.utc)
        # `_cooldown_until` is later compared against UTC-aware ts in
        # `evaluate_entry`. Normalize here so a naive caller doesn't poison
        # the dict with mixed-tz values.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)

        previous = self._last_trade_price.get(symbol)
        self._last_trade_price[symbol] = price
        if previous is None:
            return

        move = abs(price - previous)
        window = max(3, int(self.config.volatility_window_ticks))
        history = self._recent_abs_moves.get(symbol)
        if history is None:
            history = deque(maxlen=window)
            self._recent_abs_moves[symbol] = history
        history.append(move)

        if not history:
            return
        avg_move = sum(history) / len(history)
        if avg_move <= 0:
            return
        if move >= avg_move * self.config.volatility_spike_multiplier:
            self._cooldown_until[symbol] = ts + timedelta(
                seconds=max(0.1, self.config.volatility_cooldown_seconds)
            )

    def evaluate_entry(
        self,
        *,
        symbol: str,
        is_buy: bool,
        quantity: int,
        signal_price: float,
        signal_timestamp: datetime,
        quote_payload: dict[str, Any] | None,
        cross_asset_payload: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> EntryDecision:
        """Evaluate entry filters and produce passive-limit execution decision."""
        # Defensive tz normalization: callers historically passed naive
        # `datetime.now()` for the `now` arg and naive `signal_timestamp`s.
        # All arithmetic happens in UTC; naive inputs are interpreted as UTC.
        ts = now or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        transitions = [
            StateTransition(state=ExecutionState.NEW, at=ts),
            StateTransition(state=ExecutionState.FILTERING, at=ts),
        ]

        stale_seconds = max(0.1, self.config.max_signal_age_seconds)
        sig_ts = (
            signal_timestamp.replace(tzinfo=timezone.utc)
            if signal_timestamp.tzinfo is None
            else signal_timestamp.astimezone(timezone.utc)
        )
        signal_age = (ts - sig_ts).total_seconds()
        if signal_age > stale_seconds:
            return self._block(
                reason=f"stale_signal:{signal_age:.2f}s",
                at=ts,
                transitions=transitions,
            )

        if self._is_blocked_time(ts.time()):
            return self._block(
                reason="blocked_time_window", at=ts, transitions=transitions
            )

        cooldown_until = self._cooldown_until.get(symbol)
        if cooldown_until and ts < cooldown_until:
            remain = (cooldown_until - ts).total_seconds()
            return self._block(
                reason=f"volatility_cooldown:{remain:.2f}s",
                at=ts,
                transitions=transitions,
            )

        quote = parse_orderbook_snapshot(symbol, quote_payload, now=ts)
        if quote is None:
            return self._block(
                reason="orderbook_unavailable", at=ts, transitions=transitions
            )

        # Keep volatility baseline up-to-date even when evaluation is sparse.
        self.register_trade_tick(symbol, quote.last_price, timestamp=ts)

        spread_ticks = quote.spread_ticks(self.config.tick_size)
        if spread_ticks > self.config.max_spread_ticks:
            return self._block(
                reason=f"wide_spread:{spread_ticks:.2f}ticks",
                at=ts,
                transitions=transitions,
                quote=quote,
                spread_ticks=spread_ticks,
            )

        required_depth = float(quantity) * self.config.min_depth_multiplier
        available_depth = quote.available_qty(is_buy=is_buy)
        if available_depth < required_depth:
            return self._block(
                reason=f"insufficient_depth:{available_depth:.1f}<{required_depth:.1f}",
                at=ts,
                transitions=transitions,
                quote=quote,
                spread_ticks=spread_ticks,
            )

        if self.config.cross_asset_enabled:
            cross_symbol = self.config.cross_asset_symbol
            cross_quote = parse_orderbook_snapshot(
                cross_symbol, cross_asset_payload, now=ts
            )
            if cross_quote is None:
                return self._block(
                    reason=f"cross_asset_unavailable:{cross_symbol}",
                    at=ts,
                    transitions=transitions,
                    quote=quote,
                    spread_ticks=spread_ticks,
                )
            cross_spread_ticks = cross_quote.spread_ticks(self.config.tick_size)
            if cross_spread_ticks > self.config.cross_asset_max_spread_ticks:
                return self._block(
                    reason=f"cross_asset_wide_spread:{cross_spread_ticks:.2f}ticks",
                    at=ts,
                    transitions=transitions,
                    quote=quote,
                    spread_ticks=spread_ticks,
                )

        target_price = quote.entry_price(is_buy=is_buy)
        deviation_ticks = abs(target_price - signal_price) / self.config.tick_size
        if deviation_ticks > self.config.max_price_deviation_ticks:
            return self._block(
                reason=f"price_deviation:{deviation_ticks:.2f}ticks",
                at=ts,
                transitions=transitions,
                quote=quote,
                spread_ticks=spread_ticks,
                deviation_ticks=deviation_ticks,
            )

        transitions.append(
            StateTransition(
                state=ExecutionState.PASSIVE_ORDER_SUBMITTED,
                at=ts,
                reason="filters_passed",
            )
        )
        return EntryDecision(
            action=ExecutionAction.PASSIVE_LIMIT,
            state=ExecutionState.PASSIVE_ORDER_SUBMITTED,
            reason="filters_passed",
            target_price=target_price,
            spread_ticks=spread_ticks,
            price_deviation_ticks=deviation_ticks,
            quote=quote,
            transitions=transitions,
        )

    def evaluate_retry(
        self,
        *,
        symbol: str,
        is_buy: bool,
        signal_price: float,
        quote_payload: dict[str, Any] | None,
        now: datetime | None = None,
    ) -> EntryDecision:
        """Evaluate timeout path: retry once at market or cancel."""
        ts = now or datetime.now(timezone.utc)
        transitions = [
            StateTransition(state=ExecutionState.PASSIVE_TIMEOUT, at=ts),
        ]

        if self.config.retry_policy == RetryPolicy.ABORT:
            transitions.append(
                StateTransition(
                    state=ExecutionState.CANCELLED, at=ts, reason="retry_policy_abort"
                )
            )
            return EntryDecision(
                action=ExecutionAction.CANCEL,
                state=ExecutionState.CANCELLED,
                reason="retry_policy_abort",
                transitions=transitions,
            )

        quote = parse_orderbook_snapshot(symbol, quote_payload, now=ts)
        if quote is None:
            transitions.append(
                StateTransition(
                    state=ExecutionState.CANCELLED, at=ts, reason="retry_no_orderbook"
                )
            )
            return EntryDecision(
                action=ExecutionAction.CANCEL,
                state=ExecutionState.CANCELLED,
                reason="retry_no_orderbook",
                transitions=transitions,
            )

        target_price = quote.entry_price(is_buy=is_buy)
        deviation_ticks = abs(target_price - signal_price) / self.config.tick_size
        if deviation_ticks > self.config.max_price_deviation_ticks:
            transitions.append(
                StateTransition(
                    state=ExecutionState.CANCELLED,
                    at=ts,
                    reason=f"retry_deviation:{deviation_ticks:.2f}ticks",
                )
            )
            return EntryDecision(
                action=ExecutionAction.CANCEL,
                state=ExecutionState.CANCELLED,
                reason=f"retry_deviation:{deviation_ticks:.2f}ticks",
                target_price=target_price,
                price_deviation_ticks=deviation_ticks,
                quote=quote,
                transitions=transitions,
            )

        transitions.append(
            StateTransition(
                state=ExecutionState.RETRY_ORDER_SUBMITTED,
                at=ts,
                reason="retry_market_once",
            )
        )
        return EntryDecision(
            action=ExecutionAction.RETRY_MARKET,
            state=ExecutionState.RETRY_ORDER_SUBMITTED,
            reason="retry_market_once",
            target_price=target_price,
            price_deviation_ticks=deviation_ticks,
            quote=quote,
            transitions=transitions,
        )

    def _is_blocked_time(self, current: time) -> bool:
        windows = self.config.blocked_time_windows + self.config.event_time_windows
        return any(window.contains(current) for window in windows)

    @staticmethod
    def _block(
        *,
        reason: str,
        at: datetime,
        transitions: list[StateTransition],
        quote: OrderBookSnapshot | None = None,
        spread_ticks: float | None = None,
        deviation_ticks: float | None = None,
    ) -> EntryDecision:
        transitions.append(
            StateTransition(state=ExecutionState.BLOCKED, at=at, reason=reason)
        )
        return EntryDecision(
            action=ExecutionAction.BLOCK,
            state=ExecutionState.BLOCKED,
            reason=reason,
            quote=quote,
            spread_ticks=spread_ticks,
            price_deviation_ticks=deviation_ticks,
            transitions=transitions,
        )


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "f", "no", "n", "off", ""}:
            return False
    return default


def _parse_hhmm(value: str) -> time:
    try:
        hour_str, minute_str = value.split(":")
        return time(hour=int(hour_str), minute=int(minute_str))
    except (
        Exception
    ) as exc:  # pragma: no cover - guarded by config validation at runtime
        raise ValueError(f"Invalid HH:MM time format: {value!r}") from exc


def _parse_windows(raw: Any) -> list[TimeWindow]:
    if not isinstance(raw, list):
        return []
    windows: list[TimeWindow] = []
    for item in raw:
        if isinstance(item, dict):
            try:
                windows.append(TimeWindow.from_dict(item))
            except Exception as exc:
                logger.warning(f"Invalid time window config ignored: {item} ({exc})")
    return windows


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (TypeError, OSError, ValueError):
            return None

    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        except ValueError:
            return None

    return None
