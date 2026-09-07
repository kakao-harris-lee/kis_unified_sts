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
from typing import Any

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


def test_objective_routes_a_trial_through_run_with_backend(monkeypatch):
    """optimizer 도 experiment_runner 와 동일한 backend seam(backend.py) 을
    통과해야 한다 (plan 2026-09-07 §1-C, docs/plans/
    2026-09-07-vectorbt-default-flip.md) — 이전엔 optimizer._objective 가 seam
    을 우회해 BacktestEngine 을 직접 생성했다.
    """
    from shared.backtest import backend as backend_mod

    fake_result = object()
    calls: list[tuple[Any, Any, str, str]] = []
    made_with: list[dict[str, Any]] = []

    def _fake_run_with_backend(
        make_strategy, config, data, backend, *, experiment_id="", dedupe_key=None
    ):
        calls.append((config, data, backend, experiment_id, dedupe_key))
        make_strategy()  # exercise the zero-arg factory like the real dispatcher
        return backend_mod.BackendRun(result=fake_result, engine="backtest_engine")

    monkeypatch.setattr(backend_mod, "run_with_backend", _fake_run_with_backend)
    monkeypatch.setattr(backend_mod, "resolve_backend", lambda *a, **k: "legacy")
    monkeypatch.setattr(backend_mod, "load_default_engine", lambda: "legacy")

    class _FakeTrial:
        number = 7

    fake_self = SimpleNamespace(
        strategy_factory=lambda params: made_with.append(params) or object(),
        backtest_config=object(),
        data=SimpleNamespace(copy=lambda: "DATA"),
        mlflow_experiment=None,
        best_result=None,
        study=None,
        backend_bt_cfg={},
        _sample_params=lambda trial: {"bb_period": 20},
        _get_metric_value=lambda result, metric: 1.23,
    )

    value = StrategyOptimizer._objective(
        fake_self, trial=_FakeTrial(), metric="sharpe_ratio"
    )

    assert value == 1.23
    assert made_with == [{"bb_period": 20}]
    assert len(calls) == 1
    _config, _data, used_backend, experiment_id, dedupe_key = calls[0]
    assert used_backend == "legacy"
    assert experiment_id == "optimizer trial 7"
    # per-optimizer-instance, not per-trial (review fix 2026-09-07): a static
    # NotImplementedError refusal must not spam INFO once per trial.
    assert dedupe_key == f"optimizer:{id(fake_self)}"
    assert fake_self.best_result is fake_result
