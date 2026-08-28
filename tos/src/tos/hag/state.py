"""hag injected inputs + value models + monotonic-generation ordering REUSE (design #20 §2.4/§3.2).

Two roles:

* **injected value / input models (design #20 §2.4)** — the effective-principal graph elements
  (:class:`EffectivePrincipalNode` / :class:`EffectiveControlEdge`), the 7-dimension human
  :class:`ApprovalScope` (isomorphic to the liveauth ``LiveAuthorizationScope`` 7-frozenset —
  a *different axis*, authored locally, no import), the SoD :class:`RoleAssignment` /
  :class:`RoleGrant`, the policy :class:`QuorumRule`, and the injected
  :class:`AttestationInputs`. Every one is a **pydantic v2 frozen model** (``frozen=True,
  extra="forbid"`` via :class:`~tos.hag._base.FrozenModel`): ``extra="forbid"`` is the
  schema-level "omission is restrictive", and frozen is the append-only realization — there is
  **no** update / delete / mutate method on any model (design #20 §2.0/§4.6).

* **monotonic-generation order (design #20 §3.2 ordering REUSE)** — :func:`generation_monotone`
  REUSES ``tos.ordering.compare_order`` (no re-authored order) for approval-lifecycle /
  graph / roster / policy / restrictive-HALT generation order (§8/§9/§13/§15). hag owns the
  fence *meaning* (invalidation / supersession, §4.5); ordering only carries the monotonic order.
  A wall clock never orders — hag reads **no** clock (§8).

**Numeric-bound freedom (design #20 §8; ADR §4 non-scope).** hag carries no numeric quorum /
age / cooling / latency constant: every such value is an **injected** opaque scalar carried as
policy content (null in Phase 1, fail-closed at the consuming predicate). Nothing numeric is
hardcoded — the human-authority logic is over StrEnums, booleans, set / graph membership, and
injected values only.

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.hag.*`` only; no ``shared.*``, no
other sibling ``tos.*`` (design #20 §0.3). Clock-free.
"""

from __future__ import annotations

from typing import ClassVar

from tos.hag._base import FrozenModel
from tos.hag.vocabulary import AuthorityClass, ConflictRole
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "EffectivePrincipalNode",
    "EffectiveControlEdge",
    "ApprovalScope",
    "RoleGrant",
    "RoleAssignment",
    "QuorumRule",
    "AttestationInputs",
    "generation_monotone",
]


class EffectivePrincipalNode(FrozenModel):
    """One node of the effective-principal control graph (ADR-002-015 §8 line 253-272).

    A node is an opaque identity coordinate — an account, credential, device, session, service
    id, recovery path, or administrative control path (§8 line 255). Its ``principal_id`` is the
    opaque coordinate the collapse operates over (the same opaque string liveauth carries as
    ``armer_principal`` — distinctness only, §3.5). ``node_kind`` is an optional descriptive token
    (never a permission). The *meaning* of the coordinate — whether two coordinates collapse to
    one natural person — is decided by :func:`~tos.hag.predicates.effective_principal_collapse`
    over the control edges, never by the string itself (the liveauth ``!=`` limitation, §3.5).
    """

    principal_id: str | None = None
    #: Optional descriptive token (account / credential / device / session / service / recovery /
    #: control-path); a structural label, never a permission.
    node_kind: str | None = None


class EffectiveControlEdge(FrozenModel):
    """One control relationship in the effective-principal graph (ADR-002-015 §8 line 253-267).

    A directed control relationship — password reset, impersonation, credential mint, approve-as,
    or role change (§8 line 261) — under which the ``source`` coordinate can act as / control the
    ``target``. Consumed by :func:`~tos.hag.predicates.effective_principal_collapse`, which merges
    the endpoints of **every** edge into one effective principal (the union-find component).

    ``resolved`` is the **per-edge, fine-grained** completeness coordinate (design #20 §2.4/§4.1):
    ``resolved is True`` is a positively-resolved (confirmed) control link; ``resolved is not
    True`` (``None`` unknown / ``False`` unproven) is an **unresolved** link. §8 line 271:
    "Unknown, stale, contradictory, or incompletely resolved effective-control state is denial for
    authority increase" — so an unresolved edge is **conservatively merged exactly like a resolved
    one** (fail-closed: unknown control ⇒ merge ⇒ distinct-count reduction ⇒ quorum harder). The
    collapse **never** gates the merge on ``resolved is True``; that would be a fail-open letting
    an unresolved control edge escape merging and inflate the distinct count (§4.1 / property 13).
    """

    source: str | None = None
    target: str | None = None
    #: Optional control-relation token (reset / impersonate / mint-credential / approve-as /
    #: change-role); descriptive, never a permission.
    relation: str | None = None
    #: Per-edge completeness provenance (design #20 §2.4/§4.1). **Decorative for the collapse
    #: outcome**: every listed edge merges its endpoints regardless of this value (fail-closed —
    #: the collapse never requires ``resolved is True`` to merge, and an unresolved edge is merged
    #: exactly like a resolved one). It records *why* an edge is present (confirmed vs unproven) for
    #: the fine-grained 2-layer story alongside the graph-level ``unresolved_control``; the only way
    #: NOT to merge two coordinates is the absence of any edge between them.
    resolved: bool | None = None


class ApprovalScope(FrozenModel):
    """The 7-dimension human approval scope (ADR-002-015 §10/§17; design #20 §2.4).

    A frozen 7-tuple of scope dimensions carried by a :class:`~tos.hag.records.HumanApprovalRequest`
    / :class:`~tos.hag.records.HumanHaltCommand` / :class:`~tos.hag.records.HumanDelegationRecord`
    and compared for narrowing by :func:`~tos.hag.predicates.partial_rearm_scope_narrows`
    (new ⊆ prior on **every** dimension, §17 line 457). Isomorphic to the liveauth
    ``LiveAuthorizationScope`` 7-frozenset — a **different axis** (human approval scope, not Live
    Authorization scope), authored locally-fresh (no liveauth import, sibling edge 0; design #20
    §2.4). Each dimension is an injected opaque token set; a ``None`` dimension is **unknown** and
    fails closed at the consuming predicate (never a permissive default, §8), while an **empty**
    (but non-``None``) dimension is a legitimate ``∅`` that narrows to nothing (a lawful
    de-authorization — the ``∅ ⊆ prior`` both-ways guard, §4.7).
    """

    instruments: frozenset[str] | None = None
    accounts: frozenset[str] | None = None
    venues: frozenset[str] | None = None
    environments: frozenset[str] | None = None
    action_classes: frozenset[str] | None = None
    sides: frozenset[str] | None = None
    routes: frozenset[str] | None = None

    #: The 7 scope-dimension field names iterated by the narrowing / exact-scope predicates.
    DIMENSIONS: ClassVar[tuple[str, ...]] = (
        "instruments",
        "accounts",
        "venues",
        "environments",
        "action_classes",
        "sides",
        "routes",
    )


class RoleGrant(FrozenModel):
    """One (principal, role) grant for separation-of-duties evaluation (ADR-002-015 §12).

    Binds an opaque effective-principal coordinate to one :class:`~tos.hag.vocabulary.ConflictRole`.
    Consumed by :func:`~tos.hag.predicates.separation_of_duties_satisfied`, which collapses the
    principal to its effective natural person **before** checking any forbidden pair (§12 line 358
    "automation cannot count as a human principal"; the effective-principal collapse §5.1). A
    ``None`` ``principal_id`` / ``role`` fails closed at the predicate.
    """

    principal_id: str | None = None
    role: ConflictRole | None = None


class RoleAssignment(FrozenModel):
    """The set of (principal, role) grants under separation-of-duties evaluation (ADR-002-015 §12).

    The roster slice :func:`~tos.hag.predicates.separation_of_duties_satisfied` evaluates. An
    **empty** ``grants`` holds no forbidden pair (no one has authority — the availability side is
    satisfied vacuously), but the graph-completeness gate still applies (a ``None`` / unresolved
    graph denies, §5.1 (vii) / MAJOR-2). The real identity / roster mechanism is +Security
    (HAG-EV-003 is predicate-only, ≥ EV-L2; §6.1).
    """

    grants: tuple[RoleGrant, ...] = ()


class QuorumRule(FrozenModel):
    """One policy-declared quorum for an approval type (ADR-002-015 §9; design #20 §2.4/§8).

    Binds an :class:`~tos.hag.vocabulary.AuthorityClass` approval type to its injected quorum
    ``quorum_n`` (policy content, null in Phase 1 — the numeric value is Verification-Profile
    injected, §8). A ``None`` ``quorum_n`` is unknown and fails closed at
    :func:`~tos.hag.predicates.quorum_independence_satisfied` (never a permissive default, §8); a
    degenerate ``quorum_n`` of ``0`` is denial (no authority increase without a human, §4.1).
    """

    approval_type: AuthorityClass | None = None
    quorum_n: int | None = None


class AttestationInputs(FrozenModel):
    """The injected review inputs an attestation binds (ADR-002-015 §10 line 312; design #20 §2.4).

    The independent-review context a :class:`~tos.hag.records.HumanApprovalAttestation` carries:
    the reviewed-inputs digest, the independent recompute result, and the authenticator session
    context (all injected — actual authentication is +Security runtime, §3.5). A value model with
    no id and no mutate method; the actual authenticator / recompute engine is not modelled here
    (Phase-0 / +Security, §9.2).
    """

    reviewed_inputs_digest: str | None = None
    independent_recompute_result: bool | None = None
    authenticator_session_context: str | None = None


def generation_monotone(earlier: OrderingEvent, later: OrderingEvent) -> bool:
    """Whether ``earlier`` strictly precedes ``later`` in append-only order (§3.2 / §4.5).

    REUSES ``tos.ordering.compare_order`` (no re-authored order) to check the monotonic order of
    approval-lifecycle / graph / roster / policy / restrictive-HALT generations (§8/§9/§13/§15).
    ``True`` **only** when the order is unambiguously ``BEFORE``; an ``AMBIGUOUS`` / ``AFTER`` pair
    fails closed. hag owns the fence *meaning* (invalidation / supersession, §4.5); ordering only
    carries the order. A wall clock never orders — hag reads no clock (§8).

    Args:
        earlier: The earlier ordering event.
        later: The later ordering event.

    Returns:
        ``True`` iff ``earlier`` provably precedes ``later``.
    """
    return compare_order(earlier, later) is Ordering.BEFORE
