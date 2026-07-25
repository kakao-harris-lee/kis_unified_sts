"""Protective-decision vocabulary — the local StrEnums (design #11 §2.2).

Spec terms = code terms (design #11 §2; boundary design #1 §2.4). The enum values / order
are authored **verbatim** from ADR-002-001 (§3.1.4 guarantee levels, §3.1.6 protective
ownership, §4.6 protective resource domains, §8.5 de-restriction, §6.1/§6.2 classification),
with the ADR line anchors recorded on each block (the erratum-defect-class seal, design #11
§2.2). :class:`Admissibility` / :class:`ProtectiveActionOutcome` / :class:`ProtectiveAction
Kind` are the **local** decision-result / discriminator tokens (design #11 §2.2-(4)/-(6)).

These are the **protective-decision** axis; they are a distinct coordinate system from the
rcl ``CapacityState`` (capacity-consumption axis, e.g. ``TRAPPED_CONSUMED``), the authority
``AuthorityState`` (system-mode axis, e.g. ``DEGRADED_PROTECTIVE``), the orthostate
``KnowledgeState`` (per-action aggregate) and the recon ``FieldConfidenceClass`` (per-field
evidence). The near-collision token ``TRAPPED`` is intentional (ADR uses the word on the
capacity axis too), so coordinate non-collapse rests on **distinct types + non-import**
(design #11 §4.4): protective imports none of those sibling axes, so a value from one can
never be coerced onto another.

This module names **no** concrete broker (broker-agnostic — project memory
``tos-spec-broker-agnostic``; design #11 §0.1). Which resource domains / guarantee levels a
concrete broker exhibits belongs to a non-normative Broker Capability / Safety Profile
INSTANCE (ADR §4.6 "at least"; §21), not here.

Pure module: stdlib only; no ``shared.*`` (design #11 §0.3).
"""

from __future__ import annotations

from enum import StrEnum


class GuaranteeLevel(StrEnum):
    """The 5 per-resource guarantee levels (ADR-002-001 §3.1.4 line 142 verbatim).

    Verbatim from ADR §3.1.4::

        PHYSICALLY_RESERVED    failure-independent partition; ordinary traffic cannot consume
        LOGICALLY_RESERVED     shares a lower-level dependency; common-mode analysis required
        PRIORITIZED_ONLY       deprioritized but may already occupy / exhaust — NOT guaranteed
        BEST_EFFORT            residual risk
        UNAVAILABLE            the most-restrictive level

    §3.1.4 line 144 verbatim: "A prioritized resource is not a reserved resource." §4.6 line
    217 verbatim: "A resource SHALL NOT be described as **guaranteed** unless its reservation
    mechanism and failure independence have been demonstrated. **Priority is not
    reservation.**" So :func:`~tos.protective.predicates.guarantee_level_resolved` treats an
    **unassigned** domain as ``UNAVAILABLE`` (the lowest), and there is **no** path that
    promotes ``PRIORITIZED_ONLY`` / ``BEST_EFFORT`` to reserved (design #11 §4.2 — PRD-EV-002
    substrate). This is the guarantee axis, **not** rcl ``CapacityState`` — coordinate
    non-collapse (design #11 §4.4).
    """

    PHYSICALLY_RESERVED = "PHYSICALLY_RESERVED"
    LOGICALLY_RESERVED = "LOGICALLY_RESERVED"
    PRIORITIZED_ONLY = "PRIORITIZED_ONLY"
    BEST_EFFORT = "BEST_EFFORT"
    UNAVAILABLE = "UNAVAILABLE"


class ProtectiveOwnership(StrEnum):
    """The 4 protective-order ownership classes (ADR-002-001 §3.1.6 line 152 verbatim).

    Verbatim from ADR §3.1.6::

        STRATEGY_OWNED
        EXECUTION_OWNED
        SAFETY_OWNED
        OPERATOR_OWNED

    §11.1 line 473-479: a ``SAFETY_OWNED`` order SHALL NOT be cancelled by strategy or
    ordinary execution cleanup; it may be cancelled only under the three §11.1 conditions
    realized by :func:`~tos.protective.predicates.cancellation_admissible` (design #11 §6.3).
    """

    STRATEGY_OWNED = "STRATEGY_OWNED"
    EXECUTION_OWNED = "EXECUTION_OWNED"
    SAFETY_OWNED = "SAFETY_OWNED"
    OPERATOR_OWNED = "OPERATOR_OWNED"


class ProtectiveResourceDomain(StrEnum):
    """The 7 protective resource domains (ADR-002-001 §4.6 line 205-213 verbatim).

    ADR §4.6 line 205: "Reserved Protective Capacity SHALL be evaluated separately for **at
    least**" these seven domains (verbatim gloss beside each token). "at least" => the
    required set is the **minimum** 7-domain floor and is injection-extensible per broker /
    venue (PRD-EV-001's ``+Broker`` slice); a domain **not** enumerated is treated as
    ``UNAVAILABLE`` (design #11 §4.1 — PRD-EV-001 substrate, the ADR line 158 "SHALL be
    defined across all resources whose exhaustion could prevent containment").
    """

    #: ADR §4.6 "execution workers and request queues".
    EXECUTION_WORKERS_AND_QUEUES = "EXECUTION_WORKERS_AND_QUEUES"
    #: ADR §4.6 "broker/API request rate, broker session availability, and order-message rate".
    BROKER_API_RATE_SESSION_AND_ORDER_RATE = "BROKER_API_RATE_SESSION_AND_ORDER_RATE"
    #: ADR §4.6 "aggregate risk capacity, margin, collateral, and protective retry budget".
    AGGREGATE_RISK_MARGIN_COLLATERAL_RETRY = "AGGREGATE_RISK_MARGIN_COLLATERAL_RETRY"
    #: ADR §4.6 "network and control path".
    NETWORK_AND_CONTROL_PATH = "NETWORK_AND_CONTROL_PATH"
    #: ADR §4.6 "reconciliation and evidence-persistence capacity".
    RECONCILIATION_AND_EVIDENCE_PERSISTENCE = "RECONCILIATION_AND_EVIDENCE_PERSISTENCE"
    #: ADR §4.6 "operator emergency path".
    OPERATOR_EMERGENCY_PATH = "OPERATOR_EMERGENCY_PATH"
    #: ADR §4.6 "trustworthy-time and protective-authorization capability".
    TRUSTWORTHY_TIME_AND_PROTECTIVE_AUTHZ = "TRUSTWORTHY_TIME_AND_PROTECTIVE_AUTHZ"


#: The minimum required protective-resource-domain floor (ADR §4.6 "at least"). An injected
#: required set that is ``None`` / empty is treated as this 7-domain floor — the most
#: restrictive interpretation, never a vacuous pass (design #11 §4.1 / §5.1; the brokercap
#: empty-required fail-closed lesson). Broker/venue-specific domains only **widen** the
#: required set (the ``+Broker`` slice), never shrink it below this floor.
REQUIRED_PROTECTIVE_DOMAINS: frozenset[ProtectiveResourceDomain] = frozenset(
    ProtectiveResourceDomain
)


class Admissibility(StrEnum):
    """The local 3-token admissibility verdict (design #11 §2.2-(4)).

    The §9 / §11 / §13 predicate results::

        ADMISSIBLE   overlap-first / add-only within a pre-proven scope, or a cancellation
                     condition is met — the action may proceed
        TRAPPED      cancel-first outside scope / past staleness — SHALL NOT transmit; the
                     exposure is conservatively covered and trapped (ADR §9 line 448 / §15)
        PROHIBITED   unprovable / undeclared / unassigned / ``None`` — the action is prohibited

    There is deliberately **no** "assume-admissible" construction path anywhere: a predicate
    returns ``ADMISSIBLE`` only from positive proof, everything else is restrictive (design
    #11 §4.1 — the structural seal against the #6 fail-open REJECT lesson). ``TRAPPED`` is an
    **admissibility** verdict, distinct from the rcl ``CapacityState.TRAPPED_CONSUMED``
    **capacity state** (design #11 §3.5 / §4.4 — protective does not re-author the capacity
    state, only the admissibility judgment).
    """

    ADMISSIBLE = "ADMISSIBLE"
    TRAPPED = "TRAPPED"
    PROHIBITED = "PROHIBITED"


class ProtectiveActionOutcome(StrEnum):
    """The local classification outcome (design #11 §2.2-(6); ADR §6.1/§6.2).

    The §6.1 final-state / §6.2 intermediate-state test result::

        PROTECTIVE_PROVEN        final < current ∧ worst-intermediate <= no-action ∧ no
                                 exceedance increase ∧ credible state space bounded
        RISK_INCREASING_DENIED   §6.2 line 279 "classified as risk increasing and denied in
                                 degraded mode" — could not be proven protective
        UNKNOWN_CONSERVATIVE     §6.2 line 277 credible-state-space unbounded => conservatively
                                 UNKNOWN, never silently excluded

    §6 line 247-249 verbatim: "Only the Protective Action Controller may classify an action as
    protective using conservative aggregate-risk analysis. A strategy flag, sell direction,
    exit or hedge name, reduce-position intent, operator description, or correlation with an
    existing position is **non-authoritative**." So the classifier reads only injected
    conservative aggregate-risk comparisons — never a strategy label (design #11 §4.3).
    """

    PROTECTIVE_PROVEN = "PROTECTIVE_PROVEN"
    RISK_INCREASING_DENIED = "RISK_INCREASING_DENIED"
    UNKNOWN_CONSERVATIVE = "UNKNOWN_CONSERVATIVE"


class DegradedModeTransition(StrEnum):
    """The one governed de-restriction transition marker (ADR-002-001 §8.5 line 381 verbatim).

    §8.5 line 381 verbatim: "The only de-restriction this ADR governs is ``CONTAINED`` ->
    ``DEGRADED_PROTECTIVE``". The mode values themselves (``CONTAINED`` / ``DEGRADED_
    PROTECTIVE``) are owned by authority ``AuthorityState`` (design #11 §3.5); protective
    authors only this transition **direction marker** plus the fail-closed
    :func:`~tos.protective.predicates.derestriction_admissible` guard — it does **not**
    re-declare the mode enum (authority-duplication is structurally excluded, §0.4e).
    """

    CONTAINED_TO_DEGRADED_PROTECTIVE = "CONTAINED_TO_DEGRADED_PROTECTIVE"


class ProtectiveActionKind(StrEnum):
    """The local protective-action-kind discriminator (design #11 §6.2 / §6.5 signatures).

    A local discriminator the design's §6.2 / §6.5 predicate signatures type as
    ``ProtectiveActionKind`` without enumerating members in the §2.2 ADR-verbatim block; the
    members below realize the ADR §9 (overlap-first vs cancel-first) and §10 (new-order vs
    cancellation) protective-action distinctions the two predicates branch on:

    * ``OVERLAP_FIRST_ADD_ONLY`` — establish new protection without removing existing (ADR §9
      line 448 "overlap-first / add-only"); the only partition-lease ``ADMISSIBLE`` shape.
    * ``CANCEL_FIRST_OR_REMOVAL`` — cancel-first, or remove / weaken existing protection (ADR
      §9 line 448); cannot proceed on stale admissibility during a partition => trapped.
    * ``NEW_PROTECTIVE_ORDER`` — a new protective order under untrusted time (ADR §10 line
      459); admissible only under a non-time-dependent emergency rule.
    * ``CANCELLATION_OF_RISK_INCREASING`` — cancellation of a confirmed risk-increasing order
      under untrusted time (ADR §10 line 460); MAY be admissible when not risk-increasing.

    (See the final-report deviation note: this discriminator is a design-signature-implied
    local enum, not an ADR §2.2-verbatim token.)
    """

    OVERLAP_FIRST_ADD_ONLY = "OVERLAP_FIRST_ADD_ONLY"
    CANCEL_FIRST_OR_REMOVAL = "CANCEL_FIRST_OR_REMOVAL"
    NEW_PROTECTIVE_ORDER = "NEW_PROTECTIVE_ORDER"
    CANCELLATION_OF_RISK_INCREASING = "CANCELLATION_OF_RISK_INCREASING"
