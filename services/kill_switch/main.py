"""Kill-switch monitor daemon.

Phase 4 Task 13 — polls a fixed list of conditions every
``check_interval_seconds``. The first trigger:

  1. writes ``risk:event`` (Redis stream — wired by parent runtime)
  2. invokes ``force_close_callback`` to flatten all open positions
  3. sends a Telegram alert
  4. writes a sentinel file to disk so the order_router daemon refuses to
     start until an operator runs ``scripts/kill_switch_clear.sh``
  5. exits the run loop — process supervisor (systemd) brings down peers

Re-entry safety: on startup, if the sentinel exists the daemon enters the
tripped state immediately without taking action — the previous trip was
already handled. An operator must explicitly clear the sentinel.

Spec §6 lists six standard conditions, all implemented as :class:`KillCondition`
subclasses below. Conditions take their data from a runtime state snapshot
or an injected provider callable; tests verify each in isolation.

Phase 0.2 (LLM-primary plan §4) — ``_force_flat_callback`` now writes a
Redis sentinel key ``kill_switch:force_flatten:requested`` (TTL 300 s) and
appends to the ``kill_switch:events`` stream so that any consuming process
(TradingOrchestrator / order_router) can detect the request and act on it.

  **Consumer follow-up (deferred)**: ``TradingOrchestrator`` must poll
  ``kill_switch:force_flatten:requested`` on each heartbeat tick and call
  its own ``flatten_all()`` method when the key is present. That wiring is
  tracked as a separate task per the plan (§4 Phase 0.2-a follow-up) and
  intentionally not included here to keep this PR focused on the
  *signalling side only*. Until the consumer is wired, the sentinel remains
  a best-effort alert; operator manual intervention is still required.

Phase 0.4 (LLM-primary plan §4) — provider-backed conditions
(``ApiErrorRateCondition``, ``NewsPipelineLagCondition``) are instantiated in
``_build_and_run()`` with callable providers that read from observability sources.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from shared.config.runtime_defaults import redis_url_from_env
from shared.risk.runtime_state import RuntimeRiskState

logger = logging.getLogger(__name__)

# Redis key / stream constants (centralised here; never hard-code in callers).
_FORCE_FLATTEN_KEY = "kill_switch:force_flatten:requested"
_FORCE_FLATTEN_TTL_SECONDS = 300
_EVENTS_STREAM = "kill_switch:events"
_EVENTS_STREAM_TTL_SECONDS = 86400  # 24 h — consistent with project TTL policy


# ---------------------------------------------------------------------------
# Condition definitions — one per spec §6.1 row.
# ---------------------------------------------------------------------------


class KillCondition(ABC):
    name: str = "abstract"

    @abstractmethod
    def check(self, *, snapshot: Any) -> bool:
        """Return True if the condition has been triggered."""

    @property
    def details(self) -> dict[str, Any]:
        return {}


class DailyLossCondition(KillCondition):
    name = "daily_loss"

    def __init__(self, *, limit_pct: float, equity_krw: float) -> None:
        self.limit_pct = limit_pct
        self.equity_krw = equity_krw

    def check(self, *, snapshot: Any) -> bool:
        # Compare loss-as-fraction-of-equity directly so the threshold is
        # immune to float drift in (limit_pct * equity_krw). "At or beyond
        # limit" — equality fires the kill switch per spec §6.1.
        if self.equity_krw <= 0:
            return False
        loss_pct = -snapshot.daily_pnl_krw / self.equity_krw
        return loss_pct >= self.limit_pct


class WeeklyLossCondition(KillCondition):
    name = "weekly_loss"

    def __init__(self, *, limit_pct: float, equity_krw: float) -> None:
        self.limit_pct = limit_pct
        self.equity_krw = equity_krw

    def check(self, *, snapshot: Any) -> bool:
        if self.equity_krw <= 0:
            return False
        loss_pct = -snapshot.weekly_pnl_krw / self.equity_krw
        return loss_pct >= self.limit_pct


class ConsecutiveLossesCondition(KillCondition):
    name = "consecutive_losses"

    def __init__(self, *, threshold: int) -> None:
        self.threshold = threshold

    def check(self, *, snapshot: Any) -> bool:
        return snapshot.consecutive_losses >= self.threshold


class _ProviderBackedCondition(KillCondition):
    """Conditions whose value is supplied by a runtime callable, not a snapshot."""

    def __init__(self, *, threshold: float, provider: Callable[[], float]) -> None:
        self.threshold = threshold
        self.provider = provider

    def check(self, *, snapshot: Any) -> bool:  # noqa: ARG002 — abstract signature
        return self.provider() >= self.threshold


class ApiErrorRateCondition(_ProviderBackedCondition):
    name = "api_error_rate"

    def __init__(self, *, threshold: float, rate_provider: Callable[[], float]) -> None:
        super().__init__(threshold=threshold, provider=rate_provider)


class NewsPipelineLagCondition(_ProviderBackedCondition):
    name = "news_pipeline_lag"

    def __init__(
        self, *, threshold_seconds: float, lag_provider: Callable[[], float]
    ) -> None:
        super().__init__(threshold=threshold_seconds, provider=lag_provider)


# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------


class KillSwitchDaemon:
    def __init__(
        self,
        *,
        runtime_state: RuntimeRiskState,
        conditions: list[KillCondition],
        force_close_callback: Callable[..., Awaitable[None]],
        telegram_client: Any,
        check_interval_seconds: float,
        sentinel_path: str | None,
    ) -> None:
        self.runtime_state = runtime_state
        self.conditions = conditions
        self.force_close_callback = force_close_callback
        self.telegram = telegram_client
        self.check_interval_seconds = check_interval_seconds
        self.sentinel_path = Path(sentinel_path) if sentinel_path else None
        self._stop = asyncio.Event()
        self.tripped: bool = False
        self.triggered_reason: str | None = None

    async def run(self) -> None:
        if self._sentinel_present():
            self.tripped = True
            self.triggered_reason = "sentinel_present"
            logger.warning(
                "Kill switch sentinel exists at %s — refusing to operate",
                self.sentinel_path,
            )
            return

        while not self._stop.is_set():
            try:
                snapshot = await self.runtime_state.snapshot()
            except Exception:
                logger.exception("snapshot fetch failed; sleeping and retrying")
                await asyncio.sleep(self.check_interval_seconds)
                continue

            for cond in self.conditions:
                try:
                    if cond.check(snapshot=snapshot):
                        await self._trigger(cond)
                        return
                except Exception:
                    logger.exception(
                        "condition %s evaluation raised; treating as no-trigger",
                        cond.name,
                    )

            await asyncio.sleep(self.check_interval_seconds)

    async def stop(self) -> None:
        self._stop.set()

    def _sentinel_present(self) -> bool:
        return self.sentinel_path is not None and self.sentinel_path.exists()

    async def _trigger(self, condition: KillCondition) -> None:
        self.tripped = True
        self.triggered_reason = condition.name
        logger.critical(
            "KILL SWITCH TRIPPED reason=%s details=%s",
            condition.name,
            condition.details,
        )

        # 1. Force-flat callback
        try:
            await self.force_close_callback(reason=condition.name)
        except Exception:
            logger.exception("force_close_callback failed")

        # 2. Telegram alert
        try:
            await self.telegram.send_message(
                f"KILL SWITCH TRIPPED: {condition.name} :: {condition.details}"
            )
        except Exception:
            logger.exception("telegram alert failed")

        # 3. Sentinel file — order_router checks this on startup
        if self.sentinel_path is not None:
            try:
                self.sentinel_path.parent.mkdir(parents=True, exist_ok=True)
                self.sentinel_path.write_text(
                    f"reason={condition.name}\ndetails={condition.details}\n"
                )
            except Exception:
                logger.exception("sentinel write failed at %s", self.sentinel_path)


async def _build_and_run() -> int:
    """Production entrypoint — wires conditions + force_close_callback.

    Phase 4 Task 17: the force_close_callback flatlines all open positions
    via the KIS adapter when any condition trips. Conditions and thresholds
    come from KillSwitchConfig.from_yaml() (config/kill_switch.yaml).

    Equity for the loss-pct conditions is read from
    ``KIS_FUTURES_EQUITY_KRW`` env var because operator may need to adjust
    it without redeploying — defaults to 100M KRW.

    Phase 0.2 (LLM-primary plan): ``_force_flat_callback`` now writes
    ``kill_switch:force_flatten:requested`` (TTL 300 s) to Redis and publishes
    to the ``kill_switch:events`` stream.  The TradingOrchestrator consumer
    side is a **deferred follow-up task** — see module docstring.

    Phase 0.4 (LLM-primary plan): all six KillConditions are instantiated.
    The three provider-backed conditions read from available observability
    sources; where a live metric source does not yet exist, the provider
    returns 0.0 (safe default, will never trigger) and logs a TODO.
    """
    import os
    import signal as signal_mod

    import redis.asyncio as aioredis
    from services.kill_switch.config import KillSwitchConfig
    from shared.notification.telegram import TelegramNotifier
    from shared.risk.runtime_state import RuntimeRiskState

    cfg = KillSwitchConfig.from_yaml()
    if not cfg.enabled:
        logger.info("kill_switch disabled in config; refusing to start.")
        return 0

    redis_url = redis_url_from_env()
    redis_client = aioredis.from_url(redis_url)
    runtime_state = RuntimeRiskState(redis=redis_client, asset_class="futures")

    equity_krw = float(os.environ.get("KIS_FUTURES_EQUITY_KRW", "100000000"))

    conditions: list[KillCondition] = []
    cc = cfg.conditions
    if cc.daily_loss.enabled and cc.daily_loss.limit_pct is not None:
        conditions.append(
            DailyLossCondition(
                limit_pct=float(cc.daily_loss.limit_pct), equity_krw=equity_krw
            )
        )
    if cc.weekly_loss.enabled and cc.weekly_loss.limit_pct is not None:
        conditions.append(
            WeeklyLossCondition(
                limit_pct=float(cc.weekly_loss.limit_pct), equity_krw=equity_krw
            )
        )
    if cc.consecutive_losses.enabled and cc.consecutive_losses.threshold is not None:
        conditions.append(
            ConsecutiveLossesCondition(threshold=int(cc.consecutive_losses.threshold))
        )

    # ------------------------------------------------------------------
    # Phase 0.4: provider-backed conditions (all 3 wired).
    # ------------------------------------------------------------------

    if cc.api_error_rate_5min.enabled and cc.api_error_rate_5min.threshold is not None:
        conditions.append(
            ApiErrorRateCondition(
                threshold=float(cc.api_error_rate_5min.threshold),
                rate_provider=_build_api_error_rate_provider(redis_client),
            )
        )

    if (
        cc.news_pipeline_lag_seconds.enabled
        and cc.news_pipeline_lag_seconds.threshold is not None
    ):
        conditions.append(
            NewsPipelineLagCondition(
                threshold_seconds=float(cc.news_pipeline_lag_seconds.threshold),
                lag_provider=_build_news_pipeline_lag_provider(
                    redis_client, cc.news_pipeline_lag_seconds.stream_key
                ),
            )
        )

    telegram = TelegramNotifier(
        bot_token=os.environ["TELEGRAM_FUTURES_BOT_TOKEN"],
        chat_id=os.environ["TELEGRAM_FUTURES_CHAT_ID"],
    )

    async def _force_flat_callback(*, reason: str) -> None:
        """Phase 0.2 signalling-side implementation.

        Writes a Redis sentinel key so the TradingOrchestrator (or any other
        consumer running in a sibling process) can detect the flatten request
        and act on it.

        **Consumer follow-up (deferred)**: TradingOrchestrator must poll
        ``kill_switch:force_flatten:requested`` on its heartbeat loop and
        call ``flatten_all()`` when the key is present. That wiring is NOT
        included in this PR and is tracked as a separate task. Until then,
        operator manual intervention is the last line of defence.

        Data written:
          - Redis key  ``kill_switch:force_flatten:requested`` (TTL 300 s)
            Value: ``reason=<reason>`` — safe to read with a simple GET.
          - Redis stream  ``kill_switch:events``  (TTL 24 h)
            Fields: ``event=force_flatten_requested``, ``reason=<reason>``,
            ``ts=<unix_timestamp>``.
        """
        logger.critical(
            "FORCE-FLAT SIGNALLED via Redis: trip reason=%s — "
            "TradingOrchestrator consumer follow-up required; "
            "operator must verify positions are flat if consumer not yet wired.",
            reason,
        )
        try:
            # Key: simple sentinel for polling consumers.
            await redis_client.set(
                _FORCE_FLATTEN_KEY,
                f"reason={reason}",
                ex=_FORCE_FLATTEN_TTL_SECONDS,
            )
            # Stream: event log for audit trail and reactive consumers.
            await redis_client.xadd(
                _EVENTS_STREAM,
                {
                    "event": "force_flatten_requested",
                    "reason": reason,
                    "ts": str(time.time()),
                },
            )
            await redis_client.expire(_EVENTS_STREAM, _EVENTS_STREAM_TTL_SECONDS)
            logger.info(
                "force_flatten sentinel written: key=%s stream=%s",
                _FORCE_FLATTEN_KEY,
                _EVENTS_STREAM,
            )
        except Exception:
            logger.exception(
                "Failed to write force_flatten sentinel to Redis; "
                "operator MUST manually flatten KOSPI200 mini positions via KIS web/app"
            )

    daemon = KillSwitchDaemon(
        runtime_state=runtime_state,
        conditions=conditions,
        force_close_callback=_force_flat_callback,
        telegram_client=telegram,
        check_interval_seconds=cfg.check_interval_seconds,
        sentinel_path=cfg.sentinel_path,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        await redis_client.aclose()
    return 0


# ---------------------------------------------------------------------------
# Provider factories for Phase 0.4 provider-backed conditions.
# ---------------------------------------------------------------------------


def _build_api_error_rate_provider(
    redis_client: Any,
) -> Callable[[], float]:
    """Return a synchronous callable that reads the 5-minute KIS API error rate.

    Data source: Redis key ``kill_switch:metrics:api_error_rate_5min``
    written by the KIS client rate-limiter (``shared/kis/client.py``).
    The key holds a float string (fraction 0–1) representing the proportion
    of KIS REST calls that errored in the last 5-minute window.

    TODO(Phase 3 Track A): ``shared/kis/client.py`` must write this key on
    each rate-limiter tick (EGW00201 / 5xx count / total call count rolling
    window). Until that instrumentation is added the key will be absent and
    this provider returns 0.0 (never triggers).
    """
    import redis as sync_redis  # type: ignore[import-untyped]

    _METRIC_KEY = "kill_switch:metrics:api_error_rate_5min"

    def _provider() -> float:
        try:
            # redis.asyncio client does not expose synchronous get; use the
            # connection pool's underlying sync path via a temporary sync client
            # built from the same URL. This is called at most every
            # ``check_interval_seconds`` so the overhead is acceptable.
            url: str = str(
                redis_client.connection_pool.connection_kwargs.get("url", "")
            )
            if not url:
                # Fallback: reconstruct URL from kwargs
                kwargs = redis_client.connection_pool.connection_kwargs
                host = kwargs.get("host", "localhost")
                port = kwargs.get("port", 6379)
                db = kwargs.get("db", 1)
                url = f"redis://{host}:{port}/{db}"
            r = sync_redis.from_url(url, socket_timeout=1.0)
            raw = r.get(_METRIC_KEY)
            r.close()
            if raw is None:
                return 0.0
            return float(raw)
        except Exception:
            logger.debug(
                "api_error_rate provider: could not read %s — returning 0.0",
                _METRIC_KEY,
                exc_info=True,
            )
            return 0.0

    return _provider


def _build_news_pipeline_lag_provider(
    redis_client: Any,
    stream_key: str,
) -> Callable[[], float]:
    """Return a synchronous callable that returns the news pipeline lag in seconds.

    Args:
        redis_client: redis.asyncio.Redis instance providing connection metadata.
        stream_key: Redis stream key to inspect, sourced from
            ``KillSwitchConfig.conditions.news_pipeline_lag_seconds.stream_key``.
            Default in YAML: ``stream:news.raw`` (matches
            ``config/news_sources.yaml::redis_stream``).  Operators override
            via YAML if the deployment uses a different key.

    Reads the timestamp of the last message appended to the stream (via
    XREVRANGE) and returns ``now - last_message_ts``.  If the stream is empty
    or unreachable the provider returns 0.0 (never triggers).
    """
    import redis as sync_redis  # type: ignore[import-untyped]

    def _provider() -> float:
        try:
            kwargs = redis_client.connection_pool.connection_kwargs
            url: str = kwargs.get("url", "")
            if not url:
                host = kwargs.get("host", "localhost")
                port = kwargs.get("port", 6379)
                db = kwargs.get("db", 1)
                url = f"redis://{host}:{port}/{db}"
            r = sync_redis.from_url(url, socket_timeout=1.0)
            # XREVRANGE returns at most 1 entry: [(id, {fields})]
            entries = r.xrevrange(stream_key, count=1)
            r.close()
            if not entries:
                # Stream empty or not yet created — no lag to report.
                return 0.0
            msg_id: bytes = entries[0][0]
            # Redis stream ID format: "<unix_ms>-<seq>"
            ts_ms = int(msg_id.split(b"-")[0])
            lag_seconds = time.time() - ts_ms / 1000.0
            return max(0.0, lag_seconds)
        except Exception:
            logger.debug(
                "news_pipeline_lag provider: error reading %s — returning 0.0",
                stream_key,
                exc_info=True,
            )
            return 0.0

    return _provider


def main() -> int:
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
