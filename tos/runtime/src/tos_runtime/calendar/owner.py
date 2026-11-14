"""``SessionFactsOwner`` — the KST session/venue-facts runtime owner (Phase 5"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tos.time.elements import SessionContext
from tos.time.predicates import (
    session_open_positively,  # noqa: F401 (see module docstring)
)

from tos_runtime.calendar.config import CalendarConfig, calendar_bind_digest
from tos_runtime.calendar.model import MaturityFact, PhaseFact, WallClockReading
from tos_runtime.calendar.phase import (
    effective_phase_at,
    maturity_at,
    trading_date_at,
)
from tos_runtime.calendar.ports import WallClockReference
from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = [
    "SESSION_CALENDAR_BOUND_KIND",
    "SESSION_FACTS_OBSERVED_KIND",
    "SESSION_FACTS_SOURCE_ABSENT_KIND",
    "SessionCalendarMismatch",
    "SessionFacts",
    "SessionFactsOwner",
]

SESSION_CALENDAR_BOUND_KIND = "SESSION_CALENDAR_BOUND"
SESSION_FACTS_SOURCE_ABSENT_KIND = "SESSION_FACTS_SOURCE_ABSENT"
SESSION_FACTS_OBSERVED_KIND = "SESSION_FACTS_OBSERVED"

_NEVER_OBSERVED = object()


class SessionCalendarMismatch(RuntimeError):
    """Raised at construction when the calendar's own ``calendar_version``"""


@dataclass(frozen=True)
class SessionFacts:
    """One tick generation's worth of observed session facts for one"""

    phase_fact: PhaseFact
    maturity_fact: MaturityFact
    session_context: SessionContext | None
    wall_clock: WallClockReading | None
    tick_generation: int | None


class SessionFactsOwner:
    """The runtime owner of KST session/venue facts (plan §2 decision 3)."""

    def __init__(
        self,
        *,
        calendar: CalendarConfig,
        wall_clock: WallClockReference,
        evidence_store: SqliteEvidenceStore,
        tick_generation_reader: Callable[[], int | None],
        time_tz_db_version: str | None,
        time_trading_calendar_version: str | None,
        tz_db_version_observed: Callable[[], str | None] | None = None,
        trading_date_wall_clock: WallClockReference | None = None,
    ) -> None:
        """Construct the owner and record its two boot-time evidence rows."""
        if (
            calendar.calendar_version is not None
            and time_trading_calendar_version is not None
            and calendar.calendar_version != time_trading_calendar_version
        ):
            raise SessionCalendarMismatch(
                f"calendar.yaml calendar_version {calendar.calendar_version!r} != "
                f"time.yaml trading_calendar_version {time_trading_calendar_version!r} "
                "-- refusing to start (plan §2 decision 3)"
            )
        self._calendar = calendar
        self._wall_clock = wall_clock
        self._trading_date_wall_clock = (
            trading_date_wall_clock
            if trading_date_wall_clock is not None
            else wall_clock
        )
        self._evidence_store = evidence_store
        self._tick_generation_reader = tick_generation_reader
        self._time_tz_db_version = time_tz_db_version
        self._time_trading_calendar_version = time_trading_calendar_version
        self._tz_db_version_observed = tz_db_version_observed

        self._cache_generation: int | None = None
        self._cache_wall_clock_ms: int | None = None
        self._cache: dict[str, SessionFacts] = {}
        self._last_phase: dict[str, object] = {}
        self._last_expired: dict[str, object] = {}

        self._evidence_store.append(
            {
                "calendar_version": calendar.calendar_version,
                "holiday_count": len(calendar.holidays),
                "sessions_digest": calendar_bind_digest(calendar),
            },
            kind=SESSION_CALENDAR_BOUND_KIND,
            record_class=SESSION_CALENDAR_BOUND_KIND,
        )
        reading = self._wall_clock.read()
        if reading is None:
            describe = getattr(self._wall_clock, "describe", None)
            reason = (
                describe()
                if callable(describe)
                else "wall-clock reference reports no reading at boot"
            )
            self._evidence_store.append(
                {"reason": reason},
                kind=SESSION_FACTS_SOURCE_ABSENT_KIND,
                record_class=SESSION_FACTS_SOURCE_ABSENT_KIND,
            )

    def observe(self, instrument_class: str) -> SessionFacts:
        """The current tick generation's session facts for ``instrument_class``,"""
        generation = self._tick_generation_reader()
        reading = self._wall_clock.read()
        wall_clock_ms = None if reading is None else reading.unix_ms
        if (
            generation != self._cache_generation
            or wall_clock_ms != self._cache_wall_clock_ms
        ):
            self._cache = {}
            self._cache_generation = generation
            self._cache_wall_clock_ms = wall_clock_ms
        cached = self._cache.get(instrument_class)
        if cached is not None:
            return cached
        facts = self._compute(instrument_class, generation)
        self._cache[instrument_class] = facts
        self._maybe_record_observed(instrument_class, facts)
        return facts

    def phase_for_step3(self, instrument_class: str) -> str | None:
        """The ``observed_session_phase`` string step 3's ``VenueConstraintStage``"""
        return self.observe(instrument_class).phase_fact.phase

    def trading_date_now(self, instrument_class: str) -> str | None:
        """The KST trading date for ``instrument_class`` at this instant"""
        reading = self._trading_date_wall_clock.read()
        if reading is None:
            return None
        return trading_date_at(reading.unix_ms, instrument_class, self._calendar)

    def session_context(self, instrument_class: str) -> SessionContext | None:
        """The kernel ``tos.time.SessionContext`` for ``instrument_class`` this"""
        return self.observe(instrument_class).session_context

    def session_facts_current(self, instrument_class: str) -> bool:
        """Item 12's ``session_facts_current`` sub-fact (kernel round #3 §2"""
        facts = self.observe(instrument_class)
        return (
            facts.phase_fact.phase is not None
            and facts.tick_generation == self._tick_generation_reader()
            and self._calendar.calendar_version == self._time_trading_calendar_version
        )

    def tradability_facts_current(self, *, broker_reaching: bool) -> bool | None:
        """Item 12's ``tradability_facts_current`` sub-fact (kernel round #3"""
        return None if broker_reaching else True

    def account_facts_current(self, *, broker_reaching: bool) -> bool | None:
        """Item 12's ``account_facts_current`` sub-fact (kernel round #3 §2"""
        return None if broker_reaching else True

    def _compute(self, instrument_class: str, generation: int | None) -> SessionFacts:
        reading = self._wall_clock.read()
        if reading is None:
            phase_fact = PhaseFact(
                phase=None,
                is_open=None,
                boundary_unix_ms=None,
                source="calendar",
                calendar_version=self._calendar.calendar_version,
            )
            maturity_fact = MaturityFact(
                expiry_date=None,
                expired=None,
                rule_present=instrument_class in self._calendar.futures_expiry,
            )
            return SessionFacts(
                phase_fact=phase_fact,
                maturity_fact=maturity_fact,
                session_context=None,
                wall_clock=None,
                tick_generation=generation,
            )
        phase_fact = effective_phase_at(
            reading.unix_ms, instrument_class, self._calendar
        )
        maturity_fact = maturity_at(reading.unix_ms, instrument_class, self._calendar)
        session_context = self._build_session_context(phase_fact)
        return SessionFacts(
            phase_fact=phase_fact,
            maturity_fact=maturity_fact,
            session_context=session_context,
            wall_clock=reading,
            tick_generation=generation,
        )

    def _build_session_context(self, phase_fact: PhaseFact) -> SessionContext:
        """Fold this tick's ``PhaseFact`` into a kernel ``tos.time.SessionContext``."""
        observed = (
            self._tz_db_version_observed() if self._tz_db_version_observed else None
        )
        conflict = (
            self._time_tz_db_version is not None
            and observed is not None
            and self._time_tz_db_version != observed
        )
        return SessionContext(
            tz_id=self._calendar.tz_id,
            tz_db_version=self._time_tz_db_version,
            trading_calendar_version=self._calendar.calendar_version,
            phase=phase_fact.phase,
            is_open=bool(phase_fact.is_open),
            tz_version_conflict=conflict,
            boundary_value=phase_fact.boundary_unix_ms,
        )

    def _maybe_record_observed(
        self, instrument_class: str, facts: SessionFacts
    ) -> None:
        """Record ``SESSION_FACTS_OBSERVED`` only when the phase token or the"""
        new_phase = facts.phase_fact.phase
        new_expired = facts.maturity_fact.expired
        prev_phase = self._last_phase.get(instrument_class, _NEVER_OBSERVED)
        prev_expired = self._last_expired.get(instrument_class, _NEVER_OBSERVED)
        changed = prev_phase != new_phase or prev_expired != new_expired
        if changed:
            payload: dict[str, object] = {
                "instrument_class": instrument_class,
                "phase": new_phase,
                "expired": new_expired,
                "tick_generation": facts.tick_generation,
            }
            if facts.session_context is not None:
                payload["open_expectation_evaluated"] = False
                payload["open_expectation_reason"] = (
                    "no UncertaintyInterval source is exposed by "
                    "TrustworthyTimeService today (W5 survey §3) -- "
                    "session_open_positively is never called with a "
                    "fabricated interval"
                )
            self._evidence_store.append(
                payload,
                kind=SESSION_FACTS_OBSERVED_KIND,
                record_class=SESSION_FACTS_OBSERVED_KIND,
            )
        self._last_phase[instrument_class] = new_phase
        self._last_expired[instrument_class] = new_expired
