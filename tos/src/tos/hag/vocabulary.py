"""Human-authority vocabulary — the HAG-axis StrEnums (design #20 §2.2).

Spec terms = code terms (design #20 §2; boundary design #1 §2.4). The enums are authored
**verbatim** from ADR-002-015 (§7 authority-class taxonomy, §12 role taxonomy, §18 attestation
decision + approval lifecycle state).

**Truthy-sentinel structural seal (design #20 §2.2(2)/§2.2(3)/§4.7 — #13/#14 M1 adopted from
the start).** ``AttestationDecision`` and ``ApprovalLifecycleState`` are non-empty ``StrEnum``
strings, so ``if decision:`` / ``bool(state)`` would read a **denial** member (``DENY`` /
``ABSTAIN``) or a **terminal** member (``EXPIRED`` / ``REVOKED`` / ``INVALIDATED`` / ``DENIED``
/ ``SUPERSEDED``) as **truthy** — a catastrophic silent fail-open that reads a rejection as an
approval (§10 line 314 "Silence, timeout, absence ... is not approval"). Both subclass
:class:`_NonTruthyStrEnum`, whose :meth:`~_NonTruthyStrEnum.__bool__` **raises** ``TypeError``,
making them *truthy-untestable*: the misuse surfaces as an immediate runtime error, never a
silent pass. The mandated consume gates are the explicit positive-identity comparison
(``decision is AttestationDecision.APPROVE`` / ``state is ApprovalLifecycleState.QUORUM_SATISFIED``)
— everything else is denial. Isomorphic to the iap ``_NonTruthyStrEnum`` seal
(``iap/vocabulary.py:50``); authored locally-fresh here (sibling edge 0 — no iap import).

``AuthorityClass`` / ``AuthorityDirection`` / ``ConflictRole`` are **plain, closed** ``StrEnum``s
(ADR §7 line 238-249 / §12 line 345-354 fixed taxonomies): they are input taxonomy tokens
consumed by identity / set membership (never read with ``if class:``), so they do not need the
truthy seal. ADR §7 line 249 verbatim: "Any action whose direction cannot be proven is authority
increasing" — so an unproven / ``None`` direction is treated as ``MAY_INCREASE``
(fail-closed default, §5.4).

This module names **no** concrete broker (broker-agnostic — project memory
``tos-spec-broker-agnostic``; design #20 §0.2/§21) and hardcodes **no** numeric quorum / age /
cooling / latency bound (ADR §4 non-scope): every bound is an injected policy-content value
(design #20 §8). An enum member is a structural label, never a limit or a permission.

Pure module: stdlib only; no ``shared.*``, no sibling ``tos.*`` (design #20 §0.3).
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType

__all__ = [
    "AuthorityClass",
    "AuthorityDirection",
    "AttestationDecision",
    "ApprovalLifecycleState",
    "ConflictRole",
    "AUTHORITY_DIRECTION",
    "BREAK_GLASS_RESTRICTIVE_CLASSES",
    "PROGRESS_LIFECYCLE_STATES",
    "TERMINAL_LIFECYCLE_STATES",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #20 §2.2/§4.7/M1).

    Every member is a non-empty string, so a bare ``if decision:`` / ``bool(state)`` would read
    a denial member (``DENY`` / ``ABSTAIN``) or a terminal member (``EXPIRED`` / ``REVOKED`` /
    ``DENIED`` / ``INVALIDATED`` / ``SUPERSEDED``) as truthy — a catastrophic silent fail-open
    that reads a rejection as an approval. :meth:`__bool__` therefore raises ``TypeError`` on
    every member, so the misuse surfaces as a loud runtime error rather than a silent pass.
    Consumers MUST use the explicit positive-identity gate (``x is ENUM.SAFE_VALUE``).
    Isomorphic to the iap ``_NonTruthyStrEnum`` seal (``iap/vocabulary.py:50``); authored
    locally-fresh here (sibling edge 0, no iap import — design #20 §0.4e). ``is`` identity,
    ``.value``, hashing, set membership, and ``model_dump`` are all unaffected (none calls
    ``__bool__``).
    """

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #20 §2.2/§4.7/M1).

        Raises:
            TypeError: always — the enum is not truthy-testable. Use the explicit positive
                identity gate (e.g. ``decision is AttestationDecision.APPROVE``;
                ``state is ApprovalLifecycleState.QUORUM_SATISFIED``); a bare ``if decision:`` /
                ``bool(decision)`` would fail open on the truthy denial / terminal strings.
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. `decision is AttestationDecision.APPROVE`; "
            "`state is ApprovalLifecycleState.QUORUM_SATISFIED`) per the truthy-sentinel seal "
            "(design #20 §2.2/§4.7/M1). The denial / terminal members are non-empty strings and "
            "a bare `if decision:` would fail open — reading DENY / ABSTAIN / EXPIRED / REVOKED "
            "as approval."
        )


class AuthorityClass(StrEnum):
    """The closed human-authority direction taxonomy (ADR-002-015 §7 line 238-249 verbatim).

    §7 enumerates the eight authority classes and their directions; the table is a **fixed,
    closed** taxonomy (a policy may not invent a new class), so a closed ``StrEnum`` is correct.
    A **plain** ``StrEnum``: it is an input taxonomy token consumed by identity / set membership
    (:func:`~tos.hag.predicates.break_glass_direction_restrictive`), never a gate result read
    with ``if class:``. The direction of each class is fixed by :data:`AUTHORITY_DIRECTION`; §7
    line 249 "Any action whose direction cannot be proven is authority increasing" means a
    ``None`` / unmapped class is treated as ``MAY_INCREASE`` (fail-closed, §5.4).
    """

    HALT = "HALT"
    NARROW = "NARROW"
    REQUEST_PROTECTIVE = "REQUEST_PROTECTIVE"
    APPROVE_PROFILE_OR_ENVELOPE = "APPROVE_PROFILE_OR_ENVELOPE"
    APPROVE_REARM = "APPROVE_REARM"
    ACCEPT_RESIDUAL_RISK = "ACCEPT_RESIDUAL_RISK"
    CAPACITY_MUTATION = "CAPACITY_MUTATION"
    TRANSMIT = "TRANSMIT"


class AuthorityDirection(StrEnum):
    """The direction axis of an authority class (ADR-002-015 §7 line 238-249 verbatim).

    Only ``STRICTLY_RESTRICTIVE`` (HALT), ``PROVEN_RESTRICTIVE`` (NARROW), and ``PROPOSAL_ONLY``
    (REQUEST_PROTECTIVE) are non-increasing; everything else increases authority. §7 line 249:
    "Any action whose direction cannot be proven is authority increasing" — an unproven direction
    is ``MAY_INCREASE`` (fail-closed default, §5.4).
    """

    STRICTLY_RESTRICTIVE = "STRICTLY_RESTRICTIVE"
    PROVEN_RESTRICTIVE = "PROVEN_RESTRICTIVE"
    PROPOSAL_ONLY = "PROPOSAL_ONLY"
    MAY_INCREASE = "MAY_INCREASE"
    ECONOMIC_AUTHORITY = "ECONOMIC_AUTHORITY"
    IRREVERSIBLE_BOUNDARY = "IRREVERSIBLE_BOUNDARY"


#: The fixed class -> direction map (ADR §7 line 238-249). A class absent here, or a ``None``
#: class, is treated as ``MAY_INCREASE`` (unproven direction is authority increasing, §7 line
#: 249 / §5.4).
AUTHORITY_DIRECTION: MappingProxyType[AuthorityClass, AuthorityDirection] = (
    MappingProxyType(
        {
            AuthorityClass.HALT: AuthorityDirection.STRICTLY_RESTRICTIVE,
            AuthorityClass.NARROW: AuthorityDirection.PROVEN_RESTRICTIVE,
            AuthorityClass.REQUEST_PROTECTIVE: AuthorityDirection.PROPOSAL_ONLY,
            AuthorityClass.APPROVE_PROFILE_OR_ENVELOPE: AuthorityDirection.MAY_INCREASE,
            AuthorityClass.APPROVE_REARM: AuthorityDirection.MAY_INCREASE,
            AuthorityClass.ACCEPT_RESIDUAL_RISK: AuthorityDirection.MAY_INCREASE,
            AuthorityClass.CAPACITY_MUTATION: AuthorityDirection.ECONOMIC_AUTHORITY,
            AuthorityClass.TRANSMIT: AuthorityDirection.IRREVERSIBLE_BOUNDARY,
        }
    )
)

#: The break-glass restrictive-only classes (§7 table / §16 line 425; HAG-INV-006). Only these
#: three may be exercised under break-glass — expand / transmit / re-arm / capacity are forbidden.
BREAK_GLASS_RESTRICTIVE_CLASSES: frozenset[AuthorityClass] = frozenset(
    {
        AuthorityClass.HALT,
        AuthorityClass.NARROW,
        AuthorityClass.REQUEST_PROTECTIVE,
    }
)


class AttestationDecision(_NonTruthyStrEnum):
    """A single human attestation decision (ADR-002-015 §18 line 523, non-truthy — critical seal).

    §18 line 523 verbatim: ``APPROVE`` / ``DENY`` / ``ABSTAIN``. **Truthy-untestable**
    (``__bool__`` raises): ``DENY`` / ``ABSTAIN`` are non-empty strings, so ``if decision:`` would
    read a *rejection* as *approval* — the catastrophic fail-open this seal blocks (§10 line 314
    "Silence, timeout, absence, emoji, chat acknowledgement ... is not approval"). The mandated
    consume gate is ``decision is AttestationDecision.APPROVE`` — every other value is denial.
    This is the **human** attestation axis, distinct from the iap automated ``ApprovalResult``
    (ADR §4 line 98 "an automated APPROVE cannot satisfy a human quorum"; §0.4e).
    """

    APPROVE = "APPROVE"
    DENY = "DENY"
    ABSTAIN = "ABSTAIN"


class ApprovalLifecycleState(_NonTruthyStrEnum):
    """The approval-set lifecycle state (ADR-002-015 §18 line 511-521, non-truthy).

    §18 line 511-518 progress states: ``REQUESTED`` -> ``REVIEWABLE`` -> ``ATTESTING`` ->
    ``QUORUM_SATISFIED`` -> ``CONSUMED``. Terminal / invalid states (no permissive exit):
    ``DENIED`` / ``EXPIRED`` / ``INVALIDATED`` / ``REVOKED`` / ``SUPERSEDED``. §18 line 521
    verbatim: "Only ``QUORUM_SATISFIED`` may become ``CONSUMED`` ... No terminal or invalid state
    returns to a permissive state." **Truthy-untestable** (``__bool__`` raises): a terminal member
    is a non-empty string, so ``if state:`` would read ``EXPIRED`` / ``REVOKED`` as live — a
    fail-open. The mandated gate is ``state is ApprovalLifecycleState.QUORUM_SATISFIED`` before a
    single-use consume (§5.3). The lifecycle *arrows* are judged by
    :func:`~tos.hag.predicates.lifecycle_transition_legal` (the record does not self-transition —
    the liveauth transition-record precedent).
    """

    REQUESTED = "REQUESTED"
    REVIEWABLE = "REVIEWABLE"
    ATTESTING = "ATTESTING"
    QUORUM_SATISFIED = "QUORUM_SATISFIED"
    CONSUMED = "CONSUMED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"
    REVOKED = "REVOKED"
    SUPERSEDED = "SUPERSEDED"


#: The progress (non-terminal) lifecycle states — a transition may still leave these.
PROGRESS_LIFECYCLE_STATES: frozenset[ApprovalLifecycleState] = frozenset(
    {
        ApprovalLifecycleState.REQUESTED,
        ApprovalLifecycleState.REVIEWABLE,
        ApprovalLifecycleState.ATTESTING,
        ApprovalLifecycleState.QUORUM_SATISFIED,
    }
)

#: The terminal / invalid lifecycle states — no permissive exit (§18 line 521). ``CONSUMED`` is a
#: terminal progress state (single-use spent), also with no permissive exit.
TERMINAL_LIFECYCLE_STATES: frozenset[ApprovalLifecycleState] = frozenset(
    {
        ApprovalLifecycleState.CONSUMED,
        ApprovalLifecycleState.DENIED,
        ApprovalLifecycleState.EXPIRED,
        ApprovalLifecycleState.INVALIDATED,
        ApprovalLifecycleState.REVOKED,
        ApprovalLifecycleState.SUPERSEDED,
    }
)


class ConflictRole(StrEnum):
    """The separation-of-duties role taxonomy (ADR-002-015 §12 line 345-354).

    The roles the §12 minimum forbidden-pair set (:data:`~tos.hag.predicates._FORBIDDEN_ROLE_PAIRS`)
    references. A **plain, closed** ``StrEnum`` input token compared by identity / set membership,
    never truthiness. §12 fixes the *minimum* forbidden pairs (a policy may add more, but the
    minimum cannot be waived). This is the **human** role-conflict axis — distinct from the
    authority capability-lease exclusivity (``authority.lease_scope_exclusive``; §3.5).
    """

    TRADING_PROPOSER = "TRADING_PROPOSER"
    TRADE_APPROVER = "TRADE_APPROVER"
    ENVELOPE_PROFILE_AUTHOR = "ENVELOPE_PROFILE_AUTHOR"
    LIMIT_APPROVER = "LIMIT_APPROVER"
    LIVE_ARMER = "LIVE_ARMER"
    EVIDENCE_PRODUCER = "EVIDENCE_PRODUCER"
    EVIDENCE_REVIEWER = "EVIDENCE_REVIEWER"
    RECOVERY_COORDINATOR = "RECOVERY_COORDINATOR"
    REARM_APPROVER = "REARM_APPROVER"
    POLICY_ADMIN = "POLICY_ADMIN"
    IDENTITY_ROSTER_ADMIN = "IDENTITY_ROSTER_ADMIN"
    CREDENTIAL_ROUTE_ADMIN = "CREDENTIAL_ROUTE_ADMIN"
    APPROVAL_SET_VERIFIER = "APPROVAL_SET_VERIFIER"
    DOWNSTREAM_ISSUER = "DOWNSTREAM_ISSUER"
    BREAK_GLASS_CUSTODIAN = "BREAK_GLASS_CUSTODIAN"
    BYPASS_APPROVER = "BYPASS_APPROVER"
