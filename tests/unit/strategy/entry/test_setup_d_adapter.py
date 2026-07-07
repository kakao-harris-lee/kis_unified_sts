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


class TestSetupDAdapterTrendFilter:
    """The trend_filter_* config plumbs through the adapter into the setup."""

    @pytest.mark.asyncio
    async def test_trend_filter_blocks_shallow_counter_trend(self):
        # Filter ON; vol + stall gates disabled to isolate the trend gate.
        adapter = SetupDEntryAdapter(
            SetupDEntryConfig(
                trend_filter_enabled=True,
                min_atr_ratio=0.0,
                stall_buffer_atr_mult=100.0,
                trend_warmup_bars=10,
                trend_window_bars=30,
            )
        )
        # Warm 30 non-firing bars whose VWAP grinds down 130 → 101 (strong
        # downtrend), price == vwap (z == 0, never fires — only seeds the window).
        step = (101.0 - 130.0) / 29
        for i in range(30):
            v = 130.0 + step * i
            await adapter.generate(_context(_md(current_price=v, vwap=v), _utc(2, 0)))
        # A shallow counter-trend long (z=-2.0, below the 2.6 climax override)
        # into the downtrend is blocked → the field reached the setup.
        sig = await adapter.generate(
            _context(_md(current_price=96.0, vwap=100.0), _utc(2, 0))
        )
        assert sig is None

    @pytest.mark.asyncio
    async def test_trend_filter_off_by_default_lets_dip_fire(self):
        # Same downtrend + shallow dip, but the filter defaults off → fires.
        adapter = SetupDEntryAdapter(
            SetupDEntryConfig(min_atr_ratio=0.0, stall_buffer_atr_mult=100.0)
        )
        step = (101.0 - 130.0) / 29
        for i in range(30):
            v = 130.0 + step * i
            await adapter.generate(_context(_md(current_price=v, vwap=v), _utc(2, 0)))
        sig = await adapter.generate(
            _context(_md(current_price=96.0, vwap=100.0), _utc(2, 0))
        )
        assert sig is not None
        assert sig.metadata["signal_direction"] == "long"


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
        assert sig.metadata["z"] == pytest.approx(2.0)
        assert sig.metadata["target_rr"] == pytest.approx(4.0 / 3.0)
        assert sig.metadata["risk_points"] == pytest.approx(3.0)
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
        # stall_buffer high → isolate the vol gate (the stall guard is covered by
        # its own regression test below).
        adapter = SetupDEntryAdapter(
            SetupDEntryConfig(vol_warmup_bars=30, stall_buffer_atr_mult=10.0)
        )
        # market_data WITHOUT atr_90th_percentile → adapter defaults it to atr*1.5.
        for _i in range(30):
            calm = {
                "code": "101S6000",
                "close": 100.05,
                "open": 100.0,
                "prev_close": 100.0,
                "vwap": 100.0,
                "atr": 1.0,
            }
            await adapter.generate(_context(calm, _utc(2, 0)))
        spike = {
            "code": "101S6000",
            "close": 104.0,
            "open": 100.0,
            "prev_close": 100.0,
            "vwap": 100.0,
            "atr": 2.0,
        }
        sig = await adapter.generate(_context(spike, _utc(2, 0)))
        assert sig is not None
        assert sig.metadata["signal_direction"] == "short"

    @pytest.mark.asyncio
    async def test_live_default_15min_range_stall_guard_still_fires(self):
        """Regression for the 2nd review blocker: the live orchestrator path
        supplies NO last_15min_high/low (build_market_context defaults both to
        current_price → the stall guard would silently never fire live while it
        was active in backtest). The setup must self-compute the recent range, so
        a runaway-trend bar is STILL rejected with NO 15-min keys present.
        """
        adapter = SetupDEntryAdapter(
            SetupDEntryConfig(vol_warmup_bars=10, range_warmup_bars=5)
        )

        def bar(close: float, atr: float) -> dict:
            # Live-shaped market_data: NO last_15min_high/low keys at all.
            return {
                "code": "101S6000",
                "close": close,
                "open": 100.0,
                "prev_close": 100.0,
                "vwap": 100.0,
                "atr": atr,
            }

        # Warm with flat closes at 100 → self-computed recent high/low ≈ 100.
        for _i in range(12):
            await adapter.generate(_context(bar(100.0, 1.0), _utc(2, 0)))

        # Runaway up: close 110, recent high ≈ 100 → 110-100=10 >> buffer → REJECT
        # even though the build_market_context default would put 15-min high=110.
        runaway = await adapter.generate(_context(bar(110.0, 2.0), _utc(2, 0)))
        assert runaway is None  # stall guard fired (still_trending_up)

        # A stalling spike (price near the recent high) still fires: ramp the
        # recent high up to ~103.5, then a bar at 104 within buffer.
        adapter2 = SetupDEntryAdapter(
            SetupDEntryConfig(vol_warmup_bars=10, range_warmup_bars=5)
        )
        for i in range(12):
            await adapter2.generate(_context(bar(100.0 + i * 0.35, 2.0), _utc(2, 0)))
        spike = await adapter2.generate(_context(bar(104.0, 2.0), _utc(2, 0)))
        assert spike is not None
        assert spike.metadata["signal_direction"] == "short"


class TestSetupDMinConfidence:
    """Adapter-level min_confidence gate passthrough."""

    @pytest.mark.asyncio
    async def test_min_confidence_passthrough_rejects(self):
        """min_confidence=0.9 via adapter config rejects edge-of-band signal."""
        adapter = SetupDEntryAdapter(
            SetupDEntryConfig(
                vol_warmup_bars=30, stall_buffer_atr_mult=10.0, min_confidence=0.9
            )
        )
        md = _md(current_price=103.7, vwap=100.0, atr=2.0)
        ctx = _context(md, _utc(2, 0))
        # Warm up vol + range windows
        for _ in range(30):
            await adapter.generate(
                _context(_md(current_price=100.0, vwap=100.0, atr=2.0), _utc(2, 0))
            )
        sig = await adapter.generate(ctx)
        assert sig is None  # low confidence ≈ 0.5 < 0.9


class _FakeLLMCtx:
    """Minimal duck-typed LLM MarketContext stub (avoids importing shared.llm chain)."""

    def __init__(
        self, regime: str = "NEUTRAL", risk_score: float = 50.0, confidence: float = 0.8
    ) -> None:
        self.regime = regime
        self.risk_score = risk_score
        self.confidence = confidence


class TestSetupDDirectionBlock:
    """Regime direction-block (long_blocked_regimes / short_blocked_regimes)."""

    def _llm_ctx(self, regime: str) -> _FakeLLMCtx:
        return _FakeLLMCtx(regime=regime)

    def _context_with_regime(self, md: dict, ts: datetime, regime: str) -> EntryContext:
        return EntryContext(
            market_data=md,
            indicators=md,
            timestamp=ts,
            metadata={},
            market_context=self._llm_ctx(regime),
        )

    def _context_with_metadata_regime(
        self, md: dict, ts: datetime, regime: str
    ) -> EntryContext:
        return EntryContext(
            market_data=md,
            indicators=md,
            timestamp=ts,
            metadata={"regime": regime},
            market_context=None,
        )

    @pytest.mark.asyncio
    async def test_short_blocked_in_bull_strong(self):
        """SHORT signal is dropped when regime=BULL_STRONG and short_blocked_regimes configured."""
        adapter = SetupDEntryAdapter(
            SetupDEntryConfig(
                vol_warmup_bars=30,
                stall_buffer_atr_mult=10.0,
                short_blocked_regimes=["BULL_STRONG"],
            )
        )
        # Warm windows
        for _ in range(30):
            await adapter.generate(
                self._context_with_regime(
                    _md(current_price=100.0, vwap=100.0, atr=2.0),
                    _utc(2, 0),
                    "BULL_STRONG",
                )
            )
        # Up-spike would normally fire SHORT
        md = _md(current_price=104.0, vwap=100.0, atr=2.0)
        sig = await adapter.generate(
            self._context_with_regime(md, _utc(2, 0), "BULL_STRONG")
        )
        assert sig is None  # direction_blocked

    @pytest.mark.asyncio
    async def test_short_blocked_from_orchestrator_metadata_regime(self):
        """Live orchestrator metadata regime blocks SHORT even without LLM context."""
        adapter = SetupDEntryAdapter(
            SetupDEntryConfig(
                vol_warmup_bars=30,
                stall_buffer_atr_mult=10.0,
                short_blocked_regimes=["BULL_STRONG"],
            )
        )
        for _ in range(30):
            await adapter.generate(
                self._context_with_metadata_regime(
                    _md(current_price=100.0, vwap=100.0, atr=2.0),
                    _utc(2, 0),
                    "BULL_STRONG",
                )
            )
        md = _md(current_price=104.0, vwap=100.0, atr=2.0)
        sig = await adapter.generate(
            self._context_with_metadata_regime(md, _utc(2, 0), "BULL_STRONG")
        )
        assert sig is None

    @pytest.mark.asyncio
    async def test_short_allowed_in_neutral_regime(self):
        """SHORT signal passes when regime is not in short_blocked_regimes."""
        adapter = SetupDEntryAdapter(
            SetupDEntryConfig(
                vol_warmup_bars=30,
                stall_buffer_atr_mult=10.0,
                short_blocked_regimes=["BULL_STRONG"],
            )
        )
        for _ in range(30):
            await adapter.generate(
                self._context_with_regime(
                    _md(current_price=100.0, vwap=100.0, atr=2.0), _utc(2, 0), "NEUTRAL"
                )
            )
        md = _md(current_price=104.0, vwap=100.0, atr=2.0)
        sig = await adapter.generate(
            self._context_with_regime(md, _utc(2, 0), "NEUTRAL")
        )
        assert sig is not None
        assert sig.metadata["signal_direction"] == "short"

    @pytest.mark.asyncio
    async def test_direction_block_noop_when_lists_empty(self):
        """Empty blocked lists (default) never suppress signals."""
        adapter = SetupDEntryAdapter(
            SetupDEntryConfig(vol_warmup_bars=30, stall_buffer_atr_mult=10.0)
        )
        for _ in range(30):
            await adapter.generate(
                self._context_with_regime(
                    _md(current_price=100.0, vwap=100.0, atr=2.0),
                    _utc(2, 0),
                    "BULL_STRONG",
                )
            )
        md = _md(current_price=104.0, vwap=100.0, atr=2.0)
        sig = await adapter.generate(
            self._context_with_regime(md, _utc(2, 0), "BULL_STRONG")
        )
        assert sig is not None  # no block configured

    @pytest.mark.asyncio
    async def test_long_blocked_in_bear_strong(self):
        """LONG signal is dropped when regime=BEAR_STRONG and long_blocked_regimes configured."""
        adapter = SetupDEntryAdapter(
            SetupDEntryConfig(
                vol_warmup_bars=30,
                stall_buffer_atr_mult=10.0,
                long_blocked_regimes=["BEAR_STRONG"],
            )
        )
        for _ in range(30):
            await adapter.generate(
                self._context_with_regime(
                    _md(current_price=100.0, vwap=100.0, atr=2.0),
                    _utc(2, 0),
                    "BEAR_STRONG",
                )
            )
        # Down-spike would normally fire LONG
        md = _md(current_price=96.0, vwap=100.0, atr=2.0)
        sig = await adapter.generate(
            self._context_with_regime(md, _utc(2, 0), "BEAR_STRONG")
        )
        assert sig is None  # direction_blocked


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
        # required indicators expose only the live-available MR inputs. The vol
        # reference AND the recent range are self-computed, so neither
        # atr_90th_percentile nor last_15min_high/low is a required external
        # indicator (neither has a live producer in the orchestrator path).
        assert "vwap" in strat.entry.required_indicators
        assert "atr" in strat.entry.required_indicators
        assert "atr_90th_percentile" not in strat.entry.required_indicators
        assert "last_15min_high" not in strat.entry.required_indicators
        assert "last_15min_low" not in strat.entry.required_indicators
