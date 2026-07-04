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
   analysis.
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
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from shared.decision.daily_bias import DailyBiasProvider
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.entry import setup_eval_publisher as _setup_eval_publisher
from shared.strategy.entry.setup_context_builder import build_setup_market_context
from shared.strategy.entry.setup_entry_configs import (
    LLMTuningConfig,
    SetupAEntryConfig,
    SetupAForecastIntegrationConfig,
    SetupCEntryConfig,
    SetupCForecastIntegrationConfig,
    SetupDEntryConfig,
)
from shared.strategy.entry.setup_llm_gate import (
    apply_llm_tuning_setup_a,
    apply_llm_tuning_setup_c,
    apply_llm_veto,
    get_llm_context,
    normalise_regime_label,
    resolve_regime_label,
    send_veto_alert_background,
)
from shared.strategy.entry.setup_signal_mapper import (
    decision_signal_to_orchestrator_signal,
)
from shared.strategy.gates.adapter_helper import (
    acquire_infra_clients,
    apply_regime_gate,
)
from shared.strategy.gates.regime_gate import GateConfig
from shared.strategy.market_time import now_kst

if TYPE_CHECKING:
    from shared.models.signal import Signal as OrchestratorSignal

logger = logging.getLogger(__name__)

__all__ = [
    "LLMTuningConfig",
    "SetupAEntryAdapter",
    "SetupAEntryConfig",
    "SetupAForecastIntegrationConfig",
    "SetupCEntryAdapter",
    "SetupCEntryConfig",
    "SetupCForecastIntegrationConfig",
    "SetupDEntryAdapter",
    "SetupDEntryConfig",
]

# ---------------------------------------------------------------------------
# Config models (compatibility re-exports)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Extracted helper compatibility aliases
# ---------------------------------------------------------------------------

_build_market_context = build_setup_market_context
_decision_signal_to_orchestrator_signal = decision_signal_to_orchestrator_signal

# ---------------------------------------------------------------------------
# LLM helper compatibility aliases
# ---------------------------------------------------------------------------

_get_llm_context = get_llm_context
_normalise_regime_label = normalise_regime_label
_resolve_regime_label = resolve_regime_label
_apply_llm_tuning_setup_a = apply_llm_tuning_setup_a
_apply_llm_tuning_setup_c = apply_llm_tuning_setup_c
_apply_llm_veto = apply_llm_veto
_send_veto_alert_background = send_veto_alert_background

# ---------------------------------------------------------------------------
# Setup-eval publisher compatibility wrappers
# ---------------------------------------------------------------------------

SETUP_EVAL_KEY = _setup_eval_publisher.SETUP_EVAL_KEY
SETUP_EVAL_HISTORY_KEY_PREFIX = _setup_eval_publisher.SETUP_EVAL_HISTORY_KEY_PREFIX
SETUP_EVAL_HISTORY_TTL_SECONDS = _setup_eval_publisher.SETUP_EVAL_HISTORY_TTL_SECONDS
SETUP_EVAL_HISTORY_ENABLED = _setup_eval_publisher.SETUP_EVAL_HISTORY_ENABLED
_last_eval_log = _setup_eval_publisher._last_eval_log
_history_state = _setup_eval_publisher._history_state
_is_in_window_eval = _setup_eval_publisher.is_in_window_eval
_append_setup_eval_history = _setup_eval_publisher.append_setup_eval_history


def _publish_setup_eval(name: str, outcome: str, reason: str) -> None:
    """Compatibility wrapper for setup evaluation publishing.

    Existing tests and operators monkeypatch this module's infrastructure hooks,
    so pass those hooks into the extracted publisher instead of calling it as a
    direct alias.
    """
    _setup_eval_publisher.SETUP_EVAL_HISTORY_KEY_PREFIX = os.environ.get(
        "SETUP_EVAL_HISTORY_KEY_PREFIX",
        _setup_eval_publisher.SETUP_EVAL_HISTORY_KEY_PREFIX,
    )
    _setup_eval_publisher.SETUP_EVAL_HISTORY_TTL_SECONDS = int(
        os.environ.get(
            "SETUP_EVAL_HISTORY_TTL_SECONDS",
            str(_setup_eval_publisher.SETUP_EVAL_HISTORY_TTL_SECONDS),
        )
    )
    _setup_eval_publisher.SETUP_EVAL_HISTORY_ENABLED = os.environ.get(
        "SETUP_EVAL_HISTORY_ENABLED", "true"
    ).strip().lower() not in {"0", "false", "no", "off"}
    globals()[
        "SETUP_EVAL_HISTORY_KEY_PREFIX"
    ] = _setup_eval_publisher.SETUP_EVAL_HISTORY_KEY_PREFIX
    globals()[
        "SETUP_EVAL_HISTORY_TTL_SECONDS"
    ] = _setup_eval_publisher.SETUP_EVAL_HISTORY_TTL_SECONDS
    globals()[
        "SETUP_EVAL_HISTORY_ENABLED"
    ] = _setup_eval_publisher.SETUP_EVAL_HISTORY_ENABLED
    _setup_eval_publisher.publish_setup_eval(
        name,
        outcome,
        reason,
        acquire_clients=acquire_infra_clients,
        now_fn=now_kst,
        log=logger,
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
        # Daily directional bias provider — gates on LLM-derived long/short regime.
        self._daily_bias_provider = DailyBiasProvider(
            bias_min_confidence=config.daily_bias_min_confidence,
            non_long_regimes=list(config.llm_tuning.long_blocked_regimes),
            bias_refresh_minutes=config.daily_bias_refresh_minutes,
        )

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
            _publish_setup_eval(self.name, "reject", "no_market_context")
            return None

        decision_signal = self._setup.check(mc)
        if decision_signal is None:
            _publish_setup_eval(
                self.name, "reject", self._setup.last_reject_reason or "setup_rejected"
            )
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
                    _publish_setup_eval(
                        self.name, "reject", f"llm_tuning:{skip_reason}"
                    )
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
                    _publish_setup_eval(self.name, "reject", f"llm_veto:{_veto_reason}")
                    return None

        # === P2-③ T5: RegimeGate check (after LLM veto, before Signal return) ===
        if self._gate_cfg is not None:
            _redis, _event_reader = acquire_infra_clients()
            if _redis is not None:
                blocked = apply_regime_gate(
                    gate_cfg=self._gate_cfg,
                    decision_signal=decision_signal,
                    context=context,
                    strategy_name=self.name,
                    redis=_redis,
                    event_reader=_event_reader,
                )
                if blocked:
                    _publish_setup_eval(self.name, "reject", "regime_gate_blocked")
                    return None

        # Daily directional bias gate (after RegimeGate, before signal emission).
        if self.config.daily_bias_filter_enabled:
            bias = self._daily_bias_provider.get_or_compute_bias(
                _get_llm_context(context), now_kst()
            )
            direction = decision_signal.direction
            if bias == "flat":
                _publish_setup_eval(self.name, "reject", "daily_bias_flat")
                return None
            if direction != bias:
                _publish_setup_eval(self.name, "reject", "daily_bias_misaligned")
                return None

        _publish_setup_eval(self.name, "fired", decision_signal.direction)
        md = context.market_data or {}
        _atr_14 = 0.0
        for _atr_key in ("atr", "atr_14", "atr14"):
            _v = md.get(_atr_key)
            if _v is not None:
                try:
                    _f = float(_v)
                    if _f > 0:
                        _atr_14 = _f
                        break
                except (TypeError, ValueError):
                    pass
        return _decision_signal_to_orchestrator_signal(
            decision_signal,
            strategy_name=self.name,
            timestamp=ts,
            confidence_override=confidence_override,
            entry_atr=_atr_14,
        )


class SetupDEntryAdapter(EntrySignalGenerator[SetupDEntryConfig]):
    """EntrySignalGenerator adapter wrapping :class:`SetupDVWAPReversion`.

    Bridges the ``TradingOrchestrator`` entry pipeline to the Thesis-A high-vol
    intraday VWAP-reversion logic (Setup D) without duplicating any threshold or
    business logic.

    Registered as ``"setup_d_vwap_reversion"`` in
    :func:`register_builtin_components`.

    Unlike Setup A/C, Setup D consumes no macro / event / LLM context — it fades
    ATR-scaled VWAP extremes on volatile intraday bars. The adapter therefore has
    no LLM-tuning / veto / forecast / daily-bias gating; it only optionally
    applies a :class:`RegimeGate` (P2-③ pattern) when ``gate_cfg`` is supplied,
    keeping the entry path consistent with Setup A/C wiring.
    """

    CONFIG_CLASS = SetupDEntryConfig

    def __init__(
        self,
        config: SetupDEntryConfig,
        gate_cfg: GateConfig | None = None,
    ) -> None:
        super().__init__(config)
        from shared.decision.setups.vwap_reversion import (
            SetupDConfig,
            SetupDVWAPReversion,
        )

        # Build a SetupDConfig from our config fields (mirrors field names 1:1).
        setup_cfg = SetupDConfig(
            enabled=config.enabled,
            valid_minutes_min=config.valid_minutes_min,
            no_entry_after_minutes_since_open=config.no_entry_after_minutes_since_open,
            min_atr_ratio=config.min_atr_ratio,
            vol_window_bars=config.vol_window_bars,
            vol_warmup_bars=config.vol_warmup_bars,
            vol_percentile=config.vol_percentile,
            extreme_atr_mult=config.extreme_atr_mult,
            stall_buffer_atr_mult=config.stall_buffer_atr_mult,
            stop_atr_mult=config.stop_atr_mult,
            min_reward_risk=config.min_reward_risk,
            signal_ttl_minutes=config.signal_ttl_minutes,
            range_window_bars=config.range_window_bars,
            range_warmup_bars=config.range_warmup_bars,
            extension_conf_scale=config.extension_conf_scale,
            vol_conf_scale=config.vol_conf_scale,
            min_confidence=config.min_confidence,
            reversal_confirm_enabled=config.reversal_confirm_enabled,
            reversal_confirm_atr_mult=config.reversal_confirm_atr_mult,
            reversal_confirm_requires_price_turn=(
                config.reversal_confirm_requires_price_turn
            ),
        )
        self._setup = SetupDVWAPReversion(config=setup_cfg)
        self._gate_cfg = gate_cfg

    def _validate_config(self) -> None:
        """Validate config fields.

        Raises:
            AssertionError: When any numeric param is out of valid range.
        """
        assert (
            0
            <= self.config.valid_minutes_min
            < self.config.no_entry_after_minutes_since_open
        ), "valid_minutes_min must be >= 0 and < no_entry_after_minutes_since_open"
        assert self.config.min_atr_ratio >= 0.0, "min_atr_ratio must be >= 0"
        assert self.config.extreme_atr_mult > 0.0, "extreme_atr_mult must be > 0"
        assert (
            self.config.stall_buffer_atr_mult >= 0.0
        ), "stall_buffer_atr_mult must be >= 0"
        assert self.config.stop_atr_mult > 0.0, "stop_atr_mult must be > 0"
        assert self.config.min_reward_risk > 0.0, "min_reward_risk must be > 0"
        assert self.config.signal_ttl_minutes > 0, "signal_ttl_minutes must be > 0"
        assert (
            self.config.reversal_confirm_atr_mult >= 0.0
        ), "reversal_confirm_atr_mult must be >= 0"

    @property
    def name(self) -> str:
        """Strategy registry name."""
        return "setup_d_vwap_reversion"

    @property
    def required_indicators(self) -> list[str]:
        """Indicators needed by Setup D.

        Setup D requires only ATR and the session VWAP (both populated on the
        MarketContext by the orchestrator / replay). Two references are
        self-computed by the setup from the per-bar inputs, so they are NOT
        required external indicators: the high-vol reference (from per-bar ATR)
        and the recent price range used by the stall guard (from per-bar close).
        Neither ``atr_90th_percentile`` nor ``last_15min_high/low`` has a live
        producer in the orchestrator path, which is why they are not depended on.
        """
        return ["atr", "vwap"]

    async def generate(self, context: EntryContext) -> OrchestratorSignal | None:
        """Generate an entry signal by delegating to :class:`SetupDVWAPReversion`.

        Args:
            context: Orchestrator entry context for the current tick.

        Returns:
            A tz-aware UTC :class:`shared.models.signal.Signal` when Setup D
            fires (and passes the optional RegimeGate), or ``None`` otherwise.
        """
        mc = _build_market_context(context)
        if mc is None:
            logger.debug("SetupDEntryAdapter: unable to build MarketContext — skipping")
            _publish_setup_eval(self.name, "reject", "no_market_context")
            return None

        decision_signal = self._setup.check(mc)
        if decision_signal is None:
            _publish_setup_eval(
                self.name, "reject", self._setup.last_reject_reason or "setup_rejected"
            )
            return None

        # Regime direction block: suppress counter-trend entries in strong regimes.
        # Mirrors Setup A/C long_blocked_regimes / short_blocked_regimes gating,
        # while also supporting the orchestrator's metadata-only regime path.
        cfg = self.config
        if cfg.long_blocked_regimes or cfg.short_blocked_regimes:
            regime = _resolve_regime_label(context)
            if regime is None:
                logger.debug(
                    "SetupD direction block: regime unavailable — block skipped (signal passes)"
                )
            else:
                direction: str = str(decision_signal.direction)
                if direction == "long" and regime in cfg.long_blocked_regimes:
                    logger.debug(
                        "SetupD direction block: long dropped — regime=%s in long_blocked_regimes",
                        regime,
                    )
                    _publish_setup_eval(
                        self.name, "reject", f"direction_blocked:{direction}:{regime}"
                    )
                    return None
                if direction == "short" and regime in cfg.short_blocked_regimes:
                    logger.debug(
                        "SetupD direction block: short dropped — regime=%s in short_blocked_regimes",
                        regime,
                    )
                    _publish_setup_eval(
                        self.name, "reject", f"direction_blocked:{direction}:{regime}"
                    )
                    return None

        ts = context.timestamp
        if ts is None:
            ts = datetime.now(UTC)

        # Optional RegimeGate check (consistent with Setup A/C wiring).
        if self._gate_cfg is not None:
            _redis, _event_reader = acquire_infra_clients()
            if _redis is not None:
                blocked = apply_regime_gate(
                    gate_cfg=self._gate_cfg,
                    decision_signal=decision_signal,
                    context=context,
                    strategy_name=self.name,
                    redis=_redis,
                    event_reader=_event_reader,
                )
                if blocked:
                    _publish_setup_eval(self.name, "reject", "regime_gate_blocked")
                    return None

        _publish_setup_eval(self.name, "fired", decision_signal.direction)
        md = context.market_data or {}
        _atr_14 = 0.0
        for _atr_key in ("atr", "atr_14", "atr14"):
            _v = md.get(_atr_key)
            if _v is not None:
                try:
                    _f = float(_v)
                    if _f > 0:
                        _atr_14 = _f
                        break
                except (TypeError, ValueError):
                    pass
        return _decision_signal_to_orchestrator_signal(
            decision_signal,
            strategy_name=self.name,
            timestamp=ts,
            entry_atr=_atr_14,
            extra_metadata=getattr(self._setup, "last_signal_details", {}),
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
            stop_buffer_atr_mult=config.stop_buffer_atr_mult,
            no_entry_after_minutes_since_open=config.no_entry_after_minutes_since_open,
        )
        self._setup = SetupCEventReaction(config=setup_cfg)
        # Phase 5 forecast integration — optional ForecastClient (default off).
        # When provided AND config.forecast_integration.enabled is True, the
        # adapter consumes 15-min vol forecast + event impact scores to derive
        # breakout buffer/target dynamically.
        self._forecast_client = forecast_client
        self._gate_cfg = gate_cfg  # P2-③ T5
        # Daily directional bias provider — gates on LLM-derived long/short regime.
        self._daily_bias_provider = DailyBiasProvider(
            bias_min_confidence=config.daily_bias_min_confidence,
            non_long_regimes=list(config.llm_tuning.long_blocked_regimes),
            bias_refresh_minutes=config.daily_bias_refresh_minutes,
        )

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
        * ``event_score.impact_score >= min_event_impact_score``.

        When forecast integration is enabled, a missing event score means the
        configured score constraint is not satisfied.
        """
        fi = self.config.forecast_integration
        if not fi.enabled:
            return True
        if event_score is None:
            return False
        return event_score.impact_score >= fi.min_event_impact_score

    async def _latest_event_score(self) -> Any | None:
        """Fetch the latest forecast event score, returning None on miss/error."""
        if self._forecast_client is None:
            return None
        getter = getattr(self._forecast_client, "get_latest_event_score", None)
        if getter is None:
            return None
        try:
            return await getter()
        except Exception as exc:  # noqa: BLE001
            logger.debug("SetupCEntryAdapter: event score fetch failed: %s", exc)
            return None

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
        assert (
            self.config.stop_buffer_atr_mult >= 0.0
        ), "stop_buffer_atr_mult must be >= 0"
        assert (
            self.config.no_entry_after_minutes_since_open > 0
        ), "no_entry_after_minutes_since_open must be > 0"

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
            _publish_setup_eval(self.name, "reject", "no_market_context")
            return None

        recent_event = mc.find_recent_event(
            window_minutes=self.config.window_minutes,
            min_tier=self.config.min_impact_tier,
        )
        if recent_event is not None and not self._setup.tracker.already_traded(
            recent_event.event_id
        ):
            event_score = await self._latest_event_score()
            if not self._event_passes_filter(event_score):
                reason = "forecast_event_score_missing"
                if event_score is not None:
                    reason = (
                        "forecast_event_score_below_min"
                        f"({event_score.impact_score:.0f}<"
                        f"{self.config.forecast_integration.min_event_impact_score})"
                    )
                _publish_setup_eval(self.name, "reject", reason)
                return None

        decision_signal = self._setup.check(mc)
        if decision_signal is None:
            _publish_setup_eval(
                self.name, "reject", self._setup.last_reject_reason or "setup_rejected"
            )
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
                    _publish_setup_eval(
                        self.name, "reject", f"llm_tuning:{skip_reason}"
                    )
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
                    _publish_setup_eval(self.name, "reject", f"llm_veto:{_veto_reason}")
                    return None

        # === P2-③ T5: RegimeGate check (after LLM veto, before Signal return) ===
        if self._gate_cfg is not None:
            _redis, _event_reader = acquire_infra_clients()
            if _redis is not None:
                blocked = apply_regime_gate(
                    gate_cfg=self._gate_cfg,
                    decision_signal=decision_signal,
                    context=context,
                    strategy_name=self.name,
                    redis=_redis,
                    event_reader=_event_reader,
                )
                if blocked:
                    _publish_setup_eval(self.name, "reject", "regime_gate_blocked")
                    return None

        # Daily directional bias gate (after RegimeGate, before signal emission).
        if self.config.daily_bias_filter_enabled:
            bias = self._daily_bias_provider.get_or_compute_bias(
                _get_llm_context(context), now_kst()
            )
            direction = decision_signal.direction
            if bias == "flat":
                _publish_setup_eval(self.name, "reject", "daily_bias_flat")
                return None
            if direction != bias:
                _publish_setup_eval(self.name, "reject", "daily_bias_misaligned")
                return None

        _publish_setup_eval(self.name, "fired", decision_signal.direction)
        md = context.market_data or {}
        _atr_14 = 0.0
        for _atr_key in ("atr", "atr_14", "atr14"):
            _v = md.get(_atr_key)
            if _v is not None:
                try:
                    _f = float(_v)
                    if _f > 0:
                        _atr_14 = _f
                        break
                except (TypeError, ValueError):
                    pass
        return _decision_signal_to_orchestrator_signal(
            decision_signal,
            strategy_name=self.name,
            timestamp=ts,
            confidence_override=confidence_override,
            entry_atr=_atr_14,
        )
