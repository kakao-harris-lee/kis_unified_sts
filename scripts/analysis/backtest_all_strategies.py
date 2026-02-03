#!/usr/bin/env python3
"""
Backtest all supported strategies for collected symbols and generate charts.

Usage:
  python scripts/analysis/backtest_all_strategies.py --asset-class stock
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from clickhouse_driver import Client as ClickHouseDriver
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")
if os.getenv("CLICKHOUSE_NATIVE_PORT") is None and os.getenv("CLICKHOUSE_PORT") == "8123":
    os.environ["CLICKHOUSE_NATIVE_PORT"] = "9000"

from services.dashboard.routes.backtest import (  # noqa: E402
    SUPPORTED_STRATEGIES,
    IndicatorSignalStrategy,
    _clickhouse_config,
    _compute_indicators,
    _fetch_ohlcv,
    _generate_chart,
    _resolve_strategy_params,
)
from shared.backtest import BacktestConfig, BacktestEngine


def _query_symbol_ranges(
    asset_class: str, table: str, limit: int | None = None
) -> list[tuple[str, datetime, datetime, int]]:
    cfg = _clickhouse_config(asset_class)
    table = table.strip()
    client = ClickHouseDriver(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
    )
    try:
        query = f"""
            SELECT code, min(datetime) AS start_dt, max(datetime) AS end_dt, count() AS rows
            FROM {cfg['database']}.{table}
            GROUP BY code
            ORDER BY code
        """
        rows = client.execute(query)
    finally:
        client.disconnect()

    if limit:
        rows = rows[:limit]
    return [(r[0], r[1], r[2], r[3]) for r in rows]


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_chart(path: Path, chart_b64: str | None) -> bool:
    if not chart_b64:
        return False
    data = base64.b64decode(chart_b64.encode("utf-8"))
    path.write_bytes(data)
    return True


def _min_bars_required(strategy: str, params: dict[str, Any]) -> int:
    bb_period = int(params.get("bb_period", 20))
    rsi_period = int(params.get("rsi_period", 14))
    macd_slow = int(params.get("macd_slow", 26))
    atr_period = int(params.get("atr_period", 14))
    ma_long = int(params.get("ma_long", 60))
    base = max(bb_period, rsi_period, macd_slow, atr_period, ma_long)

    if strategy in {"ma_crossover", "simple_ma"}:
        short_period = int(params.get("short_period", params.get("ma_short", 5)))
        long_period = int(params.get("long_period", params.get("ma_long", 20)))
        base = max(base, short_period, long_period)

    if strategy == "stochrsi_trend":
        stoch_period = int(params.get("stoch_period", 14))
        k_period = int(params.get("k_period", 3))
        d_period = int(params.get("d_period", 3))
        base = max(base, rsi_period + stoch_period + max(k_period, d_period))

    return base + 5


def _backtest_single(
    asset_class: str,
    code: str,
    start: datetime,
    end: datetime,
    strategy: str,
    table: str,
    initial_capital: float,
) -> dict[str, Any]:
    params = _resolve_strategy_params(asset_class, strategy, {"table": table})
    df = _fetch_ohlcv(asset_class, code, start, end, params)
    if df.empty:
        return {"status": "no_data"}

    min_bars = _min_bars_required(strategy, params)
    if len(df) < min_bars:
        return {
            "status": "skipped",
            "strategy": strategy,
            "symbol": code,
            "start": str(start),
            "end": str(end),
            "rows": len(df),
            "min_bars": min_bars,
            "reason": f"insufficient bars ({len(df)} < {min_bars})",
        }

    df = _compute_indicators(df, strategy, params)

    if asset_class == "stock":
        config = BacktestConfig.stock(initial_capital=initial_capital)
    else:
        config = BacktestConfig.futures(initial_capital=initial_capital)

    engine = BacktestEngine(IndicatorSignalStrategy(strategy, params), config)
    result = engine.run(df)

    trades = [t.to_dict() for t in result.trades]
    display_name = code
    if "name" in df.columns and not df["name"].isna().all():
        display_name = str(df["name"].iloc[0])

    chart_b64 = _generate_chart(
        df,
        trades,
        title=f"{strategy} ({display_name})",
        asset_class=asset_class,
        equity_curve=result.equity_curve,
    )

    return {
        "status": "completed",
        "strategy": strategy,
        "symbol": code,
        "start": str(start),
        "end": str(end),
        "rows": len(df),
        "final_capital": result.final_capital,
        "total_return_pct": result.total_return_pct,
        "sharpe_ratio": result.sharpe_ratio,
        "max_drawdown_pct": result.max_drawdown_pct,
        "total_trades": result.total_trades,
        "win_rate": result.win_rate,
        "chart_b64": chart_b64,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-class", default="stock", choices=["stock", "futures"])
    parser.add_argument("--table", default=None)
    parser.add_argument("--output-dir", default="output/backtest_batch")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--strategies",
        nargs="*",
        default=None,
        help="Strategies to run (default: all supported)",
    )
    parser.add_argument("--initial-capital", type=float, default=10_000_000)
    args = parser.parse_args()

    asset_class = args.asset_class
    table = args.table
    if not table:
        table = "minute_candles" if asset_class == "stock" else os.getenv(
            "FUTURES_CANDLE_TABLE", "kospi_mini_1m"
        )

    strategies = list(SUPPORTED_STRATEGIES) if not args.strategies else args.strategies
    strategies = [s for s in strategies if s in SUPPORTED_STRATEGIES]

    output_root = Path(args.output_dir)
    _ensure_dir(output_root)

    summary_rows: list[dict[str, Any]] = []

    symbols = _query_symbol_ranges(asset_class, table, args.limit)
    if not symbols:
        print("No symbols found.")
        return

    for code, start, end, rows in symbols:
        symbol_dir = output_root / code
        _ensure_dir(symbol_dir)
        print(f"[{code}] {start} ~ {end} rows={rows}")

        for strategy in strategies:
            try:
                result = _backtest_single(
                    asset_class,
                    code,
                    start,
                    end,
                    strategy,
                    table,
                    args.initial_capital,
                )
                chart_path = symbol_dir / f"{strategy}.png"
                chart_written = _write_chart(chart_path, result.get("chart_b64"))
                result["chart_path"] = str(chart_path) if chart_written else None
                result.pop("chart_b64", None)
            except Exception as e:
                result = {
                    "status": "error",
                    "strategy": strategy,
                    "symbol": code,
                    "start": str(start),
                    "end": str(end),
                    "rows": rows,
                    "error": str(e),
                }
            summary_rows.append(result)
            print(f"  - {strategy}: {result.get('status')}")

    summary_path = output_root / "summary.json"
    summary_path.write_text(json.dumps(summary_rows, ensure_ascii=False, indent=2))

    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(output_root / "summary.csv", index=False)

    print(f"Done. Summary: {summary_path}")


if __name__ == "__main__":
    main()
