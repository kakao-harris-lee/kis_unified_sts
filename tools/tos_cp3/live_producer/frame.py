"""Bar completion on RAW rows, the frozen frame, and the window-filled seed."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from shared.collector.historical.ohlcv_parser import parse_ohlcv
from tools.tos_cp3.live_producer.calendar import RuntimeCalendar
from tools.tos_cp3.live_producer.config import LiveProducerRefused
from tools.tos_cp3.minute_probe import frame as bars_to_frame
from tools.tos_cp3.minute_probe import seed_capacity
from tools.tos_cp3.produce_fields import OpenAnchor, StrategyInputs
from tools.tos_cp3.quote_client import raw_stamp

Bar = tuple

FetchDay = Callable[[date, str], list[dict]]


def raw_minute(row: dict, day: date) -> datetime | None:
    """The row's naive-KST minute, or ``None`` when it belongs to another day."""
    stamp = raw_stamp(row, day)
    if stamp is None:
        return None
    return stamp.replace(tzinfo=None, second=0, microsecond=0)


@dataclass(frozen=True)
class FreezeStep:
    """What one poll's raw rows add to the frozen frame."""

    newly_frozen: tuple[Bar, ...]
    deferred: tuple[datetime, ...]
    newest_raw_minute: datetime | None
    oldest_raw_minute: datetime | None
    raw_minutes: frozenset[datetime] = frozenset()

    @property
    def published(self) -> Bar | None:
        return self.newly_frozen[-1] if self.newly_frozen else None

    @property
    def skipped_behind(self) -> tuple[Bar, ...]:
        """Bars frozen in this step that are NOT published."""
        return self.newly_frozen[:-1]


def freeze_step(
    raw_rows: Sequence[dict],
    *,
    day: date,
    symbol: str,
    last_frozen_minute: datetime | None,
    session_ended: bool,
) -> FreezeStep:
    """Parse only what is newer than *last_frozen_minute* and split by completion."""
    minutes = sorted(
        {
            minute
            for minute in (raw_minute(row, day) for row in raw_rows)
            if minute is not None
        }
    )
    if not minutes:
        return FreezeStep((), (), None, None, frozenset())
    newest, oldest = minutes[-1], minutes[0]

    fresh = [
        row
        for row in raw_rows
        if (minute := raw_minute(row, day)) is not None
        and (last_frozen_minute is None or minute > last_frozen_minute)
    ]
    parsed = parse_ohlcv(symbol, day.strftime("%Y%m%d"), {"output2": fresh})
    complete = tuple(bar for bar in parsed if bar[1] < newest or session_ended)
    deferred = tuple(bar[1] for bar in parsed if not (bar[1] < newest or session_ended))
    return FreezeStep(complete, deferred, newest, oldest, frozenset(minutes))


SEED_DROP_NO_RAW_ROWS = "no_raw_rows"
SEED_DROP_DENSITY = "density"


@dataclass(frozen=True)
class SeedSession:
    """One walked trading day, and why it was kept or dropped."""

    day: date
    contract: str
    raw_rows: int
    parsed_rows: int
    density_pass: bool

    @property
    def drop_reason(self) -> str | None:
        """``None`` when kept, else :data:`SEED_DROP_NO_RAW_ROWS`/``_DENSITY``."""
        if self.density_pass:
            return None
        return SEED_DROP_NO_RAW_ROWS if self.raw_rows == 0 else SEED_DROP_DENSITY


@dataclass(frozen=True)
class SeedDay:
    """One KEPT seed day: which contract it was requested on, and its bars."""

    day: date
    contract: str
    bars: tuple[Bar, ...]


SeedAssembler = Callable[[date, Sequence["SeedDay"]], tuple[str, Any]]


def same_contract_seed(
    day: date, kept: Sequence[SeedDay], *, instrument: str
) -> tuple[str, Any]:
    """The seed rule plan §3.2 specifies: ONE contract, the one being traded."""
    ordered = sorted(kept, key=lambda entry: entry.day)
    return instrument, bars_to_frame([bar for entry in ordered for bar in entry.bars])


def assembled_bars(frame: Any) -> tuple[Bar, ...]:
    """The assembler's frame back in ``parse_ohlcv`` tuple shape."""
    return tuple(
        (
            row[0],
            row[1].to_pydatetime(),
            float(row[2]),
            float(row[3]),
            float(row[4]),
            float(row[5]),
            int(row[6]),
        )
        for row in frame.itertuples(index=False, name=None)
    )


@dataclass(frozen=True)
class Seed:
    """The seed frame plus the lineage of how it was assembled."""

    frame: Any
    bars: tuple[Bar, ...]
    sessions: tuple[SeedSession, ...]
    days_used: tuple[date, ...]
    contracts_used: tuple[str, ...]
    capacity: int
    required: int
    min_bars_per_day: int
    kept: tuple[SeedDay, ...] = ()


def build_seed(
    *,
    target: date,
    calendar: RuntimeCalendar,
    strategy: StrategyInputs,
    anchor: OpenAnchor,
    min_bars_per_day: int,
    max_calendar_days: int,
    fetch_day: FetchDay,
    assembler: SeedAssembler,
) -> Seed:
    """Walk trading days backwards until the causal vol window is FILLED."""
    required = int(strategy.entry_config.vol_window_bars)
    sessions: list[SeedSession] = []
    kept: list[SeedDay] = []

    for day in calendar.trading_days_before(
        target, max_calendar_days=max_calendar_days
    ):
        contract, _frame = assembler(day, kept)
        rows = fetch_day(day, contract)
        parsed = parse_ohlcv(contract, day.strftime("%Y%m%d"), {"output2": rows})
        density_pass = len(parsed) >= min_bars_per_day
        sessions.append(
            SeedSession(
                day=day,
                contract=contract,
                raw_rows=len(rows),
                parsed_rows=len(parsed),
                density_pass=density_pass,
            )
        )
        if not density_pass:
            continue
        kept.append(SeedDay(day=day, contract=contract, bars=tuple(parsed)))
        _next_contract, frame = assembler(day, kept)
        capacity = seed_capacity(frame, strategy, anchor)
        if capacity >= required:
            return _filled_seed(
                frame=frame,
                kept=kept,
                sessions=sessions,
                capacity=capacity,
                required=required,
                min_bars_per_day=min_bars_per_day,
            )

    raise _unfilled_seed_refusal(
        target=target,
        sessions=tuple(sessions),
        required=required,
        min_bars_per_day=min_bars_per_day,
    )


def _filled_seed(
    *,
    frame: Any,
    kept: Sequence[SeedDay],
    sessions: Sequence[SeedSession],
    capacity: int,
    required: int,
    min_bars_per_day: int,
) -> Seed:
    """Pack the walk's result. Separate so :func:`build_seed` stays in budget."""
    ordered = sorted(kept, key=lambda entry: entry.day)
    return Seed(
        frame=frame,
        bars=assembled_bars(frame),
        sessions=tuple(sessions),
        days_used=tuple(entry.day for entry in ordered),
        contracts_used=tuple(dict.fromkeys(entry.contract for entry in ordered)),
        capacity=capacity,
        required=required,
        min_bars_per_day=min_bars_per_day,
        kept=tuple(ordered),
    )


def _unfilled_seed_refusal(
    *,
    target: date,
    sessions: Sequence[SeedSession],
    required: int,
    min_bars_per_day: int,
) -> LiveProducerRefused:
    """The refusal :func:`build_seed` raises, with the walk's own numbers in it."""
    walked = [session.day for session in sessions]
    empty = sum(1 for s in sessions if s.drop_reason == SEED_DROP_NO_RAW_ROWS)
    thin = sum(1 for s in sessions if s.drop_reason == SEED_DROP_DENSITY)
    return LiveProducerRefused(
        f"seed window not filled before {target}: "
        f"{len(walked)} trading day(s) walked back to "
        f"{min(walked) if walked else 'none'}, "
        f"{sum(1 for s in sessions if s.density_pass)} passed the "
        f"{min_bars_per_day}-bar density gate "
        f"({empty} returned no rows at all, {thin} were too thin), and the "
        f"causal vol window needs {required} in-entry-window bars. Refusing to "
        "start: a short seed makes hi_vol's percentile differ from B1a's, so "
        "the real-time and offline lines for the same bar would not match "
        "(plan §3.2). With the SAME-contract assembler the post-roll blackout "
        "this produces is INTENDED behaviour, not a defect; its disposition — "
        "plan §3.2a's cross-contract stitching — shipped in PR-2b, so reaching "
        "this message with the stitched assembler means the window could not "
        "be filled even ACROSS the roll. ⚠ A day the calendar calls a "
        "trading day that returned NO rows may be a holiday the calendar is "
        "missing; that is why it is counted separately above"
    )
