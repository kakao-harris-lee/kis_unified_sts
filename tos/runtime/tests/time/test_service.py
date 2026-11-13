"""Hermetic tests for ``tos_runtime.time.service.TrustworthyTimeService``."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TypedDict, Unpack

import pytest
from tos.evidence import EvidenceAppendReceipt
from tos.time import HealthState, TimeHealthSnapshot, snapshot_consumer_binding_ok
from tos.workload import RuntimeIdentity
from tos_runtime.evidence.ports import EvidenceAppendPort
from tos_runtime.time import service as service_module
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.generation import GenerationCounter
from tos_runtime.time.service import (
    RecoveryGenerationNotAdvanced,
    TimeServiceNotStarted,
    TrustworthyTimeService,
)
from tos_runtime.time.sources import ReferenceObservation, ReferenceSourceReader


class FakeMonotonicSource:
    """A monotonic source whose next reading is set explicitly by the test."""

    def __init__(self, first: int) -> None:
        self.value = first

    def now_ms(self) -> int:
        return self.value


_DEFAULT_TEST_WALL_CLOCK_UNIX_MS = 1_700_000_000_000


@dataclass
class FakeReferenceReader:
    """A reference reader whose observation is set explicitly by the test."""

    reachable: bool = True
    healthy: bool = True
    quality: str | None = "FAKE"
    common_mode_group: str | None = None
    wall_clock_unix_ms: int | None = _DEFAULT_TEST_WALL_CLOCK_UNIX_MS

    def read(self) -> ReferenceObservation:
        return ReferenceObservation(
            reachable=self.reachable,
            healthy=self.healthy,
            quality=self.quality,
            common_mode_group=self.common_mode_group,
            wall_clock_unix_ms=self.wall_clock_unix_ms,
        )


@dataclass
class AppendedRecord:
    payload: Mapping[str, object]
    kind: str
    record_class: str


@dataclass
class InMemoryEvidenceDouble:
    """An in-memory ``EvidenceAppendPort`` double — records every append call"""

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
    """An ``EvidenceAppendPort`` double that raises starting from the Nth call"""

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


class _TimeConfigKwargs(TypedDict):
    """1:1 with :class:`TrustworthyTimeConfig`'s dataclass fields (plan §1.1 A-rt) — a runtime"""

    max_time_source_precision_ms: int
    max_time_transport_and_queue_uncertainty_ms: int
    max_time_conservative_freshness_age_ms: int
    max_future_timestamp_tolerance_ms: int
    max_process_suspension_ms: int
    max_time_source_disagreement_ms: int
    min_time_independent_reference_count: int
    max_clock_domain_conversion_uncertainty_ms: int
    max_send_result_wait_ms: int
    max_critical_input_consumer_receipt_age_ms: int
    max_time_source_sequence_gap_ms: int
    tz_db_version: str
    trading_calendar_version: str
    verification_profile_version: str
    safety_profile_version: str
    time_health_snapshot_heartbeat_ms: int


class _TimeConfigKwargsPartial(TypedDict, total=False):
    """Same fields as :class:`_TimeConfigKwargs`, all optional — the override-kwargs shape"""

    max_time_source_precision_ms: int
    max_time_transport_and_queue_uncertainty_ms: int
    max_time_conservative_freshness_age_ms: int
    max_future_timestamp_tolerance_ms: int
    max_process_suspension_ms: int
    max_time_source_disagreement_ms: int
    min_time_independent_reference_count: int
    max_clock_domain_conversion_uncertainty_ms: int
    max_send_result_wait_ms: int
    max_critical_input_consumer_receipt_age_ms: int
    max_time_source_sequence_gap_ms: int
    tz_db_version: str
    trading_calendar_version: str
    verification_profile_version: str
    safety_profile_version: str
    time_health_snapshot_heartbeat_ms: int


def _config(**overrides: Unpack[_TimeConfigKwargsPartial]) -> TrustworthyTimeConfig:
    base: _TimeConfigKwargs = {
        "max_time_source_precision_ms": 5,
        "max_time_transport_and_queue_uncertainty_ms": 10,
        "max_time_conservative_freshness_age_ms": 1000,
        "max_future_timestamp_tolerance_ms": 200,
        "max_process_suspension_ms": 0,
        "max_time_source_disagreement_ms": 50,
        "min_time_independent_reference_count": 1,
        "max_clock_domain_conversion_uncertainty_ms": 50,
        "max_send_result_wait_ms": 5000,
        "max_critical_input_consumer_receipt_age_ms": 1000,
        "max_time_source_sequence_gap_ms": 50,
        "tz_db_version": "2026a",
        "trading_calendar_version": "cal-1",
        "verification_profile_version": "vp-0",
        "safety_profile_version": "sp-0",
        "time_health_snapshot_heartbeat_ms": 60_000,
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
    references: list[ReferenceSourceReader] | None = None,
    evidence: EvidenceAppendPort | None = None,
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


def test_first_evaluate_moves_uninitialized_to_synchronizing_never_straight_to_trusted() -> (
    None
):
    service, evidence = _build(monotonic=FakeMonotonicSource(1000))
    service.start()
    service.evaluate()
    assert service.health_state is HealthState.SYNCHRONIZING
    assert len(evidence.appended) == 2
    assert evidence.appended[1].kind == "TIME_HEALTH_SNAPSHOT"


def test_reaching_required_conditions_transitions_to_trusted_with_new_generation() -> (
    None
):
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(monotonic=monotonic)
    service.start()
    service.evaluate()
    monotonic.value = 1010
    snap = service.evaluate()
    assert service.health_state is HealthState.TRUSTED
    assert snap.health_state is HealthState.TRUSTED
    assert snap.generation == 1


def test_monotonic_regression_prevents_trusted_and_forces_untrusted() -> None:
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(monotonic=monotonic)
    service.start()
    service.evaluate()
    monotonic.value = 1010
    service.evaluate()
    assert service.health_state is HealthState.TRUSTED

    monotonic.value = 500
    snap = service.evaluate()

    assert service.health_state is not HealthState.TRUSTED
    assert snap.health_state is not HealthState.TRUSTED
    assert service.health_state is HealthState.UNTRUSTED


def test_new_generation_after_recovery_makes_old_snapshot_binding_fail() -> None:
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(monotonic=monotonic)
    service.start()
    service.evaluate()
    monotonic.value = 1010
    old_snapshot = service.evaluate()
    assert old_snapshot.generation == 1

    monotonic.value = 500
    service.evaluate()
    assert service.health_state is HealthState.UNTRUSTED

    monotonic.value = 2000
    recovery_snapshot = service.evaluate()
    assert service.health_state is HealthState.SYNCHRONIZING
    assert recovery_snapshot.generation == 2

    monotonic.value = 2010
    new_snapshot = service.evaluate()
    assert new_snapshot.generation == 3

    assert not snapshot_consumer_binding_ok(
        old_snapshot,
        expected_snapshot_id=old_snapshot.snapshot_id,
        expected_canonical_digest=old_snapshot.canonical_digest,
        expected_generation=new_snapshot.generation,
    )
    assert snapshot_consumer_binding_ok(
        old_snapshot,
        expected_snapshot_id=old_snapshot.snapshot_id,
        expected_canonical_digest=old_snapshot.canonical_digest,
        expected_generation=old_snapshot.generation,
    )


def test_recovery_raises_when_generation_would_not_strictly_advance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale snapshot must not become current after recovery without a"""
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(monotonic=monotonic)
    service.start()
    service.evaluate()
    monotonic.value = 1010
    service.evaluate()

    monotonic.value = 500
    stale_snapshot = service.evaluate()
    assert service.health_state is HealthState.UNTRUSTED
    assert stale_snapshot.generation == 1

    monkeypatch.setattr(GenerationCounter, "peek_next", lambda self: self.current)

    monotonic.value = 2000
    with pytest.raises(RecoveryGenerationNotAdvanced):
        service.evaluate()

    assert service.current_snapshot().generation == stale_snapshot.generation
    assert service.current_snapshot() is stale_snapshot
    assert service.health_state is HealthState.UNTRUSTED


def test_snapshot_digest_binding_holds() -> None:
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(monotonic=monotonic)
    service.start()
    snap = service.evaluate()

    assert snap.canonical_digest is not None
    assert TimeHealthSnapshot(**snap.model_dump()) == snap


def test_single_reference_source_with_two_required_never_reaches_trusted() -> None:
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(
        monotonic=monotonic,
        config=_config(min_time_independent_reference_count=2),
    )
    service.start()
    service.evaluate()
    monotonic.value = 1010
    snap = service.evaluate()

    assert service.health_state is HealthState.SYNCHRONIZING
    assert len(snap.reference_sources) == 1
    from tos.time import independent_reference_count

    assert independent_reference_count(snap.reference_sources) == 1


def test_single_reader_reaches_trusted_unchanged_control() -> None:
    """A single reader reaches ``TRUSTED`` with the normal configuration."""
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(monotonic=monotonic)
    service.start()
    service.evaluate()
    monotonic.value = 1010
    snap = service.evaluate()

    assert service.health_state is HealthState.TRUSTED
    assert snap.health_state is HealthState.TRUSTED


def test_two_same_clock_readers_never_reach_trusted_with_min_two_required() -> None:
    """Two readers sharing ONE common_mode_group"""
    monotonic = FakeMonotonicSource(1000)
    same_group_readers: list[ReferenceSourceReader] = [
        FakeReferenceReader(common_mode_group="LOCAL_SYSTEM_CLOCK"),
        FakeReferenceReader(common_mode_group="LOCAL_SYSTEM_CLOCK"),
    ]
    service, _ = _build(
        monotonic=monotonic,
        references=same_group_readers,
        config=_config(min_time_independent_reference_count=2),
    )
    service.start()
    service.evaluate()
    monotonic.value = 1010
    snap = service.evaluate()

    assert service.health_state is HealthState.SYNCHRONIZING
    from tos.time import independent_reference_count

    assert independent_reference_count(snap.reference_sources) == 1


def test_two_distinct_group_readers_with_no_comparison_never_reach_trusted() -> None:
    """Two readers with genuinely DISTINCT common_mode_group values"""
    monotonic = FakeMonotonicSource(1000)
    distinct_group_readers: list[ReferenceSourceReader] = [
        FakeReferenceReader(common_mode_group="SOURCE_A"),
        FakeReferenceReader(common_mode_group="SOURCE_B"),
    ]
    service, _ = _build(
        monotonic=monotonic,
        references=distinct_group_readers,
        config=_config(min_time_independent_reference_count=2),
    )
    service.start()
    service.evaluate()
    monotonic.value = 1010
    snap = service.evaluate()

    from tos.time import independent_reference_count

    assert independent_reference_count(snap.reference_sources) == 2
    assert service.health_state is HealthState.SYNCHRONIZING


def test_unreachable_reference_source_never_reaches_trusted() -> None:
    monotonic = FakeMonotonicSource(1000)
    reader = FakeReferenceReader(reachable=False, healthy=False)
    service, _ = _build(monotonic=monotonic, references=[reader])
    service.start()
    service.evaluate()
    monotonic.value = 1010
    service.evaluate()

    assert service.health_state is HealthState.SYNCHRONIZING


def test_evaluate_with_refused_transition_leaves_state_unchanged_and_records_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = _build(monotonic=FakeMonotonicSource(1000))
    service.start()
    monkeypatch.setattr(service_module, "health_transition_allowed", lambda *_: False)

    service.evaluate()

    assert service.health_state is HealthState.UNINITIALIZED
    assert service.last_transition_reason is not None
    assert "refused" in service.last_transition_reason


def test_snapshot_exposed_only_after_evidence_append_succeeds() -> None:
    evidence = RaisingAfterNEvidenceDouble(raise_from_call=2)
    service, _ = _build(monotonic=FakeMonotonicSource(1000), evidence=evidence)
    service.start()

    with pytest.raises(RuntimeError, match="simulated durable-append failure"):
        service.evaluate()

    with pytest.raises(TimeServiceNotStarted):
        service.current_snapshot()
    assert service.health_state is HealthState.UNINITIALIZED


def test_wall_clock_now_is_none_before_trusted() -> None:
    """A SYNCHRONIZING snapshot — even one"""
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=1_700_000_000_000)],
    )
    service.start()
    service.evaluate()
    assert service.health_state is HealthState.SYNCHRONIZING
    assert service.wall_clock_now() is None


def test_wall_clock_now_is_none_before_any_evaluate() -> None:
    service, _ = _build(monotonic=FakeMonotonicSource(1000))
    service.start()
    assert service.wall_clock_now() is None


def test_wall_clock_now_returns_the_reading_once_trusted() -> None:
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=1_700_000_000_000)],
    )
    service.start()
    service.evaluate()
    monotonic.value = 1010
    snap = service.evaluate()
    assert service.health_state is HealthState.TRUSTED
    assert snap.wall_clock_observation == 1_700_000_000_000
    assert service.wall_clock_now() == 1_700_000_000_000


def _trusted_at_1010() -> tuple[TrustworthyTimeService, FakeMonotonicSource]:
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=1_700_000_000_000)],
    )
    service.start()
    service.evaluate()
    monotonic.value = 1010
    service.evaluate()
    assert service.health_state is HealthState.TRUSTED
    return service, monotonic


def test_wall_clock_now_if_fresh_serves_a_fresh_snapshot() -> None:
    service, monotonic = _trusted_at_1010()
    monotonic.value = 1010 + 1000
    assert service.wall_clock_now_if_fresh(1000) == 1_700_000_000_000


def test_wall_clock_now_if_fresh_refuses_a_stale_snapshot() -> None:
    """With no further ``evaluate()`` —"""
    service, monotonic = _trusted_at_1010()
    monotonic.value = 1010 + 24 * 60 * 60 * 1000
    assert service.health_state is HealthState.TRUSTED
    assert service.wall_clock_now() == 1_700_000_000_000
    assert service.wall_clock_now_if_fresh(1000) is None
    monotonic.value = 1010 + 1001
    assert service.wall_clock_now_if_fresh(1000) is None


def test_wall_clock_now_if_fresh_refuses_a_snapshot_from_the_future() -> None:
    service, monotonic = _trusted_at_1010()
    monotonic.value = 1009
    assert service.wall_clock_now_if_fresh(1000) is None


def test_wall_clock_now_if_fresh_is_none_while_untrusted() -> None:
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(monotonic=monotonic)
    service.start()
    service.evaluate()
    assert service.wall_clock_now_if_fresh(10_000) is None


def test_wall_clock_now_reverts_to_none_after_untrusted_regression() -> None:
    """Reaching TRUSTED once does not latch wall_clock_now() permanently —"""
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=1_700_000_000_000)],
    )
    service.start()
    service.evaluate()
    monotonic.value = 1010
    service.evaluate()
    assert service.wall_clock_now() == 1_700_000_000_000

    monotonic.value = 500
    service.evaluate()
    assert service.health_state is HealthState.UNTRUSTED
    assert service.wall_clock_now() is None


def test_reader_without_a_wall_clock_value_never_fabricates_one_and_keeps_trusted_unreachable() -> (
    None
):
    """A reference reader that never supplies wall_clock_unix_ms must never"""
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=None)],
    )
    service.start()
    service.evaluate()
    monotonic.value = 1010
    snap = service.evaluate()
    assert service.health_state is not HealthState.TRUSTED
    assert snap.wall_clock_observation is None
    assert snap.suspension_status.suspension_ms is None
    assert service.wall_clock_now() is None


def test_time_wall_clock_exposed_evidence_appended_exactly_once() -> None:
    """Decision 8: TIME_WALL_CLOCK_EXPOSED fires exactly once per service"""
    monotonic = FakeMonotonicSource(1000)
    service, evidence = _build(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=1_700_000_000_000)],
    )
    service.start()
    service.evaluate()
    assert not any(r.kind == "TIME_WALL_CLOCK_EXPOSED" for r in evidence.appended)

    monotonic.value = 1010
    service.evaluate()
    exposed = [r for r in evidence.appended if r.kind == "TIME_WALL_CLOCK_EXPOSED"]
    assert len(exposed) == 1
    assert exposed[0].payload["wall_clock_observation"] == 1_700_000_000_000
    assert exposed[0].payload["unit"] == "unix_ms"

    monotonic.value = 1020
    service.evaluate()
    exposed_again = [
        r for r in evidence.appended if r.kind == "TIME_WALL_CLOCK_EXPOSED"
    ]
    assert len(exposed_again) == 1


_PASS_MS = 400
_HEARTBEAT_MS = 55_000
_FRESHNESS_AGE_MS = 1000


def _snapshot_rows(evidence: InMemoryEvidenceDouble) -> list[AppendedRecord]:
    return [r for r in evidence.appended if r.kind == "TIME_HEALTH_SNAPSHOT"]


_SteadyTrusted = tuple[
    TrustworthyTimeService,
    "InMemoryEvidenceDouble",
    FakeMonotonicSource,
    FakeReferenceReader,
]


def _steady_trusted(*, heartbeat_ms: int = _HEARTBEAT_MS) -> _SteadyTrusted:
    """A started service parked in a steady TRUSTED state — two rows written (the"""
    monotonic = FakeMonotonicSource(1000)
    reader = FakeReferenceReader()
    service, evidence = _build(
        monotonic=monotonic,
        references=[reader],
        config=_config(time_health_snapshot_heartbeat_ms=heartbeat_ms),
    )
    service.start()
    service.evaluate()
    monotonic.value += _PASS_MS
    service.evaluate()
    assert service.health_state is HealthState.TRUSTED
    assert len(_snapshot_rows(evidence)) == 2
    return service, evidence, monotonic, reader


def test_identical_evaluations_append_one_row_then_one_heartbeat() -> None:
    """N identical cycles write NO row until the heartbeat falls due, and then exactly one."""
    service, evidence, monotonic, _ = _steady_trusted()
    snapshots = []
    for _ in range(100):
        monotonic.value += _PASS_MS
        snapshots.append(service.evaluate())

    assert len(_snapshot_rows(evidence)) == 2

    assert len({snap.snapshot_id for snap in snapshots}) == 100
    assert [snap.issue_monotonic_value for snap in snapshots] == sorted(
        snap.issue_monotonic_value for snap in snapshots  # type: ignore[type-var]
    )
    assert service.current_snapshot() is snapshots[-1]

    monotonic.value += _HEARTBEAT_MS
    beat = service.evaluate()
    rows = _snapshot_rows(evidence)
    assert len(rows) == 3
    assert rows[-1].payload["snapshot_id"] == beat.snapshot_id
    assert rows[-1].record_class == "TIME_HEALTH_SNAPSHOT"

    monotonic.value += _PASS_MS
    service.evaluate()
    assert len(_snapshot_rows(evidence)) == 3


def test_a_changed_evaluation_appends_immediately_inside_the_heartbeat() -> None:
    """A judged-content change does not wait for the heartbeat — here the reference"""
    service, evidence, monotonic, reader = _steady_trusted()
    for _ in range(10):
        monotonic.value += _PASS_MS
        service.evaluate()
    assert len(_snapshot_rows(evidence)) == 2

    reader.reachable = False
    monotonic.value += _PASS_MS
    service.evaluate()

    rows = _snapshot_rows(evidence)
    assert len(rows) == 3
    assert service.health_state is HealthState.UNTRUSTED
    assert rows[-1].payload["health_state"] == HealthState.UNTRUSTED.value


def test_a_refusal_reason_alone_is_a_change_worth_a_row() -> None:
    """``last_transition_reason`` is not carried on the snapshot, so a cycle that newly"""
    monotonic = FakeMonotonicSource(1000)
    service, evidence = _build(
        monotonic=monotonic,
        config=_config(
            min_time_independent_reference_count=2,
            max_process_suspension_ms=5_000,
            time_health_snapshot_heartbeat_ms=_HEARTBEAT_MS,
        ),
    )
    service.start()
    service.evaluate()
    monotonic.value += _PASS_MS
    service.evaluate()
    assert service.health_state is HealthState.SYNCHRONIZING
    assert service.last_transition_reason is None
    assert len(_snapshot_rows(evidence)) == 1

    monotonic.value -= _PASS_MS // 2
    snapshot = service.evaluate()

    assert service.health_state is HealthState.SYNCHRONIZING
    assert service.last_transition_reason is not None
    assert snapshot.suspension_status.suspended is False
    assert len(_snapshot_rows(evidence)) == 2


def test_wall_clock_first_becoming_available_is_a_change_worth_a_row() -> None:
    """The value of ``wall_clock_observation`` is excluded from the comparison (it moves"""
    monotonic = FakeMonotonicSource(1000)
    reader = FakeReferenceReader(wall_clock_unix_ms=None)
    service, evidence = _build(
        monotonic=monotonic,
        references=[reader],
        config=_config(time_health_snapshot_heartbeat_ms=_HEARTBEAT_MS),
    )
    service.start()
    service.evaluate()
    monotonic.value += _PASS_MS
    service.evaluate()
    assert service.health_state is not HealthState.TRUSTED

    reader.wall_clock_unix_ms = 1_700_000_000_000
    monotonic.value += _PASS_MS
    service.evaluate()
    monotonic.value += _PASS_MS
    service.evaluate()

    exposed = [r for r in evidence.appended if r.kind == "TIME_WALL_CLOCK_EXPOSED"]
    assert len(exposed) == 1
    written_ids = {r.payload["snapshot_id"] for r in _snapshot_rows(evidence)}
    assert exposed[0].payload["snapshot_id"] in written_ids


def test_a_cycle_that_re_establishes_freshness_is_always_due() -> None:
    """Freshness is consumed as a judgement, so the cycle that restores it must be evidenced."""
    service, evidence, monotonic, _ = _steady_trusted()
    rows_before = len(_snapshot_rows(evidence))
    assert service.wall_clock_now_if_fresh(_FRESHNESS_AGE_MS) is not None

    monotonic.value += 4_287
    assert service.wall_clock_now_if_fresh(_FRESHNESS_AGE_MS) is None

    service.evaluate()

    assert len(_snapshot_rows(evidence)) == rows_before + 1
    assert service.wall_clock_now_if_fresh(_FRESHNESS_AGE_MS) is not None


def test_a_stale_clock_cycle_whose_append_fails_exposes_nothing() -> None:
    """The fail-closed consequence of the test above: when the evaluation that would restore"""
    service, _, monotonic, _ = _steady_trusted()
    before = service.current_snapshot()
    monotonic.value += 4_287

    service._evidence = RaisingAfterNEvidenceDouble(raise_from_call=1)  # noqa: SLF001
    with pytest.raises(RuntimeError):
        service.evaluate()

    assert service.current_snapshot() is before
    assert service.wall_clock_now_if_fresh(_FRESHNESS_AGE_MS) is None


def test_a_skipped_row_still_propagates_an_append_failure_when_one_is_due() -> None:
    """The receipt discipline survives: when a row IS due, a failing append still stops the"""
    service, _, monotonic, reader = _steady_trusted()
    before = service.current_snapshot()

    service._evidence = RaisingAfterNEvidenceDouble(raise_from_call=1)  # noqa: SLF001
    reader.reachable = False
    monotonic.value += _PASS_MS
    with pytest.raises(RuntimeError):
        service.evaluate()

    assert service.health_state is HealthState.TRUSTED
    assert service.current_snapshot() is before


def test_time_wall_clock_exposed_never_fires_without_a_reading() -> None:
    monotonic = FakeMonotonicSource(1000)
    service, evidence = _build(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=None)],
    )
    service.start()
    service.evaluate()
    monotonic.value = 1010
    service.evaluate()
    assert service.health_state is not HealthState.TRUSTED
    assert not any(r.kind == "TIME_WALL_CLOCK_EXPOSED" for r in evidence.appended)


def test_two_real_evaluate_cycles_with_the_real_local_reader_reach_trusted() -> None:
    """(a) The REAL local wall-clock reader (not a fake) paired with a"""
    from tos_runtime.time.sources import LocalSystemClockReader

    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(
        monotonic=monotonic,
        references=[LocalSystemClockReader()],
        config=_config(max_process_suspension_ms=5000),
    )
    service.start()
    service.evaluate()
    monotonic.value = 1010
    snap = service.evaluate()
    assert service.health_state is HealthState.TRUSTED
    assert snap.suspension_status.suspension_ms is not None
    assert 0 <= snap.suspension_status.suspension_ms < 5000
    assert snap.suspension_status.suspended is False


def test_a_wall_clock_jump_far_beyond_the_bound_is_observed_as_suspended() -> None:
    """(b) M7 replacement: a reference reader whose SECOND reading jumps by"""
    monotonic = FakeMonotonicSource(1000)
    reader = FakeReferenceReader(wall_clock_unix_ms=1_700_000_000_000)
    service, _ = _build(
        monotonic=monotonic,
        references=[reader],
        config=_config(max_process_suspension_ms=100),
    )
    service.start()
    service.evaluate()

    monotonic.value = 1010
    assert reader.wall_clock_unix_ms is not None
    reader.wall_clock_unix_ms += 100 + 1000
    snap = service.evaluate()

    assert service.health_state is not HealthState.TRUSTED
    assert snap.suspension_status.suspended is True
    assert snap.suspension_status.suspension_ms == 1090


def test_first_evaluate_cycle_has_no_previous_reading_to_compare() -> None:
    """(c) The very first evaluate() cycle can never observe a suspension —"""
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=1_700_000_000_000)],
    )
    service.start()
    snap = service.evaluate()
    assert service.health_state is HealthState.SYNCHRONIZING
    assert snap.suspension_status.suspension_ms is None
    assert snap.suspension_status.suspended is False


_MAPPING_WALL_MS = 1_700_000_000_000
_MAPPING_FIRST_MONO_MS = 1_000
_MAPPING_SECOND_MONO_MS = 1_010


def _trusted_for_mapping(
    *, wall_jump_ms: int = 0, max_process_suspension_ms: int = 2_000
) -> TrustworthyTimeService:
    """A service driven to TRUSTED over exactly two evaluate() cycles."""
    monotonic = FakeMonotonicSource(_MAPPING_FIRST_MONO_MS)
    reader = FakeReferenceReader(wall_clock_unix_ms=_MAPPING_WALL_MS)
    service, _ = _build(
        monotonic=monotonic,
        references=[reader],
        config=_config(max_process_suspension_ms=max_process_suspension_ms),
    )
    service.start()
    service.evaluate()
    monotonic.value = _MAPPING_SECOND_MONO_MS
    assert reader.wall_clock_unix_ms is not None
    reader.wall_clock_unix_ms += wall_jump_ms
    service.evaluate()
    assert service.health_state is HealthState.TRUSTED
    return service


def test_mapping_at_the_domain_ceiling_is_the_evaluated_reading_itself() -> None:
    """The upper domain edge — the instant the evaluation itself was taken. Nothing is"""
    service = _trusted_for_mapping()

    assert service.wall_clock_at_monotonic(_MAPPING_SECOND_MONO_MS) == _MAPPING_WALL_MS
    assert service.wall_clock_now() == _MAPPING_WALL_MS


def test_mapping_at_the_domain_floor_subtracts_the_whole_cycle() -> None:
    """The lower domain edge — the PREVIOUS evaluation's own monotonic reading. 10 ms of"""
    service = _trusted_for_mapping()

    assert service.wall_clock_at_monotonic(_MAPPING_FIRST_MONO_MS) == (
        _MAPPING_WALL_MS - (_MAPPING_SECOND_MONO_MS - _MAPPING_FIRST_MONO_MS)
    )


def test_mapping_refuses_one_millisecond_below_the_domain_floor() -> None:
    """Mutation: drop the lower-bound check -> this returns"""
    service = _trusted_for_mapping()

    assert service.wall_clock_at_monotonic(_MAPPING_FIRST_MONO_MS - 1) is None


def test_mapping_refuses_one_millisecond_above_the_evaluated_instant() -> None:
    """The other edge — the "extrapolate now" direction the 2026-09-26 plan §3 rejected."""
    service = _trusted_for_mapping()

    assert service.wall_clock_at_monotonic(_MAPPING_SECOND_MONO_MS + 1) is None


def test_mapping_subtracts_the_suspension_this_cycle_observed() -> None:
    """A 500 ms wall jump against a 10 ms monotonic advance is an observed suspension of 490"""
    service = _trusted_for_mapping(wall_jump_ms=500)
    observed_suspension_ms = 500 - (_MAPPING_SECOND_MONO_MS - _MAPPING_FIRST_MONO_MS)
    assert (
        service.current_snapshot().suspension_status.suspension_ms
        == observed_suspension_ms
    )

    assert service.wall_clock_at_monotonic(_MAPPING_FIRST_MONO_MS) == (
        _MAPPING_WALL_MS
        + 500
        - (_MAPPING_SECOND_MONO_MS - _MAPPING_FIRST_MONO_MS)
        - observed_suspension_ms
    )


def test_mapping_returns_none_while_not_trusted() -> None:
    """Same ``TRUSTED`` gate ``wall_clock_now`` applies — a SYNCHRONIZING cycle has a reading"""
    monotonic = FakeMonotonicSource(_MAPPING_FIRST_MONO_MS)
    service, _ = _build(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=_MAPPING_WALL_MS)],
    )
    service.start()
    snapshot = service.evaluate()

    assert service.health_state is HealthState.SYNCHRONIZING
    assert snapshot.wall_clock_observation == _MAPPING_WALL_MS
    assert service.wall_clock_at_monotonic(_MAPPING_FIRST_MONO_MS) is None


def test_mapping_returns_none_after_trust_is_lost() -> None:
    """Trust lost after a mapping was available: a monotonic regression forces UNTRUSTED, and"""
    monotonic = FakeMonotonicSource(_MAPPING_FIRST_MONO_MS)
    service, _ = _build(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=_MAPPING_WALL_MS)],
        config=_config(max_process_suspension_ms=2_000),
    )
    service.start()
    service.evaluate()
    monotonic.value = _MAPPING_SECOND_MONO_MS
    service.evaluate()
    assert service.wall_clock_at_monotonic(_MAPPING_SECOND_MONO_MS) is not None

    monotonic.value = 500
    service.evaluate()

    assert service.health_state is HealthState.UNTRUSTED
    assert service.wall_clock_at_monotonic(_MAPPING_FIRST_MONO_MS) is None


def test_mapping_returns_none_on_the_first_cycle_that_can_observe_no_suspension() -> (
    None
):
    """An unknown suspension term is not a zero. The first ``evaluate()`` has no previous"""
    monotonic = FakeMonotonicSource(_MAPPING_FIRST_MONO_MS)
    service, _ = _build(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=_MAPPING_WALL_MS)],
    )
    service.start()
    service.evaluate()

    assert service.current_snapshot().suspension_status.suspension_ms is None
    assert service.wall_clock_at_monotonic(_MAPPING_FIRST_MONO_MS) is None


def test_mapping_refuses_a_trusted_cycle_whose_suspension_is_unknown() -> None:
    """The ``suspension_ms is None`` branch, pinned as the defense in depth it is (PR #812"""
    service = _trusted_for_mapping()
    assert service.wall_clock_at_monotonic(_MAPPING_SECOND_MONO_MS) == _MAPPING_WALL_MS

    service._cycle_suspension_ms = None  # noqa: SLF001

    assert service.wall_clock_at_monotonic(_MAPPING_SECOND_MONO_MS) is None


def test_the_domain_floor_advances_with_each_cycle() -> None:
    """The domain is THIS cycle, not "everything since boot": a third evaluation moves the"""
    monotonic = FakeMonotonicSource(_MAPPING_FIRST_MONO_MS)
    service, _ = _build(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=_MAPPING_WALL_MS)],
        config=_config(max_process_suspension_ms=2_000),
    )
    service.start()
    service.evaluate()
    monotonic.value = _MAPPING_SECOND_MONO_MS
    service.evaluate()
    assert service.wall_clock_at_monotonic(_MAPPING_FIRST_MONO_MS) is not None

    monotonic.value = _MAPPING_SECOND_MONO_MS + 10
    service.evaluate()

    assert service.wall_clock_at_monotonic(_MAPPING_FIRST_MONO_MS) is None
    assert service.wall_clock_at_monotonic(_MAPPING_SECOND_MONO_MS) is not None
