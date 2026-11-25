"""All-false currentness authority (design #23 §6.13/§7; CUR-INV-005)."""

from __future__ import annotations

import pytest
from tos.cur import (
    AllFalseCurrentnessAuthority,
    ArtifactIntegrityError,
    CurrentnessPolicy,
    EgressCurrentnessProof,
    RestrictiveFenceRecord,
    SafetyCurrentnessVector,
    all_false_currentness_authority,
)

from ._cur_strategies import clean_fence, clean_policy, clean_proof, clean_vector

_AUTHORITY_FLAGS = (
    "approves",
    "mutates_capacity",
    "releases_capacity",
    "issues_authority",
    "issues_capability",
    "classifies_protection",
    "transmits",
    "clears_halt",
    "re_arms",
)


def test_default_authority_is_all_false() -> None:
    """(§6.13) The default AllFalseCurrentnessAuthority has every flag False."""
    effect = AllFalseCurrentnessAuthority()
    for flag in _AUTHORITY_FLAGS:
        assert getattr(effect, flag) is False


@pytest.mark.parametrize("flag", _AUTHORITY_FLAGS)
def test_any_true_authority_flag_is_unconstructable(flag: str) -> None:
    """(§6.13) Any True authority flag makes AllFalseCurrentnessAuthority unconstructable."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        AllFalseCurrentnessAuthority(**{flag: True})


def test_every_artifact_carries_all_false() -> None:
    """(§6.13) vector / proof / fence / policy carry all-false authority."""
    artifacts = (clean_vector(), clean_proof(), clean_fence(), clean_policy())
    for artifact in artifacts:
        effect = artifact.authority_effect
        for flag in _AUTHORITY_FLAGS:
            assert getattr(effect, flag) is False


def test_all_false_predicate_both_ways() -> None:
    """(§6.13 predicate) The predicate confirms an all-false block; None fails closed."""
    assert all_false_currentness_authority(AllFalseCurrentnessAuthority()) is True
    assert all_false_currentness_authority(None) is False


def test_all_false_predicate_catches_model_construct_bypass() -> None:
    """(§2.3 defence-in-depth) A model_construct block with a True flag is caught by the predicate."""
    smuggled = AllFalseCurrentnessAuthority.model_construct(transmits=True)
    assert all_false_currentness_authority(smuggled) is False


def test_artifact_classes_are_independent_id() -> None:
    """(§2.1) All four artifacts are IndependentIdArtifact (id ⊥ digest) for conflict detection."""
    from tos.cur import IndependentIdArtifact

    for cls in (
        SafetyCurrentnessVector,
        EgressCurrentnessProof,
        RestrictiveFenceRecord,
        CurrentnessPolicy,
    ):
        assert issubclass(cls, IndependentIdArtifact)
