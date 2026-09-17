"""``TickScheduler`` — the tick source (TOS tick-source wave, plan
``docs/plans/2026-09-16-tos-tick-source-plan.md`` §2 decisions 1/5/6/7/8/9, lane D).

Composes every other module in this package into one loop: poll the injected
:class:`~tos_runtime.marketfeed.ports.ObservationIntake` -> gate on the session -> issue a
:class:`~tos.capsule.CriticalInputSnapshot` (lane A) -> durably record it (lane B) -> issue a
:class:`~tos.capsule.DecisionContextCapsule` (lane A) -> resolve through the REAL kernel
:class:`~tos.marketfeed.MarketFeedContextResolver` (injected with the durable store and the lane C
:class:`~tos_runtime.marketfeed.time_projection.RuntimeTimeProjection`) -> hand the resulting
``DECISION_TICK`` to :class:`~tos_runtime.engine.driver.EngineDriver`.

**Split: a pure decision function plus a thin loop (plan §2 decision 7).** :func:`decide_tick`
receives only already-fetched, already-injected values (a session context, a batch of polled
observations, the store's own ``latest_as_of``, a wall-clock reading, the last tick's own
wall-clock reading, and the configured poll interval) and returns a :class:`TickDecision` — no
I/O, no clock read, no randomness. Every test in the paired test module drives this function
directly, or :meth:`TickScheduler.tick_once` (which performs the I/O and then calls it).
:meth:`TickScheduler.run_forever` is the ONLY place ``time.sleep`` is called — mirrors the
``time.sleep`` precedent already shipped at ``transport/kis_mock/adapter.py:480`` (module
docstring's own firewall note).

**Per-observation distinctness is checked here too, independently of the journal's own filter**
(plan §2 decision 5; ``ports.py``'s ``DurableSnapshotStore.latest_as_of`` docstring). A collector
could hand a raw observation to ANY :class:`~tos_runtime.marketfeed.ports.ObservationIntake`
implementation, not only :class:`~tos_runtime.marketfeed.journal.JsonLinesObservationJournal` (which
already filters ``after_as_of_ms``) — so :func:`decide_tick` re-derives ``SKIPPED_NOT_NEWER`` from
the polled batch and the store's own durable ``latest_as_of``, rather than trusting the intake to
have filtered correctly. A distinct as-of is what makes a distinct snapshot digest (design #32 §4.1)
— this is the CIS's own obligation, not the publication gate's (``tos/tests/marketfeed
/test_marketfeed_cis_port.py:46-49``).

**``reference`` is never claimed** (plan §2 decision 8). This module calls
``self._resolver(capsule, instrument_key=...)`` — :meth:`~tos.marketfeed.MarketFeedContextResolver
.__call__`, whose own docstring already leaves ``reference`` at the engine's ``OrderingEvent()``
default — and hands the resulting :class:`~tos.engine.EngineEvent` to
:meth:`~tos_runtime.engine.driver.EngineDriver.enqueue_and_run`, whose ``_stamp`` discards
whatever ``reference`` a caller supplied and re-stamps from its own yield-order counter
(``engine/driver.py:397``). Nothing in this module ever constructs an ``OrderingEvent`` itself.

**Single instrument only** (plan §2 decision 8; ``ports.py``'s ``TickOutcome`` docstring). A live
multi-symbol event source would owe the engine core the same single-continuity ingest order its
backtest counterpart provides (:class:`~tos.backtest.driver.YieldOrderCounter`), and that
obligation — FORWARD-OBLIGATION-MS1 — is recorded as *new and unratified*
(``tos/src/tos/backtest/driver.py:78-86``). :class:`TickScheduler` therefore takes ``instruments``
as a ``Sequence[str]`` (the shape a config file naturally produces) and REFUSES at construction,
citing that obligation, when it does not name exactly one.

**Held runtime (recovery barrier HOLD) — mirrors ``ComposedRuntime.observe_nontrade``'s own shape,
does not invent a second one** (module docstring's own "no code path left that could touch
capacity" discipline, ``_recovery_wiring.py``). When ``driver is None`` (the TOS Phase 5 W1
recovery barrier did not resolve to ``READY`` — ``ComposedRuntime.driver``'s own docstring), this
module never pretends the tick was processed: it enqueues the UNSTAMPED event directly onto the
durable inbox (to be picked up once a driver eventually exists — the SAME "inbox, not a phantom
process" idiom :meth:`~tos_runtime.compose._types.ComposedRuntime.observe_nontrade` already uses
for its own held-runtime branch) and appends an evidence row naming what was queued. **Deviation
from the committed ``ports.py`` ``TickOutcome`` vocabulary, reported rather than patched around**:
that six-member enum (a contract landed before this module and not owned by this lane) has no
"queued, driver absent" member. Rather than editing a landed contract to add one, or silently
reusing ``SKIPPED_*`` (which would misreport — a tick genuinely WAS produced and durably queued,
nothing was skipped), :meth:`TickScheduler.tick_once` returns the ADDITIVE :class:`TickResult`
wrapper (this module's own type, not a `ports.py`` edit) — ``outcome=TickOutcome.TICKED`` with
``queued_until_recovery=True``, an honest "yes, but not yet run" the plain enum cannot express.

**Every declared field going ``UNKNOWN`` is still a tick, never ``REFUSED_POLICY``.** This wave's
scheduler never produces :attr:`~tos_runtime.marketfeed.ports.TickOutcome.REFUSED_POLICY` — a
payload whose fields are all stale/absent under the governed policy still publishes an
explicit-empty (or partially-empty) value view (plan §5 exit criterion 3/4), which is a real,
recorded ``TICKED`` tick, not a refusal. The member is left in ``ports.py`` for a future producer
that might refuse a whole observation outright (e.g. an intake-level trust failure this wave does
not have); this scheduler simply never reaches it.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``time``) + ``tos.*`` +
``tos_runtime.*`` only. No ``shared.*``, no network. The one clock read anywhere in this module's
call graph is :meth:`~tos_runtime.time.service.TrustworthyTimeService.wall_clock_now`, treated as
an opaque injected reading (mirrors :mod:`~tos_runtime.marketfeed.time_projection`'s own note).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from tos.canonical import CanonicalizationScheme
from tos.capsule import PolicyRef
from tos.dsl import ContextValueView
from tos.engine import EngineEvent, EventKind, InstrumentKey
from tos.marketfeed import MarketFeedContextResolver
from tos.time import SessionContext

from tos_runtime.calendar.owner import SessionFactsOwner
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.marketfeed.capsule import CapsuleIssuer
from tos_runtime.marketfeed.policy import LoadedCriticalInputPolicy
from tos_runtime.marketfeed.ports import (
    DurableSnapshotStore,
    ObservationIntake,
    RawObservation,
    TickOutcome,
)
from tos_runtime.marketfeed.snapshot import SnapshotIssuer
from tos_runtime.marketfeed.time_projection import RuntimeTimeProjection
from tos_runtime.time.service import TrustworthyTimeService

__all__ = [
    "MultiInstrumentRefused",
    "TickDecision",
    "TickResult",
    "TickScheduler",
    "decide_tick",
]


class MultiInstrumentRefused(RuntimeError):
    """Raised by :meth:`TickScheduler.__init__` when ``instruments`` does not name exactly one
    instrument (module docstring — FORWARD-OBLIGATION-MS1 is unratified for a live multi-symbol
    source)."""


@dataclass(frozen=True)
class TickDecision:
    """One pure verdict from :func:`decide_tick`.

    Attributes:
        outcome: Why this pass did or did not tick.
        observation: The observation to issue a snapshot for — concrete iff
            ``outcome is TickOutcome.TICKED``, ``None`` otherwise.
    """

    outcome: TickOutcome
    observation: RawObservation | None = None


def decide_tick(
    *,
    session_context: SessionContext | None,
    observations: Sequence[RawObservation],
    latest_as_of_ms: int | None,
    now_ms: int | None,
    last_tick_wall_clock_ms: int | None,
    poll_interval_ms: int,
) -> TickDecision:
    """The pure decision (plan §2 decision 7): does the session admit a tick, is there a new
    observation, is it newer than what is already durably issued, and has the poll interval
    elapsed — in that order, each a DIFFERENT named absence when it fails.

    Args:
        session_context: This tick's session facts (``SessionFactsOwner.session_context(...)``),
            or ``None`` when no wall-clock reading was available to derive one.
        observations: The batch :meth:`~tos_runtime.marketfeed.ports.ObservationIntake.poll`
            returned, oldest-first (may be empty).
        latest_as_of_ms: The store's own newest already-issued as-of for this instrument, or
            ``None`` if none has been issued yet.
        now_ms: The current wall-clock reading, or ``None`` when unavailable.
        last_tick_wall_clock_ms: The wall-clock reading at the last ``TICKED`` pass, or ``None``
            before the first tick.
        poll_interval_ms: The configured minimum spacing between ticks.

    Returns:
        The :class:`TickDecision`.
    """
    if session_context is None or not session_context.is_open:
        return TickDecision(outcome=TickOutcome.SKIPPED_SESSION_CLOSED)
    if not observations:
        return TickDecision(outcome=TickOutcome.SKIPPED_NO_OBSERVATION)
    newest = max(observations, key=lambda observation: observation.as_of_ms)
    if latest_as_of_ms is not None and newest.as_of_ms <= latest_as_of_ms:
        # The CIS's own distinctness obligation (module docstring) — independent of whatever
        # filtering the intake itself already did.
        return TickDecision(outcome=TickOutcome.SKIPPED_NOT_NEWER)
    if (
        now_ms is not None
        and last_tick_wall_clock_ms is not None
        and now_ms - last_tick_wall_clock_ms < poll_interval_ms
    ):
        return TickDecision(outcome=TickOutcome.SKIPPED_INTERVAL)
    return TickDecision(outcome=TickOutcome.TICKED, observation=newest)


@dataclass(frozen=True)
class TickResult:
    """One :meth:`TickScheduler.tick_once` outcome (module docstring's own "held runtime"
    deviation note — additive over the plain :class:`~tos_runtime.marketfeed.ports.TickOutcome`,
    never a replacement for it).

    Attributes:
        outcome: The :class:`~tos_runtime.marketfeed.ports.TickOutcome`.
        queued_until_recovery: ``True`` iff a tick WAS produced (``outcome is TICKED``) but the
            recovery barrier held (``driver is None``), so it was durably enqueued rather than
            run. Always ``False`` for every non-``TICKED`` outcome.
        value_view: The resolved :class:`~tos.dsl.ContextValueView` the REAL kernel resolver
            published for this tick — the SAME object handed to the engine, exposed here so a
            caller (a test, an operator dashboard) can inspect what a tick actually admitted
            without re-resolving it. ``None`` for every non-``TICKED`` outcome (mirrors
            :attr:`~tos.engine.records.DecisionTickPayload.value_view`'s own "absent, not
            fabricated" discipline — an explicit-empty view is still a concrete, non-``None``
            :class:`~tos.dsl.ContextValueView` with ``values == ()``).
    """

    outcome: TickOutcome
    queued_until_recovery: bool = False
    value_view: ContextValueView | None = None


#: The evidence kind for a tick queued while the recovery barrier holds (module docstring —
#: mirrors ``ComposedRuntime._NONTRADE_QUEUED_UNTIL_RECOVERY_KIND``'s own naming convention).
_MARKETFEED_QUEUED_UNTIL_RECOVERY_KIND = "MARKETFEED_QUEUED_UNTIL_RECOVERY"


def _require_single_instrument(instruments: Sequence[str]) -> str:
    """The one instrument ``instruments`` must name (module docstring; :class:`TickScheduler`'s
    own single-instrument-scope discipline, split out purely for its ``__init__``'s 100-line
    function budget — no behaviour difference from inlining it there).

    Raises:
        MultiInstrumentRefused: ``instruments`` does not name exactly one instrument.
    """
    if len(instruments) != 1:
        raise MultiInstrumentRefused(
            "TickScheduler is single-instrument-scoped (plan §2 decision 8) — instruments must "
            f"name exactly one, got {tuple(instruments)!r}. A live multi-symbol event source "
            "would owe the engine core the same single-continuity ingest order its backtest "
            "counterpart provides, and that obligation (FORWARD-OBLIGATION-MS1, "
            "tos/src/tos/backtest/driver.py:78-86) is unratified."
        )
    return instruments[0]


def _build_issuers(
    *,
    instrument: str,
    account: str,
    direction: str,
    quantity_basis: str,
    unit: str,
    policy: LoadedCriticalInputPolicy,
    scheme: CanonicalizationScheme,
    store: DurableSnapshotStore,
    time_projection: RuntimeTimeProjection,
) -> tuple[SnapshotIssuer, CapsuleIssuer, MarketFeedContextResolver]:
    """Build :class:`TickScheduler`'s three issuance collaborators (split out of ``__init__``
    purely for its 100-line function budget — no behaviour difference from inlining it there).

    ``environment``/``decision_class``/``issuer_principal_id`` are read from ``policy``, never
    re-typed here (구조 파생 > 자기신고 — the same discipline ``snapshot.py``/``capsule.py`` already
    apply). The resolver's ``candidate_source`` is ``store.candidates`` — the BOUND METHOD, never
    the store object itself (``ports.py``'s ``DurableSnapshotStore`` docstring's own trap: passing
    the object there passes every construction-time check and then raises ``TypeError`` at the
    first resolve).
    """
    snapshot_issuer = SnapshotIssuer(policy=policy, scheme=scheme, account=account)
    capsule_issuer = CapsuleIssuer(
        account=account,
        instrument=instrument,
        environment=policy.environment,
        decision_class=policy.decision_class,
        direction=direction,
        quantity_basis=quantity_basis,
        unit=unit,
        issuer_principal_id=policy.issuer_principal_id,
        critical_input_policy=PolicyRef(
            policy_id=policy.policy_id,
            policy_generation=policy.policy_generation,
            canonical_digest=policy.canonical_digest,
        ),
        scheme=scheme,
    )
    resolver = MarketFeedContextResolver(
        snapshot_store=store,
        candidate_source=store.candidates,
        scheme=scheme,
        time_projection=time_projection,
    )
    return snapshot_issuer, capsule_issuer, resolver


class TickScheduler:
    """The tick source (module docstring). One fixed (account, instrument) pair per instance."""

    def __init__(
        self,
        *,
        instruments: Sequence[str],
        instrument_class: str,
        account: str,
        direction: str,
        quantity_basis: str,
        unit: str,
        policy: LoadedCriticalInputPolicy,
        scheme: CanonicalizationScheme,
        intake: ObservationIntake,
        store: DurableSnapshotStore,
        time_projection: RuntimeTimeProjection,
        time_service: TrustworthyTimeService,
        session_owner: SessionFactsOwner,
        driver: EngineDriver | None,
        inbox: SqliteEventInbox,
        evidence_store: SqliteEvidenceStore,
        poll_interval_ms: int,
    ) -> None:
        """Wire the scheduler (every arg's own docstring lives on the field it fills below —
        ``instruments``/``instrument_class``/``account``/``direction``/``quantity_basis``/
        ``unit``/``poll_interval_ms`` are this scheduler's own scope; ``policy``/``scheme``/
        ``intake``/``store``/``time_projection`` are the injected collaborators the class
        docstring already names; ``time_service``/``session_owner``/``driver``/``inbox``/
        ``evidence_store`` are THIS PROCESS's shared instances, never a second independently-run
        one (mirrors every other compose wiring module's "SAME source" discipline)).

        Raises:
            MultiInstrumentRefused: ``instruments`` does not name exactly one instrument.
        """
        self._instrument = _require_single_instrument(instruments)
        self._instrument_class = instrument_class
        self._account = account
        self._intake = intake
        self._store = store
        self._session_owner = session_owner
        self._driver = driver
        self._inbox = inbox
        self._evidence_store = evidence_store
        self._poll_interval_ms = poll_interval_ms
        self._time_service = time_service
        self._last_tick_wall_clock_ms: int | None = None
        self._instrument_key = InstrumentKey(
            account=account, instrument=self._instrument
        )
        self._snapshot_issuer, self._capsule_issuer, self._resolver = _build_issuers(
            instrument=self._instrument,
            account=account,
            direction=direction,
            quantity_basis=quantity_basis,
            unit=unit,
            policy=policy,
            scheme=scheme,
            store=store,
            time_projection=time_projection,
        )

    def tick_once(self) -> TickResult:
        """Run exactly one scheduler pass (module docstring).

        Returns:
            The :class:`TickResult`.
        """
        now_ms = self._time_service.wall_clock_now()
        session_context = self._session_owner.session_context(self._instrument_class)
        latest_as_of_ms = self._store.latest_as_of(instrument=self._instrument)
        observations = self._intake.poll(
            instrument=self._instrument, after_as_of_ms=latest_as_of_ms
        )
        decision = decide_tick(
            session_context=session_context,
            observations=observations,
            latest_as_of_ms=latest_as_of_ms,
            now_ms=now_ms,
            last_tick_wall_clock_ms=self._last_tick_wall_clock_ms,
            poll_interval_ms=self._poll_interval_ms,
        )
        if decision.outcome is not TickOutcome.TICKED:
            return TickResult(outcome=decision.outcome)
        observation = decision.observation
        assert observation is not None  # decide_tick's own TICKED contract

        issued = self._snapshot_issuer.issue(observation, now_ms=now_ms)
        self._store.put(issued.snapshot, issued.preimages)
        capsule = self._capsule_issuer.issue(issued.snapshot)
        payload = self._resolver(capsule, instrument_key=self._instrument_key)
        event = EngineEvent(kind=EventKind.DECISION_TICK, decision_tick=payload)

        queued_until_recovery = self._driver is None
        if self._driver is not None:
            self._driver.enqueue_and_run(event)
        else:
            # Held runtime (module docstring) — mirrors
            # ComposedRuntime.observe_nontrade's own "enqueue + evidence row, never pretend it
            # was processed" branch, never a second convention.
            self._inbox.enqueue(event)
            self._evidence_store.append(
                {"instrument": self._instrument, "as_of_ms": observation.as_of_ms},
                kind=_MARKETFEED_QUEUED_UNTIL_RECOVERY_KIND,
                record_class=_MARKETFEED_QUEUED_UNTIL_RECOVERY_KIND,
            )
        self._last_tick_wall_clock_ms = now_ms
        return TickResult(
            outcome=TickOutcome.TICKED,
            queued_until_recovery=queued_until_recovery,
            value_view=payload.value_view,
        )

    def run_forever(
        self,
        *,
        sleep: Callable[[float], None] = time.sleep,
        stop: Callable[[], bool] = lambda: False,
    ) -> None:
        """The thin loop — the ONLY place this module calls ``time.sleep`` (module docstring).

        Args:
            sleep: Injected sleep callable (seconds) — a test supplies a fake to run this
                loop without a real wall-clock wait.
            stop: Injected stop predicate, checked before every pass — a test supplies one that
                flips ``True`` after N calls so this loop terminates.
        """
        while not stop():
            self.tick_once()
            sleep(self._poll_interval_ms / 1000)
