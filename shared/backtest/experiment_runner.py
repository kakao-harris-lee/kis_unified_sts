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
import math
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from shared.utils.coercion import to_bool

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


def _load_symbol_frames(
    *,
    symbols: list[str],
    timeframe: str,
    window: _ResolvedWindow,
    bar_loader: BarLoader,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Load bars PER SYMBOL (single-symbol frames) + coverage_by_symbol.

    Returns one frame per loaded symbol — NOT a concatenated multi-symbol frame.
    ``DailyBacktestAdapter`` pre-computes rolling indicators over the whole frame
    and indexes bars positionally, so it is single-symbol only; the experiment
    therefore backtests each symbol independently and aggregates (equal-weight),
    mirroring the CLI's tier backtest. The whole per-symbol body is guarded so a
    malformed frame surfaces as that symbol's coverage error instead of aborting
    the run.
    """
    frames: dict[str, pd.DataFrame] = {}
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
            if df is None or df.empty:
                coverage[symbol] = {"loaded": False, "error": "no_data"}
                continue
            df = df.copy()
            if "code" not in df.columns:
                df["code"] = symbol
            df = df.sort_values("datetime").reset_index(drop=True)
            coverage[symbol] = {
                "loaded": True,
                "rows": int(len(df)),
                "start": str(pd.to_datetime(df["datetime"].min()).date()),
                "end": str(pd.to_datetime(df["datetime"].max()).date()),
            }
            frames[symbol] = df
        except Exception as exc:  # noqa: BLE001 - record, never abort the run
            coverage[symbol] = {
                "loaded": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
    return frames, coverage


def _daily_equity_points(
    equity_curve: list[tuple[datetime, float]],
) -> list[dict[str, Any]]:
    """Downsample a per-bar equity curve to one (date, equity) point per day (EOD)."""
    by_date: dict[str, float] = {}
    for ts, value in equity_curve:
        by_date[str(pd.to_datetime(ts).date())] = float(value)
    return [{"date": d, "equity": v} for d, v in sorted(by_date.items())]


def _finite(value: float, ndigits: int = 4) -> float | None:
    """Round a float, mapping non-finite (inf/nan) → None so the report stays valid
    JSON (browser ``JSON.parse`` rejects ``Infinity``; e.g. profit_factor with no
    losing trades is ``inf`` in the engine)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return round(f, ndigits) if math.isfinite(f) else None


def _portfolio_metrics(
    equity_points: list[dict[str, Any]], initial: float
) -> dict[str, float]:
    """Equal-weight portfolio metrics from a combined daily-equity series."""
    eq = [float(p["equity"]) for p in equity_points] or [initial]
    final = eq[-1]
    total_return_pct = (final - initial) / initial * 100 if initial > 0 else 0.0
    rets = [eq[i] / eq[i - 1] - 1 for i in range(1, len(eq)) if eq[i - 1] > 0]
    sharpe = sortino = 0.0
    if len(rets) >= 2:
        mean = statistics.fmean(rets)
        sd = statistics.pstdev(rets)
        sharpe = mean / sd * math.sqrt(252) if sd > 0 else 0.0
        downside = [r for r in rets if r < 0]
        dsd = statistics.pstdev(downside) if len(downside) >= 2 else 0.0
        sortino = mean / dsd * math.sqrt(252) if dsd > 0 else 0.0
    peak = eq[0]
    mdd = 0.0
    for v in eq:
        peak = max(peak, v)
        if peak > 0:
            mdd = max(mdd, (peak - v) / peak * 100)
    return {
        "final_equity": final,
        "total_return_pct": total_return_pct,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown_pct": mdd,
    }


def _aggregate_equity(
    per_symbol_curves: list[list[dict[str, Any]]], cap_per_symbol: float
) -> list[dict[str, Any]]:
    """Combine per-symbol daily equity curves into one equal-weight portfolio NAV
    (each symbol starts at ``cap_per_symbol``; forward-fill, then sum by date)."""
    all_dates: set[str] = set()
    maps: list[dict[str, float]] = []
    for curve in per_symbol_curves:
        m = {p["date"]: float(p["equity"]) for p in curve}
        maps.append(m)
        all_dates |= set(m.keys())
    last = [cap_per_symbol] * len(maps)
    points: list[dict[str, Any]] = []
    for d in sorted(all_dates):
        total = 0.0
        for i, m in enumerate(maps):
            if d in m:
                last[i] = m[d]
            total += last[i]
        points.append({"date": d, "equity": total})
    return points


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
    frames, coverage = _load_symbol_frames(
        symbols=spec.symbols,
        timeframe="daily" if timeframe == "daily" else "minute",
        window=window,
        bar_loader=bar_loader,
    )
    if not frames:
        return StrategyOutcome(
            sid,
            "skipped",
            error=f"no {timeframe} data for any symbol in window",
            coverage=coverage,
        )

    bt = strategy_config.get("strategy", {}).get("backtest", {})
    # Opt-in backend seam (plan 2026-07-08 §5 P3-a): default stays the legacy
    # BacktestEngine; `strategy.backtest.engine: vectorbt` routes through the
    # VectorbtRunner with automatic legacy fallback on NotImplementedError /
    # ImportError. Unknown values fall back to legacy WITH a warning so a
    # typo ("vbt") cannot silently produce a legacy run labeled as intended.
    engine_backend = str(bt.get("engine", "") or "legacy").lower()
    if engine_backend not in ("legacy", "vectorbt"):
        logger.warning(
            "experiment %s: unknown backtest engine %r — using legacy "
            "(valid: legacy | vectorbt)",
            sid,
            engine_backend,
        )
        engine_backend = "legacy"

    # Explicit legacy-exit escape hatch (plan §5 P3-c): a strategy whose exit is
    # a state machine the vectorbt runner cannot express (e.g. three_stage's
    # staged partial exits) sets `strategy.backtest.legacy_exit: true` to force
    # the legacy engine WITHOUT even attempting the runner — an operator-visible
    # marker, not a reliance on the runner's own refusal+fallback. Coerced as a
    # tri-state (bool / "true"/"1"/"yes" …); an unrecognized value is NOT
    # silently honored — warn and ignore it, mirroring the unknown-engine path.
    raw_legacy_exit = bt.get("legacy_exit", False)
    # 빈 키(`legacy_exit:` → None)는 "미설정"이다 — 경고 없이 False 취급.
    legacy_exit = False if raw_legacy_exit is None else to_bool(raw_legacy_exit)
    if legacy_exit is None:
        logger.warning(
            "experiment %s: unrecognized backtest.legacy_exit %r — ignoring "
            "(expected true/false)",
            sid,
            raw_legacy_exit,
        )
        legacy_exit = False
    if legacy_exit and engine_backend != "legacy":
        logger.info(
            "experiment %s: backtest.legacy_exit=true — forcing legacy engine "
            "(state-machine exit); vectorbt runner not attempted",
            sid,
        )
        engine_backend = "legacy"
    position_params = (
        strategy_config.get("strategy", {}).get("position", {}).get("params", {})
    )
    order_amount = float(position_params.get("order_amount_per_stock", 0) or 0) or None
    name = str(strategy_config.get("strategy", {}).get("name", sid))
    total_capital = float(bt.get("initial_capital", spec.initial_capital))
    cap_per_symbol = total_capital / len(frames)

    # Backtest each symbol independently (equal-weight slice of capital), then
    # aggregate — a true portfolio backtest would need a multi-symbol daily
    # adapter, which does not exist (see _load_symbol_frames).
    per_curves: list[list[dict[str, Any]]] = []
    trades: list[dict[str, Any]] = []
    closed = winners = 0
    gains = losses = 0.0
    ran = 0
    used_backends: set[str] = set()

    def _build_adapter() -> Any:
        # Fresh strategy + adapter per attempt — a mid-run vectorbt refusal
        # leaves the previous adapter warm/dirty, so the legacy fallback must
        # never reuse it.
        trading_strategy = StrategyFactory.create(strategy_config)
        return (
            DailyBacktestAdapter(trading_strategy, strategy_config)
            if timeframe == "daily"
            else BacktestStrategyAdapter(trading_strategy, strategy_config)
        )

    for symbol, df in frames.items():
        try:
            config = BacktestConfig.stock(
                initial_capital=cap_per_symbol,
                position_size_pct=float(bt.get("position_size_pct", 10.0) or 10.0),
                order_amount_per_stock=order_amount,
                max_positions=int(position_params.get("max_positions", 5) or 5),
            )
            if "risk" in bt:
                config.risk = RiskConfig.from_dict(bt["risk"])
            result = None
            symbol_backend = "backtest_engine"
            if engine_backend == "vectorbt":
                from shared.backtest.vbt_runner import (
                    VectorbtParityError,
                    VectorbtRunner,
                )

                try:
                    result = VectorbtRunner(_build_adapter(), config).run(df)
                    symbol_backend = "vectorbt"
                except (NotImplementedError, ImportError) as unsupported:
                    # NotImplementedError: 러너 표현범위 밖 (정상 폴백 경로).
                    # ImportError: vectorbt 자체가 없는 환경 — 러너의 사전
                    # 가드가 대부분 잡지만(find_spec), 깨진 설치 등 늦게
                    # 터지는 케이스도 legacy 로 폴백해야 한다.
                    logger.warning(
                        "experiment %s/%s: vectorbt runner unavailable/"
                        "unsupported (%s); falling back to legacy engine",
                        sid,
                        symbol,
                        unsupported,
                    )
                except VectorbtParityError as parity_err:
                    # 러너 내부 cross-check(resolver 원장 ↔ vbt 원장) 불일치 —
                    # 러너 결함 신호다. 심볼을 버리면(per-symbol except 로 떨어져
                    # loaded:False) 등가중 집계가 조용히 왜곡되므로, legacy 로
                    # 폴백해 결과를 보존하고 조사용 경고만 남긴다. 폴백은 아래
                    # _build_adapter() 재호출로 fresh adapter 를 쓴다(오염 무관).
                    logger.warning(
                        "experiment %s/%s: vectorbt parity cross-check FAILED "
                        "(%s); falling back to legacy engine — investigate "
                        "vbt_runner",
                        sid,
                        symbol,
                        parity_err,
                    )
            if result is None:
                result = BacktestEngine(_build_adapter(), config).run(df)
                symbol_backend = "backtest_engine"
            used_backends.add(symbol_backend)
        except Exception as exc:  # noqa: BLE001 - isolate per-symbol failure
            logger.warning("experiment %s/%s failed", sid, symbol, exc_info=True)
            coverage[symbol] = {
                "loaded": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            continue
        # 어떤 백엔드가 이 심볼을 처리했는지 리포트에 남긴다 — 혼합 실행을
        # 로그 없이 식별할 수 있어야 P3-b 관찰 증거가 오염되지 않는다.
        if isinstance(coverage.get(symbol), dict):
            coverage[symbol]["engine"] = symbol_backend
        ran += 1
        per_curves.append(_daily_equity_points(result.equity_curve))
        trades.extend(_trades_from_result(sid, name, result))
        closed += int(result.total_trades)
        winners += int(result.winning_trades)
        for t in result.trades:
            if t.pnl > 0:
                gains += float(t.pnl)
            elif t.pnl < 0:
                losses += abs(float(t.pnl))

    if ran == 0:
        return StrategyOutcome(
            sid, "error", error="all symbols failed to backtest", coverage=coverage
        )

    equity_curve = _aggregate_equity(per_curves, cap_per_symbol)
    metrics = _portfolio_metrics(equity_curve, total_capital)
    summary: dict[str, Any] = {
        "strategy_id": sid,
        "strategy_name": name,
        # 전 심볼 단일 백엔드일 때만 그 이름을 쓰고, 부분 폴백은 "mixed" 로
        # 명시한다 (per-symbol 백엔드는 coverage[symbol]["engine"] 참조).
        "engine": (
            "vectorbt"
            if used_backends == {"vectorbt"}
            else ("mixed" if "vectorbt" in used_backends else "backtest_engine")
        ),
        "timeframe": timeframe,
        "initial_capital": total_capital,
        "final_equity": _finite(metrics["final_equity"], 0),
        "total_return_pct": _finite(metrics["total_return_pct"]),
        "realized_pnl": _finite(metrics["final_equity"] - total_capital, 0),
        "unrealized_pnl": 0.0,
        "closed_trades": closed,
        "admitted_entries": closed,
        "open_positions": 0,
        "win_rate_pct": round(winners / closed * 100, 2) if closed else 0.0,
        "max_drawdown_pct": _finite(metrics["max_drawdown_pct"]),
        "sharpe_ratio": _finite(metrics["sharpe_ratio"], 3),
        "sortino_ratio": _finite(metrics["sortino_ratio"], 3),
        "profit_factor": _finite(gains / losses, 3) if losses > 0 else None,
        "symbols_ran": ran,
        "positions": [],
    }
    return StrategyOutcome(
        strategy_id=sid,
        status="ok",
        summary=summary,
        equity_curve=equity_curve,
        trades=trades,
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
    summaries.sort(key=lambda s: s.get("total_return_pct") or 0.0, reverse=True)
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


def _json_safe(obj: Any) -> Any:
    """Recursively replace non-finite floats (inf/nan) with None so the report is
    strict JSON — the dashboard's browser ``JSON.parse`` rejects ``Infinity``."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    return obj


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
    # allow_nan=False guarantees we never emit Infinity/NaN; _json_safe removes
    # them first so it cannot raise.
    payload = json.dumps(
        _json_safe(report), ensure_ascii=False, indent=2, allow_nan=False
    )
    path.write_text(payload, encoding="utf-8")
    return path


def _merge_coverage(outcomes: list[StrategyOutcome]) -> dict[str, Any]:
    """Union of per-strategy coverage maps (prefer a loaded record over a failure)."""
    merged: dict[str, Any] = {}
    for o in outcomes:
        for sym, info in o.coverage.items():
            if sym not in merged or info.get("loaded"):
                merged[sym] = info
    return merged
