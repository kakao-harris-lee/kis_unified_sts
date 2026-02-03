"""Stock workflow: screener → warmup → data engine → strategy signals.

Components:
  - UniverseConsumer: listens to `system:universe`, fetches recent N candles
    from ClickHouse (async), loads into DataEngine.
  - TickConsumer: listens to `market:ticks`, merges ticks into DataEngine.
  - StrategyLoop: runs V35 strategy on DataEngine windows and publishes signals.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from shared.config.loader import ConfigLoader
from shared.db.config import ClickHouseConfig
from shared.db.client import AsyncClickHouseClient
from shared.streaming.consumer import StreamConsumer
from shared.streaming.message import StreamMessage
from shared.streaming.publisher import StreamPublisher
from shared.streaming.client import RedisClient

from core.data_engine import DataEngine, DataEngineConfig
from core.strategy_engine import StrategyEngine, StrategyEngineConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkflowConfig:
    tick_stream: str = os.environ.get("TICK_STREAM", "market:ticks")
    universe_stream: str = os.environ.get("UNIVERSE_STREAM", "system:universe")
    universe_latest_key: str = os.environ.get("UNIVERSE_LATEST_KEY", "system:universe:latest")

    signal_stream: str = os.environ.get("SIGNAL_STREAM", "signals:entries")

    consumer_group: str = os.environ.get("WORKFLOW_GROUP", "stock_workflow")
    consumer_name: str = os.environ.get("WORKFLOW_CONSUMER", "stock_workflow_1")

    warmup_bars: int = int(os.environ.get("WARMUP_BARS", "240"))
    warmup_minutes: int = int(os.environ.get("WARMUP_MINUTES", "240"))

    strategy_interval_seconds: float = float(os.environ.get("STRATEGY_INTERVAL_SECONDS", "1.0"))

    clickhouse_config_path: str = os.environ.get("CLICKHOUSE_CONFIG_PATH", "clickhouse.yaml")


class UniverseConsumer(StreamConsumer):
    """Subscribe to universe and warm up new symbols asynchronously."""

    def __init__(self, stream: str, group: str, orchestrator: "WorkflowOrchestrator"):
        super().__init__(stream, group, consumer_name=f"{group}_universe")
        self._orchestrator = orchestrator

    def process_message(self, message: StreamMessage) -> bool:
        codes = message.data.get("codes", [])
        if not isinstance(codes, list):
            return True
        self._orchestrator.on_universe_update([str(c) for c in codes])
        return True


class TickConsumer(StreamConsumer):
    """Subscribe to market ticks and feed into DataEngine."""

    def __init__(self, stream: str, group: str, orchestrator: "WorkflowOrchestrator"):
        super().__init__(stream, group, consumer_name=f"{group}_ticks")
        self._orchestrator = orchestrator

    def process_message(self, message: StreamMessage) -> bool:
        self._orchestrator.on_tick(message.data)
        return True


class WorkflowOrchestrator:
    def __init__(self, config: WorkflowConfig | None = None):
        self.config = config or WorkflowConfig()
        self.engine = DataEngine(DataEngineConfig(max_bars=self.config.warmup_bars))
        self.strategy_engine = StrategyEngine(config=StrategyEngineConfig())
        self.publisher = StreamPublisher(self.config.signal_stream)
        self.redis = RedisClient.get_client()

        self._active_codes: set[str] = set()
        self._lock = threading.RLock()

        self._universe_consumer = UniverseConsumer(
            self.config.universe_stream,
            self.config.consumer_group,
            self,
        )
        self._tick_consumer = TickConsumer(
            self.config.tick_stream,
            self.config.consumer_group,
            self,
        )

        self._threads: list[threading.Thread] = []
        self._strategy_thread: threading.Thread | None = None

        # Bootstrap from latest universe snapshot
        self._bootstrap_universe()

    def _bootstrap_universe(self) -> None:
        raw = self.redis.get(self.config.universe_latest_key)
        if not raw:
            return
        try:
            payload = json.loads(raw)
            codes = payload.get("codes", [])
            if isinstance(codes, list):
                self.on_universe_update([str(c) for c in codes])
        except Exception as e:
            logger.debug(f"Universe bootstrap failed: {e}")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def on_universe_update(self, codes: list[str]) -> None:
        cleaned: list[str] = []
        seen: set[str] = set()
        for c in codes:
            s = (c or "").strip()
            if not s or s in seen:
                continue
            seen.add(s)
            cleaned.append(s)

        if not cleaned:
            return

        with self._lock:
            new = set(cleaned)
            added = sorted(new - self._active_codes)
            self._active_codes = new

        if added:
            logger.info(f"Universe update: +{len(added)} symbols")
            self._start_warmup(added)

    def on_tick(self, payload: dict[str, Any]) -> None:
        code = (payload.get("symbol") or payload.get("code") or "").strip()
        if not code:
            return
        with self._lock:
            if self._active_codes and code not in self._active_codes:
                return
        self.engine.ingest_tick(payload)

    # ------------------------------------------------------------------
    # Warmup (async ClickHouse)
    # ------------------------------------------------------------------
    def _start_warmup(self, codes: list[str]) -> None:
        def runner():
            asyncio.run(self._warmup_codes_async(codes))

        t = threading.Thread(target=runner, name="warmup_thread", daemon=True)
        t.start()

    async def _warmup_codes_async(self, codes: list[str]) -> None:
        config = self._load_clickhouse_config()
        client = AsyncClickHouseClient(config)
        await client.connect()
        try:
            end = datetime.now()
            start = end - timedelta(minutes=max(1, int(self.config.warmup_minutes)))

            tasks = [client.get_minute_candles(code, start, end) for code in codes]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for code, res in zip(codes, results):
                if isinstance(res, Exception):
                    logger.warning(f"Warmup failed for {code}: {res}")
                    continue
                rows = [
                    {
                        "code": c.code,
                        "datetime": c.datetime,
                        "open": float(c.open),
                        "high": float(c.high),
                        "low": float(c.low),
                        "close": float(c.close),
                        "volume": int(c.volume),
                        "value": int(c.value),
                    }
                    for c in res
                ]
                if rows:
                    self.engine.load_history(code, rows)
        finally:
            await client.close()

    def _load_clickhouse_config(self) -> ClickHouseConfig:
        raw = ConfigLoader.load(self.config.clickhouse_config_path)
        if isinstance(raw, dict) and isinstance(raw.get("clickhouse"), dict):
            data = raw["clickhouse"]
        else:
            data = raw if isinstance(raw, dict) else {}
        return ClickHouseConfig(**data)

    # ------------------------------------------------------------------
    # Strategy loop
    # ------------------------------------------------------------------
    def _run_strategy_loop(self) -> None:
        while True:
            try:
                frames = self.engine.get_frames()
                signals = self.strategy_engine.evaluate_frames(frames)
                for signal in signals:
                    payload = {
                        "code": signal.code,
                        "strategy": signal.strategy,
                        "price": signal.price,
                        "confidence": signal.confidence,
                        "timestamp": signal.timestamp.isoformat(),
                        "metadata": signal.metadata,
                    }
                    self.publisher.publish(payload)
            except Exception as e:
                logger.warning(f"Strategy loop failed: {e}")
            time.sleep(self.config.strategy_interval_seconds)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        self._threads = [
            threading.Thread(target=self._universe_consumer.run, daemon=True),
            threading.Thread(target=self._tick_consumer.run, daemon=True),
        ]
        for t in self._threads:
            t.start()

        self._strategy_thread = threading.Thread(
            target=self._run_strategy_loop, daemon=True
        )
        self._strategy_thread.start()

        logger.info("Stock workflow started")

    def join(self) -> None:
        for t in self._threads:
            t.join()
        if self._strategy_thread:
            self._strategy_thread.join()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    orchestrator = WorkflowOrchestrator()
    orchestrator.start()
    orchestrator.join()


if __name__ == "__main__":
    main()

