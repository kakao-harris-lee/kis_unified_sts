"""exact_binding_holds — exact binding chain (design #15 §5.3; IAP-EV-004 substrate, core L1 slice).

bidirectional set comparison (§4.3/§4.7, the #14 MAJOR-1 lesson): a missing link (binding broken)
AND a surplus / substituted link (a different chain) both deny. both-ways: an exactly-matching
chain binds (APPROVE, positive side). ∅ both-ways: an empty chain cannot prove binding (DENY, not
a vacuous pass). Substitution of any node invalidates (§13 line 585). A None link => UNKNOWN
(never assume-match).

Regime tag: predicate / model substrate only; IAP-EV-004 NOT_IMPLEMENTED (`/3+Security` residue);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.iap import ApprovalResult, exact_binding_holds

_CHAIN = {
    "proposal": "prop-digest-1",
    "capsule": "cap-digest-1",
    "envelope": "env-digest-1",
    "command": "cmd-digest-1",
}


def test_exact_chain_binds() -> None:
    """(positive side) An exactly-matching chain binds => APPROVE."""
    assert exact_binding_holds(_CHAIN, dict(_CHAIN)) is ApprovalResult.APPROVE


def test_substituted_link_denies() -> None:
    """(§13 line 585) Substituting any one link's digest invalidates the binding => DENY."""
    tampered = {**_CHAIN, "command": "SUBSTITUTED"}
    assert exact_binding_holds(_CHAIN, tampered) is ApprovalResult.DENY


def test_missing_link_denies() -> None:
    """(both-ways: deficit) A missing (dropped) link breaks the binding => DENY."""
    short = {k: v for k, v in _CHAIN.items() if k != "capsule"}
    assert exact_binding_holds(_CHAIN, short) is ApprovalResult.DENY


def test_surplus_link_denies() -> None:
    """(both-ways: excess, #14 MAJOR-1) A surplus link is a different chain => DENY."""
    surplus = {**_CHAIN, "unexpected": "extra-digest"}
    assert exact_binding_holds(_CHAIN, surplus) is ApprovalResult.DENY


def test_empty_chain_denies() -> None:
    """(∅ fail-closed, §4.7) An empty chain binds nothing — a vacuous pass is not binding => DENY."""
    assert exact_binding_holds({}, {}) is ApprovalResult.DENY


def test_none_link_is_unknown() -> None:
    """(§4.3) An undetermined (None) link => UNKNOWN — never assume-match."""
    holey = {**_CHAIN, "capsule": None}
    assert exact_binding_holds(holey, dict(_CHAIN)) is ApprovalResult.UNKNOWN
    assert exact_binding_holds(dict(_CHAIN), holey) is ApprovalResult.UNKNOWN


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=4),
        values=st.text(min_size=1, max_size=6),
        min_size=1,
        max_size=5,
    )
)
def test_identical_nonempty_chain_always_binds(chain: dict[str, str]) -> None:
    """(property) Any non-empty chain compared against an identical copy binds => APPROVE."""
    assert exact_binding_holds(chain, dict(chain)) is ApprovalResult.APPROVE


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=4),
        values=st.text(min_size=1, max_size=6),
        min_size=1,
        max_size=5,
    ),
    st.text(min_size=1, max_size=4),
)
def test_extra_key_never_binds(chain: dict[str, str], extra_key: str) -> None:
    """(property, both-ways) Adding a key the bound chain lacks is never APPROVE (surplus denies)."""
    if extra_key in chain:
        return  # only exercise a genuinely-surplus key
    actual = {**chain, extra_key: "surplus"}
    assert exact_binding_holds(chain, actual) is not ApprovalResult.APPROVE
