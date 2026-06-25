"""Read-only readiness report for disabled stock strategy follow-ups.

This tool evaluates offline evidence for strategies that are under review. It
does not read or mutate strategy YAML and does not enable any trading behavior.

Usage:
  python -m scripts.ops.stock_strategy_readiness --evidence evidence.json \
    --min-sharpe 0.8 --min-win-rate 52 --max-drawdown-pct 12 --min-trade-count 30
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REVIEW_STRATEGIES = ("technical_consensus", "momentum_breakout")
READY = "ready_for_small_paper"
OBSERVE = "observe_only"
BLOCKED = "blocked"
_PLACEHOLDER_STRINGS = {"", "todo", "tbd", "placeholder", "null", "none", "n/a"}


@dataclass(frozen=True)
class ReadinessThresholds:
    min_sharpe: float
    min_win_rate: float
    max_drawdown_pct: float
    min_trade_count: int
    recent_loss_block: bool = False


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("evidence JSON must be an object")
    return payload


def _load_threshold_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on local env packaging
        raise ValueError("PyYAML is required for --thresholds-yaml") from exc

    with path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("threshold YAML must be an object")
    return payload


def _is_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in _PLACEHOLDER_STRINGS or "todo" in normalized
    return False


def _placeholder_paths(value: Any, prefix: str = "") -> list[str]:
    if _is_placeholder(value):
        return [prefix or "$"]
    if isinstance(value, dict):
        paths: list[str] = []
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(_placeholder_paths(child, child_prefix))
        return paths
    if isinstance(value, list):
        paths = []
        for idx, child in enumerate(value):
            paths.extend(_placeholder_paths(child, f"{prefix}[{idx}]"))
        return paths
    return []


def _number(value: Any, field: str, reasons: list[str]) -> float | None:
    if isinstance(value, bool):
        reasons.append(f"{field} must be numeric")
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        reasons.append(f"{field} must be numeric")
        return None


def _int_number(value: Any, field: str, reasons: list[str]) -> int | None:
    parsed = _number(value, field, reasons)
    if parsed is None:
        return None
    return int(parsed)


def _strategy_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("strategies", payload)
    if not isinstance(raw, dict):
        raise ValueError("evidence must contain a strategies object")
    return raw


def _evaluate_strategy(
    name: str, evidence: Any, thresholds: ReadinessThresholds
) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        return {
            "status": BLOCKED,
            "reasons": ["missing strategy evidence"],
            "metrics": {},
        }

    blocked_reasons: list[str] = []
    observe_reasons: list[str] = []
    placeholders = _placeholder_paths(evidence)
    blocked_reasons.extend(
        f"placeholder evidence detected at {path}" for path in placeholders
    )

    sharpe = _number(evidence.get("sharpe"), "sharpe", blocked_reasons)
    win_rate = _number(evidence.get("win_rate"), "win_rate", blocked_reasons)
    max_drawdown_pct = _number(
        evidence.get("max_drawdown_pct"), "max_drawdown_pct", blocked_reasons
    )
    trade_count = _int_number(
        evidence.get("trade_count"), "trade_count", blocked_reasons
    )
    evidence_recent_loss_block = bool(evidence.get("recent_loss_block", False))

    if thresholds.recent_loss_block or evidence_recent_loss_block:
        blocked_reasons.append("recent_loss_block is true")

    metrics = {
        "sharpe": sharpe,
        "win_rate": win_rate,
        "max_drawdown_pct": max_drawdown_pct,
        "trade_count": trade_count,
        "recent_loss_block": evidence_recent_loss_block,
    }

    if blocked_reasons:
        return {"status": BLOCKED, "reasons": blocked_reasons, "metrics": metrics}

    if sharpe is not None and sharpe < thresholds.min_sharpe:
        observe_reasons.append(
            f"sharpe {sharpe:g} below min_sharpe {thresholds.min_sharpe:g}"
        )
    if win_rate is not None and win_rate < thresholds.min_win_rate:
        observe_reasons.append(
            f"win_rate {win_rate:g} below min_win_rate {thresholds.min_win_rate:g}"
        )
    if max_drawdown_pct is not None and max_drawdown_pct > thresholds.max_drawdown_pct:
        observe_reasons.append(
            "max_drawdown_pct "
            f"{max_drawdown_pct:g} above max_drawdown_pct "
            f"{thresholds.max_drawdown_pct:g}"
        )
    if trade_count is not None and trade_count < thresholds.min_trade_count:
        observe_reasons.append(
            f"trade_count {trade_count} below min_trade_count "
            f"{thresholds.min_trade_count}"
        )

    if observe_reasons:
        return {"status": OBSERVE, "reasons": observe_reasons, "metrics": metrics}
    return {
        "status": READY,
        "reasons": ["all readiness gates passed"],
        "metrics": metrics,
    }


def build_readiness_report(
    evidence_path: Path, thresholds: ReadinessThresholds
) -> dict[str, Any]:
    payload = _load_json(evidence_path)
    evidence = _strategy_evidence(payload)
    strategies = {
        name: _evaluate_strategy(name, evidence.get(name), thresholds)
        for name in REVIEW_STRATEGIES
    }
    if any(result["status"] == BLOCKED for result in strategies.values()):
        overall_status = BLOCKED
    elif any(result["status"] == OBSERVE for result in strategies.values()):
        overall_status = OBSERVE
    else:
        overall_status = READY
    return {
        "overall_status": overall_status,
        "strategies_under_review": list(REVIEW_STRATEGIES),
        "thresholds": asdict(thresholds),
        "source_evidence": str(evidence_path),
        "strategies": strategies,
    }


def _thresholds_from_args(args: argparse.Namespace) -> ReadinessThresholds:
    yaml_values: dict[str, Any] = {}
    if args.thresholds_yaml is not None:
        yaml_values = _load_threshold_yaml(args.thresholds_yaml)

    def value(name: str) -> Any:
        cli_value = getattr(args, name)
        if cli_value is not None:
            return cli_value
        if name in yaml_values:
            return yaml_values[name]
        raise ValueError(f"missing threshold {name}")

    return ReadinessThresholds(
        min_sharpe=float(value("min_sharpe")),
        min_win_rate=float(value("min_win_rate")),
        max_drawdown_pct=float(value("max_drawdown_pct")),
        min_trade_count=int(value("min_trade_count")),
        recent_loss_block=bool(
            args.recent_loss_block or yaml_values.get("recent_loss_block", False)
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Produce stock strategy reactivation/readiness JSON"
    )
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--thresholds-yaml", type=Path)
    parser.add_argument("--min-sharpe", type=float)
    parser.add_argument("--min-win-rate", type=float)
    parser.add_argument("--max-drawdown-pct", type=float)
    parser.add_argument("--min-trade-count", type=int)
    parser.add_argument(
        "--recent-loss-block",
        action="store_true",
        help="force blocked status when recent losses should prevent reactivation",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit nonzero when any strategy is blocked",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    thresholds = _thresholds_from_args(args)
    report = build_readiness_report(args.evidence, thresholds)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and report["overall_status"] == BLOCKED:
        return 1
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
