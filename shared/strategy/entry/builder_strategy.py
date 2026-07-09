"""Builder-strategy entry (no-code Strategy Builder runtime adapter).

Brings strategies built in the Next.js visual builder (/builder) into the
STS paper trading runtime. Reads a serialized ``BuilderState`` from YAML
config and evaluates entry conditions per cycle via
``StrategyBuilderEvaluator``.

Direction (schema v2): ``BuilderState.entry`` is the long condition group and
the optional ``BuilderState.entry_short`` group expresses short entries
(futures-only, enforced by the schema). The bridge evaluates the long group
first, then the short group, and emits ``signal_direction`` accordingly —
sign-symmetric, so the futures long/short symmetry invariant is expressible
declaratively. States without ``entry_short`` behave exactly as before
(long-only).

Gates (schema v2): ``BuilderState.gates.regime_gate`` reuses the existing
framework RegimeGate — the strategy factory converts it into the
``_gate_cfg`` attachment shared with other entries, and this bridge applies it
via ``apply_regime_gate`` (PERMISSIVE when infra is missing).
``BuilderState.gates.cooldown_seconds`` merges with the deploy-time
``cooldown_seconds`` param by taking the maximum (most conservative).

The YAML shape this class consumes:

    strategy:
      entry:
        type: builder_v1
        params:
          builder_state: { ... full BuilderState JSON ... }
          cooldown_seconds: 0

Declarative computation: this adapter does no indicator math. It declares
``required_indicators == ["ohlcv"]`` so the resolver supplies the recent
OHLCV candle window under ``context.indicators["ohlcv"]``, then delegates to
``build_indicator_context`` (``shared/strategy_builder/indicator_context.py``),
which computes every ``BuilderState.indicators`` entry through the TA-Lib
engine into a DataFrame of ``alias.output`` columns. Because the context
carries the full series, cross_above/cross_below (and the v2
percentile_rank_* operators) work. Missing history or an unsupported
indicator surfaces as the evaluator's ``missing`` list, so the condition
group fails safely (no signal). Adding a new indicator is a registry change
only — this adapter and the evaluator never change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from shared.config.mixins import ConfigMixin
from shared.indicators.engine import cached_default_engine, window_from_records
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.gates.adapter_helper import (
    acquire_infra_clients,
    apply_regime_gate,
)
from shared.strategy.gates.regime_gate import GateConfig
from shared.strategy_builder.evaluator import StrategyBuilderEvaluator
from shared.strategy_builder.indicator_context import build_indicator_context
from shared.strategy_builder.schema import BuilderState, SymbolSeries

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

    def __init__(
        self,
        config: BuilderStrategyConfig,
        gate_cfg: GateConfig | None = None,
    ):
        super().__init__(config)
        self._evaluator = StrategyBuilderEvaluator()
        # Shared process-wide caching engine: N builder strategies asking for
        # the same (spec, window) compute it once per symbol/bar (P2-b).
        # Value-identical to default_engine() — backends are pure, pinned by
        # test_indicator_context_golden.py.
        self._engine = cached_default_engine()
        self._state: BuilderState | None = None
        self._last_signal_at: dict[str, datetime] = {}
        # Framework RegimeGate attachment. The factory overwrites this from the
        # entry params' regime_gate section or BuilderState.gates.regime_gate.
        self._gate_cfg = gate_cfg
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
            return

    @property
    def name(self) -> str:
        if self._state is not None:
            return f"builder_v1::{self._state.metadata.id}"
        return "builder_v1"

    @property
    def required_indicators(self) -> list[str]:
        # Declarative builder computes its OWN indicator context from OHLCV
        # history via the TA-Lib engine, so it only needs the raw candle window.
        # Declaring "ohlcv" makes the resolver populate context.indicators["ohlcv"].
        return ["ohlcv"]

    @property
    def effective_cooldown_seconds(self) -> int:
        """Cooldown merged from the deploy-time param and the schema gate.

        Takes the maximum of the two so the schema-declared cooldown can only
        tighten (never loosen) the deploy-time value — most-conservative merge.
        """
        schema_cooldown = 0
        if self._state is not None and self._state.gates is not None:
            schema_cooldown = self._state.gates.cooldown_seconds or 0
        return max(self.config.cooldown_seconds, schema_cooldown)

    async def generate(self, context: EntryContext) -> Signal | None:
        if self._state is None:
            return None

        data = context.market_data or {}
        code = str(data.get("code", "") or "")
        name = str(data.get("name", "") or "")
        if not code:
            return None

        now = context.timestamp
        cooldown = self.effective_cooldown_seconds
        if cooldown > 0:
            last = self._last_signal_at.get(code)
            if last and (now - last).total_seconds() < cooldown:
                return None

        series = self._build_series(code, name, context.indicators or {})
        evaluation, direction, matched_group = self._evaluate_direction(series)
        if evaluation is None:
            return None

        close = float(data.get("close", 0) or 0)
        if close <= 0:
            return None

        if not self._gate_allows(context, direction):
            return None

        logger.info(
            "builder_v1 entry signal: %s code=%s direction=%s score=%.2f "
            "conditions=%d/%d",
            self._state.metadata.name,
            code,
            direction,
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
                "signal_direction": direction,
                "matched_group": matched_group,
                "builder_state_id": self._state.metadata.id,
                "builder_state_name": self._state.metadata.name,
                "matched_conditions": [
                    {"label": ev.label, "passed": ev.passed}
                    for ev in evaluation.evaluations
                ],
            },
        )

    def _evaluate_direction(self, series: SymbolSeries) -> tuple[Any, str, str]:
        """Evaluate the long then short entry groups against ``series``.

        The long group ("entry") is primary: it is evaluated first and wins
        when both groups would pass on the same cycle, keeping evaluation
        deterministic.

        Args:
            series: Computed indicator context for the current symbol.

        Returns:
            ``(evaluation, direction, matched_group)``; ``evaluation`` is
            ``None`` when neither group produces an actionable signal.
        """
        assert self._state is not None
        evaluation = self._evaluator.evaluate_group(
            self._state.entry.conditions,
            self._state.entry.logic,
            series,
        )
        if evaluation.passed and evaluation.score >= self.config.min_confidence:
            return evaluation, "long", "entry"

        short_group = self._state.entry_short
        if short_group is not None and short_group.conditions:
            short_evaluation = self._evaluator.evaluate_group(
                short_group.conditions,
                short_group.logic,
                series,
            )
            if (
                short_evaluation.passed
                and short_evaluation.score >= self.config.min_confidence
            ):
                return short_evaluation, "short", "entry_short"
        return None, "long", "entry"

    def _gate_allows(self, context: EntryContext, direction: str) -> bool:
        """Apply the framework RegimeGate; PERMISSIVE when infra is missing."""
        if self._gate_cfg is None:
            return True
        redis_client, event_reader = acquire_infra_clients()
        if redis_client is None:
            return True  # PERMISSIVE on missing infra
        stand_in = type("X", (), {"metadata": {"signal_direction": direction}})()
        blocked = apply_regime_gate(
            gate_cfg=self._gate_cfg,
            decision_signal=stand_in,
            context=context,
            strategy_name=self.name,
            redis=redis_client,
            event_reader=event_reader,
        )
        return not blocked

    def _build_series(
        self,
        code: str,
        name: str,
        indicators: dict[str, Any],
    ) -> SymbolSeries:
        """Compute the declarative Indicator Context over the OHLCV history.

        The resolver supplies ``indicators["ohlcv"]`` (completed candles) because
        this strategy declares ``required_indicators == ["ohlcv"]``. Every
        indicator value is computed by the TA-Lib engine from that window — the
        builder itself does no indicator math. Full series means cross operators
        have a genuine previous value. Absent history yields an empty series, so
        the evaluator reports every operand as ``missing`` and fails safe.
        """
        if self._state is None:
            return SymbolSeries(symbol=code, name=name or None)
        rows = indicators.get("ohlcv")
        if not isinstance(rows, list) or not rows:
            return SymbolSeries(symbol=code, name=name or None)
        window = window_from_records(rows)
        context = build_indicator_context(self._state, window, self._engine)
        return context.to_symbol_series(code, name or None)
