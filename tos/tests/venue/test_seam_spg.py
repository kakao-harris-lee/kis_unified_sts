"""MANDATED test-only seam cross-check: venue policy <-> spg activation boundary (design #19 §3.5 / §7).

spg (ADR-002-014) owns the Safety-Config governance CLASS — the ``VENUE_CONSTRAINT_POLICY``
governed-profile member (verified owner ``BundleMemberKind.VENUE_CONSTRAINT_POLICY``,
``spg/vocabulary.py:205``; the design's "GovernedProfileClass" label resolves to the real
``BundleMemberKind`` enum — grep-verified, phantom-avoidance §10.1). venue owns the policy
**content**; spg owns policy **activation / generation / supersession**. venue consumes the
activation verdict as an injected scalar (§8 line 243) — it does not activate its own policy.

This file imports the real spg member as a **test** to lock the boundary (the governed-profile
member exists and names the venue constraint policy). A test-only cross-import is **not** a
runtime package edge (§3.4(d)/§7.1).

Regime tag: predicate / model substrate only; VTG-EV substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.spg import BundleMemberKind
from tos.venue import VenueConstraintPolicy

from ._venue_strategies import clean_policy


def test_spg_owns_the_venue_constraint_policy_governed_member() -> None:
    """(§3.5) spg declares the VENUE_CONSTRAINT_POLICY governed-profile member (activation authority)."""
    assert BundleMemberKind.VENUE_CONSTRAINT_POLICY.value == "VENUE_CONSTRAINT_POLICY"


def test_venue_owns_policy_content_not_activation() -> None:
    """(§3.5) venue authors the policy CONTENT; it carries no activation field (spg activates)."""
    policy = clean_policy()
    # venue's policy carries content coordinates (admitting phases, constraints) — not activation.
    assert policy.policy_id is not None
    assert policy.admitting_phase_rules  # content
    # There is no venue-owned "activation" / "active" field — activation is spg's (injected verdict).
    fields = set(VenueConstraintPolicy.model_fields)
    assert "activation" not in fields
    assert "active" not in fields
    assert "activation_verdict" not in fields
