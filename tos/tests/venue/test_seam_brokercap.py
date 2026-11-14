"""MANDATED test-only seam cross-check: venue <-> brokercap ceiling boundary (design #19 §3.5 (b) / §7)."""

from __future__ import annotations

from tos.brokercap import Admissibility as BrokerCapAdmissibility
from tos.venue import OrderAdmissibilityResult

from ._venue_strategies import clean_decision


def test_capability_ceiling_and_venue_admissibility_are_distinct_axes() -> None:
    """(§3.5 (b)) brokercap Admissibility (capability CAN) != venue OrderAdmissibilityResult (venue ALLOWS)."""
    assert BrokerCapAdmissibility is not OrderAdmissibilityResult
    assert BrokerCapAdmissibility.__name__ == "Admissibility"
    assert OrderAdmissibilityResult.__name__ == "OrderAdmissibilityResult"


def test_venue_binds_brokercap_version_and_digest_as_ceiling_scalars() -> None:
    """(VTG-INV-006) venue binds the brokercap profile version/digest as reduce-only ceiling scalars."""
    decision = clean_decision()
    assert decision.broker_capability_profile_version == "bc-v1"
    assert decision.broker_capability_profile_digest == "bc-digest"


def test_venue_cannot_promote_a_brokercap_admissibility() -> None:
    """(VTG-INV-006 line 169) There is no venue path that elevates a brokercap ceiling to ADMISSIBLE."""
    ceiling_values = {a.value for a in BrokerCapAdmissibility}
    venue_values = {r.value for r in OrderAdmissibilityResult}
    assert "BEST_EFFORT" not in venue_values
    assert "UNAVAILABLE" not in venue_values
    assert "ADMISSIBLE" in ceiling_values and "ADMISSIBLE" in venue_values
    assert OrderAdmissibilityResult.ADMISSIBLE is not BrokerCapAdmissibility.ADMISSIBLE
