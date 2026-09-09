"""Shared builders for the backtest=paper parity + blind-resubmit suite (TOS Phase 3 Wave 3
Lane F-R; plan §3.2 bullets 2-3, §5).

**Not a copy of ``tos/runtime/tests/compose/_fixtures.py`` and does not import it** — the same
per-suite fixture discipline ``tos/runtime/tests/engine/_fixtures.py``'s own module docstring
states (and ``tos/runtime/tests/compose/_fixtures.py`` states in the other direction): each test
suite authors its own fixtures directly against kernel/runtime PRODUCTION packages rather than
importing another suite's test-only helpers. This module builds on top of THIS suite's own
``_fixtures.py`` (same package, not a cross-suite import) plus kernel production packages
(``tos.backtest``, ``tos.engine``) and the runtime's own production evidence-sink adapter
(``tos_runtime.evidence.sinks``).

**Why the durable ``EngineEvidenceSinkAdapter`` here, when ``_fixtures.py``'s own
``build_core`` hardcodes a discarding ``NullEvidenceSink``.** The blind-resubmit test needs to
assert that a NEW attempt reached the send boundary only through a FRESH kernel-recorded
``ATTEMPT_REQUEST_CREATED`` -> ``SEND_HANDED_OFF`` pair (``tos.engine.vocabulary.EvidenceKind``),
never a re-send of an old attempt — a claim a ``NullEvidenceSink`` cannot support, because it
discards every kernel evidence record before it ever reaches a queryable store. Mirrors exactly
how ``tos_runtime.compose._engine_wiring`` wires the SAME adapter for the real paper core
(``engine_sink = EngineEvidenceSinkAdapter(evidence_store, runtime_identity=identity)``), minus the
``runtime_identity`` binding this suite's fixtures never carry.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from tos.backtest import (
    BacktestDriver,
    BarTimeProjection,
    CausalBarConverter,
    DeterministicFillModel,
    ExecutionPriceBasis,
    FillMode,
    FillParameters,
    FillSide,
    NonBrokerTransportNature,
    ProvisionalContextResolver,
    SettlementPolicy,
    SyntheticNonLivePreconditions,
    reference_bars,
)
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.capsule.capsule import (
    CapsuleScope,
    DecisionContextCapsule,
    PolicyRef,
    SafetyCriticalFacts,
    SnapshotRef,
)
from tos.dsl import (
    Compare,
    CompareOp,
    Decision,
    DecisionKind,
    DecisionPolicy,
    Operand,
    Rule,
    TargetKind,
    TargetSpec,
)
from tos.engine import EngineCore, InstrumentKey, NullEvidenceSink, StrategyRegistry
from tos.engine.records import DecisionTickPayload
from tos.ordering import OrderingEvent
from tos.time import HealthState, SessionContext
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.sinks import EngineEvidenceSinkAdapter
from tos_runtime.evidence.store import SqliteEvidenceStore

from . import _fixtures as fx

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Independent review finding #14's own convention (``test_driver.py``): a concrete bound large
#: enough that this suite's own ``FakeMonotonicSource``/``monotonic_source`` fixture never crosses
#: it within a single test, for a caller that wants "timeout injection never fires here".
NO_TIMEOUT_WITHIN_TEST = 10**12


class AlwaysPermissivePreconditions:
    """A ``True``/``True`` ``CoordinatorPreconditions`` double — this suite's own driver tests
    exercise the durable-inbox/blind-resubmit/parity machinery, not the Coordinator gate itself
    (mirrors ``_fixtures.py``'s own, module-private ``_AlwaysPermissivePreconditions`` — declared
    fresh here rather than importing a leading-underscore name across modules)."""

    def authority_epoch_current(self) -> bool | None:
        return True

    def live_scope_authorized(self, _transport_nature: Any) -> bool | None:
        return True


def build_engine_driver(
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source: Any,
    transmit: Any = None,
    sink: Any = None,
    max_send_result_wait_ms: int = NO_TIMEOUT_WITHIN_TEST,
    continuity_id: str = "parity-fr",
    registry: StrategyRegistry | None = None,
) -> tuple[EngineDriver, EngineCore]:
    """Wire a real :class:`~tos_runtime.engine.driver.EngineDriver` over a durable
    :class:`~tos_runtime.engine.inbox.SqliteEventInbox` — the same "compose-shaped" core wiring
    ``tos/runtime/tests/engine/test_driver.py``'s own ``_make_driver`` uses, extended with an
    OPTIONAL durable evidence sink (module docstring) so a caller can query kernel-recorded
    ``ATTEMPT_REQUEST_CREATED``/``SEND_HANDED_OFF`` rows instead of only reading the ``EventResult``
    the driver hands back, and an OPTIONAL injected ``registry`` (default ``fx.registry_with()``,
    a single-scope registry) so a caller can wire :func:`registry_with_two_scopes` instead.
    """
    core = EngineCore(
        registry=registry if registry is not None else fx.registry_with(),
        stages=fx.admitting_stages(),
        configuration=fx.engine_configuration(),
        preconditions=AlwaysPermissivePreconditions(),
        transmit=transmit,
        sink=sink if sink is not None else NullEvidenceSink(),
        scheme=SCHEME,
    )
    driver = EngineDriver(
        core=core,
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id=continuity_id,
        monotonic_source=monotonic_source,
        max_send_result_wait_ms=max_send_result_wait_ms,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    return driver, core


# -- a second scope, for the "a fresh decision uses a NEW attempt" blind-resubmit check ---------
#
# **Finding (2026-09-09, this lane).** ``ProvisionalReservationLedger`` has NO release path in
# this Phase — ``tos.engine.state.PROJECTION_ORDER`` does not carry a ``RELEASED`` member at all
# (``state.py``'s own module docstring: "release 는 RCL 소관"/RFC-002 §9.1:557), and a genuinely
# ``APPLIED`` ``FULL_FILL`` advances the SAME scope's outstanding reservation only as far as
# ``CapacityState.POSITION_CONSUMED`` — still counted by ``outstanding_count``/
# ``admits_new_exposure`` as occupying the scope's one ``max_unresolved_send_per_scope`` slot,
# permanently, for the life of this in-memory ledger. Measured directly: a second
# ``DECISION_TICK`` on the SAME ``InstrumentKey``, issued AFTER the first attempt's FULL_FILL is
# durably ``APPLIED``, is still refused at the capacity stage
# ("denied at the capacity stage (MAX_unresolved_send_per_scope...)") — resolving the first
# attempt does NOT free its scope's slot; only a genuinely different scope has room. So "a fresh
# decision uses a NEW attempt, never a resend" is demonstrated here on a SECOND
# ``InstrumentKey`` in the SAME registry/core/driver — the same kernel/runtime machinery, a
# different scope — rather than by re-using the first tick's own (permanently occupied) scope.
# This is a Phase-5/RCL-release gap, not a defect in this wave's own driver/ledger wiring.

_SECOND_ACCOUNT = "acct-ar"
_SECOND_INSTRUMENT = "NQ"


def second_instrument_key() -> InstrumentKey:
    return InstrumentKey(account=_SECOND_ACCOUNT, instrument=_SECOND_INSTRUMENT)


def _second_issue_capsule(*, seq: int = 1) -> DecisionContextCapsule:
    """The second scope's own Decision Context Capsule — same shape as ``fx.issue_capsule``,
    scoped to :func:`second_instrument_key` instead."""
    return DecisionContextCapsule.issue(
        scheme=SCHEME,
        issuer_principal_id="iss-ar-2",
        critical_input_policy=PolicyRef(
            policy_id="pol-ar-2", canonical_digest="pd-ar-2"
        ),
        critical_input_snapshot=SnapshotRef(
            snapshot_id=f"cis-ar-2-{seq}", canonical_digest=f"sd-ar-2-{seq}"
        ),
        scope=CapsuleScope(
            environment="non-live-test",
            account=_SECOND_ACCOUNT,
            instrument=_SECOND_INSTRUMENT,
            decision_class=fx.DECISION_CLASS,
        ),
        safety_critical_facts=SafetyCriticalFacts(
            account=_SECOND_ACCOUNT,
            instrument=_SECOND_INSTRUMENT,
            direction="LONG",
            quantity_basis="RISK",
            unit="contract",
        ),
    )


def _second_always_fires_policy() -> DecisionPolicy:
    """The second scope's own capsule-gated always-fires policy — same shape as
    ``fx.always_fires_policy``, declaring the SECOND instrument's target."""
    action = Decision(
        kind=DecisionKind.ACTION,
        rationale="F-R second-scope fixture always fires",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account=_SECOND_ACCOUNT,
            instrument=_SECOND_INSTRUMENT,
            direction="LONG",
            position_effect="OPEN",
            quantity_basis="RISK",
            edge_or_confidence="0.7",
            rationale="F-R second-scope fixture always fires",
        ),
    )
    hold = Decision(kind=DecisionKind.NO_ACTION, rationale="unreachable default")
    rule = Rule(
        all_of=(
            Compare(
                left=Operand(ref=("capsule", "scope", "decision_class")),
                op=CompareOp.EQ,
                right=Operand(const=fx.DECISION_CLASS),
            ),
        ),
        decision=action,
    )
    return DecisionPolicy(rules=(rule,), default=hold)


def registry_with_two_scopes() -> StrategyRegistry:
    """A registry holding the SAME first-scope strategy :func:`tos_runtime.tests.engine._fixtures
    .registry_with` builds, PLUS a second, independently-scoped always-fires strategy — so ONE
    core/driver can admit a genuinely NEW decision on a scope that is not permanently
    capacity-occupied by the first scope's own (unreleasable) reservation (see the module-level
    finding above)."""
    registry = StrategyRegistry()
    registry.register(fx.issue_strategy(fx.always_fires_policy()), fx.authored_config())
    registry.register(
        fx.issue_strategy(_second_always_fires_policy()), fx.authored_config()
    )
    return registry


def second_decision_tick_event(*, seq: int = 1) -> Any:
    """An UNSTAMPED ``DECISION_TICK`` for the second scope (mirrors ``fx.decision_tick_event``)."""
    from tos.engine import EventKind
    from tos.engine.records import EngineEvent

    return EngineEvent(
        kind=EventKind.DECISION_TICK,
        decision_tick=DecisionTickPayload(
            instrument_key=second_instrument_key(),
            capsule=_second_issue_capsule(seq=seq),
            time=fx.admitting_time_inputs(),
            reference=OrderingEvent(
                source_continuity_id="fixture-second-scope", source_native_sequence=seq
            ),
        ),
    )


def durable_engine_sink(
    evidence_store: SqliteEvidenceStore,
) -> EngineEvidenceSinkAdapter:
    """A real, durable :class:`~tos.engine.sink.EvidenceSink` over ``evidence_store`` — the same
    production adapter ``tos_runtime.compose._engine_wiring`` wires for the real paper core.
    """
    return EngineEvidenceSinkAdapter(evidence_store)


def ordered_consumed_outcome_digests(
    evidence_store: SqliteEvidenceStore,
) -> tuple[str | None, ...]:
    """The ``EVENT_CONSUMED`` receipts' own ``outcome_digest`` field, in ``seq`` order.

    This is the durable, uniform way to read the FULL outcome-digest sequence for a run driven
    through :class:`~tos_runtime.engine.driver.EngineDriver`: ``enqueue_and_run`` only returns the
    ``EventResult`` for the event it was asked to admit, not for any re-injected follow-on
    ``EGRESS_RESULT`` its own drain loop processes as a side effect — but every processed event,
    tick or re-injected result alike, gets its own durable ``EVENT_CONSUMED`` receipt
    (``tos_runtime.engine.driver`` module docstring item 2/3), and that receipt already carries
    ``result.outcome_digest`` verbatim (``EngineDriver._record_consumed``).
    """
    rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'EVENT_CONSUMED' ORDER BY seq ASC"
    ).fetchall()
    digests: list[str | None] = []
    for (payload_json,) in rows:
        payload = json.loads(payload_json).get("payload", {})
        digests.append(payload.get("outcome_digest"))
    return tuple(digests)


def attempt_ids_for_kind(
    evidence_store: SqliteEvidenceStore, kind: str
) -> list[str | None]:
    """Every ``attempt_id`` recorded on a durable evidence row of the given ``kind``, in ``seq``
    order — used to read the kernel's own ``ATTEMPT_REQUEST_CREATED``/``SEND_HANDED_OFF`` receipts
    (``tos.engine.vocabulary.EvidenceKind``) off a store fed by :func:`durable_engine_sink`.
    """
    rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
    ).fetchall()
    ids: list[str | None] = []
    for (payload_json,) in rows:
        payload = json.loads(payload_json).get("payload", {})
        ids.append(payload.get("attempt_id"))
    return ids


# -- the backtest-side half of the parity harness ----------------------------------------------


def backtest_time_projection() -> BarTimeProjection:
    """Injected bar -> time-coordinate bounds that positively admit — the same shape (and the
    same proven-to-admit values) ``tos/tests/backtest/_backtest_fixtures.py::time_projection``
    uses across the kernel's own backtest suite, reproduced here (not imported — cross-suite
    imports are forbidden; module docstring) because this harness needs its OWN converter wiring
    to independently admit the exact same strategy this suite's ``_fixtures.py`` registers.
    """
    return BarTimeProjection(
        source_age=10,
        delay_bounds=(5,),
        max_age_bound=1000,
        future_tolerance=50,
        snapshot_age_bound=20,
        maximum_consumer_age_ms=1000,
        interval_width=2,
        boundary_lag=10,
        session_template=SessionContext(
            tz_id="tz",
            tz_db_version="tzdb-parity",
            trading_calendar_version="cal-parity",
            phase="CONTINUOUS",
            is_open=True,
            tz_version_conflict=False,
            boundary_value=0,
        ),
        health_state=HealthState.TRUSTED,
    )


def backtest_converter() -> CausalBarConverter:
    """The causal bar -> ``DECISION_TICK`` converter for the parity harness.

    ``capsule_source`` always returns THIS suite's own ``fx.issue_capsule(seq=1)`` — the identical
    capsule content the engine-driver side of the parity test feeds through
    ``fx.decision_tick_event(seq=1)`` — so both paths evaluate the SAME
    ``always_fires_policy`` (``fx.always_fires_policy`` gates only on
    ``capsule.scope.decision_class``, never on a value surface) against byte-identical Capsule
    content. ``ProvisionalContextResolver`` resolves no value (design #33 §3.5) — irrelevant here
    since the policy never reads one.
    """
    return CausalBarConverter(
        instrument_key=fx.instrument_key(),
        resolver=ProvisionalContextResolver(),
        capsule_source=lambda _bar: fx.issue_capsule(seq=1),
        time_projection=backtest_time_projection(),
    )


def backtest_fill_parameters() -> FillParameters:
    """A deterministic SETTLE parameterisation that always fully fills, same-bar, with no
    rejection-band edge case in play — the parity harness cares about the OUTCOME-DIGEST
    sequence, not the fill economics, so every magnitude is chosen only to avoid an incidental
    ``REJECT``."""
    return FillParameters(
        mode=FillMode.SETTLE,
        side=FillSide.BUY,
        settlement=SettlementPolicy.SAME_BAR,
        price_basis=ExecutionPriceBasis.CLOSE,
        scenario_quantity=Decimal(1),
        participation_cap_fraction=Decimal("1"),
        slippage_bps=Decimal(0),
        cost_per_unit=Decimal(0),
        limit_reference_price=Decimal(100),
        price_band_fraction=Decimal("1"),
    )


def build_backtest_driver_and_core(
    *, sink: Any = None
) -> tuple[BacktestDriver, EngineCore, DeterministicFillModel]:
    """Wire one :class:`~tos.backtest.BacktestDriver` over one :class:`~tos.engine.EngineCore`,
    registering the EXACT SAME strategy/stage-map/configuration this suite's ``_fixtures.py``
    gives the engine-driver side (:func:`build_engine_driver`) — the shared premise the parity
    assertion depends on.
    """
    fill_model = DeterministicFillModel(
        instrument_key=fx.instrument_key(),
        parameters=backtest_fill_parameters(),
        scenario_id=None,
    )
    core = EngineCore(
        registry=fx.registry_with(),
        stages=fx.admitting_stages(),
        configuration=fx.engine_configuration(),
        preconditions=SyntheticNonLivePreconditions(authority_epoch_current=True),
        transmit=fill_model,
        transport_nature=NonBrokerTransportNature(),
        sink=sink if sink is not None else NullEvidenceSink(),
        scheme=SCHEME,
    )
    driver = BacktestDriver(
        converter=backtest_converter(),
        fill_model=fill_model,
        continuity_id="parity-backtest",
    )
    return driver, core, fill_model


def one_bar():
    """The single synthetic bar the parity harness replays — content is irrelevant (the policy
    gates on capsule identity, never on a value surface); only its presence as a causally-ordered
    stream of length 1 matters."""
    return reference_bars(1)
