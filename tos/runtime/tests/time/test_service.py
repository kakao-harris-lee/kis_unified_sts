"""Hermetic tests for tos_runtime.time.service.TrustworthyTimeService
(slice plan §1 item 2 + "테스트" list + team-lead additional requirements).

Every kernel predicate the service calls is exercised only through the
service's own public surface (``start``/``evaluate``/``current_snapshot``/
``health_state``) — these tests never reach into the kernel directly except to
build the one cross-check assertion (fault contract ⑤,
``snapshot_consumer_binding_ok``) and the digest-binding reconstruction check.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest
from tos.evidence import EvidenceAppendReceipt
from tos.time import HealthState, TimeHealthSnapshot, snapshot_consumer_binding_ok
from tos.workload import RuntimeIdentity
from tos_runtime.time import service as service_module
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.service import TimeServiceNotStarted, TrustworthyTimeService
from tos_runtime.time.sources import ReferenceObservation

# ----------------------------------------------------------------------------
# fakes
# ----------------------------------------------------------------------------


class FakeMonotonicSource:
    """A monotonic source whose next reading is set explicitly by the test."""

    def __init__(self, first: int) -> None:
        self.value = first

    def now_ms(self) -> int:
        return self.value


@dataclass
class FakeReferenceReader:
    """A reference reader whose observation is set explicitly by the test."""

    reachable: bool = True
    healthy: bool = True
    quality: str | None = "FAKE"
    common_mode_group: str | None = None

    def read(self) -> ReferenceObservation:
        return ReferenceObservation(
            reachable=self.reachable,
            healthy=self.healthy,
            quality=self.quality,
            common_mode_group=self.common_mode_group,
        )


@dataclass
class AppendedRecord:
    payload: Mapping[str, object]
    kind: str
    record_class: str


@dataclass
class InMemoryEvidenceDouble:
    """An in-memory ``EvidenceAppendPort`` double — records every append call
    and returns a real receipt, never touching a real store (lane L's
    ``SqliteEvidenceStore`` is not needed for these unit tests)."""

    appended: list[AppendedRecord] = field(default_factory=list)
    _seq: int = 0

    def append(
        self, payload: Mapping[str, object], *, kind: str, record_class: str
    ) -> EvidenceAppendReceipt:
        self._seq += 1
        self.appended.append(AppendedRecord(dict(payload), kind, record_class))
        return EvidenceAppendReceipt(
            segment_id="test-segment",
            seq=self._seq,
            chain_digest=f"digest-{self._seq}",
            key_generation=0,
        )


class RaisingAfterNEvidenceDouble:
    """An ``EvidenceAppendPort`` double that raises starting from the Nth call
    (1-indexed) — lets a test let ``start()`` succeed while a later
    ``evaluate()`` append fails, or vice versa."""

    def __init__(self, raise_from_call: int) -> None:
        self._raise_from_call = raise_from_call
        self._calls = 0
        self.appended: list[AppendedRecord] = []

    def append(
        self, payload: Mapping[str, object], *, kind: str, record_class: str
    ) -> EvidenceAppendReceipt:
        self._calls += 1
        if self._calls >= self._raise_from_call:
            raise RuntimeError("simulated durable-append failure")
        self.appended.append(AppendedRecord(dict(payload), kind, record_class))
        return EvidenceAppendReceipt(
            segment_id="test-segment",
            seq=self._calls,
            chain_digest="d",
            key_generation=0,
        )


# ----------------------------------------------------------------------------
# fixtures
# ----------------------------------------------------------------------------


def _config(**overrides: object) -> TrustworthyTimeConfig:
    base: dict[str, object] = {
        "max_time_source_precision_ms": 5,
        "max_time_transport_and_queue_uncertainty_ms": 10,
        "max_time_conservative_freshness_age_ms": 1000,
        "max_future_timestamp_tolerance_ms": 200,
        "max_process_suspension_ms": 0,
        "max_time_source_disagreement_ms": 50,
        "min_time_independent_reference_count": 1,
        "tz_db_version": "2026a",
        "trading_calendar_version": "cal-1",
        "verification_profile_version": "vp-0",
        "safety_profile_version": "sp-0",
    }
    base.update(overrides)
    return TrustworthyTimeConfig(**base)


def _identity() -> RuntimeIdentity:
    return RuntimeIdentity(
        cell_id="cell-1",
        runtime_generation=0,
        process_nonce="nonce-1",
        code_digest="digest-1",
    )


def _build(
    *,
    monotonic: FakeMonotonicSource,
    config: TrustworthyTimeConfig | None = None,
    references: list[FakeReferenceReader] | None = None,
    evidence: object | None = None,
) -> tuple[TrustworthyTimeService, InMemoryEvidenceDouble]:
    evidence_double = evidence if evidence is not None else InMemoryEvidenceDouble()
    service = TrustworthyTimeService(
        monotonic=monotonic,
        references=references if references is not None else [FakeReferenceReader()],
        config=config if config is not None else _config(),
        identity=_identity(),
        evidence=evidence_double,
    )
    return service, evidence_double  # type: ignore[return-value]


# ----------------------------------------------------------------------------
# start() + evidence-before-snapshot ordering
# ----------------------------------------------------------------------------


def test_start_appends_exactly_one_evidence_record_before_any_snapshot() -> None:
    service, evidence = _build(monotonic=FakeMonotonicSource(1000))
    assert evidence.appended == []

    service.start()

    assert len(evidence.appended) == 1
    assert evidence.appended[0].kind == "TIME_SERVICE_STARTUP"
    with pytest.raises(TimeServiceNotStarted):
        service.current_snapshot()


def test_evaluate_before_start_raises() -> None:
    service, _ = _build(monotonic=FakeMonotonicSource(1000))
    with pytest.raises(TimeServiceNotStarted):
        service.evaluate()


def test_double_start_raises() -> None:
    service, _ = _build(monotonic=FakeMonotonicSource(1000))
    service.start()
    with pytest.raises(TimeServiceNotStarted):
        service.start()


# ----------------------------------------------------------------------------
# FSM shape: UNINITIALIZED -> SYNCHRONIZING -> TRUSTED
# ----------------------------------------------------------------------------


def test_first_evaluate_moves_uninitialized_to_synchronizing_never_straight_to_trusted() -> (
    None
):
    service, evidence = _build(monotonic=FakeMonotonicSource(1000))
    service.start()
    service.evaluate()
    assert service.health_state is HealthState.SYNCHRONIZING
    assert len(evidence.appended) == 2  # startup + this snapshot
    assert evidence.appended[1].kind == "TIME_HEALTH_SNAPSHOT"


def test_reaching_required_conditions_transitions_to_trusted_with_new_generation() -> (
    None
):
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(monotonic=monotonic)
    service.start()
    service.evaluate()  # -> SYNCHRONIZING
    monotonic.value = 1010
    snap = service.evaluate()  # -> TRUSTED
    assert service.health_state is HealthState.TRUSTED
    assert snap.health_state is HealthState.TRUSTED
    assert snap.generation == 1  # bumped from the start() baseline of 0


# ----------------------------------------------------------------------------
# fault contract ⑥ — clock regression never yields TRUSTED
# ----------------------------------------------------------------------------


def test_monotonic_regression_prevents_trusted_and_forces_untrusted() -> None:
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(monotonic=monotonic)
    service.start()
    service.evaluate()  # -> SYNCHRONIZING
    monotonic.value = 1010
    service.evaluate()  # -> TRUSTED
    assert service.health_state is HealthState.TRUSTED

    monotonic.value = 500  # regression: below the ratcheted anchor (1010)
    snap = service.evaluate()

    assert service.health_state is not HealthState.TRUSTED
    assert snap.health_state is not HealthState.TRUSTED
    assert service.health_state is HealthState.UNTRUSTED


# ----------------------------------------------------------------------------
# fault contract ⑤ — a new generation never revives an old snapshot's binding
# ----------------------------------------------------------------------------


def test_new_generation_after_recovery_makes_old_snapshot_binding_fail() -> None:
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(monotonic=monotonic)
    service.start()
    service.evaluate()  # -> SYNCHRONIZING
    monotonic.value = 1010
    old_snapshot = service.evaluate()  # -> TRUSTED, generation 1
    assert old_snapshot.generation == 1

    monotonic.value = 500  # regression -> UNTRUSTED
    service.evaluate()
    assert service.health_state is HealthState.UNTRUSTED

    monotonic.value = 2000  # recovery: UNTRUSTED -> SYNCHRONIZING (re-anchors)
    service.evaluate()
    assert service.health_state is HealthState.SYNCHRONIZING

    monotonic.value = 2010  # SYNCHRONIZING -> TRUSTED, generation 2
    new_snapshot = service.evaluate()
    assert new_snapshot.generation == 2

    # The OLD snapshot's binding fails against the NEW generation — the new
    # generation does not revive the old snapshot's authority.
    assert not snapshot_consumer_binding_ok(
        old_snapshot,
        expected_snapshot_id=old_snapshot.snapshot_id,
        expected_canonical_digest=old_snapshot.canonical_digest,
        expected_generation=new_snapshot.generation,
    )
    # ...but it still matches its OWN (old) generation — the mismatch is
    # specifically about generation drift, not a corrupted fixture.
    assert snapshot_consumer_binding_ok(
        old_snapshot,
        expected_snapshot_id=old_snapshot.snapshot_id,
        expected_canonical_digest=old_snapshot.canonical_digest,
        expected_generation=old_snapshot.generation,
    )


# ----------------------------------------------------------------------------
# snapshot digest binding (DigestBoundArtifact)
# ----------------------------------------------------------------------------


def test_snapshot_digest_binding_holds() -> None:
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(monotonic=monotonic)
    service.start()
    snap = service.evaluate()

    assert snap.canonical_digest is not None
    assert TimeHealthSnapshot(**snap.model_dump()) == snap


# ----------------------------------------------------------------------------
# single reference source honestly reported; a 2-source profile stays DEGRADED
# ----------------------------------------------------------------------------


def test_single_reference_source_with_two_required_never_reaches_trusted() -> None:
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(
        monotonic=monotonic,
        config=_config(min_time_independent_reference_count=2),
    )
    service.start()
    service.evaluate()  # -> SYNCHRONIZING
    monotonic.value = 1010
    snap = service.evaluate()  # required_ok False (1 < 2) -> stays SYNCHRONIZING

    assert service.health_state is HealthState.SYNCHRONIZING
    assert len(snap.reference_sources) == 1
    from tos.time import independent_reference_count

    assert independent_reference_count(snap.reference_sources) == 1


# ----------------------------------------------------------------------------
# fault contract ⑦ — source unavailable never yields FRESH/TRUSTED
# ----------------------------------------------------------------------------


def test_unreachable_reference_source_never_reaches_trusted() -> None:
    monotonic = FakeMonotonicSource(1000)
    reader = FakeReferenceReader(reachable=False, healthy=False)
    service, _ = _build(monotonic=monotonic, references=[reader])
    service.start()
    service.evaluate()  # -> SYNCHRONIZING
    monotonic.value = 1010
    service.evaluate()

    assert service.health_state is HealthState.SYNCHRONIZING  # never TRUSTED


# ----------------------------------------------------------------------------
# refused transition leaves state unchanged and records why
# ----------------------------------------------------------------------------


def test_evaluate_with_refused_transition_leaves_state_unchanged_and_records_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = _build(monotonic=FakeMonotonicSource(1000))
    service.start()
    monkeypatch.setattr(service_module, "health_transition_allowed", lambda *_: False)

    service.evaluate()

    assert service.health_state is HealthState.UNINITIALIZED  # unchanged
    assert service.last_transition_reason is not None
    assert "refused" in service.last_transition_reason


# ----------------------------------------------------------------------------
# a snapshot is exposed only after its evidence append returned a receipt
# ----------------------------------------------------------------------------


def test_snapshot_exposed_only_after_evidence_append_succeeds() -> None:
    # raise_from_call=2: the startup append (call 1) succeeds, the first
    # evaluate()'s snapshot append (call 2) raises.
    evidence = RaisingAfterNEvidenceDouble(raise_from_call=2)
    service, _ = _build(monotonic=FakeMonotonicSource(1000), evidence=evidence)
    service.start()

    with pytest.raises(RuntimeError, match="simulated durable-append failure"):
        service.evaluate()

    # No snapshot was ever committed/exposed, and health state did not move.
    with pytest.raises(TimeServiceNotStarted):
        service.current_snapshot()
    assert service.health_state is HealthState.UNINITIALIZED
