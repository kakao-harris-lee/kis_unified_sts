"""Shared fixtures for the W3-a1 safety-mesh service tests.

Every fixture writes REAL (non-null) YAML documents to ``tmp_path`` — the
checked-in ``tos/runtime/config/safety_*.example.yaml`` files stay all-null
(named-TBD) on purpose; only test fixtures carry concrete values (project
convention — see ``tos/runtime/tests/compose/conftest.py``'s own 17-dimension
/ 3-attestation fixtures for the precedent this mirrors).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.time import HealthState

# ---------------------------------------------------------------------------
# tos_runtime.safety.profile — SafetyProfileService fixtures
# ---------------------------------------------------------------------------

#: A clean, mutually-consistent, within-envelope envelope/profile/activation
#: triple (mirrors the spg property-test "clean fixture" discipline —
#: tos/tests/spg/_spg_strategies.py's own docstring: genuinely within-
#: envelope / unit-compatible, never a permissive shortcut).
NOMINAL_ENVELOPE: dict[str, Any] = {
    "envelope": {
        "envelope_id": "env-1",
        "envelope_generation": 1,
        "envelope_version": {
            "version": "e1",
            "effective_date": "2026-09-01",
            "evidence_package_version": "ep-1",
            "approver_identity": "approver-1",
            "expiration_or_revalidation_date": "2027-09-01",
            "superseded_version_link": None,
            "change_classification": None,
        },
        "governed_dimensions": [
            {
                "dimension": "qty",
                "envelope_max": "1000",
                "unit": "sh",
                "multiplier": "1",
                "sign": "+",
                "precision": "2",
                "rounding": "HALF_UP",
                "boundary": "INCLUSIVE",
            }
        ],
        "permitted_scope": ["KOSPI"],
        "prohibited_fallbacks": [],
        "residual_risk_ceiling": "500",
        "evidence_package_ref": "evref-1",
    }
}

NOMINAL_PROFILE: dict[str, Any] = {
    "profile": {
        "profile_id": "prof-1",
        "profile_generation": 1,
        "profile_version": {
            "version": "p1",
            "effective_date": "2026-09-01",
            "evidence_package_version": "ep-1",
            "approver_identity": "approver-1",
            "expiration_or_revalidation_date": "2027-09-01",
            "superseded_version_link": None,
            "change_classification": None,
        },
        "target_envelope_id": "env-1",
        "target_envelope_generation": 1,
        "governed_dimensions": [
            {
                "dimension": "qty",
                "profile_value": "500",
                "unit": "sh",
                "multiplier": "1",
                "sign": "+",
                "precision": "2",
                "rounding": "HALF_UP",
                "boundary": "INCLUSIVE",
            }
        ],
        "scope": ["KOSPI"],
        "permitted_behaviors": [],
        "fallback_rules": [],
        "evidence_package_ref": "evref-1",
    }
}

NOMINAL_ACTIVATION: dict[str, Any] = {
    "activation": {
        "activation_id": "act-1",
        "profile_generation": 1,
        "envelope_digest": None,
        "profile_digest": None,
        "bundle_digest": None,
        "scope": ["KOSPI"],
        "approval_ids": ["approval-1"],
        "compatibility_attestation_refs": ["attest-1"],
        "predecessor_generation": 0,
        "restrictive_generation_effects": [],
    },
    "not_expired": True,
}


def _write(path: Path, name: str, raw: dict[str, Any]) -> Path:
    file_path = path / name
    file_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return file_path


@pytest.fixture
def nominal_profile_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Paths to a clean, mutually-consistent envelope/profile/activation triple."""
    return (
        _write(tmp_path, "safety_envelope.yaml", NOMINAL_ENVELOPE),
        _write(tmp_path, "safety_profile.yaml", NOMINAL_PROFILE),
        _write(tmp_path, "safety_activation.yaml", NOMINAL_ACTIVATION),
    )


class TrustedTimeSource:
    """A :class:`~tos_runtime.safety.profile.TimeHealthSource` fake reporting a fixed
    health state — never a real clock (this test suite is hermetic)."""

    def __init__(self, state: HealthState) -> None:
        self._state = state

    def health_state(self) -> HealthState:
        return self._state


@pytest.fixture
def trusted_time_source() -> TrustedTimeSource:
    return TrustedTimeSource(HealthState.TRUSTED)


@pytest.fixture
def untrusted_time_source() -> TrustedTimeSource:
    return TrustedTimeSource(HealthState.UNTRUSTED)


# ---------------------------------------------------------------------------
# tos_runtime.safety.deviation — DeviationService fixtures
# ---------------------------------------------------------------------------

NOMINAL_DEVIATIONS_ONE_MEMBER: dict[str, Any] = {
    "deviations": {
        "active_set": {
            "active_set_id": "set-1",
            "active_set_generation": 1,
            "deviation_generation": 1,
            "is_complete": True,
            "combined_within_envelope": True,
        },
        "applicable_decision_ids": ["dev-1"],
        "members": [
            {
                "decision_id": "dev-1",
                "classification": "WAIVABLE_ELIGIBLE",
                "applicability_resolved": True,
                "boundary_hits": [],
                "revoke_generation": None,
                "send_generation": None,
            }
        ],
    }
}

NOMINAL_DEVIATIONS_EMPTY: dict[str, Any] = {
    "deviations": {
        "active_set": {
            "active_set_id": "set-1",
            "active_set_generation": 1,
            "deviation_generation": 1,
            "is_complete": True,
            "combined_within_envelope": True,
        },
        "applicable_decision_ids": [],
        "members": [],
    }
}


@pytest.fixture
def nominal_deviations_path(tmp_path: Path) -> Path:
    """A clean Active Deviation Set with one WAIVABLE_ELIGIBLE member."""
    return _write(tmp_path, "safety_deviations.yaml", NOMINAL_DEVIATIONS_ONE_MEMBER)


@pytest.fixture
def empty_deviations_path(tmp_path: Path) -> Path:
    """The valid explicit-empty Active Deviation Set (no active deviations)."""
    return _write(tmp_path, "safety_deviations.yaml", NOMINAL_DEVIATIONS_EMPTY)
