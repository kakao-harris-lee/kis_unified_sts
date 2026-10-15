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
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from shared.collector.historical.ohlcv_parser import parse_ohlcv
from tools.tos_cp3 import quote_client
from tools.tos_cp3.live_producer import band as band_mod
from tools.tos_cp3.live_producer import band_line as band_line_mod
from tools.tos_cp3.live_producer import calendar as calendar_mod
from tools.tos_cp3.live_producer import config as config_mod
from tools.tos_cp3.live_producer import frame as frame_mod
from tools.tos_cp3.live_producer import line as line_mod
from tools.tos_cp3.live_producer import producer as producer_mod
from tools.tos_cp3.live_producer import real_quotes as real_quotes_mod
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


#: The band response the fake serves. The three values are P-VL's 2026-10-08
#: MOCK measurement of ``A05611`` (upper 1162.72 / lower 990.48 — the pair that
#: landed on the MINI 0.02 tick grid) with a basis between them. Strings,
#: because the broker sends strings and the producer copies them verbatim.
BAND_UPPER, BAND_LOWER, BAND_BASIS = "1162.72", "990.48", "1076.60"


def _band_payload(
    *, upper: str = BAND_UPPER, lower: str = BAND_LOWER, basis: str = BAND_BASIS
) -> dict:
    """A ``FHMIF10000000`` body, shaped like the one the broker sends.

    ``output1`` is the member, measured twice: the official wrapper returns
    ``output1``/``output2``/``output3`` for this TR and P-VL reads its five L1
    price fields out of ``output1``.
    """
    return {
        "rt_cd": "0",
        "msg_cd": "MCA00000",
        "output1": {
            "futs_prpr": "1076.60",
            "futs_prdy_clpr": "1076.60",
            "futs_sdpr": basis,
            "futs_mxpr": upper,
            "futs_llam": lower,
        },
    }


class FakeQuotes:
    """The fixture server. GET-only by construction: it has no other method."""

    def __init__(self, market: Market, clock: FakeClock, *, page_size: int = 120):
        self.market, self.clock, self.page_size = market, clock, page_size
        self.calls = 0
        self.history_calls = 0
        self.http = None
        self.last_received_kst = clock.now()
        self.fail_next = 0
        #: ``minute -> seconds past its own boundary before the row appears``.
        #: Anything over G makes that boundary miss its bar (review M1).
        self.hold_until: dict[datetime, float] = {}
        # -- band (band plan §3.1). Deliberately on their OWN counters and
        # their own failure switch: a band read must not consume the price
        # path's `fail_next`, spend its pace or move `calls`, or every
        # pre-existing timing assertion in this file would be measuring the
        # band instead of what it was written for.
        self.band_calls = 0
        self.band_fail_next = 0
        #: Seconds of fake clock one band attempt costs. 0 by default, so the
        #: band is invisible to every test that is not about it.
        self.band_cost_s = 0.0
        self.band_payload: dict | None = None
        #: The clock at each band attempt, and at each price page — the two
        #: sequences the "band does not push the next poll" proof compares.
        self.band_started: list[datetime] = []
        self.poll_started: list[datetime] = []

    def _arrival(self, minute: datetime) -> datetime:
        return minute + timedelta(seconds=self.hold_until.get(minute, ARRIVAL_LAG_S))

    def _visible(self, day: date) -> list[dict]:
        rows = self.market.rows(day)
        if day != TARGET:
            return rows  # a past session is complete
        now = self.clock.now().replace(tzinfo=None)
        return [
            row
            for row in rows
            if self._arrival(
                datetime.strptime(
                    row["stck_bsop_date"] + row["stck_cntg_hour"], "%Y%m%d%H%M%S"
                )
            )
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
        self.poll_started.append(self.clock.now())
        self._receive()
        return self._visible(day)[-self.page_size :]

    def band(self, symbol: str) -> quote_client.BandRead:
        """One band attempt. Same contract as ``Quotes.band``: raise or return."""
        self.band_calls += 1
        self.band_started.append(self.clock.now())
        self.clock.sleep(self.band_cost_s)
        if self.band_fail_next:
            self.band_fail_next -= 1
            raise RuntimeError("band_auth_http_or_json_error")
        payload = (
            self.band_payload if self.band_payload is not None else _band_payload()
        )
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return quote_client.BandRead(
            payload=payload, raw_payload_digest=hashlib.sha256(raw).hexdigest()
        )

    def history(self, symbol: str, day: date) -> list[dict]:
        self.history_calls += 1
        self._receive()
        return self._visible(day)


# ---------------------------------------------------------------------------
# Config + calendar on disk
# ---------------------------------------------------------------------------


#: The years the producer's YAML declares for the tenant calendar (review L4).
COVERED_YEARS = (2026,)


def _tenant_calendar(*, covered_years=COVERED_YEARS):
    return calendar_mod.load_runtime_calendar(
        _REPO_ROOT / "config/tos_runtime/cp3-setup-d-long/calendar.yaml",
        covered_years=covered_years,
    )


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
        calendar=_tenant_calendar(),
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


def _row(raw_event_id: str = "A05611:1m:20261019T090000+0900") -> dict:
    """A journal row as ``build_line`` returns it — with NO ``as_of_ms``."""
    return {
        "raw_event_id": raw_event_id,
        "source_id": line_mod.SOURCE_ID,
        "instrument": INSTRUMENT,
        "received_ms": 1_792_286_460_001,
        "fields": dict.fromkeys(FIELD_ORDER, 1),
    }


def _journal_at(path: Path, stamps: list[int]) -> sinks_mod.ObservationJournal:
    """A journal whose clock hands out *stamps* in order."""
    feed = iter(stamps)
    return sinks_mod.ObservationJournal(path, clock=lambda: next(feed))


def test_item2_as_of_ms_must_advance(tmp_path: Path) -> None:
    journal = _journal_at(tmp_path / "journal.jsonl", [1_000, 1_001])
    assert journal.append(_row()).written
    assert journal.append(_row()).written
    assert [row["as_of_ms"] for row in _journal_rows(journal.path)] == [1_000, 1_001]


@pytest.mark.parametrize("second", [1_000, 999])
def test_item2_red_a_non_advancing_stamp_is_refused(
    tmp_path: Path, second: int
) -> None:
    """Equal is refused as well as backwards — and the session goes ON.

    The reader returns rows strictly newer than ``after_as_of_ms``, so an EQUAL
    stamp is a line nothing can ever consume; a ``>=`` here would admit exactly
    the silent loss the guard is named for.

    Plan §2 5 says to refuse THAT WRITE and log it. It does not say to end the
    session, and raising would have cost every remaining minute of a market day
    (review L6) — so this returns an outcome the caller counts.
    """
    journal = _journal_at(tmp_path / "journal.jsonl", [1_000, second, 1_002])
    assert journal.append(_row()).written

    refused = journal.append(_row())
    assert not refused.written
    assert refused.reason == "clock_regression"
    assert len(_journal_rows(journal.path)) == 1
    # the journal is still usable: the next advancing stamp is written
    assert journal.append(_row()).written
    assert [row["as_of_ms"] for row in _journal_rows(journal.path)] == [1_000, 1_002]


def test_item2_the_caller_may_not_supply_the_stamp(tmp_path: Path) -> None:
    """``as_of_ms`` belongs to the journal (review B1), enforced not just documented."""
    journal = sinks_mod.ObservationJournal(tmp_path / "journal.jsonl")
    with pytest.raises(LiveProducerRefused, match="the caller supplied as_of_ms"):
        journal.append({**_row(), "as_of_ms": 1_000})
    assert not (tmp_path / "journal.jsonl").exists()


@pytest.mark.serial
def test_item2_red_the_stamp_is_taken_after_produce_bars_not_before(
    tmp_path: Path, market: Market, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The B1 defect, as a clock that moves DURING the compute.

    ``produce_bars`` was measured at ~0.44 s late in a session, against a
    tenant budget of ``max_age_ms`` 800 with 300 ms left for the collector. A
    stamp taken before the compute is therefore stale on arrival. Here the fake
    clock advances 5 s inside ``produce_bars``, so a pre-compute stamp is 5 s
    behind the post-compute clock and the assertion below fails — which is
    exactly what it did before the fix.
    """
    producer, clock, _quotes = _build(tmp_path, market)
    clock.moment = datetime(
        TARGET.year, TARGET.month, TARGET.day, 9, 10, 5, tzinfo=producer_mod.KST
    )
    # patched on `line`, which is where `build_line` reads it from since the
    # pure half moved there (PR #904 review round 1 item A.5)
    real_produce_bars = line_mod.produce_bars
    compute_cost_s = 5.0

    def slow_produce_bars(*args, **kwargs):
        result = real_produce_bars(*args, **kwargs)
        clock.sleep(compute_cost_s)  # the compute takes real time
        return result

    monkeypatch.setattr(line_mod, "produce_bars", slow_produce_bars)
    before = clock.now()
    producer.boot()
    producer.finish()

    rows = _journal_rows(producer.journal_path)
    assert len(rows) == 1
    stamped = rows[0]["as_of_ms"]
    # the stamp is AFTER the compute, not before it
    assert stamped >= int((before.timestamp() + compute_cost_s) * 1000)
    assert stamped <= int(clock.now().timestamp() * 1000)


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
    # the morning's bars are HISTORY, not late arrivals: `late_completed` is
    # reserved for a bar whose own boundary passed while the session ran
    assert producer.counters.late_completed == 0
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
def test_item3_a_full_run_freezes_the_gap_bar_and_publishes_the_session_end_bar(
    tmp_path: Path, market: Market
) -> None:
    """End to end, with a hole in the raw feed where 15:35-15:44 was.

    The session's second-to-last minute is withheld from the fixture entirely,
    so the bar before it has no ``m+1`` successor — the 15:34 shape — and the
    last bar is the session end minute — the 15:45 shape.

    **The two get different dispositions** (review M1). The gap bar is
    COMPLETED into the frame and written to Parquet, which is all evidence §2.2
    requires and all B1a parity needs; it is NOT published, because plan §3.3
    skips publication after G and a line stamped at 15:46 for a 15:34 bar would
    be consumed as the current observation. The session-end bar IS published,
    because 15:46 is its own boundary.
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
    frozen = {bar[1] for bar in producer.frozen}
    gap_bar = market.target_bars[-3][1]
    last_bar = market.target_bars[-1][1]

    # the session-end bar: its own boundary, so published
    assert _event_id(last_bar) in published
    assert last_bar in frozen
    # the gap bar: completed into the frame, deliberately NOT published
    assert gap_bar in frozen
    assert _event_id(gap_bar) not in published
    assert producer.counters.late_completed >= 1
    # and the withheld minute never becomes a bar at all
    assert withheld not in frozen
    assert producer.counters.no_raw_row_for_minute >= 1
    # every frozen bar reached Parquet, so B1a reads the same frame
    stored = len(list((producer.market_root).rglob("*.parquet")))
    assert stored >= len(producer.frozen)


@pytest.mark.serial
def test_item3_red_a_late_bar_does_not_steal_the_current_bars_publication(
    tmp_path: Path, market: Market
) -> None:
    """The measured M1 cascade: two late rows in a row.

    Reproduces the reviewer's scenario. One minute's row arrives past G so its
    boundary ends in ``missing_no_successor``; at the NEXT boundary the first
    poll completes only that older bar. The first cut returned there — it
    published the stale bar under a fresh stamp and never looked for the
    current bar again, so the current bar was lost with no counter naming it.

    Now: the late bar is frozen and counted, the loop keeps polling, and the
    current bar is the one that gets published.

    **The second hold is what makes this test discriminate** (review N2).
    Holding only ``successor`` left both bars complete in the NEXT boundary's
    very first poll, so "return on the late bar" and "keep polling" produced the
    same journal and the mutation passed. Holding ``successor``'s own successor
    to 2.5 s — past the first poll at +1.8 s, inside G — puts the late bar
    ALONE in that first poll, which is the shape the cascade needs.
    """
    starved = market.target_bars[25][1]  # the bar whose boundary will miss
    successor = market.target_bars[26][1]  # its completion signal, held back
    producer, _clock, quotes = _build(tmp_path, market)
    # The successor row appears 12 s past ITS own boundary — past G = 10 s from
    # `starved`'s boundary, so `starved` cannot complete inside its own window.
    # And `successor`'s own completion signal arrives at +2.5 s, so the first
    # poll of ITS boundary sees `starved` completing and nothing else.
    quotes.hold_until = {successor: 12.0, market.target_bars[27][1]: 2.5}
    producer.boot()
    producer.run_session()
    producer.finish()

    published = [
        _minute_of(r["raw_event_id"]) for r in _journal_rows(producer.journal_path)
    ]
    frozen = {bar[1] for bar in producer.frozen}

    # the starved minute's own boundary published nothing...
    assert starved not in published
    assert producer.counters.missing_no_successor >= 1
    # ...it still reached the frame, so B1a sees the same bars...
    assert starved in frozen
    assert producer.counters.late_completed >= 1
    # ...and the NEXT boundary published ITS OWN bar rather than returning on
    # the late one (the cascade: the first cut lost this bar entirely)
    assert successor in published
    assert successor in frozen
    # no published line is older than the one before it
    assert published == sorted(published)


@pytest.mark.serial
def test_item3_red_a_stalled_poll_publishes_the_newest_frozen_bar(
    tmp_path: Path, market: Market
) -> None:
    """One poll that returns past the NEXT boundary (review N1).

    Reachable without anything exotic: one request may take 3 x 10 s of
    transport timeout plus 2 x 2 s of backoff, and ``history()`` escalation adds
    a second request on top of that.

    The exact repro the reviewer wrote: ``catch_up``'s row is held 30 s, so
    ``stalled``'s own boundary finds no successor, and the poll issued at
    09:16:08 does not return until 09:17:06 — by which time ``following``'s row
    exists and BOTH bars are complete in that one response.

    Before the fix the pair was lost under two wrong labels: ``stalled`` was
    published over a frame that already ended at ``catch_up``, so ``build_line``
    returned ``omitted_unusable``; ``catch_up`` was counted ``skipped_behind``
    and then, at its own boundary, polled for the full G and logged
    ``missing_no_successor`` with ``bar_minute_traded: true`` — for a bar that
    was sitting frozen in the frame. Now the newest newly frozen bar is
    published as a catch-up and the boundary it already covered returns at once.
    """
    stalled = market.target_bars[30][1]  # 09:15 — overtaken by the stall
    catch_up = market.target_bars[31][1]  # 09:16 — complete when the poll returns
    following = market.target_bars[32][1]  # 09:17 — the next ordinary boundary
    producer, clock, quotes = _build(tmp_path, market)
    quotes.hold_until = {catch_up: 30.0}

    stall_at = catch_up + timedelta(seconds=8)
    inner_page, stalled_once = quotes.page, []

    def stalling_page(symbol: str, day: date, cursor: str = "") -> list[dict]:
        if not stalled_once and clock.now().replace(tzinfo=None) >= stall_at:
            stalled_once.append(clock.now())
            clock.sleep(58.0)  # the response arrives at 09:17:06
        return inner_page(symbol, day, cursor)

    quotes.page = stalling_page
    producer.boot()
    producer.run_session()
    producer.finish()

    assert stalled_once, "the repro never stalled — the poll pacing moved"
    published = [
        _minute_of(r["raw_event_id"]) for r in _journal_rows(producer.journal_path)
    ]
    frozen = {bar[1] for bar in producer.frozen}

    # the newest bar the stalled poll froze is the one that gets published...
    assert catch_up in published
    # ...the overtaken bar is frozen and counted, not mislabelled
    assert stalled in frozen
    assert stalled not in published
    assert producer.counters.skipped_behind >= 1
    assert producer.counters.omitted_unusable == 0
    # ...the boundary the catch-up already covered polls nothing and claims no
    # missing successor for a bar that is frozen
    assert producer.counters.missing_no_successor == 0
    assert producer.counters.already_published == 1
    # ...and the session carries on at the next ordinary boundary
    assert following in published

    # the invariants this catch-up must not break
    assert len(published) == len(set(published))  # nothing published twice
    assert published == sorted(published)  # strictly increasing minutes
    assert set(published) <= frozen  # only bars that entered the frame


@pytest.mark.serial
def test_red_i1_a_minute_that_never_existed_is_not_called_already_published(
    tmp_path: Path, market: Market
) -> None:
    """**PR #898 round-3 review I1.** The reviewer's exact repro.

    Minute ``m+1`` leaves no raw row at all, and the poll at ITS boundary
    stalls past ``m+3``'s row, so one response completes ``m`` and ``m+2``
    together and the catch-up publishes ``m+2``. The next boundary is about
    ``m+1`` — a minute that never traded.

    The first cut answered that boundary from the last PUBLISHED minute alone
    (``bar_minute <= last_published_minute``), so it logged
    ``already_published`` for ``m+1``: a publication claim about a bar that was
    never frozen, never published, and never existed. The counter then read 2
    for one real catch-up. The predicate is now the FRAME — ``m+1`` is not in
    it and never can be (``freeze_step`` only returns bars after the last
    frozen minute), so the boundary records the true reason,
    ``no_raw_row_for_minute``.

    Remove the ``_is_frozen`` branch of
    :meth:`LiveProducer._boundary_already_settled` and this test goes red on
    ``already_published == 1``.
    """
    m = market.target_bars[30][1]  # 09:15 — completes only via m+2's row
    missing = market.target_bars[31][1]  # 09:16 — no raw row, ever
    m2 = market.target_bars[32][1]  # 09:17 — the catch-up publication
    producer, clock, quotes = _build(tmp_path, market)
    quotes.hold_until = {missing: 10_000.0}

    # The poll issued at m+1's boundary (+δ) returns only after m+3's row
    # exists, so m and m+2 are both complete in that one response.
    stall_at = missing + timedelta(seconds=1)
    inner_page, stalled_once = quotes.page, []

    def stalling_page(symbol: str, day: date, cursor: str = "") -> list[dict]:
        if not stalled_once and clock.now().replace(tzinfo=None) >= stall_at:
            stalled_once.append(clock.now())
            clock.sleep(120.0)
        return inner_page(symbol, day, cursor)

    quotes.page = stalling_page
    producer.boot()
    producer.run_session()
    producer.finish()

    assert stalled_once, "the repro never stalled — the poll pacing moved"
    events = [
        json.loads(line)
        for line in (producer.session_dir / "producer-log.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    published = [
        _minute_of(r["raw_event_id"]) for r in _journal_rows(producer.journal_path)
    ]
    frozen = {bar[1] for bar in producer.frozen}

    # the repro really happened: m+1 never became a bar, m+2 was the catch-up
    assert missing not in frozen
    assert m in frozen
    assert m2 in published
    # the boundary about the minute that never existed says exactly that...
    missing_events = [e for e in events if e.get("bar") == str(missing)]
    assert [e["stage"] for e in missing_events] == ["no_raw_row_for_minute"]
    assert missing_events[0]["raw_event_id"] == _event_id(missing)
    # ...and the publication counter counts the ONE real catch-up (m+2's own
    # boundary), not two.
    assert producer.counters.already_published == 1
    assert [e["bar"] for e in events if e["stage"] == "already_published"] == [str(m2)]


@pytest.mark.serial
def test_red_i2_an_omitted_catch_up_does_not_count_as_published(
    tmp_path: Path, market: Market
) -> None:
    """**PR #898 round-3 review I2.** ``last_published_minute`` after the WRITE.

    The catch-up bar's ``build_line`` returns ``omitted_unusable``, so no line
    is written for it. The next boundary is about that same bar, and it must
    not claim a publication that did not happen — nor poll the full G and then
    report ``missing_no_successor`` with ``bar_minute_traded: true`` about a bar
    sitting completed in the frame, which is what the first cut did.

    Two red proofs in one body: move ``published_minutes.add`` above the
    ``outcome.row is None`` return and ``already_published`` becomes 1; drop
    the frozen-but-unpublished branch of
    :meth:`LiveProducer._boundary_already_settled` and ``missing_no_successor``
    becomes 1 with ``bar_minute_traded: true``.
    """
    stalled = market.target_bars[30][1]  # 09:15
    catch_up = market.target_bars[31][1]  # 09:16 — frozen, publication omitted
    producer, clock, quotes = _build(tmp_path, market)
    quotes.hold_until = {catch_up: 30.0}

    stall_at = catch_up + timedelta(seconds=8)
    inner_page, stalled_once = quotes.page, []

    def stalling_page(symbol: str, day: date, cursor: str = "") -> list[dict]:
        if not stalled_once and clock.now().replace(tzinfo=None) >= stall_at:
            stalled_once.append(clock.now())
            clock.sleep(58.0)
        return inner_page(symbol, day, cursor)

    quotes.page = stalling_page

    real_build_line = producer_mod.build_line

    def omit_the_catch_up(frame: Any, **kwargs: Any) -> Any:
        if kwargs["bar_minute"] == catch_up:
            return line_mod.LineOutcome(
                reason="omitted_unusable", raw_event_id=_event_id(catch_up)
            )
        return real_build_line(frame, **kwargs)

    producer_mod.build_line = omit_the_catch_up
    try:
        producer.boot()
        producer.run_session()
        producer.finish()
    finally:
        producer_mod.build_line = real_build_line

    assert stalled_once, "the repro never stalled — the poll pacing moved"
    events = [
        json.loads(line)
        for line in (producer.session_dir / "producer-log.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    journal_minutes = {
        _minute_of(r["raw_event_id"]) for r in _journal_rows(producer.journal_path)
    }

    # the repro: the catch-up bar is in the frame, and its line was omitted
    assert catch_up in {bar[1] for bar in producer.frozen}
    assert producer.counters.omitted_unusable == 1
    assert catch_up not in journal_minutes
    # the publication bookkeeping follows the WRITE, not the attempt
    assert producer.published_minutes == journal_minutes
    assert producer.last_published_minute == max(journal_minutes)
    assert catch_up not in producer.published_minutes
    # the next boundary claims no publication and invents no missing successor
    assert producer.counters.already_published == 0
    assert producer.counters.missing_no_successor == 0
    assert [e["stage"] for e in events if e.get("bar") == str(catch_up)] == [
        "omitted_unusable",
        producer_mod.STAGE_ALREADY_FROZEN,
    ]
    # the overtaken bar is still accounted for where it always was
    assert stalled in {bar[1] for bar in producer.frozen}
    assert producer.counters.skipped_behind >= 1


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
    journal = _journal_at(tmp_path / "journal.jsonl", [1_000, 1_001])
    assert journal.append(_row()).written
    after_first = (tmp_path / "journal.jsonl").read_text(encoding="utf-8")
    seen: list[str] = []
    original = os.replace

    def spy(src, dst):
        # what a reader sees at the instant BEFORE the rename
        seen.append((tmp_path / "journal.jsonl").read_text(encoding="utf-8"))
        return original(src, dst)

    sinks_mod.os.replace = spy
    try:
        assert journal.append(_row()).written
    finally:
        sinks_mod.os.replace = original
    # mid-write the file still holds EXACTLY the previous complete line — the
    # expectation is the writer's own bytes, not a re-serialisation here
    assert seen == [after_first]
    assert len(_journal_rows(journal.path)) == 2
    assert list(tmp_path.glob("*.tmp")) == []
    assert list(tmp_path.glob(".*.tmp")) == []


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


def _module_source(name: str, root: Path) -> Path | None:
    parts = name.split(".")
    for candidate in (
        root.joinpath(*parts).with_suffix(".py"),
        root.joinpath(*parts, "__init__.py"),
    ):
        if candidate.is_file():
            return candidate
    return None


def _import_closure(module_name: str, *, root: Path | None = None) -> set[str]:
    """Every module reachable by a static import walk from *module_name*.

    Static, not ``sys.modules``: an order path imported lazily inside a
    function would not appear in a runtime snapshot of a module that was never
    called, and "we never called it" is not the claim being made.

    Two things the first cut got wrong and this does not (review M3):

    * **parent packages.** Importing ``a.b.c`` executes ``a/__init__.py`` and
      ``a/b/__init__.py``, so whatever THOSE import is in the graph too. The
      measured consequence of skipping them: the real closure reaches
      ``shared.execution`` through ``shared.backtest.config``, and the old walk
      reported the producer as having no ``shared.execution`` edge at all.
    * **relative imports.** ``from .b import thing`` has ``node.module is
      None`` or a non-zero ``node.level``; the old walk skipped every one, so
      any package that reaches an order path through its own siblings was
      invisible.
    """
    base = _REPO_ROOT if root is None else root
    seen: set[str] = set()
    queue = [module_name]
    while queue:
        name = queue.pop()
        if not name or name in seen:
            continue
        seen.add(name)
        parts = name.split(".")
        # Parent packages run their own __init__ on the way in.
        queue.extend(".".join(parts[:depth]) for depth in range(1, len(parts)))
        source = _module_source(name, base)
        if source is None:
            continue
        package = name if source.name == "__init__.py" else ".".join(parts[:-1])
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                queue.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    owner = package.split(".")
                    climb = node.level - 1
                    if climb:
                        owner = owner[: len(owner) - climb]
                    target = ".".join(owner + ([node.module] if node.module else []))
                else:
                    target = node.module or ""
                if not target:
                    continue
                queue.append(target)
                queue.extend(f"{target}.{alias.name}" for alias in node.names)
    return seen


#: The ONLY ``shared.execution`` modules the producer's closure may reach.
#: Measured on this branch, and asserted by EQUALITY below rather than by
#: "none of the bad ones" — an exact set is what turns a NEW arrival red.
#: All five are pure value/config modules: none contains an order call
#: (``place_order``/``order_cash``/``.post(``), which is checked here too so
#: the allowlist cannot quietly absorb something that grows one.
PURE_SHARED_EXECUTION = frozenset(
    {
        "shared.execution",
        "shared.execution.config",
        "shared.execution.contract_spec",
        "shared.execution.slippage_control",
        "shared.execution.slippage_model",
        "shared.execution.tr_ids",
    }
)

#: Modules that can put an order on the wire. Forbidden by NAME, because
#: "`shared.execution` is absent" is no longer true of the real closure.
ORDER_EMITTING_MODULES = (
    "shared.execution.executor",
    "shared.execution.venue_router",
    "shared.execution.kis_futures_adapter",
    "shared.execution.paper_kis_futures_adapter",
    "shared.execution.live_exit_executor",
    "shared.execution.force_close",
    "shared.execution.passive_maker",
    "shared.execution.pseudo_oco",
    "shared.execution.mock_mirror",
    "tools.broker_probes.probes_real_order",
    # Band plan §L L5 (review SUGGESTION), decided in PR-A: pinned. It emits
    # MOCK orders, which is not the real-money path `probes_real_order` is, but
    # it is still an order path and the producer must not reach it. Measured
    # free: the closure reaches `tools.broker_probes` (the package `__init__`,
    # which imports nothing) and `tools.broker_probes.common` only, so this
    # entry costs nothing today and turns a future `from .probes_order import
    # DEFAULT_PACE_S` convenience red — which is exactly the edge
    # `probes_balance`/`probes_ca` each declined by hand, in prose, twice.
    "tools.broker_probes.probes_order",
    "tos",
    "tos_runtime",
)


@pytest.fixture(scope="module")
def producer_closure() -> set[str]:
    return _import_closure("tools.tos_cp3.live_producer.producer")


@pytest.mark.parametrize("forbidden", ORDER_EMITTING_MODULES)
def test_item5_the_producer_import_graph_has_no_order_path(
    forbidden: str, producer_closure: set[str]
) -> None:
    """No order-emitting module, and no ``tos``/``tos_runtime``, in the closure.

    What is actually checked: the static closure — including parent packages
    and relative imports — contains none of
    :data:`ORDER_EMITTING_MODULES`. It does NOT claim the closure avoids
    ``shared.execution`` entirely; it does not, and
    :func:`test_item5_the_reached_shared_execution_modules_are_exactly_the_pure_set`
    pins which parts it reaches.
    """
    offending = sorted(
        name
        for name in producer_closure
        if name == forbidden or name.startswith(forbidden + ".")
    )
    assert not offending, offending
    # the walk really reached the producer's own dependencies
    assert "tools.tos_cp3.produce_fields" in producer_closure
    assert "tools.tos_cp3.quote_client" in producer_closure


def test_item5_the_reached_shared_execution_modules_are_exactly_the_pure_set(
    producer_closure: set[str],
) -> None:
    """Exact equality, so a newly reached module is red rather than tolerated.

    The producer reaches ``shared.execution`` transitively (e.g. through
    ``shared.backtest.config``). A containment check over a deny list would
    stay green when the next refactor pulls in a sixth module; equality does
    not. Each allowlisted module is also checked to contain no order call, so
    the list cannot absorb one that grows a wire path later.
    """
    reached = {
        name
        for name in producer_closure
        if (name == "shared.execution" or name.startswith("shared.execution."))
        and _module_source(name, _REPO_ROOT) is not None
    }
    assert reached == PURE_SHARED_EXECUTION

    order_calls = ("place_order", "order_cash", ".post(", "submit_order")
    for name in sorted(PURE_SHARED_EXECUTION):
        source = _module_source(name, _REPO_ROOT)
        assert source is not None
        text = source.read_text(encoding="utf-8")
        found = [call for call in order_calls if call in text]
        assert not found, f"{name} grew an order call: {found}"


def test_item5_red_the_closure_walker_sees_parents_and_relative_imports(
    tmp_path: Path,
) -> None:
    """The walker's own red proof — planted relative and parent-package edges.

    Three edges, each invisible to the first cut: a relative sibling import, a
    relative parent (``..``) import, and an order path reached only through a
    package ``__init__``. If any of them were skipped the assertions below
    would fail, which is the same shape as the real defect: the producer's
    ``shared.execution`` edge was reached through a parent ``__init__``.
    """
    (tmp_path / "pkg" / "sub").mkdir(parents=True)
    (tmp_path / "pkg" / "__init__.py").write_text(
        "import shared.execution.executor\n", encoding="utf-8"
    )
    (tmp_path / "pkg" / "sibling.py").write_text(
        "import shared.execution.venue_router\n", encoding="utf-8"
    )
    (tmp_path / "pkg" / "sub" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "sub" / "entry.py").write_text(
        "from .leaf import thing\nfrom ..sibling import other\n", encoding="utf-8"
    )
    (tmp_path / "pkg" / "sub" / "leaf.py").write_text(
        "import tools.broker_probes.probes_real_order\n", encoding="utf-8"
    )

    closure = _import_closure("pkg.sub.entry", root=tmp_path)

    # relative sibling (`.leaf`) -> and what it imports
    assert "pkg.sub.leaf" in closure
    assert "tools.broker_probes.probes_real_order" in closure
    # relative parent (`..sibling`) -> and what it imports
    assert "pkg.sibling" in closure
    assert "shared.execution.venue_router" in closure
    # parent package __init__ -> and what it imports
    assert "pkg" in closure
    assert "shared.execution.executor" in closure


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


def test_item5_red_a_second_producer_on_one_session_is_refused(
    tmp_path: Path,
) -> None:
    """The lock is per SESSION, not per journal (review L5).

    The failing input is the one a per-journal lock let through: two producers
    aimed at the same ``--session-dir`` with DIFFERENT ``--journal`` paths.
    Both would then append to the same Parquet partitions, which is the
    duplicate-timestamp input loss ``refuse_if_partitions_exist`` exists to
    prevent — and neither journal path would collide, so a per-journal lock saw
    nothing wrong.
    """
    market_root = tmp_path / "session" / "market"
    held = sinks_mod.acquire_session_lock(market_root)
    try:
        with pytest.raises(LiveProducerRefused, match="another producer holds"):
            sinks_mod.acquire_session_lock(market_root)
    finally:
        held.close()
    # released: the next acquire succeeds
    sinks_mod.acquire_session_lock(market_root).close()
    # and the lock file is not something B1a or the store would read as input
    assert list(market_root.rglob("*.parquet")) == []


def test_item5_red_the_lock_is_held_while_the_refusals_run(
    tmp_path: Path, market: Market, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ORDERING, observed rather than assumed (review L5).

    The refusals read the very state a second producer is about to create, so
    checking before locking is a race both processes win. Single-threaded, the
    way to see the order is from inside a refusal: while
    ``refuse_if_partitions_exist`` runs, a second ``acquire_session_lock`` on
    the same market root must already FAIL. If the lock were taken afterwards
    it would succeed, and this test is what turns that red.
    """
    observed: dict[str, bool] = {}
    real_refuse = producer_mod.refuse_if_partitions_exist

    def spy(market_root: Path, **kwargs):
        try:
            sinks_mod.acquire_session_lock(market_root).close()
            observed["locked_first"] = False
        except LiveProducerRefused:
            observed["locked_first"] = True
        return real_refuse(market_root, **kwargs)

    monkeypatch.setattr(producer_mod, "refuse_if_partitions_exist", spy)
    producer, _clock, _quotes = _build(tmp_path, market)
    producer.boot()
    producer.finish()

    assert observed == {"locked_first": True}


@pytest.mark.serial
def test_item5_red_a_second_producer_on_the_same_session_dir_is_refused(
    tmp_path: Path, market: Market
) -> None:
    """Two producers, one session dir, two DIFFERENT journals (review L5).

    This is the input a per-journal lock let through: neither journal path
    collides, so the old lock saw nothing wrong, and both would then append to
    the same Parquet partitions — the duplicate timestamps B1a refuses.
    """
    first, _clock, _quotes = _build(tmp_path, market)
    first.boot()
    try:
        second = producer_mod.LiveProducer(
            config=first.config,
            instrument=INSTRUMENT,
            target=TARGET,
            session_dir=first.session_dir,  # SAME session
            journal_path=first.session_dir / "other-journal.jsonl",  # different journal
            clock=first.clock,
            quotes_factory=lambda _c, _l: pytest.fail("got past the lock"),
        )
        with pytest.raises(LiveProducerRefused, match="session lock"):
            second.boot()
    finally:
        first.finish()


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

    # Neither value appears as a NUMBER anywhere in the producer's code. Asked
    # of the AST, not of the file text: a substring scan matched the "+1.8 s"
    # and "09:06:01.85" in the prose and would have had to be loosened until it
    # checked nothing.
    for module in ("producer.py", "frame.py", "sinks.py", "calendar.py"):
        tree = ast.parse(
            (_REPO_ROOT / "tools/tos_cp3/live_producer" / module).read_text("utf-8")
        )
        literals = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
        }
        assert shipped.first_poll_delay_s not in literals, module
        assert shipped.missing_no_successor_timeout_s not in literals, module


@pytest.mark.serial
def test_item5_red_a_first_page_that_misses_the_open_escalates(
    tmp_path: Path, market: Market
) -> None:
    """With nothing frozen yet, the page must reach the session OPEN (review M2).

    The failing input: a page so short it cannot reach 08:45. The first cut
    only escalated when something was already frozen, so the very first
    successful page started today's frame mid-morning — a hole B1a does not
    have, in the one place no later poll repairs. Here the page carries two
    rows; the producer must fall back to ``history()`` and the frame must start
    at the session open.
    """
    producer, clock, quotes = _build(tmp_path, market)
    # Boot BEFORE the open, so its history fetch finds nothing and the frame
    # starts out empty — the `last_frozen is None` state the old check skipped.
    producer.boot()
    assert producer.frozen == [], "the premise is an empty frame at the first poll"

    # Now it is mid-morning and the page is too short to reach the open.
    clock.moment = datetime(
        TARGET.year, TARGET.month, TARGET.day, 9, 10, 5, tzinfo=producer_mod.KST
    )
    quotes.page_size = 2
    history_before = quotes.history_calls
    producer._handle_boundary(datetime(TARGET.year, TARGET.month, TARGET.day, 9, 11))
    producer.finish()

    assert quotes.history_calls > history_before, "never escalated to history()"
    assert producer.frozen, "froze nothing at all"
    assert producer.frozen[0][1] == datetime(
        TARGET.year, TARGET.month, TARGET.day, *OPEN_HM
    ), "today's frame did not start at the session open"
    # and no minute is missing or duplicated between the open and the last bar
    minutes = [bar[1] for bar in producer.frozen]
    assert minutes == sorted(minutes)
    assert len(set(minutes)) == len(minutes)


def test_item5_red_a_density_gate_that_is_not_b1as_refuses_to_start(
    tmp_path: Path,
) -> None:
    """One source of truth for the gate value (review M4).

    The gate decides which days enter the frame, so a producer running 300
    while B1a runs 330 seeds from a DIFFERENT set of sessions than the offline
    run it is compared against — and the B3 join then diverges for a reason
    that looks like a field defect. The key stays in config; its value is
    pinned to B1a's constant at load.
    """
    from tools.tos_cp3.produce_fields import DEFAULT_MIN_BARS_PER_DAY

    assert DEFAULT_MIN_BARS_PER_DAY == 330
    shipped = config_mod.load_config(
        _REPO_ROOT / "config/tos_probes/cp3-live-producer.yaml", repo_root=_REPO_ROOT
    )
    assert shipped.min_bars_per_day == DEFAULT_MIN_BARS_PER_DAY
    with pytest.raises(LiveProducerRefused, match="DEFAULT_MIN_BARS_PER_DAY"):
        config_mod.load_config(
            _write_config(tmp_path, min_bars_per_day=300), repo_root=_REPO_ROOT
        )


def test_item5_red_a_declared_covered_year_without_holidays_is_refused() -> None:
    """Coverage is declared and cross-checked, never inferred (review L4).

    Inferring from the holiday dates makes ONE forward-dated entry mark a whole
    year as covered, which is the silent "every weekday trades" that plan
    §3.2 L2's refusal exists to prevent. The tenant calendar is digest-bound so
    it cannot carry its own range; the declaration is checked against the file
    instead.
    """
    assert _tenant_calendar().covered_years == frozenset({2026})
    # a year the file does not really cover is refused, not accepted
    with pytest.raises(LiveProducerRefused, match="2027"):
        _tenant_calendar(covered_years=(2026, 2027))
    with pytest.raises(LiveProducerRefused, match="no covered years"):
        _tenant_calendar(covered_years=())
    # the shipped config declares exactly the year the tenant file covers
    shipped = config_mod.load_config(
        _REPO_ROOT / "config/tos_probes/cp3-live-producer.yaml", repo_root=_REPO_ROOT
    )
    assert shipped.calendar_covered_years == (2026,)


def test_item5_red_a_thin_year_is_refused_even_with_one_holiday(
    tmp_path: Path,
) -> None:
    """The concrete input L4 names: a single stray 2027 entry.

    One holiday is not a covered year. Built here rather than measured on the
    tenant file, because the tenant file must not be edited.
    """
    source = yaml.safe_load(
        (_REPO_ROOT / "config/tos_runtime/cp3-setup-d-long/calendar.yaml").read_text(
            encoding="utf-8"
        )
    )
    source["holidays"] = [*source["holidays"], "2027-01-01"]
    path = tmp_path / "with-stray-2027.yaml"
    path.write_text(yaml.safe_dump(source, allow_unicode=True), encoding="utf-8")

    # 2026 is genuinely covered...
    assert calendar_mod.load_runtime_calendar(
        path, covered_years=(2026,)
    ).covered_years == frozenset({2026})
    # ...but the lone 2027 entry does not make 2027 covered
    with pytest.raises(LiveProducerRefused, match="2027: 1"):
        calendar_mod.load_runtime_calendar(path, covered_years=(2026, 2027))


def test_item5_the_token_cache_is_scoped_to_the_app_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cache path carries the app-key fingerprint (review L2).

    Dropping it is what PR-1's own derivation exists to prevent: the stock
    ``KISToken`` cache keys on the domain alone, so two different app keys
    would share one token file and a reissue for one would hand the other a
    token its key never minted. The fingerprint is irreversible, so the path
    names the key without carrying it.
    """
    from tools.broker_probes.common import secret_fingerprint

    captured: dict[str, Any] = {}

    class FakeCreds:
        app_key = "app-key-under-test"
        app_secret = "app-secret-under-test"

    # Patched on `real_quotes`, the module that now owns the only function in
    # this package that resolves REAL credentials (PR #906 review round 1 —
    # `producer.py` was at its 1,000-line cap). The function and this test's
    # claim are unchanged; only the home is.
    monkeypatch.setattr(
        real_quotes_mod, "resolve_credentials", lambda *a, **k: FakeCreds()
    )
    monkeypatch.setattr(
        real_quotes_mod,
        "Quotes",
        lambda *a, **k: captured.update(k) or SimpleNamespace(http=None),
    )
    config = config_mod.load_config(_write_config(tmp_path), repo_root=_REPO_ROOT)
    real_quotes_mod.real_quotes(config, producer_mod.EventLog(tmp_path / "log"))

    fingerprint = secret_fingerprint(FakeCreds.app_key)
    assert captured["token_cache"] == config.token_cache_dir / fingerprint
    assert fingerprint not in (FakeCreds.app_key, FakeCreds.app_secret)
    assert FakeCreds.app_key not in str(captured["token_cache"])


@pytest.mark.parametrize("walk_back_year", [2025])
def test_item5_red_a_seed_walk_leaving_the_calendar_is_refused(
    walk_back_year: int,
) -> None:
    """Plan §3.2's explicit coverage refusal, not a silent "no holidays".

    The tenant calendar holds 2026 only, so a target early enough that the walk
    crosses into the previous year must refuse before requesting anything.
    """
    calendar = _tenant_calendar()
    with pytest.raises(LiveProducerRefused, match="covers"):
        list(calendar.trading_days_before(date(2026, 1, 5), max_calendar_days=10))
    assert walk_back_year not in calendar.covered_years


def test_item5_the_session_window_comes_from_the_calendar(tmp_path: Path) -> None:
    """Not a literal 15:45: a moved close must move the completion rule.

    Red proof of "read from the calendar": a calendar whose CONTINUOUS end is
    09:20 must yield a 09:21 end boundary, which a hardcoded 15:46 could not.
    """
    tenant = _tenant_calendar()
    window = tenant.window("krx-index-futures", "CONTINUOUS")
    assert (window.start.hour, window.start.minute) == (8, 45)
    assert window.last_bar_minute(TARGET) == datetime(2026, 10, 19, 15, 45)
    assert window.end_boundary(TARGET) == datetime(2026, 10, 19, 15, 46)

    moved = calendar_mod.load_runtime_calendar(
        _write_calendar(tmp_path), covered_years=COVERED_YEARS
    )
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

    assert line_mod.SOURCE_PREFIX in (bootproof_guard.APPROVED_REAL_PRODUCER_PREFIXES)
    assert line_mod.SOURCE_ID.startswith(line_mod.SOURCE_PREFIX + "/")


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


def _dead_feed(producer: Any) -> None:
    """Every call to the transport raises, the way a revoked token does."""

    def boom(*_args, **_kwargs):
        raise RuntimeError("EGW00123 token expired")

    producer.quotes.page = boom
    producer.quotes.history = boom


@pytest.mark.serial
def test_red_a_feed_that_answers_nothing_all_day_stops_the_producer(
    tmp_path: Path, market: Market
) -> None:
    """**PR #904 review round 1 item A.1 — the give-up a dead FEED trips.**

    The reviewer's own probe, now a refusal. Before this,
    ``consecutive_produce_errors`` counted only ``ProduceFieldsError``, so a
    revoked token failed every poll of every minute and the session still
    returned 0 — measured: ``fetch_error`` 324, ``published`` 0, rc 0, and
    therefore no ABORT from the runner either.

    The counter is in MINUTES, so the refusal lands at the configured bound
    and not somewhere a change to ``repoll_pace_s`` could move: asserted on
    the count in the message, not merely on the exception type.
    """
    producer, _clock, _quotes = _build(
        tmp_path, market, max_consecutive_fetch_error_minutes=3
    )
    producer.boot()
    _dead_feed(producer)

    with pytest.raises(LiveProducerRefused, match="3 consecutive minute") as excinfo:
        producer.run_session()
    assert "NO poll succeeded" in str(excinfo.value)
    assert producer.counters.published == 0
    assert producer.counters.fetch_error > 0
    # and the refusal still writes a summary — `finish()` always runs
    assert producer.finish()["stage"] == "finish"


@pytest.mark.serial
def test_red_a_feed_that_dies_mid_session_stops_the_producer(
    tmp_path: Path, market: Market
) -> None:
    """**The reviewer's second variant: the token dies at 10:00, not at open.**

    The run must be CONSECUTIVE — a session that published all morning and
    then went silent is as unclean as one that never published, and the
    counter has to reset on success or it would never reach its bound on a
    day with one failed poll an hour.
    """
    producer, clock, _quotes = _build(
        tmp_path, market, max_consecutive_fetch_error_minutes=3
    )
    producer.boot()
    real_poll = producer._poll
    # inside the fixture's short CONTINUOUS window (08:45..09:20), the way
    # 10:00 is inside the production one
    killed_at = datetime(TARGET.year, TARGET.month, TARGET.day, 9, 0)

    def poll_until_ten():
        if clock.now().replace(tzinfo=None) >= killed_at:
            raise RuntimeError("EGW00123 token expired")
        return real_poll()

    producer._poll = poll_until_ten
    with pytest.raises(LiveProducerRefused, match="3 consecutive minute"):
        producer.run_session()
    # it did its job until the feed died, which is why the run must be
    # consecutive rather than cumulative
    assert producer.counters.published > 0


@pytest.mark.serial
def test_a_long_run_of_minutes_with_no_rows_does_not_stop_the_producer(
    tmp_path: Path, market: Market
) -> None:
    """**The input the fetch give-up must NOT trip on — and the reason it exists.**

    The genesis session's 12:39-13:08 was 30 CONSECUTIVE minutes of
    ``no_raw_row_for_minute``: the polls all worked and the market simply did
    not trade. ``fetch_error`` was 0 for the whole day. A counter that folded
    "no row this minute" into "the feed is not answering" would abort a clean
    session every lunch lull and every closing call auction, so the bound here
    is set BELOW the number of such minutes this market has and the session
    must still run to its end.
    """
    quiet = Market(sessions=market.sessions, target_bars=market.target_bars[:10])
    producer, _clock, _quotes = _build(
        tmp_path, quiet, max_consecutive_fetch_error_minutes=2
    )
    producer.boot()
    producer.run_session()  # no refusal
    summary = producer.finish()

    assert summary["counters"]["no_raw_row_for_minute"] > 2, summary["counters"]
    assert summary["counters"]["fetch_error"] == 0
    assert producer.consecutive_fetch_error_minutes == 0


@pytest.mark.serial
def test_red_a_boot_after_the_session_close_is_refused(
    tmp_path: Path, market: Market
) -> None:
    """**PR #904 review round 1 item A.2 — the other always-true path.**

    The reviewer's probe: with the wall clock past the close, ``run_session``
    walks ``while boundary <= end`` zero times and the producer returns 0
    having published nothing. A session that measured nothing is not a clean
    session, so the boot refuses — and it refuses BEFORE the seed walk, which
    is tens of paginated GETs.

    The refusal is the producer's and not the runner's because the runner
    never loads a calendar: it holds only ``TENANT_STOP_AT``, so a
    runner-side check would need a second copy of the session window, which
    is what ``calendar.py``'s module docstring refuses.
    """
    producer, clock, quotes = _build(tmp_path, market)
    clock.moment = clock.moment.replace(hour=16, minute=30)

    with pytest.raises(LiveProducerRefused, match="already past the session end"):
        producer.boot()
    # before the seed walk: nothing was fetched
    assert quotes.history_calls == 0


@pytest.mark.serial
def test_red_a_seed_walk_that_crosses_the_close_refuses_before_the_loop(
    tmp_path: Path, market: Market
) -> None:
    """**Review round 2 LOW 3 — the boot-time check alone is not enough.**

    The reviewer's probe E: boot INSIDE the session, let the seed walk spend
    real time, and the loop has nothing left to do. ``boot()``'s check passes
    (at 09:18:30 the first boundary is 09:20, inside a 09:21 end), the walk
    carries the clock past the close, and before this fix ``run_session``
    walked ``while boundary <= end`` **zero times** and returned 0 — a
    session that published nothing, reported as clean, which is exactly the
    shape A.2 exists to refuse.

    So the check is asked again at the top of ``run_session``, on the
    boundary that loop will actually use. Both halves are asserted here: the
    boot does NOT refuse, and the loop does.
    """
    producer, clock, quotes = _build(tmp_path, market)
    clock.moment = clock.moment.replace(hour=9, minute=18, second=30)
    real_history = quotes.history

    def costly_history(*args: Any, **kwargs: Any):
        rows = real_history(*args, **kwargs)
        clock.sleep(90)  # each walked day costs wall-clock time
        return rows

    quotes.history = costly_history

    producer.boot()  # the boot-time check passes: 09:20 <= 09:21
    # read off the producer's own window, never a literal close
    end = producer.window.end_boundary(TARGET)
    assert clock.now().replace(tzinfo=None) > end, "the walk must cross the close"

    with pytest.raises(LiveProducerRefused, match="already past the session end"):
        producer.run_session()
    # every line this session wrote came from the BOOT catch-up; the loop
    # contributed none, which is the "measured nothing" shape being refused
    assert producer.counters.published == producer.counters.pre_boot_lines


@pytest.mark.serial
def test_a_boot_inside_the_session_is_not_refused(
    tmp_path: Path, market: Market
) -> None:
    """The other side of the late-boot refusal, so it is not a constant.

    One minute before the close is still a session: one boundary remains, so
    one bar can still be published and the producer must not refuse. (The
    fixture's CONTINUOUS window is 08:45..09:20 so the loop stays fast; the
    production one is 08:45..15:45 and the shape is the same.)
    """
    producer, clock, _quotes = _build(tmp_path, market)
    clock.moment = clock.moment.replace(hour=9, minute=19)  # close is 09:20

    producer.boot()  # no refusal
    assert producer.window.end_boundary(TARGET) >= producer._first_boundary()


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
    assert printed["source_id"] == line_mod.SOURCE_ID
    assert not (tmp_path / "session").exists()


# ===========================================================================
# PR-A — the venue band (band plan 2026-10-15 §3.1-§3.2, §5 1)
#
# Hermetic like everything above: the band transport is the same fixture
# server, and the two transport-level tests build a ``Quotes`` with
# ``object.__new__`` so no auth manager, no credential and no socket exist at
# all. No KIS call is made anywhere in this file.
# ===========================================================================


def _log_events(producer: Any) -> list[dict]:
    return [
        json.loads(line)
        for line in (producer.session_dir / "producer-log.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]


def _stage(producer: Any, stage: str) -> list[dict]:
    return [event for event in _log_events(producer) if event.get("stage") == stage]


class _NoSocket:
    """An httpx stand-in whose use is the failure. Counts, never raises first."""

    def __init__(self) -> None:
        self.calls = 0

    def get(self, *_args: Any, **_kwargs: Any) -> Any:
        self.calls += 1
        raise AssertionError("a socket was opened for a call the gate must refuse")


class _Response:
    """Just enough of ``httpx.Response``: raw bytes, a parse and a status."""

    def __init__(self, content: bytes, status: int = 200) -> None:
        self.content, self.status_code = content, status

    def json(self) -> Any:
        return json.loads(self.content.decode("utf-8"))

    def raise_for_status(self) -> None:
        return None


class _Http:
    def __init__(self, response: Any) -> None:
        self.response, self.seen = response, []
        self.timeouts: list[Any] = []

    def get(
        self, url: str, headers: Any = None, params: Any = None, timeout: Any = None
    ) -> Any:
        self.seen.append((url, headers, params))
        self.timeouts.append(timeout)
        return self.response


class _Recorder:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def event(self, value: dict) -> None:
        self.events.append(dict(value))


def _bare_quotes(recorder: Any, http: Any) -> Any:
    """A ``Quotes`` with no auth manager and no credential behind it.

    ``object.__new__`` on purpose: ``__init__`` builds a ``KISAuthManager``,
    and nothing in this file may read a secret or resolve a token.
    """
    quotes = object.__new__(quote_client.Quotes)
    quotes.cfg = {
        "pace_s": 0.0,
        "request_timeout_s": 1.0,
        "attempts": 1,
        "retry_pause_s": 0.0,
        "max_pages": 1,
    }
    quotes.last = 0.0
    quotes.calls = 0
    quotes.recorder = recorder
    quotes.http = http
    quotes.creds = SimpleNamespace(app_key="key", app_secret="secret")
    quotes.auth = SimpleNamespace(get_token=lambda: "token", invalidate=lambda: None)
    return quotes


def test_band_the_allowlist_is_two_paired_get_entries() -> None:
    """One pair added, nothing else changed, and the PAIRING is what matters."""
    assert len(quote_client.ALLOWLIST) == 2
    assert {entry.tr_id for entry in quote_client.ALLOWLIST} == {
        quote_client.TR,
        quote_client.BAND_TR,
    }
    by_tr = {entry.tr_id: entry.path for entry in quote_client.ALLOWLIST}
    assert by_tr[quote_client.BAND_TR] == quote_client.BAND_PATH
    assert by_tr[quote_client.TR] == quote_client.QUOTE_PATH
    # The two paths are DIFFERENT endpoints: a reader who assumes the band
    # rides the minute path would be wrong, and so would a swapped pair.
    assert quote_client.BAND_PATH != quote_client.QUOTE_PATH
    source = (_REPO_ROOT / "tools/tos_cp3/quote_client.py").read_text("utf-8")
    assert ".post(" not in source and '"POST"' not in source


def test_band_tr_and_path_are_pvls_pair_defined_locally() -> None:
    """Same two literals as P-VL measured, and P-VL is NOT imported (§3.1).

    P-VL is sealed to the MOCK host (``assert_mock_host``); importing its
    constants would pull that seal into a REAL-token transport. So the pair is
    local and this test is the thing that keeps the two copies equal.
    """
    from tools.broker_probes import probes_venue_limits as pvl

    assert quote_client.BAND_TR == pvl._PRICE_TR
    assert quote_client.BAND_PATH == pvl._PRICE_PATH
    closure = _import_closure("tools.tos_cp3.quote_client")
    assert "tools.broker_probes.probes_venue_limits" not in closure


@pytest.mark.parametrize(
    "method,path,tr",
    [
        # the band pair, as a POST
        ("POST", quote_client.BAND_PATH, quote_client.BAND_TR),
        # the band TR aimed at an ORDER path
        ("GET", "/uapi/domestic-futureoption/v1/trading/order", quote_client.BAND_TR),
        # an order TR aimed at the band path
        ("GET", quote_client.BAND_PATH, "TTTO1101U"),
        # both allowlisted, but CROSSED: the minute TR on the band's path
        ("GET", quote_client.BAND_PATH, quote_client.TR),
        # ...and the band TR on the minute path
        ("GET", quote_client.QUOTE_PATH, quote_client.BAND_TR),
    ],
)
def test_band_an_off_allowlist_call_is_refused(method: str, path: str, tr: str) -> None:
    from tools.broker_probes.common import SafetyViolation, assert_read_only_call

    with pytest.raises(SafetyViolation):
        assert_read_only_call(
            method, quote_client.REAL_BASE_URL + path, tr, quote_client.ALLOWLIST
        )


def test_red_a_refused_band_call_opens_no_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate runs BEFORE the transport, not around its result.

    The concrete input: an allowlist that does not carry the band pair — which
    is the state of this file before PR-A, and the state it would return to if
    the entry were removed. Moving ``assert_read_only_call`` below the
    ``http.get`` leaves ``_NoSocket.calls == 1`` and this test red.
    """
    http = _NoSocket()
    quotes = _bare_quotes(_Recorder(), http)
    monkeypatch.setattr(quote_client, "ALLOWLIST", (quote_client.ALLOWLIST[0],))
    from tools.broker_probes.common import SafetyViolation

    with pytest.raises(SafetyViolation):
        quotes.band(INSTRUMENT)
    assert http.calls == 0


def test_band_logs_its_own_tr_id_and_hashes_the_raw_bytes() -> None:
    """Review LOW-2: a band attempt that logged ``TR`` would be INVISIBLE.

    The post-session check is "every TR in ``producer-log.jsonl`` is one of the
    two, all GET" (§3.5). A band call recorded under the minute TR passes that
    check while never having been seen by it — so the attempt record carries
    this call's own ``tr_id``, and the two must differ.
    """
    # Deliberately not minified: a digest of ``json.dumps(parsed)`` would not
    # equal a digest of THESE bytes, which is what makes the assertion below
    # able to tell the two apart.
    raw = json.dumps(_band_payload(), indent=2).encode("utf-8")
    recorder = _Recorder()
    http = _Http(_Response(raw))
    read = _bare_quotes(recorder, http).band(INSTRUMENT)

    assert read.raw_payload_digest == hashlib.sha256(raw).hexdigest()
    reserialised = json.dumps(read.payload, separators=(",", ":")).encode("utf-8")
    assert read.raw_payload_digest != hashlib.sha256(reserialised).hexdigest()

    (event,) = recorder.events
    assert event["stage"] == quote_client.BAND_FETCH_STAGE
    assert event["method"] == "GET"
    assert event["tr_id"] == quote_client.BAND_TR != quote_client.TR
    assert event["path"] == quote_client.BAND_PATH
    assert event["raw_payload_digest"] == read.raw_payload_digest
    assert event["rt_cd"] == "0"
    # The request really carried that TR as well, not only the log line.
    _url, headers, params = http.seen[0]
    assert headers["tr_id"] == quote_client.BAND_TR
    assert params == {"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": INSTRUMENT}


@pytest.mark.parametrize(
    "payload",
    [
        {"rt_cd": "1", "msg_cd": "EGW00123", "output1": {}},
        {"rt_cd": "0", "output1": {"futs_mxpr": "1162.72"}},  # two fields missing
        {"rt_cd": "0"},  # no output1 at all
    ],
)
def test_band_a_refusal_or_a_short_body_is_a_failure_that_still_logs(
    payload: dict,
) -> None:
    """``rt_cd != 0`` and an absent field are both band FAILURES (§3.1).

    Shaped as two halves because they fail in two places: the transport raises
    on ``rt_cd``, and ``band_values_from_payload`` raises on the fields. Either
    way the attempt is logged with its own TR and no value is substituted.
    """
    recorder = _Recorder()
    raw = json.dumps(payload).encode("utf-8")
    quotes = _bare_quotes(recorder, _Http(_Response(raw)))
    try:
        read = quotes.band(INSTRUMENT)
    except RuntimeError:
        pass
    else:
        with pytest.raises(band_line_mod.BandLineError):
            band_line_mod.band_values_from_payload(read.payload)
    (event,) = recorder.events
    assert event["tr_id"] == quote_client.BAND_TR
    assert event["path"] == quote_client.BAND_PATH


def test_red_the_band_is_never_read_before_the_open(
    tmp_path: Path, market: Market
) -> None:
    """⛔ No GET before the open, with the input that would make one.

    The concrete input: a clock before 08:45 and a price line already written —
    the shape of a boot before the open whose first response carries
    today-stamped pre-open rows, where ``_boot_today`` publishes the newest
    already-complete bar and would carry the band read with it. Pre-open is
    exactly where band plan §4.4a's residual risk (the broker hands out
    yesterday's band) is largest, and the band is used ALL DAY.

    Deleting the ``now < session_start`` clause in ``band._trigger`` makes the
    first assertion below find a band call.
    """
    producer, clock, quotes = _build(tmp_path, market)
    producer.boot()
    assert quotes.band_calls == 0

    clock.moment = clock.moment.replace(hour=8, minute=40, second=0)
    producer.band.after_price_line()
    assert quotes.band_calls == 0
    assert not producer.band_journal_path.exists()
    (skipped,) = _stage(producer, band_mod.STAGE_BAND_BEFORE_OPEN)
    assert skipped["session_start"].endswith("08:45:00")

    # One second past the first boundary after the open: now it reads, once.
    clock.moment = clock.moment.replace(hour=8, minute=46, second=2)
    producer.band.after_price_line()
    assert quotes.band_calls == 1
    producer.band.after_price_line()
    assert quotes.band_calls == 1, "the band is read ONCE (§3.1), not per line"


@pytest.mark.serial
def test_band_writes_one_line_in_the_plans_schema(
    tmp_path: Path, market: Market
) -> None:
    """§3.2's line, key for key, with the three values copied as strings."""
    producer, _clock, quotes = _build(tmp_path, market)
    producer.boot()
    producer.run_session()
    summary = producer.finish()

    (line,) = _journal_rows(producer.band_journal_path)
    assert list(line) == list(band_line_mod.BAND_KEY_ORDER)
    assert line["kind"] == "cp3-band/1"
    assert line["source_id"] == line_mod.SOURCE_ID
    assert line["instrument"] == INSTRUMENT
    assert line["trading_date"] == TARGET.strftime("%Y%m%d")
    assert line["tr_id"] == quote_client.BAND_TR
    # Strings, exactly as they arrived: no scale conversion, no grid check, no
    # ordering check here — those stay in the runtime's one validation set
    # (band plan §4.2).
    assert (line["upper"], line["lower"], line["basis"]) == (
        BAND_UPPER,
        BAND_LOWER,
        BAND_BASIS,
    )
    assert all(isinstance(line[key], str) for key in ("upper", "lower", "basis"))

    (published,) = _stage(producer, band_mod.STAGE_BAND_PUBLISHED)
    assert published["raw_payload_digest"] == line["raw_payload_digest"]
    assert line["producer_continuity_id"] == summary["band"]["producer_continuity_id"]
    assert summary["band"]["lines"] == 1 and summary["band"]["failures"] == 0

    # At or after the open, and from the FIRST boundary after it.
    opened = datetime(
        TARGET.year, TARGET.month, TARGET.day, 8, 45, tzinfo=producer_mod.KST
    )
    assert line["as_of_ms"] >= int(opened.timestamp() * 1000)
    assert quotes.band_calls == 1
    assert quotes.band_started[0].replace(tzinfo=None) < datetime(
        TARGET.year, TARGET.month, TARGET.day, 8, 47
    )
    # No temp file is left beside it: the band journal is the price journal's
    # writer, so it is replaced whole, atomically (§3.2).
    assert not list(producer.session_dir.glob(".band.jsonl.*"))


@pytest.mark.serial
def test_red_a_failed_band_get_writes_no_line_and_is_not_a_feed_failure(
    tmp_path: Path, market: Market
) -> None:
    """Band failure: no line, ``band_fetch_failed``, and the price feed is fine.

    Two clauses in one input, because one input is what they share (§3.1):
    the band GET fails all session and (a) no band line exists — nothing is
    substituted — and (b) the failure is NOT counted toward
    ``max_consecutive_fetch_error_minutes``, which is the minute-bar polling
    give-up. Counting it there would stop a producer whose price feed is
    perfect, and that give-up ends the whole market day.
    """
    producer, _clock, quotes = _build(tmp_path, market)
    producer.boot()
    quotes.band_fail_next = 999
    producer.run_session()
    summary = producer.finish()

    assert not producer.band_journal_path.exists()
    assert quotes.band_calls >= 1
    failures = _stage(producer, band_mod.STAGE_BAND_FETCH_FAILED)
    assert failures and all(
        entry["tr_id"] == quote_client.BAND_TR for entry in failures
    )
    assert all(entry["counts_toward_fetch_give_up"] is False for entry in failures)

    assert producer.counters.fetch_error == 0
    assert producer.consecutive_fetch_error_minutes == 0
    assert summary["band"]["lines"] == 0 and summary["band"]["failures"] >= 1
    assert summary["counters"]["published"] > 1


def test_red_a_leftover_band_journal_refuses_boot(
    tmp_path: Path, market: Market
) -> None:
    """A session directory is used once — the band file too (§3.2, MEDIUM-1).

    The concrete input: a roll day where the runner reuses the session
    directory. ``refuse_if_partitions_exist`` does not see it (a band line is
    not a partition) and the runner only ``mkdir -p``s, so without this
    refusal yesterday's band — or another contract's — is the band this
    session believes all day. That is the one fail-open on this path.
    """
    producer, _clock, _quotes = _build(tmp_path, market)
    producer.band_journal_path.write_text(
        json.dumps({"kind": "cp3-band/1", "instrument": "A05610"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(LiveProducerRefused) as refusal:
        producer.boot()
    assert band_line_mod.BAND_JOURNAL_NAME in str(refusal.value)


class _NoBand:
    """A band capture that does nothing — the "without the band" baseline."""

    def after_price_line(self) -> None:
        return None

    def report(self) -> None:
        return None


def _run_session(
    where: Path, market: Market, *, band_cost_s: float = 0.0, **overrides: Any
) -> Any:
    where.mkdir(parents=True, exist_ok=True)
    producer, _clock, quotes = _build(where, market, **overrides)
    quotes.band_cost_s = band_cost_s
    producer.boot()
    producer.run_session()
    producer.finish()
    return producer, quotes


@pytest.mark.serial
def test_red_the_price_journal_is_byte_identical_with_and_without_the_band(
    tmp_path: Path, market: Market, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Three sessions, one price journal: the band changes no price byte.

    The third session's band costs five seconds of clock per attempt, so this
    is not the vacuous "nothing moved" version of the claim — the band really
    spends time inside the minute and the price lines are still identical,
    because every wait in the loop is to an ABSOLUTE instant.
    """
    with monkeypatch.context() as patched:
        patched.setattr(band_mod, "build_capture", lambda **_kw: _NoBand())
        without, _none = _run_session(tmp_path / "without", market)
    assert not without.band_journal_path.exists()

    quick, quick_quotes = _run_session(tmp_path / "quick", market)
    slow, slow_quotes = _run_session(tmp_path / "slow", market, band_cost_s=5.0)

    reference = without.journal_path.read_bytes()
    assert quick.journal_path.read_bytes() == reference
    assert slow.journal_path.read_bytes() == reference
    assert quick_quotes.band_calls == 1 and slow_quotes.band_calls == 1
    assert quick.band_journal_path.is_file() and slow.band_journal_path.is_file()
    # and the band line itself is not identical — the stamp moved with the cost
    assert _journal_rows(quick.band_journal_path)[0]["as_of_ms"] < (
        _journal_rows(slow.band_journal_path)[0]["as_of_ms"]
    )


@pytest.mark.serial
def test_red_the_band_does_not_push_the_next_price_poll(
    tmp_path: Path, market: Market, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The next poll's START time is the same with and without the band.

    "The price journal bytes are identical" cannot see this: it compares
    CONTENT, and the content of a line published late is the same line. So
    this compares the clock at every price GET.

    The adversarial input is the worst honest one: a band that fails and whose
    every attempt spends the whole ``request_timeout_s``, so the retry loop
    walks right up to the bound. ``band._room`` refuses an attempt that cannot
    FINISH before ``next boundary - δ``; weakening it to "start before the
    bound" lets the last attempt end past the next boundary's ``+δ``, and the
    next poll then starts late. With ``δ`` 1.8 s and a 10 s timeout that is a
    0.2 s shift — invisible to every other assertion in this file.
    """
    with monkeypatch.context() as patched:
        patched.setattr(band_mod, "build_capture", lambda **_kw: _NoBand())
        _baseline, baseline_quotes = _run_session(tmp_path / "baseline", market)

    where = tmp_path / "slow-failing"
    where.mkdir(parents=True, exist_ok=True)
    producer, _clock, quotes = _build(where, market)
    producer.boot()
    quotes.band_cost_s = producer.config.request_timeout_s
    quotes.band_fail_next = 999
    producer.run_session()
    producer.finish()

    assert quotes.band_calls > 1, "the retry loop never ran; the bound is untested"
    assert quotes.poll_started == baseline_quotes.poll_started
    assert not producer.band_journal_path.exists()


@pytest.mark.serial
def test_band_a_window_with_no_room_makes_no_attempt_at_all(
    tmp_path: Path, market: Market
) -> None:
    """The bound's other half: no room, no GET — and the band is not 'read'.

    A window that made no attempt leaves the capture unattempted, so the next
    price line tries again. Otherwise one unlucky minute would cost the whole
    day's band.
    """
    producer, clock, quotes = _build(tmp_path, market)
    producer.boot()
    clock.moment = clock.moment.replace(hour=8, minute=46, second=59)
    producer.band.after_price_line()
    assert quotes.band_calls == 0
    (no_room,) = _stage(producer, band_mod.STAGE_BAND_NO_ROOM)
    assert no_room["request_timeout_s"] == producer.config.request_timeout_s

    clock.moment = clock.moment.replace(minute=47, second=2)
    producer.band.after_price_line()
    assert quotes.band_calls == 1


# -- review round 1 MEDIUM-1: the gate's refusal must PROPAGATE -------------


def _safety_violation() -> Any:
    from tools.broker_probes.common import SafetyViolation

    return SafetyViolation


def test_a_safety_violation_is_a_runtime_error_which_is_why_order_matters() -> None:
    """The fact the first cut missed, asserted so it cannot be missed again.

    ``SafetyViolation`` -> ``ProbeError`` -> ``RuntimeError``, so
    ``except RuntimeError`` catches the allowlist gate's refusal. Every
    handler in this package that catches ``RuntimeError`` around a transport
    call therefore needs a ``SafetyViolation`` clause ABOVE it, and this is the
    reason stated as a test rather than as a comment.
    """
    assert issubclass(_safety_violation(), RuntimeError)
    assert "Never caught" in (_safety_violation().__doc__ or "")


@pytest.mark.serial
def test_red_a_gate_refusal_in_the_band_propagates_and_ends_the_producer_nonzero(
    tmp_path: Path, market: Market, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**MEDIUM-1.** A refused band call must not read as a feed failure.

    The reviewer's measured input: a transport whose ``band`` always raises
    ``SafetyViolation``. Before the fix that produced 24 ``band_fetch_failed``
    events saying "gate refused" and the producer still returned **0** — the
    one place "zero real futures orders" is enforced had become a log line on
    a session that reported success. Deleting the ``except SafetyViolation:
    raise`` clause makes this test green again, which is the mutation.
    """
    violation = _safety_violation()
    config = config_mod.load_config(_write_config(tmp_path), repo_root=_REPO_ROOT)
    clock = FakeClock(datetime(TARGET.year, TARGET.month, TARGET.day, 8, 44, 30))
    quotes = FakeQuotes(market, clock)

    def refuse(_symbol: str) -> Any:
        raise violation("real-token call is not on the read-only allowlist")

    monkeypatch.setattr(quotes, "band", refuse)
    producer = producer_mod.LiveProducer(
        config=config,
        instrument=INSTRUMENT,
        target=TARGET,
        session_dir=tmp_path / "session",
        journal_path=tmp_path / "session" / "journal.jsonl",
        clock=producer_mod.Clock(now=clock.now, sleep=clock.sleep),
        quotes_factory=lambda _config, _log: quotes,
    )
    producer.boot()
    with pytest.raises(violation):
        producer.run_session()
    producer.finish()

    # No line, nothing counted as a band failure, and nothing counted as a
    # FEED failure either: the session stopped instead of carrying on.
    assert not producer.band_journal_path.exists()
    assert _stage(producer, band_mod.STAGE_BAND_FETCH_FAILED) == []
    assert producer.counters.fetch_error == 0


def test_red_a_gate_refusal_on_the_price_poll_propagates_too(
    tmp_path: Path, market: Market, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**MEDIUM-1, the pre-existing half.** Same hole on the PRICE path.

    ``_handle_boundary``'s ``except RuntimeError`` around ``_poll`` swallowed a
    ``SafetyViolation`` from ``page()`` into ``fetch_error`` and polled on —
    so an off-allowlist price call was a counted transport blip. The fix is
    the same clause in the same order, and removing it turns this green.
    """
    violation = _safety_violation()
    producer, _clock, quotes = _build(tmp_path, market)
    producer.boot()

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise violation("real-token call is not on the read-only allowlist")

    monkeypatch.setattr(quotes, "page", refuse)
    with pytest.raises(violation):
        producer.run_session()
    assert producer.counters.fetch_error == 0
    assert _stage(producer, "fetch_error") == []


def test_the_cli_cannot_fold_a_gate_refusal_into_its_refusal_path() -> None:
    """rc != 0 is what the runner reads (exit 5) — the last link in that chain.

    The two tests above measure that the refusal propagates out of
    ``run_session``. ``main`` wraps that call in exactly one handler,
    ``except LiveProducerRefused``, so the remaining question is whether that
    handler can catch a ``SafetyViolation`` and turn it into the ordinary
    rc-1-with-a-message path. It cannot: the two types are unrelated, so the
    exception leaves ``main`` uncaught and the process exits non-zero with a
    traceback — while ``finish()`` still runs in the ``finally``.

    ⚠ Asserted on the type lattice rather than by driving ``main --confirm``:
    that path calls ``read_query_credentials``, and
    ``shared.config.dotenv_guard.read_explicit_dotenv`` deliberately does
    NOTHING in hermetic mode, so the CLI refuses for a missing key long before
    a transport exists. Defeating that guard to reach the factory would be a
    worse test than this one.
    """
    assert not issubclass(_safety_violation(), LiveProducerRefused)
    assert not issubclass(LiveProducerRefused, _safety_violation())


# -- review round 1 LOW-1: what one attempt may cost ------------------------


def test_red_the_attempt_budget_charges_the_pace_sleep(
    tmp_path: Path, market: Market
) -> None:
    """**LOW-1.** ``_room`` must charge ``pace_s``, not only the timeout.

    ``Quotes.band`` sleeps up to ``pace_s`` before its request to stay inside
    the 5 rps limit, so an attempt costs pace + transport. The red input is a
    deadline in the gap between the two numbers: with the pace charged there
    is no room, without it there is — and an attempt started there ends after
    the bound.
    """
    producer, _clock, _quotes = _build(tmp_path, market)
    producer.boot()
    band = producer.band
    assert band.pace_s > 0
    assert band.attempt_budget() == band.pace_s + band.request_timeout_s

    now = band.now()
    just_the_timeout = now + timedelta(seconds=band.request_timeout_s + 0.1)
    assert not band._room(just_the_timeout)
    with_the_pace = now + timedelta(seconds=band.attempt_budget() + 0.1)
    assert band._room(with_the_pace)


def test_the_band_get_pins_httpx_phases_to_sum_to_the_timeout() -> None:
    """**LOW-1.** ``timeout=`` is PER PHASE, so the bare number allows 4x it.

    The budget ``_room`` assumes is only true if one GET cannot exceed
    ``request_timeout_s``, so the band call passes an ``httpx.Timeout`` whose
    four phases sum to it. Asserted on the object the transport actually
    handed httpx.
    """
    raw = json.dumps(_band_payload()).encode("utf-8")
    http = _Http(_Response(raw))
    quotes = _bare_quotes(_Recorder(), http)
    quotes.band(INSTRUMENT)
    (timeout,) = http.timeouts
    budget = quotes.cfg["request_timeout_s"]
    assert timeout is not None
    phases = (timeout.connect, timeout.read, timeout.write, timeout.pool)
    assert all(phase is not None for phase in phases)
    assert sum(phases) == pytest.approx(budget)


@pytest.mark.serial
def test_red_an_attempt_that_overruns_its_budget_does_not_get_a_second(
    tmp_path: Path, market: Market
) -> None:
    """**LOW-1's honest claim.** An overrun cannot be aborted; it can be bounded.

    A single attempt that costs MORE than the whole budget (the shape a
    per-phase timeout or an OAuth re-POST can produce) is spent — nothing can
    recall it. What the bound still guarantees is that it does not compound:
    the next attempt is refused, the window ends, and the next price poll
    still starts on time.
    """
    where = tmp_path / "overrun"
    where.mkdir(parents=True, exist_ok=True)
    producer, _clock, quotes = _build(where, market)
    producer.boot()
    cost = producer.config.request_timeout_s * 2
    quotes.band_cost_s = cost
    quotes.band_fail_next = 9999
    producer.run_session()
    producer.finish()

    delta = producer.band.attempt_budget()
    assert cost > delta, "the fake must cost MORE than the budget, or nothing is shown"
    assert quotes.band_started, "no attempt ran; the window bound is untested"

    # Every attempt STARTED inside its window's bound — that is what `_room`
    # can promise. The gap LOW-1 names, made visible: the last one ENDED past
    # it, because an in-flight call cannot be recalled.
    starts = [stamp.replace(tzinfo=None) for stamp in quotes.band_started]
    first_deadline = datetime(TARGET.year, TARGET.month, TARGET.day, 8, 47) - timedelta(
        seconds=producer.config.first_poll_delay_s
    )
    in_first_window = [start for start in starts if start < first_deadline]
    assert in_first_window, "the first window made no attempt"
    assert max(in_first_window) + timedelta(seconds=cost) > first_deadline

    # And it did not compound: the window is finite and the day still spends
    # only the two windows LOW-3 allows.
    assert len(starts) <= 8, starts
    assert producer.band.retried is True
    # the price side is untouched by any of it
    assert producer.counters.fetch_error == 0
    assert producer.counters.published > 1


# -- review round 1 LOW-3: exactly one extra window -------------------------


@pytest.mark.serial
def test_red_a_first_window_that_fails_everything_gets_one_more_window(
    tmp_path: Path, market: Market
) -> None:
    """**LOW-3.** One bad minute must not cost the whole day's band.

    The first window's attempts all fail; the next boundary gets ONE more
    window, and that one succeeds and writes the line. Without the retry the
    day has no band at all — which is the red: the journal does not exist.
    """
    producer, _clock, quotes = _build(tmp_path, market)
    producer.boot()
    # "Every attempt of the FIRST window fails" expressed as the condition it
    # really is, not as a count: a count would depend on how many attempts the
    # window's own bound happens to fit, which is a different clause's job.
    real_band = quotes.band

    def fail_until_the_extra_window(symbol: str) -> Any:
        if not producer.band.retried:
            quotes.band_calls += 1
            raise RuntimeError("band_auth_http_or_json_error")
        return real_band(symbol)

    quotes.band = fail_until_the_extra_window
    producer.run_session()
    summary = producer.finish()

    (line,) = _journal_rows(producer.band_journal_path)
    assert line["instrument"] == INSTRUMENT
    assert summary["band"]["failures"] > 0
    assert summary["band"]["lines"] == 1
    assert summary["band"]["retry_window_used"] is True
    triggers = [entry["trigger"] for entry in _stage(producer, "band_published")]
    assert triggers == [band_mod.TRIGGER_RETRY]


@pytest.mark.serial
def test_red_the_extra_window_is_exactly_one(tmp_path: Path, market: Market) -> None:
    """The other half of LOW-3: bounded at one, so a dead band is not a loop.

    Every attempt of every window fails all session. The day must spend TWO
    windows and stop — not one per boundary for the rest of the day, which
    would hand the band the minute-bar polling's rate-limit budget.
    """
    producer, _clock, quotes = _build(tmp_path, market)
    producer.boot()
    quotes.band_fail_next = 9999
    producer.run_session()
    summary = producer.finish()

    assert not producer.band_journal_path.exists()
    triggers = {
        entry["trigger"] for entry in _stage(producer, band_mod.STAGE_BAND_FETCH_FAILED)
    }
    assert triggers == {band_mod.TRIGGER_FIRST, band_mod.TRIGGER_RETRY}
    # EXACTLY two windows — the count, not the trigger set, is what separates
    # "one extra" from "one per boundary": an unbounded retry keeps the same
    # two trigger names while spending a window every minute of the session.
    assert summary["band"]["windows"] == 2
    assert summary["band"]["retry_window_used"] is True
    # and the price side never noticed
    assert producer.counters.fetch_error == 0
    assert summary["counters"]["published"] > 1


# -- the re-read: measurement only ------------------------------------------


def test_band_reread_is_null_in_the_shipped_config_and_says_why() -> None:
    """Default null, and the YAML states it is measurement-only (§3.1)."""
    path = _REPO_ROOT / "config/tos_probes/cp3-live-producer.yaml"
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    assert data["band_reread_minutes"] is None
    assert "측정 전용" in text
    assert "band_reread_minutes" in text


@pytest.mark.parametrize("bad", [0, -1, True, "5", 1.5])
def test_red_a_band_reread_that_is_not_a_positive_int_is_refused(
    tmp_path: Path, bad: Any
) -> None:
    with pytest.raises(LiveProducerRefused, match="band_reread_minutes"):
        config_mod.load_config(
            _write_config(tmp_path, band_reread_minutes=bad), repo_root=_REPO_ROOT
        )


def test_band_reread_absent_means_null(tmp_path: Path) -> None:
    """Absent and explicit null are the same answer — and a TYPO is not.

    The module's no-default rule is about values that change what the producer
    does; null here is the behaviour of every session before the key existed.
    An unknown key is still a refusal, so a misspelling cannot read as null.
    """
    data = yaml.safe_load(_write_config(tmp_path).read_text(encoding="utf-8"))
    del data["band_reread_minutes"]
    path = tmp_path / "no-band-key.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert (
        config_mod.load_config(path, repo_root=_REPO_ROOT).band_reread_minutes is None
    )

    data["band_reead_minutes"] = 5
    typo = tmp_path / "typo.yaml"
    typo.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(LiveProducerRefused, match="unknown key"):
        config_mod.load_config(typo, repo_root=_REPO_ROOT)


@pytest.mark.serial
def test_band_a_configured_reread_appends_lines_from_the_same_boot(
    tmp_path: Path, market: Market
) -> None:
    """A re-read APPENDS; it never replaces, and it carries the same boot id."""
    producer, _clock, quotes = _build(tmp_path, market, band_reread_minutes=5)
    producer.boot()
    producer.run_session()
    producer.finish()

    rows = _journal_rows(producer.band_journal_path)
    assert len(rows) > 1
    assert quotes.band_calls == len(rows)
    assert len({row["producer_continuity_id"] for row in rows}) == 1
    stamps = [row["as_of_ms"] for row in rows]
    assert stamps == sorted(stamps) and len(set(stamps)) == len(stamps)
    triggers = [entry["trigger"] for entry in _stage(producer, "band_published")]
    assert triggers[0] == band_mod.TRIGGER_FIRST
    assert set(triggers[1:]) == {band_mod.TRIGGER_REREAD}


# -- the journal the band reuses --------------------------------------------


def test_band_journal_keeps_the_price_journals_three_guarantees(
    tmp_path: Path,
) -> None:
    """Key order from the ARGUMENT, the stamp owned here, non-advancing refused."""
    path = tmp_path / band_line_mod.BAND_JOURNAL_NAME
    stamps = iter([1792286460000, 1792286460000, 1792286461000])
    journal = sinks_mod.ObservationJournal(
        path, clock=lambda: next(stamps), key_order=band_line_mod.BAND_KEY_ORDER
    )
    row = {
        "kind": band_line_mod.BAND_LINE_KIND,
        "source_id": line_mod.SOURCE_ID,
        "instrument": INSTRUMENT,
        "trading_date": "20261019",
        "tr_id": quote_client.BAND_TR,
        "upper": BAND_UPPER,
        "lower": BAND_LOWER,
        "basis": BAND_BASIS,
        "raw_payload_digest": "f" * 64,
        "producer_continuity_id": "c" * 32,
    }
    assert journal.append(dict(row)).written
    assert list(_journal_rows(path)[0]) == list(band_line_mod.BAND_KEY_ORDER)
    refused = journal.append(dict(row))
    assert not refused.written and refused.reason == "clock_regression"
    assert len(_journal_rows(path)) == 1
    assert journal.append(dict(row)).written
    assert len(_journal_rows(path)) == 2
    with pytest.raises(LiveProducerRefused, match="as_of_ms"):
        sinks_mod.ObservationJournal(path, key_order=("kind", "upper")).append({})


def test_red_a_band_row_missing_a_key_is_refused(tmp_path: Path) -> None:
    journal = sinks_mod.ObservationJournal(
        tmp_path / "band.jsonl",
        clock=lambda: 1,
        key_order=band_line_mod.BAND_KEY_ORDER,
    )
    with pytest.raises(LiveProducerRefused, match="missing"):
        journal.append({"kind": band_line_mod.BAND_LINE_KIND})


# -- the read side the runner uses ------------------------------------------


def _good_line(**overrides: Any) -> dict:
    line = {
        "kind": band_line_mod.BAND_LINE_KIND,
        "source_id": line_mod.SOURCE_ID,
        "instrument": INSTRUMENT,
        "trading_date": "20261019",
        "tr_id": quote_client.BAND_TR,
        "upper": BAND_UPPER,
        "lower": BAND_LOWER,
        "basis": BAND_BASIS,
        "raw_payload_digest": "f" * 64,
        "producer_continuity_id": "c" * 32,
        "as_of_ms": 1792286460000,
    }
    line.update(overrides)
    return line


_OPEN_MS = 1792286460000 - 1000


@pytest.mark.parametrize(
    "overrides,fragment",
    [
        ({"trading_date": "20261016"}, "trading_date"),
        ({"instrument": "A05610"}, "instrument"),
        ({"as_of_ms": _OPEN_MS - 1}, "before the open"),
        ({"kind": "cp3-band/2"}, "kind"),
        ({"as_of_ms": "1792286460000"}, "not an integer"),
    ],
)
def test_red_the_read_side_rejects_a_band_line_clause_by_clause(
    overrides: dict, fragment: str
) -> None:
    """Each clause the runner checks, with the input that makes it fire.

    The instrument clause's values are the measured ones: P-VL 2026-10-08 read
    ``A05610`` 987.46/1159.18 and ``A05611`` 990.48/1162.72, so a roll-day
    mix-up is ADMISSIBLE-looking rather than obviously wrong. Removing any one
    clause leaves its row here green and the session believing that line.
    """
    reason = band_line_mod.reject_reason(
        _good_line(**overrides),
        instrument=INSTRUMENT,
        trading_date="20261019",
        open_ms=_OPEN_MS,
    )
    assert reason is not None and fragment in reason


@pytest.mark.serial
def test_the_read_side_accepts_the_line_the_producer_writes(
    tmp_path: Path, market: Market
) -> None:
    """The positive half, against a line this producer actually wrote."""
    producer, _clock, _quotes = _build(tmp_path, market)
    producer.boot()
    producer.run_session()
    producer.finish()
    line = band_line_mod.read_last_band_line(producer.band_journal_path)
    open_ms, trading_date = band_line_mod.session_open_ms(
        producer.config.path, repo_root=_REPO_ROOT, day=TARGET
    )
    assert (
        band_line_mod.reject_reason(
            line,
            instrument=INSTRUMENT,
            trading_date=trading_date,
            open_ms=open_ms,
        )
        is None
    )


def test_the_read_side_never_falls_back_to_an_earlier_line(tmp_path: Path) -> None:
    """The LAST line only (§3.3, LOW-1), and a broken tail is ``None``."""
    path = tmp_path / "band.jsonl"
    path.write_text(
        json.dumps(_good_line()) + "\n" + json.dumps(_good_line(upper="9999")) + "\n",
        encoding="utf-8",
    )
    assert band_line_mod.read_last_band_line(path)["upper"] == "9999"
    path.write_text(json.dumps(_good_line()) + "\n{not json", encoding="utf-8")
    assert band_line_mod.read_last_band_line(path) is None
    assert band_line_mod.read_last_band_line(tmp_path / "absent.jsonl") is None


def test_the_open_the_read_side_uses_is_the_tenant_calendars_own() -> None:
    """One source of truth for the session window, two readers of it.

    ③ plan §3.5 forbids the runner growing its own copy of the session window.
    ``session_open_ms`` reads the producer config's own ``calendar_yaml`` /
    session id / phase with ``yaml.safe_load`` (it is imported by a bash
    heredoc and by a throwaway checkout, so it cannot pull in
    ``produce_fields``); this pins its answer against the loader the producer
    itself uses.
    """
    shipped = _REPO_ROOT / "config/tos_probes/cp3-live-producer.yaml"
    config = config_mod.load_config(shipped, repo_root=_REPO_ROOT)
    window = calendar_mod.load_runtime_calendar(
        config.calendar_yaml, covered_years=config.calendar_covered_years
    ).window(config.calendar_session_id, config.calendar_session_phase)
    expected = datetime.combine(TARGET, window.start, tzinfo=band_line_mod.KST)

    open_ms, trading_date = band_line_mod.session_open_ms(
        shipped, repo_root=_REPO_ROOT, day=TARGET
    )
    assert open_ms == int(expected.timestamp() * 1000)
    assert trading_date == TARGET.strftime("%Y%m%d")


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
    """The tools half of the hinge: the same bytes, through the real writer.

    Regenerated from the same synthetic market, the same ``received_ms`` and a
    pinned journal clock, so the only way this drifts is a real change in the
    line shape or the field values — which is exactly when the runtime-side
    half must be looked at too.

    **Written through ``ObservationJournal.append``, not ``json.dumps`` here**
    (review L1). Re-serialising in the test made the comparison a test of the
    test: changing the writer's ``separators`` or key order would have left
    this green while every real line changed shape. The bytes compared are now
    the bytes the writer produces.
    """
    expected = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    outcome = producer_mod.build_line(
        _fixture_frame(market, SEED_DAYS[-4:]),
        symbol=INSTRUMENT,
        strategy=inputs["strategy"],
        contract_spec=inputs["contract_spec"],
        anchor=inputs["anchor"],
        bar_minute=market.target_bars[-1][1],
        received_ms=expected["received_ms"],
    )
    assert outcome.row is not None
    assert "as_of_ms" not in outcome.row  # the journal owns the stamp (review B1)

    with tempfile.TemporaryDirectory() as scratch:
        regenerated = Path(scratch) / _FIXTURE.name
        journal = sinks_mod.ObservationJournal(
            regenerated, clock=lambda: expected["as_of_ms"]
        )
        assert journal.append(outcome.row).written
        assert regenerated.read_bytes() == _FIXTURE.read_bytes()


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
    assert row["source_id"] == line_mod.SOURCE_ID
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
        received_ms=1792286460001,
    )
    _FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    # Through the real writer, so the committed bytes are the writer's bytes.
    sinks_mod.ObservationJournal(_FIXTURE, clock=lambda: 1792286460123).append(
        outcome.row
    )


if __name__ == "__main__":  # pragma: no cover
    _regenerate()
    print(f"regenerated {_FIXTURE}", file=sys.stderr)
