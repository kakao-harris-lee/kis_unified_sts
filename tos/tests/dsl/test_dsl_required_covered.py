"""Required-covered fail-open suite for the DSL digest-bound artifacts (★1; design §2/§6).

This is the DSL analogue of ``test_evidence_required_covered.py`` — the negative
suite that closes the "empty/degenerate artifact reaches ISSUED" fail-open (the
family that had three prior implementations REJECTED in review). The shared
``issue_*`` fixtures always fill the required covered set, so without this suite the
issuance guard would never be exercised.

For every digest-bound DSL artifact — ``AuthoredStrategy``, ``Proposal``,
``NoActionOutcome``, ``PortfolioVector``, ``AdmissibilityResult``,
``CapabilityManifest``, ``BoundOutcome`` — this asserts:

1. **★1 required-covered**: dropping any single ``_REQUIRED_COVERED`` path makes an
   ISSUED artifact unconstructable (a degenerate artifact passing ISSUED would be
   the evidence-ReplayCapsule fail-open isomorph).
2. **non-vacuous guard**: no artifact has an empty ``_REQUIRED_COVERED`` (an empty
   set is itself the fail-open — this test *fails* if a model regresses to it).
3. **bare-issue rejection**: issuing with no covered content is rejected.
4. **positive**: each ``issue_*`` fixture is genuinely complete (no all-null coverage
   illusion) — ``missing_required_fields() == []``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError
from tos.dsl import (
    AdmissibilityResult,
    AuthoredStrategy,
    BoundOutcome,
    CapabilityManifest,
    NoActionOutcome,
    PortfolioVector,
    Proposal,
)

from ._dsl_strategies import (
    SCHEME,
    admissibility_result_required_kwargs,
    bound_outcome_required_kwargs,
    capability_manifest_required_kwargs,
    issue_admissibility_result,
    issue_bound_outcome,
    issue_capability_manifest,
    issue_no_action,
    issue_proposal,
    issue_strategy,
    issue_vector,
    no_action_required_kwargs,
    proposal_required_kwargs,
    strategy_required_kwargs,
    vector_required_kwargs,
)

# (artifact class, kwargs builder) — the digest-bound artifacts under test.
_ARTIFACTS: list[tuple[type, Callable[..., dict[str, Any]]]] = [
    (AuthoredStrategy, strategy_required_kwargs),
    (Proposal, proposal_required_kwargs),
    (NoActionOutcome, no_action_required_kwargs),
    (PortfolioVector, vector_required_kwargs),
    (AdmissibilityResult, admissibility_result_required_kwargs),
    (CapabilityManifest, capability_manifest_required_kwargs),
    (BoundOutcome, bound_outcome_required_kwargs),
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
    """Dropping any required covered path makes an ISSUED artifact unconstructable (★1; design §2)."""
    kwargs = _null_path(kwargs_fn(), path)
    with pytest.raises(ValidationError):
        cls.issue(scheme=SCHEME, **kwargs)  # type: ignore[attr-defined]


def test_every_digest_bound_artifact_has_non_vacuous_required_covered() -> None:
    """No DSL digest-bound artifact has an empty _REQUIRED_COVERED (the fail-open itself)."""
    for cls, _ in _ARTIFACTS:
        assert cls._REQUIRED_COVERED, f"{cls.__name__} has a vacuous _REQUIRED_COVERED"


@pytest.mark.parametrize("cls", [cls for cls, _ in _ARTIFACTS])
def test_bare_issue_is_rejected(cls: type) -> None:
    """Issuing an artifact with no covered content is rejected (no empty artifact reaches ISSUED)."""
    with pytest.raises(ValidationError):
        cls.issue(scheme=SCHEME)  # type: ignore[attr-defined]


def test_issue_fixtures_are_genuinely_complete() -> None:
    """Every issued fixture fills its required covered set (not an all-null coverage illusion)."""
    for artifact in (
        issue_strategy(),
        issue_proposal(),
        issue_no_action(),
        issue_vector(),
        issue_admissibility_result(),
        issue_capability_manifest(),
        issue_bound_outcome(),
    ):
        assert artifact.missing_required_fields() == []


# ---------------------------------------------------------------------------
# Non-empty rationale — the completeness guard treats "" as concrete, so a set-
# but-empty rationale would satisfy the required-rationale obligation vacuously.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_no_action_rejects_empty_rationale(blank: str) -> None:
    """A No-Action with a blank rationale is unconstructable (vacuous satisfaction)."""
    with pytest.raises(ValidationError):
        issue_no_action(rationale=blank)


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_proposal_rejects_empty_rationale(blank: str) -> None:
    """A Proposal with a blank rationale is unconstructable (vacuous satisfaction)."""
    with pytest.raises(ValidationError):
        issue_proposal(rationale=blank)
