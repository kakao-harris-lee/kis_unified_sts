"""Unit tests for the shared backtest backend seam (config/backtest.yaml).

Covers plan 2026-09-07 §1-B/C
(``docs/plans/2026-09-07-vectorbt-default-flip.md``): the process-wide default
engine now comes from config (env-overridable) instead of a code literal, and
``experiment_runner``/``optimizer`` share one resolution + dispatch
implementation (``shared/backtest/backend.py``).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from unittest.mock import Mock

import pandas as pd
import pytest

from shared.backtest.backend import (
    BackendRun,
    load_default_engine,
    reset_dedupe_state_for_tests,
    resolve_backend,
    run_with_backend,
)
from shared.backtest.config import BacktestConfig
from shared.backtest.result import BacktestResult
from shared.config.loader import ConfigLoader


@pytest.fixture(autouse=True)
def _clear_config_cache():
    """backtest.yaml is env-driven — never let a cached read leak across tests."""
    ConfigLoader.clear_cache()
    yield
    ConfigLoader.clear_cache()


@pytest.fixture(autouse=True)
def _reset_backend_dedupe_state():
    """The fallback-log dedup sets in backend.py are module-level (correct
    for a long-running process) — reset between tests so one test's
    "already seen" refusal doesn't silently suppress the next test's."""
    reset_dedupe_state_for_tests()
    yield
    reset_dedupe_state_for_tests()


def _stub_result() -> BacktestResult:
    now = datetime(2026, 6, 1, tzinfo=UTC)
    return BacktestResult(
        start_date=now,
        end_date=now,
        total_bars=1,
        initial_capital=1_000_000.0,
        final_capital=1_000_000.0,
        total_return_pct=0.0,
        total_pnl=0.0,
    )


def _tiny_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "datetime": [datetime(2026, 6, 1, tzinfo=UTC)],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1000],
        }
    )


class TestLoadDefaultEngine:
    def test_default_from_yaml_is_vectorbt(self, monkeypatch):
        """config/backtest.yaml ships default_engine: ${BACKTEST_DEFAULT_ENGINE:vectorbt}."""
        monkeypatch.delenv("BACKTEST_DEFAULT_ENGINE", raising=False)
        assert load_default_engine() == "vectorbt"

    def test_env_override_to_legacy(self, monkeypatch):
        """Rollback path: BACKTEST_DEFAULT_ENGINE=legacy."""
        monkeypatch.setenv("BACKTEST_DEFAULT_ENGINE", "legacy")
        assert load_default_engine() == "legacy"

    def test_missing_file_falls_back_to_legacy_with_warning(self, monkeypatch, caplog):
        """Config absence must never silently flip the default to vectorbt."""
        from shared.config.loader import ConfigNotFoundError

        def _raise(*args, **kwargs):
            raise ConfigNotFoundError("backtest.yaml not found")

        monkeypatch.setattr(ConfigLoader, "load", _raise)
        with caplog.at_level(logging.WARNING, logger="shared.backtest"):
            assert load_default_engine() == "legacy"
        assert any("backtest.yaml" in r.message for r in caplog.records)

    def test_unknown_value_falls_back_to_legacy_with_warning(self, monkeypatch, caplog):
        monkeypatch.setattr(
            ConfigLoader,
            "load",
            lambda *a, **k: {"backtest": {"default_engine": "vbt"}},
        )
        with caplog.at_level(logging.WARNING, logger="shared.backtest"):
            assert load_default_engine() == "legacy"
        assert any("unknown value" in r.message for r in caplog.records)


class TestResolveBackend:
    def test_no_engine_key_uses_supplied_default(self):
        assert resolve_backend({}, "vectorbt") == "vectorbt"
        assert resolve_backend({}, "legacy") == "legacy"

    def test_explicit_engine_key_overrides_default(self):
        assert resolve_backend({"engine": "legacy"}, "vectorbt") == "legacy"
        assert resolve_backend({"engine": "vectorbt"}, "legacy") == "vectorbt"

    def test_unknown_engine_value_warns_and_uses_legacy(self, caplog):
        with caplog.at_level(logging.WARNING, logger="shared.backtest"):
            result = resolve_backend({"engine": "vbt"}, "vectorbt")
        assert result == "legacy"
        assert any("unknown backtest engine" in r.message for r in caplog.records)

    def test_legacy_exit_true_forces_legacy_over_vectorbt(self, caplog):
        with caplog.at_level(logging.INFO, logger="shared.backtest"):
            result = resolve_backend(
                {"engine": "vectorbt", "legacy_exit": True}, "vectorbt"
            )
        assert result == "legacy"
        assert any("legacy_exit=true" in r.message for r in caplog.records)

    def test_legacy_exit_unrecognized_value_warns_and_is_ignored(self, caplog):
        with caplog.at_level(logging.WARNING, logger="shared.backtest"):
            result = resolve_backend(
                {"engine": "vectorbt", "legacy_exit": "maybe"}, "vectorbt"
            )
        assert result == "vectorbt"
        assert any(
            "unrecognized backtest.legacy_exit" in r.message for r in caplog.records
        )

    def test_legacy_exit_bare_none_is_unset_without_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="shared.backtest"):
            result = resolve_backend(
                {"engine": "vectorbt", "legacy_exit": None}, "vectorbt"
            )
        assert result == "vectorbt"
        assert not any("legacy_exit" in r.message for r in caplog.records)


class TestRunWithBackend:
    def test_legacy_backend_runs_backtest_engine_directly(self, monkeypatch):
        stub = _stub_result()
        monkeypatch.setattr(
            "shared.backtest.engine.BacktestEngine.run", lambda self, data: stub
        )
        strategy = Mock(name="strategy")
        run = run_with_backend(
            lambda: strategy, BacktestConfig(), _tiny_data(), "legacy"
        )
        assert isinstance(run, BackendRun)
        assert run.engine == "backtest_engine"
        assert run.result is stub

    def test_vectorbt_success_labels_run_as_vectorbt(self, monkeypatch):
        stub = _stub_result()
        monkeypatch.setattr(
            "shared.backtest.vbt_runner.VectorbtRunner.run",
            lambda self, data: stub,
        )
        strategy = Mock(name="strategy")
        run = run_with_backend(
            lambda: strategy, BacktestConfig(), _tiny_data(), "vectorbt"
        )
        assert run.engine == "vectorbt"
        assert run.result is stub

    def test_not_implemented_error_falls_back_and_labels_legacy(
        self, monkeypatch, caplog
    ):
        """The plan's fallback contract: a vectorbt refusal must still label
        the run honestly as the engine that actually produced the result.

        Review fix (2026-09-07): a static refusal logs at INFO, not WARNING
        — WARNING is reserved for genuine anomalies (ImportError /
        VectorbtParityError) that a per-symbol NotImplementedError would
        otherwise bury.
        """
        legacy_stub = _stub_result()

        def _refuse(self, data):
            raise NotImplementedError("exit generator not expressible")

        monkeypatch.setattr("shared.backtest.vbt_runner.VectorbtRunner.run", _refuse)
        monkeypatch.setattr(
            "shared.backtest.engine.BacktestEngine.run",
            lambda self, data: legacy_stub,
        )
        strategy = Mock(name="strategy")
        with caplog.at_level(logging.INFO, logger="shared.backtest"):
            run = run_with_backend(
                lambda: strategy,
                BacktestConfig(),
                _tiny_data(),
                "vectorbt",
                experiment_id="unit-test",
                dedupe_key="unit-test-strategy",
            )
        assert run.engine == "backtest_engine"
        assert run.result is legacy_stub
        assert not any(r.levelno >= logging.WARNING for r in caplog.records)
        assert any(
            r.levelno == logging.INFO
            and "vectorbt runner refused (static, expected)" in r.message
            for r in caplog.records
        )

    def test_not_implemented_error_dedupes_across_symbols(self, monkeypatch, caplog):
        """Same (experiment, strategy) dedupe_key across repeated calls (one
        per symbol, in the real caller) must log the INFO refusal once, not
        once per symbol."""
        legacy_stub = _stub_result()

        def _refuse(self, data):
            raise NotImplementedError("daily adapter path")

        monkeypatch.setattr("shared.backtest.vbt_runner.VectorbtRunner.run", _refuse)
        monkeypatch.setattr(
            "shared.backtest.engine.BacktestEngine.run",
            lambda self, data: legacy_stub,
        )
        strategy = Mock(name="strategy")
        with caplog.at_level(logging.DEBUG, logger="shared.backtest"):
            for symbol in ("005930", "000660", "035420"):
                run = run_with_backend(
                    lambda: strategy,
                    BacktestConfig(),
                    _tiny_data(),
                    "vectorbt",
                    experiment_id=f"experiment pattern_pullback/{symbol}",
                    dedupe_key="spec-1:pattern_pullback",
                )
                assert run.engine == "backtest_engine"

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1
        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert len(debug_records) == 2  # the 2nd and 3rd symbol
        assert not any(r.levelno >= logging.WARNING for r in caplog.records)

    def test_not_implemented_error_does_not_dedupe_across_different_strategies(
        self, monkeypatch, caplog
    ):
        """A different dedupe_key (different strategy) must log its own INFO
        even if another strategy already refused."""
        legacy_stub = _stub_result()

        def _refuse(self, data):
            raise NotImplementedError("no")

        monkeypatch.setattr("shared.backtest.vbt_runner.VectorbtRunner.run", _refuse)
        monkeypatch.setattr(
            "shared.backtest.engine.BacktestEngine.run",
            lambda self, data: legacy_stub,
        )
        strategy = Mock(name="strategy")
        with caplog.at_level(logging.INFO, logger="shared.backtest"):
            run_with_backend(
                lambda: strategy,
                BacktestConfig(),
                _tiny_data(),
                "vectorbt",
                dedupe_key="spec-1:strategy_a",
            )
            run_with_backend(
                lambda: strategy,
                BacktestConfig(),
                _tiny_data(),
                "vectorbt",
                dedupe_key="spec-1:strategy_b",
            )
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 2

    def test_import_error_falls_back_and_labels_legacy(self, monkeypatch, caplog):
        legacy_stub = _stub_result()

        def _refuse(self, data):
            raise ImportError("vectorbt not installed")

        monkeypatch.setattr("shared.backtest.vbt_runner.VectorbtRunner.run", _refuse)
        monkeypatch.setattr(
            "shared.backtest.engine.BacktestEngine.run",
            lambda self, data: legacy_stub,
        )
        strategy = Mock(name="strategy")
        with caplog.at_level(logging.WARNING, logger="shared.backtest"):
            run = run_with_backend(
                lambda: strategy, BacktestConfig(), _tiny_data(), "vectorbt"
            )
        assert run.engine == "backtest_engine"
        assert run.result is legacy_stub
        assert any(
            "vectorbt not installed/importable" in r.message for r in caplog.records
        )

    def test_import_error_warns_once_per_process(self, monkeypatch, caplog):
        """ImportError is a process-wide condition (vectorbt not installed at
        all), not a per-strategy one — warn once, not once per call."""
        legacy_stub = _stub_result()

        def _refuse(self, data):
            raise ImportError("vectorbt not installed")

        monkeypatch.setattr("shared.backtest.vbt_runner.VectorbtRunner.run", _refuse)
        monkeypatch.setattr(
            "shared.backtest.engine.BacktestEngine.run",
            lambda self, data: legacy_stub,
        )
        strategy = Mock(name="strategy")
        with caplog.at_level(logging.DEBUG, logger="shared.backtest"):
            for i in range(3):
                run = run_with_backend(
                    lambda: strategy,
                    BacktestConfig(),
                    _tiny_data(),
                    "vectorbt",
                    dedupe_key=f"different-strategy-{i}",  # must not matter
                )
                assert run.engine == "backtest_engine"
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) == 1
        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert len(debug_records) == 2

    def test_parity_error_falls_back_and_labels_legacy(self, monkeypatch, caplog):
        from shared.backtest.vbt_runner import VectorbtParityError

        legacy_stub = _stub_result()

        def _parity_fail(self, data):
            raise VectorbtParityError("cross-check mismatch")

        monkeypatch.setattr(
            "shared.backtest.vbt_runner.VectorbtRunner.run", _parity_fail
        )
        monkeypatch.setattr(
            "shared.backtest.engine.BacktestEngine.run",
            lambda self, data: legacy_stub,
        )
        strategy = Mock(name="strategy")
        with caplog.at_level(logging.WARNING, logger="shared.backtest"):
            run = run_with_backend(
                lambda: strategy, BacktestConfig(), _tiny_data(), "vectorbt"
            )
        assert run.engine == "backtest_engine"
        assert run.result is legacy_stub
        assert any("parity cross-check FAILED" in r.message for r in caplog.records)

    def test_parity_error_warns_every_occurrence_not_just_once(
        self, monkeypatch, caplog
    ):
        """VectorbtParityError is a real runner-defect signal — unlike
        NotImplementedError/ImportError it must NEVER be deduped, even with
        the same dedupe_key repeated."""
        from shared.backtest.vbt_runner import VectorbtParityError

        legacy_stub = _stub_result()

        def _parity_fail(self, data):
            raise VectorbtParityError("cross-check mismatch")

        monkeypatch.setattr(
            "shared.backtest.vbt_runner.VectorbtRunner.run", _parity_fail
        )
        monkeypatch.setattr(
            "shared.backtest.engine.BacktestEngine.run",
            lambda self, data: legacy_stub,
        )
        strategy = Mock(name="strategy")
        with caplog.at_level(logging.WARNING, logger="shared.backtest"):
            for _ in range(3):
                run_with_backend(
                    lambda: strategy,
                    BacktestConfig(),
                    _tiny_data(),
                    "vectorbt",
                    dedupe_key="same-strategy-every-time",
                )
        warning_records = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and "parity cross-check FAILED" in r.message
        ]
        assert len(warning_records) == 3

    def test_make_strategy_called_fresh_per_attempt(self, monkeypatch):
        """A mid-run vectorbt refusal must not reuse the (possibly dirty)
        adapter for the legacy fallback — make_strategy is a zero-arg
        factory called again."""
        legacy_stub = _stub_result()
        calls: list[int] = []

        def _make():
            calls.append(1)
            return Mock(name=f"strategy-{len(calls)}")

        def _refuse(self, data):
            raise NotImplementedError("no")

        monkeypatch.setattr("shared.backtest.vbt_runner.VectorbtRunner.run", _refuse)
        monkeypatch.setattr(
            "shared.backtest.engine.BacktestEngine.run",
            lambda self, data: legacy_stub,
        )
        run_with_backend(_make, BacktestConfig(), _tiny_data(), "vectorbt")
        assert len(calls) == 2  # once for the vectorbt attempt, once for legacy
