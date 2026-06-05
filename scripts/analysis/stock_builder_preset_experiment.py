#!/usr/bin/env python3
"""Run isolated paper-ledger experiments for stock Strategy Builder presets.

This is intentionally separate from the live paper broker. The live broker and
PositionTracker are symbol-centric; this script gives each preset its own
virtual ledger so the same symbol basket can be compared fairly across
strategies.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from shared.backtest.daily_adapter import load_stock_daily_from_parquet  # noqa: E402
from shared.config.loader import ConfigLoader  # noqa: E402
from shared.strategy_builder.evaluator import StrategyBuilderEvaluator  # noqa: E402
from shared.strategy_builder.kis_compat import (  # noqa: E402
    apply_kis_preset_params,
    get_kis_preset,
    kis_state_to_builder_state,
)
from shared.strategy_builder.schema import (  # noqa: E402
    BuilderState,
    SignalSide,
    SymbolSeries,
)

DailyLoader = Callable[[str, date, date], pd.DataFrame]


@dataclass(frozen=True)
class Costs:
    commission_rate: float
    slippage_rate: float
    tax_rate: float

    @property
    def entry_rate(self) -> float:
        return self.commission_rate + self.slippage_rate

    @property
    def exit_rate(self) -> float:
        return self.commission_rate + self.slippage_rate + self.tax_rate


@dataclass
class OpenPosition:
    symbol: str
    name: str
    entry_date: str
    entry_price: float
    quantity: int
    cost_basis: float
    highest_price: float
    lowest_price: float
    entry_strength: float


@dataclass
class Trade:
    strategy_id: str
    strategy_name: str
    symbol: str
    name: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    exit_reason: str
    entry_strength: float
    exit_strength: float


@dataclass
class Ledger:
    strategy_id: str
    strategy_name: str
    initial_capital: float
    cash: float
    positions: dict[str, OpenPosition] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[dict[str, float | str]] = field(default_factory=list)
    entry_signals: int = 0
    admitted_entries: int = 0
    rejected_max_positions: int = 0
    rejected_existing_position: int = 0
    rejected_insufficient_cash: int = 0
    exit_signals: int = 0


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _as_symbol_list(value: Any) -> list[str]:
    if not value:
        return []
    raw_items = value.split(",") if isinstance(value, str) else list(value)
    result: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        symbol = str(item).strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        result.append(symbol)
    return result


def load_experiment_config(path: str) -> dict[str, Any]:
    cfg = ConfigLoader.load(path, use_cache=False)
    if not isinstance(cfg, dict):
        raise ValueError(f"Config did not load as a mapping: {path}")
    exp = cfg.get("experiment", cfg)
    if not isinstance(exp, dict):
        raise ValueError(f"Experiment config is not a mapping: {path}")
    return exp


def _extract_redis_symbols(
    payload: dict[str, Any], strategy_names: list[str]
) -> list[str]:
    symbols: list[str] = []
    strategies = payload.get("strategies")
    if isinstance(strategies, dict):
        selected = strategy_names or list(strategies.keys())
        for name in selected:
            symbols.extend(_as_symbol_list(strategies.get(name)))
    symbols.extend(_as_symbol_list(payload.get("symbols")))
    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        for item in candidates:
            if isinstance(item, dict):
                symbols.extend(_as_symbol_list(item.get("code") or item.get("symbol")))
            else:
                symbols.extend(_as_symbol_list(item))
    return _as_symbol_list(symbols)


def _load_redis_symbols(source: dict[str, Any]) -> list[str]:
    try:
        import redis
    except Exception:
        return []

    redis_url = str(
        source.get("redis_url")
        or os.environ.get("REDIS_URL")
        or "redis://localhost:6379/1"
    )
    key = str(source.get("redis_key") or "system:daily_watchlist:latest")
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        raw = client.get(key)
    except Exception:
        return []
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    return _extract_redis_symbols(payload, _as_symbol_list(source.get("strategies")))


def resolve_symbols(config: dict[str, Any]) -> list[str]:
    explicit = _as_symbol_list(config.get("symbols"))
    if explicit:
        return explicit

    source = config.get("basket_source") or {}
    symbols: list[str] = []
    if isinstance(source, dict) and source.get("type") == "redis_daily_watchlist":
        symbols = _load_redis_symbols(source)
    if not symbols:
        symbols = _as_symbol_list(config.get("fallback_symbols"))

    max_symbols = None
    if isinstance(source, dict) and source.get("max_symbols") not in (None, ""):
        max_symbols = int(source["max_symbols"])
    if max_symbols:
        symbols = symbols[:max_symbols]
    return symbols


def _series_to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


def _true_range(df: pd.DataFrame) -> pd.Series:
    high = _series_to_float(df["high"])
    low = _series_to_float(df["low"])
    close = _series_to_float(df["close"])
    prev_close = close.shift(1)
    parts = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    )
    return parts.max(axis=1)


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    return (
        _true_range(df).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    )


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _adx_outputs(df: pd.DataFrame, period: int) -> dict[str, pd.Series]:
    high = _series_to_float(df["high"])
    low = _series_to_float(df["low"])
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=df.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=df.index,
    )
    atr = _atr(df, period)
    plus_di = (
        100
        * plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        / atr
    )
    minus_di = (
        100
        * minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        / atr
    )
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return {"value": adx, "plus_di": plus_di, "minus_di": minus_di}


def _supertrend(df: pd.DataFrame, period: int, multiplier: float) -> pd.Series:
    high = _series_to_float(df["high"])
    low = _series_to_float(df["low"])
    close = _series_to_float(df["close"])
    atr = _atr(df, period)
    hl2 = (high + low) / 2
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr
    trend = pd.Series(index=df.index, dtype=float)
    direction = 1
    for i, idx in enumerate(df.index):
        if i == 0 or math.isnan(float(atr.iloc[i])):
            trend.iloc[i] = np.nan
            continue
        prev_idx = df.index[i - 1]
        prev_trend = trend.loc[prev_idx]
        if close.loc[idx] > upper.loc[prev_idx]:
            direction = 1
        elif close.loc[idx] < lower.loc[prev_idx]:
            direction = -1
        if direction > 0:
            trend.iloc[i] = (
                max(lower.loc[idx], prev_trend)
                if not math.isnan(float(prev_trend))
                else lower.loc[idx]
            )
        else:
            trend.iloc[i] = (
                min(upper.loc[idx], prev_trend)
                if not math.isnan(float(prev_trend))
                else upper.loc[idx]
            )
    return trend


def _indicator_outputs(df: pd.DataFrame, indicator: Any) -> dict[str, pd.Series]:
    params = dict(indicator.params or {})
    indicator_id = str(indicator.indicator_id)
    close = _series_to_float(df["close"])
    high = _series_to_float(df["high"])
    low = _series_to_float(df["low"])
    volume = _series_to_float(df["volume"])

    def period(default: int) -> int:
        return max(1, int(params.get("period", default) or default))

    if indicator_id == "sma":
        return {"value": close.rolling(period(20), min_periods=period(20)).mean()}
    if indicator_id == "ema":
        p = period(20)
        return {"value": close.ewm(span=p, min_periods=p, adjust=False).mean()}
    if indicator_id == "rsi":
        return {"value": _rsi(close, period(14))}
    if indicator_id == "roc":
        p = period(60)
        return {"value": (close / close.shift(p) - 1.0) * 100.0}
    if indicator_id == "change":
        return {"value": close.pct_change() * 100.0}
    if indicator_id == "maximum":
        p = period(252)
        return {"value": high.rolling(p, min_periods=p).max().shift(1)}
    if indicator_id == "breakout_margin":
        p = period(252)
        previous_high = high.rolling(p, min_periods=p).max().shift(1)
        return {"value": (close / previous_high - 1.0) * 100.0}
    if indicator_id == "vwap":
        p = period(20)
        typical = (high + low + close) / 3.0
        numerator = (typical * volume).rolling(p, min_periods=1).sum()
        denominator = volume.rolling(p, min_periods=1).sum().replace(0, np.nan)
        return {"value": numerator / denominator}
    if indicator_id == "macd":
        fast = int(params.get("fast", 12) or 12)
        slow = int(params.get("slow", 26) or 26)
        signal_period = int(params.get("signal", 9) or 9)
        fast_ema = close.ewm(span=fast, min_periods=fast, adjust=False).mean()
        slow_ema = close.ewm(span=slow, min_periods=slow, adjust=False).mean()
        macd = fast_ema - slow_ema
        signal = macd.ewm(
            span=signal_period, min_periods=signal_period, adjust=False
        ).mean()
        return {"value": macd, "signal": signal, "histogram": macd - signal}
    if indicator_id == "donchian":
        p = period(20)
        upper = high.rolling(p, min_periods=p).max().shift(1)
        lower = low.rolling(p, min_periods=p).min().shift(1)
        return {"upper": upper, "lower": lower, "middle": (upper + lower) / 2.0}
    if indicator_id == "adx":
        return _adx_outputs(df, period(14))
    if indicator_id == "supertrend":
        return {
            "value": _supertrend(
                df,
                period(10),
                float(params.get("multiplier", 3) or 3),
            )
        }
    if indicator_id == "keltner":
        p = period(20)
        multiplier = float(params.get("multiplier", 2) or 2)
        middle = close.ewm(span=p, min_periods=p, adjust=False).mean()
        atr = _atr(df, p)
        return {
            "middle": middle,
            "upper": middle + multiplier * atr,
            "lower": middle - multiplier * atr,
        }
    return {}


def _prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    if "datetime" not in frame.columns:
        raise ValueError("daily frame must contain datetime column")
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    for col in ("open", "high", "low", "close", "volume"):
        if col not in frame.columns:
            raise ValueError(f"daily frame missing required column: {col}")
        frame[col] = _series_to_float(frame[col])
    frame = frame.sort_values("datetime").drop_duplicates("datetime", keep="last")
    return frame.reset_index(drop=True)


def _feature_frame(state: BuilderState, df: pd.DataFrame) -> pd.DataFrame:
    frame = _prepare_frame(df)
    for indicator in state.indicators:
        outputs = _indicator_outputs(frame, indicator)
        for output, values in outputs.items():
            frame[f"ind:{indicator.alias}.{output}"] = values
    return frame


def _values_until(frame: pd.DataFrame, column: str, end_index: int) -> list[float]:
    values = frame.loc[:end_index, column].tolist()
    result: list[float] = []
    for value in values:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = math.nan
        result.append(numeric)
    return result


def _series_for_row(
    state: BuilderState, symbol: str, frame: pd.DataFrame, row_index: int
) -> SymbolSeries:
    fields = {
        col: _values_until(frame, col, row_index)
        for col in ("open", "high", "low", "close", "volume")
    }
    indicators: dict[str, list[float]] = {}
    for indicator in state.indicators:
        for output in {
            indicator.output,
            "value",
            "signal",
            "histogram",
            "upper",
            "lower",
            "middle",
            "plus_di",
            "minus_di",
        }:
            col = f"ind:{indicator.alias}.{output}"
            if col in frame.columns:
                indicators[f"{indicator.alias}.{output}"] = _values_until(
                    frame, col, row_index
                )
    return SymbolSeries(
        symbol=symbol,
        name=symbol,
        timestamps=[
            ts.to_pydatetime()
            for ts in pd.to_datetime(frame.loc[:row_index, "datetime"])
        ],
        fields=fields,
        indicators=indicators,
    )


def _load_states(config: dict[str, Any]) -> list[BuilderState]:
    states: list[BuilderState] = []
    for item in config.get("presets", []):
        if not isinstance(item, dict):
            continue
        preset_id = str(item["id"])
        preset = get_kis_preset(preset_id)
        if preset is None:
            raise ValueError(f"Unknown KIS builder preset: {preset_id}")
        state_dict = apply_kis_preset_params(preset, item.get("params") or {})
        state = kis_state_to_builder_state(state_dict)
        if state.asset_class != "stock":
            raise ValueError(f"Preset is not stock asset_class: {preset_id}")
        states.append(state)
    if not states:
        raise ValueError("experiment.presets must contain at least one preset")
    return states


def _load_market_data(
    symbols: list[str],
    *,
    start: date,
    end: date,
    warmup_days: int,
    loader: DailyLoader,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    data_start = start - timedelta(days=warmup_days)
    frames: dict[str, pd.DataFrame] = {}
    coverage: dict[str, Any] = {}
    for symbol in symbols:
        try:
            frame = loader(symbol, data_start, end)
        except Exception as exc:  # noqa: BLE001 - report per-symbol loader failures
            coverage[symbol] = {
                "loaded": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            continue
        if frame is None or frame.empty:
            coverage[symbol] = {"loaded": False, "error": "no_data"}
            continue
        prepared = _prepare_frame(frame)
        frames[symbol] = prepared
        coverage[symbol] = {
            "loaded": True,
            "rows": int(len(prepared)),
            "start": str(prepared["datetime"].min().date()),
            "end": str(prepared["datetime"].max().date()),
        }
    return frames, coverage


def _should_exit(
    *,
    state: BuilderState,
    position: OpenPosition,
    close: float,
    signal_side: SignalSide,
) -> str | None:
    stop = state.risk.stop_loss
    if stop.enabled and close <= position.entry_price * (1.0 - stop.percent / 100.0):
        return "stop_loss"
    take = state.risk.take_profit
    if take.enabled and close >= position.entry_price * (1.0 + take.percent / 100.0):
        return "take_profit"
    trailing = state.risk.trailing_stop
    if trailing.enabled and close <= position.highest_price * (
        1.0 - trailing.percent / 100.0
    ):
        return "trailing_stop"
    if signal_side == SignalSide.SELL:
        return "builder_exit"
    return None


def _close_position(
    ledger: Ledger,
    *,
    state: BuilderState,
    position: OpenPosition,
    exit_date: str,
    exit_price: float,
    exit_reason: str,
    exit_strength: float,
    costs: Costs,
) -> None:
    gross = exit_price * position.quantity
    proceeds = gross * (1.0 - costs.exit_rate)
    pnl = proceeds - position.cost_basis
    ledger.cash += proceeds
    ledger.trades.append(
        Trade(
            strategy_id=state.metadata.id,
            strategy_name=state.metadata.name,
            symbol=position.symbol,
            name=position.name,
            entry_date=position.entry_date,
            exit_date=exit_date,
            entry_price=position.entry_price,
            exit_price=exit_price,
            quantity=position.quantity,
            pnl=round(pnl, 4),
            pnl_pct=round(100.0 * pnl / position.cost_basis, 4),
            exit_reason=exit_reason,
            entry_strength=position.entry_strength,
            exit_strength=exit_strength,
        )
    )
    ledger.positions.pop(position.symbol, None)


def _open_position(
    ledger: Ledger,
    *,
    symbol: str,
    trade_date: str,
    close: float,
    strength: float,
    order_amount: float,
    costs: Costs,
) -> None:
    qty = int(order_amount // (close * (1.0 + costs.entry_rate)))
    if qty <= 0:
        ledger.rejected_insufficient_cash += 1
        return
    gross = close * qty
    cost_basis = gross * (1.0 + costs.entry_rate)
    if cost_basis > ledger.cash:
        ledger.rejected_insufficient_cash += 1
        return
    ledger.cash -= cost_basis
    ledger.positions[symbol] = OpenPosition(
        symbol=symbol,
        name=symbol,
        entry_date=trade_date,
        entry_price=close,
        quantity=qty,
        cost_basis=cost_basis,
        highest_price=close,
        lowest_price=close,
        entry_strength=strength,
    )
    ledger.admitted_entries += 1


def _mark_equity(
    ledger: Ledger,
    *,
    trade_date: date,
    close_by_symbol: dict[str, float],
    costs: Costs,
) -> None:
    equity = ledger.cash
    for position in ledger.positions.values():
        close = close_by_symbol.get(position.symbol, position.entry_price)
        equity += close * position.quantity * (1.0 - costs.exit_rate)
    ledger.equity_curve.append(
        {"date": trade_date.isoformat(), "equity": round(equity, 4)}
    )


def _max_drawdown_pct(equity_curve: list[dict[str, float | str]]) -> float:
    peak: float | None = None
    max_dd = 0.0
    for point in equity_curve:
        equity = float(point["equity"])
        peak = equity if peak is None else max(peak, equity)
        if peak > 0:
            max_dd = min(max_dd, (equity - peak) / peak * 100.0)
    return round(abs(max_dd), 4)


def _summarize(
    ledger: Ledger, costs: Costs, close_by_symbol: dict[str, float]
) -> dict[str, Any]:
    realized_pnl = sum(trade.pnl for trade in ledger.trades)
    unrealized_pnl = 0.0
    open_positions: list[dict[str, Any]] = []
    for position in ledger.positions.values():
        close = close_by_symbol.get(position.symbol, position.entry_price)
        liquidation_value = close * position.quantity * (1.0 - costs.exit_rate)
        pnl = liquidation_value - position.cost_basis
        unrealized_pnl += pnl
        open_positions.append(
            {**asdict(position), "mark_price": close, "unrealized_pnl": round(pnl, 4)}
        )

    last_equity = (
        ledger.equity_curve[-1]["equity"]
        if ledger.equity_curve
        else ledger.initial_capital
    )
    wins = sum(1 for trade in ledger.trades if trade.pnl > 0)
    return {
        "strategy_id": ledger.strategy_id,
        "strategy_name": ledger.strategy_name,
        "initial_capital": ledger.initial_capital,
        "final_equity": round(float(last_equity), 4),
        "total_return_pct": round(
            (float(last_equity) / ledger.initial_capital - 1.0) * 100.0, 4
        ),
        "realized_pnl": round(realized_pnl, 4),
        "unrealized_pnl": round(unrealized_pnl, 4),
        "closed_trades": len(ledger.trades),
        "open_positions": len(ledger.positions),
        "win_rate_pct": (
            round(100.0 * wins / len(ledger.trades), 4) if ledger.trades else 0.0
        ),
        "max_drawdown_pct": _max_drawdown_pct(ledger.equity_curve),
        "entry_signals": ledger.entry_signals,
        "admitted_entries": ledger.admitted_entries,
        "exit_signals": ledger.exit_signals,
        "rejected_existing_position": ledger.rejected_existing_position,
        "rejected_max_positions": ledger.rejected_max_positions,
        "rejected_insufficient_cash": ledger.rejected_insufficient_cash,
        "positions": open_positions,
    }


def run_experiment(
    config: dict[str, Any],
    *,
    start: date | None = None,
    end: date | None = None,
    loader: DailyLoader = load_stock_daily_from_parquet,
) -> dict[str, Any]:
    experiment_id = str(config.get("id") or "stock_builder_preset_experiment")
    start_date = start or _as_date(config["start_date"])
    end_date = end or _as_date(config["end_date"])
    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    costs = Costs(**(config.get("costs") or {}))
    symbols = resolve_symbols(config)
    if not symbols:
        raise ValueError("No symbols resolved for experiment basket")
    states = _load_states(config)
    market_data, coverage = _load_market_data(
        symbols,
        start=start_date,
        end=end_date,
        warmup_days=int(config.get("warmup_days") or 280),
        loader=loader,
    )
    feature_frames = {
        state.metadata.id: {
            symbol: _feature_frame(state, frame)
            for symbol, frame in market_data.items()
        }
        for state in states
    }
    ledgers = {
        state.metadata.id: Ledger(
            strategy_id=state.metadata.id,
            strategy_name=state.metadata.name,
            initial_capital=float(config.get("initial_capital") or 10_000_000),
            cash=float(config.get("initial_capital") or 10_000_000),
        )
        for state in states
    }
    evaluator = StrategyBuilderEvaluator()
    order_amount = float(config.get("order_amount_per_stock") or 1_000_000)
    max_positions = int(config.get("max_positions_per_strategy") or 5)
    min_strength = float(config.get("min_signal_strength") or 0.5)

    all_dates = sorted(
        {
            pd.Timestamp(value).date()
            for frame in market_data.values()
            for value in frame["datetime"]
            if start_date <= pd.Timestamp(value).date() <= end_date
        }
    )

    last_close_by_symbol: dict[str, float] = {}
    for trade_date in all_dates:
        daily_close_by_symbol: dict[str, float] = {}
        for symbol, frame in market_data.items():
            rows = frame[pd.to_datetime(frame["datetime"]).dt.date <= trade_date]
            if not rows.empty:
                daily_close_by_symbol[symbol] = float(rows.iloc[-1]["close"])
        last_close_by_symbol.update(daily_close_by_symbol)

        for state in states:
            ledger = ledgers[state.metadata.id]
            frames = feature_frames[state.metadata.id]

            for symbol, position in list(ledger.positions.items()):
                frame = frames.get(symbol)
                if frame is None:
                    continue
                matches = frame[pd.to_datetime(frame["datetime"]).dt.date == trade_date]
                if matches.empty:
                    continue
                row_index = int(matches.index[-1])
                close = float(frame.loc[row_index, "close"])
                position.highest_price = max(position.highest_price, close)
                position.lowest_price = min(position.lowest_price, close)
                signal = evaluator.generate_signals(
                    state, [_series_for_row(state, symbol, frame, row_index)]
                )[0]
                if signal.side == SignalSide.SELL:
                    ledger.exit_signals += 1
                reason = _should_exit(
                    state=state,
                    position=position,
                    close=close,
                    signal_side=signal.side,
                )
                if reason:
                    _close_position(
                        ledger,
                        state=state,
                        position=position,
                        exit_date=trade_date.isoformat(),
                        exit_price=close,
                        exit_reason=reason,
                        exit_strength=signal.strength,
                        costs=costs,
                    )

            for symbol in symbols:
                frame = frames.get(symbol)
                if frame is None:
                    continue
                matches = frame[pd.to_datetime(frame["datetime"]).dt.date == trade_date]
                if matches.empty:
                    continue
                row_index = int(matches.index[-1])
                close = float(frame.loc[row_index, "close"])
                signal = evaluator.generate_signals(
                    state, [_series_for_row(state, symbol, frame, row_index)]
                )[0]
                if (
                    signal.side != SignalSide.BUY
                    or signal.orderability != "paper_orderable"
                    or signal.strength < min_strength
                ):
                    continue
                ledger.entry_signals += 1
                if symbol in ledger.positions:
                    ledger.rejected_existing_position += 1
                    continue
                if len(ledger.positions) >= max_positions:
                    ledger.rejected_max_positions += 1
                    continue
                _open_position(
                    ledger,
                    symbol=symbol,
                    trade_date=trade_date.isoformat(),
                    close=close,
                    strength=signal.strength,
                    order_amount=order_amount,
                    costs=costs,
                )

            _mark_equity(
                ledger,
                trade_date=trade_date,
                close_by_symbol=last_close_by_symbol,
                costs=costs,
            )

    summaries = [
        _summarize(ledger, costs, last_close_by_symbol) for ledger in ledgers.values()
    ]
    summaries.sort(key=lambda item: item["total_return_pct"], reverse=True)
    return {
        "experiment": {
            "id": experiment_id,
            "description": str(config.get("description") or ""),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "generated_at": datetime.now(UTC).isoformat(),
            "symbols": symbols,
            "presets": [state.metadata.id for state in states],
            "initial_capital": float(config.get("initial_capital") or 10_000_000),
            "order_amount_per_stock": order_amount,
            "max_positions_per_strategy": max_positions,
            "min_signal_strength": min_strength,
            "costs": asdict(costs),
        },
        "data_coverage": coverage,
        "summaries": summaries,
        "trades": [
            asdict(trade) for ledger in ledgers.values() for trade in ledger.trades
        ],
        "equity_curves": {
            ledger.strategy_id: ledger.equity_curve for ledger in ledgers.values()
        },
    }


def _format_markdown(result: dict[str, Any]) -> str:
    exp = result["experiment"]
    lines = [
        f"# Stock Builder Preset Paper Experiment: {exp['id']}",
        "",
        f"- Window: {exp['start_date']} -> {exp['end_date']}",
        f"- Symbols: {len(exp['symbols'])}",
        f"- Presets: {len(exp['presets'])}",
        f"- Capital per preset: {exp['initial_capital']:,.0f} KRW",
        "",
        "| Rank | Strategy | Return % | Realized PnL | Unrealized PnL | Closed | Open | Win % | MDD % | Entries | Rejected |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for idx, summary in enumerate(result["summaries"], start=1):
        rejected = (
            summary["rejected_existing_position"]
            + summary["rejected_max_positions"]
            + summary["rejected_insufficient_cash"]
        )
        lines.append(
            "| "
            f"{idx} | {summary['strategy_id']} | {summary['total_return_pct']:.2f} | "
            f"{summary['realized_pnl']:,.0f} | {summary['unrealized_pnl']:,.0f} | "
            f"{summary['closed_trades']} | {summary['open_positions']} | "
            f"{summary['win_rate_pct']:.1f} | {summary['max_drawdown_pct']:.2f} | "
            f"{summary['admitted_entries']} | {rejected} |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(result: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    exp = result["experiment"]
    stamp = f"{exp['end_date'].replace('-', '')}_{datetime.now().strftime('%H%M%S')}"
    base = f"{exp['id']}_{stamp}"
    json_path = output_dir / f"{base}.json"
    md_path = output_dir / f"{base}.md"
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    md_path.write_text(_format_markdown(result), encoding="utf-8")
    return json_path, md_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="stock_builder_preset_experiment.yaml",
        help="Config path under config/ or a direct file path.",
    )
    parser.add_argument("--start-date", type=_as_date, default=None)
    parser.add_argument("--end-date", type=_as_date, default=None)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--print-json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_experiment_config(args.config)
    result = run_experiment(config, start=args.start_date, end=args.end_date)
    if args.print_json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    if not args.no_write:
        output_dir = Path(
            args.output_dir
            or config.get("output_dir")
            or "reports/stock_builder_preset_experiment"
        )
        json_path, md_path = write_outputs(result, output_dir)
        print(f"json={json_path}")
        print(f"markdown={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
