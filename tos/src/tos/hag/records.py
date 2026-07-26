"""hag digest-bound artifacts — the eight human-authority ledger citizens (design #20 §2).

Every artifact is a **pydantic v2 frozen model** (``frozen=True, extra="forbid"`` via
:class:`~tos.hag._base.FrozenModel`): ``extra="forbid"`` is the schema-level "omission is
restrictive" and frozen is the append-only, current-generation-bound realization; there is
**no** update / delete / mutate method on any model (design #20 §2.0/§4.6). Field names use the
ADR §5-§22 terms **verbatim** (spec terms = code terms, boundary design #1 §2.4).

**Eight id-independent artifacts (design #20 §2.1/§3.1).** ``HumanAuthorityPolicy`` /
``EffectivePrincipalGraph`` / ``HumanApprovalRequest`` / ``HumanApprovalAttestation`` /
``HumanApprovalSet`` / ``ApprovalSetConsumptionRecord`` / ``HumanHaltCommand`` /
``HumanDelegationRecord`` are **issued-identity** records
(:class:`~tos.hag._base.IndependentIdArtifact`, ``id != f(digest)``): the id is separately issued,
so a same-id / different-bytes forged, re-issued, contradictory (substitution §10 / §22), or
replayed record is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` (HAG-EV-002/004/012).

**Coordinate non-collapse (design #20 §2.3).** The mutable :class:`~tos.hag.vocabulary.
ApprovalLifecycleState` is **not** a covered digest field of any artifact — a lawful lifecycle
transition (e.g. ``REVIEWABLE`` -> ``ATTESTING``) must not change the digest and be mis-flagged as
a same-id / different-bytes ``CRITICAL_CONFLICT``. The current state is injected into the predicate
and recorded as a separate append-only transition, not carried on the artifact (the liveauth
coordinate-non-collapse precedent). ``_REQUIRED_COVERED`` names only a **structural** coordinate
(a generation / request digest), never a numeric bound (Phase-1 null profiles must still build).

**All-false authority (design #20 §2.4/§4.3; HAG-INV-004).** Every authority-bearing artifact
carries a :class:`~tos.hag._base.HumanAuthorityEffect` with all six flags ``False`` — approval is
a safety datum, not permission. ``EffectivePrincipalGraph`` is a pure structural artifact and
carries no authority effect (it grants nothing).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.hag._base``) + ``tos.hag.*``
only; no ``shared.*``, no sibling ``tos.*`` (design #20 §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import model_validator

from tos.hag._base import (
    ArtifactIntegrityError,
    HumanAuthorityEffect,
    IndependentIdArtifact,
)
from tos.hag.state import (
    ApprovalScope,
    EffectiveControlEdge,
    EffectivePrincipalNode,
    QuorumRule,
)
from tos.hag.vocabulary import (
    AttestationDecision,
    AuthorityClass,
    ConflictRole,
)

__all__ = [
    "HumanAuthorityPolicy",
    "EffectivePrincipalGraph",
    "HumanApprovalRequest",
    "HumanApprovalAttestation",
    "HumanApprovalSet",
    "ApprovalSetConsumptionRecord",
    "HumanHaltCommand",
    "HumanDelegationRecord",
    "HumanAuthorityEffect",
]


class HumanAuthorityPolicy(IndependentIdArtifact):
    """An immutable, separately-governed Human Authority Policy (ADR-002-015 §9; design #20 §2.4).

    §9 declares the human-authority policy content: quorum-by-approval-type, declared
    conflict roles, independence constraints, authentication strength, and scopes. An
    :class:`~tos.hag._base.IndependentIdArtifact` (``id != f(digest)``): the ``policy_id`` is
    separately issued, so a same-id / different-bytes policy forgery / rollback is a detectable
    ``CRITICAL_CONFLICT``. **Policy activation / generation / supersession is spg-owned**
    (ADR-002-014 §9; §3.5) — hag is the content author, not the activation authority; it consumes
    the activation verdict as an injected scalar. Carries an all-false
    :class:`~tos.hag._base.HumanAuthorityEffect` (authoring a policy grants no runtime authority).
    """

    _ID_FIELD: ClassVar[str] = "policy_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("policy_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "policy_generation",
            "scope",
            "quorum_by_approval_type",
            "declared_conflict_roles",
            "authentication_strength",
            "human_authority_effect",
        }
    )

    policy_id: str | None = None
    policy_generation: int | None = None
    #: The policy scope identity (environment / broker / account / venue / segment / instrument).
    scope: str | None = None
    #: Per-approval-type quorum rules (injected N — null in Phase 1, fail-closed at the predicate).
    quorum_by_approval_type: tuple[QuorumRule, ...] = ()
    #: The declared conflict roles governed by this policy (§12 minimum set is non-waivable).
    declared_conflict_roles: frozenset[ConflictRole] = frozenset()
    #: The required authentication strength token (injected; actual auth is +Security, §14).
    authentication_strength: str | None = None
    #: §4.3 — authoring a policy creates no authority (all-false, HAG-INV-004).
    human_authority_effect: HumanAuthorityEffect = HumanAuthorityEffect()

    def quorum_for(self, approval_type: AuthorityClass) -> int | None:
        """The declared quorum for ``approval_type`` (``None`` if undeclared / null).

        Returns the injected ``quorum_n`` for the exact approval type, or ``None`` when the type
        is not declared — an undeclared quorum fails closed at
        :func:`~tos.hag.predicates.quorum_independence_satisfied` (never a permissive default, §8).

        Args:
            approval_type: The exact authority class.

        Returns:
            The declared quorum count, or ``None`` if undeclared.
        """
        for rule in self.quorum_by_approval_type:
            if rule.approval_type is approval_type:
                return rule.quorum_n
        return None


class EffectivePrincipalGraph(IndependentIdArtifact):
    """An immutable effective-principal control graph (ADR-002-015 §8 line 253-272; design #20 §2.4).

    §8: the graph whose nodes are identity coordinates (account / credential / device / session /
    service id / recovery path / control path) and whose edges are control relationships (reset /
    impersonate / mint-credential / approve-as / change-role). An
    :class:`~tos.hag._base.IndependentIdArtifact` (``id != f(digest)``): a same-id / different-bytes
    graph substitution is a detectable ``CRITICAL_CONFLICT``. Consumed by
    :func:`~tos.hag.predicates.effective_principal_collapse`, whose distinct-count verdict feeds
    the downstream liveauth ``DualControlAttestation.distinct_approver_count`` (§3.5 — hag produces,
    liveauth consumes). Carries **no** authority effect (a graph grants nothing).

    **Two-layer completeness (design #20 §2.4/§4.1; MAJOR-2).** ``unresolved_control`` is the
    graph-level completeness flag: a graph-level flag cannot identify *which* node / edge is
    missing, so per-edge merging is impossible when it is unproven ⇒ ``True`` / ``None`` is a
    **whole-graph denial** (§8 line 271 "incompletely resolved effective-control state is denial";
    the quorum / SoD / dual-control predicates reject unless ``unresolved_control is False``). The
    per-edge :attr:`~tos.hag.state.EffectiveControlEdge.resolved` coordinate is the fine-grained
    merge layer (an unresolved edge still merges, fail-closed).
    """

    _ID_FIELD: ClassVar[str] = "graph_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("graph_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "graph_generation",
            "nodes",
            "edges",
            "unresolved_control",
        }
    )

    graph_id: str | None = None
    graph_generation: int | None = None
    nodes: tuple[EffectivePrincipalNode, ...] = ()
    edges: tuple[EffectiveControlEdge, ...] = ()
    #: Graph-level completeness (MAJOR-2). ``True`` / ``None`` ⇒ whole-graph denial (§8 line 271);
    #: only ``False`` (positively fully resolved) admits a quorum / SoD / dual-control judgement.
    unresolved_control: bool | None = None

    def node_ids(self) -> frozenset[str]:
        """The set of concrete node ``principal_id`` coordinates (skips null nodes).

        Returns:
            The frozenset of non-``None`` node ids in the graph.
        """
        return frozenset(
            n.principal_id for n in self.nodes if n.principal_id is not None
        )

    @model_validator(mode="after")
    def _malformed_edge_forbids_resolved_claim(self) -> EffectivePrincipalGraph:
        """A None-endpoint control edge cannot coexist with ``unresolved_control=False`` (MAJOR-1).

        A control edge missing an endpoint (``source`` / ``target`` is ``None``) is an
        **incompletely-resolved** effective-control fact: the collapse cannot merge a ``None``
        coordinate, so such an edge would be silently dropped and let a same-person-multi-identity
        escape merging (ADR-002-015 §8 line 271 "incompletely resolved effective-control state is
        denial"; §2 line 40 — the one-person-two-accounts attack). This validator forbids the
        graph from *positively claiming* full resolution (``unresolved_control is False``) while any
        edge is malformed — so a malformed graph is forced to ``unresolved_control`` ``None`` / ``True``
        (a whole-graph denial via the §5.1 (vii) gate), never a false ``False``. A ``None`` / ``True``
        graph may carry malformed edges (it already denies).
        """
        if self.unresolved_control is False:
            for edge in self.edges:
                if edge.source is None or edge.target is None:
                    raise ArtifactIntegrityError(
                        "EffectivePrincipalGraph declares unresolved_control=False but carries an "
                        "incompletely-resolved (None-endpoint) control edge — a graph cannot claim "
                        "full effective-control resolution while an edge is malformed (ADR-002-015 "
                        "§8 line 271; design #20 MAJOR-1). Leave unresolved_control None/True (a "
                        "whole-graph denial) until every control edge names both endpoints."
                    )
        return self


class HumanApprovalRequest(IndependentIdArtifact):
    """An immutable Human Approval Request binding one exact context (ADR-002-015 §10; design #20 §2.4).

    §10 line 300-310: a request binds the exact decision context — the requested action, the
    maximum authority class, the scope, the evidence-package digest, the Decision Context Capsule
    identity and digest, and the bound policy / graph generations. An
    :class:`~tos.hag._base.IndependentIdArtifact` (``id != f(digest)``): a same-id / different-bytes
    request substitution is a detectable ``CRITICAL_CONFLICT`` (HAG-EV-002). **The request binds the
    capsule digest** (request -> capsule direction, §10 line 306; MAJOR-1): the capsule
    ``approval_request_id`` (``capsule.py:161``) is the **iap** automated-pipeline chain field
    (iap ``ProposalApprovalRequest`` axis, §0.4a/§0.4e) — **not** an HAG downstream reference; hag
    binds only the capsule identity / digest, never the capsule's own ``approval_request_id``.
    Carries an all-false :class:`~tos.hag._base.HumanAuthorityEffect` (a request is a proposal, not
    permission, §5.5).
    """

    _ID_FIELD: ClassVar[str] = "request_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("creation_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "request_type",
            "nonce",
            "predecessor_request_id",
            "creation_generation",
            "requested_action",
            "maximum_authority",
            "scope",
            "evidence_package_digest",
            "decision_context_capsule_id",
            "decision_context_capsule_digest",
            "policy_generation",
            "graph_generation",
            "reason",
            "requested_validity",
            "consumption_rule",
            "human_authority_effect",
        }
    )

    request_id: str | None = None
    #: The requested authority class (§7 taxonomy; break-glass restricted by §5.4).
    request_type: AuthorityClass | None = None
    nonce: str | None = None
    predecessor_request_id: str | None = None
    creation_generation: int | None = None
    requested_action: str | None = None
    #: The maximum authority the request may confer (§10; never exceeded by the attestations).
    maximum_authority: AuthorityClass | None = None
    scope: ApprovalScope = ApprovalScope()
    #: Bound evidence-package digest (sbr-owned; hag binds the scalar, §3.5).
    evidence_package_digest: str | None = None
    #: Bound Decision Context Capsule (capsule-owned; request -> capsule digest bind, §10 line 306).
    decision_context_capsule_id: str | None = None
    decision_context_capsule_digest: str | None = None
    #: Bound policy / graph generation coordinates (injected scalars; sibling edge 0).
    policy_generation: int | None = None
    graph_generation: int | None = None
    reason: str | None = None
    requested_validity: str | None = None
    consumption_rule: str | None = None
    #: §5.5 — a request is a proposal, not permission (all-false, HAG-INV-004).
    human_authority_effect: HumanAuthorityEffect = HumanAuthorityEffect()


class HumanApprovalAttestation(IndependentIdArtifact):
    """A single human attestation on an exact request (ADR-002-015 §10 line 312; design #20 §2.4).

    §10 line 312: an **individual** human decision binding the exact request digest, the attesting
    principal, its effective-principal-graph generation, its role, and the review context. An
    :class:`~tos.hag._base.IndependentIdArtifact` (``id != f(digest)``). The ``decision`` is the
    truthy-sealed :class:`~tos.hag.vocabulary.AttestationDecision` — a consume gate MUST use
    ``decision is AttestationDecision.APPROVE`` (§4.7). This is the **human** attestation axis; iap
    has no such per-principal artifact (ADR §4 line 98 — an automated ``APPROVE`` cannot satisfy a
    human quorum; §0.4e). Carries an all-false :class:`~tos.hag._base.HumanAuthorityEffect`.
    """

    _ID_FIELD: ClassVar[str] = "attestation_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("request_digest",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "request_digest",
            "principal_id",
            "effective_principal_graph_generation",
            "role",
            "decision",
            "reviewed_inputs_digest",
            "independent_recompute_result",
            "authenticator_session_context",
            "issue_generation",
            "expiry",
            "human_authority_effect",
        }
    )

    attestation_id: str | None = None
    #: The exact request digest this attestation binds (exact context binding, §5.2).
    request_digest: str | None = None
    #: The attesting principal (opaque coordinate — collapsed to a natural person, §5.1).
    principal_id: str | None = None
    effective_principal_graph_generation: int | None = None
    role: ConflictRole | None = None
    #: The truthy-sealed human decision (consume gate: ``is AttestationDecision.APPROVE``, §4.7).
    decision: AttestationDecision | None = None
    reviewed_inputs_digest: str | None = None
    independent_recompute_result: bool | None = None
    authenticator_session_context: str | None = None
    #: Opaque injected issue / expiry coordinates (clock-free — hag reads no clock, §8).
    issue_generation: int | None = None
    expiry: str | None = None
    human_authority_effect: HumanAuthorityEffect = HumanAuthorityEffect()


class HumanApprovalSet(IndependentIdArtifact):
    """An immutable set of attestations forming a quorum (ADR-002-015 §11; design #20 §2.4).

    §11: the set of :class:`HumanApprovalAttestation` bound to one request, evaluated for
    quorum-independence (§5.1). An :class:`~tos.hag._base.IndependentIdArtifact`. §5.6: the set is
    **not** a Live Authorization and grants **no** broker or capacity authority — its
    :class:`~tos.hag._base.HumanAuthorityEffect` is all-false. Downstream references it via the
    evidence ``approval_set_id`` slot (``envelope.py:93``, §3.4 — evidence carries the HAG id;
    hag does not import evidence).
    """

    _ID_FIELD: ClassVar[str] = "set_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("bound_request_digest",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "attestations",
            "policy_generation",
            "graph_generation",
            "bound_request_digest",
            "human_authority_effect",
        }
    )

    set_id: str | None = None
    attestations: tuple[HumanApprovalAttestation, ...] = ()
    policy_generation: int | None = None
    graph_generation: int | None = None
    #: The exact request digest every attestation binds (§5.2 exact binding).
    bound_request_digest: str | None = None
    #: §5.6 — the set is not Live Authorization and grants no authority (all-false, HAG-INV-004).
    human_authority_effect: HumanAuthorityEffect = HumanAuthorityEffect()


class ApprovalSetConsumptionRecord(IndependentIdArtifact):
    """A single-use consumption of an approval set (ADR-002-015 §11/§18; design #20 §2.4).

    §5.8/§11: the atomic single-use consumption of a :class:`HumanApprovalSet` by a downstream
    decision. An :class:`~tos.hag._base.IndependentIdArtifact`: a re-consumption (same set digest,
    or a reused consumption id) is rejected by :func:`~tos.hag.predicates.approval_set_single_use`
    (§23 line 611 "Approval consumed twice ⇒ reject"). ``single_use`` must be positively ``True``.
    Carries an all-false :class:`~tos.hag._base.HumanAuthorityEffect` (consuming a set records a
    fact; it issues no authority — the downstream issuer does, §4.3).
    """

    _ID_FIELD: ClassVar[str] = "consumption_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("consumed_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "approval_set_digest",
            "downstream_decision_ref",
            "single_use",
            "consumed_generation",
            "human_authority_effect",
        }
    )

    consumption_id: str | None = None
    #: The digest of the consumed approval set (single-use — one consumption per set, §5.3).
    approval_set_digest: str | None = None
    downstream_decision_ref: str | None = None
    #: Positive single-use witness; anything but ``True`` fails closed at the predicate.
    single_use: bool | None = None
    consumed_generation: int | None = None
    human_authority_effect: HumanAuthorityEffect = HumanAuthorityEffect()


class HumanHaltCommand(IndependentIdArtifact):
    """An immutable human HALT command (ADR-002-015 §15; design #20 §2.4).

    §15: an independent authorized human may issue a restrictive HALT without a proposer, strategy,
    dual-control quorum, or live-arming service. An :class:`~tos.hag._base.IndependentIdArtifact`
    carrying the restrictive generation (ordering, monotonic — §4.6), scope, environment, and the
    bound policy / session / trustworthy-time generations (all injected scalars). Its
    :class:`~tos.hag._base.HumanAuthorityEffect` is all-false: **setting a restrictive latch is a
    defined effect, not a permissive authority** — every one of the six permissive flags is
    ``False`` (§2.4). Judged by :func:`~tos.hag.predicates.human_halt_monotonic_restrictive`.
    """

    _ID_FIELD: ClassVar[str] = "command_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("restrictive_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "principal_id",
            "scope",
            "environment",
            "nonce",
            "policy_generation",
            "session_generation",
            "restrictive_generation",
            "trustworthy_time_generation",
            "human_authority_effect",
        }
    )

    command_id: str | None = None
    principal_id: str | None = None
    scope: ApprovalScope = ApprovalScope()
    environment: str | None = None
    nonce: str | None = None
    policy_generation: int | None = None
    session_generation: int | None = None
    #: The monotonic restrictive generation this HALT sets (ordering carries the scalar, §3.2).
    restrictive_generation: int | None = None
    trustworthy_time_generation: int | None = None
    #: §2.4 — a restrictive latch is a defined effect, not a permissive authority (all-false).
    human_authority_effect: HumanAuthorityEffect = HumanAuthorityEffect()


class HumanDelegationRecord(IndependentIdArtifact):
    """An immutable human delegation record (ADR-002-015 §13; design #20 §2.4).

    §13: a bounded, non-transitive, revocable delegation of one role / scope from a grantor to a
    delegate, never exceeding the grantor's authority. An
    :class:`~tos.hag._base.IndependentIdArtifact`. ``transitive`` defaults to ``False`` (a
    delegation is non-transitive unless explicitly permitted, §13 line 364); judged by
    :func:`~tos.hag.predicates.delegation_bounded_nontransitive`. Carries an all-false
    :class:`~tos.hag._base.HumanAuthorityEffect` (delegating records a grant; it issues no runtime
    authority, §4.3).
    """

    _ID_FIELD: ClassVar[str] = "delegation_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("delegation_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "grantor_principal",
            "delegate_principal",
            "role",
            "scope",
            "validity",
            "transitive",
            "delegation_generation",
            "revocation_generation",
            "human_authority_effect",
        }
    )

    delegation_id: str | None = None
    grantor_principal: str | None = None
    delegate_principal: str | None = None
    role: ConflictRole | None = None
    scope: ApprovalScope = ApprovalScope()
    validity: str | None = None
    #: Non-transitive by default (§13 line 364 — no onward delegation without explicit permission).
    transitive: bool = False
    delegation_generation: int | None = None
    revocation_generation: int | None = None
    human_authority_effect: HumanAuthorityEffect = HumanAuthorityEffect()
