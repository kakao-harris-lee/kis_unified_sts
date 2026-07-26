"""egress-boundary predicates (design #22 §5/§6/§6b) — pure, fail-closed.

Pure decision rules over injected frozen models (design #22 §0.2/§4.6): egress authors the
**egress-boundary structural / coordinate model** — Quorum Commit Certificate structural
completeness, quorum coordinate currency, quorum threshold shape, evidence-receipt-is-not-QCC
rejection, replay / substitution classification, capability / permit single-use, exact binding,
credential-route disjointness, egress-generation monotonicity, stale-principal rejection, and
monotonic denial non-revival. It **re-authors none** of the sibling instances it feeds or consumes:
rcl owns the ADR-002-012 Commit Proof coordinates + ``claim_capability`` nonce ledger +
``TransmissionCapability`` + ``writer_fenced`` (§0.4b/§3.5), ioc owns the command-conformance
verdict ``derived_command_conformance`` / ``mutation_fence_holds`` (§0.4c), evidence owns the commit
receipt / segment-commitment (§0.4d), capsule owns the ``Bindings`` forward-reference chain
(§0.4e), venue / iap / capsule own their per-decision egress-currentness and CUR (not landed) owns
the complete-vector aggregation (§0.4f), and brokercap / protective / recon / authority / liveauth
own their profile / lease / external / epoch / Live-Authorization verdicts (§0.4g). egress
**consumes** every one of those as an **injected produced scalar / bool / verdict / digest** and
re-authors none of them (sibling edge 0).

**The over-realization boundary (design #22 §1/§5.3 — this package's maximum risk).** This is the
thinnest L1 surface in the series. The cryptographic signature validity, the quorum consensus /
durability, the bypass resistance, the credential custody, the route / env enforcement, and the
rotation / failover / compromise runtime are **all +Security** — L1 owns only structural
completeness, coordinate equality / currency, distinct-count-over-injected-flags, the
``classify_record_pair`` replay / substitution classification, single-use, and the monotonic
non-revival state machine. ``quorum_threshold_structurally_met`` is a distinct-count over
**injected** verification flags, **not** a signature or consensus check; a green result means the
carried claim set is quorum-shaped, never that a quorum committed.

**Truthy-sentinel discipline (design #22 §4.7).** ``EgressAdmission`` / ``CommitProofValidity`` /
``RestrictiveLatchState`` are truthy-untestable ``StrEnum``s (``__bool__`` raises), so every gate
uses ``x is ENUM.SAFE_VALUE``; a bare ``if state:`` would fail open reading ``DENY_LATCHED`` as
clear. Injected ``bool | None`` flags are normalized with ``is True`` / ``is not True`` / ``is
False`` (a ``None`` is UNKNOWN, never a soft pass).

Pure module: ``pydantic`` + stdlib + ``tos.egress.*`` (records / state / vocabulary / _base) +
``tos.ordering`` (via ``tos.egress.state.generation_monotone``) only; no ``shared.*``, no other
sibling ``tos.*`` (design #22 §0.3).
"""

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
    # core §5 (EGRESS-EV-004/005 substrate)
    "quorum_commit_certificate_structurally_complete",
    "quorum_coordinates_current",
    "quorum_threshold_structurally_met",
    "evidence_receipt_is_not_quorum_proof",
    "replay_or_substitution_detected",
    "capability_and_permit_single_use",
    "exact_binding_holds",
    # predicate-only §6.1 (EGRESS-EV-001 substrate)
    "credential_route_authority_disjoint",
    # not-Phase-1 thin model §6b (EGRESS-EV-002/006/007 substrate)
    "egress_generation_monotonic",
    "stale_principal_structurally_rejected",
    "monotonic_denial_no_revival",
]

#: The injected ioc conformance verdict token accepted by :func:`exact_binding_holds` (§5.7 (iv)).
#: The ioc ``ConformanceResult.CONFORMANT`` verdict is injected as an enum-token (str); egress
#: re-authors **no** ioc conformance decision (sibling edge 0, §0.4c). Contract asserted by the
#: ``test_seam_ioc.py`` cross-check (``ConformanceResult.CONFORMANT.value == _CONFORMANT_TOKEN``).
_CONFORMANT_TOKEN = "CONFORMANT"


# ===========================================================================
# core §5.1-§5.4 — Quorum Commit Certificate structural validation (EGRESS-EV-004)
# ===========================================================================


def quorum_commit_certificate_structurally_complete(
    qcc: QuorumCommitCertificate | None,
) -> bool:
    """Whether a QCC carries a structurally complete §11.1 claim set (§5.1; EGRESS-EV-004 substrate).

    ``True`` **only** when (i) every ``_REQUIRED_COVERED`` field (commit-proof coordinates, egress
    generation, active principal) is concrete, (ii) both single-use nonces (``capability_nonce`` /
    ``action_flow_permit_nonce``) are concrete (§11.2 step 17), (iii) ``signer_coordinates`` is
    **non-empty** (§4.7), and (iv) a positively-claimed restricted-live trial carries a complete
    trial group (the malformed-model ``model_construct`` re-check — defence in depth, §2.3). A
    ``None`` QCC or any missing / ``None`` field ⇒ ``False`` (fail-closed).

    **Over-realization boundary (§5.1):** this is **structural completeness only** — whether the
    quorum actually durably committed is §5.2 / §5.3 + +Security. The construction-time validator
    already rejects an ISSUED QCC with a ``None`` required field and a malformed trial claim; this
    predicate re-checks so a ``model_construct`` bypass cannot pass a complete-flag through (§2.3).

    Args:
        qcc: The Quorum Commit Certificate (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the QCC is structurally complete.
    """
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
    """Whether a QCC's carried coordinates equal the injected current committed values (§5.2).

    ``True`` **only** when every commit-proof / egress coordinate the QCC carries
    (:data:`~tos.egress.state.CommitProofCoordinates.COORDINATES`) is concrete on **both** sides and
    equal (§11.2 step 6-7 line 336-337). Any ``None`` (either side) or mismatch / stale ⇒ ``False``.

    This is **not** an rcl ``writer_fenced`` re-authoring (§3.5): rcl already owns the stale-writer /
    CAS fencing; egress verifies only that the QCC carries the exact current committed coordinates.
    **Over-realization boundary (§5.2):** the actual quorum consensus / durability verification
    (§11.2 step 3) is +Security — L1 is coordinate equality only.

    Args:
        qcc: The Quorum Commit Certificate (``None`` ⇒ ``False``).
        injected_current: The injected current committed commit-proof coordinates (``None`` ⇒
            ``False``).

    Returns:
        ``True`` iff every coordinate is concrete on both sides and equal.
    """
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
    """Whether the distinct eligible-and-signed signer count meets the quorum threshold (§5.3).

    ``True`` **only** when (i) ``quorum_n >= 1`` (a degenerate ``0`` / ``None`` is denial — §4.7
    non-vacuous), (ii) ``signer_coordinates`` is non-empty (§4.7), (iii) the count of **distinct**
    ``signer_identity`` values that are eligible-and-signed is ``>= quorum_n``, and (iv) the quorum
    does not reduce to one ``LEADER`` (§11.2 line 351 "One leader signature ... is insufficient").

    **Dedup interpretation B (v1.1 fail-closed — design #22 §4.7).** A ``signer_identity`` is
    counted **only** when *every* entry carrying it agrees with ``eligible_verified is True`` **and**
    ``signature_verified is True``; if any entry for that identity is ``None`` / ``False``, the whole
    identity is **excluded** from the count (a forged / unverified entry cannot piggy-back on a
    genuine one — the interpretation-A fail-open is blocked; the cost is a spurious-deny on the
    availability side, never a safety hole). A ``None`` ``signer_identity`` cannot be counted.

    **Over-realization boundary (§5.3 — this package's maximum risk).** ``eligible_verified`` /
    ``signature_verified`` are **injected** verified-flags (``is True``): this predicate is a
    distinct-count over those flags, **not** a cryptographic-signature or quorum-consensus check.
    The actual signature verification (§11.2 step 4), the membership-generation eligibility proof,
    and the consensus durability (§11.2 step 3) are **all +Security**. A green result means the
    carried claim set is quorum-shaped, never that a quorum committed.

    Args:
        signer_coordinates: The QCC's quorum signer coordinates (∅ ⇒ ``False``).
        quorum_n: The injected quorum threshold N (``None`` / ``< 1`` ⇒ ``False``).

    Returns:
        ``True`` iff the distinct eligible-and-signed signer count meets a non-degenerate quorum.
    """
    if quorum_n is None or quorum_n < 1:
        return False
    if not signer_coordinates:
        return False
    by_identity: dict[str, list[SignerCoordinate]] = defaultdict(list)
    for signer in signer_coordinates:
        if signer.signer_identity is None:
            continue
        by_identity[signer.signer_identity].append(signer)
    # For each counted identity, record whether its role is a *positively confirmed*
    # QUORUM_MEMBER across EVERY entry (role reconciliation, mirroring the dedup-B discipline):
    # a role conflict (any entry LEADER / None) leaves the identity NOT positively confirmed, so
    # the lone-signer carve-out cannot be bypassed by an input-order-dependent role label (MAJOR-1).
    counted_confirmed_members: list[bool] = []
    for entries in by_identity.values():
        # dedup interpretation B: count only when EVERY entry for this identity agrees True.
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
    # §11.2 line 351 — a quorum SHALL NOT reduce to one signature: a lone signer must be a
    # positively-confirmed QUORUM_MEMBER (a lone LEADER / None-role / role-conflicted identity is
    # rejected, order-independently — the fail-open carve-out is inverted to require positive proof).
    return not (count == 1 and not counted_confirmed_members[0])


def evidence_receipt_is_not_quorum_proof(candidate: object | None = None) -> bool:
    """Whether an evidence commit receipt (or leader receipt) can never substitute for a QCC (§5.4).

    **Unconditionally ``True``** — a rejection predicate. An evidence commit receipt, a single
    leader receipt, a local journal entry, a cache entry, a projection, or an audit record is
    structurally **not** a Quorum Commit Certificate and can never substitute for one at final
    egress. Structural grounds (§0.4d): the evidence ``EvidenceCommitReceipt`` carries a **single**
    ``receipt_signer_identity`` (≠ a quorum threshold, §5.3), a ``ReceiptVerificationStatus.
    UNVERIFIED`` (≠ durable quorum acceptance — ``evidence/receipt.py:11-12``), and an all-false
    authority (transmits nothing). ADR §21.4 line 560-562 "Leader Receipt as Commit Proof ...
    Rejected because leader belief, local persistence, or signature does not prove quorum
    commitment"; §2 line 49 "a durable local journal being treated as equivalent to ADR-002-012
    quorum commit" (UNSAFE). egress re-authors **no** evidence ``EvidenceCommitReceipt`` /
    ``SegmentCommitmentScheme`` (§3.5 — it only rejects the substitution attempt).

    Args:
        candidate: The receipt / journal / projection offered as a QCC substitute (ignored — the
            rejection is unconditional; accepted for call-site documentation).

    Returns:
        ``True`` — always; an evidence receipt is never a quorum proof.
    """
    del candidate  # the rejection is unconditional (§21.4) — no receipt is ever a quorum proof
    return True


# ===========================================================================
# core §5.5-§5.7 — replay / substitution, single-use, exact binding (EGRESS-EV-005)
# ===========================================================================


def replay_or_substitution_detected(
    a: ReplayObservation | None,
    b: ReplayObservation | None,
) -> RecordPairKind:
    """Classify two replay observations by shared subject vs bound request bytes (§5.5).

    REUSES ``classify_record_pair`` (canonical, §3.1) over the two observations' ``subject_identity``
    (the proof / capability / nonce) and ``canonical_digest`` (which covers the bound request bytes).
    A same subject-id / **different** bound bytes pair ⇒ ``CRITICAL_CONFLICT`` (substitution — §11.2
    step 18 / §20 line 532 "Proof valid but request bytes or endpoint differ ... reject; Critical
    integrity alert"); a same subject-id / same bytes pair ⇒ ``IDEMPOTENT_DUP`` (an already-consumed
    replay, no new send authority — the rcl ``claim_capability`` replay isomorph). A ``None``
    observation or a pre-issuance (null digest) record ⇒ ``NOT_COMPARABLE`` (never a false conflict).
    A transplant to a different principal / endpoint is caught by the exact-binding mismatch (§5.7);
    the ``id != f(digest)`` independence (§2.1) keeps the same-id / different-bytes case detectable.

    Args:
        a: The first replay observation (``None`` ⇒ ``NOT_COMPARABLE``).
        b: The second replay observation (``None`` ⇒ ``NOT_COMPARABLE``).

    Returns:
        The :class:`~tos.egress._base.RecordPairKind` (``CRITICAL_CONFLICT`` on substitution).
    """
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
    """Whether the capability + permit nonces are each claimed exactly once for this bind (§5.6).

    ``True`` **only** when (i) both nonces are concrete, (ii) the ``principal`` and
    ``request_digest`` this claim binds are concrete, and (iii) **no** prior claim already carries
    either nonce — whether an exact replay (same principal / request, already consumed) or a
    transplant (a different principal / request), so the nonce is provably claimed exactly once for
    THIS principal + request (§11.2 step 17 line 347 "verify the capability nonce and Action Flow
    Permit claim nonce are each bound and claimed exactly once for this principal and request").

    rcl ``claim_capability`` (``rcl/predicates.py:677``) already owns the nonce single-use + replay
    ledger (``rcl/predicates.py:698-703``); egress **consumes** the injected prior-claim
    observations and adds the principal / request binding — re-authoring **no** rcl claim ledger
    (§3.5). A ``None`` nonce / principal / request_digest ⇒ ``False`` (fail-closed; the rcl
    ``predicates.py:698`` None-nonce isomorph).

    Args:
        capability_nonce: The capability nonce being claimed (``None`` ⇒ ``False``).
        action_flow_permit_nonce: The Action Flow Permit nonce (``None`` ⇒ ``False``).
        prior_claims: The injected already-recorded claim observations (append-only).
        principal: The exact runtime principal this claim binds (``None`` ⇒ ``False``).
        request_digest: The exact request digest this claim binds (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff both nonces are unclaimed and the bind context is concrete.
    """
    if capability_nonce is None or action_flow_permit_nonce is None:
        return False
    if principal is None or request_digest is None:
        return False
    claimed_nonces = {capability_nonce, action_flow_permit_nonce}
    for claim in prior_claims:
        if claim.nonce is not None and claim.nonce in claimed_nonces:
            # already claimed (exact replay or transplant) ⇒ not single-use ⇒ fail-closed.
            return False
    return True


def exact_binding_holds(
    request: EgressRequestRecord | None,
    qcc: QuorumCommitCertificate | None,
    injected_authorized: EgressCoordinateSet | None,
    ioc_conformance_verdict: str | None,
    capsule_egress_request_digest: str | None,
) -> bool:
    """Whether every egress coordinate exactly binds with no substitution (§5.7).

    ``True`` **only** when (i) every request egress coordinate
    (:data:`~tos.egress.state.EgressCoordinateSet.COORDINATES`) is concrete and equals the injected
    authorized value (EGRESS-INV-004 line 155-157 "SHALL match. No field may be substituted after
    validation."), (ii) ``request.request_bytes_digest`` equals ``capsule_egress_request_digest``
    (the capsule ``Bindings`` chain terminus, §0.4e), (iii) ``qcc.canonical_command_digest`` equals
    ``request.canonical_command_digest``, and (iv) the injected ioc conformance verdict is
    ``CONFORMANT`` (command↔proof↔effect conformance is ioc-owned — injected enum-token, §0.4c).
    Any ``None`` / mismatch / non-``CONFORMANT`` ⇒ ``False`` (fail-closed).

    egress re-authors **no** ioc ``derived_command_conformance`` / ``mutation_fence_holds`` and no
    capsule ``Bindings`` (§3.5 — verdict / digest injected). **Over-realization boundary (§5.7):**
    the actual byte-level outbound reconstruction (§11.2 step 18), the §10 route confinement, and the
    §8 env non-interchangeability enforcement are **+Security** (EGRESS-EV-003 not-Phase-1) — L1 is
    injected coordinate equality + the ioc verdict only.

    Args:
        request: The exact outbound egress request (``None`` ⇒ ``False``).
        qcc: The Quorum Commit Certificate whose command digest the request must match (``None`` ⇒
            ``False``).
        injected_authorized: The authorized egress coordinate set (``None`` ⇒ ``False``).
        ioc_conformance_verdict: The injected ioc ``ConformanceResult`` verdict (enum-token;
            non-``CONFORMANT`` / ``None`` ⇒ ``False``).
        capsule_egress_request_digest: The capsule ``Bindings.egress_request_digest`` chain terminus
            (``None`` / mismatch ⇒ ``False``).

    Returns:
        ``True`` iff every coordinate binds exactly and the ioc verdict is ``CONFORMANT``.
    """
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


# ===========================================================================
# predicate-only §6.1 — credential-route authority disjointness (EGRESS-EV-001)
# ===========================================================================


def credential_route_authority_disjoint(
    inventory: Sequence[CredentialRouteInventoryEntry],
) -> bool:
    """Whether no outside-boundary principal holds both usable credential and route (§6.1).

    ``True`` **only** when **no** entry describes an outside-boundary (or unknown) principal that
    holds both a usable credential and a broker route (EGRESS-INV-002 line 147-149 "No identity
    outside the current boundary possesses both usable live-order authority and a broker-order
    route"). For each entry: an ``inside_boundary is not True`` (outside / unknown) principal with
    ``usable_credential is not False`` (``True`` / ``None`` = potentially-usable) **and**
    ``broker_route is not False`` is a bypass candidate ⇒ ``False``. A ``None`` flag is **UNKNOWN ⇒
    conservatively potentially-usable** (EGRESS-INV-011 / §4.6). An **empty** inventory ⇒ ``False``
    (disjointness unproven — inventory completeness is itself unproven, §4.7).

    **Over-realization boundary (§6.1):** the real inventory enumeration (hidden operational /
    recovery / portal / CI-CD / support / vendor credential, §9.1 line 251) is L2+ (register floor
    ``EV-L2/3+Security``) — this is the injected-inventory disjointness predicate only, a predicate,
    not a prevention (§14 EGRESS-INV-014 line 195).

    Args:
        inventory: The injected credential-route inventory (∅ ⇒ ``False``).

    Returns:
        ``True`` iff no outside / unknown principal is a credential-and-route bypass candidate.
    """
    if not inventory:
        return False
    for entry in inventory:
        outside_or_unknown = entry.inside_boundary is not True
        potentially_usable = entry.usable_credential is not False
        has_route = entry.broker_route is not False
        if outside_or_unknown and potentially_usable and has_route:
            return False
    return True


# ===========================================================================
# not-Phase-1 thin model §6b — egress generation / stale principal / monotonic denial
# ===========================================================================
# These are thin L1 model properties authored defence-in-depth; they close NO EGRESS-EV. The real
# bypass resistance / reconnect runtime / race timing is +Security (design #22 §6b).


def egress_generation_monotonic(prior: OrderingEvent, new: OrderingEvent) -> bool:
    """Whether the Egress Generation strictly increases in append-only order (§6b.1; thin model).

    REUSES ``tos.ordering`` (via :func:`~tos.egress.state.generation_monotone`): an Egress
    Generation is monotonic (§8), so ``True`` **only** when ``prior`` provably precedes ``new``
    (``BEFORE``); a decrease / ambiguous / equal pair ⇒ ``False``. A rollback is a **new** Egress
    Generation, never a revival (§15 line 437).

    **not-Phase-1 (§6b.1):** this is a model property feeding the §5.1/§5.2 QCC egress-generation
    claim; it does **not** close EGRESS-EV-002 — the actual direct / stale-principal bypass
    resistance (credential custody §9 + route confinement §10 + network enforcement) is +Security
    (csv:150 ``EV-L3+Security``).

    Args:
        prior: The prior generation ordering event.
        new: The new generation ordering event.

    Returns:
        ``True`` iff ``prior`` provably precedes ``new``.
    """
    return generation_monotone(prior, new)


def stale_principal_structurally_rejected(
    principal: str | None,
    active_set: ActiveEgressPrincipalSet | None,
    *,
    expected_generation: int | None,
) -> bool:
    """Whether a principal is represented, active, and current in the committed set (§6b.1; thin model).

    ``True`` **only** when ``principal`` is explicitly represented in ``active_set``, its committed
    ``active is True`` and ``expired is False`` (positive proof of non-expiry — a ``None`` unknown
    old-principal state is denial, EGRESS-INV-011 line 183), and the set's ``egress_generation``
    equals the ``expected_generation``. An unrepresented / wrong-generation / inactive / expired /
    unknown-expiry principal ⇒ ``False`` (§8 line 233 "SHALL NOT infer membership from a service
    account name, namespace, host role, load-balancer target, possession of an old secret, or
    successful broker authentication"). A ``None`` principal / set / generation ⇒ ``False``
    (fail-closed).

    **not-Phase-1 (§6b.1):** this model property feeds the §5.1/§5.2 QCC active-principal claim; it
    does **not** close EGRESS-EV-002 — the real bypass resistance is +Security (csv:150).

    Args:
        principal: The runtime principal to check (``None`` ⇒ ``False``).
        active_set: The committed active egress principal set (``None`` ⇒ ``False``).
        expected_generation: The injected current Egress Generation (``None`` / mismatch ⇒
            ``False``).

    Returns:
        ``True`` iff the principal is represented, active, current, and unexpired.
    """
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
            # ``expired`` is negative-polarity (True = expired = risk): require positive proof of
            # non-expiry ``is False`` — a ``None`` (unknown old-principal state) is denial
            # (EGRESS-INV-011 line 183; #18 polarity discipline; matches the conservative
            # credential_route_authority_disjoint treatment — asymmetry resolved, MAJOR-2).
            return member.active is True and member.expired is False
    return False


def monotonic_denial_no_revival(
    latch_state: RestrictiveLatchState | None,
    injected_events: Iterable[EgressEvent],
) -> RestrictiveLatchState:
    """Resolve the restrictive latch under injected events — deny is monotonic (§6b.3; thin model).

    The deny state is **monotonic** (§13 line 393): once ``DENY_LATCHED``, **no** injected event
    (cache recovery / reconnect / secret refresh / route restoration / deployment success / alert
    deletion) can return it to ``CLEAR`` — it stays ``DENY_LATCHED``. From ``CLEAR``, any restrictive
    event (``restrictive is True``) latches deny; an **empty** event stream (or only revival /
    unknown events) leaves it ``CLEAR`` (§4.7 both-ways — a valid QCC within currency is not
    spuriously denied). A ``None`` latch state is UNKNOWN ⇒ ``DENY_LATCHED`` (fail-closed).

    Isomorphic to authority ``recovery_generation_revives_nothing`` (``authority/predicates.py:787``)
    / rcl ``partition_verdict`` ``automatic_rearm_denied=True`` / liveauth ``no_automatic_rearm``
    (``liveauth/predicates.py:606``) — authored locally (§3.5, no import). **not-Phase-1 (§6b.3):**
    the real race timing and the ``B_revocation_to_egress`` / ``B_halt_to_egress`` /
    ``B_egress_hard_fence`` bound propagation are +Security (EGRESS-EV-006/007 not-Phase-1).

    Args:
        latch_state: The current restrictive latch state (``None`` ⇒ ``DENY_LATCHED``).
        injected_events: The injected egress events (∅ ⇒ no new invalidation).

    Returns:
        ``RestrictiveLatchState.DENY_LATCHED`` if latched / a restrictive event fired / unknown,
        else ``RestrictiveLatchState.CLEAR``.
    """
    if latch_state is RestrictiveLatchState.DENY_LATCHED:
        return RestrictiveLatchState.DENY_LATCHED
    if latch_state is not RestrictiveLatchState.CLEAR:
        # None / unknown ⇒ fail-closed.
        return RestrictiveLatchState.DENY_LATCHED
    for event in injected_events:
        if event.restrictive is True:
            return RestrictiveLatchState.DENY_LATCHED
    return RestrictiveLatchState.CLEAR
