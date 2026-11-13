"""MAJOR-1 required-covered completeness + MINOR-3 DRAFT strictness (design §3.2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.capsule import (
    ArtifactStatus,
    CriticalInputSnapshot,
    DecisionContextCapsule,
)
from tos.capsule._base import PolicyRef
from tos.capsule.capsule import CapsuleScope, SafetyCriticalFacts, SnapshotRef
from tos.capsule.consistency_cut import ConsistencyCut
from tos.capsule.predicates import capsule_can_authorize_new_risk
from tos.capsule.snapshot import SnapshotScope

from ._strategies import (
    SCHEME,
    capsule_required_kwargs,
    issue_capsule,
    issue_snapshot,
    snapshot_required_kwargs,
)


def test_bare_capsule_issue_rejected() -> None:
    """Issuing a capsule with no covered content is rejected (was fail-open)."""
    with pytest.raises(ValidationError):
        DecisionContextCapsule.issue(scheme=SCHEME)


def test_bare_snapshot_issue_rejected() -> None:
    """Issuing a snapshot with no covered content is rejected (was fail-open)."""
    with pytest.raises(ValidationError):
        CriticalInputSnapshot.issue(scheme=SCHEME)


def test_fully_populated_issue_succeeds() -> None:
    """A capsule/snapshot with every required field concrete issues cleanly."""
    cap = issue_capsule()
    snap = issue_snapshot()
    assert cap.missing_required_fields() == []
    assert snap.missing_required_fields() == []


@pytest.mark.parametrize(
    "override",
    [
        {"issuer_principal_id": None},
        {"critical_input_policy": PolicyRef(policy_id="p")},
        {"critical_input_snapshot": SnapshotRef(snapshot_id="s")},
        {"scope": CapsuleScope(environment="paper")},
        {
            "safety_critical_facts": SafetyCriticalFacts(
                account="a", instrument="i", direction="long", quantity_basis="c"
            )
        },
    ],
    ids=["issuer", "policy_digest", "snapshot_digest", "scope", "facts_unit"],
)
def test_capsule_missing_one_required_blocks_issuance(override: dict) -> None:
    """Dropping any single required capsule field blocks ISSUED (MAJOR-1, §3.2)."""
    with pytest.raises(ValidationError):
        DecisionContextCapsule.issue(
            scheme=SCHEME, **capsule_required_kwargs(**override)
        )


@pytest.mark.parametrize(
    "override",
    [
        {"issuer_principal_id": None},
        {"critical_input_policy": PolicyRef(policy_id="p")},
        {"scope": SnapshotScope(environment="paper")},
        {"intended_use": None},
        {"consistency_cut": ConsistencyCut()},
    ],
    ids=["issuer", "policy_digest", "scope", "intended_use", "cut_id"],
)
def test_snapshot_missing_one_required_blocks_issuance(override: dict) -> None:
    """Dropping any single required snapshot field blocks ISSUED (MAJOR-1, §3.2)."""
    with pytest.raises(ValidationError):
        CriticalInputSnapshot.issue(
            scheme=SCHEME, **snapshot_required_kwargs(**override)
        )


def test_authorize_fails_closed_when_required_absent() -> None:
    """A capsule missing required fields cannot authorize, even via model_construct."""
    bypassed = DecisionContextCapsule.model_construct(status=ArtifactStatus.ISSUED)
    assert bypassed.missing_required_fields() != []
    assert capsule_can_authorize_new_risk(bypassed) is False
    assert capsule_can_authorize_new_risk(issue_capsule()) is True


def test_draft_with_forged_digest_rejected() -> None:
    """A DRAFT carrying a non-null digest is rejected (MINOR-3)."""
    with pytest.raises(ValidationError):
        DecisionContextCapsule(status=ArtifactStatus.DRAFT, canonical_digest="forged")


def test_draft_with_forged_id_rejected() -> None:
    """A DRAFT carrying a non-null id is rejected (MINOR-3)."""
    with pytest.raises(ValidationError):
        DecisionContextCapsule(status=ArtifactStatus.DRAFT, capsule_id="dcc-forged")


def test_clean_draft_is_accepted() -> None:
    """A DRAFT with null digest and null id constructs (pre-issuance, §3.2)."""
    draft = DecisionContextCapsule(status=ArtifactStatus.DRAFT)
    assert draft.canonical_digest is None
    assert draft.capsule_id is None
