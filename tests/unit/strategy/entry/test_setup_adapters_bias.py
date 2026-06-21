"""Unit tests — daily bias filter in SetupAEntryAdapter.

Task 4: gate Setup A/C entries on daily directional bias from DailyBiasProvider.
Tests use SetupAEntryAdapter with llm_tuning.enabled=False to bypass the LLM
gating block so only the bias filter is under test.

Pattern mirrors test_setup_adapters_regime_gate.py:
  - monkeypatch module-level helpers (_build_market_context, _publish_setup_eval)
  - patch adapter._setup.check to return a mock decision signal
  - patch adapter._daily_bias_provider.get_or_compute_bias to control bias output
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import pytest

from shared.strategy.entry import setup_adapters
from shared.strategy.entry.setup_adapters import (
    SetupAEntryAdapter,
    SetupAEntryConfig,
    SetupCEntryAdapter,
    SetupCEntryConfig,
)
from shared.strategy.base import EntryContext


def _ctx() -> EntryContext:
    """Minimal EntryContext that lets _build_market_context return a mock."""
    return EntryContext(
        market_data={"code": "A05603", "close": 348.8, "atr": 1.0},
        timestamp=dt.datetime(2026, 6, 21, 9, 30, tzinfo=dt.timezone.utc),
    )


def _adapter(enabled: bool = True) -> SetupAEntryAdapter:
    """Build a SetupAEntryAdapter with LLM tuning disabled (bypass LLM gating)."""
    cfg = SetupAEntryConfig()
    cfg.llm_tuning.enabled = False
    cfg.daily_bias_filter_enabled = enabled
    return SetupAEntryAdapter(cfg)


def _adapter_c(enabled: bool = True) -> SetupCEntryAdapter:
    """Build a SetupCEntryAdapter with LLM tuning disabled (bypass LLM gating)."""
    cfg = SetupCEntryConfig()
    cfg.llm_tuning.enabled = False
    cfg.daily_bias_filter_enabled = enabled
    return SetupCEntryAdapter(cfg)


def _fake_decision(direction: str = "long") -> MagicMock:
    """Mock decision signal with the required attributes."""
    sig = MagicMock()
    sig.direction = direction
    sig.confidence = 0.8
    sig.stop_loss = 347.5
    sig.take_profit = 350.0
    sig.entry_price = 348.8
    sig.setup_type = "gap_reversion"
    sig.reason_tags = ["gap_down", "retrace"]
    sig.symbol = "A05603"
    sig.valid_until = None
    return sig


# ---------------------------------------------------------------------------
# Case 1: bias="flat" → generate() returns None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flat_bias_blocks_entry(monkeypatch):
    """When daily bias is 'flat', generate() must return None regardless of direction."""
    adapter = _adapter()
    adapter._setup.check = MagicMock(return_value=_fake_decision("long"))
    monkeypatch.setattr(setup_adapters, "_build_market_context", lambda _c: MagicMock())
    monkeypatch.setattr(setup_adapters, "_publish_setup_eval", MagicMock())
    monkeypatch.setattr(
        adapter._daily_bias_provider, "get_or_compute_bias", MagicMock(return_value="flat")
    )

    result = await adapter.generate(_ctx())
    assert result is None


# ---------------------------------------------------------------------------
# Case 2: bias="long", signal direction="short" → returns None (misaligned)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_misaligned_bias_blocks_entry(monkeypatch):
    """When bias='long' but signal direction='short', generate() returns None."""
    adapter = _adapter()
    adapter._setup.check = MagicMock(return_value=_fake_decision("short"))
    monkeypatch.setattr(setup_adapters, "_build_market_context", lambda _c: MagicMock())
    monkeypatch.setattr(setup_adapters, "_publish_setup_eval", MagicMock())
    monkeypatch.setattr(
        adapter._daily_bias_provider, "get_or_compute_bias", MagicMock(return_value="long")
    )

    result = await adapter.generate(_ctx())
    assert result is None


# ---------------------------------------------------------------------------
# Case 3: daily_bias_filter_enabled=False → get_or_compute_bias NOT called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_disabled_bypasses_bias_provider(monkeypatch):
    """When daily_bias_filter_enabled=False, DailyBiasProvider is never called."""
    adapter = _adapter(enabled=False)
    fake_decision = _fake_decision("long")
    adapter._setup.check = MagicMock(return_value=fake_decision)
    monkeypatch.setattr(setup_adapters, "_build_market_context", lambda _c: MagicMock())
    monkeypatch.setattr(setup_adapters, "_publish_setup_eval", MagicMock())
    fake_signal = MagicMock()
    monkeypatch.setattr(
        setup_adapters,
        "_decision_signal_to_orchestrator_signal",
        MagicMock(return_value=fake_signal),
    )
    spy = MagicMock(return_value="flat")
    monkeypatch.setattr(adapter._daily_bias_provider, "get_or_compute_bias", spy)

    result = await adapter.generate(_ctx())

    spy.assert_not_called()
    assert result is fake_signal


# ---------------------------------------------------------------------------
# Case 4: bias="flat" → _publish_setup_eval called with "daily_bias_flat"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flat_bias_publishes_correct_reason(monkeypatch):
    """bias='flat' must publish reject reason 'daily_bias_flat'."""
    adapter = _adapter()
    adapter._setup.check = MagicMock(return_value=_fake_decision("long"))
    monkeypatch.setattr(setup_adapters, "_build_market_context", lambda _c: MagicMock())
    publish_spy = MagicMock()
    monkeypatch.setattr(setup_adapters, "_publish_setup_eval", publish_spy)
    monkeypatch.setattr(
        adapter._daily_bias_provider, "get_or_compute_bias", MagicMock(return_value="flat")
    )

    await adapter.generate(_ctx())

    publish_spy.assert_called_with(adapter.name, "reject", "daily_bias_flat")


# ---------------------------------------------------------------------------
# Case 5: bias="long", direction="short" → publishes "daily_bias_misaligned"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_misaligned_bias_publishes_correct_reason(monkeypatch):
    """bias='long' + direction='short' must publish 'daily_bias_misaligned'."""
    adapter = _adapter()
    adapter._setup.check = MagicMock(return_value=_fake_decision("short"))
    monkeypatch.setattr(setup_adapters, "_build_market_context", lambda _c: MagicMock())
    publish_spy = MagicMock()
    monkeypatch.setattr(setup_adapters, "_publish_setup_eval", publish_spy)
    monkeypatch.setattr(
        adapter._daily_bias_provider, "get_or_compute_bias", MagicMock(return_value="long")
    )

    await adapter.generate(_ctx())

    publish_spy.assert_called_with(adapter.name, "reject", "daily_bias_misaligned")


# ---------------------------------------------------------------------------
# SetupC adapter — bias filter coverage (mirrors SetupA patterns)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setup_c_flat_bias_blocks_entry(monkeypatch):
    """SetupC: when daily bias is 'flat', generate() must return None."""
    adapter = _adapter_c()
    adapter._setup.check = MagicMock(return_value=_fake_decision("long"))
    monkeypatch.setattr(setup_adapters, "_build_market_context", lambda _c: MagicMock())
    monkeypatch.setattr(setup_adapters, "_publish_setup_eval", MagicMock())
    monkeypatch.setattr(
        adapter._daily_bias_provider, "get_or_compute_bias", MagicMock(return_value="flat")
    )

    result = await adapter.generate(_ctx())
    assert result is None


@pytest.mark.asyncio
async def test_setup_c_misaligned_bias_blocks_entry(monkeypatch):
    """SetupC: when bias='long' but signal direction='short', generate() returns None."""
    adapter = _adapter_c()
    adapter._setup.check = MagicMock(return_value=_fake_decision("short"))
    monkeypatch.setattr(setup_adapters, "_build_market_context", lambda _c: MagicMock())
    monkeypatch.setattr(setup_adapters, "_publish_setup_eval", MagicMock())
    monkeypatch.setattr(
        adapter._daily_bias_provider, "get_or_compute_bias", MagicMock(return_value="long")
    )

    result = await adapter.generate(_ctx())
    assert result is None
