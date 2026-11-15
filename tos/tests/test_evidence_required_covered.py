"""Evidence required-covered + fail-closed issuance guards (design #4 §3.2/§6)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError
from tos.canonical import DigestBoundArtifact
from tos.evidence import (
    EvidenceCommitReceipt,
    EvidenceIntegrityPolicy,
    ReplayCapsule,
    ReplayResultState,
    SafetyEvidenceEnvelope,
)
from tos.evidence.elements import NondeterministicBoundary
from tos.evidence.replay import (
    ReplayDeterminism,
    ReplayExpected,
    ReplayInputs,
    ReplayResult,
)

from ._evidence_strategies import (
    SCHEME,
    eip_required_kwargs,
    envelope_required_kwargs,
    issue_replay,
    receipt_required_kwargs,
    replay_required_kwargs,
)
from ._required_covered import (
    assert_required_covered_non_vacuous,
    null_path,
    required_covered_cases,
)

_ARTIFACTS: list[tuple[type[DigestBoundArtifact], Callable[..., dict[str, Any]]]] = [
    (SafetyEvidenceEnvelope, envelope_required_kwargs),
    (EvidenceCommitReceipt, receipt_required_kwargs),
    (EvidenceIntegrityPolicy, eip_required_kwargs),
    (ReplayCapsule, replay_required_kwargs),
]


@pytest.mark.parametrize("cls,kwargs_fn,path", required_covered_cases(_ARTIFACTS))
def test_missing_required_covered_rejects_issuance(
    cls: type[DigestBoundArtifact], kwargs_fn: Callable[..., dict[str, Any]], path: str
) -> None:
    """Dropping any required covered path makes an ISSUED artifact unconstructable (§3.2)."""
    kwargs = null_path(kwargs_fn(), path)
    with pytest.raises(ValidationError):
        cls.issue(scheme=SCHEME, **kwargs)


def test_every_artifact_has_non_vacuous_required_covered() -> None:
    """No digest-bound evidence artifact has an empty _REQUIRED_COVERED (MAJOR-1 guard)."""
    assert_required_covered_non_vacuous(_ARTIFACTS)


def test_degenerate_empty_replay_capsule_rejected() -> None:
    """An empty ReplayCapsule (no baseline/inputs/expected) cannot be ISSUED (§6.2/§15)."""
    with pytest.raises(ValidationError):
        ReplayCapsule.issue(scheme=SCHEME, replay_capsule_id="rc-empty")


def test_replay_missing_input_binding_rejected() -> None:
    """A capsule with baseline+expected but no bound raw evidence digest is rejected."""
    kwargs = {**replay_required_kwargs(), "inputs": ReplayInputs()}
    with pytest.raises(ValidationError):
        ReplayCapsule.issue(scheme=SCHEME, **kwargs)


def test_degenerate_empty_eip_rejected() -> None:
    """An empty EIP (no integrity serialization identifiers) cannot be ISSUED (§3.5)."""
    with pytest.raises(ValidationError):
        EvidenceIntegrityPolicy.issue(scheme=SCHEME, policy_id="eip-empty")


def test_false_match_with_unbounded_nondeterminism_rejected() -> None:
    """result.state=MATCH under an unbounded boundary is unconstructable (ERI-INV-009)."""
    with pytest.raises(ValidationError):
        issue_replay(
            result=ReplayResult(state=ReplayResultState.MATCH),
            determinism=ReplayDeterminism(
                documented_nondeterministic_boundaries=(
                    NondeterministicBoundary(boundary_id="b", bounded=False),
                )
            ),
        )


def test_false_match_missing_expected_digest_rejected() -> None:
    """result.state=MATCH without an expected end-state digest is unconstructable (§6.1)."""
    with pytest.raises(ValidationError):
        issue_replay(
            result=ReplayResult(state=ReplayResultState.MATCH),
            expected=ReplayExpected(state_digest=None),
        )


def test_honest_match_is_constructable() -> None:
    """A MATCH with all boundaries bounded + expected digest + baseline is allowed."""
    capsule = issue_replay(
        result=ReplayResult(state=ReplayResultState.MATCH),
        determinism=ReplayDeterminism(
            documented_nondeterministic_boundaries=(
                NondeterministicBoundary(boundary_id="b", bounded=True),
            )
        ),
    )
    assert capsule.result.state is ReplayResultState.MATCH


def test_non_match_state_not_constrained_by_match_invariant() -> None:
    """A DIVERGED result with an unbounded boundary is fine (only MATCH is fail-closed)."""
    capsule = issue_replay(
        result=ReplayResult(state=ReplayResultState.DIVERGED),
        determinism=ReplayDeterminism(
            documented_nondeterministic_boundaries=(
                NondeterministicBoundary(boundary_id="b", bounded=False),
            )
        ),
    )
    assert capsule.result.state is ReplayResultState.DIVERGED
