from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd

import scripts.analysis.backtest_portfolio as portfolio
from shared.backtest import BacktestConfig
from shared.backtest.engine import SignalType
from shared.models.signal import Signal


def test_select_stocks_supports_symbol_and_max_filters(monkeypatch):
    monkeypatch.setattr(
        portfolio,
        "STOCK_UNIVERSE",
        [
            {"code": "AAA", "name": "A", "tier": "top"},
            {"code": "BBB", "name": "B", "tier": "top"},
            {"code": "CCC", "name": "C", "tier": "mid"},
        ],
    )

    assert [s["code"] for s in portfolio._select_stocks("top", max_symbols=1)] == [
        "AAA"
    ]
    selected = portfolio._select_stocks("all", symbols="CCC,ZZZ", max_symbols=2)
    assert selected == [
        {"code": "CCC", "name": "C", "tier": "mid"},
        {"code": "ZZZ", "name": "ZZZ", "tier": "custom"},
    ]


def test_scope_label_includes_codes_and_truncates_long_lists():
    stocks = [
        {"code": "AAA", "name": "A", "tier": "top"},
        {"code": "BBB", "name": "B", "tier": "top"},
        {"code": "CCC", "name": "C", "tier": "top"},
        {"code": "DDD", "name": "D", "tier": "top"},
        {"code": "EEE", "name": "E", "tier": "top"},
        {"code": "FFF", "name": "F", "tier": "top"},
    ]

    assert (
        portfolio._scope_label("all", stocks, max_symbols=6)
        == "all_first6_AAA_BBB_CCC_DDD_EEE_plus1"
    )


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


def test_default_warmup_days_uses_daily_indicator_periods():
    cfg = {
        "strategy": {
            "entry": {
                "params": {
                    "sma_long_period": 200,
                    "sma_mid_period": 60,
                    "mid_trend_lookback": 5,
                }
            },
            "exit": {"params": {"atr_period": 22}},
        }
    }

    assert portfolio._default_warmup_days(cfg, "daily") == 400
    assert portfolio._default_warmup_days(cfg, "minute") == 0


def test_default_warmup_days_uses_technical_consensus_periods():
    cfg = {
        "strategy": {
            "entry": {
                "type": "technical_consensus",
                "params": {
                    "rsi_period": 14,
                    "williams_r_period": 14,
                    "macd_fast": 12,
                    "macd_slow": 26,
                    "macd_signal": 9,
                    "volume_lookback": 20,
                },
            },
            "exit": {"type": "technical_consensus_exit", "params": {}},
        }
    }

    assert portfolio._daily_warmup_bars(cfg) == 35
    assert portfolio._default_warmup_days(cfg, "daily") == 70


def test_evaluation_metrics_use_requested_period_not_warmup():
    data = pd.DataFrame(
        {
            "datetime": pd.to_datetime(
                ["2026-04-30", "2026-05-01", "2026-05-02", "2026-05-03"]
            )
        }
    )

    assert (
        round(
            portfolio._annualized_return_pct(2.0, date(2026, 5, 1), date(2026, 5, 3)), 2
        )
        > 0
    )
    assert portfolio._monthly_expected_return_pct(2.0, data, date(2026, 5, 1)) == 14.0


def test_realized_trade_metrics_excludes_end_of_data_marks():
    metrics = portfolio._realized_trade_metrics(
        [
            SimpleNamespace(pnl=100.0, exit_reason="time_cut"),
            SimpleNamespace(pnl=-50.0, exit_reason="stop_loss"),
            SimpleNamespace(pnl=200.0, exit_reason="end_of_data"),
        ],
        initial_capital=10_000.0,
    )

    assert metrics["realized_trade_count"] == 2
    assert metrics["realized_winning_trades"] == 1
    assert metrics["realized_losing_trades"] == 1
    assert metrics["realized_win_rate_pct"] == 50.0
    assert metrics["realized_total_pnl"] == 50.0
    assert metrics["realized_return_pct"] == 0.5
    assert metrics["end_of_data_trade_count"] == 1
    assert metrics["end_of_data_unrealized_pnl"] == 200.0
    assert metrics["end_of_data_unrealized_return_pct"] == 2.0


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
        def __init__(self, _strategy, _config, *, entry_start=None):
            self.prescan_codes = set()
            self.positions = []
            self.entry_start = entry_start
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

    entry_start = pd.Timestamp("2026-05-12").to_pydatetime()
    adapter = portfolio.DailyPortfolioAdapter(
        {"strategy": {"name": "daily_test"}},
        entry_start=entry_start,
    )
    data = pd.concat([_daily_df("AAA", 2), _daily_df("BBB", 2)], ignore_index=True)
    data = data.sort_values(["datetime", "code"]).reset_index(drop=True)

    adapter.prescan_data(data)

    assert [a.prescan_codes for a in created] == [{"AAA"}, {"BBB"}]
    assert [a.entry_start for a in created] == [entry_start, entry_start]

    position = {"code": "AAA", "side": "BUY"}
    adapter.set_position(position)
    assert adapter.on_bar({"code": "AAA"}) == SignalType.BUY
    assert created[0].positions[-1] == position


def test_priority_daily_engine_admits_same_date_entries_by_signal_priority():
    class PriorityStrategy:
        name = "priority_daily"

        def __init__(self):
            self.last_entry_signal = None

        def prescan_data(self, _data):
            return None

        def set_position(self, _position):
            return None

        def check_exit(self, _bar):
            return False, None

        def on_bar(self, bar):
            priority = {"AAA": 10.0, "BBB": 1.0}.get(bar["code"])
            if priority is None:
                self.last_entry_signal = None
                return SignalType.HOLD
            self.last_entry_signal = Signal(
                code=bar["code"],
                name=bar["name"],
                strategy=self.name,
                confidence=0.7,
                metadata={"entry_priority": priority, "signal_direction": "long"},
            )
            return SignalType.BUY

    data = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-05-11", "2026-05-11"]),
            "open": [10.0, 10.0],
            "high": [10.0, 10.0],
            "low": [10.0, 10.0],
            "close": [10.0, 10.0],
            "volume": [1000, 1000],
            "code": ["AAA", "BBB"],
            "name": ["A", "B"],
        }
    )
    config = BacktestConfig.stock(
        initial_capital=1_000.0,
        order_amount_per_stock=500.0,
        max_positions=1,
    )

    result = portfolio.PriorityDailyPortfolioBacktestEngine(
        PriorityStrategy(),
        config,
    ).run(data)

    assert result.total_trades == 1
    assert result.trades[0].code == "BBB"
