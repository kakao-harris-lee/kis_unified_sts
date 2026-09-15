"""``tos_runtime.calendar.owner.SessionFactsOwner`` — isolated unit tests (TOS
Phase 5 W5 plan §2 decision 3).

Hermetic (D1.4): a real :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`
under ``tmp_path`` + a fixed-byte :class:`FixedKeyProvider` test double (the same
minimal shape ``tos/runtime/tests/evidence/conftest.py`` uses, re-declared here
rather than imported — cross-suite imports are forbidden, each package's
fixtures stay in its own suite). No compose stack, no engine, no gateway: this
file proves the owner's OWN caching/evidence/derivation logic directly, before
``tests/compose/test_session_wiring.py`` exercises it through a full composed
runtime.
"""

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
    """A :class:`~tos_runtime.evidence.store.KeyProvider` test double — fixed
    bytes (mirrors ``tests/evidence/conftest.py::FixedKeyProvider``, re-declared
    per that module's own "cross-suite imports are forbidden" convention)."""

    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes-calendar-owner")

    def generations(self) -> tuple[int, ...]:
        return (1,)


class _SteppingWallClock:
    """A settable :class:`~tos_runtime.calendar.ports.WallClockReference` test
    double — the test flips ``.unix_ms`` between :meth:`SessionFactsOwner.observe`
    calls to simulate the wall clock advancing across tick generations."""

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


# ============================================================================
# Boot-time evidence + calendar/time-config cross-check (M4)
# ============================================================================


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
    """Mutation M4: skipping this cross-check would let a stale/incompatible
    calendar silently boot alongside a disagreeing ``time.yaml``."""
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
    """Either side ``None`` (still named-TBD upstream) is not a MISMATCH —
    only two known, disagreeing values refuse construction."""
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


# ============================================================================
# Absent wall clock — honest None facts + SESSION_FACTS_SOURCE_ABSENT once
# ============================================================================


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
    # Observing multiple times (even across generations) never re-records the
    # boot-time ABSENT fact — it is a construction-time observation, not a
    # per-tick one.
    owner.observe(STOCK_CLASS)
    owner.observe(FUTURES_CLASS)
    assert _kind_count(evidence_store, SESSION_FACTS_SOURCE_ABSENT_KIND) == 1


def test_session_facts_current_is_false_when_phase_absent(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """``session_facts_current`` (kernel round #3 §2 decision 4, ex-plan §2
    decision 3 (c)'s ``session_current`` conjunct) is a plain boolean, never
    itself tri-state — an absent phase fact makes it definitely ``False``
    (never a mysterious ``None`` needing its own propagation; only
    ``tradability_facts_current``/``account_facts_current`` can be
    ``None``)."""
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


# ============================================================================
# session_facts_current / tradability_facts_current / account_facts_current —
# the three raw sub-facts (kernel round #3 §2 decision 4). The None-
# propagating AND that used to live here now lives in the kernel's own
# ``tos.egressgw.venuefacts.venue_session_account_facts_current`` (see
# ``tos/tests/egressgw/test_venuefacts.py`` for its exhaustive 27-combination
# table) — this owner supplies each raw sub-fact only.
# ============================================================================


def test_synthetic_scope_open_session_is_true(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    calendar_path = write_fixture_calendar(tmp_path)
    calendar = load_calendar_config(calendar_path)
    # 2026-01-05 10:00 KST is a Monday within the fixture's 09:00-15:30 window.
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
    """Mutation M2: a broker-reaching scope must NEVER be silently fabricated
    True — this is the exact fact ``test_kis_mock_e2e_honesty.py``'s honesty
    pin depends on staying UNKNOWN (via the kernel composite, which sees a
    ``None`` sub-fact here)."""
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
    # session_facts_current does not depend on broker_reaching at all.
    assert owner.session_facts_current(STOCK_CLASS) is True


def test_after_hours_phase_is_closed(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """Fixed at 22:00 (well outside the stock fixture's 09:00-15:30 window) —
    ``phase_for_step3`` reports the calendar's ``closed_phase``, never a
    fabricated open phase. The kernel's own ``session_phase_admits`` is what
    actually denies admission on a closed phase (at step 3) — this owner
    never asserts admissibility itself (module docstring)."""
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
    """The fixture holiday (a Thursday that would otherwise be a regular
    trading weekday) overrides the weekday window entirely — 10:00 on that
    date is CLOSED, not CONTINUOUS."""
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
    """``session_facts_current`` only checks phase non-``None`` (a KNOWN
    closed phase is still a known fact) — this owner never re-implements the
    kernel's own ``session_phase_admits`` membership judgement, so a closed
    phase alone does not, by itself, make this sub-fact ``False``."""
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


# ============================================================================
# SESSION_FACTS_OBSERVED — only on change (decision 10)
# ============================================================================


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

    # Second tick, same instant/phase (CONTINUOUS) -- count must NOT increase.
    generation.generation = 2
    owner.observe(STOCK_CLASS)
    assert _kind_count(evidence_store, SESSION_FACTS_OBSERVED_KIND) == 1

    # Third tick crosses the window boundary (22:00, now CLOSED) -- +1.
    generation.generation = 3
    clock.unix_ms = _kst_ms(2026, 1, 5, 22, 0)
    owner.observe(STOCK_CLASS)
    assert _kind_count(evidence_store, SESSION_FACTS_OBSERVED_KIND) == 2


def test_observe_caches_within_the_same_tick_generation(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """Calling ``observe`` twice at the SAME generation must not double-count
    even a genuine first-time observation."""
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


# ============================================================================
# Session-open-expectation fields (folded into SESSION_FACTS_OBSERVED — team-
# lead review follow-up, 2026-09-12: no separate kind, no per-tick firing)
# ============================================================================


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
    """No session context, no wall clock -- the open-expectation fields are
    only ever folded in alongside a real observed instant (never fabricated
    for an absent wall clock)."""
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
    """The folded fields inherit SESSION_FACTS_OBSERVED's own change-only
    gate -- three same-phase ticks record them exactly once, not three
    times."""
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


# ============================================================================
# Unknown instrument class -- never guessed
# ============================================================================


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
