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
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from shared.risk.runtime_state import RuntimeRiskState

logger = logging.getLogger(__name__)


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

    def check(self, *, snapshot: Any) -> bool:
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


class ClickHouseInsertFailCondition(_ProviderBackedCondition):
    name = "clickhouse_insert_fail_rate"

    def __init__(self, *, threshold: float, rate_provider: Callable[[], float]) -> None:
        super().__init__(threshold=threshold, provider=rate_provider)


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
