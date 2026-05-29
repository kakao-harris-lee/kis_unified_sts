"""Builder-strategy entry (no-code Strategy Builder runtime adapter).

Brings strategies built in the Next.js visual builder (/builder) into the
STS paper trading runtime. Reads a serialized ``BuilderState`` from YAML
config and evaluates entry conditions per cycle via
``StrategyBuilderEvaluator``.

Stock-only by design (Phase 1 of the builder→paper bridge, 2026-05-29):
futures strategies stay on the dedicated entry classes (setup_a, setup_c,
bb_reversion_15m). When ``builder_state.asset_class != "stock"`` the
entry no-ops with a one-time warning.

The YAML shape this class consumes:

    strategy:
      entry:
        type: builder_v1
        params:
          builder_state: { ... full BuilderState JSON ... }
          cooldown_seconds: 0

History feed: STS provides per-tick scalar indicators; the evaluator only
needs the latest two values (current + previous for crossover detection).
We build a 2-element ``SymbolSeries`` from the runtime context — enough
for ``current_left / current_right`` and ``previous_left / previous_right``
in evaluate_condition.

Indicator name mapping: builder operands reference ``alias.output``
(default ``alias.value``). The runtime expects the orchestrator's
``context.indicators`` dict to contain the alias under that same key.
Builder users set the alias to whatever the runtime emits — typically the
indicator id itself (e.g. alias=``rsi``, output=``value`` → series.indicators[``rsi.value``]).
Missing aliases surface as the evaluator's ``missing`` list, which makes
the condition group fail safely (no signal).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy_builder.evaluator import StrategyBuilderEvaluator
from shared.strategy_builder.schema import BuilderState, SymbolSeries

_KST = ZoneInfo("Asia/Seoul")
logger = logging.getLogger(__name__)


@dataclass
class BuilderStrategyConfig(ConfigMixin):
    """Config for the builder_v1 entry."""

    builder_state: dict[str, Any] = field(default_factory=dict)
    cooldown_seconds: int = 0
    # Confidence floor for the BuilderEvaluator score (0.0-1.0). Conditions
    # report a score of ``passed_count / total_count``; require at least this
    # before emitting a Signal.
    min_confidence: float = 0.5


class BuilderStrategyEntry(EntrySignalGenerator[BuilderStrategyConfig]):
    """Run a no-code builder strategy at paper-trade cadence."""

    CONFIG_CLASS = BuilderStrategyConfig

    def __init__(self, config: BuilderStrategyConfig):
        super().__init__(config)
        self._evaluator = StrategyBuilderEvaluator()
        self._state: BuilderState | None = None
        self._last_signal_at: dict[str, datetime] = {}
        self._asset_mismatch_warned = False
        self._parse_state()

    def _validate_config(self) -> None:
        assert isinstance(self.config.builder_state, dict), "builder_state must be dict"
        assert self.config.cooldown_seconds >= 0
        assert 0.0 <= self.config.min_confidence <= 1.0

    def _parse_state(self) -> None:
        if not self.config.builder_state:
            logger.warning("builder_v1 entry has empty builder_state; will no-op")
            return
        try:
            self._state = BuilderState.model_validate(self.config.builder_state)
        except Exception as exc:
            logger.error("builder_v1 entry failed to parse builder_state: %s", exc)
            self._state = None

    @property
    def name(self) -> str:
        if self._state is not None:
            return f"builder_v1::{self._state.metadata.id}"
        return "builder_v1"

    @property
    def required_indicators(self) -> list[str]:
        # Builder operands reference indicator aliases at runtime; we don't
        # ask the resolver to materialize anything specific. The orchestrator
        # passes whatever was already computed, and missing aliases just
        # make the condition group fail safely.
        return []

    async def generate(self, context: EntryContext) -> Signal | None:
        if self._state is None:
            return None
        if self._state.asset_class != "stock":
            if not self._asset_mismatch_warned:
                logger.warning(
                    "builder_v1 entry skipping: asset_class=%s (stock-only in Phase 1)",
                    self._state.asset_class,
                )
                self._asset_mismatch_warned = True
            return None

        data = context.market_data or {}
        code = str(data.get("code", "") or "")
        name = str(data.get("name", "") or "")
        if not code:
            return None

        now = context.timestamp
        if self.config.cooldown_seconds > 0:
            last = self._last_signal_at.get(code)
            if last and (now - last).total_seconds() < self.config.cooldown_seconds:
                return None

        series = self._build_series(code, name, data, context.indicators or {})
        evaluation = self._evaluator.evaluate_group(
            self._state.entry.conditions,
            self._state.entry.logic,
            series,
        )
        if not evaluation.passed:
            return None
        if evaluation.score < self.config.min_confidence:
            return None

        close = float(data.get("close", 0) or 0)
        if close <= 0:
            return None

        logger.info(
            "builder_v1 entry signal: %s code=%s score=%.2f conditions=%d/%d",
            self._state.metadata.name,
            code,
            evaluation.score,
            sum(1 for ev in evaluation.evaluations if ev.passed),
            len(evaluation.evaluations),
        )
        self._last_signal_at[code] = now
        return Signal(
            code=code,
            name=name,
            signal_type=SignalType.ENTRY,
            price=close,
            timestamp=context.timestamp,
            strategy=self.name,
            confidence=evaluation.score,
            metadata={
                "signal_direction": "long",
                "builder_state_id": self._state.metadata.id,
                "builder_state_name": self._state.metadata.name,
                "matched_conditions": [
                    {"label": ev.label, "passed": ev.passed}
                    for ev in evaluation.evaluations
                ],
            },
        )

    def _build_series(
        self,
        code: str,
        name: str,
        data: dict[str, Any],
        indicators: dict[str, Any],
    ) -> SymbolSeries:
        """Materialize a 2-tick SymbolSeries from per-tick context.

        evaluate_condition only reads ``_latest`` and ``_previous``, so 2
        observations are enough. We duplicate the current scalar into
        previous when no history is available — the cross-over branch then
        cannot fire on the first tick (correct: a fresh strategy has no
        crossover to detect yet).
        """
        def _dup(x: float | None) -> list[float]:
            if x is None:
                return []
            return [float(x), float(x)]

        fields: dict[str, list[float]] = {}
        for key in ("close", "open", "high", "low", "volume"):
            value = data.get(key)
            if value is not None:
                fields[key] = _dup(value)

        # Resolve every builder alias against the runtime indicators dict.
        # Builder operand key = "alias.output"; runtime indicators expose
        # values either keyed by full "alias.output" or by raw alias.
        series_indicators: dict[str, list[float]] = {}
        if self._state is not None:
            for ind in self._state.indicators:
                key_alias = ind.alias
                key_full = f"{ind.alias}.{ind.output}"
                value = indicators.get(key_full)
                if value is None:
                    value = indicators.get(key_alias)
                if isinstance(value, (int, float)):
                    series_indicators[key_full] = _dup(value)
                elif isinstance(value, dict):
                    # Some indicators (bb) expose multi-output dicts.
                    out_value = value.get(ind.output)
                    if isinstance(out_value, (int, float)):
                        series_indicators[key_full] = _dup(out_value)

        return SymbolSeries(
            symbol=code,
            name=name or None,
            timestamps=[],
            fields=fields,
            indicators=series_indicators,
        )
