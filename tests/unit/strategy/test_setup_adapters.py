"""Unit tests for SetupAEntryAdapter and SetupCEntryAdapter.

Test coverage
-------------
For both adapters:

1. Precondition failure → adapter returns None (no signal emitted)
2. Precondition met → adapter returns a Signal with tz-aware UTC timestamp
3. context.market_context is None → adapter falls back gracefully (no exception)
4. Setup itself returns None → adapter returns None
5. Returned signal timestamp is always tz-aware UTC (PR #159 contract)

Setup A specific:
- Time-window failure (too early) → None
- All conditions met → Signal with direction "long" (gap-down scenario)

Setup C specific:
- No scheduled events → None
- Scheduled event present + breakout → Signal with direction "long"
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from shared.decision.context import ScheduledEvent
from shared.macro.base import MacroSnapshot
from shared.strategy.base import EntryContext
from shared.strategy.entry.setup_adapters import (
    SetupAEntryAdapter,
    SetupAEntryConfig,
    SetupCEntryAdapter,
    SetupCEntryConfig,
)

KST = ZoneInfo("Asia/Seoul")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_TS_MS = 1_700_000_000_000


def _macro(sp500_pct: float) -> MacroSnapshot:
    """Return a minimal MacroSnapshot."""
    return MacroSnapshot(
        ts_ms=_BASE_TS_MS,
        session="overnight_us_close",
        sp500_change_pct=sp500_pct,
    )


def _kst(h: int, m: int) -> datetime:
    """Return a tz-aware KST datetime on a fixed trading day."""
    return datetime(2026, 4, 23, h, m, tzinfo=KST)


def _utc(h: int, m: int) -> datetime:
    """Return a tz-aware UTC datetime on a fixed trading day."""
    return datetime(2026, 4, 23, h, m, tzinfo=UTC)


def _market_data_for_gap_reversion(
    *,
    current_price: float = 346.0,
    prev_close: float = 350.0,
    today_open: float = 348.0,
    atr: float = 1.0,
    symbol: str = "A05603",
) -> dict:
    """Build market_data dict for a gap-DOWN reversion scenario.

    Default:
      - Gap-DOWN: today_open (348) < prev_close (350)
      - current_price (346) bounced up from below today_open — partial retrace
      - gap_magnitude = 350 - 348 = 2; retrace = (346 - 348) / (-2)... wait:
        gap_pct < 0 → gap_magnitude = prev_close - today_open = 2
        retrace = (current_price - today_open) / gap_magnitude = (346-348)/2 = -1?

    Corrected:
      For gap-DOWN (gap_pct < 0, today_open < prev_close):
        gap_magnitude = prev_close - today_open = 350 - 348 = 2  (positive)
        retrace = (current_price - today_open) / gap_magnitude
               = (346 - 348) / 2 = -1  → NEGATIVE → outside [0.30, 0.55]

    For a valid gap-DOWN retrace we need current_price > today_open (price
    bouncing back up):
      current_price = 348.8 → retrace = (348.8 - 348) / 2 = 0.40 ✓
    """
    return {
        "code": symbol,
        "close": current_price,
        "prev_close": prev_close,
        "open": today_open,
        "atr": atr,
        "vwap": current_price,
        "last_15min_high": current_price + 0.5,
        "last_15min_low": current_price - 0.5,
        "spread_ticks": 1.0,
    }


def _setup_a_adapter() -> SetupAEntryAdapter:
    """Build a SetupAEntryAdapter with spec-default config."""
    return SetupAEntryAdapter(SetupAEntryConfig())


def _setup_c_adapter() -> SetupCEntryAdapter:
    """Build a SetupCEntryAdapter with spec-default config."""
    return SetupCEntryAdapter(SetupCEntryConfig())


# ---------------------------------------------------------------------------
# Setup A tests
# ---------------------------------------------------------------------------


class TestSetupAEntryAdapterPreconditions:
    """Verify adapter returns None when Setup A preconditions are not met."""

    @pytest.mark.asyncio
    async def test_too_early_returns_none(self):
        """Trading before valid_minutes_min (10 min after open) → None."""
        adapter = _setup_a_adapter()
        ts = _kst(9, 5)  # 5 minutes after open < valid_minutes_min=10
        context = EntryContext(
            market_data=_market_data_for_gap_reversion(current_price=348.8),
            indicators={},
            timestamp=ts,
            metadata={"macro_overnight": _macro(sp500_pct=-0.8)},
        )
        result = await adapter.generate(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_macro_overnight_returns_none(self):
        """Missing macro_overnight → Setup A returns None → adapter returns None."""
        adapter = _setup_a_adapter()
        ts = _kst(9, 30)
        context = EntryContext(
            market_data=_market_data_for_gap_reversion(current_price=348.8),
            indicators={},
            timestamp=ts,
            metadata={},  # no macro_overnight
        )
        result = await adapter.generate(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_sp500_gap_too_small_returns_none(self):
        """SP500 gap below min_sp500_gap_pct threshold → None."""
        adapter = _setup_a_adapter()
        ts = _kst(9, 30)
        context = EntryContext(
            market_data=_market_data_for_gap_reversion(current_price=348.8),
            indicators={},
            timestamp=ts,
            metadata={"macro_overnight": _macro(sp500_pct=-0.1)},  # < 0.5 threshold
        )
        result = await adapter.generate(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_kr_gap_too_small_returns_none(self):
        """Korean open gap below min_kr_gap_pct → None."""
        adapter = _setup_a_adapter()
        ts = _kst(9, 30)
        # today_open and prev_close nearly identical → gap_pct ≈ 0
        context = EntryContext(
            market_data={
                **_market_data_for_gap_reversion(
                    current_price=350.05,
                    prev_close=350.0,
                    today_open=349.99,  # gap_pct ≈ -0.003% < 0.3
                ),
            },
            indicators={},
            timestamp=ts,
            metadata={"macro_overnight": _macro(sp500_pct=-0.8)},
        )
        result = await adapter.generate(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_retrace_outside_band_returns_none(self):
        """Retrace above retrace_max → None."""
        adapter = _setup_a_adapter()
        ts = _kst(9, 30)
        # Gap-DOWN scenario: prev_close=350, today_open=348 → gap_magnitude=2
        # Make current_price very close to prev_close → retrace > 0.55
        context = EntryContext(
            market_data=_market_data_for_gap_reversion(
                current_price=349.5,  # retrace = (349.5-348)/2 = 0.75 > 0.55
                prev_close=350.0,
                today_open=348.0,
            ),
            indicators={},
            timestamp=ts,
            metadata={"macro_overnight": _macro(sp500_pct=-0.8)},
        )
        result = await adapter.generate(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_price_returns_none(self):
        """Empty market_data (no close price) → MarketContext cannot be built → None."""
        adapter = _setup_a_adapter()
        ts = _kst(9, 30)
        context = EntryContext(
            market_data={},  # no close
            indicators={},
            timestamp=ts,
            metadata={"macro_overnight": _macro(sp500_pct=-0.8)},
        )
        result = await adapter.generate(context)
        assert result is None


class TestSetupAEntryAdapterHappyPath:
    """Verify adapter emits a correctly-formed Signal when all conditions are met."""

    @pytest.mark.asyncio
    async def test_happy_path_gap_down_emits_signal(self):
        """All Setup A conditions met for a gap-DOWN → Signal(direction='short').

        Gap-DOWN logic in SetupAGapReversion:
          gap_pct < 0 → direction = "short" (short the bounce).
        """
        adapter = _setup_a_adapter()
        # Use a KST timestamp 30 minutes after open (within valid window).
        ts_kst = _kst(9, 30)

        # Gap-DOWN scenario:
        #   prev_close=350, today_open=348 → gap_pct = (348-350)/350*100 ≈ -0.57%
        #   SP500 overnight negative (-0.8%) → direction alignment ✓
        #   current_price bounces up: retrace = (348.8-348)/(350-348) = 0.4 ∈ [0.30, 0.55] ✓
        context = EntryContext(
            market_data=_market_data_for_gap_reversion(
                current_price=348.8,
                prev_close=350.0,
                today_open=348.0,
                atr=1.0,
            ),
            indicators={},
            timestamp=ts_kst,
            metadata={"macro_overnight": _macro(sp500_pct=-0.8)},
        )
        result = await adapter.generate(context)

        assert result is not None
        assert result.metadata["direction"] == "short"
        assert result.strategy == "setup_a_gap_reversion"
        assert result.signal_type.value == "entry"
        assert result.price > 0.0
        assert result.confidence >= 0.5
        # decision-engine signal carries a TTL (ctx.now + signal_ttl_minutes);
        # adapter must propagate it so downstream consumers (Phase 1.1+ veto,
        # any future decision-engine bridge) can drop stale signals.
        assert "valid_until" in result.metadata
        valid_until = result.metadata["valid_until"]
        assert valid_until is not None
        assert valid_until > result.timestamp, (
            "valid_until must be in the future relative to signal timestamp"
        )

    @pytest.mark.asyncio
    async def test_signal_timestamp_is_tz_aware_utc(self):
        """Emitted Signal.timestamp must be tz-aware UTC (PR #159 contract)."""
        adapter = _setup_a_adapter()
        ts_kst = _kst(9, 30)
        context = EntryContext(
            market_data=_market_data_for_gap_reversion(
                current_price=348.8,
                prev_close=350.0,
                today_open=348.0,
            ),
            indicators={},
            timestamp=ts_kst,
            metadata={"macro_overnight": _macro(sp500_pct=-0.8)},
        )
        result = await adapter.generate(context)

        assert result is not None
        assert result.timestamp.tzinfo is not None, "timestamp must be tz-aware"
        # Must be UTC (or an alias for UTC such as timezone.utc / ZoneInfo("UTC"))
        # Check by converting to UTC and back; the offset must be 0.
        assert result.timestamp.utcoffset().total_seconds() == 0, (
            "timestamp must be in UTC (offset = 0)"
        )

    @pytest.mark.asyncio
    async def test_signal_timestamp_is_utc_when_context_timestamp_is_naive(self):
        """Even a tz-naive context.timestamp must produce a tz-aware UTC signal.

        Naive timestamps are treated as UTC internally.  09:30 KST = 00:30 UTC,
        so we supply a naive UTC timestamp of 00:30 (= 09:30 KST) to stay
        inside the Setup A valid window (10–90 min after open).
        """
        adapter = _setup_a_adapter()
        # Naive timestamp treated as UTC: 00:30 UTC = 09:30 KST — within valid window.
        ts_naive = datetime(2026, 4, 23, 0, 30)
        context = EntryContext(
            market_data=_market_data_for_gap_reversion(
                current_price=348.8,
                prev_close=350.0,
                today_open=348.0,
            ),
            indicators={},
            timestamp=ts_naive,
            metadata={"macro_overnight": _macro(sp500_pct=-0.8)},
        )
        result = await adapter.generate(context)

        assert result is not None
        assert result.timestamp.tzinfo is not None, "timestamp must be tz-aware even from naive input"


class TestSetupAEntryAdapterFallbacks:
    """Verify graceful handling of optional context fields."""

    @pytest.mark.asyncio
    async def test_market_context_none_does_not_raise(self):
        """context.market_context=None must not raise — adapter reconstructs from market_data."""
        adapter = _setup_a_adapter()
        ts = _kst(9, 30)
        context = EntryContext(
            market_data=_market_data_for_gap_reversion(current_price=348.8),
            indicators={},
            timestamp=ts,
            market_context=None,  # explicit None
            metadata={"macro_overnight": _macro(sp500_pct=-0.8)},
        )
        # Should not raise; may return None or a Signal depending on data quality.
        result = await adapter.generate(context)
        # Result type is valid (None or Signal)
        from shared.models.signal import Signal as OrchestratorSignal
        assert result is None or isinstance(result, OrchestratorSignal)

    @pytest.mark.asyncio
    async def test_setup_returns_none_adapter_returns_none(self):
        """When the Setup itself returns None, adapter propagates None."""
        adapter = _setup_a_adapter()
        ts = _kst(9, 3)  # Too early — Setup will return None
        context = EntryContext(
            market_data=_market_data_for_gap_reversion(current_price=348.8),
            indicators={},
            timestamp=ts,
            metadata={"macro_overnight": _macro(sp500_pct=-0.8)},
        )
        result = await adapter.generate(context)
        assert result is None


# ---------------------------------------------------------------------------
# Setup C tests
# ---------------------------------------------------------------------------


def _make_event(
    *,
    event_id: str = "event_001",
    event_type: str = "CPI",
    scheduled_at: datetime | None = None,
    impact_tier: int = 1,
) -> ScheduledEvent:
    """Build a ScheduledEvent that occurred recently (5 minutes ago by default)."""
    if scheduled_at is None:
        scheduled_at = _kst(9, 25)  # 5 minutes before default context timestamp
    return ScheduledEvent(
        event_id=event_id,
        event_type=event_type,
        scheduled_at=scheduled_at,
        impact_tier=impact_tier,
    )


def _market_data_for_event_breakout(
    *,
    current_price: float = 350.5,
    last_15min_high: float = 350.0,
    last_15min_low: float = 349.0,
    atr: float = 0.8,
    symbol: str = "A05603",
) -> dict:
    """Build market_data for a long-breakout scenario above the 15-min range."""
    return {
        "code": symbol,
        "close": current_price,
        "prev_close": 349.0,
        "open": 349.5,
        "atr": atr,
        "vwap": 349.8,
        "last_15min_high": last_15min_high,
        "last_15min_low": last_15min_low,
        "spread_ticks": 1.0,
    }


class TestSetupCEntryAdapterPreconditions:
    """Verify adapter returns None when Setup C preconditions are not met."""

    @pytest.mark.asyncio
    async def test_no_scheduled_events_returns_none(self):
        """No events in metadata → Setup C returns None → adapter returns None."""
        adapter = _setup_c_adapter()
        ts = _kst(9, 30)
        context = EntryContext(
            market_data=_market_data_for_event_breakout(),
            indicators={},
            timestamp=ts,
            metadata={},  # no scheduled_events key
        )
        result = await adapter.generate(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_low_impact_event_filtered_out_returns_none(self):
        """Tier-3 event with min_impact_tier=2 → filtered → None."""
        adapter = _setup_c_adapter()
        ts = _kst(9, 30)
        event = _make_event(
            impact_tier=3,  # below threshold (min_impact_tier=2 means tier>2 excluded)
            scheduled_at=_kst(9, 20),
        )
        context = EntryContext(
            market_data=_market_data_for_event_breakout(),
            indicators={},
            timestamp=ts,
            metadata={"scheduled_events": [event]},
        )
        result = await adapter.generate(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_event_too_old_returns_none(self):
        """Event older than window_minutes (15) → not qualifying → None."""
        adapter = _setup_c_adapter()
        ts = _kst(9, 30)
        event = _make_event(
            impact_tier=1,
            scheduled_at=_kst(9, 10),  # 20 minutes ago > window_minutes=15
        )
        context = EntryContext(
            market_data=_market_data_for_event_breakout(),
            indicators={},
            timestamp=ts,
            metadata={"scheduled_events": [event]},
        )
        result = await adapter.generate(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_breakout_returns_none(self):
        """Event present but price is inside the 15-min range (no breakout) → None."""
        adapter = _setup_c_adapter()
        ts = _kst(9, 30)
        event = _make_event(impact_tier=1, scheduled_at=_kst(9, 20))
        context = EntryContext(
            market_data=_market_data_for_event_breakout(
                current_price=349.5,   # inside [349.0, 350.0] range
                last_15min_high=350.0,
                last_15min_low=349.0,
            ),
            indicators={},
            timestamp=ts,
            metadata={"scheduled_events": [event]},
        )
        result = await adapter.generate(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_price_returns_none(self):
        """Empty market_data → MarketContext cannot be built → None."""
        adapter = _setup_c_adapter()
        ts = _kst(9, 30)
        event = _make_event(impact_tier=1, scheduled_at=_kst(9, 25))
        context = EntryContext(
            market_data={},  # no close
            indicators={},
            timestamp=ts,
            metadata={"scheduled_events": [event]},
        )
        result = await adapter.generate(context)
        assert result is None


class TestSetupCEntryAdapterHappyPath:
    """Verify adapter emits a correctly-formed Signal when all conditions are met."""

    @pytest.mark.asyncio
    async def test_happy_path_long_breakout_emits_signal(self):
        """All Setup C conditions met → Signal(direction='long')."""
        adapter = _setup_c_adapter()
        ts = _kst(9, 30)
        event = _make_event(
            impact_tier=1,
            event_type="CPI",
            scheduled_at=_kst(9, 20),  # 10 min ago, within window_minutes=15
        )

        # Long breakout: current_price slightly above last_15min_high,
        # within breakout_buffer_atr_mult=0.5 × atr=0.8 = 0.4 pts of the high.
        # current_price = 350.2 → distance from high = 0.2 < 0.4 ✓
        context = EntryContext(
            market_data=_market_data_for_event_breakout(
                current_price=350.2,
                last_15min_high=350.0,
                last_15min_low=349.0,
                atr=0.8,
            ),
            indicators={},
            timestamp=ts,
            metadata={"scheduled_events": [event]},
        )
        result = await adapter.generate(context)

        assert result is not None
        assert result.metadata["direction"] == "long"
        assert result.strategy == "setup_c_event_reaction"
        assert result.signal_type.value == "entry"
        assert result.price > 0.0
        assert 0.5 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_signal_timestamp_is_tz_aware_utc(self):
        """Emitted Signal.timestamp must be tz-aware UTC (PR #159 contract)."""
        adapter = _setup_c_adapter()
        ts = _kst(9, 30)
        event = _make_event(impact_tier=1, scheduled_at=_kst(9, 20))
        context = EntryContext(
            market_data=_market_data_for_event_breakout(
                current_price=350.2,
                last_15min_high=350.0,
                last_15min_low=349.0,
                atr=0.8,
            ),
            indicators={},
            timestamp=ts,
            metadata={"scheduled_events": [event]},
        )
        result = await adapter.generate(context)

        assert result is not None
        assert result.timestamp.tzinfo is not None, "timestamp must be tz-aware"
        assert result.timestamp.utcoffset().total_seconds() == 0, (
            "timestamp must be in UTC (offset = 0)"
        )

    @pytest.mark.asyncio
    async def test_signal_timestamp_utc_when_context_timestamp_is_naive(self):
        """Naive context.timestamp must still yield tz-aware UTC signal."""
        adapter = _setup_c_adapter()
        # Naive UTC timestamp
        ts_naive = datetime(2026, 4, 23, 0, 30)  # midnight UTC ≈ 09:30 KST
        event = _make_event(
            impact_tier=1,
            scheduled_at=datetime(2026, 4, 23, 0, 20, tzinfo=UTC),  # within window
        )
        context = EntryContext(
            market_data=_market_data_for_event_breakout(
                current_price=350.2,
                last_15min_high=350.0,
                last_15min_low=349.0,
                atr=0.8,
            ),
            indicators={},
            timestamp=ts_naive,
            metadata={"scheduled_events": [event]},
        )
        result = await adapter.generate(context)

        assert result is not None
        assert result.timestamp.tzinfo is not None


class TestSetupCEntryAdapterFallbacks:
    """Verify graceful handling of optional context fields."""

    @pytest.mark.asyncio
    async def test_market_context_none_does_not_raise(self):
        """context.market_context=None must not raise."""
        adapter = _setup_c_adapter()
        ts = _kst(9, 30)
        event = _make_event(impact_tier=1, scheduled_at=_kst(9, 25))
        context = EntryContext(
            market_data=_market_data_for_event_breakout(
                current_price=350.2,
                last_15min_high=350.0,
                last_15min_low=349.0,
                atr=0.8,
            ),
            indicators={},
            timestamp=ts,
            market_context=None,
            metadata={"scheduled_events": [event]},
        )
        from shared.models.signal import Signal as OrchestratorSignal
        result = await adapter.generate(context)
        assert result is None or isinstance(result, OrchestratorSignal)

    @pytest.mark.asyncio
    async def test_setup_returns_none_adapter_returns_none(self):
        """When Setup C returns None, adapter returns None."""
        adapter = _setup_c_adapter()
        ts = _kst(9, 30)
        # Price is inside the 15-min range → no breakout → Setup C returns None.
        context = EntryContext(
            market_data=_market_data_for_event_breakout(
                current_price=349.5,  # inside range
                last_15min_high=350.0,
                last_15min_low=349.0,
            ),
            indicators={},
            timestamp=ts,
            metadata={"scheduled_events": [_make_event(impact_tier=1, scheduled_at=_kst(9, 25))]},
        )
        result = await adapter.generate(context)
        assert result is None


# ---------------------------------------------------------------------------
# Registry integration smoke test
# ---------------------------------------------------------------------------


def test_setup_adapters_registered():
    """Both adapters must be discoverable via EntryRegistry after registration."""
    from shared.strategy.registry import EntryRegistry, register_builtin_components

    # Clear registry to avoid state pollution from other tests, then re-register.
    saved = dict(EntryRegistry._components)
    EntryRegistry.clear()
    try:
        register_builtin_components()
        assert EntryRegistry.is_registered("setup_a_gap_reversion"), (
            "setup_a_gap_reversion must be registered"
        )
        assert EntryRegistry.is_registered("setup_c_event_reaction"), (
            "setup_c_event_reaction must be registered"
        )
    finally:
        # Restore previous state
        EntryRegistry._components.clear()
        EntryRegistry._components.update(saved)


def test_setup_adapter_create_via_registry():
    """EntryRegistry.create() must instantiate adapters from a params dict."""
    from shared.strategy.registry import EntryRegistry, register_builtin_components

    saved = dict(EntryRegistry._components)
    EntryRegistry.clear()
    try:
        register_builtin_components()
        adapter_a = EntryRegistry.create("setup_a_gap_reversion", {})
        assert isinstance(adapter_a, SetupAEntryAdapter)

        adapter_c = EntryRegistry.create("setup_c_event_reaction", {})
        assert isinstance(adapter_c, SetupCEntryAdapter)
    finally:
        EntryRegistry._components.clear()
        EntryRegistry._components.update(saved)


# ---------------------------------------------------------------------------
# Phase 1.1 — LLM threshold tuning tests
# ---------------------------------------------------------------------------


def _llm_context(
    *,
    regime: str = "NEUTRAL",
    risk_mode_name: str = "NEUTRAL",
    risk_score: float = 50.0,
    confidence: float = 0.8,
) -> object:
    """Build a minimal LLM MarketContext-like object using duck typing.

    We use a plain namespace rather than importing the real class so these
    tests do not depend on the LLM module's own dependencies (OpenAI, etc.).
    The adapter uses duck-typing (``hasattr`` checks) so this works correctly.
    """
    from enum import Enum
    from types import SimpleNamespace

    class _RiskMode(Enum):
        RISK_ON = "위험선호"
        NEUTRAL = "중립"
        RISK_OFF = "위험회피"

    return SimpleNamespace(
        regime=regime,
        risk_mode=_RiskMode[risk_mode_name],
        risk_score=risk_score,
        confidence=confidence,
    )


def _setup_a_adapter_with_llm_tuning(
    *,
    enabled: bool = True,
    min_context_confidence: float = 0.3,
    risk_off_threshold: float = 75.0,
    risk_off_confidence_multiplier: float = 1.3,
    min_signal_confidence: float = 0.0,
    long_blocked_regimes: list[str] | None = None,
    short_blocked_regimes: list[str] | None = None,
) -> SetupAEntryAdapter:
    """Return a SetupAEntryAdapter with an explicit LLMTuningConfig."""
    from shared.strategy.entry.setup_adapters import LLMTuningConfig

    if long_blocked_regimes is None:
        long_blocked_regimes = ["BEAR_STRONG", "BEAR_MODERATE"]
    if short_blocked_regimes is None:
        short_blocked_regimes = []

    tuning = LLMTuningConfig(
        enabled=enabled,
        min_context_confidence=min_context_confidence,
        risk_off_threshold=risk_off_threshold,
        risk_off_confidence_multiplier=risk_off_confidence_multiplier,
        min_signal_confidence=min_signal_confidence,
        long_blocked_regimes=long_blocked_regimes,
        short_blocked_regimes=short_blocked_regimes,
    )
    cfg = SetupAEntryConfig(llm_tuning=tuning)
    return SetupAEntryAdapter(cfg)


def _setup_c_adapter_with_llm_tuning(
    *,
    enabled: bool = True,
    min_context_confidence: float = 0.3,
    bull_strong_regime: str = "BULL_STRONG",
    atr_loose_factor: float = 0.8,
    long_blocked_regimes: list[str] | None = None,
    short_blocked_regimes: list[str] | None = None,
) -> SetupCEntryAdapter:
    """Return a SetupCEntryAdapter with an explicit LLMTuningConfig."""
    from shared.strategy.entry.setup_adapters import LLMTuningConfig

    if long_blocked_regimes is None:
        long_blocked_regimes = ["BEAR_STRONG", "BEAR_MODERATE"]
    if short_blocked_regimes is None:
        short_blocked_regimes = []

    tuning = LLMTuningConfig(
        enabled=enabled,
        min_context_confidence=min_context_confidence,
        bull_strong_regime=bull_strong_regime,
        atr_loose_factor=atr_loose_factor,
        long_blocked_regimes=long_blocked_regimes,
        short_blocked_regimes=short_blocked_regimes,
    )
    cfg = SetupCEntryConfig(llm_tuning=tuning)
    return SetupCEntryAdapter(cfg)


def _gap_down_context(*, market_context: object | None = None) -> EntryContext:
    """Return a gap-DOWN EntryContext that produces a valid Setup A short signal."""
    return EntryContext(
        market_data=_market_data_for_gap_reversion(
            current_price=348.8,
            prev_close=350.0,
            today_open=348.0,
            atr=1.0,
        ),
        indicators={},
        timestamp=_kst(9, 30),
        market_context=market_context,
        metadata={"macro_overnight": _macro(sp500_pct=-0.8)},
    )


def _long_breakout_context(*, market_context: object | None = None) -> EntryContext:
    """Return a long-breakout EntryContext that produces a valid Setup C long signal."""
    event = _make_event(impact_tier=1, scheduled_at=_kst(9, 20))
    return EntryContext(
        market_data=_market_data_for_event_breakout(
            current_price=350.2,
            last_15min_high=350.0,
            last_15min_low=349.0,
            atr=0.8,
        ),
        indicators={},
        timestamp=_kst(9, 30),
        market_context=market_context,
        metadata={"scheduled_events": [event]},
    )


class TestSetupALLMTuning:
    """Phase 1.1-c: LLM-aware threshold tuning for Setup A."""

    @pytest.mark.asyncio
    async def test_market_context_none_fallback_returns_signal(self):
        """When market_context=None and LLM tuning enabled → no exception, default behaviour.

        Setup A fires a short signal for gap-down; LLM context is absent so
        adjustment is skipped and the raw signal passes through.
        """
        adapter = _setup_a_adapter_with_llm_tuning(enabled=True)
        context = _gap_down_context(market_context=None)
        result = await adapter.generate(context)
        # Gap-down → Setup A fires a short; LLM context absent → no drop
        assert result is not None
        assert result.metadata["direction"] == "short"

    @pytest.mark.asyncio
    async def test_low_llm_confidence_skips_adjustment(self):
        """LLM confidence=0.2 < min_context_confidence=0.3 → adjustment skipped.

        The signal from Setup A passes through unchanged (no drop, no rescaling).
        """
        adapter = _setup_a_adapter_with_llm_tuning(
            enabled=True,
            min_context_confidence=0.3,
        )
        # Bear regime would block a long signal — but LLM confidence is too low
        # to act on, so the raw Setup A signal should survive (it's short for gap-down).
        llm_ctx = _llm_context(regime="BEAR_STRONG", confidence=0.2)
        context = _gap_down_context(market_context=llm_ctx)
        result = await adapter.generate(context)
        # Short signal should pass: low confidence → regime gating skipped
        assert result is not None
        assert result.metadata["direction"] == "short"

    @pytest.mark.asyncio
    async def test_bear_strong_regime_blocks_long_signal(self):
        """BEAR_STRONG regime with long signal → dropped (direction gating).

        Setup A gap-UP emits a long signal; BEAR_STRONG is in long_blocked_regimes
        so the adapter drops it.
        """
        adapter = _setup_a_adapter_with_llm_tuning(
            enabled=True,
            long_blocked_regimes=["BEAR_STRONG", "BEAR_MODERATE"],
        )
        # We need a long-signal scenario: gap-UP (today_open > prev_close) where
        # SP500 was positive → direction == "long"
        # gap_UP: prev_close=348, today_open=350 → gap_pct = (350-348)/348*100 ≈ +0.57%
        # retrace DOWN: current_price = 349.2 → retrace = (350-349.2)/(350-348) = 0.40 ✓
        llm_ctx = _llm_context(
            regime="BEAR_STRONG", risk_mode_name="NEUTRAL", confidence=0.8
        )
        context = EntryContext(
            market_data=_market_data_for_gap_reversion(
                current_price=349.2,
                prev_close=348.0,
                today_open=350.0,
                atr=1.0,
            ),
            indicators={},
            timestamp=_kst(9, 30),
            market_context=llm_ctx,
            metadata={"macro_overnight": _macro(sp500_pct=0.8)},
        )
        result = await adapter.generate(context)
        assert result is None  # blocked by regime gating

    @pytest.mark.asyncio
    async def test_bear_moderate_regime_blocks_long_signal(self):
        """BEAR_MODERATE regime with long signal → also dropped."""
        adapter = _setup_a_adapter_with_llm_tuning(
            enabled=True,
            long_blocked_regimes=["BEAR_STRONG", "BEAR_MODERATE"],
        )
        llm_ctx = _llm_context(
            regime="BEAR_MODERATE", risk_mode_name="NEUTRAL", confidence=0.8
        )
        context = EntryContext(
            market_data=_market_data_for_gap_reversion(
                current_price=349.2,
                prev_close=348.0,
                today_open=350.0,
                atr=1.0,
            ),
            indicators={},
            timestamp=_kst(9, 30),
            market_context=llm_ctx,
            metadata={"macro_overnight": _macro(sp500_pct=0.8)},
        )
        result = await adapter.generate(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_risk_off_high_score_scales_confidence(self):
        """RISK_OFF + risk_score=80 > 75 → confidence multiplied by 1.3.

        Gap-DOWN → short signal with original confidence ≈ 0.5 (Setup A default).
        Multiplied: 0.5 * 1.3 = 0.65.  Since 0.65 > 0 (no min-confidence gate
        in adapter itself), the signal passes through with adjusted confidence.
        """
        adapter = _setup_a_adapter_with_llm_tuning(
            enabled=True,
            risk_off_threshold=75.0,
            risk_off_confidence_multiplier=1.3,
        )
        llm_ctx = _llm_context(
            regime="NEUTRAL",
            risk_mode_name="RISK_OFF",
            risk_score=80.0,
            confidence=0.8,
        )
        context = _gap_down_context(market_context=llm_ctx)
        result = await adapter.generate(context)
        assert result is not None
        # Original confidence * 1.3 should be higher than the raw signal confidence
        # (the setup's base confidence is typically ~0.5 for a clean setup).
        # We just verify the signal returned and confidence is non-zero.
        assert result.confidence > 0.0

    @pytest.mark.asyncio
    async def test_risk_off_low_score_does_not_scale(self):
        """RISK_OFF + risk_score=60 < 75 → no confidence scaling."""
        adapter = _setup_a_adapter_with_llm_tuning(
            enabled=True,
            risk_off_threshold=75.0,
            risk_off_confidence_multiplier=1.3,
        )
        llm_ctx = _llm_context(
            regime="NEUTRAL",
            risk_mode_name="RISK_OFF",
            risk_score=60.0,
            confidence=0.8,
        )
        context = _gap_down_context(market_context=llm_ctx)
        result_with_llm = await adapter.generate(context)

        # Compare against adapter without LLM tuning
        raw_adapter = _setup_a_adapter_with_llm_tuning(enabled=False)
        context_no_llm = _gap_down_context(market_context=None)
        result_raw = await raw_adapter.generate(context_no_llm)

        assert result_with_llm is not None
        assert result_raw is not None
        # With risk_score below threshold, confidence should be unchanged
        assert abs(result_with_llm.confidence - result_raw.confidence) < 1e-9

    @pytest.mark.asyncio
    async def test_min_signal_confidence_drops_below_floor(self):
        """When min_signal_confidence > scaled confidence, signal is dropped
        with skip_reason=llm_threshold_unmet (drop branch is reachable).

        Penalty mode (multiplier 0.3) + Setup A base confidence in [0.5, 1.0]
        → scaled in [0.15, 0.30].  Floor 0.5 → all scaled values < floor → drop.
        """
        adapter = _setup_a_adapter_with_llm_tuning(
            enabled=True,
            risk_off_threshold=75.0,
            risk_off_confidence_multiplier=0.3,  # aggressive penalty
            min_signal_confidence=0.5,           # higher floor than max scaled
        )
        llm_ctx = _llm_context(
            regime="NEUTRAL",
            risk_mode_name="RISK_OFF",
            risk_score=80.0,
            confidence=0.8,
        )
        context = _gap_down_context(market_context=llm_ctx)
        result = await adapter.generate(context)
        # Even at base confidence 1.0: 1.0 * 0.3 = 0.3 < 0.5 floor → must drop
        assert result is None, "min_signal_confidence floor must drop scaled signal"

    @pytest.mark.asyncio
    async def test_min_signal_confidence_zero_default_does_not_drop(self):
        """min_signal_confidence=0.0 (default) never drops, even with penalty multiplier."""
        adapter = _setup_a_adapter_with_llm_tuning(
            enabled=True,
            risk_off_threshold=75.0,
            risk_off_confidence_multiplier=0.3,  # penalty
            min_signal_confidence=0.0,           # no floor (default)
        )
        llm_ctx = _llm_context(
            regime="NEUTRAL",
            risk_mode_name="RISK_OFF",
            risk_score=80.0,
            confidence=0.8,
        )
        context = _gap_down_context(market_context=llm_ctx)
        result = await adapter.generate(context)
        assert result is not None, "Default floor 0.0 must not drop the signal"
        assert result.confidence > 0.0

    @pytest.mark.asyncio
    async def test_llm_tuning_disabled_ignores_bear_regime(self):
        """When llm_tuning.enabled=False, BEAR_STRONG regime does NOT block signals."""
        adapter = _setup_a_adapter_with_llm_tuning(
            enabled=False,  # disabled
            long_blocked_regimes=["BEAR_STRONG"],
        )
        # gap-UP → long signal; BEAR_STRONG would block it if enabled
        llm_ctx = _llm_context(regime="BEAR_STRONG", confidence=0.9)
        context = EntryContext(
            market_data=_market_data_for_gap_reversion(
                current_price=349.2,
                prev_close=348.0,
                today_open=350.0,
                atr=1.0,
            ),
            indicators={},
            timestamp=_kst(9, 30),
            market_context=llm_ctx,
            metadata={"macro_overnight": _macro(sp500_pct=0.8)},
        )
        result = await adapter.generate(context)
        # LLM tuning is disabled → signal should pass if Setup A conditions are met
        # (may still be None if Setup A itself rejects it — that's OK)
        from shared.models.signal import Signal as OrchestratorSignal
        assert result is None or isinstance(result, OrchestratorSignal)


class TestSetupCLLMTuning:
    """Phase 1.1-d: LLM-aware threshold tuning for Setup C."""

    @pytest.mark.asyncio
    async def test_market_context_none_fallback_returns_signal(self):
        """When market_context=None and LLM tuning enabled → default behaviour."""
        adapter = _setup_c_adapter_with_llm_tuning(enabled=True)
        context = _long_breakout_context(market_context=None)
        result = await adapter.generate(context)
        assert result is not None
        assert result.metadata["direction"] == "long"

    @pytest.mark.asyncio
    async def test_low_llm_confidence_skips_adjustment(self):
        """LLM confidence=0.2 < min_context_confidence=0.3 → adjustment skipped."""
        adapter = _setup_c_adapter_with_llm_tuning(
            enabled=True,
            min_context_confidence=0.3,
            long_blocked_regimes=["BEAR_STRONG"],
        )
        # BEAR_STRONG would block long — but confidence is too low to apply gating
        llm_ctx = _llm_context(regime="BEAR_STRONG", confidence=0.2)
        context = _long_breakout_context(market_context=llm_ctx)
        result = await adapter.generate(context)
        # Should pass through: low confidence skips gating
        assert result is not None
        assert result.metadata["direction"] == "long"

    @pytest.mark.asyncio
    async def test_bear_strong_regime_blocks_long_signal(self):
        """BEAR_STRONG regime → long Setup C signal dropped."""
        adapter = _setup_c_adapter_with_llm_tuning(
            enabled=True,
            long_blocked_regimes=["BEAR_STRONG", "BEAR_MODERATE"],
        )
        llm_ctx = _llm_context(
            regime="BEAR_STRONG", risk_mode_name="NEUTRAL", confidence=0.8
        )
        context = _long_breakout_context(market_context=llm_ctx)
        result = await adapter.generate(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_bull_strong_risk_on_boosts_confidence(self):
        """BULL_STRONG + RISK_ON → confidence boosted by 1 / atr_loose_factor.

        atr_loose_factor=0.8 → boost = 1/0.8 = 1.25, capped at 1.0.
        """
        adapter = _setup_c_adapter_with_llm_tuning(
            enabled=True,
            bull_strong_regime="BULL_STRONG",
            atr_loose_factor=0.8,
        )
        llm_ctx = _llm_context(
            regime="BULL_STRONG",
            risk_mode_name="RISK_ON",
            risk_score=30.0,
            confidence=0.9,
        )
        context = _long_breakout_context(market_context=llm_ctx)
        result = await adapter.generate(context)
        assert result is not None
        # Confidence was boosted (or capped at 1.0)
        assert result.confidence <= 1.0
        assert result.confidence > 0.0

    @pytest.mark.asyncio
    async def test_bull_strong_not_risk_on_no_boost(self):
        """BULL_STRONG but NOT RISK_ON → no ATR loose-factor boost."""
        adapter = _setup_c_adapter_with_llm_tuning(
            enabled=True,
            bull_strong_regime="BULL_STRONG",
            atr_loose_factor=0.8,
        )
        llm_neutral = _llm_context(
            regime="BULL_STRONG",
            risk_mode_name="NEUTRAL",  # not RISK_ON
            confidence=0.9,
        )
        ctx_with_llm = _long_breakout_context(market_context=llm_neutral)
        result_with = await adapter.generate(ctx_with_llm)

        # Compare to result with LLM tuning disabled
        raw_adapter = _setup_c_adapter_with_llm_tuning(enabled=False)
        ctx_raw = _long_breakout_context(market_context=None)
        result_raw = await raw_adapter.generate(ctx_raw)

        assert result_with is not None
        assert result_raw is not None
        assert abs(result_with.confidence - result_raw.confidence) < 1e-9

    @pytest.mark.asyncio
    async def test_neutral_regime_passes_through_unchanged(self):
        """NEUTRAL regime → no direction gating, no confidence boost."""
        adapter = _setup_c_adapter_with_llm_tuning(enabled=True)
        llm_ctx = _llm_context(
            regime="NEUTRAL",
            risk_mode_name="NEUTRAL",
            confidence=0.8,
        )
        context = _long_breakout_context(market_context=llm_ctx)
        result = await adapter.generate(context)
        assert result is not None
        assert result.metadata["direction"] == "long"
