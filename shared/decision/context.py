"""MarketContext + ScheduledEvent dataclasses + YAML loader."""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import yaml

if TYPE_CHECKING:
    pass

KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class ScheduledEvent:
    """A macro calendar event that may influence trading decisions."""

    event_id: str
    event_type: str
    scheduled_at: datetime  # tz-aware
    impact_tier: int  # 1 = top tier, 3 = minor


@dataclass(frozen=True)
class MarketContext:
    """Aggregated market state snapshot consumed by signal generators."""

    now: datetime  # KST
    symbol: str  # e.g. "A05603" — mini front-month
    current_price: float
    prev_close: float
    today_open: float
    vwap: float
    atr_14: float
    atr_90th_percentile: float  # 60-day rolling percentile (backtest warmup)
    last_15min_high: float
    last_15min_low: float
    current_spread_ticks: float
    macro_overnight: object | None  # MacroSnapshot | None
    scheduled_events: list[ScheduledEvent]  # recent / upcoming macro events

    # Configured regular-session open (hour/minute KST).
    # Defaults to 08:45 — the KRX futures day-session open.
    # Set explicitly by context builders that load market_schedule.yaml.
    # Stock strategies that rely on the 09:00 open can override these fields.
    market_open_hour: int = 8
    market_open_minute: int = 45

    def market_open_time(self) -> datetime:
        """Return the configured market open time (KST) on the same date as ``self.now``."""
        return datetime(
            self.now.year,
            self.now.month,
            self.now.day,
            self.market_open_hour,
            self.market_open_minute,
            tzinfo=KST,
        )

    def minutes_since_open(self) -> float:
        """Elapsed minutes since today's configured market open (KST)."""
        return (self.now - self.market_open_time()).total_seconds() / 60

    def find_recent_event(
        self,
        window_minutes: float,
        min_tier: int,
    ) -> ScheduledEvent | None:
        """Return the most recent qualifying ScheduledEvent, or None.

        Qualifying criteria:
        - ``scheduled_at <= self.now``  (event has already occurred)
        - elapsed minutes since event ``<= window_minutes``
        - ``impact_tier <= min_tier``  (tier 1 is top; lower = higher impact)
        """
        best: ScheduledEvent | None = None
        best_elapsed: float = float("inf")

        for evt in self.scheduled_events:
            if evt.scheduled_at > self.now:
                continue
            elapsed = (self.now - evt.scheduled_at).total_seconds() / 60
            if elapsed > window_minutes:
                continue
            if evt.impact_tier > min_tier:
                continue
            if elapsed < best_elapsed:
                best = evt
                best_elapsed = elapsed

        return best


#: Canonical ``MarketContext`` field names — the single source of truth for the
#: live↔replay field-fill parity contract. Because it derives from
#: :func:`dataclasses.fields`, adding a field to :class:`MarketContext`
#: automatically extends this tuple, which makes the parity contract
#: (``tests/unit/decision/test_market_context_parity.py``) fail until BOTH
#: producers explicitly populate the new field:
#:   * the canonical assembler :func:`build_market_context` (a named parameter), and
#:   * the backtest replay
#:     :class:`shared.backtest.market_context_replay.MarketContextReplay`
#:     (a keyword in its direct ``MarketContext(...)`` construction).
#: This is the structural guard against the #533/#537 class of silent
#: field-fill divergence (a field that one producer computes and the other
#: silently leaves at its dataclass default).
MARKET_CONTEXT_FIELDS: tuple[str, ...] = tuple(f.name for f in fields(MarketContext))


def load_scheduled_events(path: str) -> list[ScheduledEvent]:
    """Parse a ``scheduled_events.yaml`` file and return a list of ScheduledEvent.

    Each event's ``scheduled_at`` is an ISO 8601 string converted to a
    tz-aware ``datetime`` with UTC tzinfo.
    """
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw_events = data.get("events", [])
    events: list[ScheduledEvent] = []
    for item in raw_events:
        scheduled_at_str: str = item["scheduled_at"]
        # Parse ISO 8601; Python 3.11+ fromisoformat handles Z suffix
        dt = datetime.fromisoformat(scheduled_at_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        events.append(
            ScheduledEvent(
                event_id=item["event_id"],
                event_type=item["event_type"],
                scheduled_at=dt,
                impact_tier=int(item["impact_tier"]),
            )
        )
    return events


_FUTURES_OPEN_CACHE: dict[str, tuple[int, int]] = {}


def _load_futures_open_from_config(
    config_path: str = "config/market_schedule.yaml",
) -> tuple[int, int]:
    """Read ``market_schedule.futures.regular.open`` and return (hour, minute).

    Result is cached per *config_path* after the first successful read so
    per-tick callers (setup_adapters._build_market_context) pay the I/O cost
    only once per process lifetime.  Returns the 08:45 default if the config
    is missing or unparseable so callers always get a safe value without raising.
    """
    _DEFAULT = (8, 45)
    if config_path in _FUTURES_OPEN_CACHE:
        return _FUTURES_OPEN_CACHE[config_path]
    try:
        path = Path(config_path)
        if not path.exists():
            return _DEFAULT
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        open_str: str | None = (
            data.get("market_schedule", {})
            .get("futures", {})
            .get("regular", {})
            .get("open")
        )
        if not open_str:
            return _DEFAULT
        parts = str(open_str).strip().split(":")
        if len(parts) < 2:
            return _DEFAULT
        result: tuple[int, int] = (int(parts[0]), int(parts[1]))
        _FUTURES_OPEN_CACHE[config_path] = result
        return result
    except Exception:  # noqa: BLE001
        return _DEFAULT


def _reset_futures_open_cache() -> None:
    """Clear the cached futures-open lookups.

    Intended for test isolation: an autouse fixture clears this between tests so
    a value cached by one test (e.g. via a temp config path) cannot leak into
    another, especially under pytest-xdist where module-level state is shared
    within a worker process.
    """
    _FUTURES_OPEN_CACHE.clear()


def build_market_context(
    *,
    now: datetime,
    symbol: str,
    current_price: float,
    prev_close: float,
    today_open: float,
    atr_14: float,
    last_15min_high: float,
    last_15min_low: float,
    vwap: float | None = None,
    atr_90th_percentile: float | None = None,
    current_spread_ticks: float | None = None,
    macro_overnight: object | None = None,
    scheduled_events: list[ScheduledEvent] | None = None,
    market_open_hour: int | None = None,
    market_open_minute: int | None = None,
    config_path: str = "config/market_schedule.yaml",
) -> MarketContext:
    """Assemble a MarketContext with the canonical default policy (F-4).

    Setup A and Setup C read NONE of ``vwap`` / ``atr_90th_percentile`` /
    ``current_spread_ticks`` (locked by the F-4 invariance test). They are
    assembled here with shared defaults so the decoupled (decision_engine) and
    orchestrator (setup_adapters) builders stay consistent: vwap→current_price,
    atr_90th→atr_14*1.5, spread→1.0. ``current_spread_ticks`` is uncomputable
    from the OHLCV-only tick stream, so the decoupled path always defaults it.

    ⚠ F-9 PRECONDITION — ``vwap`` is intentionally still optional (fallback
    ``vwap := current_price``). Setup D (VWAP reversion) DOES read vwap; on the
    decoupled ``FuturesContextProvider`` (which omits vwap) the fallback makes
    Setup D's ``z = (price - vwap)/atr`` collapse to 0 → Setup D silently inert.
    This is dormant today (futures trade the orchestrator path, which threads a
    real vwap). Before the F-9 decoupled cutover, the provider must source a real
    session VWAP (engine ``get_indicators()['vwap']``); only THEN make ``vwap``
    required (drop this fallback) so a future omission is a loud TypeError, not a
    silent #533/#537-class inert. Contract-pinned in
    ``tests/unit/decision/test_market_context_parity.py``.

    ``market_open_hour`` / ``market_open_minute`` set the session open anchor
    used by ``minutes_since_open()``. When omitted they are read from
    ``config/market_schedule.yaml::market_schedule.futures.regular.open``
    (defaults to 08:45 if the config is absent or the key is missing).
    Pass them explicitly to avoid the file I/O when the caller already has the
    values (e.g. the orchestrator builds from its loaded ``MarketSchedule``).
    """
    if market_open_hour is None or market_open_minute is None:
        cfg_hour, cfg_minute = _load_futures_open_from_config(config_path)
        if market_open_hour is None:
            market_open_hour = cfg_hour
        if market_open_minute is None:
            market_open_minute = cfg_minute

    return MarketContext(
        now=now,
        symbol=symbol,
        current_price=current_price,
        prev_close=prev_close,
        today_open=today_open,
        vwap=vwap if vwap is not None else current_price,
        atr_14=atr_14,
        atr_90th_percentile=(
            atr_90th_percentile if atr_90th_percentile is not None else atr_14 * 1.5
        ),
        last_15min_high=last_15min_high,
        last_15min_low=last_15min_low,
        current_spread_ticks=(
            current_spread_ticks if current_spread_ticks is not None else 1.0
        ),
        macro_overnight=macro_overnight,
        scheduled_events=list(scheduled_events) if scheduled_events else [],
        market_open_hour=market_open_hour,
        market_open_minute=market_open_minute,
    )
