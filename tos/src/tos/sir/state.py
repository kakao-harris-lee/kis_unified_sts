"""sir injected inputs + value models + Incident Generation ordering REUSE (design #28 §2.1/§3.2).

Two roles:

* **value / injected input models (design #28 §2.1/§2.4)** — the §5.2 Safety Signal
  (:class:`SafetySignal`), the §5.5/§10 per-incident active-set element (:class:`ActiveSetMember`), the
  §5.6 22-dimension dependency closure (:class:`IncidentDependencyClosure`), the §10 exact scope
  (:class:`IncidentScope`), the §5.8/§12 controlled-shutdown section (:class:`ControlledShutdownProcedure`
  and its :class:`ShutdownStep`), the §5.11 ongoing obligation (:class:`OngoingSafetyObligation`), the
  §18 line 472 communication honesty view (:class:`CommunicationHonestyLadder`), the §18 line 474
  analysis claim (:class:`AnalysisClaim`), the §7/§20 item 10 closure independence ladder
  (:class:`ClosureIndependenceLadder`), the §8 classification input
  (:class:`IncidentClassificationInput`), the §11 containment action (:class:`ContainmentAction`), and
  the three §6 substrate carriers (:class:`IncidentUnknownState` — §13/§16 UNKNOWN axes;
  :class:`BrokerFinalityTokens` — §13 broker-finality tokens; :class:`RecoveryRevivalInputs` — §21
  non-revival axes; :class:`ExternalActivityClaim` — §15 external/manual activity). Every one is a
  **pydantic v2 frozen model** (``frozen=True, extra="forbid"`` via :class:`~tos.sir._base.FrozenModel`):
  ``extra="forbid"`` is the schema-level "omission is restrictive" and frozen is the append-only
  realization — there is **no** update / delete / mutate method on any model (design #28 §2.3/§4.1).

* **Incident Generation order (design #28 §3.2 ordering REUSE)** — :func:`incident_generation_advances`
  and :func:`max_incident_generation` REUSE ``tos.ordering.compare_order`` (no re-authored order) for
  the §5.4 Incident Generation monotonic fence ("A monotonic generation fencing earlier incident scope,
  state, plans, closure eligibility, recovery handoff, configuration requests, authority requests, and
  consumers") and the §16 line 427 "absence of a newer declaration, scope expansion ... ordered before
  the claim/send boundary" floor. sir owns the fence *meaning* (a newer Incident Generation fences an
  earlier scope / plan / closure eligibility); ordering only carries the monotonic order. **A wall clock
  never orders — sir reads no clock**: an Incident Generation is an ordering identity, not wall-clock
  (design #28 §3.2/§8), so this package is clock-free (the ``MAX_incident_*_ms`` wall-clock ages are
  **injected** secondary +Security / INSTANCE bounds, design #28 §8/§10.3-4).

**Numeric-bound freedom (design #28 §8; ADR §28 item 12).** sir carries no numeric size / duration /
threshold constant: ``B_incident_signal_to_restriction`` / ``B_incident_restriction_to_egress`` /
``B_incident_scope_expansion`` / ``B_incident_generation_fence`` /
``B_controlled_shutdown_hard_fence`` / ``MAX_incident_status_age_ms`` /
``MAX_incident_containment_plan_age_ms`` / ``MAX_incident_closure_evidence_age_ms`` are all **injected**
opaque Profile-INSTANCE scalars, null in Phase 1 and fail-closed at the consuming predicate.

**Injected-verdict discipline (design #28 §3.5 duplication boundary).** Every sibling
owner's produced verdict / generation / digest is an **injected** coordinate: sir does **not** re-decide
any owner's business content (sbr Recovery Barrier / Recovery Session, hag effective-principal collapse
+ quorum + the Governed Single-Operator Re-Arm Variant, spg Safety Incident Policy activation + Hard
Safety Envelope, evidence custody / causal chain / gap, liveauth Live Authorization, rcl capacity
mutation + worst-credible effect, egress final-egress enforcement, cur Active Currentness Vector,
authority Safety Authority / HALT, protective Protective Action Controller / Cancellation Arbiter, time
Trustworthy Time, rlp demotion / production scope, wdr Non-Waivable Boundary, and the sibling-owned -028 /
-029 handoff and compromise coordinates) — it consumes the produced fact and judges only the
declaration / scope / honesty / closure structure.

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.sir.*`` only; no ``shared.*``, no other
sibling ``tos.*`` (design #28 §0.3). Clock-free.

Regime tag: restrictive-declaration / exact-scope-combined / evidence-honesty predicate substrate only;
closes **no** SIR-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.sir._base import FrozenModel
from tos.sir.vocabulary import (
    ClosureDimension,
    CommunicationAssertionKind,
    IncidentLifecycleState,
    SignalClassificationClass,
)

__all__ = [
    "SafetySignal",
    "ActiveSetMember",
    "IncidentDependencyClosure",
    "IncidentScope",
    "ShutdownStep",
    "ControlledShutdownProcedure",
    "OngoingSafetyObligation",
    "CommunicationHonestyLadder",
    "AnalysisClaim",
    "ClosureIndependenceLadder",
    "IncidentClassificationInput",
    "ContainmentAction",
    "IncidentUnknownState",
    "BrokerFinalityTokens",
    "RecoveryRevivalInputs",
    "ExternalActivityClaim",
    "incident_generation_advances",
    "max_incident_generation",
]


class SafetySignal(FrozenModel):
    """One Safety Signal view (ADR-002-027 §5.2 line 110; design #28 §2.4).

    §5.2 verbatim: "An **authenticated observation or conservative inference** that a safety invariant,
    authority boundary, economic-state assumption, broker contract, protective obligation, currentness
    fact, evidence path, or operational gate may be violated, unavailable, stale, bypassed, or
    unverifiable." The "**or**" is load-bearing (design #28 §5.1 conjunct 3, M6): an unauthenticated
    *conservative inference* is still a Safety Signal — it is classified
    ``UNESTABLISHED_SCOPE_SEVERITY`` and expands to the greatest credible scope (§8 line 257), never
    dismissed. ``is_authenticated`` is therefore **not** an AND gate of the declaration predicate.

    Polarity (design #28 §4.3): ``is_material`` / ``is_authenticated`` are **positive** (only ``is
    True`` admits); ``scope_establishable`` is **negative** — ``is False`` (or an unknown ``None``)
    means the scope cannot yet be established conservatively, which per §8 line 257 makes the signal a
    declaration subject in the greatest credible scope.

    ``trustworthy_time_basis`` is an **injected** ``tos.time`` coordinate (§8 step 1 "the signal is
    preserved with source identity and trustworthy-time evidence") — an opaque reference string, never
    a wall clock read here (design #28 §3.5; sir is clock-free).
    """

    signal_id: str | None = None
    source_identity: str | None = None
    #: Injected ADR-002-008 Trustworthy Time reference (§8 step 1) — opaque; sir reads no clock.
    trustworthy_time_basis: str | None = None
    classification: SignalClassificationClass | None = None
    #: Positive polarity (§8 "On a material signal") — only ``is True`` admits.
    is_material: bool | None = None
    #: Positive polarity (§5.2 "authenticated observation") — **not** an AND gate (M6 disjunction).
    is_authenticated: bool | None = None
    #: Negative polarity (§8 line 257) — ``is False`` / ``None`` ⇒ unestablished ⇒ greatest credible.
    scope_establishable: bool | None = None


class ActiveSetMember(FrozenModel):
    """One member of the Active Safety Incident Set (ADR-002-027 §5.5/§10; design #28 §2.4).

    The per-incident **structural** element that replaced design #28 v1.0's parallel
    ``member_incidents`` / ``member_digests`` tuples (v1.1 C2-2): a parallel-tuple pair admits a
    length-mismatch / order-skew defect class that a per-member structure removes outright. The
    :class:`~tos.sir.records.ActiveSafetyIncidentSet` validator additionally seals (i) no duplicate
    ``incident_id``, (ii) no dangling ``parent_id``, (iii) ``shared_cause_ids`` ⊆ the set's
    ``shared_dependencies``.

    ``no_favorable_subset`` (design #28 §5.2 conjunct 3) **derives** ``open_parent_present`` /
    ``open_child_present`` / ``shared_cause_unresolved`` / ``common_mode_present`` from these fields —
    structural derivation, never a self-reported flag (design #28 §14 "구조 파생 > 자기신고").

    ``resolved`` is consumed with the **positive** gate ``is True`` (design #28 §5.2 conjunct 3
    verbatim: "``resolved is not True`` ⇒ ``shared_cause_unresolved=True``"), so an unknown ``None``
    converges to *unresolved* — the fail-closed direction of §10 line 314 "Unknown dependency closure
    means the broader plausible set remains contained".
    """

    incident_id: str | None = None
    incident_digest: str | None = None
    lifecycle_state: IncidentLifecycleState | None = None
    parent_id: str | None = None
    shared_cause_ids: frozenset[str] = frozenset()
    #: Positive polarity (§5.2 conjunct 3) — only ``is True`` counts a shared cause as resolved.
    resolved: bool | None = None


class IncidentDependencyClosure(FrozenModel):
    """The Incident Dependency Closure (ADR-002-027 §5.6 line 130; design #28 §2.4/§5.2).

    §5.6 verbatim: "Every Safety Cell, Capacity Domain, legal portfolio, account, broker, venue,
    instrument, strategy, order, position, commitment, protection, credential, route, session,
    generation, component, artifact, failure domain, evidence path, external activity, and downstream
    consumer that may be affected by the signal or response." ``present_dimensions`` carries the
    :class:`~tos.sir.vocabulary.ClosureDimension` members the closure actually represents;
    ``affected_ids_by_dimension`` carries the affected coordinates per dimension (an **explicitly
    empty** entry is a represented dimension with no affected coordinate — an *absent* entry is an
    unrepresented dimension and denies, design #28 §5.2 conjunct 4 "미표현 차원 ⇒ incomplete").

    Polarity (design #28 §4.3): ``closure_unknown`` is **negative** — only ``is False`` clears (§10 line
    314 "Unknown dependency closure means the broader plausible set remains contained");
    ``dependency_closure_complete`` is **positive** — only ``is True`` admits. The positive flag is an
    injected runtime/+Security completeness proof and is consumed **in conjunction with** the structural
    22-dimension derivation, never as a substitute for it (defence in depth; the flag alone can never
    admit — :func:`~tos.sir.predicates.dependency_closure_complete`).
    """

    present_dimensions: frozenset[ClosureDimension] = frozenset()
    affected_ids_by_dimension: dict[ClosureDimension, frozenset[str]] = Field(
        default_factory=dict
    )
    #: Negative polarity (§10 line 314) — only ``is False`` clears; ``True`` / ``None`` ⇒ contained.
    closure_unknown: bool | None = None
    #: Positive polarity (design #28 §4.3) — an injected completeness proof, never a substitute for
    #: the structural 22-dimension derivation.
    dependency_closure_complete: bool | None = None


class IncidentScope(FrozenModel):
    """The exact greatest-credible incident scope (ADR-002-027 §10 line 303; design #28 §2.4).

    §10 line 303 verbatim: "Incident scope SHALL be policy-owned and include every possibly affected
    upstream, downstream, shared, and external dependency. The affected component **cannot self-exempt**
    itself or declare a failure local." §8 line 269: "A low-severity label cannot override a Critical
    invariant or make unknown scope narrow."

    Polarity (design #28 §4.3): ``self_exempted`` and ``wildcard_or_narrowed`` are both **negative** —
    only ``is False`` clears; ``True`` / an unknown ``None`` denies (SIR-INV-003 line 166 "Unknown,
    stale, conflicting, incomplete, wildcard, patched, or self-selected scope expands containment; it
    never narrows permission").
    """

    scope_by_dimension: dict[ClosureDimension, frozenset[str]] = Field(
        default_factory=dict
    )
    #: Negative polarity (§10 line 303) — only ``is False`` clears.
    self_exempted: bool | None = None
    #: Negative polarity (§8 line 269 / SIR-INV-003) — only ``is False`` clears.
    wildcard_or_narrowed: bool | None = None


class ShutdownStep(FrozenModel):
    """One ordered controlled-shutdown step (ADR-002-027 §12 line 343-352; design #28 §2.4).

    ``step_kind`` is one of the transcribed
    :data:`~tos.sir.vocabulary.SHUTDOWN_STEP_KINDS` 10-step labels; ``step_ordinal`` is its position.
    Polarity (design #28 §4.3): ``completed`` is **negative** — §17 line 451 "Shutdown step result
    ambiguous | **assume not completed where that is safer**", so an unknown ``None`` is treated as not
    completed. The *ordering proof* itself is L3 runtime (design #28 §6b); L1 judges only structure.
    """

    step_ordinal: int | None = None
    step_kind: str | None = None
    #: Negative polarity (§17 line 451 "assume not completed where that is safer").
    completed: bool | None = None


class ControlledShutdownProcedure(FrozenModel):
    """The ordered non-authorizing Controlled Shutdown Procedure (ADR-002-027 §5.8/§12; design #28 §2.4).

    §5.8 verbatim: "The ordered non-authorizing section of an Incident Containment Plan that defines how
    new economic action is denied and components are fenced or stopped while required protection, RCL,
    reconciliation, evidence, currentness, notification, and external-obligation functions remain safe."
    A **value** model (no independent id) carried by
    :class:`~tos.sir.records.IncidentContainmentPlan`.

    Polarity (design #28 §4.3): ``deny_before_stop`` is **positive** — §12 step 1 "latch or commit
    denial of new risk **before** stopping ordinary producers", so only ``is True`` admits.
    ``prohibited`` declares the §12 line 354-362 "Shutdown SHALL NOT" set;
    :func:`~tos.sir.predicates.controlled_shutdown_not_broker_finality` floors it to at least
    :data:`~tos.sir.vocabulary.SHUTDOWN_PROHIBITIONS` (more is allowed, fewer never).

    This model **proves nothing about the broker**: SIR-INV-007 line 182 "Process stop, scale-to-zero,
    disconnect, session close, credential revocation, route removal, or deployment shutdown does not
    prove non-acceptance, Final Quantity, absence of fills, or absence of external economic effect."
    """

    ordered_steps: tuple[ShutdownStep, ...] = ()
    #: Positive polarity (§12 step 1) — only ``is True`` admits.
    deny_before_stop: bool | None = None
    #: The §12 step 7 functions that must remain safe (HALT / egress latch / reconciliation / time /
    #: evidence / notification / recovery) — structural labels only.
    preserved_functions: tuple[str, ...] = ()
    hard_fenced_paths: tuple[str, ...] = ()
    #: The declared §12 line 354-362 prohibitions (floored, never capped, by the predicate).
    prohibited: frozenset[str] = frozenset()


class OngoingSafetyObligation(FrozenModel):
    """An Ongoing Safety Obligation (ADR-002-027 §5.11 line 150; design #28 §2.4).

    §5.11 verbatim: "An unresolved position, potentially-live order, unknown broker effect, protection
    duty, capacity commitment, reconciliation gap, evidence gap, external activity, settlement duty,
    recovery task, or monitoring/fencing duty that **survives incident workflow state**." ``kind`` is a
    free-form structural label from that catalogue (never an enum gate).

    Polarity (design #28 §4.3 / operative §6.4 + §6.8b items 4/9): ``resolved`` and
    ``transferred_with_owner_and_evidence`` are both consumed with the **positive** gate ``is True`` —
    an obligation survives shutdown unless it is *positively* resolved or *positively* transferred with
    owner and evidence (§12 step 5 / §14 line 396 "failed protection is recorded as an ongoing
    obligation"; §20 item 9 "recovery obligations are transferred to ADR-002-017 behind a closed
    Recovery Barrier"). An unknown ``None`` therefore converges to *unresolved and untransferred* — the
    fail-closed direction of SIR-INV-008.
    """

    obligation_id: str | None = None
    kind: str | None = None
    #: Positive polarity — only ``is True`` counts the obligation as resolved.
    resolved: bool | None = None
    #: Positive polarity (§20 item 4/9) — only ``is True`` counts a deliberate transfer.
    transferred_with_owner_and_evidence: bool | None = None


class CommunicationHonestyLadder(FrozenModel):
    """One communication's honesty view (ADR-002-027 §18 line 472; design #28 §2.4/§5.3).

    §18 line 472 verbatim: "Communications SHALL **distinguish** observed fact, conservative assumption,
    unresolved UNKNOWN, planned action, authorized action, transmitted attempt, broker evidence,
    verified result, and administrative decision. A message acknowledgement is **never** an enforcement
    acknowledgement." ``assertion_kind`` is what the communication *is*; ``claimed_as`` is what it is
    *labelled as* — a mismatch is a distinction violation (design #28 §5.3 conjunct 2). The ADR states a
    **distinction obligation, not a strength total order**; any "which kind outranks which" judgement is
    policy-owned and Phase-0 (M7).

    Polarity (design #28 §4.3): ``is_message_ack`` is **positive** (a marker — ``is True`` arms the
    enforcement-ack gate); ``treated_as_enforcement_ack`` is **negative** — only ``is False`` clears, so
    an unknown ``None`` on a message acknowledgement denies.
    """

    assertion_kind: CommunicationAssertionKind | None = None
    #: What the communication is labelled as, when that differs from ``assertion_kind``.
    claimed_as: CommunicationAssertionKind | None = None
    #: Positive polarity marker (§18 line 472) — ``is True`` arms the enforcement-ack gate.
    is_message_ack: bool | None = None
    #: Negative polarity (§18 line 472 "never an enforcement acknowledgement") — ``is False`` only.
    treated_as_enforcement_ack: bool | None = None


class AnalysisClaim(FrozenModel):
    """What a root-cause / replay / postmortem analysis claims (ADR §18 line 474; design #28 §2.4).

    §18 line 474 verbatim: "Root-cause analysis, replay, and postmortem findings may improve future
    controls but **cannot authorize past effects, mark preventive evidence complete, or permit current
    operation**." SIR-INV-014 line 210: tickets, pages, chat, dashboards, status reports, timelines,
    postmortems, audit, replay, root-cause analysis and notification "support response and learning but
    **do not substitute** for preventive or containment enforcement".

    Polarity (design #28 §4.3): ``substitutes_prevention`` and ``authorizes_past_effect`` are both
    **negative** — only ``is False`` clears; ``True`` / an unknown ``None`` is dishonest and denies.
    """

    analysis_kind: str | None = None
    #: Negative polarity (SIR-INV-014 line 210) — only ``is False`` clears.
    substitutes_prevention: bool | None = None
    #: Negative polarity (§18 line 474) — only ``is False`` clears.
    authorizes_past_effect: bool | None = None


class ClosureIndependenceLadder(FrozenModel):
    """The §20 item 10 closure independence ladder (ADR-002-027 §7 / SIR-INV-016; design #28 §2.4/§6.9).

    SIR-INV-016 line 217-218 verbatim: "The detector, affected service owner, response implementer,
    evidence producer, performance beneficiary, and live armer **cannot collapse into one Effective
    Principal for closure. Unknown independence denies closure.** Where two distinct natural persons are
    unavailable, the approved Governed Single-Operator Re-Arm Variant (ADR-002-015 §17.1, RFC-001
    SAFE-053) MAY supply the second independent effective principal for closure within its reduced bound
    scope; this adds a satisfaction path and does not relax the independence obligation or the
    fail-closed default on unknown independence."

    **``principals_collapsed`` is an injected hag verdict, not a sir derivation** (design #28 §6.9 M5).
    The Effective Principal collapse judgement is owned by hag (``hag/predicates.py:199``
    ``effective_principal_collapse``; ``:283`` ``quorum_independence_satisfied``), whose control-graph
    union-find merges *the same human behind two accounts* — a merge that
    ``hag/predicates.py:213-214`` performs even for an **unresolved** control edge, precisely because a
    plain string ``!=`` between role names cannot see it. The six role-name coordinates below are
    therefore a **necessary-but-not-sufficient auxiliary hint** only: sir may observe that fewer than
    two *distinct role strings* are present, but it may never conclude independence from string
    distinctness alone — the hag verdict is ANDed and dominates.

    Polarity (design #28 §4.3): ``principals_collapsed`` is **negative** (``is False`` = no collapse =
    clear); ``independence_resolved`` is **positive** (naming inversion noted — "Unknown independence
    denies closure", so only ``is True`` admits); ``single_operator_variant_supplies_second`` is
    **positive** (an injected hag verdict).
    """

    detector: str | None = None
    affected_owner: str | None = None
    response_implementer: str | None = None
    evidence_producer: str | None = None
    performance_beneficiary: str | None = None
    live_armer: str | None = None
    #: Negative polarity — the **injected hag** collapse verdict (``hag/predicates.py:199``).
    principals_collapsed: bool | None = None
    #: Positive polarity (naming inversion; SIR-INV-016 line 218 "Unknown independence denies closure").
    independence_resolved: bool | None = None
    #: Positive polarity — injected hag Governed Single-Operator Re-Arm Variant verdict (§20 item 10).
    single_operator_variant_supplies_second: bool | None = None

    #: The six §7 / SIR-INV-016 line 217 role coordinates, in ADR order (a transcribed anchor).
    ROLE_FIELDS: ClassVar[tuple[str, ...]] = (
        "detector",
        "affected_owner",
        "response_implementer",
        "evidence_producer",
        "performance_beneficiary",
        "live_armer",
    )

    def role_identities(self) -> tuple[str | None, ...]:
        """The six role coordinates in ADR order (``None`` where the role identity is unresolved).

        Returns:
            The six role identity strings in ``ROLE_FIELDS`` order.
        """
        return tuple(getattr(self, name) for name in self.ROLE_FIELDS)


class IncidentClassificationInput(FrozenModel):
    """The §8 classification input view (ADR-002-027 §8 line 248-257; design #28 §2.4).

    §8 line 248 "The Safety Incident Policy SHALL classify at least:" the eight classes, closing with
    line 257 "any condition whose scope or severity **cannot yet be established conservatively**" —
    :attr:`~tos.sir.vocabulary.SignalClassificationClass.UNESTABLISHED_SCOPE_SEVERITY`, the fail-closed
    convergence point.

    Polarity (design #28 §4.3): ``policy_class_match`` is **positive** (only ``is True`` admits);
    ``unestablished`` is **negative** (only ``is False`` clears — an unknown ``None`` converges to
    unestablished, which then requires the ``UNESTABLISHED_SCOPE_SEVERITY`` class, §8 line 257).
    """

    classification: SignalClassificationClass | None = None
    #: Positive polarity — only ``is True`` admits a matched policy class.
    policy_class_match: bool | None = None
    severity: str | None = None
    #: Negative polarity (§8 line 257) — only ``is False`` clears.
    unestablished: bool | None = None


class ContainmentAction(FrozenModel):
    """One proposed containment action (ADR-002-027 §11 line 326-333; design #28 §2.4).

    §11 line 326 enumerates the action kinds (protective, cancellation, replacement, reconciliation,
    query, credential, route, configuration, deployment); line 327 requires "each action's **separately
    owned** classifier, authority, capacity, currentness, and final-egress prerequisites"; line 331 "An
    action that is missing exact current context, admissibility, construction proof, aggregate-risk
    proof, action-flow permit, RCL commitment, Safety Authority, Live Authorization where applicable,
    currentness proof, or final-egress validation is **denied**"; line 333 an action described as
    ``exit`` / ``reduce-only`` / ``cancel`` / ``replace`` / ``protective`` / ``emergency`` /
    ``incident-critical`` "is **not assumed executable** or risk reducing".

    The five ``*_ref`` fields are **injected** opaque references to the separately owned prerequisites
    (protective classifier, authority, rcl capacity, cur currentness, egress) — sir re-authors none of
    them (design #28 §3.5). Polarity (design #28 §4.3): ``assumed_executable`` is **negative** — only
    ``is False`` clears.
    """

    action_kind: str | None = None
    classifier_ref: str | None = None
    authority_ref: str | None = None
    capacity_ref: str | None = None
    currentness_ref: str | None = None
    egress_ref: str | None = None
    #: Negative polarity (§11 line 333) — only ``is False`` clears.
    assumed_executable: bool | None = None

    #: The five §11 line 327 separately-owned prerequisite reference fields (a transcribed anchor).
    PREREQUISITE_FIELDS: ClassVar[tuple[str, ...]] = (
        "classifier_ref",
        "authority_ref",
        "capacity_ref",
        "currentness_ref",
        "egress_ref",
    )


class IncidentUnknownState(FrozenModel):
    """The §13/§16 UNKNOWN axes carried for SIR-INV-009 (design #28 §4.3/§6.5).

    SIR-INV-009 line 190 verbatim: "Unknown incident scope, broker/order/fill/exposure state,
    containment outcome, protection, external activity, shutdown result, evidence, or currentness
    **blocks new risk and consumes worst-credible capacity where economic effect may exist**." §16 line
    429 "Failure to prove current incident state is denial."

    **Every field is negative polarity**: only ``is False`` clears; ``True`` **or an unknown ``None``**
    denies and retains worst-credible capacity. This is the exact #18/#22 MAJOR-2 fail-open the design
    #28 §4.3 polarity rule seals — an ``is not True`` here would read ``None`` as "known" and fail open.
    The worst-credible capacity *arithmetic* is rcl-owned and +Broker (design #28 §3.5, **rcl edge 0** —
    sir performs no capacity arithmetic; §13 line 382 "An incident budget, severity, responder priority,
    shutdown plan, executive decision, or accepted residual risk is **never headroom**").

    This carrier is the §4.3 polarity table's UNKNOWN row realized as a model (design #28 §7.2 (a)
    field-closure property); design #28 §2.4 enumerates the fields without naming their carrier.
    """

    #: The ten §13/§16 UNKNOWN axes, in design #28 §4.3 table order (a transcribed anchor).
    UNKNOWN_FIELDS: ClassVar[tuple[str, ...]] = (
        "broker_state_unknown",
        "order_state_unknown",
        "fill_state_unknown",
        "exposure_unknown",
        "containment_outcome_unknown",
        "protection_state_unknown",
        "external_activity_unknown",
        "shutdown_result_unknown",
        "evidence_state_unknown",
        "currentness_unknown",
    )

    broker_state_unknown: bool | None = None
    order_state_unknown: bool | None = None
    fill_state_unknown: bool | None = None
    exposure_unknown: bool | None = None
    containment_outcome_unknown: bool | None = None
    protection_state_unknown: bool | None = None
    external_activity_unknown: bool | None = None
    shutdown_result_unknown: bool | None = None
    evidence_state_unknown: bool | None = None
    currentness_unknown: bool | None = None


class BrokerFinalityTokens(FrozenModel):
    """The §13 broker-finality tokens carried for SIR-INV-010 (design #28 §6.6).

    §13 line 372-374 verbatim: "missing ACK remains **potentially accepted**"; "Cancel ACK remains
    **insufficient** for Final Quantity Proof"; "a broker query omission is **not proof** that an order
    or fill is absent". SIR-INV-010 line 194: "Missing ACK is not proof of non-acceptance. Cancel ACK is
    not Final Quantity Proof. Incident handling **cannot authorize blind retry, premature release, or
    optimistic reconciliation**."

    Polarity (design #28 §4.3): the six "treated as / authorized" fields are **negative** — only ``is
    False`` clears; ``final_quantity_proof_present`` is **positive** — ``is not True`` keeps the attempt
    potentially live (§20 item 3). The broker-finality *quantification* is +Broker (design #28 §6.6);
    L1 judges only the token structure. **Broker-agnostic**: no concrete broker is named anywhere here
    (project memory ``tos-spec-broker-agnostic``).
    """

    #: Negative polarity (§13 line 372) — only ``is False`` clears.
    missing_ack_treated_as_non_acceptance: bool | None = None
    #: Negative polarity (§13 line 373) — only ``is False`` clears.
    cancel_ack_treated_as_final_quantity_proof: bool | None = None
    #: Negative polarity (§13 line 374) — only ``is False`` clears.
    query_omission_treated_as_absence_proof: bool | None = None
    #: Negative polarity (SIR-INV-010 line 194) — only ``is False`` clears.
    blind_retry_authorized: bool | None = None
    #: Negative polarity (SIR-INV-010 line 194) — only ``is False`` clears.
    premature_release_authorized: bool | None = None
    #: Negative polarity (SIR-INV-010 line 194) — only ``is False`` clears.
    optimistic_reconciliation_authorized: bool | None = None
    #: Positive polarity (§20 item 3) — ``is not True`` keeps the attempt potentially live. Consumed
    #: model-side by :func:`~tos.sir.predicates.final_quantity_proof_absent` and argument-side by the
    #: §6b :func:`~tos.sir.predicates.attempt_potentially_live` coordinate of the same name;
    #: deliberately **not** a conjunct of :func:`~tos.sir.predicates.broker_finality_unchanged` (design
    #: #28 §6.6 — "the rules are unchanged" is a different claim from "this attempt is final"). The
    #: proof itself is quantified downstream by +Broker evidence, never here.
    final_quantity_proof_present: bool | None = None


class RecoveryRevivalInputs(FrozenModel):
    """The §21 non-revival axes carried for SIR-INV-015 (design #28 §6.3).

    SIR-INV-015 line 214 verbatim: "Restart, reconnect, restore, rollback, remediation deployment,
    root-cause completion, evidence repair, replay match, reconciliation, time recovery, workflow
    recovery, quiet time, or operator return **cannot revive prior incident-dependent authority, resume
    a trial, restore production scope, or automatically re-arm**." §21 line 522: "If a later fresh
    re-arm is requested, ADR-002-007/015 governs it and **no** prior approval, Trial Run, production
    scope, deviation, closure decision, or authorization is reused."

    **Every field is negative polarity**: only ``is False`` clears; ``True`` or an unknown ``None``
    denies. The Recovery Barrier and the Recovery Session are sbr-owned (ADR-002-017) and injected; the
    fresh re-arm chain is liveauth / hag owned (design #28 §3.5).
    """

    #: The five §21 / SIR-INV-015 non-revival axes, in design #28 §4.3 table order (transcribed).
    REVIVAL_FIELDS: ClassVar[tuple[str, ...]] = (
        "re_armed",
        "self_reverted",
        "revived_prior_authority",
        "resumed_trial",
        "restored_production_scope",
    )

    re_armed: bool | None = None
    self_reverted: bool | None = None
    revived_prior_authority: bool | None = None
    resumed_trial: bool | None = None
    restored_production_scope: bool | None = None


class ExternalActivityClaim(FrozenModel):
    """An external / manual emergency activity claim (ADR-002-027 §15 line 405-412; design #28 §6b).

    §15 line 407-412 verbatim: such activity "is recorded as unattributed or attributed external
    activity under conservative evidence rules"; "**does not become retroactively compliant TOS
    transmission**"; "does not prove execution, reduction, cancellation, or Final Quantity until normal
    evidence rules pass"; "**cannot release RCL capacity by operator statement**"; "**cannot clear HALT,
    close the incident, or re-arm**"; "**expands** reconciliation and dependency closure to every
    possibly affected account and order".

    Polarity (design #28 §4.3 discipline): the five "does/cannot" fields are **negative** — only ``is
    False`` clears; ``expands_reconciliation_and_closure`` is **positive** — §15 line 412 makes the
    expansion mandatory, so only ``is True`` admits. The external procedure, credential custody and
    reconciliation themselves are +Broker / +Security runtime (design #28 §6b).
    """

    #: Negative polarity (§15 line 408) — only ``is False`` clears.
    retroactively_compliant_transmission: bool | None = None
    #: Negative polarity (§15 line 409) — only ``is False`` clears.
    proves_execution_or_final_quantity: bool | None = None
    #: Negative polarity (§15 line 410) — only ``is False`` clears.
    releases_capacity_by_operator_statement: bool | None = None
    #: Negative polarity (§15 line 411) — only ``is False`` clears.
    clears_halt_or_closes_incident: bool | None = None
    #: Negative polarity (§15 line 411) — only ``is False`` clears.
    re_arms: bool | None = None
    #: Positive polarity (§15 line 412) — only ``is True`` admits.
    expands_reconciliation_and_closure: bool | None = None


def incident_generation_advances(
    predecessor: int | None, candidate: int | None
) -> bool:
    """Whether ``candidate`` strictly advances ``predecessor`` in Incident Generation order (§5.4).

    REUSES ``tos.ordering.compare_order`` (no re-authored order) for the §5.4 Incident Generation
    monotonic fence — "A **monotonic** generation fencing earlier incident scope, state, plans, closure
    eligibility, recovery handoff, configuration requests, authority requests, and consumers after any
    material signal, scope, severity, restriction, obligation, evidence, cause, plan, owner, policy, or
    recovery change" — and the §16 line 427 "absence of a newer declaration, scope expansion ... ordered
    before the claim/send boundary" floor. The two generations are wrapped as ordering coordinates (an
    ordering scalar, **not** a clock — design #28 §3.2) and the result is ``True`` **only** when
    ``predecessor`` provably precedes ``candidate`` (``BEFORE``); an equal, ambiguous or regressing pair
    fails closed. sir owns the fence *meaning* (a newer Incident Generation fences an earlier scope /
    plan / closure eligibility); ordering only carries the order.

    Args:
        predecessor: The predecessor Incident Generation ordering scalar (``None`` ⇒ ``False``).
        candidate: The candidate Incident Generation ordering scalar (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff ``candidate`` provably strictly exceeds ``predecessor``.
    """
    if predecessor is None or candidate is None:
        return False
    return (
        compare_order(
            OrderingEvent(quorum_commit_index=predecessor),
            OrderingEvent(quorum_commit_index=candidate),
        )
        is Ordering.BEFORE
    )


def max_incident_generation(generations: tuple[int | None, ...]) -> int | None:
    """The newest (MAX) Incident Generation of a group, or ``None`` if any is unknown (§4.4/§16).

    The design #28 §4.4 group-reconcile rule: when several entries carry an Incident Generation the
    reconciled fence is the **newest**, never the first (§5.4 monotonic; §16 line 427 "absence of a
    newer declaration, scope expansion ... ordered before the claim/send boundary"). Order-independent
    by construction. A single ``None`` makes the group's newest generation **unprovable**, so the whole
    group fails closed to ``None`` rather than silently maximising over the known subset.

    Args:
        generations: The group's Incident Generation ordering scalars.

    Returns:
        The newest generation, or ``None`` when the group is empty or any member is unknown.
    """
    if not generations:
        return None
    newest: int | None = None
    for generation in generations:
        if generation is None:
            return None
        if newest is None or incident_generation_advances(newest, generation):
            newest = generation
    return newest
