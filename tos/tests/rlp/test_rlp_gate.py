"""gate_status_separated yolk (RLP-EV-012) — status separation (design #25 §5.4).

The yolk 4 property suite: ∅-seal, nine-stage explicit (no inferred stage), no-implication, and
readiness ≠ authority — plus the nine-stage anchor.

Regime tag: structural / separation predicate substrate only; RLP-EV-012 NOT_IMPLEMENTED
(``EV-L1/3``); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given
from tos.rlp import (
    AllFalseTrialAuthority,
    ArtifactIntegrityError,
    GateStatusLadder,
    all_false_trial_authority,
    gate_status_separated,
    no_status_implication,
    readiness_not_authority,
)

from ._rlp_strategies import clean_ladder

#: The §26 RLP-AC-012 line 680 nine-stage ladder, transcribed by hand (design #25 §0.4h).
_STAGE_ANCHOR: tuple[str, ...] = (
    "evl0_review",
    "adr_accepted",
    "plan_eligible",
    "evl5_complete",
    "promotion_eligible",
    "config_activated",
    "live_authorized",
    "restricted_live_ready",
    "production_ready",
)


def test_stage_anchor_matches_model() -> None:
    """(§7.2 anchor drift) The nine STAGE_FIELDS == the §26 line 680 reference set, and are model fields."""
    assert GateStatusLadder.STAGE_FIELDS == _STAGE_ANCHOR
    for name in _STAGE_ANCHOR:
        assert name in GateStatusLadder.model_fields


def test_empty_seal() -> None:
    """(§5.4 point 1) None ladder denies."""
    assert gate_status_separated(None) is False
    assert no_status_implication(None) is False
    assert readiness_not_authority(None) is False


def test_clean_ladder_is_separated() -> None:
    """(§5.4 positive) A ladder with all nine explicit stages + all-false authority is separated."""
    assert gate_status_separated(clean_ladder()) is True


@given(dropped=st.sampled_from(list(_STAGE_ANCHOR)))
def test_any_inferred_stage_denies(dropped: str) -> None:
    """(§5.4 point 2) A None (inferred / implied) stage denies — every stage must be explicit."""
    ladder = clean_ladder(**{dropped: None})
    assert no_status_implication(ladder) is False
    assert gate_status_separated(ladder) is False


@given(
    plan_eligible=st.booleans(),
    live_authorized=st.booleans(),
    promotion_eligible=st.booleans(),
    production_ready=st.booleans(),
)
def test_stages_are_independent_no_implication(
    plan_eligible: bool,
    live_authorized: bool,
    promotion_eligible: bool,
    production_ready: bool,
) -> None:
    """(§5.4 point 3) Every explicit-bool combination is separated — no stage implies another.

    In particular ``plan_eligible=True, live_authorized=False`` and
    ``promotion_eligible=True, production_ready=False`` are both valid separated ladders (a trial
    status never masquerades as a production status).
    """
    ladder = clean_ladder(
        plan_eligible=plan_eligible,
        live_authorized=live_authorized,
        promotion_eligible=promotion_eligible,
        production_ready=production_ready,
    )
    assert gate_status_separated(ladder) is True


def test_readiness_carries_no_authority() -> None:
    """(§5.4 point 4) restricted_live_ready / production_ready True still carry an all-false authority."""
    ladder = clean_ladder(restricted_live_ready=True, production_ready=True)
    assert readiness_not_authority(ladder) is True
    assert gate_status_separated(ladder) is True


def test_non_all_false_authority_denies_via_model_construct() -> None:
    """(§5.4 point 4 / §2.3) A model_construct ladder with a permissive authority fails readiness."""
    permissive = AllFalseTrialAuthority.model_construct(transmits=True)
    malformed = GateStatusLadder.model_construct(
        **dict.fromkeys(_STAGE_ANCHOR, False), authority_effect=permissive
    )
    assert all_false_trial_authority(permissive) is False
    assert readiness_not_authority(malformed) is False
    assert gate_status_separated(malformed) is False


def test_true_authority_flag_unconstructable() -> None:
    """(RLP-INV-001) A ladder authority with any True flag is unconstructable on the normal path."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        GateStatusLadder(authority_effect=AllFalseTrialAuthority(transmits=True))
