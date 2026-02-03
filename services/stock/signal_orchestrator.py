"""Signal-to-Orchestrator bridge.

Consumes `signals:entries` stream and routes signals to TradingOrchestrator
for position/risk management and execution.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import redis

from shared.execution.config import ExecutionConfig
from shared.execution.executor import OrderExecutor
from shared.kis.auth import KISAuthConfig, KISAuthManager
from shared.models.signal import Signal, SignalType
from shared.streaming.client import RedisClient
from shared.streaming.message import StreamMessage
from services.trading.orchestrator import TradingConfig, TradingOrchestrator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SignalOrchestratorConfig:
    signal_stream: str = os.environ.get("SIGNAL_STREAM", "signals:entries")
    consumer_group: str = os.environ.get("SIGNAL_ORCH_GROUP", "stock_signal_orch")
    consumer_name: str = os.environ.get("SIGNAL_ORCH_CONSUMER", "stock_signal_orch_1")

    strategy_name: str = os.environ.get("SIGNAL_ORCH_STRATEGY", "v35_optimized_polars")
    order_amount_per_trade: float = float(os.environ.get("ORDER_AMOUNT_PER_TRADE", "1000000"))

    trading_mode: str = os.environ.get("TRADING_MODE", "PAPER")
    account_no: str = os.environ.get("KIS_ACCOUNT_NO", "")

    redis_url: str = os.environ.get("EXECUTION_REDIS_URL", "")
    rate_limit_key: str = os.environ.get("EXECUTION_RATE_LIMIT_KEY", "stock")
    requests_per_second: float = float(os.environ.get("EXECUTION_RPS", "20.0"))

    dedupe_seconds: float = float(os.environ.get("SIGNAL_ORCH_DEDUPE_SECONDS", "10"))


class SignalOrchestrator:
    def __init__(self, config: SignalOrchestratorConfig | None = None):
        self.config = config or SignalOrchestratorConfig()
        self.client = RedisClient.get_client()

        self._read_count = int(os.environ.get("REDIS_CONSUMER_READ_COUNT", "10"))
        self._block_ms = int(os.environ.get("REDIS_CONSUMER_BLOCK_MS", "1000"))

        self._last_seen: dict[str, float] = {}
        self._ensure_group()

        paper_trading = self.config.trading_mode.upper() == "PAPER"

        tconfig = TradingConfig.stock(
            strategy_name=self.config.strategy_name,
            symbols=[],
            order_amount=self.config.order_amount_per_trade,
        )
        tconfig.paper_trading = paper_trading

        self.orchestrator = TradingOrchestrator(tconfig)

        self.order_executor: OrderExecutor | None = None
        if not paper_trading:
            exec_config = ExecutionConfig(
                trading_mode=self.config.trading_mode,
                account_no=self.config.account_no,
                redis_url=self.config.redis_url,
                rate_limit_key=self.config.rate_limit_key,
                requests_per_second=self.config.requests_per_second,
            )
            kis_config = KISAuthConfig(is_real=(self.config.trading_mode.upper() == "REAL"))
            auth_manager = KISAuthManager.get_instance(kis_config)
            self.order_executor = OrderExecutor(exec_config, auth_manager=auth_manager)
            self.orchestrator.set_order_executor(self.order_executor)

    def _ensure_group(self) -> None:
        try:
            self.client.xgroup_create(
                self.config.signal_stream,
                self.config.consumer_group,
                id="0",
                mkstream=True,
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def run(self) -> None:
        if self.order_executor:
            await self.order_executor.initialize()

        await self.orchestrator._initialize_components()

        try:
            await self._process_pending()

            while True:
                result = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self.client.xreadgroup(
                        self.config.consumer_group,
                        self.config.consumer_name,
                        {self.config.signal_stream: ">"},
                        count=self._read_count,
                        block=self._block_ms,
                    ),
                )
                if not result:
                    continue

                for stream_name, stream_msgs in result:
                    for msg_id, fields in stream_msgs:
                        msg = StreamMessage.from_raw(stream_name, msg_id, fields)
                        ok = await self._handle_message(msg)
                        if ok:
                            self.client.xack(stream_name, self.config.consumer_group, msg_id)
        finally:
            if self.order_executor:
                await self.order_executor.cleanup()

    async def _process_pending(self) -> None:
        pending = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self.client.xreadgroup(
                self.config.consumer_group,
                self.config.consumer_name,
                {self.config.signal_stream: "0"},
                count=self._read_count,
                block=None,
            ),
        )
        if not pending:
            return
        for stream_name, stream_msgs in pending:
            for msg_id, fields in stream_msgs:
                msg = StreamMessage.from_raw(stream_name, msg_id, fields)
                ok = await self._handle_message(msg)
                if ok:
                    self.client.xack(stream_name, self.config.consumer_group, msg_id)

    async def _handle_message(self, msg: StreamMessage) -> bool:
        data = msg.data
        code = (data.get("code") or data.get("symbol") or "").strip()
        if not code:
            return True

        now = time.time()
        last = self._last_seen.get(code, 0.0)
        if now - last < self.config.dedupe_seconds:
            return True
        self._last_seen[code] = now

        price = _parse_float(data.get("price"))
        if price <= 0:
            return True

        ts = data.get("timestamp")
        if isinstance(ts, str):
            try:
                timestamp = datetime.fromisoformat(ts)
            except ValueError:
                timestamp = datetime.now()
        else:
            timestamp = datetime.now()

        signal = Signal(
            code=code,
            signal_type=SignalType.ENTRY,
            strategy=str(data.get("strategy") or self.config.strategy_name),
            price=price,
            confidence=_parse_float(data.get("confidence")) or 0.5,
            timestamp=timestamp,
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
        )

        await self.orchestrator._execute_entry(signal)
        return True


def _parse_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    orch = SignalOrchestrator()
    asyncio.run(orch.run())


if __name__ == "__main__":
    main()

