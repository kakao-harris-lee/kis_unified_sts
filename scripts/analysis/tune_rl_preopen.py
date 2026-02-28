#!/usr/bin/env python3
"""Tune RL hold-override parameters from Redis candle cache.

This script replays cached 1-minute candles and ranks candidate values for:
  - hold_override_max_gap
  - hold_override_min_entry_prob
  - hold_override_min_confidence

Usage:
  python scripts/analysis/tune_rl_preopen.py --asset futures --mode long_bias
  python scripts/analysis/tune_rl_preopen.py --asset futures --write-profiles
  python scripts/analysis/tune_rl_preopen.py --evaluation-mode paper --tune-target paper
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import sys
from copy import deepcopy
from datetime import datetime, time, timedelta
from itertools import product
from pathlib import Path
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from services.trading.indicator_engine import StreamingIndicatorEngine  # noqa: E402
from shared.config.loader import ConfigLoader  # noqa: E402
from shared.strategy.base import EntryContext  # noqa: E402
from shared.strategy.entry.rl_mppo import RLMPPOConfig, RLMPPOEntry  # noqa: E402
from shared.streaming.trading_state import TradingStateReader  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
logger = logging.getLogger(__name__)


def _parse_float_grid(raw: str, arg_name: str) -> list[float]:
    values: list[float] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            values.append(round(float(token), 4))
        except ValueError as exc:
            raise ValueError(f"Invalid float in --{arg_name}: '{token}'") from exc
    if not values:
        raise ValueError(f"--{arg_name} produced an empty grid")
    if any(v < 0.0 or v > 1.0 for v in values):
        raise ValueError(f"--{arg_name} values must be in [0.0, 1.0]")
    return sorted(set(values))


def _parse_symbols(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [sym.strip() for sym in raw.split(",") if sym.strip()]


def _normalize_candle_cache(raw_candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize candle cache rows and synthesize datetimes when missing."""
    normalized: list[dict[str, Any]] = []
    current_date = datetime.now(tz=KST).date()
    prev_minute: int | None = None

    for idx, row in enumerate(raw_candles):
        try:
            open_price = float(row["open"])
            high_price = float(row["high"])
            low_price = float(row["low"])
            close_price = float(row["close"])
            volume = float(row.get("volume", 0.0))
        except (KeyError, TypeError, ValueError):
            continue

        dt = None
        raw_dt = row.get("datetime")
        if isinstance(raw_dt, datetime):
            dt = raw_dt
        elif isinstance(raw_dt, str):
            try:
                dt = datetime.fromisoformat(raw_dt)
            except ValueError:
                dt = None

        minute = None
        raw_minute = row.get("minute")
        try:
            minute = int(raw_minute) if raw_minute is not None else None
        except (TypeError, ValueError):
            minute = None

        if dt is None:
            if minute is None or minute < 0 or minute > 2359:
                # Fallback to sequential minute buckets.
                minute = 900 + idx
            hh = minute // 100
            mm = minute % 100
            if hh > 23:
                hh = 23
            if mm > 59:
                mm = 59
            if prev_minute is not None and minute < prev_minute:
                current_date = current_date + timedelta(days=1)
            dt = datetime.combine(current_date, time(hh, mm), tzinfo=KST)
        else:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=KST)
            minute = dt.hour * 100 + dt.minute

        prev_minute = minute
        normalized.append(
            {
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
                "minute": minute,
                "datetime": dt,
            }
        )

    normalized.sort(key=lambda x: x["datetime"])
    return normalized


def _load_candles(
    asset: str,
    symbols: list[str],
    limit_candles: int,
) -> dict[str, list[dict[str, Any]]]:
    reader = TradingStateReader(asset)
    cache = reader.get_candle_cache()
    if not cache:
        return {}

    symbol_filter = set(symbols)
    selected: dict[str, list[dict[str, Any]]] = {}
    for symbol, rows in cache.items():
        if symbol_filter and symbol not in symbol_filter:
            continue
        if not isinstance(rows, list):
            continue
        normalized = _normalize_candle_cache(rows)
        if limit_candles > 0:
            normalized = normalized[-limit_candles:]
        if normalized:
            selected[symbol] = normalized
    return selected


def _safe_mean(values: list[float]) -> float:
    return mean(values) if values else 0.0


async def _replay_symbol(
    symbol: str,
    candles: list[dict[str, Any]],
    entry: RLMPPOEntry,
    lookahead: int,
    warmup: int,
    evaluation_mode: str,
) -> list[dict[str, float | str]]:
    outcomes: list[dict[str, float | str]] = []
    engine = StreamingIndicatorEngine(
        candle_maxlen=max(360, warmup + lookahead + 60),
        staleness_seconds=0.0,
    )

    for idx, candle in enumerate(candles):
        engine.seed_candles(symbol, [candle], minute=int(candle["minute"]))
        if idx + 1 < warmup:
            continue

        indicators = engine.get_indicators(symbol)
        rl_features = engine.get_rl_features(symbol)
        if rl_features:
            indicators.update(rl_features)
        else:
            ohlcv = engine.get_recent_candles(symbol, limit=240)
            if ohlcv:
                indicators["ohlcv"] = ohlcv

        market_data = {
            "code": symbol,
            "name": symbol,
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "volume": candle["volume"],
        }
        context = EntryContext(
            market_data=market_data,
            indicators=indicators,
            current_positions=[],
            timestamp=candle["datetime"],
            metadata={
                "paper_trading": evaluation_mode == "paper",
                "is_backtest": evaluation_mode == "backtest",
            },
        )
        signal = await entry.generate(context)
        if signal is None:
            continue

        direction = str(signal.metadata.get("signal_direction", ""))
        if direction not in {"long", "short"}:
            continue

        target_idx = idx + lookahead
        if target_idx >= len(candles):
            continue

        current_close = float(candle["close"])
        future_close = float(candles[target_idx]["close"])
        if current_close <= 0.0:
            continue

        raw_return = (future_close - current_close) / current_close
        signed_return = raw_return if direction == "long" else -raw_return
        outcomes.append(
            {
                "symbol": symbol,
                "direction": direction,
                "confidence": float(signal.confidence),
                "raw_return": raw_return,
                "signed_return": signed_return,
            }
        )

    return outcomes


def _score_metrics(
    metrics: dict[str, Any],
    mode: str,
) -> float:
    signals = int(metrics["signals"])
    long_signals = int(metrics["long_signals"])
    short_signals = int(metrics["short_signals"])
    avg_signed = float(metrics["avg_signed_return_bps"])
    avg_long = float(metrics["avg_long_return_bps"])
    long_win = float(metrics["long_win_rate"])
    win_rate = float(metrics["win_rate"])

    if mode == "long_bias":
        score = (
            avg_long * 2.0
            + long_win * 120.0
            + avg_signed * 0.5
            - short_signals * 0.15
        )
        if long_signals == 0:
            score -= 120.0
    else:
        score = avg_signed + win_rate * 100.0

    if signals < 5:
        score -= 20.0
    return round(score, 4)


def _build_metrics(
    params: dict[str, Any],
    outcomes: list[dict[str, float | str]],
    mode: str,
    tune_target: str,
) -> dict[str, Any]:
    use_paper_params = tune_target in {"paper", "both"}
    tuned_gap = float(
        params.get(
            "paper_hold_override_max_gap" if use_paper_params else "hold_override_max_gap",
            params["hold_override_max_gap"],
        )
    )
    tuned_min_entry_prob = float(
        params.get(
            "paper_hold_override_min_entry_prob"
            if use_paper_params
            else "hold_override_min_entry_prob",
            params["hold_override_min_entry_prob"],
        )
    )
    tuned_min_conf = float(
        params.get(
            "paper_hold_override_min_confidence"
            if use_paper_params
            else "hold_override_min_confidence",
            params["hold_override_min_confidence"],
        )
    )

    long_outcomes = [o for o in outcomes if o["direction"] == "long"]
    short_outcomes = [o for o in outcomes if o["direction"] == "short"]

    signed_returns = [float(o["signed_return"]) for o in outcomes]
    long_raw_returns = [float(o["raw_return"]) for o in long_outcomes]
    short_signed_returns = [float(o["signed_return"]) for o in short_outcomes]

    win_rate = _safe_mean([1.0 if ret > 0.0 else 0.0 for ret in signed_returns])
    long_win_rate = _safe_mean([1.0 if ret > 0.0 else 0.0 for ret in long_raw_returns])
    short_win_rate = _safe_mean(
        [1.0 if ret > 0.0 else 0.0 for ret in short_signed_returns]
    )

    metrics: dict[str, Any] = {
        "hold_override_max_gap": tuned_gap,
        "hold_override_min_entry_prob": tuned_min_entry_prob,
        "hold_override_min_confidence": tuned_min_conf,
        "signals": len(outcomes),
        "long_signals": len(long_outcomes),
        "short_signals": len(short_outcomes),
        "win_rate": round(win_rate, 4),
        "long_win_rate": round(long_win_rate, 4),
        "short_win_rate": round(short_win_rate, 4),
        "avg_signed_return_bps": round(_safe_mean(signed_returns) * 10_000, 4),
        "avg_long_return_bps": round(_safe_mean(long_raw_returns) * 10_000, 4),
        "avg_short_return_bps": round(_safe_mean(short_signed_returns) * 10_000, 4),
    }
    metrics["score"] = _score_metrics(metrics, mode=mode)
    return metrics


async def _evaluate_candidate(
    entry_params: dict[str, Any],
    candle_cache: dict[str, list[dict[str, Any]]],
    lookahead: int,
    warmup: int,
    mode: str,
    evaluation_mode: str,
    tune_target: str,
) -> dict[str, Any]:
    entry = RLMPPOEntry(RLMPPOConfig(**entry_params))
    outcomes: list[dict[str, float | str]] = []
    for symbol, candles in candle_cache.items():
        symbol_outcomes = await _replay_symbol(
            symbol=symbol,
            candles=candles,
            entry=entry,
            lookahead=lookahead,
            warmup=warmup,
            evaluation_mode=evaluation_mode,
        )
        outcomes.extend(symbol_outcomes)
    return _build_metrics(
        entry_params,
        outcomes,
        mode=mode,
        tune_target=tune_target,
    )


async def _run_grid_search(
    base_entry: dict[str, Any],
    candle_cache: dict[str, list[dict[str, Any]]],
    lookahead: int,
    warmup: int,
    mode: str,
    evaluation_mode: str,
    tune_target: str,
    max_gap_grid: list[float],
    min_entry_prob_grid: list[float],
    min_conf_grid: list[float],
) -> list[dict[str, Any]]:
    combos = list(product(max_gap_grid, min_entry_prob_grid, min_conf_grid))
    logger.info("Grid search started: %d combinations", len(combos))

    results: list[dict[str, Any]] = []
    for idx, (max_gap, min_entry_prob, min_conf) in enumerate(combos, start=1):
        entry_params = deepcopy(base_entry)
        if tune_target in {"base", "both"}:
            entry_params["hold_override_max_gap"] = max_gap
            entry_params["hold_override_min_entry_prob"] = min_entry_prob
            entry_params["hold_override_min_confidence"] = min_conf
        if tune_target in {"paper", "both"}:
            entry_params["paper_enable_hold_override"] = True
            entry_params["paper_hold_override_max_gap"] = max_gap
            entry_params["paper_hold_override_min_entry_prob"] = min_entry_prob
            entry_params["paper_hold_override_min_confidence"] = min_conf

        metrics = await _evaluate_candidate(
            entry_params=entry_params,
            candle_cache=candle_cache,
            lookahead=lookahead,
            warmup=warmup,
            mode=mode,
            evaluation_mode=evaluation_mode,
            tune_target=tune_target,
        )
        results.append(metrics)
        logger.info(
            "[%d/%d] gap=%.3f entry=%.3f conf=%.3f score=%.4f signals=%d",
            idx,
            len(combos),
            max_gap,
            min_entry_prob,
            min_conf,
            metrics["score"],
            metrics["signals"],
        )

    results.sort(key=lambda x: float(x["score"]), reverse=True)
    for rank, row in enumerate(results, start=1):
        row["rank"] = rank
    return results


def _write_rankings(
    output_dir: Path,
    metadata: dict[str, Any],
    results: list[dict[str, Any]],
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=KST).strftime("%Y%m%d_%H%M%S")
    stem = f"rl_preopen_tuning_{metadata['mode']}_{stamp}"

    json_path = output_dir / f"{stem}.json"
    payload = {"metadata": metadata, "results": results}
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    csv_path = output_dir / f"{stem}.csv"
    fieldnames = [
        "rank",
        "score",
        "hold_override_max_gap",
        "hold_override_min_entry_prob",
        "hold_override_min_confidence",
        "signals",
        "long_signals",
        "short_signals",
        "win_rate",
        "long_win_rate",
        "short_win_rate",
        "avg_signed_return_bps",
        "avg_long_return_bps",
        "avg_short_return_bps",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    return json_path, csv_path


def _write_profiles(
    base_config: dict[str, Any],
    asset: str,
    profile_prefix: str,
    mode: str,
    tune_target: str,
    best_rows: list[dict[str, Any]],
) -> list[Path]:
    if len(best_rows) < 2:
        return []

    profile_names = [f"{profile_prefix}_a", f"{profile_prefix}_b"]
    paths: list[Path] = []

    for profile_name, row in zip(profile_names, best_rows[:2]):
        cfg = deepcopy(base_config)
        strategy_cfg = cfg.setdefault("strategy", {})
        strategy_cfg["name"] = profile_name
        strategy_cfg["enabled"] = False
        strategy_cfg["description"] = (
            f"RL M-PPO tuned profile {profile_name[-1].upper()} ({mode})"
        )
        entry_params = strategy_cfg.setdefault("entry", {}).setdefault("params", {})
        if tune_target in {"base", "both"}:
            entry_params["hold_override_max_gap"] = float(row["hold_override_max_gap"])
            entry_params["hold_override_min_entry_prob"] = float(
                row["hold_override_min_entry_prob"]
            )
            entry_params["hold_override_min_confidence"] = float(
                row["hold_override_min_confidence"]
            )
            entry_params["backtest_hold_override_min_confidence"] = round(
                max(0.0, min(1.0, float(row["hold_override_min_confidence"]) - 0.05)),
                3,
            )
        if tune_target in {"paper", "both"}:
            entry_params["paper_enable_hold_override"] = True
            entry_params["paper_hold_override_max_gap"] = float(
                row["hold_override_max_gap"]
            )
            entry_params["paper_hold_override_min_entry_prob"] = float(
                row["hold_override_min_entry_prob"]
            )
            entry_params["paper_hold_override_min_confidence"] = float(
                row["hold_override_min_confidence"]
            )

        path = (
            REPO_ROOT
            / "config"
            / "strategies"
            / asset
            / f"{profile_name}.yaml"
        )
        with path.open("w", encoding="utf-8") as fp:
            yaml.safe_dump(cfg, fp, sort_keys=False, allow_unicode=False)
        paths.append(path)

    return paths


def _print_top(results: list[dict[str, Any]], top_k: int) -> None:
    print(
        f"{'rank':>4} {'score':>9} {'gap':>7} {'entry':>7} {'conf':>7} "
        f"{'sig':>5} {'long':>5} {'short':>6} {'long_bps':>10}"
    )
    for row in results[:top_k]:
        print(
            f"{int(row['rank']):>4} "
            f"{float(row['score']):>9.3f} "
            f"{float(row['hold_override_max_gap']):>7.3f} "
            f"{float(row['hold_override_min_entry_prob']):>7.3f} "
            f"{float(row['hold_override_min_confidence']):>7.3f} "
            f"{int(row['signals']):>5} "
            f"{int(row['long_signals']):>5} "
            f"{int(row['short_signals']):>6} "
            f"{float(row['avg_long_return_bps']):>10.2f}"
        )


async def _async_main(args: argparse.Namespace) -> int:
    symbols = _parse_symbols(args.symbols)
    max_gap_grid = _parse_float_grid(args.max_gap_grid, "max-gap-grid")
    min_entry_prob_grid = _parse_float_grid(
        args.min_entry_prob_grid,
        "min-entry-prob-grid",
    )
    min_conf_grid = _parse_float_grid(args.min_conf_grid, "min-conf-grid")

    if args.lookahead < 1:
        raise ValueError("--lookahead must be >= 1")
    if args.warmup < 1:
        raise ValueError("--warmup must be >= 1")

    base_cfg = ConfigLoader.load_strategy(args.asset, args.base_strategy, use_cache=False)
    base_entry = (
        base_cfg.get("strategy", {})
        .get("entry", {})
        .get("params", {})
    )
    if not isinstance(base_entry, dict) or not base_entry:
        raise ValueError("Base strategy entry params are empty")

    candle_cache = _load_candles(
        asset=args.asset,
        symbols=symbols,
        limit_candles=args.limit_candles,
    )
    if not candle_cache:
        raise RuntimeError(
            f"No candle cache found for asset={args.asset}. "
            "Run trading first so candle cache is persisted to Redis."
        )

    print(
        f"Loaded candle cache: {len(candle_cache)} symbols, "
        f"{sum(len(v) for v in candle_cache.values())} candles"
    )

    results = await _run_grid_search(
        base_entry=base_entry,
        candle_cache=candle_cache,
        lookahead=args.lookahead,
        warmup=args.warmup,
        mode=args.mode,
        evaluation_mode=args.evaluation_mode,
        tune_target=args.tune_target,
        max_gap_grid=max_gap_grid,
        min_entry_prob_grid=min_entry_prob_grid,
        min_conf_grid=min_conf_grid,
    )
    if not results:
        raise RuntimeError("No tuning results produced")

    metadata = {
        "generated_at": datetime.now(tz=KST).isoformat(),
        "asset": args.asset,
        "base_strategy": args.base_strategy,
        "mode": args.mode,
        "evaluation_mode": args.evaluation_mode,
        "tune_target": args.tune_target,
        "symbols": sorted(candle_cache.keys()),
        "lookahead": args.lookahead,
        "warmup": args.warmup,
        "limit_candles": args.limit_candles,
        "grid": {
            "max_gap": max_gap_grid,
            "min_entry_prob": min_entry_prob_grid,
            "min_confidence": min_conf_grid,
        },
    }

    json_path, csv_path = _write_rankings(
        output_dir=Path(args.output_dir),
        metadata=metadata,
        results=results,
    )

    print("\nTop candidates")
    _print_top(results, top_k=args.top_k)
    print(f"\nSaved JSON: {json_path}")
    print(f"Saved CSV : {csv_path}")

    if args.write_profiles:
        profile_paths = _write_profiles(
            base_config=base_cfg,
            asset=args.asset,
            profile_prefix=args.profile_prefix,
            mode=args.mode,
            tune_target=args.tune_target,
            best_rows=results,
        )
        if profile_paths:
            print("\nWrote profiles:")
            for path in profile_paths:
                print(f"- {path}")
                print(
                    f"  sts trade start -a {args.asset} -s {path.stem} "
                    "--paper --single"
                )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tune RL hold-override params from Redis candle cache",
    )
    parser.add_argument("--asset", default="futures", help="Asset class")
    parser.add_argument(
        "--base-strategy",
        default="rl_mppo",
        help="Base strategy YAML name to clone params from",
    )
    parser.add_argument(
        "--symbols",
        default="",
        help="Comma-separated symbol filter (default: all cached symbols)",
    )
    parser.add_argument(
        "--lookahead",
        type=int,
        default=5,
        help="Forward bars for simple return scoring",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=120,
        help="Bars before first evaluation",
    )
    parser.add_argument(
        "--limit-candles",
        type=int,
        default=0,
        help="Use only the latest N candles per symbol (0 = all)",
    )
    parser.add_argument(
        "--mode",
        choices=["long_bias", "balanced"],
        default="long_bias",
        help="Scoring mode",
    )
    parser.add_argument(
        "--evaluation-mode",
        choices=["live", "paper", "backtest"],
        default="live",
        help="Threshold path used during replay context",
    )
    parser.add_argument(
        "--tune-target",
        choices=["base", "paper", "both"],
        default="base",
        help="Which hold-override fields to tune/write",
    )
    parser.add_argument(
        "--max-gap-grid",
        default="0.08,0.10,0.12,0.15",
        help="Comma-separated grid for hold_override_max_gap",
    )
    parser.add_argument(
        "--min-entry-prob-grid",
        default="0.30,0.33,0.35",
        help="Comma-separated grid for hold_override_min_entry_prob",
    )
    parser.add_argument(
        "--min-conf-grid",
        default="0.32,0.35,0.38,0.40",
        help="Comma-separated grid for hold_override_min_confidence",
    )
    parser.add_argument(
        "--output-dir",
        default="output/analysis",
        help="Directory for JSON/CSV rankings",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Print top K rows",
    )
    parser.add_argument(
        "--write-profiles",
        action="store_true",
        help="Write top-2 tuned profiles to config/strategies/<asset>/",
    )
    parser.add_argument(
        "--profile-prefix",
        default="rl_mppo_tune",
        help="Prefix for generated profile names",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable INFO logs",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    try:
        return asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
