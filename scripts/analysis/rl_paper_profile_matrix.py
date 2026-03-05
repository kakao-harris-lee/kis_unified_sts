#!/usr/bin/env python3
"""Run/analyze RL paper profile matrix experiments.

Purpose:
1) Rotate multiple RL strategy profiles in paper mode (time-sliced runs)
2) Parse logs and rank profiles for uptrend-biased selection

Examples:
  .venv/bin/python scripts/analysis/rl_paper_profile_matrix.py \
    --profiles rl_mppo,rl_mppo_profile_asym_long_strict,rl_mppo_tune_a,rl_mppo_tune_b \
    --duration-minutes 30

  .venv/bin/python scripts/analysis/rl_paper_profile_matrix.py \
    --analyze-only --logs logs/rl_paper_20260227.log
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

PROFILE_RE = re.compile(r"Strategy:\s+([A-Za-z0-9_\-]+)")
MATRIX_PROFILE_RE = re.compile(r"^\[matrix\]\s+profile=(.+)$")
ENTRY_SIGNALS_RE = re.compile(r"Entry signals:\s*(\d+)")
BLOCK_RE = re.compile(r"Entry blocked by execution guard:\s+\S+\s+([^\s]+)")
SLIPPAGE_RE = re.compile(r"slippage=([+-]?\d+(?:\.\d+)?)t")
EXIT_PNL_RE = re.compile(r"Exit executed: .*pnl=([+-]?\d+(?:\.\d+)?)%")

# Matrix presets for paper slippage guard tuning.
# label -> strategy + env overrides
PROFILE_PRESETS: dict[str, dict[str, Any]] = {
    "rl_mppo_spread6": {
        "strategy": "rl_mppo",
        "env": {
            "FUTURES_PAPER_MAX_SPREAD_TICKS": "6",
            "FUTURES_PAPER_MIN_DEPTH_MULTIPLIER": "1.0",
            "FUTURES_PAPER_MAX_PRICE_DEVIATION_TICKS": "6",
            "FUTURES_PAPER_CROSS_ASSET_ENABLED": "false",
        },
    },
    "rl_mppo_spread7": {
        "strategy": "rl_mppo",
        "env": {
            "FUTURES_PAPER_MAX_SPREAD_TICKS": "7",
            "FUTURES_PAPER_MIN_DEPTH_MULTIPLIER": "1.0",
            "FUTURES_PAPER_MAX_PRICE_DEVIATION_TICKS": "7",
            "FUTURES_PAPER_CROSS_ASSET_ENABLED": "false",
        },
    },
    "rl_mppo_spread8": {
        "strategy": "rl_mppo",
        "env": {
            "FUTURES_PAPER_MAX_SPREAD_TICKS": "8",
            "FUTURES_PAPER_MIN_DEPTH_MULTIPLIER": "1.0",
            "FUTURES_PAPER_MAX_PRICE_DEVIATION_TICKS": "8",
            "FUTURES_PAPER_CROSS_ASSET_ENABLED": "false",
        },
    },
}


def _parse_profiles(raw: str) -> list[str]:
    profiles = [item.strip() for item in raw.split(",") if item.strip()]
    if not profiles:
        raise ValueError("No profiles provided")
    return profiles


def _resolve_profile(token: str) -> tuple[str, str, dict[str, str]]:
    preset = PROFILE_PRESETS.get(token)
    if not preset:
        return token, token, {}
    strategy = str(preset.get("strategy", token)).strip() or token
    env_payload = preset.get("env", {})
    env_overrides = (
        {str(k): str(v) for k, v in env_payload.items()}
        if isinstance(env_payload, dict)
        else {}
    )
    return token, strategy, env_overrides


def _infer_profile(log_path: Path) -> str:
    fallback = log_path.stem
    try:
        with log_path.open(encoding="utf-8", errors="replace") as fp:
            for _ in range(300):
                line = fp.readline()
                if not line:
                    break
                matrix_matched = MATRIX_PROFILE_RE.search(line.strip())
                if matrix_matched:
                    value = matrix_matched.group(1).strip()
                    if value:
                        return value
                matched = PROFILE_RE.search(line)
                if matched:
                    return matched.group(1).strip()
    except OSError:
        return fallback
    return fallback


def _compute_uptrend_score(metrics: dict[str, Any]) -> float:
    score = 0.0
    score += float(metrics["total_pnl_pct"]) * 25.0
    score += float(metrics["win_rate"]) * 35.0
    score += float(metrics["entry_fill_rate"]) * 30.0
    score += float(metrics["signal_execution_rate"]) * 10.0
    score -= float(metrics["avg_slippage_ticks_abs"]) * 8.0
    score -= float(metrics["blocks_wide_spread"]) * 0.15
    score -= float(metrics["blocks_insufficient_depth"]) * 0.15
    if int(metrics["exits"]) == 0:
        score -= 8.0
    return round(score, 4)


def parse_paper_log(log_path: Path, profile: str | None = None) -> dict[str, Any]:
    entry_signals = 0
    entries = 0
    exits = 0
    block_counts: dict[str, int] = {}
    slippages: list[float] = []
    pnl_pcts: list[float] = []

    with log_path.open(encoding="utf-8", errors="replace") as fp:
        for line in fp:
            match = ENTRY_SIGNALS_RE.search(line)
            if match:
                entry_signals += int(match.group(1))

            if "Entry executed:" in line:
                entries += 1

            match = BLOCK_RE.search(line)
            if match:
                raw_reason = match.group(1).strip()
                reason = raw_reason.split(":", 1)[0] if ":" in raw_reason else raw_reason
                block_counts[reason] = block_counts.get(reason, 0) + 1

            match = SLIPPAGE_RE.search(line)
            if match:
                slippages.append(float(match.group(1)))

            match = EXIT_PNL_RE.search(line)
            if match:
                pnl_pcts.append(float(match.group(1)))
                exits += 1

    blocked_total = sum(block_counts.values())
    attempts = entries + blocked_total
    wins = sum(1 for pnl in pnl_pcts if pnl > 0.0)

    fill_rate = (entries / attempts) if attempts > 0 else 0.0
    signal_exec_rate = (entries / entry_signals) if entry_signals > 0 else 0.0
    win_rate = (wins / exits) if exits > 0 else 0.0

    metrics: dict[str, Any] = {
        "profile": profile or _infer_profile(log_path),
        "log_file": str(log_path),
        "entry_signals": int(entry_signals),
        "entries": int(entries),
        "exits": int(exits),
        "blocked_total": int(blocked_total),
        "blocks_wide_spread": int(block_counts.get("wide_spread", 0)),
        "blocks_insufficient_depth": int(block_counts.get("insufficient_depth", 0)),
        "blocks_volatility_cooldown": int(block_counts.get("volatility_cooldown", 0)),
        "blocks_cross_asset_wide_spread": int(
            block_counts.get("cross_asset_wide_spread", 0)
        ),
        "entry_fill_rate": round(fill_rate, 4),
        "signal_execution_rate": round(signal_exec_rate, 4),
        "avg_slippage_ticks": round(mean(slippages), 4) if slippages else 0.0,
        "avg_slippage_ticks_abs": (
            round(mean([abs(item) for item in slippages]), 4) if slippages else 0.0
        ),
        "win_rate": round(win_rate, 4),
        "avg_pnl_pct": round(mean(pnl_pcts), 4) if pnl_pcts else 0.0,
        "total_pnl_pct": round(sum(pnl_pcts), 4),
    }
    metrics["uptrend_score"] = _compute_uptrend_score(metrics)
    return metrics


def _write_summary(rows: list[dict[str, Any]], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"paper_profile_matrix_summary_{stamp}.csv"
    json_path = output_dir / f"paper_profile_matrix_summary_{stamp}.json"

    fields = [
        "profile",
        "uptrend_score",
        "entry_signals",
        "entries",
        "exits",
        "blocked_total",
        "blocks_wide_spread",
        "blocks_insufficient_depth",
        "blocks_volatility_cooldown",
        "blocks_cross_asset_wide_spread",
        "entry_fill_rate",
        "signal_execution_rate",
        "win_rate",
        "avg_pnl_pct",
        "total_pnl_pct",
        "avg_slippage_ticks",
        "avg_slippage_ticks_abs",
        "log_file",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})

    payload = {
        "generated_at": datetime.now().isoformat(),
        "rows": rows,
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return csv_path, json_path


def _print_rank(rows: list[dict[str, Any]]) -> None:
    print(
        f"{'rank':>4} {'profile':<36} {'score':>8} {'sig':>5} {'ent':>5} {'exit':>5} "
        f"{'fill%':>7} {'win%':>7} {'pnl%':>8} {'spread_blk':>10} {'depth_blk':>9}"
    )
    for idx, row in enumerate(rows, start=1):
        print(
            f"{idx:>4} "
            f"{str(row['profile']):<36} "
            f"{float(row['uptrend_score']):>8.2f} "
            f"{int(row['entry_signals']):>5} "
            f"{int(row['entries']):>5} "
            f"{int(row['exits']):>5} "
            f"{float(row['entry_fill_rate']) * 100:>7.1f} "
            f"{float(row['win_rate']) * 100:>7.1f} "
            f"{float(row['total_pnl_pct']):>8.2f} "
            f"{int(row['blocks_wide_spread']):>10} "
            f"{int(row['blocks_insufficient_depth']):>9}"
        )


def _run_profile(
    *,
    profile_label: str,
    strategy: str,
    model: str,
    duration_minutes: int,
    log_path: Path,
    env_overrides: dict[str, str],
    dry_run: bool,
) -> int:
    sts_bin = REPO_ROOT / ".venv/bin/sts"
    if not sts_bin.exists():
        raise FileNotFoundError(f"sts binary not found: {sts_bin}")

    duration_seconds = int(duration_minutes * 60)
    # Guard against graceful-shutdown hangs: send TERM at duration, then
    # force-kill if process does not exit within the grace period.
    kill_after_seconds = max(20, min(90, int(duration_minutes * 10)))
    cmd = [
        "timeout",
        "--signal=TERM",
        "--kill-after",
        f"{kill_after_seconds}s",
        f"{duration_seconds}s",
        str(sts_bin),
        "rl",
        "paper",
        "--model",
        model,
        "--strategy",
        strategy,
        "--no-daemon",
    ]

    if dry_run:
        print("[dry-run]", " ".join(cmd))
        return 0

    env = os.environ.copy()
    env["RL_PAPER_MATRIX_PROFILE"] = profile_label
    # Isolate profile evaluation from previous session carry-over.
    env["STS_DISABLE_POSITION_RECOVERY"] = "1"
    env.update(env_overrides)

    with log_path.open("w", encoding="utf-8") as fp:
        fp.write(f"[matrix] started_at={datetime.now().isoformat()}\n")
        fp.write(f"[matrix] profile={profile_label}\n")
        fp.write(f"[matrix] strategy={strategy}\n")
        fp.write(f"[matrix] model={model}\n")
        fp.write(f"[matrix] duration_minutes={duration_minutes}\n")
        if env_overrides:
            fp.write(f"[matrix] env_overrides={json.dumps(env_overrides, ensure_ascii=False)}\n")
        fp.write(f"[matrix] command={' '.join(cmd)}\n")
        fp.flush()

        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            env=env,
            stdout=fp,
            stderr=subprocess.STDOUT,
            check=False,
        )

        fp.write(f"[matrix] exit_code={proc.returncode}\n")
        fp.write(f"[matrix] ended_at={datetime.now().isoformat()}\n")
        fp.flush()
    return int(proc.returncode)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run/analyze RL paper profile matrix experiments",
    )
    parser.add_argument(
        "--profiles",
        default=(
            "rl_mppo_spread6,"
            "rl_mppo_spread7,"
            "rl_mppo_spread8,"
            "rl_mppo_profile_asym_long_strict,"
            "rl_mppo_profile_uptrend_spike_guard"
        ),
        help="Comma-separated strategy profile names",
    )
    parser.add_argument("--model", default="mppo_best", help="RL model name")
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=30,
        help="Per-profile run duration in minutes",
    )
    parser.add_argument(
        "--cooldown-seconds",
        type=int,
        default=8,
        help="Sleep between profile runs",
    )
    parser.add_argument(
        "--output-dir",
        default="output/paper_matrix",
        help="Directory for logs and summary outputs",
    )
    parser.add_argument(
        "--run-dir",
        default="",
        help="Explicit run directory for execution mode (overrides auto timestamp dir)",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Skip execution and only parse logs",
    )
    parser.add_argument(
        "--logs",
        default="",
        help="Comma-separated log paths to parse (used with --analyze-only)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print commands only")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output_root = Path(args.output_dir)
    profiles = _parse_profiles(args.profiles)

    log_entries: list[tuple[str, Path]] = []
    if args.analyze_only:
        logs = [item.strip() for item in args.logs.split(",") if item.strip()]
        if not logs:
            raise ValueError("--analyze-only requires --logs")
        for log in logs:
            path = Path(log)
            if not path.exists():
                raise FileNotFoundError(f"Log not found: {path}")
            log_entries.append((_infer_profile(path), path))
    else:
        run_dir = (
            Path(args.run_dir)
            if str(args.run_dir).strip()
            else output_root / datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        run_dir.mkdir(parents=True, exist_ok=True)
        print(f"Run directory: {run_dir}")

        for idx, profile_token in enumerate(profiles, start=1):
            profile_label, strategy, env_overrides = _resolve_profile(profile_token)
            log_path = run_dir / f"{idx:02d}_{profile_label}.log"
            print(
                f"[{idx}/{len(profiles)}] running {profile_label} "
                f"(strategy={strategy}, {args.duration_minutes}m)"
            )
            code = _run_profile(
                profile_label=profile_label,
                strategy=strategy,
                model=args.model,
                duration_minutes=args.duration_minutes,
                log_path=log_path,
                env_overrides=env_overrides,
                dry_run=bool(args.dry_run),
            )
            log_entries.append((profile_label, log_path))
            timed_out = (code == 124)
            print(
                f"  exit_code={code}"
                + (" (timeout as expected)" if timed_out else "")
                + f", log={log_path}"
            )
            if not args.dry_run and idx < len(profiles) and args.cooldown_seconds > 0:
                time.sleep(args.cooldown_seconds)

    if args.dry_run and not args.analyze_only:
        print("\nDry-run complete. No logs were generated; summary step skipped.")
        return 0

    rows = [parse_paper_log(path, profile=profile) for profile, path in log_entries]
    rows.sort(
        key=lambda item: (
            float(item["uptrend_score"]),
            float(item["total_pnl_pct"]),
            float(item["entry_fill_rate"]),
        ),
        reverse=True,
    )

    _print_rank(rows)
    summary_dir = output_root if args.analyze_only else log_entries[0][1].parent
    csv_path, json_path = _write_summary(rows, summary_dir)
    print(f"\nSaved CSV : {csv_path}")
    print(f"Saved JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
