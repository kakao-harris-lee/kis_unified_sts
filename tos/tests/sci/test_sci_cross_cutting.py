"""Cross-cutting structural predicates §5.6 (b)-(e) both-ways canaries (design #29 §5.6).

(a) ``supply_chain_artifact_not_authority`` lives in ``test_sci_authority.py`` beside the block it
reads. This file covers generation monotonicity and rollback (b), restriction non-revival (c), the
negative-gate discipline (d), and the spg produced-value verdict (e).

Regime tag: release-admission predicate/model substrate only; **closes no SCI-EV**; the
restriction-floor **advance** mechanism is cur's ``fence_advances_floor``, re-authored not at all.
"""

from __future__ import annotations

import pytest
import tos.sci as sci
from hypothesis import given
from hypothesis import strategies as st

from ._sci_strategies import (
    CREDIBLE_SCOPE_DIMENSIONS,
    TRIBOOL,
    clean_restriction,
    clean_scope,
)

_GATE_ARGS = (
    "supplies_capacity",
    "supplies_authority",
    "supplies_protection",
    "supplies_approval",
    "supplies_admissibility",
    "supplies_permission",
)


# --- (b) release generation monotonicity + rollback -------------------------------------------


def test_release_generation_monotonic_passes_on_strict_advance() -> None:
    """(§5.8/SCI-INV-012) A strictly advancing generation passes."""
    assert sci.release_generation_monotonic(41, 42) is True


@pytest.mark.parametrize("pair", [(42, 42), (42, 41), (None, 42), (42, None)])
def test_release_generation_monotonic_denies(
    pair: tuple[int | None, int | None],
) -> None:
    """(§5.8 line 131) Reuse, regression, and absence all deny."""
    assert sci.release_generation_monotonic(*pair) is False


def test_rollback_takes_a_new_generation() -> None:
    """(§22 line 433) "Rollback is a new release proposal ... and Release Generation"."""
    assert sci.rollback_is_new_generation(41, 42, False) is True


def test_rollback_reusing_the_historical_generation_denies() -> None:
    """(SCI-INV-012 line 199) "identical bytes require a new Release Generation"."""
    assert sci.rollback_is_new_generation(41, 41, False) is False


@given(flag=TRIBOOL)
def test_rollback_reuse_permission_is_negative_polarity(flag: bool | None) -> None:
    """(§5.6b) The reuse permission clears only on an explicit ``False``; ``None`` denies."""
    assert sci.rollback_is_new_generation(41, 42, flag) is (flag is False)


# --- (c) restriction monotonic non-revival ----------------------------------------------------


def test_clean_restriction_passes() -> None:
    """(both-ways) A scope-complete restriction covering the credible closure passes."""
    assert (
        sci.restriction_is_monotonic_non_revival(
            clean_restriction(), CREDIBLE_SCOPE_DIMENSIONS, True, False
        )
        is True
    )


def test_absent_restriction_denies() -> None:
    """(§5.6c ∅-seal) A ``None`` restriction denies."""
    assert (
        sci.restriction_is_monotonic_non_revival(
            None, CREDIBLE_SCOPE_DIMENSIONS, True, False
        )
        is False
    )


@given(flag=TRIBOOL)
def test_unresolved_credible_closure_denies(flag: bool | None) -> None:
    """(§5.6c) The closure-resolution gate is positive polarity."""
    assert sci.restriction_is_monotonic_non_revival(
        clean_restriction(), CREDIBLE_SCOPE_DIMENSIONS, flag, False
    ) is (flag is True)


@pytest.mark.parametrize("closure", [None, frozenset()])
def test_absent_or_empty_credible_closure_denies(
    closure: frozenset[str] | None,
) -> None:
    """(§5.6c / §0.5-2) ∅ both ways — an unknown closure is not an empty closure."""
    assert (
        sci.restriction_is_monotonic_non_revival(
            clean_restriction(), closure, True, False
        )
        is False
    )


@given(flag=TRIBOOL)
def test_restriction_scope_complete_is_positive_polarity(flag: bool | None) -> None:
    """(§5.6c / SCI-INV-006 line 175) Incomplete or unknown restricted scope denies."""
    restriction = clean_restriction(restricted_scope=clean_scope(scope_complete=flag))
    assert sci.restriction_is_monotonic_non_revival(
        restriction, CREDIBLE_SCOPE_DIMENSIONS, True, False
    ) is (flag is True)


def test_absent_restricted_scope_denies() -> None:
    """(§5.6c) A restriction with no scope denies."""
    restriction = clean_restriction(restricted_scope=None)
    assert (
        sci.restriction_is_monotonic_non_revival(
            restriction, CREDIBLE_SCOPE_DIMENSIONS, True, False
        )
        is False
    )


@pytest.mark.parametrize("dimension", sorted(CREDIBLE_SCOPE_DIMENSIONS))
def test_a_narrower_restriction_denies_per_dimension(dimension: str) -> None:
    """(§20 line 404) "Scope expands to the greatest credible dependency closure" — any-broaden-wins.

    An omitted dimension is an unknown axis, and unknown scope is denial (SCI-INV-006 line 175), so
    a silently narrower restriction cannot pass. Each of the eight dimensions is fired individually.
    """
    restriction = clean_restriction(restricted_scope=clean_scope(**{dimension: None}))
    assert (
        sci.restriction_is_monotonic_non_revival(
            restriction, CREDIBLE_SCOPE_DIMENSIONS, True, False
        )
        is False
    )


@pytest.mark.parametrize("bad", ["TBD", "latest", "*", "   "])
def test_a_mutable_scope_coordinate_denies(bad: str) -> None:
    """(SCI-INV-002 / SCI-INV-006 line 175) A wildcarded scope coordinate is not exact."""
    restriction = clean_restriction(restricted_scope=clean_scope(environment=bad))
    assert (
        sci.restriction_is_monotonic_non_revival(
            restriction, CREDIBLE_SCOPE_DIMENSIONS, True, False
        )
        is False
    )


def test_an_unknown_credible_dimension_denies() -> None:
    """(§5.6c) A dimension outside the §4.10 catalogue is unresolvable — denial, never ignored."""
    assert (
        sci.restriction_is_monotonic_non_revival(
            clean_restriction(),
            CREDIBLE_SCOPE_DIMENSIONS | {"not_a_dimension"},
            True,
            False,
        )
        is False
    )


@given(flag=TRIBOOL)
def test_revival_claim_is_negative_polarity(flag: bool | None) -> None:
    """(§20 line 406 / SCI-INV-016) A claim to readmit or clear — and an unknown — both deny."""
    assert sci.restriction_is_monotonic_non_revival(
        clean_restriction(), CREDIBLE_SCOPE_DIMENSIONS, True, flag
    ) is (flag is False)


def test_sci_does_not_reauthor_the_cur_floor_advance() -> None:
    """(§3.5 M4) The cross-artifact floor-advance mechanism stays cur's — absent here by name."""
    assert not hasattr(sci, "fence_advances_floor")
    assert not hasattr(sci, "RestrictiveFenceRecord")
    assert not hasattr(sci, "floor_strictly_advances")
    doc = sci.restriction_is_monotonic_non_revival.__doc__ or ""
    assert "fence_advances_floor" in doc


# --- (d) active currentness is a negative gate ------------------------------------------------


def test_negative_gate_passes_when_it_supplies_nothing() -> None:
    """(§1 line 27) A current check that grants nothing is a negative gate."""
    assert (
        sci.active_currentness_is_negative_gate(
            True, False, False, False, False, False, False
        )
        is True
    )


@given(flag=TRIBOOL)
def test_currentness_verdict_is_positive_polarity(flag: bool | None) -> None:
    """(SCI-INV-013 line 203) A non-current — or unknown — verdict denies."""
    assert sci.active_currentness_is_negative_gate(
        flag, False, False, False, False, False, False
    ) is (flag is True)


@pytest.mark.parametrize("position", range(len(_GATE_ARGS)))
@given(flag=TRIBOOL)
def test_each_supply_claim_is_negative_polarity(
    position: int, flag: bool | None
) -> None:
    """(§1 line 27) Each of the six supply claims individually denies unless explicitly ``False``.

    §1 line 27 verbatim: "It cannot supply capacity, authority, protection, approval,
    admissibility, or permission that another owner has not independently granted."
    """
    args = [False] * len(_GATE_ARGS)
    args[position] = flag  # type: ignore[call-overload]
    assert sci.active_currentness_is_negative_gate(True, *args) is (flag is False)


def test_negative_gate_covers_exactly_the_six_line_27_claims() -> None:
    """(§1 line 27) Six supply claims — no more, no fewer."""
    import inspect

    parameters = list(
        inspect.signature(sci.active_currentness_is_negative_gate).parameters
    )
    assert parameters[0] == "currentness_current"
    assert tuple(parameters[1:]) == _GATE_ARGS
    assert len(_GATE_ARGS) == 6


# --- (e) software_deployment_ok_verdict (the spg produced-value seam) --------------------------


def test_verdict_passes_on_a_complete_positive_chain() -> None:
    """(both-ways) ADMIT + matching runtime + current + no restriction ⇒ ``True``."""
    assert (
        sci.software_deployment_ok_verdict(
            sci.AdmissionResult.ADMIT, True, True, False, True
        )
        is True
    )


@given(flag=TRIBOOL)
def test_restriction_state_resolution_gate_is_positive_polarity(
    flag: bool | None,
) -> None:
    """(§5.6e / §21 line 427) An unresolved restriction lookup denies conservatively."""
    assert sci.software_deployment_ok_verdict(
        sci.AdmissionResult.ADMIT, True, True, False, flag
    ) is (flag is True)


@pytest.mark.parametrize("result", [*list(sci.AdmissionResult), None])
def test_verdict_requires_a_positive_admit(result: sci.AdmissionResult | None) -> None:
    """(§5.6e / §0.5-4) Only ``ADMIT`` passes — no fall-through over the residual space."""
    assert sci.software_deployment_ok_verdict(result, True, True, False, True) is (
        result is sci.AdmissionResult.ADMIT
    )


@given(flag=TRIBOOL)
def test_runtime_match_is_positive_polarity(flag: bool | None) -> None:
    """(SCI-INV-010 line 191) "Desired state and process health are insufficient"."""
    assert sci.software_deployment_ok_verdict(
        sci.AdmissionResult.ADMIT, flag, True, False, True
    ) is (flag is True)


@given(flag=TRIBOOL)
def test_active_currentness_is_positive_polarity(flag: bool | None) -> None:
    """(§5.6e) The injected cur currentness verdict clears only on an explicit ``True``."""
    assert sci.software_deployment_ok_verdict(
        sci.AdmissionResult.ADMIT, True, flag, False, True
    ) is (flag is True)


@given(flag=TRIBOOL)
def test_restriction_present_is_negative_polarity(flag: bool | None) -> None:
    """(SCI-INV-014 / §16 line 348) A present — or unknown — restriction denies."""
    assert sci.software_deployment_ok_verdict(
        sci.AdmissionResult.ADMIT, True, True, flag, True
    ) is (flag is False)


@given(
    result=st.sampled_from([*list(sci.AdmissionResult), None]),
    matches=TRIBOOL,
    current=TRIBOOL,
    restricted=TRIBOOL,
    resolved=TRIBOOL,
)
def test_verdict_is_the_exact_conjunction(
    result: sci.AdmissionResult | None,
    matches: bool | None,
    current: bool | None,
    restricted: bool | None,
    resolved: bool | None,
) -> None:
    """(property) The verdict is exactly the five-clause fail-closed conjunction."""
    expected = (
        resolved is True
        and result is sci.AdmissionResult.ADMIT
        and matches is True
        and current is True
        and restricted is False
    )
    assert (
        sci.software_deployment_ok_verdict(
            result, matches, current, restricted, resolved
        )
        is expected
    )


# --- MAJOR-2: the near-∅ credible closure -----------------------------------------------------


def test_scope_complete_only_closure_is_a_near_empty_closure_and_denies() -> None:
    """(§5.6c / §0.5-2) ``frozenset({"scope_complete"})`` names no axis — it denies exactly as ∅.

    ``scope_complete`` is a completeness *flag*, not a scope axis. Before the fix the ∅ guard saw a
    non-empty set, the loop reached its ``continue``, and the predicate returned ``True`` having
    verified **no coordinate at all** — a vacuous pass of the same family as the C2 ∅ admitted-set
    defect. The guard now subtracts the flag before testing emptiness.
    """
    assert (
        sci.restriction_is_monotonic_non_revival(
            clean_restriction(), frozenset({"scope_complete"}), True, False
        )
        is False
    )


def test_a_closure_of_only_the_flag_plus_one_axis_still_verifies_that_axis() -> None:
    """(both-ways) Subtracting the flag does not weaken the check on the real axes."""
    assert (
        sci.restriction_is_monotonic_non_revival(
            clean_restriction(),
            frozenset({"scope_complete", "environment"}),
            True,
            False,
        )
        is True
    )
    narrowed = clean_restriction(restricted_scope=clean_scope(environment=None))
    assert (
        sci.restriction_is_monotonic_non_revival(
            narrowed, frozenset({"scope_complete", "environment"}), True, False
        )
        is False
    )


def test_unknown_dimension_still_denies_when_paired_with_the_flag() -> None:
    """(§5.6c) Subtracting ``scope_complete`` must not let an unknown dimension slip past."""
    assert (
        sci.restriction_is_monotonic_non_revival(
            clean_restriction(),
            frozenset({"scope_complete", "not_a_dimension"}),
            True,
            False,
        )
        is False
    )
