"""Strategy-output-semantics property tests — SOS-EV-001..006 (design §6.3; ADR-DEV-007).

* **SOS-EV-001**: No-Action and an Explicit-Flat Proposal are **distinct** non-null
  types with opposite exposure — never conflated, never an error/null/omission.
* **SOS-EV-002/003**: a Portfolio Vector is a **set** of per-instrument Proposals
  with **no** union / aggregate-authority field (realized by that field's absence).
* **SOS-EV-004**: each target binds a Capsule and is wildcard-free; the Proposal
  Builder rejects a wildcard / 'latest' account or instrument.
* **SOS-EV-005**: every Outcome carries an all-false authority block; any true flag
  is unconstructable.
* **SOS-EV-006**: an undeclared vector is atomic (fail-closed); an atomic partial
  approval yields whole-vector non-realization + required re-evaluation — never a
  silent naked partial.

★ fail-open guards: **★3 vacuous-True** (an empty vector is unconstructable);
**★5 SOS-INV-005** true-flag authority is unconstructable.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given
from pydantic import ValidationError
from tos.dsl import (
    FLAT_QUANTITY_BASIS,
    WILDCARD_TOKENS,
    AllFalseAuthority,
    NoActionOutcome,
    PortfolioVector,
    Proposal,
    Proposer,
    TargetKind,
    VectorInterdependence,
    VectorRealization,
    build_flat,
    build_proposal,
    resolve_vector_realization,
)

from ._dsl_strategies import (
    SCHEME,
    capref,
    issue_capsule,
    issue_no_action,
    issue_proposal,
    issue_vector,
)

_FLAG_NAMES = tuple(AllFalseAuthority.model_fields)
_PROPOSER = Proposer(strategy_id="astrat-1", strategy_version="digest-1")


def _build_flat(**overrides: object) -> Proposal:
    base: dict[str, object] = {
        "scheme": SCHEME,
        "proposer": _PROPOSER,
        "account": "acct-1",
        "instrument": "ES",
        "direction": "SELL",
        "position_effect": "CLOSE",
        "rationale": "exit",
        "decision_context_capsule": capref(),
        "dsl_version": "dsl-0",
        "config_version": "cfg-v1",
    }
    base.update(overrides)
    return build_flat(**base)  # type: ignore[arg-type]


def _build_action(**overrides: object) -> Proposal:
    base: dict[str, object] = {
        "scheme": SCHEME,
        "proposer": _PROPOSER,
        "account": "acct-1",
        "instrument": "ES",
        "direction": "LONG",
        "position_effect": "OPEN",
        "quantity_basis": "RISK",
        "rationale": "edge present",
        "decision_context_capsule": capref(),
        "dsl_version": "dsl-0",
        "config_version": "cfg-v1",
    }
    base.update(overrides)
    return build_proposal(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# SOS-EV-001 — No-Action ≠ Explicit-Flat
# ---------------------------------------------------------------------------


def test_no_action_and_explicit_flat_are_distinct_non_null_types() -> None:
    """No-Action and Explicit-Flat are distinct, recorded, opposite-exposure outcomes (SOS-EV-001)."""
    na = issue_no_action()
    flat = _build_flat()

    assert type(na) is NoActionOutcome
    assert type(flat) is Proposal
    assert not isinstance(na, Proposal)
    assert not isinstance(flat, NoActionOutcome)

    # Both are non-null and recorded (reproducible), never an error / omission.
    assert na.outcome_id is not None
    assert flat.proposal_id is not None

    # Opposite exposure: a flat is a zero-position ACTION-shaped proposal; a
    # no-action leaves exposure and carries no target/quantity vocabulary at all.
    assert flat.target_kind is TargetKind.FLAT
    assert flat.quantity_basis == FLAT_QUANTITY_BASIS
    assert not hasattr(na, "target_kind")
    assert not hasattr(na, "quantity_basis")


def test_action_proposal_cannot_use_flat_quantity_basis() -> None:
    """An ACTION proposal using the zero-position basis is an Explicit Flat — rejected (SOS-INV-001)."""
    with pytest.raises(ValidationError):
        _build_action(quantity_basis=FLAT_QUANTITY_BASIS)


# ---------------------------------------------------------------------------
# SOS-EV-002/003 — Portfolio Vector is a set, with no aggregate authority
# ---------------------------------------------------------------------------


def test_portfolio_vector_is_a_set_of_proposals_without_aggregate_authority() -> None:
    """A vector is a set of per-instrument Proposals; no union/aggregate field exists (SOS-EV-002/003)."""
    vector = issue_vector()
    assert len(vector.components) >= 2
    assert all(isinstance(component, Proposal) for component in vector.components)

    fields = set(PortfolioVector.model_fields)
    forbidden_aggregate_fields = {
        "union",
        "aggregate",
        "aggregated_authority",
        "aggregate_authority",
        "combined_authority",
        "combined",
        "total_authority",
        "union_authority",
    }
    assert forbidden_aggregate_fields.isdisjoint(fields)  # SOS-INV-003 by absence
    assert {"components", "interdependence"} <= fields


def test_vector_rejects_duplicate_per_instrument_targets() -> None:
    """A vector is a set of *distinct* per-instrument targets (SOS-INV-002)."""
    ref = capref()
    component = issue_proposal(instrument="ES", decision_context_capsule=ref)
    with pytest.raises(ValidationError):
        issue_vector(components=(component, component), decision_context_capsule=ref)


def test_vector_components_must_bind_the_same_capsule() -> None:
    """A vector is one coherent evaluation — components binding a different Capsule reject (SOS-INV-003)."""
    ref1 = capref()
    ref2 = capref(issue_capsule(issuer_principal_id="principal-2"))
    assert ref1.capsule_id != ref2.capsule_id
    comp1 = issue_proposal(instrument="ES", decision_context_capsule=ref1)
    comp2 = issue_proposal(instrument="NQ", decision_context_capsule=ref2)
    with pytest.raises(ValidationError):
        issue_vector(components=(comp1, comp2), decision_context_capsule=ref1)


def test_empty_vector_is_unconstructable() -> None:
    """An empty vector is not a portfolio decision — unconstructable (★3 vacuous-True)."""
    with pytest.raises(ValidationError):
        issue_vector(components=())


# ---------------------------------------------------------------------------
# SOS-EV-004 — targets are wildcard-free and Capsule-bound
# ---------------------------------------------------------------------------


def test_each_vector_target_is_capsule_bound_and_wildcard_free() -> None:
    """Every component binds a Capsule and names no wildcard scope (SOS-EV-004)."""
    vector = issue_vector()
    for component in vector.components:
        assert component.decision_context_capsule.capsule_id is not None
        assert "*" not in (component.account or "")
        assert "*" not in (component.instrument or "")


@given(token=st.sampled_from(sorted(WILDCARD_TOKENS)))
def test_proposal_builder_rejects_wildcard_account(token: str) -> None:
    """The effect-free builder rejects a wildcard / 'latest' account (SOS-INV-004)."""
    with pytest.raises(ValidationError):
        _build_action(account=token)


@given(token=st.sampled_from(sorted(WILDCARD_TOKENS)))
def test_proposal_builder_rejects_wildcard_instrument(token: str) -> None:
    """The effect-free builder rejects a wildcard / 'latest' instrument (SOS-INV-004)."""
    with pytest.raises(ValidationError):
        _build_action(instrument=token)


# ---------------------------------------------------------------------------
# SOS-EV-005 — every Outcome authority block is all-false
# ---------------------------------------------------------------------------


def test_default_authority_is_all_false() -> None:
    """The authored authority block defaults every flag to false (SOS-EV-005)."""
    authority = AllFalseAuthority()
    assert _FLAG_NAMES  # non-vacuous: there are flags to check
    assert all(getattr(authority, flag) is False for flag in _FLAG_NAMES)


@given(flag=st.sampled_from(_FLAG_NAMES))
def test_any_true_authority_flag_is_unconstructable(flag: str) -> None:
    """Setting any single authority flag true is rejected (★5 SOS-INV-005)."""
    with pytest.raises(ValidationError):
        AllFalseAuthority(**{flag: True})


def test_every_outcome_carries_all_false_authority() -> None:
    """A Proposal, No-Action, and Vector all carry an all-false authority block (SOS-EV-005)."""
    for artifact in (issue_proposal(), issue_no_action(), issue_vector()):
        for flag in _FLAG_NAMES:
            assert getattr(artifact.authority, flag) is False


# ---------------------------------------------------------------------------
# SOS-EV-006 — interdependence default + partial-approval transition
# ---------------------------------------------------------------------------


def test_undeclared_interdependence_defaults_to_atomic() -> None:
    """An undeclared vector is atomic (fail-closed default; SOS-EV-006)."""
    vector = issue_vector(interdependence=None)
    assert vector.interdependence is None
    assert vector.effective_interdependence() is VectorInterdependence.ATOMIC


def test_atomic_partial_approval_yields_whole_vector_non_realization() -> None:
    """An atomic vector with a rejected component is wholly non-realized — no silent partial (SOS-EV-006)."""
    vector = issue_vector(interdependence=VectorInterdependence.ATOMIC)
    keys = [(c.account, c.instrument) for c in vector.components]
    resolution = resolve_vector_realization(vector, frozenset({keys[0]}))
    assert resolution.realization is VectorRealization.WHOLE_VECTOR_NON_REALIZATION
    assert resolution.reevaluation_required is True
    assert resolution.proceeding_targets == ()  # never a silent naked partial
    assert keys[0] in resolution.rejected_targets


def test_undeclared_atomic_partial_approval_fails_closed() -> None:
    """The fail-closed default (undeclared ⇒ atomic) forces whole-vector non-realization (SOS-EV-006)."""
    vector = issue_vector(interdependence=None)
    keys = [(c.account, c.instrument) for c in vector.components]
    resolution = resolve_vector_realization(vector, frozenset({keys[0]}))
    assert resolution.realization is VectorRealization.WHOLE_VECTOR_NON_REALIZATION
    assert resolution.reevaluation_required is True


def test_independent_partial_approval_lets_non_rejected_proceed() -> None:
    """A declared-independent vector lets its non-rejected components proceed (SOS-EV-006)."""
    vector = issue_vector(interdependence=VectorInterdependence.INDEPENDENT)
    keys = [(c.account, c.instrument) for c in vector.components]
    resolution = resolve_vector_realization(vector, frozenset({keys[0]}))
    assert resolution.realization is VectorRealization.NON_REJECTED_COMPONENTS_PROCEED
    assert resolution.reevaluation_required is False
    assert keys[1] in resolution.proceeding_targets
    assert keys[0] in resolution.rejected_targets


def test_no_rejection_lets_all_components_proceed() -> None:
    """With no rejection every component proceeds and no re-evaluation is required (SOS-EV-006)."""
    vector = issue_vector()
    resolution = resolve_vector_realization(vector, frozenset())
    assert resolution.realization is VectorRealization.ALL_COMPONENTS_PROCEED
    assert resolution.reevaluation_required is False
    assert resolution.rejected_targets == ()
