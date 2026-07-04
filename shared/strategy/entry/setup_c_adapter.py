"""Setup C event-reaction entry adapter."""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from shared.decision.daily_bias import DailyBiasProvider
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.entry.setup_context_builder import build_setup_market_context
from shared.strategy.entry.setup_entry_configs import SetupCEntryConfig
from shared.strategy.entry.setup_eval_publisher import (
    publish_setup_eval as _default_publish_setup_eval,
)
from shared.strategy.entry.setup_llm_gate import (
    apply_llm_tuning_setup_c as _default_apply_llm_tuning_setup_c,
)
from shared.strategy.entry.setup_llm_gate import (
    apply_llm_veto as _default_apply_llm_veto,
)
from shared.strategy.entry.setup_llm_gate import (
    get_llm_context as _default_get_llm_context,
)
from shared.strategy.entry.setup_signal_mapper import (
    decision_signal_to_orchestrator_signal as _default_decision_signal_to_orchestrator_signal,
)
from shared.strategy.gates.adapter_helper import (
    acquire_infra_clients as _default_acquire_infra_clients,
)
from shared.strategy.gates.adapter_helper import (
    apply_regime_gate as _default_apply_regime_gate,
)
from shared.strategy.gates.regime_gate import GateConfig
from shared.strategy.market_time import now_kst as _default_now_kst

if TYPE_CHECKING:
    from shared.models.signal import Signal as OrchestratorSignal

logger = logging.getLogger(__name__)

_FACADE_MODULE = "shared.strategy.entry.setup_adapters"


def _facade_attr(name: str, default: Any) -> Any:
    facade = sys.modules.get(_FACADE_MODULE)
    if facade is None:
        return default
    return getattr(facade, name, default)


def _build_market_context(context: EntryContext) -> Any | None:
    fn = _facade_attr("_build_market_context", build_setup_market_context)
    return fn(context)


def _decision_signal_to_orchestrator_signal(*args: Any, **kwargs: Any) -> Any:
    fn = _facade_attr(
        "_decision_signal_to_orchestrator_signal",
        _default_decision_signal_to_orchestrator_signal,
    )
    return fn(*args, **kwargs)


def _publish_setup_eval(name: str, outcome: str, reason: str) -> None:
    fn = _facade_attr("_publish_setup_eval", None)
    if fn is not None and fn is not _publish_setup_eval:
        fn(name, outcome, reason)
        return
    _default_publish_setup_eval(name, outcome, reason)


def _get_llm_context(context: EntryContext) -> Any | None:
    fn = _facade_attr("_get_llm_context", _default_get_llm_context)
    return fn(context)


def _apply_llm_tuning_setup_c(*args: Any, **kwargs: Any) -> Any:
    fn = _facade_attr(
        "_apply_llm_tuning_setup_c",
        _default_apply_llm_tuning_setup_c,
    )
    return fn(*args, **kwargs)


def _apply_llm_veto(*args: Any, **kwargs: Any) -> Any:
    fn = _facade_attr("_apply_llm_veto", _default_apply_llm_veto)
    return fn(*args, **kwargs)


def _acquire_infra_clients() -> Any:
    fn = _facade_attr("acquire_infra_clients", _default_acquire_infra_clients)
    return fn()


def _apply_regime_gate(*args: Any, **kwargs: Any) -> Any:
    fn = _facade_attr("apply_regime_gate", _default_apply_regime_gate)
    return fn(*args, **kwargs)


def _now_kst() -> datetime:
    fn = _facade_attr("now_kst", _default_now_kst)
    return fn()


class SetupCEntryAdapter(EntrySignalGenerator[SetupCEntryConfig]):
    """EntrySignalGenerator adapter wrapping SetupCEventReaction."""

    CONFIG_CLASS = SetupCEntryConfig

    def __init__(
        self,
        config: SetupCEntryConfig,
        forecast_client: Any | None = None,
        gate_cfg: GateConfig | None = None,
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
        self._forecast_client = forecast_client
        self._gate_cfg = gate_cfg
        self._daily_bias_provider = DailyBiasProvider(
            bias_min_confidence=config.daily_bias_min_confidence,
            non_long_regimes=list(config.llm_tuning.long_blocked_regimes),
            bias_refresh_minutes=config.daily_bias_refresh_minutes,
        )

    def _derive_thresholds(
        self, forecast: Any | None, atr: float
    ) -> tuple[float, float]:
        """Return (breakout_buffer, target_distance) in price units."""
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
        """Return True if event_score meets the configured impact threshold."""
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
        """Validate config fields."""
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
        """Indicators needed by Setup C."""
        return ["atr", "last_15min_high", "last_15min_low"]

    async def generate(self, context: EntryContext) -> OrchestratorSignal | None:
        """Generate an entry signal by delegating to SetupCEventReaction."""
        mc = _build_market_context(context)
        if mc is None:
            logger.debug("SetupCEntryAdapter: unable to build MarketContext - skipping")
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

        confidence_override: float | None = None
        tuning = self.config.llm_tuning

        if not tuning.enabled:
            pass
        else:
            llm_ctx = _get_llm_context(context)
            if llm_ctx is None:
                logger.debug(
                    "SetupCEntryAdapter: market_context is None - skipping LLM tuning"
                )
            elif float(llm_ctx.confidence) < tuning.min_context_confidence:
                logger.info(
                    "SetupCEntryAdapter: LLM confidence %.3f < min %.3f - skipping LLM tuning",
                    float(llm_ctx.confidence),
                    tuning.min_context_confidence,
                )
            else:
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

                symbol = str(
                    (context.market_data or {}).get(
                        "code",
                        (context.market_data or {}).get("symbol", ""),
                    )
                )
                should_veto, veto_reason = _apply_llm_veto(
                    decision_signal=decision_signal,
                    llm_ctx=llm_ctx,
                    tuning=tuning,
                    setup_name=self.name,
                    symbol=symbol,
                    ts=ts,
                )
                if should_veto:
                    _publish_setup_eval(self.name, "reject", f"llm_veto:{veto_reason}")
                    return None

        if self._gate_cfg is not None:
            redis_client, event_reader = _acquire_infra_clients()
            if redis_client is not None:
                blocked = _apply_regime_gate(
                    gate_cfg=self._gate_cfg,
                    decision_signal=decision_signal,
                    context=context,
                    strategy_name=self.name,
                    redis=redis_client,
                    event_reader=event_reader,
                )
                if blocked:
                    _publish_setup_eval(self.name, "reject", "regime_gate_blocked")
                    return None

        if self.config.daily_bias_filter_enabled:
            bias = self._daily_bias_provider.get_or_compute_bias(
                _get_llm_context(context), _now_kst()
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
        atr_14 = 0.0
        for atr_key in ("atr", "atr_14", "atr14"):
            value = md.get(atr_key)
            if value is not None:
                try:
                    parsed = float(value)
                    if parsed > 0:
                        atr_14 = parsed
                        break
                except (TypeError, ValueError):
                    pass
        return _decision_signal_to_orchestrator_signal(
            decision_signal,
            strategy_name=self.name,
            timestamp=ts,
            confidence_override=confidence_override,
            entry_atr=atr_14,
        )
