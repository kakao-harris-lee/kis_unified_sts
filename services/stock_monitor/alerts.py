"""Selective, important-only Telegram alerting for the stock monitor bridge.

Policy (spec §7): NO per-fill alerts. Only:
  1. notable exit  — |pnl%| >= pnl_alert_pct
  2. health anomaly — emitted by the daemon (cooldown-gated) via send_health()
  3. session digest — one aggregate per day via emit_digest()

In ``shadow`` mode nothing is sent; each alert-worthy event logs one
``would-alert`` line (so even the logs are not per-fill noise). In ``live``
mode the wrapped notifier is used.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SessionDigest:
    """Accumulates one trading session's realized results for the daily digest."""

    trades: int = 0
    realized_pnl: float = 0.0
    wins: int = 0

    def add(self, *, pnl: float) -> None:
        self.trades += 1
        self.realized_pnl += pnl
        if pnl > 0:
            self.wins += 1

    def reset(self) -> None:
        self.trades = 0
        self.realized_pnl = 0.0
        self.wins = 0


class AlertSink:
    """Decides + dispatches important-only alerts (send in live, log in shadow)."""

    def __init__(
        self,
        *,
        notifier: Any | None,
        mode: str,
        pnl_alert_pct: float,
    ) -> None:
        if mode not in ("live", "shadow"):
            raise ValueError(f"AlertSink: unknown mode {mode!r}")
        self.notifier = notifier
        self.mode = mode
        self.pnl_alert_pct = pnl_alert_pct
        self.digest = SessionDigest()

    async def _dispatch(self, message: str) -> None:
        if self.mode == "live" and self.notifier is not None:
            try:
                await self.notifier.send_message(message)
            except Exception:
                logger.warning("telegram send failed", exc_info=True)
        else:
            logger.info("would-alert: %s", message.replace("\n", " | "))

    async def on_entry(self, **_: Any) -> None:
        """Entries are routine — never alerted (digest counts them at exit)."""
        return None

    async def on_exit(self, *, code: str, pnl: float, pnl_pct: float) -> None:
        self.digest.add(pnl=pnl)  # every exit counts toward the daily digest
        if abs(pnl_pct) < self.pnl_alert_pct:
            return  # routine exit -> digest only, no alert
        icon = "🟢" if pnl >= 0 else "🔴"
        await self._dispatch(
            f"{icon} <b>주목 청산</b> {code}\nPnL {pnl:,.0f}원 ({pnl_pct:+.2f}%)"
        )

    async def send_health(self, message: str) -> None:
        await self._dispatch(f"⚠️ <b>헬스 이상</b>\n{message}")

    async def emit_digest(self, *, open_count: int) -> None:
        """Emit the session digest. Pure emitter — no side effects.

        Does NOT reset the accumulator. The daemon owns the once-per-day emit
        guard and the daily ``self.digest.reset()`` (at 09:00 KST), keeping this
        method side-effect-free and safe to call without mutating state.
        """
        d = self.digest
        win_rate = (d.wins / d.trades * 100) if d.trades else 0.0
        await self._dispatch(
            f"📊 <b>세션 다이제스트</b>\n"
            f"거래 {d.trades}건 · 실현 {d.realized_pnl:,.0f}원 · "
            f"승률 {win_rate:.0f}% · 미청산 {open_count}건"
        )
