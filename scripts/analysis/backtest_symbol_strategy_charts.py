#!/usr/bin/env python3
"""Run per-strategy stock backtests for one symbol and render buy/sell charts."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import traceback
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
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
from shared.collector.historical.stock import load_stock_minute_from_clickhouse  # noqa: E402
from shared.config.loader import ConfigLoader  # noqa: E402
from shared.strategy.registry import StrategyFactory, register_builtin_components  # noqa: E402


@dataclass
class StrategyRunRow:
    strategy: str
    timeframe: str
    status: str
    bars: int
    total_return_pct: float | None
    total_trades: int | None
    win_rate: float | None
    max_drawdown_pct: float | None
    sharpe_ratio: float | None
    trades_csv: str
    chart_png: str
    metrics_json: str
    error: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "timeframe": self.timeframe,
            "status": self.status,
            "bars": self.bars,
            "total_return_pct": self.total_return_pct,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "trades_csv": self.trades_csv,
            "chart_png": self.chart_png,
            "metrics_json": self.metrics_json,
            "error": self.error,
        }


def _parse_date(v: str) -> date:
    return datetime.strptime(v, "%Y-%m-%d").date()


def _to_plot_series(series: pd.Series) -> pd.Series:
    ts = pd.to_datetime(series, errors="coerce")
    tz = getattr(ts.dt, "tz", None)
    if tz is not None:
        ts = ts.dt.tz_convert("Asia/Seoul").dt.tz_localize(None)
    return ts


def _to_plot_timestamp(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ts
    if getattr(ts, "tzinfo", None) is not None:
        ts = ts.tz_convert("Asia/Seoul").tz_localize(None)
    return ts


def _build_backtest_config(strategy_cfg: dict[str, Any], capital: float) -> BacktestConfig:
    bt = strategy_cfg.get("strategy", {}).get("backtest", {})
    pos = strategy_cfg.get("strategy", {}).get("position", {}).get("params", {})

    bt_capital = float(bt.get("initial_capital", capital))
    bt_position_size_pct = float(bt.get("position_size_pct", 10.0) or 10.0)
    max_positions = int(pos.get("max_positions", 5) or 5)
    order_amount = float(pos.get("order_amount_per_stock", 0) or 0)
    if order_amount <= 0:
        order_amount = None

    cfg = BacktestConfig.stock(
        initial_capital=bt_capital,
        position_size_pct=bt_position_size_pct,
        order_amount_per_stock=order_amount,
        max_positions=max_positions,
    )
    if "risk" in bt:
        cfg.risk = RiskConfig.from_dict(bt["risk"])
    return cfg


def _load_symbol_data(symbol: str, timeframe: str, start: date, end: date) -> pd.DataFrame:
    if timeframe == "daily":
        df = load_stock_daily_from_clickhouse(symbol, start, end)
    else:
        df = load_stock_minute_from_clickhouse(symbol, start, end)

    if "code" not in df.columns:
        df["code"] = symbol
    if "name" not in df.columns:
        df["name"] = symbol

    return df.sort_values("datetime").reset_index(drop=True)


def _resolve_strategy_names(user_input: str | None, include_disabled: bool) -> list[str]:
    if user_input:
        names = [x.strip() for x in user_input.split(",") if x.strip()]
        return sorted(set(names))

    cfg_dir = REPO_ROOT / "config/strategies/stock"
    names: list[str] = []
    for path in sorted(cfg_dir.glob("*.yaml")):
        name = path.stem
        cfg = ConfigLoader.load_strategy("stock", name)
        enabled = bool(cfg.get("strategy", {}).get("enabled", False))
        if include_disabled or enabled:
            names.append(name)
    return names


def _render_chart(
    *,
    data: pd.DataFrame,
    trades: pd.DataFrame,
    strategy: str,
    symbol: str,
    timeframe: str,
    result_metrics: dict[str, Any],
    output_png: Path,
) -> None:
    fig, (ax_price, ax_vol) = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(16, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    dt = _to_plot_series(data["datetime"])
    close = data["close"].astype(float)
    volume = data["volume"].astype(float)

    ax_price.plot(dt, close, color="black", linewidth=1.0, label="Close")

    if not trades.empty:
        entry_t = _to_plot_series(trades["entry_time"])
        exit_t = _to_plot_series(trades["exit_time"])
        entry_p = trades["entry_price"].astype(float)
        exit_p = trades["exit_price"].astype(float)

        ax_price.scatter(
            entry_t,
            entry_p,
            marker="^",
            s=55,
            color="green",
            edgecolors="white",
            linewidths=0.5,
            label=f"Buy ({len(trades)})",
            zorder=5,
        )
        ax_price.scatter(
            exit_t,
            exit_p,
            marker="v",
            s=55,
            color="red",
            edgecolors="white",
            linewidths=0.5,
            label=f"Sell ({len(trades)})",
            zorder=5,
        )

        # Draw thin segments from entry to exit for readability.
        for _, row in trades.iterrows():
            x0 = _to_plot_timestamp(row["entry_time"])
            x1 = _to_plot_timestamp(row["exit_time"])
            if pd.isna(x0) or pd.isna(x1):
                continue
            y0 = float(row["entry_price"])
            y1 = float(row["exit_price"])
            line_color = "green" if float(row.get("pnl", 0.0)) >= 0 else "red"
            ax_price.plot([x0, x1], [y0, y1], color=line_color, alpha=0.25, linewidth=1.0)

    ax_price.set_ylabel("Price")
    ax_price.grid(alpha=0.25)
    ax_price.legend(loc="upper left")

    ret = result_metrics.get("total_return_pct", 0.0)
    trades_count = result_metrics.get("total_trades", 0)
    win_rate = result_metrics.get("win_rate", 0.0)
    mdd = result_metrics.get("max_drawdown_pct", 0.0)
    title = f"{symbol} | {strategy} ({timeframe})"
    subtitle = (
        f"Return={ret:+.2f}%  Trades={trades_count}  "
        f"WinRate={win_rate:.2f}%  MDD={mdd:.2f}%"
    )
    ax_price.set_title(f"{title}\n{subtitle}", fontsize=11)

    width_days = 0.005
    if len(dt) > 1:
        width_days = max((dt.iloc[1] - dt.iloc[0]).total_seconds() / 86400 * 0.8, 0.0008)
    ax_vol.bar(dt, volume, color="#4C78A8", width=width_days, alpha=0.65)
    ax_vol.set_ylabel("Volume")
    ax_vol.grid(alpha=0.2)

    locator = mdates.AutoDateLocator(minticks=6, maxticks=12)
    ax_vol.xaxis.set_major_locator(locator)
    ax_vol.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax_vol.set_xlabel("Datetime")

    fig.tight_layout()
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=150)
    plt.close(fig)


def _run_single_strategy(
    *,
    strategy_name: str,
    symbol: str,
    start: date,
    end: date,
    capital: float,
    charts_dir: Path,
    trades_dir: Path,
    metrics_dir: Path,
) -> StrategyRunRow:
    try:
        strategy_cfg = ConfigLoader.load_strategy("stock", strategy_name)
        timeframe = strategy_cfg.get("strategy", {}).get("timeframe", "minute")
        data = _load_symbol_data(symbol, timeframe, start, end)

        cfg = _build_backtest_config(strategy_cfg, capital)
        strategy = StrategyFactory.create(copy.deepcopy(strategy_cfg))
        if timeframe == "daily":
            adapter = DailyBacktestAdapter(strategy, strategy_cfg)
        else:
            adapter = BacktestStrategyAdapter(strategy, strategy_cfg)

        result = BacktestEngine(adapter, cfg).run(data)

        trades = pd.DataFrame([t.to_dict() for t in result.trades])
        if trades.empty:
            trades = pd.DataFrame(
                columns=[
                    "code",
                    "name",
                    "strategy",
                    "side",
                    "entry_time",
                    "exit_time",
                    "entry_price",
                    "exit_price",
                    "quantity",
                    "pnl",
                    "pnl_pct",
                    "commission",
                    "exit_reason",
                ]
            )

        trades_csv = trades_dir / f"{strategy_name}_trades.csv"
        metrics_json = metrics_dir / f"{strategy_name}_metrics.json"
        chart_png = charts_dir / f"{strategy_name}.png"

        trades.to_csv(trades_csv, index=False)

        metrics = result.to_dict()
        metrics.update(
            {
                "strategy": strategy_name,
                "symbol": symbol,
                "timeframe": timeframe,
                "bars": len(data),
                "config": cfg.to_dict(),
            }
        )
        metrics_json.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        _render_chart(
            data=data,
            trades=trades,
            strategy=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            result_metrics=metrics,
            output_png=chart_png,
        )

        return StrategyRunRow(
            strategy=strategy_name,
            timeframe=timeframe,
            status="OK",
            bars=len(data),
            total_return_pct=float(result.total_return_pct),
            total_trades=int(result.total_trades),
            win_rate=float(result.win_rate),
            max_drawdown_pct=float(result.max_drawdown_pct),
            sharpe_ratio=float(result.sharpe_ratio),
            trades_csv=str(trades_csv),
            chart_png=str(chart_png),
            metrics_json=str(metrics_json),
            error="",
        )
    except Exception as exc:
        return StrategyRunRow(
            strategy=strategy_name,
            timeframe="unknown",
            status="ERROR",
            bars=0,
            total_return_pct=None,
            total_trades=None,
            win_rate=None,
            max_drawdown_pct=None,
            sharpe_ratio=None,
            trades_csv="",
            chart_png="",
            metrics_json="",
            error=f"{exc}\n{traceback.format_exc(limit=1)}".strip(),
        )


def _write_summary_markdown(
    *,
    output_path: Path,
    rows: list[StrategyRunRow],
    symbol: str,
    start: date,
    end: date,
    capital: float,
) -> None:
    lines: list[str] = []
    lines.append("# Symbol Strategy Backtest Summary")
    lines.append("")
    lines.append(f"- symbol: {symbol}")
    lines.append(f"- period: {start} ~ {end}")
    lines.append(f"- capital: {capital:,.0f}")
    lines.append(f"- strategies: {len(rows)}")
    lines.append("")
    lines.append("| Strategy | TF | Status | Return% | Trades | WinRate% | MDD% | Sharpe | Chart | Trades |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---|---|")
    for r in rows:
        chart = Path(r.chart_png).name if r.chart_png else "-"
        trades = Path(r.trades_csv).name if r.trades_csv else "-"
        ret = f"{r.total_return_pct:+.2f}" if r.total_return_pct is not None else "-"
        tc = f"{r.total_trades}" if r.total_trades is not None else "-"
        wr = f"{r.win_rate:.2f}" if r.win_rate is not None else "-"
        mdd = f"{r.max_drawdown_pct:.2f}" if r.max_drawdown_pct is not None else "-"
        sr = f"{r.sharpe_ratio:.2f}" if r.sharpe_ratio is not None else "-"
        lines.append(
            f"| {r.strategy} | {r.timeframe} | {r.status} | {ret} | {tc} | {wr} | {mdd} | {sr} | {chart} | {trades} |"
        )
    lines.append("")
    errors = [r for r in rows if r.status != "OK"]
    if errors:
        lines.append("## Errors")
        lines.append("")
        for r in errors:
            lines.append(f"- `{r.strategy}`: `{r.error.splitlines()[0]}`")

    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest one symbol across stock strategies and create charts.")
    parser.add_argument("--symbol", default="005930", help="Stock code")
    parser.add_argument("--start", default="2026-02-01", help="YYYY-MM-DD")
    parser.add_argument("--end", default="2026-02-28", help="YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=100_000_000)
    parser.add_argument("--strategies", default=None, help="Comma-separated strategy names (default: all yaml)")
    parser.add_argument(
        "--enabled-only",
        action="store_true",
        help="Run only strategies with strategy.enabled=true",
    )
    parser.add_argument(
        "--output-dir",
        default="output/analysis/symbol_strategy_charts",
        help="Base output directory",
    )
    args = parser.parse_args()

    start = _parse_date(args.start)
    end = _parse_date(args.end)
    if end < start:
        raise SystemExit("end must be >= start")

    register_builtin_components()
    strategy_names = _resolve_strategy_names(args.strategies, include_disabled=not args.enabled_only)
    if not strategy_names:
        raise SystemExit("No strategies selected")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.output_dir) / f"{args.symbol}_{args.start}_{args.end}_{stamp}"
    charts_dir = run_dir / "charts"
    trades_dir = run_dir / "trades"
    metrics_dir = run_dir / "metrics"
    run_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)
    trades_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"[run] symbol={args.symbol} period={args.start}~{args.end} "
        f"capital={args.capital:,.0f} strategies={len(strategy_names)}"
    )

    rows: list[StrategyRunRow] = []
    for i, name in enumerate(strategy_names, start=1):
        print(f"[{i:02d}/{len(strategy_names):02d}] {name} ...")
        row = _run_single_strategy(
            strategy_name=name,
            symbol=args.symbol,
            start=start,
            end=end,
            capital=args.capital,
            charts_dir=charts_dir,
            trades_dir=trades_dir,
            metrics_dir=metrics_dir,
        )
        rows.append(row)
        if row.status == "OK":
            print(
                f"  -> OK tf={row.timeframe} bars={row.bars} "
                f"ret={row.total_return_pct:+.2f}% trades={row.total_trades}"
            )
        else:
            print(f"  -> ERROR {row.error.splitlines()[0]}")

    summary_csv = run_dir / "summary.csv"
    summary_md = run_dir / "summary.md"
    rows_df = pd.DataFrame([r.to_dict() for r in rows])
    rows_df.to_csv(summary_csv, index=False)
    _write_summary_markdown(
        output_path=summary_md,
        rows=rows,
        symbol=args.symbol,
        start=start,
        end=end,
        capital=float(args.capital),
    )

    ok_count = int((rows_df["status"] == "OK").sum()) if not rows_df.empty else 0
    err_count = len(rows) - ok_count
    print(f"[done] run_dir={run_dir}")
    print(f"[done] summary_csv={summary_csv}")
    print(f"[done] summary_md={summary_md}")
    print(f"[done] ok={ok_count} error={err_count}")


if __name__ == "__main__":
    main()
