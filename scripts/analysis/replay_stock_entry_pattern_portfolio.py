#!/usr/bin/env python3
"""Replay scanned stock entry patterns with portfolio constraints.

The entry scanner ranks raw close-to-close forward returns. This replay keeps the
same signal definitions, then adds shared capital, position limits, fixed order
size, and trading costs so we can see whether the edge survives the portfolio
layer before wiring a strategy.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from scripts.analysis.scan_stock_entry_patterns import (  # noqa: E402
    Loader,
    PatternResult,
    ScanTargets,
    _as_list,
    _compute_features,
    _evaluate_signals,
    _mask_for_conditions,
    _parse_date,
    _pattern_param_sets,
    _select_stocks,
)
from shared.backtest.daily_adapter import load_stock_daily_from_parquet  # noqa: E402
from shared.config.loader import ConfigLoader  # noqa: E402


@dataclass(frozen=True)
class ReplayCosts:
    commission_rate: float
    slippage_rate: float
    tax_rate: float

    @property
    def entry_rate(self) -> float:
        return self.commission_rate + self.slippage_rate

    @property
    def exit_rate(self) -> float:
        return self.commission_rate + self.slippage_rate + self.tax_rate


@dataclass(frozen=True)
class ReplaySpec:
    hold_days: int
    initial_capital: float
    order_amount_per_stock: float
    max_positions: int
    max_daily_entries: int
    costs: ReplayCosts
    require_complete_horizon: bool
    entry_sort: str

    @property
    def run_id(self) -> str:
        return (
            f"hold={self.hold_days}|order={self.order_amount_per_stock:.0f}|"
            f"maxpos={self.max_positions}|sort={self.entry_sort}"
        )


@dataclass
class ReplayTrade:
    run_id: str
    code: str
    name: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    exit_reason: str


@dataclass
class ReplayResult:
    run_id: str
    hold_days: int
    order_amount_per_stock: float
    max_positions: int
    max_daily_entries: int
    total_signals: int
    completed_signal_candidates: int
    admitted_trades: int
    skipped_incomplete_horizon: int
    rejected_existing_position: int
    rejected_max_positions: int
    rejected_max_daily_entries: int
    rejected_insufficient_cash: int
    final_capital: float
    total_return_pct: float
    monthly_expected_return_pct: float
    win_rate_pct: float
    max_drawdown_pct: float
    equity_slope: float
    equity_is_upward: bool
    avg_deployed_pct: float
    avg_pnl_pct: float
    median_pnl_pct: float
    profit_factor: float
    trades: list[ReplayTrade]


LoaderWithSummary = Callable[
    [dict[str, Any], tuple[int, ...], Loader], tuple[pd.DataFrame, dict[str, Any]]
]


def _load_replay_config(path: str) -> dict[str, Any]:
    cfg = ConfigLoader.load(path, use_cache=False)
    if not isinstance(cfg, dict):
        raise ValueError(f"Config did not load as a mapping: {path}")
    replay = cfg.get("replay", cfg)
    if not isinstance(replay, dict):
        raise ValueError(f"Replay config is not a mapping: {path}")
    return replay


def _load_scan_config(path: str) -> dict[str, Any]:
    cfg = ConfigLoader.load(path, use_cache=False)
    if not isinstance(cfg, dict):
        raise ValueError(f"Config did not load as a mapping: {path}")
    scan = cfg.get("scan", cfg)
    if not isinstance(scan, dict):
        raise ValueError(f"Scan config is not a mapping: {path}")
    return scan


def _float_list(value: Any) -> list[float]:
    return [float(v) for v in _as_list(value) if v not in (None, "")]


def _int_list(value: Any) -> list[int]:
    return [int(v) for v in _as_list(value) if v not in (None, "")]


def _load_feature_data(
    scan_config: dict[str, Any],
    *,
    horizons: tuple[int, ...],
    loader: Loader = load_stock_daily_from_parquet,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    start = _parse_date(str(scan_config["start"]))
    end = _parse_date(str(scan_config["end"]))
    warmup_days = int(scan_config.get("warmup_days") or 0)
    data_start = start - timedelta(days=warmup_days)
    stocks = _select_stocks(
        str(scan_config.get("tier") or "all"),
        symbols=str(scan_config.get("symbols") or ""),
        max_symbols=(
            int(scan_config["max_symbols"])
            if scan_config.get("max_symbols") not in (None, "")
            else None
        ),
    )

    frames: list[pd.DataFrame] = []
    missing: list[str] = []
    for stock in stocks:
        code = str(stock["code"])
        try:
            raw = loader(code, data_start, end)
        except Exception:
            missing.append(code)
            continue
        if raw is None or raw.empty:
            missing.append(code)
            continue
        df = raw.copy()
        df["code"] = code
        df["name"] = str(stock.get("name") or code)
        features = _compute_features(df, horizons)
        features = features[pd.to_datetime(features["datetime"]).dt.date >= start]
        frames.append(features)

    summary = {
        "symbols_requested": len(stocks),
        "symbols_loaded": len(frames),
        "symbols_missing": missing,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "data_start": data_start.isoformat(),
        "rows": 0,
    }
    if not frames:
        return pd.DataFrame(), summary

    data = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["datetime", "code"])
        .reset_index(drop=True)
    )
    data["date"] = pd.to_datetime(data["datetime"]).dt.date
    data["bar_index"] = data.groupby("code").cumcount()
    for hold_days in horizons:
        data[f"exit_datetime_{hold_days}d"] = data.groupby("code")["datetime"].shift(
            -hold_days
        )
        data[f"exit_close_{hold_days}d"] = data.groupby("code")["close"].shift(
            -hold_days
        )
    summary["rows"] = int(len(data))
    return data, summary


def _rank_patterns(
    data: pd.DataFrame,
    scan_config: dict[str, Any],
    *,
    horizons: tuple[int, ...],
) -> list[PatternResult]:
    if data.empty:
        return []
    start = _parse_date(str(scan_config["start"]))
    end = _parse_date(str(scan_config["end"]))
    targets = ScanTargets(
        min_signals=int(scan_config.get("min_signals") or 20),
        horizons=horizons,
        rank_horizon=int(scan_config.get("rank_horizon") or horizons[0]),
        round_trip_cost_pct=float(scan_config.get("round_trip_cost_pct") or 0.0),
    )
    results: list[PatternResult] = []
    for pattern in scan_config.get("patterns", []):
        for params in _pattern_param_sets(pattern):
            signals = data[_mask_for_conditions(data, params)].copy()
            result = _evaluate_signals(
                signals,
                pattern=pattern,
                params=params,
                targets=targets,
                start=start,
                end=end,
            )
            if result is not None:
                results.append(result)

    results.sort(
        key=lambda r: (
            -r.score,
            -r.rank_avg_net_return_pct,
            -r.rank_win_rate_pct,
            -r.signals,
            r.name,
        )
    )
    return results


def _select_pattern(
    results: list[PatternResult],
    *,
    pattern_rank: int,
    pattern_name: str,
) -> PatternResult:
    if pattern_name:
        for result in results:
            if result.name == pattern_name:
                return result
        raise ValueError(f"Pattern not found: {pattern_name}")
    if pattern_rank <= 0:
        raise ValueError("pattern_rank must be positive")
    if pattern_rank > len(results):
        raise ValueError(
            f"pattern_rank={pattern_rank} exceeds available results={len(results)}"
        )
    return results[pattern_rank - 1]


def _string_list(value: Any) -> list[str]:
    return [str(v) for v in _as_list(value) if v not in (None, "")]


def _selected_patterns_from_config(
    results: list[PatternResult],
    replay_config: dict[str, Any],
) -> list[PatternResult]:
    pattern_names = _string_list(replay_config.get("pattern_names"))
    pattern_name = str(replay_config.get("pattern_name") or "")
    if pattern_name:
        pattern_names.insert(0, pattern_name)

    selected: list[PatternResult] = []
    selected_keys: set[tuple[str, str]] = set()

    def append_once(pattern: PatternResult) -> None:
        key = (pattern.name, json.dumps(pattern.params, sort_keys=True))
        if key not in selected_keys:
            selected.append(pattern)
            selected_keys.add(key)

    for name in pattern_names:
        matches = [result for result in results if result.name == name]
        if not matches:
            raise ValueError(f"Pattern not found: {name}")
        for match in matches:
            append_once(match)

    pattern_ranks = _int_list(replay_config.get("pattern_ranks"))
    pattern_rank = int(replay_config.get("pattern_rank") or 0)
    if pattern_rank > 0:
        pattern_ranks.insert(0, pattern_rank)
    top_count = int(replay_config.get("top_pattern_count") or 0)
    if top_count > 0:
        pattern_ranks.extend(range(1, top_count + 1))

    for rank in pattern_ranks:
        if rank <= 0:
            raise ValueError("pattern ranks must be positive")
        if rank > len(results):
            raise ValueError(
                f"pattern_rank={rank} exceeds available results={len(results)}"
            )
        append_once(results[rank - 1])

    if not selected:
        append_once(_select_pattern(results, pattern_rank=1, pattern_name=""))
    return selected


def _pattern_label(patterns: list[PatternResult]) -> str:
    if len(patterns) == 1:
        return patterns[0].name
    names = []
    seen = set()
    for pattern in patterns:
        if pattern.name not in seen:
            names.append(pattern.name)
            seen.add(pattern.name)
    return f"combo_{len(patterns)}:" + ",".join(names)


def _signals_for_pattern(
    data: pd.DataFrame,
    pattern: PatternResult,
    *,
    hold_days: int,
    require_complete_horizon: bool,
) -> tuple[pd.DataFrame, int]:
    signals = data[_mask_for_conditions(data, pattern.params)].copy()
    exit_time_col = f"exit_datetime_{hold_days}d"
    exit_close_col = f"exit_close_{hold_days}d"
    signals["exit_datetime"] = signals[exit_time_col]
    signals["exit_close"] = signals[exit_close_col]
    incomplete = int(signals["exit_close"].isna().sum())
    if require_complete_horizon:
        signals = signals.dropna(subset=["exit_datetime", "exit_close"])
    signals = signals.sort_values(["datetime", "code"]).reset_index(drop=True)
    return signals, incomplete


def _signals_for_patterns(
    data: pd.DataFrame,
    patterns: list[PatternResult],
    *,
    hold_days: int,
    require_complete_horizon: bool,
) -> tuple[pd.DataFrame, int, int]:
    frames: list[pd.DataFrame] = []
    incomplete = 0
    raw_signal_count = 0
    for priority, pattern in enumerate(patterns, start=1):
        signals, missing = _signals_for_pattern(
            data,
            pattern,
            hold_days=hold_days,
            require_complete_horizon=require_complete_horizon,
        )
        raw_signal_count += len(data[_mask_for_conditions(data, pattern.params)])
        incomplete += missing
        if signals.empty:
            continue
        signals = signals.copy()
        signals["pattern_name"] = pattern.name
        signals["pattern_priority"] = priority
        signals["pattern_score"] = pattern.score
        signals["pattern_rank_win_rate_pct"] = pattern.rank_win_rate_pct
        signals["pattern_rank_avg_net_return_pct"] = pattern.rank_avg_net_return_pct
        frames.append(signals)

    if not frames:
        return pd.DataFrame(), incomplete, raw_signal_count

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(
        ["datetime", "code", "pattern_priority", "pattern_score"],
        ascending=[True, True, True, False],
    )
    combined = combined.drop_duplicates(
        subset=["datetime", "code"],
        keep="first",
    )
    combined = combined.sort_values(["datetime", "code"]).reset_index(drop=True)
    return combined, incomplete, raw_signal_count


def _sort_daily_signals(signals: pd.DataFrame, entry_sort: str) -> pd.DataFrame:
    if signals.empty:
        return signals
    sort_map = {
        "code": (["code"], [True]),
        "pattern_priority": (["pattern_priority", "code"], [True, True]),
        "pattern_score_desc": (["pattern_score", "code"], [False, True]),
        "volume_ratio_desc": (["volume_ratio", "code"], [False, True]),
        "rsi5_asc": (["rsi5", "code"], [True, True]),
        "atr_pct_desc": (["atr_pct", "code"], [False, True]),
    }
    if entry_sort not in sort_map:
        raise ValueError(
            "entry_sort must be one of "
            f"{', '.join(sorted(sort_map))}: {entry_sort!r}"
        )
    by, ascending = sort_map[entry_sort]
    return signals.sort_values(by, ascending=ascending)


def _max_drawdown_pct(equity_values: list[float]) -> float:
    peak = equity_values[0] if equity_values else 0.0
    max_dd = 0.0
    for value in equity_values:
        if value > peak:
            peak = value
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak * 100.0)
    return float(max_dd)


def _profit_factor(pnls: list[float]) -> float:
    gains = sum(p for p in pnls if p > 0)
    losses = abs(sum(p for p in pnls if p < 0))
    if losses == 0.0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def replay_signals(
    data: pd.DataFrame,
    pattern: PatternResult,
    spec: ReplaySpec,
) -> ReplayResult:
    return replay_pattern_set(data, [pattern], spec)


def replay_pattern_set(
    data: pd.DataFrame,
    patterns: list[PatternResult],
    spec: ReplaySpec,
) -> ReplayResult:
    signals, incomplete, total_signals = _signals_for_patterns(
        data,
        patterns,
        hold_days=spec.hold_days,
        require_complete_horizon=spec.require_complete_horizon,
    )
    close_lookup = {
        (str(row.code), row.date): float(row.close)
        for row in data[["code", "date", "close"]].itertuples(index=False)
    }
    signals_by_date = dict(signals.groupby(pd.to_datetime(signals["datetime"]).dt.date))
    trading_dates = sorted(data["date"].unique())

    cash = float(spec.initial_capital)
    positions: dict[str, dict[str, Any]] = {}
    trades: list[ReplayTrade] = []
    equity_values: list[float] = [float(spec.initial_capital)]
    deployed_values: list[float] = []

    rejected_existing = 0
    rejected_max_positions = 0
    rejected_max_daily = 0
    rejected_cash = 0

    def mark_to_market(day: date) -> tuple[float, float]:
        market_value = 0.0
        for code, position in positions.items():
            mark = close_lookup.get((code, day), float(position["entry_price"]))
            market_value += float(position["quantity"]) * mark
        return cash + market_value, market_value

    for day in trading_dates:
        due_codes = [
            code
            for code, position in positions.items()
            if pd.to_datetime(position["exit_datetime"]).date() <= day
        ]
        for code in sorted(due_codes):
            position = positions.pop(code)
            exit_price = float(position["exit_price"])
            revenue = exit_price * int(position["quantity"])
            exit_cost = revenue * spec.costs.exit_rate
            net_revenue = revenue - exit_cost
            cash += net_revenue
            entry_notional = float(position["entry_price"]) * int(position["quantity"])
            pnl = net_revenue - entry_notional
            pnl_pct = (
                (exit_price - float(position["entry_price"]))
                / float(position["entry_price"])
                * 100.0
            )
            trades.append(
                ReplayTrade(
                    run_id=spec.run_id,
                    code=code,
                    name=str(position["name"]),
                    entry_date=pd.to_datetime(position["entry_datetime"])
                    .date()
                    .isoformat(),
                    exit_date=pd.to_datetime(position["exit_datetime"])
                    .date()
                    .isoformat(),
                    entry_price=float(position["entry_price"]),
                    exit_price=exit_price,
                    quantity=int(position["quantity"]),
                    pnl=float(pnl),
                    pnl_pct=float(pnl_pct),
                    exit_reason=f"hold_{spec.hold_days}d",
                )
            )

        daily_entries = 0
        daily_signals = signals_by_date.get(day)
        if daily_signals is not None:
            for row in _sort_daily_signals(daily_signals, spec.entry_sort).itertuples(
                index=False
            ):
                code = str(row.code)
                if code in positions:
                    rejected_existing += 1
                    continue
                if len(positions) >= spec.max_positions:
                    rejected_max_positions += 1
                    continue
                if (
                    spec.max_daily_entries > 0
                    and daily_entries >= spec.max_daily_entries
                ):
                    rejected_max_daily += 1
                    continue
                entry_price = float(row.close)
                effective_price = entry_price * (1.0 + spec.costs.entry_rate)
                position_value = min(float(spec.order_amount_per_stock), cash)
                quantity = int(position_value / effective_price)
                if quantity < 1:
                    rejected_cash += 1
                    continue
                total_cost = quantity * effective_price
                if total_cost > cash:
                    rejected_cash += 1
                    continue
                cash -= total_cost
                positions[code] = {
                    "name": str(row.name),
                    "entry_datetime": row.datetime,
                    "exit_datetime": row.exit_datetime,
                    "entry_price": entry_price,
                    "exit_price": float(row.exit_close),
                    "quantity": quantity,
                }
                daily_entries += 1

        equity, deployed = mark_to_market(day)
        equity_values.append(float(equity))
        deployed_values.append(float(deployed))

    if positions:
        last_day = trading_dates[-1]
        for code, position in sorted(positions.items()):
            exit_price = close_lookup.get(
                (code, last_day), float(position["entry_price"])
            )
            revenue = exit_price * int(position["quantity"])
            exit_cost = revenue * spec.costs.exit_rate
            net_revenue = revenue - exit_cost
            cash += net_revenue
            entry_notional = float(position["entry_price"]) * int(position["quantity"])
            pnl = net_revenue - entry_notional
            pnl_pct = (
                (exit_price - float(position["entry_price"]))
                / float(position["entry_price"])
                * 100.0
            )
            trades.append(
                ReplayTrade(
                    run_id=spec.run_id,
                    code=code,
                    name=str(position["name"]),
                    entry_date=pd.to_datetime(position["entry_datetime"])
                    .date()
                    .isoformat(),
                    exit_date=last_day.isoformat(),
                    entry_price=float(position["entry_price"]),
                    exit_price=float(exit_price),
                    quantity=int(position["quantity"]),
                    pnl=float(pnl),
                    pnl_pct=float(pnl_pct),
                    exit_reason="end_of_data",
                )
            )
        positions.clear()
        equity_values.append(float(cash))

    total_return_pct = (cash - spec.initial_capital) / spec.initial_capital * 100.0
    eval_days = max(1, len(trading_dates))
    monthly_expected = total_return_pct * 21.0 / eval_days
    pnls = [trade.pnl for trade in trades]
    pnl_pcts = [trade.pnl_pct for trade in trades]
    wins = sum(1 for pnl in pnls if pnl > 0)
    win_rate = wins / len(trades) * 100.0 if trades else 0.0
    if len(equity_values) >= 2:
        slope = float(np.polyfit(range(len(equity_values)), equity_values, 1)[0])
    else:
        slope = 0.0

    return ReplayResult(
        run_id=spec.run_id,
        hold_days=spec.hold_days,
        order_amount_per_stock=spec.order_amount_per_stock,
        max_positions=spec.max_positions,
        max_daily_entries=spec.max_daily_entries,
        total_signals=total_signals,
        completed_signal_candidates=len(signals),
        admitted_trades=len(trades),
        skipped_incomplete_horizon=incomplete if spec.require_complete_horizon else 0,
        rejected_existing_position=rejected_existing,
        rejected_max_positions=rejected_max_positions,
        rejected_max_daily_entries=rejected_max_daily,
        rejected_insufficient_cash=rejected_cash,
        final_capital=float(cash),
        total_return_pct=float(total_return_pct),
        monthly_expected_return_pct=float(monthly_expected),
        win_rate_pct=float(win_rate),
        max_drawdown_pct=_max_drawdown_pct(equity_values),
        equity_slope=slope,
        equity_is_upward=bool(slope > 0 and cash > spec.initial_capital),
        avg_deployed_pct=(
            float(np.mean(deployed_values) / spec.initial_capital * 100.0)
            if deployed_values
            else 0.0
        ),
        avg_pnl_pct=float(np.mean(pnl_pcts)) if pnl_pcts else 0.0,
        median_pnl_pct=float(np.median(pnl_pcts)) if pnl_pcts else 0.0,
        profit_factor=_profit_factor(pnls),
        trades=trades,
    )


def _specs_from_config(replay_config: dict[str, Any]) -> list[ReplaySpec]:
    costs_cfg = replay_config.get("costs", {}) or {}
    costs = ReplayCosts(
        commission_rate=float(costs_cfg.get("commission_rate", 0.0) or 0.0),
        slippage_rate=float(costs_cfg.get("slippage_rate", 0.0) or 0.0),
        tax_rate=float(costs_cfg.get("tax_rate", 0.0) or 0.0),
    )
    hold_days = _int_list(replay_config.get("hold_days") or [10])
    order_amounts = _float_list(replay_config.get("order_amount_per_stock") or [0])
    max_positions = _int_list(replay_config.get("max_positions") or [1])
    max_daily_entries = int(replay_config.get("max_daily_entries") or 0)
    initial_capital = float(replay_config.get("initial_capital") or 100_000_000)
    require_complete_horizon = bool(replay_config.get("require_complete_horizon", True))
    entry_sorts = _string_list(replay_config.get("entry_sort") or "code")

    specs = []
    for hold, amount, max_pos, entry_sort in itertools.product(
        hold_days,
        order_amounts,
        max_positions,
        entry_sorts,
    ):
        specs.append(
            ReplaySpec(
                hold_days=hold,
                initial_capital=initial_capital,
                order_amount_per_stock=amount,
                max_positions=max_pos,
                max_daily_entries=max_daily_entries,
                costs=costs,
                require_complete_horizon=require_complete_horizon,
                entry_sort=entry_sort,
            )
        )
    return specs


def run_replay(
    replay_config: dict[str, Any],
    *,
    loader: Loader = load_stock_daily_from_parquet,
) -> tuple[list[ReplayResult], list[PatternResult], dict[str, Any]]:
    scan_config = _load_scan_config(
        str(replay_config.get("scan_config") or "stock_entry_pattern_scan.yaml")
    )
    specs = _specs_from_config(replay_config)
    horizons = tuple(sorted({spec.hold_days for spec in specs}))
    data, summary = _load_feature_data(scan_config, horizons=horizons, loader=loader)
    pattern_results = _rank_patterns(data, scan_config, horizons=horizons)
    if not pattern_results:
        raise ValueError("No ranked patterns available for replay")
    selected = _selected_patterns_from_config(pattern_results, replay_config)
    results = [replay_pattern_set(data, selected, spec) for spec in specs]
    results.sort(
        key=lambda r: (
            -r.monthly_expected_return_pct,
            -r.win_rate_pct,
            r.max_drawdown_pct,
            -r.admitted_trades,
        )
    )
    summary.update(
        {
            "scan_config": str(
                replay_config.get("scan_config") or "stock_entry_pattern_scan.yaml"
            ),
            "pattern_rank": int(replay_config.get("pattern_rank") or 0),
            "pattern_count": len(selected),
            "pattern_label": _pattern_label(selected),
            "pattern_names": [pattern.name for pattern in selected],
            "patterns": [asdict(pattern) for pattern in selected],
            "rank_horizon": selected[0].rank_horizon,
            "rank_win_rate_pct": selected[0].rank_win_rate_pct,
            "rank_avg_net_return_pct": selected[0].rank_avg_net_return_pct,
            "runs": len(results),
        }
    )
    return results, selected, summary


def _format_markdown(
    results: list[ReplayResult],
    patterns: list[PatternResult],
    summary: dict[str, Any],
) -> str:
    primary = patterns[0]
    lines = [
        "# Stock Entry Pattern Portfolio Replay",
        "",
        f"- Generated at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Period: `{summary['start']}~{summary['end']}`",
        f"- Symbols loaded: `{summary['symbols_loaded']}/{summary['symbols_requested']}`",
        f"- Pattern set: `{summary.get('pattern_label') or _pattern_label(patterns)}`",
        f"- Pattern count: `{len(patterns)}`",
        f"- Primary raw rank horizon: `{primary.rank_horizon}d`",
        f"- Primary raw rank win/avg net: `{primary.rank_win_rate_pct:.2f}% / {primary.rank_avg_net_return_pct:.2f}%`",
        "",
        "| Rank | Run | Trades | Monthly | Win | MDD | Upward | Avg deployed | Rej maxpos | Rej cash |",
        "|---:|---|---:|---:|---:|---:|---|---:|---:|---:|",
    ]
    for idx, result in enumerate(results, start=1):
        upward = "yes" if result.equity_is_upward else "no"
        lines.append(
            f"| {idx} | `{result.run_id}` | {result.admitted_trades} | "
            f"{result.monthly_expected_return_pct:.2f}% | "
            f"{result.win_rate_pct:.2f}% | {result.max_drawdown_pct:.2f}% | "
            f"{upward} | {result.avg_deployed_pct:.2f}% | "
            f"{result.rejected_max_positions} | {result.rejected_insufficient_cash} |"
        )
    lines.append("")
    lines.append("## Patterns")
    lines.append("")
    lines.append("| Rank | Pattern | Signals | Win | Avg net | Params |")
    lines.append("|---:|---|---:|---:|---:|---|")
    for idx, pattern in enumerate(patterns, start=1):
        params = json.dumps(pattern.params, ensure_ascii=False, sort_keys=True)
        lines.append(
            f"| {idx} | `{pattern.name}` | {pattern.signals} | "
            f"{pattern.rank_win_rate_pct:.2f}% | "
            f"{pattern.rank_avg_net_return_pct:.2f}% | `{params}` |"
        )
    return "\n".join(lines)


def write_outputs(
    results: list[ReplayResult],
    patterns: list[PatternResult] | PatternResult,
    summary: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    pattern_list = patterns if isinstance(patterns, list) else [patterns]
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"stock_entry_pattern_replay_{stamp}.json"
    md_path = output_dir / f"stock_entry_pattern_replay_{stamp}.md"
    trades_path = output_dir / f"stock_entry_pattern_replay_{stamp}_trades.csv"

    payload = {
        "summary": summary,
        "pattern": asdict(pattern_list[0]),
        "patterns": [asdict(pattern) for pattern in pattern_list],
        "results": [
            {
                **{
                    key: value
                    for key, value in asdict(result).items()
                    if key != "trades"
                },
                "trade_count": len(result.trades),
            }
            for result in results
        ],
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        _format_markdown(results, pattern_list, summary),
        encoding="utf-8",
    )

    trade_rows = [asdict(trade) for result in results for trade in result.trades]
    if trade_rows:
        pd.DataFrame(trade_rows).to_csv(trades_path, index=False)
    else:
        trades_path.write_text(
            "run_id,code,name,entry_date,exit_date,entry_price,exit_price,quantity,pnl,pnl_pct,exit_reason\n",
            encoding="utf-8",
        )
    return json_path, md_path, trades_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay scanned stock entry patterns with portfolio constraints."
    )
    parser.add_argument(
        "--config",
        default="stock_entry_pattern_portfolio_replay.yaml",
        help="ConfigLoader-relative replay YAML path.",
    )
    args = parser.parse_args()

    replay_config = _load_replay_config(args.config)
    results, patterns, summary = run_replay(replay_config)
    output_dir = Path(
        replay_config.get("output_dir") or "reports/stock_entry_pattern_replay"
    )
    json_path, md_path, trades_path = write_outputs(
        results,
        patterns,
        summary,
        output_dir,
    )
    best = results[0] if results else None
    print(
        f"runs={len(results)} patterns={_pattern_label(patterns)} "
        f"symbols={summary['symbols_loaded']}/{summary['symbols_requested']}"
    )
    if best:
        print(
            f"best={best.run_id} trades={best.admitted_trades} "
            f"monthly={best.monthly_expected_return_pct:+.2f}% "
            f"win={best.win_rate_pct:.2f}% mdd={best.max_drawdown_pct:.2f}%"
        )
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    print(f"trades={trades_path}")


if __name__ == "__main__":
    main()
