"""Unit tests for orchestrator setup-signal row mapping.

The interim futures paper path (TradingOrchestrator) records executed Setup
A/C entries to ``kospi.signals_all`` so the Phase 2 verification gates
(``setup_a_signals_today`` + the 30-day cumulative gate) measure the running
system. ClickHouse persistence has been removed; the legacy persistence hook is
kept as a no-op so trading is not disrupted.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from services.trading.orchestrator import (
    _SETUP_TYPE_BY_STRATEGY,
    TradingOrchestrator,
)


class _Sig:
    """Minimal stand-in for the orchestrator Signal."""

    def __init__(
        self,
        strategy: str,
        price: float = 100.0,
        confidence: float = 0.7,
        timestamp: datetime | None = None,
        metadata: dict | None = None,
        code: str = "A05000",
    ):
        self.strategy = strategy
        self.price = price
        self.confidence = confidence
        self.timestamp = timestamp
        self.metadata = metadata or {}
        self.code = code


class TestSetupTypeMapping:
    def test_known_setups(self):
        assert _SETUP_TYPE_BY_STRATEGY["setup_a_gap_reversion"] == "A"
        assert _SETUP_TYPE_BY_STRATEGY["setup_c_event_reaction"] == "C"


class TestBuildSignalsAllRow:
    def test_setup_a_row_shape(self):
        sig = _Sig(
            "setup_a_gap_reversion",
            price=405.5,
            confidence=0.62,
            timestamp=datetime(2026, 6, 2, 9, 5, tzinfo=UTC),
            metadata={"stop_loss": 400.0, "take_profit": 415.0},
        )
        row = TradingOrchestrator._build_signals_all_row(sig, "long", 405.5, True)
        assert row is not None
        (
            signal_id,
            generated_at,
            setup_type,
            direction,
            entry_price,
            stop_loss,
            take_profit,
            confidence,
            executed,
            skip_reason,
            reason_tags,
        ) = row
        assert isinstance(signal_id, str) and signal_id
        assert generated_at == datetime(2026, 6, 2, 9, 5)  # naive UTC
        assert generated_at.tzinfo is None
        assert setup_type == "A"
        assert direction == "long"
        assert entry_price == 405.5
        assert stop_loss == 400.0
        assert take_profit == 415.0
        assert abs(confidence - 0.62) < 1e-6
        assert executed == 1
        assert skip_reason == ""
        assert reason_tags == []

    def test_setup_c_executed_false(self):
        row = TradingOrchestrator._build_signals_all_row(
            _Sig("setup_c_event_reaction"), "short", 100.0, False
        )
        assert row is not None
        assert row[2] == "C"
        assert row[3] == "short"
        assert row[8] == 0  # executed

    def test_non_setup_ac_returns_none(self):
        assert (
            TradingOrchestrator._build_signals_all_row(
                _Sig("bb_reversion_15m"), "long", 1.0, True
            )
            is None
        )

    def test_missing_metadata_defaults_zero(self):
        row = TradingOrchestrator._build_signals_all_row(
            _Sig("setup_a_gap_reversion", metadata={}), "long", 200.0, True
        )
        assert row[5] == 0.0  # stop_loss
        assert row[6] == 0.0  # take_profit


class TestPersistNoop:
    def _orch(self, asset_class: str):
        # Bypass the heavy __init__; the method only touches self.config.
        orch = TradingOrchestrator.__new__(TradingOrchestrator)
        orch.config = SimpleNamespace(asset_class=asset_class)
        return orch

    def test_futures_is_noop(self):
        orch = self._orch("futures")
        asyncio.run(
            orch._persist_setup_signal_row(
                _Sig("setup_a_gap_reversion"),
                direction="long",
                entry_price=100.0,
                executed=True,
            )
        )

    def test_non_futures_is_noop(self):
        orch = self._orch("stock")
        asyncio.run(
            orch._persist_setup_signal_row(
                _Sig("setup_a_gap_reversion"),
                direction="long",
                entry_price=100.0,
                executed=True,
            )
        )

    def test_non_setup_strategy_is_noop(self):
        orch = self._orch("futures")
        asyncio.run(
            orch._persist_setup_signal_row(
                _Sig("bb_reversion_15m"),
                direction="long",
                entry_price=100.0,
                executed=True,
            )
        )
