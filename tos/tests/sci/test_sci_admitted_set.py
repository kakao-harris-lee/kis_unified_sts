"""Yolk 5 — ``admitted_set_no_permissive_union`` both-ways canaries (§16/SCI-INV-009; design #29 §5.5).

The C2 clause is the sharp one: an ∅ applicable set together with an ∅ membership **denies**. The
ADR nowhere sanctions an explicitly-empty Admitted Release Set (negative grep over §5.9 / §11 /
§16), and §1 line 17 says missing or incompletely closed state "grants zero eligibility" — so a
vacuous ``True`` would be a real fail-open, not a conservative-over-reach.

Regime tag: release-admission predicate/model substrate only; **closes no SCI-EV**.
"""

from __future__ import annotations

import pytest
import tos.sci as sci
from hypothesis import given

from ._sci_strategies import (
    CANDIDATE_GENERATION,
    PREDECESSOR_GENERATION,
    TRIBOOL,
    admitted_set_args,
    clean_release_set,
)

_MEMBERS = frozenset({"d-manifest-a", "d-manifest-b"})


def test_clean_release_set_passes() -> None:
    """(both-ways) A complete, committed, current, compatible, exactly-matching set passes."""
    assert sci.admitted_set_no_permissive_union(**admitted_set_args()) is True


def test_absent_release_set_denies() -> None:
    """(§5.5 item 1 ∅-seal) A ``None`` set denies."""
    assert (
        sci.admitted_set_no_permissive_union(**admitted_set_args(release_set=None))
        is False
    )


@given(flag=TRIBOOL)
def test_unresolved_applicable_lookup_denies(flag: bool | None) -> None:
    """(§5.5 item 1) The applicable-set resolution gate is positive polarity."""
    assert sci.admitted_set_no_permissive_union(
        **admitted_set_args(applicable_set_resolved=flag)
    ) is (flag is True)


def test_absent_applicable_set_denies() -> None:
    """(§5.5 item 1) A ``None`` applicable set is unknown scope — denial."""
    assert (
        sci.admitted_set_no_permissive_union(
            **admitted_set_args(applicable_manifest_digests=None)
        )
        is False
    )


def test_empty_applicable_and_empty_membership_denies() -> None:
    """(§5.5 item 1 / C2) ∅ + ∅ + ``complete=True`` denies — the vacuous-True fail-open is sealed.

    §16 line 346: "Missing artifact ... invalidates the set for the affected scope." Reversing this
    would require an ADR §16 erratum (design #29 §10.1-3).
    """
    assert (
        sci.admitted_set_no_permissive_union(
            **admitted_set_args(
                applicable_manifest_digests=frozenset(),
                member_manifest_digests=frozenset(),
            )
        )
        is False
    )


def test_missing_member_denies() -> None:
    """(§5.5 item 2 / §16 line 346) "Missing artifact ... invalidates the set"."""
    assert (
        sci.admitted_set_no_permissive_union(
            **admitted_set_args(member_manifest_digests=frozenset({"d-manifest-a"}))
        )
        is False
    )


def test_extra_member_denies() -> None:
    """(§5.5 item 2 / §16 line 346) "extra artifact ... invalidates the set" — both ways."""
    assert (
        sci.admitted_set_no_permissive_union(
            **admitted_set_args(
                member_manifest_digests=_MEMBERS | {"d-manifest-c"},
            )
        )
        is False
    )


def test_favorable_subset_denies() -> None:
    """(SCI-INV-009 line 187) "Partial deployment and favorable subsets cannot form a permissive union"."""
    assert (
        sci.admitted_set_no_permissive_union(
            **admitted_set_args(
                applicable_manifest_digests=_MEMBERS | {"d-manifest-c"},
                member_manifest_digests=_MEMBERS,
            )
        )
        is False
    )


@pytest.mark.parametrize(
    "field",
    ["partial_set_permitted", "set_union_permitted", "favorable_subset_permitted"],
)
@given(flag=TRIBOOL)
def test_union_permission_flags_are_negative_polarity(
    field: str, flag: bool | None
) -> None:
    """(§5.5 item 3 / SCI-INV-009) Only an explicit ``False`` clears; ``None`` denies."""
    release_set = clean_release_set(**{field: flag})
    assert sci.admitted_set_no_permissive_union(
        **admitted_set_args(release_set=release_set)
    ) is (flag is False)


@pytest.mark.parametrize("field", ["committed", "current", "compatibility_complete"])
@given(flag=TRIBOOL)
def test_state_flags_are_positive_polarity(field: str, flag: bool | None) -> None:
    """(§5.5 item 4 / NEW-4 + 1b) Committed / current / compatibility all clear only on ``True``.

    ``compatibility_complete`` in particular is a **bool gate**, not a digest-presence check:
    SCI-INV-011 line 195 and §17 line 358 — "Unknown compatibility denies the affected scope."
    """
    release_set = clean_release_set(**{field: flag})
    assert sci.admitted_set_no_permissive_union(
        **admitted_set_args(release_set=release_set)
    ) is (flag is True)


def test_incomplete_set_denies() -> None:
    """(§5.5 item 4) ``complete is not True`` denies (the seal keeps the digest present)."""
    release_set = clean_release_set(complete=False)
    assert (
        sci.admitted_set_no_permissive_union(
            **admitted_set_args(release_set=release_set)
        )
        is False
    )


@pytest.mark.parametrize(
    "state", [None, "UNKNOWN", "unknown", "  Unknown  ", "", "   "]
)
def test_unresolved_restriction_state_denies(state: str | None) -> None:
    """(§5.5 item 4 / §5.0) ``UNKNOWN`` — in any case or padding — and absent both deny.

    The **clear**-value set is a Phase-0 template INSTANCE decision, so no clear member is invented
    here: SCI decides only "``UNKNOWN`` or absent ⇒ deny" (design #29 §5.0).
    """
    release_set = clean_release_set(restriction_state=state)
    assert (
        sci.admitted_set_no_permissive_union(
            **admitted_set_args(release_set=release_set)
        )
        is False
    )


@pytest.mark.parametrize("state", ["NO_RESTRICTION", "RESTRICTED", "CLEARED_BY_OWNER"])
def test_positively_resolved_restriction_state_passes(state: str) -> None:
    """(both-ways) Any positively-resolved token passes — SCI invents no clear-value member."""
    release_set = clean_release_set(restriction_state=state)
    assert (
        sci.admitted_set_no_permissive_union(
            **admitted_set_args(release_set=release_set)
        )
        is True
    )


@given(flag=TRIBOOL)
def test_historical_generation_reuse_is_negative_polarity(flag: bool | None) -> None:
    """(§5.5 item 5 / §5.8 line 131) Historical reuse clears only on an explicit ``False``."""
    release_set = clean_release_set(historical_generation_reuse_permitted=flag)
    assert sci.admitted_set_no_permissive_union(
        **admitted_set_args(release_set=release_set)
    ) is (flag is False)


def test_equal_generation_denies() -> None:
    """(§5.5 item 5 / §5.8 line 131) A committed generation equal to its predecessor is a reuse."""
    release_set = clean_release_set(release_generation=PREDECESSOR_GENERATION)
    assert (
        sci.admitted_set_no_permissive_union(
            **admitted_set_args(release_set=release_set)
        )
        is False
    )


def test_regressing_generation_denies() -> None:
    """(§5.5 item 5) A committed generation behind its predecessor denies."""
    release_set = clean_release_set(release_generation=PREDECESSOR_GENERATION - 1)
    assert (
        sci.admitted_set_no_permissive_union(
            **admitted_set_args(release_set=release_set)
        )
        is False
    )


def test_absent_generation_denies() -> None:
    """(§5.5 item 5) An absent generation on either side is unknown ordering — denial."""
    for override in (
        {"release_generation": None},
        {"predecessor_release_generation": None},
    ):
        release_set = clean_release_set(**override)
        assert (
            sci.admitted_set_no_permissive_union(
                **admitted_set_args(release_set=release_set)
            )
            is False
        )


def test_advancing_generation_passes() -> None:
    """(both-ways) A strictly advancing committed generation passes."""
    release_set = clean_release_set(release_generation=CANDIDATE_GENERATION + 3)
    assert (
        sci.admitted_set_no_permissive_union(
            **admitted_set_args(release_set=release_set)
        )
        is True
    )
