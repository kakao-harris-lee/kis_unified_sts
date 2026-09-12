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
from tos_runtime.time.generation import GenerationCounter
from tos_runtime.time.service import (
    RecoveryGenerationNotAdvanced,
    TimeServiceNotStarted,
    TrustworthyTimeService,
)
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
    #: G-1 (runtime operations wiring plan §2 decision 1) — None by default,
    #: matching every EXISTING test in this file (none of them care about a
    #: wall-clock value); a test that does sets this explicitly.
    wall_clock_unix_ms: int | None = None

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
        "max_clock_domain_conversion_uncertainty_ms": 50,
        "max_send_result_wait_ms": 5000,
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

    # recovery: UNTRUSTED -> SYNCHRONIZING (re-anchors AND mints generation 2 —
    # LOW-5 fix, review of ba7d438f: recovery itself must strictly advance the
    # generation past whatever the last exposed [UNTRUSTED] snapshot carried).
    monotonic.value = 2000
    recovery_snapshot = service.evaluate()
    assert service.health_state is HealthState.SYNCHRONIZING
    assert recovery_snapshot.generation == 2

    monotonic.value = 2010  # SYNCHRONIZING -> TRUSTED, generation 3
    new_snapshot = service.evaluate()
    assert new_snapshot.generation == 3

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
# LOW-5 (review of ba7d438f): the recovery generation-advance guard is real,
# not a stripped-under-`-O` `assert` that always passed anyway
# ----------------------------------------------------------------------------


def test_recovery_raises_when_generation_would_not_strictly_advance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale snapshot must not become current after recovery without a
    strictly-new generation: forcing GenerationCounter.peek_next() to NOT
    advance (simulating a corrupted/non-monotonic counter) must make the
    recovery step raise, leaving the stale snapshot as the exposed one."""
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(monotonic=monotonic)
    service.start()
    service.evaluate()  # -> SYNCHRONIZING
    monotonic.value = 1010
    service.evaluate()  # -> TRUSTED, generation 1

    monotonic.value = 500  # regression -> UNTRUSTED
    stale_snapshot = service.evaluate()
    assert service.health_state is HealthState.UNTRUSTED
    assert stale_snapshot.generation == 1

    # Force the recovery step's generation candidate to NOT advance.
    monkeypatch.setattr(GenerationCounter, "peek_next", lambda self: self.current)

    monotonic.value = 2000
    with pytest.raises(RecoveryGenerationNotAdvanced):
        service.evaluate()

    # No snapshot was silently re-exposed or advanced past the stale one, and
    # health state did not move — the failed recovery attempt left no trace.
    assert service.current_snapshot().generation == stale_snapshot.generation
    assert service.current_snapshot() is stale_snapshot
    assert service.health_state is HealthState.UNTRUSTED


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
# HIGH-2 (review of ba7d438f): same-clock instances must not count as
# independent, and un-measured disagreement must not be asserted as agreement
# ----------------------------------------------------------------------------


def test_single_reader_reaches_trusted_unchanged_control() -> None:
    """Control: the pre-fix single-reader path is untouched by the HIGH-2 fix."""
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(monotonic=monotonic)  # default: one FakeReferenceReader
    service.start()
    service.evaluate()  # -> SYNCHRONIZING
    monotonic.value = 1010
    snap = service.evaluate()  # -> TRUSTED, same as before the fix

    assert service.health_state is HealthState.TRUSTED
    assert snap.health_state is HealthState.TRUSTED


def test_two_same_clock_readers_never_reach_trusted_with_min_two_required() -> None:
    """HIGH-2 red-proof, now green: two readers sharing ONE common_mode_group
    (the real LocalSystemClockReader case) must collapse to 1 independent
    reference, never satisfying a profile requiring 2."""
    monotonic = FakeMonotonicSource(1000)
    same_group_readers = [
        FakeReferenceReader(common_mode_group="LOCAL_SYSTEM_CLOCK"),
        FakeReferenceReader(common_mode_group="LOCAL_SYSTEM_CLOCK"),
    ]
    service, _ = _build(
        monotonic=monotonic,
        references=same_group_readers,
        config=_config(min_time_independent_reference_count=2),
    )
    service.start()
    service.evaluate()  # -> SYNCHRONIZING
    monotonic.value = 1010
    snap = service.evaluate()

    assert service.health_state is HealthState.SYNCHRONIZING  # never TRUSTED
    from tos.time import independent_reference_count

    assert independent_reference_count(snap.reference_sources) == 1


def test_two_distinct_group_readers_with_no_comparison_never_reach_trusted() -> None:
    """HIGH-2: two readers with genuinely DISTINCT common_mode_group values
    satisfy the independent-count requirement (2 >= 2), but Phase 2 performs
    no pairwise disagreement comparison — disagreement must be reported
    UNKNOWN, not silently asserted as 0/agreeing, so TRUSTED still must not
    be reached."""
    monotonic = FakeMonotonicSource(1000)
    distinct_group_readers = [
        FakeReferenceReader(common_mode_group="SOURCE_A"),
        FakeReferenceReader(common_mode_group="SOURCE_B"),
    ]
    service, _ = _build(
        monotonic=monotonic,
        references=distinct_group_readers,
        config=_config(min_time_independent_reference_count=2),
    )
    service.start()
    service.evaluate()  # -> SYNCHRONIZING
    monotonic.value = 1010
    snap = service.evaluate()

    from tos.time import independent_reference_count

    # The independent-count gate alone WOULD pass (2 distinct groups)...
    assert independent_reference_count(snap.reference_sources) == 2
    # ...but un-measured disagreement still fails closed, so TRUSTED is
    # correctly refused anyway.
    assert service.health_state is HealthState.SYNCHRONIZING  # never TRUSTED


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


# ----------------------------------------------------------------------------
# G-1 (runtime operations wiring plan §2 decision 1) — wall-clock exposure
# ----------------------------------------------------------------------------


def test_wall_clock_now_is_none_before_trusted() -> None:
    """M1 (plan §5 mutation table): a SYNCHRONIZING snapshot — even one
    carrying a real wall-clock observation — must never be surfaced through
    ``wall_clock_now()``."""
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=1_700_000_000_000)],
    )
    service.start()
    service.evaluate()  # -> SYNCHRONIZING only
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
    service.evaluate()  # -> SYNCHRONIZING
    monotonic.value = 1010
    snap = service.evaluate()  # -> TRUSTED
    assert service.health_state is HealthState.TRUSTED
    assert snap.wall_clock_observation == 1_700_000_000_000
    assert service.wall_clock_now() == 1_700_000_000_000


def test_wall_clock_now_reverts_to_none_after_untrusted_regression() -> None:
    """Reaching TRUSTED once does not latch wall_clock_now() permanently —
    a later regression to UNTRUSTED must re-gate it, same as HealthState
    itself (mirrors test_monotonic_regression_prevents_trusted_and_forces_
    untrusted's own FSM shape)."""
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=1_700_000_000_000)],
    )
    service.start()
    service.evaluate()  # -> SYNCHRONIZING
    monotonic.value = 1010
    service.evaluate()  # -> TRUSTED
    assert service.wall_clock_now() == 1_700_000_000_000

    monotonic.value = 500  # regression -> UNTRUSTED
    service.evaluate()
    assert service.health_state is HealthState.UNTRUSTED
    assert service.wall_clock_now() is None


def test_reader_without_a_wall_clock_value_never_fabricates_one() -> None:
    """A reference reader that does not supply wall_clock_unix_ms (the
    default for every reader in this file's fixtures) must never see one
    invented on its behalf — the snapshot's observation stays honestly
    None even once TRUSTED."""
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(
        monotonic=monotonic
    )  # default FakeReferenceReader: no wall clock
    service.start()
    service.evaluate()  # -> SYNCHRONIZING
    monotonic.value = 1010
    snap = service.evaluate()  # -> TRUSTED
    assert service.health_state is HealthState.TRUSTED
    assert snap.wall_clock_observation is None
    assert service.wall_clock_now() is None


def test_time_wall_clock_exposed_evidence_appended_exactly_once() -> None:
    """Decision 8: TIME_WALL_CLOCK_EXPOSED fires exactly once per service
    instance, the first TRUSTED cycle that carries a wall-clock reading —
    never again on subsequent TRUSTED cycles, and never before TRUSTED."""
    monotonic = FakeMonotonicSource(1000)
    service, evidence = _build(
        monotonic=monotonic,
        references=[FakeReferenceReader(wall_clock_unix_ms=1_700_000_000_000)],
    )
    service.start()
    service.evaluate()  # -> SYNCHRONIZING: no TIME_WALL_CLOCK_EXPOSED yet
    assert not any(r.kind == "TIME_WALL_CLOCK_EXPOSED" for r in evidence.appended)

    monotonic.value = 1010
    service.evaluate()  # -> TRUSTED: fires exactly once
    exposed = [r for r in evidence.appended if r.kind == "TIME_WALL_CLOCK_EXPOSED"]
    assert len(exposed) == 1
    assert exposed[0].payload["wall_clock_observation"] == 1_700_000_000_000
    assert exposed[0].payload["unit"] == "unix_ms"

    monotonic.value = 1020
    service.evaluate()  # still TRUSTED: no second announcement
    exposed_again = [
        r for r in evidence.appended if r.kind == "TIME_WALL_CLOCK_EXPOSED"
    ]
    assert len(exposed_again) == 1


def test_time_wall_clock_exposed_never_fires_without_a_reading() -> None:
    monotonic = FakeMonotonicSource(1000)
    service, evidence = _build(monotonic=monotonic)  # no wall clock configured
    service.start()
    service.evaluate()
    monotonic.value = 1010
    service.evaluate()  # -> TRUSTED, but no wall-clock observation
    assert service.health_state is HealthState.TRUSTED
    assert not any(r.kind == "TIME_WALL_CLOCK_EXPOSED" for r in evidence.appended)


# ----------------------------------------------------------------------------
# G-1 (decision 2) — expected_evaluate_cadence_ms-gated suspension_status
# ----------------------------------------------------------------------------


def test_suspension_status_stays_unfilled_when_cadence_is_unset() -> None:
    """Unchanged behavior (the current, shipped state): every existing
    config in this distribution leaves expected_evaluate_cadence_ms null,
    so suspension_status must stay exactly the kernel default."""
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(monotonic=monotonic)  # _config()'s cadence is None
    service.start()
    service.evaluate()
    monotonic.value = 1010
    snap = service.evaluate()
    assert snap.suspension_status.suspended is False
    assert snap.suspension_status.suspension_ms is None


def test_suspension_ms_is_computed_when_cadence_is_configured() -> None:
    """M7 (plan §5 mutation table, positive direction): with a real cadence
    configured, a gap larger than it produces a positive suspension_ms —
    proving the fill-in is not a dead branch."""
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(
        monotonic=monotonic,
        config=_config(expected_evaluate_cadence_ms=5, max_process_suspension_ms=1000),
    )
    service.start()
    service.evaluate()  # -> SYNCHRONIZING, anchor at 1000
    monotonic.value = 1010  # elapsed 10ms since the anchor, cadence 5ms
    snap = service.evaluate()
    assert snap.suspension_status.suspension_ms == 5  # max(0, 10 - 5)
    assert (
        snap.suspension_status.suspended is False
    )  # 10 <= max_process_suspension_ms(1000)


def test_suspension_ms_clamps_to_zero_within_cadence() -> None:
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(
        monotonic=monotonic,
        config=_config(
            expected_evaluate_cadence_ms=1000, max_process_suspension_ms=1000
        ),
    )
    service.start()
    service.evaluate()
    monotonic.value = 1010  # elapsed 10ms, well within the 1000ms cadence
    snap = service.evaluate()
    assert snap.suspension_status.suspension_ms == 0
    assert snap.suspension_status.suspended is False


def test_suspended_flag_reflects_the_raw_elapsed_gap_not_the_cadence() -> None:
    """`suspended` is gated on the ABSOLUTE max_process_suspension_ms bound
    (independent of the cadence-relative suspension_ms magnitude) —
    deliberately different denominators for the two fields."""
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(
        monotonic=monotonic,
        config=_config(expected_evaluate_cadence_ms=1, max_process_suspension_ms=5),
    )
    service.start()
    service.evaluate()
    monotonic.value = 1010  # elapsed 10ms > max_process_suspension_ms(5)
    snap = service.evaluate()
    assert snap.suspension_status.suspended is True
    assert snap.suspension_status.suspension_ms == 9  # max(0, 10 - 1)


def test_anchor_ok_literal_is_unchanged_this_wave() -> None:
    """Documents the deliberate scope boundary (service.py's own _anchor_ok
    docstring): reaching TRUSTED with the default (cadence-unset) config
    still works exactly as before -- this wave does NOT feed the observed
    suspension_ms into the kernel anchor_valid call, because doing so would
    make TRUSTED permanently unreachable everywhere no real cadence value
    is configured (confirmed, not merely feared: see the docstring)."""
    monotonic = FakeMonotonicSource(1000)
    service, _ = _build(monotonic=monotonic)  # default config: cadence unset
    service.start()
    service.evaluate()
    monotonic.value = 1010
    service.evaluate()
    assert service.health_state is HealthState.TRUSTED
