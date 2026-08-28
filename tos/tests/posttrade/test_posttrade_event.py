"""§5.5 event obligation legs + event-state non-implication (PTF-EV-006; nontrade boundary).

The largest ownership boundary in the package (design #24 §3.5): ADR-002-010 §16 line 309
and ADR-002-030 §17 line 414 are a **mutual** deferral — nontrade owns the non-trade event
and transformation identity plus the event workflow lifecycle, this package owns the
resulting obligation legs and their finality.

Both directions of both guards:

* **guard fires** — an empty required leg set is ``False`` (never vacuously complete); a
  missing leg kind is incomplete; an empty or all-unproven finality map means the obligation's
  finality picture is not proof-borne;
* **legitimate pass** — the required subset present ⇒ complete; at least one dimension with
  its own proof ⇒ proof-borne.

The §17 line 418 non-implication ("an event state such as ``APPLIED_LOCAL`` or ``RECONCILED``
does not prove its resulting obligations final") is asserted **structurally**: the verdict is
invariant under every event-state token, including the two the ADR names, the ones it does
not, an empty string, and a forged one. That invariance is only possible because the token is
never read.

[PTF-EV-006 coordinate; ``/2``, ``/3``, and ``+Broker`` remain open. Closing PTF-EV = 0.]
"""

from __future__ import annotations

import pytest
from hypothesis import given
from tos.posttrade import (
    EVENT_OBLIGATION_LEG_MINIMUM_SET,
    EVENT_STATE_TOKENS_THAT_PROVE_NO_FINALITY,
    EventObligationLegKind,
    FinalityDimensionKind,
    event_state_not_obligation_finality,
    obligation_legs_from_event_complete,
)

from ._posttrade_strategies import (
    EVENT_LEG_SETS,
    EVENT_STATE_TOKENS,
    PROOF_MAPS,
    proof_map_only,
)

_ALL_TOKENS: tuple[str | None, ...] = (
    "APPLIED_LOCAL",
    "RECONCILED",
    "OBSERVED",
    "CORROBORATING",
    "VALIDATED",
    "QUARANTINED_UNKNOWN",
    "CONFLICTED",
    "FINALITY_PROVEN",
    "applied_local",
    "",
    "FORGED-TOKEN",
    None,
)


# --- §17 line 416 obligation_legs_from_event_complete ------------------------


def test_the_full_nine_leg_set_is_complete() -> None:
    """(positive side) Every credible asset / cash / fee / tax / financing / margin /
    borrow / custody / delivery leg modelled ⇒ complete."""
    assert (
        obligation_legs_from_event_complete(
            EVENT_OBLIGATION_LEG_MINIMUM_SET, EVENT_OBLIGATION_LEG_MINIMUM_SET
        )
        is True
    )


def test_an_event_class_parametric_subset_is_complete_when_present() -> None:
    """(positive side) The required subset is injected, not defaulted to all nine."""
    required = frozenset({EventObligationLegKind.CASH, EventObligationLegKind.TAX})
    assert (
        obligation_legs_from_event_complete(required, EVENT_OBLIGATION_LEG_MINIMUM_SET)
        is True
    )


def test_empty_required_set_is_false_not_vacuously_true() -> None:
    """(∅ guard, §4.8 row 19) ``∅ <= present`` would certify every event as fully modelled."""
    assert (
        obligation_legs_from_event_complete(
            frozenset(), EVENT_OBLIGATION_LEG_MINIMUM_SET
        )
        is False
    )


def test_empty_required_set_is_false_even_with_nothing_present() -> None:
    """(∅ guard, both empty) Two empty sets are the most vacuous pass of all."""
    assert obligation_legs_from_event_complete(frozenset(), frozenset()) is False


@pytest.mark.parametrize("missing", list(EventObligationLegKind))
def test_each_of_the_nine_legs_is_individually_load_bearing(
    missing: EventObligationLegKind,
) -> None:
    """(guard fires) Dropping any one of the nine makes the event incompletely modelled."""
    present = EVENT_OBLIGATION_LEG_MINIMUM_SET - {missing}
    assert (
        obligation_legs_from_event_complete(EVENT_OBLIGATION_LEG_MINIMUM_SET, present)
        is False
    )


@given(required=EVENT_LEG_SETS, present=EVENT_LEG_SETS)
def test_completeness_is_subset_containment_with_a_non_empty_requirement(
    required: frozenset[EventObligationLegKind],
    present: frozenset[EventObligationLegKind],
) -> None:
    """(§5.5) The predicate is exactly "non-empty requirement, fully present"."""
    expected = bool(required) and required <= present
    assert obligation_legs_from_event_complete(required, present) is expected


def test_the_minimum_set_is_a_convenience_universe_not_a_default() -> None:
    """(§2.2-5b) The nine-member universe exists for callers; it is never auto-required."""
    assert frozenset(EventObligationLegKind) == EVENT_OBLIGATION_LEG_MINIMUM_SET
    assert obligation_legs_from_event_complete(frozenset(), frozenset()) is False


# --- §17 line 418 event_state_not_obligation_finality ------------------------


def test_a_dimension_specific_proof_makes_the_picture_proof_borne() -> None:
    """(positive side) At least one dimension with its own proof ⇒ ``True``."""
    proof_map = proof_map_only(FinalityDimensionKind.SETTLEMENT)
    assert event_state_not_obligation_finality("APPLIED_LOCAL", proof_map) is True


@pytest.mark.parametrize("token", _ALL_TOKENS)
def test_no_event_state_token_can_manufacture_finality(token: str | None) -> None:
    """(§17 line 418) With no dimension proven, **no** token makes the picture proof-borne.

    "An ADR-002-010 event state such as ``APPLIED_LOCAL`` or ``RECONCILED`` does not prove
    its resulting obligations final."
    """
    all_unknown: dict[FinalityDimensionKind, bool | None] = dict.fromkeys(
        FinalityDimensionKind
    )
    assert event_state_not_obligation_finality(token, all_unknown) is False


@pytest.mark.parametrize("token", _ALL_TOKENS)
def test_the_verdict_is_invariant_under_every_event_state_token(
    token: str | None,
) -> None:
    """(§5.5 structural) The token is never read, so it cannot change any verdict.

    Asserted against a fixed baseline for both a proven and an unproven map: if any branch
    consulted the token, one of these would differ.
    """
    proven = proof_map_only(FinalityDimensionKind.FEE_FINALITY)
    unproven: dict[FinalityDimensionKind, bool | None] = dict.fromkeys(
        FinalityDimensionKind, False
    )
    assert event_state_not_obligation_finality(token, proven) is True
    assert event_state_not_obligation_finality(token, unproven) is False


def test_the_two_tokens_the_adr_names_are_covered_by_the_invariance() -> None:
    """(§17 line 418) ``APPLIED_LOCAL`` and ``RECONCILED`` are in the exercised token set."""
    for token in EVENT_STATE_TOKENS_THAT_PROVE_NO_FINALITY:
        assert token in _ALL_TOKENS


def test_empty_proof_map_is_false_not_vacuously_true() -> None:
    """(∅ guard, §4.8 row 7) "No proof anywhere" never reads as "the event did not
    overreach, so we are fine"."""
    assert event_state_not_obligation_finality("RECONCILED", {}) is False
    assert event_state_not_obligation_finality(None, {}) is False


@pytest.mark.parametrize("forged", [1, "yes", [1], 0, "", []])
def test_a_forged_proof_entry_is_not_a_proof(forged: object) -> None:
    """(polarity) The map entry is gated ``is True``; truthy and falsy forgeries both fail."""
    proof_map = {FinalityDimensionKind.SETTLEMENT: forged}
    assert (
        event_state_not_obligation_finality("APPLIED_LOCAL", proof_map)  # type: ignore[arg-type]
        is False
    )


@given(token=EVENT_STATE_TOKENS, proof_map=PROOF_MAPS)
def test_verdict_is_exactly_any_dimension_positively_proven(
    token: str | None, proof_map: dict[FinalityDimensionKind, bool | None]
) -> None:
    """(§5.5) The proposition, over arbitrary tokens and maps."""
    expected = any(value is True for value in proof_map.values())
    assert event_state_not_obligation_finality(token, proof_map) is expected
