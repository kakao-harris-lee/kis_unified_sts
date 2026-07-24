"""Orthostate vocabulary — the four local dimension enums + coordination enums.

Spec terms = code terms (design #8 §2; boundary design #1 §2.4). The four dimension
enums are authored **verbatim** from ADR-002-005 §5 (Intent), §6 (Transmission
Attempt), §7 (Broker Order), and §8 (Knowledge / Evidence). The fifth dimension —
Capacity — is **not** re-authored here: it is REUSED from ``tos.rcl`` (design #8
§3.4; ADR-002-005 §9 line 148 "Defined by ADR-002-002 … owned solely by the Risk
Capacity Ledger").

``StateDimension`` and ``TransitionAuthority`` (design #8 §6.2; ADR-002-005 §12) name
the five dimensions and their six exclusive transition authorities. ``ConservatismBasis``
(design #8 §6.1; ADR-002-005 §11) is the **local, wider** weak/strong basis taxonomy —
deliberately NOT ``tos.rcl.WEAK_CAUSES`` (which lacks ``LOCAL_CACHE`` /
``RECOVERY_RECONNECT``); reusing the narrower rcl set on the four local dimensions would
let a "local cache" conservatism reduction pass unfiltered (a fail-open — design #8
§0.4c). Only the Capacity dimension delegates to ``rcl.transition_allowed`` (rcl's
narrower ``WEAK_CAUSES``, faithful to ADR-002-002 §10.2).

**Global string-value distinctness** across the five dimension enums (the four here +
``tos.rcl.CapacityState``) is a design invariant (design #8 §2.2 / §4.2): no state
string appears in two dimensions, so putting one dimension's value in another
dimension's field fails StrEnum coercion (the dimension-swap canary).

Pure module: stdlib only; no ``shared.*`` (design #8 §0.3).
"""

from __future__ import annotations

from enum import StrEnum


class IntentState(StrEnum):
    """The 7 Intent-dimension states (ADR-002-005 §5 line 65-77).

    The business / authorization lifecycle of a decision, owned by the **Intent
    Registry** (§5 line 66). Transitions (§5 line 69-73)::

        PROPOSED -> APPROVED -> AUTHORIZED_FOR_CAPACITY -> ACTIVE -> CLOSED
                             \\-> DENIED
        ACTIVE -> WITHDRAWN            (only if no attempt may be live; §11)

    ``DENIED`` branches from ``APPROVED`` (line 71 column-22 alignment + line 75 "Approval
    + Aggregate-Risk policy granted"), **not** from ``PROPOSED`` — the transition
    predicate regression-locks that ``PROPOSED -> DENIED`` is NOT allowed (design #8
    §2.2). ``AUTHORIZED_FOR_CAPACITY`` means Approval + Aggregate-Risk granted; it does
    **not** mean capacity is committed or that anything was transmitted (line 75). Intent
    identity is immutable and globally unique and never reused after terminal (SAFE-020,
    line 76). ``CLOSED`` / ``WITHDRAWN`` are permitted only when Capacity and Knowledge
    prove no potentially-live effect remains (line 77; §11).
    """

    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    AUTHORIZED_FOR_CAPACITY = "AUTHORIZED_FOR_CAPACITY"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    DENIED = "DENIED"
    WITHDRAWN = "WITHDRAWN"


class TransmissionAttemptState(StrEnum):
    """The 8 Transmission-Attempt-dimension states (ADR-002-005 §6 line 81-99).

    Local send preparation and transport uncertainty, owned by the **Execution
    Coordinator** (preparation) and the **Broker Adapter / Egress Gateway** (send
    boundary) (§6 line 82). Transitions (§6 line 85-92)::

        NONE -> PREPARED -> CAPABILITY_ISSUED -> SEND_STARTED -> SENT_UNCONFIRMED
             -> {ACK_OBSERVED | SEND_FAILED_PROVEN | SUPERSEDED}

    Conservative rules: the transition into ``SEND_STARTED`` is durable **before** the
    external call (write-ahead boundary, line 89/96); ``SEND_FAILED_PROVEN`` requires
    **positive evidence** the broker did not and cannot accept — timeout / missing-ACK /
    reset / restart SHALL NOT reach it (line 97); once ``SEND_STARTED`` is reached, no
    TTL / restart / authority-expiry may retire the attempt to a capacity-releasing state
    (line 98).

    ``NONE`` ("no attempt yet") is a legitimate value and is distinct from a **missing /
    ``None``** composite field (design #8 §2.2 canary — NONE ≠ None).
    """

    NONE = "NONE"
    PREPARED = "PREPARED"
    CAPABILITY_ISSUED = "CAPABILITY_ISSUED"
    SEND_STARTED = "SEND_STARTED"
    SENT_UNCONFIRMED = "SENT_UNCONFIRMED"
    ACK_OBSERVED = "ACK_OBSERVED"
    SEND_FAILED_PROVEN = "SEND_FAILED_PROVEN"
    SUPERSEDED = "SUPERSEDED"


class BrokerOrderState(StrEnum):
    """The 9 Broker-Order-dimension states (ADR-002-005 §7 line 102-122).

    The broker-side order lifecycle, established **only from broker / venue evidence**
    under the approved Broker Capability Profile (ADR-002-004); no internal component
    may set this dimension from assumption (§7 line 104). ADR-002-005 gives this
    dimension as a **state set, not a transition graph** — direction is governed by the
    §11 conservative-direction predicate, not an arrow table.

    Conservative rules: absence of an order from one query / page / session / stream is
    **not** proof of ``NONE_OBSERVED`` / ``CANCELLED`` — it only lowers broker-state
    confidence (the Knowledge dimension) (line 120); a later valid fill SHALL be
    accepted even after a locally observed ``CANCELLED`` / ``REJECTED`` (line 121);
    ``UNKNOWN`` forces ``QUARANTINED_UNKNOWN`` in the Capacity dimension (line 122;
    CPL-5). ``UNKNOWN`` is first-class and capacity-consuming and never means rejected /
    cancelled / unfilled / safe-to-retry (§1 line 27).
    """

    NONE_OBSERVED = "NONE_OBSERVED"
    WORKING = "WORKING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class KnowledgeState(StrEnum):
    """The 7 Knowledge / Evidence-dimension states (ADR-002-005 §8 line 126-142).

    How well the other dimensions are known, owned by the **Reconciliation Service**
    (ADR-002-006 defines the confidence representation) (§8 line 128). Transitions
    (§8 line 130-136)::

        UNOBSERVED -> {CONSISTENT | CONFLICTED}
        CONSISTENT -> CONFLICTED
        CONFLICTED -> RECONCILING -> {RECONCILED | QUARANTINED}
        STALE                          (prior knowledge older than freshness bound)

    Conservative rules: ``RECONCILED`` requires positive corroborating evidence
    (ADR-002-006) and, where a broker order is involved, Final Quantity Proof
    (ADR-002-004) — never inferred from a single source or silence (line 140); loss of
    freshness moves knowledge to ``STALE``, which SHALL NOT authorize new risk (line
    141); ``QUARANTINED`` is a stable conservative state whose exit requires evidence,
    never assertion (line 142).

    Authored **locally** (design #8 §0.4e): ``KnowledgeState`` is a decision-side axis
    distinct from the evidence *ledger* (a downstream projection — not imported) and from
    the capsule ``FieldState`` (per-field context freshness — a different coordinate
    system). ``KnowledgeState.CONFLICTED`` ("confidence about this trading action") is
    NOT ``FieldState.CONFLICTED`` ("freshness of one context field") — coordinate
    non-collapse. There is deliberately **no** ``UNKNOWN`` member here (that value lives
    only on the Broker / Capacity dimensions); uncertainty is ``UNOBSERVED`` / ``CONFLICTED``.
    """

    UNOBSERVED = "UNOBSERVED"
    CONSISTENT = "CONSISTENT"
    CONFLICTED = "CONFLICTED"
    RECONCILING = "RECONCILING"
    RECONCILED = "RECONCILED"
    QUARANTINED = "QUARANTINED"
    STALE = "STALE"


class StateDimension(StrEnum):
    """The five orthogonal state dimensions (design #8 §6.2; ADR-002-005 §1 line 15-22).

    Names the coordinate axes for ``coupling`` / ``ownership`` / ``transition`` queries.
    Capacity is a first-class dimension whose *states* live in ``tos.rcl.CapacityState``
    (design #8 §3.4); this enum names the dimension, not its states.
    """

    INTENT = "INTENT"
    TRANSMISSION_ATTEMPT = "TRANSMISSION_ATTEMPT"
    BROKER_ORDER = "BROKER_ORDER"
    KNOWLEDGE = "KNOWLEDGE"
    CAPACITY = "CAPACITY"


class TransitionAuthority(StrEnum):
    """The six exclusive transition authorities (design #8 §6.2; ADR-002-005 §12).

    Local **role labels** (not ``tos.authority`` artifacts — design #8 §0.4e): who may
    write each dimension per the §12 table (line 183-189). The Transmission Attempt
    dimension has two owners split by region — the ``EXECUTION_COORDINATOR`` (preparation)
    and the ``BROKER_ADAPTER_EGRESS`` (send boundary) (§6 line 82); the Broker Order
    dimension is owned by ``BROKER_ADAPTER_EVIDENCE`` (broker evidence under profile, not
    assumption — §7 line 104), a distinct role from egress.
    """

    INTENT_REGISTRY = "INTENT_REGISTRY"
    EXECUTION_COORDINATOR = "EXECUTION_COORDINATOR"
    BROKER_ADAPTER_EGRESS = "BROKER_ADAPTER_EGRESS"
    BROKER_ADAPTER_EVIDENCE = "BROKER_ADAPTER_EVIDENCE"
    RECONCILIATION_SERVICE = "RECONCILIATION_SERVICE"
    RISK_CAPACITY_LEDGER = "RISK_CAPACITY_LEDGER"


class ConservatismBasis(StrEnum):
    """Basis for a per-dimension conservative-direction transition (design #8 §6.1).

    Authored **locally and wider** than ``tos.rcl.WEAK_CAUSES`` (design #8 §0.4c;
    ADR-002-005 §11 line 172-175). The **weak** bases (:data:`WEAK_BASES`) may never
    reduce conservatism on any dimension; the **strong** bases are the §5-§8 positive
    proof rules that alone may reduce it. ``tos.rcl.WEAK_CAUSES`` lacks ``LOCAL_CACHE``
    and ``RECOVERY_RECONNECT``, so ``WEAK_BASES ⊋ rcl.WEAK_CAUSES`` — the divergence is
    intentional (each faithful to its own ADR); only the Capacity dimension reuses
    ``rcl.transition_allowed`` (design #8 §6.1b).
    """

    # Weak bases (ADR-002-005 §11 line 172-175) — may only increase conservatism.
    TIMEOUT = "TIMEOUT"
    ABSENCE = "ABSENCE"
    LOCAL_CACHE = "LOCAL_CACHE"
    OPERATOR_ASSERTION = "OPERATOR_ASSERTION"
    RECOVERY_RECONNECT = "RECOVERY_RECONNECT"
    # Strong dimension-specific proof bases (ADR-002-005 §11 line 176; §5-§8 proof rules).
    BROKER_EVIDENCE_UNDER_PROFILE = "BROKER_EVIDENCE_UNDER_PROFILE"
    POSITIVE_CORROBORATION = "POSITIVE_CORROBORATION"
    POSITIVE_SEND_FAILURE_PROOF = "POSITIVE_SEND_FAILURE_PROOF"
    AUTHORITY_DECISION = "AUTHORITY_DECISION"


#: The weak conservatism bases that may never drive a less-conservative transition
#: (ADR-002-005 §11 line 172-175). Wider than ``tos.rcl.WEAK_CAUSES`` (design #8 §0.4c):
#: it additionally includes ``LOCAL_CACHE`` and ``RECOVERY_RECONNECT``.
WEAK_BASES: frozenset[ConservatismBasis] = frozenset(
    {
        ConservatismBasis.TIMEOUT,
        ConservatismBasis.ABSENCE,
        ConservatismBasis.LOCAL_CACHE,
        ConservatismBasis.OPERATOR_ASSERTION,
        ConservatismBasis.RECOVERY_RECONNECT,
    }
)
