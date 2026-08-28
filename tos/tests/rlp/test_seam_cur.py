"""MANDATED test-only seam cross-check: cur RESTRICTED_LIVE_TRIAL dimension + TrialClaims ↔ rlp (§3.5/§7).

cur (ADR-002-024) owns the ``SafetyCurrentnessVector`` conditional ``RESTRICTED_LIVE_TRIAL`` dimension
(``cur/vocabulary.py:131-132`` — "the **conditional** dimension ... **RLP-deferred content**") and its
own ``TrialClaims`` 6-scalar value model (``cur/state.py:134-150``). cur **explicitly defers the
trial-content validation to RLP by name** (``state.py:140`` "deferred to RLP (``tos.rlp`` ...)"). rlp
owns that dimension's *generation content*; cur owns the vector-completeness axis (which dimension is
present) — **different axes**, edge 0. This file imports the real cur models as a **test**; the
import-closure test proves ``tos.cur`` is **absent** from the rlp runtime closure (and a rlp → cur
import would be a cycle since cur consumes rlp).

Regime tag: structural / coordinate predicate substrate only; RLP-EV-001 substrate; EV-L1-complete
claim forbidden.
"""

from __future__ import annotations

import tos.rlp as rlp
from tos.cur import CONDITIONAL_DIMENSION_KEYS, DimensionKey
from tos.cur import TrialClaims as CurTrialClaims
from tos.rlp import TrialClaimGroup


def test_cur_trial_claims_field_set_matches_rlp_anchor() -> None:
    """(§0.4b/§0.4h) cur TrialClaims 6-scalar == rlp TrialClaimGroup field set (design-time anchor)."""
    assert set(CurTrialClaims.model_fields) == set(TrialClaimGroup.model_fields)
    assert set(CurTrialClaims.model_fields) == set(TrialClaimGroup.REQUIRED_SCALARS)


def test_cur_restricted_live_trial_is_the_conditional_dimension() -> None:
    """(§0.4c) cur owns RESTRICTED_LIVE_TRIAL as the conditional (RLP-deferred-content) dimension.

    The dimension is the sole member outside cur's mandated floor — its *content* (what generation is
    carried) is RLP-owned; cur owns only whether the dimension is present in a vector (a different
    axis). rlp re-authors NO cur dimension vocabulary.
    """
    assert DimensionKey.RESTRICTED_LIVE_TRIAL in CONDITIONAL_DIMENSION_KEYS
    assert not hasattr(rlp, "DimensionKey")
    assert not hasattr(rlp, "SafetyCurrentnessVector")


def test_cur_trial_claims_all_optional_non_trial_leaves_none() -> None:
    """(§0.4b) cur TrialClaims is an all-optional value model — a non-trial vector leaves it None."""
    empty = CurTrialClaims()
    for name in CurTrialClaims.model_fields:
        assert getattr(empty, name) is None
    # rlp's mirror is likewise all-optional (the same 6-scalar shape).
    rlp_empty = TrialClaimGroup()
    for name in TrialClaimGroup.model_fields:
        assert getattr(rlp_empty, name) is None


def test_rlp_reauthors_no_cur_vector_completeness() -> None:
    """(§0.4c / §3.4) rlp re-authors NO cur vector-completeness (edge 0; a cur import would be a cycle)."""
    assert not hasattr(rlp, "vector_complete")
    assert not hasattr(rlp, "CurrentnessPolicy")
