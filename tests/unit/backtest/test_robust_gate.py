from shared.backtest.robust_gate import (
    SENTINEL,
    objective_value,
    rescoped_gate,
)


class _T:
    def __init__(self, value, pf):
        self.value = value
        self.user_attrs = {"profit_factor": pf}


class _Study:
    def __init__(self, trials): self.trials = trials


def test_pass_when_distribution_robust_and_oos_ok():
    trials = [_T(1.0, 1.5)] * 8 + [_T(-0.2, 0.9)] * 2  # 80% clear floor
    oos = {"sharpe_ratio": 1.2, "profit_factor": 1.4,
           "max_drawdown_pct": 10.0, "total_return_pct": 30.0}
    r = rescoped_gate(_Study(trials), oos)
    assert r["a"] and r["b"] and r["c"] and r["pass"]


def test_fail_single_lucky_outlier():
    trials = [_T(5.0, 4.0)] + [_T(-2.0, 0.7)] * 39  # 1/40 basin
    oos = {"sharpe_ratio": 8.0, "profit_factor": 3.0,
           "max_drawdown_pct": 7.0, "total_return_pct": 100.0}
    r = rescoped_gate(_Study(trials), oos)
    assert r["a"] is False and r["b"] is False and r["pass"] is False


def test_objective_value_min_trades_floor():
    assert objective_value(
        {"total_trades": 10, "sharpe_ratio": 3.0}, 50) <= SENTINEL + 0.1
    assert objective_value(
        {"total_trades": 80, "sharpe_ratio": 1.4}, 50) == 1.4
