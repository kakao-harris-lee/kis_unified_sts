"""Shared fixtures for ``tos_runtime.authority`` tests (design #40 §5 order 4)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.evidence import EvidenceAppendReceipt
from tos.time import (
    EvaluatedMonotonicAnchor,
    HealthState,
    SuspensionStatus,
    TimeContinuityIdentity,
    TimeHealthSnapshot,
)
from tos.workload import RuntimeIdentity
from tos_runtime.authority.epoch import (
    AuthorityRuntimeConfig,
    SafetyAuthorityEpochService,
)
from tos_runtime.authority.iap import IntentRegistry
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.service import TimeServiceNotStarted, TrustworthyTimeService
from tos_runtime.time.sources import ReferenceObservation

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


class FakeEvidenceAppendPort:
    """An in-memory :class:`~tos_runtime.evidence.ports.EvidenceAppendPort` double."""

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


class FakeMonotonicSource:
    """A settable monotonic-ms source for :class:`TrustworthyTimeService`."""

    def __init__(self, first: int = 1_000) -> None:
        self.value = first

    def now_ms(self) -> int:
        return self.value


#: G-1 (team-lead follow-up, 2026-09-13): a fixed, non-None default wall
#: reading. Anchor validity now needs a real Δwall-Δmono observation
#: (``TrustworthyTimeService._observed_suspension_ms``) — a reader that never
#: supplies a wall value can no longer reach TRUSTED at all, which would
#: break every existing ``make_trusted()``-driven test in this package.
#: Held CONSTANT across every read() by default (this class's instances are
#: never mutated between evaluate() calls unless a test does so explicitly),
#: so Δwall == 0 and the observed suspension is always exactly 0 for every
#: test that isn't specifically about wall-clock/suspension semantics.
_DEFAULT_TEST_WALL_CLOCK_UNIX_MS = 1_700_000_000_000


@dataclass
class FakeReferenceReader:
    reachable: bool = True
    healthy: bool = True
    quality: str | None = "FAKE"
    common_mode_group: str | None = None
    #: G-1 (runtime operations wiring plan §2 decision 1) — a fixed, static
    #: default (see :data:`_DEFAULT_TEST_WALL_CLOCK_UNIX_MS`'s own docstring);
    #: a test proving the "no wall clock at all" gap sets this to ``None``
    #: explicitly.
    wall_clock_unix_ms: int | None = _DEFAULT_TEST_WALL_CLOCK_UNIX_MS

    def read(self) -> ReferenceObservation:
        return ReferenceObservation(
            reachable=self.reachable,
            healthy=self.healthy,
            quality=self.quality,
            common_mode_group=self.common_mode_group,
            wall_clock_unix_ms=self.wall_clock_unix_ms,
        )


@pytest.fixture
def evidence_port() -> FakeEvidenceAppendPort:
    return FakeEvidenceAppendPort()


@pytest.fixture
def identity() -> RuntimeIdentity:
    return RuntimeIdentity(cell_id="test-cell", process_nonce="test-nonce-1")


@pytest.fixture
def log_path(tmp_path: Path) -> Path:
    return tmp_path / "rcl.sqlite3"


@pytest.fixture
def log(log_path: Path, evidence_port: FakeEvidenceAppendPort) -> SqliteCommitLog:
    instance = SqliteCommitLog(log_path, evidence_port=evidence_port)
    yield instance
    instance.close()


@pytest.fixture
def writer_epoch(log: SqliteCommitLog, identity: RuntimeIdentity) -> int:
    return log.acquire_epoch(identity)


def _time_config(**overrides: object) -> TrustworthyTimeConfig:
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


@pytest.fixture
def time_monotonic() -> FakeMonotonicSource:
    return FakeMonotonicSource(first=1_000)


@pytest.fixture
def time_evidence() -> FakeEvidenceAppendPort:
    return FakeEvidenceAppendPort()


@pytest.fixture
def time_service(
    time_monotonic: FakeMonotonicSource,
    identity: RuntimeIdentity,
    time_evidence: FakeEvidenceAppendPort,
) -> TrustworthyTimeService:
    service = TrustworthyTimeService(
        monotonic=time_monotonic,
        references=[FakeReferenceReader()],
        config=_time_config(),
        identity=identity,
        evidence=time_evidence,
    )
    service.start()
    return service


def make_trusted(service: TrustworthyTimeService) -> None:
    """Drive a freshly-started :class:`TrustworthyTimeService` to ``TRUSTED``.

    Two ``evaluate()`` calls at a stable monotonic reading: the first moves
    ``UNINITIALIZED -> SYNCHRONIZING``, the second ``SYNCHRONIZING ->
    TRUSTED`` (the same FSM shape ``tos/runtime/tests/time/test_service.py``
    exercises directly).
    """
    service.evaluate()
    service.evaluate()
    assert service.health_state is HealthState.TRUSTED


@pytest.fixture
def authority_config() -> AuthorityRuntimeConfig:
    return AuthorityRuntimeConfig(containment_bound_ms=500)


@pytest.fixture
def epoch_service(
    log: SqliteCommitLog,
    time_service: TrustworthyTimeService,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
    authority_config: AuthorityRuntimeConfig,
) -> SafetyAuthorityEpochService:
    return SafetyAuthorityEpochService(
        log,
        time_service,
        evidence_port,
        authority_domain="acct-main",
        writer_epoch=writer_epoch,
        config=authority_config,
    )


@pytest.fixture
def trading_approval_policy_generation() -> int:
    return 1


@pytest.fixture
def intent_registry(
    log: SqliteCommitLog,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
    trading_approval_policy_generation: int,
) -> IntentRegistry:
    return IntentRegistry(
        log,
        evidence_port,
        writer_epoch=writer_epoch,
        trading_approval_policy_generation=trading_approval_policy_generation,
    )


@pytest.fixture
def approvals_dir(tmp_path: Path) -> Path:
    root = tmp_path / "approvals"
    root.mkdir()
    return root


def write_approval_file(
    path: Path,
    *,
    environment_label: str = "non-live-test",
    decision_id: str = "decision-1",
    decision_generation: int = 1,
    result: str = "APPROVE",
    mode: int = 0o600,
    **extra: object,
) -> Path:
    """Write one operator approval YAML file with the given mode."""
    payload: dict[str, object] = {
        "environment_label": environment_label,
        "decision_id": decision_id,
        "decision_generation": decision_generation,
        "result": result,
    }
    payload.update(extra)
    path.write_text(yaml.safe_dump(payload))
    os.chmod(path, mode)
    return path


@pytest.fixture
def expected_owner_uid() -> int:
    return os.getuid()


# ============================================================================
# kernel round #1 §2.2 — decision-expiry test doubles
# ============================================================================


class FakeTimeService:
    """A ``TrustworthyTimeService``-shaped double for decision-expiry tests
    (mirrors ``tos_runtime.tests.currentness.conftest.FakeTimeService``
    exactly): returns a fixed, injected :class:`~tos.time.TimeHealthSnapshot`
    (or raises ``TimeServiceNotStarted`` when none is set) — the real FSM is
    lane K's own test scope, not this lane's. Using a duck-typed double
    (rather than driving the real FSM to a chosen wall-clock reading) keeps
    most of these tests hermetic and focused on the expiry composition logic
    directly, at an arbitrary chosen instant, without needing a real clock
    read or a multi-``evaluate()`` FSM walk for every scenario.

    G-1 update (runtime operations wiring plan §2 decision 1): the real
    :class:`~tos_runtime.time.service.TrustworthyTimeService` CAN now
    populate ``wall_clock_observation`` once TRUSTED, PROVIDED it is wired
    with a reference reader that itself supplies a
    :attr:`~tos_runtime.time.sources.ReferenceObservation.wall_clock_unix_ms`
    value (:class:`FakeReferenceReader` above defaults this to ``None`` —
    matching every reader already configured on the shared ``time_service``
    fixture, unaffected). ``test_iap.py``'s
    ``test_real_time_service_refuses_a_future_dated_issuance`` exercises this
    end-to-end with the real service, replacing this double for that one
    case, precisely to prove the wiring is genuinely connected now — this
    double remains the right tool for every OTHER expiry-composition test in
    this suite, which do not need a live FSM walk."""

    def __init__(self, snapshot: TimeHealthSnapshot | None = None) -> None:
        self._snapshot = snapshot

    def set_snapshot(self, snapshot: TimeHealthSnapshot | None) -> None:
        self._snapshot = snapshot

    def current_snapshot(self) -> TimeHealthSnapshot:
        if self._snapshot is None:
            raise TimeServiceNotStarted("no snapshot set on FakeTimeService")
        return self._snapshot


def expiry_snapshot(
    *,
    health_state: HealthState = HealthState.TRUSTED,
    monotonic_continuity_id: str = "mono-1",
    monotonic_anchor_value: int = 1_000,
    wall_clock_observation: int | None = 1_000_000,
    generation: int = 1,
    suspension_ms: int | None = 0,
) -> TimeHealthSnapshot:
    """A digest-verified, minimally-complete :class:`~tos.time.TimeHealthSnapshot`
    with a settable monotonic continuity/value and wall-clock observation —
    the two coordinates :func:`~tos_runtime.authority.iap.load_operator_approval_with_receipt`
    / :meth:`~tos_runtime.authority.iap.IntentRegistry._expiry_verdict` read.

    ``suspension_ms`` defaults to ``0`` — an explicit OBSERVED "not suspended"
    fact for the admit-path tests (kernel round #1 §2.2 re-review finding #2:
    :meth:`~tos_runtime.authority.iap.IntentRegistry._expiry_verdict` now reads
    ``snapshot.suspension_status.suspension_ms`` rather than fabricating a
    literal, so a caller that wants an admit must supply the observation
    itself). Pass ``None`` for the "never actually observed" case, which the
    kernel's own ``tos.time.predicates.anchor_valid`` treats as an invalid
    anchor (fail-closed)."""
    anchor = TimeContinuityIdentity(
        host_or_runtime_id="cell-1",
        boot_id="boot-1",
        process_id="proc-1",
        monotonic_anchor_id=monotonic_continuity_id,
        monotonic_anchor_value=monotonic_anchor_value,
        tts_generation=generation,
    )
    issued = TimeHealthSnapshot.issue(
        scheme=_SCHEME,
        snapshot_id=f"ths-expiry-{generation}-{monotonic_anchor_value}",
        generation=generation,
        health_state=health_state,
        time_continuity_identity=anchor,
        evaluated_monotonic_anchor=EvaluatedMonotonicAnchor(
            monotonic_anchor_id=monotonic_continuity_id,
            monotonic_anchor_value=monotonic_anchor_value,
        ),
        wall_clock_observation=wall_clock_observation,
        suspension_status=SuspensionStatus(
            suspended=suspension_ms is not None and suspension_ms > 0,
            suspension_ms=suspension_ms,
        ),
        issuer_continuity_id=monotonic_continuity_id,
        issue_monotonic_value=monotonic_anchor_value,
        tz_db_version="v1",
        trading_calendar_version="v1",
        verification_profile_version="v1",
        safety_profile_version="v1",
    )
    assert isinstance(issued, TimeHealthSnapshot)
    return issued


@pytest.fixture
def expiry_time_service() -> FakeTimeService:
    return FakeTimeService(snapshot=expiry_snapshot())


@pytest.fixture
def expiry_time_config() -> TrustworthyTimeConfig:
    return _time_config()


@pytest.fixture
def expiry_intent_registry(
    log: SqliteCommitLog,
    evidence_port: FakeEvidenceAppendPort,
    writer_epoch: int,
    trading_approval_policy_generation: int,
    expiry_time_service: FakeTimeService,
    expiry_time_config: TrustworthyTimeConfig,
) -> IntentRegistry:
    return IntentRegistry(
        log,
        evidence_port,
        writer_epoch=writer_epoch,
        trading_approval_policy_generation=trading_approval_policy_generation,
        time=expiry_time_service,
        time_config=expiry_time_config,
    )
