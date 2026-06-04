"""Adapter classes that wrap Phase-5 Setup A / Setup C as EntrySignalGenerator.

Phase 1.0 of the LLM-primary RL-minimization plan (PR #160 §2.4 Adapter pattern):
  - ``SetupAEntryAdapter`` wraps ``SetupAGapReversion``
  - ``SetupCEntryAdapter`` wraps ``SetupCEventReaction``

Both adapters convert the :class:`shared.strategy.base.EntryContext` available
inside ``TradingOrchestrator`` into the :class:`shared.decision.context.MarketContext`
consumed by the Setup hierarchy, then translate the returned
:class:`shared.decision.signal.Signal` into the :class:`shared.models.signal.Signal`
that the orchestrator pipeline expects.

Phase 1.1 — LLM-aware threshold tuning (1.1-c / 1.1-d)
---------------------------------------------------------
After the underlying Setup fires a candidate signal, both adapters apply
LLM-context adjustments **before** returning the signal to the orchestrator:

* **Direction gating**: signals whose direction is blocked by the current LLM
  regime (``llm_tuning.long_blocked_regimes`` / ``short_blocked_regimes``) are
  dropped silently with a debug log.
* **Risk-score confidence scaling** (Setup A): when ``risk_mode == RISK_OFF``
  *and* ``risk_score > risk_off_threshold`` the candidate's ``confidence`` is
  multiplied by ``risk_off_confidence_multiplier`` (raising the bar to pass the
  orchestrator's minimum-confidence filter).
* **ATR loose-factor** (Setup C): when ``regime == bull_strong_regime`` *and*
  ``risk_mode == RISK_ON`` the candidate's ``confidence`` is boosted by
  ``1 / atr_loose_factor`` (reflecting a more permissive breakout environment).

All three adjustments are skipped when:
  * ``context.market_context`` is ``None`` (LLM context unavailable).
  * ``context.market_context.confidence < llm_tuning.min_context_confidence``
    (low-confidence LLM output — treated as unavailable).
  * ``llm_tuning.enabled`` is ``False`` (opt-out switch).

Phase 1.2 — LLM veto authority (entry-only)
---------------------------------------------
After Phase 1.1 threshold tuning, both adapters apply an additional LLM
**veto** gate before emitting any entry signal.  When the LLM has high
confidence in an overall market signal that directly opposes the candidate
entry direction, the signal is dropped entirely.

* Long candidate + ``overall_signal == veto_long_block_signal`` (default
  ``"STRONG_BEARISH"``) + ``confidence >= veto_min_confidence`` → **veto**.
* Short candidate + ``overall_signal == veto_short_block_signal`` (default
  ``"STRONG_BULLISH"``) + ``confidence >= veto_min_confidence`` → **veto**.

Vetoed signals are:
1. Buffered via :mod:`shared.strategy.llm_veto_logger` for counterfactual
   ClickHouse flush.
2. Sent to the futures Telegram channel so operators have immediate visibility.
3. Returned as ``None`` (signal dropped, no orchestrator emission).

The veto is **ENTRY-ONLY**.  Exit / stop signals never reach this helper.

Both ``llm_tuning.enabled`` (master) AND ``llm_tuning.veto_enabled`` must be
``True`` for the veto to apply.  Operators can disable the veto independently
of threshold/sizing adjustments by setting ``veto_enabled: false``.

Design notes
------------
* Both configs are Pydantic ``ServiceConfigBase`` subclasses so they can be
  loaded from YAML via ``ConfigLoader`` without any extra boilerplate.
* ``LLMTuningConfig`` is a shared typed nested model — no ``dict[str, Any]``
  placeholders remain in production code paths.
* The ``timestamp`` on emitted :class:`shared.models.signal.Signal` objects is
  always a tz-aware UTC ``datetime`` (PR #159 contract).
* The ``valid_until`` metadata preservation from PR #165 remains intact.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import BaseModel, Field

from shared.config.base import ServiceConfigBase
from shared.decision.context import MarketContext, ScheduledEvent
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.gates.adapter_helper import (
    acquire_infra_clients,
    apply_regime_gate,
)
from shared.strategy.gates.regime_gate import GateConfig

if TYPE_CHECKING:
    from shared.models.signal import Signal as OrchestratorSignal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM tuning config
# ---------------------------------------------------------------------------


class LLMTuningConfig(BaseModel):
    """Typed configuration for LLM-aware threshold tuning.

    Shared by both :class:`SetupAEntryConfig` and :class:`SetupCEntryConfig`.
    All fields have sensible defaults so that an empty ``llm_tuning: {}`` YAML
    section still yields a fully-initialised, no-op config (``enabled: false``).

    Args:
        enabled: Master opt-in switch.  When ``False`` all LLM adjustments are
            skipped unconditionally.
        min_context_confidence: Minimum LLM analysis confidence required to
            apply any adjustment.  Below this threshold the LLM output is
            treated as unavailable (same as ``market_context=None``).
        risk_off_threshold: Setup-A only.  ``risk_score`` value above which
            RISK_OFF regime triggers the confidence multiplier.
        risk_off_confidence_multiplier: Setup-A only.  Multiplier applied to
            the candidate signal's confidence under RISK_OFF + high risk_score.
            Values > 1.0 raise the effective bar (fewer signals pass through).
        bull_strong_regime: Setup-C only.  Regime label that triggers the ATR
            loose-factor boost (typically ``"BULL_STRONG"``).
        atr_loose_factor: Setup-C only.  Factor < 1.0 that loosens the
            effective ATR breakout requirement.  The candidate confidence is
            boosted by ``1 / atr_loose_factor`` to reflect the permissive env.
        long_blocked_regimes: Regime labels where long signals are dropped.
        short_blocked_regimes: Regime labels where short signals are dropped
            (default empty — shorts are never blocked out-of-the-box).
    """

    enabled: bool = Field(default=False, description="Master opt-in switch")
    min_context_confidence: float = Field(
        default=0.3,
        description="Minimum LLM confidence required to apply adjustments",
    )
    # Setup A fields
    risk_off_threshold: float = Field(
        default=75.0,
        description="risk_score above which RISK_OFF triggers confidence scaling",
    )
    risk_off_confidence_multiplier: float = Field(
        default=1.3,
        description="Confidence multiplier applied under RISK_OFF + high risk_score",
    )
    # Setup C fields
    bull_strong_regime: str = Field(
        default="BULL_STRONG",
        description="Regime label that triggers ATR loose-factor boost",
    )
    atr_loose_factor: float = Field(
        default=0.8,
        description="ATR loose-factor for bull-strong regime (< 1.0 → looser)",
    )
    # Shared direction-gating lists
    long_blocked_regimes: list[str] = Field(
        default_factory=lambda: ["BEAR_STRONG", "BEAR_MODERATE"],
        description="Regime labels where long signals are dropped",
    )
    short_blocked_regimes: list[str] = Field(
        default_factory=list,
        description="Regime labels where short signals are dropped",
    )
    # Shared confidence floor — applied AFTER any RISK_OFF scaling.  With the
    # default risk_off_confidence_multiplier=1.3 (boost), a non-zero floor only
    # rejects already-low base confidences.  If operators tune the multiplier
    # below 1.0 (penalty mode), this floor enforces a hard drop threshold so
    # the multiplied value cannot collapse signals silently.  Default 0.0
    # means "no floor" (matches Setup A's own [0.5, 1.0] confidence range).
    min_signal_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum confidence floor after LLM scaling. Signals whose adjusted "
            "confidence falls below this are dropped with skip_reason=llm_threshold_unmet."
        ),
    )
    # Phase 1.2 — LLM veto authority fields
    veto_enabled: bool = Field(
        default=True,
        description=(
            "Enable/disable LLM veto independently of threshold/size adjustments. "
            "Requires the master ``enabled`` flag to also be True. "
            "Set to False to exercise Phase 1.1 threshold tuning without veto authority."
        ),
    )
    veto_min_confidence: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum LLM context confidence required to trigger a veto. "
            "Below this threshold the veto is skipped even if the overall_signal "
            "is opposing (treats low-confidence LLM output as unavailable)."
        ),
    )
    veto_long_block_signal: str = Field(
        default="STRONG_BEARISH",
        description=(
            "overall_signal value that triggers a veto for long entry candidates. "
            "Configurable so operators can tune the opposing signal threshold "
            "(e.g. 'BEARISH' for a stricter veto, 'STRONG_BEARISH' for a looser one)."
        ),
    )
    veto_short_block_signal: str = Field(
        default="STRONG_BULLISH",
        description=(
            "overall_signal value that triggers a veto for short entry candidates. "
            "Configurable so operators can tune the opposing signal threshold."
        ),
    )


# ---------------------------------------------------------------------------
# Phase 5 forecast integration configs (default off)
# ---------------------------------------------------------------------------


class SetupAForecastIntegrationConfig(BaseModel):
    """Phase 5 forecast integration for Setup A (default off)."""

    enabled: bool = Field(default=False)
    gap_threshold_vol_mult: float = Field(default=1.0, gt=0.0, le=10.0)
    retracement_buffer_vol_mult: float = Field(default=0.3, gt=0.0, le=10.0)
    max_gap_for_reversion_vol_mult: float = Field(default=4.0, gt=0.0, le=20.0)
    use_event_impact_for_size: bool = Field(default=True)
    min_event_impact_score: int = Field(default=50, ge=0, le=100)


class SetupCForecastIntegrationConfig(BaseModel):
    """Phase 5 forecast integration for Setup C (default off)."""

    enabled: bool = Field(default=False)
    buffer_vol_mult: float = Field(default=0.5, gt=0.0, le=10.0)
    target_vol_mult: float = Field(default=2.5, gt=0.0, le=20.0)
    min_event_impact_score: int = Field(default=60, ge=0, le=100)
    vol_baseline_window_days: int = Field(default=30, ge=5, le=365)
    stale_forecast_fallback: Literal["atr", "skip"] = Field(default="atr")
    inverse_vol_position_size: bool = Field(default=True)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


class SetupAEntryConfig(ServiceConfigBase):
    """Configuration for :class:`SetupAEntryAdapter`.

    All numeric thresholds mirror :class:`~shared.decision.setups.gap_reversion.SetupAConfig`
    so that the adapter can be driven purely from YAML without referencing the
    decision-engine config file.  The ``llm_tuning`` section is a typed
    :class:`LLMTuningConfig` (Phase 1.1).
    """

    _default_config_file: ClassVar[str] = (
        "strategies/futures/setup_a_gap_reversion.yaml"
    )
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
    llm_tuning: LLMTuningConfig = Field(
        default_factory=LLMTuningConfig,
        description="Phase 1.1 LLM-threshold tuning parameters",
    )
    forecast_integration: SetupAForecastIntegrationConfig = Field(
        default_factory=SetupAForecastIntegrationConfig,
        description="Phase 5 forecast integration (default off — gated activation)",
    )


class SetupCEntryConfig(ServiceConfigBase):
    """Configuration for :class:`SetupCEntryAdapter`.

    Mirrors :class:`~shared.decision.setups.event_reaction.SetupCConfig`.
    The ``llm_tuning`` section is a typed :class:`LLMTuningConfig` (Phase 1.1).
    """

    _default_config_file: ClassVar[str] = (
        "strategies/futures/setup_c_event_reaction.yaml"
    )
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
    llm_tuning: LLMTuningConfig = Field(
        default_factory=LLMTuningConfig,
        description="Phase 1.1 LLM-threshold tuning parameters",
    )
    forecast_integration: SetupCForecastIntegrationConfig = Field(
        default_factory=SetupCForecastIntegrationConfig,
        description="Phase 5 forecast integration (default off — gated activation)",
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

    Note: This builds the *decision-engine* ``MarketContext`` (price/OHLCV
    fields).  The *LLM* ``MarketContext`` (regime, risk_score, confidence) is
    accessed separately via ``context.market_context`` — see
    :func:`_read_llm_context`.
    """
    from zoneinfo import ZoneInfo

    KST = ZoneInfo("Asia/Seoul")

    # ------------------------------------------------------------------
    # Fast-path: context.market_context already IS a decision MarketContext
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
    confidence_override: float | None = None,
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
        confidence_override: When provided, replaces ``decision_signal.confidence``
            on the emitted signal (used by LLM threshold scaling in Phase 1.1).

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
    effective_confidence = (
        confidence_override
        if confidence_override is not None
        else decision_signal.confidence
    )

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
        confidence=effective_confidence,
        timestamp=timestamp,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# LLM tuning helpers
# ---------------------------------------------------------------------------


def _get_llm_context(context: EntryContext) -> Any | None:
    """Return the LLM :class:`~shared.llm.market_context.MarketContext` from
    ``context.market_context``, or ``None`` if absent.

    The decision-engine ``MarketContext`` (dataclass from
    ``shared.decision.context``) is never returned here — only the LLM variant
    (from ``shared.llm.market_context``) carries ``regime``/``risk_score``/
    ``confidence`` fields.
    """
    mc = context.market_context
    if mc is None:
        return None
    # Decision-engine MarketContext is a frozen dataclass; LLM MarketContext is
    # a standard dataclass.  We distinguish them by duck-typing the LLM-specific
    # fields rather than importing the class (avoids circular-import risk).
    if (
        hasattr(mc, "regime")
        and hasattr(mc, "risk_score")
        and hasattr(mc, "confidence")
    ):
        return mc
    return None


def _apply_llm_tuning_setup_a(
    decision_signal: Any,
    llm_ctx: Any,
    tuning: LLMTuningConfig,
    min_signal_confidence: float = 0.0,
) -> tuple[float | None, str | None]:
    """Apply Phase 1.1-c LLM threshold adjustments for Setup A.

    Returns a tuple of ``(adjusted_confidence, skip_reason)``.
    When ``skip_reason`` is not ``None`` the caller must drop the signal.
    When ``adjusted_confidence`` is not ``None`` the caller should use it
    instead of ``decision_signal.confidence``.

    Args:
        decision_signal: Raw decision-engine signal.
        llm_ctx: LLM MarketContext (never ``None`` here).
        tuning: Typed LLM tuning configuration.
        min_signal_confidence: Minimum confidence threshold; signal is dropped
            if the adjusted confidence falls below this value.

    Returns:
        (adjusted_confidence, skip_reason)
    """
    regime: str = str(llm_ctx.regime)
    direction: str = str(decision_signal.direction)
    risk_mode_raw = llm_ctx.risk_mode
    # RiskMode is an Enum whose .value is a Korean string (e.g. "위험회피").
    # Normalise to the enum's .name (e.g. "RISK_OFF") for YAML-friendly comparison.
    risk_mode: str = (
        risk_mode_raw.name if hasattr(risk_mode_raw, "name") else str(risk_mode_raw)
    )
    risk_score: float = float(llm_ctx.risk_score)

    # 1. Direction gating
    if direction == "long" and regime in tuning.long_blocked_regimes:
        logger.debug(
            "SetupA LLM gating: long signal dropped — regime=%s is in long_blocked_regimes",
            regime,
        )
        return None, "llm_long_blocked"

    if direction == "short" and regime in tuning.short_blocked_regimes:
        logger.debug(
            "SetupA LLM gating: short signal dropped — regime=%s is in short_blocked_regimes",
            regime,
        )
        return None, "llm_short_blocked"

    # 2. Risk-score confidence scaling
    adjusted_confidence = float(decision_signal.confidence)
    if risk_score > tuning.risk_off_threshold and risk_mode == "RISK_OFF":
        adjusted_confidence = (
            adjusted_confidence * tuning.risk_off_confidence_multiplier
        )
        logger.debug(
            "SetupA LLM tuning: confidence scaled %.3f → %.3f "
            "(risk_score=%.1f > %.1f, RISK_OFF)",
            decision_signal.confidence,
            adjusted_confidence,
            risk_score,
            tuning.risk_off_threshold,
        )
        if adjusted_confidence < min_signal_confidence:
            logger.debug(
                "SetupA LLM tuning: scaled confidence %.3f < min %.3f — signal dropped",
                adjusted_confidence,
                min_signal_confidence,
            )
            return None, "llm_threshold_unmet"

    return adjusted_confidence, None


def _apply_llm_tuning_setup_c(
    decision_signal: Any,
    llm_ctx: Any,
    tuning: LLMTuningConfig,
) -> tuple[float | None, str | None]:
    """Apply Phase 1.1-d LLM threshold adjustments for Setup C.

    Returns a tuple of ``(adjusted_confidence, skip_reason)``.

    Args:
        decision_signal: Raw decision-engine signal.
        llm_ctx: LLM MarketContext (never ``None`` here).
        tuning: Typed LLM tuning configuration.

    Returns:
        (adjusted_confidence, skip_reason)
    """
    regime: str = str(llm_ctx.regime)
    direction: str = str(decision_signal.direction)
    risk_mode_raw = llm_ctx.risk_mode
    # Normalise to .name for YAML-friendly comparison (same as Setup A).
    risk_mode: str = (
        risk_mode_raw.name if hasattr(risk_mode_raw, "name") else str(risk_mode_raw)
    )

    # 1. Direction gating (same logic as Setup A)
    if direction == "long" and regime in tuning.long_blocked_regimes:
        logger.debug(
            "SetupC LLM gating: long signal dropped — regime=%s is in long_blocked_regimes",
            regime,
        )
        return None, "llm_long_blocked"

    if direction == "short" and regime in tuning.short_blocked_regimes:
        logger.debug(
            "SetupC LLM gating: short signal dropped — regime=%s is in short_blocked_regimes",
            regime,
        )
        return None, "llm_short_blocked"

    # 2. ATR loose-factor confidence boost for bull-strong regime
    adjusted_confidence = float(decision_signal.confidence)
    if regime == tuning.bull_strong_regime and risk_mode == "RISK_ON":
        boosted = adjusted_confidence / tuning.atr_loose_factor
        # Cap at 1.0 so confidence stays in [0, 1].
        adjusted_confidence = min(boosted, 1.0)
        logger.debug(
            "SetupC LLM tuning: ATR loose-factor applied — confidence %.3f → %.3f "
            "(regime=%s, RISK_ON, atr_loose_factor=%.2f)",
            decision_signal.confidence,
            adjusted_confidence,
            regime,
            tuning.atr_loose_factor,
        )

    return adjusted_confidence, None


# ---------------------------------------------------------------------------
# Phase 1.2 — LLM veto helper
# ---------------------------------------------------------------------------


def _apply_llm_veto(
    decision_signal: Any,
    llm_ctx: Any,
    tuning: LLMTuningConfig,
    *,
    setup_name: str,
    symbol: str,
    ts: datetime,
) -> tuple[bool, str | None]:
    """Evaluate whether the LLM has high-confidence authority to veto an entry signal.

    This helper is **ENTRY-ONLY**.  Exit and stop signals must never reach it.

    The veto fires when ALL of the following hold:

    1. ``tuning.enabled`` is ``True`` (master switch).
    2. ``tuning.veto_enabled`` is ``True`` (veto sub-switch).
    3. ``llm_ctx.confidence >= tuning.veto_min_confidence``.
    4. ``direction == "long"``  AND ``overall_signal == tuning.veto_long_block_signal``
       OR ``direction == "short"`` AND ``overall_signal == tuning.veto_short_block_signal``.

    When the veto fires the caller should:
    1. Record the event via :func:`shared.strategy.llm_veto_logger.record_veto`.
    2. Send a Telegram alert (futures channel).
    3. Return ``None`` (drop the signal).

    Args:
        decision_signal: Raw decision-engine signal (must have ``.direction``
            and ``.confidence`` attributes).
        llm_ctx: LLM MarketContext (never ``None`` here — caller must guard).
            Must have ``.confidence``, ``.regime``, and ``.overall_signal``
            attributes (duck-typed for test isolation).
        tuning: Typed LLM tuning configuration.
        setup_name: Registry name of the setup (e.g. ``"setup_a_gap_reversion"``).
        symbol: Instrument symbol (for logging / buffer payload).
        ts: Tz-aware UTC timestamp from the orchestrator tick (PR #159 contract).

    Returns:
        ``(should_veto, reason)`` where ``reason`` is ``"llm_veto"`` on veto
        or ``None`` when the signal passes through.
    """
    if not tuning.enabled or not tuning.veto_enabled:
        return False, None

    if float(llm_ctx.confidence) < tuning.veto_min_confidence:
        return False, None

    direction: str = str(decision_signal.direction)
    # MarketSignal is an Enum whose .value is a Korean string (e.g. "강한 하락").
    # Normalise to .name (e.g. "STRONG_BEARISH") so YAML config values like
    # "STRONG_BEARISH" / "STRONG_BULLISH" compare correctly.  Same pattern as
    # the risk_mode normalisation in Phase 1.1 _apply_llm_tuning_setup_a.
    overall_signal_raw = getattr(llm_ctx, "overall_signal", "")
    overall_signal: str = (
        overall_signal_raw.name
        if hasattr(overall_signal_raw, "name")
        else str(overall_signal_raw)
    )
    regime: str = str(llm_ctx.regime)

    veto_triggered = (
        direction == "long" and overall_signal == tuning.veto_long_block_signal
    ) or (direction == "short" and overall_signal == tuning.veto_short_block_signal)

    if not veto_triggered:
        return False, None

    logger.info(
        "LLM veto: %s %s signal dropped — overall_signal=%s confidence=%.3f "
        "veto_min_confidence=%.3f setup=%s symbol=%s",
        direction,
        setup_name,
        overall_signal,
        float(llm_ctx.confidence),
        tuning.veto_min_confidence,
        setup_name,
        symbol,
    )

    # Ensure ts is tz-aware UTC (PR #159 contract).
    from datetime import UTC

    ts = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)

    # Buffer the veto event for counterfactual ClickHouse flush (follow-up PR).
    from shared.strategy.llm_veto_logger import record_veto

    record_veto(
        {
            "ts": ts,
            "symbol": symbol,
            "direction": direction,
            "regime": regime,
            "overall_signal": overall_signal,
            "confidence": float(llm_ctx.confidence),
            "setup": setup_name,
        }
    )

    # Send Telegram alert (futures channel) — fire-and-forget; failures are
    # logged internally by the notifier and must not block the hot path.
    _send_veto_alert_background(
        symbol=symbol,
        direction=direction,
        regime=regime,
        overall_signal=overall_signal,
        confidence=float(llm_ctx.confidence),
        setup_name=setup_name,
        ts=ts,
    )

    return True, "llm_veto"


def _send_veto_alert_background(
    *,
    symbol: str,
    direction: str,
    regime: str,
    overall_signal: str,
    confidence: float,
    setup_name: str,
    ts: datetime,
) -> None:
    """Schedule a Telegram veto alert without blocking the caller.

    Creates an asyncio task if a running event loop is available; otherwise
    logs only.  The alert is sent to the ``futures`` channel so operators have
    immediate visibility when the LLM blocks an otherwise-tradable signal.

    Args:
        symbol: Instrument symbol.
        direction: Candidate entry direction (``"long"`` or ``"short"``).
        regime: LLM market regime string.
        overall_signal: The opposing overall_signal that triggered the veto.
        confidence: LLM context confidence at veto time.
        setup_name: Registry name of the setup.
        ts: Tz-aware UTC datetime of the vetoed tick.
    """
    import asyncio

    from shared.notification.telegram import notifier_for_domain

    notifier = notifier_for_domain("futures")
    if notifier is None:
        logger.debug("llm_veto Telegram alert skipped — futures notifier unavailable")
        return

    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S UTC")
    msg = (
        f"<b>LLM Veto</b> — entry blocked\n"
        f"Setup: {setup_name}\n"
        f"Symbol: {symbol}\n"
        f"Direction: {direction}\n"
        f"Regime: {regime}\n"
        f"Overall signal: {overall_signal}\n"
        f"LLM confidence: {confidence:.2f}\n"
        f"Time: {ts_str}"
    )

    async def _send() -> None:
        try:
            await notifier.send_message(msg, is_critical=True)
        except Exception as exc:
            logger.warning("llm_veto Telegram alert failed: %s", exc)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send())
    except RuntimeError:
        # No running event loop (e.g. during tests or synchronous callers).
        logger.debug(
            "llm_veto Telegram alert not scheduled — no running event loop; "
            "message: %s",
            msg,
        )


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


class SetupAEntryAdapter(EntrySignalGenerator[SetupAEntryConfig]):
    """EntrySignalGenerator adapter wrapping :class:`SetupAGapReversion`.

    Bridges the ``TradingOrchestrator`` entry pipeline to the Phase-5 Setup A
    gap-reversion logic without duplicating any threshold or business logic.

    Registered as ``"setup_a_gap_reversion"`` in :func:`register_builtin_components`.

    Phase 1.1-c — LLM-aware threshold tuning
    -----------------------------------------
    After :meth:`SetupAGapReversion.check` returns a candidate signal the
    adapter optionally applies:

    1. **Direction gating** — drops the signal when the LLM regime is in
       ``llm_tuning.long_blocked_regimes`` / ``short_blocked_regimes``.
    2. **Risk-score confidence scaling** — multiplies the signal's confidence
       by ``llm_tuning.risk_off_confidence_multiplier`` under
       ``RISK_OFF + risk_score > risk_off_threshold``.  The multiplier > 1.0
       raises the bar; signals whose adjusted confidence falls below the setup's
       min-confidence gate are dropped.

    Adjustments are skipped when ``llm_tuning.enabled`` is ``False``, when
    ``context.market_context`` is ``None``, or when its ``confidence`` field
    is below ``llm_tuning.min_context_confidence``.
    """

    CONFIG_CLASS = SetupAEntryConfig

    def __init__(
        self,
        config: SetupAEntryConfig,
        forecast_client: Any | None = None,
        gate_cfg: GateConfig | None = None,  # P2-③ T5
    ) -> None:
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
        # Phase 5 forecast integration — optional ForecastClient (default off).
        # When provided AND config.forecast_integration.enabled is True, the
        # adapter consumes 15-min vol forecast + event impact scores to derive
        # gap threshold + reversion range dynamically and scale position size.
        self._forecast_client = forecast_client
        self._gate_cfg = gate_cfg  # P2-③ T5

    def _derive_gap_threshold_pct(self, forecast: Any | None) -> float:
        """Return the gap entry threshold in percent units.

        When forecast integration is enabled and a fresh
        :class:`~shared.forecasting.models.VolForecast` is supplied, the
        threshold is scaled by the forecast's annualized vol percent:
        ``gap_threshold_vol_mult × forecast.forecast_pct``.

        Otherwise fall back to the existing config ``min_kr_gap_pct`` (Korean
        open gap vs prev close — the primary gap input for Setup A).
        """
        fi = self.config.forecast_integration
        if fi.enabled and forecast is not None:
            return fi.gap_threshold_vol_mult * forecast.forecast_pct
        return self.config.min_kr_gap_pct

    def _gap_within_reversion_range(self, gap_pct: float, forecast: Any | None) -> bool:
        """Return True if ``gap_pct`` is within the reversion-acceptable range.

        When forecast integration is enabled and a fresh forecast is supplied,
        reject gaps larger than ``max_gap_for_reversion_vol_mult ×
        forecast.forecast_pct`` (extreme gaps are unlikely to mean-revert and
        should defer to event-driven setups instead).

        When forecast integration is off or no forecast is available, return
        True (let the existing retrace_min/max gating handle the call).
        """
        fi = self.config.forecast_integration
        if not fi.enabled or forecast is None:
            return True
        max_pct = fi.max_gap_for_reversion_vol_mult * forecast.forecast_pct
        return gap_pct <= max_pct

    def _compute_event_size_mult(self, event_score: Any | None) -> float:
        """Return a position-size multiplier in (0, 1] based on event impact.

        Strong events (high ``impact_score``) imply elevated overreaction risk,
        so size is reduced: ``mult = 1 / (1 + impact_score / 100)``.

        Returns 1.0 (no scaling) when forecast integration is off, when the
        ``use_event_impact_for_size`` toggle is off, or when no event score is
        supplied.
        """
        fi = self.config.forecast_integration
        if not fi.enabled or not fi.use_event_impact_for_size:
            return 1.0
        if event_score is None:
            return 1.0
        return 1.0 / (1.0 + event_score.impact_score / 100.0)

    def _validate_config(self) -> None:
        """Validate config fields.

        Raises:
            AssertionError: When any numeric param is out of valid range.
        """
        assert (
            0 <= self.config.valid_minutes_min <= self.config.valid_minutes_max
        ), "valid_minutes_min must be <= valid_minutes_max"
        assert self.config.min_sp500_gap_pct >= 0.0, "min_sp500_gap_pct must be >= 0"
        assert self.config.min_kr_gap_pct >= 0.0, "min_kr_gap_pct must be >= 0"
        assert (
            0.0 <= self.config.retrace_min <= self.config.retrace_max <= 1.0
        ), "retrace_min/max must be in [0,1] and retrace_min <= retrace_max"
        assert self.config.stop_atr_mult > 0.0, "stop_atr_mult must be > 0"
        assert (
            0.0 < self.config.target_gap_fill_ratio <= 1.0
        ), "target_gap_fill_ratio must be in (0, 1]"
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

        After the underlying setup fires, Phase 1.1-c LLM-threshold tuning is
        applied (direction gating + risk-score confidence scaling).

        Args:
            context: Orchestrator entry context for the current tick.

        Returns:
            A tz-aware UTC :class:`shared.models.signal.Signal` when Setup A
            fires and passes LLM tuning, or ``None`` when any precondition or
            LLM gate fails.
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

        # ------------------------------------------------------------------
        # Phase 1.1-c — LLM threshold adjustments
        # ------------------------------------------------------------------
        confidence_override: float | None = None
        tuning = self.config.llm_tuning

        if not tuning.enabled:
            pass  # LLM tuning disabled — use default Setup A behaviour
        else:
            llm_ctx = _get_llm_context(context)
            if llm_ctx is None:
                logger.debug(
                    "SetupAEntryAdapter: market_context is None — skipping LLM tuning"
                )
            elif float(llm_ctx.confidence) < tuning.min_context_confidence:
                logger.info(
                    "SetupAEntryAdapter: LLM confidence %.3f < min %.3f — skipping LLM tuning",
                    float(llm_ctx.confidence),
                    tuning.min_context_confidence,
                )
            else:
                # Phase 1.1-c: direction gating + risk-score confidence scaling.
                adjusted_confidence, skip_reason = _apply_llm_tuning_setup_a(
                    decision_signal=decision_signal,
                    llm_ctx=llm_ctx,
                    tuning=tuning,
                    min_signal_confidence=tuning.min_signal_confidence,
                )
                if skip_reason is not None:
                    return None
                confidence_override = adjusted_confidence

                # Phase 1.2: LLM veto authority — applied AFTER threshold tuning,
                # BEFORE signal emission.  Entry signals only; never veto exits.
                symbol = str(
                    (context.market_data or {}).get(
                        "code",
                        (context.market_data or {}).get("symbol", ""),
                    )
                )
                should_veto, _veto_reason = _apply_llm_veto(
                    decision_signal=decision_signal,
                    llm_ctx=llm_ctx,
                    tuning=tuning,
                    setup_name=self.name,
                    symbol=symbol,
                    ts=ts,
                )
                if should_veto:
                    return None

        # === P2-③ T5: RegimeGate check (after LLM veto, before Signal return) ===
        if self._gate_cfg is not None:
            _redis, _ch = acquire_infra_clients()
            if _redis is not None and _ch is not None:
                blocked = apply_regime_gate(
                    gate_cfg=self._gate_cfg,
                    decision_signal=decision_signal,
                    context=context,
                    strategy_name=self.name,
                    redis=_redis,
                    ch_client=_ch,
                )
                if blocked:
                    return None

        return _decision_signal_to_orchestrator_signal(
            decision_signal,
            strategy_name=self.name,
            timestamp=ts,
            confidence_override=confidence_override,
        )


class SetupCEntryAdapter(EntrySignalGenerator[SetupCEntryConfig]):
    """EntrySignalGenerator adapter wrapping :class:`SetupCEventReaction`.

    Bridges the ``TradingOrchestrator`` entry pipeline to the Phase-5 Setup C
    event-reaction logic.

    Registered as ``"setup_c_event_reaction"`` in :func:`register_builtin_components`.

    Phase 1.1-d — LLM-aware threshold tuning
    -----------------------------------------
    After :meth:`SetupCEventReaction.check` returns a candidate signal the
    adapter optionally applies:

    1. **Direction gating** — drops the signal when the LLM regime is in
       ``llm_tuning.long_blocked_regimes`` / ``short_blocked_regimes``.
    2. **ATR loose-factor boost** — when ``regime == bull_strong_regime`` *and*
       ``risk_mode == RISK_ON`` the signal's confidence is boosted by
       ``1 / atr_loose_factor``, reflecting a more permissive breakout
       environment (capped at 1.0).

    Adjustments are skipped when ``llm_tuning.enabled`` is ``False``, when
    ``context.market_context`` is ``None``, or when its ``confidence`` field
    is below ``llm_tuning.min_context_confidence``.

    Two-level gating
    ----------------
    There are TWO independent enable flags:

    * ``strategy.enabled`` (outer, default ``false``) — gates the entire Setup
      C strategy.  Operator flips to ``true`` only after Gate 1-3
      paper-rollout validation per the Phase 5 verification runbook.
    * ``llm_tuning.enabled`` (inner, default ``true`` in YAML, ``false`` in the
      Pydantic class default) — gates only the LLM threshold adjustments
      *within* Setup C.  When the outer ``strategy.enabled`` is still
      ``false``, the inner flag is moot.  Once operators flip the outer
      flag, the inner flag's YAML value (``true``) immediately arms LLM
      tuning; toggle it to ``false`` to exercise Setup C without LLM
      influence.
    """

    CONFIG_CLASS = SetupCEntryConfig

    def __init__(
        self,
        config: SetupCEntryConfig,
        forecast_client: Any | None = None,
        gate_cfg: GateConfig | None = None,  # P2-③ T5
    ) -> None:
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
        # Phase 5 forecast integration — optional ForecastClient (default off).
        # When provided AND config.forecast_integration.enabled is True, the
        # adapter consumes 15-min vol forecast + event impact scores to derive
        # breakout buffer/target dynamically.
        self._forecast_client = forecast_client
        self._gate_cfg = gate_cfg  # P2-③ T5

    def _derive_thresholds(
        self, forecast: Any | None, atr: float
    ) -> tuple[float, float]:
        """Return ``(breakout_buffer, target_distance)`` in price units.

        When ``forecast_integration.enabled`` is True and a fresh
        :class:`~shared.forecasting.models.VolForecast` is supplied, derive
        thresholds from ``forecast.forecast_atr_equivalent`` (15-min vol ATR).
        Otherwise fall back to the legacy ATR-based config
        (``breakout_buffer_atr_mult`` × atr, ``target_atr_mult`` × atr).
        """
        fi = self.config.forecast_integration
        if fi.enabled and forecast is not None:
            buffer = fi.buffer_vol_mult * forecast.forecast_atr_equivalent
            target = fi.target_vol_mult * forecast.forecast_atr_equivalent
            return (buffer, target)
        return (
            atr * self.config.breakout_buffer_atr_mult,
            atr * self.config.target_atr_mult,
        )

    def _event_passes_filter(self, event_score: Any | None) -> bool:
        """Return ``True`` if ``event_score`` meets the impact threshold.

        Returns ``True`` when:
        * ``forecast_integration.enabled`` is False (legacy tier filter
          remains the gate); OR
        * ``event_score`` is ``None`` (let the legacy tier filter decide); OR
        * ``event_score.impact_score >= min_event_impact_score``.
        """
        fi = self.config.forecast_integration
        if not fi.enabled or event_score is None:
            return True
        return event_score.impact_score >= fi.min_event_impact_score

    def _validate_config(self) -> None:
        """Validate config fields.

        Raises:
            AssertionError: When any numeric param is out of valid range.
        """
        assert self.config.window_minutes > 0, "window_minutes must be > 0"
        assert (
            self.config.breakout_buffer_atr_mult > 0.0
        ), "breakout_buffer_atr_mult must be > 0"
        assert self.config.target_atr_mult > 0.0, "target_atr_mult must be > 0"
        assert self.config.signal_ttl_minutes > 0, "signal_ttl_minutes must be > 0"
        assert (
            1 <= self.config.min_impact_tier <= 3
        ), "min_impact_tier must be between 1 and 3"

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

        After the underlying setup fires, Phase 1.1-d LLM-threshold tuning is
        applied (direction gating + ATR loose-factor confidence boost).

        Args:
            context: Orchestrator entry context for the current tick.

        Returns:
            A tz-aware UTC :class:`shared.models.signal.Signal` when Setup C
            fires and passes LLM tuning, or ``None`` when any precondition or
            LLM gate fails.
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

        # ------------------------------------------------------------------
        # Phase 1.1-d — LLM threshold adjustments
        # ------------------------------------------------------------------
        confidence_override: float | None = None
        tuning = self.config.llm_tuning

        if not tuning.enabled:
            pass  # LLM tuning disabled — use default Setup C behaviour
        else:
            llm_ctx = _get_llm_context(context)
            if llm_ctx is None:
                logger.debug(
                    "SetupCEntryAdapter: market_context is None — skipping LLM tuning"
                )
            elif float(llm_ctx.confidence) < tuning.min_context_confidence:
                logger.info(
                    "SetupCEntryAdapter: LLM confidence %.3f < min %.3f — skipping LLM tuning",
                    float(llm_ctx.confidence),
                    tuning.min_context_confidence,
                )
            else:
                # Phase 1.1-d: direction gating + ATR loose-factor confidence boost.
                adjusted_confidence, skip_reason = _apply_llm_tuning_setup_c(
                    decision_signal=decision_signal,
                    llm_ctx=llm_ctx,
                    tuning=tuning,
                )
                if skip_reason is not None:
                    return None
                confidence_override = adjusted_confidence

                # Phase 1.2: LLM veto authority — applied AFTER threshold tuning,
                # BEFORE signal emission.  Entry signals only; never veto exits.
                symbol = str(
                    (context.market_data or {}).get(
                        "code",
                        (context.market_data or {}).get("symbol", ""),
                    )
                )
                should_veto, _veto_reason = _apply_llm_veto(
                    decision_signal=decision_signal,
                    llm_ctx=llm_ctx,
                    tuning=tuning,
                    setup_name=self.name,
                    symbol=symbol,
                    ts=ts,
                )
                if should_veto:
                    return None

        # === P2-③ T5: RegimeGate check (after LLM veto, before Signal return) ===
        if self._gate_cfg is not None:
            _redis, _ch = acquire_infra_clients()
            if _redis is not None and _ch is not None:
                blocked = apply_regime_gate(
                    gate_cfg=self._gate_cfg,
                    decision_signal=decision_signal,
                    context=context,
                    strategy_name=self.name,
                    redis=_redis,
                    ch_client=_ch,
                )
                if blocked:
                    return None

        return _decision_signal_to_orchestrator_signal(
            decision_signal,
            strategy_name=self.name,
            timestamp=ts,
            confidence_override=confidence_override,
        )
