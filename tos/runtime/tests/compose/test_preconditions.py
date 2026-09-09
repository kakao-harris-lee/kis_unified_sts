"""``tos_runtime.compose._preconditions`` tests (TOS Phase 3 Wave 2 Lane B-R,
plan §2.1 "Coordinator 양성 게이트").

Hermetic — no external network, no ambient env (D1.4). Deliberately does not
import ``tos.runtime.tests.engine._fixtures`` (that module's own docstring:
"Not a copy of ``tos/tests/engine/_engine_fixtures.py`` and does not import
it — runtime tests may not import kernel test modules") — the firewall's
``tools/tos_firewall_check.py`` [TOS-FW-A] scan extends the same
no-cross-test-package-import discipline to ``tos/runtime/tests`` itself, so
this file authors its own minimal single-instrument DECISION_TICK builders
below, and its own minimal :class:`SafetyAuthorityEpochService` wiring
(mirroring ``tos/runtime/tests/authority/conftest.py``'s own fixtures).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.capsule.capsule import (
    CapsuleScope,
    DecisionContextCapsule,
    PolicyRef,
    SafetyCriticalFacts,
    SnapshotRef,
)
from tos.egressgw import TransportNature
from tos.engine import (
    EngineConfiguration,
    EngineCore,
    EngineEvent,
    EventKind,
    InstrumentKey,
    RecordingEvidenceSink,
    Stage,
    StrategyRegistry,
    TimeAdmissionInputs,
)
from tos.engine.records import DecisionTickPayload
from tos.engine.standins import provisional_stage_map
from tos.engine.vocabulary import CommitmentStep, EvidenceKind, HaltReason
from tos.evidence import EvidenceAppendReceipt
from tos.ordering import OrderingEvent
from tos.time import SessionContext, UncertaintyInterval
from tos.workload import RuntimeIdentity
from tos_runtime.authority.epoch import (
    AuthorityRuntimeConfig,
    SafetyAuthorityEpochService,
)
from tos_runtime.compose._preconditions import (
    CoordinatorPreconditionsConfigError,
    RuntimeCoordinatorPreconditions,
    _ReplayPreconditions,
    load_coordinator_preconditions_config,
)
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.service import TrustworthyTimeService
from tos_runtime.time.sources import ReferenceObservation

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_ACCOUNT = "acct-br"
_INSTRUMENT = "ES"
_DECISION_CLASS = "entry"
_PROOF_DIGEST = "proof-digest-br-0"
_PERMIT_IDENTITY = "permit-br-0"


def _instrument_key() -> InstrumentKey:
    return InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT)


def _issue_capsule() -> DecisionContextCapsule:
    return DecisionContextCapsule.issue(
        scheme=_SCHEME,
        issuer_principal_id="iss-br",
        critical_input_policy=PolicyRef(policy_id="pol-br", canonical_digest="pd-br"),
        critical_input_snapshot=SnapshotRef(
            snapshot_id="cis-br-1", canonical_digest="sd-br-1"
        ),
        scope=CapsuleScope(
            environment="non-live-test",
            account=_ACCOUNT,
            instrument=_INSTRUMENT,
            decision_class=_DECISION_CLASS,
        ),
        safety_critical_facts=SafetyCriticalFacts(
            account=_ACCOUNT,
            instrument=_INSTRUMENT,
            direction="LONG",
            quantity_basis="RISK",
            unit="contract",
        ),
    )


def _admitting_time_inputs() -> TimeAdmissionInputs:
    return TimeAdmissionInputs(
        source_age=10,
        delay_bounds=(5,),
        max_age_bound=1000,
        future_tolerance=50,
        snapshot_age_bound=20,
        maximum_consumer_age_ms=1000,
        session_context=SessionContext(
            tz_id="tz",
            tz_db_version="tzdb-br",
            trading_calendar_version="cal-br",
            phase="CONTINUOUS",
            is_open=True,
            tz_version_conflict=False,
            boundary_value=100000,
        ),
        uncertainty_interval=UncertaintyInterval(lo=1, hi=2),
    )


def _decision_tick_event() -> EngineEvent:
    """An UNSTAMPED ``DECISION_TICK`` event — no real strategy needs to fire:
    every test using this reaches at most the Coordinator gate + dispatch
    resolution over an EMPTY registry, never a real commitment flow."""
    return EngineEvent(
        kind=EventKind.DECISION_TICK,
        decision_tick=DecisionTickPayload(
            instrument_key=_instrument_key(),
            capsule=_issue_capsule(),
            time=_admitting_time_inputs(),
            reference=OrderingEvent(
                source_continuity_id="fixture", source_native_sequence=1
            ),
        ),
    )


def _engine_configuration() -> EngineConfiguration:
    return EngineConfiguration(
        dsl_evaluation_budget_steps=64,
        max_unresolved_send_per_scope=1,
        canonicalization_version=EV_L1_PROVISIONAL_VERSION,
        enforcement_mechanism_version="engine-br-tests-v1",
    )


def _admitting_stages() -> dict[CommitmentStep, Stage]:
    return provisional_stage_map(
        conformance_proof_digest=_PROOF_DIGEST,
        action_flow_permit_identity=_PERMIT_IDENTITY,
    )


_SYNTHETIC = TransportNature(
    principal="synthetic-paper-test",
    reaches_broker=False,
    credential_bearing=False,
    route_bearing=False,
    risk_relevant_live=False,
)
_REAL = TransportNature(
    principal="real-broker-test",
    reaches_broker=True,
    credential_bearing=True,
    route_bearing=True,
    risk_relevant_live=True,
)
_UNESTABLISHED = TransportNature()  # every field None — conservatively broker-consuming


def _write_yaml(path: Path, content: dict) -> None:
    path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")


# ============================================================================
# load_coordinator_preconditions_config — fail-closed load
# ============================================================================


def test_not_authorized_loads(tmp_path: Path) -> None:
    path = tmp_path / "coordinator_preconditions.yaml"
    _write_yaml(path, {"live_authorization_state": "NOT_AUTHORIZED"})
    config = load_coordinator_preconditions_config(path)
    assert config.live_authorization_state == "NOT_AUTHORIZED"


def test_null_value_refuses_to_load(tmp_path: Path) -> None:
    path = tmp_path / "coordinator_preconditions.yaml"
    _write_yaml(path, {"live_authorization_state": None})
    with pytest.raises(CoordinatorPreconditionsConfigError):
        load_coordinator_preconditions_config(path)


def test_missing_key_refuses_to_load(tmp_path: Path) -> None:
    path = tmp_path / "coordinator_preconditions.yaml"
    _write_yaml(path, {})
    with pytest.raises(CoordinatorPreconditionsConfigError):
        load_coordinator_preconditions_config(path)


def test_unsupported_value_refuses_to_load(tmp_path: Path) -> None:
    """No runtime wiring exists yet for any posture other than NOT_AUTHORIZED —
    an "ACTIVE"-shaped value must be refused, never silently trusted."""
    path = tmp_path / "coordinator_preconditions.yaml"
    _write_yaml(path, {"live_authorization_state": "ACTIVE"})
    with pytest.raises(CoordinatorPreconditionsConfigError):
        load_coordinator_preconditions_config(path)


def test_missing_file_refuses_to_load(tmp_path: Path) -> None:
    with pytest.raises(CoordinatorPreconditionsConfigError):
        load_coordinator_preconditions_config(tmp_path / "does-not-exist.yaml")


def test_example_file_is_named_tbd_null() -> None:
    """The checked-in example file itself must still refuse to load (null)."""
    example = (
        Path(__file__).resolve().parents[3]
        / "config"
        / "coordinator_preconditions.example.yaml"
    )
    with pytest.raises(CoordinatorPreconditionsConfigError):
        load_coordinator_preconditions_config(example)


# ============================================================================
# RuntimeCoordinatorPreconditions.authority_epoch_current — fake double
# ============================================================================


class _FakeEpochService:
    """A minimal duck-typed double over ``SafetyAuthorityEpochService``'s own
    ``current_epoch``/``epoch_current`` surface (not mypy-checked — tests
    only)."""

    def __init__(
        self, *, current_epoch: int | None, domain_matches: bool = True
    ) -> None:
        self._current_epoch = current_epoch
        self._domain_matches = domain_matches

    def current_epoch(self) -> int | None:
        return self._current_epoch

    def epoch_current(self, claimed_epoch: int | None) -> bool:
        if not self._domain_matches:
            return False
        if claimed_epoch is None or self._current_epoch is None:
            return False
        return claimed_epoch >= self._current_epoch


def test_authority_epoch_current_is_none_when_service_not_wired() -> None:
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=None, live_authorization_state=None
    )
    assert preconditions.authority_epoch_current() is None


def test_authority_epoch_current_is_true_when_a_floor_is_established() -> None:
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=_FakeEpochService(current_epoch=1),  # type: ignore[arg-type]
        live_authorization_state=None,
    )
    assert preconditions.authority_epoch_current() is True


def test_authority_epoch_current_is_false_when_no_floor_is_established_yet() -> None:
    """A wired-but-unissued epoch service (current_epoch() is None) is a
    genuinely fenced state — distinct from "not wired" (None), but still not
    a passing gate."""
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=_FakeEpochService(current_epoch=None),  # type: ignore[arg-type]
        live_authorization_state=None,
    )
    assert preconditions.authority_epoch_current() is False


def test_authority_epoch_current_delegates_to_the_kernel_predicate_never_reimplements_it() -> (
    None
):
    """Mutation canary: if this method ever compared ``current_epoch() is not
    None`` itself instead of calling through ``epoch_current``, a domain
    mismatch reported by the service would be silently ignored. Red under
    that mutation."""
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=_FakeEpochService(current_epoch=1, domain_matches=False),  # type: ignore[arg-type]
        live_authorization_state=None,
    )
    assert preconditions.authority_epoch_current() is False


# ============================================================================
# RuntimeCoordinatorPreconditions.authority_epoch_current — real service
# ============================================================================


class _FakeEvidenceAppendPort:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, object], str, str]] = []

    def append(
        self, payload: Mapping[str, object], *, kind: str, record_class: str
    ) -> EvidenceAppendReceipt:
        self.calls.append((dict(payload), kind, record_class))
        return EvidenceAppendReceipt(
            segment_id=None,
            seq=len(self.calls) - 1,
            chain_digest="fake",
            key_generation=1,
        )


class _FakeReferenceReader:
    def read(self) -> ReferenceObservation:
        return ReferenceObservation(reachable=True, healthy=True, quality="FAKE")


def _time_service(tmp_path: Path) -> TrustworthyTimeService:
    config = TrustworthyTimeConfig(
        max_time_source_precision_ms=5,
        max_time_transport_and_queue_uncertainty_ms=10,
        max_time_conservative_freshness_age_ms=1000,
        max_future_timestamp_tolerance_ms=200,
        max_process_suspension_ms=0,
        max_time_source_disagreement_ms=50,
        min_time_independent_reference_count=1,
        max_clock_domain_conversion_uncertainty_ms=50,
        max_send_result_wait_ms=5000,
        tz_db_version="2026a",
        trading_calendar_version="cal-1",
        verification_profile_version="vp-0",
        safety_profile_version="sp-0",
    )
    identity = RuntimeIdentity(cell_id="test-cell", process_nonce="test-nonce-1")
    service = TrustworthyTimeService(
        monotonic=_FixedMonotonic(),
        references=[_FakeReferenceReader()],
        config=config,
        identity=identity,
        evidence=_FakeEvidenceAppendPort(),
    )
    service.start()
    return service


class _FixedMonotonic:
    def now_ms(self) -> int:
        return 1_000


@pytest.fixture()
def real_epoch_service(tmp_path: Path) -> SafetyAuthorityEpochService:
    identity = RuntimeIdentity(cell_id="test-cell", process_nonce="test-nonce-1")
    log = SqliteCommitLog(
        tmp_path / "rcl.sqlite3", evidence_port=_FakeEvidenceAppendPort()
    )
    writer_epoch = log.acquire_epoch(identity)
    return SafetyAuthorityEpochService(
        log,
        _time_service(tmp_path),
        _FakeEvidenceAppendPort(),
        authority_domain="acct-main",
        writer_epoch=writer_epoch,
        config=AuthorityRuntimeConfig(containment_bound_ms=500),
    )


def test_authority_epoch_current_true_against_a_real_epoch_service_after_a_transition(
    real_epoch_service: SafetyAuthorityEpochService,
) -> None:
    from tos.authority import AuthorityTransitionReason

    real_epoch_service.transition(
        leader_identity="leader-1",
        transition_reason=AuthorityTransitionReason.SAFETY_AUTHORITY_FAILOVER,
    )
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=real_epoch_service, live_authorization_state=None
    )
    assert preconditions.authority_epoch_current() is True


def test_authority_epoch_current_false_against_a_real_epoch_service_before_any_transition(
    real_epoch_service: SafetyAuthorityEpochService,
) -> None:
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=real_epoch_service, live_authorization_state=None
    )
    assert preconditions.authority_epoch_current() is False


def test_authority_epoch_current_refuses_once_the_bound_epoch_is_stale(
    real_epoch_service: SafetyAuthorityEpochService,
) -> None:
    """Review finding #7 (P3W2 wave-2 review). The CLAIMED epoch must come
    from the runtime's own state at composition time, not from re-reading
    the current floor and feeding it back as its own claim (a ``floor >=
    floor`` tautology can only detect an unreadable log, never a stale
    epoch). This gate is composed once at boot and re-evaluated on every
    ``DECISION_TICK`` — a Safety Authority epoch transition that happens
    AFTER composition (e.g. a failover) must make a runtime bound to the
    old epoch refuse on its very next tick, exactly the CPL-6 "a stale
    epoch SHALL fail closed" guarantee (ADR-002-005 §10)."""
    from tos.authority import AuthorityTransitionReason

    real_epoch_service.transition(
        leader_identity="leader-1",
        transition_reason=AuthorityTransitionReason.SAFETY_AUTHORITY_FAILOVER,
    )
    # Composition happens here, at epoch floor 1 — this is what the runtime
    # is bound to for the rest of its life, not whatever the floor happens
    # to read as on a later tick.
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=real_epoch_service, live_authorization_state=None
    )
    assert preconditions.authority_epoch_current() is True

    # An epoch transition after composition (e.g. a failover) advances the
    # floor out from under the already-bound runtime.
    real_epoch_service.transition(
        leader_identity="leader-2",
        transition_reason=AuthorityTransitionReason.SAFETY_AUTHORITY_FAILOVER,
    )
    assert preconditions.authority_epoch_current() is False


# ============================================================================
# RuntimeCoordinatorPreconditions.live_scope_authorized
# ============================================================================


def test_live_scope_authorized_is_none_when_not_configured() -> None:
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=None, live_authorization_state=None
    )
    assert preconditions.live_scope_authorized(_SYNTHETIC) is None


def test_live_scope_authorized_is_none_for_an_unsupported_posture() -> None:
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=None, live_authorization_state="ACTIVE"
    )
    assert preconditions.live_scope_authorized(_SYNTHETIC) is None


def test_live_scope_authorized_is_true_for_a_synthetic_transport_under_not_authorized() -> (
    None
):
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=None, live_authorization_state="NOT_AUTHORIZED"
    )
    assert preconditions.live_scope_authorized(_SYNTHETIC) is True


def test_live_scope_authorized_is_false_for_a_broker_reaching_transport_regardless() -> (
    None
):
    """Structural non-live guarantee: reaches_broker=True is refused even
    though the governance posture is otherwise identical to the synthetic
    case above."""
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=None, live_authorization_state="NOT_AUTHORIZED"
    )
    assert preconditions.live_scope_authorized(_REAL) is False


def test_live_scope_authorized_is_false_for_an_unestablished_transport_nature() -> None:
    """``reaches_broker=None`` (unestablished) is conservatively
    broker-consuming — never treated as non-broker (TransportNature's own
    docstring)."""
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=None, live_authorization_state="NOT_AUTHORIZED"
    )
    assert preconditions.live_scope_authorized(_UNESTABLISHED) is False


def test_live_scope_authorized_checks_reaches_broker_mutation_canary() -> None:
    """Mutation canary: if the ``reaches_broker is False`` structural check
    were ever dropped in favor of the kernel liveness call alone, a
    broker-reaching transport under NOT_AUTHORIZED would wrongly read True
    (since ``is_live(None, ...)`` is unconditionally False, ``not
    is_live(...)`` is unconditionally True). This test is red under that
    mutation."""
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=None, live_authorization_state="NOT_AUTHORIZED"
    )
    assert preconditions.live_scope_authorized(_REAL) is False
    assert preconditions.live_scope_authorized(_SYNTHETIC) is True


# ============================================================================
# _ReplayPreconditions — always True/True
# ============================================================================


def test_replay_preconditions_authority_epoch_current_is_always_true() -> None:
    assert _ReplayPreconditions().authority_epoch_current() is True


@pytest.mark.parametrize("nature", [_SYNTHETIC, _REAL, _UNESTABLISHED])
def test_replay_preconditions_live_scope_authorized_is_always_true(
    nature: TransportNature,
) -> None:
    assert _ReplayPreconditions().live_scope_authorized(nature) is True


# ============================================================================
# Integration with the kernel EngineCore (kernel lane KW2-B — landed
# 2026-09-09 in this shared tree; ``preconditions`` is now a REQUIRED
# ``EngineCore`` constructor argument with no default). Reuses
# ``tests.engine._fixtures`` (Lane A-R's own shared builders) for the
# DECISION_TICK plumbing rather than re-authoring it here.
# ============================================================================


def _build_core(preconditions: object) -> tuple[EngineCore, RecordingEvidenceSink]:
    sink = RecordingEvidenceSink()
    core = EngineCore(
        registry=StrategyRegistry(),
        stages=_admitting_stages(),
        configuration=_engine_configuration(),
        preconditions=preconditions,  # type: ignore[arg-type]
        transmit=None,
        transport_nature=_SYNTHETIC,
        sink=sink,
        scheme=_SCHEME,
    )
    return core, sink


def test_engine_core_accepts_runtime_coordinator_preconditions() -> None:
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=None, live_authorization_state="NOT_AUTHORIZED"
    )
    core, _sink = _build_core(preconditions)
    assert core is not None


def test_decision_tick_refused_before_step_1_when_authority_epoch_not_current() -> None:
    """A fenced (never-issued) epoch service must refuse the tick BEFORE
    dispatch/step 1 — no pipeline evidence, only COORDINATOR_PRECONDITION_REFUSED."""
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=_FakeEpochService(current_epoch=None),  # type: ignore[arg-type]
        live_authorization_state="NOT_AUTHORIZED",
    )
    core, sink = _build_core(preconditions)
    event = _decision_tick_event()
    result = core.handle(event)  # direct-core-call: sanctioned (determinism control)
    assert result.halt_reason is HaltReason.AUTHORITY_NOT_CURRENT
    kinds = [record.kind for record in sink.records]
    assert kinds == [EvidenceKind.COORDINATOR_PRECONDITION_REFUSED]


def test_decision_tick_refused_before_step_1_when_transport_reaches_broker() -> None:
    """A broker-reaching transport nature must refuse the tick even though the
    epoch is current — the structural non-live guarantee (authority passes,
    live-scope alone refuses)."""
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=_FakeEpochService(current_epoch=1),  # type: ignore[arg-type]
        live_authorization_state="NOT_AUTHORIZED",
    )
    sink = RecordingEvidenceSink()
    core = EngineCore(
        registry=StrategyRegistry(),
        stages=_admitting_stages(),
        configuration=_engine_configuration(),
        preconditions=preconditions,
        transmit=None,
        transport_nature=_REAL,
        sink=sink,
        scheme=_SCHEME,
    )
    event = _decision_tick_event()
    result = core.handle(event)  # direct-core-call: sanctioned (determinism control)
    assert result.halt_reason is HaltReason.LIVE_SCOPE_NOT_AUTHORIZED
    kinds = [record.kind for record in sink.records]
    assert kinds == [EvidenceKind.COORDINATOR_PRECONDITION_REFUSED]


def test_decision_tick_reaches_dispatch_when_both_preconditions_hold() -> None:
    """With a current epoch and a synthetic (non-broker) transport, the tick
    proceeds past the Coordinator gate — same fixture-set behaviour as before
    KW2-B, now flowing through a real ``RuntimeCoordinatorPreconditions``
    rather than an unconditional pass."""
    preconditions = RuntimeCoordinatorPreconditions(
        epoch_service=_FakeEpochService(current_epoch=1),  # type: ignore[arg-type]
        live_authorization_state="NOT_AUTHORIZED",
    )
    core, sink = _build_core(preconditions)
    event = _decision_tick_event()
    result = core.handle(event)  # direct-core-call: sanctioned (determinism control)
    assert result.halt_reason is not HaltReason.AUTHORITY_NOT_CURRENT
    assert result.halt_reason is not HaltReason.LIVE_SCOPE_NOT_AUTHORIZED
    kinds = [record.kind for record in sink.records]
    assert EvidenceKind.COORDINATOR_PRECONDITION_REFUSED not in kinds
