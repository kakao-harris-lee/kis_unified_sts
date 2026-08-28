"""egress injected inputs + value models + monotonic-generation ordering REUSE (design #22 §2.4/§3.2).

Two roles:

* **injected value / input models (design #22 §2.4)** — the quorum signer coordinate
  (:class:`SignerCoordinate`, carrying the injected ``eligible_verified`` / ``signature_verified``
  bool flags — actual cryptographic verification is +Security), the exact-binding egress coordinate
  set (:class:`EgressCoordinateSet`), the credential-route inventory entry
  (:class:`CredentialRouteInventoryEntry`), the injected rcl commit-proof coordinate mirror
  (:class:`CommitProofCoordinates` — the *verification target*, **not** an rcl re-authoring), the
  restricted-live trial claim group (:class:`TrialClaims` — opaque optional scalars deferred to RLP,
  §2.4), one active egress principal (:class:`EgressPrincipal`, §8), one prior capability claim
  observation (:class:`ClaimObservation`, §5.6), and one restrictive event (:class:`EgressEvent`,
  §13). Every one is a **pydantic v2 frozen model** (``frozen=True, extra="forbid"`` via
  :class:`~tos.egress._base.FrozenModel`): ``extra="forbid"`` is the schema-level "omission is
  restrictive", and frozen is the append-only realization — there is **no** update / delete /
  mutate method on any model (design #22 §2.0/§4.6).

* **monotonic-generation order (design #22 §3.2 ordering REUSE)** — :func:`generation_monotone`
  REUSES ``tos.ordering.compare_order`` (no re-authored order) for egress / credential / session /
  route / trust-bundle / restrictive generation order (§8/§13/§14). egress owns the fence *meaning*
  (invalidation / non-revival, §4.5); ordering only carries the monotonic order. A wall clock never
  orders — egress reads **no** clock (§8).

**Numeric-bound freedom (design #22 §8; ADR §4 non-scope).** egress carries no numeric quorum /
age / latency / propagation constant: every such value is an **injected** opaque scalar (null in
Phase 1, fail-closed at the consuming predicate). Nothing numeric is hardcoded — the egress logic
is over StrEnums, booleans, set / coordinate equality, and injected values only.

**Injected verified-flag discipline (design #22 §1/§5.3 over-realization boundary).**
``SignerCoordinate.eligible_verified`` / ``signature_verified`` are **injected** ``bool | None``
flags: egress does **not** verify a signature or an eligibility — the actual cryptographic /
membership-generation verification is +Security. The count predicate consumes only the injected
flags (``is True``); a ``None`` is UNKNOWN and excluded (fail-closed).

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.egress.*`` only; no ``shared.*``, no
other sibling ``tos.*`` (design #22 §0.3). Clock-free.
"""

from __future__ import annotations

from typing import ClassVar

from tos.egress._base import FrozenModel
from tos.egress.vocabulary import SignerRole
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "SignerCoordinate",
    "EgressCoordinateSet",
    "CredentialRouteInventoryEntry",
    "CommitProofCoordinates",
    "TrialClaims",
    "EgressPrincipal",
    "ClaimObservation",
    "EgressEvent",
    "generation_monotone",
]


class SignerCoordinate(FrozenModel):
    """One quorum signer coordinate (ADR-002-013 §11.1 line 325; design #22 §2.4).

    A signer identity plus its **injected** verification flags (§11.1 "quorum signer identities or
    equivalent threshold-verification material"). ``eligible_verified`` (the signer was eligible in
    the claimed membership generation, §11.2 step 4) and ``signature_verified`` (the signature
    verified, §11.2 step 4) are **injected** ``bool | None`` — egress does **not** verify a
    signature or an eligibility; the actual cryptographic / membership verification is +Security
    (design #22 §5.3 over-realization boundary). The count predicate consumes only the injected
    flags (``is True``): a ``None`` is UNKNOWN and **excluded** from the distinct count
    (fail-closed, §5.3). ``signer_role`` is the closed leader-vs-quorum taxonomy token (§11.2 line
    351 — a lone ``LEADER`` is insufficient).
    """

    signer_identity: str | None = None
    signer_role: SignerRole | None = None
    #: Injected — the signer was eligible in the claimed membership generation (+Security, §11.2:4).
    eligible_verified: bool | None = None
    #: Injected — the signature verified (+Security, §11.2 step 4); egress does not verify it.
    signature_verified: bool | None = None


class EgressCoordinateSet(FrozenModel):
    """The exact-binding egress coordinate set (ADR-002-013 §11.2 step 18 / §12; design #22 §2.4).

    The authorized egress coordinates an :class:`~tos.egress.records.EgressRequestRecord` must match
    field-for-field (EGRESS-INV-004 line 155-157 "endpoint, account, credential generation, broker
    session, Egress Generation, and exact runtime principal SHALL match. No field may be substituted
    after validation."). Consumed by :func:`~tos.egress.predicates.exact_binding_holds` as the
    injected authorized value; a ``None`` coordinate on either side fails closed (§5.7). The actual
    route / env confinement + network enforcement is +Security (EGRESS-EV-003 not-Phase-1) — this is
    the injected coordinate-equality substrate only.
    """

    endpoint: str | None = None
    account: str | None = None
    environment: str | None = None
    action: str | None = None
    method: str | None = None
    route_identity: str | None = None
    credential_generation: int | None = None
    broker_session_generation: int | None = None
    egress_generation: int | None = None
    active_principal: str | None = None

    #: The exact-binding coordinate field names iterated by :func:`exact_binding_holds` (§5.7).
    COORDINATES: ClassVar[tuple[str, ...]] = (
        "endpoint",
        "account",
        "environment",
        "action",
        "method",
        "route_identity",
        "credential_generation",
        "broker_session_generation",
        "egress_generation",
        "active_principal",
    )


class CredentialRouteInventoryEntry(FrozenModel):
    """One credential-route inventory entry (ADR-002-013 §6/§9/§10; design #22 §2.4/§6.1).

    A principal cross-referenced with its **injected** ``usable_credential`` (holds usable
    live-order authority), ``broker_route`` (has a broker-order route), and ``inside_boundary``
    (is inside the current egress boundary) flags — all ``bool | None``. Consumed by
    :func:`~tos.egress.predicates.credential_route_authority_disjoint` (EGRESS-INV-002 line 147-149
    "No identity outside the current boundary possesses both usable live-order authority and a
    broker-order route"). A ``None`` flag is **UNKNOWN ⇒ conservatively potentially-usable**
    (EGRESS-INV-011 / §4.6). The real inventory enumeration (hidden / recovery / portal / CI
    credential, §9.1 line 251) is L2+ (register floor ``EV-L2/3+Security``) — this is the injected
    per-entry substrate only, a predicate, not a prevention (§14 EGRESS-INV-014 line 195).
    """

    principal: str | None = None
    #: Injected — the principal holds usable live-order authority (``None`` = UNKNOWN ⇒ potentially).
    usable_credential: bool | None = None
    #: Injected — the principal has a broker-order route (``None`` = UNKNOWN ⇒ potentially).
    broker_route: bool | None = None
    #: Injected — the principal is inside the current egress boundary (``None`` = UNKNOWN ⇒ outside).
    inside_boundary: bool | None = None


class CommitProofCoordinates(FrozenModel):
    """The injected current committed commit-proof coordinates (design #22 §2.4/§5.2).

    A **mirror** of the rcl ``AuthoritativeSnapshot`` (``rcl/records.py:428``) / ``RclTransition
    Record`` (``rcl/records.py:191``) / ``LedgerCommandRecord`` (``rcl/records.py:119``) commit-proof
    coordinates, carried as an **injected verification target** — **not** an rcl re-authoring (design
    #22 §0.4b/§3.5; egress imports no rcl). Consumed by
    :func:`~tos.egress.predicates.quorum_coordinates_current`, which asserts a
    :class:`~tos.egress.records.QuorumCommitCertificate`'s carried coordinates equal these injected
    current committed values (stale / mismatch ⇒ deny, §5.2). rcl produces the commit-proof
    coordinates first (``writer_fenced`` / CAS ownership, §3.5); egress verifies the QCC carries the
    exact current values — it re-authors **no** rcl fencing. A ``None`` on either side fails closed.
    """

    cluster_identity: str | None = None
    capacity_domain: str | None = None
    membership_generation: int | None = None
    restore_generation: int | None = None
    writer_epoch: int | None = None
    committed_revision: int | None = None
    canonical_command_digest: str | None = None
    resulting_state_digest: str | None = None
    egress_generation: int | None = None
    credential_generation: int | None = None
    broker_session_generation: int | None = None
    route_policy_generation: int | None = None
    trust_bundle_generation: int | None = None

    #: The coordinate field names iterated by :func:`quorum_coordinates_current` (§5.2).
    COORDINATES: ClassVar[tuple[str, ...]] = (
        "cluster_identity",
        "capacity_domain",
        "membership_generation",
        "restore_generation",
        "writer_epoch",
        "committed_revision",
        "canonical_command_digest",
        "resulting_state_digest",
        "egress_generation",
        "credential_generation",
        "broker_session_generation",
        "route_policy_generation",
        "trust_bundle_generation",
    )


class TrialClaims(FrozenModel):
    """The conditional restricted-live trial claim group (ADR-002-013 §11.1 line 308; design #22 §2.4).

    §11.1 line 308: a restricted-live trial (ADR-002-025 RLP) request requires the Trial Policy /
    Plan / Run / Promotion Generation, the remaining envelope, and the abort generation as
    **conditional** required claims. Phase 1 carries these as an **opaque optional scalar group**;
    the actual trial-content validation is deferred to RLP (``tos.rlp``, not landed — design #22 §9.2
    item 17), so egress cites no RLP code. When a :class:`~tos.egress.records.QuorumCommitCertificate`
    positively claims to be a restricted-live trial (``is_restricted_live_trial=True``), every scalar
    here must be concrete — the QCC validator forbids an incomplete trial group coexisting with the
    positive completeness claim (malformed-model self-defence, design #22 §2.3).
    """

    trial_policy_generation: int | None = None
    trial_plan_generation: int | None = None
    trial_run_generation: int | None = None
    promotion_generation: int | None = None
    remaining_envelope: str | None = None
    abort_generation: int | None = None

    #: The trial-claim scalar names checked for completeness when a QCC claims to be a trial (§2.3).
    REQUIRED_SCALARS: ClassVar[tuple[str, ...]] = (
        "trial_policy_generation",
        "trial_plan_generation",
        "trial_run_generation",
        "promotion_generation",
        "remaining_envelope",
        "abort_generation",
    )

    def is_complete(self) -> bool:
        """Whether every conditional trial scalar is concrete (design #22 §2.3).

        Returns:
            ``True`` iff no :data:`REQUIRED_SCALARS` value is ``None`` — the positive completeness a
            ``is_restricted_live_trial`` QCC must carry (fail-closed on any ``None``).
        """
        return all(getattr(self, name) is not None for name in self.REQUIRED_SCALARS)


class EgressPrincipal(FrozenModel):
    """One active egress principal (ADR-002-013 §8 line 223-231; design #22 §2.4).

    A workload identity plus its deployment / artifact / config / env digests, its credential /
    session / route / trust-bundle generation coordinates, and its activation / expiration state
    (§8 line 223-231). Membership is **positive and explicit**: §8 line 233 "SHALL NOT infer
    membership from a service account name, namespace, host role, load-balancer target, possession
    of an old secret, or successful broker authentication". Consumed by
    :func:`~tos.egress.predicates.stale_principal_structurally_rejected`, which admits a principal
    only when it is represented, ``active is True``, ``expired is not True``, and its generation
    matches (fail-closed otherwise). Both ``active`` and ``expired`` are injected ``bool | None`` (a
    ``None`` activation is UNKNOWN ⇒ not live).
    """

    workload_identity: str | None = None
    deployment_digest: str | None = None
    artifact_digest: str | None = None
    config_digest: str | None = None
    env_digest: str | None = None
    credential_generation: int | None = None
    broker_session_generation: int | None = None
    route_policy_generation: int | None = None
    trust_bundle_generation: int | None = None
    #: Injected activation state — must be positively ``True`` to be live (``None`` = UNKNOWN, §8).
    active: bool | None = None
    #: Injected expiration state — ``True`` = expired (not live); ``not True`` required for live.
    expired: bool | None = None


class ClaimObservation(FrozenModel):
    """One prior capability / permit nonce claim (ADR-002-013 §11.2 step 17; design #22 §2.4/§5.6).

    An **injected** record of a nonce already claimed — carrying the nonce, the principal, and the
    request digest it was bound to. Consumed by
    :func:`~tos.egress.predicates.capability_and_permit_single_use`: rcl ``claim_capability``
    (``rcl/predicates.py:677``) already owns the nonce single-use + replay ledger (``rcl/predicates.py:
    698-703``); egress **consumes** the injected prior-claim observations to verify a nonce is
    claimed exactly once for THIS principal + request, re-authoring **no** rcl claim ledger (design
    #22 §3.5). A prior claim of the same nonce (whether an exact replay or a transplant to another
    principal / request) makes the new claim not single-use (§5.6).
    """

    nonce: str | None = None
    principal: str | None = None
    request_digest: str | None = None


class EgressEvent(FrozenModel):
    """One injected egress state-machine event (ADR-002-013 §13; design #22 §2.4/§6b.3).

    An event fed to :func:`~tos.egress.predicates.monotonic_denial_no_revival`. ``restrictive`` is
    the injected classification: a restrictive event (HALT / revocation / generation change /
    credential compromise / proof failure / route contradiction, §13) latches deny; a **revival**
    event (cache recovery / reconnect / secret refresh / route restoration / deployment success /
    alert deletion, §13 line 393) carries ``restrictive=False`` and **cannot** clear a latched deny.
    ``None`` is UNKNOWN and treated as non-latching on the CLEAR path (only a positive ``True``
    latches); a latched state never revives regardless of the event (§13 monotonic).
    """

    event_kind: str | None = None
    #: Injected classification — ``True`` = restrictive (latches deny); ``False`` = revival (cannot
    #: clear); ``None`` = UNKNOWN (non-latching on the CLEAR path — a latch never revives anyway).
    restrictive: bool | None = None


def generation_monotone(earlier: OrderingEvent, later: OrderingEvent) -> bool:
    """Whether ``earlier`` strictly precedes ``later`` in append-only order (§3.2 / §4.5).

    REUSES ``tos.ordering.compare_order`` (no re-authored order) to check the monotonic order of
    egress / credential / session / route / trust-bundle / restrictive generations (§8/§13/§14).
    ``True`` **only** when the order is unambiguously ``BEFORE``; an ``AMBIGUOUS`` / ``AFTER`` pair
    fails closed. egress owns the fence *meaning* (invalidation / non-revival, §4.5); ordering only
    carries the order. A wall clock never orders — egress reads no clock (§8).

    Args:
        earlier: The earlier ordering event.
        later: The later ordering event.

    Returns:
        ``True`` iff ``earlier`` provably precedes ``later``.
    """
    return compare_order(earlier, later) is Ordering.BEFORE
