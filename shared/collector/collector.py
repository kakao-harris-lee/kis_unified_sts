"""Main data collector class."""
import time
import logging
from typing import List, Optional

from .adapter import BaseAPIAdapter
from .models import TickData
from shared.streaming.publisher import StreamPublisher

logger = logging.getLogger(__name__)


class DataCollector:
    """Data Collector - ingests data from API adapter to Redis Stream.

    This is the main entry point for real-time data collection.
    """

    def __init__(
        self,
        api_adapter: BaseAPIAdapter,
        stream_name: str = "raw_data",
        stream_maxlen: int = 100000,
    ):
        """Initialize collector.

        Args:
            api_adapter: API adapter instance
            stream_name: Redis stream name for output
            stream_maxlen: Maximum stream length (older entries trimmed)
        """
        self.adapter = api_adapter
        self.stream_name = stream_name
        self.stream_maxlen = stream_maxlen

        # Publisher created lazily on start
        self.publisher: Optional[StreamPublisher] = None

        self._running = False
        self._message_count = 0

    def _on_tick(self, tick: TickData) -> None:
        """Callback for tick data from adapter.

        Publishes tick to Redis Stream.
        """
        try:
            data = tick.to_dict()
            if self.publisher:
                self.publisher.publish(data)

            self._message_count += 1

            if self._message_count % 1000 == 0:
                logger.info(f"Published {self._message_count} messages")

        except Exception as e:
            logger.error(f"Error publishing tick: {e}")

    def start(self, symbols: List[str]) -> None:
        """Start data collection.

        Args:
            symbols: List of symbols to collect
        """
        logger.info(f"Starting Data Collector for {len(symbols)} symbols")
        self._running = True

        try:
            # Initialize publisher
            self.publisher = StreamPublisher(
                stream_name=self.stream_name,
                maxlen=self.stream_maxlen
            )

            # Connect and subscribe
            self.adapter.connect()
            self.adapter.subscribe(symbols, self._on_tick)

            # Main loop (adapter's subscribe is blocking)
            while self._running:
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop data collection."""
        self._running = False
        self.adapter.disconnect()
        logger.info(f"Data Collector stopped. Total messages: {self._message_count}")
