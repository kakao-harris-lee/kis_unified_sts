"""Safety-deviation vocabulary — the WDR StrEnums (design #26 §2.2).

Spec terms = code terms (design #26 §2.2; boundary design #1 §2.4). The enums are authored
**verbatim** from ADR-002-026 (§5.3 decision result, §8 line 252 non-waivable classification, §21
request / active-deviation state, §19 line 484-490 verification-item status, §5.7 line 128 scope
catalogue, §5.5/§11 compensating-control kind).

**Truthy-sentinel structural seal (design #26 §2.2/§4.2 — #13/#14 M1 adopted from the start).**
``DecisionResult`` (DENY / HOLD / ELIGIBLE_FOR_RESTRICTED_CONFIGURATION), ``NonWaivableClassification``
(NON_WAIVABLE / WAIVABLE_ELIGIBLE / UNRESOLVED), ``RequestState`` (the 10-state flow),
``ActiveDeviationState`` (the 7-state machine), and ``WaivedEvidenceStatus`` (the §19 status set) are
non-empty ``StrEnum`` strings, so ``if result:`` / ``bool(state)`` would read a **denial /
non-permissive / terminal** member (``DENY`` / ``HOLD`` / ``NON_WAIVABLE`` / ``UNRESOLVED`` /
``REVOKED`` / ``EXPIRED`` / ``FAIL``) as **truthy** — a catastrophic silent fail-open that reads a
*rejection* / *terminal* state as a *go* (ADR §5.3 "an immutable independent result of ``DENY``,
``HOLD``"; §8 line 252 "unresolved ... treated as non-waivable"). Each subclasses
:class:`_NonTruthyStrEnum`, whose :meth:`~_NonTruthyStrEnum.__bool__` **raises** ``TypeError``, making
them *truthy-untestable*. The mandated consume gates are the explicit positive-identity comparison
(``result is DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`` / ``classification is
NonWaivableClassification.WAIVABLE_ELIGIBLE``) — everything else is denial. Isomorphic to the iap
``ApprovalResult`` seal, the cur ``ProofResult`` seal, and the rlp ``PlanResult`` seal; authored
**locally-fresh** here (sibling edge 0 — no iap / cur / rlp import, design #26 §3.3).

``WaivedEvidenceStatus.PASS`` is a member (an honestly measured PASS), but the ``evidence_status_honest``
predicate (§5.4) forbids **relabeling** a covered item to ``PASS`` merely because a deviation exists
(§19 line 490). The enum stays truthy-untestable so a bare ``if status:`` never mistakes a ``FAIL`` for
a go.

``ScopeDimension`` and ``CompensatingControlKind`` are **plain, closed** ``StrEnum``s (ADR §5.7 line
128 scope catalogue / §5.5-§11 control kinds): structural identifier tokens consumed by set membership
/ subset checks, never gate results read with ``if key:``, so they do not need the truthy seal. Each is
a **structural identifier**, never a threshold / bound — hardcoding it is **not** a numeric hardcode
(design #26 §2.2/§8; the rlp ``ScopeDimension`` / cur ``DimensionKey`` field-enumeration precedent).
``ScopeDimension`` is a **manually-transcribed regression anchor** (design #26 §0.4h): the §7.2
anchor-drift property asserts the enum equals the ADR §5.7 line 128 21-dimension reference set so a
drift is caught immediately.

This module names **no** concrete broker (broker-agnostic — project memory ``tos-spec-broker-
agnostic``; design #26 §0.2) and hardcodes **no** numeric floor / size / duration / threshold (ADR §8):
every bound is an injected Profile-INSTANCE value (design #26 §8). An enum member is a structural
label, never a limit or a permission.

Pure module: stdlib only; no ``shared.*``, no sibling ``tos.*`` (design #26 §0.3).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "DecisionResult",
    "NonWaivableClassification",
    "RequestState",
    "ActiveDeviationState",
    "WaivedEvidenceStatus",
    "ScopeDimension",
    "CompensatingControlKind",
    "MANDATED_SCOPE_FLOOR",
    "MEASURED_FAILURE_STATUSES",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #26 §2.2/§4.2).

    Every member is a non-empty string, so a bare ``if result:`` / ``bool(state)`` would read a denial
    / non-permissive / terminal member (``DENY`` / ``HOLD`` / ``NON_WAIVABLE`` / ``UNRESOLVED`` /
    ``REVOKED`` / ``EXPIRED`` / ``FAIL``) as truthy — a catastrophic silent fail-open that reads a
    rejection or a terminal state as a go. :meth:`__bool__` therefore raises ``TypeError`` on every
    member, so the misuse surfaces as a loud runtime error rather than a silent pass. Consumers MUST use
    the explicit positive-identity gate (``x is ENUM.SAFE_VALUE``). Isomorphic to the iap
    ``ApprovalResult`` / cur ``ProofResult`` / rlp ``PlanResult`` seals; authored **locally-fresh** here
    (sibling edge 0, no iap / cur / rlp import — design #26 §3.3). ``is`` identity, ``.value``, hashing,
    set membership, and ``model_dump`` are all unaffected (none calls ``__bool__``).
    """

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #26 §2.2/§4.2).

        Raises:
            TypeError: always — the enum is not truthy-testable. Use the explicit positive
                identity gate (e.g. ``result is
                DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION``); a bare ``if result:`` /
                ``bool(result)`` would fail open on the truthy denial / non-permissive strings.
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. `result is "
            "DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`; `classification is "
            "NonWaivableClassification.WAIVABLE_ELIGIBLE`) per the truthy-sentinel seal (design "
            "#26 §2.2/§4.2). The denial / non-permissive members are non-empty strings and a bare "
            "`if result:` would fail open — reading a rejection or a terminal state as a go."
        )


class DecisionResult(_NonTruthyStrEnum):
    """The Safety Deviation Decision result (ADR-002-026 §5.3 line 110-112, non-truthy — critical seal).

    §5.3 verbatim: "An immutable independent result of ``DENY``, ``HOLD``, or
    ``ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`` for one exact request digest." §12 line 356 "An
    ``ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`` decision SHALL bind ... one allowed configuration-request
    consumption." **Truthy-untestable** (``__bool__`` raises): ``DENY`` / ``HOLD`` are non-empty
    strings, so ``if result:`` would read a *denial* as an *eligibility* — the catastrophic fail-open
    this seal blocks. The mandated consume gate is
    ``result is DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION``; every other value is denial.
    ``ELIGIBLE_FOR_RESTRICTED_CONFIGURATION`` itself grants **no** authority (§1 line 25 "It does not
    activate configuration or satisfy the affected requirement"; all-false
    :class:`~tos.wdr._base.AllFalseDeviationAuthority`, §6.3) — it is only eligibility to *request* one
    configuration consumption.
    """

    DENY = "DENY"
    HOLD = "HOLD"
    ELIGIBLE_FOR_RESTRICTED_CONFIGURATION = "ELIGIBLE_FOR_RESTRICTED_CONFIGURATION"


class NonWaivableClassification(_NonTruthyStrEnum):
    """The non-waivable classification of a requirement (ADR-002-026 §8 line 252, non-truthy).

    §8 line 252 verbatim: "If requirement identity or applicability is unresolved, it is treated as
    **non-waivable** until positively classified otherwise by the current policy and independent
    review." So ``UNRESOLVED`` and ``NON_WAIVABLE`` both converge to deny. **Truthy-untestable**
    (``__bool__`` raises): ``NON_WAIVABLE`` / ``UNRESOLVED`` are non-empty strings ⇒ ``if
    classification:`` would read a denial as a "go" — a fail-open. The mandated consume gate is
    ``classification is NonWaivableClassification.WAIVABLE_ELIGIBLE``; every other value is denial
    (§5.1).
    """

    NON_WAIVABLE = "NON_WAIVABLE"
    WAIVABLE_ELIGIBLE = "WAIVABLE_ELIGIBLE"
    UNRESOLVED = "UNRESOLVED"


class RequestState(_NonTruthyStrEnum):
    """The Safety Deviation Request lifecycle state (ADR-002-026 §21 line 518-524, non-truthy — 10-state).

    §21 line 518-524 verbatim flow: ``DRAFT -> SUBMITTED -> UNDER_REVIEW -> DENIED | HOLD |
    ELIGIBLE_FOR_RESTRICTED_CONFIGURATION -> CONSUMED | SUPERSEDED | REVOKED | EXPIRED``.
    **Truthy-untestable** (``__bool__`` raises): a non-permissive / terminal state is a non-empty string
    so ``if state:`` would read ``DENIED`` / ``REVOKED`` / ``EXPIRED`` as a truthy "go" — a fail-open.
    No state grants authority (§6.2 all-false); the state is a lifecycle marker, not a permit.
    """

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    DENIED = "DENIED"
    HOLD = "HOLD"
    ELIGIBLE_FOR_RESTRICTED_CONFIGURATION = "ELIGIBLE_FOR_RESTRICTED_CONFIGURATION"
    CONSUMED = "CONSUMED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class ActiveDeviationState(_NonTruthyStrEnum):
    """The Active Deviation applicability state (ADR-002-026 §21 line 528-534, non-truthy — 7-state).

    §21 line 528-534 verbatim: ``NOT_ACTIVE -> CONFIGURATION_STAGED -> ACTIVE_RESTRICTED ->
    RESTRICTION_PENDING -> REVOKED | EXPIRED | SUPERSEDED``. §21 line 536 "Only ADR-002-014 activation
    may move ``CONFIGURATION_STAGED`` to ``ACTIVE_RESTRICTED``, and that state still creates **no live
    authority**"; line 538 "No transition from ``REVOKED``, ``EXPIRED``, or ``SUPERSEDED`` returns to
    ``ACTIVE_RESTRICTED``." **Truthy-untestable** (``__bool__`` raises): a terminal / non-permissive
    state is a non-empty string ⇒ ``if state:`` is a fail-open. Even ``ACTIVE_RESTRICTED`` is all-false
    authority (§6.2); activation transitions are spg / ADR-002-014 injected (§0.4c).
    """

    NOT_ACTIVE = "NOT_ACTIVE"
    CONFIGURATION_STAGED = "CONFIGURATION_STAGED"
    ACTIVE_RESTRICTED = "ACTIVE_RESTRICTED"
    RESTRICTION_PENDING = "RESTRICTION_PENDING"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class WaivedEvidenceStatus(_NonTruthyStrEnum):
    """The verification-item status under a deviation (ADR-002-026 §19 line 484-490, non-truthy).

    §19 line 484-488 verbatim: "An evidence item covered by an allowed deviation SHALL remain one of:
    ``NOT_IMPLEMENTED`` ... ``FAIL``, ``INCONCLUSIVE``, ``BLOCKED``, or ``EXPIRED`` ...
    ``WAIVED_WITH_RESIDUAL_RISK`` **only** when RFC-001 explicitly permits it and the exact current
    decision, reduced scope, compensation, and review record exist." + line 490 "It SHALL NOT be
    relabeled ``PASS``, ``ACCEPTED``, or completed merely because a deviation exists." **Truthy-
    untestable** (``__bool__`` raises): ``FAIL`` / ``BLOCKED`` / ``EXPIRED`` are non-empty strings ⇒
    ``if status:`` is a fail-open. ``PASS`` is a member (an honestly measured PASS), but the deviation ⇒
    PASS **flip** is forbidden by :func:`~tos.wdr.predicates.evidence_status_honest` (§5.4). **This
    vocabulary is WDR-owned** — measured verification-status honesty is a different axis from evidence
    custody, and ``tos.evidence`` does not own this enum (design #26 §0.4d; seam conflict 0).
    """

    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"
    EXPIRED = "EXPIRED"
    WAIVED_WITH_RESIDUAL_RISK = "WAIVED_WITH_RESIDUAL_RISK"
    PASS = "PASS"


class ScopeDimension(StrEnum):
    """The Deviation Scope catalogue (ADR-002-026 §5.7 line 126-128, closed structural token — 21-dim).

    §5.7 line 126-128 enumerates the exact 21 scope dimensions one deviation decision applies to
    (environment / Safety Cell / Capacity Domain / legal portfolio / account / broker / venue /
    instrument / strategy / action class / software / configuration / identity / route / session /
    failure-domain / time / evidence / requirement / hazard / dependency closure). A **plain, closed**
    ``StrEnum`` structural identifier consumed by set membership / subset checks
    (:func:`~tos.wdr.predicates.scope_exact_and_complete`), never a gate result read with ``if key:``,
    so it is deliberately **not** truthy-sealed. It is a **structural dimension identifier**, never a
    numeric threshold / bound — enumerating it is **not** a numeric hardcode (design #26 §2.2/§8; the
    rlp ``ScopeDimension`` / cur ``DimensionKey`` field-enumeration precedent).

    Each member's lowercased name is the matching :class:`~tos.wdr.state.DeviationScope` field
    (``ENVIRONMENT`` <-> ``environment``), a correspondence the §7.2 anchor-drift property asserts so a
    scope field can never drift from the catalogue. This set is a **manually-transcribed regression
    anchor** of ADR §5.7 line 128 (design #26 §0.4h / appendix B) — not a derivation.
    """

    ENVIRONMENT = "ENVIRONMENT"
    SAFETY_CELL = "SAFETY_CELL"
    CAPACITY_DOMAIN = "CAPACITY_DOMAIN"
    LEGAL_PORTFOLIO = "LEGAL_PORTFOLIO"
    ACCOUNT = "ACCOUNT"
    BROKER = "BROKER"
    VENUE = "VENUE"
    INSTRUMENT = "INSTRUMENT"
    STRATEGY = "STRATEGY"
    ACTION_CLASS = "ACTION_CLASS"
    SOFTWARE = "SOFTWARE"
    CONFIGURATION = "CONFIGURATION"
    IDENTITY = "IDENTITY"
    ROUTE = "ROUTE"
    SESSION = "SESSION"
    FAILURE_DOMAIN = "FAILURE_DOMAIN"
    TIME_INTERVAL = "TIME_INTERVAL"
    EVIDENCE = "EVIDENCE"
    REQUIREMENT = "REQUIREMENT"
    HAZARD = "HAZARD"
    DEPENDENCY_CLOSURE = "DEPENDENCY_CLOSURE"


class CompensatingControlKind(StrEnum):
    """The compensating-control kind label (ADR-002-026 §5.5/§11, closed structural token).

    §5.5 verbatim: "An independently governed, enforceable **preventive or containment** mechanism ...
    A document, alert, dashboard, audit, replay, priority label, or operator promise is **not by
    itself** a compensating control." A **plain, closed** ``StrEnum`` structural label — the two
    qualifying kinds (``PREVENTIVE`` / ``CONTAINMENT``) plus the §5.5 non-qualifying observation kinds
    (``DOCUMENT`` / ``ALERT`` / ``DASHBOARD`` / ``AUDIT`` / ``REPLAY`` / ``PRIORITY_LABEL`` /
    ``OPERATOR_PROMISE`` / ``MONITORING``). It is a descriptive label only; the compensating-control
    *judgement* is carried by the polarity fields on
    :class:`~tos.wdr.state.CompensatingControl` (``is_preventive_or_containment`` /
    ``observation_only``) consumed by :func:`~tos.wdr.predicates.compensating_control_not_observation`
    (§6.1), never by this label — so this is **not** a drift-counted anchor, only a structural kind
    catalogue. Never a numeric bound (design #26 §8).
    """

    PREVENTIVE = "PREVENTIVE"
    CONTAINMENT = "CONTAINMENT"
    DOCUMENT = "DOCUMENT"
    ALERT = "ALERT"
    DASHBOARD = "DASHBOARD"
    AUDIT = "AUDIT"
    REPLAY = "REPLAY"
    PRIORITY_LABEL = "PRIORITY_LABEL"
    OPERATOR_PROMISE = "OPERATOR_PROMISE"
    MONITORING = "MONITORING"


#: The §5.7 mandated scope floor: **every** ``ScopeDimension`` member.
#: :func:`~tos.wdr.predicates.scope_exact_and_complete` floors its ``mandated_scope`` argument to at
#: least this set — a caller may require *more* but **never fewer** (design #26 §5.2; the cur
#: ``MANDATED_DIMENSION_FLOOR`` v1.1 MINOR-1 / rlp ``MANDATED_SCOPE_FLOOR`` precedent). Derived from the
#: enum so it can never drift below the catalogue (the §7.2 anchor-drift property asserts the derivation
#: equals the ADR §5.7 line 128 reference set).
MANDATED_SCOPE_FLOOR: frozenset[ScopeDimension] = frozenset(ScopeDimension)

#: The §19 line 484 measured-failure statuses whose visibility a deviation may never erase — a relabel
#: cannot move a measured item off one of these except to ``WAIVED_WITH_RESIDUAL_RISK`` under the
#: §19 line 488 exact-current gate (:func:`~tos.wdr.predicates.evidence_status_honest`; §5.4). A
#: manually-transcribed anchor of ADR §19 line 484-490 (design #26 §0.4h).
MEASURED_FAILURE_STATUSES: frozenset[WaivedEvidenceStatus] = frozenset(
    {
        WaivedEvidenceStatus.NOT_IMPLEMENTED,
        WaivedEvidenceStatus.FAIL,
        WaivedEvidenceStatus.INCONCLUSIVE,
        WaivedEvidenceStatus.BLOCKED,
        WaivedEvidenceStatus.EXPIRED,
    }
)
