"""Engine models — events, injected coordinates, stage verdicts, the attempt request, evidence.

The frozen data the single event core and the Execution Coordinator sequencer exchange (design
#31 §5). Three shapes deserve attention:

* :class:`InstrumentKey` — the **structurally derived** dispatch key (design #31 §3.3). It is
  wildcard-free and ``None``-free by construction, mirroring the RFC-003 §9:279-283 Proposal
  wildcard prohibition at the dispatch layer; the wildcard token set is *reused* from
  :data:`tos.dsl.WILDCARD_TOKENS`, never re-authored.
* :class:`EgressResultPayload` — carries a partial fill **as** a partial fill (RFC-005 §11:338-339,
  §6:176-178). Its shape validator derives the fill/partial distinction from the magnitudes rather
  than trusting the declared kind (구조 파생 > 자기신고).
* :class:`AttemptRequest` — the Coordinator's only direct artifact (ADR-002-002 §11.3:599). Its
  identity is **content-addressed** from (conformance-proof digest, Action Flow Permit identity,
  injected reference coordinate); there is no uuid4 / timestamp nonce anywhere, so replay identity
  survives (RFC-003 §10:360-363; design #31 §4.3 MAJOR-3).

Every engine-emitted record carries :class:`~tos.engine._base.AllFalseCoordinatorAuthority`.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #31 §0.3). No clock, no RNG.
"""

from __future__ import annotations

from pydantic import model_validator

from tos.capsule import DecisionContextCapsule
from tos.dsl import (
    WILDCARD_TOKENS,
    AuthoredStrategy,
    EvaluationConfig,
    Proposal,
)
from tos.engine._base import (
    AllFalseCoordinatorAuthority,
    ArtifactIntegrityError,
    CanonicalDecimal,
    FrozenModel,
)
from tos.engine.vocabulary import (
    FILL_RESULT_KINDS,
    CommitmentStep,
    EgressKnowledge,
    EgressResultKind,
    EventKind,
    EvidenceKind,
    HaltReason,
    StageAuthorityClass,
    StageOutcome,
)
from tos.ordering import OrderingEvent
from tos.rcl import CapacityState
from tos.time import HealthState, SessionContext, UncertaintyInterval

__all__ = [
    "AttemptRequest",
    "DecisionTickPayload",
    "EgressResultPayload",
    "EngineConfiguration",
    "EngineEvent",
    "EngineEvidenceRecord",
    "InstrumentKey",
    "ProvisionalReservation",
    "RegisteredStrategy",
    "SendHandoff",
    "StageRequest",
    "StageVerdict",
    "TimeAdmissionInputs",
]

#: The content-addressed attempt-request id prefix (a design/config prefix, not a safety token —
#: the ``tos.dsl`` ``prop`` / ``astrat`` precedent).
ATTEMPT_ID_PREFIX = "attempt"


def _is_wildcard_scope(value: str) -> bool:
    """Whether a scope token is a wildcard / "latest" (RFC-003 §9:279-283 dispatch mirror).

    Reuses :data:`tos.dsl.WILDCARD_TOKENS` — the shipped set the effect-free Proposal Builder
    already rejects — rather than re-authoring one (design #31 §5.1 REUSE).

    Args:
        value: The scope token.

    Returns:
        ``True`` iff the token is a wildcard / "latest" form.
    """
    if value in WILDCARD_TOKENS:
        return True
    return "*" in value or value.lower() == "latest"


class InstrumentKey(FrozenModel):
    """The structurally derived (account, instrument) dispatch key (design #31 §3.3 / D2).

    Derived from the :class:`~tos.dsl.TargetSpec` an Authored Strategy declares — never
    self-reported by a registrant (구조 파생 > 자기신고). ``account`` / ``instrument`` are
    ``str | None`` on the TargetSpec (``vocabulary.py:204-205``); a ``None`` (wildcard) scope
    cannot produce a key at all, which is why both fields here are required, non-empty, and
    wildcard-free: the dispatch-layer mirror of the RFC-003 §9:279-283 Proposal wildcard
    prohibition.
    """

    account: str
    instrument: str

    @model_validator(mode="after")
    def _scope_is_concrete_and_wildcard_free(self) -> InstrumentKey:
        """Reject an empty or wildcard scope component (fail-closed key derivation)."""
        for name in ("account", "instrument"):
            value: str = getattr(self, name)
            if not value.strip():
                raise ArtifactIntegrityError(
                    f"InstrumentKey.{name} must be a concrete non-empty scope — an unkeyable "
                    "strategy is not dispatchable (design #31 §3.3)"
                )
            if _is_wildcard_scope(value):
                raise ArtifactIntegrityError(
                    f"InstrumentKey.{name} must not be a wildcard/'latest' scope "
                    "(RFC-003 §9:279-283 dispatch-layer mirror; design #31 §3.3)"
                )
        return self


class TimeAdmissionInputs(FrozenModel):
    """The injected time coordinates the §2.3 freshness gate consumes — never a clock read.

    The engine never calls ``time`` / ``datetime``: every coordinate here rides in on the event
    (a bar timestamp for a backtest, an injected clock reading placed on the event by D-E2 / D-E4
    for paper). :mod:`tos.time` is itself clock-free (``time/__init__:7-9``), so the whole
    freshness judgement is a pure function of these injected values (design #31 §2.3).

    Absence is restrictive everywhere: a ``None`` bound, a missing session context, or a missing
    health state denies admission — an unestablished threshold is not a threshold.
    """

    #: Conservatively-estimated source-event age (negative = future-dated; never clamped).
    source_age: int | None = None
    #: The applicable injected delay-class upper bounds (ADR-002-008 §9).
    delay_bounds: tuple[int | None, ...] = ()
    #: The injected freshness threshold.
    max_age_bound: int | None = None
    #: The injected future-timestamp tolerance.
    future_tolerance: int | None = None
    #: The effective snapshot age bound (cross-continuity composition is time-owned).
    snapshot_age_bound: int | None = None
    #: The injected maximum consumer age.
    maximum_consumer_age_ms: int | None = None
    #: The injected session context (calendar/session authority determined; §2.3).
    session_context: SessionContext | None = None
    #: The reference-frame uncertainty interval for "now".
    uncertainty_interval: UncertaintyInterval | None = None
    #: The injected time health state; only ``TRUSTED`` permits new normal risk.
    health_state: HealthState | None = None


class DecisionTickPayload(FrozenModel):
    """A ``DECISION_TICK`` payload (design #31 §2.2).

    The resolved Decision Context Capsule for one bound instrument plus the injected reference
    time coordinates. The Critical Input **value surface** (a Snapshot body carrying admitted
    observations with source identity / continuity / provenance) is D-E2's to add
    (design #31 §3.2 (4)); slice #1 binds the Capsule's ``SnapshotRef`` only.
    """

    instrument_key: InstrumentKey
    capsule: DecisionContextCapsule
    time: TimeAdmissionInputs = TimeAdmissionInputs()
    #: The causal-ordering coordinates of this event (design #31 §2.1(ii)).
    reference: OrderingEvent = OrderingEvent()


class EgressResultPayload(FrozenModel):
    """An ``EGRESS_RESULT`` payload re-injected from the D-E4 send boundary (design #31 §2.2).

    A **partial fill is represented as a partial fill**: both the filled and the remaining
    magnitude are carried, and the already-filled part is never re-requested (RFC-005 §11:338-339,
    §6:176-178). The shape validator derives the fill/partial distinction from the magnitudes,
    so a producer cannot label a partial as a full fill (구조 파생 > 자기신고).

    ``attempt_id`` is a mandatory positive identity: a result is applied **only** to the exact
    attempt it names, so a late / reordered result can never transition someone else's
    reservation (design #31 §2.1(ii)).
    """

    instrument_key: InstrumentKey
    attempt_id: str
    kind: EgressResultKind
    filled_quantity: CanonicalDecimal | None = None
    remaining_quantity: CanonicalDecimal | None = None
    reference: OrderingEvent = OrderingEvent()

    @model_validator(mode="after")
    def _fill_shape_consistent(self) -> EgressResultPayload:
        """Enforce magnitude/kind consistency — partial stays partial (RFC-005 §11:338-339)."""
        if not self.attempt_id.strip():
            raise ArtifactIntegrityError(
                "EgressResultPayload.attempt_id must be concrete — a result with no attempt "
                "identity cannot be applied to any reservation (design #31 §2.1(ii))"
            )
        if self.kind not in FILL_RESULT_KINDS:
            if self.filled_quantity is not None or self.remaining_quantity is not None:
                raise ArtifactIntegrityError(
                    f"EgressResultPayload kind={self.kind} must carry no fill magnitude — only "
                    f"{sorted(FILL_RESULT_KINDS)} do (design #31 §2.2)"
                )
            return self
        if self.filled_quantity is None or self.remaining_quantity is None:
            raise ArtifactIntegrityError(
                f"EgressResultPayload kind={self.kind} requires both filled_quantity and "
                "remaining_quantity — an unquantified fill is not a fill (RFC-005 §11:338-339)"
            )
        if self.filled_quantity <= 0:
            raise ArtifactIntegrityError(
                f"EgressResultPayload kind={self.kind} requires a positive filled_quantity"
            )
        if self.remaining_quantity < 0:
            raise ArtifactIntegrityError(
                "EgressResultPayload.remaining_quantity must not be negative"
            )
        # ★ structural derivation: partial vs full follows the magnitudes, not the label.
        partial_by_magnitude = self.remaining_quantity > 0
        declared_partial = self.kind is EgressResultKind.PARTIAL_FILL
        if partial_by_magnitude != declared_partial:
            raise ArtifactIntegrityError(
                "declared fill kind contradicts the magnitudes — a remaining quantity > 0 is a "
                "PARTIAL_FILL and must not be recorded as a FULL_FILL (RFC-005 §11:338-339; "
                "구조 파생 > 자기신고)"
            )
        return self


class EngineEvent(FrozenModel):
    """One event of the closed vocabulary (design #31 §2.2).

    Exactly one payload, matching ``kind``. A kind with the wrong (or a missing) payload is
    unconstructable — the closed-vocabulary discipline applies to the payload shape too, so a
    dispatcher can never reach a ``None`` payload.
    """

    kind: EventKind
    decision_tick: DecisionTickPayload | None = None
    egress_result: EgressResultPayload | None = None

    @model_validator(mode="after")
    def _payload_matches_kind(self) -> EngineEvent:
        """Reject an event whose payload does not match its kind (fail-closed)."""
        expected = {
            EventKind.DECISION_TICK: ("decision_tick", "egress_result"),
            EventKind.EGRESS_RESULT: ("egress_result", "decision_tick"),
        }[self.kind]
        present, absent = expected
        if getattr(self, present) is None:
            raise ArtifactIntegrityError(
                f"EngineEvent kind={self.kind} requires a {present} payload"
            )
        if getattr(self, absent) is not None:
            raise ArtifactIntegrityError(
                f"EngineEvent kind={self.kind} must not carry a {absent} payload"
            )
        return self

    def payload(self) -> DecisionTickPayload | EgressResultPayload:
        """Return the single payload ``_payload_matches_kind`` guarantees is present.

        Returns:
            The ``DECISION_TICK`` or ``EGRESS_RESULT`` payload.

        Raises:
            ArtifactIntegrityError: If neither payload is present — unreachable through normal
                construction, kept as a fail-closed backstop rather than an unchecked ``None``.
        """
        if self.decision_tick is not None:
            return self.decision_tick
        if self.egress_result is not None:
            return self.egress_result
        raise ArtifactIntegrityError("EngineEvent carries no payload (fail-closed)")

    def reference(self) -> OrderingEvent:
        """Return the event's causal-ordering coordinates (design #31 §2.1(ii))."""
        return self.payload().reference

    def instrument_key(self) -> InstrumentKey:
        """Return the event's bound instrument key."""
        return self.payload().instrument_key


class StageVerdict(FrozenModel):
    """A stage's native verdict wrapped as a positive-admit judgement (design #31 §4.1).

    The sequencer advances **only** on ``outcome is StageOutcome.ADMIT``. The native sibling
    verdict is *not* stored as a typed field: the ioc / venue / are / afg / cur result enums all
    share member names (``UNKNOWN`` in five of them), so a pydantic union would smart-coerce one
    into another and mis-attribute the evidence. Instead the wrapping adapters in
    :mod:`tos.engine.adapters` record the native type name and its digest/identity **structurally**
    from the artifact they were handed (design #31 §5.2).

    ``authority_class`` labels where the stage logic came from; a
    ``NON_AUTHORITATIVE_PROVISIONAL`` verdict closes no capacity or approval EV (design #31 §4.4).
    """

    step: CommitmentStep
    outcome: StageOutcome
    authority_class: StageAuthorityClass
    #: The native sibling verdict type name, derived via ``type(artifact).__name__``.
    native_verdict_type: str | None = None
    #: The native verdict's own value (for the result enums), recorded as a plain string.
    native_verdict_value: str | None = None
    #: The native artifact's canonical digest, when it is a digest-bound artifact.
    bound_digest: str | None = None
    #: The native artifact's independent identity, when it has one (e.g. a permit id).
    bound_identity: str | None = None
    reason: str | None = None
    authority: AllFalseCoordinatorAuthority = AllFalseCoordinatorAuthority()


class AttemptRequest(FrozenModel):
    """The Coordinator's step-12 unique attempt request (ADR-002-002 §11.3:599; design #31 §4.3).

    The Execution Coordinator's **only** direct action in the whole flow. Bound to the exact
    Order Conformance Proof and the exact Action Flow Permit, and identified by a
    **content-addressed** derivation over (proof digest, permit identity, reference coordinate
    digest) — never a uuid4 or a timestamp nonce, so the same three inputs always reproduce the
    same attempt identity and replay identity is preserved (RFC-003 §10:360-363).

    Creating an attempt request grants nothing: it mutates no capacity, issues no Transmission
    Capability, and constructs no broker command (all-false authority block).
    """

    attempt_id: str
    conformance_proof_digest: str
    action_flow_permit_identity: str
    reference_coordinate_digest: str
    authority: AllFalseCoordinatorAuthority = AllFalseCoordinatorAuthority()

    @model_validator(mode="after")
    def _bindings_concrete(self) -> AttemptRequest:
        """Every binding must be concrete — an unbound attempt is unconstructable."""
        for name in (
            "attempt_id",
            "conformance_proof_digest",
            "action_flow_permit_identity",
            "reference_coordinate_digest",
        ):
            value: str = getattr(self, name)
            if not value.strip():
                raise ArtifactIntegrityError(
                    f"AttemptRequest.{name} must be concrete — a transmission attempt is bound to "
                    "the exact proof and permit (ADR-002-002 §11.3:599)"
                )
        return self


class StageRequest(FrozenModel):
    """The input one injected stage receives (design #31 §4.1 / §12-2).

    The sequencer passes the accumulating flow context; a stage returns a
    :class:`StageVerdict`. The sequencer does **not** know which of the three
    :class:`~tos.engine.vocabulary.StageAuthorityClass` sources implements the stage — that
    ignorance is exactly what makes backtest / paper / test-double parity possible (design #31
    §4.1/§12).
    """

    step: CommitmentStep
    instrument_key: InstrumentKey
    proposal: Proposal
    reference: OrderingEvent = OrderingEvent()
    prior_verdicts: tuple[StageVerdict, ...] = ()
    #: Present from step 13 onward (the Coordinator's step-12 artifact).
    attempt: AttemptRequest | None = None


class SendHandoff(FrozenModel):
    """The immediate return of the injected ``Transmit`` interface (design #31 §4.5).

    The core hands the bound attempt over and returns at once — it never blocks on the network
    (design #31 §2.1 D5). This value is an acknowledgement **of the hand-off**, not an order
    result: the order result arrives later as an ``EGRESS_RESULT`` event. Its polarity is
    positive: only ``accepted_for_transmission is True`` records an accepted hand-off. Either way
    the reservation projection is already conservatively ``POTENTIALLY_LIVE`` — the projection is
    advanced *before* the call, mirroring ADR-002-002 §11.4 step 16 ("durably records
    ``SEND_STARTED`` before the external call") and INV-005:168.
    """

    accepted_for_transmission: bool | None = None
    handoff_reference: str | None = None


class ProvisionalReservation(FrozenModel):
    """The engine's **non-authoritative** reservation projection (design #31 §2.4/§4.4).

    A projection of the ADR-002-002 §10.1 capacity-state vocabulary (:class:`~tos.rcl.CapacityState`)
    onto one (account, instrument) scope, held only so the core can observe an outstanding
    exposure. It is **not** the ledger: the real Risk Capacity Ledger is the sole serialization and
    mutation authority (RFC-002 §9.1:557; ADR-002-002 §8.1:403 linearizability, §8.3:434 fencing
    epoch, §8.4:449 CAS), and this record claims none of that.

    ``knowledge`` carries UNKNOWN as an **explicit member**, never a missing field
    (RFC-002 §12.1:1231; design #31 §2.4).
    """

    instrument_key: InstrumentKey
    capacity_state: CapacityState
    knowledge: EgressKnowledge
    proposal_id: str | None = None
    attempt_id: str | None = None
    filled_quantity: CanonicalDecimal | None = None
    remaining_quantity: CanonicalDecimal | None = None
    authority: AllFalseCoordinatorAuthority = AllFalseCoordinatorAuthority()


class RegisteredStrategy(FrozenModel):
    """One admitted Authored Strategy plus its authored configuration (design #31 §3.3/§3.5).

    ``config.bindings`` carries **authored constants only** — the band multiplier, the period, the
    thresholds the author chose. A market-derived value here would be the RFC-008 §10:327-331 /
    RFC-003 §8:236-237 relabelling prohibition (design #31 §3.2 (2)); the engine's typed admission
    partially seals that by requiring at least one capsule-sourced operand in every
    outcome-gating comparison (design #31 §3.2 (3)/§3.5).
    """

    strategy: AuthoredStrategy
    config: EvaluationConfig
    #: The key derived structurally from the strategy's own declared TargetSpec scope.
    instrument_key: InstrumentKey


class EngineConfiguration(FrozenModel):
    """Every injected scalar the engine consumes (design #31 §8 — hardcoded numbers: 0).

    | value | owner | state |
    | --- | --- | --- |
    | ``dsl_evaluation_budget_steps`` | DCE-INV-007 | key absent from VERIFICATION-PROFILE-002 — **provisional** |
    | ``max_unresolved_send_per_scope`` | limits (``MAX_unresolved_send_per_scope``) | register-fixed at 1, injected here |
    | ``canonicalization_version`` | ADR-002-018 OQ1 | ``ev-l1-provisional-0`` is non-production |
    | ``enforcement_mechanism_version`` | ADR-DEV-001 §7 | injected, recorded, never hard-coded |

    Because several of these bounds are unapproved (register §8-1) the whole slice output is
    provisional and closes no EV (design #31 §1.1/§8).
    """

    #: The symbolic DSL-evaluation budget (``budget_steps``); compared against a statically derived
    #: work count. Symbolic integer accounting — never a wall-time interrupt (design #31 §3.4).
    dsl_evaluation_budget_steps: int
    #: ``MAX_unresolved_send_per_scope`` (design #31 §4.4/§8). The engine observes the projection
    #: restrictively against it; it never creates headroom (RFC-002 §9.1:558).
    max_unresolved_send_per_scope: int
    #: The canonicalization scheme version to resolve (``tos.canonical.get_scheme``).
    canonicalization_version: str
    #: The recorded escape-checker / enforcement-mechanism version passed to ``evaluate``.
    enforcement_mechanism_version: str

    @model_validator(mode="after")
    def _bounds_non_negative(self) -> EngineConfiguration:
        """Reject a negative injected bound — an ill-formed bound is not a bound."""
        for name in ("dsl_evaluation_budget_steps", "max_unresolved_send_per_scope"):
            value: int = getattr(self, name)
            if value < 0:
                raise ArtifactIntegrityError(
                    f"EngineConfiguration.{name} must be non-negative (got {value})"
                )
        for name in ("canonicalization_version", "enforcement_mechanism_version"):
            token: str = getattr(self, name)
            if not token.strip():
                raise ArtifactIntegrityError(
                    f"EngineConfiguration.{name} must be a concrete injected version"
                )
        return self


class EngineEvidenceRecord(FrozenModel):
    """One provisional evidence record (design #31 §5.1/§12-5).

    Deliberately **not** a :class:`~tos.evidence.SafetyEvidenceEnvelope`: the full Evidence Store
    runtime (ADR-002-016) is deferred (design #31 §9-3), and issuing an envelope whose custody,
    integrity policy, and commitment chain do not exist would be exactly the over-realization the
    design forbids. This is an engine-local record consumed by an injected
    :class:`~tos.engine.sink.EvidenceSink`.

    A halt is always recorded **with** its reason, and a bounded-evaluation degradation is recorded
    under its own ``DECISION_DEGRADED`` kind so it stays distinguishable from an ordinary no-action
    (design #31 §3.4).
    """

    kind: EvidenceKind
    instrument_key: InstrumentKey | None = None
    step: CommitmentStep | None = None
    halt_reason: HaltReason | None = None
    stage_outcome: StageOutcome | None = None
    authority_class: StageAuthorityClass | None = None
    egress_result_kind: EgressResultKind | None = None
    capacity_state: CapacityState | None = None
    knowledge: EgressKnowledge | None = None
    outcome_type: str | None = None
    outcome_digest: str | None = None
    capsule_id: str | None = None
    capsule_digest: str | None = None
    strategy_version: str | None = None
    config_version: str | None = None
    attempt_id: str | None = None
    detail: str | None = None
    authority: AllFalseCoordinatorAuthority = AllFalseCoordinatorAuthority()
