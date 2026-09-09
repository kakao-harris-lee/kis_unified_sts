"""``EgressResultKind`` / reservation projection -> ADR-002-005 ``CompositeState`` adapter.

Phase 3 wave 2 KW2-C2 (plan §2.2): the engine's own provisional reservation projection
(:mod:`tos.engine.state`) and closed :class:`~tos.engine.vocabulary.EgressResultKind`
vocabulary carry, in their own local shape, the same underlying facts ADR-002-005 §6-§8
model as the **Transmission Attempt**, **Broker Order**, and **Knowledge / Evidence**
dimensions. This module is the pure, one-way adapter between the two: it authors the
mapping exactly once, here, so a consuming runtime can call
``tos.orthostate.may_transition`` / ``tos.orthostate.coupling_violations`` directly against
a real :class:`~tos.orthostate.records.CompositeState` without re-deriving which broker
state or knowledge state a ``FULL_FILL`` (or a ``CANCEL_ACK``, or a ``TIMEOUT``, ...) means.

**Why this lives in the kernel, not the runtime.** The mapping itself — "what does a
``FULL_FILL`` egress result *mean* on the ADR-002-005 dimensions" — is a closed,
deterministic, pure fact about the vocabulary this package already owns (design #31 §2.2);
it has no I/O, no runtime state, and belongs beside the vocabulary it maps, not duplicated
in every consuming runtime. Only the **use** of the mapping (deciding what to do when
``coupling_violations`` is non-empty, wiring a real ``Intent`` identity, persisting a
``CompositeState`` observation) is a runtime concern.

**Closure widening (2026-09-09, this module).** ``tos.orthostate`` becomes a directly
realized edge of ``tos.engine`` for the first time (see the package docstring's "Closure
widened" note). This is safe in the direction that matters: ``tos.orthostate`` does not,
and structurally cannot without breaking its own ratified closure (design #8 §0.3), import
``tos.engine`` back — unlike ``tos.egressgw`` / ``tos.authority`` / ``tos.liveauth``, all
three of which import **from** ``tos.engine`` and so remain permanently excluded (see
:class:`~tos.engine.core.TransportNatureLike` for why the Coordinator-precondition gate
cannot take the same shortcut with those three).

**Two independent tables, one shared axis.** :func:`result_transition_for` and
:func:`composite_state_for` both need a Broker-Order / Knowledge pair, but they start from
different inputs — a fresh :class:`~tos.engine.vocabulary.EgressResultKind` versus an
already-projected :class:`~tos.engine.vocabulary.EgressKnowledge`. Rather than author that
pair twice (a drift risk), both route through :data:`_KNOWLEDGE_ORTHOSTATE_PROJECTION`,
keyed on :class:`~tos.engine.vocabulary.EgressKnowledge` — the coarser, already-existing
axis :func:`~tos.engine.state.knowledge_for_result` derives from a result kind. Only the
**Transmission Attempt** half differs per result kind (a fresh result names a fresh
transport-side transition target that ``EgressKnowledge`` alone does not carry), which is
why :data:`_RESULT_ATTEMPT_TRANSITION` is the one genuinely separate table.

**Recorded decisions (report to the reviewer, plan §2.2's "read §7 and choose"):**

* ``CANCEL_ACK`` -> Broker Order ``CANCEL_PENDING``, not ``CANCELLED``. ADR-002-002 §16.2
  names this exact case verbatim: "Cancel Acknowledgement moves the reservation to
  ``RELEASE_PENDING_PROOF``" — a *bare* acknowledgement, distinct from a *proven* cancel.
  ADR-002-005 §10 CPL-4 independently says "Broker Order = ``CANCEL_PENDING`` or a bare
  cancel acknowledgement SHALL NOT move Capacity toward RELEASED". Both cite the same
  Broker Order value for the same event, so ``CANCEL_PENDING`` is the literal, not an
  inference.
* Both ``CANCEL_ACK`` and ``EXPIRED`` project **Transmission Attempt** as ``ACK_OBSERVED``,
  not ``SUPERSEDED``. ``SUPERSEDED`` (ADR-002-005 §6) is reserved for *this* attempt being
  displaced by a *different*, later attempt (replacement) — a cancel or an expiry is a
  broker-order-lifecycle fact about the *same* attempt that was already transmitted and
  acknowledged, and collapsing the two dimensions would reintroduce exactly the
  false-coupling RFC-002 §12 forbids (an order lifecycle event silently asserting something
  about transmission identity).
* ``ACK`` / ``FULL_FILL`` / ``PARTIAL_FILL`` / ``CANCEL_ACK`` / ``EXPIRED`` all project
  Knowledge as ``CONSISTENT``, never ``RECONCILED``: ADR-002-005 §8 requires positive
  corroborating evidence *and*, where a broker order is involved, Final Quantity Proof
  (ADR-002-004) for ``RECONCILED`` — a bare synthetic/paper result proves neither, so
  claiming ``RECONCILED`` here would be exactly the over-claim the ADR forbids. ``REJECT``
  is likewise ``CONSISTENT`` (a definite, single-source broker verdict — not yet
  cross-corroborated).
* ``UNKNOWN`` / ``TIMEOUT`` project Knowledge as ``UNOBSERVED``, not ``CONFLICTED``:
  neither result carries *conflicting* evidence, only *absent* evidence, and
  ``KnowledgeState`` has no dedicated ``UNKNOWN`` member (design #8 §8 "no UNKNOWN member
  here; uncertainty is UNOBSERVED / CONFLICTED"). Broker Order for both is the ADR's own
  explicit ``UNKNOWN`` member.
* The pre-result knowledge states (``NOT_SENT`` / ``SENT_UNCONFIRMED``) both project Broker
  Order as ``NONE_OBSERVED`` rather than ``UNKNOWN``: nothing has been queried yet at that
  point, which is a materially weaker claim than "broker state cannot currently be
  determined" (ADR-002-005 §7) — a query attempt is what ``UNKNOWN`` describes, not its
  absence.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #31 §0.3, widened per the note
above). No clock, no RNG.
"""

from __future__ import annotations

from tos.engine._base import ArtifactIntegrityError
from tos.engine.records import ProvisionalReservation
from tos.engine.state import knowledge_for_result
from tos.engine.vocabulary import EgressKnowledge, EgressResultKind
from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    IntentState,
    KnowledgeState,
    TransmissionAttemptState,
)

__all__ = [
    "composite_state_for",
    "result_transition_for",
]


#: The Broker-Order / Knowledge pair every :class:`~tos.engine.vocabulary.EgressKnowledge`
#: member projects onto (module docstring "two independent tables, one shared axis"). This
#: is the single place either half is decided; both :func:`result_transition_for` and
#: :func:`composite_state_for` read it, so the two can never silently drift apart.
_KNOWLEDGE_ORTHOSTATE_PROJECTION: dict[
    EgressKnowledge, tuple[BrokerOrderState, KnowledgeState]
] = {
    EgressKnowledge.NOT_SENT: (
        BrokerOrderState.NONE_OBSERVED,
        KnowledgeState.UNOBSERVED,
    ),
    EgressKnowledge.SENT_UNCONFIRMED: (
        BrokerOrderState.NONE_OBSERVED,
        KnowledgeState.UNOBSERVED,
    ),
    EgressKnowledge.ACKNOWLEDGED: (BrokerOrderState.WORKING, KnowledgeState.CONSISTENT),
    EgressKnowledge.PARTIALLY_FILLED: (
        BrokerOrderState.PARTIALLY_FILLED,
        KnowledgeState.CONSISTENT,
    ),
    EgressKnowledge.FILLED: (BrokerOrderState.FILLED, KnowledgeState.CONSISTENT),
    EgressKnowledge.REJECTED: (BrokerOrderState.REJECTED, KnowledgeState.CONSISTENT),
    EgressKnowledge.UNKNOWN: (BrokerOrderState.UNKNOWN, KnowledgeState.UNOBSERVED),
    EgressKnowledge.CANCEL_ACKNOWLEDGED: (
        BrokerOrderState.CANCEL_PENDING,
        KnowledgeState.CONSISTENT,
    ),
    EgressKnowledge.EXPIRED: (BrokerOrderState.EXPIRED, KnowledgeState.CONSISTENT),
}

#: The Transmission-Attempt target each :class:`~tos.engine.vocabulary.EgressResultKind`
#: projects onto — the one half :data:`_KNOWLEDGE_ORTHOSTATE_PROJECTION` cannot supply,
#: because ``EgressKnowledge`` alone does not distinguish "the send failed" from
#: "the send succeeded and something later happened to the order" (module docstring,
#: recorded decisions).
_RESULT_ATTEMPT_TRANSITION: dict[EgressResultKind, TransmissionAttemptState] = {
    EgressResultKind.ACK: TransmissionAttemptState.ACK_OBSERVED,
    EgressResultKind.FULL_FILL: TransmissionAttemptState.ACK_OBSERVED,
    EgressResultKind.PARTIAL_FILL: TransmissionAttemptState.ACK_OBSERVED,
    EgressResultKind.REJECT: TransmissionAttemptState.SEND_FAILED_PROVEN,
    EgressResultKind.UNKNOWN: TransmissionAttemptState.SENT_UNCONFIRMED,
    EgressResultKind.TIMEOUT: TransmissionAttemptState.SENT_UNCONFIRMED,
    EgressResultKind.CANCEL_ACK: TransmissionAttemptState.ACK_OBSERVED,
    EgressResultKind.EXPIRED: TransmissionAttemptState.ACK_OBSERVED,
}


def result_transition_for(
    kind: EgressResultKind,
) -> tuple[TransmissionAttemptState, BrokerOrderState, KnowledgeState]:
    """The ADR-002-005 §6-§8 triple a fresh ``EGRESS_RESULT`` of ``kind`` projects onto.

    A pure lookup — see the module docstring for the mapping table and the recorded
    per-kind decisions (``CANCEL_ACK`` -> ``CANCEL_PENDING``, both new kinds -> Attempt
    ``ACK_OBSERVED``, no result kind ever claims ``RECONCILED``).

    Args:
        kind: The egress result kind (any member of the closed
            :class:`~tos.engine.vocabulary.EgressResultKind` vocabulary).

    Returns:
        ``(attempt_transition, broker_order_state, knowledge_state)`` — the Transmission
        Attempt target, the Broker Order state, and the Knowledge state this result
        establishes.

    Raises:
        ArtifactIntegrityError: If ``kind`` is outside the closed vocabulary this module
            maps (fail-closed — an unmapped kind is a defect here, never a silent guess).
    """
    attempt = _RESULT_ATTEMPT_TRANSITION.get(kind)
    if attempt is None:
        raise ArtifactIntegrityError(
            f"no orthostate Transmission-Attempt projection is declared for egress result "
            f"kind {kind!r} (fail-closed) — engine/orthostate_projection.py must map every "
            "member of the closed EgressResultKind vocabulary"
        )
    broker, knowledge = _KNOWLEDGE_ORTHOSTATE_PROJECTION[knowledge_for_result(kind)]
    return attempt, broker, knowledge


def composite_state_for(
    projection: ProvisionalReservation,
    *,
    intent_state: IntentState,
    attempt_state: TransmissionAttemptState,
) -> CompositeState:
    """Build one ADR-002-005 ``CompositeState`` observation from the engine's own projection.

    ``projection.capacity_state`` is reused directly — the Capacity dimension is itself
    REUSED from ``tos.rcl`` by both ``tos.orthostate`` (design #8 §3.4) and this engine
    (:mod:`tos.engine.state`), so no conversion exists to write. Broker Order and Knowledge
    are derived from ``projection.knowledge`` via the same table
    :func:`result_transition_for` reads (module docstring). ``intent_state`` and
    ``attempt_state`` are **not** derivable from the projection at all — this package
    tracks neither an ADR-002-005 Intent (the Intent Registry does not exist as a runtime
    object here) nor a Transmission-Attempt dimension value (only the coarser
    ``EgressKnowledge`` axis) — so the caller supplies both explicitly.

    ``intent_identity`` is populated from ``projection.proposal_id``, the closest identity
    this package actually has; it is honestly not an ADR-002-005 Intent identity (no such
    object exists yet), and it may be ``None`` (e.g. before ``commit_unbound`` binds one).
    The resulting :class:`~tos.orthostate.records.CompositeState` is left at its default
    ``DRAFT`` status, for which ``tos.orthostate``'s own required-covered completeness
    check is deferred (``tos/src/tos/canonical/_base.py`` "Required-covered completeness
    is deferred to issuance") — so a ``None`` identity does not make the composite
    unconstructable; it only means this observation is never meant to be issued as-is.

    Args:
        projection: The engine's own reservation projection.
        intent_state: The caller-supplied ADR-002-005 Intent-dimension state.
        attempt_state: The caller-supplied ADR-002-005 Transmission-Attempt-dimension
            state — typically the ``attempt_transition`` half of a prior
            :func:`result_transition_for` call, or a caller's own tracked value.

    Returns:
        The composed, unissued (``DRAFT``) :class:`~tos.orthostate.records.CompositeState`.

    Raises:
        ArtifactIntegrityError: If ``projection.knowledge`` is outside the closed mapping
            (fail-closed — this can only happen if a future ``EgressKnowledge`` member is
            added here without a corresponding table entry).
    """
    mapped = _KNOWLEDGE_ORTHOSTATE_PROJECTION.get(projection.knowledge)
    if mapped is None:
        raise ArtifactIntegrityError(
            f"no orthostate Broker-Order/Knowledge projection is declared for "
            f"EgressKnowledge {projection.knowledge!r} (fail-closed)"
        )
    broker, knowledge = mapped
    return CompositeState(
        intent_identity=projection.proposal_id,
        intent_state=intent_state,
        transmission_attempt_state=attempt_state,
        broker_order_state=broker,
        knowledge_state=knowledge,
        capacity_state=projection.capacity_state,
    )
