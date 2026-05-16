#!/usr/bin/env python3
"""Gate stock strategy backtest candidates against paper-trading objectives.

The portfolio backtest runner emits one metrics JSON and one trades CSV per
run. This script groups those files by strategy/override/sizing signature and
evaluates every available window for the same candidate against the active
stock paper targets from ``config/stock_paper_verification.yaml``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.config.loader import ConfigLoader  # noqa: E402


@dataclass(frozen=True)
class CandidateTargets:
    min_closed_trades: int
    min_windows: int
    min_monthly_expected_return_pct: float
    min_win_rate_pct: float
    target_win_rate_max_pct: float
    max_mdd_pct: float
    require_positive_equity_slope: bool
    strict_win_rate_band: bool


@dataclass(frozen=True)
class CandidateIssue:
    severity: str
    code: str
    observed: str
    expected: str
    detail: str


@dataclass
class CandidateWindow:
    label: str
    metrics_path: str
    trades_path: str
    start: str
    end: str
    total_trades: int
    monthly_expected_return_pct: float
    win_rate_pct: float
    max_drawdown_pct: float
    total_return_pct: float
    equity_slope_per_trade: float
    equity_is_upward: bool
    issues: list[CandidateIssue] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if any(issue.severity == "FAIL" for issue in self.issues):
            return "FAIL"
        if self.issues:
            return "WARN"
        return "PASS"


@dataclass
class CandidateReport:
    candidate_id: str
    signature: dict[str, Any]
    windows: list[CandidateWindow]
    issues: list[CandidateIssue]
    fail_count: int
    warn_count: int
    score: float

    @property
    def verdict(self) -> str:
        if self.fail_count:
            return "FAIL"
        if self.warn_count:
            return "WARN"
        return "PASS"


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _as_float(value: Any, default: float) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def load_targets(
    config_path: str,
    *,
    strict_win_rate_band: bool | None = None,
    min_windows: int = 2,
) -> CandidateTargets:
    cfg = ConfigLoader.load(config_path, use_cache=False)
    if not isinstance(cfg, dict):
        raise ValueError(f"Config did not load as a mapping: {config_path}")
    targets = cfg.get("targets", {}) or {}

    return CandidateTargets(
        min_closed_trades=_as_int(targets.get("min_closed_trades_for_metric_gate"), 5),
        min_windows=max(1, int(min_windows)),
        min_monthly_expected_return_pct=_as_float(
            targets.get("min_monthly_expected_return_pct"), 10.0
        ),
        min_win_rate_pct=_as_float(targets.get("min_win_rate_pct"), 55.0),
        target_win_rate_max_pct=_as_float(targets.get("target_win_rate_max_pct"), 60.0),
        max_mdd_pct=_as_float(targets.get("max_mdd_pct"), 10.0),
        require_positive_equity_slope=_as_bool(
            targets.get("require_positive_equity_slope"), True
        ),
        strict_win_rate_band=(
            True if strict_win_rate_band is None else bool(strict_win_rate_band)
        ),
    )


def _metrics_to_trades_path(metrics_path: Path) -> Path:
    name = metrics_path.name
    if name.endswith("_metrics.json"):
        return metrics_path.with_name(
            f"{name.removesuffix('_metrics.json')}_trades.csv"
        )
    return metrics_path.with_suffix(".csv")


def _equity_shape_from_trades(trades_path: Path) -> tuple[float, bool]:
    if not trades_path.exists():
        return 0.0, False

    rows: list[tuple[str, float]] = []
    with trades_path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw_pnl = row.get("pnl", "")
            try:
                pnl = float(raw_pnl)
            except (TypeError, ValueError):
                continue
            sort_key = row.get("exit_time") or row.get("entry_time") or ""
            rows.append((sort_key, pnl))

    if not rows:
        return 0.0, False

    equity: list[float] = []
    cumulative = 0.0
    for _, pnl in sorted(rows, key=lambda item: item[0]):
        cumulative += pnl
        equity.append(cumulative)

    if len(equity) == 1:
        slope = equity[0]
    else:
        x_mean = (len(equity) - 1) / 2.0
        y_mean = sum(equity) / len(equity)
        numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(equity))
        denominator = sum((i - x_mean) ** 2 for i in range(len(equity)))
        slope = numerator / denominator if denominator else 0.0

    return slope, bool(equity[-1] > 0.0 and slope > 0.0)


def _candidate_signature(metrics: dict[str, Any]) -> dict[str, Any]:
    config = metrics.get("config", {}) or {}
    return {
        "strategy": metrics.get("strategy", ""),
        "timeframe": metrics.get("timeframe", ""),
        "tier": metrics.get("tier", ""),
        "scope_label": metrics.get("scope_label", ""),
        "symbols_selected": metrics.get("symbols_selected", []),
        "strategy_overrides": metrics.get("strategy_overrides", []),
        "order_amount_per_stock": config.get("order_amount_per_stock"),
        "max_positions": config.get("max_positions"),
    }


def _candidate_id(signature: dict[str, Any]) -> str:
    raw = json.dumps(signature, sort_keys=True, ensure_ascii=False, default=str)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    strategy = str(signature.get("strategy") or "candidate")
    return f"{strategy}-{digest}"


def _add_issue(
    issues: list[CandidateIssue],
    severity: str,
    code: str,
    observed: str,
    expected: str,
    detail: str,
) -> None:
    issues.append(CandidateIssue(severity, code, observed, expected, detail))


def evaluate_metrics_file(
    metrics_path: Path, targets: CandidateTargets
) -> tuple[dict[str, Any], CandidateWindow]:
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    trades_path = _metrics_to_trades_path(metrics_path)
    slope, is_upward = _equity_shape_from_trades(trades_path)

    total_trades = _as_int(metrics.get("total_trades"), 0)
    monthly_return = _as_float(metrics.get("monthly_expected_return_pct"), 0.0)
    win_rate = _as_float(metrics.get("win_rate"), 0.0)
    mdd = _as_float(metrics.get("max_drawdown_pct"), 0.0)
    total_return = _as_float(metrics.get("total_return_pct"), 0.0)
    issues: list[CandidateIssue] = []

    if total_trades == 0:
        _add_issue(
            issues,
            "FAIL",
            "no_closed_trades",
            "0",
            "> 0",
            "No closed trades in this backtest window.",
        )
    elif total_trades < targets.min_closed_trades:
        _add_issue(
            issues,
            "FAIL",
            "insufficient_closed_trades",
            str(total_trades),
            f">= {targets.min_closed_trades}",
            "Candidate has too few closed trades for an objective gate.",
        )

    if monthly_return < targets.min_monthly_expected_return_pct:
        _add_issue(
            issues,
            "FAIL",
            "monthly_expected_return_below_target",
            f"{monthly_return:.2f}%",
            f">= {targets.min_monthly_expected_return_pct:.2f}%",
            "Monthly expected return is below the stock paper objective.",
        )

    if win_rate < targets.min_win_rate_pct:
        _add_issue(
            issues,
            "FAIL",
            "win_rate_below_target",
            f"{win_rate:.2f}%",
            f">= {targets.min_win_rate_pct:.2f}%",
            "Win rate is below the target band.",
        )
    elif win_rate > targets.target_win_rate_max_pct:
        severity = "FAIL" if targets.strict_win_rate_band else "WARN"
        _add_issue(
            issues,
            severity,
            "win_rate_above_target_band",
            f"{win_rate:.2f}%",
            f"{targets.min_win_rate_pct:.2f}% to {targets.target_win_rate_max_pct:.2f}%",
            "Win rate is above the target band; check overfitting or capped exits.",
        )

    if mdd > targets.max_mdd_pct:
        _add_issue(
            issues,
            "FAIL",
            "mdd_above_target",
            f"{mdd:.2f}%",
            f"<= {targets.max_mdd_pct:.2f}%",
            "Max drawdown is above the stock paper objective.",
        )

    if targets.require_positive_equity_slope and not is_upward:
        _add_issue(
            issues,
            "FAIL",
            "equity_curve_not_upward",
            f"slope={slope:.2f}",
            "positive slope and positive ending equity",
            "Closed-trade equity curve is not upward in this window.",
        )

    window = CandidateWindow(
        label=f"{metrics.get('start', '')}~{metrics.get('end', '')}",
        metrics_path=str(metrics_path),
        trades_path=str(trades_path),
        start=str(metrics.get("start", "")),
        end=str(metrics.get("end", "")),
        total_trades=total_trades,
        monthly_expected_return_pct=monthly_return,
        win_rate_pct=win_rate,
        max_drawdown_pct=mdd,
        total_return_pct=total_return,
        equity_slope_per_trade=slope,
        equity_is_upward=is_upward,
        issues=issues,
    )
    return _candidate_signature(metrics), window


def _score_window(window: CandidateWindow, targets: CandidateTargets) -> float:
    monthly_gap = max(
        0.0,
        targets.min_monthly_expected_return_pct - window.monthly_expected_return_pct,
    )
    win_low_gap = max(0.0, targets.min_win_rate_pct - window.win_rate_pct)
    win_high_gap = (
        max(0.0, window.win_rate_pct - targets.target_win_rate_max_pct)
        if targets.strict_win_rate_band
        else 0.0
    )
    mdd_gap = max(0.0, window.max_drawdown_pct - targets.max_mdd_pct)
    trade_gap = max(0, targets.min_closed_trades - window.total_trades)
    equity_penalty = 10.0 if not window.equity_is_upward else 0.0
    return (
        monthly_gap * 3.0
        + win_low_gap
        + win_high_gap * 0.5
        + mdd_gap * 2.0
        + trade_gap * 2.0
        + equity_penalty
    )


def _candidate_level_issues(
    windows: list[CandidateWindow], targets: CandidateTargets
) -> list[CandidateIssue]:
    issues: list[CandidateIssue] = []
    if len(windows) < targets.min_windows:
        _add_issue(
            issues,
            "FAIL",
            "insufficient_backtest_windows",
            str(len(windows)),
            f">= {targets.min_windows}",
            "Candidate needs both recent and longer-window evidence before promotion.",
        )
    return issues


def build_reports(
    metrics_paths: list[Path], targets: CandidateTargets
) -> list[CandidateReport]:
    grouped: dict[str, tuple[dict[str, Any], list[CandidateWindow]]] = {}
    for metrics_path in metrics_paths:
        signature, window = evaluate_metrics_file(metrics_path, targets)
        cid = _candidate_id(signature)
        if cid not in grouped:
            grouped[cid] = (signature, [])
        grouped[cid][1].append(window)

    reports: list[CandidateReport] = []
    for cid, (signature, windows) in grouped.items():
        windows.sort(key=lambda w: (w.start, w.end, w.metrics_path))
        report_issues = _candidate_level_issues(windows, targets)
        fail_count = sum(
            1 for w in windows for issue in w.issues if issue.severity == "FAIL"
        ) + sum(1 for issue in report_issues if issue.severity == "FAIL")
        warn_count = sum(
            1 for w in windows for issue in w.issues if issue.severity == "WARN"
        ) + sum(1 for issue in report_issues if issue.severity == "WARN")
        score = sum(_score_window(w, targets) for w in windows)
        if len(windows) < targets.min_windows:
            score += (targets.min_windows - len(windows)) * 25.0
        reports.append(
            CandidateReport(
                candidate_id=cid,
                signature=signature,
                windows=windows,
                issues=report_issues,
                fail_count=fail_count,
                warn_count=warn_count,
                score=score,
            )
        )

    reports.sort(
        key=lambda r: (
            r.verdict != "PASS",
            len(r.windows) < targets.min_windows,
            r.fail_count,
            r.score,
            -max((w.monthly_expected_return_pct for w in r.windows), default=0.0),
            r.candidate_id,
        )
    )
    return reports


def _report_to_dict(report: CandidateReport) -> dict[str, Any]:
    data = asdict(report)
    data["verdict"] = report.verdict
    for window_data, window in zip(data["windows"], report.windows, strict=True):
        window_data["verdict"] = window.verdict
    return data


def _format_markdown(
    reports: list[CandidateReport],
    targets: CandidateTargets,
    source_count: int,
) -> str:
    lines = [
        "# Stock Strategy Candidate Gate",
        "",
        f"- Generated at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Metrics files: `{source_count}`",
        (
            "- Targets: "
            f"monthly `>= {targets.min_monthly_expected_return_pct:.2f}%`, "
            f"win `{targets.min_win_rate_pct:.2f}%"
            f"~{targets.target_win_rate_max_pct:.2f}%`, "
            f"MDD `<= {targets.max_mdd_pct:.2f}%`, "
            f"min trades `{targets.min_closed_trades}`, "
            f"min windows `{targets.min_windows}`, "
            f"equity upward `{targets.require_positive_equity_slope}`"
        ),
        "",
        "| Verdict | Candidate | Windows | Best monthly | Worst MDD | Fail/Warn |",
        "|---|---|---:|---:|---:|---:|",
    ]

    for report in reports:
        best_monthly = max(
            (w.monthly_expected_return_pct for w in report.windows), default=0.0
        )
        worst_mdd = max((w.max_drawdown_pct for w in report.windows), default=0.0)
        lines.append(
            f"| {report.verdict} | `{report.candidate_id}` | "
            f"{len(report.windows)} | {best_monthly:.2f}% | {worst_mdd:.2f}% | "
            f"{report.fail_count}/{report.warn_count} |"
        )

    lines.append("")
    for report in reports[:20]:
        sig = report.signature
        lines.extend(
            [
                f"## {report.verdict} `{report.candidate_id}`",
                "",
                f"- Strategy: `{sig.get('strategy')}`",
                f"- Sizing: order `{sig.get('order_amount_per_stock')}`, max positions `{sig.get('max_positions')}`",
                f"- Overrides: `{json.dumps(sig.get('strategy_overrides', []), ensure_ascii=False)}`",
            ]
        )
        if report.issues:
            lines.append(
                "- Candidate issues: `"
                + ", ".join(issue.code for issue in report.issues)
                + "`"
            )
        lines.extend(
            [
                "",
                "| Window | Verdict | Trades | Monthly | Win | MDD | Equity slope | Issues |",
                "|---|---|---:|---:|---:|---:|---:|---|",
            ]
        )
        for window in report.windows:
            issue_codes = ", ".join(issue.code for issue in window.issues) or "-"
            lines.append(
                f"| {window.label} | {window.verdict} | {window.total_trades} | "
                f"{window.monthly_expected_return_pct:.2f}% | "
                f"{window.win_rate_pct:.2f}% | {window.max_drawdown_pct:.2f}% | "
                f"{window.equity_slope_per_trade:.0f} | {issue_codes} |"
            )
        lines.append("")
    return "\n".join(lines)


def _expand_metrics_paths(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matched = sorted(Path().glob(pattern))
        if matched:
            paths.extend(path for path in matched if path.is_file())
            continue
        path = Path(pattern)
        if path.is_file():
            paths.append(path)
    return sorted(set(paths))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate stock strategy backtest candidates against targets."
    )
    parser.add_argument(
        "--config",
        default="stock_paper_verification.yaml",
        help="ConfigLoader-relative stock paper verification config path.",
    )
    parser.add_argument(
        "--metrics-glob",
        action="append",
        default=["reports/candidate_strategy_backtest/*_metrics.json"],
        help="Metrics glob or file path. Can be passed multiple times.",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/candidate_strategy_gate/stock",
        help="Directory for JSON and markdown reports.",
    )
    parser.add_argument(
        "--allow-high-win-rate",
        action="store_true",
        help="Warn, rather than fail, when win rate is above the configured band.",
    )
    parser.add_argument(
        "--min-windows",
        type=int,
        default=2,
        help="Minimum number of distinct backtest windows required per candidate.",
    )
    args = parser.parse_args()

    targets = load_targets(
        args.config,
        strict_win_rate_band=not args.allow_high_win_rate,
        min_windows=args.min_windows,
    )
    metrics_paths = _expand_metrics_paths(args.metrics_glob)
    if not metrics_paths:
        raise SystemExit("No metrics files matched")

    reports = build_reports(metrics_paths, targets)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"stock_candidate_gate_{stamp}.json"
    md_path = output_dir / f"stock_candidate_gate_{stamp}.md"

    payload = {
        "targets": asdict(targets),
        "metrics_files": [str(path) for path in metrics_paths],
        "reports": [_report_to_dict(report) for report in reports],
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path.write_text(
        _format_markdown(reports, targets, len(metrics_paths)), encoding="utf-8"
    )

    pass_count = sum(1 for report in reports if report.verdict == "PASS")
    warn_count = sum(1 for report in reports if report.verdict == "WARN")
    fail_count = sum(1 for report in reports if report.verdict == "FAIL")
    best = reports[0]
    print(
        f"candidates={len(reports)} pass={pass_count} warn={warn_count} fail={fail_count}"
    )
    print(
        f"best={best.candidate_id} verdict={best.verdict} "
        f"fail_count={best.fail_count} score={best.score:.2f}"
    )
    print(f"json={json_path}")
    print(f"markdown={md_path}")


if __name__ == "__main__":
    main()
