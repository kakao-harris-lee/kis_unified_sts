"""classify_field: empty / single / corroborated / conflict / common-mode / stale (§5.1).

RECON-EV-001 / -004 predicate substrate (design #9 §5.1 / §7). Both-ways canaries: each
fail-closed guard fires on the negative input AND the positive path still reaches the
strong class. Independence / tolerance / freshness are injected — no hardcoded numbers.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.recon import (
    FieldConfidenceClass,
    SafetyRelevantField,
    classify_field,
    is_conflicted,
    is_corroborated,
)

from ._recon_strategies import (
    fresh_marker,
    markers,
    observation,
    observations,
    stale_marker,
)

_C = FieldConfidenceClass
_F = SafetyRelevantField.ORDER_EXISTENCE


def test_empty_observations_is_unknown() -> None:
    """(§4.4) An empty evidence set is UNKNOWN — never a vacuous CORROBORATED."""
    assert classify_field((), fresh_marker()) is _C.UNKNOWN


def test_all_absence_is_unknown() -> None:
    """(§5.3) A set of only absence observations has 0 usable paths => UNKNOWN."""
    obs = (
        observation(is_absence=True),
        observation(is_absence=True, independence_class="B"),
    )
    assert classify_field(obs, fresh_marker()) is _C.UNKNOWN


def test_single_path_is_single_source() -> None:
    """(§4.5) Exactly one usable path is SINGLE_SOURCE (below release grade)."""
    assert classify_field((observation(),), fresh_marker()) is _C.SINGLE_SOURCE


def test_two_independent_agreeing_is_corroborated() -> None:
    """(positive side) >=2 sufficiently independent paths agreeing within tolerance."""
    obs = (
        observation(independence_class="A", agrees_within_tolerance=True),
        observation(independence_class="B", agrees_within_tolerance=True),
    )
    assert classify_field(obs, fresh_marker()) is _C.CORROBORATED


def test_common_mode_two_paths_not_corroborated() -> None:
    """(canary RECON-EV-001) Two same-independence_class (common-mode) paths never corroborate."""
    obs = (
        observation(independence_class="A", agrees_within_tolerance=True),
        observation(independence_class="A", agrees_within_tolerance=True),
    )
    result = classify_field(obs, fresh_marker())
    assert result is not _C.CORROBORATED
    assert result is _C.SINGLE_SOURCE


def test_independent_disagreement_is_conflicted() -> None:
    """(§7 line 101) Independent paths disagreeing beyond tolerance set CONFLICTED."""
    obs = (
        observation(independence_class="A", agrees_within_tolerance=True),
        observation(independence_class="B", agrees_within_tolerance=False),
    )
    assert classify_field(obs, fresh_marker()) is _C.CONFLICTED


def test_none_independence_fails_closed() -> None:
    """(fail-closed) None independence_class on both paths => not sufficiently independent."""
    obs = (
        observation(independence_class=None, agrees_within_tolerance=True),
        observation(independence_class=None, agrees_within_tolerance=True),
    )
    assert classify_field(obs, fresh_marker()) is not _C.CORROBORATED


def test_none_tolerance_fails_closed() -> None:
    """(fail-closed) None agreement flag => cannot corroborate (unproven agreement)."""
    obs = (
        observation(independence_class="A", agrees_within_tolerance=None),
        observation(independence_class="B", agrees_within_tolerance=None),
    )
    assert classify_field(obs, fresh_marker()) is not _C.CORROBORATED


def test_aged_corroborated_is_stale_m1() -> None:
    """(canary m1) Aged marker + >=2-independent-agree => STALE (STALE over CORROBORATED)."""
    obs = (
        observation(independence_class="A", agrees_within_tolerance=True),
        observation(independence_class="B", agrees_within_tolerance=True),
    )
    # Same observations under a fresh marker would be CORROBORATED (both-ways).
    assert classify_field(obs, fresh_marker()) is _C.CORROBORATED
    assert classify_field(obs, stale_marker()) is _C.STALE


def test_time_confidence_loss_downgrades_corroborated() -> None:
    """(fail-closed) Time-confidence loss on a would-be CORROBORATED field pins STALE."""
    obs = (
        observation(independence_class="A", agrees_within_tolerance=True),
        observation(independence_class="B", agrees_within_tolerance=True),
    )
    lost = fresh_marker(time_confidence_held=False)
    assert classify_field(obs, lost) is _C.STALE


def test_new_generation_downgrades_corroborated() -> None:
    """(RECON-EV-004) A generation-changed marker does not keep a corroborated field fresh."""
    obs = (
        observation(independence_class="A", agrees_within_tolerance=True),
        observation(independence_class="B", agrees_within_tolerance=True),
    )
    restarted = fresh_marker(time_generation=2, anchored_generation=1)
    assert classify_field(obs, restarted) is _C.STALE


def test_is_corroborated_and_is_conflicted_track_classify() -> None:
    """is_corroborated / is_conflicted are exactly the classify_field projections (§5.3)."""
    corr = (
        observation(independence_class="A", agrees_within_tolerance=True),
        observation(independence_class="B", agrees_within_tolerance=True),
    )
    conf = (
        observation(independence_class="A", agrees_within_tolerance=True),
        observation(independence_class="B", agrees_within_tolerance=False),
    )
    assert is_corroborated(corr, fresh_marker()) is True
    assert is_conflicted(corr, fresh_marker()) is False
    assert is_conflicted(conf, fresh_marker()) is True
    assert is_corroborated(conf, fresh_marker()) is False


@given(obs=st.lists(observations(), min_size=0, max_size=6), marker=markers())
def test_classify_is_total_and_single_source_never_corroborated(
    obs: list, marker
) -> None:
    """(property) classify always returns a class; one usable path is never CORROBORATED."""
    result = classify_field(tuple(obs), marker)
    assert result in set(FieldConfidenceClass)
    usable = [o for o in obs if not o.is_absence]
    if len(usable) <= 1:
        assert result is not _C.CORROBORATED


@given(marker=markers())
def test_single_source_ceiling_no_marker_lifts_it(marker) -> None:
    """(§4.5) A single path is never CORROBORATED under ANY injected freshness marker."""
    assert (
        classify_field((observation(),), marker)
        is not FieldConfidenceClass.CORROBORATED
    )
