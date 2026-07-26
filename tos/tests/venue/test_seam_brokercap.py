"""MANDATED test-only seam cross-check: venue <-> brokercap ceiling boundary (design #19 §3.5 (b) / §7).

brokercap (ADR-002-004) owns broker **capability semantics** — what a broker CAN do (the
``Admissibility`` capability-ceiling axis, ``brokercap/vocabulary.py:225``); venue owns the
**current venue admissibility within that ceiling** — what the venue ALLOWS now
(``OrderAdmissibilityResult``). VTG-INV-006 line 169-171: "The active Broker Capability Profile
may reduce or prohibit scope. It never proves current venue state and **cannot expand** policy,
authorization, capacity, or Hard Safety Envelope limits." So venue consumes the brokercap
version/digest as a **ceiling scalar** (reduce-only) and **cannot promote** it.

This file imports the real brokercap records/enums as a **test** to lock (a) the two axes are
distinct types (capability-ceiling vs venue-admissibility — no promotion), and (b) venue binds
the brokercap version/digest as a scalar it does not re-author. A test-only cross-import is
**not** a runtime package edge (§3.4(d)/§7.1).

Regime tag: predicate / model substrate only; VTG-EV substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.brokercap import Admissibility as BrokerCapAdmissibility
from tos.venue import OrderAdmissibilityResult

from ._venue_strategies import clean_decision


def test_capability_ceiling_and_venue_admissibility_are_distinct_axes() -> None:
    """(§3.5 (b)) brokercap Admissibility (capability CAN) != venue OrderAdmissibilityResult (venue ALLOWS)."""
    # Distinct enum types — no promotion path between the capability ceiling and venue admissibility.
    assert BrokerCapAdmissibility is not OrderAdmissibilityResult
    assert BrokerCapAdmissibility.__name__ == "Admissibility"
    assert OrderAdmissibilityResult.__name__ == "OrderAdmissibilityResult"


def test_venue_binds_brokercap_version_and_digest_as_ceiling_scalars() -> None:
    """(VTG-INV-006) venue binds the brokercap profile version/digest as reduce-only ceiling scalars."""
    decision = clean_decision()
    # venue consumes the brokercap ceiling as injected scalars — it does not re-author capability.
    assert decision.broker_capability_profile_version == "bc-v1"
    assert decision.broker_capability_profile_digest == "bc-digest"


def test_venue_cannot_promote_a_brokercap_admissibility() -> None:
    """(VTG-INV-006 line 169) There is no venue path that elevates a brokercap ceiling to ADMISSIBLE.

    A ``BEST_EFFORT`` / ``UNAVAILABLE`` capability ceiling cannot be promoted by the gate (§13
    line 323). The structural seal: the two enums are unrelated types, so a brokercap ceiling
    value can never be assigned as a venue ``OrderAdmissibilityResult`` — the venue result comes
    only from venue's own predicates over injected scalars, never from the capability enum.
    """
    ceiling_values = {a.value for a in BrokerCapAdmissibility}
    venue_values = {r.value for r in OrderAdmissibilityResult}
    # The venue result vocabulary is its own — a brokercap BEST_EFFORT/UNAVAILABLE has no venue
    # counterpart to be promoted into.
    assert "BEST_EFFORT" not in venue_values
    assert "UNAVAILABLE" not in venue_values
    # (ADMISSIBLE is a homonym across axes but the TYPES are distinct — no cross-assignment.)
    assert "ADMISSIBLE" in ceiling_values and "ADMISSIBLE" in venue_values
    assert OrderAdmissibilityResult.ADMISSIBLE is not BrokerCapAdmissibility.ADMISSIBLE
