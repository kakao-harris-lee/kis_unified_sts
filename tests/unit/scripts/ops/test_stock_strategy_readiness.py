from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.ops.stock_strategy_readiness as mod


def _write_evidence(path: Path, metrics: dict) -> None:
    path.write_text(json.dumps({"strategies": metrics}), encoding="utf-8")


def _thresholds() -> mod.ReadinessThresholds:
    return mod.ReadinessThresholds(
        min_sharpe=0.8,
        min_win_rate=52.0,
        max_drawdown_pct=12.0,
        min_trade_count=30,
        recent_loss_block=False,
    )


def test_marks_strategy_ready_for_small_paper_when_all_gates_pass(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "evidence.json"
    _write_evidence(
        evidence,
        {
            "technical_consensus": {
                "sharpe": 1.1,
                "win_rate": 57.5,
                "max_drawdown_pct": 8.2,
                "trade_count": 42,
                "recent_loss_block": False,
            },
            "momentum_breakout": {
                "sharpe": 0.4,
                "win_rate": 48.0,
                "max_drawdown_pct": 10.1,
                "trade_count": 35,
                "recent_loss_block": False,
            },
        },
    )

    report = mod.build_readiness_report(evidence, _thresholds())

    technical = report["strategies"]["technical_consensus"]
    momentum = report["strategies"]["momentum_breakout"]
    assert technical["status"] == "ready_for_small_paper"
    assert technical["reasons"] == ["all readiness gates passed"]
    assert momentum["status"] == "observe_only"
    assert "sharpe 0.4 below min_sharpe 0.8" in momentum["reasons"]


def test_blocks_recent_loss_and_placeholder_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    _write_evidence(
        evidence,
        {
            "technical_consensus": {
                "sharpe": 1.3,
                "win_rate": 60.0,
                "max_drawdown_pct": 7.0,
                "trade_count": 50,
                "recent_loss_block": True,
            },
            "momentum_breakout": {
                "sharpe": "TODO",
                "win_rate": 61.0,
                "max_drawdown_pct": 6.0,
                "trade_count": 50,
                "recent_loss_block": False,
            },
        },
    )

    report = mod.build_readiness_report(evidence, _thresholds())

    technical = report["strategies"]["technical_consensus"]
    momentum = report["strategies"]["momentum_breakout"]
    assert technical["status"] == "blocked"
    assert technical["reasons"] == ["recent_loss_block is true"]
    assert momentum["status"] == "blocked"
    assert "placeholder evidence detected at sharpe" in momentum["reasons"]


def test_missing_required_strategy_is_blocked(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    _write_evidence(evidence, {"technical_consensus": {}})

    report = mod.build_readiness_report(evidence, _thresholds())

    assert report["strategies"]["momentum_breakout"]["status"] == "blocked"
    assert report["strategies"]["momentum_breakout"]["reasons"] == [
        "missing strategy evidence"
    ]


def test_cli_outputs_json_with_cli_thresholds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    evidence = tmp_path / "evidence.json"
    _write_evidence(
        evidence,
        {
            "technical_consensus": {
                "sharpe": 0.9,
                "win_rate": 54.0,
                "max_drawdown_pct": 9.0,
                "trade_count": 31,
                "recent_loss_block": False,
            },
            "momentum_breakout": {
                "sharpe": 0.9,
                "win_rate": 54.0,
                "max_drawdown_pct": 9.0,
                "trade_count": 31,
                "recent_loss_block": False,
            },
        },
    )

    rc = mod.main(
        [
            "--evidence",
            str(evidence),
            "--min-sharpe",
            "0.8",
            "--min-win-rate",
            "52",
            "--max-drawdown-pct",
            "12",
            "--min-trade-count",
            "30",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert output["thresholds"]["min_sharpe"] == 0.8
    assert (
        output["strategies"]["technical_consensus"]["status"] == "ready_for_small_paper"
    )


def test_cli_strict_exits_nonzero_when_any_strategy_is_blocked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    evidence = tmp_path / "evidence.json"
    _write_evidence(
        evidence,
        {
            "technical_consensus": {
                "sharpe": "TODO",
                "win_rate": 54.0,
                "max_drawdown_pct": 9.0,
                "trade_count": 31,
                "recent_loss_block": False,
            },
            "momentum_breakout": {
                "sharpe": 0.9,
                "win_rate": 54.0,
                "max_drawdown_pct": 9.0,
                "trade_count": 31,
                "recent_loss_block": False,
            },
        },
    )

    rc = mod.main(
        [
            "--evidence",
            str(evidence),
            "--min-sharpe",
            "0.8",
            "--min-win-rate",
            "52",
            "--max-drawdown-pct",
            "12",
            "--min-trade-count",
            "30",
            "--strict",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert output["overall_status"] == "blocked"
    assert output["strategies"]["technical_consensus"]["status"] == "blocked"
