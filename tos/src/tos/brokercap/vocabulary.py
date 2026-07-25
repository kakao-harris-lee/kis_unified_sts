"""Broker-capability vocabulary — the capability-CLASS StrEnums (design #10 §2.2).

Spec terms = code terms (design #10 §2; boundary design #1 §2.4). The enums are
authored **verbatim** from ADR-002-004 (§5.3 status, §8 dimensions, §8.3
acknowledgement, §8.8 replace, §9 assurance, §10 conformance, §5.4 assurance-source,
§15.3 prohibited proofs), and :class:`Admissibility` is the local 3-token realization
of ADR-002-004 §1 line 32 ("reduce live scope or prohibit"). These are the
**broker-capability** axis; they are a distinct coordinate system from the orthostate
``KnowledgeState`` / ``BrokerOrderState`` (per-action / broker-order state), the recon
``FieldConfidenceClass`` (per-field evidence confidence), and the capsule ``FieldState``
(per-field context freshness). The shared token ``UNKNOWN`` is intentional (ADR uses the
same word on several axes), so coordinate non-collapse rests on **distinct types +
non-import** (design #10 §4.4): brokercap imports none of those sibling axes, so a value
from one can never be coerced onto another.

This module names **no** concrete broker (broker-agnostic — project memory
``tos-spec-broker-agnostic``; design #10 §0.1). The capability values / class assignment
of any one broker belong to a non-normative Broker Capability Profile INSTANCE (ADR §21),
not here.

Pure module: stdlib only; no ``shared.*`` (design #10 §0.3).
"""

from __future__ import annotations

from enum import StrEnum


class CapabilityStatus(StrEnum):
    """The 7 broker-capability statuses (ADR-002-004 §5.3 line 136-144 verbatim).

    Verbatim from ADR §5.3::

        VERIFIED
        VERIFIED_WITH_RESTRICTION
        DOCUMENTED_NOT_VERIFIED
        UNSUPPORTED
        CONTRADICTORY
        UNKNOWN
        EXPIRED

    §5.3 line 146 verbatim: "Only ``VERIFIED`` and explicitly approved
    ``VERIFIED_WITH_RESTRICTION`` may authorize live behavior." The other five statuses —
    and any **undeclared** dimension (BC-INV-001) — are restrictive (design #10 §4.1 /
    §5.1). This is the broker-capability axis, **not** orthostate ``BrokerOrderState``
    (whose ``UNKNOWN`` is a different type) — coordinate non-collapse (design #10 §4.4).
    """

    VERIFIED = "VERIFIED"
    VERIFIED_WITH_RESTRICTION = "VERIFIED_WITH_RESTRICTION"
    DOCUMENTED_NOT_VERIFIED = "DOCUMENTED_NOT_VERIFIED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTORY = "CONTRADICTORY"
    UNKNOWN = "UNKNOWN"
    EXPIRED = "EXPIRED"


class CapabilityDimension(StrEnum):
    """The 17 broker-capability dimensions (ADR-002-004 §8 line 293-512, §8.1-§8.17).

    Verbatim from the §8.x subsection titles. Each dimension carries one
    :class:`~tos.brokercap.records.CapabilityDeclaration` (status + assurance + evidence +
    restriction + fallback). An **undeclared** dimension is BC-INV-001 ("A broker property
    that is not present and current in the approved Capability Profile SHALL be treated as
    unavailable", line 191) => most-restrictive (design #10 §4.1). Which dimensions an
    action class requires is **injected** (``RequiredCapabilitySet``), never hardcoded
    (design #10 §5.1 / §8).
    """

    ORDER_IDENTITY = "ORDER_IDENTITY"
    SUBMISSION_IDEMPOTENCY = "SUBMISSION_IDEMPOTENCY"
    ACKNOWLEDGEMENT_SEMANTICS = "ACKNOWLEDGEMENT_SEMANTICS"
    FILL_EVENTS = "FILL_EVENTS"
    OPEN_ORDER_QUERY = "OPEN_ORDER_QUERY"
    ORDER_HISTORY_QUERY = "ORDER_HISTORY_QUERY"
    CANCELLATION = "CANCELLATION"
    REPLACE_OR_AMEND = "REPLACE_OR_AMEND"
    REDUCE_ONLY = "REDUCE_ONLY"
    POSITIONS_BALANCES_MARGIN = "POSITIONS_BALANCES_MARGIN"
    ACCOUNT_EVENT_PUSH = "ACCOUNT_EVENT_PUSH"
    CORPORATE_ADMINISTRATIVE_EVENTS = "CORPORATE_ADMINISTRATIVE_EVENTS"
    RATE_LIMITS = "RATE_LIMITS"
    SESSION_CONNECTION_MODEL = "SESSION_CONNECTION_MODEL"
    CREDENTIALS_AUTHORIZATION = "CREDENTIALS_AUTHORIZATION"
    BROKER_TIME = "BROKER_TIME"
    MARKET_INSTRUMENT_CONSTRAINTS = "MARKET_INSTRUMENT_CONSTRAINTS"


class AssuranceLevel(StrEnum):
    """The 5 assurance levels (ADR-002-004 §9 line 516-540 verbatim).

    Verbatim from ADR §9::

        LEVEL_0_UNKNOWN                    (Level 0 — Unknown; live use prohibited)
        LEVEL_1_DOCUMENTED                 (Level 1 — Documented; not operationally verified)
        LEVEL_2_CONTROLLED_TEST_VERIFIED   (Level 2 — sandbox/controlled)
        LEVEL_3_RESTRICTED_PRODUCTION      (Level 3 — controlled production, bounded risk)
        LEVEL_4_CONTINUOUSLY_MONITORED     (Level 4 — verified + continuous drift check)

    §9 line 540 verbatim: "Safety-critical live scope normally requires **Level 3 or Level
    4** for the dimensions it relies upon." The required level is **injected** per scope;
    an unspecified required level fails closed (treated as the highest requirement) —
    design #10 §5.1.
    """

    LEVEL_0_UNKNOWN = "LEVEL_0_UNKNOWN"
    LEVEL_1_DOCUMENTED = "LEVEL_1_DOCUMENTED"
    LEVEL_2_CONTROLLED_TEST_VERIFIED = "LEVEL_2_CONTROLLED_TEST_VERIFIED"
    LEVEL_3_RESTRICTED_PRODUCTION = "LEVEL_3_RESTRICTED_PRODUCTION"
    LEVEL_4_CONTINUOUSLY_MONITORED = "LEVEL_4_CONTINUOUSLY_MONITORED"


#: The §9 line 516-540 assurance-level ordering (0 lowest .. 4 highest). Used by the
#: admissibility predicate to compare a declared level against the injected required
#: level (design #10 §5.1). An unranked / ``None`` level fails closed.
ASSURANCE_LEVEL_RANK: dict[AssuranceLevel, int] = {
    AssuranceLevel.LEVEL_0_UNKNOWN: 0,
    AssuranceLevel.LEVEL_1_DOCUMENTED: 1,
    AssuranceLevel.LEVEL_2_CONTROLLED_TEST_VERIFIED: 2,
    AssuranceLevel.LEVEL_3_RESTRICTED_PRODUCTION: 3,
    AssuranceLevel.LEVEL_4_CONTINUOUSLY_MONITORED: 4,
}


class ConformanceClass(StrEnum):
    """The 4 conformance classes (ADR-002-004 §10 line 544-584 verbatim).

    Verbatim from ADR §10::

        CLASS_A_DETERMINISTIC_LIVE
        CLASS_B_RESTRICTED_SERIALIZED_LIVE
        CLASS_C_PROTECTIVE_SUPERVISED_ONLY
        CLASS_D_NON_LIVE

    §10 line 546 verbatim: "Conformance classes summarize but do **not** replace
    dimension-level decisions." §10 line 584 verbatim: "**A class cannot override a failed
    mandatory dimension.**" The class is therefore only a summary label
    (:func:`~tos.brokercap.predicates.active_conformance_class` exposes it as a scalar); it
    never overrides the per-dimension admissibility decision (design #10 §4.1 / §5.1
    canary).
    """

    CLASS_A_DETERMINISTIC_LIVE = "CLASS_A_DETERMINISTIC_LIVE"
    CLASS_B_RESTRICTED_SERIALIZED_LIVE = "CLASS_B_RESTRICTED_SERIALIZED_LIVE"
    CLASS_C_PROTECTIVE_SUPERVISED_ONLY = "CLASS_C_PROTECTIVE_SUPERVISED_ONLY"
    CLASS_D_NON_LIVE = "CLASS_D_NON_LIVE"


#: The classes that are NOT full deterministic/serialized live — used by the §13.15
#: partition-protective-class scope predicate (design #10 §6.5): a partition-protective
#: profile is admissible only if reduced OR classified into one of these.
NON_LIVE_OR_SUPERVISED_CLASSES: frozenset[ConformanceClass] = frozenset(
    {
        ConformanceClass.CLASS_C_PROTECTIVE_SUPERVISED_ONLY,
        ConformanceClass.CLASS_D_NON_LIVE,
    }
)


class AssuranceSource(StrEnum):
    """The 8 assurance sources (ADR-002-004 §5.4 line 150-159).

    The evidence-source kinds a declaration's assurance may rest on. Sandbox-only sources
    do not by themselves establish live capability (§13.14 / BC-INV-009; design #10 §6.4
    environment binding).
    """

    OFFICIAL_SPECIFICATION = "OFFICIAL_SPECIFICATION"
    BROKER_CONTRACTUAL_STATEMENT = "BROKER_CONTRACTUAL_STATEMENT"
    CONTROLLED_SANDBOX_TEST = "CONTROLLED_SANDBOX_TEST"
    CONTROLLED_PRODUCTION_PROBE = "CONTROLLED_PRODUCTION_PROBE"
    FAULT_INJECTION_RESULT = "FAULT_INJECTION_RESULT"
    OBSERVED_LIVE_EVIDENCE = "OBSERVED_LIVE_EVIDENCE"
    BROKER_SUPPORT_CONFIRMATION = "BROKER_SUPPORT_CONFIRMATION"
    INDEPENDENT_OPERATIONAL_REVIEW = "INDEPENDENT_OPERATIONAL_REVIEW"


class AcknowledgementState(StrEnum):
    """The 6 acknowledgement-semantics states (ADR-002-004 §8.3 line 322-329 verbatim).

    Verbatim from ADR §8.3::

        TRANSPORT_RECEIVED
        BROKER_RECEIVED
        VALIDATED
        ACCEPTED
        WORKING
        REJECTED

    §8.3 line 331 verbatim: "**If one response code combines these states, the weakest safe
    interpretation applies.**" (BC-EV-004 substrate.)
    """

    TRANSPORT_RECEIVED = "TRANSPORT_RECEIVED"
    BROKER_RECEIVED = "BROKER_RECEIVED"
    VALIDATED = "VALIDATED"
    ACCEPTED = "ACCEPTED"
    WORKING = "WORKING"
    REJECTED = "REJECTED"


class ReplaceSemantics(StrEnum):
    """The 5 replace/amend semantics (ADR-002-004 §8.8 line 386-391 verbatim).

    Verbatim from ADR §8.8::

        ATOMIC_REPLACE
        CANCEL_THEN_NEW
        NEW_THEN_CANCEL
        BROKER_UNSPECIFIED
        UNSUPPORTED

    §8.8 line 394: "The profile SHALL define overlap and protection-gap behavior." Any
    non-atomic semantics (everything but ``ATOMIC_REPLACE``) => the §13.7 fallback (reserve
    overlap capacity or represent the gap as unprotected risk; BC-EV-009).
    """

    ATOMIC_REPLACE = "ATOMIC_REPLACE"
    CANCEL_THEN_NEW = "CANCEL_THEN_NEW"
    NEW_THEN_CANCEL = "NEW_THEN_CANCEL"
    BROKER_UNSPECIFIED = "BROKER_UNSPECIFIED"
    UNSUPPORTED = "UNSUPPORTED"


class Admissibility(StrEnum):
    """The local 3-token admissibility verdict (ADR-002-004 §1 line 32 realization).

    ADR line 32 ("... SHALL reduce live scope or prohibit the affected action") as a
    3-token verdict::

        ADMISSIBLE   all required dimensions VERIFIED / approved-restriction, level met,
                     version current, no drift / contradiction
        REDUCED      a deficiency exists but every deficient dimension has an approved
                     conservative fallback => restricted-live (a smaller scope)
        PROHIBITED   missing / unknown / contradictory / expired / unsupported, or a
                     deficiency with no approved fallback => the action is prohibited

    There is deliberately **no** "assume-admissible" construction path anywhere: the
    central predicate returns ``ADMISSIBLE`` only from positive proof, and everything else
    is restrictive (design #10 §4.1 — the structural seal against the #6 fail-open REJECT
    lesson).
    """

    ADMISSIBLE = "ADMISSIBLE"
    REDUCED = "REDUCED"
    PROHIBITED = "PROHIBITED"


class ProhibitedProof(StrEnum):
    """The 7 prohibited Final-Quantity-Proof bases (ADR-002-004 §15.3 line 857-863 verbatim).

    Verbatim from ADR §15.3 — a Final Quantity Proof SHALL NOT rest solely on any of::

        CANCEL_ACKNOWLEDGEMENT                        (§15.3; BC-INV-004/005)
        ONE_OPEN_ORDER_QUERY_OMISSION                 (§15.3; BC-INV-004)
        LOCAL_TIMEOUT                                 (§15.3; §1 line 43)
        STRATEGY_CANCELLATION_INTENT                  (§15.3)
        PROCESS_RESTART                               (§15.3)
        ACCOUNT_POSITION_MATCHING_EXPECTED_VALUE      (§15.3; §23.4)
        OPERATOR_ASSERTION_WITHOUT_BROKER_EVIDENCE    (§15.3)

    If any of these is the **sole** basis for a claimed final quantity, the proof is not
    adequate (design #10 §6.3 :func:`~tos.brokercap.predicates.fqp_adequate`).
    """

    CANCEL_ACKNOWLEDGEMENT = "CANCEL_ACKNOWLEDGEMENT"
    ONE_OPEN_ORDER_QUERY_OMISSION = "ONE_OPEN_ORDER_QUERY_OMISSION"
    LOCAL_TIMEOUT = "LOCAL_TIMEOUT"
    STRATEGY_CANCELLATION_INTENT = "STRATEGY_CANCELLATION_INTENT"
    PROCESS_RESTART = "PROCESS_RESTART"
    ACCOUNT_POSITION_MATCHING_EXPECTED_VALUE = (
        "ACCOUNT_POSITION_MATCHING_EXPECTED_VALUE"
    )
    OPERATOR_ASSERTION_WITHOUT_BROKER_EVIDENCE = (
        "OPERATOR_ASSERTION_WITHOUT_BROKER_EVIDENCE"
    )


#: The authorizing statuses — the ONLY two that may authorize live behavior (§5.3 line
#: 146). ``VERIFIED_WITH_RESTRICTION`` additionally requires an explicit restriction
#: approval on the declaration (design #10 §5.1); the constant names the status membership,
#: the approval flag is checked separately.
AUTHORIZING_STATUSES: frozenset[CapabilityStatus] = frozenset(
    {
        CapabilityStatus.VERIFIED,
        CapabilityStatus.VERIFIED_WITH_RESTRICTION,
    }
)
