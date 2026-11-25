"""``TickScheduler`` — the tick source (TOS tick-source wave, plan"""

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
from tos_runtime.marketfeed.snapshot import IssuedSnapshot, SnapshotIssuer
from tos_runtime.marketfeed.time_projection import RuntimeTimeProjection
from tos_runtime.time.service import TrustworthyTimeService
from tos_runtime.time.sources import MonotonicSource

__all__ = [
    "MultiInstrumentRefused",
    "PassBudget",
    "TickDecision",
    "TickResult",
    "TickScheduler",
    "decide_tick",
]


@dataclass(frozen=True)
class PassBudget:
    """What one :meth:`TickScheduler.run_forever` pass is allowed to cost, and the clock that"""

    monotonic: MonotonicSource
    allowance_ms: int


class MultiInstrumentRefused(RuntimeError):
    """Raised by :meth:`TickScheduler.__init__` when ``instruments`` does not name exactly one"""


@dataclass(frozen=True)
class TickDecision:
    """One pure verdict from :func:`decide_tick`."""

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
    """The pure decision (plan §2 decision 7): does the session admit a tick, is there a new"""
    if session_context is None or not session_context.is_open:
        return TickDecision(outcome=TickOutcome.SKIPPED_SESSION_CLOSED)
    if not observations:
        return TickDecision(outcome=TickOutcome.SKIPPED_NO_OBSERVATION)
    newest = max(observations, key=lambda observation: observation.as_of_ms)
    if latest_as_of_ms is not None and newest.as_of_ms <= latest_as_of_ms:
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
    'One :meth:`TickScheduler.tick_once` outcome (module docstring\'s own "held runtime"'

    outcome: TickOutcome
    queued_until_recovery: bool = False
    value_view: ContextValueView | None = None


_MARKETFEED_QUEUED_UNTIL_RECOVERY_KIND = "MARKETFEED_QUEUED_UNTIL_RECOVERY"

_MARKETFEED_FIELD_REFUSED_KIND = "MARKETFEED_FIELD_REFUSED"

_MARKETFEED_PASS_OVERRUN_KIND = "MARKETFEED_PASS_OVERRUN"


def _require_single_instrument(instruments: Sequence[str]) -> str:
    """The one instrument ``instruments`` must name (module docstring; :class:`TickScheduler`'s"""
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
    """Build :class:`TickScheduler`'s three issuance collaborators (split out of ``__init__``"""
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
        after_pass: Callable[[], None] | None = None,
        pass_budget: PassBudget | None = None,
    ) -> None:
        """Wire the scheduler (every arg's own docstring lives on the field it fills below —"""
        self._before_decide = before_decide
        self._after_pass = after_pass
        self._pass_budget = pass_budget
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
        """Finalize every :class:`~tos_runtime.marketfeed.ports.MonotonicAnchoredObservation`"""
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
        """Run exactly one scheduler pass — intake read FIRST, wall-clock reading SECOND (module"""
        latest_as_of_ms = self._store.latest_as_of(instrument=self._instrument)
        polled = self._intake.poll(
            instrument=self._instrument, after_as_of_ms=latest_as_of_ms
        )
        if self._before_decide is not None and not self._before_decide():
            return TickResult(outcome=TickOutcome.SKIPPED_TIME_NOT_EVALUATED)
        now_ms = self._time_service.wall_clock_now()
        session_context = self._session_owner.session_context(self._instrument_class)
        if session_context is None or not session_context.is_open:
            return TickResult(outcome=TickOutcome.SKIPPED_SESSION_CLOSED)
        observations = self._anchor_polled(polled)
        if observations is None:
            return TickResult(outcome=TickOutcome.SKIPPED_TIME_UNANCHORED)
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
        assert observation is not None

        issued = self._snapshot_issuer.issue(observation, now_ms=now_ms)
        self._store.put(issued.snapshot, issued.preimages)
        capsule = self._capsule_issuer.issue(issued.snapshot)
        payload = self._resolver(capsule, instrument_key=self._instrument_key)
        event = EngineEvent(kind=EventKind.DECISION_TICK, decision_tick=payload)

        queued_until_recovery = self._driver is None
        if self._driver is not None:
            self._driver.enqueue_and_run(event)
        else:
            self._inbox.enqueue(event)
            self._evidence_store.append(
                {"instrument": self._instrument, "as_of_ms": observation.as_of_ms},
                kind=_MARKETFEED_QUEUED_UNTIL_RECOVERY_KIND,
                record_class=_MARKETFEED_QUEUED_UNTIL_RECOVERY_KIND,
            )
        self._record_field_refusals(issued, observation, now_ms=now_ms)
        self._last_tick_wall_clock_ms = now_ms
        return TickResult(
            outcome=TickOutcome.TICKED,
            queued_until_recovery=queued_until_recovery,
            value_view=payload.value_view,
        )

    def _record_field_refusals(
        self,
        issued: IssuedSnapshot,
        observation: RawObservation,
        *,
        now_ms: int | None,
    ) -> None:
        """Record WHY an issued snapshot refused fields, when it refused any."""
        refused = [
            report for report in issued.field_reports if report.reason is not None
        ]
        if not refused:
            return
        by_reason: dict[str, list[str]] = {}
        for report in refused:
            by_reason.setdefault(report.reason or "", []).append(report.field_key)
        stale_bounds = sorted(
            {report.max_age_ms for report in refused if report.reason == "stale"}
        )
        self._evidence_store.append(
            {
                "instrument": self._instrument,
                "raw_event_id": observation.raw_event_id,
                "as_of_ms": observation.as_of_ms,
                "evaluated_at_ms": now_ms,
                "age_ms": None if now_ms is None else now_ms - observation.as_of_ms,
                "stale_max_age_ms": stale_bounds,
                "fields_declared": len(issued.field_reports),
                "fields_refused": len(refused),
                "refused_by_reason": {
                    reason: sorted(keys) for reason, keys in sorted(by_reason.items())
                },
            },
            kind=_MARKETFEED_FIELD_REFUSED_KIND,
            record_class=_MARKETFEED_FIELD_REFUSED_KIND,
        )

    def run_forever(
        self,
        *,
        sleep: Callable[[float], None] = time.sleep,
        stop: Callable[[], bool] = lambda: False,
    ) -> None:
        """The thin loop — the ONLY place this module calls ``time.sleep`` (module docstring)."""
        budget = self._pass_budget
        while not stop():
            started_ms = None if budget is None else budget.monotonic.now_ms()
            self.tick_once()
            ticked_ms = None if budget is None else budget.monotonic.now_ms()
            if self._after_pass is not None:
                self._after_pass()
            done_ms = None if budget is None else budget.monotonic.now_ms()
            self._record_pass_overrun(started_ms, ticked_ms, done_ms)
            sleep(self._pass_sleep_seconds(started_ms, done_ms))

    def _pass_sleep_seconds(self, started_ms: int | None, done_ms: int | None) -> float:
        """How long to sleep after a pass: the configured interval MINUS what the pass itself"""
        if started_ms is None or done_ms is None:
            return self._poll_interval_ms / 1000
        remaining_ms = self._poll_interval_ms - (done_ms - started_ms)
        return max(0.0, remaining_ms / 1000)

    def _record_pass_overrun(
        self, started_ms: int | None, ticked_ms: int | None, done_ms: int | None
    ) -> None:
        """Record a pass that ran longer than the whole window the freshness guard reserves —"""
        budget = self._pass_budget
        if budget is None or started_ms is None or ticked_ms is None or done_ms is None:
            return
        pass_ms = done_ms - started_ms
        budget_ms = self._poll_interval_ms + budget.allowance_ms
        if pass_ms <= budget_ms:
            return
        self._evidence_store.append(
            {
                "instrument": self._instrument,
                "budget_ms": budget_ms,
                "pass_ms": pass_ms,
                "tick_ms": ticked_ms - started_ms,
                "after_pass_ms": done_ms - ticked_ms,
                "poll_interval_ms": self._poll_interval_ms,
                "pass_allowance_ms": budget.allowance_ms,
            },
            kind=_MARKETFEED_PASS_OVERRUN_KIND,
            record_class=_MARKETFEED_PASS_OVERRUN_KIND,
        )
