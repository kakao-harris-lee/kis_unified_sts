#!/usr/bin/env python3
"""Run configured stock strategy candidate sweeps and gate the results."""

from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.analysis import evaluate_stock_strategy_candidates as gate  # noqa: E402
from shared.config.loader import ConfigLoader  # noqa: E402


@dataclass(frozen=True)
class SweepWindow:
    name: str
    start: str
    end: str


@dataclass(frozen=True)
class SweepRun:
    candidate_name: str
    strategy: str
    window: SweepWindow
    tier: str
    symbols: str
    max_symbols: int | None
    capital: float
    output_dir: str
    order_amount_per_stock: float | None
    max_positions: int | None
    overrides: tuple[tuple[str, Any], ...]

    @property
    def run_id(self) -> str:
        parts = [
            self.candidate_name,
            self.window.name,
            f"order={self.order_amount_per_stock}",
            f"maxpos={self.max_positions}",
        ]
        if self.overrides:
            parts.extend(f"{key}={value}" for key, value in self.overrides)
        return "|".join(parts)


class Runner(Protocol):
    def __call__(
        self,
        cmd: list[str],
        *,
        cwd: Path,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]: ...


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return [None]
    if isinstance(value, list):
        return value or [None]
    return [value]


def _as_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _as_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _format_override_value(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return json.dumps(value)
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def _override_combinations(
    overrides: dict[str, Any],
) -> list[tuple[tuple[str, Any], ...]]:
    if not overrides:
        return [()]
    keys = list(overrides.keys())
    value_lists = [_as_list(overrides[key]) for key in keys]
    combos: list[tuple[tuple[str, Any], ...]] = []
    for values in itertools.product(*value_lists):
        combos.append(tuple(zip(keys, values, strict=True)))
    return combos


def load_sweep_config(path: str) -> dict[str, Any]:
    cfg = ConfigLoader.load(path, use_cache=False)
    if not isinstance(cfg, dict):
        raise ValueError(f"Config did not load as a mapping: {path}")
    sweep = cfg.get("sweep", cfg)
    if not isinstance(sweep, dict):
        raise ValueError(f"Sweep config is not a mapping: {path}")
    return sweep


def expand_sweep_runs(config: dict[str, Any]) -> list[SweepRun]:
    windows = [
        SweepWindow(
            name=str(item.get("name") or f"{item['start']}_{item['end']}"),
            start=str(item["start"]),
            end=str(item["end"]),
        )
        for item in config.get("windows", [])
    ]
    if not windows:
        raise ValueError("sweep.windows must contain at least one window")

    tier = str(config.get("tier") or "all")
    symbols = str(config.get("symbols") or "")
    max_symbols = _as_optional_int(config.get("max_symbols"))
    capital = float(config.get("capital") or 100_000_000)
    output_dir = str(config.get("output_dir") or "reports/candidate_strategy_sweep")

    runs: list[SweepRun] = []
    for candidate in config.get("candidates", []):
        if candidate.get("enabled", True) is False:
            continue
        strategy = str(candidate["strategy"])
        candidate_name = str(candidate.get("name") or strategy)
        order_amounts = _as_list(candidate.get("order_amount_per_stock"))
        max_positions_values = _as_list(candidate.get("max_positions"))
        override_sets = _override_combinations(candidate.get("overrides", {}) or {})

        for window, order_amount, max_positions, overrides in itertools.product(
            windows, order_amounts, max_positions_values, override_sets
        ):
            runs.append(
                SweepRun(
                    candidate_name=candidate_name,
                    strategy=strategy,
                    window=window,
                    tier=str(candidate.get("tier") or tier),
                    symbols=str(candidate.get("symbols") or symbols),
                    max_symbols=_as_optional_int(
                        candidate.get("max_symbols", max_symbols)
                    ),
                    capital=float(candidate.get("capital") or capital),
                    output_dir=str(candidate.get("output_dir") or output_dir),
                    order_amount_per_stock=_as_optional_float(order_amount),
                    max_positions=_as_optional_int(max_positions),
                    overrides=overrides,
                )
            )
    return runs


def build_backtest_command(run: SweepRun, config: dict[str, Any]) -> list[str]:
    python_executable = str(config.get("python") or sys.executable)
    portfolio_script = str(
        config.get("portfolio_script") or "scripts/analysis/backtest_portfolio.py"
    )
    cmd = [
        python_executable,
        portfolio_script,
        "--strategy",
        run.strategy,
        "--tier",
        run.tier,
        "--start",
        run.window.start,
        "--end",
        run.window.end,
        "--capital",
        str(run.capital),
        "--output-dir",
        run.output_dir,
    ]
    if run.symbols:
        cmd.extend(["--symbols", run.symbols])
    if run.max_symbols is not None:
        cmd.extend(["--max-symbols", str(run.max_symbols)])
    if run.order_amount_per_stock is not None:
        cmd.extend(["--order-amount-per-stock", str(run.order_amount_per_stock)])
    if run.max_positions is not None:
        cmd.extend(["--max-positions", str(run.max_positions)])
    for key, value in run.overrides:
        cmd.extend(["--set", f"{key}={_format_override_value(value)}"])
    return cmd


def parse_backtest_paths(stdout: str) -> tuple[str | None, str | None]:
    metrics_path: str | None = None
    trades_path: str | None = None
    for line in stdout.splitlines():
        if line.startswith("metrics="):
            metrics_path = line.split("=", 1)[1].strip()
        elif line.startswith("trades="):
            trades_path = line.split("=", 1)[1].strip()
    return metrics_path, trades_path


def _tail(text: str, max_lines: int = 20) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])


def _write_gate_outputs(
    *,
    metrics_paths: list[Path],
    config: dict[str, Any],
    manifest_dir: Path,
) -> dict[str, Any]:
    if not metrics_paths:
        return {}

    gate_output_dir = Path(config.get("gate_output_dir") or manifest_dir / "gate")
    gate_output_dir.mkdir(parents=True, exist_ok=True)
    targets = gate.load_targets(
        str(config.get("gate_config") or "stock_paper_verification.yaml"),
        strict_win_rate_band=not bool(config.get("allow_high_win_rate", False)),
        min_windows=int(config.get("min_windows") or 2),
    )
    reports = gate.build_reports(metrics_paths, targets)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = gate_output_dir / f"stock_candidate_sweep_gate_{stamp}.json"
    md_path = gate_output_dir / f"stock_candidate_sweep_gate_{stamp}.md"

    payload = {
        "targets": asdict(targets),
        "metrics_files": [str(path) for path in metrics_paths],
        "reports": [gate._report_to_dict(report) for report in reports],
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path.write_text(
        gate._format_markdown(reports, targets, len(metrics_paths)), encoding="utf-8"
    )
    return {
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "pass_count": sum(1 for report in reports if report.verdict == "PASS"),
        "warn_count": sum(1 for report in reports if report.verdict == "WARN"),
        "fail_count": sum(1 for report in reports if report.verdict == "FAIL"),
        "best_candidate": reports[0].candidate_id if reports else None,
        "best_verdict": reports[0].verdict if reports else None,
    }


def run_sweep(
    config: dict[str, Any],
    *,
    dry_run: bool = False,
    max_runs: int | None = None,
    candidate_names: set[str] | None = None,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    runs = expand_sweep_runs(config)
    if candidate_names:
        runs = [run for run in runs if run.candidate_name in candidate_names]
    if max_runs is not None:
        runs = runs[: max(0, max_runs)]

    run_results: list[dict[str, Any]] = []
    metrics_paths: list[Path] = []
    for run in runs:
        cmd = build_backtest_command(run, config)
        result: dict[str, Any] = {
            "run_id": run.run_id,
            "candidate_name": run.candidate_name,
            "window": asdict(run.window),
            "command": cmd,
            "dry_run": dry_run,
            "returncode": None,
            "metrics_path": None,
            "trades_path": None,
        }
        if not dry_run:
            completed = runner(
                cmd,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            metrics_path, trades_path = parse_backtest_paths(completed.stdout)
            result.update(
                {
                    "returncode": completed.returncode,
                    "metrics_path": metrics_path,
                    "trades_path": trades_path,
                    "stdout_tail": _tail(completed.stdout),
                    "stderr_tail": _tail(completed.stderr),
                }
            )
            if completed.returncode == 0 and metrics_path:
                metrics_paths.append(Path(metrics_path))
        run_results.append(result)

    manifest_dir = Path(config.get("manifest_dir") or config.get("output_dir") or ".")
    manifest_dir.mkdir(parents=True, exist_ok=True)
    gate_summary = (
        {}
        if dry_run
        else _write_gate_outputs(
            metrics_paths=metrics_paths, config=config, manifest_dir=manifest_dir
        )
    )
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    manifest_path = manifest_dir / f"stock_candidate_sweep_{stamp}.json"
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "planned_runs": len(runs),
        "successful_runs": sum(1 for item in run_results if item["returncode"] == 0),
        "failed_runs": sum(
            1 for item in run_results if item["returncode"] not in (None, 0)
        ),
        "gate": gate_summary,
        "runs": run_results,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run configured stock strategy candidate sweeps."
    )
    parser.add_argument(
        "--config",
        default="stock_strategy_candidate_sweep.yaml",
        help="ConfigLoader-relative sweep YAML path.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="Run only the first N expanded backtests for smoke checks.",
    )
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        help="Candidate name to run. Can be passed multiple times.",
    )
    args = parser.parse_args()

    config = load_sweep_config(args.config)
    manifest = run_sweep(
        config,
        dry_run=args.dry_run,
        max_runs=args.max_runs,
        candidate_names=set(args.candidate) if args.candidate else None,
    )
    print(
        f"planned={manifest['planned_runs']} successful={manifest['successful_runs']} "
        f"failed={manifest['failed_runs']} dry_run={manifest['dry_run']}"
    )
    gate_summary = manifest.get("gate") or {}
    if gate_summary:
        print(
            f"gate pass={gate_summary['pass_count']} warn={gate_summary['warn_count']} "
            f"fail={gate_summary['fail_count']} best={gate_summary['best_candidate']}"
        )
        print(f"gate_markdown={gate_summary['markdown_path']}")
    print(f"manifest={manifest['manifest_path']}")


if __name__ == "__main__":
    main()
