"""``TickScheduler`` — the tick source (TOS tick-source wave, plan
``docs/plans/2026-09-16-tos-tick-source-plan.md`` §2 decisions 1/5/6/7/8/9, lane D).

Composes every other module in this package into one loop: poll the injected
:class:`~tos_runtime.marketfeed.ports.ObservationIntake` -> take this pass's wall-clock reading
through the injected ``before_decide`` hook -> gate on the session -> issue a
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

**Read order: the intake FIRST, the wall-clock reading SECOND** (plan
``docs/plans/2026-09-27-tos-freshness-read-order-plan.md`` §2.1, operator disposition §6.1;
issue #809). :meth:`~tos_runtime.time.service.TrustworthyTimeService.wall_clock_now` returns the
reading the LAST ``evaluate()`` cached (``time/service.py:697-711``), so a pass that evaluated
BEFORE reading the journal judged every line appended in between against a reading older than the
line's own ``as_of`` — ``source_age`` went negative, and past
``MAX_future_timestamp_tolerance_ms`` (50) the kernel answered ``CONFLICTED``
(``tos/src/tos/time/predicates.py`` ``freshness_verdict``) for an observation that was simply
*newer than the reading*. Measured: 1 of 35 appended observations in the 2026-09-27 rehearsal.
Reading the journal first and evaluating after makes ``as_of <= R < S'`` for any sane collector,
so ``source_age >= 0`` and ``CONFLICTED`` is left to mean what it should — a collector clock
genuinely ahead by more than the tolerance. The kernel's future-dating defence is neither widened
nor narrowed, and the evaluation count stays exactly one per pass.

**``tick_once`` still never evaluates time itself.** It calls the constructor-injected
``before_decide`` hook (compose passes :meth:`~tos_runtime.marketfeed.time_pacer
.TimeEvaluationPacer.before_decide`) between the poll and the decision, and
:meth:`TickScheduler.run_forever` calls nothing but :meth:`TickScheduler.tick_once` and ``sleep``.
A ``False`` answer — the evaluation was due and failed — returns
:attr:`~tos_runtime.marketfeed.ports.TickOutcome.SKIPPED_TIME_NOT_EVALUATED` **without** a
``store.put``, so the polled observation is not consumed. ⚠ Not consuming is the whole of what
this module can do — whether the next pass actually SEES that observation again is the INTAKE's
property, not this one's. It holds for an intake whose ``poll`` is a pure function of
``after_as_of_ms`` (the port's own contract, and what
:class:`~tos_runtime.marketfeed.journal.JsonLinesObservationJournal` does), and it also holds for
``transport.kis_quote.adapter.KisQuoteObservationIntake``, which dedups on a content digest it
holds PENDING until ``after_as_of_ms`` advances — the signal that the previous pass's observation
was durably consumed (``ports.py``'s own ``SKIPPED_TIME_NOT_EVALUATED`` docstring).

**The request anchor: a pending observation is stamped HERE, after the hook** (plan
``docs/plans/2026-09-28-tos-kis-quote-request-anchor-plan.md`` §2.3; issue #810). A pull intake
with no source event time of its own returns
:class:`~tos_runtime.marketfeed.ports.MonotonicAnchoredObservation` — the monotonic instants its
fetch spanned — and :meth:`TickScheduler._anchor_polled` maps them onto THIS pass's freshly
evaluated reading through :meth:`~tos_runtime.time.service.TrustworthyTimeService
.wall_clock_at_monotonic`, so ``as_of`` is the instant the REQUEST went out and ``source_age``
carries the round trip instead of the pass spacing. When either mapping is unavailable (time not
``TRUSTED``, or the instants fall outside the cycle that evaluation covers) the pass answers
:attr:`~tos_runtime.marketfeed.ports.TickOutcome.SKIPPED_TIME_UNANCHORED` — again without a
``store.put``, and again without stopping the loop. A ``RawObservation`` is never re-anchored:
its collector measured a real event time and this module does not overwrite measurements.

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
that enum has no "queued, driver absent" member. Rather than editing a landed contract to add one,
or silently reusing ``SKIPPED_*`` (which would misreport — a tick genuinely WAS produced and
durably queued, nothing was skipped), :meth:`TickScheduler.tick_once` returns the ADDITIVE
:class:`TickResult`
wrapper (this module's own type, not a `ports.py`` edit) — ``outcome=TickOutcome.TICKED`` with
``queued_until_recovery=True``, an honest "yes, but not yet run" the plain enum cannot express.
(#809 DID add one member to that enum,
:attr:`~tos_runtime.marketfeed.ports.TickOutcome.SKIPPED_TIME_NOT_EVALUATED`, under the operator's
own disposition — and the two cases are not the same shape: that one names a pass that produced
**no** tick, which is exactly what this vocabulary is for, whereas "queued, driver absent" is a
tick that WAS produced and therefore belongs on the richer result, as this enum's own docstring
already says.)

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
    MonotonicAnchoredObservation,
    ObservationIntake,
    RawObservation,
    TickOutcome,
    anchor_observation,
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
        before_decide: Callable[[], bool] | None = None,
    ) -> None:
        """Wire the scheduler (every arg's own docstring lives on the field it fills below —
        ``instruments``/``instrument_class``/``account``/``direction``/``quantity_basis``/
        ``unit``/``poll_interval_ms`` are this scheduler's own scope; ``policy``/``scheme``/
        ``intake``/``store``/``time_projection`` are the injected collaborators the class
        docstring already names; ``time_service``/``session_owner``/``driver``/``inbox``/
        ``evidence_store`` are THIS PROCESS's shared instances, never a second independently-run
        one (mirrors every other compose wiring module's "SAME source" discipline)).

        ``before_decide`` runs INSIDE every :meth:`tick_once` pass — after the intake read and
        before this pass's wall-clock reading is taken (module docstring's own read-order
        paragraph, plan 2026-09-27 §2.1 / issue #809) — and the pass decides only when it returns
        ``True``. Compose passes :meth:`~tos_runtime.marketfeed.time_pacer
        .TimeEvaluationPacer.before_decide` so the wall-clock reading advances once per pass, on
        the intake-read side of the poll (plan 2026-09-26 periodic time eval, W1); ``None`` leaves
        the time service to the caller. :meth:`tick_once` still evaluates nothing itself — it only
        calls this hook.

        Raises:
            MultiInstrumentRefused: ``instruments`` does not name exactly one instrument.
        """
        self._before_decide = before_decide
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

    def _anchor_polled(
        self, polled: Sequence[RawObservation | MonotonicAnchoredObservation]
    ) -> tuple[RawObservation, ...] | None:
        """Finalize every :class:`~tos_runtime.marketfeed.ports.MonotonicAnchoredObservation`
        in ``polled`` against the reading THIS pass's evaluation just produced (module
        docstring's own request-anchor paragraph; plan 2026-09-28 §2.3).

        A :class:`~tos_runtime.marketfeed.ports.RawObservation` passes through untouched — the
        journal's collector already stamped an honest source event time, and re-anchoring it
        here would overwrite a measurement with a guess.

        Returns:
            The finalized batch, or ``None`` when ANY pending observation cannot be mapped —
            the whole pass is then :attr:`~tos_runtime.marketfeed.ports.TickOutcome
            .SKIPPED_TIME_UNANCHORED`. All-or-nothing on purpose: a batch silently reduced to
            its mappable members would let ``decide_tick`` pick a "newest" that is merely the
            newest of the survivors.
        """
        finalized: list[RawObservation] = []
        for observation in polled:
            if isinstance(observation, RawObservation):
                finalized.append(observation)
                continue
            as_of_ms = self._time_service.wall_clock_at_monotonic(
                observation.requested_monotonic_ms
            )
            received_ms = self._time_service.wall_clock_at_monotonic(
                observation.received_monotonic_ms
            )
            if as_of_ms is None or received_ms is None:
                return None
            finalized.append(
                anchor_observation(
                    observation, as_of_ms=as_of_ms, received_ms=received_ms
                )
            )
        return tuple(finalized)

    def tick_once(self) -> TickResult:
        """Run exactly one scheduler pass — intake read FIRST, wall-clock reading SECOND (module
        docstring's own read-order paragraph; plan 2026-09-27 §2.1, issue #809).

        Returns:
            The :class:`TickResult`. ``SKIPPED_TIME_NOT_EVALUATED`` when ``before_decide``
            answered ``False``, and ``SKIPPED_TIME_UNANCHORED`` when it answered ``True`` but a
            polled :class:`~tos_runtime.marketfeed.ports.MonotonicAnchoredObservation` could not
            be placed on the resulting reading: no ``store.put`` happens on either path, so
            whatever was polled stays unconsumed. Whether the next pass then SEES it again is
            the intake's own property (module docstring).
        """
        latest_as_of_ms = self._store.latest_as_of(instrument=self._instrument)
        polled = self._intake.poll(
            instrument=self._instrument, after_as_of_ms=latest_as_of_ms
        )
        if self._before_decide is not None and not self._before_decide():
            return TickResult(outcome=TickOutcome.SKIPPED_TIME_NOT_EVALUATED)
        observations = self._anchor_polled(polled)
        if observations is None:
            return TickResult(outcome=TickOutcome.SKIPPED_TIME_UNANCHORED)
        now_ms = self._time_service.wall_clock_now()
        session_context = self._session_owner.session_context(self._instrument_class)
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

        This loop calls nothing but :meth:`tick_once` and ``sleep``: the constructor's
        ``before_decide`` hook now runs INSIDE the pass, between the intake read and the decision
        (module docstring's own read-order paragraph; plan 2026-09-27 §2.1, issue #809), so a
        pass whose time evaluation failed is a :class:`TickResult` with
        ``SKIPPED_TIME_NOT_EVALUATED``, not a pass this loop skipped.
        """
        while not stop():
            self.tick_once()
            sleep(self._poll_interval_ms / 1000)
