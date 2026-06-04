"""Tests for shared/backtest/signals_writer.py."""

from datetime import UTC, datetime

import pytest

from shared.backtest.signals_writer import SignalsAllWriter
from shared.decision.signal import Signal
from shared.risk.layer import LayerResult


def _signal() -> Signal:
    return Signal(
        setup_type="A_gap_reversion",
        direction="long",
        symbol="A05603",
        entry_price=331.20,
        stop_loss=330.50,
        take_profit=332.50,
        confidence=0.85,
        valid_until=datetime(2026, 4, 28, 6, 0, tzinfo=UTC),
        generated_at=datetime(2026, 4, 28, 5, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_signals_writer_noop_when_mirror_disabled():
    writer = SignalsAllWriter(ch_client=None, batch_size=1)

    await writer.enqueue(
        _signal(),
        LayerResult(passed=True, skip_reason=None, size_multiplier=1.0),
        executed=True,
        signal_id="sig-no-ch",
    )
    await writer.flush()
