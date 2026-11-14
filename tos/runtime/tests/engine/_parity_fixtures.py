"""Shared builders for the backtest=paper parity + blind-resubmit suite (TOS Phase 3 Wave 3"""

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
from tos.brokeradapter.synthetic import SyntheticFillPolicy, SyntheticPaperTransport
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
from tos.engine import (
    EngineCore,
    InstrumentKey,
    NullEvidenceSink,
    SendHandoff,
    StrategyRegistry,
)
from tos.engine.records import DecisionTickPayload, EgressResultPayload
from tos.ordering import OrderingEvent
from tos.time import HealthState, SessionContext
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.sinks import EngineEvidenceSinkAdapter
from tos_runtime.evidence.store import SqliteEvidenceStore

from . import _fixtures as fx

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

NO_TIMEOUT_WITHIN_TEST = 10**12

PARITY_QUANTITY = Decimal(1)


class SyntheticBrokerGateway:
    """A ``Transmit``-protocol adapter over the kernel's own, already-shipped"""

    def __init__(self, *, quantity: Decimal = PARITY_QUANTITY) -> None:
        """Wire a full-fill synthetic broker: ``fill_numerator/fill_denominator = 1/1`` over a"""
        self._quantity = quantity
        self._transport = SyntheticPaperTransport(
            SyntheticFillPolicy(
                fill_numerator=1, fill_denominator=1, lot_size=Decimal(1)
            )
        )
        self.results: tuple[EgressResultPayload, ...] = ()

    @property
    def attempts(self) -> tuple[Any, ...]:
        """Every attempt request handed to the underlying transport, in order — mirrors"""
        return tuple(request.attempt for request in self._transport.requests)

    def __call__(self, attempt: Any) -> SendHandoff:
        payload = self._transport.send_once(
            attempt,
            instrument_key=fx.instrument_key(),
            coordinates=(),
            quantity=self._quantity,
        )
        self.results = self.results + (payload,)
        return SendHandoff(
            accepted_for_transmission=True, handoff_reference=attempt.attempt_id
        )


class AlwaysPermissivePreconditions:
    """A ``True``/``True`` ``CoordinatorPreconditions`` double — this suite's own driver tests"""

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
    """Wire a real :class:`~tos_runtime.engine.driver.EngineDriver` over a durable"""
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


_SECOND_ACCOUNT = "acct-ar"
_SECOND_INSTRUMENT = "NQ"


def second_instrument_key() -> InstrumentKey:
    return InstrumentKey(account=_SECOND_ACCOUNT, instrument=_SECOND_INSTRUMENT)


def _second_issue_capsule(*, seq: int = 1) -> DecisionContextCapsule:
    """The second scope's own Decision Context Capsule — same shape as ``fx.issue_capsule``,"""
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
    """The second scope's own capsule-gated always-fires policy — same shape as"""
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
    """A registry holding the SAME first-scope strategy :func:`tos_runtime.tests.engine._fixtures"""
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
    """A real, durable :class:`~tos.engine.sink.EvidenceSink` over ``evidence_store`` — the same"""
    return EngineEvidenceSinkAdapter(evidence_store)


def ordered_consumed_outcome_digests(
    evidence_store: SqliteEvidenceStore,
) -> tuple[str | None, ...]:
    """The ``EVENT_CONSUMED`` receipts' own ``outcome_digest`` field, in ``seq`` order."""
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
    """Every ``attempt_id`` recorded on a durable evidence row of the given ``kind``, in ``seq``"""
    rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
    ).fetchall()
    ids: list[str | None] = []
    for (payload_json,) in rows:
        payload = json.loads(payload_json).get("payload", {})
        ids.append(payload.get("attempt_id"))
    return ids


def backtest_time_projection() -> BarTimeProjection:
    """Injected bar -> time-coordinate bounds that positively admit — the same shape (and the"""
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
    """The causal bar -> ``DECISION_TICK`` converter for the parity harness."""
    return CausalBarConverter(
        instrument_key=fx.instrument_key(),
        resolver=ProvisionalContextResolver(),
        capsule_source=lambda _bar: fx.issue_capsule(seq=1),
        time_projection=backtest_time_projection(),
    )


def backtest_fill_parameters() -> FillParameters:
    """A deterministic SETTLE parameterisation that always fully fills, same-bar, with no"""
    return FillParameters(
        mode=FillMode.SETTLE,
        side=FillSide.BUY,
        settlement=SettlementPolicy.SAME_BAR,
        price_basis=ExecutionPriceBasis.CLOSE,
        scenario_quantity=PARITY_QUANTITY,
        participation_cap_fraction=Decimal("1"),
        slippage_bps=Decimal(0),
        cost_per_unit=Decimal(0),
        limit_reference_price=Decimal(100),
        price_band_fraction=Decimal("1"),
    )


def build_backtest_driver_and_core(
    *, sink: Any = None
) -> tuple[BacktestDriver, EngineCore, DeterministicFillModel]:
    """Wire one :class:`~tos.backtest.BacktestDriver` over one :class:`~tos.engine.EngineCore`,"""
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
    """The single synthetic bar the parity harness replays — content is irrelevant (the policy"""
    return reference_bars(1)
