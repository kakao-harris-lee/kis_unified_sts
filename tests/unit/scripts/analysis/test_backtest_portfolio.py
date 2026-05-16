from __future__ import annotations

from datetime import date

import pandas as pd

import scripts.analysis.backtest_portfolio as portfolio
from shared.backtest.engine import SignalType


def _daily_df(code: str, rows: int = 3) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "datetime": pd.date_range("2026-05-11", periods=rows, freq="D"),
            "open": [100.0 + i for i in range(rows)],
            "high": [101.0 + i for i in range(rows)],
            "low": [99.0 + i for i in range(rows)],
            "close": [100.5 + i for i in range(rows)],
            "volume": [1000 + i for i in range(rows)],
            "code": [code] * rows,
        }
    )


def test_load_symbol_data_uses_daily_loader_for_daily_strategy(monkeypatch):
    calls = []

    def fake_daily_loader(code, start, end):
        calls.append((code, start, end))
        return _daily_df(code).drop(columns=["code"])

    monkeypatch.setattr(
        portfolio, "load_stock_daily_from_clickhouse", fake_daily_loader
    )

    df = portfolio._load_symbol_data(
        code="005930",
        name="삼성전자",
        timeframe="daily",
        start=date(2026, 5, 1),
        end=date(2026, 5, 15),
    )

    assert calls == [("005930", date(2026, 5, 1), date(2026, 5, 15))]
    assert df is not None
    assert df["code"].tolist() == ["005930", "005930", "005930"]
    assert df["name"].tolist() == ["삼성전자", "삼성전자", "삼성전자"]


def test_build_backtest_config_honors_cli_capital_over_yaml_default():
    cfg = portfolio._build_backtest_config(
        {
            "strategy": {
                "backtest": {"initial_capital": 100_000_000},
                "position": {"params": {"order_amount_per_stock": 2_000_000}},
            }
        },
        initial_capital=10_000_000,
    )

    assert cfg.initial_capital == 10_000_000
    assert cfg.order_amount_per_stock == 2_000_000


def test_build_backtest_config_accepts_position_overrides():
    cfg = portfolio._build_backtest_config(
        {
            "strategy": {
                "position": {
                    "params": {
                        "order_amount_per_stock": 2_000_000,
                        "max_positions": 5,
                    }
                }
            }
        },
        initial_capital=10_000_000,
        order_amount_per_stock=1_000_000,
        max_positions=4,
    )

    assert cfg.order_amount_per_stock == 1_000_000
    assert cfg.max_positions == 4


def test_apply_strategy_overrides_updates_copy_only():
    original = {
        "strategy": {
            "entry": {"params": {"rsi_oversold": 45.0}},
            "exit": {"params": {"hard_stop_pct": -0.07}},
        }
    }

    cfg = portfolio._apply_strategy_overrides(
        original,
        [
            "entry.params.rsi_oversold=40",
            "strategy.exit.params.hard_stop_pct=-0.05",
            "paper.enabled=false",
        ],
    )

    assert cfg["strategy"]["entry"]["params"]["rsi_oversold"] == 40
    assert cfg["strategy"]["exit"]["params"]["hard_stop_pct"] == -0.05
    assert cfg["strategy"]["paper"]["enabled"] is False
    assert original["strategy"]["entry"]["params"]["rsi_oversold"] == 45.0


def test_apply_strategy_overrides_rejects_unknown_root():
    try:
        portfolio._apply_strategy_overrides({}, ["unknown.params.foo=1"])
    except ValueError as exc:
        assert "Override path must start" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_daily_portfolio_adapter_keeps_indicator_windows_per_symbol(monkeypatch):
    created = []

    class FakeDailyAdapter:
        def __init__(self, _strategy, _config):
            self.prescan_codes = set()
            self.positions = []
            created.append(self)

        def prescan_data(self, df):
            self.prescan_codes = set(df["code"].tolist())

        def set_position(self, position):
            self.positions.append(position)

        def check_exit(self, _bar):
            return False, None

        def on_bar(self, bar):
            return SignalType.BUY if bar["code"] == "AAA" else SignalType.HOLD

    monkeypatch.setattr(portfolio.StrategyFactory, "create", lambda _cfg: object())
    monkeypatch.setattr(portfolio, "DailyBacktestAdapter", FakeDailyAdapter)

    adapter = portfolio.DailyPortfolioAdapter({"strategy": {"name": "daily_test"}})
    data = pd.concat([_daily_df("AAA", 2), _daily_df("BBB", 2)], ignore_index=True)
    data = data.sort_values(["datetime", "code"]).reset_index(drop=True)

    adapter.prescan_data(data)

    assert [a.prescan_codes for a in created] == [{"AAA"}, {"BBB"}]

    position = {"code": "AAA", "side": "BUY"}
    adapter.set_position(position)
    assert adapter.on_bar({"code": "AAA"}) == SignalType.BUY
    assert created[0].positions[-1] == position
