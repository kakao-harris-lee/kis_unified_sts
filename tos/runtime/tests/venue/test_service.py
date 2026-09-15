"""tos_runtime.venue.service.VenueConstraintService — unit tests (hermetic,
tmp_path only; fake session-phase / tick-generation readers, no mocks
framework)."""

from __future__ import annotations

from pathlib import Path

from tos.egressgw import fold_venue_admissibility
from tos.ioc import CanonicalBrokerCommand
from tos.venue import (
    ActionClass,
    InstrumentRouteFields,
    OrderAdmissibilityResult,
    OrderShapeFields,
)
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.venue.config import load_venue_constraint_policy
from tos_runtime.venue.service import (
    ORDER_ADMISSIBILITY_DECISION_ISSUED_KIND,
    VENUE_POLICY_BOUND_KIND,
    VENUE_SNAPSHOT_ISSUED_KIND,
    VenueConstraintService,
)

from .conftest import SCHEME, kind_count, venue_policy_yaml, write_fixture_venue_policy

_ADMITTING_SHAPE = OrderShapeFields(
    price=200,
    quantity=1,
    order_type="LIMIT",
    tif="DAY",
    side="BUY",
    position_effect="OPEN",
    silently_rounded=False,
)


class _FakeReader:
    """A settable zero-arg reader double — mirrors
    ``tos/runtime/tests/calendar/test_owner.py::_SteppingGeneration``."""

    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


def _build_service(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    *,
    max_quantity: str = "null",
    admitting_phases: str = '["REGULAR"]',
    initial_phase: str | None = "REGULAR",
    initial_generation: int | None = 1,
):
    path = write_fixture_venue_policy(
        tmp_path,
        venue_policy_yaml(max_quantity=max_quantity, admitting_phases=admitting_phases),
    )
    loaded = load_venue_constraint_policy(path, scheme=SCHEME)
    phase_reader = _FakeReader(initial_phase)
    generation_reader = _FakeReader(initial_generation)
    service = VenueConstraintService(
        loaded_policy=loaded,
        scheme=SCHEME,
        session_phase_reader=phase_reader,
        tick_generation_reader=generation_reader,
        evidence_store=evidence_store,
        environment_label="test-env",
        route_fields=InstrumentRouteFields(),
        broker_capability_profile_version=None,
        broker_capability_profile_digest=None,
        activated_member_digest="fixture-activation-digest",
    )
    return service, phase_reader, generation_reader, loaded


# ===========================================================================
# construction — VENUE_POLICY_BOUND
# ===========================================================================


def test_construction_records_venue_policy_bound_once(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    _build_service(tmp_path, evidence_store)
    assert kind_count(evidence_store, VENUE_POLICY_BOUND_KIND) == 1


# ===========================================================================
# snapshot() caching
# ===========================================================================


def test_snapshot_same_tick_issues_one_evidence_row(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    service, _phase, _gen, _loaded = _build_service(tmp_path, evidence_store)
    snap1 = service.snapshot()
    snap2 = service.snapshot()
    snap3 = service.snapshot()
    assert snap1 is snap2 is snap3
    assert kind_count(evidence_store, VENUE_SNAPSHOT_ISSUED_KIND) == 1


def test_snapshot_phase_change_reissues_with_generation_plus_one(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    service, phase, gen, _loaded = _build_service(tmp_path, evidence_store)
    snap1 = service.snapshot()
    phase.value = "CLOSED"
    gen.value = 2
    snap2 = service.snapshot()
    assert snap2 is not snap1
    assert snap2.constraint_generation == snap1.constraint_generation + 1
    assert kind_count(evidence_store, VENUE_SNAPSHOT_ISSUED_KIND) == 2


def test_snapshot_same_phase_new_tick_does_not_reissue(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    service, _phase, gen, _loaded = _build_service(tmp_path, evidence_store)
    snap1 = service.snapshot()
    gen.value = 2
    snap2 = service.snapshot()
    gen.value = 3
    snap3 = service.snapshot()
    assert snap1 is snap2 is snap3
    assert kind_count(evidence_store, VENUE_SNAPSHOT_ISSUED_KIND) == 1


def test_snapshot_restart_constraint_generation_strictly_greater(
    tmp_path: Path, evidence_store: SqliteEvidenceStore, key_provider
) -> None:
    service, phase, gen, loaded = _build_service(tmp_path, evidence_store)
    service.snapshot()  # the initial (REGULAR-phase) snapshot, superseded below
    phase.value = "CLOSED"
    gen.value = 2
    snap2 = service.snapshot()
    evidence_store.close()

    reopened = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=key_provider
    )
    try:
        service2 = VenueConstraintService(
            loaded_policy=loaded,
            scheme=SCHEME,
            session_phase_reader=_FakeReader("REGULAR"),
            tick_generation_reader=_FakeReader(1),
            evidence_store=reopened,
            environment_label="test-env",
            route_fields=InstrumentRouteFields(),
            broker_capability_profile_version=None,
            broker_capability_profile_digest=None,
            activated_member_digest="fixture-activation-digest",
        )
        snap3 = service2.snapshot()
        assert snap3.constraint_generation > snap2.constraint_generation
    finally:
        reopened.close()


def test_snapshot_absent_fields_recorded(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    service, _phase, _gen, _loaded = _build_service(tmp_path, evidence_store)
    snapshot = service.snapshot()
    assert snapshot.critical_input_snapshot_digest is None
    assert snapshot.source_continuity_id is None
    assert snapshot.max_age is None
    assert snapshot.action_tradability == ()


# ===========================================================================
# decide()
# ===========================================================================


def test_decide_admissible_matches_kernel_fold(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    service, _phase, _gen, loaded = _build_service(
        tmp_path, evidence_store, max_quantity="100"
    )
    decision = service.decide(
        action_class=ActionClass.NEW_LONG,
        shape=_ADMITTING_SHAPE,
        candidate_command=None,
    )
    snapshot = service.last_snapshot
    expected = fold_venue_admissibility(
        observed_session_phase=snapshot.observed_session_phase,
        action_class=ActionClass.NEW_LONG,
        snapshot=snapshot,
        policy=loaded.policy,
        shape=_ADMITTING_SHAPE,
        constraints=loaded.policy.shape_constraints,
    )
    assert decision.result is expected
    assert decision.result is OrderAdmissibilityResult.ADMISSIBLE
    assert decision.failed_predicates == ()
    assert decision.unknown_predicates == ()


def test_decide_inadmissible_closed_phase_matches_kernel_fold(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    service, phase, _gen, loaded = _build_service(
        tmp_path, evidence_store, max_quantity="100"
    )
    phase.value = "CLOSED"
    decision = service.decide(
        action_class=ActionClass.NEW_LONG,
        shape=_ADMITTING_SHAPE,
        candidate_command=None,
    )
    snapshot = service.last_snapshot
    expected = fold_venue_admissibility(
        observed_session_phase=snapshot.observed_session_phase,
        action_class=ActionClass.NEW_LONG,
        snapshot=snapshot,
        policy=loaded.policy,
        shape=_ADMITTING_SHAPE,
        constraints=loaded.policy.shape_constraints,
    )
    assert decision.result is expected
    assert decision.result is OrderAdmissibilityResult.INADMISSIBLE
    assert decision.failed_predicates == ("session_phase_admits",)
    assert decision.unknown_predicates == ()


def test_decide_unknown_null_bound_matches_kernel_fold(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    """Default fixture leaves ``max_quantity`` null — ``order_shape_admissible``
    must come back UNKNOWN (module docstring's honest-absence discipline)."""
    service, _phase, _gen, loaded = _build_service(tmp_path, evidence_store)
    decision = service.decide(
        action_class=ActionClass.NEW_LONG,
        shape=_ADMITTING_SHAPE,
        candidate_command=None,
    )
    snapshot = service.last_snapshot
    expected = fold_venue_admissibility(
        observed_session_phase=snapshot.observed_session_phase,
        action_class=ActionClass.NEW_LONG,
        snapshot=snapshot,
        policy=loaded.policy,
        shape=_ADMITTING_SHAPE,
        constraints=loaded.policy.shape_constraints,
    )
    assert decision.result is expected
    assert decision.result is OrderAdmissibilityResult.UNKNOWN
    assert decision.failed_predicates == ()
    assert decision.unknown_predicates == ("order_shape_admissible",)


def test_decide_binds_candidate_command_digest_when_supplied(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    service, _phase, _gen, _loaded = _build_service(
        tmp_path, evidence_store, max_quantity="100"
    )
    command = CanonicalBrokerCommand.issue(
        scheme=SCHEME,
        command_id="cmd-1",
        command_generation=1,
        proposal_id="prop-1",
        proposal_digest="prop-digest",
        axis_bindings=(),
    )
    assert isinstance(command, CanonicalBrokerCommand)
    decision = service.decide(
        action_class=ActionClass.NEW_LONG,
        shape=_ADMITTING_SHAPE,
        candidate_command=command,
    )
    assert decision.candidate_command_id == "cmd-1"
    assert decision.candidate_command_digest == command.canonical_digest


def test_decide_candidate_command_none_leaves_digest_none(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    service, _phase, _gen, _loaded = _build_service(
        tmp_path, evidence_store, max_quantity="100"
    )
    decision = service.decide(
        action_class=ActionClass.NEW_LONG,
        shape=_ADMITTING_SHAPE,
        candidate_command=None,
    )
    assert decision.candidate_command_id is None
    assert decision.candidate_command_digest is None


def test_decide_records_one_evidence_row_per_call(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    service, _phase, _gen, _loaded = _build_service(
        tmp_path, evidence_store, max_quantity="100"
    )
    service.decide(
        action_class=ActionClass.NEW_LONG,
        shape=_ADMITTING_SHAPE,
        candidate_command=None,
    )
    service.decide(
        action_class=ActionClass.NEW_LONG,
        shape=_ADMITTING_SHAPE,
        candidate_command=None,
    )
    assert kind_count(evidence_store, ORDER_ADMISSIBILITY_DECISION_ISSUED_KIND) == 2


def test_decide_decision_generation_strictly_increases(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> None:
    service, _phase, _gen, _loaded = _build_service(
        tmp_path, evidence_store, max_quantity="100"
    )
    d1 = service.decide(
        action_class=ActionClass.NEW_LONG,
        shape=_ADMITTING_SHAPE,
        candidate_command=None,
    )
    d2 = service.decide(
        action_class=ActionClass.NEW_LONG,
        shape=_ADMITTING_SHAPE,
        candidate_command=None,
    )
    assert d2.decision_generation == d1.decision_generation + 1
