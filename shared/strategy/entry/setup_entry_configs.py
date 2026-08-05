"""Configuration models for futures setup entry adapters."""

from typing import ClassVar, Literal

from pydantic import BaseModel, Field

from shared.config.base import ServiceConfigBase

__all__ = [
    "LLMTuningConfig",
    "SetupAForecastIntegrationConfig",
    "SetupCForecastIntegrationConfig",
    "SetupAEntryConfig",
    "SetupDEntryConfig",
    "SetupCEntryConfig",
]


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
        risk_off_confidence_multiplier: Setup-A only.  Applied as a
            multiplication on the candidate signal's confidence under RISK_OFF +
            high risk_score, so values < 1.0 penalise (lower) it and values
            > 1.0 raise it.  The default 1.0 is NEUTRAL: the RISK_OFF branch
            still runs and still records the ``llm_risk_off_*`` telemetry, but
            the emitted confidence equals the base, so an operator opts into a
            boost (> 1.0) or a penalty (< 1.0) explicitly.  The notes below
            describe what moving off 1.0 buys.
            The product is capped at 1.0 to honour the
            documented ``Signal.confidence`` range — ``shared/models/signal.py``
            documents ``확신도 (0.0 ~ 1.0)`` but declares a plain dataclass field
            with no validator, so nothing downstream would reject an
            out-of-range value.
            The field is bounded ``ge=0.0`` because ``min(scaled, 1.0)`` guards
            only the ceiling: a negative operator value would otherwise emit a
            negative confidence, still outside the documented range.  No ``le=``
            is imposed — the runtime cap already bounds what is emitted, so an
            upper bound would only restrict operator experimentation without
            buying any range safety.
            Raising confidence makes admission easier IN GENERAL, but at the
            current configuration it does not change whether a Setup-A signal is
            admitted.  Setup A's base confidence is in [0.5, 1.0] by
            construction (:mod:`shared.decision.setups.gap_reversion`: ``0.5 +
            gap_strength(<=0.3) + retrace_centrality(<=0.2)``) — that is the
            THEORETICAL range.  Under the LIVE gate
            (``min_sp500_gap_pct: 0.30``) ``gap_strength`` is at least
            ``0.30 / 1.5 = 0.20``, so the LIVE base range is the narrower
            [0.70, 1.00].  Either way the downstream floor
            ``StrategyManagerConfig.min_confidence`` is 0.3 and
            ``min_signal_confidence`` below is 0.0, so the base clears both
            floors with or without the multiplier.
            What a value above 1.0 does change is PRIORITY ORDERING: entry
            contention is ranked by descending confidence under
            ``max_positions``, so a boosted Setup-A candidate can displace a
            competing signal.
            ORDERING CONSEQUENCE OF THE 1.0 CAP (reachable only when tuned
            above 1.0): capping collapses the whole previously-ordered band
            [1.0, multiplier] onto the single value 1.0, so
            ties fall through to the next key of
            ``services/trading/entry_runtime.py::entry_signal_priority`` —
            ``(priority, -confidence, strategy, code)``.  Setup A sets no
            ``entry_priority``, so a tie resolves by STRATEGY NAME.  Today
            ``"setup_a_gap_reversion"`` sorts before ``setup_c_event_reaction``
            and ``setup_d_vwap_reversion``, so nothing changes — accidentally.
            Enabling a futures strategy whose registry name sorts earlier
            (``bb_reversion_15m``, ``llm_directed_indicator``,
            ``macd_ema_crossover_15m``, ``momentum_breakout_futures`` — all
            currently ``enabled: false``) would hand priority to it where the
            uncapped Setup A won outright.  Set an explicit ``entry_priority``
            if that ordering must be guaranteed rather than inherited from
            alphabetical luck.
            OPERATOR JUDGMENT 2026-08-05 (SETTLED): the default and the live
            futures value are both 1.0.  Whether a RISK_OFF read should raise
            Setup A's priority at all was decided in the negative FOR NOW — not
            because a boost is wrong in principle, but because no evidence ever
            supported one.  A future re-introduction is legitimate once the
            ``llm_risk_off_*`` telemetry (commit ``d0ae81cb``) has accumulated
            enough RISK_OFF firings to argue from; it must be a deliberate
            operator choice, not an inherited value.
            History: the 1.3 default landed in ``274d55a7`` / PR #167
            (2026-05-07) alongside an inverted rationale ("values > 1.0 raise
            the effective bar"); the same-day review ``d2caddb4`` correctly
            identified 1.3 as a boost and wired ``min_signal_confidence``, but
            left both the value and the false docstring in place.  The false
            docstring stood until ``21550f4b`` (2026-08-05) corrected it and
            raised the operator flag; the cap is the follow-up to that
            commit, and the 2026-08-05 judgment above retired the flag by
            neutralising the value.  (The PR-branch-local hash ``6a66df1e``
            names the same work
            but is reachable only from ``origin/feat/phase-1-1-setup-llm-tuning``
            — cite the mainline ``274d55a7`` so the reference survives branch
            pruning.)
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
        default=1.0,
        ge=0.0,
        description=(
            "Confidence multiplier applied under RISK_OFF + high risk_score. "
            "Default 1.0 is neutral (no-op); > 1.0 boosts, < 1.0 penalises."
        ),
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
    # neutral default risk_off_confidence_multiplier=1.0 the scaling is a no-op,
    # so a non-zero floor here rejects purely on the base confidence; the same
    # holds for any boost (> 1.0), which only ever raises it.  If operators tune
    # the multiplier below 1.0 (penalty mode), this floor enforces a hard drop
    # threshold so the multiplied value cannot collapse signals silently.  Default 0.0
    # means "no floor" — below Setup A's theoretical [0.5, 1.0] base range, and
    # so also below its live [0.70, 1.00] range under min_sp500_gap_pct: 0.30.
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
    daily_bias_filter_enabled: bool = Field(
        default=True,
        description="Gate entries on daily directional bias (LLM regime-guided)",
    )
    daily_bias_min_confidence: float = Field(
        default=0.5,
        description="Minimum LLM confidence required to compute a non-flat daily bias",
    )
    daily_bias_refresh_minutes: int = Field(
        default=60,
        description=(
            "I2: minutes before a stale flat bias is re-evaluated. "
            "A flat bias older than this is recomputed on the next call; "
            "non-flat (long/short) biases remain sticky all day. "
            "Default 60 minutes."
        ),
    )


class SetupDEntryConfig(ServiceConfigBase):
    """Configuration for :class:`SetupDEntryAdapter`.

    Mirrors :class:`~shared.decision.setups.vwap_reversion.SetupDConfig` field
    names 1:1 so the adapter is driven purely from
    ``config/strategies/futures/setup_d_vwap_reversion.yaml`` without referencing
    the decision-engine config file. Setup D is a self-contained indicator setup
    (no LLM-driven signal generation — the entry signal itself is produced purely
    from ATR/VWAP mechanics), so this config has no ``llm_tuning`` /
    ``forecast_integration`` / ``daily_bias`` sections for signal shaping. The
    regime direction block below is the one exception: it reads the runtime
    regime label *after* the setup fires to post-filter signals whose direction
    conflicts with a strong regime (``long_blocked_regimes`` /
    ``short_blocked_regimes``). Empty lists (defaults) disable the block entirely.
    """

    _default_config_file: ClassVar[str] = (
        "strategies/futures/setup_d_vwap_reversion.yaml"
    )
    _default_section: ClassVar[str] = "strategy.entry.params"

    enabled: bool = Field(default=True, description="Enable/disable the adapter")
    valid_minutes_min: int = Field(
        default=15, description="Earliest minutes after open to fire (skip auction)"
    )
    no_entry_after_minutes_since_open: int = Field(
        default=345,
        description="No new entries after this many minutes since 09:00 KST (345=14:45)",
    )
    min_atr_ratio: float = Field(
        default=0.9,
        description="High-vol gate: atr_14 >= min_atr_ratio × causal vol reference",
    )
    vol_window_bars: int = Field(
        default=780,
        description="Causal trailing window (bars) for the self-computed vol reference",
    )
    vol_warmup_bars: int = Field(
        default=120,
        description="Min past-ATR observations before the high-vol gate activates",
    )
    vol_percentile: float = Field(
        default=90.0,
        description="Percentile of the causal ATR window used as the vol reference",
    )
    extreme_atr_mult: float = Field(
        default=1.8,
        description="Fade trigger: |(price-vwap)/atr_14| must reach this many ATRs",
    )
    stall_buffer_atr_mult: float = Field(
        default=1.0,
        description="Trend-day guard: spike must be within this many ATRs of 15-min extreme",
    )
    stop_atr_mult: float = Field(
        default=1.5, description="Hard stop = entry ± stop_atr_mult × ATR14"
    )
    min_reward_risk: float = Field(
        default=1.0, description="Floor on reward/risk of the VWAP-revert target"
    )
    signal_ttl_minutes: int = Field(
        default=10, description="Signal validity window in minutes"
    )
    range_window_bars: int = Field(
        default=15,
        description="Prior closes used for the self-computed recent-range (stall guard)",
    )
    range_warmup_bars: int = Field(
        default=5,
        description="Min prior closes before the stall guard activates",
    )
    extension_conf_scale: float = Field(
        default=0.3, description="Confidence slope per extra ATR of extension"
    )
    vol_conf_scale: float = Field(
        default=0.3, description="Confidence slope per unit of vol_ratio above gate"
    )
    min_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum signal confidence gate (0.0 = disabled). Mirrors SetupDConfig.",
    )
    reversal_confirm_enabled: bool = Field(
        default=False,
        description="Require price to start reverting toward VWAP before firing.",
    )
    reversal_confirm_atr_mult: float = Field(
        default=0.2,
        ge=0.0,
        description="Minimum abs(z) improvement versus the prior close, in ATR units.",
    )
    reversal_confirm_requires_price_turn: bool = Field(
        default=True,
        description="Require the latest close to move back toward VWAP.",
    )
    trend_filter_enabled: bool = Field(
        default=False,
        description=(
            "Session-VWAP-slope trend gate: block a counter-trend fade on a "
            "strongly trending session unless the stretch is climactic. Ships "
            "off. Mirrors SetupDConfig."
        ),
    )
    trend_window_bars: int = Field(
        default=30,
        description="Trailing window (bars) of session VWAP for the trend score.",
    )
    trend_warmup_bars: int = Field(
        default=10,
        description="Min VWAP observations before the trend gate activates.",
    )
    trend_block_threshold: float = Field(
        default=1.0,
        ge=0.0,
        description="Block only when abs(trend_score) >= this many ATRs of drift.",
    )
    against_trend_extreme_atr_mult: float = Field(
        default=2.6,
        description=(
            "Climax override: allow the counter-trend fade when abs(z) >= this "
            "many ATRs (clamped to >= extreme_atr_mult at runtime)."
        ),
    )
    long_blocked_regimes: list[str] = Field(
        default_factory=list,
        description=(
            "LLM regime labels where LONG signals are suppressed "
            '(e.g. ["BEAR_STRONG"]). Empty list disables the block.'
        ),
    )
    short_blocked_regimes: list[str] = Field(
        default_factory=list,
        description=(
            "LLM regime labels where SHORT signals are suppressed "
            '(e.g. ["BULL_STRONG"]). Empty list disables the block.'
        ),
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
    stop_buffer_atr_mult: float = Field(
        default=0.5,
        description="Extra ATR cushion beyond the opposite 15-min range edge for the stop",
    )
    no_entry_after_minutes_since_open: int = Field(
        default=360,
        description="No new entries after this many minutes since 09:00 KST (360=15:00)",
    )
    llm_tuning: LLMTuningConfig = Field(
        default_factory=LLMTuningConfig,
        description="Phase 1.1 LLM-threshold tuning parameters",
    )
    forecast_integration: SetupCForecastIntegrationConfig = Field(
        default_factory=SetupCForecastIntegrationConfig,
        description="Phase 5 forecast integration (default off — gated activation)",
    )
    daily_bias_filter_enabled: bool = Field(
        default=True,
        description="Gate entries on daily directional bias (LLM regime-guided)",
    )
    daily_bias_min_confidence: float = Field(
        default=0.5,
        description="Minimum LLM confidence required to compute a non-flat daily bias",
    )
    daily_bias_refresh_minutes: int = Field(
        default=60,
        description=(
            "I2: minutes before a stale flat bias is re-evaluated. "
            "A flat bias older than this is recomputed on the next call; "
            "non-flat (long/short) biases remain sticky all day. "
            "Default 60 minutes."
        ),
    )
