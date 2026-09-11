"""Hermetic tests for :mod:`tos_runtime.safety.deviation.DeviationService`
(TOS Phase 5 W3-a1)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml
from tos_runtime.safety.deviation import DeviationConfigError, DeviationService
from tos_runtime.safety.ports import SafetyMeshService

from .conftest import NOMINAL_DEVIATIONS_ONE_MEMBER, _write


def _service(path: Path) -> DeviationService:
    return DeviationService(deviations_path=path)


# ---------------------------------------------------------------------------
# nominal clearance
# ---------------------------------------------------------------------------


def test_one_admissible_member_clears_true(nominal_deviations_path: Path) -> None:
    service = _service(nominal_deviations_path)
    clearance = service.clear()
    assert clearance.clear is True
    assert clearance.reasons == ()
    assert clearance.identity == "deviation-service-wdr-v1"


def test_explicit_empty_set_clears_true(empty_deviations_path: Path) -> None:
    """The kernel's own v1.1 MAJOR-1 fix: an explicit empty Active Deviation Set is
    the valid canonical "no deviations" representation, never rejected."""
    service = _service(empty_deviations_path)
    clearance = service.clear()
    assert clearance.clear is True
    assert clearance.reasons == ()


def test_is_a_safety_mesh_service(nominal_deviations_path: Path) -> None:
    assert isinstance(_service(nominal_deviations_path), SafetyMeshService)


def test_dimension_report_reflects_clear_true(nominal_deviations_path: Path) -> None:
    report = _service(nominal_deviations_path).dimension_report()
    assert report is not None
    assert report.positively_established is True
    assert report.bound_generation == 1
    assert report.restrictive_floor == 0


def test_describe_is_json_serializable_and_carries_no_secret(
    nominal_deviations_path: Path,
) -> None:
    described = _service(nominal_deviations_path).describe()
    dumped = json.dumps(described)
    for forbidden in ("token", "secret", "password", "bearer"):
        assert forbidden not in dumped.lower()
    assert described["active_set_id"] == "set-1"
    assert described["member_decision_ids"] == ["dev-1"]


# ---------------------------------------------------------------------------
# each violation alone -> False with its reason
# ---------------------------------------------------------------------------


def test_omitted_applicable_deviation_denies_combined_set(tmp_path: Path) -> None:
    raw = copy.deepcopy(NOMINAL_DEVIATIONS_ONE_MEMBER)
    raw["deviations"]["applicable_decision_ids"] = ["dev-1", "dev-2"]
    path = _write(tmp_path, "safety_deviations.yaml", raw)
    clearance = _service(path).clear()
    assert clearance.clear is False
    assert "combined_set_no_permissive_union" in clearance.reasons


def test_incomplete_set_denies_combined_set(tmp_path: Path) -> None:
    raw = copy.deepcopy(NOMINAL_DEVIATIONS_ONE_MEMBER)
    raw["deviations"]["active_set"]["is_complete"] = False
    path = _write(tmp_path, "safety_deviations.yaml", raw)
    clearance = _service(path).clear()
    assert clearance.clear is False
    assert clearance.reasons == ("combined_set_no_permissive_union",)


def test_not_within_envelope_denies_combined_set(tmp_path: Path) -> None:
    raw = copy.deepcopy(NOMINAL_DEVIATIONS_ONE_MEMBER)
    raw["deviations"]["active_set"]["combined_within_envelope"] = False
    path = _write(tmp_path, "safety_deviations.yaml", raw)
    clearance = _service(path).clear()
    assert clearance.clear is False
    assert clearance.reasons == ("combined_set_no_permissive_union",)


@pytest.mark.parametrize("classification", ["NON_WAIVABLE", "UNRESOLVED"])
def test_non_waivable_member_denies_classification(
    tmp_path: Path, classification: str
) -> None:
    raw = copy.deepcopy(NOMINAL_DEVIATIONS_ONE_MEMBER)
    raw["deviations"]["members"][0]["classification"] = classification
    path = _write(tmp_path, "safety_deviations.yaml", raw)
    clearance = _service(path).clear()
    assert clearance.clear is False
    assert clearance.reasons == ("unresolved_is_non_waivable_or_not_admissible",)


def test_unresolved_applicability_denies_classification(tmp_path: Path) -> None:
    raw = copy.deepcopy(NOMINAL_DEVIATIONS_ONE_MEMBER)
    raw["deviations"]["members"][0]["applicability_resolved"] = False
    path = _write(tmp_path, "safety_deviations.yaml", raw)
    clearance = _service(path).clear()
    assert clearance.clear is False
    assert clearance.reasons == ("unresolved_is_non_waivable_or_not_admissible",)


def test_boundary_hit_denies_classification(tmp_path: Path) -> None:
    raw = copy.deepcopy(NOMINAL_DEVIATIONS_ONE_MEMBER)
    raw["deviations"]["members"][0]["boundary_hits"] = ["fail_closed_unknown"]
    path = _write(tmp_path, "safety_deviations.yaml", raw)
    clearance = _service(path).clear()
    assert clearance.clear is False
    assert clearance.reasons == ("unresolved_is_non_waivable_or_not_admissible",)


def test_unproven_revocation_order_denies_revocation_check(tmp_path: Path) -> None:
    """A member declaring a revocation in progress but no send_generation to prove
    ordering against is NOT a clean denial in the kernel's own eyes (it stays
    "potentially live") -- so this service must not clear it."""
    raw = copy.deepcopy(NOMINAL_DEVIATIONS_ONE_MEMBER)
    raw["deviations"]["members"][0]["revoke_generation"] = 5
    raw["deviations"]["members"][0]["send_generation"] = None
    path = _write(tmp_path, "safety_deviations.yaml", raw)
    clearance = _service(path).clear()
    assert clearance.clear is False
    assert clearance.reasons == ("revocation_dominates_send",)


def test_revocation_before_send_clears(tmp_path: Path) -> None:
    raw = copy.deepcopy(NOMINAL_DEVIATIONS_ONE_MEMBER)
    raw["deviations"]["members"][0]["revoke_generation"] = 1
    raw["deviations"]["members"][0]["send_generation"] = 5
    path = _write(tmp_path, "safety_deviations.yaml", raw)
    clearance = _service(path).clear()
    assert clearance.clear is True
    assert clearance.reasons == ()


def test_send_before_revocation_denies(tmp_path: Path) -> None:
    raw = copy.deepcopy(NOMINAL_DEVIATIONS_ONE_MEMBER)
    raw["deviations"]["members"][0]["revoke_generation"] = 5
    raw["deviations"]["members"][0]["send_generation"] = 1
    path = _write(tmp_path, "safety_deviations.yaml", raw)
    clearance = _service(path).clear()
    assert clearance.clear is False
    assert clearance.reasons == ("revocation_dominates_send",)


# ---------------------------------------------------------------------------
# loader refusals
# ---------------------------------------------------------------------------


def test_missing_file_refuses_construction(tmp_path: Path) -> None:
    with pytest.raises(DeviationConfigError, match="not found"):
        _service(tmp_path / "missing.yaml")


def test_null_deviations_key_refuses_construction(tmp_path: Path) -> None:
    path = _write(tmp_path, "safety_deviations.yaml", {"deviations": None})
    with pytest.raises(DeviationConfigError, match="deviations"):
        _service(path)


def test_null_members_list_refuses_construction(tmp_path: Path) -> None:
    raw = copy.deepcopy(NOMINAL_DEVIATIONS_ONE_MEMBER)
    raw["deviations"]["members"] = None
    path = _write(tmp_path, "safety_deviations.yaml", raw)
    with pytest.raises(DeviationConfigError, match="members"):
        _service(path)


def test_null_active_set_generation_refuses_construction(tmp_path: Path) -> None:
    raw = copy.deepcopy(NOMINAL_DEVIATIONS_ONE_MEMBER)
    raw["deviations"]["active_set"]["deviation_generation"] = None
    path = _write(tmp_path, "safety_deviations.yaml", raw)
    with pytest.raises(DeviationConfigError, match="deviation_generation"):
        _service(path)


def test_bad_classification_value_refuses_construction(tmp_path: Path) -> None:
    raw = copy.deepcopy(NOMINAL_DEVIATIONS_ONE_MEMBER)
    raw["deviations"]["members"][0]["classification"] = "NOT_A_REAL_VALUE"
    path = _write(tmp_path, "safety_deviations.yaml", raw)
    with pytest.raises(DeviationConfigError):
        _service(path)


def test_not_a_mapping_refuses_construction(tmp_path: Path) -> None:
    path = tmp_path / "safety_deviations.yaml"
    path.write_text(yaml.safe_dump(["not", "a", "mapping"]), encoding="utf-8")
    with pytest.raises(DeviationConfigError, match="mapping"):
        _service(path)


# ---------------------------------------------------------------------------
# mutation M1 pin
# ---------------------------------------------------------------------------


def test_mutation_m1_constant_true_is_caught(
    monkeypatch: pytest.MonkeyPatch, nominal_deviations_path: Path
) -> None:
    from tos_runtime.safety import deviation as deviation_module

    monkeypatch.setattr(
        deviation_module,
        "combined_set_no_permissive_union",
        lambda *_args, **_kwargs: False,
    )
    clearance = _service(nominal_deviations_path).clear()
    assert clearance.clear is False
    assert "combined_set_no_permissive_union" in clearance.reasons
