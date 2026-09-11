"""Shared fixtures for the W3-a1/W3-c safety-mesh tests.

Every fixture writes REAL (non-null) YAML documents to ``tmp_path`` — the
checked-in ``tos/runtime/config/safety_*.example.yaml`` files stay all-null
(named-TBD) on purpose; only test fixtures carry concrete values (project
convention — see ``tos/runtime/tests/compose/conftest.py``'s own 17-dimension
/ 3-attestation fixtures for the precedent this mirrors).

The bottom section (lane W3-c) adds the ``tos_runtime.safety.latch`` /
``tos_runtime.safety.rearm`` test doubles — kept in the same file, appended
rather than replacing the W3-a1 fixtures above (shared-worktree file: this
lane owns ``safety/{latch,rearm}.py`` and adds only what its own tests need).
"""

from __future__ import annotations

import os
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


# ---------------------------------------------------------------------------
# tos_runtime.safety.latch / tos_runtime.safety.rearm — W3-c fixtures
# ---------------------------------------------------------------------------

from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore  # noqa: E402


class FixedKeyProvider:
    """A :class:`~tos_runtime.evidence.store.KeyProvider` test double — fixed bytes
    (mirrors ``tos/runtime/tests/evidence/conftest.py``'s own double)."""

    def __init__(
        self, key_generation: int = 1, key: bytes = b"safety-test-fixed-key-bytes"
    ) -> None:
        self._key_generation = key_generation
        self._key = key

    def current(self) -> tuple[int, bytes]:
        return (self._key_generation, self._key)


@pytest.fixture
def key_provider() -> KeyProvider:
    return FixedKeyProvider()


@pytest.fixture
def evidence_store(tmp_path: Path, key_provider: KeyProvider) -> SqliteEvidenceStore:
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=key_provider
    )
    yield instance
    instance.close()


@pytest.fixture
def expected_owner_uid() -> int:
    return os.getuid()


class FakeNewRiskHaltInbox:
    """A :class:`~tos_runtime.safety.latch.NewRiskHaltReader`-shaped, and
    ``SqliteEventInbox.new_risk_halt``-shaped, double: a settable
    ``current`` row (or ``None``)."""

    def __init__(self, current: dict[str, object] | None = None) -> None:
        self.current = current

    def new_risk_halt(self) -> dict[str, object] | None:
        return self.current


class FakeTimeService:
    """A minimal ``TrustworthyTimeService``-shaped double — :class:`~tos_runtime
    .safety.rearm.ReArmWorkflow` never actually consults it (hag reads no clock),
    so this double need not reproduce the real FSM (mirrors ``tos/runtime/tests
    /authority/conftest.py``'s own ``FakeTimeService`` rationale)."""


def write_rearm_roster_file(
    approvals_dir: Path,
    *,
    principal_ids: list[str],
    control_edges: list[dict[str, str]] | None = None,
    unresolved_control: bool = False,
    environment_label: str = "non-live-test",
    mode: int = 0o600,
) -> Path:
    """Write ``approvals/rearm/roster.yaml`` — the operator-authored
    effective-principal roster (:mod:`tos_runtime.safety.rearm` module
    docstring, independent-review HIGH-3 disposition).

    Defaults (``control_edges=None`` -> ``[]``, ``unresolved_control=False``)
    describe genuinely distinct, unconnected principals; a caller passes an
    edge connecting two ``principal_ids`` (or ``unresolved_control=True``) to
    exercise a refusal.
    """
    path = approvals_dir / "rearm" / "roster.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "environment_label": environment_label,
                "principals": [{"id": principal_id} for principal_id in principal_ids],
                "control_edges": control_edges or [],
                "unresolved_control": unresolved_control,
            },
            sort_keys=False,
        )
    )
    os.chmod(path, mode)
    return path


def write_rearm_approval_file(
    approvals_dir: Path,
    *,
    latched_evidence_seq: int,
    environment_label: str = "non-live-test",
    approvals: list[dict[str, str]] | None = None,
    mode: int = 0o600,
    write_roster: bool = True,
    roster_control_edges: list[dict[str, str]] | None = None,
    roster_unresolved_control: bool = False,
) -> Path:
    """Write one ``approvals/rearm/<latched_evidence_seq>.yaml`` two-person
    decision file (:mod:`tos_runtime.safety.rearm` module docstring).

    Defaults to a genuinely satisfying two-distinct-principal ``APPROVE`` pair;
    a caller mutates ``approvals`` to exercise a refusal (one entry, a
    duplicate principal, a ``DENY``, etc).

    Also writes a matching ``roster.yaml`` (:func:`write_rearm_roster_file`,
    ``principal_ids`` derived from ``approvals`` — a genuinely independent
    default roster) unless ``write_roster=False``, so every EXISTING caller
    keeps working unchanged after the HIGH-3 disposition (the roster is no
    longer optional — :mod:`tos_runtime.safety.rearm` refuses without one).
    Pass ``write_roster=False`` and call :func:`write_rearm_roster_file`
    explicitly to exercise a roster-specific refusal (a collapsing edge, an
    unresolved roster, a missing roster, an approver absent from the roster).
    """
    if approvals is None:
        approvals = [
            {"principal_id": "alice", "decision": "APPROVE"},
            {"principal_id": "bob", "decision": "APPROVE"},
        ]
    if write_roster:
        write_rearm_roster_file(
            approvals_dir,
            principal_ids=sorted({entry["principal_id"] for entry in approvals}),
            control_edges=roster_control_edges,
            unresolved_control=roster_unresolved_control,
            environment_label=environment_label,
            mode=mode,
        )
    path = approvals_dir / "rearm" / f"{latched_evidence_seq}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "environment_label": environment_label,
                "latched_evidence_seq": latched_evidence_seq,
                "approvals": approvals,
            },
            sort_keys=False,
        )
    )
    os.chmod(path, mode)
    return path
