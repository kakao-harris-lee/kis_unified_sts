#!/usr/bin/env python3
"""Portfolio-style stock backtest for multi-symbol minute strategies.

This script runs a single BacktestEngine instance over an interleaved
multi-symbol minute stream (datetime, code order), so capital and position
limits are shared like a portfolio.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from shared.backtest import BacktestConfig, BacktestEngine  # noqa: E402
from shared.backtest.adapter import BacktestStrategyAdapter  # noqa: E402
from shared.backtest.config import RiskConfig  # noqa: E402
from shared.backtest.daily_adapter import (  # noqa: E402
    DailyBacktestAdapter,
    load_stock_daily_from_clickhouse,
)
from shared.backtest.engine import ExitReason, SignalType  # noqa: E402
from shared.collector.historical.stock import (  # noqa: E402
    STOCK_UNIVERSE,
    load_stock_minute_from_clickhouse,
)
from shared.config.loader import ConfigLoader  # noqa: E402
from shared.strategy.registry import (  # noqa: E402
    StrategyFactory,
    register_builtin_components,
)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _select_stocks(
    tier: str,
    *,
    symbols: str = "",
    max_symbols: int | None = None,
) -> list[dict[str, str]]:
    requested = [s.strip() for s in symbols.split(",") if s.strip()]
    if requested:
        by_code = {s["code"]: s for s in STOCK_UNIVERSE}
        stocks = [
            by_code.get(code, {"code": code, "name": code, "tier": "custom"})
            for code in requested
        ]
    elif tier == "all":
        stocks = list(STOCK_UNIVERSE)
    else:
        stocks = [s for s in STOCK_UNIVERSE if s["tier"] == tier]
    if max_symbols is not None and max_symbols > 0:
        return stocks[:max_symbols]
    return stocks


def _scope_label(
    tier: str, stocks: list[dict[str, str]], max_symbols: int | None
) -> str:
    if not stocks:
        return tier
    if max_symbols is not None and max_symbols > 0:
        prefix = f"{tier}_first{max_symbols}"
    else:
        prefix = tier
    codes = "_".join(str(s.get("code", "")) for s in stocks[:5])
    if len(stocks) > 5:
        codes = f"{codes}_plus{len(stocks) - 5}"
    return f"{prefix}_{codes}" if codes else prefix


def _daily_warmup_bars(strategy_config: dict[str, Any]) -> int:
    strategy = strategy_config.get("strategy", {})
    entry = strategy.get("entry", {})
    exit_ = strategy.get("exit", {})
    entry_type = str(entry.get("type", "") or "")
    exit_type = str(exit_.get("type", "") or "")
    entry_params = entry.get("params", {}) or {}
    exit_params = exit_.get("params", {}) or {}

    def int_param(params: dict[str, Any], key: str, default: int = 0) -> int:
        try:
            return int(params.get(key, default) or 0)
        except (TypeError, ValueError):
            return int(default)

    periods: list[int] = []
    if entry_type == "daily_pullback" or "sma_long_period" in entry_params:
        periods.extend(
            [
                int_param(entry_params, "sma_long_period", 200),
                int_param(entry_params, "sma_mid_period", 60)
                + int_param(entry_params, "mid_trend_lookback", 0),
                int_param(entry_params, "sma_short_period", 20),
                int_param(entry_params, "rsi_period", 5),
            ]
        )

    if (
        entry_type == "vr_composite"
        or "vr_period" in entry_params
        or "ma_long" in entry_params
    ):
        vr_period = int_param(entry_params, "vr_period", 20)
        ma_long = int_param(entry_params, "ma_long", 60)
        periods.extend(
            [
                vr_period + ma_long,
                ma_long,
                int_param(entry_params, "ma_mid", 20),
                int_param(entry_params, "ma_short", 5),
                int_param(entry_params, "rsi_period", 14),
            ]
        )

    if (
        entry_type == "technical_consensus"
        or "williams_r_period" in entry_params
        or "macd_slow" in entry_params
    ):
        macd_fast = int_param(entry_params, "macd_fast", 12)
        macd_slow = int_param(entry_params, "macd_slow", 26)
        macd_signal = int_param(entry_params, "macd_signal", 9)
        periods.extend(
            [
                int_param(entry_params, "rsi_period", 14) + 1,
                int_param(entry_params, "williams_r_period", 14) + 1,
                max(macd_fast, macd_slow) + macd_signal,
                int_param(entry_params, "volume_lookback", 20) + 1,
                20,
            ]
        )

    if exit_type == "chandelier_exit" or {"atr_period", "lookback_period"} & set(
        exit_params
    ):
        periods.extend(
            [
                int_param(exit_params, "atr_period", 22),
                int_param(exit_params, "lookback_period", 22),
            ]
        )

    if exit_type == "vr_composite_exit":
        vr_period = int_param(exit_params, "vr_period", 20)
        ma_long = int_param(exit_params, "ma_long", 60)
        periods.extend(
            [
                vr_period + ma_long,
                ma_long,
                int_param(exit_params, "ma_mid", 20),
                int_param(exit_params, "ma_short", 5),
                int_param(exit_params, "rsi_period", 14),
            ]
        )

    return max((int(p or 0) for p in periods), default=0)


def _daily_indicator_periods_from_keys(keys: list[str] | tuple[str, ...]) -> list[int]:
    periods: list[int] = []
    for raw in keys:
        key = str(raw or "")
        for prefix in ("daily_sma_", "daily_ema_", "daily_rsi_"):
            if key.startswith(prefix):
                try:
                    periods.append(int(key.removeprefix(prefix)))
                except ValueError:
                    pass
    return periods


def _default_warmup_days(strategy_config: dict[str, Any], timeframe: str) -> int:
    if timeframe != "daily":
        return 0
    bars = _daily_warmup_bars(strategy_config)
    # Convert trading bars to calendar days with room for weekends/holidays.
    return max(0, bars * 2)


def _daily_prewarm_days_for_minute_strategy(strategy: Any) -> int:
    periods = _daily_indicator_periods_from_keys(
        list(getattr(strategy, "required_indicators", []) or [])
    )
    if not periods:
        return 0
    return max(periods) * 2


def _seed_minute_strategy_daily_indicators(
    adapter: Any,
    stocks: list[dict[str, str]],
    *,
    start: date,
    end: date,
) -> list[str]:
    if not hasattr(adapter, "seed_daily_candles"):
        return []

    missing: list[str] = []
    for stock in stocks:
        code = stock["code"]
        try:
            daily_df = load_stock_daily_from_clickhouse(code, start, end)
        except Exception:
            missing.append(code)
            continue
        if daily_df is None or daily_df.empty:
            missing.append(code)
            continue
        adapter.seed_daily_candles(code, daily_df.to_dict("records"))
    return missing


def _annualized_return_pct(total_return_pct: float, start: date, end: date) -> float:
    days = max(1, (end - start).days)
    years = days / 365.0
    return ((1.0 + total_return_pct / 100.0) ** (1.0 / years) - 1.0) * 100.0


def _monthly_expected_return_pct(
    total_return_pct: float, data: pd.DataFrame, start: date
) -> float:
    dates = pd.to_datetime(data["datetime"]).dt.date
    eval_days = int(dates[dates >= start].nunique())
    if eval_days <= 0:
        return 0.0
    return total_return_pct * 21.0 / eval_days


def _realized_trade_metrics(
    trades: list[Any], initial_capital: float
) -> dict[str, Any]:
    """Split realized exits from forced end-of-data marks.

    Swing backtests mark still-open positions at the final bar using
    ``end_of_data``. That mark is useful for equity/MDD, but it is not a live
    closed trade and should not be used as the only win-rate proxy.
    """
    realized = [
        t for t in trades if str(getattr(t, "exit_reason", "")) != "end_of_data"
    ]
    end_of_data = [
        t for t in trades if str(getattr(t, "exit_reason", "")) == "end_of_data"
    ]

    realized_pnl = float(sum(float(getattr(t, "pnl", 0.0) or 0.0) for t in realized))
    end_of_data_pnl = float(
        sum(float(getattr(t, "pnl", 0.0) or 0.0) for t in end_of_data)
    )
    wins = sum(1 for t in realized if float(getattr(t, "pnl", 0.0) or 0.0) > 0.0)
    losses = sum(1 for t in realized if float(getattr(t, "pnl", 0.0) or 0.0) < 0.0)
    count = len(realized)
    capital = float(initial_capital or 0.0)
    return {
        "realized_trade_count": count,
        "realized_winning_trades": wins,
        "realized_losing_trades": losses,
        "realized_win_rate_pct": round((wins / count * 100.0) if count else 0.0, 2),
        "realized_total_pnl": round(realized_pnl, 0),
        "realized_return_pct": round(
            (realized_pnl / capital * 100.0) if capital > 0.0 else 0.0,
            2,
        ),
        "end_of_data_trade_count": len(end_of_data),
        "end_of_data_unrealized_pnl": round(end_of_data_pnl, 0),
        "end_of_data_unrealized_return_pct": round(
            (end_of_data_pnl / capital * 100.0) if capital > 0.0 else 0.0,
            2,
        ),
    }


def _parse_override_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    lowered = raw.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    return raw


def _apply_strategy_overrides(
    strategy_config: dict[str, Any], overrides: list[str]
) -> dict[str, Any]:
    """Apply dotted-path strategy overrides to a copied config.

    Paths are relative to the ``strategy`` section by default, so both
    ``entry.params.rsi_oversold=40`` and
    ``strategy.entry.params.rsi_oversold=40`` are valid.
    """
    cfg = copy.deepcopy(strategy_config)
    allowed_roots = {"entry", "exit", "position", "backtest", "paper", "indicators"}

    for item in overrides:
        if "=" not in item:
            raise ValueError(f"Override must be KEY=VALUE: {item!r}")
        raw_path, raw_value = item.split("=", 1)
        parts = [part.strip() for part in raw_path.split(".") if part.strip()]
        if not parts:
            raise ValueError(f"Override path is empty: {item!r}")
        if parts[0] == "strategy":
            parts = parts[1:]
        if not parts or parts[0] not in allowed_roots:
            raise ValueError(
                "Override path must start with one of "
                f"{sorted(allowed_roots)} or 'strategy.': {raw_path!r}"
            )

        target = cfg.setdefault("strategy", {})
        for part in parts[:-1]:
            next_target = target.setdefault(part, {})
            if not isinstance(next_target, dict):
                raise ValueError(f"Override path is not a mapping: {raw_path!r}")
            target = next_target
        target[parts[-1]] = _parse_override_value(raw_value)
    return cfg


def _build_backtest_config(
    strategy_config: dict[str, Any],
    initial_capital: float,
    *,
    order_amount_per_stock: float | None = None,
    max_positions: int | None = None,
) -> BacktestConfig:
    bt_override = strategy_config.get("strategy", {}).get("backtest", {})
    position_params = (
        strategy_config.get("strategy", {}).get("position", {}).get("params", {})
    )

    # CLI capital represents the portfolio/account size for the experiment.
    # Strategy YAML may keep legacy standalone defaults, but this portfolio
    # runner should honor the explicit command-line capital.
    bt_capital = float(initial_capital)
    bt_position_size_pct = float(bt_override.get("position_size_pct", 10.0) or 10.0)
    resolved_max_positions = int(position_params.get("max_positions", 5) or 5)
    resolved_order_amount = float(position_params.get("order_amount_per_stock", 0) or 0)
    if order_amount_per_stock is not None:
        resolved_order_amount = float(order_amount_per_stock)
    if max_positions is not None:
        resolved_max_positions = int(max_positions)
    if resolved_order_amount <= 0:
        resolved_order_amount = None

    config = BacktestConfig.stock(
        initial_capital=bt_capital,
        position_size_pct=bt_position_size_pct,
        order_amount_per_stock=resolved_order_amount,
        max_positions=resolved_max_positions,
    )
    if "risk" in bt_override:
        config.risk = RiskConfig.from_dict(bt_override["risk"])
    return config


class DailyPortfolioAdapter:
    """Route each symbol to its own DailyBacktestAdapter in a portfolio engine.

    DailyBacktestAdapter precomputes rolling indicators over one symbol. The
    portfolio engine feeds interleaved multi-symbol bars, so sharing one daily
    adapter would mix SMA/RSI/ATR windows across symbols.
    """

    def __init__(
        self,
        strategy_config: dict[str, Any],
        *,
        entry_start: datetime | None = None,
    ):
        strategy_name = strategy_config.get("strategy", {}).get(
            "name", "daily_strategy"
        )
        self.name = strategy_name
        self._strategy_config = strategy_config
        self._entry_start = entry_start
        self._adapters: dict[str, DailyBacktestAdapter] = {}
        self._pending_position: dict[str, Any] | None = None
        self.last_entry_signal = None

    def prescan_data(self, data: pd.DataFrame) -> None:
        if "code" not in data.columns:
            raise ValueError("Daily portfolio backtest requires a code column")

        self._adapters.clear()
        for code, group in data.groupby("code", sort=False):
            cfg = copy.deepcopy(self._strategy_config)
            strategy = StrategyFactory.create(cfg)
            adapter = DailyBacktestAdapter(
                strategy,
                cfg,
                entry_start=self._entry_start,
            )
            adapter.prescan_data(group.sort_values("datetime").reset_index(drop=True))
            self._adapters[str(code)] = adapter

    def set_position(self, position: dict[str, Any] | None) -> None:
        self._pending_position = position

    def _adapter_for_bar(self, bar: dict[str, Any]) -> DailyBacktestAdapter | None:
        code = str(bar.get("code", "") or "")
        adapter = self._adapters.get(code)
        if adapter is not None:
            adapter.set_position(self._pending_position)
        return adapter

    def check_exit(self, bar: dict[str, Any]):
        adapter = self._adapter_for_bar(bar)
        if adapter is None:
            return False, None
        return adapter.check_exit(bar)

    def on_bar(self, bar: dict[str, Any]):
        self.last_entry_signal = None
        adapter = self._adapter_for_bar(bar)
        if adapter is None:
            return SignalType.HOLD
        signal = adapter.on_bar(bar)
        self.last_entry_signal = getattr(adapter, "last_entry_signal", None)
        return signal


def _entry_signal_priority(signal: Any) -> tuple[float, float, str, str]:
    metadata = getattr(signal, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    raw_priority = metadata.get("entry_priority", metadata.get("pattern_priority"))
    if raw_priority is None:
        priority = 1_000_000.0
    else:
        try:
            priority = float(raw_priority)
        except (TypeError, ValueError):
            priority = 1_000_000.0
    try:
        confidence = float(getattr(signal, "confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return (
        priority,
        -confidence,
        str(getattr(signal, "strategy", "") or ""),
        str(getattr(signal, "code", "") or ""),
    )


class PriorityDailyPortfolioBacktestEngine(BacktestEngine):
    """Backtest daily portfolio entries in the same priority order as runtime.

    The shared engine processes interleaved rows in ``datetime, code`` order.
    For daily stock strategies this can admit alphabetical candidates first
    when several symbols trigger on the same date and position/capital limits
    bind. This engine keeps exit/risk processing per bar, then batches same-date
    entry signals and sorts by entry metadata before opening positions.
    """

    def run(self, data: pd.DataFrame):
        if data.empty:
            raise ValueError("Empty data provided")

        self._reset()
        sort_cols = ["datetime"] + (["code"] if "code" in data.columns else [])
        data = data.sort_values(sort_cols).reset_index(drop=True)

        if hasattr(self.strategy, "prescan_data"):
            self.strategy.prescan_data(data)

        for _, group in data.groupby("datetime", sort=False):
            bars = [
                dict(zip(data.columns, row))
                for row in group.itertuples(index=False, name=None)
            ]
            for bar in bars:
                self._process_bar_without_signal(bar)
            pending_entries = []
            for bar in bars:
                pending = self._collect_or_apply_signal(bar)
                if pending is not None:
                    pending_entries.append(pending)
            for pending in sorted(
                pending_entries,
                key=lambda item: _entry_signal_priority(item["entry_signal"]),
            ):
                risk = self.config.risk
                if (
                    risk.max_daily_trades > 0
                    and self._daily_trades >= risk.max_daily_trades
                ):
                    break
                code = pending["code"]
                if code in self.positions:
                    continue
                signal = pending["signal"]
                side = "BUY" if signal == SignalType.BUY else "SELL"
                self._open_position(
                    code=code,
                    name=pending["name"],
                    side=side,
                    price=pending["price"],
                    timestamp=pending["timestamp"],
                    bar=pending["bar"],
                    entry_signal=pending.get("entry_signal"),
                )

        if self.positions:
            last_bar = data.iloc[-1].to_dict()
            for code in list(self.positions.keys()):
                last_price = self._last_price_by_code.get(
                    code, float(last_bar["close"])
                )
                self._close_position(
                    code=code,
                    exit_price=last_price,
                    exit_time=last_bar["datetime"],
                    reason=ExitReason.END_OF_DATA,
                )

        if self._current_day_pnl != 0:
            self.daily_returns.append(self._current_day_pnl)

        return self._generate_result(data)

    def _process_bar_without_signal(self, bar: dict[str, Any]) -> None:
        timestamp = bar["datetime"]
        current_price = bar["close"]
        code = str(bar.get("code", "DEFAULT") or "DEFAULT")
        self._last_price_by_code[code] = float(current_price)

        if self._last_date and timestamp.date() != self._last_date.date():
            if self.config.risk.close_on_day_change and self.positions:
                for pos_code in list(self.positions.keys()):
                    self._close_position(
                        pos_code,
                        self._last_price_by_code.get(pos_code, float(current_price)),
                        timestamp,
                        ExitReason.FORCE_CLOSE,
                    )
            if self._current_day_pnl != 0:
                self.daily_returns.append(self._current_day_pnl)
            self._current_day_pnl = 0.0
            self._daily_trades = 0

        self._last_date = timestamp
        self.equity_curve.append((timestamp, self._calculate_total_equity()))

        current_pos = self.positions.get(code)
        if not current_pos:
            return

        current_pos.bars_held += 1
        if current_price > current_pos.highest_price:
            current_pos.highest_price = current_price
        if current_price < current_pos.lowest_price or current_pos.lowest_price == 0:
            current_pos.lowest_price = current_price

        if hasattr(self.strategy, "check_exit") and hasattr(
            self.strategy, "set_position"
        ):
            self.strategy.set_position(
                self._position_payload(current_pos, current_price)
            )
            should_exit, exit_reason = self.strategy.check_exit(bar)
            if should_exit and exit_reason:
                self._close_position(
                    code=code,
                    exit_price=current_price,
                    exit_time=timestamp,
                    reason=exit_reason,
                )
                current_pos = None

        if current_pos:
            exit_reason = self._check_risk(current_pos, current_price, timestamp)
            if exit_reason:
                self._close_position(
                    code=code,
                    exit_price=current_price,
                    exit_time=timestamp,
                    reason=exit_reason,
                )

    def _collect_or_apply_signal(self, bar: dict[str, Any]) -> dict[str, Any] | None:
        timestamp = bar["datetime"]
        current_price = bar["close"]
        code = str(bar.get("code", "DEFAULT") or "DEFAULT")
        name = bar.get("name", code)

        risk = self.config.risk
        if risk.max_daily_trades > 0 and self._daily_trades >= risk.max_daily_trades:
            return None

        current_pos = self.positions.get(code)
        if hasattr(self.strategy, "set_position"):
            self.strategy.set_position(
                self._position_payload(current_pos, current_price)
                if current_pos
                else None
            )

        signal = self.strategy.on_bar(bar)
        entry_signal = getattr(self.strategy, "last_entry_signal", None)

        if code not in self.positions:
            if signal in (SignalType.BUY, SignalType.SELL):
                return {
                    "bar": bar,
                    "code": code,
                    "name": name,
                    "price": current_price,
                    "timestamp": timestamp,
                    "signal": signal,
                    "entry_signal": entry_signal,
                }
            return None

        pos = self.positions[code]
        should_close = (pos.side == "BUY" and signal == SignalType.SELL) or (
            pos.side == "SELL" and signal == SignalType.BUY
        )
        if should_close:
            self._close_position(
                code=code,
                exit_price=current_price,
                exit_time=timestamp,
                reason=ExitReason.SIGNAL,
            )
        return None

    @staticmethod
    def _position_payload(position: Any, current_price: float) -> dict[str, Any]:
        if position.side == "BUY":
            unrealized_pnl = (current_price - position.entry_price) * position.quantity
        else:
            unrealized_pnl = (position.entry_price - current_price) * position.quantity
        return {
            "code": position.code,
            "side": position.side,
            "entry_price": position.entry_price,
            "quantity": position.quantity,
            "unrealized_pnl": unrealized_pnl,
            "highest_price": position.highest_price,
            "lowest_price": position.lowest_price,
            "entry_time": position.entry_time,
            "metadata": dict(getattr(position, "metadata", {}) or {}),
        }


def _load_symbol_data(
    *,
    code: str,
    name: str,
    timeframe: str,
    start: date,
    end: date,
) -> pd.DataFrame | None:
    if timeframe == "daily":
        df = load_stock_daily_from_clickhouse(code, start, end)
    else:
        df = load_stock_minute_from_clickhouse(code, start, end)

    if df is None or df.empty:
        return None

    cols = ["datetime", "open", "high", "low", "close", "volume", "code", "name"]
    for col in cols:
        if col not in df.columns:
            if col == "code":
                df[col] = code
            elif col == "name":
                df[col] = name
    return df[cols].copy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run portfolio-style stock backtest.")
    parser.add_argument(
        "--strategy", required=True, help="Strategy name (stock minute only)"
    )
    parser.add_argument(
        "--tier", default="all", choices=["top", "mid", "bottom", "all"]
    )
    parser.add_argument(
        "--symbols",
        default="",
        help="Comma-separated stock codes to run. Overrides --tier when set.",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=None,
        help="Limit selected symbols for faster smoke/parameter experiments.",
    )
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=100_000_000)
    parser.add_argument(
        "--warmup-days",
        type=int,
        default=None,
        help=(
            "Calendar days to load before --start for indicator warmup. "
            "Defaults to 2x the largest daily indicator period for daily strategies."
        ),
    )
    parser.add_argument(
        "--order-amount-per-stock",
        type=float,
        default=None,
        help="Override stock fixed order amount from strategy YAML.",
    )
    parser.add_argument(
        "--max-positions",
        type=int,
        default=None,
        help="Override max concurrent positions from strategy YAML.",
    )
    parser.add_argument(
        "--set",
        dest="strategy_overrides",
        action="append",
        default=[],
        metavar="PATH=VALUE",
        help=(
            "Override a strategy config value for this run, e.g. "
            "--set entry.params.rsi_oversold=40 or "
            "--set exit.params.hard_stop_pct=-0.05"
        ),
    )
    parser.add_argument("--output-dir", default="output/analysis/portfolio_backtest")
    args = parser.parse_args()

    start = _parse_date(args.start)
    end = _parse_date(args.end)
    if end < start:
        raise SystemExit("end must be >= start")

    register_builtin_components()
    strategy_config = ConfigLoader.load_strategy("stock", args.strategy)
    strategy_config = _apply_strategy_overrides(
        strategy_config, args.strategy_overrides
    )
    timeframe = strategy_config.get("strategy", {}).get("timeframe", "minute")
    if timeframe not in ("minute", "daily"):
        raise SystemExit(f"Unsupported timeframe for '{args.strategy}': {timeframe}")
    warmup_days = (
        _default_warmup_days(strategy_config, timeframe)
        if args.warmup_days is None
        else max(0, int(args.warmup_days))
    )
    data_start = start - timedelta(days=warmup_days)

    stocks = _select_stocks(
        args.tier,
        symbols=args.symbols,
        max_symbols=args.max_symbols,
    )
    if not stocks:
        raise SystemExit("No stocks selected")

    frames: list[pd.DataFrame] = []
    missing: list[str] = []
    for s in stocks:
        code = s["code"]
        try:
            df = _load_symbol_data(
                code=code,
                name=s["name"],
                timeframe=timeframe,
                start=data_start,
                end=end,
            )
        except Exception:
            missing.append(code)
            continue
        if df is None:
            missing.append(code)
            continue
        frames.append(df)

    if not frames:
        raise SystemExit("No symbol data loaded")

    data = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["datetime", "code"])
        .reset_index(drop=True)
    )

    config = _build_backtest_config(
        strategy_config,
        initial_capital=args.capital,
        order_amount_per_stock=args.order_amount_per_stock,
        max_positions=args.max_positions,
    )
    if timeframe == "daily":
        adapted = DailyPortfolioAdapter(
            strategy_config,
            entry_start=datetime.combine(start, time.min),
        )
        engine = PriorityDailyPortfolioBacktestEngine(adapted, config)
    else:
        strategy = StrategyFactory.create(strategy_config)
        adapted = BacktestStrategyAdapter(strategy, strategy_config)
        daily_prewarm_days = _daily_prewarm_days_for_minute_strategy(strategy)
        if daily_prewarm_days:
            daily_missing = _seed_minute_strategy_daily_indicators(
                adapted,
                stocks,
                start=start - timedelta(days=daily_prewarm_days),
                end=end,
            )
        else:
            daily_missing = []
        engine = BacktestEngine(adapted, config)
    result = engine.run(data)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    scope = _scope_label(args.tier, stocks, args.max_symbols)
    tag = f"{args.strategy}_{scope}_{args.start}_{args.end}_{stamp}"
    metrics_path = output_dir / f"{tag}_metrics.json"
    trades_path = output_dir / f"{tag}_trades.csv"

    metrics = result.to_dict()
    metrics["strategy"] = args.strategy
    metrics["timeframe"] = timeframe
    metrics["tier"] = args.tier
    metrics["start"] = args.start
    metrics["end"] = args.end
    metrics["data_start"] = data_start.isoformat()
    metrics["warmup_days"] = warmup_days
    metrics["evaluation_annualized_return"] = round(
        _annualized_return_pct(result.total_return_pct, start, end), 2
    )
    metrics["monthly_expected_return_pct"] = round(
        _monthly_expected_return_pct(result.total_return_pct, data, start), 2
    )
    metrics["realized_trade_metrics"] = _realized_trade_metrics(
        result.trades,
        config.initial_capital,
    )
    if hasattr(adapted, "get_regime_stats"):
        metrics["backtest_adapter_stats"] = adapted.get_regime_stats()
    metrics["symbols_requested"] = len(stocks)
    metrics["symbols_loaded"] = len(frames)
    metrics["symbols_missing"] = missing
    metrics["daily_indicator_symbols_missing"] = (
        daily_missing if timeframe != "daily" else []
    )
    metrics["symbols_selected"] = [s["code"] for s in stocks]
    metrics["scope_label"] = scope
    metrics["bars"] = len(data)
    metrics["config"] = config.to_dict()
    metrics["strategy_overrides"] = args.strategy_overrides
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    trades_df = pd.DataFrame([t.to_dict() for t in result.trades])
    if not trades_df.empty:
        trades_df.to_csv(trades_path, index=False)
    else:
        trades_path.write_text(
            "code,name,strategy,side,entry_time,exit_time,entry_price,exit_price,quantity,pnl,pnl_pct,commission,exit_reason\n",
            encoding="utf-8",
        )

    print(f"strategy={args.strategy} tier={args.tier} period={args.start}~{args.end}")
    if warmup_days:
        print(f"data_start={data_start.isoformat()} warmup_days={warmup_days}")
    print(
        f"symbols_loaded={len(frames)}/{len(stocks)} bars={len(data)} trades={result.total_trades}"
    )
    print(
        f"return={result.total_return_pct:+.3f}% sharpe={result.sharpe_ratio:.3f} "
        f"mdd={result.max_drawdown_pct:.3f}% win_rate={result.win_rate:.2f}%"
    )
    print(
        f"monthly_expected={metrics['monthly_expected_return_pct']:+.2f}% "
        f"eval_annualized={metrics['evaluation_annualized_return']:+.2f}%"
    )
    print(f"metrics={metrics_path}")
    print(f"trades={trades_path}")


if __name__ == "__main__":
    main()
