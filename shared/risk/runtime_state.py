"""Runtime mutating risk state for Phase 4 daemons.

Phase 3's :class:`shared.risk.state.RiskStateSnapshot` is a read-only view
constructed for each filter evaluation. The Phase 4 daemons (order_router
fill handler + kill_switch monitor) need higher-level operations:

  * record a closed trade — accumulates daily/weekly/monthly PnL and trade count
  * record a loss/win — drives the consecutive-loss counter
  * reset_daily — zeros the daily counters at the 09:00 KST session start
  * should_reset_daily — calendar-day boundary check

This wraps the existing Phase 3 :class:`RiskStateStore` Redis HASH writer and
adds two sibling HASHes:

  * ``risk:state:{asset_class}:meta`` — daily-reset bookkeeping
    (``last_reset_date_kst``).
  * ``risk:state:{asset_class}:period`` — calendar-window accumulations
    (Phase 3C, design spec §4.2/§4.3 Track C survival rules):

      - ``weekly_pnl_krw``  + ``week_anchor``  — resets at the KST Monday
        00:00 boundary (C5: replaces the old implicit reliance on the main
        HASH's 24 h idle TTL).
      - ``monthly_pnl_krw`` + ``month_anchor`` — resets at the KST
        1st-of-month 00:00 boundary (C1: feeds the kill-switch
        ``monthly_loss`` latch, which must hold until month end).
      - ``size_reduce_until_kst`` — end of the consecutive-loss soft
        size-reduction window (C2: streak reaching the soft threshold opens
        a ``soft_reduce_persist_days`` window during which the x0.5
        reduction persists even through wins and process restarts).

    Boundary resets are **anchor-based and lazy**: readers zero a window
    whose stored anchor no longer matches the current KST week/month; only
    the recording writer persists the rollover. The ``:period`` TTL is
    recomputed on every write to cover the remainder of the current KST
    month (plus a grace window) and the soft-reduce window — it must never
    depend on the main HASH's 24 h TTL, otherwise the monthly kill-switch
    latch could silently expire before month end.

Each operation does load → mutate → save. Multi-writer atomicity isn't
guaranteed. Trade/loss/win accumulation still has a single writer (the
order_router / exit daemon), and kill_switch stays a pure reader via
:meth:`RuntimeRiskState.snapshot`. The daily-counter reset is the one path
with more than one writer: both the in-process ``stock_risk_filter``
day-boundary hook (KST midnight, per consume cycle) and the M5c
``scripts/maintenance/daily_risk_reset.py`` cron (08:59 KST) may call
:meth:`reset_daily` on ``risk:state:{asset}``. That stays safe without
WATCH/Lua because :meth:`should_reset_daily` gates every reset on the
``:meta`` ``last_reset_date_kst`` stamp — the second writer for a given KST
date is a no-op, and even a rare concurrent double reset only re-zeros
already-zero daily counters.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from shared.risk.state import RiskStateSnapshot, RiskStateStore

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")

_META_TTL_SECONDS = 86400 * 7  # 7-day rolling window covers KR holidays.
# Grace added on top of the computed period horizon (month end / soft-reduce
# window end) so the state comfortably survives clock skew and late reads.
_PERIOD_TTL_GRACE_SECONDS = 86400 * 7


def _week_anchor(d: date) -> str:
    """ISO date of the KST Monday that starts the week containing *d*."""
    return (d - timedelta(days=d.weekday())).isoformat()


def _month_anchor(d: date) -> str:
    """``YYYY-MM`` anchor of the KST month containing *d*."""
    return f"{d.year:04d}-{d.month:02d}"


def _next_month_start_kst(now_kst: datetime) -> datetime:
    """00:00 KST on the 1st of the month after *now_kst* (the monthly boundary)."""
    d = now_kst.date()
    first = date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)
    return datetime.combine(first, time.min, tzinfo=_KST)


def _as_kst(dt: datetime) -> datetime:
    """Coerce *dt* to an aware KST datetime (naive input is assumed KST)."""
    return dt.astimezone(_KST) if dt.tzinfo else dt.replace(tzinfo=_KST)


def _decode(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        return value.decode()
    return str(value)


@dataclass
class _PeriodState:
    """In-memory view of the ``risk:state:{asset_class}:period`` HASH."""

    weekly_pnl_krw: float = 0.0
    monthly_pnl_krw: float = 0.0
    week_anchor: str = ""
    month_anchor: str = ""
    size_reduce_until_kst: str = ""


class RuntimeRiskState:
    def __init__(
        self,
        *,
        redis: Any,
        asset_class: str = "futures",
        key_suffix: str = "",
        clock: Callable[[], datetime] | None = None,
        consecutive_loss_soft_threshold: int | None = None,
        soft_reduce_persist_days: int | None = None,
    ) -> None:
        """Args:
        redis: Async Redis client (``redis.asyncio`` / fakeredis compatible).
        asset_class: ``"futures"`` or ``"stock"`` — also selects which
            ``config/risk.yaml`` section supplies the soft-reduce parameters
            when the explicit overrides below are ``None``.
        key_suffix: Isolates a shadow/paper run's risk-state from live (F-1).
            Default "" → identical keys to before.
        clock: Injectable KST "now" provider (tests). Defaults to
            ``datetime.now(KST)``.
        consecutive_loss_soft_threshold: Override for the consecutive-loss
            soft threshold; ``None`` → loaded from ``config/risk.yaml``.
        soft_reduce_persist_days: Override for the soft-reduction persistence
            window in days (design spec §4.2: 14). ``0`` disables persistence
            (legacy behaviour: reduction ends on the first win). ``None`` →
            loaded from ``config/risk.yaml``.
        """
        self._redis = redis
        self._asset_class = asset_class
        # key_suffix isolates a shadow/paper run's risk-state from live
        # (F-1). Default "" → identical keys to before (stock + all existing
        # callers unaffected). Colon-delimited to match the key convention.
        suffix = f":{key_suffix}" if key_suffix else ""
        self._risk_state = RiskStateStore(
            redis, asset_class, key=f"risk:state:{asset_class}{suffix}"
        )
        self._meta_key = f"risk:state:{asset_class}{suffix}:meta"
        self._period_key = f"risk:state:{asset_class}{suffix}:period"
        self._clock = clock if clock is not None else (lambda: datetime.now(_KST))
        self._soft_threshold_override = consecutive_loss_soft_threshold
        self._persist_days_override = soft_reduce_persist_days
        self._soft_params: tuple[int, int] | None = None

    # ------------------------------------------------------------------
    # Read path (never writes — risk_filter / kill_switch stay pure readers)
    # ------------------------------------------------------------------

    async def snapshot(self) -> RiskStateSnapshot:
        snap = await self._risk_state.load()
        period = await self._load_period()
        if period is None:
            # Pre-``:period`` state (migration): the main-HASH weekly value is
            # the best available accumulation for both calendar windows.
            snap.monthly_pnl_krw = snap.weekly_pnl_krw
            return snap
        effective = self._rollover(period, self._now_kst())
        snap.weekly_pnl_krw = effective.weekly_pnl_krw
        snap.monthly_pnl_krw = effective.monthly_pnl_krw
        snap.size_reduce_until_kst = effective.size_reduce_until_kst
        return snap

    # ------------------------------------------------------------------
    # Write path (single writer: the order_router / exit daemon)
    # ------------------------------------------------------------------

    async def record_trade(
        self, *, pnl_krw: float, now_kst: datetime | None = None
    ) -> None:
        now = _as_kst(now_kst) if now_kst is not None else self._now_kst()
        snap = await self._risk_state.load()
        pre_weekly = snap.weekly_pnl_krw
        snap.daily_pnl_krw += pnl_krw
        snap.weekly_pnl_krw += pnl_krw
        snap.daily_trade_count += 1
        await self._risk_state.save(snap)

        period = await self._load_period()
        if period is None:
            # First write after migration: seed both windows from the
            # main-HASH weekly accumulation (best available information;
            # attributed to the current week/month).
            period = _PeriodState(
                weekly_pnl_krw=pre_weekly,
                monthly_pnl_krw=pre_weekly,
                week_anchor=_week_anchor(now.date()),
                month_anchor=_month_anchor(now.date()),
            )
        period = self._rollover(period, now)
        period.weekly_pnl_krw += pnl_krw
        period.monthly_pnl_krw += pnl_krw
        await self._save_period(period, now_kst=now)

    async def record_loss(self, *, now_kst: datetime | None = None) -> None:
        snap = await self._risk_state.load()
        snap.consecutive_losses += 1
        await self._risk_state.save(snap)

        soft_threshold, persist_days = self._soft_reduce_params()
        if persist_days <= 0 or snap.consecutive_losses < soft_threshold:
            return
        # Design spec §4.2 (C2): the streak reached the soft threshold —
        # open (or extend) the x0.5 reduction window. Extension on further
        # losses re-anchors the window at the most recent threshold hit,
        # which is the more conservative reading of "from the moment the
        # streak reaches 4 losses".
        now = _as_kst(now_kst) if now_kst is not None else self._now_kst()
        period = self._rollover(await self._load_period() or _PeriodState(), now)
        new_until = now + timedelta(days=persist_days)
        existing = self._parse_until(period.size_reduce_until_kst)
        if existing is None or new_until > existing:
            period.size_reduce_until_kst = new_until.isoformat()
            await self._save_period(period, now_kst=now)
            logger.warning(
                "consecutive-loss soft-reduce window opened/extended: "
                "asset_class=%s losses=%d until=%s (persist_days=%d)",
                self._asset_class,
                snap.consecutive_losses,
                period.size_reduce_until_kst,
                persist_days,
            )

    async def record_win(self) -> None:
        # Resets the streak counter only. The soft-reduce window
        # (``size_reduce_until_kst``) intentionally survives wins — design
        # spec §4.2 keeps the x0.5 reduction for the full persistence window.
        snap = await self._risk_state.load()
        snap.consecutive_losses = 0
        await self._risk_state.save(snap)

    async def reset_daily(self, *, now_kst: datetime) -> None:
        snap = await self._risk_state.load()
        snap.daily_pnl_krw = 0.0
        snap.daily_trade_count = 0
        await self._risk_state.save(snap)
        await self._redis.hset(
            self._meta_key, "last_reset_date_kst", now_kst.date().isoformat()
        )
        await self._redis.expire(self._meta_key, _META_TTL_SECONDS)

    async def should_reset_daily(self, *, now_kst: datetime) -> bool:
        last = await self._redis.hget(self._meta_key, "last_reset_date_kst")
        if last is None:
            return True
        if isinstance(last, (bytes, bytearray)):
            last = last.decode()
        return last != now_kst.date().isoformat()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _now_kst(self) -> datetime:
        return _as_kst(self._clock())

    def _soft_reduce_params(self) -> tuple[int, int]:
        """Resolve ``(soft_threshold, persist_days)``.

        Constructor overrides win; missing values load lazily from
        ``config/risk.yaml`` (section per asset class), falling back to the
        config class field defaults if the file cannot be read.
        """
        if self._soft_params is not None:
            return self._soft_params
        soft = self._soft_threshold_override
        days = self._persist_days_override
        if soft is None or days is None:
            from shared.risk.config import FuturesRiskConfig, StockRiskConfig

            cfg_cls = (
                StockRiskConfig if self._asset_class == "stock" else FuturesRiskConfig
            )
            try:
                cfg = cfg_cls.from_yaml()
            except Exception:
                logger.warning(
                    "risk config load failed; using %s field defaults",
                    cfg_cls.__name__,
                    exc_info=True,
                )
                cfg = cfg_cls()
            if soft is None:
                soft = cfg.consecutive_loss_soft_threshold
            if days is None:
                days = cfg.soft_reduce_persist_days
        self._soft_params = (int(soft), int(days))
        return self._soft_params

    async def _load_period(self) -> _PeriodState | None:
        raw: dict[Any, Any] = await self._redis.hgetall(self._period_key)
        if not raw:
            return None
        decoded = {_decode(k): _decode(v) for k, v in raw.items()}
        return _PeriodState(
            weekly_pnl_krw=float(decoded.get("weekly_pnl_krw", 0.0) or 0.0),
            monthly_pnl_krw=float(decoded.get("monthly_pnl_krw", 0.0) or 0.0),
            week_anchor=decoded.get("week_anchor", ""),
            month_anchor=decoded.get("month_anchor", ""),
            size_reduce_until_kst=decoded.get("size_reduce_until_kst", ""),
        )

    @staticmethod
    def _rollover(period: _PeriodState, now_kst: datetime) -> _PeriodState:
        """Apply KST calendar-boundary resets, returning a fresh view.

        A window whose stored anchor differs from the current week/month
        anchor restarts at zero. The soft-reduce window is purely
        time-based (independent of calendar boundaries) and passes through.
        """
        week = _week_anchor(now_kst.date())
        month = _month_anchor(now_kst.date())
        return _PeriodState(
            weekly_pnl_krw=(
                period.weekly_pnl_krw if period.week_anchor == week else 0.0
            ),
            monthly_pnl_krw=(
                period.monthly_pnl_krw if period.month_anchor == month else 0.0
            ),
            week_anchor=week,
            month_anchor=month,
            size_reduce_until_kst=period.size_reduce_until_kst,
        )

    @staticmethod
    def _parse_until(raw: str) -> datetime | None:
        if not raw:
            return None
        try:
            return _as_kst(datetime.fromisoformat(raw))
        except ValueError:
            logger.warning("unparseable size_reduce_until_kst=%r; ignoring", raw)
            return None

    def _period_ttl_seconds(self, period: _PeriodState, now_kst: datetime) -> int:
        horizon = _next_month_start_kst(now_kst)
        until = self._parse_until(period.size_reduce_until_kst)
        if until is not None and until > horizon:
            horizon = until
        remaining = int((horizon - now_kst).total_seconds())
        return max(remaining, 0) + _PERIOD_TTL_GRACE_SECONDS

    async def _save_period(self, period: _PeriodState, *, now_kst: datetime) -> None:
        mapping = {
            "weekly_pnl_krw": str(period.weekly_pnl_krw),
            "monthly_pnl_krw": str(period.monthly_pnl_krw),
            "week_anchor": period.week_anchor,
            "month_anchor": period.month_anchor,
            "size_reduce_until_kst": period.size_reduce_until_kst,
        }
        await self._redis.hset(self._period_key, mapping=mapping)
        # TTL must always cover the remainder of the current KST month (C1
        # monthly latch) and any open soft-reduce window (C2) — never the
        # default 24 h operational TTL.
        await self._redis.expire(
            self._period_key, self._period_ttl_seconds(period, now_kst)
        )
