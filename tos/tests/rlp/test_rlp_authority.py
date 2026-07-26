"""All-false trial authority seal (design #25 §2.4/§6.4; RLP-INV-001).

Every rlp artifact carries an ``AllFalseTrialAuthority`` whose nine flags are forced ``False`` at
construction — a Trial Policy / Exact Trial Plan / Trial Run / Trial Evidence Package / Production
Scope Promotion Decision is verified data / a non-authorizing decision, not permission. Any ``True``
flag makes the artifact unconstructable; the predicate re-derives all-false so a ``model_construct``
bypass cannot smuggle a permissive block past a consumer (defence in depth).

Regime tag: authority substrate; RLP-EV-008 NOT_IMPLEMENTED (``EV-L2/3+Security``); EV-L1-complete
claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given
from tos.rlp import (
    AllFalseTrialAuthority,
    ArtifactIntegrityError,
    all_false_trial_authority,
)

from ._rlp_strategies import (
    clean_decision,
    clean_package,
    clean_plan,
    clean_policy,
    clean_run,
)

_FLAG_NAMES = tuple(AllFalseTrialAuthority.model_fields)


def test_default_authority_is_all_false() -> None:
    """(§6.4) The default AllFalseTrialAuthority has every flag False and passes the predicate."""
    authority = AllFalseTrialAuthority()
    assert all_false_trial_authority(authority) is True
    for name in _FLAG_NAMES:
        assert getattr(authority, name) is False


def test_nine_flags_present() -> None:
    """(§2.4) The authority block declares exactly the nine RLP-INV-001 flags."""
    assert set(_FLAG_NAMES) == {
        "creates_capacity",
        "creates_protection",
        "issues_live_authorization",
        "issues_capability",
        "transmits",
        "clears_halt",
        "re_arms",
        "grants_broker_permission",
        "classifies_protection",
    }


@given(flag=st.sampled_from(_FLAG_NAMES))
def test_any_true_flag_is_unconstructable(flag: str) -> None:
    """(§6.4 / RLP-INV-001) Setting any single authority flag True makes it unconstructable."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        AllFalseTrialAuthority(**{flag: True})


@given(flag=st.sampled_from(_FLAG_NAMES))
def test_predicate_recaught_model_construct_bypass(flag: str) -> None:
    """(§2.3 defence in depth) A model_construct permissive block is re-caught by the predicate."""
    permissive = AllFalseTrialAuthority.model_construct(**{flag: True})
    assert all_false_trial_authority(permissive) is False


def test_predicate_none_fails_closed() -> None:
    """(fail-closed) A None authority block ⇒ False."""
    assert all_false_trial_authority(None) is False


def test_every_artifact_carries_all_false_authority() -> None:
    """(§2.4) Every one of the five digest-bound artifacts carries an all-false authority."""
    for artifact in (
        clean_policy(),
        clean_plan(),
        clean_run(),
        clean_package(),
        clean_decision(),
    ):
        assert all_false_trial_authority(artifact.authority_effect) is True
