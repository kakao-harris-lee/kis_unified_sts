"""Bar completion on RAW rows, the frozen frame, and the window-filled seed.

**Completion is judged on raw rows, never on parsed bars** (plan §3.3 M5). A
successor minute whose volume is below ``KIS_MINUTE_BAR_MIN_VOLUME`` is dropped
by ``parse_ohlcv``, so a parsed-row rule would leave bar ``m`` forever
incomplete. The rule here, with both relaxations the PR-1 evidence forced:

    bar ``m`` is complete  ⟺  a raw row exists at a minute STRICTLY LATER than
    ``m``   OR   the session end time has elapsed.

Both clauses are load-bearing and neither subsumes the other — measured on
2026-10-12 (evidence §1.6, §2.2):

* **15:34** has no 15:35 successor (15:35-15:44 produced no raw rows at all),
  so the plan's literal ``m+1`` rule would skip it. The widened "any strictly
  later raw row" clause completes it when the 15:45 row arrives.
* **15:45** is the session's last minute; no later row can ever exist. Only the
  session-end clause completes it, and the session window comes from the
  runtime calendar, not a literal.

**Freezing** (plan §3.3): ``parse_ohlcv``'s ``_resolve_minute_bars`` picks its
continuity anchor from the WHOLE response, so re-parsing a growing intraday day
can change bars that were already published. A completed bar is therefore
frozen and never re-parsed; each poll parses only the rows newer than the last
frozen bar. The PR-1 evidence §5.1 measured the cost of not doing this: the
same day re-parsed from accumulated intraday responses yields 217 bars instead
of 411.

⚠ Known cost (plan §3.3, v2 review L2): on a one- or two-row batch the anchor
is chosen from those rows themselves, so a lone phantom row supports itself.
Parity is preserved — B1a reads the SAME frozen frame (§3.6) — but the data
quality filter is weaker. The disposition if it bites is to pass K previously
frozen bars along as context.
"""

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

#: One parsed bar, as ``parse_ohlcv`` returns it:
#: ``(code, naive-KST minute, open, high, low, close, volume)``.
Bar = tuple

#: ``(day, contract) -> raw rows``. Injected so every test here is hermetic: no
#: socket is opened and no credential is read.
FetchDay = Callable[[date, str], list[dict]]


def raw_minute(row: dict, day: date) -> datetime | None:
    """The row's naive-KST minute, or ``None`` when it belongs to another day.

    Naive because that is what ``parse_ohlcv`` emits and what B1a's Parquet
    frame carries; mixing an aware stamp into the frame would make the
    ``_bar_lookup`` join miss.
    """
    stamp = raw_stamp(row, day)
    if stamp is None:
        return None
    return stamp.replace(tzinfo=None, second=0, microsecond=0)


@dataclass(frozen=True)
class FreezeStep:
    """What one poll's raw rows add to the frozen frame."""

    #: Newly complete bars, oldest first. ALL of them are appended to the frame
    #: — the causal ATR/VWAP windows must advance over every bar — while only
    #: the newest one is published (plan §2 4).
    newly_frozen: tuple[Bar, ...]
    #: Parsed bars that exist but are not complete yet. At most one: every bar
    #: older than the newest raw minute is complete by definition.
    deferred: tuple[datetime, ...]
    newest_raw_minute: datetime | None
    oldest_raw_minute: datetime | None
    #: Every minute the RAW response carried for this day. Lets the caller tell
    #: "this minute traded but has no successor yet" (the 15:34 shape) from
    #: "this minute never traded at all" (the 15:35-15:44 shape) — two facts the
    #: counters must not merge (review M1).
    raw_minutes: frozenset[datetime] = frozenset()

    @property
    def published(self) -> Bar | None:
        return self.newly_frozen[-1] if self.newly_frozen else None

    @property
    def skipped_behind(self) -> tuple[Bar, ...]:
        """Bars frozen in this step that are NOT published.

        ``decide_tick`` keeps only the newest observation of a polled batch and
        ``store.put`` advances ``latest_as_of``, so a second line in one write
        would be silently dropped forever (plan §2 4). These are counted, not
        written.
        """
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


#: Why a walked seed day was dropped.
#:
#: ``no_raw_rows`` is kept APART from ``density`` on purpose (review L3). A day
#: the calendar calls a trading day that returns zero rows is either a real
#: no-trade day or a HOLIDAY THE CALENDAR IS MISSING, and the second is the
#: 2026-08-17 / 10-05 defect plan §3.2 moved off
#: ``shared/collector/historical/calendar.py`` to avoid. Merged into a density
#: count it would be invisible; counted separately an operator can see "the
#: walk found eleven empty 'trading' days" and go look at the calendar.
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


#: ``(day, kept) -> (contract code to request for `day`, frame built from
#: `kept`)``. ONE seam, deliberately: day→contract selection and frame assembly
#: are the two things a stitched seed changes, so they live in a single
#: replaceable function. Plan §3.2a 「월물 교차 시드」 (cross-contract stitching)
#: landed in PR-2b and did exactly that: it supplies
#: :class:`~tools.tos_cp3.live_producer.stitch_seed.StitchedSeed` here and
#: changes nothing else in this module's walk. :func:`build_seed` below still
#: never names a contract itself.
SeedAssembler = Callable[[date, Sequence["SeedDay"]], tuple[str, Any]]


def same_contract_seed(
    day: date, kept: Sequence[SeedDay], *, instrument: str
) -> tuple[str, Any]:
    """The seed rule plan §3.2 specifies: ONE contract, the one being traded.

    Every seed day is requested on *instrument*, and the frame is simply those
    days' bars in time order. ⚠ The measured consequence (plan §6.2, evidence
    §5.3) is a post-roll blackout of about N = 3 trading days during which the
    window cannot be filled and the producer refuses to start. That refusal is
    intended behaviour under this rule; relaxing it is the open operator
    decision plan §6.2 records, and plan §3.2a's stitching is its candidate.
    """
    ordered = sorted(kept, key=lambda entry: entry.day)
    return instrument, bars_to_frame([bar for entry in ordered for bar in entry.bars])


def assembled_bars(frame: Any) -> tuple[Bar, ...]:
    """The assembler's frame back in ``parse_ohlcv`` tuple shape.

    One direction of travel: bars -> frame (the assembler) -> bars (here). The
    alternative, re-concatenating ``SeedDay.bars``, silently drops whatever the
    assembler did to them, which for a cross-contract seed is the whole
    alignment.
    """
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
    #: The kept days with the contract each was requested on and its UNADJUSTED
    #: bars. ``bars`` above is the assembled (possibly back-adjusted) frame; a
    #: caller that must store what the broker actually returned — which plan
    #: §3.2a 「라벨은 진실하게」 requires — reads these instead.
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
    """Walk trading days backwards until the causal vol window is FILLED.

    Plan §3.2, review H2: a session-count seed is wrong. ``_atr_window``
    (``vol_window_bars`` = 780) advances only on bars inside the entry window
    and the earliest session is excluded entirely for having no prior close, so
    a three-session seed reaches 662 and ``hi_vol``'s percentile differs from
    B1a's long-frame run. The stopping condition is therefore capacity, not a
    day count, and the capacity is counted by PR-1's own measured function
    (:func:`tools.tos_cp3.minute_probe.seed_capacity` — the function the M3
    proxy measurement imported).

    The density gate is B1a's: a day with fewer than *min_bars_per_day* parsed
    bars is dropped whole, exactly as ``produce_fields.load_bars`` drops it, so
    a thin post-roll day pushes the walk further back instead of entering the
    frame at a different density. The caller's config is refused at load unless
    that number equals ``produce_fields.DEFAULT_MIN_BARS_PER_DAY``
    (:func:`~tools.tos_cp3.live_producer.config.load_config`), so there is one
    source of truth for the value even though it is passed in (review M4).

    ⚠ **Documented deviation from plan §3.2** (review L3). The plan says
    「달력 안의 휴장일 빈 응답은 결측 세션이 아니라 달력 오류로 거부한다」. A
    calendar holiday is never requested here — :meth:`RuntimeCalendar
    .is_trading_day` skips it — so the case that actually arises is the
    converse: a day the calendar calls a TRADING day returning zero rows. This
    function treats that as a dropped session and walks further back rather
    than refusing startup, because PR-1's measured run walked 59 trading days
    of which 34 returned zero rows (evidence §3.2) and refusing would have made
    the seed unusable on a day the plan expects to work. The missing-holiday
    risk the plan was guarding is kept visible instead: those days are counted
    under :data:`SEED_DROP_NO_RAW_ROWS`, separately from density misses.

    Which contract each day is requested on, and how the kept days become one
    frame, are both *assembler*'s business — nothing here names a contract
    (see :data:`SeedAssembler`).

    Raises:
        LiveProducerRefused: the window could not be filled inside the horizon,
            or the walk left the calendar's covered years.
    """
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
        # Read BACK off the assembled frame, not re-concatenated from ``kept``:
        # a cross-contract assembler (plan §3.2a) back-adjusts the previous
        # month, and the two would then disagree — the frame B1a reconstructs
        # would be aligned while the one the producer feeds ``produce_bars``
        # every minute would not.
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
    """The refusal :func:`build_seed` raises, with the walk's own numbers in it.

    Separated so the caller stays inside the module's function-size budget and
    so the two drop reasons are reported distinctly (review L3): an operator
    reading "11 of the walked days returned zero rows" goes and looks at the
    calendar, which is what a merged density count would have hidden.
    """
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
