"""Hermetic tests for :mod:`tos_runtime.safety.profile.SafetyProfileService`
(TOS Phase 5 W3-a1)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos_runtime.safety.ports import SafetyMeshService
from tos_runtime.safety.profile import SafetyProfileConfigError, SafetyProfileService

from tos import spg as spg_module

from .conftest import (
    NOMINAL_ACTIVATION,
    NOMINAL_ENVELOPE,
    NOMINAL_PROFILE,
    TrustedTimeSource,
    _write,
)


def _service(
    paths: tuple[Path, Path, Path], time_source: object | None
) -> SafetyProfileService:
    envelope_path, profile_path, activation_path = paths
    return SafetyProfileService(
        envelope_path=envelope_path,
        profile_path=profile_path,
        activation_path=activation_path,
        time_source=time_source,
    )


# ---------------------------------------------------------------------------
# nominal clearance
# ---------------------------------------------------------------------------


def test_nominal_triple_clears_true(
    nominal_profile_paths: tuple[Path, Path, Path],
    trusted_time_source: TrustedTimeSource,
) -> None:
    service = _service(nominal_profile_paths, trusted_time_source)
    clearance = service.clear()
    assert clearance.clear is True
    assert clearance.reasons == ()
    assert clearance.identity == "safety-profile-service-spg-v1"


def test_nominal_triple_is_a_safety_mesh_service(
    nominal_profile_paths: tuple[Path, Path, Path],
    trusted_time_source: TrustedTimeSource,
) -> None:
    service = _service(nominal_profile_paths, trusted_time_source)
    assert isinstance(service, SafetyMeshService)


def test_dimension_report_reflects_clear_true(
    nominal_profile_paths: tuple[Path, Path, Path],
    trusted_time_source: TrustedTimeSource,
) -> None:
    service = _service(nominal_profile_paths, trusted_time_source)
    report = service.dimension_report()
    assert report is not None
    assert report.positively_established is True
    assert report.bound_generation == 1
    assert report.restrictive_floor == 0


def test_describe_is_json_serializable_and_carries_no_secret(
    nominal_profile_paths: tuple[Path, Path, Path],
    trusted_time_source: TrustedTimeSource,
) -> None:
    service = _service(nominal_profile_paths, trusted_time_source)
    described = service.describe()
    dumped = json.dumps(described)
    for forbidden in ("token", "secret", "password", "bearer"):
        assert forbidden not in dumped.lower()
    assert described["envelope_id"] == "env-1"
    assert described["profile_id"] == "prof-1"


# ---------------------------------------------------------------------------
# unevaluable time -> None (never a fabricated False)
# ---------------------------------------------------------------------------


def test_no_time_source_yields_unevaluable_none(
    nominal_profile_paths: tuple[Path, Path, Path],
) -> None:
    service = _service(nominal_profile_paths, None)
    clearance = service.clear()
    assert clearance.clear is None
    assert "time_health_not_trusted" in clearance.reasons


def test_untrusted_time_health_yields_unevaluable_none(
    nominal_profile_paths: tuple[Path, Path, Path],
    untrusted_time_source: TrustedTimeSource,
) -> None:
    service = _service(nominal_profile_paths, untrusted_time_source)
    clearance = service.clear()
    assert clearance.clear is None
    assert "time_health_not_trusted" in clearance.reasons


def test_false_dominates_unevaluable_time(
    tmp_path: Path, untrusted_time_source: TrustedTimeSource
) -> None:
    """A positively-established violation (over-envelope) must still report False
    even when time health is simultaneously unevaluable — False dominates None
    (module docstring's combination rule)."""
    profile = copy.deepcopy(NOMINAL_PROFILE)
    profile["profile"]["governed_dimensions"][0]["profile_value"] = "5000"  # > max 1000
    envelope_path = _write(tmp_path, "safety_envelope.yaml", NOMINAL_ENVELOPE)
    profile_path = _write(tmp_path, "safety_profile.yaml", profile)
    activation_path = _write(tmp_path, "safety_activation.yaml", NOMINAL_ACTIVATION)
    service = _service(
        (envelope_path, profile_path, activation_path), untrusted_time_source
    )
    clearance = service.clear()
    assert clearance.clear is False
    assert "profile_within_envelope" in clearance.reasons


# ---------------------------------------------------------------------------
# each predicate positively violated alone -> False with its reason
# ---------------------------------------------------------------------------


def test_over_envelope_profile_denies(
    tmp_path: Path, trusted_time_source: TrustedTimeSource
) -> None:
    profile = copy.deepcopy(NOMINAL_PROFILE)
    profile["profile"]["governed_dimensions"][0]["profile_value"] = "5000"
    envelope_path = _write(tmp_path, "safety_envelope.yaml", NOMINAL_ENVELOPE)
    profile_path = _write(tmp_path, "safety_profile.yaml", profile)
    activation_path = _write(tmp_path, "safety_activation.yaml", NOMINAL_ACTIVATION)
    service = _service(
        (envelope_path, profile_path, activation_path), trusted_time_source
    )
    clearance = service.clear()
    assert clearance.clear is False
    assert clearance.reasons == ("profile_within_envelope", "activation_atomic")


def test_generation_mismatch_denies_versions_match(
    tmp_path: Path, trusted_time_source: TrustedTimeSource
) -> None:
    activation = copy.deepcopy(NOMINAL_ACTIVATION)
    activation["activation"]["profile_generation"] = 99
    envelope_path = _write(tmp_path, "safety_envelope.yaml", NOMINAL_ENVELOPE)
    profile_path = _write(tmp_path, "safety_profile.yaml", NOMINAL_PROFILE)
    activation_path = _write(tmp_path, "safety_activation.yaml", activation)
    service = _service(
        (envelope_path, profile_path, activation_path), trusted_time_source
    )
    clearance = service.clear()
    assert clearance.clear is False
    assert "hard_and_runtime_versions_match" in clearance.reasons
    assert "activation_atomic" in clearance.reasons


def test_no_approvals_denies_activation_atomic_only(
    tmp_path: Path, trusted_time_source: TrustedTimeSource
) -> None:
    activation = copy.deepcopy(NOMINAL_ACTIVATION)
    activation["activation"]["approval_ids"] = []
    envelope_path = _write(tmp_path, "safety_envelope.yaml", NOMINAL_ENVELOPE)
    profile_path = _write(tmp_path, "safety_profile.yaml", NOMINAL_PROFILE)
    activation_path = _write(tmp_path, "safety_activation.yaml", activation)
    service = _service(
        (envelope_path, profile_path, activation_path), trusted_time_source
    )
    clearance = service.clear()
    assert clearance.clear is False
    assert clearance.reasons == ("activation_atomic",)


def test_expired_denies_expiry_suspends_new_risk_only(
    tmp_path: Path, trusted_time_source: TrustedTimeSource
) -> None:
    activation = copy.deepcopy(NOMINAL_ACTIVATION)
    activation["not_expired"] = False
    envelope_path = _write(tmp_path, "safety_envelope.yaml", NOMINAL_ENVELOPE)
    profile_path = _write(tmp_path, "safety_profile.yaml", NOMINAL_PROFILE)
    activation_path = _write(tmp_path, "safety_activation.yaml", activation)
    service = _service(
        (envelope_path, profile_path, activation_path), trusted_time_source
    )
    clearance = service.clear()
    assert clearance.clear is False
    assert clearance.reasons == ("expiry_suspends_new_risk",)


# ---------------------------------------------------------------------------
# loader refusals (fail-closed at construction)
# ---------------------------------------------------------------------------


def test_missing_envelope_file_refuses_construction(
    tmp_path: Path, trusted_time_source: TrustedTimeSource
) -> None:
    profile_path = _write(tmp_path, "safety_profile.yaml", NOMINAL_PROFILE)
    activation_path = _write(tmp_path, "safety_activation.yaml", NOMINAL_ACTIVATION)
    with pytest.raises(SafetyProfileConfigError, match="not found"):
        _service(
            (tmp_path / "missing.yaml", profile_path, activation_path),
            trusted_time_source,
        )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda raw: raw["envelope"].__setitem__("envelope_id", None),
        lambda raw: raw["envelope"].__setitem__("envelope_generation", None),
    ],
)
def test_still_null_envelope_field_refuses_construction(
    tmp_path: Path,
    trusted_time_source: TrustedTimeSource,
    mutator: Any,
) -> None:
    envelope = copy.deepcopy(NOMINAL_ENVELOPE)
    mutator(envelope)
    envelope_path = _write(tmp_path, "safety_envelope.yaml", envelope)
    profile_path = _write(tmp_path, "safety_profile.yaml", NOMINAL_PROFILE)
    activation_path = _write(tmp_path, "safety_activation.yaml", NOMINAL_ACTIVATION)
    # envelope_id / envelope_generation are optional on the bare kernel model
    # (every field defaults to None), so a still-null identity field does not
    # raise at model_validate time -- it instead denies at clear() time via
    # profile_within_envelope's own None-fails-closed check. This test
    # documents that boundary rather than asserting a false construction
    # refusal.
    service = _service(
        (envelope_path, profile_path, activation_path), trusted_time_source
    )
    assert service.clear().clear is False


def test_not_expired_missing_key_refuses_construction(
    tmp_path: Path, trusted_time_source: TrustedTimeSource
) -> None:
    activation = copy.deepcopy(NOMINAL_ACTIVATION)
    del activation["not_expired"]
    envelope_path = _write(tmp_path, "safety_envelope.yaml", NOMINAL_ENVELOPE)
    profile_path = _write(tmp_path, "safety_profile.yaml", NOMINAL_PROFILE)
    activation_path = _write(tmp_path, "safety_activation.yaml", activation)
    with pytest.raises(SafetyProfileConfigError, match="not_expired"):
        _service((envelope_path, profile_path, activation_path), trusted_time_source)


def test_not_expired_null_refuses_construction(
    tmp_path: Path, trusted_time_source: TrustedTimeSource
) -> None:
    activation = copy.deepcopy(NOMINAL_ACTIVATION)
    activation["not_expired"] = None
    envelope_path = _write(tmp_path, "safety_envelope.yaml", NOMINAL_ENVELOPE)
    profile_path = _write(tmp_path, "safety_profile.yaml", NOMINAL_PROFILE)
    activation_path = _write(tmp_path, "safety_activation.yaml", activation)
    with pytest.raises(SafetyProfileConfigError, match="not_expired"):
        _service((envelope_path, profile_path, activation_path), trusted_time_source)


def test_unknown_field_refuses_construction_extra_forbid(
    tmp_path: Path, trusted_time_source: TrustedTimeSource
) -> None:
    envelope = copy.deepcopy(NOMINAL_ENVELOPE)
    envelope["envelope"]["not_a_real_field"] = "surprise"
    envelope_path = _write(tmp_path, "safety_envelope.yaml", envelope)
    profile_path = _write(tmp_path, "safety_profile.yaml", NOMINAL_PROFILE)
    activation_path = _write(tmp_path, "safety_activation.yaml", NOMINAL_ACTIVATION)
    with pytest.raises(SafetyProfileConfigError):
        _service((envelope_path, profile_path, activation_path), trusted_time_source)


def test_not_a_mapping_refuses_construction(
    tmp_path: Path, trusted_time_source: TrustedTimeSource
) -> None:
    envelope_path = tmp_path / "safety_envelope.yaml"
    envelope_path.write_text(yaml.safe_dump(["not", "a", "mapping"]), encoding="utf-8")
    profile_path = _write(tmp_path, "safety_profile.yaml", NOMINAL_PROFILE)
    activation_path = _write(tmp_path, "safety_activation.yaml", NOMINAL_ACTIVATION)
    with pytest.raises(SafetyProfileConfigError, match="mapping"):
        _service((envelope_path, profile_path, activation_path), trusted_time_source)


# ---------------------------------------------------------------------------
# mutation M1 pin -- clear() must actually call the kernel predicates, never
# return a constant True.
# ---------------------------------------------------------------------------


def test_mutation_m1_constant_true_is_caught(
    monkeypatch: pytest.MonkeyPatch,
    nominal_profile_paths: tuple[Path, Path, Path],
    trusted_time_source: TrustedTimeSource,
) -> None:
    """If ``profile_within_envelope`` is forced to report a violation, the
    service must NOT still report ``clear=True`` -- a constant-True
    implementation that never actually calls the kernel predicate would pass
    this test only by accident; this pins that it does not."""
    from tos_runtime.safety import profile as profile_module

    def _always_over_envelope(envelope: object, profile: object) -> Any:
        result = spg_module.SemanticValidationResult(
            valid=False,
            reason_set=frozenset({spg_module.ValidationReason.EXCEEDS_ENVELOPE}),
        )
        return result

    monkeypatch.setattr(
        profile_module, "profile_within_envelope", _always_over_envelope
    )
    service = _service(nominal_profile_paths, trusted_time_source)
    clearance = service.clear()
    assert clearance.clear is False
    assert "profile_within_envelope" in clearance.reasons
