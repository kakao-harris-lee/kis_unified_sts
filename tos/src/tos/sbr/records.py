"""sbr recovery models + injected inputs + the digest-bound artifacts (design #17 §2).

Every artifact is a **pydantic v2 frozen model** (``ConfigDict(frozen=True,
extra="forbid")`` via :class:`~tos.sbr._base.FrozenModel`): ``extra="forbid"`` is the
schema-level realization of "omission is restrictive" (SBR-INV-005 line 162 — no unknown /
silently-dropped field), and frozen is the record-level realization of the append-only,
current-Recovery-Generation-bound transition log (§10 line 293); there is **no** update /
delete / mutate method on any model (design #17 §2.0/§4.6). Field names use the ADR §5-§22
terms **verbatim** (spec terms = code terms, boundary design #1 §2.4).

**Numeric-bound freedom (design #17 §8; ADR §4 non-scope line 96).** SBR carries no numeric
recovery bound: every bound / age / generation value is an **injected** opaque scalar
(``int`` / ``str`` reference), null in Phase 1 and fail-closed at the consuming predicate.
Nothing numeric is hardcoded. The recovery-completeness / closure / isolation logic is over
StrEnums, booleans, and set/graph membership only.

**Two id strategies (design #17 §2.1/§3.1).**

* ``RecoveryTrigger`` / ``RecoveryInventoryCut`` / ``RecoveryObligation`` are **content-
  addressed** digest-bound records (:class:`~tos.sbr._base.DigestBoundArtifact` — the
  ``tos.evidence`` precedent, no ``f(digest)`` id derivation): the same trigger / cut /
  obligation content yields the same canonical digest.
* ``RecoverySession`` / ``RecoveryEvidencePackage`` / ``RecoveryReadinessDecision`` are
  **issued-identity** records (:class:`~tos.sbr._base.IndependentIdArtifact`,
  ``id != f(digest)``): the session / package / decision id is separately issued, so a
  same-id / different-bytes forged, re-issued, contradictory (readiness substitution §22),
  or replayed record is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``. A
  legitimate retry / revalidation / supersession is a **new** identity, never an in-place
  mutation (§10 line 293 "Retry creates a new session identity").

``RecoveryGeneration`` is **not** a class here: the monotonic recovery generation order is
REUSED from :mod:`tos.ordering` (``Ordering`` / ``OrderingEvent`` / ``compare_order``,
design #17 §3.2), and the ``recovery_generation`` scalar coordinate authority carries as a
reference-only field is an ``int`` (§0.4e). ``RecoveryBarrierState`` is an enum
(:mod:`tos.sbr.vocabulary`). Every readiness / snapshot carries an all-false
:class:`~tos.sbr._base.RecoveryAuthorityEffect` (readiness != authority, SBR-INV-003).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.sbr._base``) only; no
``shared.*``, no sibling ``tos.*`` (design #17 §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from tos.sbr._base import (
    DigestBoundArtifact,
    FrozenModel,
    IndependentIdArtifact,
    RecoveryAuthorityEffect,
)
from tos.sbr.vocabulary import (
    ObligationResult,
    OwnerStatus,
    ReadinessVerdict,
    SessionState,
)

__all__ = [
    # injected inputs / value models
    "RecoveryBarrierPolicy",
    "RecoveryScope",
    "IsolationFacts",
    "BrokerReadSequence",
    "RecoveryObligationGraph",
    "OwnerStatus",
    # content-addressed digest-bound artifacts
    "RecoveryTrigger",
    "RecoveryInventoryCut",
    "RecoveryObligation",
    # issued-identity artifacts
    "RecoverySession",
    "RecoveryEvidencePackage",
    "RecoveryReadinessDecision",
    # all-false authority
    "RecoveryAuthorityEffect",
]


# ===========================================================================
# Injected inputs + value models (plain frozen)
# ===========================================================================


class RecoveryBarrierPolicy(FrozenModel):
    """The injected Recovery Barrier Policy coordinate (ADR-002-017 §8 line 112; §5.3).

    The policy is a **separately-governed** artifact (spg Safety Config Bundle governance,
    §8.3) — SBR is only its **consumer** and imports / parses **nothing** (YAML is the
    harness's concern, design #17 §0.3). It is pinned here by injected id / generation /
    digest scalars (VP-002 ``recovery_barrier_policy_id`` / ``_generation`` / ``_digest``,
    all TBD/null in Phase 1, §8.1) plus the **required dependency kinds** the policy declares
    an inventory cut must cover. An **empty** ``required_dependency_kinds`` cannot establish
    completeness — a cut proving "complete over nothing" is vacuous, so
    :func:`~tos.sbr.predicates.recovery_inventory_complete` fails closed on it (design #17
    §4.7; the afg ``scope_graph_complete`` non-empty-required-set precedent).
    """

    policy_id: str | None = None
    policy_generation: int | None = None
    policy_digest: str | None = None
    #: The dependency kinds the policy declares an inventory cut MUST cover (§12; empty =>
    #: fail-closed at the consuming predicate — a vacuous completeness is not completeness).
    required_dependency_kinds: frozenset[str] = frozenset()


class RecoveryScope(FrozenModel):
    """A recovery scope descriptor (ADR-002-017 §8 / §16 / §17).

    A scope the recovery orchestration reasons over — its identity plus the scopes it
    positively excludes (for a ``READY_RESTRICTED`` candidate, §17). SBR carries the scope
    **identity** only; the concrete dependency-graph semantics and the trigger classifier are
    Phase-0 injected (§9.2). A ``None`` ``scope_id`` is UNKNOWN — never "the whole account by
    default" and never "nothing" (fail-closed at the consuming predicate).
    """

    scope_id: str | None = None
    #: The scopes this (restricted) candidate positively excludes (§16 line 420).
    excluded_scopes: frozenset[str] = frozenset()


class IsolationFacts(FrozenModel):
    """The eight §17 partial-recovery isolation proofs (ADR-002-017 §17 line 438-445).

    §17 line 438-445 enumerates the **eight** conditions that must **all** be positively
    proven before a ``READY_RESTRICTED`` verdict is admissible; §17 line 447: "Logical
    strategy separation, different UI labels, separate recovery tickets, distinct process
    instances, or unused nominal capacity do not prove isolation." Every field is a positive-
    proof flag (``bool | None``): a ``None`` / ``False`` is **not** proven, so a label /
    ticket / instance can never set a flag ``True`` — the caller injects only positively-
    evidenced flags (fail-closed, SBR-INV-008 line 174). :meth:`all_proven` requires every
    one to be positively ``True``.
    """

    #: (1) distinct RCL Capacity Domain (or conservative aggregate) — no cross-scope reuse.
    distinct_capacity_domain: bool | None = None
    #: (2) broker session / credential / route / rate-limit / account-semantics isolated.
    broker_session_isolated: bool | None = None
    #: (3) margin / collateral / cash / settlement / financing / concentration safe.
    margin_collateral_safe: bool | None = None
    #: (4) no protective order / lease / resource / arbiter / replacement boundary crossing.
    no_protective_boundary_crossing: bool | None = None
    #: (5) config / authority / time / evidence / deployment / identity / failure-domain
    #: compatible and current.
    config_authority_time_compatible: bool | None = None
    #: (6) external / manual / non-trade activity unmappable into the candidate scope.
    external_non_trade_unmappable: bool | None = None
    #: (7) final egress can enforce the exact restricted scope + current generation.
    final_egress_scope_enforceable: bool | None = None
    #: (8) Hard Safety Envelope satisfied under the union of resolved + unresolved.
    hard_safety_envelope_satisfied: bool | None = None

    def all_proven(self) -> bool:
        """Whether all eight isolation conditions are positively ``True`` (§17 line 438-445).

        ``True`` **only** when every one of the eight flags is positively ``True``; any
        ``None`` (unknown) / ``False`` (disproven) fails closed. There is no partial credit —
        a single unproven condition drops the candidate to a broader ``NOT_READY`` (§17 line
        447; the ``ScopeIndependenceEvidence.is_independent`` afg precedent).

        Returns:
            ``True`` iff all eight isolation conditions are positively evidenced.
        """
        return (
            self.distinct_capacity_domain is True
            and self.broker_session_isolated is True
            and self.margin_collateral_safe is True
            and self.no_protective_boundary_crossing is True
            and self.config_authority_time_compatible is True
            and self.external_non_trade_unmappable is True
            and self.final_egress_scope_enforceable is True
            and self.hard_safety_envelope_satisfied is True
        )


class BrokerReadSequence(FrozenModel):
    """The observed broker read sequence for a non-atomic inventory (ADR §12 line 333; §14).

    SBR-INV-007 line 170 verbatim: "One broker query, flat position, cache agreement, absent
    page result, missing ACK, or cancel ACK cannot establish completeness, non-acceptance,
    Final Quantity Proof, or capacity release." §12 line 333: "Equality between two reads does
    not prove that an unobservable event did not occur." So completeness requires **bounded
    convergence** (re-read until a field-specific proof is stable) with any intervening event
    reflected — not a single optimistic read. SBR does **not** own the broker page / cursor
    protocol or the Final Quantity Proof (+Broker / recon, §3.5); it carries only the
    conservatism witnesses. The documentary single-read flags record which optimistic basis
    was observed; the two gating witnesses (:attr:`bounded_convergence_proven`,
    :attr:`field_specific_proof_stable`) are what a completeness claim must positively carry.
    """

    #: Documentary — the optimistic bases §12 line 333 / SBR-INV-007 forbids as completeness.
    single_read_only: bool | None = None
    flat_position_only: bool | None = None
    cache_agreement_only: bool | None = None
    absent_page_only: bool | None = None
    missing_ack: bool | None = None
    cancel_ack_only: bool | None = None
    #: Positive witness: convergence bounded (re-read until stable), not a single read.
    bounded_convergence_proven: bool | None = None
    #: Positive witness: the field-specific proof is stable across reads (§12 line 333).
    field_specific_proof_stable: bool | None = None
    #: Positive witness: any intervening unobservable event was reflected (§12 line 333).
    intervening_events_reflected: bool | None = None


# ===========================================================================
# Content-addressed digest-bound artifacts (DigestBoundArtifact)
# ===========================================================================


class RecoveryTrigger(DigestBoundArtifact):
    """A content-addressed recovery trigger (ADR-002-017 §5.1 line 104; §9 line 261).

    §9 line 261: a trigger has "unique trigger identity and conservative initial scope". A
    :class:`~tos.sbr._base.DigestBoundArtifact` — content-addressed, so the same trigger
    content yields the same canonical digest (design #17 §2.1). The ``trigger_class`` is an
    **injected** classifier token (the classifier is Phase-0, §2.2(6)/§27 q1) — SBR consumes
    the classification, it does not re-classify. ``_REQUIRED_COVERED`` lists the structural
    trigger identity only; the concrete scope semantics are Phase-0 injected, so a trigger is
    ISSUED-reachable under Phase-1 null bounds. Non-transmitting, non-enforcing (§4.6).
    """

    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("trigger_id",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "trigger_id",
            "trigger_class",
            "initial_scope",
            "recovery_generation",
        }
    )

    trigger_id: str | None = None
    #: The injected trigger-class classifier token (Phase-0 classifier, §2.2(6)).
    trigger_class: str | None = None
    initial_scope: str | None = None
    recovery_generation: int | None = None


class RecoveryInventoryCut(DigestBoundArtifact):
    """A bounded, versioned, conservative Recovery Inventory Cut (ADR-002-017 §12 line 318-332).

    §12 line 128 verbatim: the cut is "conservative evidence, not an assertion that external
    state was atomically frozen." A :class:`~tos.sbr._base.DigestBoundArtifact` — content-
    addressed (same revision-set / observation => same cut, design #17 §2.1). The concrete
    per-field values (each order / attempt / fill / position / capacity / protective / …
    dependency) are **judged by siblings** (orthostate state, recon confidence, rcl capacity,
    protective classification — §3.5); this model carries the **completeness** coordinates so
    :func:`~tos.sbr.predicates.recovery_inventory_complete` can decide only whether any
    required dependency is **omitted or unbounded** (SBR-INV-005 line 162). The many §12
    line 318-331 dependency dimensions are represented as **kind sets** (required / observed /
    unbounded) rather than re-modelling every sibling's field — SBR is the completeness
    orchestrator, not the per-dimension judge (design #17 §5.1). The monotonic-clock
    coordinate is opaque and never compared across continuities (§12 line 335); a time-
    ambiguous cut stays non-permissive.
    """

    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "session_id",
        "recovery_generation",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "session_id",
            "recovery_generation",
            "scope_digest",
            "trigger_digest",
            "policy_digest",
            "dependency_graph_digest",
            "time_start",
            "time_end",
            "time_uncertainty",
            "time_ambiguous",
            "required_dependency_kinds",
            "observed_dependency_kinds",
            "unbounded_dependency_kinds",
            "observed_events",
            "unobserved_window_assumptions_present",
            "max_adverse_bounds_present",
            "required_repeat_observations_met",
        }
    )

    session_id: str | None = None
    recovery_generation: int | None = None
    scope_digest: str | None = None
    trigger_digest: str | None = None
    policy_digest: str | None = None
    dependency_graph_digest: str | None = None
    #: Opaque injected time coordinates (clock-free — never subtracted, §8 / §12 line 335).
    time_start: str | None = None
    time_end: str | None = None
    time_uncertainty: str | None = None
    #: Whether the cut's time is ambiguous (True/None => non-permissive, §12 line 335).
    time_ambiguous: bool | None = None
    #: The dependency kinds this cut MUST cover (from the policy + trigger scope, §12).
    required_dependency_kinds: frozenset[str] = frozenset()
    #: The dependency kinds positively observed present in the cut (§12 line 318-331).
    observed_dependency_kinds: frozenset[str] = frozenset()
    #: The dependency kinds present but **unbounded** (unbounded => incomplete, §12 line 162).
    unbounded_dependency_kinds: frozenset[str] = frozenset()
    #: The events observed during the cut (§12 line 331) — conservative evidence, not a freeze.
    observed_events: tuple[str, ...] = ()
    #: §12 line 332 — the unobserved-window assumptions are present (positive witness).
    unobserved_window_assumptions_present: bool | None = None
    #: §12 line 332 — the max-adverse bounds for the unobserved window are present.
    max_adverse_bounds_present: bool | None = None
    #: §12 line 332 — the required repeat observations were met (positive witness).
    required_repeat_observations_met: bool | None = None


class RecoveryObligation(DigestBoundArtifact):
    """One typed recovery obligation with owner, scope, and evidence rule (§13 line 343-350).

    §5.8 line 130: "one mandatory, typed predicate with owner, scope, evidence rule." A
    :class:`~tos.sbr._base.DigestBoundArtifact` — content-addressed obligation spec (design
    #17 §2.1). The obligation's ``result`` is produced by the **owning sibling's** predicate
    (§3.5); SBR folds it into the graph closure, it does not re-author the per-obligation
    judgement. The prerequisite graph is closed by
    :func:`~tos.sbr.predicates.obligation_graph_closed`. **Self-satisfy is forbidden** (§13
    line 372): an obligation requiring independent review
    (``independent_review_required is True``) may not be marked ``SATISFIED`` by its proposing
    owner — closure requires ``independent_review_satisfied is True``.
    """

    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("obligation_id",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "obligation_id",
            "obligation_type",
            "owner",
            "scope",
            "hazard",
            "priority",
            "prerequisite_ids",
            "acceptable_results",
            "result",
            "independent_review_required",
            "independent_review_satisfied",
            "source_digests",
            "proof_rule_digest",
            "inventory_cut_position",
        }
    )

    obligation_id: str | None = None
    obligation_type: str | None = None
    owner: str | None = None
    scope: str | None = None
    hazard: str | None = None
    priority: str | None = None
    #: The prerequisite obligation ids (the closure input, §13 line 344).
    prerequisite_ids: frozenset[str] = frozenset()
    #: The result classes that pass this obligation (§13 line 346).
    acceptable_results: frozenset[ObligationResult] = frozenset()
    #: The obligation's terminal result — produced by the owning sibling's predicate (§3.5).
    result: ObligationResult | None = None
    #: §13 line 372 — independent evidence is required to satisfy this obligation.
    independent_review_required: bool | None = None
    #: §13 line 372 — the required independent review was positively completed (not self-satisfied).
    independent_review_satisfied: bool | None = None
    source_digests: tuple[str, ...] = ()
    proof_rule_digest: str | None = None
    inventory_cut_position: str | None = None


class RecoveryObligationGraph(FrozenModel):
    """The recovery obligation graph — a container over the obligation set (§13 line 339-374).

    A thin frozen container the runtime assembles from the recovery obligation registry
    (Phase-0, §27 q1). :func:`~tos.sbr.predicates.obligation_graph_closed` decides closure +
    acyclicity over :meth:`obligation_set`. Carried as a **tuple** (deterministic) with a
    ``frozenset`` view for the predicate; a duplicate-id tuple is caught as not-closed (the
    graph does not silently de-duplicate).
    """

    obligations: tuple[RecoveryObligation, ...] = ()

    def obligation_set(self) -> frozenset[RecoveryObligation]:
        """The obligation set for the closure predicate (frozen models are hashable)."""
        return frozenset(self.obligations)


# ===========================================================================
# Issued-identity artifacts (IndependentIdArtifact — id ⊥ digest)
# ===========================================================================


class RecoverySession(IndependentIdArtifact):
    """An immutable-identity recovery workflow instance (ADR-002-017 §5.4 line 114; §10).

    §5.4 line 114: "immutable-identity workflow instance"; §10 line 293: "Retry creates a new
    session identity" — the transition log is append-only and every transition binds the
    current Recovery Generation. An :class:`~tos.sbr._base.IndependentIdArtifact`
    (``id != f(digest)``, design #17 §2.1): the session id is separately issued so a same-id /
    different-bytes forged or replayed session is a detectable ``classify_record_pair``
    ``CRITICAL_CONFLICT``, and a retry is a **new** id — an old (possibly terminal) session is
    never re-activated (:func:`~tos.sbr.state.session_transition_allowed`). Carries an all-
    false :class:`~tos.sbr._base.RecoveryAuthorityEffect` (a session creates no authority,
    SBR-INV-003).
    """

    _ID_FIELD: ClassVar[str] = "session_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "recovery_generation",
        "state",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "recovery_generation",
            "trigger_digest",
            "state",
            "scope",
            "authority_effect",
        }
    )

    session_id: str | None = None
    recovery_generation: int | None = None
    trigger_digest: str | None = None
    state: SessionState | None = None
    scope: str | None = None
    authority_effect: RecoveryAuthorityEffect = RecoveryAuthorityEffect()


class RecoveryEvidencePackage(IndependentIdArtifact):
    """An immutable canonical recovery evidence package (ADR-002-017 §9 line 134; §16 line 416).

    §9 line 134: an "immutable canonical manifest"; §16 line 416: the package "digests" the
    recovery inputs. An :class:`~tos.sbr._base.IndependentIdArtifact` (``id != f(digest)``):
    the session issues the package id and the canonical manifest digest is separate, so a
    package substitution (same id, different bytes) is a detectable ``CRITICAL_CONFLICT``. The
    package binds the inventory-cut / obligation-set / decision digests plus the input
    manifest digests; SBR authors the **record substrate** only — evidence custody and
    deterministic replay are ADR-002-016 runtime (§0.2). Carries an all-false authority effect.
    """

    _ID_FIELD: ClassVar[str] = "package_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("recovery_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "session_id",
            "recovery_generation",
            "inventory_cut_digest",
            "obligation_set_digest",
            "decision_digest",
            "manifest_digests",
            "authority_effect",
        }
    )

    package_id: str | None = None
    session_id: str | None = None
    recovery_generation: int | None = None
    inventory_cut_digest: str | None = None
    obligation_set_digest: str | None = None
    decision_digest: str | None = None
    #: The immutable manifest input digests (self-excludes its own digest, §2.3).
    manifest_digests: tuple[str, ...] = ()
    authority_effect: RecoveryAuthorityEffect = RecoveryAuthorityEffect()


class RecoveryReadinessDecision(IndependentIdArtifact):
    """A non-authorizing recovery readiness decision (ADR-002-017 §16 line 416-424).

    §16 line 416: "decision identity, canonical digest, issuer"; §16 line 424: the decision is
    explicitly **non-authorizing** (all-false authority effect). An
    :class:`~tos.sbr._base.IndependentIdArtifact` (``id != f(digest)``, design #17 §2.1): the
    issuer issues the ``decision_id`` and the canonical digest is separate, so a readiness
    substitution / stale-decision replay (same id, different bytes — §22 line 554) is a
    detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``. The ``verdict`` is the SBR-owned
    :class:`~tos.sbr.vocabulary.ReadinessVerdict`; the generation vector (RCL / authority /
    HALT / profile / broker / deployment / release / post-trade / egress / evidence / human)
    is composed of **injected upstream scalars** (§8.2), each owned by its sibling ADR — SBR
    binds them as reference coordinates, it does not enforce their composition (that is EV-L3
    final-egress runtime). ``NOT_READY`` cannot be manually promoted (§16 line 430); the
    truthy-sentinel seal makes ``verdict`` truthy-untestable, so a consumer's ``if verdict:``
    misuse raises rather than fails open.
    """

    _ID_FIELD: ClassVar[str] = "decision_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "session_id",
        "recovery_generation",
        "verdict",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "issuer",
            "session_id",
            "recovery_generation",
            "policy_digest",
            "scope",
            "requested_rearm_scope",
            "package_digest",
            "inventory_cut_digest",
            "obligation_set_digest",
            "all_results",
            "verdict",
            "max_safe_scope",
            "excluded_scopes",
            "issue_time",
            "max_age",
            "expiry",
            "invalidation_conditions",
            "authority_effect",
        }
    )

    decision_id: str | None = None
    issuer: str | None = None
    session_id: str | None = None
    recovery_generation: int | None = None
    policy_digest: str | None = None
    scope: str | None = None
    requested_rearm_scope: str | None = None
    package_digest: str | None = None
    inventory_cut_digest: str | None = None
    obligation_set_digest: str | None = None
    #: The obligation results folded into this decision (all must be SATISFIED for READY).
    all_results: tuple[ObligationResult, ...] = ()
    verdict: ReadinessVerdict | None = None
    max_safe_scope: str | None = None
    excluded_scopes: frozenset[str] = frozenset()
    #: Opaque injected age / expiry coordinates (clock-free, §8; null in Phase 1).
    issue_time: str | None = None
    max_age: str | None = None
    expiry: str | None = None
    invalidation_conditions: tuple[str, ...] = ()
    #: §16 line 424 — the decision creates no authority (all-false, SBR-INV-003).
    authority_effect: RecoveryAuthorityEffect = RecoveryAuthorityEffect()
