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
        storage_client: Any,
        taxonomy_path: Path,
        llm_client: LLMScorerClient | None = None,
        futures_tick_stream: str = "raw_data",
    ):
        self._config = config
        self._redis = redis_client
        self._storage_client = storage_client
        self._taxonomy = EventTaxonomy.load(taxonomy_path)
        self._llm = llm_client
        self._stop_event: asyncio.Event | None = None
        # Futures tick stream market_ingest republishes each mark to. Same key
        # the producer (TickStreamPublisher) uses so the two cannot drift.
        self._futures_tick_stream = futures_tick_stream
        # Last observed futures mark — bridges transient empty stream reads so a
        # single missed tick does not fabricate a price.
        self._last_close: float | None = None
        self._forecaster = VolatilityForecaster(config.har_rv)
        self._publisher = ForecastPublisher(
            redis=redis_client,
            storage_client=storage_client,
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
            self._forecaster = VolatilityForecaster.from_json(raw, self._config.har_rv)
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
            except TimeoutError:
                continue

    def _read_current_close(self) -> float | None:
        """Return the latest futures mark from the tick stream, or None.

        market_ingest (INGEST_ASSET=futures) republishes every mark to the
        futures tick stream (``raw_data`` by default). We read its newest entry
        rather than a hand-maintained scalar so the price tracks the live feed.
        Returns None on an empty/unreadable stream so the caller can fall back
        to the last known mark instead of a fabricated price.
        """
        try:
            entries = self._redis.xrevrange(self._futures_tick_stream, count=1)
        except Exception as e:  # noqa: BLE001 — off-path telemetry read
            logger.debug(
                "could not read futures tick stream %s: %s",
                self._futures_tick_stream,
                e,
            )
            return None
        if not entries:
            return None
        try:
            _entry_id, fields = entries[0]
        except Exception:  # noqa: BLE001 — malformed / non-stream entry
            return None

        def _field(name: str) -> Any:
            # Stream fields arrive as {bytes: bytes} (decode_responses=False) or
            # {str: str} (fakeredis / decoded clients); tolerate both.
            try:
                if name in fields:
                    return fields[name]
                return fields.get(name.encode())
            except (TypeError, AttributeError):
                return None

        for key in ("close", "current_price", "price"):
            raw = _field(key)
            if raw is None:
                continue
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", "ignore")
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
        return None

    async def _tick_forecast(self) -> None:
        # If model not fit, skip
        if self._forecaster._coefficients is None:
            return
        asof = datetime.now(UTC)
        current_close = self._read_current_close()
        if current_close is not None:
            self._last_close = current_close
        elif self._last_close is not None:
            # Transient empty read — reuse the last observed mark.
            current_close = self._last_close
        else:
            # No futures mark yet (pre-open / stream not primed). Skip rather
            # than scale the forecast to a fabricated price: forecast_atr_equivalent
            # drives Setup A gap/buffer/target geometry (shared/strategy/entry/
            # setup_adapters.py), so a wrong close distorts real entry/exit levels.
            logger.warning(
                "no futures mark on %s yet — skipping forecast tick",
                self._futures_tick_stream,
            )
            return
        vf = self._forecaster.forecast(asof, current_close=current_close)
        self._publisher.publish_vol_forecast(vf)

    async def _event_loop(self) -> None:
        assert self._stop_event is not None
        pubsub = None
        try:
            pubsub = self._redis.pubsub()
            pubsub.subscribe("news:raw")
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not subscribe to news:raw: %s — event loop idle", e)
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
            loop.add_signal_handler(sig, lambda: asyncio.create_task(service.stop()))
        except (NotImplementedError, RuntimeError):
            # Signal handlers are not available on all platforms (e.g. Windows
            # or non-main threads). Best-effort installation.
            logger.warning("Could not install handler for signal %s", sig)

    # SIGUSR1 → reload HAR-RV model from Redis (refit is performed externally
    # by scripts/forecasting/refit_har_rv.py which writes forecast:vol:model).
    try:
        loop.add_signal_handler(signal.SIGUSR1, service._try_load_model_from_redis)
    except (NotImplementedError, RuntimeError):
        logger.warning("Could not install handler for signal SIGUSR1")


async def _main() -> None:
    from shared.streaming.client import RedisClient

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    cfg = ForecastingConfig.from_yaml()
    redis = RedisClient.get_client()

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
            logger.warning("LLM client init failed: %s — event scorer rule-only", e)

    taxonomy_path = Path("config/event_taxonomy.yaml")
    service = ForecastingService(
        config=cfg,
        redis_client=redis,
        storage_client=None,
        taxonomy_path=taxonomy_path,
        llm_client=llm_client,
        # Same env var the producer (TickStreamPublisher) reads, so the
        # forecasting consumer always tracks the stream market_ingest writes.
        futures_tick_stream=os.environ.get("MONITOR_FUTURES_TICK_STREAM", "raw_data"),
    )

    loop = asyncio.get_running_loop()
    _install_signal_handlers(service, loop)
    await service.start()


if __name__ == "__main__":
    asyncio.run(_main())
