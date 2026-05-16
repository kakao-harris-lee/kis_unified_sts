"""Technical consensus entry strategy for stock timing.

This strategy turns the shared RSI / Williams %R / MACD consensus helper into
an entry generator. It is intentionally conservative by default: at least two
core indicator votes must overlap before an entry signal is emitted.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.technical_consensus import (
    TechnicalConsensusConfig,
    build_technical_consensus,
)

logger = logging.getLogger(__name__)


@dataclass
class TechnicalConsensusEntryConfig(ConfigMixin):
    """Config for RSI / Williams %R / MACD entry vote overlap."""

    min_entry_votes: int = 2
    min_entry_core_votes: int = 2
    min_exit_votes: int = 2
    min_exit_core_votes: int = 2

    rsi_oversold: float = 35.0
    rsi_recovery: float = 40.0
    rsi_overbought: float = 70.0
    rsi_rollover: float = 60.0

    williams_oversold: float = -80.0
    williams_reversal: float = -65.0
    williams_overbought: float = -20.0
    williams_exit: float = -35.0

    macd_hist_threshold: float = 0.0
    include_trend_vote: bool = True
    trend_buffer_pct: float = 0.0
    include_volume_vote: bool = True
    min_volume_ratio: float = 1.2
    exit_retrace_from_high_pct: float = 0.03

    stop_loss_pct: float = 3.0
    signal_cooldown_days: int = 1
    min_confidence: float = 0.70
    confidence_base: float = 0.60
    confidence_vote_bonus: float = 0.10

    def validate(self) -> None:
        if self.stop_loss_pct <= 0:
            raise ValueError("stop_loss_pct must be positive")
        if self.signal_cooldown_days < 0:
            raise ValueError("signal_cooldown_days must be non-negative")
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0, 1]")
        if not 0.0 < self.confidence_base <= 1.0:
            raise ValueError("confidence_base must be in (0, 1]")
        if self.confidence_vote_bonus < 0:
            raise ValueError("confidence_vote_bonus must be non-negative")
        self.to_consensus_config().validate()

    def to_consensus_config(self) -> TechnicalConsensusConfig:
        values = {
            field.name: getattr(self, field.name)
            for field in dataclasses.fields(TechnicalConsensusConfig)
            if hasattr(self, field.name)
        }
        return TechnicalConsensusConfig(**values)


class TechnicalConsensusEntry(EntrySignalGenerator[TechnicalConsensusEntryConfig]):
    """Long-only stock entry using overlapping technical timing votes."""

    CONFIG_CLASS = TechnicalConsensusEntryConfig

    def __init__(self, config: TechnicalConsensusEntryConfig) -> None:
        super().__init__(config)
        self._last_signal_at: dict[str, datetime] = {}

    def _validate_config(self) -> None:
        self.config.validate()

    @property
    def name(self) -> str:
        return "technical_consensus"

    @property
    def required_indicators(self) -> list[str]:
        return [
            "rsi",
            "prev_rsi",
            "williams_r",
            "prev_williams_r",
            "macd_hist",
            "prev_macd_hist",
            "ma20",
            "volume_ratio",
        ]

    async def generate(self, context: EntryContext) -> Signal | None:
        data = context.market_data or {}
        indicators = context.indicators or {}
        code = str(data.get("code", "") or indicators.get("code", "") or "")
        name = str(data.get("name", "") or indicators.get("name", "") or "")
        close = self._first_float(data, indicators, "close", "price", "current_price")
        if not code or close is None or close <= 0:
            return None

        now = context.timestamp
        if self._is_cooling_down(code, now):
            return None

        snapshot: dict[str, Any] = {**data, **indicators}
        snapshot.setdefault("close", close)
        if "ma20" not in snapshot:
            for key in ("sma_20", "daily_sma_20", "bb_middle", "vwap"):
                if key in snapshot:
                    snapshot["ma20"] = snapshot[key]
                    break

        consensus = build_technical_consensus(
            snapshot,
            market_data=data,
            config=self.config.to_consensus_config(),
        )
        if not consensus.entry_signal:
            return None

        confidence = self._confidence(consensus.entry_core_vote_count)
        if confidence < self.config.min_confidence:
            return None

        self._last_signal_at[code] = now
        stop_loss = close * (1.0 - self.config.stop_loss_pct / 100.0)

        logger.info(
            "TechnicalConsensus LONG signal: %s close=%.2f votes=%s confidence=%.2f",
            code,
            close,
            consensus.summary,
            confidence,
        )
        return Signal(
            code=code,
            name=name,
            signal_type=SignalType.ENTRY,
            price=close,
            timestamp=now,
            strategy=self.name,
            confidence=confidence,
            metadata={
                "signal_direction": "long",
                "trigger": "technical_consensus",
                "stop_loss": stop_loss,
                "stop_loss_pct": float(self.config.stop_loss_pct),
                "technical_consensus": consensus.to_dict(),
            },
        )

    def _is_cooling_down(self, code: str, now: datetime) -> bool:
        if self.config.signal_cooldown_days <= 0:
            return False
        last = self._last_signal_at.get(code)
        if last is None:
            return False
        return (now - last).days < self.config.signal_cooldown_days

    def _confidence(self, core_votes: int) -> float:
        extra_votes = max(0, core_votes - self.config.min_entry_core_votes)
        return min(
            0.95,
            self.config.confidence_base + extra_votes * self.config.confidence_vote_bonus,
        )

    @staticmethod
    def _first_float(
        data: dict[str, Any],
        indicators: dict[str, Any],
        *keys: str,
    ) -> float | None:
        for key in keys:
            for source in (indicators, data):
                value = source.get(key)
                if value is None:
                    continue
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return None
