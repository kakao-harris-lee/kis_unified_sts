"""First-trigger composite exit.

Composes multiple exit generators into one: children are evaluated in order
and the first one that wants to exit wins. Used by the strategy factory to
combine the declarative ``builder_v1_exit`` risk block with a named exit
primitive referenced via ``BuilderState.exit_primitive`` (schema v2), but the
class is component-agnostic and reusable.

Exit signals keep the child's own ``strategy`` name so ledger attribution
shows which component actually closed the position.

State-cleanup protocol: when any child triggers an exit for a position, every
child is offered ``on_position_closed(pos_key)`` (looked up via ``getattr``,
so the hook is optional per child). Without this, a non-winning child's
per-position state (e.g. a trailing-stop extreme) would linger after the
position closes — and leak onto a future position that reuses the same key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared.config.mixins import ConfigMixin
from shared.models.signal import ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator, MarketStateProtocol


def _position_key(position: Any) -> str:
    """Per-position state key: position id, falling back to symbol code.

    Mirrors the convention used by exit generators that keep per-position
    state (e.g. ``BuilderStrategyExit``).
    """
    return str(getattr(position, "id", "") or getattr(position, "code", ""))


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
        children (trailing stops, stage machines) keep their state warm. When
        a child triggers, all children get ``on_position_closed`` so the
        non-winning children release their per-position state.
        """
        for child in self._children:
            triggered, signal = await child.should_exit(context)
            if triggered:
                self._notify_position_closed(_position_key(context.position))
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
                if _position_key(position) not in signaled
            ]
        for signal in signals:
            self._notify_position_closed(signal.position_id or signal.code)
        return signals

    def update_state(self, context: ExitContext) -> None:
        """Propagate state updates (trailing marks etc.) to every child."""
        for child in self._children:
            child.update_state(context)

    def _notify_position_closed(self, pos_key: str) -> None:
        """Offer every child the optional ``on_position_closed`` cleanup hook."""
        if not pos_key:
            return
        for child in self._children:
            hook = getattr(child, "on_position_closed", None)
            if callable(hook):
                hook(pos_key)
