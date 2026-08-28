"""§4.2 — the broker-applicability positive gate (design #34 MAJOR-2).

The gate has to avoid **two** failures at once, which is what makes it the design's most
delicate seal:

* a **silent skip** of the six deferred safety-governance items would be a fail-open;
* an **unconditional deny** would also block the synthetic path §2.1 says the slice runs.

So the deferred mesh is required — and therefore UNKNOWN-denying — for anything broker-reaching,
risk-relevant-live, or simply unresolved, and explicitly ``NOT_APPLICABLE`` only for a
*positively established* synthetic non-broker send. The justification is "**no broker route was
reached**", not "no live scope was armed": a real paper-account API call is non-live and still
broker-resource-consuming, and these tests assert it is denied.

Regime tag: authoring evidence only; closes no EV (design #34 §1.1).
"""

from __future__ import annotations

import pytest
from tos.egress import CredentialRouteInventoryEntry
from tos.egressgw import (
    DEFERRED_ITEMS,
    BrokerApplicability,
    SendHaltReason,
    SendVerifyItem,
    TransportNature,
    VerifyOutcome,
    resolve_broker_applicability,
    verify_send_boundary,
)

from ._egressgw_fixtures import (
    NON_LIVE_TEST_ENVIRONMENT,
    PRINCIPAL,
    TRANSPORT_PRINCIPAL,
    disjoint_inventory,
    happy_context,
    synthetic_nature,
)


def _applicability(**context_overrides) -> BrokerApplicability:
    """Resolve applicability over the baseline context with one override applied."""
    _, context = happy_context(**context_overrides)
    return resolve_broker_applicability(context.transport_nature, context)


def _deferred_outcomes(**context_overrides) -> set[VerifyOutcome]:
    """The outcomes the six deferred items receive under the given override."""
    attempt, context = happy_context(**context_overrides)
    verification = verify_send_boundary(attempt=attempt, context=context)
    return {v.outcome for v in verification.verdicts if v.item in DEFERRED_ITEMS}


# ---------------------------------------------------------------------------
# the positive path
# ---------------------------------------------------------------------------


def test_the_synthetic_baseline_is_positively_established_as_non_broker() -> None:
    """(§4.2 (iii)) Declaration + inventory corroboration + disjointness + environment."""
    assert _applicability() is BrokerApplicability.NON_BROKER_SYNTHETIC
    assert _deferred_outcomes() == {VerifyOutcome.NOT_APPLICABLE}


# ---------------------------------------------------------------------------
# a declaration alone never establishes it (the 자기신고 refusal)
# ---------------------------------------------------------------------------


def test_a_self_declaration_without_inventory_corroboration_is_unresolved() -> None:
    """(§4.2 구조 파생 > 자기신고) The transport's own say-so is not enough."""
    assert (
        _applicability(credential_route_inventory=())
        is BrokerApplicability.UNKNOWN
    )


def test_an_unrepresented_transport_principal_is_unresolved() -> None:
    """(§4.2) The declaring principal must actually appear in the inventory."""
    inventory = (
        CredentialRouteInventoryEntry(
            principal=PRINCIPAL,
            usable_credential=False,
            broker_route=False,
            inside_boundary=True,
        ),
    )
    assert _applicability(credential_route_inventory=inventory) is BrokerApplicability.UNKNOWN


def test_a_transport_principal_holding_a_route_is_broker_reaching_whatever_it_declared() -> None:
    """(§4.2) Structure overrides the declaration: a route makes it broker-reaching."""
    inventory = (
        CredentialRouteInventoryEntry(
            principal=TRANSPORT_PRINCIPAL,
            usable_credential=False,
            broker_route=True,
            inside_boundary=True,
        ),
    )
    assert (
        _applicability(credential_route_inventory=inventory)
        is BrokerApplicability.BROKER_RESOURCE_CONSUMING
    )


def test_an_unknown_credential_flag_is_conservatively_potentially_usable() -> None:
    """(EGRESS-INV-011 / §4.5) ``None`` is UNKNOWN ⇒ potentially usable, never "no"."""
    inventory = (
        CredentialRouteInventoryEntry(
            principal=TRANSPORT_PRINCIPAL,
            usable_credential=None,
            broker_route=False,
            inside_boundary=True,
        ),
        *disjoint_inventory()[1:],
    )
    assert (
        _applicability(credential_route_inventory=inventory)
        is BrokerApplicability.BROKER_RESOURCE_CONSUMING
    )


def test_an_outside_boundary_principal_with_credential_and_route_breaks_disjointness() -> None:
    """(EGRESS-INV-002:147-149 / Q-CRED-1) A bypass candidate anywhere denies the whole gate."""
    inventory = (
        *disjoint_inventory(),
        CredentialRouteInventoryEntry(
            principal="ops-worker",
            usable_credential=True,
            broker_route=True,
            inside_boundary=False,
        ),
    )
    assert _applicability(credential_route_inventory=inventory) is BrokerApplicability.UNKNOWN


def test_an_empty_inventory_proves_no_disjointness() -> None:
    """(∅ fail-closed) egress returns ``False`` on an empty inventory — nothing is proven."""
    assert _applicability(credential_route_inventory=()) is BrokerApplicability.UNKNOWN


# ---------------------------------------------------------------------------
# negative polarity: only an explicit False establishes anything
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    ["reaches_broker", "credential_bearing", "route_bearing", "risk_relevant_live"],
)
def test_an_unestablished_nature_flag_is_conservatively_broker_consuming(field: str) -> None:
    """(§4.2 negative polarity) ``None`` is not ``False`` — an unknown nature never passes."""
    nature = synthetic_nature(**{field: None})
    assert _applicability(transport_nature=nature) is BrokerApplicability.UNKNOWN
    assert _deferred_outcomes(transport_nature=nature) == {VerifyOutcome.UNKNOWN}


@pytest.mark.parametrize(
    "field",
    ["reaches_broker", "credential_bearing", "route_bearing", "risk_relevant_live"],
)
def test_a_positively_declared_broker_flag_is_broker_consuming(field: str) -> None:
    """(§4.2) Any positively broker-reaching or risk-relevant-live flag requires the mesh."""
    nature = synthetic_nature(**{field: True})
    assert (
        _applicability(transport_nature=nature)
        is BrokerApplicability.BROKER_RESOURCE_CONSUMING
    )
    assert _deferred_outcomes(transport_nature=nature) == {VerifyOutcome.UNKNOWN}


def test_an_absent_transport_nature_is_unresolved_not_permissive() -> None:
    """(§4.2) No declaration at all is conservatively broker-consuming."""
    assert _applicability(transport_nature=None) is BrokerApplicability.UNKNOWN
    assert _deferred_outcomes(transport_nature=None) == {VerifyOutcome.UNKNOWN}


def test_an_anonymous_transport_principal_is_unresolved() -> None:
    """(§4.2) An unnamed principal cannot be corroborated against the inventory."""
    assert (
        _applicability(transport_nature=TransportNature(reaches_broker=False))
        is BrokerApplicability.UNKNOWN
    )


# ---------------------------------------------------------------------------
# environment binding (§4.7)
# ---------------------------------------------------------------------------


def test_a_scope_outside_the_injected_non_live_test_token_is_unresolved() -> None:
    """(§4.7) The synthetic path binds to the injected non-live-test scope, positively."""
    assert _applicability(scope_environment="live") is BrokerApplicability.UNKNOWN


def test_cross_environment_inheritance_is_refused() -> None:
    """(BC-INV-009:223) Paper evidence never automatically establishes another environment."""
    assert _applicability(environment_inherited=True) is BrokerApplicability.UNKNOWN
    assert _applicability(environment_inherited=None) is BrokerApplicability.UNKNOWN


def test_mismatched_evidence_and_scope_environments_are_refused() -> None:
    """(BC-INV-009) The evidence must bind to *this* scope's environment."""
    assert _applicability(evidence_environment="live") is BrokerApplicability.UNKNOWN


def test_an_uninjected_environment_token_is_unresolved() -> None:
    """(§9 — no hardcoded scope) Without the injected token there is nothing to bind to."""
    assert _applicability(non_live_test_environment_token=None) is BrokerApplicability.UNKNOWN


# ---------------------------------------------------------------------------
# the honest consequence: a real paper API call would be denied here
# ---------------------------------------------------------------------------


def test_a_real_paper_broker_call_is_denied_even_though_it_is_non_live() -> None:
    """(§2.2 MAJOR-1 / §4.7) The axis is broker-reached / synthetic, not live / non-live.

    This is the design's load-bearing correction in mechanical form: a transport that reaches a
    real broker's paper endpoint is ``environment: non-live-test`` **and** broker-resource-
    consuming, so RFC-002 §10.8:741 triggers the whole verify list for it and the not-landed
    safety-governance mesh makes the required facts unverifiable ⇒ §10.8:761 rejection.
    """
    real_paper = synthetic_nature(
        reaches_broker=True, credential_bearing=True, route_bearing=True
    )
    attempt, context = happy_context(
        transport_nature=real_paper,
        scope_environment=NON_LIVE_TEST_ENVIRONMENT,
        evidence_environment=NON_LIVE_TEST_ENVIRONMENT,
    )
    verification = verify_send_boundary(attempt=attempt, context=context)
    assert verification.applicability is BrokerApplicability.BROKER_RESOURCE_CONSUMING
    assert verification.admitted is not True
    assert verification.halt_reason is SendHaltReason.VERIFY_ITEM_UNKNOWN
    assert verification.halt_item is SendVerifyItem.CURRENT_SAFETY_AUTHORITY_EPOCH
    assert "unverifiable" in (verification.detail or "")


def test_a_broker_consuming_send_also_loses_the_brokercap_allowance_item() -> None:
    """(§4.1 item 6 / §1.1-3) A VERIFIED-0 profile is structurally PROHIBITED for live paths."""
    attempt, context = happy_context(
        transport_nature=synthetic_nature(reaches_broker=True),
        broker_capability_profile=None,
        required_capability_set=None,
    )
    verification = verify_send_boundary(attempt=attempt, context=context)
    allowance = next(
        v
        for v in verification.verdicts
        if v.item is SendVerifyItem.ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY
    )
    assert allowance.outcome is VerifyOutcome.DENIED
    assert "PROHIBITED" in (allowance.reason or "")
