"""Tests for SetupDEntryAdapter and its registry/factory wiring.

Coverage
--------
- The adapter fires through the orchestrator EntryContext path and emits a
  tz-aware UTC Signal carrying signal_direction + stop_loss/take_profit metadata.
- Long/short symmetry through the adapter.
- Rejection paths return None (chop, quiet/low-vol bar, missing price).
- The registry registers ``setup_d_vwap_reversion`` and the StrategyFactory
  builds the full TradingStrategy from the YAML config.

Hermetic: no Redis / network / YAML loads beyond the in-repo strategy config
(StrategyFactory.create_from_file reads config/strategies/futures/*.yaml from the
repo, which is allowed in unit tests as it carries no secrets).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from shared.strategy.base import EntryContext
from shared.strategy.entry.setup_adapters import (
    SetupDEntryAdapter,
    SetupDEntryConfig,
)


def _utc(h: int, m: int) -> datetime:
    """A tz-aware UTC timestamp whose KST equivalent is in-session.

    The adapter converts to KST internally; 02:00 UTC == 11:00 KST (120 min
    after the 09:00 KST open → inside the [15, 345] window).
    """
    return datetime(2026, 3, 10, h, m, tzinfo=UTC)


def _md(
    *,
    current_price: float,
    vwap: float,
    atr: float = 2.0,
    atr_90th: float = 2.0,
    last_15min_high: float | None = None,
    last_15min_low: float | None = None,
    symbol: str = "101S6000",
) -> dict:
    if last_15min_high is None:
        last_15min_high = current_price + 0.1
    if last_15min_low is None:
        last_15min_low = current_price - 0.1
    return {
        "code": symbol,
        "close": current_price,
        "prev_close": vwap,
        "open": vwap,
        "vwap": vwap,
        "atr": atr,
        "atr_90th_percentile": atr_90th,
        "last_15min_high": last_15min_high,
        "last_15min_low": last_15min_low,
        "spread_ticks": 1.0,
    }


def _adapter() -> SetupDEntryAdapter:
    return SetupDEntryAdapter(SetupDEntryConfig())


def _context(md: dict, ts: datetime) -> EntryContext:
    return EntryContext(market_data=md, indicators=md, timestamp=ts, metadata={})


class TestSetupDAdapterFires:
    @pytest.mark.asyncio
    async def test_up_spike_emits_short_signal(self):
        adapter = _adapter()
        md = _md(current_price=104.0, vwap=100.0, last_15min_high=103.9)
        sig = await adapter.generate(_context(md, _utc(2, 0)))
        assert sig is not None
        assert sig.strategy == "setup_d_vwap_reversion"
        assert sig.metadata["signal_direction"] == "short"
        assert sig.metadata["stop_loss"] == pytest.approx(104.0 + 1.5 * 2.0)
        assert sig.metadata["take_profit"] == pytest.approx(100.0)
        # tz-aware UTC contract
        assert sig.timestamp.tzinfo is not None
        assert sig.timestamp.utcoffset().total_seconds() == 0

    @pytest.mark.asyncio
    async def test_down_spike_emits_long_signal_mirror(self):
        adapter = _adapter()
        md = _md(current_price=96.0, vwap=100.0, last_15min_low=96.1)
        sig = await adapter.generate(_context(md, _utc(2, 0)))
        assert sig is not None
        assert sig.metadata["signal_direction"] == "long"
        assert sig.metadata["stop_loss"] == pytest.approx(96.0 - 1.5 * 2.0)
        assert sig.metadata["take_profit"] == pytest.approx(100.0)


class TestSetupDAdapterRejects:
    @pytest.mark.asyncio
    async def test_chop_near_vwap_returns_none(self):
        adapter = _adapter()
        md = _md(current_price=101.0, vwap=100.0)  # z=0.5 < trigger
        assert await adapter.generate(_context(md, _utc(2, 0))) is None

    @pytest.mark.asyncio
    async def test_low_vol_bar_returns_none(self):
        # Small warmup so the causal gate activates within the test.
        adapter = SetupDEntryAdapter(SetupDEntryConfig(vol_warmup_bars=30))
        # Seed the causal window with high-ATR calm bars (reference ≈ 2.0).
        for _i in range(30):
            calm = _md(current_price=100.05, vwap=100.0, atr=2.0)
            await adapter.generate(_context(calm, _utc(2, 0)))
        # Now an extreme on a low-ATR bar: vol_ratio = 1.0/2.0 = 0.5 < 0.9 → gate.
        md = _md(current_price=101.8, vwap=100.0, atr=1.0)
        assert await adapter.generate(_context(md, _utc(2, 0))) is None

    @pytest.mark.asyncio
    async def test_missing_price_returns_none(self):
        adapter = _adapter()
        md = _md(current_price=103.6, vwap=100.0)
        md["close"] = 0.0  # unusable price → no MarketContext
        assert await adapter.generate(_context(md, _utc(2, 0))) is None

    @pytest.mark.asyncio
    async def test_live_default_atr90_does_not_silently_block(self):
        """Regression for the review blocker: the live path supplies no
        atr_90th_percentile (build_market_context defaults it to atr*1.5). The
        gate must NOT read that default and must instead self-compute, so the
        setup still fires on a genuine high-vol extreme.
        """
        adapter = SetupDEntryAdapter(SetupDEntryConfig(vol_warmup_bars=30))
        # market_data WITHOUT atr_90th_percentile → adapter defaults it to atr*1.5.
        for _i in range(30):
            calm = {
                "code": "101S6000",
                "close": 100.05,
                "open": 100.0,
                "prev_close": 100.0,
                "vwap": 100.0,
                "atr": 1.0,
                "last_15min_high": 100.15,
                "last_15min_low": 99.95,
            }
            await adapter.generate(_context(calm, _utc(2, 0)))
        spike = {
            "code": "101S6000",
            "close": 104.0,
            "open": 100.0,
            "prev_close": 100.0,
            "vwap": 100.0,
            "atr": 2.0,
            "last_15min_high": 103.9,
            "last_15min_low": 99.95,
        }
        sig = await adapter.generate(_context(spike, _utc(2, 0)))
        assert sig is not None
        assert sig.metadata["signal_direction"] == "short"


class TestSetupDValidation:
    def test_invalid_config_raises(self):
        with pytest.raises(AssertionError):
            SetupDEntryAdapter(SetupDEntryConfig(stop_atr_mult=0.0))
        with pytest.raises(AssertionError):
            SetupDEntryAdapter(SetupDEntryConfig(extreme_atr_mult=0.0))


class TestSetupDRegistryWiring:
    def test_registered_in_entry_registry(self):
        from shared.strategy.registry import EntryRegistry, register_builtin_components

        register_builtin_components()
        assert "setup_d_vwap_reversion" in EntryRegistry.list_all()

    def test_factory_builds_strategy_from_yaml(self):
        from shared.strategy.registry import (
            StrategyFactory,
            register_builtin_components,
        )

        register_builtin_components()
        strat = StrategyFactory.create_from_file("futures", "setup_d_vwap_reversion")
        assert strat.name == "setup_d_vwap_reversion"
        assert strat.entry.name == "setup_d_vwap_reversion"
        # required indicators expose the MR inputs (the vol reference is
        # self-computed, so it is NOT a required external indicator)
        assert "vwap" in strat.entry.required_indicators
        assert "atr" in strat.entry.required_indicators
        assert "atr_90th_percentile" not in strat.entry.required_indicators
