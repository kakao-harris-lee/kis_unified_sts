"""Setup A gap-reversion entry adapter."""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from shared.decision.daily_bias import DailyBiasProvider as _default_DailyBiasProvider
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.entry.setup_context_builder import build_setup_market_context
from shared.strategy.entry.setup_entry_configs import SetupAEntryConfig
from shared.strategy.entry.setup_eval_publisher import (
    publish_setup_eval as _default_publish_setup_eval,
)
from shared.strategy.entry.setup_llm_gate import (
    apply_llm_tuning_setup_a as _default_apply_llm_tuning_setup_a,
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


def _apply_llm_tuning_setup_a(*args: Any, **kwargs: Any) -> Any:
    fn = _facade_attr(
        "_apply_llm_tuning_setup_a",
        _default_apply_llm_tuning_setup_a,
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


def _daily_bias_provider_class() -> Any:
    return _facade_attr("DailyBiasProvider", _default_DailyBiasProvider)


class SetupAEntryAdapter(EntrySignalGenerator[SetupAEntryConfig]):
    """EntrySignalGenerator adapter wrapping SetupAGapReversion."""

    CONFIG_CLASS = SetupAEntryConfig

    def __init__(
        self,
        config: SetupAEntryConfig,
        forecast_client: Any | None = None,
        gate_cfg: GateConfig | None = None,
    ) -> None:
        super().__init__(config)
        from shared.decision.setups.gap_reversion import (
            SetupAConfig,
            SetupAGapReversion,
        )

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
        self._forecast_client = forecast_client
        self._gate_cfg = gate_cfg
        self._daily_bias_provider = _daily_bias_provider_class()(
            bias_min_confidence=config.daily_bias_min_confidence,
            non_long_regimes=list(config.llm_tuning.long_blocked_regimes),
            bias_refresh_minutes=config.daily_bias_refresh_minutes,
        )

    def _derive_gap_threshold_pct(self, forecast: Any | None) -> float:
        """Return the gap entry threshold in percent units."""
        fi = self.config.forecast_integration
        if fi.enabled and forecast is not None:
            return fi.gap_threshold_vol_mult * forecast.forecast_pct
        return self.config.min_kr_gap_pct

    def _gap_within_reversion_range(self, gap_pct: float, forecast: Any | None) -> bool:
        """Return True when gap_pct is within the forecast-aware range."""
        fi = self.config.forecast_integration
        if not fi.enabled or forecast is None:
            return True
        max_pct = fi.max_gap_for_reversion_vol_mult * forecast.forecast_pct
        return gap_pct <= max_pct

    def _compute_event_size_mult(self, event_score: Any | None) -> float:
        """Return a position-size multiplier in (0, 1] based on event impact."""
        fi = self.config.forecast_integration
        if not fi.enabled or not fi.use_event_impact_for_size:
            return 1.0
        if event_score is None:
            return 1.0
        return 1.0 / (1.0 + event_score.impact_score / 100.0)

    def _validate_config(self) -> None:
        """Validate config fields."""
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
        """Minimal indicators needed to satisfy Setup A price lookups."""
        return ["atr", "prev_close", "vwap"]

    async def generate(self, context: EntryContext) -> OrchestratorSignal | None:
        """Generate an entry signal by delegating to SetupAGapReversion."""
        mc = _build_market_context(context)
        if mc is None:
            logger.debug("SetupAEntryAdapter: unable to build MarketContext - skipping")
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

        confidence_override: float | None = None
        tuning = self.config.llm_tuning

        if not tuning.enabled:
            pass
        else:
            llm_ctx = _get_llm_context(context)
            if llm_ctx is None:
                logger.debug(
                    "SetupAEntryAdapter: market_context is None - skipping LLM tuning"
                )
            elif float(llm_ctx.confidence) < tuning.min_context_confidence:
                logger.info(
                    "SetupAEntryAdapter: LLM confidence %.3f < min %.3f - skipping LLM tuning",
                    float(llm_ctx.confidence),
                    tuning.min_context_confidence,
                )
            else:
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
