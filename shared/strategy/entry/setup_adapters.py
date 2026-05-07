"""Adapter classes that wrap Phase-5 Setup A / Setup C as EntrySignalGenerator.

Phase 1.0 of the LLM-primary RL-minimization plan (PR #160 §2.4 Adapter pattern):
  - ``SetupAEntryAdapter`` wraps ``SetupAGapReversion``
  - ``SetupCEntryAdapter`` wraps ``SetupCEventReaction``

Both adapters convert the :class:`shared.strategy.base.EntryContext` available
inside ``TradingOrchestrator`` into the :class:`shared.decision.context.MarketContext`
consumed by the Setup hierarchy, then translate the returned
:class:`shared.decision.signal.Signal` into the :class:`shared.models.signal.Signal`
that the orchestrator pipeline expects.

Design notes
------------
* No LLM-threshold tuning is applied in this PR (Phase 1.0).  The ``llm_tuning``
  config section is declared but left empty — Phase 1.1 will populate it.
* Both configs are Pydantic ``ServiceConfigBase`` subclasses so they can be loaded
  from YAML via ``ConfigLoader`` without any extra boilerplate.
* The ``timestamp`` on emitted :class:`shared.models.signal.Signal` objects is
  always a tz-aware UTC ``datetime`` (PR #159 contract).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import Field

from shared.config.base import ServiceConfigBase
from shared.decision.context import MarketContext, ScheduledEvent
from shared.strategy.base import EntryContext, EntrySignalGenerator

if TYPE_CHECKING:
    from shared.models.signal import Signal as OrchestratorSignal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


class SetupAEntryConfig(ServiceConfigBase):
    """Configuration for :class:`SetupAEntryAdapter`.

    All numeric thresholds mirror :class:`~shared.decision.setups.gap_reversion.SetupAConfig`
    so that the adapter can be driven purely from YAML without referencing the
    decision-engine config file.  A ``llm_tuning`` placeholder section is
    included for Phase 1.1.
    """

    _default_config_file: ClassVar[str] = "strategies/futures/setup_a_gap_reversion.yaml"
    _default_section: ClassVar[str] = "strategy.entry.params"

    enabled: bool = Field(default=True, description="Enable/disable the adapter")
    valid_minutes_min: int = Field(
        default=10, description="Earliest minutes after open to fire (inclusive)"
    )
    valid_minutes_max: int = Field(
        default=90, description="Latest minutes after open to fire (inclusive)"
    )
    min_sp500_gap_pct: float = Field(
        default=0.5, description="Minimum absolute S&P 500 overnight gap (%)"
    )
    min_kr_gap_pct: float = Field(
        default=0.3, description="Minimum absolute Korean open gap vs prev close (%)"
    )
    retrace_min: float = Field(
        default=0.30, description="Minimum retrace ratio of the gap (fraction)"
    )
    retrace_max: float = Field(
        default=0.55, description="Maximum retrace ratio of the gap (fraction)"
    )
    stop_atr_mult: float = Field(
        default=1.5, description="ATR multiplier for the hard stop-loss"
    )
    target_gap_fill_ratio: float = Field(
        default=0.9,
        description="Fraction of the gap to fill as the take-profit target",
    )
    signal_ttl_minutes: int = Field(
        default=10, description="Signal validity window in minutes"
    )
    # Phase 1.1 placeholder — leave empty until LLM-tuning is wired up.
    llm_tuning: dict[str, Any] = Field(
        default_factory=dict,
        description="Reserved for Phase 1.1 LLM-threshold tuning parameters",
    )


class SetupCEntryConfig(ServiceConfigBase):
    """Configuration for :class:`SetupCEntryAdapter`.

    Mirrors :class:`~shared.decision.setups.event_reaction.SetupCConfig`.
    A ``llm_tuning`` placeholder section is included for Phase 1.1.
    """

    _default_config_file: ClassVar[str] = "strategies/futures/setup_c_event_reaction.yaml"
    _default_section: ClassVar[str] = "strategy.entry.params"

    enabled: bool = Field(default=True, description="Enable/disable the adapter")
    window_minutes: int = Field(
        default=15,
        description="Look-back window in minutes: events older than this are ignored",
    )
    breakout_buffer_atr_mult: float = Field(
        default=0.5,
        description=(
            "Breakout must be within this many ATRs of the 15-min high/low "
            "(prevents chasing a move that has already extended too far)"
        ),
    )
    target_atr_mult: float = Field(
        default=2.5,
        description="Take-profit = entry ± target_atr_mult × ATR14",
    )
    signal_ttl_minutes: int = Field(
        default=30,
        description="Signal validity window in minutes",
    )
    min_impact_tier: int = Field(
        default=2,
        description=(
            "Ignore events with impact_tier > this value "
            "(1 = top tier, 3 = minor; default=2 means tier-3 events are skipped)"
        ),
    )
    # Phase 1.1 placeholder.
    llm_tuning: dict[str, Any] = Field(
        default_factory=dict,
        description="Reserved for Phase 1.1 LLM-threshold tuning parameters",
    )


# ---------------------------------------------------------------------------
# Context-building helpers
# ---------------------------------------------------------------------------


def _build_market_context(context: EntryContext) -> MarketContext | None:
    """Attempt to build a :class:`MarketContext` from an :class:`EntryContext`.

    Returns ``None`` when the mandatory price fields are missing or zero,
    which causes the caller to short-circuit and return ``None`` from
    ``generate()``.

    The conversion strategy:
    * Prefer ``context.market_context`` if it is already a ``MarketContext``
      (future-proof: the orchestrator may supply one directly).
    * Otherwise reconstruct from ``context.market_data`` and
      ``context.indicators``.

    ``now`` is taken from ``context.timestamp`` and normalised to KST as
    expected by the Setup logic.  When ``context.timestamp`` is tz-naive it is
    treated as UTC and converted to KST (belt-and-suspenders against
    upstream callers that forget to set tzinfo).
    """
    from zoneinfo import ZoneInfo

    KST = ZoneInfo("Asia/Seoul")

    # ------------------------------------------------------------------
    # Fast-path: context.market_context already IS a MarketContext
    # ------------------------------------------------------------------
    mc = context.market_context
    if isinstance(mc, MarketContext):
        return mc

    # ------------------------------------------------------------------
    # Reconstruct from raw market_data / indicators
    # ------------------------------------------------------------------
    md = context.market_data or {}
    ind = context.indicators or {}

    def _get_float(keys: list[str], default: float = 0.0) -> float:
        for k in keys:
            v = md.get(k) or ind.get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    continue
        return default

    current_price = _get_float(["close", "current_price", "price"])
    if current_price <= 0.0:
        return None

    prev_close = _get_float(["prev_close", "previous_close"])
    today_open = _get_float(["open", "today_open"])
    atr_14 = _get_float(["atr", "atr_14", "atr14"])
    atr_90th = _get_float(["atr_90th_percentile", "atr_90pct"], default=atr_14 * 1.5)
    vwap = _get_float(["vwap"], default=current_price)
    last_15min_high = _get_float(
        ["last_15min_high", "range_high_15m"], default=current_price
    )
    last_15min_low = _get_float(
        ["last_15min_low", "range_low_15m"], default=current_price
    )
    spread_ticks = _get_float(["spread_ticks", "current_spread_ticks"], default=1.0)
    symbol = str(md.get("code", md.get("symbol", "")))

    # Normalise timestamp → KST-aware datetime
    ts = context.timestamp
    if ts is None:
        ts = datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    ts_kst = ts.astimezone(KST)

    # Build scheduled events list from context metadata (optional).
    # Orchestrator may inject them under metadata["scheduled_events"].
    raw_events: list[Any] = (context.metadata or {}).get("scheduled_events", [])
    scheduled_events: list[ScheduledEvent] = []
    for evt in raw_events:
        if isinstance(evt, ScheduledEvent):
            scheduled_events.append(evt)

    # Macro overnight snapshot from market_context or metadata.
    macro_overnight = None
    if mc is not None and hasattr(mc, "macro_overnight"):
        macro_overnight = mc.macro_overnight  # type: ignore[union-attr]
    else:
        macro_overnight = (context.metadata or {}).get("macro_overnight")

    return MarketContext(
        now=ts_kst,
        symbol=symbol,
        current_price=current_price,
        prev_close=prev_close,
        today_open=today_open,
        vwap=vwap,
        atr_14=atr_14,
        atr_90th_percentile=atr_90th,
        last_15min_high=last_15min_high,
        last_15min_low=last_15min_low,
        current_spread_ticks=spread_ticks,
        macro_overnight=macro_overnight,
        scheduled_events=scheduled_events,
    )


def _decision_signal_to_orchestrator_signal(
    decision_signal: Any,
    *,
    strategy_name: str,
    timestamp: datetime,
) -> OrchestratorSignal:
    """Convert a :class:`shared.decision.signal.Signal` to a :class:`shared.models.signal.Signal`.

    The ``timestamp`` argument is the authoritative tz-aware UTC timestamp from
    ``EntryContext`` — it overrides ``decision_signal.generated_at`` to ensure
    PR #159 tz-aware UTC contract is satisfied even when the Setup generates a
    KST timestamp.

    Args:
        decision_signal: Signal from the decision-engine Setup.
        strategy_name: Registry name used as the ``strategy`` field.
        timestamp: Tz-aware UTC datetime from the orchestrator tick.

    Returns:
        OrchestratorSignal ready for the TradingOrchestrator pipeline.
    """
    from shared.models.signal import Signal as OrchestratorSignal
    from shared.models.signal import SignalType

    # Ensure timestamp is tz-aware UTC (PR #159 contract).
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    else:
        timestamp = timestamp.astimezone(UTC)

    direction = decision_signal.direction  # "long" or "short"

    valid_until = getattr(decision_signal, "valid_until", None)
    metadata: dict[str, Any] = {
        "signal_direction": direction,
        "direction": direction,
        "setup_type": decision_signal.setup_type,
        "stop_loss": decision_signal.stop_loss,
        "take_profit": decision_signal.take_profit,
        "reason_tags": list(decision_signal.reason_tags),
    }
    # Preserve the decision-engine TTL so downstream consumers (risk filter,
    # orchestrator) can drop stale signals without re-deriving the deadline.
    # Phase 1.0: not yet read by orchestrator entry guards, but Phase 1.1+
    # threshold/veto logic and any future decision-engine bridge will need it.
    if valid_until is not None:
        metadata["valid_until"] = valid_until

    return OrchestratorSignal(
        code=decision_signal.symbol,
        name=decision_signal.symbol,
        signal_type=SignalType.ENTRY,
        strategy=strategy_name,
        price=decision_signal.entry_price,
        confidence=decision_signal.confidence,
        timestamp=timestamp,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


class SetupAEntryAdapter(EntrySignalGenerator[SetupAEntryConfig]):
    """EntrySignalGenerator adapter wrapping :class:`SetupAGapReversion`.

    Bridges the ``TradingOrchestrator`` entry pipeline to the Phase-5 Setup A
    gap-reversion logic without duplicating any threshold or business logic.

    Registered as ``"setup_a_gap_reversion"`` in :func:`register_builtin_components`.

    Phase 1.0 notes
    ---------------
    * LLM-threshold tuning (``llm_tuning`` section) is *not* applied yet.
    * Setup A parameters are driven entirely by the YAML config.
    * ``enabled: false`` in the default YAML — no production behaviour change.
    """

    CONFIG_CLASS = SetupAEntryConfig

    def __init__(self, config: SetupAEntryConfig) -> None:
        super().__init__(config)
        from shared.decision.setups.gap_reversion import (
            SetupAConfig,
            SetupAGapReversion,
        )

        # Build a SetupAConfig from our config fields (mirrors field names 1:1).
        setup_cfg = SetupAConfig(
            enabled=config.enabled,
            valid_minutes_min=config.valid_minutes_min,
            valid_minutes_max=config.valid_minutes_max,
            min_sp500_gap_pct=config.min_sp500_gap_pct,
            min_kr_gap_pct=config.min_kr_gap_pct,
            retrace_min=config.retrace_min,
            retrace_max=config.retrace_max,
            stop_atr_mult=config.stop_atr_mult,
            target_gap_fill_ratio=config.target_gap_fill_ratio,
            signal_ttl_minutes=config.signal_ttl_minutes,
        )
        self._setup = SetupAGapReversion(config=setup_cfg)

    def _validate_config(self) -> None:
        """Validate config fields.

        Raises:
            AssertionError: When any numeric param is out of valid range.
        """
        assert 0 <= self.config.valid_minutes_min <= self.config.valid_minutes_max, (
            "valid_minutes_min must be <= valid_minutes_max"
        )
        assert self.config.min_sp500_gap_pct >= 0.0, "min_sp500_gap_pct must be >= 0"
        assert self.config.min_kr_gap_pct >= 0.0, "min_kr_gap_pct must be >= 0"
        assert 0.0 <= self.config.retrace_min <= self.config.retrace_max <= 1.0, (
            "retrace_min/max must be in [0,1] and retrace_min <= retrace_max"
        )
        assert self.config.stop_atr_mult > 0.0, "stop_atr_mult must be > 0"
        assert 0.0 < self.config.target_gap_fill_ratio <= 1.0, (
            "target_gap_fill_ratio must be in (0, 1]"
        )
        assert self.config.signal_ttl_minutes > 0, "signal_ttl_minutes must be > 0"

    @property
    def name(self) -> str:
        """Strategy registry name."""
        return "setup_a_gap_reversion"

    @property
    def required_indicators(self) -> list[str]:
        """Minimal indicators needed to satisfy Setup A price lookups.

        The Setup only uses prices from MarketContext fields which the
        orchestrator already populates; ``atr`` is the one computed indicator.
        """
        return ["atr", "prev_close", "vwap"]

    async def generate(self, context: EntryContext) -> OrchestratorSignal | None:
        """Generate an entry signal by delegating to :class:`SetupAGapReversion`.

        Args:
            context: Orchestrator entry context for the current tick.

        Returns:
            A tz-aware UTC :class:`shared.models.signal.Signal` when Setup A
            fires, or ``None`` when any precondition fails.
        """
        mc = _build_market_context(context)
        if mc is None:
            logger.debug("SetupAEntryAdapter: unable to build MarketContext — skipping")
            return None

        decision_signal = self._setup.check(mc)
        if decision_signal is None:
            return None

        ts = context.timestamp
        if ts is None:
            ts = datetime.now(UTC)

        return _decision_signal_to_orchestrator_signal(
            decision_signal,
            strategy_name=self.name,
            timestamp=ts,
        )


class SetupCEntryAdapter(EntrySignalGenerator[SetupCEntryConfig]):
    """EntrySignalGenerator adapter wrapping :class:`SetupCEventReaction`.

    Bridges the ``TradingOrchestrator`` entry pipeline to the Phase-5 Setup C
    event-reaction logic.

    Registered as ``"setup_c_event_reaction"`` in :func:`register_builtin_components`.

    Phase 1.0 notes
    ---------------
    * LLM-threshold tuning (``llm_tuning`` section) is *not* applied yet.
    * The in-memory :class:`~shared.decision.setups.event_reaction.EventTradeTracker`
      persists only for the lifetime of this adapter instance.  A Redis-backed
      tracker will be introduced in a later phase when live paper-trading requires
      cross-process deduplication.
    * ``enabled: false`` in the default YAML — no production behaviour change.
    """

    CONFIG_CLASS = SetupCEntryConfig

    def __init__(self, config: SetupCEntryConfig) -> None:
        super().__init__(config)
        from shared.decision.setups.event_reaction import (
            SetupCConfig,
            SetupCEventReaction,
        )

        setup_cfg = SetupCConfig(
            enabled=config.enabled,
            window_minutes=config.window_minutes,
            breakout_buffer_atr_mult=config.breakout_buffer_atr_mult,
            target_atr_mult=config.target_atr_mult,
            signal_ttl_minutes=config.signal_ttl_minutes,
            min_impact_tier=config.min_impact_tier,
        )
        self._setup = SetupCEventReaction(config=setup_cfg)

    def _validate_config(self) -> None:
        """Validate config fields.

        Raises:
            AssertionError: When any numeric param is out of valid range.
        """
        assert self.config.window_minutes > 0, "window_minutes must be > 0"
        assert self.config.breakout_buffer_atr_mult > 0.0, (
            "breakout_buffer_atr_mult must be > 0"
        )
        assert self.config.target_atr_mult > 0.0, "target_atr_mult must be > 0"
        assert self.config.signal_ttl_minutes > 0, "signal_ttl_minutes must be > 0"
        assert 1 <= self.config.min_impact_tier <= 3, (
            "min_impact_tier must be between 1 and 3"
        )

    @property
    def name(self) -> str:
        """Strategy registry name."""
        return "setup_c_event_reaction"

    @property
    def required_indicators(self) -> list[str]:
        """Indicators needed by Setup C.

        Setup C requires ATR and the 15-min price range.
        """
        return ["atr", "last_15min_high", "last_15min_low"]

    async def generate(self, context: EntryContext) -> OrchestratorSignal | None:
        """Generate an entry signal by delegating to :class:`SetupCEventReaction`.

        Args:
            context: Orchestrator entry context for the current tick.

        Returns:
            A tz-aware UTC :class:`shared.models.signal.Signal` when Setup C
            fires, or ``None`` when any precondition fails.
        """
        mc = _build_market_context(context)
        if mc is None:
            logger.debug("SetupCEntryAdapter: unable to build MarketContext — skipping")
            return None

        decision_signal = self._setup.check(mc)
        if decision_signal is None:
            return None

        ts = context.timestamp
        if ts is None:
            ts = datetime.now(UTC)

        return _decision_signal_to_orchestrator_signal(
            decision_signal,
            strategy_name=self.name,
            timestamp=ts,
        )
