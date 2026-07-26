"""cur digest-bound artifacts — the four currentness ledger citizens (design #23 §2).

Every artifact is a **pydantic v2 frozen model** (``frozen=True, extra="forbid"`` via
:class:`~tos.cur._base.FrozenModel`): ``extra="forbid"`` is the schema-level "omission is
restrictive" and frozen is the append-only, revision-bound realization; there is **no** update /
delete / mutate / transmit / sign / re-arm / clear-latch method on any model (design #23 §2.3/§4.1
— the constructive-absence canary). Field names use the ADR §5-§12 terms **verbatim** (spec terms =
code terms, boundary design #1 §2.4).

**Four id-independent artifacts (design #23 §2.1/§3.1).** ``SafetyCurrentnessVector`` /
``EgressCurrentnessProof`` / ``RestrictiveFenceRecord`` / ``CurrentnessPolicy`` are
**issued-identity** records (:class:`~tos.cur._base.IndependentIdArtifact`, ``id != f(digest)``): the
id is separately issued, so a same-id / different-bytes forged, re-issued, or replayed record is a
detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` (design #23 §2.1/§3.1 —
CUR-EV-001/004). §9 line 264 "canonical vector digest and signature or equivalent integrity
evidence"; §12 line 314 "proof identity, nonce, single-use state ... integrity evidence".

**CUR = complete-vector aggregator; venue / iap / capsule = per-decision leaf (design #23 §0.4b —
the key architecture decision).** The ``SafetyCurrentnessVector`` is the **aggregating** artifact:
it carries the **injected** per-dimension owner verdicts / generations / digests as
:class:`~tos.cur.state.CurrentnessDimension` coordinates and its completeness
(:func:`~tos.cur.predicates.vector_complete`) is the **aggregate-only** axis — every-dimension-
present + single-revision + policy-complete + no-placeholder — that **no** per-decision leaf can
detect (§0.4b). cur re-authors **no** venue ``egress_currentness_active`` / iap
``active_egress_currentness`` / capsule ``egress_currentness_ok`` per-decision leaf, and **no**
egress ``QuorumCommitCertificate`` / ``RestrictiveLatchState`` / ``monotonic_denial_no_revival``
(§0.4c/d) — those produced facts are injected scalars / verdicts / digests (sibling edge 0).

**Malformed-model self-defence (design #23 §2.3 / #20 lesson).** The ``IndependentIdArtifact`` base
already rejects an ISSUED artifact whose ``_REQUIRED_COVERED`` identity is ``None`` — so a vector /
proof claiming to be a complete issued citizen while a required identity is blank is
**unconstructable** on the normal validation path. The ``model_construct`` escape hatch that skips
validators is re-caught in the §5.1/§6.5 predicate layer (defence in depth, §2.3): the
``vector_complete`` / ``proof_structurally_complete`` predicates re-derive completeness structurally
and never trust a stored flag.

**Coordinate non-collapse (design #23 §2.3).** No mutable lifecycle coordinate — the proof
``single_use_consumed`` / ``is_expired`` single-use state and the injected
``egress_coordinates.local_latch_clear`` latch state — is a covered digest field: a lawful lifecycle
transition must not change a proof's digest and be mis-flagged as a same-id / different-bytes
``CRITICAL_CONFLICT`` (the rcl / egress coordinate-non-collapse precedent). Every covered field is an
immutable claim; the current lifecycle state is injected into the predicate.

**Deterministic set-covered digest (design #23 §3.1).** ``CurrentnessPolicy.required_dimensions``
and ``RestrictiveFenceRecord.affected_scope`` are ``frozenset``s (the §8 subset-check contract);
because ``model_dump(mode="json")`` serializes a ``frozenset`` to an **unordered** list and the
canonicalizer preserves sequence order, :meth:`covered_content` **sorts** each set field so the digest
is deterministic across processes (a frozenset's iteration order is otherwise unstable). The field
type stays a ``frozenset`` for the predicate's subset math.

**All-false authority (design #23 §2.4/§6.13; CUR-INV-005).** Every artifact carries an
:class:`~tos.cur._base.AllFalseCurrentnessAuthority` with all nine flags ``False`` — a vector / proof
/ fence / policy is verified ordering data, not permission.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.cur._base``) + ``tos.cur.*``
only; no ``shared.*``, no sibling ``tos.*`` (design #23 §0.3).
"""

from __future__ import annotations

from typing import Any, ClassVar

from tos.cur._base import AllFalseCurrentnessAuthority, IndependentIdArtifact
from tos.cur.state import (
    CurrentnessDimension,
    CurrentnessRevision,
    EgressProofCoordinateSet,
    TrialClaims,
)
from tos.cur.vocabulary import DimensionKey, ProofResult

__all__ = [
    "SafetyCurrentnessVector",
    "EgressCurrentnessProof",
    "RestrictiveFenceRecord",
    "CurrentnessPolicy",
    "AllFalseCurrentnessAuthority",
]


class CurrentnessPolicy(IndependentIdArtifact):
    """The governed Currentness Policy content model (ADR-002-024 §5.1/§8; design #23 §2.4).

    §8: the policy that declares the dependency-scope closure — which dimensions a complete vector
    must carry. cur **authors** the policy *content* model (``required_dimensions``), but the policy's
    **activation / generation is spg/014-governed** (design #23 §0.4g) — carried as injected
    ``policy_generation`` / ``policy_digest`` scalars, re-authored not at all. An
    :class:`~tos.cur._base.IndependentIdArtifact` (``id != f(digest)``). Its
    :class:`~tos.cur._base.AllFalseCurrentnessAuthority` is all-false — a policy is governed content,
    not permission. Consumed by :func:`~tos.cur.predicates.policy_covers_mandated_dimensions`, which
    denies when ``required_dimensions`` under-declares the §9 mandated floor ("Unknown materiality is
    material", §8).
    """

    _ID_FIELD: ClassVar[str] = "policy_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "policy_id",
        "policy_generation",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "policy_generation",
            "policy_digest",
            "required_dimensions",
            "compatibility_manifest_digest",
            "authority_effect",
        }
    )

    policy_id: str | None = None
    #: Injected spg/014-governed activation generation (§0.4g; ``None`` ⇒ fail-closed at predicate).
    policy_generation: int | None = None
    policy_digest: str | None = None
    #: The §8 dependency-scope closure — the dimensions a complete vector must carry (subset math).
    required_dimensions: frozenset[DimensionKey] = frozenset()
    compatibility_manifest_digest: str | None = None
    #: §6.13 — a policy is governed content, not permission (all-false, CUR-INV-005).
    authority_effect: AllFalseCurrentnessAuthority = AllFalseCurrentnessAuthority()

    def covered_content(self) -> dict[str, Any]:
        """Digest preimage with the ``required_dimensions`` set serialized deterministically (§3.1).

        ``model_dump(mode="json")`` serializes a ``frozenset`` to an **unordered** list and the
        canonicalizer preserves sequence order, so the raw dump would give an unstable digest across
        processes. This override sorts ``required_dimensions`` into a canonical list so the digest is
        deterministic; the field itself stays a ``frozenset`` for the subset-check contract.

        Returns:
            The covered content mapping with ``required_dimensions`` as a sorted list.
        """
        content = super().covered_content()
        value = content.get("required_dimensions")
        if value is not None:
            content["required_dimensions"] = sorted(value)
        return content


class SafetyCurrentnessVector(IndependentIdArtifact):
    """The complete action-scoped Safety Currentness Vector (ADR-002-024 §9; design #23 §2.4).

    §9: the immutable vector that **aggregates** ~20 dependency dimensions at **one** Currentness
    Revision and whose completeness the aggregator judges (:func:`~tos.cur.predicates.vector_
    complete`). It carries its identity + Currentness Revision, the governing policy coordinates
    (injected spg/014 generation / digest), the action scope (§9 line 249), the per-dimension
    coordinates (each owner verdict / generation / digest **injected**, §9 line 250-262), the
    conditional restricted-live trial group (§9:258), and the vector digest (§9 line 264). An
    :class:`~tos.cur._base.IndependentIdArtifact` (``id != f(digest)``): a same-id / different-bytes
    forgery / rollback is a detectable ``CRITICAL_CONFLICT``. Its
    :class:`~tos.cur._base.AllFalseCurrentnessAuthority` is all-false — **holding a vector is not
    authority** (§6.13; the §5 aggregate-completeness predicate plus +Security decide, never mere
    possession).

    **Aggregate-only completeness (§0.4b).** cur re-authors **no** venue / iap / capsule per-decision
    egress-currentness leaf and **no** dimension owner's business logic (§3.5) — each leaf verdict is
    injected as one :class:`~tos.cur.state.CurrentnessDimension` coordinate. The residual cur owns is
    the completeness *axis* (every mandated dimension present + positively established + one revision +
    policy complete + no placeholder) that a per-decision leaf structurally **cannot** detect (§5.1).
    """

    _ID_FIELD: ClassVar[str] = "vector_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "vector_id",
        "currentness_revision",
        "policy_id",
        "policy_generation",
        "vector_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "currentness_revision",
            "vector_digest",
            "policy_id",
            "policy_generation",
            "policy_digest",
            "compatibility_manifest_digest",
            # action scope (§9 line 249)
            "environment",
            "safety_cell",
            "capacity_domain",
            "account",
            "portfolio",
            "strategy",
            "venue",
            "session",
            "instrument",
            "action_class",
            "route_scope",
            # dimensions (§9 line 250-262 — order-significant tuple of injected coordinates)
            "dimensions",
            "trial_claims",
            "authority_effect",
        }
    )

    vector_id: str | None = None
    #: The single Currentness Revision every dimension must sit at (§5.4 ordering identity).
    currentness_revision: CurrentnessRevision | None = None
    vector_digest: str | None = None
    #: Governing policy coordinates (injected spg/014-governed activation, §0.4g).
    policy_id: str | None = None
    policy_generation: int | None = None
    policy_digest: str | None = None
    compatibility_manifest_digest: str | None = None

    # action scope (§9 line 249)
    environment: str | None = None
    safety_cell: str | None = None
    capacity_domain: str | None = None
    account: str | None = None
    portfolio: str | None = None
    strategy: str | None = None
    venue: str | None = None
    session: str | None = None
    instrument: str | None = None
    action_class: str | None = None
    route_scope: str | None = None

    #: The aggregated per-dimension coordinates (each owner verdict / generation / digest injected,
    #: NOT re-authored — §3.5). An order-significant tuple (frozen, append-only).
    dimensions: tuple[CurrentnessDimension, ...] = ()
    #: The conditional restricted-live trial claim group (opaque; RLP-deferred, §0.4f).
    trial_claims: TrialClaims | None = None
    #: §6.13 — a vector is verified ordering data, not permission (all-false, CUR-INV-005).
    authority_effect: AllFalseCurrentnessAuthority = AllFalseCurrentnessAuthority()


class EgressCurrentnessProof(IndependentIdArtifact):
    """A single-use Egress Currentness Proof conformance fact (ADR-002-024 §12; design #23 §2.4).

    §12: the single-use conformance fact that a complete vector satisfied every restrictive floor +
    the local latch at the claim revision. It carries its identity + nonce, the single-use state, the
    expiry state, the bound vector identity / digest / committed revision, the per-owner bound
    generations + restrictive floors (§12 line 308), the injected egress-scope coordinates (§12 line
    310-311, including the egress-owned ``local_latch_clear`` latch state — §0.4d), the conditional
    trial group, the capability-claim command + committed result (§12 line 312), the SEND_STARTED
    revision + injected claim-to-send bound (§12 line 313), and the conformance ``result`` (§12 line
    316). An :class:`~tos.cur._base.IndependentIdArtifact` (``id != f(digest)``): a same-id /
    different-bytes proof substitution / replay is a detectable ``CRITICAL_CONFLICT`` (CUR-EV-004).

    **QCC != ECP (design #23 §0.4c).** cur re-authors **no** egress ``QuorumCommitCertificate`` /
    ``CommitProofValidity``: QCC is the quorum-commitment axis (egress-owned, VALID/INVALID) and this
    ECP is the currentness-conformance axis (CUR-owned, ``result`` CURRENT/RESTRICTED/UNKNOWN). The
    egress QCC **carries** this proof's id (``egress_currentness_proof_id``) as a bound claim
    (egress → cur consumption, never the reverse).

    **Coordinate non-collapse (§2.3).** ``single_use_consumed`` / ``is_expired`` (single-use
    lifecycle) and ``egress_coordinates`` (the injected latch-state carrier) are **excluded** from the
    covered digest — a lawful consume / expire transition must not change the proof's digest. The
    current lifecycle state is injected into :func:`~tos.cur.predicates.proof_admissible`.
    """

    _ID_FIELD: ClassVar[str] = "proof_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "proof_id",
        "nonce",
        "vector_id",
        "vector_digest",
        "committed_revision",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "nonce",
            "issue_revision",
            "expiry_evidence",
            "vector_id",
            "vector_digest",
            "committed_revision",
            "bound_generations",
            "restrictive_floors",
            "capability_claim_command",
            "claim_committed_result",
            "send_started_revision",
            "max_claim_to_send_bound_ms",
            "result",
            "trial_claims",
            "authority_effect",
        }
    )

    proof_id: str | None = None
    nonce: str | None = None
    #: Negative-polarity single-use state (mutable lifecycle — NOT covered, §2.3). ``is not False``
    #: (True / None) ⇒ reject reuse (§12 "consumed ... proof is denial"); admit needs ``is False``.
    single_use_consumed: bool | None = None
    issue_revision: CurrentnessRevision | None = None
    expiry_evidence: str | None = None
    #: Negative-polarity expiry state (mutable lifecycle — NOT covered, §2.3). ``is not False``
    #: (True / None) ⇒ future-use deny (§6.10); admit needs ``is False``.
    is_expired: bool | None = None

    vector_id: str | None = None
    vector_digest: str | None = None
    committed_revision: CurrentnessRevision | None = None
    #: Per-owner bound generations (§12 line 308; order-significant tuple).
    bound_generations: tuple[int, ...] = ()
    #: Per-owner restrictive floors (§12 line 308; order-significant tuple).
    restrictive_floors: tuple[int, ...] = ()
    #: Injected egress-scope coordinate mirror + egress-owned latch state (NOT covered — §0.4c/d/§2.3).
    egress_coordinates: EgressProofCoordinateSet = EgressProofCoordinateSet()
    #: The conditional restricted-live trial claim group (opaque; RLP-deferred, §0.4f).
    trial_claims: TrialClaims | None = None

    capability_claim_command: str | None = None
    claim_committed_result: str | None = None
    send_started_revision: CurrentnessRevision | None = None
    #: Injected Profile-INSTANCE bound (§8 — null in Phase 1, fail-closed at predicate).
    max_claim_to_send_bound_ms: int | None = None

    #: The §12 conformance result (Only CURRENT admits, §6.6) — truthy-untestable enum.
    result: ProofResult | None = None
    #: §6.13 — a proof is verified ordering data, not permission (all-false, CUR-INV-005).
    authority_effect: AllFalseCurrentnessAuthority = AllFalseCurrentnessAuthority()


class RestrictiveFenceRecord(IndependentIdArtifact):
    """One monotonic restrictive-floor advance (ADR-002-024 §5.5/§11; design #23 §2.4).

    §10 line 278 / §11: a fence that "advances a minimum accepted generation or terminal denial
    floor" over an affected scope. It carries its identity + owner, the affected scope, the
    predecessor + advanced floors (the monotonic advance judged by
    :func:`~tos.cur.predicates.fence_advances_floor`), the terminal-denial flag, and the fence digest.
    An :class:`~tos.cur._base.IndependentIdArtifact`. Its
    :class:`~tos.cur._base.AllFalseCurrentnessAuthority` is all-false. **The Local Restrictive Latch
    state machine + monotonic resolver is egress-owned (Final Egress Trust Boundary = ADR-002-013;
    §0.4d) — this record is the predicate-only floor-advance substrate; the real fence commit +
    deny-first sequence is runtime** (§11 line 285-300).
    """

    _ID_FIELD: ClassVar[str] = "fence_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "fence_id",
        "owner_identity",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "owner_identity",
            "affected_scope",
            "predecessor_floor",
            "advanced_floor",
            "terminal_denial",
            "fence_digest",
            "authority_effect",
        }
    )

    fence_id: str | None = None
    owner_identity: str | None = None
    #: The scope this fence restricts (frozenset for §6.3 union math; sorted in the covered digest).
    affected_scope: frozenset[str] = frozenset()
    predecessor_floor: int | None = None
    #: §10 line 278 — the advanced minimum accepted generation / terminal denial floor.
    advanced_floor: int | None = None
    #: Negative-polarity — ``is True`` ⇒ terminal denial (§10 restrictive-only-sufficient).
    terminal_denial: bool | None = None
    fence_digest: str | None = None
    #: §6.13 — a fence is verified ordering data, not permission (all-false, CUR-INV-005).
    authority_effect: AllFalseCurrentnessAuthority = AllFalseCurrentnessAuthority()

    def covered_content(self) -> dict[str, Any]:
        """Digest preimage with the ``affected_scope`` set serialized deterministically (§3.1).

        Mirrors :meth:`CurrentnessPolicy.covered_content`: a ``frozenset`` dumps to an unordered
        list and the canonicalizer preserves order, so the scope is sorted into a canonical list for
        a deterministic digest; the field stays a ``frozenset`` for the §6.3 union math.

        Returns:
            The covered content mapping with ``affected_scope`` as a sorted list.
        """
        content = super().covered_content()
        value = content.get("affected_scope")
        if value is not None:
            content["affected_scope"] = sorted(value)
        return content
