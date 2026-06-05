"""Tests for scripts/walk_forward_paper_foldin.py — paper-gate evaluation.

Verifies the paper-only rules (3 + 4) against synthetic PaperTrade lists
without touching external storage. The bootstrap rule (1 + 2) is already covered
by tests/unit/backtest/test_bootstrap.py.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Direct import — script lives in scripts/, not a package. Register in
# sys.modules before exec_module so @dataclass can find the module via
# cls.__module__ lookup.
import importlib.util

spec = importlib.util.spec_from_file_location(
    "walk_forward_paper_foldin",
    _REPO_ROOT / "scripts" / "walk_forward_paper_foldin.py",
)
_module = importlib.util.module_from_spec(spec)
sys.modules["walk_forward_paper_foldin"] = _module
spec.loader.exec_module(_module)

PaperTrade = _module.PaperTrade
evaluate_paper_only_gate = _module.evaluate_paper_only_gate


def _trade(
    direction: str = "long",
    entry: float = 100.0,
    exit_: float = 100.0,
    setup: str = "A_gap_reversion",
    tick: float = 0.02,
    quantity: int = 1,
) -> PaperTrade:
    return PaperTrade(
        setup_type=setup,
        direction=direction,
        generated_at=datetime(2026, 5, 1, 9, 30),
        entry_price=entry,
        exit_price=exit_,
        quantity=quantity,
        tick_size_points=tick,
    )


class TestPnLTicks:
    def test_long_winner(self):
        # entry 100, exit 100.10 → 5 ticks profit (long)
        t = _trade(direction="long", entry=100.0, exit_=100.10, tick=0.02)
        assert t.pnl_ticks == pytest.approx(5.0)

    def test_long_loser(self):
        t = _trade(direction="long", entry=100.0, exit_=99.90, tick=0.02)
        assert t.pnl_ticks == pytest.approx(-5.0)

    def test_short_winner(self):
        # entry 100, exit 99.90 → +5 ticks profit (short)
        t = _trade(direction="short", entry=100.0, exit_=99.90, tick=0.02)
        assert t.pnl_ticks == pytest.approx(5.0)

    def test_short_loser(self):
        t = _trade(direction="short", entry=100.0, exit_=100.10, tick=0.02)
        assert t.pnl_ticks == pytest.approx(-5.0)

    def test_zero_tick_returns_zero(self):
        t = _trade(direction="long", entry=100.0, exit_=110.0, tick=0.0)
        assert t.pnl_ticks == 0.0


class TestPaperGate:
    def test_empty_trade_list_fails_both_rules(self):
        result = evaluate_paper_only_gate([])
        assert result["n_trades"] == 0
        assert result["rule3_paper_median_positive"]["passed"] is False
        assert result["rule4_paper_sharpe"]["passed"] is False

    def test_all_winners_pass(self):
        trades = [
            _trade(direction="long", entry=100.0, exit_=100.10) for _ in range(20)
        ]
        result = evaluate_paper_only_gate(trades)
        assert result["n_trades"] == 20
        assert result["pnl_median_ticks"] == pytest.approx(5.0)
        assert result["rule3_paper_median_positive"]["passed"] is True
        # All-winners has zero std → sharpe undefined → set to 0 → rule 4 FAIL
        # (this is correct: no variance means "no statistical evidence" not "perfect")
        assert result["rule4_paper_sharpe"]["passed"] is False

    def test_mixed_with_positive_edge_passes_both(self):
        # 70% winners (5 ticks), 30% losers (-3 ticks) → mean=2.6, std≈3.7, sharpe≈0.7
        trades = [
            _trade(direction="long", entry=100.0, exit_=100.10) for _ in range(70)
        ] + [_trade(direction="long", entry=100.0, exit_=99.94) for _ in range(30)]
        result = evaluate_paper_only_gate(trades, sharpe_min=0.5)
        assert result["pnl_median_ticks"] == pytest.approx(5.0)
        assert result["rule3_paper_median_positive"]["passed"] is True
        assert result["sharpe_per_trade"] > 0.5
        assert result["rule4_paper_sharpe"]["passed"] is True

    def test_negative_edge_fails_rule3(self):
        trades = [
            _trade(direction="long", entry=100.0, exit_=99.90) for _ in range(60)
        ] + [_trade(direction="long", entry=100.0, exit_=100.06) for _ in range(40)]
        result = evaluate_paper_only_gate(trades)
        assert result["pnl_median_ticks"] == pytest.approx(-5.0)
        assert result["rule3_paper_median_positive"]["passed"] is False

    def test_low_sharpe_fails_rule4(self):
        # Symmetric +/- with small mean → sharpe near 0
        trades = [
            _trade(direction="long", entry=100.0, exit_=100.20) for _ in range(50)
        ] + [_trade(direction="long", entry=100.0, exit_=99.80) for _ in range(50)]
        result = evaluate_paper_only_gate(trades, sharpe_min=0.5)
        assert abs(result["pnl_mean_ticks"]) < 0.5
        assert result["rule4_paper_sharpe"]["passed"] is False

    def test_short_only_winners_pass(self):
        trades = [
            _trade(direction="short", entry=100.0, exit_=99.96) for _ in range(20)
        ]
        result = evaluate_paper_only_gate(trades)
        assert result["pnl_median_ticks"] == pytest.approx(2.0)
        assert result["rule3_paper_median_positive"]["passed"] is True

    def test_sharpe_threshold_is_configurable(self):
        # 60 winners (3 ticks), 40 losers (-2 ticks) → mean=1.0, std≈2.5, sharpe≈0.4
        trades = [
            _trade(direction="long", entry=100.0, exit_=100.06) for _ in range(60)
        ] + [_trade(direction="long", entry=100.0, exit_=99.96) for _ in range(40)]
        # Default 0.5 — should fail
        assert (
            evaluate_paper_only_gate(trades, sharpe_min=0.5)["rule4_paper_sharpe"][
                "passed"
            ]
            is False
        )
        # Lower 0.3 — should pass
        assert (
            evaluate_paper_only_gate(trades, sharpe_min=0.3)["rule4_paper_sharpe"][
                "passed"
            ]
            is True
        )
