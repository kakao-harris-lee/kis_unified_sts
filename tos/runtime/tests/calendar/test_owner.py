"""``tos_runtime.calendar.owner.SessionFactsOwner`` — isolated unit tests (TOS"""

from __future__ import annotations

import datetime
import json
import zoneinfo
from pathlib import Path

import pytest
from tos_runtime.calendar.config import load_calendar_config
from tos_runtime.calendar.model import WallClockReading
from tos_runtime.calendar.owner import (
    SESSION_CALENDAR_BOUND_KIND,
    SESSION_FACTS_OBSERVED_KIND,
    SESSION_FACTS_SOURCE_ABSENT_KIND,
    SessionCalendarMismatch,
    SessionFactsOwner,
)
from tos_runtime.calendar.ports import AbsentWallClockReference, FixedWallClockReference
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore

from .conftest import (
    FIXTURE_HOLIDAY,
    FUTURES_CLASS,
    STOCK_CLASS,
    write_fixture_calendar,
)

_KST = zoneinfo.ZoneInfo("Asia/Seoul")


def _kst_ms(year: int, month: int, day: int, hour: int, minute: int) -> int:
    return int(
        datetime.datetime(year, month, day, hour, minute, tzinfo=_KST).timestamp()
        * 1000
    )


class FixedKeyProvider:
    """A :class:`~tos_runtime.evidence.store.KeyProvider` test double — fixed"""

    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes-calendar-owner")

    def generations(self) -> tuple[int, ...]:
        return (1,)

    def key_for(self, generation: int) -> bytes:
        del generation
        return b"test-fixed-key-bytes-calendar-owner"


class _SteppingWallClock:
    """A settable :class:`~tos_runtime.calendar.ports.WallClockReference` test"""

    def __init__(self, unix_ms: int) -> None:
        self.unix_ms = unix_ms

    def read(self):
        return WallClockReading(unix_ms=self.unix_ms, source_label="stepping-test")


class _SteppingGeneration:
    """A settable tick-generation reader double."""

    def __init__(self, generation: int | None) -> None:
        self.generation = generation

    def read(self) -> int | None:
        return self.generation


@pytest.fixture
def key_provider() -> KeyProvider:
    return FixedKeyProvider()


@pytest.fixture
def evidence_store(tmp_path: Path, key_provider: KeyProvider):
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=key_provider
    )
    yield instance
    instance.close()


def _kind_count(evidence_store: SqliteEvidenceStore, kind: str) -> int:
    return sum(1 for entry in evidence_store.iter_entry_meta() if entry.kind == kind)


def test_construction_records_session_calendar_bound_once(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    SessionFactsOwner(
        calendar=calendar,
        wall_clock=AbsentWallClockReference(),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: None,
        time_tz_db_version="tzdb-1",
        time_trading_calendar_version=calendar.calendar_version,
    )
    assert _kind_count(evidence_store, SESSION_CALENDAR_BOUND_KIND) == 1


def test_matching_calendar_versions_construct_cleanly(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=AbsentWallClockReference(),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: None,
        time_tz_db_version="tzdb-1",
        time_trading_calendar_version=calendar.calendar_version,
    )
    assert owner is not None


def test_mismatched_calendar_version_refuses_construction(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """Mutation M4: skipping this cross-check would let a stale/incompatible"""
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    with pytest.raises(SessionCalendarMismatch):
        SessionFactsOwner(
            calendar=calendar,
            wall_clock=AbsentWallClockReference(),
            evidence_store=evidence_store,
            tick_generation_reader=lambda: None,
            time_tz_db_version="tzdb-1",
            time_trading_calendar_version="a-completely-different-version",
        )


def test_none_calendar_or_time_version_never_raises_mismatch(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """Either side ``None`` (still named-TBD upstream) is not a MISMATCH —"""
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=AbsentWallClockReference(),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: None,
        time_tz_db_version=None,
        time_trading_calendar_version=None,
    )
    assert owner is not None


def test_absent_wall_clock_yields_none_phase_and_records_absent_once(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=AbsentWallClockReference(),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: 1,
        time_tz_db_version=None,
        time_trading_calendar_version=None,
    )
    assert owner.phase_for_step3(STOCK_CLASS) is None
    assert owner.session_context(STOCK_CLASS) is None
    owner.observe(STOCK_CLASS)
    owner.observe(FUTURES_CLASS)
    assert _kind_count(evidence_store, SESSION_FACTS_SOURCE_ABSENT_KIND) == 1


def test_session_facts_current_is_false_when_phase_absent(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """``session_facts_current`` (kernel round #3 §2 decision 4, ex-plan §2"""
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=AbsentWallClockReference(),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: 1,
        time_tz_db_version=None,
        time_trading_calendar_version=None,
    )
    assert owner.session_facts_current(STOCK_CLASS) is False


def test_synthetic_scope_open_session_is_true(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    instant = _kst_ms(2026, 1, 5, 10, 0)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=FixedWallClockReference(instant),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: 1,
        time_tz_db_version="tzdb-1",
        time_trading_calendar_version=calendar.calendar_version,
    )
    assert owner.phase_for_step3(STOCK_CLASS) == "CONTINUOUS"
    assert owner.session_facts_current(STOCK_CLASS) is True
    assert owner.tradability_facts_current(broker_reaching=False) is True
    assert owner.account_facts_current(broker_reaching=False) is True


def test_broker_reaching_scope_tradability_and_account_are_unknown_not_true(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """Mutation M2: a broker-reaching scope must NEVER be silently fabricated"""
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    instant = _kst_ms(2026, 1, 5, 10, 0)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=FixedWallClockReference(instant),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: 1,
        time_tz_db_version="tzdb-1",
        time_trading_calendar_version=calendar.calendar_version,
    )
    assert owner.tradability_facts_current(broker_reaching=True) is None
    assert owner.account_facts_current(broker_reaching=True) is None
    assert owner.session_facts_current(STOCK_CLASS) is True


def test_after_hours_phase_is_closed(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """Fixed at 22:00 (well outside the stock fixture's 09:00-15:30 window) —"""
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    instant = _kst_ms(2026, 1, 5, 22, 0)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=FixedWallClockReference(instant),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: 1,
        time_tz_db_version="tzdb-1",
        time_trading_calendar_version=calendar.calendar_version,
    )
    assert owner.phase_for_step3(STOCK_CLASS) == "CLOSED"


def test_holiday_phase_is_closed_even_during_the_regular_window(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """The fixture holiday (a Thursday that would otherwise be a regular"""
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    holiday_date = datetime.date.fromisoformat(FIXTURE_HOLIDAY)
    instant = _kst_ms(holiday_date.year, holiday_date.month, holiday_date.day, 10, 0)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=FixedWallClockReference(instant),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: 1,
        time_tz_db_version="tzdb-1",
        time_trading_calendar_version=calendar.calendar_version,
    )
    assert owner.phase_for_step3(STOCK_CLASS) == "CLOSED"


def test_closed_phase_session_facts_current_is_not_false_by_itself(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """``session_facts_current`` only checks phase non-``None`` (a KNOWN"""
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    instant = _kst_ms(2026, 1, 5, 22, 0)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=FixedWallClockReference(instant),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: 1,
        time_tz_db_version="tzdb-1",
        time_trading_calendar_version=calendar.calendar_version,
    )
    assert owner.phase_for_step3(STOCK_CLASS) == "CLOSED"
    assert owner.session_facts_current(STOCK_CLASS) is True


def test_session_facts_observed_fires_once_on_first_observation(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    instant = _kst_ms(2026, 1, 5, 10, 0)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=FixedWallClockReference(instant),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: 1,
        time_tz_db_version=None,
        time_trading_calendar_version=None,
    )
    owner.observe(STOCK_CLASS)
    assert _kind_count(evidence_store, SESSION_FACTS_OBSERVED_KIND) == 1


def test_session_facts_observed_count_unchanged_across_two_ticks_same_phase(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    clock = _SteppingWallClock(_kst_ms(2026, 1, 5, 10, 0))
    generation = _SteppingGeneration(1)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=clock,
        evidence_store=evidence_store,
        tick_generation_reader=generation.read,
        time_tz_db_version=None,
        time_trading_calendar_version=None,
    )
    owner.observe(STOCK_CLASS)
    assert _kind_count(evidence_store, SESSION_FACTS_OBSERVED_KIND) == 1

    generation.generation = 2
    owner.observe(STOCK_CLASS)
    assert _kind_count(evidence_store, SESSION_FACTS_OBSERVED_KIND) == 1

    generation.generation = 3
    clock.unix_ms = _kst_ms(2026, 1, 5, 22, 0)
    owner.observe(STOCK_CLASS)
    assert _kind_count(evidence_store, SESSION_FACTS_OBSERVED_KIND) == 2


def test_observe_caches_within_the_same_tick_generation(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """Calling ``observe`` twice at the SAME generation must not double-count"""
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=FixedWallClockReference(_kst_ms(2026, 1, 5, 10, 0)),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: 1,
        time_tz_db_version=None,
        time_trading_calendar_version=None,
    )
    owner.observe(STOCK_CLASS)
    owner.observe(STOCK_CLASS)
    owner.observe(STOCK_CLASS)
    assert _kind_count(evidence_store, SESSION_FACTS_OBSERVED_KIND) == 1


def test_observe_recomputes_when_the_wall_clock_advances_without_a_tick(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """While the session is closed no tick is consumed, so the tick generation never moves —"""
    calendar = load_calendar_config(write_fixture_calendar(tmp_path))
    clock = _SteppingWallClock(_kst_ms(2026, 1, 5, 8, 0))
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=clock,
        evidence_store=evidence_store,
        tick_generation_reader=lambda: 7,
        time_tz_db_version="tzdb-1",
        time_trading_calendar_version=calendar.calendar_version,
    )
    before = owner.session_context(STOCK_CLASS)
    assert before is not None and before.is_open is False
    clock.unix_ms = _kst_ms(2026, 1, 5, 10, 0)
    after = owner.session_context(STOCK_CLASS)
    assert after is not None and after.is_open is True


def test_session_open_expectation_fields_folded_into_session_facts_observed(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=FixedWallClockReference(_kst_ms(2026, 1, 5, 10, 0)),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: 1,
        time_tz_db_version=None,
        time_trading_calendar_version=None,
    )
    owner.observe(STOCK_CLASS)
    rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ?",
        (SESSION_FACTS_OBSERVED_KIND,),
    ).fetchall()
    assert len(rows) == 1
    payload = json.loads(rows[0][0])["payload"]
    assert payload["open_expectation_evaluated"] is False


def test_session_open_expectation_fields_absent_when_wall_clock_absent(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """No session context, no wall clock -- the open-expectation fields are"""
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=AbsentWallClockReference(),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: 1,
        time_tz_db_version=None,
        time_trading_calendar_version=None,
    )
    owner.observe(STOCK_CLASS)
    rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ?",
        (SESSION_FACTS_OBSERVED_KIND,),
    ).fetchall()
    assert len(rows) == 1
    payload = json.loads(rows[0][0])["payload"]
    assert "open_expectation_evaluated" not in payload


def test_session_open_expectation_fields_do_not_fire_every_tick(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """The folded fields inherit SESSION_FACTS_OBSERVED's own change-only"""
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    generation = _SteppingGeneration(1)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=FixedWallClockReference(_kst_ms(2026, 1, 5, 10, 0)),
        evidence_store=evidence_store,
        tick_generation_reader=generation.read,
        time_tz_db_version=None,
        time_trading_calendar_version=None,
    )
    owner.observe(STOCK_CLASS)
    generation.generation = 2
    owner.observe(STOCK_CLASS)
    generation.generation = 3
    owner.observe(STOCK_CLASS)
    assert _kind_count(evidence_store, SESSION_FACTS_OBSERVED_KIND) == 1


def test_unknown_instrument_class_yields_none_phase(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=FixedWallClockReference(_kst_ms(2026, 1, 5, 10, 0)),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: 1,
        time_tz_db_version=None,
        time_trading_calendar_version=None,
    )
    assert owner.phase_for_step3("some-unconfigured-class") is None


def _owner_at(tmp_path: Path, evidence_store: SqliteEvidenceStore, wall_clock):
    calendar = load_calendar_config(write_fixture_calendar(tmp_path))
    return SessionFactsOwner(
        calendar=calendar,
        wall_clock=wall_clock,
        evidence_store=evidence_store,
        tick_generation_reader=lambda: None,
        time_tz_db_version="tzdb-1",
        time_trading_calendar_version=calendar.calendar_version,
    )


def test_trading_date_now_reads_the_owners_own_wall_clock(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    owner = _owner_at(
        tmp_path, evidence_store, FixedWallClockReference(_kst_ms(2026, 1, 5, 10, 0))
    )
    assert owner.trading_date_now("krx-stock-fixture") == "20260105"


def test_trading_date_now_is_none_without_a_wall_clock_reading(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """Production reads the trusted-time-gated reference: untrusted time means no date."""
    owner = _owner_at(tmp_path, evidence_store, AbsentWallClockReference())
    assert owner.trading_date_now("krx-stock-fixture") is None


def test_trading_date_now_prefers_its_own_injected_clock(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """Production injects a trusted-AND-fresh reference for the trading date only (review"""
    calendar = load_calendar_config(write_fixture_calendar(tmp_path))
    owner = SessionFactsOwner(
        calendar=calendar,
        wall_clock=FixedWallClockReference(_kst_ms(2026, 1, 5, 10, 0)),
        evidence_store=evidence_store,
        tick_generation_reader=lambda: None,
        time_tz_db_version="tzdb-1",
        time_trading_calendar_version=calendar.calendar_version,
        trading_date_wall_clock=AbsentWallClockReference(),
    )
    assert owner.phase_for_step3("krx-stock-fixture") == "CONTINUOUS"
    assert owner.trading_date_now("krx-stock-fixture") is None


def test_fresh_trusted_reference_is_absent_when_the_service_says_stale() -> None:
    from tos_runtime.calendar.ports import FreshTrustedWallClockReference

    class _Service:
        def __init__(self, value: int | None) -> None:
            self.value = value
            self.asked: list[int] = []

        def wall_clock_now_if_fresh(self, max_age_ms: int) -> int | None:
            self.asked.append(max_age_ms)
            return self.value

    fresh = _Service(1_789_601_400_000)
    reading = FreshTrustedWallClockReference(fresh, max_age_ms=1000).read()
    assert reading is not None and reading.unix_ms == 1_789_601_400_000
    assert fresh.asked == [1000]
    assert (
        FreshTrustedWallClockReference(_Service(None), max_age_ms=1000).read() is None
    )
