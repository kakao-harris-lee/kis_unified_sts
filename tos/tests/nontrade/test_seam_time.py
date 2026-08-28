"""MANDATED test-only seam cross-check: nontrade <-> time / ADR-002-008 (§3.4(d)/§6.2).

``tos.nontrade`` is **clock-free** (design #21 §7.2): it reads no time source, parses no
timestamp, and orders nothing by a wall clock — ADR-002-010 §8 line 175 forbids clock
recovery or a later source update from granting retroactive authority to an action denied
during the uncertainty interval. Trustworthy time is ADR-002-008's, and its verdict crosses
the seam as a bare **token** compared against the local
:data:`~tos.nontrade.FRESHNESS_VERDICT_FRESH` constant (sibling edge 0 — the type cannot be
named at runtime).

That local constant was the **one injected token of the thirteen without a drift lock**, so
this file closes that gap: a rename or a member removal on time's side must break here
rather than silently degrade every ``==`` comparison to ``False`` — a *quiet* failure whose
only symptom is that the effective-time window never opens again (a vacuous block, which is
an availability defect the design counts as seriously as a fail-open).

The lock is deliberately **two-sided**: ``FRESH`` must match, and each of the other three
members must **not**, so a mutation that repoints the constant at ``STALE`` / ``UNKNOWN`` /
``CONFLICTED`` is caught rather than merely renamed around.

A test-only cross-import is **not** a runtime package edge (design #21 §3.4(d)/§7.1); the
§7.1 allowlist closure test still asserts ``tos.time`` is absent from the runtime closure.
"""

from __future__ import annotations

import pytest
from tos.nontrade import FRESHNESS_VERDICT_FRESH, effective_window_blocks_new_risk
from tos.time.domains import FreshnessVerdict

from ._nontrade_strategies import clean_window_inputs

#: The three verdicts that are **not** a pass. Every one is a non-empty (truthy) string, so
#: a bare ``if time_freshness:`` would have opened the window on all of them.
_NON_FRESH_MEMBERS = (
    FreshnessVerdict.STALE,
    FreshnessVerdict.UNKNOWN,
    FreshnessVerdict.CONFLICTED,
)


# ---------------------------------------------------------------------------
# Token drift lock (both sides)
# ---------------------------------------------------------------------------


def test_the_local_freshness_token_matches_the_live_member() -> None:
    """(§3.4 drift lock) ``FRESHNESS_VERDICT_FRESH`` still names time's ``FRESH``."""
    assert FreshnessVerdict.FRESH.value == FRESHNESS_VERDICT_FRESH
    assert FRESHNESS_VERDICT_FRESH == FreshnessVerdict.FRESH


@pytest.mark.parametrize("member", _NON_FRESH_MEMBERS, ids=lambda m: m.value)
def test_the_local_token_matches_no_other_member(member: FreshnessVerdict) -> None:
    """(drift lock, negative side) The constant must not drift onto a denial member.

    A one-word mutation (``"FRESH"`` -> ``"STALE"``) would leave the positive assertion
    above failing but a name-only check green; asserting non-equivalence against every
    other member pins the constant from both directions.
    """
    assert member.value != FRESHNESS_VERDICT_FRESH


def test_the_producer_domain_is_the_four_members_the_fold_assumes() -> None:
    """(§6.2) The fold treats exactly one of four verdicts as a pass.

    If time ever adds a fifth member, this fails loudly so the fold is re-examined instead
    of silently classifying the newcomer as not-fresh by accident.
    """
    assert len(FreshnessVerdict) == 4
    assert {member.value for member in FreshnessVerdict} == {
        "FRESH",
        "STALE",
        "UNKNOWN",
        "CONFLICTED",
    }


# ---------------------------------------------------------------------------
# Polarity through the real member tokens
# ---------------------------------------------------------------------------


def test_the_live_fresh_member_opens_the_window() -> None:
    """(availability side) The real producer member — not a hand-typed string — passes.

    Passing the live ``StrEnum`` member proves the ``==``-against-a-local-constant
    comparison genuinely recognizes time's output, which a string literal fixture could
    not.
    """
    assert (
        effective_window_blocks_new_risk(
            **clean_window_inputs(time_freshness=FreshnessVerdict.FRESH)
        )
        is True
    )


@pytest.mark.parametrize("member", _NON_FRESH_MEMBERS, ids=lambda m: m.value)
def test_every_non_fresh_live_member_keeps_the_window_closed(
    member: FreshnessVerdict,
) -> None:
    """(§8 line 173 prohibited direction) An unestablished window blocks the whole interval.

    Causal isolation: only the verdict moves — both boundaries and the source-disagreement
    bound stay positively proven — so the flip is attributable to the token alone.
    """
    assert (
        bool(member) is True
    ), "the denial members are truthy strings — hence the token"
    assert (
        effective_window_blocks_new_risk(**clean_window_inputs(time_freshness=member))
        is False
    )


def test_nontrade_re_authors_no_part_of_the_time_service() -> None:
    """(§0.2/§3.5) The verdict, the bounds, and the generation logic are all time's."""
    from tos import nontrade as nontrade_pkg

    for forbidden in (
        "FreshnessVerdict",
        "freshness_verdict",
        "effective_snapshot_age_bound",
        "source_disagreement_within_bound",
        "recovery_generation_revives_nothing",
        "snapshot_grants_no_authority",
    ):
        assert not hasattr(nontrade_pkg, forbidden), (
            f"{forbidden} is time-owned (ADR-002-008) — nontrade is clock-free and "
            "consumes the verdict as an injected token"
        )
