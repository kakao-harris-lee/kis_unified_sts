"""Fallback monotone-restrictive + REDUCED path (design #10 §5.3; BC-EV-002/009/010).

A fallback never increases capability: a widening fallback is rejected; a legitimate
conservative one enables a REDUCED (restricted-live) scope; no fallback => PROHIBITED.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.brokercap import (
    Admissibility,
    CapabilityDimension,
    FallbackSpec,
    capability_admissible,
    fallback_admissible,
)

from ._brokercap_strategies import (
    conservative_fallback,
    issue_profile,
    required_set,
    verified_declaration,
)

_OID = CapabilityDimension.ORDER_IDENTITY
_CANCEL = CapabilityDimension.CANCELLATION


# ---------------------------------------------------------------------------
# fallback_admissible both-ways
# ---------------------------------------------------------------------------


def test_conservative_fallback_admissible() -> None:
    """(§5.3 canary b) A non-widening, conservative, tied fallback is admissible."""
    assert fallback_admissible(conservative_fallback()) is True


def test_widening_fallback_rejected() -> None:
    """(§4.2 / §23.9 canary a) A fallback that widens capability is rejected."""
    assert fallback_admissible(conservative_fallback(widens_capability=True)) is False


def test_non_conservative_fallback_rejected() -> None:
    """(§5.3) A fallback that is not conservative is rejected."""
    assert fallback_admissible(conservative_fallback(conservative=False)) is False
    assert fallback_admissible(conservative_fallback(conservative=None)) is False


def test_untied_fallback_rejected() -> None:
    """(ADR line 34) A fallback not tied to authority + risk scope is rejected."""
    assert (
        fallback_admissible(
            conservative_fallback(tied_to_authority_and_risk_scope=False)
        )
        is False
    )


def test_no_fallback_is_rejected() -> None:
    """(§5.3) No fallback (None) => False (=> PROHIBITED, never REDUCED)."""
    assert fallback_admissible(None) is False


@given(
    widens=st.sampled_from([True, None]),
    conservative=st.sampled_from([False, None]),
    tied=st.sampled_from([False, None]),
)
def test_any_non_positive_flag_fails_closed(
    widens: bool | None, conservative: bool | None, tied: bool | None
) -> None:
    """No non-positive flag combination is admissible (structural fail-closed)."""
    spec = FallbackSpec(
        widens_capability=widens,
        conservative=conservative,
        tied_to_authority_and_risk_scope=tied,
    )
    assert fallback_admissible(spec) is False


# ---------------------------------------------------------------------------
# REDUCED vs PROHIBITED at the central predicate
# ---------------------------------------------------------------------------


def test_deficient_with_approved_fallback_is_reduced() -> None:
    """(§5.1 REDUCED) A deficient dimension with an approved fallback => REDUCED."""
    profile = issue_profile(declarations=(verified_declaration(dimension=_OID),))
    req = required_set(
        dimensions=frozenset({_OID, _CANCEL}),
        approved_fallback_dimensions=frozenset({_CANCEL}),
    )
    assert (
        capability_admissible(profile, "entry", req, version_current=True)
        is Admissibility.REDUCED
    )


def test_deficient_without_approved_fallback_is_prohibited() -> None:
    """(§5.1) A deficient dimension with no approved fallback => PROHIBITED."""
    profile = issue_profile(declarations=(verified_declaration(dimension=_OID),))
    req = required_set(dimensions=frozenset({_OID, _CANCEL}))
    assert (
        capability_admissible(profile, "entry", req, version_current=True)
        is Admissibility.PROHIBITED
    )


def test_reduced_requires_all_deficient_covered() -> None:
    """(§5.1) If not ALL deficient dims have an approved fallback => PROHIBITED."""
    profile = issue_profile(declarations=(verified_declaration(dimension=_OID),))
    req = required_set(
        dimensions=frozenset({_OID, _CANCEL, CapabilityDimension.REPLACE_OR_AMEND}),
        approved_fallback_dimensions=frozenset({_CANCEL}),  # REPLACE_OR_AMEND uncovered
    )
    assert (
        capability_admissible(profile, "entry", req, version_current=True)
        is Admissibility.PROHIBITED
    )
