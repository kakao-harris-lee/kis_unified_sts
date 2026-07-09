"""First-trigger composite exit.

Composes multiple exit generators into one: children are evaluated in order
and the first one that wants to exit wins. Used by the strategy factory to
combine the declarative ``builder_v1_exit`` risk block with a named exit
primitive referenced via ``BuilderState.exit_primitive`` (schema v2), but the
class is component-agnostic and reusable.

Exit signals keep the child's own ``strategy`` name so ledger attribution
shows which component actually closed the position.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared.config.mixins import ConfigMixin
from shared.models.signal import ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator, MarketStateProtocol


@dataclass
class FirstTriggerExitConfig(ConfigMixin):
    """Config for FirstTriggerExit (composition carries no tunables)."""


class FirstTriggerExit(ExitSignalGenerator[FirstTriggerExitConfig]):
    """Evaluate child exits in order; the first triggered child wins."""

    CONFIG_CLASS = FirstTriggerExitConfig

    def __init__(self, children: list[ExitSignalGenerator[Any]]):
        if not children:
            raise ValueError("FirstTriggerExit requires at least one child exit")
        self._children = list(children)
        super().__init__(FirstTriggerExitConfig())

    def _validate_config(self) -> None:
        assert self._children, "children must not be empty"

    @property
    def name(self) -> str:
        return "first_trigger(" + ",".join(c.name for c in self._children) + ")"

    @property
    def children(self) -> list[ExitSignalGenerator[Any]]:
        """The composed child exits, in evaluation order."""
        return list(self._children)

    async def should_exit(self, context: ExitContext) -> tuple[bool, ExitSignal | None]:
        """Return the first child's exit decision that triggers.

        Every child still sees every cycle until one triggers, so stateful
        children (trailing stops, stage machines) keep their state warm.
        """
        for child in self._children:
            triggered, signal = await child.should_exit(context)
            if triggered:
                return triggered, signal
        return False, None

    async def scan_positions(
        self,
        positions: list[Any],
        market_data: dict[str, Any],
        market_state: MarketStateProtocol | None = None,
    ) -> list[ExitSignal]:
        """Scan children in order; the first signal per position wins."""
        signals: list[ExitSignal] = []
        remaining = list(positions)
        for child in self._children:
            if not remaining:
                break
            child_signals = await child.scan_positions(
                remaining, market_data, market_state
            )
            if not child_signals:
                continue
            signals.extend(child_signals)
            signaled = {signal.position_id or signal.code for signal in child_signals}
            remaining = [
                position
                for position in remaining
                if (str(getattr(position, "id", "") or "") or position.code)
                not in signaled
            ]
        return signals

    def update_state(self, context: ExitContext) -> None:
        """Propagate state updates (trailing marks etc.) to every child."""
        for child in self._children:
            child.update_state(context)
