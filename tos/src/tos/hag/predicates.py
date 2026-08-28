"""hag human-authority predicates (design #20 §5/§6) — pure, fail-closed.

Pure decision rules over injected frozen models (design #20 §0.2/§4.6): hag authors the
**human-authority general model** — effective-principal collapse, quorum-independence, exact
approval binding, single-use consumption, break-glass direction, human-protective proposal-only,
dual-control distinctness, economic continuity / non-revival, replay reconstruction, separation
of duties, human HALT monotonicity, delegation bounds, compromise fail-closed, and the
governed-single-operator variant substrate. It **re-authors none** of the sibling instances it
feeds or consumes: liveauth owns the §17 re-arm consumption instance
(``rearm_dual_control_satisfied`` / ``Safe053VariantAttestation`` / ``ReArmPathKind`` /
7-control / 13-prerequisite), spg owns the safety-config break-glass action-token
(``break_glass_confined``), iap owns the automated per-proposal decision
(``IndependentApprovalDecision``), protective owns the classification verdict
(``protective_classification``), rcl owns capacity, and evidence owns replay custody (§3.5). hag
**consumes** every one of those as an **injected produced scalar / bool / verdict / digest** and
re-authors none of them.

**The effective-principal collapse yolk (design #20 §4.1/§5.1; HAG-EV-001).** Two required human
approvals must come from two distinct **effective natural persons** — not two accounts / sessions
/ credentials / role labels (§8 line 267). :func:`effective_principal_collapse` merges the
endpoints of **every** control edge (union-find component); an **unresolved** edge is merged
exactly like a resolved one (fail-closed: unknown control ⇒ merge ⇒ distinct-count reduction ⇒
quorum harder, §4.1). This is what the liveauth string ``!=`` (``predicates.py:525``) cannot do —
``alice-svc-01`` ``!=`` ``alice-svc-02`` is distinct to a string compare but collapses to one
person here (§3.5). Two MAJOR-2 gates guard it: every attesting principal must be **in** the graph
nodes (an unrepresented principal counted as an isolated singleton is the "one person approving
twice" fail-open, ADR §2 line 40), and the graph-level ``unresolved_control`` must be positively
``False`` (an incompletely-resolved graph is a whole-graph denial, §8 line 271).

**Truthy-sentinel discipline (design #20 §4.7).** ``AttestationDecision`` / ``ApprovalLifecycleState``
are truthy-untestable ``StrEnum``s (``__bool__`` raises), so every gate uses ``x is ENUM.SAFE_VALUE``
(``decision is AttestationDecision.APPROVE`` / ``state is ApprovalLifecycleState.QUORUM_SATISFIED``);
a bare ``if decision:`` would fail open reading ``DENY`` / ``EXPIRED`` as approval. Injected
``bool | None`` flags are normalized with ``is True`` / ``is not True`` (a ``None`` is UNKNOWN,
never a soft pass).

Pure module: ``pydantic`` + stdlib + ``tos.hag.*`` (records / state / vocabulary / _base) only; no
``shared.*``, no other sibling ``tos.*`` (design #20 §0.3).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from tos.hag._base import HumanAuthorityEffect
from tos.hag.records import (
    ApprovalSetConsumptionRecord,
    EffectivePrincipalGraph,
    HumanApprovalAttestation,
    HumanApprovalRequest,
    HumanDelegationRecord,
    HumanHaltCommand,
)
from tos.hag.state import ApprovalScope, RoleAssignment
from tos.hag.vocabulary import (
    BREAK_GLASS_RESTRICTIVE_CLASSES,
    PROGRESS_LIFECYCLE_STATES,
    TERMINAL_LIFECYCLE_STATES,
    ApprovalLifecycleState,
    AttestationDecision,
    AuthorityClass,
    ConflictRole,
)

__all__ = [
    # core §5 (HAG-EV-001/002/004/006/007/010/011/012 substrate)
    "effective_principal_collapse",
    "quorum_independence_satisfied",
    "approval_binding_exact",
    "material_change_invalidates",
    "approval_set_single_use",
    "stale_replayed_rejected",
    "lifecycle_transition_legal",
    "break_glass_direction_restrictive",
    "human_protective_request_proposal_only",
    "dual_control_effective_distinct",
    "partial_rearm_scope_narrows",
    "approval_expiry_preserves_economic_effect",
    "no_automatic_rearm",
    "human_authority_replay_reconstructs",
    "human_authority_effect_separated",
    # predicate-only §6 (HAG-EV-003/005/008/009/013-018 substrate)
    "separation_of_duties_satisfied",
    "human_halt_monotonic_restrictive",
    "degraded_path_no_permissive",
    "delegation_bounded_nontransitive",
    "compromise_fails_closed",
    "variant_pre_declared_exact_scope",
    "operator_config_authz_error_fail_closed",
]


#: The §12 line 345-354 minimum forbidden role pairs (design #20 §6.1). A single effective natural
#: person may hold at most one role of each pair. The minimum is **non-waivable** (a policy may add
#: more, §12); each pair anchors an ADR §12 conflict clause.
_FORBIDDEN_ROLE_PAIRS: frozenset[frozenset[ConflictRole]] = frozenset(
    {
        # trading proposer ∧ trade approver
        frozenset({ConflictRole.TRADING_PROPOSER, ConflictRole.TRADE_APPROVER}),
        # envelope / profile author ∧ sole approver
        frozenset({ConflictRole.ENVELOPE_PROFILE_AUTHOR, ConflictRole.TRADE_APPROVER}),
        # limit approver ∧ sole armer
        frozenset({ConflictRole.LIMIT_APPROVER, ConflictRole.LIVE_ARMER}),
        # evidence producer ∧ reviewer
        frozenset({ConflictRole.EVIDENCE_PRODUCER, ConflictRole.EVIDENCE_REVIEWER}),
        # recovery coordinator ∧ sole re-arm approver
        frozenset({ConflictRole.RECOVERY_COORDINATOR, ConflictRole.REARM_APPROVER}),
        # policy admin ∧ beneficiary (the trade proposer who benefits)
        frozenset({ConflictRole.POLICY_ADMIN, ConflictRole.TRADING_PROPOSER}),
        # roster admin ∧ quorum member (an approver)
        frozenset({ConflictRole.IDENTITY_ROSTER_ADMIN, ConflictRole.TRADE_APPROVER}),
        # credential / route admin ∧ sole approver
        frozenset({ConflictRole.CREDENTIAL_ROUTE_ADMIN, ConflictRole.TRADE_APPROVER}),
        # approval-set verifier ∧ downstream issuer
        frozenset({ConflictRole.APPROVAL_SET_VERIFIER, ConflictRole.DOWNSTREAM_ISSUER}),
        # break-glass custodian ∧ bypass approver
        frozenset({ConflictRole.BREAK_GLASS_CUSTODIAN, ConflictRole.BYPASS_APPROVER}),
    }
)

#: The legal approval-lifecycle transitions (ADR-002-015 §18 line 511-518, verbatim-aligned).
#: Terminal / invalid states have no entry here — they have **no** permissive exit (§18 line 521).
#: Only ``QUORUM_SATISFIED`` may reach ``CONSUMED`` (line 521); ``SUPERSEDED`` is reachable only from
#: ``QUORUM_SATISFIED`` (line 518); ``QUORUM_SATISFIED`` may still be ``DENIED`` (line 514 — "a later
#: APPROVE does not erase a retained denial").
_LEGAL_LIFECYCLE_TRANSITIONS: dict[
    ApprovalLifecycleState, frozenset[ApprovalLifecycleState]
] = {
    ApprovalLifecycleState.REQUESTED: frozenset(
        {
            ApprovalLifecycleState.REVIEWABLE,
            ApprovalLifecycleState.DENIED,
            ApprovalLifecycleState.EXPIRED,
            ApprovalLifecycleState.INVALIDATED,
            ApprovalLifecycleState.REVOKED,
        }
    ),
    ApprovalLifecycleState.REVIEWABLE: frozenset(
        {
            ApprovalLifecycleState.ATTESTING,
            ApprovalLifecycleState.DENIED,
            ApprovalLifecycleState.EXPIRED,
            ApprovalLifecycleState.INVALIDATED,
            ApprovalLifecycleState.REVOKED,
        }
    ),
    ApprovalLifecycleState.ATTESTING: frozenset(
        {
            ApprovalLifecycleState.QUORUM_SATISFIED,
            ApprovalLifecycleState.DENIED,
            ApprovalLifecycleState.EXPIRED,
            ApprovalLifecycleState.INVALIDATED,
            ApprovalLifecycleState.REVOKED,
        }
    ),
    ApprovalLifecycleState.QUORUM_SATISFIED: frozenset(
        {
            ApprovalLifecycleState.CONSUMED,
            ApprovalLifecycleState.DENIED,
            ApprovalLifecycleState.EXPIRED,
            ApprovalLifecycleState.INVALIDATED,
            ApprovalLifecycleState.REVOKED,
            ApprovalLifecycleState.SUPERSEDED,
        }
    ),
}


def _graph_completely_resolved(graph: EffectivePrincipalGraph) -> bool:
    """Whether the graph positively claims full effective-control resolution (§8 line 271; MAJOR-1).

    The §5.1 (vii) graph-completeness gate, hardened against a malformed edge. Returns ``True``
    **only** when ``unresolved_control is False`` **and** no control edge is incompletely resolved
    (a ``None``-endpoint edge that the collapse cannot merge). The edge re-check is defence in depth
    for a graph that reached the consumer via an unvalidated ``model_construct`` path (bypassing the
    :class:`~tos.hag.records.EffectivePrincipalGraph` validator, §4.3) — a malformed edge under a
    ``False`` claim would let a same-person-multi-identity escape merging (ADR §2 line 40).

    Args:
        graph: The effective-principal control graph.

    Returns:
        ``True`` iff the graph positively and completely claims full resolution.
    """
    if graph.unresolved_control is not False:
        return False
    # No control edge may be malformed under a False claim (a None-endpoint edge the collapse
    # cannot merge would let a same-person-multi-identity escape, ADR §2 line 40).
    return all(
        edge.source is not None and edge.target is not None for edge in graph.edges
    )


# ===========================================================================
# core §5.1 — effective-principal collapse + quorum independence (HAG-EV-001, the yolk, +Security)
# ===========================================================================


def effective_principal_collapse(
    graph: EffectivePrincipalGraph | None,
    principal_ids: Iterable[str],
) -> dict[str, str]:
    """Collapse identity coordinates to their effective natural persons (§8; HAG-INV-001).

    The central pure function (HAG-EV-001 yolk). §8 line 267 verbatim: "Quorum evaluation SHALL
    collapse all nodes under common effective control before counting principals." The effective
    principal of a coordinate is its **connected component** in the control graph (union-find over
    the reset / impersonate / mint-credential / approve-as / change-role edges). §8 line 271:
    "Unknown, stale, contradictory, or incompletely resolved effective-control state is denial for
    authority increase" — so an **unresolved** edge (:attr:`~tos.hag.state.EffectiveControlEdge.
    resolved` ``is not True``) is merged **exactly like** a resolved one (fail-closed — the merge
    is never gated on ``resolved is True``, which would let an unresolved control edge escape and
    inflate the distinct count, §4.1 / property 13). This catches the same-person-multi-identity
    that the liveauth string ``!=`` (``predicates.py:525``) cannot (§3.5).

    Pure and deterministic: the class representative is the lexicographic minimum of the component,
    so the mapping is stable across runs. A ``None`` graph yields each requested principal as its
    own singleton (the graph-membership / completeness gate is the caller's — §5.1 (vii)); this
    function does not reject, it only collapses.

    **WARNING — this is a low-level primitive; do NOT gate authority on it directly.** It cannot
    merge a ``None``-endpoint control edge (there is no coordinate to merge to), so such an edge is
    dropped here. On its own that would be a fail-open (an incompletely-resolved edge escaping the
    merge). It is safe **only** because every authority-gating consumer runs the §5.1 (vii)
    completeness gate (:func:`_graph_completely_resolved`) first, which rejects any graph that
    carries a malformed edge while claiming ``unresolved_control is False`` (and the
    :class:`~tos.hag.records.EffectivePrincipalGraph` validator forbids that combination at
    construction, MAJOR-1). Never call this primitive as the sole basis for a quorum / SoD /
    dual-control decision.

    Args:
        graph: The effective-principal control graph (``None`` => every principal is a singleton).
        principal_ids: The coordinates to resolve to their effective-principal class.

    Returns:
        A mapping ``{principal_id: class_representative}`` for every requested principal.
    """
    requested = list(principal_ids)
    parent: dict[str, str] = {}

    def _find(x: str) -> str:
        parent.setdefault(x, x)
        root = x
        while parent[root] != root:
            root = parent[root]
        # Path compression (still deterministic — representative is min-of-component below).
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def _union(a: str, b: str) -> None:
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[rb] = ra

    # Seed every graph node + every requested principal so isolated coordinates are singletons.
    if graph is not None:
        for node_id in graph.node_ids():
            parent.setdefault(node_id, node_id)
        for edge in graph.edges:
            if edge.source is None or edge.target is None:
                continue
            # §4.1: every control edge merges its endpoints; an UNRESOLVED edge (resolved is not
            # True) is merged exactly like a resolved one (fail-closed — never gated on
            # `resolved is True`, which would be a fail-open letting unresolved control escape).
            _union(edge.source, edge.target)
    for pid in requested:
        parent.setdefault(pid, pid)

    # Group into components, then pick the deterministic (min) representative per component.
    components: dict[str, set[str]] = {}
    for member in parent:
        components.setdefault(_find(member), set()).add(member)
    representative: dict[str, str] = {}
    for members in components.values():
        rep = min(members)
        for member in members:
            representative[member] = rep

    return {pid: representative[pid] for pid in requested}


def quorum_independence_satisfied(
    attestations: Sequence[HumanApprovalAttestation],
    graph: EffectivePrincipalGraph | None,
    quorum_n: int | None,
    required_roles: frozenset[ConflictRole],
) -> bool:
    """Whether the attestations satisfy an independent human quorum (§8/§11; HAG-INV-001; HAG-AC-001).

    Returns ``True`` **only** when every condition holds (§5.1):

    * (i)   every attestation's ``decision is AttestationDecision.APPROVE`` (truthy-sealed gate —
            ``DENY`` / ``ABSTAIN`` never count, §4.7);
    * (ii)  the collapsed distinct effective-principal count is ``>= quorum_n``;
    * (iii) **no duplicate effective principal** — two attestations that collapse to one natural
            person are rejected outright (§11 line 325 "reject duplicate natural persons"; the
            "one person approving twice through two accounts" attack, ADR §2 line 40);
    * (iv)  every ``required_role`` is covered by an attestation;
    * (v)   ``quorum_n >= 1`` (a degenerate ``quorum_n`` of ``0`` / ``None`` is denial — no
            authority increase without a human, §4.1);
    * (vi)  the attestation set is non-empty (∅ => 0 distinct < N, §4.7);
    * (vii) **every attesting principal is in ``graph.nodes`` AND ``graph.unresolved_control is
            False``** — an unrepresented principal (counted as an isolated singleton) or an
            incompletely-resolved graph is an immediate denial (MAJOR-2; §8 line 271; ADR §2 line
            40 — the collapse-bypass fail-open).

    hag **produces** this distinct count; the liveauth ``DualControlAttestation.
    distinct_approver_count`` (``state.py:180``) **consumes** it (§3.5) — hag imports no liveauth.

    Args:
        attestations: The human attestations (∅ => ``False``).
        graph: The effective-principal control graph (``None`` / unresolved => ``False``).
        quorum_n: The injected policy quorum (``None`` / ``< 1`` => ``False``).
        required_roles: The roles the quorum must cover.

    Returns:
        ``True`` iff an independent human quorum is positively satisfied.
    """
    if graph is None:
        return False
    # (vii) graph-level completeness — an incompletely-resolved graph (unresolved_control not
    # positively False, OR a malformed None-endpoint edge under a False claim) is a whole-graph
    # denial (§8 line 271; MAJOR-1 defence-in-depth for a model_construct bypass).
    if not _graph_completely_resolved(graph):
        return False
    # (v) degenerate / unknown quorum is denial.
    if quorum_n is None or quorum_n < 1:
        return False
    # (vi) ∅ attestations => 0 distinct < N.
    if not attestations:
        return False
    node_ids = graph.node_ids()
    for att in attestations:
        # (i) truthy-sealed positive-identity gate — only APPROVE counts.
        if att.decision is not AttestationDecision.APPROVE:
            return False
        # (vii) every attesting principal must be represented in the graph.
        if att.principal_id is None or att.principal_id not in node_ids:
            return False
    principals = [
        att.principal_id for att in attestations if att.principal_id is not None
    ]
    collapse = effective_principal_collapse(graph, principals)
    classes = [collapse[pid] for pid in principals]
    # (iii) no duplicate effective principal (one person approving twice is rejected outright).
    distinct_classes = set(classes)
    if len(distinct_classes) != len(classes):
        return False
    # (ii) distinct effective-principal count must meet the quorum.
    if len(distinct_classes) < quorum_n:
        return False
    # (iv) every required role covered by an attestation.
    roles_present = {att.role for att in attestations if att.role is not None}
    return required_roles <= roles_present


# ===========================================================================
# core §5.2 — exact approval context binding (HAG-EV-002, +Security)
# ===========================================================================


def approval_binding_exact(
    request: HumanApprovalRequest | None,
    attestation: HumanApprovalAttestation | None,
) -> bool:
    """Whether the attestation binds the exact request digest (§10; HAG-INV-002; HAG-AC-002).

    §10 line 300-310: every approval binds one exact request / scope / evidence / policy context.
    The attestation's ``request_digest`` must equal the request's ``canonical_digest`` — the
    request digest covers all of §10's bound context (enforced structurally by the digest-bound
    base), so an exact match proves the attestation binds that exact context. A ``None`` request /
    attestation, a missing digest, or any mismatch fails closed.

    Args:
        request: The human approval request (``None`` / null digest => ``False``).
        attestation: The attestation (``None`` / null request_digest => ``False``).

    Returns:
        ``True`` iff the attestation binds the request's exact canonical digest.
    """
    if request is None or attestation is None:
        return False
    if request.canonical_digest is None or attestation.request_digest is None:
        return False
    return attestation.request_digest == request.canonical_digest


def material_change_invalidates(
    prior_request: HumanApprovalRequest | None,
    current_context_digest: str | None,
) -> bool:
    """Whether a material context change invalidates a pre-consumption approval (§1 line 30; HAG-INV-008).

    §1 line 30 / HAG-INV-008: if any bound context (input / capsule / venue / intent / evidence /
    scope / digest / generation / software / deployment / broker / credential / route / time /
    residual / policy) changes, a pre-consumption approval is invalid and a new request + approval
    is required. Returns ``True`` (**invalidated**) whenever the current recomputed context digest
    does **not** exactly equal the prior request's canonical digest — including when either is
    ``None`` (unknown context is treated as changed, fail-closed). The same-id / different-digest
    pair is separately a ``classify_record_pair`` ``CRITICAL_CONFLICT`` (replay / substitution
    resistance, §5.2).

    Args:
        prior_request: The prior approval request (``None`` => invalidated).
        current_context_digest: The recomputed current context digest (``None`` => invalidated).

    Returns:
        ``True`` iff the approval is invalidated by a material change.
    """
    if prior_request is None or prior_request.canonical_digest is None:
        return True
    if current_context_digest is None:
        return True
    return current_context_digest != prior_request.canonical_digest


# ===========================================================================
# core §5.3 — approval-set single-use + stale/replayed rejection + lifecycle (HAG-EV-004, +Security)
# ===========================================================================


def approval_set_single_use(
    consumption_record: ApprovalSetConsumptionRecord | None,
    prior_consumptions: Iterable[ApprovalSetConsumptionRecord],
) -> bool:
    """Whether a single-use approval set may be consumed exactly once (§11/§5.8; HAG-AC-004).

    §5.8: "A single-use set cannot be consumed again." Returns ``True`` **only** when the record
    exists, is positively ``single_use``, carries a concrete consumption id and set digest, and
    **no** prior consumption already consumed that set digest or reused that consumption id (§23
    line 611 "Approval consumed twice ⇒ reject"). Any missing field, a non-positive ``single_use``,
    or any collision fails closed.

    Args:
        consumption_record: The proposed consumption (``None`` / non-single-use => ``False``).
        prior_consumptions: The prior consumption records (a collision => ``False``).

    Returns:
        ``True`` iff this is a valid first-time single-use consumption.
    """
    if consumption_record is None:
        return False
    if consumption_record.single_use is not True:
        return False
    if consumption_record.consumption_id is None:
        return False
    if consumption_record.approval_set_digest is None:
        return False
    for prior in prior_consumptions:
        if prior.approval_set_digest == consumption_record.approval_set_digest:
            return False  # the set was already consumed (single-use spent)
        if prior.consumption_id == consumption_record.consumption_id:
            return False  # the consumption id was reused (replay)
    return True


def stale_replayed_rejected(
    lifecycle_state: ApprovalLifecycleState | None,
    *,
    replayed: bool | None = None,
    policy_matches: bool | None = None,
) -> bool:
    """Whether an attestation / set must be rejected as stale / replayed / mismatched (§11/§18; SAFE-035).

    Returns ``True`` (**reject**) whenever the item is not in a live progress state, has been
    replayed, or no longer matches the current policy (§11 line 329). A terminal / invalid state
    (``CONSUMED`` / ``DENIED`` / ``EXPIRED`` / ``INVALIDATED`` / ``REVOKED`` / ``SUPERSEDED``), a
    ``None`` state, a positive ``replayed``, or a non-positive ``policy_matches`` all reject
    (fail-closed — the truthy-sealed state is compared by identity, never ``if state:``). Returns
    ``False`` (**not rejected**) **only** for a live progress state that is not replayed and whose
    policy positively matches.

    Args:
        lifecycle_state: The current approval lifecycle state (``None`` / terminal => reject).
        replayed: Whether the item was replayed (``True`` => reject).
        policy_matches: Whether the item matches the current policy (not ``True`` => reject).

    Returns:
        ``True`` iff the item must be rejected.
    """
    if lifecycle_state is None:
        return True
    if lifecycle_state in TERMINAL_LIFECYCLE_STATES:
        return True
    if lifecycle_state not in PROGRESS_LIFECYCLE_STATES:
        return True  # unknown / unmodelled state => reject (fail-closed)
    if replayed is True:
        return True
    return policy_matches is not True


def lifecycle_transition_legal(
    from_state: ApprovalLifecycleState | None,
    to_state: ApprovalLifecycleState | None,
) -> bool:
    """Whether an approval-lifecycle transition is legal (§18 line 511-521; HAG-AC-004).

    §18 line 521 verbatim: "Only ``QUORUM_SATISFIED`` may become ``CONSUMED`` ... No terminal or
    invalid state returns to a permissive state." Returns ``True`` **only** for a transition in the
    fixed :data:`_LEGAL_LIFECYCLE_TRANSITIONS` table — a terminal / invalid ``from_state`` (which
    has no table entry) never has a legal exit, so no permissive revival is representable. A ``None``
    endpoint fails closed.

    Args:
        from_state: The current state (``None`` / terminal => ``False``).
        to_state: The proposed next state (``None`` => ``False``).

    Returns:
        ``True`` iff the transition is legal.
    """
    if from_state is None or to_state is None:
        return False
    return to_state in _LEGAL_LIFECYCLE_TRANSITIONS.get(from_state, frozenset())


# ===========================================================================
# core §5.4 — break-glass directional confinement (HAG-EV-006, +Security — spg boundary)
# ===========================================================================


def break_glass_direction_restrictive(authority_class: AuthorityClass | None) -> bool:
    """Whether a break-glass action is direction-restrictive (§7/§16; HAG-INV-006; HAG-AC-006).

    Returns ``True`` **only** when ``authority_class`` is one of the three restrictive classes
    (``HALT`` / ``NARROW`` / ``REQUEST_PROTECTIVE``, §7 table / §16 line 425). Every other class
    (``APPROVE_*`` / ``ACCEPT_RESIDUAL_RISK`` / ``CAPACITY_MUTATION`` / ``TRANSMIT``) and a ``None``
    (unproven direction ⇒ ``MAY_INCREASE``, §7 line 249) is authority-increasing and rejected; a
    break-glass action can never create / restore / broaden / prolong new-risk authority or
    auto-revert (HAG-INV-006). This is the **human authority-class direction** axis (8 classes) —
    **not** a re-authoring of the spg safety-config ``break_glass_confined`` action-token
    (``{HALT, RESTRICTIVE_OVERRIDE}``, 2 tokens; §3.5 (b) — spg's docstring explicitly defers the
    effective-principal-independence residue to HAG).

    Args:
        authority_class: The break-glass authority class (``None`` / non-restrictive => ``False``).

    Returns:
        ``True`` iff the class is direction-restrictive.
    """
    if authority_class is None:
        return False
    return authority_class in BREAK_GLASS_RESTRICTIVE_CLASSES


# ===========================================================================
# core §5.5 — human protective request is proposal-only (HAG-EV-007 — protective boundary)
# ===========================================================================


def human_protective_request_proposal_only(
    request: HumanApprovalRequest | None,
    protective_classification_admissible: bool | None,
    capacity_authorized: bool | None,
    egress_verified: bool | None,
) -> bool:
    """Whether a human containment request may proceed — never on the label alone (§16; HAG-INV-007).

    §16 line 438 verbatim: "If the proposed action cannot be proven protective, it is risk
    increasing." A human containment request is a **proposal**, not permission — it proceeds
    ``True`` **only** when all four hold: (i) the request is a ``REQUEST_PROTECTIVE`` class; (ii) a
    **separate** protective classification positively returned ADMISSIBLE
    (``protective_classification_admissible is True`` — the injected protective verdict, §16 line
    429); (iii) capacity is positively authorized by rcl / an exclusive sub-ledger; and (iv) egress
    positively verified the exact current capability. The human label itself performs **no**
    protective classification (HAG-INV-007). Any missing / non-positive verdict fails closed. The
    protective ``protective_classification`` (``predicates.py:246``) / rcl capacity / egress checks
    are **injected verdicts**, re-authored by none of them (§3.5).

    Args:
        request: The human containment request (``None`` / non-protective class => ``False``).
        protective_classification_admissible: The injected protective verdict (not ``True`` =>
            ``False``).
        capacity_authorized: The injected capacity verdict (not ``True`` => ``False``).
        egress_verified: The injected egress verdict (not ``True`` => ``False``).

    Returns:
        ``True`` iff the containment request may proceed on all four positive conditions.
    """
    if request is None:
        return False
    if request.request_type is not AuthorityClass.REQUEST_PROTECTIVE:
        return False
    if protective_classification_admissible is not True:
        return False
    if capacity_authorized is not True:
        return False
    return egress_verified is True


# ===========================================================================
# core §5.6 — dual-control effective distinctness + narrow scope (HAG-EV-010, +Security — liveauth boundary)
# ===========================================================================


def dual_control_effective_distinct(
    attestations: Sequence[HumanApprovalAttestation],
    graph: EffectivePrincipalGraph | None,
) -> bool:
    """Whether a re-arm quorum has two distinct effective natural persons (§17; HAG-AC-010; SAFE-053).

    §17 line 444: re-arm dual control requires **>= 2 distinct effective natural persons** — the
    collapse-before-count of :func:`quorum_independence_satisfied` with ``quorum_n=2`` (inheriting
    the MAJOR-2 node-membership + ``unresolved_control`` whole-graph-denial gate, §5.1 (vii)). An
    external reviewer who collapses to the operator is **not** a second principal (§17.1.4 /
    HAG-INV-018 — handled by the distinct-class requirement). This is the **liveauth boundary**
    (§3.5 (a)): hag **produces** the distinct-count meaning; the liveauth
    ``rearm_dual_control_satisfied`` (``predicates.py:492``) **consumes** the count — hag imports
    no liveauth and re-authors none of its 7-control / 13-prerequisite re-arm instance.

    Args:
        attestations: The re-arm attestations (< 2 distinct effective persons => ``False``).
        graph: The effective-principal control graph (``None`` / unresolved => ``False``).

    Returns:
        ``True`` iff there are >= 2 distinct effective natural persons.
    """
    return quorum_independence_satisfied(
        attestations, graph, quorum_n=2, required_roles=frozenset()
    )


def partial_rearm_scope_narrows(
    prior_scope: ApprovalScope | None,
    new_scope: ApprovalScope | None,
) -> bool:
    """Whether a partial re-arm restores only a subset of the prior scope (§17 line 457; SAFE-053).

    §17 line 457 verbatim: "Partial re-arm restores only the exact approved scope." Returns
    ``True`` **only** when, on **every** one of the 7 scope dimensions, the new dimension is a
    subset of the prior — an empty new dimension is a lawful full de-authorization (``∅ ⊆ prior``,
    §4.7 both-ways), while a ``None`` dimension on either side is unknown and fails closed (never a
    permissive default, §8). A widening on any dimension is rejected.

    Args:
        prior_scope: The prior approved scope (``None`` => ``False``).
        new_scope: The re-armed scope (``None`` => ``False``).

    Returns:
        ``True`` iff the new scope narrows (⊆) the prior on every dimension.
    """
    if prior_scope is None or new_scope is None:
        return False
    for dim in ApprovalScope.DIMENSIONS:
        prior_val = getattr(prior_scope, dim)
        new_val = getattr(new_scope, dim)
        if prior_val is None or new_val is None:
            return False  # unknown dimension => fail-closed
        if not (new_val <= prior_val):
            return False  # widening => rejected
    return True


# ===========================================================================
# core §5.7 — approval/economic continuity + non-revival (HAG-EV-011; HAG-INV-012/014)
# ===========================================================================


def approval_expiry_preserves_economic_effect(expiry_event: object | None) -> bool:
    """Whether approval expiry preserves the economic effect — always (§18/§20; HAG-INV-012).

    HAG-INV-012 line 202 / §18 line 525: approval expiry / revocation / consumption does **not**
    cancel an order, release capacity, resolve an ``UNKNOWN``, prove broker non-acceptance, or
    prove a final quantity. Realized as an **unconditional** ``True`` with the ``expiry_event``
    **accepted and discarded**: the model provides **no** economic-effect-mutating operation at all,
    so nothing an expiry event carries can change the answer — this predicate documents and fixes
    that structural absence (isomorphic to the liveauth ``authorization_revived_by_nothing`` /
    iap ``economic_effect_outlives`` replica pattern, human axis; §3.5).

    Returns:
        ``True`` — an approval expiry never mutates an economic effect (unconditionally).
    """
    del expiry_event  # accepted and discarded — no economic-effect mutation exists to influence.
    return True


def no_automatic_rearm(
    *,
    health_recovered: bool | None = None,
    timeout_elapsed: bool | None = None,
    reconciliation_completed: bool | None = None,
    leader_elected: bool | None = None,
    restart_completed: bool | None = None,
) -> bool:
    """Whether any recovery event auto-re-arms — never (§18/§20; HAG-INV-014; HAG-AC-011).

    HAG-INV-014 line 210: no human / credential / device / IdP / workflow / approval-service /
    control-plane recovery re-uses an approval or restores live authority automatically. Realized
    as an **unconditional** ``True`` with every recovery input **accepted and discarded**: no
    recovery / timeout / restart flag can influence the answer because the model provides **no**
    auto-re-arm path at all — a lawful re-arm always requires a fresh governed workflow (§3.5),
    never a revival (isomorphic to the liveauth ``no_automatic_rearm`` ``predicates.py:606`` replica
    pattern, human axis).

    Returns:
        ``True`` — nothing auto-re-arms (unconditionally).
    """
    del health_recovered, timeout_elapsed, reconciliation_completed
    del leader_elected, restart_completed
    return True


# ===========================================================================
# core §5.8 — human authority replay reconstructs + evidence-is-not-authority (HAG-EV-012)
# ===========================================================================


def human_authority_replay_reconstructs(
    records: Sequence[tuple[str | None, str | None]],
) -> bool:
    """Whether an append-only human-authority record set replays without a Critical conflict (§22; HAG-AC-012).

    §22 line 585: replay reconstructs the human-authority history (identity / effective control /
    policy / evidence review / approval / denial / HALT / consumption / compromise / re-arm) from
    the digest-bound append-only records. Returns ``True`` **only** when **no** two records share a
    primary id with different canonical bytes — a same-id / different-bytes pair is a
    ``classify_record_pair`` ``CRITICAL_CONFLICT`` (forgery / replay / substitution) that breaks
    reconstruction. Any pre-issuance (null digest) record is not a ledger citizen and is skipped
    (``NOT_COMPARABLE``). This L1 substrate is the **record consistency** check; the replay ENGINE
    and custody are evidence-owned (§3.5 — evidence carries the HAG digests, hag imports no evidence).

    Args:
        records: The ``(primary_id, canonical_digest)`` pairs to replay.

    Returns:
        ``True`` iff no same-id / different-bytes Critical conflict exists.
    """
    seen: dict[str, str] = {}
    for identity, digest in records:
        if identity is None or digest is None:
            continue  # pre-issuance / not a ledger citizen => NOT_COMPARABLE, skipped.
        if identity in seen and seen[identity] != digest:
            return (
                False  # same id, different bytes => CRITICAL_CONFLICT => replay broken.
            )
        seen.setdefault(identity, digest)
    return True


def human_authority_effect_separated(effect: HumanAuthorityEffect | None) -> bool:
    """Whether a human-authority effect grants no authority (§4.3/§5.8; HAG-INV-004).

    The §4.3 defence-in-depth predicate: because :class:`~tos.hag._base.HumanAuthorityEffect` is
    unconstructable with any ``True`` flag, a *validated* effect always separates authority — this
    is the defining predicate that states it, **and** the re-check for a block that reached the
    consumer via an unvalidated ``model_construct`` path (never trust an un-validated block, §4.3).
    Returns ``True`` **only** when the effect exists and every one of its six flags is ``False`` —
    evidence / replay reconstructs a record but never re-creates authority (§22 line 596 "Evidence
    and notification do not substitute for enforcement").

    Args:
        effect: The human-authority effect (``None`` / any ``True`` flag => ``False``).

    Returns:
        ``True`` iff the effect grants no authority.
    """
    if effect is None:
        return False
    return not (
        effect.mutates_capacity
        or effect.activates_configuration
        or effect.issues_live_authorization
        or effect.clears_deny_latch
        or effect.transmits_to_broker
        or effect.re_arms
    )


# ===========================================================================
# predicate-only §6.1 — separation of duties (HAG-EV-003, ≥ EV-L2/3+Security)
# ===========================================================================


def separation_of_duties_satisfied(
    role_assignment: RoleAssignment | None,
    graph: EffectivePrincipalGraph | None,
) -> bool:
    """Whether the role assignment violates no §12 forbidden pair on an effective person (§12; HAG-INV-003).

    Judges the §12 minimum forbidden role pairs (:data:`_FORBIDDEN_ROLE_PAIRS`) over **effective
    principals** — the role grants are collapsed to their natural persons **first** (§5.1), then no
    effective person may hold both roles of any forbidden pair (§12 line 358 "automation cannot
    count as a human principal"). Inherits the MAJOR-2 gate (§5.1 (vii)): every grant's principal
    must be in ``graph.nodes`` and ``graph.unresolved_control is False``, else denial. An **empty**
    role assignment holds no forbidden pair (no one has authority — the availability side is
    satisfied), but the graph-completeness gate still applies. This is the **human role-conflict**
    axis — **not** the authority capability-lease exclusivity (§3.5). The real identity / roster
    mechanism is +Security (HAG-EV-003 is ≥ EV-L2).

    Args:
        role_assignment: The (principal, role) grants (``None`` => ``False``).
        graph: The effective-principal control graph (``None`` / unresolved => ``False``).

    Returns:
        ``True`` iff no effective person holds a forbidden role pair.
    """
    if role_assignment is None or graph is None:
        return False
    if not _graph_completely_resolved(graph):
        return False  # (vii) incompletely-resolved / malformed-edge graph => denial (MAJOR-1/-2)
    node_ids = graph.node_ids()
    for grant in role_assignment.grants:
        if grant.principal_id is None or grant.role is None:
            return False  # incomplete grant => fail-closed
        if grant.principal_id not in node_ids:
            return False  # (vii) unrepresented principal => denial (MAJOR-2)
    principals = [
        g.principal_id for g in role_assignment.grants if g.principal_id is not None
    ]
    collapse = effective_principal_collapse(graph, principals)
    # Map each effective person to the set of roles they hold.
    roles_by_person: dict[str, set[ConflictRole]] = {}
    for grant in role_assignment.grants:
        if grant.principal_id is None or grant.role is None:
            continue
        person = collapse[grant.principal_id]
        roles_by_person.setdefault(person, set()).add(grant.role)
    for held in roles_by_person.values():
        for pair in _FORBIDDEN_ROLE_PAIRS:
            if pair <= held:
                return (
                    False  # one effective person holds both roles of a forbidden pair
                )
    return True


# ===========================================================================
# predicate-only §6.2 — human HALT monotonic-restrictive + degraded no-permissive (HAG-EV-005, ≥ EV-L2/3+Security)
# ===========================================================================


def human_halt_monotonic_restrictive(
    command: HumanHaltCommand | None,
    prior_generation: int | None,
) -> bool:
    """Whether a human HALT command is monotonic-restrictive (§15; HAG-INV-005; SAFE line).

    §15 line 410: a HALT command is monotonic restrictive only — its restrictive generation must
    strictly advance and it can carry **no** permissive effect. Returns ``True`` **only** when the
    command exists, carries a concrete ``restrictive_generation``, its
    :class:`~tos.hag._base.HumanAuthorityEffect` grants no authority (permissive forbidden, §4.3),
    and — when a ``prior_generation`` is given — the new generation **strictly** exceeds it (a
    duplicate / non-advancing generation is not a new restrictive step). A ``None``
    ``prior_generation`` is the first HALT (monotonic trivially). The real HALT
    availability / propagation timing (``B_human_halt_to_commit``) is +Security runtime (§8.1;
    HAG-EV-005 is ≥ EV-L2) — L1 is the command-shape monotonicity substrate only.

    Args:
        command: The human HALT command (``None`` / null generation / permissive => ``False``).
        prior_generation: The prior restrictive generation (``None`` => first HALT).

    Returns:
        ``True`` iff the HALT command is monotonic-restrictive.
    """
    if command is None:
        return False
    if command.restrictive_generation is None:
        return False
    if not human_authority_effect_separated(command.human_authority_effect):
        return False  # a permissive HALT is never monotonic-restrictive (§15 line 410)
    # No prior HALT is the first (monotonic trivially); otherwise the generation must strictly advance.
    return prior_generation is None or command.restrictive_generation > prior_generation


def degraded_path_no_permissive(
    command: HumanHaltCommand | None,
    safety_commit_log_available: bool | None,
) -> bool:
    """Whether a degraded-path HALT admits only a restrictive latch (§15/§20; HAG-INV-005).

    §15 line 417: when the Safety Commit Log is unavailable (degraded path), only a restrictive
    local latch may be applied — a **permissive command is never admitted** (§20 line 551 — a
    pre-provisioned authenticator is finite-restrictive only). Returns ``True`` **only** when the
    command exists and grants no authority (its :class:`~tos.hag._base.HumanAuthorityEffect` is all
    false); a ``None`` command or any permissive effect fails closed. The ``safety_commit_log_
    available`` flag is accepted and does **not** loosen the check — whether or not the log is
    available, only a restrictive latch is ever admitted (the degraded path only restricts
    further). The real availability / failure-domain isolation is +Security runtime (§6.2;
    HAG-EV-005 is ≥ EV-L2).

    Args:
        command: The human HALT command (``None`` / permissive => ``False``).
        safety_commit_log_available: Whether the Safety Commit Log is available (accepted; the
            degraded path does not loosen the restrictive-only rule).

    Returns:
        ``True`` iff only a restrictive latch is admitted (no permissive command).
    """
    del safety_commit_log_available  # accepted — the degraded path never loosens restrictive-only.
    if command is None:
        return False
    return human_authority_effect_separated(command.human_authority_effect)


# ===========================================================================
# predicate-only §6.3 — delegation bounded + non-transitive (HAG-EV-008, ≥ EV-L2/3+Security)
# ===========================================================================


def delegation_bounded_nontransitive(
    delegation: HumanDelegationRecord | None,
    grantor_authority_roles: frozenset[ConflictRole],
    graph: EffectivePrincipalGraph | None,
) -> bool:
    """Whether a delegation is bounded, non-transitive, and within the grantor's authority (§13; HAG-INV-009).

    §13 line 364-378: a delegation is one role / scope, **non-transitive** (unless explicitly
    permitted), cannot exceed the grantor's authority, and the grantor + delegate cannot count
    independently on the same request while effective control persists. Returns ``True`` **only**
    when the delegation exists, is **not** transitive (``transitive is False``), names a concrete
    role within the grantor's authorized roles, names concrete grantor + delegate principals both
    represented in a fully-resolved graph, and the grantor + delegate do **not** collapse to one
    effective natural person (else they cannot count independently, §5.1). Any missing / exceeding /
    transitive / collapsed condition fails closed. The real roster / employment-change mechanism is
    +Security (HAG-EV-008 is ≥ EV-L2).

    Args:
        delegation: The delegation record (``None`` / transitive => ``False``).
        grantor_authority_roles: The roles the grantor is actually authorized for.
        graph: The effective-principal control graph (``None`` / unresolved => ``False``).

    Returns:
        ``True`` iff the delegation is bounded, non-transitive, and independent.
    """
    if delegation is None or graph is None:
        return False
    if not _graph_completely_resolved(graph):
        return False  # (vii) incompletely-resolved / malformed-edge graph => denial (MAJOR-1/-2)
    if delegation.transitive is not False:
        return False  # non-transitive unless explicitly permitted (§13 line 364)
    if delegation.role is None or delegation.role not in grantor_authority_roles:
        return False  # cannot exceed the grantor's authority
    grantor = delegation.grantor_principal
    delegate = delegation.delegate_principal
    if grantor is None or delegate is None:
        return False
    node_ids = graph.node_ids()
    if grantor not in node_ids or delegate not in node_ids:
        return False  # (vii) both principals must be represented (MAJOR-2)
    collapse = effective_principal_collapse(graph, [grantor, delegate])
    # Grantor and delegate must be distinct effective persons to count independently (§5.1).
    return collapse[grantor] != collapse[delegate]


# ===========================================================================
# predicate-only §6.4 — compromise fails closed (HAG-EV-009, ≥ EV-L2/3+Security)
# ===========================================================================


def compromise_fails_closed(
    *,
    compromise_suspected: bool | None,
    pending_authority_invalidated: bool | None,
    scope_restricted_to_narrowest: bool | None,
    economic_effect_preserved: bool | None,
) -> bool:
    """Whether a suspected compromise response fails closed correctly (§19; HAG-INV-010).

    §19 line 531-539: a suspected compromise (approver / authenticator / device / session / IdP /
    roster / signer / verifier / recovery / break-glass custody) invalidates the affected sessions
    / delegations / pending attestations / unconsumed sets, restricts to the narrowest scope, and
    **preserves** the economic effect while requiring a fresh governed recovery. Returns ``True``
    (**correctly fails closed**) when a compromise is not positively present
    (``compromise_suspected is False`` — nothing to contain), or — for a suspected **or unknown**
    (``None``, treated as suspected, fail-closed) compromise — when the pending authority is
    positively invalidated, the scope is positively restricted to the narrowest, and the economic
    effect is positively preserved. Any missing containment step under a (possibly-unknown)
    compromise fails (``False``). The real detection / reconciliation is +Security (HAG-EV-009 is
    ≥ EV-L2).

    Args:
        compromise_suspected: Whether a compromise is suspected (``None`` => treated as suspected).
        pending_authority_invalidated: Whether pending authority is invalidated.
        scope_restricted_to_narrowest: Whether scope is restricted to the narrowest.
        economic_effect_preserved: Whether the economic effect is preserved.

    Returns:
        ``True`` iff the containment response fails closed correctly.
    """
    if compromise_suspected is False:
        return True  # positively no compromise — nothing to contain.
    # Suspected (True) OR unknown (None, treated as suspected — fail-closed): full containment.
    if pending_authority_invalidated is not True:
        return False
    if scope_restricted_to_narrowest is not True:
        return False
    return economic_effect_preserved is True


# ===========================================================================
# predicate-only §6.5/§6.6 — governed single-operator variant + operator config/authz (HAG-EV-013-018)
# ===========================================================================


def variant_pre_declared_exact_scope(
    variant_declared: bool | None,
    declared_scope: ApprovalScope | None,
    current_scope: ApprovalScope | None,
) -> bool:
    """Whether a governed-single-operator variant was pre-declared with the exact scope (§17.1; HAG-INV-015).

    §17.1.1: a variant is admissible **only** when an approved policy pre-declared it with the exact
    scope — the operator may not select or expand it at re-arm time ("Absence of a current, exact
    declaration is denial"). Returns ``True`` **only** when the variant is positively declared, both
    scopes exist, and the current scope **exactly equals** the declared scope on every one of the 7
    dimensions (no expansion, no ad-hoc selection). A ``None`` declaration / scope / dimension fails
    closed. This is the **general-model** residue only — liveauth already realizes the §17.1 re-arm
    **consumption** instance (7-control / 13-prerequisite / ``ReArmPathKind``), which hag re-authors
    **not** (§0.4b/§6.5). ≥ EV-L2 — not closed.

    Args:
        variant_declared: Whether the policy pre-declared the variant (not ``True`` => ``False``).
        declared_scope: The pre-declared exact scope (``None`` => ``False``).
        current_scope: The scope being exercised now (``None`` => ``False``).

    Returns:
        ``True`` iff the variant was pre-declared with exactly the current scope.
    """
    if variant_declared is not True:
        return False
    if declared_scope is None or current_scope is None:
        return False
    for dim in ApprovalScope.DIMENSIONS:
        declared_val = getattr(declared_scope, dim)
        current_val = getattr(current_scope, dim)
        if declared_val is None or current_val is None:
            return False  # unknown dimension => fail-closed
        if declared_val != current_val:
            return False  # ad-hoc selection / expansion => denial (§17.1.1)
    return True


def operator_config_authz_error_fail_closed(
    variant_declaration_present: bool | None,
    scope_matches: bool | None,
    authorization_valid: bool | None,
) -> bool:
    """Whether an operator's variant config + authorization is positively valid (§17.1; HAG-INV-015).

    §17.1.1: a missing / mis-configured variant declaration, a scope mismatch, or an authorization
    error is **denial** ("Absence of a current, exact declaration is denial"). Returns ``True``
    (**admit**) **only** when all three are positively ``True``: the variant declaration is present,
    the scope matches, and the authorization is valid. Any ``None`` / ``False`` fails closed — the
    predicate never admits on an unknown config / authz state. The real config / authorization
    evaluation is +Security (HAG-EV-018 is ≥ EV-L2).

    Args:
        variant_declaration_present: Whether the variant declaration is present (not ``True`` =>
            ``False``).
        scope_matches: Whether the current scope matches the declaration (not ``True`` => ``False``).
        authorization_valid: Whether the operator authorization is valid (not ``True`` => ``False``).

    Returns:
        ``True`` iff config + authorization are all positively valid.
    """
    if variant_declaration_present is not True:
        return False
    if scope_matches is not True:
        return False
    return authorization_valid is True
