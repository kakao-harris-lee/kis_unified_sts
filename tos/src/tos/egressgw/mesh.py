"""The broker-applicability positive gate + the deferred safety-governance mesh judgement
(design #34 §4.2; kernel round #2 §2 decision 1 — split out of ``gateway.py``).

Two functions live here, both public (the leading underscore is dropped — kernel round #2 §2
decision 1):

* :func:`resolve_broker_applicability` — the §4.2 positive gate that decides whether a send
  consumes a broker resource *before* any per-item check runs.
* :func:`deferred_item_verdict` — judges one of the six deferred live safety-governance mesh
  items (:data:`~tos.egressgw.vocabulary.DEFERRED_ITEMS`), now reading the six injected
  :class:`~tos.egressgw.records.SendBoundaryContext` fields the owning runtime services supply
  (kernel round #2 §2 decision 2), rather than returning ``UNKNOWN`` unconditionally.

Both are consumed by :func:`~tos.egressgw.gateway.verify_send_boundary`, which still runs the
gate first and still dispatches every :data:`~tos.egressgw.vocabulary.DEFERRED_ITEMS` member
through :func:`deferred_item_verdict` — only the module each function lives in, and
:func:`deferred_item_verdict`'s signature, changed.

This module deliberately does **not** import :mod:`tos.egressgw.gateway` (that would be a
circular edge back to the module that imports this one) — the import-closure test pins this
absence structurally (kernel round #2 §2 decision 1 / mutation M5).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #34 §0.3). No clock, no RNG, no network.
"""

from __future__ import annotations

from tos.brokercap import environment_binding_ok
from tos.egress import credential_route_authority_disjoint
from tos.egressgw._base import ArtifactIntegrityError, _verdict
from tos.egressgw.records import SendBoundaryContext, TransportNature, VerifyItemVerdict
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

#: The closed item -> ``SendBoundaryContext`` field mapping the deferred mesh judges (kernel
#: round #2 §2 decision 2). Exactly the six :data:`~tos.egressgw.vocabulary.DEFERRED_ITEMS`
#: members — an item outside this table is a structural error (mutation M6), never a silent
#: ``UNKNOWN``.
_DEFERRED_ITEM_FIELDS: dict[SendVerifyItem, str] = {
    SendVerifyItem.CURRENT_SAFETY_AUTHORITY_EPOCH: "safety_authority_epoch_current",
    SendVerifyItem.VALID_LIVE_SCOPE: "live_scope_valid",
    SendVerifyItem.HARD_SAFETY_ENVELOPE_VERSIONS: "safety_profile_current",
    SendVerifyItem.SAFETY_DEVIATION: "deviation_clear",
    SendVerifyItem.SAFETY_INCIDENT: "incident_clear",
    SendVerifyItem.SAFETY_MONITORING: "monitoring_clear",
}


# ===========================================================================
# §4.2 — the broker-applicability positive gate (runs BEFORE the per-item gates)
# ===========================================================================


def resolve_broker_applicability(
    nature: TransportNature | None,
    context: SendBoundaryContext,
) -> BrokerApplicability:
    """Positively establish whether this send consumes a broker resource (design #34 §4.2).

    RFC-002 §10.8:741 triggers the verify list "before any risk-relevant **or**
    broker-resource-consuming transmission", so this — not live / non-live — is the axis that
    decides whether the deferred safety-governance mesh is required (design #34 MAJOR-1).

    Returns :attr:`~tos.egressgw.vocabulary.BrokerApplicability.NON_BROKER_SYNTHETIC` **only**
    when every one of the following positively holds:

    1. the declared :class:`~tos.egressgw.records.TransportNature` names a principal and carries
       ``reaches_broker is False``, ``credential_bearing is False``, ``route_bearing is False``,
       and ``risk_relevant_live is False`` — **explicit ``False``**, because a ``None`` is an
       unestablished nature and is conservatively broker-consuming (negative polarity, §4.2);
    2. that declaration is **structurally corroborated**: the transport principal is explicitly
       represented in the injected credential-route inventory holding neither a usable credential
       (``usable_credential is False``) nor a broker route (``broker_route is False``). A
       self-report alone never establishes it — the structural fact is that a synthetic transport
       does not constitute the ADR-002-013 §1 Final Egress Trust Boundary at all, and that is
       what the inventory shows (design #34 §1.1-1 / §4.5);
    3. egress :func:`~tos.egress.credential_route_authority_disjoint` holds over the whole
       inventory — an ∅ inventory is ``False`` there (disjointness unproven), so an empty
       inventory can never produce a synthetic verdict;
    4. the environment binds positively to the injected non-live-test scope token through
       brokercap :func:`~tos.brokercap.environment_binding_ok` (profile- and VERIFIED-independent
       — BC-INV-009 §4.7).

    Any positively-established broker-reaching or risk-relevant-live flag returns
    ``BROKER_RESOURCE_CONSUMING``; anything unestablished returns ``UNKNOWN``. **Both** make the
    deferred mesh required, so the fail-closed behaviour is identical — the distinction exists so
    the recorded evidence says which it was.

    Args:
        nature: The declared transport nature (``None`` ⇒ ``UNKNOWN``).
        context: The send-boundary context carrying the inventory and environment coordinates.

    Returns:
        The :class:`~tos.egressgw.vocabulary.BrokerApplicability` verdict.
    """
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
                # The principal is represented but holds (or may hold) a credential or a route:
                # that is a broker-reaching transport whatever it declared about itself.
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


# ===========================================================================
# §4.2 — the deferred live safety-governance mesh (items 4, 5, 7, 8, 9, 10)
# ===========================================================================


def deferred_item_verdict(
    item: SendVerifyItem,
    applicability: BrokerApplicability,
    context: SendBoundaryContext,
) -> VerifyItemVerdict:
    """Judge one deferred safety-governance mesh item (kernel round #2 §2 decision 2).

    ``NOT_APPLICABLE`` **only** for a positively established synthetic non-broker send — a
    recorded positive judgement, never a silent skip (design #34 §4.2, unchanged).

    Otherwise the item is required, and this reads the one
    :class:`~tos.egressgw.records.SendBoundaryContext` field :data:`_DEFERRED_ITEM_FIELDS` maps
    it to — the owning runtime service's own positively-supplied flag, threaded from the caller
    (compose) rather than derived here (the kernel judges positivity only):

    * ``is True`` ⇒ ``SATISFIED`` — positively supplied by the owning runtime service.
    * ``is False`` ⇒ ``DENIED`` — an explicit negative signal is a denial, not an unknown
      (kernel round #2 §3 기각 대안: folding ``False`` into ``UNKNOWN`` would lose the
      operational service's own "not clear" judgement).
    * ``None`` ⇒ ``UNKNOWN`` — the owning runtime has not landed the fact, which is a rejection
      (RFC-002 §10.8:741 → :761).

    Args:
        item: One of the six :data:`~tos.egressgw.vocabulary.DEFERRED_ITEMS` members.
        applicability: The §4.2 gate's verdict for this send.
        context: The send-boundary context carrying the six injected mesh flags.

    Returns:
        The :class:`~tos.egressgw.records.VerifyItemVerdict`.

    Raises:
        ArtifactIntegrityError: ``item`` is not one of the six closed
            :data:`_DEFERRED_ITEM_FIELDS` members — a structural error, never a silent
            ``UNKNOWN`` (mutation M6).
    """
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
            f"{item!r} is not one of the six deferred safety-governance mesh items "
            f"{sorted(f.value for f in _DEFERRED_ITEM_FIELDS)} — deferred_item_verdict judges "
            "only the closed CURRENT_SAFETY_AUTHORITY_EPOCH / VALID_LIVE_SCOPE / "
            "HARD_SAFETY_ENVELOPE_VERSIONS / SAFETY_DEVIATION / SAFETY_INCIDENT / "
            "SAFETY_MONITORING set (design #34 §4.2; kernel round #2 §2 decision 2) — an item "
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
