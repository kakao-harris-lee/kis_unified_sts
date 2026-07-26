"""Shared valid-artifact builders + strategies for the egress property tests (design #22 §7).

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #22 §0.3). The builders enforce
the §7 clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture must be *genuinely*
complete / bound, never a permissive shortcut):

* a **clean** QCC carries every ``_REQUIRED_COVERED`` coordinate concrete, both single-use nonces,
  and a genuine two-distinct-signer quorum (all eligible + signed), so a genuine admission is
  achievable;
* a **clean** current-coordinate mirror matches the clean QCC field-for-field, so ``quorum_
  coordinates_current`` is genuinely satisfiable (not a shortcut);
* the **∅ strategies** deliberately generate empty signer / inventory sets so the ∅-void guards are
  actually exercised (the #10 lesson — a strategy that never emits ∅ leaves the ∅ branch untested).

Every quorum / generation value is an explicit fixture int — nothing here is a *policy* number; the
real egress bounds are Verification-Profile injected and all null / TBD in Phase 1 (design #22 §8.1).
The reserved ``"TBD"`` placeholder is excluded from required-field text.
"""

from __future__ import annotations

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.egress import (
    ActiveEgressPrincipalSet,
    CommitProofCoordinates,
    CredentialRouteInventoryEntry,
    EgressCoordinateSet,
    EgressPrincipal,
    EgressRequestRecord,
    QuorumCommitCertificate,
    ReplayObservation,
    SignerCoordinate,
    SignerRole,
)

#: The injected provisional canonicalizer (REUSE, design #22 §3.1 — no new scheme).
SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved ``"TBD"``).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")
#: Injected ``bool | None`` flag (fail-closed on ``None`` / ``False``).
TRIBOOL = st.sampled_from([True, False, None])

#: The clean commit-proof / egress coordinate values shared by the clean QCC + current mirror.
_CLEAN_COORDS = {
    "cluster_identity": "cluster-A",
    "capacity_domain": "domain-A",
    "membership_generation": 7,
    "restore_generation": 2,
    "writer_epoch": 4,
    "committed_revision": 42,
    "canonical_command_digest": "cmd-digest",
    "resulting_state_digest": "state-digest",
    "egress_generation": 9,
    "credential_generation": 3,
    "broker_session_generation": 5,
    "route_policy_generation": 6,
    "trust_bundle_generation": 8,
}

#: The clean exact-binding egress coordinate values shared by the clean request + authorized set.
_CLEAN_EGRESS_COORDS = {
    "endpoint": "endpoint-1",
    "account": "acct-1",
    "environment": "paper",
    "action": "NEW_LONG",
    "method": "POST",
    "route_identity": "route-1",
    "credential_generation": 3,
    "broker_session_generation": 5,
    "egress_generation": 9,
    "active_principal": "principal-1",
}


# ---------------------------------------------------------------------------
# Clean builders (genuinely complete / bound — the #8 lesson)
# ---------------------------------------------------------------------------


def clean_signer(
    *,
    signer_identity: str,
    signer_role: SignerRole = SignerRole.QUORUM_MEMBER,
    eligible_verified: bool | None = True,
    signature_verified: bool | None = True,
) -> SignerCoordinate:
    """One signer coordinate (default eligible + signed — a genuine countable member)."""
    return SignerCoordinate(
        signer_identity=signer_identity,
        signer_role=signer_role,
        eligible_verified=eligible_verified,
        signature_verified=signature_verified,
    )


def clean_signers() -> tuple[SignerCoordinate, SignerCoordinate]:
    """Two distinct eligible-and-signed quorum members — a genuine quorum of 2."""
    return (
        clean_signer(signer_identity="member-alpha"),
        clean_signer(signer_identity="member-beta"),
    )


def clean_qcc(
    *,
    qcc_id: str = "qcc-1",
    signer_coordinates: tuple[SignerCoordinate, ...] | None = None,
    **overrides: object,
) -> QuorumCommitCertificate:
    """A digest-verified, structurally complete QCC (id ⊥ digest, all-false authority)."""
    content: dict[str, object] = dict(_CLEAN_COORDS)
    content.update(
        {
            "active_egress_principal": "principal-1",
            "capability_nonce": "cap-nonce-1",
            "action_flow_permit_nonce": "afp-nonce-1",
        }
    )
    content.update(overrides)
    signers = signer_coordinates if signer_coordinates is not None else clean_signers()
    return QuorumCommitCertificate.issue(
        scheme=SCHEME,
        qcc_id=qcc_id,
        signer_coordinates=signers,
        **content,
    )


def clean_current_coordinates(**overrides: object) -> CommitProofCoordinates:
    """The injected current committed coordinates matching :func:`clean_qcc` field-for-field."""
    values = dict(_CLEAN_COORDS)
    values.update(overrides)
    return CommitProofCoordinates(**values)


def clean_request(
    *,
    request_id: str = "req-1",
    canonical_command_digest: str = "cmd-digest",
    request_bytes_digest: str = "bytes-digest",
    **overrides: object,
) -> EgressRequestRecord:
    """A digest-verified exact outbound request matching the clean authorized coordinates."""
    content: dict[str, object] = dict(_CLEAN_EGRESS_COORDS)
    content.update(overrides)
    return EgressRequestRecord.issue(
        scheme=SCHEME,
        request_id=request_id,
        canonical_command_digest=canonical_command_digest,
        request_bytes_digest=request_bytes_digest,
        **content,
    )


def clean_authorized_coordinates(**overrides: object) -> EgressCoordinateSet:
    """The injected authorized egress coordinates matching :func:`clean_request` field-for-field."""
    values = dict(_CLEAN_EGRESS_COORDS)
    values.update(overrides)
    return EgressCoordinateSet(**values)


def clean_active_set(
    *,
    set_id: str = "aeps-1",
    egress_generation: int = 9,
    principals: tuple[EgressPrincipal, ...] | None = None,
) -> ActiveEgressPrincipalSet:
    """A committed active-principal set with one live, current, unexpired principal."""
    members = (
        principals
        if principals is not None
        else (
            EgressPrincipal(
                workload_identity="principal-1", active=True, expired=False
            ),
        )
    )
    return ActiveEgressPrincipalSet.issue(
        scheme=SCHEME,
        set_id=set_id,
        egress_generation=egress_generation,
        active_principals=members,
    )


def clean_replay_observation(
    *,
    observation_id: str,
    subject_identity: str = "proof-1",
    bound_request_digest: str = "bytes-A",
    principal: str = "principal-1",
    endpoint: str = "endpoint-1",
    egress_generation: int = 9,
) -> ReplayObservation:
    """A digest-verified replay observation (subject_identity ⊥ digest for §5.5 classify)."""
    return ReplayObservation.issue(
        scheme=SCHEME,
        observation_id=observation_id,
        subject_identity=subject_identity,
        bound_request_digest=bound_request_digest,
        principal=principal,
        endpoint=endpoint,
        egress_generation=egress_generation,
    )


def clean_inventory_entry(
    *,
    principal: str,
    usable_credential: bool | None,
    broker_route: bool | None,
    inside_boundary: bool | None,
) -> CredentialRouteInventoryEntry:
    """One credential-route inventory entry."""
    return CredentialRouteInventoryEntry(
        principal=principal,
        usable_credential=usable_credential,
        broker_route=broker_route,
        inside_boundary=inside_boundary,
    )


# ---------------------------------------------------------------------------
# Hypothesis strategies (∅ deliberately reachable — the #10 lesson)
# ---------------------------------------------------------------------------


@st.composite
def signer_sets(draw: st.DrawFn) -> tuple[tuple[SignerCoordinate, ...], int]:
    """A random signer coordinate tuple (∅ reachable) + a random quorum N (0 reachable).

    Returns ``(signers, quorum_n)`` so a property test can predict the distinct eligible-and-signed
    count against the threshold. Each signer has an independently-drawn identity, role, and injected
    ``eligible_verified`` / ``signature_verified`` tri-bool (so dedup-B conflicts are reachable).
    """
    signers = draw(
        st.lists(
            st.builds(
                SignerCoordinate,
                signer_identity=st.sampled_from(["a", "b", "c", None]),
                signer_role=st.sampled_from(
                    [SignerRole.QUORUM_MEMBER, SignerRole.LEADER, None]
                ),
                eligible_verified=TRIBOOL,
                signature_verified=TRIBOOL,
            ),
            max_size=6,
        )
    )
    quorum_n = draw(st.integers(min_value=0, max_value=4))
    return tuple(signers), quorum_n


def _counted_confirmed_members(
    signers: tuple[SignerCoordinate, ...],
) -> list[bool]:
    """Group by identity (dedup-B) and, per counted identity, reconcile the role across entries.

    A counted identity (EVERY entry eligible + signed) records whether its role is a *positively
    confirmed* QUORUM_MEMBER across EVERY entry — a role conflict (any entry LEADER / None) leaves
    it NOT confirmed (independent reference for the MAJOR-1 role-reconcile).
    """
    from collections import defaultdict

    groups: dict[str, list[SignerCoordinate]] = defaultdict(list)
    for signer in signers:
        if signer.signer_identity is None:
            continue
        groups[signer.signer_identity].append(signer)
    confirmed: list[bool] = []
    for entries in groups.values():
        if all(
            e.eligible_verified is True and e.signature_verified is True
            for e in entries
        ):
            confirmed.append(
                all(e.signer_role is SignerRole.QUORUM_MEMBER for e in entries)
            )
    return confirmed


def distinct_eligible_signed_count(
    signers: tuple[SignerCoordinate, ...],
) -> int:
    """The oracle: count distinct identities whose EVERY entry is eligible + signed (dedup-B)."""
    return len(_counted_confirmed_members(signers))


def expected_quorum_threshold(
    signers: tuple[SignerCoordinate, ...],
    quorum_n: int | None,
) -> bool:
    """The full bidirectional oracle for :func:`quorum_threshold_structurally_met` (§5.3).

    An independent reference implementation of the §5.3 spec including the MAJOR-1 role-reconcile:
    a non-degenerate quorum (``quorum_n >= 1``, non-empty signers) is met when the count of distinct
    eligible-and-signed identities is ``>= quorum_n`` AND the quorum does not reduce to a single
    identity that is not a positively-confirmed QUORUM_MEMBER (a lone LEADER / None-role / role-
    conflicted identity is rejected, order-independently).
    """
    if quorum_n is None or quorum_n < 1:
        return False
    if not signers:
        return False
    confirmed = _counted_confirmed_members(signers)
    count = len(confirmed)
    if count < quorum_n:
        return False
    return not (count == 1 and not confirmed[0])
