"""``SessionFactsOwner`` — the KST session/venue-facts runtime owner (Phase 5
W5 plan §2 decision 3, ``docs/plans/2026-09-12-tos-phase5-w5-scenarios-plan.md``).

This is the one place that turns :mod:`tos_runtime.calendar`'s pure functions
(``session_phase_at``/``maturity_at``/``effective_phase_at``) plus an injected
:class:`~tos_runtime.calendar.ports.WallClockReference` into the two facts the
rest of compose actually consumes:

* :meth:`SessionFactsOwner.phase_for_step3` — the ``observed_session_phase``
  string step 3's ``VenueConstraintStage`` needs (W5 survey §2: previously a
  hardcoded ``ConstructionConfig`` literal, now this owner's honest read).
* :meth:`SessionFactsOwner.venue_session_account_facts_current` — item 12's
  remaining operator attestation (:mod:`tos_runtime.compose._egress_attestations`,
  now retired to zero, plan §2 decision 4), replaced by a real, structurally
  derived fact.

**Never asserts admissibility itself.** The phase token this owner produces is
opaque calendar DATA (:mod:`tos_runtime.calendar.config`'s own module
docstring); the KERNEL's own ``session_phase_admits``/``VenueConstraintStage``
is the sole authority on whether that token permits an action. This module
only observes, caches per tick generation, and evidences.

**Wall-clock honesty (G-1, plan §6 ①).** When the injected
:class:`~tos_runtime.calendar.ports.WallClockReference` reports no reading
(the production default, :class:`~tos_runtime.calendar.ports.AbsentWallClockReference`),
every fact this owner produces is honestly ``None`` — never a fabricated
phase/maturity/session-context. ``SESSION_FACTS_SOURCE_ABSENT`` is recorded
once, at construction, when that is the case.

**Tick-generation caching.** Mirrors the ``_current_tick_generation``/
``_InboxCell`` idiom :mod:`tos_runtime.compose._safety_wiring` already uses:
``tick_generation_reader`` is a zero-argument callable (typically closing over
a late-bound cell over the durable inbox's own ``count``, since the inbox does
not exist yet when this owner is constructed — see
:mod:`tos_runtime.compose._session_wiring`). :meth:`observe` recomputes only
when the generation changes, never on every call within the same tick.

**The broker-scope endpoint classification is never read in this module.**
An EC-1 governance gate (``tests/brokercap/test_exit_conditions.py`` and
``tests/brokercap/test_scopes.py``) only allows that
:class:`~tos_runtime.brokercap.scopes.BrokerScope` attribute to be read
inside the ``brokercap`` package itself.
:meth:`SessionFactsOwner.venue_session_account_facts_current` therefore
takes a plain ``broker_reaching: bool`` the CALLER derives via
:func:`tos_runtime.brokercap.is_broker_reaching` (see
:mod:`tos_runtime.compose.root`) — never the scope object itself.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.time``
(``SessionContext``, ``session_open_positively``) + ``tos_runtime.calendar`` +
``tos_runtime.evidence.store`` only. No ``shared.*``, no ``tos_runtime.brokercap``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tos.time.elements import SessionContext
from tos.time.predicates import (
    session_open_positively,  # noqa: F401 (see module docstring)
)

from tos_runtime.calendar.config import CalendarConfig, calendar_bind_digest
from tos_runtime.calendar.model import MaturityFact, PhaseFact, WallClockReading
from tos_runtime.calendar.phase import effective_phase_at, maturity_at
from tos_runtime.calendar.ports import WallClockReference
from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = [
    "SESSION_CALENDAR_BOUND_KIND",
    "SESSION_FACTS_OBSERVED_KIND",
    "SESSION_FACTS_SOURCE_ABSENT_KIND",
    "SESSION_OPEN_EXPECTATION_KIND",
    "SessionCalendarMismatch",
    "SessionFacts",
    "SessionFactsOwner",
]

#: Evidence kinds (plan §2 decision 10) — runtime constants, never a kernel
#: ``EvidenceKind`` member (mirrors ``ComposedRuntime``'s own
#: ``_NEW_RISK_HALT_CLEARED_KIND`` precedent for a runtime-level record kind).
SESSION_CALENDAR_BOUND_KIND = "SESSION_CALENDAR_BOUND"
SESSION_FACTS_SOURCE_ABSENT_KIND = "SESSION_FACTS_SOURCE_ABSENT"
SESSION_FACTS_OBSERVED_KIND = "SESSION_FACTS_OBSERVED"
SESSION_OPEN_EXPECTATION_KIND = "SESSION_OPEN_EXPECTATION"

#: Sentinel distinguishing "never observed before" from an observed ``None``
#: phase/expired value, so the very first observation for an instrument class
#: always counts as a change (plan §2 decision 10: ``SESSION_FACTS_OBSERVED``
#: fires "only when the phase token or maturity state changes").
_NEVER_OBSERVED = object()


class SessionCalendarMismatch(RuntimeError):
    """Raised at construction when the calendar's own ``calendar_version``
    disagrees with ``time.yaml``'s ``trading_calendar_version`` (both
    non-``None``) — plan §2 decision 3, mutation M4. A boot refusal, never a
    silently-tolerated drift between the two configs."""


@dataclass(frozen=True)
class SessionFacts:
    """One tick generation's worth of observed session facts for one
    instrument class (:meth:`SessionFactsOwner.observe`)."""

    phase_fact: PhaseFact
    maturity_fact: MaturityFact
    session_context: SessionContext | None
    wall_clock: WallClockReading | None
    tick_generation: int | None


def _and_with_none(*values: bool | None) -> bool | None:
    """Three-way AND with ``None`` propagation (plan §2 decision 3 (c)):
    ``False`` dominates (any known-negative fact makes the whole conjunction
    negative); otherwise ``None`` if any conjunct is unknown; ``True`` only
    when every conjunct is positively known."""
    if any(v is False for v in values):
        return False
    if any(v is None for v in values):
        return None
    return True


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
    ) -> None:
        """Construct the owner and record its two boot-time evidence rows.

        Args:
            calendar: The loaded, validated calendar (:func:`~tos_runtime.calendar
                .config.load_calendar_config`).
            wall_clock: The injected wall-clock reference (production default:
                :class:`~tos_runtime.calendar.ports.AbsentWallClockReference`).
            evidence_store: Where ``SESSION_CALENDAR_BOUND``/
                ``SESSION_FACTS_SOURCE_ABSENT``/``SESSION_FACTS_OBSERVED``/
                ``SESSION_OPEN_EXPECTATION`` are recorded.
            tick_generation_reader: Zero-argument callable returning the
                current tick generation, or ``None`` before any tick has run
                (typically a late-bound cell over the durable inbox's own
                ``count`` — see :mod:`tos_runtime.compose._session_wiring`).
            time_tz_db_version: ``time.yaml``'s ``tz_db_version`` (opaque
                version label, never compared byte-for-byte against
                ``zoneinfo`` internals — this owner has no way to introspect
                the system tzdata package's own version).
            time_trading_calendar_version: ``time.yaml``'s
                ``trading_calendar_version`` — cross-checked against
                ``calendar.calendar_version`` below.
            tz_db_version_observed: An optional zero-argument callable
                reporting an independently-observed tzdata version label, or
                ``None`` when no such source exists (the honest default today
                — W5 survey found none). See :meth:`_session_context`'s own
                docstring for how this feeds ``tz_version_conflict``.

        Raises:
            SessionCalendarMismatch: ``calendar.calendar_version`` and
                ``time_trading_calendar_version`` are both known and disagree.
        """
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
        self._evidence_store = evidence_store
        self._tick_generation_reader = tick_generation_reader
        self._time_tz_db_version = time_tz_db_version
        self._time_trading_calendar_version = time_trading_calendar_version
        self._tz_db_version_observed = tz_db_version_observed

        self._cache_generation: int | None = None
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
        """The current tick generation's session facts for ``instrument_class``,
        cached once per generation (module docstring)."""
        generation = self._tick_generation_reader()
        if generation != self._cache_generation:
            self._cache = {}
            self._cache_generation = generation
        cached = self._cache.get(instrument_class)
        if cached is not None:
            return cached
        facts = self._compute(instrument_class, generation)
        self._cache[instrument_class] = facts
        self._maybe_record_observed(instrument_class, facts)
        return facts

    def phase_for_step3(self, instrument_class: str) -> str | None:
        """The ``observed_session_phase`` string step 3's ``VenueConstraintStage``
        should fold this tick — ``None`` when no wall-clock reading is available
        (never a fabricated phase; the kernel treats an absent phase as UNKNOWN,
        not as a silent admit)."""
        return self.observe(instrument_class).phase_fact.phase

    def session_context(self, instrument_class: str) -> SessionContext | None:
        """The kernel ``tos.time.SessionContext`` for ``instrument_class`` this
        tick, or ``None`` when no wall-clock reading is available."""
        return self.observe(instrument_class).session_context

    def venue_session_account_facts_current(
        self, instrument_class: str, *, broker_reaching: bool
    ) -> bool | None:
        """Item 12's ``venue_session_account_facts_current`` (plan §2 decision
        3 (c)) — a three-way AND, with ``None`` propagation, of:

        * ``session_current``: this tick's phase fact exists, was observed at
          the CURRENT tick generation, and ``calendar.calendar_version``
          matches ``time.yaml``'s ``trading_calendar_version`` (the same
          cross-check the constructor already enforces at boot — re-asserted
          per-call as a genuine currentness fact, not a re-derivation of a
          different judgement).
        * ``tradability_current`` / ``account_facts_current``: structurally
          ``True`` when ``broker_reaching`` is ``False`` (the caller derives
          this via :func:`~tos_runtime.brokercap.is_broker_reaching` — the
          same structural fact :func:`~tos_runtime.brokercap.derive_item6_item12`
          already uses for item 12's OTHER field) — a synthetic transport is
          its own only ledger, so there is no separate tradability/account-
          halt source to be stale. When ``broker_reaching`` is ``True``,
          ``None``: this runtime has no KIS tradability/account-halt query TR
          consumer yet (a transport-track follow-up), so these two facts are
          honestly unsourced, never fabricated ``True``.
        """
        facts = self.observe(instrument_class)
        session_current = (
            facts.phase_fact.phase is not None
            and facts.tick_generation == self._tick_generation_reader()
            and self._calendar.calendar_version == self._time_trading_calendar_version
        )
        tradability_current: bool | None = None if broker_reaching else True
        account_facts_current: bool | None = None if broker_reaching else True
        return _and_with_none(
            session_current, tradability_current, account_facts_current
        )

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
        self._record_session_open_expectation(session_context)
        return SessionFacts(
            phase_fact=phase_fact,
            maturity_fact=maturity_fact,
            session_context=session_context,
            wall_clock=reading,
            tick_generation=generation,
        )

    def _build_session_context(self, phase_fact: PhaseFact) -> SessionContext:
        """Fold this tick's ``PhaseFact`` into a kernel ``tos.time.SessionContext``.

        ``tz_version_conflict`` is a strict ``bool`` on the kernel record (no
        third "unknown" state exists to express in that field) — this owner
        can only assert a conflict when BOTH ``time.yaml``'s declared
        ``tz_db_version`` and an independently-observed tzdata version are
        known and disagree. When either is unknown (the common case today —
        no ``tz_db_version_observed`` source exists, W5 survey §3), this
        reports ``False``: a documented limitation ("cannot detect a
        conflict"), never a claim that the two values were verified to
        match.
        """
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

    def _record_session_open_expectation(self, session_context: SessionContext) -> None:
        """Record ``SESSION_OPEN_EXPECTATION`` (plan §2 decision 3 (b)).

        ``session_open_positively`` (:mod:`tos.time.predicates`) is
        deliberately NEVER called here: it needs a real
        ``UncertaintyInterval`` from the reference time frame, and
        ``TrustworthyTimeService`` exposes none today (W5 survey §3 — no
        ``current_snapshot()`` field or public accessor carries one). Rather
        than fabricate an interval to force a call, this records the
        observation as explicitly UNEVALUATED — non-authoritative, consumed
        by nothing (``tests/compose/test_session_wiring.py`` pins a
        zero-consumer negative-grep).
        """
        self._evidence_store.append(
            {
                "evaluated": False,
                "reason": (
                    "no UncertaintyInterval source is exposed by "
                    "TrustworthyTimeService today (W5 survey §3) -- "
                    "session_open_positively is never called with a "
                    "fabricated interval"
                ),
                "phase": session_context.phase,
                "is_open": session_context.is_open,
            },
            kind=SESSION_OPEN_EXPECTATION_KIND,
            record_class=SESSION_OPEN_EXPECTATION_KIND,
        )

    def _maybe_record_observed(
        self, instrument_class: str, facts: SessionFacts
    ) -> None:
        """Record ``SESSION_FACTS_OBSERVED`` only when the phase token or the
        maturity ``expired`` state actually changed since the last observed
        generation for this instrument class (plan §2 decision 10 — never
        every tick)."""
        new_phase = facts.phase_fact.phase
        new_expired = facts.maturity_fact.expired
        prev_phase = self._last_phase.get(instrument_class, _NEVER_OBSERVED)
        prev_expired = self._last_expired.get(instrument_class, _NEVER_OBSERVED)
        changed = prev_phase != new_phase or prev_expired != new_expired
        if changed:
            self._evidence_store.append(
                {
                    "instrument_class": instrument_class,
                    "phase": new_phase,
                    "expired": new_expired,
                    "tick_generation": facts.tick_generation,
                },
                kind=SESSION_FACTS_OBSERVED_KIND,
                record_class=SESSION_FACTS_OBSERVED_KIND,
            )
        self._last_phase[instrument_class] = new_phase
        self._last_expired[instrument_class] = new_expired
