"""The broker-applicability positive gate + the deferred safety-governance mesh judgement"""

from __future__ import annotations

from tos.brokercap import environment_binding_ok
from tos.egress import credential_route_authority_disjoint
from tos.egressgw._base import ArtifactIntegrityError
from tos.egressgw.records import (
    SendBoundaryContext,
    TransportNature,
    VerifyItemVerdict,
    _verdict,
)
from tos.egressgw.vocabulary import (
    BrokerApplicability,
    SendVerifyItem,
    VerifyOutcome,
    verify_item_number,
)

__all__ = [
    "deferred_item_verdict",
    "resolve_broker_applicability",
]

_DEFERRED_ITEM_FIELDS: dict[SendVerifyItem, str] = {
    SendVerifyItem.VALID_LIVE_SCOPE: "live_scope_valid",
}


def resolve_broker_applicability(
    nature: TransportNature | None,
    context: SendBoundaryContext,
) -> BrokerApplicability:
    """Positively establish whether this send consumes a broker resource (design #34 §4.2)."""
    if nature is None:
        return BrokerApplicability.UNKNOWN
    if (
        nature.reaches_broker is True
        or nature.credential_bearing is True
        or nature.route_bearing is True
        or nature.risk_relevant_live is True
    ):
        return BrokerApplicability.BROKER_RESOURCE_CONSUMING
    if not (
        nature.reaches_broker is False
        and nature.credential_bearing is False
        and nature.route_bearing is False
        and nature.risk_relevant_live is False
    ):
        return BrokerApplicability.UNKNOWN
    principal = nature.principal
    if principal is None or not principal.strip():
        return BrokerApplicability.UNKNOWN
    inventory = context.credential_route_inventory
    if not credential_route_authority_disjoint(inventory):
        return BrokerApplicability.UNKNOWN
    corroborated = False
    for entry in inventory:
        if entry.principal == principal:
            if entry.usable_credential is False and entry.broker_route is False:
                corroborated = True
            else:
                return BrokerApplicability.BROKER_RESOURCE_CONSUMING
    if not corroborated:
        return BrokerApplicability.UNKNOWN
    if context.non_live_test_environment_token is None:
        return BrokerApplicability.UNKNOWN
    if context.scope_environment != context.non_live_test_environment_token:
        return BrokerApplicability.UNKNOWN
    if not environment_binding_ok(
        context.evidence_environment,
        context.scope_environment,
        context.environment_inherited,
    ):
        return BrokerApplicability.UNKNOWN
    return BrokerApplicability.NON_BROKER_SYNTHETIC


def deferred_item_verdict(
    item: SendVerifyItem,
    applicability: BrokerApplicability,
    context: SendBoundaryContext,
) -> VerifyItemVerdict:
    """Judge one deferred safety-governance mesh item (kernel round #2 §2 decision 2)."""
    if applicability is BrokerApplicability.NON_BROKER_SYNTHETIC:
        return _verdict(
            item,
            VerifyOutcome.NOT_APPLICABLE,
            reason=(
                f"item {verify_item_number(item)} is not applicable: the send was positively "
                "established as synthetic and non-broker-reaching, so no broker resource is "
                "consumed and no live scope is in play. The justification is 'no broker route "
                "was reached', NOT 'no live scope was armed' — a real paper-account API call is "
                "non-live and still broker-resource-consuming, and would be denied here "
                "(design #34 §4.2/§4.7)"
            ),
            native_value=applicability.value,
        )
    if item not in _DEFERRED_ITEM_FIELDS:
        raise ArtifactIntegrityError(
            f"{item!r} is not one of the deferred safety-governance mesh items "
            f"{sorted(f.value for f in _DEFERRED_ITEM_FIELDS)} — deferred_item_verdict judges "
            "only the closed VALID_LIVE_SCOPE set "
            "(design #34 §4.2; kernel round #2 §2 decision 2) — an item "
            "outside it is a structural error, never a silent UNKNOWN"
        )
    flag = getattr(context, _DEFERRED_ITEM_FIELDS[item])
    if flag is True:
        return _verdict(
            item,
            VerifyOutcome.SATISFIED,
            reason=(
                f"item {verify_item_number(item)} was positively supplied by the owning "
                "runtime service (kernel round #2 §2 decision 2)"
            ),
            native_value=applicability.value,
        )
    if flag is False:
        return _verdict(
            item,
            VerifyOutcome.DENIED,
            reason=(
                f"item {verify_item_number(item)} was explicitly denied by the owning runtime "
                "service — an explicit negative signal is a denial, not an unknown "
                "(kernel round #2 §2 decision 2)"
            ),
            native_value=applicability.value,
        )
    return _verdict(
        item,
        VerifyOutcome.UNKNOWN,
        reason=(
            f"item {verify_item_number(item)} is required for a "
            f"{applicability.value} send and its owning runtime has not landed — the required "
            "fact is unverifiable, which is a rejection (RFC-002 §10.8:741 → :761); "
            "design #34 §4.1 records this item as Deferred"
        ),
        native_value=applicability.value,
    )
