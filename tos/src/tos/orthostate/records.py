"""Orthostate ledger-citizen records — composite observation + transition (§2, §4).

Two digest-bound :class:`~tos.orthostate._base.IndependentIdArtifact` records with an
independent, service-assigned identity (``id != f(digest)``, design #8 §3.1) so an
append-only observation log can represent and detect a "duplicate identity with
different content" conflict (``classify_record_pair`` => ``CRITICAL_CONFLICT``;
ADR-002-005 §5 line 76 SAFE-020 immutable / non-reuse). There is **no** update / delete
/ mutate method — a legitimate dimension transition is expressed by appending a **new
observation** (a fresh ``composite_state_id``) plus a transition record, never by
mutating a stored composite (design #8 §2.3 / §4.5 / §4.6 representation ≠ effect).

The :class:`CompositeState` frozen product realizes the central **no-mixed-enum**
invariant (design #8 §4.1; RFC-002 §12 "SHALL NOT … single order-status enumeration"):
the five dimensions are five separate-typed coordinates, so a dimension collapse is
structurally unrepresentable and a dimension-swap fails validation.

Spec terms = code terms (boundary design #1 §2.4).

Pure module: ``pydantic`` + stdlib + ``tos.rcl`` (Capacity dimension REUSE) +
``tos.orthostate`` only; no ``shared.*`` (design #8 §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from tos.orthostate._base import IndependentIdArtifact
from tos.orthostate.vocabulary import (
    BrokerOrderState,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransitionAuthority,
    TransmissionAttemptState,
)
from tos.rcl import CapacityState


class CompositeState(IndependentIdArtifact):
    """One append-only observation of the five orthogonal dimensions (§2.2 / §14).

    A frozen product carrying the five dimensions as five **separate-typed, required,
    non-Optional** coordinates (design #8 §4.1/§4.4): ``intent_state`` /
    ``transmission_attempt_state`` / ``broker_order_state`` / ``knowledge_state`` /
    ``capacity_state`` (the last REUSED from ``tos.rcl``, design #8 §3.4). None has a
    default — omitting any dimension makes the composite unconstructable (there is no
    4-dimension composite), and putting one dimension's value in another's field fails
    StrEnum coercion (global string-value distinctness, §2.2). The dimensions MAY
    disagree temporarily and the model **represents** that disagreement rather than
    collapsing it (ADR-002-005 §1 line 25) — a coupling-flagged composite is still
    representable (design #8 §5.0).

    **Fresh id per observation (design #8 §2.3):** the five dimensions transition
    independently over time (ADR-002-005 §1 line 25). Each observation is an immutable
    append-only record with its **own** ``composite_state_id``; a legitimate transition
    (e.g. Broker ``WORKING`` -> ``PARTIALLY_FILLED``) is a **new observation with a new
    id**, never a same-id byte change (which would be a ``CRITICAL_CONFLICT`` forgery /
    replay). Committed observation order is carried by ``observation_revision``
    (self-excluded from the digest, §2.3), and the transition itself by
    :class:`DimensionTransitionRecord` (§2.4).

    ``covered`` (the Layer-1 digest preimage, §2.3) = ``intent_identity`` + the five
    dimension coordinates + the ``state_model_version`` reference; the id,
    ``canonical_digest`` / ``status`` / ``canonicalization_version`` meta, and the
    ledger-placement ``observation_revision`` are self-excluded.
    """

    _ID_FIELD: ClassVar[str] = "composite_state_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "intent_identity",
        "intent_state",
        "transmission_attempt_state",
        "broker_order_state",
        "knowledge_state",
        "capacity_state",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "intent_identity",
            "intent_state",
            "transmission_attempt_state",
            "broker_order_state",
            "knowledge_state",
            "capacity_state",
            "state_model_version",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    composite_state_id: str | None = None

    # ---- Layer-1 covered content (ADR-002-005 §1/§14) --------------------------
    intent_identity: str | None = None
    intent_state: IntentState
    transmission_attempt_state: TransmissionAttemptState
    broker_order_state: BrokerOrderState
    knowledge_state: KnowledgeState
    capacity_state: CapacityState
    state_model_version: str | None = None

    # ---- ledger-placement (self-excluded from the digest, §2.3) ---------------
    observation_revision: int | None = None


class DimensionTransitionRecord(IndependentIdArtifact):
    """One append-only per-dimension transition record (§2.4; ADR-002-005 §12/§13).

    An element of the append-only transition sequence that is the input to the
    ownership predicate (§6.2), the restart substrate (§6.3), and audit. Records which
    ``dimension`` moved, ``from_state`` -> ``to_state`` (carried as scalar strings since
    the value type varies by dimension), the ``owning_authority`` that performed it
    (§12), the conservative-direction ``basis`` (§6.1), and a scalar ``evidence_reference``.
    Actual evidence emission and causal edges are design #4's concern — orthostate leaves
    only a scalar (design #8 §2.4). ``transition_id`` is independent of the digest, so a
    same-id / different-bytes pair is a detectable ``CRITICAL_CONFLICT`` (§4.5).

    ``covered`` = ``intent_identity`` + ``dimension`` + ``from_state`` / ``to_state`` +
    ``owning_authority`` + ``basis`` + ``evidence_reference`` + ``observation_revision``;
    the id and lifecycle meta are self-excluded (§2.4).
    """

    _ID_FIELD: ClassVar[str] = "transition_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "intent_identity",
        "dimension",
        "from_state",
        "to_state",
        "owning_authority",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "intent_identity",
            "dimension",
            "from_state",
            "to_state",
            "owning_authority",
            "basis",
            "evidence_reference",
            "observation_revision",
        }
    )

    transition_id: str | None = None

    intent_identity: str | None = None
    dimension: StateDimension | None = None
    from_state: str | None = None
    to_state: str | None = None
    owning_authority: TransitionAuthority | None = None
    basis: str | None = None
    evidence_reference: str | None = None
    observation_revision: int | None = None
