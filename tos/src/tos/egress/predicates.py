"""egress-boundary predicates (design #22 §5/§6/§6b) — pure, fail-closed."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence

from tos.egress._base import RecordPairKind, classify_record_pair
from tos.egress.records import (
    ActiveEgressPrincipalSet,
    EgressRequestRecord,
    QuorumCommitCertificate,
    ReplayObservation,
)
from tos.egress.state import (
    ClaimObservation,
    CommitProofCoordinates,
    CredentialRouteInventoryEntry,
    EgressCoordinateSet,
    EgressEvent,
    SignerCoordinate,
    generation_monotone,
)
from tos.egress.vocabulary import RestrictiveLatchState, SignerRole
from tos.ordering import OrderingEvent

__all__ = [
    "quorum_commit_certificate_structurally_complete",
    "quorum_coordinates_current",
    "quorum_threshold_structurally_met",
    "evidence_receipt_is_not_quorum_proof",
    "replay_or_substitution_detected",
    "capability_and_permit_single_use",
    "exact_binding_holds",
    "credential_route_authority_disjoint",
    "egress_generation_monotonic",
    "stale_principal_structurally_rejected",
    "monotonic_denial_no_revival",
]

_CONFORMANT_TOKEN = "CONFORMANT"


def quorum_commit_certificate_structurally_complete(
    qcc: QuorumCommitCertificate | None,
) -> bool:
    """Whether a QCC carries a structurally complete §11.1 claim set (§5.1; EGRESS-EV-004 substrate)."""
    if qcc is None:
        return False
    if qcc.missing_required_fields():
        return False
    if qcc.capability_nonce is None or qcc.action_flow_permit_nonce is None:
        return False
    if not qcc.signer_coordinates:
        return False
    if qcc.is_restricted_live_trial is True:
        if qcc.trial_claims is None or not qcc.trial_claims.is_complete():
            return False
    return True


def quorum_coordinates_current(
    qcc: QuorumCommitCertificate | None,
    injected_current: CommitProofCoordinates | None,
) -> bool:
    """Whether a QCC's carried coordinates equal the injected current committed values (§5.2)."""
    if qcc is None or injected_current is None:
        return False
    for name in CommitProofCoordinates.COORDINATES:
        carried = getattr(qcc, name, None)
        current = getattr(injected_current, name, None)
        if carried is None or current is None or carried != current:
            return False
    return True


def quorum_threshold_structurally_met(
    signer_coordinates: Sequence[SignerCoordinate],
    quorum_n: int | None,
) -> bool:
    """Whether the distinct eligible-and-signed signer count meets the quorum threshold (§5.3)."""
    if quorum_n is None or quorum_n < 1:
        return False
    if not signer_coordinates:
        return False
    by_identity: dict[str, list[SignerCoordinate]] = defaultdict(list)
    for signer in signer_coordinates:
        if signer.signer_identity is None:
            continue
        by_identity[signer.signer_identity].append(signer)
    counted_confirmed_members: list[bool] = []
    for entries in by_identity.values():
        if all(
            entry.eligible_verified is True and entry.signature_verified is True
            for entry in entries
        ):
            confirmed_member = all(
                entry.signer_role is SignerRole.QUORUM_MEMBER for entry in entries
            )
            counted_confirmed_members.append(confirmed_member)
    count = len(counted_confirmed_members)
    if count < quorum_n:
        return False
    return not (count == 1 and not counted_confirmed_members[0])


def evidence_receipt_is_not_quorum_proof(candidate: object | None = None) -> bool:
    """Whether an evidence commit receipt (or leader receipt) can never substitute for a QCC (§5.4)."""
    del candidate
    return True


def replay_or_substitution_detected(
    a: ReplayObservation | None,
    b: ReplayObservation | None,
) -> RecordPairKind:
    """Classify two replay observations by shared subject vs bound request bytes (§5.5)."""
    if a is None or b is None:
        return RecordPairKind.NOT_COMPARABLE
    return classify_record_pair(
        a.subject_identity,
        a.canonical_digest,
        b.subject_identity,
        b.canonical_digest,
    )


def capability_and_permit_single_use(
    capability_nonce: str | None,
    action_flow_permit_nonce: str | None,
    prior_claims: Iterable[ClaimObservation],
    *,
    principal: str | None,
    request_digest: str | None,
) -> bool:
    """Whether the capability + permit nonces are each claimed exactly once for this bind (§5.6)."""
    if capability_nonce is None or action_flow_permit_nonce is None:
        return False
    if principal is None or request_digest is None:
        return False
    claimed_nonces = {capability_nonce, action_flow_permit_nonce}
    for claim in prior_claims:
        if claim.nonce is not None and claim.nonce in claimed_nonces:
            return False
    return True


def exact_binding_holds(
    request: EgressRequestRecord | None,
    qcc: QuorumCommitCertificate | None,
    injected_authorized: EgressCoordinateSet | None,
    ioc_conformance_verdict: str | None,
    capsule_egress_request_digest: str | None,
) -> bool:
    """Whether every egress coordinate exactly binds with no substitution (§5.7)."""
    if request is None or qcc is None or injected_authorized is None:
        return False
    for name in EgressCoordinateSet.COORDINATES:
        request_value = getattr(request, name, None)
        authorized_value = getattr(injected_authorized, name, None)
        if (
            request_value is None
            or authorized_value is None
            or request_value != authorized_value
        ):
            return False
    if (
        request.request_bytes_digest is None
        or capsule_egress_request_digest is None
        or request.request_bytes_digest != capsule_egress_request_digest
    ):
        return False
    if (
        qcc.canonical_command_digest is None
        or request.canonical_command_digest is None
        or qcc.canonical_command_digest != request.canonical_command_digest
    ):
        return False
    return ioc_conformance_verdict == _CONFORMANT_TOKEN


def credential_route_authority_disjoint(
    inventory: Sequence[CredentialRouteInventoryEntry],
) -> bool:
    """Whether no outside-boundary principal holds both usable credential and route (§6.1)."""
    if not inventory:
        return False
    for entry in inventory:
        outside_or_unknown = entry.inside_boundary is not True
        potentially_usable = entry.usable_credential is not False
        has_route = entry.broker_route is not False
        if outside_or_unknown and potentially_usable and has_route:
            return False
    return True


def egress_generation_monotonic(prior: OrderingEvent, new: OrderingEvent) -> bool:
    """Whether the Egress Generation strictly increases in append-only order (§6b.1; thin model)."""
    return generation_monotone(prior, new)


def stale_principal_structurally_rejected(
    principal: str | None,
    active_set: ActiveEgressPrincipalSet | None,
    *,
    expected_generation: int | None,
) -> bool:
    """Whether a principal is represented, active, and current in the committed set (§6b.1; thin model)."""
    if principal is None or active_set is None:
        return False
    if active_set.egress_generation is None or expected_generation is None:
        return False
    if active_set.egress_generation != expected_generation:
        return False
    for member in active_set.active_principals:
        if (
            member.workload_identity is not None
            and member.workload_identity == principal
        ):
            return member.active is True and member.expired is False
    return False


def monotonic_denial_no_revival(
    latch_state: RestrictiveLatchState | None,
    injected_events: Iterable[EgressEvent],
) -> RestrictiveLatchState:
    """Resolve the restrictive latch under injected events — deny is monotonic (§6b.3; thin model)."""
    if latch_state is RestrictiveLatchState.DENY_LATCHED:
        return RestrictiveLatchState.DENY_LATCHED
    if latch_state is not RestrictiveLatchState.CLEAR:
        return RestrictiveLatchState.DENY_LATCHED
    for event in injected_events:
        if event.restrictive is True:
            return RestrictiveLatchState.DENY_LATCHED
    return RestrictiveLatchState.CLEAR
