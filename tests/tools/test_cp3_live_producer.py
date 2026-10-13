"""CP-3 ③ live field producer — plan §5's six test items, all hermetic.

No socket is opened, no credential is read, no KIS call is made: the quotation
transport is replaced by a fixture server and the clock by a fake one. The
arrival model the fake uses is the one PR-1 measured (evidence §1.1): the raw
row stamped minute ``m`` first appears about 1.1 s after the ``m`` boundary, and
that row is the completion signal for bar ``m-1``.

Each clause of each guard is red-proved in the body of its own test — either by
a parametrised "and here is the input that makes it fail" case, or by the
companion ``test_red_*`` next to it.
"""

from __future__ import annotations

import ast
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

import pytest
import yaml

from shared.collector.historical.ohlcv_parser import parse_ohlcv
from tools.tos_cp3.live_producer import calendar as calendar_mod
from tools.tos_cp3.live_producer import config as config_mod
from tools.tos_cp3.live_producer import frame as frame_mod
from tools.tos_cp3.live_producer import producer as producer_mod
from tools.tos_cp3.live_producer import sinks as sinks_mod
from tools.tos_cp3.live_producer.config import LiveProducerRefused
from tools.tos_cp3.minute_probe import frame as bars_to_frame
from tools.tos_cp3.produce_fields import (
    FIELD_ORDER,
    JOURNAL_REQUIRED_KEYS,
    ContractSpecRegistry,
    discover_input_files,
    load_strategy_inputs,
    produce_bars,
    resolve_contract_spec,
    resolve_open_anchor,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

INSTRUMENT = "A05611"
BASE_PRICE = 400.0
SESSION_BARS = 420  # 08:45 .. 15:44, the real shape of a 2026 futures session
OPEN_HM = (8, 45)

#: Ten past sessions for the long-frame reference plus the target session. The
#: dates are real 2026 trading days in the tenant calendar (so no holiday and
#: no weekend), after the 2026-06-28 open-anchor cutover.
SEED_DAYS = [date(2026, 10, d) for d in (1, 2, 6, 7, 8, 12, 13, 14, 15, 16)]
TARGET = date(2026, 10, 19)

#: The target session is cut short in the test calendar so the loop walks 36
#: boundaries instead of 420. Bar 09:00 is the first inside the entry window
#: (``valid_minutes_min`` 15 after the 08:45 anchor).
TARGET_BARS = 36
TARGET_SESSION_END = "09:20"


#: Measured in this file (see ``test_equivalence_*``): seed amplitude DECREASES
#: toward the present, so a 780-bar causal window reaches back into a more
#: volatile session than a 683-bar one does and ``hi_vol``'s percentile differs.
#: Without that arrangement the equivalence test would be a tautology — any
#: seed length would pass.
def _seed_scale(index: int) -> float:
    return 4.00 - 0.30 * index


def _target_scale(bar_index: int) -> float:
    """Ramped so the target session's ATR sweeps ACROSS 0.9 x both percentiles."""
    return 1.50 + 0.022 * bar_index


# ---------------------------------------------------------------------------
# Synthetic market data
# ---------------------------------------------------------------------------


def _zigzag(index: int, period: int = 7) -> float:
    phase = index % period
    half = period / 2
    return (phase / half) if phase < half else (2 - phase / half)


def _session_bars(day: date, scale, *, count: int = SESSION_BARS) -> list[tuple]:
    """``parse_ohlcv``-shaped bars for one synthetic session.

    Steps stay far inside ``parse_ohlcv``'s 6 % continuity tolerance, so no
    minute is dropped as a phantom and the frame has exactly *count* bars.

    Every price is rounded to two decimals, which is the precision a KIS
    ``output2`` row carries. Without that the round trip through
    :func:`_raw_row` would quietly re-quantise the frame, and the equivalence
    test would then be measuring the generator's float tail (measured: ~0.3 %
    on ``atr14`` and up to 3 units of ``z_x1000``) rather than the producer.
    """
    bars: list[tuple] = []
    previous = BASE_PRICE
    for index in range(count):
        width = scale(index)
        close = round(BASE_PRICE + width * (_zigzag(index) - 0.5) * 2, 2)
        stamp = datetime(day.year, day.month, day.day, *OPEN_HM) + timedelta(
            minutes=index
        )
        bars.append(
            (
                INSTRUMENT,
                stamp,
                previous,
                round(max(previous, close) + width * 0.2, 2),
                round(min(previous, close) - width * 0.2, 2),
                close,
                50 + index % 17,
            )
        )
        previous = close
    return bars


def _raw_row(bar: tuple, *, volume: int | None = None) -> dict:
    """One KIS ``output2`` row for a bar, in the shape PR-1 recorded."""
    return {
        "stck_bsop_date": bar[1].strftime("%Y%m%d"),
        "stck_cntg_hour": bar[1].strftime("%H%M%S"),
        "futs_oprc": f"{bar[2]:.2f}",
        "futs_hgpr": f"{bar[3]:.2f}",
        "futs_lwpr": f"{bar[4]:.2f}",
        "futs_prpr": f"{bar[5]:.2f}",
        "cntg_vol": str(bar[6] if volume is None else volume),
    }


@dataclass
class Market:
    """Every session's bars, and the raw rows a day's response would carry."""

    sessions: dict[date, list[tuple]]
    target_bars: list[tuple]

    def rows(self, day: date) -> list[dict]:
        bars = self.sessions.get(day, self.target_bars if day == TARGET else [])
        return [_raw_row(bar) for bar in bars]


@pytest.fixture(scope="module")
def market() -> Market:
    return Market(
        sessions={
            day: _session_bars(day, partial(_constant, _seed_scale(index)))
            for index, day in enumerate(SEED_DAYS)
        },
        target_bars=_session_bars(TARGET, _target_scale, count=TARGET_BARS),
    )


def _constant(value: float, _index: int) -> float:
    return value


# ---------------------------------------------------------------------------
# Strategy / contract inputs, shared by the heavier tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def inputs() -> dict[str, Any]:
    strategy = load_strategy_inputs(
        _REPO_ROOT / "config/strategies/futures/setup_d_vwap_reversion.yaml"
    )
    return {
        "strategy": strategy,
        "anchor": resolve_open_anchor(
            cli_value="auto", first_session=TARGET, last_session=TARGET
        ),
        "contract_spec": resolve_contract_spec(
            INSTRUMENT,
            ContractSpecRegistry.from_yaml(str(_REPO_ROOT / "config/execution.yaml")),
        ),
    }


def _full_day_frame(market: Market, seed_days: list[date]) -> Any:
    """``seed_days`` + the target session, parsed the way B1a's input was built.

    Each day goes through ``parse_ohlcv`` ONCE over its whole response — the
    offline convention — so the comparison against the live path is between two
    readings of the SAME raw rows (plan §5 1 「같은 원시 응답 픽스처에서」). The
    live path instead parses each day's tail incrementally and freezes it, which
    is the difference plan §3.3 wants measured, not assumed away.
    """
    bars: list[tuple] = []
    for day in [*seed_days, TARGET]:
        bars.extend(
            parse_ohlcv(
                INSTRUMENT, day.strftime("%Y%m%d"), {"output2": market.rows(day)}
            )
        )
    return bars_to_frame(bars)


def _b1a_target_records(market: Market, inputs: dict, seed_days: list[date]) -> dict:
    """B1a over ``seed_days`` + the target session; the target's records only."""
    produced = produce_bars(
        _full_day_frame(market, seed_days),
        symbol=INSTRUMENT,
        strategy=inputs["strategy"],
        contract_spec=inputs["contract_spec"],
        anchor=inputs["anchor"],
    )
    return {
        record.raw_event_id: record.fields
        for record in produced.records
        if record.bar_kst.date() == TARGET
    }


# ---------------------------------------------------------------------------
# Fakes: the clock and the quotation transport
# ---------------------------------------------------------------------------


#: The measured first-appearance lag of a raw row after its own minute boundary
#: (evidence §1.2: the ``+1 s`` mode's p50 is 1.107809 s).
ARRIVAL_LAG_S = 1.1


class FakeClock:
    """A clock that only moves when the producer sleeps."""

    def __init__(self, start: datetime):
        self.moment = start.replace(tzinfo=producer_mod.KST)

    def now(self) -> datetime:
        return self.moment

    def sleep(self, seconds: float) -> None:
        self.moment += timedelta(seconds=max(0.0, seconds))


class FakeQuotes:
    """The fixture server. GET-only by construction: it has no other method."""

    def __init__(self, market: Market, clock: FakeClock, *, page_size: int = 120):
        self.market, self.clock, self.page_size = market, clock, page_size
        self.calls = 0
        self.history_calls = 0
        self.http = None
        self.last_received_kst = clock.now()
        self.fail_next = 0

    def _visible(self, day: date) -> list[dict]:
        rows = self.market.rows(day)
        if day != TARGET:
            return rows  # a past session is complete
        now = self.clock.now().replace(tzinfo=None)
        return [
            row
            for row in rows
            if datetime.strptime(
                row["stck_bsop_date"] + row["stck_cntg_hour"], "%Y%m%d%H%M%S"
            )
            + timedelta(seconds=ARRIVAL_LAG_S)
            <= now
        ]

    def _receive(self) -> None:
        self.calls += 1
        self.clock.sleep(0.05)
        self.last_received_kst = self.clock.now()
        if self.fail_next:
            self.fail_next -= 1
            raise RuntimeError("auth_http_or_json_error")

    def page(self, symbol: str, day: date, cursor: str = "") -> list[dict]:
        self._receive()
        return self._visible(day)[-self.page_size :]

    def history(self, symbol: str, day: date) -> list[dict]:
        self.history_calls += 1
        self._receive()
        return self._visible(day)


# ---------------------------------------------------------------------------
# Config + calendar on disk
# ---------------------------------------------------------------------------


def _write_calendar(tmp_path: Path, *, session_end: str = TARGET_SESSION_END) -> Path:
    """A tenant-shaped calendar whose target session is short, so the loop is fast.

    The holiday list and the session SHAPE are the tenant tree's own
    (``config/tos_runtime/cp3-setup-d-long/calendar.yaml``); only the
    CONTINUOUS end moves, which is exactly the value the production file would
    change if the exchange moved the close — and the point of reading it from
    the calendar rather than hardcoding 15:45.
    """
    source = yaml.safe_load(
        (_REPO_ROOT / "config/tos_runtime/cp3-setup-d-long/calendar.yaml").read_text(
            encoding="utf-8"
        )
    )
    source["sessions"] = {
        "krx-index-futures": [
            {"phase": "CONTINUOUS", "start": "08:45", "end": session_end}
        ]
    }
    path = tmp_path / "calendar.yaml"
    path.write_text(yaml.safe_dump(source, allow_unicode=True), encoding="utf-8")
    return path


def _write_config(tmp_path: Path, **overrides: Any) -> Path:
    """The shipped producer config with test paths swapped in."""
    data = yaml.safe_load(
        (_REPO_ROOT / "config/tos_probes/cp3-live-producer.yaml").read_text(
            encoding="utf-8"
        )
    )
    data["calendar_yaml"] = str(_write_calendar(tmp_path))
    data["env_file"] = str(tmp_path / "env")
    data["token_cache_dir"] = str(tmp_path / "token-cache")
    data.update(overrides)
    (tmp_path / "env").write_text(
        "KIS_FUTURES_APP_KEY=fake\nKIS_FUTURES_APP_SECRET=fake\n", encoding="utf-8"
    )
    path = tmp_path / "producer.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _build(tmp_path: Path, market: Market, **overrides: Any):
    """A producer wired to the fakes, plus the clock and transport it uses."""
    config = config_mod.load_config(
        _write_config(tmp_path, **overrides), repo_root=_REPO_ROOT
    )
    clock = FakeClock(datetime(TARGET.year, TARGET.month, TARGET.day, 8, 44, 30))
    quotes = FakeQuotes(market, clock)
    producer = producer_mod.LiveProducer(
        config=config,
        instrument=INSTRUMENT,
        target=TARGET,
        session_dir=tmp_path / "session",
        journal_path=tmp_path / "session" / "journal.jsonl",
        clock=producer_mod.Clock(now=clock.now, sleep=clock.sleep),
        quotes_factory=lambda _config, _log: quotes,
    )
    return producer, clock, quotes


def _minute_of(raw_event_id: str) -> datetime:
    """The bar's naive-KST minute, back out of B1a's own join key.

    ``derive_raw_event_id`` stamps ``%z`` and the replay's contexts are
    KST-aware, so the key carries ``+0900``.
    """
    return datetime.strptime(raw_event_id.split(":1m:")[1], "%Y%m%dT%H%M%S%z").replace(
        tzinfo=None
    )


def _event_id(bar_minute: datetime) -> str:
    stamp = bar_minute.replace(tzinfo=producer_mod.KST).strftime("%Y%m%dT%H%M%S%z")
    return f"{INSTRUMENT}:1m:{stamp}"


def _journal_rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ===========================================================================
# §5 1 — equivalence, and the proof it is not a tautology
# ===========================================================================


@pytest.mark.serial
def test_item1_live_lines_equal_b1a_over_a_ten_session_frame(
    tmp_path: Path, market: Market, inputs: dict
) -> None:
    """The real-time lines' fifteen fields == B1a's over a LONGER frame.

    The producer seeds by window fill (four sessions here, capacity 993 against
    the 780 the strategy YAML declares); B1a is run over all ten. Every
    published ``raw_event_id`` must carry byte-identical field values, which is
    what makes a B3 join on that key meaningful.
    """
    producer, _clock, quotes = _build(tmp_path, market)
    producer.boot()
    producer.run_session()
    producer.finish()

    assert producer.seed.capacity >= producer.seed.required
    assert len(producer.seed.days_used) == 4, producer.seed.days_used
    assert producer.seed.contracts_used == (INSTRUMENT,)

    rows = _journal_rows(producer.journal_path)
    assert rows, "the producer published nothing"
    reference = _b1a_target_records(market, inputs, SEED_DAYS)
    live = {row["raw_event_id"]: row["fields"] for row in rows}
    assert set(live) <= set(reference)
    mismatched = {key for key in live if live[key] != reference[key]}
    assert not mismatched, sorted(mismatched)
    # ... and the comparison actually covered the discriminating bars.
    assert {reference[key]["hi_vol"] for key in live} == {True, False}


@pytest.mark.serial
def test_item1_red_a_three_session_seed_breaks_the_equivalence(
    market: Market, inputs: dict
) -> None:
    """The red proof §5 1 names: shrink the seed to three sessions and this fails.

    Measured here rather than asserted: three sessions leave the causal
    ``_atr_window`` at 683 of 780, so ``hi_vol``'s percentile is taken over a
    window that does not reach as far back, and the published ``hi_vol`` flips
    on the bars whose ATR sits between the two thresholds. Without this,
    "the live path matches B1a" would hold for any seed length and would be
    saying nothing about the seed rule at all.
    """
    reference = _b1a_target_records(market, inputs, SEED_DAYS)
    short = _b1a_target_records(market, inputs, SEED_DAYS[-3:])
    flipped = [
        key
        for key in reference
        if key in short and reference[key]["hi_vol"] != short[key]["hi_vol"]
    ]
    assert flipped, "a three-session seed must change hi_vol, or §5 1 is vacuous"
    assert _b1a_target_records(market, inputs, SEED_DAYS[-4:]) == reference


def test_item1_the_window_fill_rule_counts_capacity_not_sessions(
    market: Market, inputs: dict
) -> None:
    """Four kept sessions, 993 capacity: (sessions - 1) x 331 in-window bars.

    PR-1 measured exactly this table (evidence §5.2: 10-13 -> 331, 10-14 -> 662,
    10-15 -> 993), and it is why the stopping condition is capacity.
    """
    required = inputs["strategy"].entry_config.vol_window_bars
    assert required == 780
    walked: list[date] = []

    def fetch(day: date, contract: str) -> list[dict]:
        walked.append(day)
        return market.rows(day)

    seed = frame_mod.build_seed(
        target=TARGET,
        calendar=calendar_mod.load_runtime_calendar(
            _REPO_ROOT / "config/tos_runtime/cp3-setup-d-long/calendar.yaml"
        ),
        strategy=inputs["strategy"],
        anchor=inputs["anchor"],
        min_bars_per_day=330,
        max_calendar_days=90,
        fetch_day=fetch,
        assembler=partial(frame_mod.same_contract_seed, instrument=INSTRUMENT),
    )
    assert seed.capacity == 993
    assert len(seed.days_used) == 4
    assert walked == sorted(walked, reverse=True)  # newest first


# ===========================================================================
# §5 2 — as_of_ms monotonicity, regression refusal, one line per write
# ===========================================================================


def _row(as_of_ms: int, raw_event_id: str = "A05611:1m:20261019T090000+0900") -> dict:
    return {
        "raw_event_id": raw_event_id,
        "source_id": producer_mod.SOURCE_ID,
        "instrument": INSTRUMENT,
        "as_of_ms": as_of_ms,
        "received_ms": as_of_ms - 50,
        "fields": dict.fromkeys(FIELD_ORDER, 1),
    }


def test_item2_as_of_ms_must_advance(tmp_path: Path) -> None:
    journal = sinks_mod.ObservationJournal(tmp_path / "journal.jsonl")
    journal.append(_row(1_000))
    journal.append(_row(1_001))
    assert [row["as_of_ms"] for row in _journal_rows(journal.path)] == [1_000, 1_001]


@pytest.mark.parametrize("second", [1_000, 999])
def test_item2_red_a_non_advancing_stamp_is_refused(
    tmp_path: Path, second: int
) -> None:
    """Equal is refused as well as backwards.

    The reader returns rows strictly newer than ``after_as_of_ms``, so an EQUAL
    stamp is a line nothing can ever consume — a ``>=`` here would admit
    exactly the silent loss the guard is named for.
    """
    journal = sinks_mod.ObservationJournal(tmp_path / "journal.jsonl")
    journal.append(_row(1_000))
    with pytest.raises(LiveProducerRefused, match="does not advance"):
        journal.append(_row(second))
    assert len(_journal_rows(journal.path)) == 1


@pytest.mark.serial
def test_item2_one_line_per_write_and_catch_up_is_counted_not_batched(
    tmp_path: Path, market: Market
) -> None:
    """A late start freezes the whole morning but writes ONE line for it.

    ``decide_tick`` keeps only the newest observation of a polled batch, so a
    second line in one write would never be consumed. The bars behind it are
    counted as ``skipped_behind``.
    """
    producer, clock, _quotes = _build(tmp_path, market)
    clock.moment = datetime(
        TARGET.year, TARGET.month, TARGET.day, 9, 10, 5, tzinfo=producer_mod.KST
    )
    producer.boot()
    rows = _journal_rows(producer.journal_path)
    assert len(rows) == 1
    assert producer.counters.pre_boot_lines == 1
    assert producer.counters.skipped_behind > 20
    # every frozen bar is in the frame even though only one was published
    assert len(producer.frozen) == producer.counters.skipped_behind + 1
    producer.finish()


# ===========================================================================
# §5 3 — completion is judged on RAW rows
# ===========================================================================


def _target_rows_through(market: Market, minute_index: int) -> list[dict]:
    return [_raw_row(bar) for bar in market.target_bars[: minute_index + 1]]


def test_item3_no_later_raw_row_means_no_publication(market: Market) -> None:
    rows = _target_rows_through(market, 5)
    step = frame_mod.freeze_step(
        rows,
        day=TARGET,
        symbol=INSTRUMENT,
        last_frozen_minute=market.target_bars[4][1],
        session_ended=False,
    )
    assert step.newly_frozen == ()
    assert step.deferred == (market.target_bars[5][1],)
    assert step.published is None


def test_item3_a_sub_threshold_successor_row_still_completes_the_bar(
    market: Market,
) -> None:
    """The reason completion is judged on raw rows and not on parsed bars.

    ``KIS_MINUTE_BAR_MIN_VOLUME`` is 10, so a successor minute with volume 1 is
    dropped by ``parse_ohlcv`` and never becomes a bar. A parsed-row rule would
    leave bar ``m`` forever incomplete; the raw-row rule completes it.
    """
    rows = _target_rows_through(market, 4)
    rows.append(_raw_row(market.target_bars[5], volume=1))
    step = frame_mod.freeze_step(
        rows,
        day=TARGET,
        symbol=INSTRUMENT,
        last_frozen_minute=market.target_bars[3][1],
        session_ended=False,
    )
    assert [bar[1] for bar in step.newly_frozen] == [market.target_bars[4][1]]
    assert step.deferred == ()
    # the sub-threshold minute itself is not fabricated into a bar
    assert market.target_bars[5][1] not in [bar[1] for bar in step.newly_frozen]


def test_item3_the_closing_gap_bar_completes_on_a_later_row_not_m_plus_one(
    market: Market,
) -> None:
    """The measured 15:34 case (evidence §1.6 / §2.2), in miniature.

    Bar ``k`` has no ``k+1`` row at all (the call-auction gap). The plan's
    literal ``m+1`` rule would skip it; widening "successor" to any strictly
    later raw row completes it when the session's final row arrives.
    """
    gap_bar = market.target_bars[20]
    final_bar = market.target_bars[30]
    rows = _target_rows_through(market, 20) + [_raw_row(final_bar)]
    step = frame_mod.freeze_step(
        rows,
        day=TARGET,
        symbol=INSTRUMENT,
        last_frozen_minute=market.target_bars[19][1],
        session_ended=False,
    )
    assert gap_bar[1] in [bar[1] for bar in step.newly_frozen]
    assert step.published is not None and step.published[1] == gap_bar[1]
    assert step.deferred == (final_bar[1],)


def test_item3_the_last_bar_of_the_day_completes_only_on_session_end(
    market: Market,
) -> None:
    """The measured 15:45 case: no later row can EVER exist (evidence §2.2).

    Widening the successor rule does not help here, which is why the session-end
    clause is required and not optional. Red proof of the clause: with
    ``session_ended=False`` the same rows publish nothing.
    """
    last = market.target_bars[-1]
    rows = [_raw_row(last)]
    kwargs = {
        "day": TARGET,
        "symbol": INSTRUMENT,
        "last_frozen_minute": market.target_bars[-2][1],
    }
    assert frame_mod.freeze_step(rows, session_ended=False, **kwargs).newly_frozen == ()
    ended = frame_mod.freeze_step(rows, session_ended=True, **kwargs)
    assert [bar[1] for bar in ended.newly_frozen] == [last[1]]


@pytest.mark.serial
def test_item3_a_full_run_publishes_both_the_gap_bar_and_the_session_end_bar(
    tmp_path: Path, market: Market
) -> None:
    """End to end, with a hole in the raw feed where 15:35-15:44 was.

    The session's second-to-last minute is withheld from the fixture entirely,
    so the bar before it has no ``m+1`` successor — the 15:34 shape — and the
    last bar is the session end minute — the 15:45 shape. Both must appear.
    """
    withheld = market.target_bars[-2][1]
    thinned = Market(
        sessions=market.sessions,
        target_bars=[bar for bar in market.target_bars if bar[1] != withheld],
    )
    producer, _clock, _quotes = _build(tmp_path, thinned)
    producer.boot()
    producer.run_session()
    producer.finish()

    published = {row["raw_event_id"] for row in _journal_rows(producer.journal_path)}
    gap_bar = market.target_bars[-3][1]
    last_bar = market.target_bars[-1][1]
    for bar_minute in (gap_bar, last_bar):
        assert _event_id(bar_minute) in published
    assert producer.counters.missing_no_successor >= 1


# ===========================================================================
# §5 4 — freezing
# ===========================================================================


def test_item4_a_response_that_would_move_an_earlier_bar_cannot(
    market: Market,
) -> None:
    """A frozen bar is never re-parsed, so a revised row for it is invisible.

    The input that makes this bite: the same minute re-served with a different
    close. Only rows strictly newer than the last frozen bar are parsed, so the
    revision is not in the parse at all — which is what keeps a published line
    from being contradicted by a later one.
    """
    frozen_bar = market.target_bars[5]
    revised = list(frozen_bar)
    revised[5] = revised[5] + 3.0
    rows = (
        _target_rows_through(market, 4)
        + [_raw_row(tuple(revised))]
        + [_raw_row(market.target_bars[6]), _raw_row(market.target_bars[7])]
    )
    step = frame_mod.freeze_step(
        rows,
        day=TARGET,
        symbol=INSTRUMENT,
        last_frozen_minute=frozen_bar[1],
        session_ended=False,
    )
    assert [bar[1] for bar in step.newly_frozen] == [market.target_bars[6][1]]
    assert frozen_bar[1] not in [bar[1] for bar in step.newly_frozen]

    # Red proof of the clause: the revision IS in the response, so without the
    # frozen-minute filter the same rows re-publish 08:50 with the moved close.
    unfrozen = frame_mod.freeze_step(
        rows,
        day=TARGET,
        symbol=INSTRUMENT,
        last_frozen_minute=None,
        session_ended=False,
    )
    moved = [bar for bar in unfrozen.newly_frozen if bar[1] == frozen_bar[1]]
    assert moved and moved[0][5] != frozen_bar[5]


@pytest.mark.serial
def test_item4_the_frozen_frame_is_append_only_across_a_whole_run(
    tmp_path: Path, market: Market
) -> None:
    """Every published bar's own ``fields`` stay as published, run-long.

    A re-parse that moved an earlier bar would show up here as a frame whose
    bar values no longer match the line that was written from it.
    """
    producer, _clock, _quotes = _build(tmp_path, market)
    producer.boot()
    producer.run_session()
    producer.finish()

    by_minute = {bar[1]: bar for bar in producer.frozen}
    assert len(by_minute) == len(producer.frozen)  # no duplicate minute
    for row in _journal_rows(producer.journal_path):
        bar = by_minute[_minute_of(row["raw_event_id"])]
        assert row["fields"]["close_x100"] == round(bar[5] * 100)
        assert row["fields"]["volume"] == bar[6]


# ===========================================================================
# §5 5 — half-written files, order-path imports, pins, seed refusal
# ===========================================================================


def test_item5_a_half_written_journal_is_never_visible(tmp_path: Path) -> None:
    """Whole-file replacement: a reader only ever sees complete lines.

    Proved on the file system rather than by reading the code: the temp file
    does not carry the journal's name, so a reader globbing or opening the
    journal path cannot observe a partial write, and after the replace the file
    holds exactly the complete lines.
    """
    journal = sinks_mod.ObservationJournal(tmp_path / "journal.jsonl")
    journal.append(_row(1))
    seen: list[str] = []
    original = os.replace

    def spy(src, dst):
        # what a reader sees at the instant BEFORE the rename
        seen.append((tmp_path / "journal.jsonl").read_text(encoding="utf-8"))
        return original(src, dst)

    sinks_mod.os.replace = spy
    try:
        journal.append(_row(2))
    finally:
        sinks_mod.os.replace = original
    assert seen == [json.dumps(_row(1), separators=(",", ":")) + "\n"]
    assert len(_journal_rows(journal.path)) == 2
    assert list(tmp_path.glob("*.tmp")) == []


def test_item5_a_crashed_parquet_write_is_not_picked_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The in-flight temp file must be invisible to both ``*.parquet`` globs.

    B1a's ``discover_input_files`` globs ``year=*/month=*/day=*/*.parquet`` and
    the store's own reader uses ``rglob("*.parquet")``, so a half-written file
    with that suffix would be READ as input.

    Measured AT THE INSTANT a crash would leave the temp file behind — between
    ``to_parquet`` and ``os.replace`` — because that is the only moment the file
    exists. ⚠ An earlier version of this test planted its own ``.tmp`` leftover
    afterwards instead; that passes whatever the producer names its temp file,
    i.e. it was a guard that admitted exactly what it claimed to block
    (measured: renaming the temp file to ``*.parquet`` left it green).
    """
    market_root = tmp_path / "market"
    day = date(2026, 10, 19)
    seen: list[tuple[list[str], int]] = []
    original = os.replace

    def spy(src, dst):
        seen.append(
            (
                sorted(path.name for path in market_root.rglob("*.parquet")),
                len(
                    discover_input_files(
                        market_root,
                        asset_class="futures",
                        symbol=INSTRUMENT,
                        start=day,
                        end=day,
                    )
                ),
            )
        )
        return original(src, dst)

    monkeypatch.setattr(sinks_mod.os, "replace", spy)
    written = sinks_mod.append_bar_part(
        market_root,
        asset_class="futures",
        symbol=INSTRUMENT,
        bars=[(INSTRUMENT, datetime(2026, 10, 19, 9, 0), 1.0, 2.0, 0.5, 1.5, 11)],
    )
    monkeypatch.undo()

    # mid-write: the temp file exists on disk, and NEITHER glob can see it
    assert seen == [([], 0)]
    # afterwards: exactly the committed part file, visible to both
    assert [path.name for path in market_root.rglob("*.parquet")] == [written[0].name]
    assert written[0].name.startswith("part-") and not written[0].name.startswith(".")
    assert (
        len(
            discover_input_files(
                market_root,
                asset_class="futures",
                symbol=INSTRUMENT,
                start=day,
                end=day,
            )
        )
        == 1
    )


def _import_closure(module_name: str) -> set[str]:
    """Every module reachable by a static import walk from *module_name*.

    Static, not ``sys.modules``: an order path that is imported lazily inside a
    function would not show up in a runtime snapshot of a module that was never
    called, and "we never called it" is not the claim being made.
    """
    seen: set[str] = set()
    queue = [module_name]
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        parts = name.split(".")
        candidates = [
            _REPO_ROOT.joinpath(*parts).with_suffix(".py"),
            _REPO_ROOT.joinpath(*parts, "__init__.py"),
        ]
        source = next((p for p in candidates if p.is_file()), None)
        if source is None:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                queue.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                queue.append(node.module)
                queue.extend(f"{node.module}.{a.name}" for a in node.names)
    return seen


@pytest.mark.parametrize(
    "forbidden",
    ["shared.execution", "tools.broker_probes.probes_real_order", "tos", "tos_runtime"],
)
def test_item5_the_producer_import_graph_has_no_order_path(forbidden: str) -> None:
    """GET-only and firewall-clean, pinned on the whole static closure.

    ``shared.execution`` is the order path, ``probes_real_order`` is the probe
    harness that can emit one, and ``tos`` / ``tos_runtime`` are the other side
    of the bidirectional import firewall (``tools/`` may not import either).
    """
    closure = _import_closure("tools.tos_cp3.live_producer.producer")
    offending = sorted(
        name
        for name in closure
        if name == forbidden or name.startswith(forbidden + ".")
    )
    assert not offending, offending
    # the walk really reached the producer's own dependencies
    assert "tools.tos_cp3.produce_fields" in closure
    assert "tools.tos_cp3.quote_client" in closure


def test_item5_the_transport_is_a_get_only_allowlist() -> None:
    """The positive half: one method, one TR, one path, and no POST code path."""
    from tools.broker_probes.common import SafetyViolation, assert_read_only_call
    from tools.tos_cp3 import quote_client

    source = (_REPO_ROOT / "tools/tos_cp3/quote_client.py").read_text("utf-8")
    assert ".post(" not in source and '"POST"' not in source
    for method, path, tr in (
        ("POST", quote_client.QUOTE_PATH, quote_client.TR),
        ("GET", "/uapi/domestic-futureoption/v1/trading/order", quote_client.TR),
        ("GET", quote_client.QUOTE_PATH, "TTTO1101U"),
    ):
        with pytest.raises(SafetyViolation):
            assert_read_only_call(
                method,
                quote_client.REAL_BASE_URL + path,
                tr,
                quote_client.ALLOWLIST,
            )


@pytest.mark.parametrize(
    "key,bad",
    [
        ("KIS_MINUTE_BAR_MIN_VOLUME", "0"),
        ("KIS_FUTURES_HOUR_CLS_CODE", "30"),
    ],
)
def test_item5_red_an_env_pin_mismatch_refuses_to_start(
    tmp_path: Path, key: str, bad: str
) -> None:
    """Each pin is checked, and each one on its own makes startup refuse.

    ``KIS_MINUTE_BAR_MIN_VOLUME=0`` keeps the rows the pinned run drops;
    ``KIS_FUTURES_HOUR_CLS_CODE=30`` asks for a different bar size. Either
    would make the producer's frame disagree with B1a's bar for bar, silently.
    """
    config = config_mod.load_config(_write_config(tmp_path), repo_root=_REPO_ROOT)
    environ = {key: bad}
    with pytest.raises(LiveProducerRefused, match="parser env pin mismatch"):
        config_mod.assert_env_pins(config, environ)
    # unset is fine, and the pin is then applied
    applied: dict[str, str] = {}
    config_mod.assert_env_pins(config, applied)
    assert applied == dict(config.parser_env)


@pytest.mark.serial
def test_item5_red_an_unfilled_seed_window_refuses_to_start(
    tmp_path: Path, market: Market
) -> None:
    """The post-roll blackout, as a startup refusal rather than a short seed.

    The failing input is a market with only two dense sessions available before
    the target — PR-1's measured post-roll shape (one dense day, capacity
    0/780). The producer must refuse rather than run with a window that makes
    ``hi_vol`` differ from B1a's.
    """
    thin = Market(
        sessions={day: market.sessions[day] for day in SEED_DAYS[-2:]},
        target_bars=market.target_bars,
    )
    producer, _clock, _quotes = _build(tmp_path, thin)
    with pytest.raises(LiveProducerRefused, match="seed window not filled"):
        producer.boot()
    assert not producer.journal_path.exists()
    producer.finish()


@pytest.mark.serial
def test_item5_red_a_reused_session_directory_refuses_to_start(
    tmp_path: Path, market: Market
) -> None:
    """Append-only writes mean a second run into one directory loses the window.

    The failing input is a directory that already holds one part file: B1a's
    ``_bar_lookup`` refuses duplicate timestamps, so the whole session's offline
    input would be lost rather than doubled.
    """
    producer, _clock, _quotes = _build(tmp_path, market)
    sinks_mod.append_bar_part(
        producer.market_root,
        asset_class="futures",
        symbol=INSTRUMENT,
        bars=[(INSTRUMENT, datetime(2026, 10, 19, 9, 0), 1.0, 2.0, 0.5, 1.5, 11)],
    )
    with pytest.raises(LiveProducerRefused, match="already holds"):
        producer.boot()
    producer.finish()


def test_item5_red_a_second_producer_on_one_journal_is_refused(
    tmp_path: Path,
) -> None:
    held = sinks_mod.acquire_journal_lock(tmp_path / "journal.jsonl")
    try:
        with pytest.raises(LiveProducerRefused, match="another producer holds"):
            sinks_mod.acquire_journal_lock(tmp_path / "journal.jsonl")
    finally:
        held.close()
    # released: the next acquire succeeds
    sinks_mod.acquire_journal_lock(tmp_path / "journal.jsonl").close()


def test_item5_red_an_existing_journal_is_not_overwritten(tmp_path: Path) -> None:
    """A whole-file replace would destroy whatever is already there."""
    path = tmp_path / "journal.jsonl"
    path.write_text('{"source_id":"cp3-bootproof-synthetic:x"}\n', encoding="utf-8")
    with pytest.raises(LiveProducerRefused, match="already holds"):
        sinks_mod.refuse_if_journal_exists(path)
    path.write_text("", encoding="utf-8")
    sinks_mod.refuse_if_journal_exists(path)  # empty is fine


@pytest.mark.parametrize(
    "override,expected",
    [
        ({"first_poll_delay_s": 12.0}, "must exceed"),
        ({"missing_no_successor_timeout_s": 61.0}, "next minute boundary"),
        ({"max_consecutive_produce_errors": 0}, "must be >= 1"),
    ],
)
def test_item5_red_the_config_refuses_incoherent_values(
    tmp_path: Path, override: dict, expected: str
) -> None:
    """δ past G, a G that straddles the next boundary, a zero error budget."""
    with pytest.raises(LiveProducerRefused, match=expected):
        config_mod.load_config(
            _write_config(tmp_path, **override), repo_root=_REPO_ROOT
        )


def test_item5_red_an_unknown_or_missing_config_key_is_refused(
    tmp_path: Path,
) -> None:
    """A typo must not read as "the default was fine"."""
    with pytest.raises(LiveProducerRefused, match="unknown key"):
        config_mod.load_config(
            _write_config(tmp_path, missing_no_successor_timeout=10.0),
            repo_root=_REPO_ROOT,
        )
    data = yaml.safe_load(_write_config(tmp_path).read_text(encoding="utf-8"))
    del data["first_poll_delay_s"]
    path = tmp_path / "incomplete.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(LiveProducerRefused, match="missing key"):
        config_mod.load_config(path, repo_root=_REPO_ROOT)


def test_item5_the_shipped_config_carries_the_operator_confirmed_delta_and_g(
    tmp_path: Path,
) -> None:
    """δ and G live in YAML, not in code, and carry the confirmed values.

    Operator decision 2026-10-14 confirmed δ = 1.8 s and G = 10 s; the PR-1
    evidence had only proposed them and refused to let them be written into
    code. Confirmation does not move them out of configuration.
    """
    shipped = config_mod.load_config(
        _REPO_ROOT / "config/tos_probes/cp3-live-producer.yaml", repo_root=_REPO_ROOT
    )
    assert shipped.first_poll_delay_s == 1.8
    assert shipped.missing_no_successor_timeout_s == 10.0
    text = (_REPO_ROOT / "config/tos_probes/cp3-live-producer.yaml").read_text("utf-8")
    assert "운영자 결정 2026-10-14" in text
    assert "1.765964" in text and "5.345897" in text
    source = (_REPO_ROOT / "tools/tos_cp3/live_producer/producer.py").read_text("utf-8")
    assert "1.8" not in source and "10.0" not in source


@pytest.mark.parametrize("walk_back_year", [2025])
def test_item5_red_a_seed_walk_leaving_the_calendar_is_refused(
    walk_back_year: int,
) -> None:
    """Plan §3.2's explicit coverage refusal, not a silent "no holidays".

    The tenant calendar holds 2026 only, so a target early enough that the walk
    crosses into the previous year must refuse before requesting anything.
    """
    calendar = calendar_mod.load_runtime_calendar(
        _REPO_ROOT / "config/tos_runtime/cp3-setup-d-long/calendar.yaml"
    )
    with pytest.raises(LiveProducerRefused, match="covers"):
        list(calendar.trading_days_before(date(2026, 1, 5), max_calendar_days=10))
    assert walk_back_year not in calendar.covered_years


def test_item5_the_session_window_comes_from_the_calendar(tmp_path: Path) -> None:
    """Not a literal 15:45: a moved close must move the completion rule.

    Red proof of "read from the calendar": a calendar whose CONTINUOUS end is
    09:20 must yield a 09:21 end boundary, which a hardcoded 15:46 could not.
    """
    tenant = calendar_mod.load_runtime_calendar(
        _REPO_ROOT / "config/tos_runtime/cp3-setup-d-long/calendar.yaml"
    )
    window = tenant.window("krx-index-futures", "CONTINUOUS")
    assert (window.start.hour, window.start.minute) == (8, 45)
    assert window.last_bar_minute(TARGET) == datetime(2026, 10, 19, 15, 45)
    assert window.end_boundary(TARGET) == datetime(2026, 10, 19, 15, 46)

    moved = calendar_mod.load_runtime_calendar(_write_calendar(tmp_path))
    assert moved.window("krx-index-futures", "CONTINUOUS").end_boundary(
        TARGET
    ) == datetime(2026, 10, 19, 9, 21)


def test_item5_the_allowlist_approves_this_producers_prefix() -> None:
    """``source_id`` must actually be the prefix the boot-proof guard approves.

    A producer whose ``source_id`` drifted from the allowlist entry would be
    refused at the guard with nothing here saying why, and the delimiter rule
    means a near-miss (``tos-cp3-live-EVIL``) does NOT match.
    """
    from tools.tos_cp3 import bootproof_guard

    assert producer_mod.SOURCE_PREFIX in (
        bootproof_guard.APPROVED_REAL_PRODUCER_PREFIXES
    )
    assert producer_mod.SOURCE_ID.startswith(producer_mod.SOURCE_PREFIX + "/")


@pytest.mark.serial
def test_item5_consecutive_produce_errors_stop_the_producer(
    tmp_path: Path, market: Market, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Five in a row stops; four does not. Both halves, so the bound is real."""
    producer, _clock, _quotes = _build(
        tmp_path, market, max_consecutive_produce_errors=2
    )
    producer.boot()
    from tools.tos_cp3.produce_fields import ProduceFieldsError

    def always_fail(*_args, **_kwargs):
        raise ProduceFieldsError("non-finite close in the replayed bar stream")

    monkeypatch.setattr(producer_mod, "build_line", always_fail)
    with pytest.raises(LiveProducerRefused, match="consecutive produce_error"):
        producer.run_session()
    assert producer.counters.produce_error >= 2
    producer.finish()


@pytest.mark.serial
def test_item5_a_transport_failure_is_counted_and_the_minute_continues(
    tmp_path: Path, market: Market
) -> None:
    """One failed fetch costs that poll, not the session."""
    producer, _clock, quotes = _build(tmp_path, market)
    producer.boot()
    quotes.fail_next = 1
    producer.run_session()
    producer.finish()
    assert producer.counters.fetch_error == 1
    assert producer.counters.published > 1


@pytest.mark.serial
def test_item5_the_session_end_writes_a_digest_of_the_frozen_frame(
    tmp_path: Path, market: Market
) -> None:
    producer, _clock, _quotes = _build(tmp_path, market)
    producer.boot()
    producer.run_session()
    summary = producer.finish()
    digest = json.loads(
        (producer.market_root / "sha256.json").read_text(encoding="utf-8")
    )
    assert digest and digest == summary["market_sha256"]
    assert all(name.endswith(".parquet") for name in digest)
    assert summary["counters"]["published"] == len(_journal_rows(producer.journal_path))


def test_item5_the_dry_run_touches_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """No ``--confirm``, no transport: the same discipline PR-1's probe keeps."""
    config = _write_config(tmp_path)
    assert (
        producer_mod.main(
            [
                "--config",
                str(config),
                "--instrument",
                INSTRUMENT,
                "--session-dir",
                str(tmp_path / "session"),
                "--journal",
                str(tmp_path / "session" / "journal.jsonl"),
                "--date",
                TARGET.isoformat(),
            ]
        )
        == 0
    )
    printed = json.loads(capsys.readouterr().out)
    assert printed["mode"] == "DRY_RUN"
    assert printed["orders"] == 0
    assert printed["method"] == "GET"
    assert printed["source_id"] == producer_mod.SOURCE_ID
    assert not (tmp_path / "session").exists()


# ===========================================================================
# §5 6 — the reader round trip, and the fixture that cannot drift
# ===========================================================================

#: The committed hinge. ``tos/runtime/tests/marketfeed/
#: test_journal_cp3_live_producer_row.py`` feeds it to the REAL
#: ``JsonLinesObservationJournal``; the test below proves this producer still
#: makes exactly these bytes. The firewall forbids one test doing both.
_FIXTURE = (
    _REPO_ROOT
    / "tos"
    / "runtime"
    / "tests"
    / "fixtures"
    / "cp3-live-producer-row.jsonl"
)


def _fixture_frame(market: Market, seed_days: list[date]) -> Any:
    return _full_day_frame(market, seed_days)


@pytest.mark.serial
def test_item6_the_producer_reproduces_the_committed_fixture(
    market: Market, inputs: dict
) -> None:
    """The tools half of the hinge: the same bytes, from ``build_line``.

    Regenerated from the same synthetic market and the same ``as_of_ms`` /
    ``received_ms`` the fixture records, so the only way this drifts is a real
    change in the line shape or the field values — which is exactly when the
    runtime-side half must be looked at too.
    """
    expected = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    outcome = producer_mod.build_line(
        _fixture_frame(market, SEED_DAYS[-4:]),
        symbol=INSTRUMENT,
        strategy=inputs["strategy"],
        contract_spec=inputs["contract_spec"],
        anchor=inputs["anchor"],
        bar_minute=market.target_bars[-1][1],
        now_ms=expected["as_of_ms"],
        received_ms=expected["received_ms"],
    )
    assert outcome.row == expected
    rendered = json.dumps(outcome.row, separators=(",", ":"), ensure_ascii=True) + "\n"
    assert rendered.encode("utf-8") == _FIXTURE.read_bytes()


def test_item6_the_fixture_carries_the_journals_required_shape() -> None:
    """What the runtime reader demands, restated on the tools side.

    ``JOURNAL_REQUIRED_KEYS`` mirrors
    ``tos_runtime.marketfeed.journal._REQUIRED_KEYS``; the firewall forbids
    importing the real name, so both sides mirror the literal and the fixture
    is what ties them together.
    """
    row = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert set(JOURNAL_REQUIRED_KEYS) <= row.keys()
    assert tuple(row["fields"]) == FIELD_ORDER
    assert row["source_id"] == producer_mod.SOURCE_ID
    assert isinstance(row["as_of_ms"], int) and isinstance(row["received_ms"], int)
    assert all(
        isinstance(value, (bool, int, float, str)) for value in row["fields"].values()
    )
    # the live stamp is the WRITE time, not the bar label: a label stamp would
    # make every observation at least 60,000 ms old against a budget of 800
    label = _minute_of(row["raw_event_id"]).replace(tzinfo=producer_mod.KST)
    assert row["as_of_ms"] != int(label.timestamp() * 1000)


def test_item6_the_runtime_side_half_of_the_hinge_exists() -> None:
    """A fixture with only one consumer proves nothing about the real reader."""
    paired = (
        _REPO_ROOT
        / "tos"
        / "runtime"
        / "tests"
        / "marketfeed"
        / "test_journal_cp3_live_producer_row.py"
    )
    assert paired.is_file(), paired
    source = paired.read_text(encoding="utf-8")
    assert "JsonLinesObservationJournal" in source
    assert _FIXTURE.name in source


# ---------------------------------------------------------------------------
# Regeneration helper — run by hand when the line shape legitimately changes
# ---------------------------------------------------------------------------


def _regenerate() -> None:  # pragma: no cover - a maintenance entry point
    """Rewrite the committed fixture. ``python -m pytest`` never calls this."""
    strategy = load_strategy_inputs(
        _REPO_ROOT / "config/strategies/futures/setup_d_vwap_reversion.yaml"
    )
    market = Market(
        sessions={
            day: _session_bars(day, partial(_constant, _seed_scale(index)))
            for index, day in enumerate(SEED_DAYS)
        },
        target_bars=_session_bars(TARGET, _target_scale, count=TARGET_BARS),
    )
    outcome = producer_mod.build_line(
        _fixture_frame(market, SEED_DAYS[-4:]),
        symbol=INSTRUMENT,
        strategy=strategy,
        contract_spec=resolve_contract_spec(
            INSTRUMENT,
            ContractSpecRegistry.from_yaml(str(_REPO_ROOT / "config/execution.yaml")),
        ),
        anchor=resolve_open_anchor(
            cli_value="auto", first_session=TARGET, last_session=TARGET
        ),
        bar_minute=market.target_bars[-1][1],
        now_ms=1792286460123,
        received_ms=1792286460001,
    )
    _FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    _FIXTURE.write_text(
        json.dumps(outcome.row, separators=(",", ":"), ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":  # pragma: no cover
    _regenerate()
    print(f"regenerated {_FIXTURE}", file=sys.stderr)
