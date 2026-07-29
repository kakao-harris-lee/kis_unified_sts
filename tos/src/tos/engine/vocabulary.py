"""Closed engine vocabulary — event kinds, stage outcomes, and the 19-step flow (design #31 §2.2/§4).

Everything the event core and the Execution Coordinator sequencer dispatch on is a **closed
enumeration** here, inheriting the ``DecisionKind`` 4-member closure discipline of
:mod:`tos.dsl.vocabulary` (design #31 §2.2): an unknown member is not a silent drop, it is a
fail-closed error, and every progress gate is **positive membership**, never a negated denial.

Three seals live in this module:

1. **Truthy-sentinel seal** (#14 M1 / #19 / #23 precedent). Every verdict-shaped ``StrEnum``
   (:class:`StageOutcome`, :class:`EgressResultKind`, :class:`AdmissionVerdict`,
   :class:`OrderingAdmission`, :class:`DispatchResolution`) has non-empty string members, so
   ``if verdict:`` would read ``DENY`` / ``REJECT`` / ``INADMISSIBLE`` as *truthy* — a silent
   fail-open. ``__bool__`` therefore **raises**: the mandated gate is the explicit positive
   identity ``verdict is StageOutcome.ADMIT`` (design #31 §4.2 rule 1 / §6).
2. **19-step normative order** (:data:`COMMITMENT_FLOW_ORDER`) taken verbatim from ADR-002-002 §11
   (§11.1 steps 1-7, §11.2 steps 8-11, §11.3 steps 12-14, §11.4 steps 15-19). RFC-005 §7:192 —
   "SHALL NOT redefine, reorder, or abridge that sequence" — so the tuple order *is* the contract
   (design #31 §1.3/§4.1).
3. **No ``AUTHORITATIVE`` stage class.** :class:`StageAuthorityClass` has exactly the three sources
   design #31 §0.4/§4.1 sanctions; a provisional stand-in cannot label itself authoritative because
   the member does not exist (design #31 §4.4/§11 over-realization seal).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #31 §0.3).
"""

from __future__ import annotations

from enum import StrEnum

from tos.dsl import ADMISSIBLE_CONTEXT_SOURCES
from tos.engine._base import ArtifactIntegrityError

__all__ = [
    "ADMISSIBLE_EVENT_KINDS",
    "CAPSULE_CONTEXT_SOURCE",
    "COMMITMENT_FLOW_ORDER",
    "CONFIG_CONTEXT_SOURCE",
    "COORDINATOR_REALIZED_STEPS",
    "GUARANTEED_FAIL_CLOSED_STEPS",
    "INJECTED_STAGE_STEPS",
    "SEND_BOUNDARY_STEPS",
    "SEQUENCED_STEPS",
    "AdmissionVerdict",
    "CommitmentStep",
    "DispatchResolution",
    "EgressKnowledge",
    "EgressResultKind",
    "EventKind",
    "EvidenceKind",
    "HaltReason",
    "OrderingAdmission",
    "StageAuthorityClass",
    "StageOutcome",
    "step_number",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that refuses truthiness testing (truthy-sentinel seal, #14 M1 precedent).

    Every member is a non-empty string, so ``if value:`` / ``bool(value)`` would read a *denial*
    as a *pass*. Raising here makes that misuse an immediate ``TypeError`` instead of a silent
    fail-open; consumers must use an explicit positive-identity gate.
    """

    def __bool__(self) -> bool:
        """Reject truthiness outright.

        Raises:
            TypeError: always — use the explicit positive-identity gate instead.
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive-identity "
            "gate (e.g. `outcome is StageOutcome.ADMIT`); a bare `if value:` would read a denial "
            "as a pass (design #31 §4.2 rule 1 / §6)"
        )


# ===========================================================================
# §2.2 — the closed event vocabulary
# ===========================================================================


class EventKind(StrEnum):
    """The closed set of event kinds the single event core processes (design #31 §2.2).

    Slice #1 carries exactly two: a ``DECISION_TICK`` (an admitted Critical Input refresh that
    drives one decision-pipeline run for the bound instrument) and an ``EGRESS_RESULT`` (the
    typed result re-injected from the D-E4 send boundary, so the core can transition its
    provisional reservation projection — RFC-002 §10.7:719 "maintain potentially live order
    state"). Extension (cancel / reconciliation / corporate-action events) is an enum addition
    only; the dispatcher interface does not change (design #31 §2.2).
    """

    DECISION_TICK = "DECISION_TICK"
    EGRESS_RESULT = "EGRESS_RESULT"


#: The positive-membership admission set for the dispatcher (design #31 §2.2 "닫힘 규율").
#: The dispatcher advances **only** for a kind in this set; anything else is a fail-closed error,
#: never a silent drop.
ADMISSIBLE_EVENT_KINDS: frozenset[EventKind] = frozenset(
    {EventKind.DECISION_TICK, EventKind.EGRESS_RESULT}
)


class EgressResultKind(_NonTruthyStrEnum):
    """The typed results the D-E4 send boundary re-injects (design #31 §2.2).

    ``PARTIAL_FILL`` is first-class and is **never** collapsed into either a full fill or a
    rejection: a partial is represented as a partial and the already-filled quantity is never
    re-requested (RFC-005 §11:338-339, §6:176-178). ``UNKNOWN`` and ``TIMEOUT`` are neither a
    rejection nor safe-to-retry — they consume exposure at the worst-credible bound (RFC-005
    §11:325-327; ADR-002-002 INV-006:174), which is why they are distinct members rather than a
    missing value.
    """

    ACK = "ACK"
    FULL_FILL = "FULL_FILL"
    PARTIAL_FILL = "PARTIAL_FILL"
    REJECT = "REJECT"
    UNKNOWN = "UNKNOWN"
    TIMEOUT = "TIMEOUT"


#: The result kinds that carry fill magnitudes; every other kind must carry none (design #31 §2.2).
FILL_RESULT_KINDS: frozenset[EgressResultKind] = frozenset(
    {EgressResultKind.FULL_FILL, EgressResultKind.PARTIAL_FILL}
)


class EgressKnowledge(StrEnum):
    """Knowledge about the fate of a handed-off attempt — ``UNKNOWN`` is an explicit member.

    RFC-002 §12.1:1231 makes UNKNOWN a first-class orthogonal condition, so the engine's
    provisional projection carries it as a **named member**, never as a missing/null field
    (design #31 §2.4). This axis is orthogonal to the capacity projection
    (:class:`~tos.rcl.CapacityState`): a ``SENT_UNCONFIRMED`` / ``UNKNOWN`` knowledge state
    coexists with a conservatively-retained ``POTENTIALLY_LIVE`` capacity projection.
    """

    NOT_SENT = "NOT_SENT"
    SENT_UNCONFIRMED = "SENT_UNCONFIRMED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


# ===========================================================================
# §4 — the 19-step Normal Commitment Flow (ADR-002-002 §11, verbatim order)
# ===========================================================================


class CommitmentStep(StrEnum):
    """The 19 numbered steps of ADR-002-002 §11 Normal Commitment Flow (design #31 §1.3).

    Named after the ADR's own step text (§11.1:580-588 steps 1-7, §11.2:590-595 steps 8-11,
    §11.3:597-601 steps 12-14, §11.4:605-609 steps 15-19). RFC-005 §7:192 forbids redefining,
    reordering, or abridging the sequence, so :data:`COMMITMENT_FLOW_ORDER` is the contract and
    this enum is only its vocabulary.
    """

    # §11.1 Proposal and Approval
    DECISION_PROPOSAL = "DECISION_PROPOSAL"  # 1
    CANDIDATE_COMMAND_CONSTRUCTION = "CANDIDATE_COMMAND_CONSTRUCTION"  # 2
    VENUE_ADMISSIBILITY_DECISION = "VENUE_ADMISSIBILITY_DECISION"  # 3
    INDEPENDENT_APPROVAL = "INDEPENDENT_APPROVAL"  # 4
    ECONOMIC_EFFECT_ENVELOPE = "ECONOMIC_EFFECT_ENVELOPE"  # 5
    AGGREGATE_RISK_DECISION = "AGGREGATE_RISK_DECISION"  # 6
    ACTION_FLOW_DECISION = "ACTION_FLOW_DECISION"  # 7
    # §11.2 Atomic Commitment
    LEDGER_VERIFICATION = "LEDGER_VERIFICATION"  # 8
    ATOMIC_COMMIT = "ATOMIC_COMMIT"  # 9
    COMMITMENT_UNAVAILABILITY = "COMMITMENT_UNAVAILABILITY"  # 10
    ORDER_CONFORMANCE_PROOF = "ORDER_CONFORMANCE_PROOF"  # 11
    # §11.3 Attempt Binding
    ATTEMPT_REQUEST = "ATTEMPT_REQUEST"  # 12
    ATTEMPT_BIND_VERIFICATION = "ATTEMPT_BIND_VERIFICATION"  # 13
    TRANSMISSION_CAPABILITY = "TRANSMISSION_CAPABILITY"  # 14
    # §11.4 Send Boundary — D-E4 (never run by this sequencer, design #31 §4.5 item-7)
    SEND_BOUNDARY_VERIFICATION = "SEND_BOUNDARY_VERIFICATION"  # 15
    SEND_STARTED_DURABLE = "SEND_STARTED_DURABLE"  # 16
    POTENTIALLY_LIVE_TRANSITION = "POTENTIALLY_LIVE_TRANSITION"  # 17
    NETWORK_CALL = "NETWORK_CALL"  # 18
    EVIDENCE_RECORD = "EVIDENCE_RECORD"  # 19


#: The normative 19-step order (ADR-002-002 §11). Tuple order **is** the RFC-005 §7:192 contract.
COMMITMENT_FLOW_ORDER: tuple[CommitmentStep, ...] = (
    CommitmentStep.DECISION_PROPOSAL,
    CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION,
    CommitmentStep.VENUE_ADMISSIBILITY_DECISION,
    CommitmentStep.INDEPENDENT_APPROVAL,
    CommitmentStep.ECONOMIC_EFFECT_ENVELOPE,
    CommitmentStep.AGGREGATE_RISK_DECISION,
    CommitmentStep.ACTION_FLOW_DECISION,
    CommitmentStep.LEDGER_VERIFICATION,
    CommitmentStep.ATOMIC_COMMIT,
    CommitmentStep.COMMITMENT_UNAVAILABILITY,
    CommitmentStep.ORDER_CONFORMANCE_PROOF,
    CommitmentStep.ATTEMPT_REQUEST,
    CommitmentStep.ATTEMPT_BIND_VERIFICATION,
    CommitmentStep.TRANSMISSION_CAPABILITY,
    CommitmentStep.SEND_BOUNDARY_VERIFICATION,
    CommitmentStep.SEND_STARTED_DURABLE,
    CommitmentStep.POTENTIALLY_LIVE_TRANSITION,
    CommitmentStep.NETWORK_CALL,
    CommitmentStep.EVIDENCE_RECORD,
)

#: Steps 15-19 — the Send Boundary. **Constitutionally D-E4** (RFC-002 §10.8:741-759 verify list,
#: §9.1:567 currentness). The slice-1 sequencer does not run them and refuses to host a stage for
#: them, so D-E1 makes no claim about final-egress currentness / QCC / single-use capability
#: (design #31 §4.5 item-7 / §10.2-3).
SEND_BOUNDARY_STEPS: frozenset[CommitmentStep] = frozenset(
    COMMITMENT_FLOW_ORDER[COMMITMENT_FLOW_ORDER.index(
        CommitmentStep.SEND_BOUNDARY_VERIFICATION
    ):]
)

#: Steps 1-14 — the range the sequencer runs **and** the honest range of its fail-closed guarantee
#: (design #31 §4.5 item-7).
SEQUENCED_STEPS: tuple[CommitmentStep, ...] = tuple(
    step for step in COMMITMENT_FLOW_ORDER if step not in SEND_BOUNDARY_STEPS
)

#: Alias emphasising the guarantee scope (design #31 §4.5 item-7): fail-closed is proven for
#: steps 1-14 only.
GUARANTEED_FAIL_CLOSED_STEPS: frozenset[CommitmentStep] = frozenset(SEQUENCED_STEPS)

#: The two steps D-E1 realizes **directly** (design #31 §1.3 "정직 귀결"): step 1 (the Decision
#: Service proposal, produced by the decision pipeline) and step 12 (the Coordinator's unique
#: attempt request — its only direct action, ADR-002-002 §11.3:599). Neither is injectable.
COORDINATOR_REALIZED_STEPS: frozenset[CommitmentStep] = frozenset(
    {CommitmentStep.DECISION_PROPOSAL, CommitmentStep.ATTEMPT_REQUEST}
)

#: The steps the sequencer calls through an injected ``Stage`` (design #31 §4.1): everything in
#: steps 1-14 that the Coordinator does not realize itself.
INJECTED_STAGE_STEPS: tuple[CommitmentStep, ...] = tuple(
    step for step in SEQUENCED_STEPS if step not in COORDINATOR_REALIZED_STEPS
)


#: The ADR-002-002 §11 step numbers, derived structurally from :data:`COMMITMENT_FLOW_ORDER` (the
#: numbering is the ADR's own 1-based enumeration, never a re-assigned label).
_STEP_NUMBERS: dict[CommitmentStep, int] = {
    step: number for number, step in enumerate(COMMITMENT_FLOW_ORDER, start=1)
}


def step_number(step: CommitmentStep) -> int:
    """Return the ADR-002-002 §11 step number (1-19) of ``step``.

    Args:
        step: The commitment step.

    Returns:
        The 1-based normative step number.

    Raises:
        ArtifactIntegrityError: If ``step`` is not a member of the normative order — a step
            outside the closed 19 is not a step (fail-closed, design #31 §2.2/§4.1).
    """
    number = _STEP_NUMBERS.get(step)
    if number is None:
        raise ArtifactIntegrityError(
            f"{step!r} is not one of the 19 ADR-002-002 §11 Normal Commitment Flow steps"
        )
    return number


class StageOutcome(_NonTruthyStrEnum):
    """The positive-admit wrapping of a stage's native verdict (design #31 §4.1/§4.2).

    Only ``ADMIT`` advances the sequence. ``DENY`` is a definite denial; ``UNKNOWN`` is
    restrictive **and** special — it is neither a rejection nor safe-to-retry, and it consumes
    exposure at the worst-credible bound (RFC-005 §11:325-327; ADR-002-002 INV-006:174), so the
    consumer distinguishes it from ``DENY`` in the recorded halt reason. There is deliberately no
    "assume-admit" construction path and no negated gate: ``verdict is not DENY`` is forbidden
    because it fails open on ``None`` and on any future member (design #31 §4.2 rule 1 / §6).
    """

    ADMIT = "ADMIT"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


class StageAuthorityClass(StrEnum):
    """Where a stage's logic comes from — the three sanctioned sources (design #31 §0.4/§4.1).

    There is **no** ``AUTHORITATIVE`` member: in slice #1 no stage holds authority, and the
    absence of the member is the structural seal against a provisional stand-in being promoted
    to real authority (design #31 §4.4/§11 "provisional over-realization").
    """

    #: An already-shipped pure sibling predicate (ioc / venue / cur / rcl arithmetic).
    AVAILABLE_PURE_PREDICATE = "AVAILABLE_PURE_PREDICATE"
    #: A non-authoritative in-memory stand-in for a future owning runtime (approval / ARE / AFG /
    #: RCL atomic commit / Transmission Capability). Closes **no** capacity or approval EV.
    NON_AUTHORITATIVE_PROVISIONAL = "NON_AUTHORITATIVE_PROVISIONAL"
    #: The D-E4 send boundary — never hosted by this package (design #31 §4.5).
    DEFERRED_SEND_BOUNDARY = "DEFERRED_SEND_BOUNDARY"


# ===========================================================================
# §3 / §6 — dispatch, admission, ordering, and halt vocabulary
# ===========================================================================


class DispatchResolution(_NonTruthyStrEnum):
    """The ∅-both-ways registry resolution (design #31 §6 "∅ 양방향" / §11).

    ``MISSING`` (no registry entry for the instrument key at all) is **fail-closed**: nothing is
    evaluated. ``EXPLICIT_EMPTY`` (a key registered with zero strategies) is a **defined
    no-action**, not a failure. Collapsing the two — in either direction — is the #17/#26 ∅ defect
    class: over-rejecting an explicit empty is as wrong as vacuously admitting a missing one.
    """

    MISSING = "MISSING"
    EXPLICIT_EMPTY = "EXPLICIT_EMPTY"
    DISPATCHED = "DISPATCHED"


class AdmissionVerdict(_NonTruthyStrEnum):
    """The typed-admission verdict for an in-process Authored Strategy (design #31 §3.5)."""

    ADMISSIBLE = "ADMISSIBLE"
    INADMISSIBLE = "INADMISSIBLE"


class OrderingAdmission(_NonTruthyStrEnum):
    """Causal-order admission of an incoming event against the last consumed one (§2.1(ii)).

    ``REVERSED`` — :func:`~tos.ordering.compare_order` positively establishes that the incoming
    event precedes the last consumed one — is fail-closed. ``AMBIGUOUS`` (the ordering bases do
    not establish an order) is **recorded and admitted**, not rejected: rejecting it would be the
    #26 WDR MAJOR-1 over-rejection defect (an explicit "cannot order" is not a proven reversal),
    and the safety consequence it might carry is separately sealed by the at-most-one reservation
    retention (§4.4) and by the positive attempt-identity match on ``EGRESS_RESULT`` consumption.
    Full causal enforcement needs the ordering coordinates D-E2 / D-E4 supply (design #31 §9-7).
    """

    MONOTONE = "MONOTONE"
    AMBIGUOUS = "AMBIGUOUS"
    REVERSED = "REVERSED"


class HaltReason(StrEnum):
    """Why a decision-pipeline run or a commitment flow stopped (design #31 §4.2 "중단 사유 기록").

    A halt is always recorded with its reason: "restrictive termination without a recorded reason"
    is not a fail-closed stop, it is a silent one. ``DEGRADED_BOUND_EXHAUSTED`` is deliberately a
    **distinct** member from ``NO_ACTION_OUTCOME`` — a degradation is not an ordinary no-action
    (design #31 §3.4 "구별된 degradation 증거").
    """

    REGISTRY_MISSING = "REGISTRY_MISSING"
    REGISTRY_EXPLICIT_EMPTY = "REGISTRY_EXPLICIT_EMPTY"
    EVENT_STRATEGY_KEY_MISMATCH = "EVENT_STRATEGY_KEY_MISMATCH"
    CAPSULE_ABSENT = "CAPSULE_ABSENT"
    CAPSULE_NOT_ISSUED = "CAPSULE_NOT_ISSUED"
    CAPSULE_INCOMPLETE = "CAPSULE_INCOMPLETE"
    CAPSULE_SCOPE_MISMATCH = "CAPSULE_SCOPE_MISMATCH"
    TIME_NOT_ADMITTED = "TIME_NOT_ADMITTED"
    DEGRADED_BOUND_EXHAUSTED = "DEGRADED_BOUND_EXHAUSTED"
    NO_ACTION_OUTCOME = "NO_ACTION_OUTCOME"
    VECTOR_OUTCOME_UNSUPPORTED = "VECTOR_OUTCOME_UNSUPPORTED"
    PROPOSAL_SCOPE_MISMATCH = "PROPOSAL_SCOPE_MISMATCH"
    STAGE_MISSING = "STAGE_MISSING"
    STAGE_VERDICT_ABSENT = "STAGE_VERDICT_ABSENT"
    STAGE_VERDICT_STEP_MISMATCH = "STAGE_VERDICT_STEP_MISMATCH"
    STAGE_DENIED = "STAGE_DENIED"
    STAGE_UNKNOWN = "STAGE_UNKNOWN"
    STAGE_RAISED = "STAGE_RAISED"
    ATTEMPT_BINDING_INCOMPLETE = "ATTEMPT_BINDING_INCOMPLETE"
    AT_MOST_ONE_EXPOSURE_HELD = "AT_MOST_ONE_EXPOSURE_HELD"
    EVENT_ORDER_REVERSED = "EVENT_ORDER_REVERSED"
    RESERVATION_ABSENT_FOR_RESULT = "RESERVATION_ABSENT_FOR_RESULT"
    ATTEMPT_IDENTITY_MISMATCH = "ATTEMPT_IDENTITY_MISMATCH"
    TRANSMIT_UNAVAILABLE = "TRANSMIT_UNAVAILABLE"
    TRANSMIT_RAISED = "TRANSMIT_RAISED"


class EvidenceKind(StrEnum):
    """The kinds of record the provisional evidence sink receives (design #31 §12-5).

    ``DECISION_DEGRADED`` is separate from ``DECISION_WITHHELD`` and from
    ``DECISION_OUTCOME_EMITTED`` because a bounded-evaluation degradation has a *different cause*
    from an ordinary no-action and must stay distinguishable in evidence (design #31 §3.4/§7.2-3).
    """

    REGISTRATION_REFUSED = "REGISTRATION_REFUSED"
    EVENT_REFUSED = "EVENT_REFUSED"
    DECISION_WITHHELD = "DECISION_WITHHELD"
    DECISION_DEGRADED = "DECISION_DEGRADED"
    DECISION_OUTCOME_EMITTED = "DECISION_OUTCOME_EMITTED"
    FLOW_STEP_ADMITTED = "FLOW_STEP_ADMITTED"
    FLOW_HALTED = "FLOW_HALTED"
    ATTEMPT_REQUEST_CREATED = "ATTEMPT_REQUEST_CREATED"
    SEND_HANDED_OFF = "SEND_HANDED_OFF"
    EGRESS_RESULT_CONSUMED = "EGRESS_RESULT_CONSUMED"


# ===========================================================================
# §3.2 (3) — the two admissible Decision Context sources, named (D1 ↔ D4 coupling)
# ===========================================================================

#: The Critical-Input context source. Market-derived values flow **only** here, through an admitted
#: Critical Input observation carried by the Snapshot body (RFC-004 §9:242-244; RFC-003 §8:236-237;
#: RFC-008 §10:327-331 no-relabelling). Value-surface realization is D-E2 (design #31 §3.2).
CAPSULE_CONTEXT_SOURCE = "capsule"

#: The authored-constant context source: thresholds / periods the *author* chose. Carrying a
#: market-derived value here is the RFC-008 §10 relabelling prohibition (design #31 §3.2 (2)).
CONFIG_CONTEXT_SOURCE = "config"


def _verify_context_source_anchor() -> None:
    """Anchor the two named sources to ``tos.dsl.ADMISSIBLE_CONTEXT_SOURCES`` (enum-drift guard).

    The engine names ``"capsule"`` / ``"config"`` as literals because the DSL exports the *set*
    but not the individual member names. This module-import-time check makes the pair
    **exhaustive and exact** against the shipped DSL constant, so a future DSL source addition or
    rename cannot leave the engine silently reading a stale name (the #23 CUR enum-drift-anchor
    lesson).

    Raises:
        ArtifactIntegrityError: If the named pair is not exactly ``ADMISSIBLE_CONTEXT_SOURCES``.
    """
    named = frozenset({CAPSULE_CONTEXT_SOURCE, CONFIG_CONTEXT_SOURCE})
    if named != ADMISSIBLE_CONTEXT_SOURCES:
        raise ArtifactIntegrityError(
            "engine context-source anchor drifted from tos.dsl.ADMISSIBLE_CONTEXT_SOURCES "
            f"(engine={sorted(named)}, dsl={sorted(ADMISSIBLE_CONTEXT_SOURCES)}) — design #31 "
            "§3.2 (3)"
        )


_verify_context_source_anchor()
