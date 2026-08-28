"""All-false deviation authority — any True flag is unconstructable (design #26 §2.4/§6/§7; WDR-INV-001).

A Safety Deviation Policy / Request / Decision / Residual-Risk Acceptance Record / Active Deviation Set
creates **no** authority (WDR-INV-001 line 148 + §1 line 21). Every one of the 11 flags defaults False;
any ``True`` flag makes the block unconstructable; the ``all_false_deviation_authority`` predicate
re-derives the property (defence in depth against a ``model_construct`` bypass).

Regime tag: all-false authority substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
import tos.wdr as w
from hypothesis import given
from hypothesis import strategies as st

_FLAGS = tuple(w.AllFalseDeviationAuthority.model_fields)


def test_default_all_false_constructs() -> None:
    """(§2.4) The default authority block is all-false and constructs; the predicate confirms it."""
    auth = w.AllFalseDeviationAuthority()
    assert w.all_false_deviation_authority(auth) is True
    assert all(getattr(auth, name) is False for name in _FLAGS)


def test_eleven_flags_verbatim() -> None:
    """(§2.4 / WDR-INV-001 line 148) The authority carries exactly the 11 verbatim flags (over/under)."""
    assert set(_FLAGS) == {
        "creates_capacity",
        "creates_protection",
        "creates_safety_authority",
        "issues_live_authorization",
        "creates_capability",
        "transmits",
        "clears_halt",
        "creates_production_scope",
        "re_arms",
        "grants_broker_permission",
        "classifies_protection",
    }
    assert len(_FLAGS) == 11


@pytest.mark.parametrize("flag", _FLAGS)
def test_any_true_flag_is_unconstructable(flag: str) -> None:
    """(WDR-INV-001) Any single True authority flag makes the block unconstructable."""
    with pytest.raises((w.ArtifactIntegrityError, ValueError)):
        w.AllFalseDeviationAuthority(**{flag: True})


def test_none_block_denies() -> None:
    """(§6) all_false_deviation_authority: a None block ⇒ False (fail-closed)."""
    assert w.all_false_deviation_authority(None) is False


@pytest.mark.parametrize("flag", _FLAGS)
def test_model_construct_bypass_recaught_by_predicate(flag: str) -> None:
    """(§2.3 defence in depth) A model_construct'd True flag is re-caught by the predicate ⇒ False."""
    smuggled = w.AllFalseDeviationAuthority.model_construct(**{flag: True})
    assert w.all_false_deviation_authority(smuggled) is False


def test_every_artifact_carries_all_false_authority() -> None:
    """(§2.4) Every one of the five artifacts defaults an all-false authority_effect."""
    from ._wdr_strategies import (
        clean_acceptance,
        clean_active_set,
        clean_decision,
        clean_policy,
        clean_request,
    )

    for artifact in (
        clean_policy(),
        clean_request(),
        clean_decision(),
        clean_acceptance(),
        clean_active_set(),
    ):
        assert w.all_false_deviation_authority(artifact.authority_effect) is True


@given(flags=st.lists(st.sampled_from(_FLAGS), min_size=1, max_size=3, unique=True))
def test_any_subset_of_true_flags_unconstructable(flags: list[str]) -> None:
    """(WDR-INV-001) Any non-empty subset of True flags is unconstructable (property)."""
    with pytest.raises((w.ArtifactIntegrityError, ValueError)):
        w.AllFalseDeviationAuthority(**dict.fromkeys(flags, True))
