#!/usr/bin/env python3
"""Scan stock daily data for forward-return entry pattern candidates."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from shared.backtest.daily_adapter import load_stock_daily_from_clickhouse  # noqa: E402
from shared.collector.historical.stock import STOCK_UNIVERSE  # noqa: E402
from shared.config.loader import ConfigLoader  # noqa: E402


@dataclass(frozen=True)
class ScanTargets:
    min_signals: int
    horizons: tuple[int, ...]
    rank_horizon: int
    round_trip_cost_pct: float


@dataclass
class PatternResult:
    name: str
    description: str
    params: dict[str, Any]
    signals: int
    unique_symbols: int
    start: str
    end: str
    rank_horizon: int
    rank_win_rate_pct: float
    rank_avg_net_return_pct: float
    rank_median_net_return_pct: float
    rank_profit_factor: float
    horizon_metrics: dict[str, dict[str, float]]
    score: float


Loader = Callable[[str, date, date], pd.DataFrame]


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return [None]
    if isinstance(value, list):
        return value or [None]
    return [value]


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


def _compute_rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100.0 - (100.0 / (1.0 + rs))


def _compute_features(df: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    out = df.sort_values("datetime").copy()
    out["sma20"] = out["close"].rolling(window=20, min_periods=20).mean()
    out["sma60"] = out["close"].rolling(window=60, min_periods=60).mean()
    out["sma200"] = out["close"].rolling(window=200, min_periods=200).mean()
    out["sma60_prev5"] = out["sma60"].shift(5)
    out["rsi5"] = _compute_rsi(out["close"], 5)
    out["prev_rsi5"] = out["rsi5"].shift(1)
    out["rsi14"] = _compute_rsi(out["close"], 14)
    prev_close = out["close"].shift(1)
    true_range = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - prev_close).abs(),
            (out["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["atr22"] = true_range.rolling(window=22, min_periods=22).mean()
    out["atr_pct"] = out["atr22"] / out["close"]
    volume_avg = out["volume"].shift(1).rolling(window=20, min_periods=1).mean()
    out["volume_ratio"] = np.where(volume_avg > 0, out["volume"] / volume_avg, np.nan)
    out["highest_high20"] = out["high"].shift(1).rolling(window=20, min_periods=1).max()
    out["highest_high22"] = out["high"].rolling(window=22, min_periods=1).max()
    out["highest_high_gap"] = (out["close"] - out["highest_high22"]) / out[
        "highest_high22"
    ]
    out["return_1d"] = out["close"].pct_change(1)
    out["return_20d"] = out["close"].pct_change(20)
    out["return_60d"] = out["close"].pct_change(60)
    out["breakout_20d"] = out["close"] > out["highest_high20"]
    for horizon in horizons:
        out[f"forward_return_{horizon}d"] = (
            out["close"].shift(-horizon) / out["close"] - 1.0
        )
    return out


def _mask_for_conditions(df: pd.DataFrame, conditions: dict[str, Any]) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for key, raw_value in conditions.items():
        if raw_value is None:
            continue
        value = float(raw_value) if isinstance(raw_value, (int, float)) else raw_value
        if key == "close_above_sma200":
            if bool(value):
                mask &= df["close"] > df["sma200"]
        elif key == "close_above_sma60":
            if bool(value):
                mask &= df["close"] > df["sma60"]
        elif key == "close_below_sma20":
            if bool(value):
                mask &= df["close"] <= df["sma20"]
        elif key == "close_above_sma20":
            if bool(value):
                mask &= df["close"] > df["sma20"]
        elif key == "sma60_rising":
            if bool(value):
                mask &= df["sma60"] > df["sma60_prev5"]
        elif key == "breakout_20d":
            if bool(value):
                mask &= df["breakout_20d"]
        elif key == "rsi5_recovery":
            if bool(value):
                mask &= df["rsi5"] > df["prev_rsi5"]
        elif key.endswith("_min"):
            feature = _condition_feature_name(key.removesuffix("_min"))
            mask &= df[feature] >= float(value)
        elif key.endswith("_max"):
            feature = _condition_feature_name(key.removesuffix("_max"))
            mask &= df[feature] <= float(value)
        else:
            raise ValueError(f"Unsupported condition key: {key}")
    return mask.fillna(False)


def _condition_feature_name(key: str) -> str:
    aliases = {
        "rsi5_prev": "prev_rsi5",
        "close_change_1d": "return_1d",
    }
    return aliases.get(key, key)


def _pattern_param_sets(pattern: dict[str, Any]) -> list[dict[str, Any]]:
    base = pattern.get("base", {}) or {}
    grid = pattern.get("grid", {}) or {}
    if not grid:
        return [dict(base)]
    keys = list(grid.keys())
    combos: list[dict[str, Any]] = []
    for values in itertools.product(*[_as_list(grid[key]) for key in keys]):
        params = dict(base)
        params.update(dict(zip(keys, values, strict=True)))
        combos.append(params)
    return combos


def _profit_factor(returns: pd.Series) -> float:
    gains = float(returns[returns > 0].sum())
    losses = abs(float(returns[returns < 0].sum()))
    if losses == 0.0:
        return gains if gains > 0 else 0.0
    return gains / losses


def _evaluate_signals(
    signals: pd.DataFrame,
    *,
    pattern: dict[str, Any],
    params: dict[str, Any],
    targets: ScanTargets,
    start: date,
    end: date,
) -> PatternResult | None:
    signal_count = len(signals)
    if signal_count < targets.min_signals:
        return None

    horizon_metrics: dict[str, dict[str, float]] = {}
    for horizon in targets.horizons:
        col = f"forward_return_{horizon}d"
        net_returns = signals[col].dropna() - targets.round_trip_cost_pct
        if net_returns.empty:
            continue
        horizon_metrics[str(horizon)] = {
            "samples": float(len(net_returns)),
            "win_rate_pct": float((net_returns > 0).mean() * 100.0),
            "avg_net_return_pct": float(net_returns.mean() * 100.0),
            "median_net_return_pct": float(net_returns.median() * 100.0),
            "profit_factor": float(_profit_factor(net_returns)),
        }

    rank_key = str(targets.rank_horizon)
    rank = horizon_metrics.get(rank_key)
    if not rank:
        return None

    score = (
        rank["avg_net_return_pct"] * 5.0
        + rank["win_rate_pct"] * 0.25
        + min(rank["profit_factor"], 5.0) * 3.0
        + min(signal_count, 200) * 0.02
    )
    return PatternResult(
        name=str(pattern.get("name", "")),
        description=str(pattern.get("description", "")),
        params=params,
        signals=signal_count,
        unique_symbols=int(signals["code"].nunique()),
        start=start.isoformat(),
        end=end.isoformat(),
        rank_horizon=targets.rank_horizon,
        rank_win_rate_pct=rank["win_rate_pct"],
        rank_avg_net_return_pct=rank["avg_net_return_pct"],
        rank_median_net_return_pct=rank["median_net_return_pct"],
        rank_profit_factor=rank["profit_factor"],
        horizon_metrics=horizon_metrics,
        score=score,
    )


def scan_patterns(
    config: dict[str, Any],
    *,
    loader: Loader = load_stock_daily_from_clickhouse,
) -> tuple[list[PatternResult], dict[str, Any]]:
    start = _parse_date(str(config["start"]))
    end = _parse_date(str(config["end"]))
    warmup_days = int(config.get("warmup_days") or 0)
    data_start = start - timedelta(days=warmup_days)
    horizons = tuple(int(h) for h in config.get("horizons", [5, 10, 20]))
    targets = ScanTargets(
        min_signals=int(config.get("min_signals") or 20),
        horizons=horizons,
        rank_horizon=int(config.get("rank_horizon") or horizons[0]),
        round_trip_cost_pct=float(config.get("round_trip_cost_pct") or 0.0),
    )
    stocks = _select_stocks(
        str(config.get("tier") or "all"),
        symbols=str(config.get("symbols") or ""),
        max_symbols=(
            int(config["max_symbols"])
            if config.get("max_symbols") not in (None, "")
            else None
        ),
    )

    frames: list[pd.DataFrame] = []
    missing: list[str] = []
    for stock in stocks:
        code = str(stock["code"])
        try:
            df = loader(code, data_start, end)
        except Exception:
            missing.append(code)
            continue
        if df is None or df.empty:
            missing.append(code)
            continue
        df = df.copy()
        df["code"] = code
        df["name"] = str(stock.get("name") or code)
        features = _compute_features(df, horizons)
        features = features[pd.to_datetime(features["datetime"]).dt.date >= start]
        frames.append(features)

    if not frames:
        return [], {
            "symbols_requested": len(stocks),
            "symbols_loaded": 0,
            "symbols_missing": missing,
            "rows": 0,
            "targets": asdict(targets),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "data_start": data_start.isoformat(),
        }

    data = pd.concat(frames, ignore_index=True)
    results: list[PatternResult] = []
    for pattern in config.get("patterns", []):
        for params in _pattern_param_sets(pattern):
            mask = _mask_for_conditions(data, params)
            signals = data[mask].copy()
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
    summary = {
        "symbols_requested": len(stocks),
        "symbols_loaded": len(frames),
        "symbols_missing": missing,
        "rows": int(len(data)),
        "targets": asdict(targets),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "data_start": data_start.isoformat(),
    }
    return results, summary


def _load_scan_config(path: str) -> dict[str, Any]:
    cfg = ConfigLoader.load(path, use_cache=False)
    if not isinstance(cfg, dict):
        raise ValueError(f"Config did not load as a mapping: {path}")
    scan = cfg.get("scan", cfg)
    if not isinstance(scan, dict):
        raise ValueError(f"Scan config is not a mapping: {path}")
    return scan


def _format_markdown(results: list[PatternResult], summary: dict[str, Any]) -> str:
    lines = [
        "# Stock Entry Pattern Scan",
        "",
        f"- Generated at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Period: `{summary['start']}~{summary['end']}`",
        f"- Symbols loaded: `{summary['symbols_loaded']}/{summary['symbols_requested']}`",
        f"- Rows: `{summary['rows']}`",
        f"- Rank horizon: `{summary['targets']['rank_horizon']}d`",
        f"- Min signals: `{summary['targets']['min_signals']}`",
        "",
        "| Rank | Pattern | Signals | Symbols | Win | Avg net | Median net | PF | Score |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for idx, result in enumerate(results, start=1):
        lines.append(
            f"| {idx} | `{result.name}` | {result.signals} | {result.unique_symbols} | "
            f"{result.rank_win_rate_pct:.2f}% | {result.rank_avg_net_return_pct:.2f}% | "
            f"{result.rank_median_net_return_pct:.2f}% | {result.rank_profit_factor:.2f} | "
            f"{result.score:.2f} |"
        )

    lines.append("")
    for idx, result in enumerate(results[:20], start=1):
        lines.extend(
            [
                f"## {idx}. `{result.name}`",
                "",
                f"- Description: {result.description}",
                f"- Params: `{json.dumps(result.params, ensure_ascii=False, sort_keys=True)}`",
                f"- Signals: `{result.signals}` across `{result.unique_symbols}` symbols",
                "",
                "| Horizon | Samples | Win | Avg net | Median net | PF |",
                "|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for horizon, metrics in sorted(
            result.horizon_metrics.items(), key=lambda item: int(item[0])
        ):
            lines.append(
                f"| {horizon}d | {metrics['samples']:.0f} | "
                f"{metrics['win_rate_pct']:.2f}% | "
                f"{metrics['avg_net_return_pct']:.2f}% | "
                f"{metrics['median_net_return_pct']:.2f}% | "
                f"{metrics['profit_factor']:.2f} |"
            )
        lines.append("")
    return "\n".join(lines)


def write_outputs(
    results: list[PatternResult],
    summary: dict[str, Any],
    output_dir: Path,
    *,
    top_k: int,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    selected = results[:top_k]
    json_path = output_dir / f"stock_entry_pattern_scan_{stamp}.json"
    md_path = output_dir / f"stock_entry_pattern_scan_{stamp}.md"
    payload = {
        "summary": summary,
        "results": [asdict(result) for result in selected],
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path.write_text(_format_markdown(selected, summary), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan stock daily data for forward-return entry patterns."
    )
    parser.add_argument(
        "--config",
        default="stock_entry_pattern_scan.yaml",
        help="ConfigLoader-relative scan YAML path.",
    )
    args = parser.parse_args()

    config = _load_scan_config(args.config)
    results, summary = scan_patterns(config)
    output_dir = Path(config.get("output_dir") or "reports/stock_entry_pattern_scan")
    top_k = int(config.get("top_k") or 30)
    json_path, md_path = write_outputs(results, summary, output_dir, top_k=top_k)
    best = results[0] if results else None
    print(
        f"patterns={len(results)} symbols={summary['symbols_loaded']}/{summary['symbols_requested']} "
        f"rows={summary['rows']}"
    )
    if best:
        print(
            f"best={best.name} signals={best.signals} "
            f"win={best.rank_win_rate_pct:.2f}% avg_net={best.rank_avg_net_return_pct:.2f}%"
        )
    print(f"json={json_path}")
    print(f"markdown={md_path}")


if __name__ == "__main__":
    main()
