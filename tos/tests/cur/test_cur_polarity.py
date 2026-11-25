"""Polarity exhaustive regression — None ⇒ deny convergence (design #23 §4.3 / #22 MAJOR-2 seal)."""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.cur import (
    DimensionKey,
    dimension_positively_established,
    expiry_denies_future_use_only,
    proof_admissible,
    recovery_revives_nothing,
)

from ._cur_strategies import (
    TRIBOOL,
    clean_coordinates,
    clean_dimension,
    clean_proof,
    clean_revision,
)


@given(established=TRIBOOL)
def test_positively_established_only_true_clears(established: bool | None) -> None:
    """(§4.3 positive) positively_established: only True clears; None / False deny."""
    rev = clean_revision()
    dim = clean_dimension(
        dimension_key=DimensionKey.CONTEXT,
        revision=rev,
        positively_established=established,
    )
    assert dimension_positively_established(dim) is (established is True)


@given(latch=TRIBOOL)
def test_local_latch_clear_only_true_admits(latch: bool | None) -> None:
    """(§4.3 positive / §5.7) local_latch_clear: only True admits; None / False deny."""
    proof = clean_proof(coordinates=clean_coordinates(local_latch_clear=latch))
    assert proof_admissible(proof) is (latch is True)


@given(consumed=TRIBOOL)
def test_single_use_consumed_only_false_admits(consumed: bool | None) -> None:
    """(§4.3 negative / v1.1 MAJOR-3) single_use_consumed: only explicit False admits; None denies."""
    proof = clean_proof(single_use_consumed=consumed)
    assert proof_admissible(proof) is (consumed is False)


@given(expired=TRIBOOL)
def test_is_expired_only_false_admits(expired: bool | None) -> None:
    """(§4.3 negative / §6.10) is_expired: only explicit False admits; None / True deny future use."""
    proof = clean_proof(is_expired=expired)
    assert proof_admissible(proof) is (expired is False)
    assert expiry_denies_future_use_only(expired) is (expired is not False)


@given(is_recovery=TRIBOOL, latch=TRIBOOL)
def test_recovery_revives_nothing(is_recovery: bool | None, latch: bool | None) -> None:
    """(§6.12 / §4.3) A recovery event revives nothing; otherwise only a True prior latch stays clear."""
    result = recovery_revives_nothing(is_recovery, latch)
    if is_recovery is True:
        assert result is False
    else:
        assert result is (latch is True)


@given(
    consumed=st.sampled_from([None, True]),
    expired=st.sampled_from([None, True]),
)
def test_any_negative_none_or_true_denies_admission(
    consumed: bool | None, expired: bool | None
) -> None:
    """(§4.3 exhaustive) Any negative-polarity None / True on the proof ⇒ inadmissible."""
    assert (
        proof_admissible(clean_proof(single_use_consumed=consumed, is_expired=expired))
        is False
    )
