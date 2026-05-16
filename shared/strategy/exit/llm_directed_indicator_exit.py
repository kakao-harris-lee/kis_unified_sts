"""Composite exit for the LLM-directed indicator strategy.

Reuses ATRDynamicExit (trailing + hard-stop + EOD) and MomentumDecayExit
(momentum exhaustion). Both are evaluated per position; the highest
priority signal (lowest priority int) is returned. Hard-stop + EOD are
inherent to ATRDynamicExit and are independent safety nets the composite
never suppresses (design spec section 5).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from shared.config.mixins import ConfigMixin
from shared.models.position import Position
from shared.models.signal import ExitSignal
from shared.strategy.base import (
    ExitContext,
    ExitSignalGenerator,
    MarketStateProtocol,
)
from shared.strategy.exit.atr_dynamic import (
    ATRDynamicExit,
    ATRDynamicExitConfig,
)
from shared.strategy.exit.momentum_decay import (
    MomentumDecayConfig,
    MomentumDecayExit,
)
from shared.strategy.market_data import get_symbol_snapshot
from shared.strategy.market_time import now_kst

logger = logging.getLogger(__name__)


@dataclass
class LLMDirectedIndicatorExitConfig(ConfigMixin):
    """Sub-exit configs (defaults mirror each exit's own defaults)."""

    atr: dict[str, Any] = field(default_factory=dict)
    momentum_decay: dict[str, Any] = field(default_factory=dict)


class LLMDirectedIndicatorExit(
    ExitSignalGenerator[LLMDirectedIndicatorExitConfig]
):
    CONFIG_CLASS = LLMDirectedIndicatorExitConfig
    NAME = "LLM_DIRECTED_INDICATOR_EXIT"

    def __init__(self, config: LLMDirectedIndicatorExitConfig):
        super().__init__(config)
        self._atr = ATRDynamicExit(
            ATRDynamicExitConfig(**(config.atr or {})))
        self._mom = MomentumDecayExit(
            MomentumDecayConfig(**(config.momentum_decay or {})))

    def _validate_config(self):
        pass

    @property
    def name(self) -> str:
        return "llm_directed_indicator_exit"

    async def should_exit(
        self, context: ExitContext
    ) -> tuple[bool, ExitSignal | None]:
        candidates: list[ExitSignal] = []
        for sub in (self._atr, self._mom):
            try:
                fired, sig = await sub.should_exit(context)
                if fired and sig is not None:
                    candidates.append(sig)
            except Exception as exc:  # noqa: BLE001 — isolate sub-exit
                logger.debug("sub-exit %s raised: %s", sub.name, exc)
        if not candidates:
            return (False, None)
        best = min(candidates, key=lambda s: getattr(s, "priority", 99))
        return (True, best)

    async def scan_positions(
        self,
        positions: list[Position],
        market_data: dict[str, Any],
        market_state: MarketStateProtocol | None = None,
    ) -> list[ExitSignal]:
        out: list[ExitSignal] = []
        now = now_kst()
        for p in positions:
            snap = get_symbol_snapshot(market_data, p.code)
            ctx = ExitContext(position=p, market_data=snap,
                              indicators=snap, timestamp=now,
                              market_state=market_state)
            fired, sig = await self.should_exit(ctx)
            if fired and sig is not None:
                out.append(sig)
        return out
