import os
from pathlib import Path

import pytest
import yaml

from shared.backtest.adapter import BacktestStrategyAdapter
from shared.backtest.config import BacktestConfig
from shared.backtest.engine import BacktestEngine
from shared.config.loader import ConfigLoader
from shared.strategy.registry import (
    StrategyFactory,
    register_builtin_components,
)
from shared.validation.cli_validators import validate_csv_file

# tests/integration/<file> -> tests/ -> repo root
_ROOT = Path(__file__).resolve().parents[2]

_CSV = "/home/deploy/project/kis_unified_sts/data/kospi200f_1m_ch_101S6000.csv"
_CSV_KW = {
    "reject_duplicate_datetime": True,
    "require_monotonic_datetime": True,
    "max_zero_volume_ratio": 0.95,
    "max_zero_volume_price_move_ratio": 0.20,
}


@pytest.mark.integration
def test_bb_reversion_15m_entry_declares_mtf_base_15m():
    """Entry must declare mtf_base_15m; this is the root signal that
    drives T4 adapter wiring and the MTF accumulator in tests 2 and 3."""
    register_builtin_components()
    cfg = ConfigLoader.load_strategy("futures", "bb_reversion_15m")
    strat = StrategyFactory.create(cfg)
    assert "mtf_base_15m" in strat.entry.required_indicators


@pytest.mark.integration
def test_adapter_builds_15m_mtf_accumulator():
    """T4 carry-forward: the registered BacktestStrategyAdapter for
    bb_reversion_15m must actually create a 15-minute MTF feed (not just
    parse the contract). Without this the strategy would silently run on
    1-min bars (the known catastrophic FAIL).
    """
    register_builtin_components()
    cfg = ConfigLoader.load_strategy("futures", "bb_reversion_15m")
    strat = StrategyFactory.create(cfg)
    adapter = BacktestStrategyAdapter(strat, cfg)
    # StreamingIndicatorEngine stores numeric MTF timeframes in
    # _numeric_mtf_timeframes (list[int]).  This must include 15 for the
    # resolver to inject 15m BB/RSI under the plain bb_*/rsi keys.
    eng = adapter._indicator_engine
    numeric_tfs = eng._numeric_mtf_timeframes
    assert 15 in numeric_tfs, (
        f"adapter engine has no 15m mtf timeframe: _numeric_mtf_timeframes={numeric_tfs!r}"
    )


@pytest.mark.integration
@pytest.mark.slow
def test_registered_backtest_matches_probe_15m_profile():
    """End-to-end: registered path on the 1m CSV must behave as a 15m
    strategy (few-hundred trades, Sharpe>1, PF>1.2) — NOT the 1-min
    catastrophic profile (~1832 trades) nor near-zero. Asserts the
    REGIME, not exact numbers (engine magnitudes are inflated; only the
    regime transfers — see reports/optuna/BB_REVERSION_15M_PROBE.md).
    """
    register_builtin_components()
    if not os.path.exists(_CSV):
        pytest.skip(f"data CSV absent: {_CSV}")
    df1 = validate_csv_file(_CSV, **_CSV_KW)
    cfg = ConfigLoader.load_strategy("futures", "bb_reversion_15m")
    strat = StrategyFactory.create(cfg)
    adapter = BacktestStrategyAdapter(strat, cfg)
    bt = BacktestConfig.futures(initial_capital=10_000_000, point_value=50_000)
    m = BacktestEngine(adapter, bt).run(df1.copy()).to_metrics_dict()
    assert 150 <= m["total_trades"] <= 800, m["total_trades"]
    assert m["sharpe_ratio"] > 1.0, m["sharpe_ratio"]
    assert m["profit_factor"] > 1.2, m["profit_factor"]


@pytest.mark.integration
def test_bb_reversion_15m_enabled_for_paper_but_live_gated():
    """Strategy must be enabled (loaded for PAPER) while live execution
    remains independently gated via futures_live.yaml and Redis flag.
    Invariant: strategy.enabled=True AND futures_live.enabled=False.
    """
    with open(_ROOT / "config" / "strategies" / "futures" / "bb_reversion_15m.yaml") as f:
        d = yaml.safe_load(f)
    assert d["strategy"]["enabled"] is True            # loaded for PAPER
    assert d["strategy"]["entry"]["params"]["timeframe_minutes"] == 15
    with open(_ROOT / "config" / "futures_live.yaml") as f:
        live = yaml.safe_load(f)
    assert live["futures_live"]["enabled"] is False     # live still gated
