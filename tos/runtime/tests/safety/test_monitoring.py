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
    ``SqliteEvidenceStore.last_committed``'s own shape."""

    def __init__(self, seq: int | None = None) -> None:
        self.seq = seq

    def __call__(self) -> tuple[int | None, str, int | None]:
        return self.seq, "chain-digest", 1


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
# nominal / negative clear() behavior
# ---------------------------------------------------------------------------


def test_all_healthy_clears(nominal_coverage_path: Path) -> None:
    service, *_rest, recorder = _build_service(
        nominal_coverage_path, seq=1, now_ns=0, time_state="TRUSTED", unconsumed=0
    )
    clearance = service.clear()
    assert clearance.clear is True
    assert clearance.reasons == ()
    assert recorder.calls == []


def test_empty_evidence_store_is_unknown(nominal_coverage_path: Path) -> None:
    """seq=None (an empty store) is honestly UNKNOWN, not fresh (module docstring)."""
    service, *_rest, recorder = _build_service(nominal_coverage_path, seq=None)
    clearance = service.clear()
    assert clearance.clear is None
    assert "evidence_tip_never_observed" in clearance.reasons
    assert len(recorder.calls) == 1
    assert recorder.calls[0][0] == "STM_ALERT"


def test_evidence_tip_stall_over_bound_denies(nominal_coverage_path: Path) -> None:
    service, tip, clock, *_rest = _build_service(nominal_coverage_path, seq=1, now_ns=0)
    # First observation establishes the seq at t=0 (fresh, no stall yet).
    first = service.clear()
    assert first.clear is True
    # seq never advances; clock jumps past the 1000ms bound.
    clock.now_ns = 2_000 * _NS_PER_MS
    second = service.clear()
    assert second.clear is False
    assert "evidence_tip_stalled" in second.reasons


def test_time_unhealthy_denies(nominal_coverage_path: Path) -> None:
    service, *_rest = _build_service(nominal_coverage_path, time_state="UNTRUSTED")
    clearance = service.clear()
    assert clearance.clear is False
    assert "time_health_not_in_healthy_states" in clearance.reasons


def test_inbox_backlog_over_bound_denies(nominal_coverage_path: Path) -> None:
    service, *_rest = _build_service(nominal_coverage_path, unconsumed=999)
    clearance = service.clear()
    assert clearance.clear is False
    assert "inbox_unconsumed_over_bound" in clearance.reasons


def test_stm_alert_emitted_exactly_once_per_non_true_clear(
    nominal_coverage_path: Path,
) -> None:
    service, *_rest, recorder = _build_service(
        nominal_coverage_path, time_state="UNTRUSTED"
    )
    service.clear()
    service.clear()
    assert len(recorder.calls) == 2
    assert all(kind == "STM_ALERT" for kind, _fields in recorder.calls)


def test_stm_alert_never_emitted_on_true_clear(nominal_coverage_path: Path) -> None:
    service, *_rest, recorder = _build_service(nominal_coverage_path)
    service.clear()
    service.clear()
    assert recorder.calls == []


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
    service, *_rest = _build_service(nominal_coverage_path)
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
