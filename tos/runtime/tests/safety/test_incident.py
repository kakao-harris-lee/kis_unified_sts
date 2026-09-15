"""Tests for :mod:`tos_runtime.safety.incident` (lane W3-a2; plan §2 decision 2, INCIDENT
bullet). Fixtures are local to this file (shared-worktree convention — see this package's
top teammate brief: ``tests/safety/conftest.py`` belongs to lanes W3-a1/W3-c)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos_runtime.safety import incident as incident_module
from tos_runtime.safety.incident import IncidentConfigError, IncidentService
from tos_runtime.safety.ports import SafetyMeshService

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _write(path: Path, raw: dict[str, Any]) -> Path:
    file_path = path / "safety_incidents.yaml"
    file_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return file_path


def _active_set_body(
    *, members: list[dict[str, Any]], applicable_incident_ids: list[str]
) -> dict[str, Any]:
    return {
        "incidents": {
            "active_set": {
                "active_set_id": "set-1",
                "active_set_generation": 1,
                "incident_generation": 7,
                "safety_cell": "cell-1",
                "shared_dependencies": [],
                "is_complete": True,
                "is_current": True,
            },
            "applicable_incident_ids": applicable_incident_ids,
            "members": members,
        }
    }


NOMINAL_EMPTY = _active_set_body(members=[], applicable_incident_ids=[])

NOMINAL_ONE_CLOSED = _active_set_body(
    members=[
        {
            "incident_id": "inc-1",
            "lifecycle_state": "CLOSED",
            "shared_cause_ids": [],
        }
    ],
    applicable_incident_ids=["inc-1"],
)

ONE_OPEN_INCIDENT = _active_set_body(
    members=[
        {
            "incident_id": "inc-1",
            "lifecycle_state": "DECLARED",
            "shared_cause_ids": [],
        }
    ],
    applicable_incident_ids=["inc-1"],
)

MISMATCHED_APPLICABLE_SET = _active_set_body(
    members=[
        {
            "incident_id": "inc-1",
            "lifecycle_state": "CLOSED",
            "shared_cause_ids": [],
        }
    ],
    # declares a SECOND applicable incident that has no member — genuine drift.
    applicable_incident_ids=["inc-1", "inc-2"],
)


@pytest.fixture
def empty_incidents_path(tmp_path: Path) -> Path:
    return _write(tmp_path, NOMINAL_EMPTY)


@pytest.fixture
def one_closed_incident_path(tmp_path: Path) -> Path:
    return _write(tmp_path, NOMINAL_ONE_CLOSED)


@pytest.fixture
def one_open_incident_path(tmp_path: Path) -> Path:
    return _write(tmp_path, ONE_OPEN_INCIDENT)


@pytest.fixture
def mismatched_applicable_set_path(tmp_path: Path) -> Path:
    return _write(tmp_path, MISMATCHED_APPLICABLE_SET)


# ---------------------------------------------------------------------------
# loader refusals
# ---------------------------------------------------------------------------


def test_missing_file_refuses_to_load(tmp_path: Path) -> None:
    with pytest.raises(IncidentConfigError, match="not found"):
        IncidentService(config_path=tmp_path / "does_not_exist.yaml")


def test_not_a_mapping_refuses_to_load(tmp_path: Path) -> None:
    path = tmp_path / "safety_incidents.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(IncidentConfigError, match="top-level mapping"):
        IncidentService(config_path=path)


@pytest.mark.parametrize(
    "field_path",
    [
        ("active_set", "active_set_id"),
        ("active_set", "active_set_generation"),
        ("active_set", "incident_generation"),
        ("active_set", "safety_cell"),
        ("active_set", "shared_dependencies"),
        ("active_set", "is_complete"),
        ("active_set", "is_current"),
    ],
)
def test_a_still_null_active_set_field_refuses_to_load(
    tmp_path: Path, field_path: tuple[str, str]
) -> None:
    raw = json.loads(json.dumps(NOMINAL_EMPTY))
    section, key = field_path
    raw["incidents"][section][key] = None
    path = _write(tmp_path, raw)
    with pytest.raises(IncidentConfigError):
        IncidentService(config_path=path)


def test_null_applicable_incident_ids_refuses_to_load(tmp_path: Path) -> None:
    raw = json.loads(json.dumps(NOMINAL_EMPTY))
    raw["incidents"]["applicable_incident_ids"] = None
    path = _write(tmp_path, raw)
    with pytest.raises(IncidentConfigError, match="applicable_incident_ids"):
        IncidentService(config_path=path)


def test_null_members_refuses_to_load(tmp_path: Path) -> None:
    raw = json.loads(json.dumps(NOMINAL_EMPTY))
    raw["incidents"]["members"] = None
    path = _write(tmp_path, raw)
    with pytest.raises(IncidentConfigError, match="members"):
        IncidentService(config_path=path)


def test_member_missing_incident_id_refuses_to_load(tmp_path: Path) -> None:
    raw = json.loads(json.dumps(NOMINAL_EMPTY))
    raw["incidents"]["members"] = [{"lifecycle_state": "CLOSED"}]
    path = _write(tmp_path, raw)
    with pytest.raises(IncidentConfigError, match="incident_id"):
        IncidentService(config_path=path)


def test_member_invalid_lifecycle_state_refuses_to_load(tmp_path: Path) -> None:
    raw = json.loads(json.dumps(NOMINAL_EMPTY))
    raw["incidents"]["members"] = [
        {"incident_id": "inc-1", "lifecycle_state": "NOT_A_REAL_STATE"}
    ]
    path = _write(tmp_path, raw)
    with pytest.raises(IncidentConfigError, match="IncidentLifecycleState"):
        IncidentService(config_path=path)


def test_duplicate_incident_id_refuses_to_load(tmp_path: Path) -> None:
    raw = _active_set_body(
        members=[
            {"incident_id": "inc-1", "lifecycle_state": "CLOSED"},
            {"incident_id": "inc-1", "lifecycle_state": "CLOSED"},
        ],
        applicable_incident_ids=["inc-1"],
    )
    path = _write(tmp_path, raw)
    with pytest.raises(IncidentConfigError, match="duplicate"):
        IncidentService(config_path=path)


# ---------------------------------------------------------------------------
# nominal / negative clear() behavior
# ---------------------------------------------------------------------------


def test_empty_active_set_clears(empty_incidents_path: Path) -> None:
    service = IncidentService(config_path=empty_incidents_path)
    clearance = service.clear()
    assert clearance.clear is True
    assert clearance.reasons == ()


def test_one_closed_incident_clears(one_closed_incident_path: Path) -> None:
    service = IncidentService(config_path=one_closed_incident_path)
    clearance = service.clear()
    assert clearance.clear is True
    assert clearance.reasons == ()


def test_one_open_incident_denies(one_open_incident_path: Path) -> None:
    service = IncidentService(config_path=one_open_incident_path)
    clearance = service.clear()
    assert clearance.clear is False
    assert "dominating_open_incident_present" in clearance.reasons


def test_mismatched_applicable_set_denies(
    mismatched_applicable_set_path: Path,
) -> None:
    service = IncidentService(config_path=mismatched_applicable_set_path)
    clearance = service.clear()
    assert clearance.clear is False
    assert "active_set_is_canonical_union" in clearance.reasons


def test_clear_never_returns_none(one_open_incident_path: Path) -> None:
    """Module docstring "Tri-state note" — no injected external port exists here, so
    every input is either a loaded document field or a definite kernel-predicate call.
    """
    service = IncidentService(config_path=one_open_incident_path)
    assert service.clear().clear in (True, False)


# ---------------------------------------------------------------------------
# Protocol / dimension_report / describe
# ---------------------------------------------------------------------------


def test_service_satisfies_safety_mesh_service_protocol(
    empty_incidents_path: Path,
) -> None:
    service = IncidentService(config_path=empty_incidents_path)
    assert isinstance(service, SafetyMeshService)
    assert service.identity == "incident-service-sir-v1"


def test_dimension_report_reflects_clear(empty_incidents_path: Path) -> None:
    service = IncidentService(config_path=empty_incidents_path)
    report = service.dimension_report()
    assert report is not None
    assert report.bound_generation == 7
    assert report.positively_established is True
    assert report.restrictive_floor == 0


def test_dimension_report_reflects_denial(one_open_incident_path: Path) -> None:
    service = IncidentService(config_path=one_open_incident_path)
    report = service.dimension_report()
    assert report is not None
    assert report.positively_established is False


def test_describe_is_json_serializable_and_secret_free(
    empty_incidents_path: Path,
) -> None:
    service = IncidentService(config_path=empty_incidents_path)
    described = service.describe()
    dumped = json.dumps(described)
    for forbidden in ("token", "secret", "password", "key="):
        assert forbidden not in dumped.lower()
    assert described["active_set_id"] == "set-1"
    assert described["incident_generation"] == 7


# ---------------------------------------------------------------------------
# M1 mutation pin — a monkeypatched kernel predicate must flip the service's own verdict
# ---------------------------------------------------------------------------


def test_m1_mutation_dominating_predicate_negative_flips_service_false(
    one_closed_incident_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutation M1 (plan §5): a service that authored its own constant verdict instead of
    calling the kernel predicate would NOT observe this monkeypatch at all."""
    monkeypatch.setattr(
        incident_module, "dominating_open_incident_present", lambda _active_set: True
    )
    service = IncidentService(config_path=one_closed_incident_path)
    clearance = service.clear()
    assert clearance.clear is False
    assert "dominating_open_incident_present" in clearance.reasons


def test_m1_mutation_canonical_union_predicate_negative_flips_service_false(
    one_closed_incident_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        incident_module,
        "active_set_is_canonical_union",
        lambda _active_set, _applicable_incidents: False,
    )
    service = IncidentService(config_path=one_closed_incident_path)
    clearance = service.clear()
    assert clearance.clear is False
    assert "active_set_is_canonical_union" in clearance.reasons
