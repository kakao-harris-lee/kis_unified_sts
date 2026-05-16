"""Config-driven daily pullback pattern combo entry."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator

logger = logging.getLogger(__name__)


def _default_patterns() -> list[dict[str, Any]]:
    return [
        {
            "name": "pullback_reversal",
            "rsi5_max": 45.0,
            "min_atr_pct": 0.02,
            "min_highest_high_gap_pct": -0.05,
            "require_mid_trend": True,
        },
        {
            "name": "volume_pullback",
            "rsi5_max": 50.0,
            "min_volume_ratio": 1.5,
            "max_return_60d": 0.05,
            "min_atr_pct": 0.03,
        },
    ]


@dataclass
class PatternPullbackConfig(ConfigMixin):
    """Daily pullback pattern-combo configuration."""

    sma_long_period: int = 200
    sma_short_period: int = 20
    sma_mid_period: int = 60
    rsi_period: int = 5
    mid_trend_lookback: int = 5
    signal_cooldown_days: int = 5
    confidence_base: float = 0.72
    confidence_pattern_bonus: float = 0.01
    min_confidence: float = 0.30
    stop_loss_pct: float = 7.0
    entry_sort: str = "rsi5_asc"
    patterns: list[dict[str, Any]] = field(default_factory=_default_patterns)

    def validate(self) -> None:
        if self.sma_long_period <= 0:
            raise ValueError("sma_long_period must be positive")
        if self.sma_short_period <= 0:
            raise ValueError("sma_short_period must be positive")
        if self.sma_mid_period <= 0:
            raise ValueError("sma_mid_period must be positive")
        if self.rsi_period <= 0:
            raise ValueError("rsi_period must be positive")
        if self.mid_trend_lookback < 0:
            raise ValueError("mid_trend_lookback must be non-negative")
        if self.signal_cooldown_days < 0:
            raise ValueError("signal_cooldown_days must be non-negative")
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0, 1]")
        if not 0.0 < self.confidence_base <= 1.0:
            raise ValueError("confidence_base must be in (0, 1]")
        if self.confidence_pattern_bonus < 0.0:
            raise ValueError("confidence_pattern_bonus must be non-negative")
        if self.stop_loss_pct <= 0:
            raise ValueError("stop_loss_pct must be positive")
        if self.entry_sort not in {
            "pattern_priority",
            "rsi5_asc",
            "atr_pct_desc",
            "volume_ratio_desc",
        }:
            raise ValueError(f"unsupported entry_sort: {self.entry_sort}")
        if not self.patterns:
            raise ValueError("patterns must not be empty")
        if not all(isinstance(pattern, dict) for pattern in self.patterns):
            raise ValueError("patterns must be a list of mappings")


class PatternPullbackEntry(EntrySignalGenerator[PatternPullbackConfig]):
    """Long-only daily strategy that admits a ranked set of pullback patterns."""

    CONFIG_CLASS = PatternPullbackConfig

    def __init__(self, config: PatternPullbackConfig) -> None:
        super().__init__(config)
        self._last_signal_date: dict[str, datetime] = {}

    def _validate_config(self) -> None:
        self.config.validate()

    @property
    def name(self) -> str:
        return "pattern_pullback"

    @property
    def required_indicators(self) -> list[str]:
        return [
            "sma_200",
            "sma_20",
            "sma_60",
            "sma_60_prev",
            "rsi_5",
            "atr",
            "highest_high",
            "volume_ratio",
        ]

    async def generate(self, context: EntryContext) -> Signal | None:
        data = context.market_data or {}
        indicators = context.indicators or {}
        code = str(data.get("code", "") or "")
        name = str(data.get("name", "") or code)
        close = self._get(data, indicators, "close", 0.0)
        if not code or close <= 0:
            return None

        now = context.timestamp
        if self._is_cooling_down(code, now):
            return None

        values = self._values(data, indicators, close)
        if not self._base_trend_ok(values):
            return None

        for idx, pattern in enumerate(self.config.patterns):
            if not self._matches_pattern(pattern, values):
                continue
            confidence = self._confidence(pattern, idx)
            if confidence < self.config.min_confidence:
                continue
            self._last_signal_date[code] = now
            entry_priority = self._entry_priority(idx, values)
            logger.info(
                "PatternPullback LONG signal: %s pattern=%s close=%.0f "
                "rsi5=%.1f atr_pct=%.2f%% volume_ratio=%.2f priority=%.4f",
                code,
                pattern.get("name", f"pattern_{idx}"),
                close,
                values["rsi_5"],
                values["atr_pct"] * 100.0,
                values["volume_ratio"],
                entry_priority,
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
                    "trigger": "pattern_pullback",
                    "pattern_name": pattern.get("name", f"pattern_{idx}"),
                    "pattern_index": idx,
                    "entry_priority": entry_priority,
                    "entry_sort": self.config.entry_sort,
                    "stop_loss": close * (1.0 - self.config.stop_loss_pct / 100.0),
                    "sma_200": values["sma_200"],
                    "sma_20": values["sma_20"],
                    "sma_60": values["sma_60"],
                    "rsi_5": values["rsi_5"],
                    "atr_pct": values["atr_pct"],
                    "volume_ratio": values["volume_ratio"],
                    "highest_high_gap_pct": values["highest_high_gap_pct"],
                    "return_60d": values["return_60d"],
                },
            )

        return None

    def _is_cooling_down(self, code: str, now: datetime) -> bool:
        if self.config.signal_cooldown_days <= 0:
            return False
        last = self._last_signal_date.get(code)
        if last is None:
            return False
        return (now - last).days < self.config.signal_cooldown_days

    def _values(
        self,
        data: dict[str, Any],
        indicators: dict[str, Any],
        close: float,
    ) -> dict[str, float | None]:
        atr = self._get(data, indicators, "atr", 0.0)
        highest_high = self._get(data, indicators, "highest_high", 0.0)
        return {
            "close": close,
            "sma_200": self._get(data, indicators, "sma_200", 0.0),
            "sma_20": self._get(data, indicators, "sma_20", 0.0),
            "sma_60": self._get(data, indicators, "sma_60", 0.0),
            "sma_60_prev": self._get(data, indicators, "sma_60_prev", 0.0),
            "rsi_5": self._get(data, indicators, "rsi_5", 50.0),
            "atr": atr,
            "atr_pct": atr / close if atr > 0 else 0.0,
            "volume_ratio": self._get(data, indicators, "volume_ratio", 0.0),
            "highest_high": highest_high,
            "highest_high_gap_pct": (
                (close - highest_high) / highest_high if highest_high > 0 else 0.0
            ),
            "return_60d": self._recent_return(data, indicators, 60),
        }

    def _base_trend_ok(self, values: dict[str, float | None]) -> bool:
        close = float(values["close"] or 0.0)
        sma_200 = float(values["sma_200"] or 0.0)
        sma_20 = float(values["sma_20"] or 0.0)
        if sma_200 <= 0 or close <= sma_200:
            return False
        return not (sma_20 <= 0 or close > sma_20)

    def _matches_pattern(
        self,
        pattern: dict[str, Any],
        values: dict[str, float | None],
    ) -> bool:
        rsi_5 = float(values["rsi_5"] or 50.0)
        atr_pct = float(values["atr_pct"] or 0.0)
        volume_ratio = float(values["volume_ratio"] or 0.0)
        highest_high = float(values["highest_high"] or 0.0)
        highest_high_gap_pct = float(values["highest_high_gap_pct"] or 0.0)
        return_60d = values["return_60d"]

        require_mid_trend = self._pattern_bool(
            pattern,
            "require_mid_trend",
            self._pattern_bool(pattern, "sma60_rising", False),
        )
        if require_mid_trend and not (
            float(values["sma_60"] or 0.0) > float(values["sma_60_prev"] or 0.0) > 0.0
        ):
            return False

        if rsi_5 > self._pattern_float(pattern, "rsi5_max", 100.0):
            return False
        min_atr_pct = self._pattern_float_any(
            pattern,
            ("min_atr_pct", "atr_pct_min"),
            0.0,
        )
        if min_atr_pct > 0.0 and atr_pct < min_atr_pct:
            return False
        max_atr_pct = self._pattern_optional_float_any(
            pattern,
            ("max_atr_pct", "atr_pct_max"),
        )
        if max_atr_pct is not None and atr_pct > max_atr_pct:
            return False
        min_volume_ratio = self._pattern_float_any(
            pattern,
            ("min_volume_ratio", "volume_ratio_min"),
            0.0,
        )
        if min_volume_ratio > 0.0 and volume_ratio < min_volume_ratio:
            return False
        max_volume_ratio = self._pattern_optional_float_any(
            pattern,
            ("max_volume_ratio", "volume_ratio_max"),
        )
        if max_volume_ratio is not None and volume_ratio > max_volume_ratio:
            return False
        min_hh_gap = self._pattern_optional_float_any(
            pattern,
            ("min_highest_high_gap_pct", "highest_high_gap_min"),
        )
        if min_hh_gap is not None and (
            highest_high <= 0.0 or highest_high_gap_pct < min_hh_gap
        ):
            return False
        max_return_60d = self._pattern_optional_float_any(
            pattern,
            ("max_return_60d", "return_60d_max"),
        )
        if max_return_60d is None:
            return True
        return return_60d is not None and return_60d <= max_return_60d

    def _entry_priority(
        self,
        pattern_index: int,
        values: dict[str, float | None],
    ) -> float:
        if self.config.entry_sort == "rsi5_asc":
            return float(values["rsi_5"] or 100.0)
        if self.config.entry_sort == "atr_pct_desc":
            return -float(values["atr_pct"] or 0.0)
        if self.config.entry_sort == "volume_ratio_desc":
            return -float(values["volume_ratio"] or 0.0)
        return float(pattern_index)

    def _confidence(self, pattern: dict[str, Any], pattern_index: int) -> float:
        configured = self._pattern_optional_float(pattern, "confidence")
        if configured is not None:
            return max(0.1, min(0.95, configured))
        bonus = max(0, len(self.config.patterns) - pattern_index - 1)
        return max(
            0.1,
            min(
                0.95,
                self.config.confidence_base
                + bonus * self.config.confidence_pattern_bonus,
            ),
        )

    @staticmethod
    def _get(
        data: dict[str, Any],
        indicators: dict[str, Any],
        key: str,
        default: float,
    ) -> float:
        for candidate in (key, f"daily_{key}"):
            for source in (indicators, data):
                value = source.get(candidate)
                if value is None:
                    continue
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return default

    @staticmethod
    def _recent_return(
        data: dict[str, Any],
        indicators: dict[str, Any],
        period: int,
    ) -> float | None:
        raw_closes = indicators.get("daily_closes") or data.get("daily_closes") or []
        if not isinstance(raw_closes, list) or len(raw_closes) <= period:
            return None
        try:
            current = float(raw_closes[-1])
            previous = float(raw_closes[-period - 1])
        except (TypeError, ValueError, IndexError):
            return None
        if current <= 0 or previous <= 0:
            return None
        return current / previous - 1.0

    @staticmethod
    def _pattern_float(pattern: dict[str, Any], key: str, default: float) -> float:
        value = pattern.get(key, default)
        try:
            return float(default if value is None else value)
        except (TypeError, ValueError):
            return float(default)

    @classmethod
    def _pattern_float_any(
        cls,
        pattern: dict[str, Any],
        keys: tuple[str, ...],
        default: float,
    ) -> float:
        for key in keys:
            if key in pattern:
                return cls._pattern_float(pattern, key, default)
        return float(default)

    @staticmethod
    def _pattern_optional_float(pattern: dict[str, Any], key: str) -> float | None:
        value = pattern.get(key)
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _pattern_optional_float_any(
        cls,
        pattern: dict[str, Any],
        keys: tuple[str, ...],
    ) -> float | None:
        for key in keys:
            if key in pattern:
                return cls._pattern_optional_float(pattern, key)
        return None

    @staticmethod
    def _pattern_bool(pattern: dict[str, Any], key: str, default: bool) -> bool:
        value = pattern.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return bool(value)
