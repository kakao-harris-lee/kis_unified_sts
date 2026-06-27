"""API adapter interfaces for data collection."""
import logging
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Callable

from .models import TickData

logger = logging.getLogger(__name__)


class BaseAPIAdapter(ABC):
    """Base class for API adapters.

    Implement this for each data source (KIS, Upbit, etc.)
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to data source."""
        pass

    @abstractmethod
    def subscribe(self, symbols: list[str], callback: Callable[[TickData], None]) -> None:
        """Subscribe to symbols and register tick callback.

        Args:
            symbols: List of symbols to subscribe
            callback: Function called on each tick
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection."""
        pass


class MockAPIAdapter(BaseAPIAdapter):
    """Mock adapter for testing.

    Generates fake tick data at configurable interval.
    """

    def __init__(self, tick_interval: float = 0.1):
        self.tick_interval = tick_interval
        self._running = False
        self._callback: Callable[[TickData], None] = None

    def connect(self) -> None:
        logger.info("Mock API connected")

    def subscribe(self, symbols: list[str], callback: Callable[[TickData], None]) -> None:
        self._callback = callback
        self._running = True

        # Generate base prices for each symbol
        base_prices = {s: 330.0 + random.random() * 10 for s in symbols}

        while self._running:
            for symbol in symbols:
                base = base_prices[symbol]
                # Random walk
                base_prices[symbol] += (random.random() - 0.5) * 0.1

                tick = TickData(
                    symbol=symbol,
                    timestamp=time.time(),
                    bid_price_1=base - 0.025,
                    bid_qty_1=random.randint(10, 100),
                    ask_price_1=base + 0.025,
                    ask_qty_1=random.randint(10, 100),
                    current_price=base,
                    tick_volume=random.randint(1, 20),
                )
                self._callback(tick)

            time.sleep(self.tick_interval)

    def disconnect(self) -> None:
        self._running = False
        logger.info("Mock API disconnected")
