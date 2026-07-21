"""Evidence required-covered + fail-closed issuance guards (design #4 §3.2/§6).

This is the evidence analogue of the capsule ``test_required_covered.py`` — the
negative suite the review found missing (MAJOR-3): the ``issue_*`` fixtures always
fill the required covered set, so the issuance guard was never exercised and a
degenerate ReplayCapsule slipped through (MAJOR-1). Each test drops a required
binding and asserts that issuance is **rejected**, and covers the ReplayCapsule
fail-closed cross-field invariants (MAJOR-1 empty capsule, MAJOR-2 false MATCH).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError
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

_ARTIFACTS: list[tuple[type, Callable[..., dict[str, Any]]]] = [
    (SafetyEvidenceEnvelope, envelope_required_kwargs),
    (EvidenceCommitReceipt, receipt_required_kwargs),
    (EvidenceIntegrityPolicy, eip_required_kwargs),
    (ReplayCapsule, replay_required_kwargs),
]


def _null_path(kwargs: dict[str, Any], path: str) -> dict[str, Any]:
    """Return ``kwargs`` with the (possibly one-level-nested) dotted ``path`` nulled."""
    out = dict(kwargs)
    if "." in path:
        block, field = path.split(".", 1)
        value = out[block]
        assert isinstance(value, BaseModel), f"expected a model block at {block!r}"
        out[block] = value.model_copy(update={field: None})
    else:
        out[path] = None
    return out


def _cases() -> list[Any]:
    """Yield one param per (artifact, required covered path)."""
    cases: list[Any] = []
    for cls, kwargs_fn in _ARTIFACTS:
        for path in cls._REQUIRED_COVERED:  # type: ignore[attr-defined]
            cases.append(
                pytest.param(cls, kwargs_fn, path, id=f"{cls.__name__}:{path}")
            )
    return cases


@pytest.mark.parametrize("cls,kwargs_fn,path", _cases())
def test_missing_required_covered_rejects_issuance(
    cls: type, kwargs_fn: Callable[..., dict[str, Any]], path: str
) -> None:
    """Dropping any required covered path makes an ISSUED artifact unconstructable (§3.2)."""
    kwargs = _null_path(kwargs_fn(), path)
    with pytest.raises(ValidationError):
        cls.issue(scheme=SCHEME, **kwargs)  # type: ignore[attr-defined]


def test_every_artifact_has_non_vacuous_required_covered() -> None:
    """No digest-bound evidence artifact has an empty _REQUIRED_COVERED (MAJOR-1 guard)."""
    for cls, _ in _ARTIFACTS:
        assert cls._REQUIRED_COVERED, f"{cls.__name__} has a vacuous _REQUIRED_COVERED"


# ---- MAJOR-1: degenerate empty capsules are rejected -----------------------


def test_degenerate_empty_replay_capsule_rejected() -> None:
    """An empty ReplayCapsule (no baseline/inputs/expected) cannot be ISSUED (§6.2/§15)."""
    with pytest.raises(ValidationError):
        ReplayCapsule.issue(scheme=SCHEME, replay_capsule_id="rc-empty")


def test_replay_missing_input_binding_rejected() -> None:
    """A capsule with baseline+expected but no bound raw evidence digest is rejected."""
    kwargs = {**replay_required_kwargs(), "inputs": ReplayInputs()}  # no digests
    with pytest.raises(ValidationError):
        ReplayCapsule.issue(scheme=SCHEME, **kwargs)


def test_degenerate_empty_eip_rejected() -> None:
    """An empty EIP (no integrity serialization identifiers) cannot be ISSUED (§3.5)."""
    with pytest.raises(ValidationError):
        EvidenceIntegrityPolicy.issue(scheme=SCHEME, policy_id="eip-empty")


# ---- MAJOR-2: a stored false MATCH is unconstructable ----------------------


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
