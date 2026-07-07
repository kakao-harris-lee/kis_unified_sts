"""Setup D VWAP-reversion entry adapter."""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.entry.setup_context_builder import build_setup_market_context
from shared.strategy.entry.setup_entry_configs import SetupDEntryConfig
from shared.strategy.entry.setup_eval_publisher import (
    publish_setup_eval as _default_publish_setup_eval,
)
from shared.strategy.entry.setup_llm_gate import (
    resolve_regime_label as _default_resolve_regime_label,
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


def _resolve_regime_label(context: EntryContext) -> str | None:
    fn = _facade_attr("_resolve_regime_label", _default_resolve_regime_label)
    return fn(context)


def _acquire_infra_clients() -> Any:
    fn = _facade_attr("acquire_infra_clients", _default_acquire_infra_clients)
    return fn()


def _apply_regime_gate(*args: Any, **kwargs: Any) -> Any:
    fn = _facade_attr("apply_regime_gate", _default_apply_regime_gate)
    return fn(*args, **kwargs)


class SetupDEntryAdapter(EntrySignalGenerator[SetupDEntryConfig]):
    """EntrySignalGenerator adapter wrapping SetupDVWAPReversion."""

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
            trend_filter_enabled=config.trend_filter_enabled,
            trend_window_bars=config.trend_window_bars,
            trend_warmup_bars=config.trend_warmup_bars,
            trend_block_threshold=config.trend_block_threshold,
            against_trend_extreme_atr_mult=config.against_trend_extreme_atr_mult,
        )
        self._setup = SetupDVWAPReversion(config=setup_cfg)
        self._gate_cfg = gate_cfg

    def _validate_config(self) -> None:
        """Validate config fields."""
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
        """Indicators needed by Setup D."""
        return ["atr", "vwap"]

    async def generate(self, context: EntryContext) -> OrchestratorSignal | None:
        """Generate an entry signal by delegating to SetupDVWAPReversion."""
        mc = _build_market_context(context)
        if mc is None:
            logger.debug("SetupDEntryAdapter: unable to build MarketContext - skipping")
            _publish_setup_eval(self.name, "reject", "no_market_context")
            return None

        decision_signal = self._setup.check(mc)
        if decision_signal is None:
            _publish_setup_eval(
                self.name, "reject", self._setup.last_reject_reason or "setup_rejected"
            )
            return None

        cfg = self.config
        if cfg.long_blocked_regimes or cfg.short_blocked_regimes:
            regime = _resolve_regime_label(context)
            if regime is None:
                logger.debug(
                    "SetupD direction block: regime unavailable - block skipped (signal passes)"
                )
            else:
                direction: str = str(decision_signal.direction)
                if direction == "long" and regime in cfg.long_blocked_regimes:
                    logger.debug(
                        "SetupD direction block: long dropped - regime=%s in long_blocked_regimes",
                        regime,
                    )
                    _publish_setup_eval(
                        self.name, "reject", f"direction_blocked:{direction}:{regime}"
                    )
                    return None
                if direction == "short" and regime in cfg.short_blocked_regimes:
                    logger.debug(
                        "SetupD direction block: short dropped - regime=%s in short_blocked_regimes",
                        regime,
                    )
                    _publish_setup_eval(
                        self.name, "reject", f"direction_blocked:{direction}:{regime}"
                    )
                    return None

        ts = context.timestamp
        if ts is None:
            ts = datetime.now(UTC)

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
            entry_atr=atr_14,
            extra_metadata=getattr(self._setup, "last_signal_details", {}),
        )
