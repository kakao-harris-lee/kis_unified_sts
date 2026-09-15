"""Tests for :mod:`tos_runtime.safety.monitoring` (lane W3-a2; plan §2 decision 2,
MONITORING bullet). Fixtures are local to this file (shared-worktree convention)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos_runtime.safety import monitoring as monitoring_module
from tos_runtime.safety.monitoring import MonitoringConfigError, MonitoringService
from tos_runtime.safety.ports import SafetyMeshService

_NS_PER_MS = 1_000_000


# ---------------------------------------------------------------------------
# self-observation test doubles
# ---------------------------------------------------------------------------


class FakeEvidenceTip:
    """A :class:`~tos_runtime.safety.monitoring.EvidenceTipObserver` double — a settable
    ``(seq, chain_digest, key_generation)`` triple, mirroring
    ``SqliteEvidenceStore.last_committed``'s own shape. ``chain_digest`` is independently
    settable (review disposition, HIGH-2) so a test can drive a genuine continuity break
    (a ``seq`` advance with no digest movement, or vice versa) without monkeypatching any
    kernel predicate."""

    def __init__(
        self, seq: int | None = None, chain_digest: str = "chain-digest-0"
    ) -> None:
        self.seq = seq
        self.chain_digest = chain_digest

    def __call__(self) -> tuple[int | None, str, int | None]:
        return self.seq, self.chain_digest, 1


class FakeClock:
    """A :class:`~tos_runtime.safety.monitoring.MonotonicClock` double — never a real
    clock (this test suite is hermetic)."""

    def __init__(self, now_ns: int = 0) -> None:
        self.now_ns = now_ns

    def __call__(self) -> int:
        return self.now_ns


class FakeTimeHealth:
    """A :class:`~tos_runtime.safety.monitoring.TimeHealthObserver` double."""

    def __init__(self, state: str = "TRUSTED") -> None:
        self.state = state

    def __call__(self) -> str:
        return self.state


class FakeInboxUnconsumed:
    """A :class:`~tos_runtime.safety.monitoring.InboxUnconsumedObserver` double."""

    def __init__(self, count: int = 0) -> None:
        self.count = count

    def __call__(self) -> int:
        return self.count


class RecordingAlertRecorder:
    """A :class:`~tos_runtime.safety.monitoring.AlertRecorder` double that records every
    call for assertion."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, kind: str, fields: Any) -> None:
        self.calls.append((kind, dict(fields)))


class RaisingThenRecordingAlertRecorder:
    """An :class:`~tos_runtime.safety.monitoring.AlertRecorder` double that raises on its
    first ``fail_times`` calls, then records like :class:`RecordingAlertRecorder` — pins
    that a delivery failure is never swallowed (it propagates) and is honestly carried
    into the NEXT snapshot's ``delivery_failures`` (review disposition, HIGH-2's sibling
    requirement)."""

    def __init__(self, fail_times: int = 1) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._remaining_failures = fail_times

    def __call__(self, kind: str, fields: Any) -> None:
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("simulated STM_ALERT delivery failure")
        self.calls.append((kind, dict(fields)))


# ---------------------------------------------------------------------------
# config fixtures
# ---------------------------------------------------------------------------


def _item_flags(criticality: str = "CRITICAL") -> dict[str, Any]:
    return {
        "restrictive_response_present": True,
        "alert_path_present": True,
        "evidence_path_present": True,
        "currentness_rule_present": True,
        "closure_1_to_12_complete": True,
        "criticality": criticality,
    }


def _nominal_manifest() -> dict[str, Any]:
    return {
        "coverage": {
            "manifest": {
                "coverage_manifest_id": "cov-1",
                "coverage_generation": 3,
                "coverage_manifest_digest": "digest-1",
                "policy_digest": "policy-1",
                "is_complete": True,
            },
            "items": {
                "evidence-tip-currency": _item_flags(),
                "time-service-health": _item_flags(),
                "inbox-backlog": _item_flags(),
            },
            "bounds": {
                "max_evidence_tip_stall_ms": 1_000,
                "healthy_time_states": ["TRUSTED"],
                "max_inbox_unconsumed": 5,
            },
        }
    }


def _write(path: Path, raw: dict[str, Any]) -> Path:
    file_path = path / "monitor_coverage.yaml"
    file_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return file_path


@pytest.fixture
def nominal_coverage_path(tmp_path: Path) -> Path:
    return _write(tmp_path, _nominal_manifest())


def _build_service(
    config_path: Path,
    *,
    seq: int | None = 1,
    now_ns: int = 0,
    time_state: str = "TRUSTED",
    unconsumed: int = 0,
) -> tuple[
    MonitoringService,
    FakeEvidenceTip,
    FakeClock,
    FakeTimeHealth,
    FakeInboxUnconsumed,
    RecordingAlertRecorder,
]:
    tip = FakeEvidenceTip(seq)
    clock = FakeClock(now_ns)
    time_health = FakeTimeHealth(time_state)
    inbox = FakeInboxUnconsumed(unconsumed)
    recorder = RecordingAlertRecorder()
    service = MonitoringService(
        config_path=config_path,
        evidence_tip_observer=tip,
        time_health_observer=time_health,
        inbox_unconsumed_observer=inbox,
        monotonic_ns=clock,
        evidence_recorder=recorder,
    )
    return service, tip, clock, time_health, inbox, recorder


def _prime(service: MonitoringService, recorder: RecordingAlertRecorder) -> None:
    """Consume this service's first tick and clear the recorder.

    Module docstring "Honest-source table" consequence (review disposition, HIGH-2): a
    brand-new service's first :meth:`~MonitoringService.clear` call always reports
    ``None`` (continuity cannot be established without a prior observation), regardless of
    how healthy every other signal is. Tests that want to exercise STEADY-STATE (second
    tick onward) behavior call this first so their own assertions are not about the
    first-tick consequence itself (that consequence has its own dedicated test below).
    """
    service.clear()
    recorder.calls.clear()


# ---------------------------------------------------------------------------
# loader refusals
# ---------------------------------------------------------------------------


def test_missing_file_refuses_to_load(tmp_path: Path) -> None:
    with pytest.raises(MonitoringConfigError, match="not found"):
        _build_service(tmp_path / "does_not_exist.yaml")


@pytest.mark.parametrize(
    "key",
    [
        "coverage_manifest_id",
        "coverage_generation",
        "coverage_manifest_digest",
        "policy_digest",
        "is_complete",
    ],
)
def test_a_still_null_manifest_field_refuses_to_load(tmp_path: Path, key: str) -> None:
    raw = json.loads(json.dumps(_nominal_manifest()))
    raw["coverage"]["manifest"][key] = None
    path = _write(tmp_path, raw)
    with pytest.raises(MonitoringConfigError):
        _build_service(path)


@pytest.mark.parametrize(
    "key",
    ["max_evidence_tip_stall_ms", "healthy_time_states", "max_inbox_unconsumed"],
)
def test_a_still_null_bounds_field_refuses_to_load(tmp_path: Path, key: str) -> None:
    raw = json.loads(json.dumps(_nominal_manifest()))
    raw["coverage"]["bounds"][key] = None
    path = _write(tmp_path, raw)
    with pytest.raises(MonitoringConfigError):
        _build_service(path)


def test_empty_healthy_time_states_refuses_to_load(tmp_path: Path) -> None:
    raw = json.loads(json.dumps(_nominal_manifest()))
    raw["coverage"]["bounds"]["healthy_time_states"] = []
    path = _write(tmp_path, raw)
    with pytest.raises(MonitoringConfigError, match="non-empty"):
        _build_service(path)


def test_missing_obligation_refuses_to_load(tmp_path: Path) -> None:
    raw = json.loads(json.dumps(_nominal_manifest()))
    del raw["coverage"]["items"]["inbox-backlog"]
    path = _write(tmp_path, raw)
    with pytest.raises(MonitoringConfigError, match="EXACTLY the three"):
        _build_service(path)


def test_surplus_obligation_refuses_to_load(tmp_path: Path) -> None:
    raw = json.loads(json.dumps(_nominal_manifest()))
    raw["coverage"]["items"]["surplus-obligation"] = _item_flags()
    path = _write(tmp_path, raw)
    with pytest.raises(MonitoringConfigError, match="EXACTLY the three"):
        _build_service(path)


def test_invalid_criticality_refuses_to_load(tmp_path: Path) -> None:
    raw = json.loads(json.dumps(_nominal_manifest()))
    raw["coverage"]["items"]["inbox-backlog"]["criticality"] = "NOT_A_REAL_LEVEL"
    path = _write(tmp_path, raw)
    with pytest.raises(MonitoringConfigError, match="TelemetryCriticality"):
        _build_service(path)


# ---------------------------------------------------------------------------
# first-tick consequence (module docstring "Honest-source table"; review disposition
# HIGH-2) — a dedicated pair of tests for the documented first-observation behavior
# before any steady-state test primes past it.
# ---------------------------------------------------------------------------


def test_first_tick_reports_unknown_before_continuity_established(
    nominal_coverage_path: Path,
) -> None:
    """A brand-new service's first clear() reports None even though every OTHER signal
    (freshness, time health, inbox backlog) is nominal — continuity has no prior
    observation to compare against yet, and this service refuses to assert it."""
    service, *_rest, recorder = _build_service(nominal_coverage_path)
    clearance = service.clear()
    assert clearance.clear is None
    assert "source_continuity_unestablished" in clearance.reasons
    assert len(recorder.calls) == 1
    assert recorder.calls[0][0] == "STM_ALERT"


def test_second_tick_with_an_idle_evidence_tip_clears(
    nominal_coverage_path: Path,
) -> None:
    """The seq/digest pair not moving at all between two ticks is an ordinary idle tick —
    continuity holds (module docstring "Honest-source table" — "unchanged ⇔ unchanged").
    """
    service, *_rest, recorder = _build_service(nominal_coverage_path)
    service.clear()
    recorder.calls.clear()
    clearance = service.clear()
    assert clearance.clear is True
    assert clearance.reasons == ()
    assert recorder.calls == []


# ---------------------------------------------------------------------------
# nominal / negative clear() behavior (steady-state — past the first tick)
# ---------------------------------------------------------------------------


def test_all_healthy_clears(nominal_coverage_path: Path) -> None:
    service, *_rest, recorder = _build_service(
        nominal_coverage_path, seq=1, now_ns=0, time_state="TRUSTED", unconsumed=0
    )
    _prime(service, recorder)
    clearance = service.clear()
    assert clearance.clear is True
    assert clearance.reasons == ()
    assert recorder.calls == []


def test_empty_evidence_store_is_unknown(nominal_coverage_path: Path) -> None:
    """seq=None (an empty store) is honestly UNKNOWN (a GAP, not a continuity-unknown) —
    module docstring "Tri-state combination"."""
    service, *_rest, recorder = _build_service(nominal_coverage_path, seq=None)
    clearance = service.clear()
    assert clearance.clear is None
    assert "evidence_tip_never_observed" in clearance.reasons
    assert "source_continuity_unestablished" not in clearance.reasons
    assert len(recorder.calls) == 1
    assert recorder.calls[0][0] == "STM_ALERT"


def test_evidence_tip_stall_over_bound_denies(nominal_coverage_path: Path) -> None:
    service, tip, clock, *_rest, recorder = _build_service(
        nominal_coverage_path, seq=1, now_ns=0
    )
    _prime(service, recorder)
    # Steady-state tick, still under bound: the idle seq/digest pair holds continuity.
    clock.now_ns = 500 * _NS_PER_MS
    steady = service.clear()
    assert steady.clear is True
    # seq never advances again; clock jumps past the 1000ms bound.
    clock.now_ns = 2_000 * _NS_PER_MS
    stalled = service.clear()
    assert stalled.clear is False
    assert "evidence_tip_stalled" in stalled.reasons


def test_continuity_break_denies_without_predicate_monkeypatch(
    nominal_coverage_path: Path,
) -> None:
    """Drives the REAL service (no kernel-predicate monkeypatch) into a False
    conformance via a genuine continuity break: seq advances but the chain digest does
    NOT move — an inconsistent (torn) evidence chain (review disposition, HIGH-2
    reachability requirement)."""
    service, tip, *_rest, recorder = _build_service(nominal_coverage_path, seq=1)
    _prime(service, recorder)
    tip.seq = 2  # advances; tip.chain_digest is left unchanged — the break.
    clearance = service.clear()
    assert clearance.clear is False
    assert "source_continuity_broken" in clearance.reasons
    assert len(recorder.calls) == 1


def test_time_unhealthy_denies(nominal_coverage_path: Path) -> None:
    service, *_rest, recorder = _build_service(
        nominal_coverage_path, time_state="UNTRUSTED"
    )
    _prime(service, recorder)
    clearance = service.clear()
    assert clearance.clear is False
    assert "time_health_not_in_healthy_states" in clearance.reasons


def test_inbox_backlog_over_bound_denies(nominal_coverage_path: Path) -> None:
    service, *_rest, recorder = _build_service(nominal_coverage_path, unconsumed=999)
    _prime(service, recorder)
    clearance = service.clear()
    assert clearance.clear is False
    assert "inbox_unconsumed_over_bound" in clearance.reasons


def test_stm_alert_emitted_exactly_once_per_non_true_clear(
    nominal_coverage_path: Path,
) -> None:
    service, *_rest, recorder = _build_service(
        nominal_coverage_path, time_state="UNTRUSTED"
    )
    _prime(service, recorder)
    service.clear()
    service.clear()
    assert len(recorder.calls) == 2
    assert all(kind == "STM_ALERT" for kind, _fields in recorder.calls)


def test_stm_alert_never_emitted_on_true_clear(nominal_coverage_path: Path) -> None:
    service, *_rest, recorder = _build_service(nominal_coverage_path)
    _prime(service, recorder)
    service.clear()
    service.clear()
    assert recorder.calls == []


def test_alert_delivery_failure_is_never_swallowed_and_denies_the_next_tick(
    nominal_coverage_path: Path,
) -> None:
    """A recorder that raises must not be swallowed (it propagates immediately) AND must
    be honestly carried into the NEXT snapshot's delivery_failures (review disposition,
    HIGH-2's sibling requirement) — never a literal ``()``."""
    tip = FakeEvidenceTip(1)
    clock = FakeClock(0)
    time_health = FakeTimeHealth("UNTRUSTED")  # a non-True clear() on every tick
    inbox = FakeInboxUnconsumed(0)
    recorder = RaisingThenRecordingAlertRecorder(fail_times=1)
    service = MonitoringService(
        config_path=nominal_coverage_path,
        evidence_tip_observer=tip,
        time_health_observer=time_health,
        inbox_unconsumed_observer=inbox,
        monotonic_ns=clock,
        evidence_recorder=recorder,
    )
    with pytest.raises(RuntimeError, match="simulated STM_ALERT delivery failure"):
        service.clear()
    clearance = service.clear()
    assert clearance.clear is False
    assert "stm_alert_delivery_failed" in clearance.reasons
    assert len(recorder.calls) == 1  # this second attempt succeeded and was recorded


# ---------------------------------------------------------------------------
# Protocol / dimension_report / describe
# ---------------------------------------------------------------------------


def test_service_satisfies_safety_mesh_service_protocol(
    nominal_coverage_path: Path,
) -> None:
    service, *_rest = _build_service(nominal_coverage_path)
    assert isinstance(service, SafetyMeshService)
    assert service.identity == "monitoring-service-stm-v1"


def test_dimension_report_reflects_clear(nominal_coverage_path: Path) -> None:
    service, *_rest, recorder = _build_service(nominal_coverage_path)
    _prime(service, recorder)
    report = service.dimension_report()
    assert report is not None
    assert report.bound_generation == 3
    assert report.positively_established is True
    assert report.restrictive_floor == 0


def test_dimension_report_reflects_denial(nominal_coverage_path: Path) -> None:
    service, *_rest = _build_service(nominal_coverage_path, time_state="UNTRUSTED")
    report = service.dimension_report()
    assert report is not None
    assert report.positively_established is False


def test_describe_is_json_serializable_and_secret_free(
    nominal_coverage_path: Path,
) -> None:
    service, *_rest = _build_service(nominal_coverage_path)
    described = service.describe()
    dumped = json.dumps(described)
    for forbidden in ("token", "secret", "password", "key="):
        assert forbidden not in dumped.lower()
    assert described["coverage_manifest_id"] == "cov-1"


# ---------------------------------------------------------------------------
# M1 mutation pin — a monkeypatched kernel predicate must flip the service's own verdict
# ---------------------------------------------------------------------------


def test_m1_mutation_coverage_predicate_negative_flips_service_false(
    nominal_coverage_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        monitoring_module,
        "critical_coverage_complete_or_gap",
        lambda _manifest, _obligations, _dimensions, _assumption_ids: False,
    )
    service, *_rest = _build_service(nominal_coverage_path)
    clearance = service.clear()
    assert clearance.clear is False
    assert "critical_coverage_complete_or_gap" in clearance.reasons


def test_m1_mutation_conformance_predicate_negative_flips_service_false(
    nominal_coverage_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        monitoring_module,
        "conformance_requires_complete_current_valid",
        lambda _snapshot: False,
    )
    service, *_rest = _build_service(nominal_coverage_path)
    clearance = service.clear()
    assert clearance.clear is False
    assert "conformance_requires_complete_current_valid" in clearance.reasons
