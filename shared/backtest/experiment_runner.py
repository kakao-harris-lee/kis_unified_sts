"""Stock strategy experiment runner — run current registry strategies through the
real :class:`BacktestEngine` on collected market data and emit one unified report.

This is the Phase-1 core of the dashboard "experiment" feature. Unlike the legacy
``scripts/analysis/stock_builder_preset_experiment.py`` (a self-contained paper-sim
loop that only runs *builder presets*), this runner drives the production
:class:`BacktestEngine` so registry strategies (pattern_pullback, vr_composite,
momentum_breakout, williams_r, ...) get proper metrics (Sharpe / MDD / win-rate),
and records a per-strategy ``status`` (ok / skipped / error) so a real failure is
never confused with a flat/losing result or a data gap.

The report schema is a superset of the legacy builder report so the dashboard
report viewer can render it once the API is generalized (Phase 3/4):
``{experiment, data_coverage, summaries[], equity_curves{}, trades[]}``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Default loader is imported lazily inside the runner so importing this module
# (e.g. in tests that inject a fake loader) does not require the storage stack.
BarLoader = Callable[..., pd.DataFrame]


class ExperimentStrategy(BaseModel):
    """One strategy entry in an experiment spec."""

    type: str = Field(default="registry", description="registry | builder")
    name: str = Field(description="Registry strategy name (or builder preset id)")
    asset: str = Field(default="stock")


class ExperimentSpec(BaseModel):
    """Declarative experiment definition (on-demand or scheduled)."""

    id: str = Field(default="stock_experiment")
    description: str = Field(default="")
    strategies: list[ExperimentStrategy] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    start: date | None = None
    end: date | None = None
    lookback_days: int = Field(default=365, ge=1)
    initial_capital: float = Field(default=10_000_000, gt=0)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentSpec:
        return cls.model_validate(data)


@dataclass
class _ResolvedWindow:
    start: date
    end: date


@dataclass
class StrategyOutcome:
    """Per-strategy result captured by the runner (before report serialization)."""

    strategy_id: str
    status: str  # ok | skipped | error
    summary: dict[str, Any] = field(default_factory=dict)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _resolve_window(spec: ExperimentSpec, now: datetime) -> _ResolvedWindow:
    end = spec.end or now.astimezone(UTC).date()
    start = spec.start or (end - timedelta(days=spec.lookback_days))
    return _ResolvedWindow(start=start, end=end)


def _default_bar_loader() -> BarLoader:
    from shared.storage.market_data_store import load_market_bars_for_backtest

    return load_market_bars_for_backtest


def _strategy_timeframe(strategy_config: dict[str, Any]) -> str:
    return str(strategy_config.get("strategy", {}).get("timeframe", "minute"))


def _load_symbols(
    *,
    symbols: list[str],
    timeframe: str,
    window: _ResolvedWindow,
    bar_loader: BarLoader,
) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """Load + concat bars for all symbols; return (df_or_none, coverage_by_symbol).

    Per-symbol coverage records loaded/rows/start/end, or an error/no_data marker —
    so a missing symbol surfaces in the report instead of silently shrinking the
    universe.
    """
    frames: list[pd.DataFrame] = []
    coverage: dict[str, Any] = {}
    for symbol in symbols:
        try:
            df = bar_loader(
                symbol=symbol,
                asset_class="stock",
                timeframe=timeframe,
                start=window.start,
                end=window.end,
            )
        except Exception as exc:  # noqa: BLE001 - record, don't abort the whole run
            coverage[symbol] = {
                "loaded": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            continue
        if df is None or df.empty:
            coverage[symbol] = {"loaded": False, "error": "no_data"}
            continue
        df = df.copy()
        if "code" not in df.columns:
            df["code"] = symbol
        coverage[symbol] = {
            "loaded": True,
            "rows": int(len(df)),
            "start": str(pd.to_datetime(df["datetime"].min()).date()),
            "end": str(pd.to_datetime(df["datetime"].max()).date()),
        }
        frames.append(df)

    if not frames:
        return None, coverage
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(["datetime", "code"]).reset_index(drop=True)
    return combined, coverage


def _daily_equity_points(
    equity_curve: list[tuple[datetime, float]],
) -> list[dict[str, Any]]:
    """Downsample a per-bar equity curve to one (date, equity) point per day (EOD)."""
    by_date: dict[str, float] = {}
    for ts, value in equity_curve:
        by_date[str(pd.to_datetime(ts).date())] = float(value)
    return [{"date": d, "equity": v} for d, v in sorted(by_date.items())]


def _summary_from_result(strategy_id: str, name: str, result: Any) -> dict[str, Any]:
    """Map a ``BacktestResult`` to the unified report summary shape (frontend schema
    fields + Sharpe/MDD/win-rate that the legacy paper-sim never produced)."""
    return {
        "strategy_id": strategy_id,
        "strategy_name": name,
        "engine": "backtest_engine",
        "initial_capital": float(result.initial_capital),
        "final_equity": float(result.final_capital),
        "total_return_pct": round(float(result.total_return_pct), 4),
        "realized_pnl": float(result.total_pnl),
        "unrealized_pnl": 0.0,  # the engine liquidates all positions at data end
        "closed_trades": int(result.total_trades),
        "admitted_entries": int(result.total_trades),
        "open_positions": 0,
        "win_rate_pct": round(float(result.win_rate), 2),
        "max_drawdown_pct": round(float(result.max_drawdown_pct), 4),
        "sharpe_ratio": round(float(result.sharpe_ratio), 3),
        "sortino_ratio": round(float(result.sortino_ratio), 3),
        "profit_factor": round(float(result.profit_factor), 3),
        "positions": [],
    }


def _trades_from_result(
    strategy_id: str, name: str, result: Any
) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    for t in result.trades:
        trades.append(
            {
                "strategy_id": strategy_id,
                "strategy_name": name,
                "symbol": t.code,
                "name": t.name,
                "entry_date": (
                    t.entry_time.date().isoformat() if t.entry_time else None
                ),
                "exit_date": (t.exit_time.date().isoformat() if t.exit_time else None),
                "entry_price": float(t.entry_price),
                "exit_price": float(t.exit_price),
                "quantity": int(t.quantity),
                "pnl": float(t.pnl),
                "pnl_pct": round(float(t.pnl_pct), 4),
                "exit_reason": t.exit_reason,
            }
        )
    return trades


def _run_registry_strategy(
    *,
    entry: ExperimentStrategy,
    spec: ExperimentSpec,
    window: _ResolvedWindow,
    bar_loader: BarLoader,
) -> StrategyOutcome:
    """Run one registry strategy through the real BacktestEngine over the universe."""
    from shared.backtest import BacktestConfig, BacktestEngine
    from shared.backtest.adapter import BacktestStrategyAdapter
    from shared.backtest.config import RiskConfig
    from shared.backtest.daily_adapter import DailyBacktestAdapter
    from shared.config.loader import ConfigLoader
    from shared.strategy.registry import StrategyFactory

    sid = entry.name
    try:
        strategy_config = ConfigLoader.load_strategy(entry.asset, entry.name)
    except Exception as exc:  # noqa: BLE001
        return StrategyOutcome(sid, "error", error=f"config load failed: {exc}")

    timeframe = _strategy_timeframe(strategy_config)
    df, coverage = _load_symbols(
        symbols=spec.symbols,
        timeframe="daily" if timeframe == "daily" else "minute",
        window=window,
        bar_loader=bar_loader,
    )
    if df is None:
        return StrategyOutcome(
            sid,
            "skipped",
            error=f"no {timeframe} data for any symbol in window",
            coverage=coverage,
        )

    bt = strategy_config.get("strategy", {}).get("backtest", {})
    position_params = (
        strategy_config.get("strategy", {}).get("position", {}).get("params", {})
    )
    order_amount = float(position_params.get("order_amount_per_stock", 0) or 0) or None
    try:
        config = BacktestConfig.stock(
            initial_capital=float(bt.get("initial_capital", spec.initial_capital)),
            position_size_pct=float(bt.get("position_size_pct", 10.0) or 10.0),
            order_amount_per_stock=order_amount,
            max_positions=int(position_params.get("max_positions", 5) or 5),
        )
        if "risk" in bt:
            config.risk = RiskConfig.from_dict(bt["risk"])

        trading_strategy = StrategyFactory.create(strategy_config)
        adapted = (
            DailyBacktestAdapter(trading_strategy, strategy_config)
            if timeframe == "daily"
            else BacktestStrategyAdapter(trading_strategy, strategy_config)
        )
        result = BacktestEngine(adapted, config).run(df)
    except Exception as exc:  # noqa: BLE001 - isolate per-strategy failure
        logger.warning("experiment strategy %s failed", sid, exc_info=True)
        return StrategyOutcome(
            sid, "error", error=f"{type(exc).__name__}: {exc}", coverage=coverage
        )

    name = str(strategy_config.get("strategy", {}).get("name", sid))
    summary = _summary_from_result(sid, name, result)
    summary["timeframe"] = timeframe
    return StrategyOutcome(
        strategy_id=sid,
        status="ok",
        summary=summary,
        equity_curve=_daily_equity_points(result.equity_curve),
        trades=_trades_from_result(sid, name, result),
        coverage=coverage,
    )


def run_stock_experiment(
    spec: ExperimentSpec,
    *,
    bar_loader: BarLoader | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run every strategy in ``spec`` and return one unified report dict.

    Each strategy is isolated: a config/data/engine failure on one is recorded as
    ``status: error`` (or ``skipped`` for no-data) and the rest still run. Builder
    presets (``type: builder``) are not yet driven here (Phase 1b) — they are
    recorded as ``skipped`` so the report is honest about what ran.

    Args:
        spec: Experiment definition.
        bar_loader: Injectable bar loader (defaults to the Parquet store loader);
            override in tests.
        now: Clock override for window resolution (defaults to ``datetime.now(UTC)``).
    """
    from shared.strategy.registry import register_builtin_components

    register_builtin_components()
    now = now or datetime.now(UTC)
    window = _resolve_window(spec, now)
    loader = bar_loader or _default_bar_loader()

    outcomes: list[StrategyOutcome] = []
    for entry in spec.strategies:
        if entry.type == "registry":
            outcomes.append(
                _run_registry_strategy(
                    entry=entry, spec=spec, window=window, bar_loader=loader
                )
            )
        else:
            outcomes.append(
                StrategyOutcome(
                    entry.name,
                    "skipped",
                    error="builder presets not yet supported by this runner (Phase 1b)",
                )
            )

    # data_coverage is shared across strategies of the same timeframe; merge what we
    # have (registry strategies already validated coverage). Recompute once from the
    # union so the report carries a single coverage map.
    coverage = _merge_coverage(outcomes)

    summaries = [o.summary for o in outcomes if o.status == "ok"]
    summaries.sort(key=lambda s: s.get("total_return_pct", 0.0), reverse=True)
    equity_curves = {
        o.strategy_id: o.equity_curve for o in outcomes if o.status == "ok"
    }
    trades = [t for o in outcomes if o.status == "ok" for t in o.trades]

    return {
        "experiment": {
            "id": spec.id,
            "description": spec.description,
            "start_date": window.start.isoformat(),
            "end_date": window.end.isoformat(),
            "generated_at": now.astimezone(UTC).isoformat(),
            "symbols": list(spec.symbols),
            "strategies": [e.name for e in spec.strategies],
            "initial_capital": float(spec.initial_capital),
        },
        "data_coverage": coverage,
        "summaries": summaries,
        "equity_curves": equity_curves,
        "trades": trades,
        "status_by_strategy": [
            {"strategy_id": o.strategy_id, "status": o.status, "error": o.error}
            for o in outcomes
        ],
    }


def write_experiment_report(
    report: dict[str, Any], output_dir: str | Path, *, now: datetime | None = None
) -> Path:
    """Write the report JSON to ``output_dir/<id>_<YYYYMMDD>_<HHMMSS>.json``."""
    import json

    now = now or datetime.now(UTC)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    exp_id = report.get("experiment", {}).get("id", "stock_experiment")
    stamp = now.astimezone(UTC).strftime("%Y%m%d_%H%M%S")
    path = out / f"{exp_id}_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _merge_coverage(outcomes: list[StrategyOutcome]) -> dict[str, Any]:
    """Union of per-strategy coverage maps (prefer a loaded record over a failure)."""
    merged: dict[str, Any] = {}
    for o in outcomes:
        for sym, info in o.coverage.items():
            if sym not in merged or info.get("loaded"):
                merged[sym] = info
    return merged
