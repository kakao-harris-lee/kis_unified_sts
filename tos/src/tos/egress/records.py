"""egress digest-bound artifacts — the five egress-boundary ledger citizens (design #22 §2).

Every artifact is a **pydantic v2 frozen model** (``frozen=True, extra="forbid"`` via
:class:`~tos.egress._base.FrozenModel`): ``extra="forbid"`` is the schema-level "omission is
restrictive" and frozen is the append-only, current-generation-bound realization; there is **no**
update / delete / mutate / transmit / sign / re-arm / clear-latch method on any model (design #22
§2.0/§4.6/§4.7 — the constructive-absence canary). Field names use the ADR §8-§12 terms
**verbatim** (spec terms = code terms, boundary design #1 §2.4).

**Five id-independent artifacts (design #22 §2.1/§3.1).** ``QuorumCommitCertificate`` /
``EgressRequestRecord`` / ``EgressGeneration`` / ``ActiveEgressPrincipalSet`` / ``ReplayObservation``
are **issued-identity** records (:class:`~tos.egress._base.IndependentIdArtifact`, ``id != f(digest)``):
the id is separately issued, so a same-id / different-bytes forged, re-issued, or replayed record is
a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` (EGRESS-EV-004/005). The
``ReplayObservation`` carries a ``subject_identity`` (the proof / capability / nonce being observed)
so :func:`~tos.egress.predicates.replay_or_substitution_detected` can classify a same-subject /
different-request-bytes pair as ``CRITICAL_CONFLICT`` (substitution, §5.5).

**QCC != commit proof, QCC != evidence receipt (design #22 §0.4b/§0.4d/§3.5 — the two-layer
boundary).** The ``QuorumCommitCertificate`` is the **egress-boundary aggregating** artifact: it
**carries** the rcl ADR-002-012 Commit Proof coordinates as bound claims and adds the egress
generation, active principal, sibling generation / digest bindings, and quorum signer coordinates —
it does **not** re-author the rcl commit proof, and it is structurally **not** an evidence commit
receipt (single-signer / UNVERIFIED / all-false — ``evidence/receipt.py:11-12``, §5.4). ADR §5.7
line 129 verbatim: "The bare ADR-002-012 Commit Proof is necessary but not sufficient at final
egress; the full Quorum Commit Certificate claim set in §11.1 SHALL be satisfied."

**Malformed-model self-defence (design #22 §2.3 / #20 lesson).** The ``QuorumCommitCertificate``
validator forbids an **incomplete** trial claim group coexisting with the **positive** completeness
claim ``is_restricted_live_trial=True`` (a positively-claimed restricted-live trial with a ``None``
trial scalar is unconstructable); the base already rejects an ISSUED QCC with a ``None``
``_REQUIRED_COVERED`` field. The ``model_construct`` escape hatch that skips validators is re-caught
in the §5.1 predicate layer (defence in depth).

**Coordinate non-collapse (design #22 §2.3).** No mutable lifecycle coordinate (the injected
``RestrictiveLatchState``, the current-generation verdicts) is a covered digest field — a lawful
transition must not change a QCC's digest and be mis-flagged as a same-id / different-bytes
``CRITICAL_CONFLICT`` (the rcl coordinate-non-collapse precedent). Every covered field is an
immutable claim; the current state is injected into the predicate.

**All-false authority (design #22 §2.4/§4.3; EGRESS-INV-005/010).** Every authority-bearing
artifact carries an :class:`~tos.egress._base.AllFalseEgressAuthority` with all five flags ``False``
— a QCC / request / generation is verified data, not permission.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.egress._base``) + ``tos.egress.*``
only; no ``shared.*``, no sibling ``tos.*`` (design #22 §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import model_validator

from tos.egress._base import (
    AllFalseEgressAuthority,
    ArtifactIntegrityError,
    IndependentIdArtifact,
)
from tos.egress.state import EgressPrincipal, SignerCoordinate, TrialClaims

__all__ = [
    "QuorumCommitCertificate",
    "EgressRequestRecord",
    "EgressGeneration",
    "ActiveEgressPrincipalSet",
    "ReplayObservation",
    "AllFalseEgressAuthority",
]


class QuorumCommitCertificate(IndependentIdArtifact):
    """The egress-boundary Quorum Commit Certificate (ADR-002-013 §11.1; design #22 §2.4).

    §11.1: the aggregating artifact satisfied at final egress. It **carries** (as bound claims) the
    rcl ADR-002-012 Commit Proof coordinates (cluster / capacity domain / safety cell / membership /
    restore / writer epoch / committed + parent revision / command identity / canonical command +
    resulting state digest, §11.1 line 300-306 — rcl-owned, injected, **not** re-authored), the
    EGRESS-owned egress coordinates (egress generation / active principal / credential / session /
    route / endpoint / trust-bundle generation, §11.1 line 323-324), the sibling generation / digest
    bindings (sbr / capsule / venue / ioc / are / afg / iap and the 024/029/030 upstream that landed later,
    §11.1 line 313-322 — injected, **not** re-authored), the quorum signer coordinates (§11.1 line
    325), the capability / permit nonces (§11.2 step 17), and the conditional restricted-live trial
    claim group (§11.1 line 308).

    An :class:`~tos.egress._base.IndependentIdArtifact` (``id != f(digest)``): a same-id /
    different-bytes QCC forgery / rollback is a detectable ``CRITICAL_CONFLICT``. Its
    :class:`~tos.egress._base.AllFalseEgressAuthority` is all-false — **holding a QCC is not
    transmission authority** (§4.3; the §5 structural / coordinate / threshold predicates plus
    +Security decide, never the mere possession of the artifact). The actual quorum consensus /
    durability / cryptographic-signature validity is **+Security** (design #22 §1/§5.3
    over-realization boundary); this artifact + the §5.1-5.3 predicates own only the aggregation
    completeness, coordinate currency, and threshold shape.
    """

    _ID_FIELD: ClassVar[str] = "qcc_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "cluster_identity",
        "capacity_domain",
        "membership_generation",
        "restore_generation",
        "writer_epoch",
        "committed_revision",
        "canonical_command_digest",
        "resulting_state_digest",
        "egress_generation",
        "active_egress_principal",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            # commit-proof coordinates (rcl-owned; injected, not re-authored — §11.1 line 300-306)
            "cluster_identity",
            "capacity_domain",
            "safety_cell",
            "membership_generation",
            "restore_generation",
            "writer_epoch",
            "committed_revision",
            "parent_revision",
            "command_identity",
            "canonical_command_digest",
            "resulting_state_digest",
            # egress coordinates (EGRESS-owned axis — §11.1 line 323-324)
            "egress_generation",
            "active_egress_principal",
            "credential_generation",
            "broker_session_generation",
            "route_policy_generation",
            "endpoint_policy_generation",
            "trust_bundle_generation",
            # sibling generation / digest bindings (injected, not re-authored — §11.1 line 313-322)
            "recovery_evidence_package_digest",
            "decision_context_capsule_digest",
            "venue_admissibility_decision_digest",
            "canonical_broker_command_digest",
            "order_conformance_proof_digest",
            "aggregate_risk_decision_digest",
            "action_flow_decision_digest",
            "action_flow_permit_id",
            "approval_consumption_record_digest",
            "egress_currentness_proof_id",
            "release_artifact_attestation_digest",
            "post_trade_obligation_generation",
            # signer coordinates + nonces + trial claim group + authority (§11.1 line 325 / §11.2:17)
            "signer_coordinates",
            "capability_nonce",
            "action_flow_permit_nonce",
            "is_restricted_live_trial",
            "trial_claims",
            "authority_effect",
        }
    )

    qcc_id: str | None = None

    # commit-proof coordinates (rcl-owned; injected verification target, §0.4b/§3.5)
    cluster_identity: str | None = None
    capacity_domain: str | None = None
    safety_cell: str | None = None
    membership_generation: int | None = None
    restore_generation: int | None = None
    writer_epoch: int | None = None
    committed_revision: int | None = None
    parent_revision: int | None = None
    command_identity: str | None = None
    canonical_command_digest: str | None = None
    resulting_state_digest: str | None = None

    # egress coordinates (EGRESS-owned axis)
    egress_generation: int | None = None
    active_egress_principal: str | None = None
    credential_generation: int | None = None
    broker_session_generation: int | None = None
    route_policy_generation: int | None = None
    endpoint_policy_generation: int | None = None
    trust_bundle_generation: int | None = None

    # sibling generation / digest bindings (injected scalars/digests; sibling edge 0)
    recovery_evidence_package_digest: str | None = None
    decision_context_capsule_digest: str | None = None
    venue_admissibility_decision_digest: str | None = None
    canonical_broker_command_digest: str | None = None
    order_conformance_proof_digest: str | None = None
    aggregate_risk_decision_digest: str | None = None
    action_flow_decision_digest: str | None = None
    action_flow_permit_id: str | None = None
    approval_consumption_record_digest: str | None = None
    #: 024/CUR (egress currentness proof) — upstream landed later; injected id, ADR text only (§0.4f).
    egress_currentness_proof_id: str | None = None
    #: 029/SCI release attestation — upstream landed later; injected digest, ADR text only (§0.4f).
    release_artifact_attestation_digest: str | None = None
    #: 030/PTF post-trade obligation — upstream landed later (as posttrade); injected generation, ADR text only.
    post_trade_obligation_generation: int | None = None

    # quorum signer coordinates + single-use nonces (§11.1 line 325 / §11.2 step 17)
    signer_coordinates: tuple[SignerCoordinate, ...] = ()
    capability_nonce: str | None = None
    action_flow_permit_nonce: str | None = None

    #: Positive restricted-live-trial completeness claim (§11.1 line 308). ``True`` requires a fully
    #: concrete ``trial_claims`` group — the malformed-model coexistence seal (§2.3).
    is_restricted_live_trial: bool = False
    #: The conditional restricted-live trial claim group (opaque scalars; RLP-deferred, §2.4).
    trial_claims: TrialClaims | None = None

    #: §4.3 — a QCC is verified data, not permission (all-false, EGRESS-INV-005/010).
    authority_effect: AllFalseEgressAuthority = AllFalseEgressAuthority()

    @model_validator(mode="after")
    def _trial_claim_completeness(self) -> QuorumCommitCertificate:
        """A positively-claimed restricted-live trial cannot carry an incomplete trial group (§2.3).

        Malformed-model self-defence (design #22 §2.3 / #20 lesson): a QCC that positively claims to
        be a restricted-live trial (``is_restricted_live_trial is True``) requires the full §11.1
        line 308 trial claim group (Trial Policy / Plan / Run / Promotion Generation, remaining
        envelope, abort generation) to be concrete. A positive completeness claim coexisting with a
        ``None`` trial scalar — or with no ``trial_claims`` at all — is a malformed model and is
        **unconstructable** on the normal validation path; the ``model_construct`` escape hatch is
        re-caught by :func:`~tos.egress.predicates.quorum_commit_certificate_structurally_complete`
        (defence in depth, §5.1).
        """
        if self.is_restricted_live_trial is True:
            if self.trial_claims is None or not self.trial_claims.is_complete():
                raise ArtifactIntegrityError(
                    "QuorumCommitCertificate declares is_restricted_live_trial=True but carries an "
                    "incomplete trial claim group — a positively-claimed restricted-live trial "
                    "requires the full §11.1 line 308 Trial Policy / Plan / Run / Promotion "
                    "Generation, remaining envelope, and abort generation to be concrete "
                    "(malformed-model self-defence, design #22 §2.3 / ADR-002-013 §11.1)."
                )
        return self


class EgressRequestRecord(IndependentIdArtifact):
    """The exact outbound egress request (ADR-002-013 §12 line 365-367; design #22 §2.4).

    §12: the exact final outbound broker-order request. Binds the request-bytes digest and the exact
    egress coordinates — account, instrument (via the quantity digest), side, endpoint, action,
    method, route, credential generation, broker session generation, Egress Generation, and the
    active egress principal (§12 line 367). An :class:`~tos.egress._base.IndependentIdArtifact`
    (``id != f(digest)``): a same-id / different-bytes request substitution is a detectable
    ``CRITICAL_CONFLICT`` (§5.5). Consumed by :func:`~tos.egress.predicates.exact_binding_holds`,
    which asserts every egress coordinate equals the injected authorized value and the request-bytes
    digest equals the capsule ``egress_request_digest`` chain terminus (§5.7). Carries an all-false
    :class:`~tos.egress._base.AllFalseEgressAuthority` (a request is data, not permission).
    """

    _ID_FIELD: ClassVar[str] = "request_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "request_bytes_digest",
        "endpoint",
        "account",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "request_bytes_digest",
            "canonical_command_digest",
            "endpoint",
            "account",
            "environment",
            "action",
            "method",
            "side",
            "quantity_digest",
            "route_identity",
            "credential_generation",
            "broker_session_generation",
            "egress_generation",
            "active_principal",
            "authority_effect",
        }
    )

    request_id: str | None = None
    request_bytes_digest: str | None = None
    #: The command digest this request transmits (matched to the QCC command digest, §5.7 (iii)).
    canonical_command_digest: str | None = None
    endpoint: str | None = None
    account: str | None = None
    environment: str | None = None
    action: str | None = None
    method: str | None = None
    side: str | None = None
    quantity_digest: str | None = None
    route_identity: str | None = None
    credential_generation: int | None = None
    broker_session_generation: int | None = None
    egress_generation: int | None = None
    active_principal: str | None = None
    #: §4.3 — an egress request is data, not permission (all-false, EGRESS-INV-005/010).
    authority_effect: AllFalseEgressAuthority = AllFalseEgressAuthority()


class EgressGeneration(IndependentIdArtifact):
    """One monotonic Egress Generation (ADR-002-013 §8; design #22 §2.4).

    §8: the monotonic generation coordinate that fences the active egress principal set. Order is
    carried by ``tos.ordering`` (§3.2); a rollback is a **new** Egress Generation, never a revival
    (§15 line 437, §6b). An :class:`~tos.egress._base.IndependentIdArtifact`. Its
    :class:`~tos.egress._base.AllFalseEgressAuthority` is all-false — §8 line 231 "no authority
    outside the committed set": arming a generation is a defined coordinate, not a permissive
    authority.
    """

    _ID_FIELD: ClassVar[str] = "generation_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("egress_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "egress_generation",
            "authority_effect",
        }
    )

    generation_id: str | None = None
    #: The monotonic Egress Generation coordinate (``tos.ordering`` carries the order, §3.2).
    egress_generation: int | None = None
    #: §8 line 231 — no authority outside the committed set (all-false, EGRESS-INV-005/010).
    authority_effect: AllFalseEgressAuthority = AllFalseEgressAuthority()


class ActiveEgressPrincipalSet(IndependentIdArtifact):
    """The committed active egress principal set (ADR-002-013 §8 line 223-231; design #22 §2.4).

    §8: the explicitly committed set of active egress principals bound to one Egress Generation.
    Membership is **positive and explicit** — §8 line 233 "SHALL NOT infer membership from a service
    account name, namespace, host role, load-balancer target, possession of an old secret, or
    successful broker authentication". An :class:`~tos.egress._base.IndependentIdArtifact`. Consumed
    by :func:`~tos.egress.predicates.stale_principal_structurally_rejected` (§8/§6b.1). Its
    :class:`~tos.egress._base.AllFalseEgressAuthority` is all-false (§8 line 231 "no authority
    outside the committed set"). An **empty** ``active_principals`` is a legitimate fully-fenced
    deny-all safety state (§14 hard-fence complete, §4.7 both-ways) — never a defect.
    """

    _ID_FIELD: ClassVar[str] = "set_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("egress_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "egress_generation",
            "active_principals",
            "authority_effect",
        }
    )

    set_id: str | None = None
    #: The Egress Generation this committed set is bound to (§8 fencing).
    egress_generation: int | None = None
    #: The explicitly committed active egress principals (∅ = fully-fenced deny-all safety, §4.7).
    active_principals: tuple[EgressPrincipal, ...] = ()
    #: §8 line 231 — no authority outside the committed set (all-false, EGRESS-INV-005/010).
    authority_effect: AllFalseEgressAuthority = AllFalseEgressAuthority()


class ReplayObservation(IndependentIdArtifact):
    """One replay / substitution observation (ADR-002-013 §11/§12; design #22 §2.4/§5.5).

    A digest-bound observation of a proof / capability / nonce (the ``subject_identity``) bound to a
    specific outbound request. An :class:`~tos.egress._base.IndependentIdArtifact`: because the
    ``subject_identity`` is INDEPENDENT of the ``canonical_digest`` (``id != f(digest)``), a
    same-subject / different-request-bytes pair is a detectable
    :func:`~tos.egress.predicates.replay_or_substitution_detected` ``CRITICAL_CONFLICT``
    (substitution — §11.2 step 18 / §20 line 532 "Proof valid but request bytes or endpoint differ
    ... reject; Critical integrity alert"), and a same-subject / same-bytes pair is an
    ``IDEMPOTENT_DUP`` (an already-consumed replay, no new send authority — the rcl
    ``claim_capability`` replay isomorph). Carries an all-false
    :class:`~tos.egress._base.AllFalseEgressAuthority` (observing a replay records a fact, it grants
    nothing).
    """

    _ID_FIELD: ClassVar[str] = "observation_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("subject_identity",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "subject_identity",
            "bound_request_digest",
            "principal",
            "endpoint",
            "egress_generation",
            "authority_effect",
        }
    )

    observation_id: str | None = None
    #: The proof / capability / nonce identity observed (the same-identity axis for §5.5 classify).
    subject_identity: str | None = None
    #: The request bytes the subject was bound to (the different-bytes substitution axis, §5.5).
    bound_request_digest: str | None = None
    principal: str | None = None
    endpoint: str | None = None
    egress_generation: int | None = None
    #: §4.3 — a replay observation records a fact, it grants nothing (all-false).
    authority_effect: AllFalseEgressAuthority = AllFalseEgressAuthority()
