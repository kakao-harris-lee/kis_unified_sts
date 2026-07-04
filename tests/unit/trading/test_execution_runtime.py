"""Owner tests for trading execution runtime helpers."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from shared.models.signal import Signal


def test_finalize_entry_execution_metadata_preserves_order_identity_fields() -> None:
    from services.trading.execution_runtime import finalize_entry_execution_metadata

    original = {
        "mode": "slippage_guard",
        "submit_price": "100.04",
        "filled_qty": 1,
        "client_order_id": "coid-123",
        "idempotency_key": "idem-123",
        "venue": "NXT",
        "transitions": [{"state": "filled"}],
    }
    signal = Signal(code="101W09", price=100.00)

    finalized = finalize_entry_execution_metadata(
        signal=signal,
        fill_price=99.96,
        is_short=True,
        execution_meta=original,
        tick_size=0.02,
    )

    assert finalized["signal_price"] == 100.00
    assert finalized["submit_price"] == 100.04
    assert finalized["fill_price"] == 99.96
    assert finalized["slippage_ticks"] == pytest.approx(2.0)
    assert finalized["slippage_tick_size"] == 0.02
    assert finalized["client_order_id"] == "coid-123"
    assert finalized["idempotency_key"] == "idem-123"
    assert finalized["venue"] == "NXT"
    assert finalized["transitions"] == [{"state": "filled"}]
    assert "signal_price" not in original


def test_record_mock_mirror_result_normalizes_metadata_and_stats() -> None:
    from services.trading.execution_runtime import record_mock_mirror_result

    position = SimpleNamespace(metadata={"existing": True})
    stats = {"entry_failed": 2}

    record_mock_mirror_result(position, stats, "entry", None)

    entry_result = position.metadata["mock_mirror"]["entry"]
    assert entry_result == {
        "success": False,
        "message": "mock_mirror_no_result",
        "skipped": False,
    }
    assert position.metadata["existing"] is True
    assert stats["entry_failed"] == 3


def test_mock_mirror_exit_should_skip_only_after_failed_entry_mirror() -> None:
    from services.trading.execution_runtime import mock_mirror_exit_should_skip

    assert (
        mock_mirror_exit_should_skip(
            SimpleNamespace(metadata={"mock_mirror": {"entry": {"success": False}}})
        )
        is True
    )
    assert (
        mock_mirror_exit_should_skip(
            SimpleNamespace(metadata={"mock_mirror": {"entry": {"success": True}}})
        )
        is False
    )
    assert mock_mirror_exit_should_skip(SimpleNamespace(metadata={})) is False


def test_update_entry_slippage_stats_accumulates_average() -> None:
    from services.trading.execution_runtime import update_entry_slippage_stats

    stats = {"count": 1.0, "adverse_ticks_sum": 2.0, "avg_adverse_ticks": 2.0}

    update_entry_slippage_stats(stats, 4.0)

    assert stats == {
        "count": 2.0,
        "adverse_ticks_sum": 6.0,
        "avg_adverse_ticks": 3.0,
    }


def test_serialize_state_transitions_preserves_state_value_and_timestamp() -> None:
    from services.trading.execution_runtime import serialize_state_transitions

    transitions = [
        SimpleNamespace(
            state=SimpleNamespace(value="submitted"),
            at=datetime(2026, 7, 4, 9, 15, tzinfo=UTC),
            reason="passive_limit",
        ),
        SimpleNamespace(state="cancelled", at=None, reason="retry_unfilled"),
    ]

    assert serialize_state_transitions(transitions) == [
        {
            "state": "submitted",
            "at": "2026-07-04T09:15:00+00:00",
            "reason": "passive_limit",
        },
        {"state": "cancelled", "at": "None", "reason": "retry_unfilled"},
    ]


def test_execution_runtime_import_does_not_import_orchestrator() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""
                import sys
                import services.trading.execution_runtime

                assert "services.trading.orchestrator" not in sys.modules
                """),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
