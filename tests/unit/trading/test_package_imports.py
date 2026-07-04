"""Package import compatibility and laziness tests."""

from __future__ import annotations

import subprocess
import sys
import textwrap


def _run_python(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_runtime_config_submodule_import_does_not_import_orchestrator() -> None:
    result = _run_python("""
        import sys

        import services.trading.runtime_config as runtime_config

        assert runtime_config.TradingConfig.__module__ == (
            "services.trading.runtime_config"
        )
        assert "services.trading.orchestrator" not in sys.modules
        """)

    assert result.returncode == 0, result.stderr


def test_top_level_trading_config_import_does_not_import_orchestrator() -> None:
    result = _run_python("""
        import sys

        from services.trading import TradingConfig

        assert TradingConfig.__module__ == "services.trading.runtime_config"
        assert "services.trading.orchestrator" not in sys.modules
        """)

    assert result.returncode == 0, result.stderr


def test_session_calendar_submodule_import_does_not_import_orchestrator() -> None:
    result = _run_python("""
        import sys

        from services.trading import session_calendar

        assert session_calendar.TradingState.__module__ == (
            "services.trading.session_calendar"
        )
        assert "services.trading.orchestrator" not in sys.modules
        """)

    assert result.returncode == 0, result.stderr


def test_direct_package_submodule_attributes_resolve_lazily() -> None:
    result = _run_python("""
        import sys
        import services.trading as trading

        assert trading.runtime_config.TradingConfig.__module__ == (
            "services.trading.runtime_config"
        )
        assert "services.trading.orchestrator" not in sys.modules

        assert trading.session_calendar.TradingState.__module__ == (
            "services.trading.session_calendar"
        )
        assert "services.trading.orchestrator" not in sys.modules

        assert trading.orchestrator.TradingOrchestrator is trading.TradingOrchestrator
        assert "services.trading.orchestrator" in sys.modules
        """)

    assert result.returncode == 0, result.stderr


def test_execution_facade_package_attribute_resolves_without_orchestrator() -> None:
    result = _run_python("""
        import sys
        import services.trading as trading

        assert trading.execution_facade.get_signal_direction is not None
        assert "services.trading.orchestrator" not in sys.modules
        """)

    assert result.returncode == 0, result.stderr


def test_execution_runtime_package_attribute_resolves_without_orchestrator() -> None:
    result = _run_python("""
        import sys
        import services.trading as trading

        assert trading.execution_runtime.finalize_entry_execution_metadata is not None
        assert "services.trading.orchestrator" not in sys.modules
        """)

    assert result.returncode == 0, result.stderr


def test_entry_runtime_package_attribute_resolves_without_orchestrator() -> None:
    result = _run_python("""
        import sys
        import services.trading as trading

        assert trading.entry_runtime.entry_signal_priority is not None
        assert "services.trading.orchestrator" not in sys.modules
        """)

    assert result.returncode == 0, result.stderr


def test_signals_all_runtime_package_attribute_resolves_without_orchestrator() -> None:
    result = _run_python("""
        import sys
        import services.trading as trading

        assert trading.signals_all_runtime.build_signals_all_row is not None
        assert "services.trading.orchestrator" not in sys.modules
        """)

    assert result.returncode == 0, result.stderr


def test_recovery_package_attribute_resolves_without_orchestrator() -> None:
    result = _run_python("""
        import sys
        import services.trading as trading

        assert trading.recovery.parse_recovery_entry_time is not None
        assert "services.trading.orchestrator" not in sys.modules
        """)

    assert result.returncode == 0, result.stderr


def test_market_data_bootstrap_package_attribute_resolves_without_orchestrator() -> (
    None
):
    result = _run_python("""
        import sys
        import services.trading as trading

        assert trading.market_data_bootstrap.init_price_feeds is not None
        assert "services.trading.orchestrator" not in sys.modules
        """)

    assert result.returncode == 0, result.stderr


def test_startup_sequence_package_attribute_resolves_without_orchestrator() -> None:
    result = _run_python("""
        import sys
        import services.trading as trading

        assert trading.startup_sequence.run_trading_startup_sequence is not None
        assert "services.trading.orchestrator" not in sys.modules
        """)

    assert result.returncode == 0, result.stderr


def test_initialization_runtime_package_attribute_resolves_without_orchestrator() -> (
    None
):
    result = _run_python("""
        import sys
        import services.trading as trading

        assert trading.initialization_runtime.execution_layer_mode is not None
        assert "services.trading.orchestrator" not in sys.modules
        """)

    assert result.returncode == 0, result.stderr


def test_kill_switch_runtime_package_attribute_resolves_without_orchestrator() -> None:
    result = _run_python("""
        import sys
        import services.trading as trading

        assert trading.kill_switch_runtime.parse_force_flatten_request is not None
        assert "services.trading.orchestrator" not in sys.modules
        """)

    assert result.returncode == 0, result.stderr


def test_top_level_orchestrator_import_still_uses_facade_exports() -> None:
    result = _run_python("""
        from services.trading import TradingConfig, TradingOrchestrator, TradingState
        import services.trading.orchestrator as orchestrator

        assert TradingConfig is orchestrator.TradingConfig
        assert TradingOrchestrator is orchestrator.TradingOrchestrator
        assert TradingState is orchestrator.TradingState
        """)

    assert result.returncode == 0, result.stderr
