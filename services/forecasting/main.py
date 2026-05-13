"""Forecasting service — asyncio daemon publishing vol + event scores."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared.forecasting.config import ForecastingConfig
from shared.forecasting.event_impact_scorer import EventImpactScorer
from shared.forecasting.event_taxonomy import EventTaxonomy
from shared.forecasting.forecast_publisher import ForecastPublisher
from shared.forecasting.llm_event_scorer import LLMScorerClient
from shared.forecasting.volatility_har_rv import VolatilityForecaster

logger = logging.getLogger(__name__)


class ForecastingService:
    """Background daemon: 1m forecast publish + news pubsub event scoring."""

    def __init__(
        self,
        config: ForecastingConfig,
        redis_client: Any,
        clickhouse_client: Any,
        taxonomy_path: Path,
        llm_client: LLMScorerClient | None = None,
    ):
        self._config = config
        self._redis = redis_client
        self._ch = clickhouse_client
        self._taxonomy = EventTaxonomy.load(taxonomy_path)
        self._llm = llm_client
        self._stop_event: asyncio.Event | None = None
        self._forecaster = VolatilityForecaster(config.har_rv)
        self._publisher = ForecastPublisher(
            redis=redis_client,
            clickhouse=clickhouse_client,
            vol_ttl_s=config.forecast_redis_ttl_seconds,
        )
        self._event_scorer = EventImpactScorer(
            config=config.event_scorer,
            taxonomy=self._taxonomy,
            llm_client=llm_client,
        )

    async def start(self) -> None:
        # Lazy-init asyncio.Event so it binds to the running loop.
        self._stop_event = asyncio.Event()

        if not self._config.publisher_enabled:
            logger.info("publisher_enabled=false — service idle")
            await self._stop_event.wait()
            return

        # Load latest model from Redis (if any)
        self._try_load_model_from_redis()

        forecast_task = asyncio.create_task(self._forecast_loop())
        event_task = asyncio.create_task(self._event_loop())

        try:
            await self._stop_event.wait()
        finally:
            for t in (forecast_task, event_task):
                t.cancel()
            await asyncio.gather(forecast_task, event_task, return_exceptions=True)

    async def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()

    def _try_load_model_from_redis(self) -> None:
        try:
            raw = self._redis.get("forecast:vol:model")
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not read forecast:vol:model: %s", e)
            return
        if raw is None:
            logger.info(
                "No saved HAR-RV model in Redis — service will run in "
                "ATR-fallback mode until first refit"
            )
            return
        try:
            self._forecaster = VolatilityForecaster.from_json(
                raw, self._config.har_rv
            )
            logger.info("Loaded HAR-RV model from Redis")
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not deserialize saved model: %s", e)

    async def _forecast_loop(self) -> None:
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            try:
                await self._tick_forecast()
            except Exception as e:  # noqa: BLE001
                logger.warning("forecast_loop tick failed: %s", e)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._config.forecast_loop_interval_seconds,
                )
            except asyncio.TimeoutError:
                continue

    async def _tick_forecast(self) -> None:
        # If model not fit, skip
        if self._forecaster._coefficients is None:
            return
        asof = datetime.now(UTC)
        # Caller should supply current_close from data_provider in production;
        # for now use a stub queryable from Redis (set elsewhere).
        try:
            close_raw = self._redis.get("market:futures:current_close")
        except Exception:  # noqa: BLE001
            close_raw = None
        try:
            current_close = float(close_raw) if close_raw else 380.0
        except (TypeError, ValueError):
            current_close = 380.0
        vf = self._forecaster.forecast(asof, current_close=current_close)
        self._publisher.publish_vol_forecast(vf)

    async def _event_loop(self) -> None:
        assert self._stop_event is not None
        pubsub = None
        try:
            pubsub = self._redis.pubsub()
            pubsub.subscribe("news:raw")
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Could not subscribe to news:raw: %s — event loop idle", e
            )
            await self._stop_event.wait()
            return

        try:
            while not self._stop_event.is_set():
                try:
                    msg = pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1.0
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning("pubsub.get_message failed: %s", e)
                    await asyncio.sleep(0.5)
                    continue
                if msg is None:
                    # Yield to event loop so stop_event can interrupt us.
                    await asyncio.sleep(0.1)
                    continue
                if msg.get("type") != "message":
                    continue
                data = msg.get("data", b"")
                if isinstance(data, bytes):
                    data = data.decode("utf-8", errors="ignore")
                try:
                    es = await self._event_scorer.score(data)
                    self._publisher.publish_event_score(es)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Event scoring failed: %s", e)
        finally:
            try:
                if pubsub is not None:
                    pubsub.unsubscribe()
                    pubsub.close()
            except Exception:  # noqa: BLE001
                pass


def _install_signal_handlers(
    service: ForecastingService, loop: asyncio.AbstractEventLoop
) -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                sig, lambda: asyncio.create_task(service.stop())
            )
        except (NotImplementedError, RuntimeError):
            # Signal handlers are not available on all platforms (e.g. Windows
            # or non-main threads). Best-effort installation.
            logger.warning("Could not install handler for signal %s", sig)


async def _main() -> None:
    from clickhouse_driver import Client

    from shared.db.config import ClickHouseConfig
    from shared.streaming.client import RedisClient

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    cfg = ForecastingConfig.from_yaml()
    redis = RedisClient.get_client()

    ch_cfg = ClickHouseConfig.from_env(database="kospi")
    ch = Client(
        host=ch_cfg.host,
        port=ch_cfg.port,
        user=ch_cfg.user,
        password=ch_cfg.password,
        database="kospi",
    )

    # LLM client (optional)
    llm_client = None
    if os.environ.get("OPENAI_API_KEY"):
        try:
            import openai

            from shared.forecasting.llm_event_scorer import OpenAIEventScorer

            llm_client = OpenAIEventScorer(
                openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "LLM client init failed: %s — event scorer rule-only", e
            )

    taxonomy_path = Path("config/event_taxonomy.yaml")
    service = ForecastingService(
        config=cfg,
        redis_client=redis,
        clickhouse_client=ch,
        taxonomy_path=taxonomy_path,
        llm_client=llm_client,
    )

    loop = asyncio.get_running_loop()
    _install_signal_handlers(service, loop)
    await service.start()


if __name__ == "__main__":
    asyncio.run(_main())
