"""Thin structural contracts for strategy components."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from shared.llm.market_context import MarketContext
    from shared.models.position import Position
    from shared.models.signal import ExitSignal, Signal
    from shared.strategy.base import EntryContext, ExitContext, MarketStateProtocol


@runtime_checkable
class EntrySignalGeneratorProtocol(Protocol):
    """Small entry-generator surface used by TradingStrategy callers."""

    @property
    def name(self) -> str:
        """Strategy component name."""
        ...

    @property
    def required_indicators(self) -> list[str]:
        """Indicator keys required before generate() can run."""
        ...

    async def generate(self, context: EntryContext) -> Signal | None:
        """Return an entry signal when conditions are met."""
        ...


@runtime_checkable
class ExitSignalGeneratorProtocol(Protocol):
    """Small exit-generator surface used by TradingStrategy callers."""

    @property
    def name(self) -> str:
        """Strategy component name."""
        ...

    async def should_exit(self, context: ExitContext) -> tuple[bool, ExitSignal | None]:
        """Return whether the current position should exit."""
        ...

    async def scan_positions(
        self,
        positions: list[Position],
        market_data: dict[str, Any],
        market_state: MarketStateProtocol | None = None,
    ) -> list[ExitSignal]:
        """Return exit signals for positions matching the current market data."""
        ...


@runtime_checkable
class PositionSizerProtocol(Protocol):
    """Small position-sizing surface used by TradingStrategy callers."""

    def calculate(
        self,
        signal: Signal,
        account_balance: float,
        current_positions: list[Position],
        market_context: MarketContext | None = None,
    ) -> int:
        """Return the quantity to trade for an entry signal."""
        ...


__all__ = [
    "EntrySignalGeneratorProtocol",
    "ExitSignalGeneratorProtocol",
    "PositionSizerProtocol",
]
