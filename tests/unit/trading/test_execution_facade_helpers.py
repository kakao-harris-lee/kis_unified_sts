"""Owner tests for pure trading execution facade helpers."""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from shared.models.signal import Signal


def test_normalize_entry_order_result_accepts_current_tuple_shape() -> None:
    from services.trading.execution_facade import normalize_entry_order_result

    assert normalize_entry_order_result((True, "330.5", "2", "KRX")) == (
        True,
        330.5,
        2,
        "KRX",
    )


def test_normalize_entry_order_result_accepts_legacy_tuple_shape() -> None:
    from services.trading.execution_facade import normalize_entry_order_result

    assert normalize_entry_order_result((False, 0, 0)) == (False, 0.0, 0, "KRX")


def test_normalize_entry_order_result_rejects_unknown_shapes() -> None:
    from services.trading.execution_facade import normalize_entry_order_result

    with pytest.raises(ValueError, match="Unexpected entry order result type"):
        normalize_entry_order_result(["not", "a", "tuple"])

    with pytest.raises(ValueError, match="Unexpected entry order result length"):
        normalize_entry_order_result((True, 1.0))


def test_get_signal_direction_prefers_signal_direction_metadata() -> None:
    from services.trading.execution_facade import get_signal_direction

    signal = Signal(
        code="A05TEST",
        strategy="setup_a_gap_reversion",
        metadata={"signal_direction": " SHORT ", "direction": "long"},
    )

    assert get_signal_direction(signal) == "short"


def test_get_signal_direction_defaults_to_long_for_unknown_or_invalid_metadata() -> (
    None
):
    from services.trading.execution_facade import get_signal_direction

    assert get_signal_direction(
        Signal(code="005930", metadata={"direction": "sell"})
    ) == ("long")

    signal = Signal(code="005930")
    signal.metadata = "short"

    assert get_signal_direction(signal) == "long"


def test_execution_facade_import_does_not_import_orchestrator() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""
                import sys
                import services.trading.execution_facade

                assert "services.trading.orchestrator" not in sys.modules
                """),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
