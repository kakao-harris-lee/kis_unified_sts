"""Unit tests for shared/backtest/optimizer.py's None-guarded param sampling.

These target the mypy-driven guards added to ``StrategyOptimizer._sample_params``
(int/float branches raise ``ValueError`` instead of letting ``int(None)`` /
``suggest_float(None)`` blow up with a less specific error) and to
``StrategyOptimizer._objective`` (raises ``RuntimeError`` instead of an
assert-based None-check that would be stripped under ``python -O``).

``optuna`` is not installed in every dev environment, and ``StrategyOptimizer.__init__``
raises ``ImportError`` when it is missing — so these tests call the unbound methods
directly against a minimal stand-in object instead of constructing a real instance.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from shared.backtest.optimizer import ParamSpec, StrategyOptimizer


def test_sample_params_int_branch_none_low_raises_value_error():
    spec = ParamSpec(name="bb_period", param_type="int", low=None, high=30)
    fake_self = SimpleNamespace(param_specs=[spec])

    with pytest.raises(ValueError, match="requires low and high"):
        StrategyOptimizer._sample_params(fake_self, trial=None)


def test_sample_params_int_branch_none_high_raises_value_error():
    spec = ParamSpec(name="bb_period", param_type="int", low=10, high=None)
    fake_self = SimpleNamespace(param_specs=[spec])

    with pytest.raises(ValueError, match="requires low and high"):
        StrategyOptimizer._sample_params(fake_self, trial=None)


def test_sample_params_float_branch_none_low_raises_value_error():
    spec = ParamSpec(name="bb_std", param_type="float", low=None, high=3.0)
    fake_self = SimpleNamespace(param_specs=[spec])

    with pytest.raises(ValueError, match="requires low and high"):
        StrategyOptimizer._sample_params(fake_self, trial=None)


def test_sample_params_float_branch_none_high_raises_value_error():
    spec = ParamSpec(name="bb_std", param_type="float", low=1.5, high=None)
    fake_self = SimpleNamespace(param_specs=[spec])

    with pytest.raises(ValueError, match="requires low and high"):
        StrategyOptimizer._sample_params(fake_self, trial=None)


def test_objective_raises_runtime_error_when_study_missing_on_trial_failure():
    """A trial failure with ``self.study`` unset must raise, not silently
    fall through to ``None.direction`` (which the old ``assert`` guarded
    against, but would be stripped under ``python -O``)."""

    def _raising_strategy_factory(params):
        raise ValueError("boom")

    fake_self = SimpleNamespace(
        strategy_factory=_raising_strategy_factory,
        backtest_config=None,
        data=None,
        mlflow_experiment=None,
        best_result=None,
        study=None,
        _sample_params=lambda trial: {},
    )

    with pytest.raises(
        RuntimeError, match="_objective called before study was created"
    ):
        StrategyOptimizer._objective(fake_self, trial=None, metric="sharpe_ratio")
