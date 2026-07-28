"""sir safety-incident predicates (design #28 §5/§6/§6b) — pure, fail-closed.

Pure decision rules over injected frozen models (design #28 §0.2/§4): sir authors the **restrictive
declaration / exact-scope-combined / evidence-honesty structural substrate** — the three yolk predicates
(:func:`restrictive_declaration_non_authorizing` — SIR-EV-001; :func:`scope_exact_combined_no_favorable_subset`
— SIR-EV-002; :func:`evidence_communication_status_honest` — SIR-EV-009) and their supporting predicates,
plus the nine §6 predicate-only substrate predicates and the thin §6b not-Phase-1 models. It
**re-authors none** of the sibling / not-landed instances it consumes: sbr owns the Recovery Barrier and
the Recovery Session; hag owns the Effective Principal collapse, the quorum and the Governed
Single-Operator Re-Arm Variant; spg owns Safety Incident Policy activation and the Hard Safety Envelope;
evidence owns custody / causal chain / gap; liveauth owns the Live Authorization; rcl owns capacity
mutation and the worst-credible effect; egress owns final-egress enforcement; cur owns the Active
Currentness Vector; authority owns Safety Authority / HALT; protective owns the Protective Action
Controller and the Cancellation Arbiter; time owns Trustworthy Time; rlp owns demotion / production
scope; wdr owns the Non-Waivable Boundary; and the -028 / -029 handoff and compromise coordinates are
not landed (injected opaque coordinates). sir **consumes** every produced fact as an **injected scalar /
bool / verdict / digest / generation** and re-authors none of them (sibling edge 0, design #28 §3.5).

**The two boundaries (design #28 §0.4c — SIR's maximum risk is over-realization).** SIR-INV-001..016 is
sixteen invariants over only three ``EV-L1``-sliced rows, so most of this module is **predicate-only
substrate that closes no SIR-EV at all**: the authoritative signal registry and the deterministic
severity / scope classifier, the dependency-graph and common-mode engine, the Incident Generation
registry and writer fence, the restrictive ingress and final-egress currentness latch, the
controlled-shutdown orchestrator's ordering proof, the Effective Principal quorum counting, the external
broker procedure and credential custody, the evidence / notification / timeline pipelines, the
ADR-002-025 demotion and the ADR-002-017 Recovery Barrier handoff, and the §22 security controls are
**all human / runtime / +Security / +Broker / sibling-owned**. L1 owns only declaration / scope / honesty
/ closure **structural** judgement over injected coordinates.

**Truthy-sentinel discipline (design #28 §4.2).** ``IncidentLifecycleState`` / ``ClosureDecisionResult``
/ ``IncidentRecordState`` / ``CommunicationAssertionKind`` / ``SignalClassificationClass`` /
``ClosureDimension`` are truthy-untestable ``StrEnum``s (``__bool__`` raises), so every gate uses ``x is
ENUM.SAFE_VALUE``; a bare ``if result:`` would fail open reading ``DENY`` / ``HOLD`` / ``SUSPECTED`` as a
go.

**Polarity discipline (design #28 §4.3 — the #18/#22/#23/#25 MAJOR-2 seal).** Every ``bool | None`` field
declares a polarity in :data:`POSITIVE_POLARITY_FIELDS` / :data:`NEGATIVE_POLARITY_FIELDS` and is
normalized with ``is True`` / ``is False``. A **negative-polarity field is never read with ``is not
True``** — that admits a ``None`` and re-opens the fail-open; its clear is ``is False`` and its deny
normalization is ``is not False``. A positive-polarity field clears on ``is True`` and denies on ``is not
True``. A ``None`` is UNKNOWN and converges to **deny** on both polarities (SIR-INV-009 line 190). The
polarity expectations are read off the design #28 §4.3 table, never back-derived from this code.

**Structural derivation over self-report (design #28 §3.6/§5.2/§14).** ``open_parent_present`` /
``open_child_present`` / ``shared_cause_unresolved`` / ``common_mode_present`` and
:func:`dominating_open_incident_present` are **derived from the**
:class:`~tos.sir.state.ActiveSetMember` **structure**, not read from a self-reported flag; the
Effective-Principal collapse verdict is an **injected hag** verdict, not a sir string comparison
(design #28 §6.9 M5).

**Group reconcile discipline (design #28 §4.4 — the #22 MAJOR-1 seal).** The Active Safety Incident Set
reconciles **all** members conservatively, never the first: the canonical-union check is both-ways
(applicable = members, any omission invalidates, §10 line 311) and order-independent; the group's
reconciled fence is the **newest** Incident Generation (:func:`~tos.sir.state.max_incident_generation`),
never the first. The §4.4 **explicit-empty** Active Safety Incident Set (applicable = ∅, members = (),
``is_complete`` / ``is_current`` positively ``True``) is **valid** — the canonical representation of a
no-incident bundle (§5.5 line 126 "applicable to"; §16 line 423-424 requires the Active Set digest even
with no incident) — while a malformed ∅ (members = () with a non-empty applicable set, or a surplus
member with an empty applicable set) denies. Both ways.

**Forward-seam discipline (design #28 §3.6/§4.1).** sir produces the **incident half** of the
downstream de-restriction / recovery coordinate as :func:`dominating_open_incident_present`. The HALT
half is authority-owned and the *combination* is downstream's; sir therefore neither authors nor assigns
the consumer's combined coordinate — a §4.1 canary asserts that consumer coordinate's name is absent
from every sir source. The polarity sir produces is consistent with the two committed consumers
(``protective/predicates.py:395`` and ``sbr/predicates.py:731`` both clear only on a positive ``False``).

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.sir.*`` (records / state / vocabulary /
_base) only; no ``shared.*``, no other sibling ``tos.*`` (design #28 §0.3). Clock-free.

Regime tag: **restrictive-declaration / exact-scope-combined / evidence-honesty predicate substrate
only; SIR-EV-001..012 all remain NOT_IMPLEMENTED** — the core rows 001 / 002 / 009 await ``/3``
integration and adversarial evidence and 001 additionally carries ``+Security``; the six predicate-only
rows await component-fault ``EV-L2`` plus ``+Broker`` / ``+Security``; the three not-Phase-1 rows
(004 / 007 / 008) are ``EV-L3`` runtime. **EV-L1-complete claim forbidden.**
"""

from __future__ import annotations

from tos.sir._base import AllFalseIncidentAuthority
from tos.sir.records import (
    ActiveSafetyIncidentSet,
    IncidentClosureDecision,
    IncidentContainmentPlan,
    IncidentRecoveryHandoffPackage,
    SafetyIncidentRecord,
)
from tos.sir.state import (
    ActiveSetMember,
    AnalysisClaim,
    BrokerFinalityTokens,
    ClosureIndependenceLadder,
    CommunicationHonestyLadder,
    ContainmentAction,
    ControlledShutdownProcedure,
    ExternalActivityClaim,
    IncidentClassificationInput,
    IncidentDependencyClosure,
    IncidentScope,
    IncidentUnknownState,
    OngoingSafetyObligation,
    RecoveryRevivalInputs,
    SafetySignal,
    ShutdownStep,
    incident_generation_advances,
    max_incident_generation,
)
from tos.sir.vocabulary import (
    CLOSURE_CONTRACT_ITEM_COUNT,
    CLOSURE_CONTRACT_ITEM_POLARITY,
    MANDATED_CLOSURE_DIMENSION_FLOOR,
    RESTRICTIVE_LIFECYCLE_STATES,
    SHUTDOWN_PROHIBITIONS,
    SHUTDOWN_STEP_KINDS,
    ClosureDecisionResult,
    ClosureDimension,
    SignalClassificationClass,
)

__all__ = [
    # polarity registry (design #28 §4.3 / §7.2 (a) field-closure property)
    "POSITIVE_POLARITY_FIELDS",
    "NEGATIVE_POLARITY_FIELDS",
    "DERIVED_NEGATIVE_POLARITY_NAMES",
    # core §5 predicates — the three yolk + supporting
    "restrictive_declaration_non_authorizing",
    "declaration_creates_no_authority",
    "low_severity_no_narrow",
    "classification_admissible",
    "scope_not_self_exempt_or_narrowed",
    "scope_exact_combined_no_favorable_subset",
    "active_set_is_canonical_union",
    "no_favorable_subset",
    "dependency_closure_complete",
    "evidence_communication_status_honest",
    "communication_assertions_distinguished",
    "message_ack_not_enforcement_ack",
    "analysis_not_prevention",
    "emergency_evidence_no_suppress",
    # predicate-only §6 substrate (closes NO SIR-EV)
    "all_false_incident_authority",
    "containment_uses_normal_authority",
    "incident_system_no_route",
    "controlled_shutdown_not_broker_finality",
    "step_completion_proven",
    "recovery_revives_nothing",
    "dominating_open_incident_present",
    "obligations_survive_shutdown",
    "unknown_remains_conservative",
    "broker_finality_unchanged",
    "final_quantity_proof_absent",
    "economic_effect_outlives_incident_state",
    "closure_administrative_non_permissive",
    "closure_contract_complete",
    "closure_single_use_non_authorizing",
    "closure_independence_non_self_exemption",
    "recovery_handoff_requires_accepted_barrier",
    # not-Phase-1 thin models §6b
    "restriction_dominates_send",
    "attempt_potentially_live",
    "external_activity_conservative",
]


# ===========================================================================
# polarity registry (design #28 §4.3 — transcribed from the contract's table)
# ===========================================================================

#: Every **positive**-polarity ``bool | None`` coordinate: it clears on ``is True`` and denies on ``is
#: not True`` (``False`` **and** an unknown ``None`` both deny). Transcribed from the design #28 §4.3
#: polarity table plus the §2.4 field skeletons; the §7.2 (a) field-closure property asserts both
#: directions (every registered name is a declared model field or a documented argument coordinate, and
#: every declared ``bool | None`` model field is registered).
POSITIVE_POLARITY_FIELDS: frozenset[str] = frozenset(
    {
        # §4.3 table rows
        "is_material",
        "is_authenticated",
        "greatest_credible_scope_computed",
        "dependency_closure_complete",
        "is_complete",
        "is_current",
        "effective_principal_verdict",
        "recovery_barrier_closed",
        "accepted_by_recovery_session",
        "single_operator_variant_supplies_second",
        "final_quantity_proof_present",
        "independence_resolved",
        "is_message_ack",
        "deny_before_stop",
        # §2.4 field skeletons + the §6 substrate carriers
        "resolved",
        "transferred_with_owner_and_evidence",
        "policy_class_match",
        "cancellation_arbiter_approved",
        "expands_reconciliation_and_closure",
    }
)

#: Every **negative**-polarity ``bool | None`` coordinate: it clears **only** on ``is False`` and denies
#: on ``is not False`` (``True`` **and** an unknown ``None`` both deny). ``is not True`` is **never**
#: used on any of these — that is the exact #18/#22/#23/#25 fail-open the design #28 §4.3 rule seals,
#: and the §7.2 polarity regression greps this module to prove it.
NEGATIVE_POLARITY_FIELDS: frozenset[str] = frozenset(
    {
        # §4.3 table rows
        "single_use_consumed",
        "consumed_by_live_authority",
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
        "restriction_workflow_gated",
        "severity_label_narrows_scope",
        "principals_collapsed",
        "treated_as_enforcement_ack",
        "substitutes_prevention",
        "authorizes_past_effect",
        "re_armed",
        "self_reverted",
        "revived_prior_authority",
        "resumed_trial",
        "restored_production_scope",
        "scope_establishable",
        # §2.4 field skeletons + the §6 / §6b substrate carriers
        "closure_unknown",
        "self_exempted",
        "wildcard_or_narrowed",
        "completed",
        "assumed_executable",
        "unestablished",
        "protection_blindly_cancelled",
        "exposure_reported_safely_closed",
        "missing_ack_treated_as_non_acceptance",
        "cancel_ack_treated_as_final_quantity_proof",
        "query_omission_treated_as_absence_proof",
        "blind_retry_authorized",
        "premature_release_authorized",
        "optimistic_reconciliation_authorized",
        "retroactively_compliant_transmission",
        "proves_execution_or_final_quantity",
        "releases_capacity_by_operator_statement",
        "clears_halt_or_closes_incident",
        "re_arms",
    }
)

#: The four §4.3 negative-polarity coordinates that are **derived from structure, never declared as a
#: field** (design #28 §5.2 conjunct 3 / §14 "구조 파생 > 자기신고"). Each has a private
#: ``_derive_<name>`` function in this module; the §7.2 (a) field-closure property asserts the
#: correspondence so a derived coordinate can never quietly become a self-reported flag.
DERIVED_NEGATIVE_POLARITY_NAMES: frozenset[str] = frozenset(
    {
        "open_parent_present",
        "open_child_present",
        "shared_cause_unresolved",
        "common_mode_present",
    }
)


# ===========================================================================
# all-false authority (SIR-INV-001; design #28 §2.4/§6.8)
# ===========================================================================


def all_false_incident_authority(authority: AllFalseIncidentAuthority | None) -> bool:
    """Whether an incident artifact's authority block is genuinely all-false (SIR-INV-001; §7).

    SIR-INV-001 line 158 verbatim: "Policy, signal, record, severity, plan, task, message, timeline,
    evidence, review, and closure artifacts create **no** capacity, protection, Safety Authority, Live
    Authorization, Transmission Capability, broker permission, HALT clear, production scope, or re-arm
    authority" (+ §7 line 231 protective self-labelling and line 237 recovery readiness). The
    construction validator already rejects a ``True`` flag, so this predicate is the **second layer**
    that re-derives the fact for a ``model_construct`` bypass (defence in depth, design #28 §2.3): every
    declared flag must be positively ``False``, and an absent block denies.

    Args:
        authority: The artifact's authority block (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff every declared authority flag is positively ``False``.
    """
    if authority is None:
        return False
    return all(
        getattr(authority, name) is False for name in type(authority).model_fields
    )


# ===========================================================================
# core §5.1 — restrictive declaration (SIR-EV-001 yolk, +Security residue)
# ===========================================================================


def declaration_creates_no_authority(record: SafetyIncidentRecord | None) -> bool:
    """Whether a declaration record grants nothing (SIR-INV-001; design #28 §5.1 conjunct 2).

    §5.3 verbatim: an incident record "**grants no authority**". A declaration is restrictive input to
    separately owned controls, never permission (§5.5 "not authority itself").

    Args:
        record: The incident record (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the record's authority block is genuinely all-false.
    """
    if record is None:
        return False
    return all_false_incident_authority(record.authority_effect)


def low_severity_no_narrow(record: SafetyIncidentRecord | None) -> bool:
    """Whether a severity label leaves the scope un-narrowed (§8 line 269; design #28 §5.1 conjunct 5).

    §8 line 269 verbatim: "A **low-severity label cannot override a Critical invariant or make unknown
    scope narrow**." SIR-INV-003 line 166: unknown, stale, conflicting, incomplete, wildcard, patched or
    self-selected scope "expands containment; it never narrows permission". ``severity_label_narrows_scope``
    is **negative** polarity: only a positive ``False`` clears, so an unknown ``None`` denies.

    Args:
        record: The incident record (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the record positively asserts its severity label narrows no scope.
    """
    if record is None:
        return False
    return record.severity_label_narrows_scope is False


def classification_admissible(
    classification: IncidentClassificationInput | None,
) -> bool:
    """Whether the §8 classification input is admissible (design #28 §5.1; §8 line 248-257).

    Two structural facts, both fail-closed:

    1. **The unestablished convergence point (§8 line 257).** ``unestablished`` is negative polarity, so
       anything other than a positive ``False`` — a positive ``True`` *or* an unknown ``None`` — means
       the scope or severity "cannot yet be established conservatively", and the ADR's own answer is the
       :attr:`~tos.sir.vocabulary.SignalClassificationClass.UNESTABLISHED_SCOPE_SEVERITY` class. A
       classification that is unestablished but labelled as one of the seven concrete classes is
       inadmissible (it would understate the hazard).
    2. **A concrete class needs a positive policy match.** When the input positively asserts the scope
       and severity *are* established, the class must be one the policy matched
       (``policy_class_match is True``); an unknown match denies (§8 line 248 "The Safety Incident Policy
       SHALL classify at least ...").

    The *deterministic classifier itself* is runtime and +Security (ADR §28 OQ2; design #28 §6c) — this
    is a structural admissibility judgement only.

    Args:
        classification: The §8 classification input (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the classification input is structurally admissible.
    """
    if classification is None:
        return False
    if classification.unestablished is not False:
        return (
            classification.classification
            is SignalClassificationClass.UNESTABLISHED_SCOPE_SEVERITY
        )
    if classification.classification is None:
        return False
    return classification.policy_class_match is True


def scope_not_self_exempt_or_narrowed(scope: IncidentScope | None) -> bool:
    """Whether the exact scope is neither self-exempted nor narrowed (§10 line 303; §8 line 269).

    §10 line 303 verbatim: "The affected component **cannot self-exempt itself** or declare a failure
    local." SIR-INV-003 line 166: wildcard / narrowed scope "expands containment; it never narrows
    permission". Both coordinates are **negative** polarity: only a positive ``False`` clears, so an
    unknown ``None`` denies.

    Args:
        scope: The exact incident scope (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the scope positively asserts neither self-exemption nor wildcard/narrowing.
    """
    if scope is None:
        return False
    return scope.self_exempted is False and scope.wildcard_or_narrowed is False


def restrictive_declaration_non_authorizing(
    record: SafetyIncidentRecord | None,
    signal: SafetySignal | None,
) -> bool:
    """Whether a restrictive incident declaration is coherent (SIR-EV-001 yolk; design #28 §5.1).

    The first yolk. ``True`` means the declaration is **restrictive, asymmetric and non-authorizing**;
    ``False`` means incoherent or undecidable. Every conjunct is fail-closed:

    1. **∅-seal.** An absent record or signal is undecidable ⇒ ``False``.
    2. **All-false authority (SIR-INV-001 line 158).** Declaring an incident creates no capacity,
       protection, Safety Authority, Live Authorization, Transmission Capability, broker permission,
       HALT clear, production scope, re-arm, protective classification, or recovery readiness.
    3. **The two recognition axes, kept separate (design #28 §5.1 conjunct 3, M6).** The *subject* axis:
       a signal is a declaration subject when it is positively material **or** its scope cannot yet be
       established (§8 line 257; §23 line 549 "Unclassified material signal | declare suspected; deny
       new risk in greatest credible scope") — only a positively non-material signal with a positively
       establishable scope is out of scope. The *evidence* axis is a **disjunction, not a gate**: §5.2
       line 110 defines a Safety Signal as "an authenticated observation **or** conservative inference",
       so ``is_authenticated`` is deliberately **not** ANDed here — an unauthenticated conservative
       inference is classified ``UNESTABLISHED_SCOPE_SEVERITY`` and expands the scope rather than being
       dismissed.
    4. **Restrictive and asymmetric (SIR-INV-002 line 162).** "Declaration and restriction **do not
       wait for a permissive quorum**" (§8 step 3 "commits a HALT, deny, demotion, quarantine, or fence
       **without waiting for ordinary workflow**"; §1 line 21 formal ticket creation, human availability
       or classification completion "SHALL NOT delay an independently available Human HALT"). Structural
       form: ``restriction_workflow_gated`` positively ``False`` (negative polarity — an unknown
       ``None`` denies).
    5. **Low severity narrows nothing (§8 line 269).** :func:`low_severity_no_narrow`.
    6. **The greatest credible scope is computed and un-exempted (§8 step 2; SIR-INV-003).**
       ``greatest_credible_scope_computed`` positively ``True`` (positive polarity) **and** the exact
       scope is neither self-exempted nor wildcard/narrowed
       (:func:`scope_not_self_exempt_or_narrowed`) — a record whose scope structure is absent is
       undecidable.
    7. **The classification input is admissible (§8 line 248-257).** :func:`classification_admissible`.

    **Closes no SIR-EV.** SIR-EV-001 is ``EV-L1/3+Security`` — the ``/3`` integration and adversarial
    evidence remains, and the whole ``+Security`` axis (§22 line 532 "signal suppression, forgery,
    downgrade, or reordering") is runtime and Phase-1-out. The authoritative signal registry and the
    deterministic severity / scope classifier are runtime (ADR §28 OQ2).

    Args:
        record: The immutable versioned incident record (``None`` ⇒ ``False``).
        signal: The Safety Signal the declaration answers (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the declaration is restrictive, asymmetric and non-authorizing.
    """
    if record is None or signal is None:
        return False
    # (2) SIR-INV-001 — declaration grants nothing.
    if not declaration_creates_no_authority(record):
        return False
    # (3) subject axis — material, or a scope that cannot yet be established conservatively.
    # ``is False or is None`` is written out rather than the equivalent ``is not True`` on purpose:
    # ``scope_establishable`` is a negative-polarity field, and although this use is the *restrictive*
    # direction (an unestablished scope **widens** the declaration, §8 line 257) the explicit form keeps
    # the polarity canary's negative-field rule literally true instead of relying on a reader to
    # classify the direction. See the §4.3 canary docstring on equivalent-form detection limits.
    scope_unestablished = (
        signal.scope_establishable is False or signal.scope_establishable is None
    )
    if not (signal.is_material is True or scope_unestablished):
        return False
    # (4) SIR-INV-002 — restriction does not wait for a permissive quorum (negative polarity).
    if record.restriction_workflow_gated is not False:
        return False
    # (5) §8 line 269 — a low-severity label narrows nothing (negative polarity).
    if not low_severity_no_narrow(record):
        return False
    # (6) §8 step 2 / SIR-INV-003 — greatest credible scope computed, un-exempted, un-narrowed.
    if record.greatest_credible_scope_computed is not True:
        return False
    if not scope_not_self_exempt_or_narrowed(record.incident_scope):
        return False
    # (7) §8 line 248-257 — the classification input is structurally admissible.
    return classification_admissible(record.classification)


# ===========================================================================
# core §5.2 — exact scope + combined incidents (SIR-EV-002 yolk, the cleanest L1)
# ===========================================================================


def _member_is_open(member: ActiveSetMember) -> bool:
    """Whether a member is in a restrictive (non-``CLOSED``) state; an unknown state is open (§9)."""
    state = member.lifecycle_state
    if state is None:
        return True  # unknown lifecycle ⇒ conservatively open (§10 line 314)
    return state in RESTRICTIVE_LIFECYCLE_STATES


def _derive_open_parent_present(members: tuple[ActiveSetMember, ...]) -> bool:
    """Derive ``open_parent_present`` from the member structure (design #28 §5.2 conjunct 3).

    A member that declares a ``parent_id`` whose parent is still open (or, under a
    ``model_construct`` bypass of the set validator, is **not a member at all**) means an open parent
    can still invalidate a child-only disposition (§10 line 310; §1 line 23 "A consumer SHALL NOT ...
    close one child while a shared unresolved cause remains").
    """
    by_id = {member.incident_id: member for member in members}
    for member in members:
        if member.parent_id is None:
            continue
        parent = by_id.get(member.parent_id)
        if parent is None:
            return (
                True  # dangling parent ⇒ conservatively open (model_construct re-catch)
            )
        if _member_is_open(parent):
            return True
    return False


def _derive_open_child_present(members: tuple[ActiveSetMember, ...]) -> bool:
    """Derive ``open_child_present`` from the member structure (design #28 §5.2 conjunct 3).

    A member that *is* a child (declares a ``parent_id``) and is itself still open leaves the parent's
    disposition unresolvable (§10 line 310).
    """
    return any(
        member.parent_id is not None and _member_is_open(member) for member in members
    )


def _derive_shared_cause_unresolved(members: tuple[ActiveSetMember, ...]) -> bool:
    """Derive ``shared_cause_unresolved`` from the member structure (design #28 §5.2 conjunct 3).

    Two members sharing a cause where either is not **positively** resolved leaves a shared unresolved
    cause (§1 line 23; §10 line 310). ``resolved`` is consumed with the positive gate, so an unknown
    ``None`` counts as unresolved.

    **Limitation (pairwise, not transitive).** This walks member *pairs*: a cause shared transitively
    through a third member — A shares c1 with B, B shares c2 with C — is not chained here. The complete
    causal graph is a dependency-graph engine owned by the runtime and +Security (ADR §28 OQ3;
    design #28 §5.2 exactness note). The gap is bounded in the safe direction by
    :func:`active_set_is_canonical_union`, which already requires the set to carry **every** applicable
    incident, so a transitively-related member cannot be omitted from the set in the first place.
    """
    for index, first in enumerate(members):
        for second in members[index + 1 :]:
            if not (first.shared_cause_ids & second.shared_cause_ids):
                continue
            if first.resolved is not True or second.resolved is not True:
                return True
    return False


def _derive_common_mode_present(
    members: tuple[ActiveSetMember, ...], shared_dependencies: tuple[str, ...]
) -> bool:
    """Derive ``common_mode_present`` from the member structure (design #28 §5.2 conjunct 3).

    §10 line 305 verbatim: "If two incidents share an account, Capacity Domain, broker session,
    credential, route, currentness owner, authority generation, evidence path, failure domain,
    configuration, protection, or remediation, the Active Safety Incident Set SHALL represent the
    **common mode and combined response risk**." Structurally: two or more still-open members while the
    set declares any shared dependency. **The real common-mode detection** (proving that two incidents
    actually share a credential / route / session) is a dependency-graph engine, runtime and +Security
    (ADR §28 OQ3; design #28 §5.2 honesty note) — this is the set-structural half only.
    """
    if not shared_dependencies:
        return False
    return sum(1 for member in members if _member_is_open(member)) >= 2


def active_set_is_canonical_union(
    active_set: ActiveSafetyIncidentSet | None,
    applicable_incidents: frozenset[str],
) -> bool:
    """Whether the set is the canonical union of exactly the applicable incidents (§5.5; §10 line 305).

    §5.5 verbatim: "One immutable canonical set of **every** suspected or open incident and shared
    dependency applicable to an exact Safety Cell and scope." §10 line 311: "the remaining Active Safety
    Incident Set is **complete and current**." The check is **both ways** (the #10 lesson): a missing
    applicable incident is an incomplete set, and a surplus member that is not applicable is a
    conflicting set — either denies. Order-independent by construction (set equality), so no member
    ordering can change the verdict (design #28 §4.4). A duplicate member id is re-caught here for a
    ``model_construct`` bypass of the set validator.

    Args:
        active_set: The canonical set (``None`` ⇒ ``False``).
        applicable_incidents: Every incident applicable to the exact Safety Cell and scope.

    Returns:
        ``True`` iff the member id set equals the applicable set exactly.
    """
    if active_set is None:
        return False
    member_ids = [member.incident_id for member in active_set.members]
    if any(member_id is None for member_id in member_ids):
        return False
    unique = frozenset(member_id for member_id in member_ids if member_id is not None)
    if len(unique) != len(member_ids):
        return False  # duplicate id (model_construct re-catch)
    return unique == frozenset(applicable_incidents)


def no_favorable_subset(
    active_set: ActiveSafetyIncidentSet | None,
    applicable_shared_causes: frozenset[str],
) -> bool:
    """Whether no favorable subset can be selected out of the combined set (SIR-INV-004; §10 line 307).

    SIR-INV-004 line 170 verbatim: "A consumer **cannot select, union, or close artifacts to create
    broader permission**." §1 line 23: "A consumer SHALL NOT select a favorable subset, close one child
    while a shared unresolved cause remains." The four blocking coordinates —
    ``open_parent_present`` / ``open_child_present`` / ``shared_cause_unresolved`` /
    ``common_mode_present`` — are **derived from the**
    :class:`~tos.sir.state.ActiveSetMember` **structure**, never read from a self-reported flag (design
    #28 §5.2 conjunct 3 C2-2). Each is negative polarity: anything but a positive ``False`` denies.
    Additionally the caller's applicable shared causes must all be represented in the set's declared
    ``shared_dependencies`` (an unrepresented shared cause is exactly the omission SIR-INV-004 forbids).

    Args:
        active_set: The canonical set (``None`` ⇒ ``False``).
        applicable_shared_causes: The shared causes applicable to the exact Safety Cell and scope.

    Returns:
        ``True`` iff no open parent / open child / unresolved shared cause / common mode remains and
        every applicable shared cause is represented.
    """
    if active_set is None:
        return False
    members = active_set.members
    shared_dependencies = active_set.shared_dependencies
    if _derive_open_parent_present(members) is not False:
        return False
    if _derive_open_child_present(members) is not False:
        return False
    if _derive_shared_cause_unresolved(members) is not False:
        return False
    if _derive_common_mode_present(members, shared_dependencies) is not False:
        return False
    return frozenset(applicable_shared_causes) <= frozenset(shared_dependencies)


def dependency_closure_complete(
    dependency_closure: IncidentDependencyClosure | None,
    applicable_dimensions: frozenset[ClosureDimension],
) -> bool:
    """Whether the greatest-credible dependency closure is complete (§5.6; §10 line 303/314).

    §5.6 enumerates the closure as "**Every** Safety Cell, Capacity Domain, legal portfolio, account,
    broker, venue, instrument, strategy, order, position, commitment, protection, credential, route,
    session, generation, component, artifact, failure domain, evidence path, external activity, and
    downstream consumer that may be affected by the signal or response" — 22 dimensions. Four
    fail-closed conjuncts:

    1. **∅-seal.** An absent closure is undecidable ⇒ ``False``.
    2. **Unknown closure contains (§10 line 314).** "Unknown dependency closure means the broader
       plausible set remains contained" — ``closure_unknown`` is negative polarity, so anything but a
       positive ``False`` denies.
    3. **The 22-dimension floor (design #28 §5.2 conjunct 4).** The caller's ``applicable_dimensions``
       is floored to :data:`~tos.sir.vocabulary.MANDATED_CLOSURE_DIMENSION_FLOOR` — a caller may require
       *more*, never *fewer* (the wdr ``MANDATED_SCOPE_FLOOR`` / cur ``MANDATED_DIMENSION_FLOOR``
       precedent) — and every required dimension must be present. An unrepresented dimension is an
       incomplete closure, which is exactly the vacuous-``True`` the §10 line 303 "cannot self-exempt"
       rule forbids.
    4. **Representation is both ways.** ``affected_ids_by_dimension`` must key **exactly** the present
       dimensions: a present dimension with no entry is unrepresented, and an entry for an absent
       dimension is a malformed surplus. An **explicitly empty** entry is legitimate (a represented
       dimension with no affected coordinate); an *absent* entry is not.

    The injected ``dependency_closure_complete`` proof is ANDed on top and can **never admit alone** —
    the structural derivation above dominates (design #28 §14 "구조 파생 > 자기신고"). The dependency-graph
    engine that actually computes the closure is runtime and +Security (ADR §28 OQ3).

    Args:
        dependency_closure: The §5.6 closure (``None`` ⇒ ``False``).
        applicable_dimensions: Dimensions the caller requires beyond the mandated 22-dimension floor.

    Returns:
        ``True`` iff the closure is structurally complete and positively proven complete.
    """
    if dependency_closure is None:
        return False
    if dependency_closure.closure_unknown is not False:
        return False
    present = frozenset(dependency_closure.present_dimensions)
    required = frozenset(applicable_dimensions) | MANDATED_CLOSURE_DIMENSION_FLOOR
    if not required <= present:
        return False
    if frozenset(dependency_closure.affected_ids_by_dimension) != present:
        return False
    return dependency_closure.dependency_closure_complete is True


def scope_exact_combined_no_favorable_subset(
    active_set: ActiveSafetyIncidentSet | None,
    dependency_closure: IncidentDependencyClosure | None,
    applicable_incidents: frozenset[str],
    applicable_shared_causes: frozenset[str],
    applicable_dimensions: frozenset[ClosureDimension],
) -> bool:
    """Whether the exact combined scope admits no favorable subset (SIR-EV-002 yolk; design #28 §5.2).

    The second yolk and the cleanest ``EV-L1`` slice (register minimum ``EV-L1/3``, no residual tag).
    The signature accepts **every input the judgement needs** — the set, the closure, and all three
    applicable coordinates — so no conjunct is decided on data the caller could not supply (the #21 NT /
    #24 PTF C1 partial-signature defect). Six fail-closed conjuncts:

    1. **∅-seal, both ways (design #28 §4.4).** An absent set or closure is undecidable ⇒ ``False``. An
       **explicit-empty** set (``members = ()`` with an empty applicable set) is **valid** — the
       canonical representation of a no-incident bundle (§5.5 line 126 "applicable to"; §16 line 423-424
       requires the exact Active Safety Incident Set digest at every final egress even with no
       incident). A **malformed** ∅ — an empty member tuple with a non-empty applicable set, or a
       surplus member with an empty applicable set — denies.
    2. **Canonical union, both ways (§5.5; §10 line 311).** :func:`active_set_is_canonical_union`.
    3. **No favorable subset (SIR-INV-004; §10 line 307-312).** :func:`no_favorable_subset`, on the
       structurally derived open-parent / open-child / shared-cause / common-mode coordinates.
    4. **Dependency closure complete (§5.6; §10 line 303/314).** :func:`dependency_closure_complete`.
    5. **Combined, complete and current (§10 line 311).** ``is_complete`` and ``is_current`` are
       positive polarity — an unknown ``None`` denies and "the broader plausible set remains contained"
       (§10 line 314).
    6. **Generation coherence (§5.4; §16 line 427).** The set carries both its Incident Generation and
       its own set generation; without them the §16 line 427 "absence of a newer declaration, scope
       expansion ... ordered before the claim/send boundary" fence is unprovable. Reconciling a *group*
       of generations takes the newest, never the first (:func:`~tos.sir.state.max_incident_generation`).

    **Closes no SIR-EV.** SIR-EV-002 is ``EV-L1/3`` — the ``/3`` integration and adversarial evidence is
    Phase-1-out. **Exactness honesty:** the 22-dimension catalogue is a hand transcription of §5.6, but
    *actually detecting* a common mode (proving two incidents share a credential / route / session) is a
    dependency-graph engine owned by the runtime and +Security (ADR §28 OQ3).

    Args:
        active_set: The canonical Active Safety Incident Set (``None`` ⇒ ``False``).
        dependency_closure: The §5.6 dependency closure (``None`` ⇒ ``False``).
        applicable_incidents: Every incident applicable to the exact Safety Cell and scope.
        applicable_shared_causes: Every shared cause applicable to that exact scope.
        applicable_dimensions: Closure dimensions required beyond the mandated 22-dimension floor.

    Returns:
        ``True`` iff the combined scope is exact, complete, current and admits no favorable subset.
    """
    if active_set is None or dependency_closure is None:
        return False
    # (1) ∅ both ways — explicit-empty is valid, malformed-∅ denies.
    members_empty = len(active_set.members) == 0
    applicable_empty = len(applicable_incidents) == 0
    if members_empty != applicable_empty:
        return False
    if members_empty and active_set.shared_dependencies:
        # §5.5 line 126 scopes the canonical set to "every suspected or open incident **and shared
        # dependency** applicable to an exact Safety Cell and scope". With no applicable incident a
        # declared shared dependency is a surplus the canonical form cannot carry — an axis the
        # conjunct-2 id equality (incident ids only) and the conjunct-3 subset check (∅ ⊆ anything)
        # both leave open.
        return False
    # (2) canonical union, both ways.
    if not active_set_is_canonical_union(active_set, applicable_incidents):
        return False
    # (3) SIR-INV-004 — no favorable subset (structurally derived).
    if not no_favorable_subset(active_set, applicable_shared_causes):
        return False
    # (4) §5.6 — the 22-dimension closure is complete.
    if not dependency_closure_complete(dependency_closure, applicable_dimensions):
        return False
    # (5) §10 line 311 — complete and current (positive polarity).
    if active_set.is_complete is not True or active_set.is_current is not True:
        return False
    # (6) §5.4 / §16 line 427 — the generation fence is provable, group-reconciled to the newest.
    # ``max_incident_generation`` is the §4.4 group reconcile: it takes the **newest** coordinate, is
    # order-independent, and fails closed to ``None`` the moment **any** member of the group is unknown
    # — so a set carrying an unknown Incident Generation *or* an unknown set generation can present no
    # fence at all, and a first-entry reading of the group cannot substitute for it.
    return (
        max_incident_generation(
            (active_set.incident_generation, active_set.active_set_generation)
        )
        is not None
    )


# ===========================================================================
# core §5.3 — evidence / communication / status honesty (SIR-EV-009 yolk)
# ===========================================================================


def communication_assertions_distinguished(
    ladder: CommunicationHonestyLadder | None,
) -> bool:
    """Whether a communication's assertion kind is honestly distinguished (§18 line 472).

    §18 line 472 verbatim: "Communications SHALL **distinguish** observed fact, conservative assumption,
    unresolved UNKNOWN, planned action, authorized action, transmitted attempt, broker evidence,
    verified result, and administrative decision." The L1-decidable content is the **distinction
    obligation**: the communication must carry exactly one of the nine
    :class:`~tos.sir.vocabulary.CommunicationAssertionKind` tokens, and if it is additionally *labelled*
    as something (``claimed_as``), that label must be the same token — labelling a conservative
    assumption as an observed fact is a distinction violation.

    The ADR states **no strength total order** between the nine kinds, so no "promotion to a stronger
    kind" judgement is made here; any such ranking is policy-owned and Phase-0 (design #28 §5.3
    conjunct 2, M7 — the v1.0 total order was withdrawn as an invention).

    Args:
        ladder: The communication honesty view (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the assertion kind is present and any label matches it exactly.
    """
    if ladder is None:
        return False
    if ladder.assertion_kind is None:
        return False
    if ladder.claimed_as is None:
        return True
    return ladder.claimed_as is ladder.assertion_kind


def message_ack_not_enforcement_ack(ladder: CommunicationHonestyLadder | None) -> bool:
    """Whether a message acknowledgement is kept distinct from enforcement (§18 line 472).

    §18 line 472 verbatim: "A message acknowledgement is **never** an enforcement acknowledgement."
    ``treated_as_enforcement_ack`` is **negative** polarity, so it is never cleared by anything but a
    positive ``False``. Two layers: treating *anything* as an enforcement acknowledgement is dishonest
    outright, and on a message acknowledgement specifically (``is_message_ack is True``, the positive
    marker) an **unknown** ``None`` also denies — the exact fail-open the polarity rule seals.

    Args:
        ladder: The communication honesty view (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff no enforcement acknowledgement is claimed from a message acknowledgement.
    """
    if ladder is None:
        return False
    if ladder.treated_as_enforcement_ack is True:
        return False
    if ladder.is_message_ack is True:
        return ladder.treated_as_enforcement_ack is False
    return True


def analysis_not_prevention(analysis_claim: AnalysisClaim | None) -> bool:
    """Whether analysis stays analysis (SIR-INV-014 line 210; §18 line 474).

    SIR-INV-014 line 210 verbatim: tickets, pages, chat, dashboards, status reports, timelines,
    postmortems, audit, replay, root-cause analysis and notification "support response and learning but
    **do not substitute for preventive or containment enforcement**." §18 line 474: root-cause analysis,
    replay and postmortem findings "may improve future controls but **cannot authorize past effects,
    mark preventive evidence complete, or permit current operation**." Both coordinates are **negative**
    polarity — only a positive ``False`` clears, so an unknown ``None`` denies.

    Args:
        analysis_claim: What the analysis claims (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the analysis substitutes for no prevention and authorizes no past effect.
    """
    if analysis_claim is None:
        return False
    return (
        analysis_claim.substitutes_prevention is False
        and analysis_claim.authorizes_past_effect is False
    )


def evidence_communication_status_honest(
    ladder: CommunicationHonestyLadder | None,
    analysis_claim: AnalysisClaim | None,
) -> bool:
    """Whether evidence, communication and status are honest (SIR-EV-009 yolk; design #28 §5.3).

    The third yolk. ``True`` means the communication and the analysis substitute for neither prevention,
    finality nor authority; ``False`` means dishonest or undecidable. Conjuncts:

    1. **∅-seal.** An absent ladder or analysis claim is undecidable ⇒ ``False``.
    2. **The distinction obligation (§18 line 472).** :func:`communication_assertions_distinguished` —
       exactly one of the nine kinds, and any label matches it. No strength order is invented (M7).
    3. **Message ack ≠ enforcement ack (§18 line 472).** :func:`message_ack_not_enforcement_ack`.
    4. **Evidence is not prevention (SIR-INV-014 line 210).** and
    5. **Analysis authorizes no past effect (§18 line 474).** :func:`analysis_not_prevention`.
    6. **Truthy seal (design #28 §4.2).** Every assertion-kind comparison is an explicit ``is``
       identity — the enum raises on ``bool()``, so a truthiness read cannot silently pass.

    **Closes no SIR-EV.** SIR-EV-009 is ``EV-L1/3`` — the ``/3`` integration and adversarial evidence is
    Phase-1-out. Evidence custody, the causal chain and Evidence Gap integrity are evidence-owned
    (ADR-002-016) and injected, never re-authored here (design #28 §3.5).

    Args:
        ladder: The communication honesty view (``None`` ⇒ ``False``).
        analysis_claim: What the root-cause / replay / postmortem analysis claims (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the communication and the analysis are both honest.
    """
    if ladder is None or analysis_claim is None:
        return False
    if not communication_assertions_distinguished(ladder):
        return False
    if not message_ack_not_enforcement_ack(ladder):
        return False
    return analysis_not_prevention(analysis_claim)


def emergency_evidence_no_suppress(
    restriction_waits_for_ordinary_pipeline: bool | None,
    evidence_loss_blocks_closure: bool | None,
    halt_suppressed: bool | None,
) -> bool:
    """Whether the emergency evidence path suppresses nothing it must not (§18 line 470).

    §18 line 470 verbatim: "Immediate restrictive action **SHALL NOT wait for the ordinary evidence
    pipeline** when an approved emergency evidence path exists. **Evidence loss remains an incident and
    blocks closure; it does not justify suppressing a necessary HALT.**" Three injected argument
    coordinates: the first and third are **negative** polarity (only a positive ``False`` clears) and the
    second is **positive** (evidence loss must positively block closure). The emergency evidence path,
    its custody and the journal itself are evidence-owned (ADR-002-016) and runtime (design #28 §6c).

    Args:
        restriction_waits_for_ordinary_pipeline: Negative polarity — restriction must not wait.
        evidence_loss_blocks_closure: Positive polarity — evidence loss must block closure.
        halt_suppressed: Negative polarity — a necessary HALT must not be suppressed.

    Returns:
        ``True`` iff restriction waits for nothing, evidence loss blocks closure, and no HALT is
        suppressed.
    """
    return (
        restriction_waits_for_ordinary_pipeline is False
        and evidence_loss_blocks_closure is True
        and halt_suppressed is False
    )


# ===========================================================================
# §6 predicate-only substrate — closes NO SIR-EV (design #28 §0.4c/§6)
# ===========================================================================


def incident_system_no_route(authority: AllFalseIncidentAuthority | None) -> bool:
    """Whether the incident system holds no live credential or broker route (SIR-INV-006; §15 line 414).

    SIR-INV-006 line 178 verbatim: "Only the RCL mutates and serializes capacity. Only the Broker Adapter
    / Egress Gateway is the final transmission enforcement point. **Incident systems hold neither a
    usable live-order credential nor an independent broker route.**" §15 line 414: incident systems, chat
    bots, ticketing tools, paging tools, dashboards and postmortem systems "SHALL NOT hold a usable
    live-order credential and route". §22 line 538 forbids "alternate broker routes, portals, SDKs,
    proxies, or shared credentials bypassing final egress". Structurally: the artifact creates no
    Transmission Capability and grants no broker permission. The final-egress enforcement itself is
    egress-owned (ADR-002-013) and the capacity authority is rcl-owned (**rcl edge 0** — sir performs no
    capacity arithmetic; §13 line 382 an incident budget, severity, responder priority, shutdown plan,
    executive decision or accepted residual risk "is **never headroom**").

    **Closes no SIR-EV** (SIR-EV-003 / 004 substrate; ``EV-L2/3+Security``).

    Args:
        authority: The artifact's authority block (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the artifact creates no transmission capability and grants no broker permission.
    """
    if authority is None:
        return False
    return (
        authority.creates_transmission_capability is False
        and authority.grants_broker_permission is False
    )


def containment_uses_normal_authority(plan: IncidentContainmentPlan | None) -> bool:
    """Whether containment uses only the normal authority chain (SIR-INV-005; §11 line 331-333).

    SIR-INV-005 line 174 verbatim: "Incident labels, severity, priority, commander approval, or emergency
    status **cannot classify protection, reserve capacity, waive broker/venue constraints, issue
    authority, or bypass final egress**. Every broker-directed action follows the normal exact chain."
    §7 line 240: "Incident coordinators may coordinate work but SHALL NOT accumulate the authorities of
    the components they coordinate." §11 line 331: an action missing any of its separately owned
    prerequisites "is denied"; line 333 an action labelled ``exit`` / ``reduce-only`` / ``cancel`` /
    ``replace`` / ``protective`` / ``emergency`` / ``incident-critical`` "is **not assumed executable**
    or risk reducing".

    Conjuncts: the plan exists; its authority block is genuinely all-false; it holds no route or live
    credential (:func:`incident_system_no_route`); it binds the one exact Incident Generation and the
    exact Active Safety Incident Set digest (§11 line 322); and **every** proposed action carries all
    five §11 line 327 separately owned prerequisite references and positively asserts it is not assumed
    executable.

    An **action-free** plan (a pure controlled-shutdown or restriction plan) is admissible on the action
    axis — the §11 line 320 binding axis and the all-false axis still apply, so the judgement is not
    vacuous (design #28 §4.4: an ∅ guard must not over-seal a legitimate empty case). The *actual*
    authority separation is +Security (design #28 §6.1).

    **Closes no SIR-EV** (SIR-EV-003 substrate; ``EV-L2/3+Security``).

    Args:
        plan: The Incident Containment Plan (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff containment claims no authority of its own and every action keeps the normal chain.
    """
    if plan is None:
        return False
    if not all_false_incident_authority(plan.authority_effect):
        return False
    if not incident_system_no_route(plan.authority_effect):
        return False
    if plan.incident_generation is None or plan.active_set_digest is None:
        return False
    return all(_action_keeps_normal_chain(action) for action in plan.proposed_actions)


def _action_keeps_normal_chain(action: ContainmentAction) -> bool:
    """Whether one proposed action carries its five §11 line 327 prerequisites and claims nothing."""
    for name in ContainmentAction.PREREQUISITE_FIELDS:
        if getattr(action, name) is None:
            return False
    return action.assumed_executable is False


def controlled_shutdown_not_broker_finality(
    procedure: ControlledShutdownProcedure | None,
) -> bool:
    """Whether a controlled shutdown claims no broker finality (SIR-INV-007; §12 line 354-362).

    SIR-INV-007 line 182 verbatim: "**Process stop, scale-to-zero, disconnect, session close, credential
    revocation, route removal, or deployment shutdown does not prove non-acceptance, Final Quantity,
    absence of fills, or absence of external economic effect.**" §12 line 356 the first prohibition is to
    "infer broker finality from process or connection state".

    Conjuncts: the procedure exists; ``deny_before_stop`` is positively ``True`` (§12 step 1 "latch or
    commit denial of new risk **before** stopping ordinary producers" — positive polarity, so an unknown
    ``None`` denies); the declared ``prohibited`` set covers at least the seven §12 line 354-362 "Shutdown
    SHALL NOT" items (:data:`~tos.sir.vocabulary.SHUTDOWN_PROHIBITIONS` — a procedure may declare more,
    never fewer); and every declared step carries a known
    :data:`~tos.sir.vocabulary.SHUTDOWN_STEP_KINDS` kind with a concrete, strictly increasing, duplicate-free
    ordinal. A **step-free** procedure still has to pass the deny-before-stop and prohibition axes, so
    the judgement is not vacuous.

    The §12 10-step **ordering proof**, the hard fencing itself and the §17 partition matrix are L3
    runtime plus +Broker / +Security (design #28 §6.2/§6b); the late-fill and exit-feasibility analyses
    are +Broker.

    **Closes no SIR-EV** (SIR-EV-004 substrate; ``EV-L3+Broker+Security``).

    Args:
        procedure: The §5.8 Controlled Shutdown Procedure (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the procedure denies before stopping, declares the mandated prohibitions, and
        carries a structurally sound step ordering.
    """
    if procedure is None:
        return False
    if procedure.deny_before_stop is not True:
        return False
    if not frozenset(procedure.prohibited) >= SHUTDOWN_PROHIBITIONS:
        return False
    previous: int | None = None
    for step in procedure.ordered_steps:
        if step.step_ordinal is None or step.step_kind not in SHUTDOWN_STEP_KINDS:
            return False
        if previous is not None and step.step_ordinal <= previous:
            return False
        previous = step.step_ordinal
    return True


def step_completion_proven(step: ShutdownStep | None) -> bool:
    """Whether a controlled-shutdown step is **positively** proven complete (§17 line 451).

    §17 line 451 verbatim, for the "Shutdown step result ambiguous" row: "**assume not completed where
    that is safer**; preserve obligations and hard fence." ``completed`` is therefore negative polarity
    read from the completion side: only a positive ``True`` counts as completed, so an ambiguous
    ``None`` — and an absent step — is treated as **not** completed and the obligations stay live.

    This is a *completion* judgement, never a broker-finality one: SIR-INV-007 line 182 "Process stop,
    scale-to-zero, disconnect, session close, credential revocation, route removal, or deployment
    shutdown **does not prove** non-acceptance, Final Quantity, absence of fills, or absence of external
    economic effect", so a proven step still proves nothing about the broker (:func:`broker_finality_unchanged`
    is the separate axis). The real step-completion evidence is L3 runtime (design #28 §6b).

    **Closes no SIR-EV** (SIR-EV-004 substrate; ``EV-L3+Broker+Security``).

    Args:
        step: The ordered shutdown step (``None`` ⇒ ``False``, i.e. not completed).

    Returns:
        ``True`` iff the step is positively proven complete.
    """
    if step is None:
        return False
    return step.completed is True


def dominating_open_incident_present(
    active_set: ActiveSafetyIncidentSet | None,
) -> bool:
    """Whether a dominating open incident restriction is present (design #28 §3.6/§6.3; §9).

    The **incident half** of the downstream de-restriction / recovery dominance coordinate, derived
    **structurally** from the :class:`~tos.sir.state.ActiveSetMember` tuple — never a self-reported flag.
    ``True`` means a dominating open incident restriction is present (or cannot be ruled out); ``False``
    means it is positively absent. The three conservative branches:

    * an absent set is undecidable ⇒ ``True`` (§10 line 314 "Unknown dependency closure means the
      broader plausible set remains contained");
    * a set that is not positively complete **and** current cannot rule anything out ⇒ ``True`` (§10 line
      311; positive polarity, so an unknown ``None`` lands here);
    * any member in a restrictive (non-``CLOSED``, or unknown) lifecycle state ⇒ ``True`` (§9 line 290
      "``SUSPECTED`` is restrictive for the greatest credible scope; it is not permission to wait").

    A **valid explicit-empty** set (no members, positively complete and current) therefore returns
    ``False`` — the no-incident case §16 line 423-424 requires to be expressible (design #28 §4.4).

    **Seam discipline (design #28 §3.6, the ambiguity prescription).** The negation of this result is
    only a *necessary component* of the downstream consumers' combined dominance coordinate; the HALT
    component is authority-owned and the combination and injection are downstream's. sir therefore never
    authors or assigns that combined consumer coordinate — a §4.1 canary asserts its name is absent from
    every sir source. The polarity produced here matches both committed consumers, which clear only on a
    positive ``False`` (``protective/predicates.py:395``; ``sbr/predicates.py:731``).

    **Closes no SIR-EV** (SIR-EV-012 substrate; ``EV-L2/3+Security``).

    Args:
        active_set: The canonical Active Safety Incident Set (``None`` ⇒ ``True``, conservatively).

    Returns:
        ``True`` iff a dominating open incident restriction is present or cannot be ruled out.
    """
    if active_set is None:
        return True
    if active_set.is_complete is not True or active_set.is_current is not True:
        return True
    return any(_member_is_open(member) for member in active_set.members)


def recovery_revives_nothing(inputs: RecoveryRevivalInputs | None) -> bool:
    """Whether recovery revives nothing (SIR-INV-015 line 214; §21 line 522).

    SIR-INV-015 line 214 verbatim: "Restart, reconnect, restore, rollback, remediation deployment,
    root-cause completion, evidence repair, replay match, reconciliation, time recovery, workflow
    recovery, quiet time, or operator return **cannot revive prior incident-dependent authority, resume a
    trial, restore production scope, or automatically re-arm**." §21 line 522: "no prior approval, Trial
    Run, production scope, deviation, closure decision, or authorization is reused."

    All five axes are **negative** polarity and each must be positively ``False`` — an unknown ``None``
    denies, which is the exact fail-open the design #28 §4.3 rule seals. The hard fencing, the Recovery
    Barrier and the Recovery Session are sbr-owned (ADR-002-017) and +Security; the fresh re-arm chain is
    liveauth / hag governed (ADR-002-007/015) — all injected, none re-authored (design #28 §3.5).

    **Closes no SIR-EV** (SIR-EV-012 substrate; ``EV-L2/3+Security``).

    Args:
        inputs: The §21 non-revival axes (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff every non-revival axis is positively ``False``.
    """
    if inputs is None:
        return False
    return all(
        getattr(inputs, name) is False for name in RecoveryRevivalInputs.REVIVAL_FIELDS
    )


def _obligation_survives(obligation: OngoingSafetyObligation) -> bool:
    """Whether one obligation is positively resolved or positively transferred (§5.11; §20 item 4/9)."""
    return (
        obligation.resolved is True
        or obligation.transferred_with_owner_and_evidence is True
    )


def obligations_survive_shutdown(plan: IncidentContainmentPlan | None) -> bool:
    """Whether protection and obligations survive the shutdown (SIR-INV-008; §12 step 5-6; §14).

    SIR-INV-008 line 186 verbatim: "Shutdown **preserves or deliberately transfers** required protection,
    RCL commitments, currentness fences, reconciliation, evidence, notification, settlement,
    external-activity, trapped-exposure, and recovery obligations. It **does not blindly cancel,
    liquidate, abandon, or report them complete**." §14 line 388: "Existing protection SHALL NOT be
    blindly cancelled merely because ordinary trading is halted or shutdown is requested." §12 step 6:
    "preserve necessary protection and **obtain Cancellation Arbiter approval** before changing
    safety-owned protection." §14 line 397: "the system SHALL NOT report the exposure safely closed."

    Conjuncts: the plan exists; protection is positively not blindly cancelled (negative polarity); the
    Cancellation Arbiter has positively approved (positive polarity — a protective-owned injected
    verdict, never re-decided here); the exposure is positively not reported safely closed (negative
    polarity); and **every** declared protection obligation is either positively resolved or positively
    transferred with owner and evidence — a failed protection stays an ongoing obligation (§14 line 396).

    Exit feasibility, late-fill analysis and protection replacement are +Broker (design #28 §6.4); the
    Protective Action Controller and the Cancellation Arbiter are protective-owned (ADR-002-001).

    **Closes no SIR-EV** (SIR-EV-005 substrate; ``EV-L2/3+Broker``).

    Args:
        plan: The Incident Containment Plan (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff protection is preserved and every obligation is resolved or deliberately
        transferred.
    """
    if plan is None:
        return False
    if plan.protection_blindly_cancelled is not False:
        return False
    if plan.cancellation_arbiter_approved is not True:
        return False
    if plan.exposure_reported_safely_closed is not False:
        return False
    return all(
        _obligation_survives(obligation) for obligation in plan.protection_obligations
    )


def unknown_remains_conservative(state: IncidentUnknownState | None) -> bool:
    """Whether every UNKNOWN axis is positively resolved (SIR-INV-009 line 190; §13; §16 line 429).

    SIR-INV-009 line 190 verbatim: "Unknown incident scope, broker/order/fill/exposure state, containment
    outcome, protection, external activity, shutdown result, evidence, or currentness **blocks new risk
    and consumes worst-credible capacity where economic effect may exist**." §16 line 429: "Failure to
    prove current incident state is denial."

    All ten axes are **negative** polarity: each must be positively ``False``. Anything else — a positive
    ``True`` *or* an unknown ``None`` — denies and retains worst-credible capacity. Reading any of these
    with ``is not True`` would treat ``None`` as "known" and is precisely the #18/#22/#23/#25 fail-open
    the design #28 §4.3 rule bans. The worst-credible capacity *arithmetic* is rcl-owned and +Broker
    (**rcl edge 0** — sir performs no capacity arithmetic).

    **Closes no SIR-EV** (SIR-EV-006 substrate; ``EV-L2/3+Broker``).

    Args:
        state: The §13/§16 UNKNOWN axes (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff every UNKNOWN axis is positively ``False``.
    """
    if state is None:
        return False
    return all(
        getattr(state, name) is False for name in IncidentUnknownState.UNKNOWN_FIELDS
    )


def broker_finality_unchanged(tokens: BrokerFinalityTokens | None) -> bool:
    """Whether incident handling leaves broker finality rules unchanged (SIR-INV-010; §13 line 372-374).

    SIR-INV-010 line 194 verbatim: "**Missing ACK is not proof of non-acceptance. Cancel ACK is not Final
    Quantity Proof.** Incident handling **cannot authorize blind retry, premature release, or optimistic
    reconciliation**." §13 line 372-374: "missing ACK remains potentially accepted"; "Cancel ACK remains
    insufficient for Final Quantity Proof"; "a broker query omission is not proof that an order or fill
    is absent".

    All six token coordinates are **negative** polarity and each must be positively ``False`` — an
    unknown ``None`` denies. ``final_quantity_proof_present`` is deliberately **not** a conjunct here: it
    is the positive-polarity coordinate of :func:`attempt_potentially_live` (§20 item 3), and requiring
    it would confuse "the rules are unchanged" with "this attempt is final". The broker-finality
    *quantification* is +Broker (design #28 §6.6). **Broker-agnostic**: no concrete broker is named.

    **Closes no SIR-EV** (SIR-EV-006 substrate; ``EV-L2/3+Broker``).

    Args:
        tokens: The §13 broker-finality tokens (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff no broker-finality shortcut is taken.
    """
    if tokens is None:
        return False
    return (
        tokens.missing_ack_treated_as_non_acceptance is False
        and tokens.cancel_ack_treated_as_final_quantity_proof is False
        and tokens.query_omission_treated_as_absence_proof is False
        and tokens.blind_retry_authorized is False
        and tokens.premature_release_authorized is False
        and tokens.optimistic_reconciliation_authorized is False
    )


def final_quantity_proof_absent(tokens: BrokerFinalityTokens | None) -> bool:
    """Whether an attempt lacks a Final Quantity Proof and so stays capacity-covered (§20 item 3).

    §20 item 3 verbatim: "every broker attempt and economic effect has **Final Quantity Proof or remains
    an explicit current capacity-covered obligation**." §13 line 376: "a potentially-live attempt remains
    capacity-covered until the normal release rule passes." ``final_quantity_proof_present`` is positive
    polarity, so this returns ``True`` (proof absent ⇒ the obligation stands) on ``False`` **and** on an
    unknown ``None`` **and** on an absent token set — the fail-closed direction of SIR-INV-010 line 194
    "Missing ACK is not proof of non-acceptance".

    It is deliberately **not** a conjunct of :func:`broker_finality_unchanged`: "the finality rules are
    unchanged" and "this attempt is final" are different claims (design #28 §6.6). It is the model-side
    counterpart of the ``final_quantity_proof_present`` argument coordinate
    :func:`attempt_potentially_live` consumes. Quantifying the proof itself is +Broker; the capacity
    coverage is rcl-owned (**rcl edge 0**). **Broker-agnostic**: no concrete broker is named.

    **Closes no SIR-EV** (SIR-EV-006 substrate; ``EV-L2/3+Broker``).

    Args:
        tokens: The §13 broker-finality tokens (``None`` ⇒ ``True``, conservatively).

    Returns:
        ``True`` iff no Final Quantity Proof is positively present.
    """
    if tokens is None:
        return True
    return tokens.final_quantity_proof_present is not True


def economic_effect_outlives_incident_state(
    authority: AllFalseIncidentAuthority | None,
) -> bool:
    """Whether economic effect outlives incident state (SIR-INV-013 line 206; §13 line 377).

    SIR-INV-013 line 206 verbatim: "Signal dismissal, record expiry, task completion, incident closure,
    credential expiry, authority expiry, evidence retention change, or workflow deletion **cannot erase
    orders, attempts, fills, positions, obligations, external activity, or capacity consumption**." §13
    line 377: "incident, plan, authority, capability, credential, session, or record expiry **does not
    release capacity**."

    The judgement is made on the **all-false authority shape**, not on an expiry flag (the #26 WDR v1.2
    ``economic_effect_persists`` lesson): consuming ``is_expired is False`` as a *clear* would let an
    expiry be read as "effect gone" and invert the invariant. Instead the two authority flags that would
    have to be true for an incident-state transition to erase economic effect —
    ``creates_capacity`` (release) and ``classifies_protective_action`` (re-labelling) — must be
    positively ``False``; an absent block denies. Expiry's *future-use* refusal is owned by the §6b
    send-race axis and the §6.3 non-revival axis, not by this predicate.

    **Closes no SIR-EV** (SIR-EV-006 / 012 substrate; ``EV-L2/3+Broker``).

    Args:
        authority: The artifact's authority block (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the artifact can neither release capacity nor re-label a protective action.
    """
    if authority is None:
        return False
    return (
        authority.creates_capacity is False
        and authority.classifies_protective_action is False
    )


def closure_contract_complete(items: tuple[bool | None, ...]) -> bool:
    """Whether the §20 12-item closure contract is fully satisfied (§20 line 490-503; design #28 §6.8b).

    §20 line 490 verbatim: "Administrative closure requires **all of the following** for the exact
    current Incident Generation and Active Safety Incident Set", then the twelve items — signals /
    severity / scope / closure / common modes / chronology complete (1); every required restriction and
    hard fence proven current (2); every broker attempt with Final Quantity Proof or an explicit current
    capacity-covered obligation (3); positions / orders / fills / external activity / margin / settlement
    / trapped exposure / protection reconciled or explicitly retained (4); every containment and shutdown
    action with evidence-backed disposition (5); Evidence Gaps resolved or explicitly preventing closure
    (6); root cause recorded without substituting analysis for enforcement (7); remediation and rollback
    governed by fresh configuration (8); recovery obligations transferred to ADR-002-017 behind a closed
    Recovery Barrier (9); the closure request independently reviewed by the required Effective Principals
    **or** by the approved Governed Single-Operator Re-Arm Variant (10); no open parent, child,
    overlapping incident, shared cause, or common mode invalidating closure (11); and an explicit
    statement that the decision creates no capacity, readiness, HALT clear, authority, transmission,
    production scope, or re-arm (12).

    The tuple must carry **exactly** twelve items (a short tuple is an under-specified contract, a long
    one is a surplus) and each slot must match its
    :data:`~tos.sir.vocabulary.CLOSURE_CONTRACT_ITEM_POLARITY` polarity: eleven positive slots admit only
    on ``is True``, and item 11 — whose proposition is that an open parent / child / overlap / shared
    cause / common mode **invalidates** closure — admits only on ``is False``. An unknown ``None`` denies
    on **both** polarities.

    Args:
        items: The 12 closure-contract slots in ADR order.

    Returns:
        ``True`` iff all twelve slots are present and each satisfies its polarity.
    """
    if len(items) != CLOSURE_CONTRACT_ITEM_COUNT:
        return False
    for item, positive in zip(items, CLOSURE_CONTRACT_ITEM_POLARITY, strict=True):
        if positive:
            if item is not True:
                return False
        elif item is not False:
            return False
    return True


def closure_single_use_non_authorizing(
    closure: IncidentClosureDecision | None,
) -> bool:
    """Whether a closure decision is unconsumed and live-authority-free (§20 line 505; SIR-INV-012).

    §20 line 505 verbatim: "A closure decision is **single-use** for record transition only and **cannot
    be consumed by a live-authority path**." Both coordinates are **negative** polarity: each must be
    positively ``False``, so a re-presented (``True``) or unknown (``None``) consumption denies. This
    REUSES the single-use consumption *shape* the iap approval gate established
    (``iap/predicates.py:176``) — the shape is re-expressed locally, never imported (sibling edge 0,
    design #28 §3.3/§3.5). The registry-level replay detection is +Security; the byte-level replay
    detection is the ``classify_record_pair`` ``CRITICAL_CONFLICT`` on the artifact itself (§22 line 536).

    **Closes no SIR-EV** (SIR-EV-010 substrate; ``EV-L2/3+Security``).

    Args:
        closure: The Incident Closure Decision (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the decision is positively unconsumed and positively not live-authority consumed.
    """
    if closure is None:
        return False
    return (
        closure.single_use_consumed is False
        and closure.consumed_by_live_authority is False
    )


def closure_administrative_non_permissive(
    closure: IncidentClosureDecision | None,
) -> bool:
    """Whether an administrative closure stays non-permissive (SIR-INV-012 line 202; §20).

    SIR-INV-012 line 202 verbatim: "Closure records evidence-complete administrative disposition for one
    exact generation. **It does not establish safe state, release capacity, clear UNKNOWN or HALT,
    validate configuration, restore scope, satisfy recovery, or authorize transmission.**" §5.10: the
    decision "creates no permissive state".

    Conjuncts: the decision exists; the result **is** ``CLOSE_ADMINISTRATIVELY`` by explicit identity
    (the truthy seal makes ``if result:`` impossible — ``DENY`` / ``HOLD`` are non-closure); the authority
    block is genuinely all-false; the decision is single-use-unconsumed and live-authority-free
    (:func:`closure_single_use_non_authorizing`); the **injected hag Effective Principal verdict** is
    positively ``True``; and the §20 12-item contract is fully satisfied
    (:func:`closure_contract_complete`). The construction validator seals the same facts, so a
    ``model_construct`` bypass is caught here as a second layer (design #28 §2.3).

    **The injected verdict outranks the self-reported item (design #28 §14 "구조 파생 > 자기신고").** §20
    item 10 is *also* a ``closure_contract_items`` slot, but that slot is a claim the closure record
    makes about itself. ``effective_principal_verdict`` is the **verdict hag actually produced**
    (``hag/predicates.py:283`` ``quorum_independence_satisfied``), and it is positive polarity — a
    ``False`` ("independence does not hold") or an unknown ``None`` denies, whatever the self-reported
    item claims. Without this conjunct a record could self-certify item 10 and close over a hag denial.

    The closure quorum counting, the registry replay detection and the Effective Principal verification
    are hag-owned and +Security (design #28 §6.8/§6.9).

    **Closes no SIR-EV** (SIR-EV-010 substrate; ``EV-L2/3+Security``).

    Args:
        closure: The Incident Closure Decision (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the decision is an administrative, non-permissive, contract-complete closure.
    """
    if closure is None:
        return False
    if closure.result is not ClosureDecisionResult.CLOSE_ADMINISTRATIVELY:
        return False
    if not all_false_incident_authority(closure.authority_effect):
        return False
    if not closure_single_use_non_authorizing(closure):
        return False
    # §20 item 10 — the injected hag verdict, not the record's self-report about itself.
    if closure.effective_principal_verdict is not True:
        return False
    return closure_contract_complete(closure.closure_contract_items)


def closure_independence_non_self_exemption(
    ladder: ClosureIndependenceLadder | None,
) -> bool:
    """Whether closure independence holds without self-exemption (SIR-INV-016 line 217-218; §20 item 10).

    SIR-INV-016 line 217-218 verbatim: "The detector, affected service owner, response implementer,
    evidence producer, performance beneficiary, and live armer **cannot collapse into one Effective
    Principal for closure. Unknown independence denies closure.** Where two distinct natural persons are
    unavailable, the approved Governed Single-Operator Re-Arm Variant (ADR-002-015 §17.1, RFC-001
    SAFE-053) MAY supply the second independent effective principal for closure within its reduced bound
    scope; **this adds a satisfaction path and does not relax the independence obligation or the
    fail-closed default on unknown independence**."

    Conjuncts:

    1. **∅-seal.** An absent ladder is undecidable ⇒ ``False``.
    2. **No collapse — the injected hag verdict (design #28 §6.9 M5).** ``principals_collapsed`` is
       **negative** polarity and must be positively ``False``. The collapse judgement itself belongs to
       hag (``hag/predicates.py:199`` ``effective_principal_collapse``; ``:283``
       ``quorum_independence_satisfied``), whose control-graph union-find merges *the same human behind
       two accounts* — and merges an **unresolved** control edge exactly like a resolved one
       (``hag/predicates.py:213-214``), the fail-closed behaviour a name comparison cannot reproduce.
    3. **Every role identity is resolved.** A ``None`` role coordinate is unknown independence, which
       §SIR-INV-016 line 218 denies outright.
    4. **Independence positively resolved.** ``independence_resolved`` is **positive** polarity despite
       the positive-sounding name (design #28 §4.3 naming-inversion note): only ``is True`` admits.
    5. **The two-person floor, or the governed variant.** If the six role coordinates collapse to fewer
       than two *distinct* strings, the approved Governed Single-Operator Re-Arm Variant must positively
       supply the second effective principal (an injected hag verdict, §20 item 10 / patch v0.2).

    **The role-name comparison in conjunct 5 is a necessary-but-not-sufficient auxiliary hint and is
    never a standalone basis.** Two distinct role *strings* can still be one natural person behind two
    accounts — exactly what the hag control graph resolves and a string ``!=`` cannot
    (``hag/predicates.py:213-214``). The hag verdict of conjunct 2 is ANDed and dominates; sir contributes
    only the structural hint. The quorum counting and the Effective Principal verification are hag-owned
    and +Security (design #28 §6.9).

    **Closes no SIR-EV** (SIR-EV-010 substrate; ``EV-L2/3+Security``).

    Args:
        ladder: The §20 item 10 closure independence ladder (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff no collapse, every role resolved, independence positively resolved, and the
        two-person floor met or the governed variant positively supplying the second principal.
    """
    if ladder is None:
        return False
    if ladder.principals_collapsed is not False:
        return False
    roles = ladder.role_identities()
    if any(role is None for role in roles):
        return False
    if ladder.independence_resolved is not True:
        return False
    if len(frozenset(roles)) < 2:
        return ladder.single_operator_variant_supplies_second is True
    return True


def recovery_handoff_requires_accepted_barrier(
    package: IncidentRecoveryHandoffPackage | None,
) -> bool:
    """Whether a recovery handoff may transfer any obligation (§5.9 line 142; §21 line 511).

    §5.9 verbatim: "**No obligation transfers until one current ADR-002-017 Recovery Session explicitly
    accepts the exact package.**" §21 line 511: "The Recovery Barrier **remains closed**." Both
    coordinates are **injected sbr verdicts** and both are **positive** polarity — only ``is True``
    admits, so an unknown ``None`` blocks the transfer and every obligation stays with its current owner.
    The package's own authority block must additionally be genuinely all-false (§5.9 "non-authorizing";
    §7 line 237 "incident closure cannot declare readiness"). The Recovery Barrier and the Recovery
    Session are sbr-owned (ADR-002-017), never re-authored here (design #28 §3.5).

    **Closes no SIR-EV** (SIR-EV-012 substrate; ``EV-L2/3+Security``).

    Args:
        package: The Incident Recovery Handoff Package (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the Recovery Barrier is positively closed, a Recovery Session has positively
        accepted the exact package, and the package grants nothing.
    """
    if package is None:
        return False
    if not all_false_incident_authority(package.authority_effect):
        return False
    return (
        package.recovery_barrier_closed is True
        and package.accepted_by_recovery_session is True
    )


# ===========================================================================
# §6b not-Phase-1 thin models — closes NO SIR-EV (design #28 §6b)
# ===========================================================================


def restriction_dominates_send(
    restriction_generation: int | None, send_generation: int | None
) -> bool:
    """Whether an incident restriction is ordered before a send boundary (§16 line 427/431).

    §16 line 427: every dependent new-risk authority issuance and final-egress decision SHALL actively
    establish the "absence of a newer declaration, scope expansion, demotion, shutdown, compromise, or
    closure invalidation **ordered before the claim/send boundary**". REUSES
    ``tos.ordering.compare_order`` through :func:`~tos.sir.state.incident_generation_advances`: ``True``
    means the restriction **provably** precedes the send and the send is denied.

    **This predicate answers one question only — "is the restriction provably first?" — and its
    ``False`` is not a clearance.** An unknown, equal or ambiguous ordering returns ``False`` here
    because nothing was proven, **not** because the send is admissible; the ordering-unprovable case is
    answered separately and conservatively by :func:`attempt_potentially_live`, which returns ``True``
    (potentially live) on exactly those inputs. A consumer that reads this ``False`` as "the send may
    proceed" would invert §16 line 431; the send-admissibility question belongs to the egress
    final-egress decision (design #28 §3.5), not here.

    The cache-free currentness protocol, the ``B_incident_restriction_to_egress`` bound and the deny-first
    latch are +Security runtime and egress-owned (design #28 §6b); §16 line 429 "Cached ``NO_INCIDENT``,
    stale status pages, TTL, heartbeat, service health, workflow reachability, quiet time, absence of
    alerts, or absence of a new event is **not currentness proof**."

    **Closes no SIR-EV** (SIR-EV-007 substrate; ``EV-L3+Security``).

    Args:
        restriction_generation: The restriction's ordering scalar (``None`` ⇒ ``False``).
        send_generation: The send boundary's ordering scalar (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the restriction provably precedes the send boundary.
    """
    return incident_generation_advances(restriction_generation, send_generation)


def attempt_potentially_live(
    restriction_generation: int | None,
    send_generation: int | None,
    first_byte_generation: int | None,
    final_quantity_proof_present: bool | None,
) -> bool:
    """Whether an attempt racing an incident restriction remains potentially live (§16 line 431).

    §16 line 431 verbatim: "If an incident restriction or scope expansion races a capability claim or
    first broker byte and **ordering cannot be proven, the attempt is potentially live, remains
    capacity-covered, cannot be blindly retried**, and the incident scope includes the possible effect."

    ``True`` means the attempt remains potentially live and capacity-covered. **The model demands a
    positive proof to clear and treats every unproven ordering as a race** — the polarity §16 line 431
    dictates:

    * without a positive Final Quantity Proof the attempt is potentially live outright (SIR-INV-010 line
      194 "Missing ACK is not proof of non-acceptance"; ``final_quantity_proof_present`` is positive
      polarity so an unknown ``None`` lands here);
    * with a Final Quantity Proof, the **only** clearing case is a *provable* ``RESTRICT < SEND`` —
      the restriction was ordered before the send boundary, so the send was denied before it happened
      (design #28 §6b "``RESTRICT<SEND ⇒ deny``");
    * **every other ordering is potentially live**: a ``None`` coordinate, an *equal* generation, an
      ``AMBIGUOUS`` comparison, and the ``SEND < RESTRICT < FIRST_BYTE`` interleaving alike. §16 line 431
      collapses them into one rule — "ordering **cannot be proven** ⇒ the attempt is potentially live".
      Requiring the positive proof rather than excluding the known-bad orderings is what keeps an
      equal-generation race (which ``compare_order`` reports as ``AMBIGUOUS``, i.e. not ``BEFORE``) on the
      conservative side.
    * a recorded first broker byte is a further *strictly conservative* trigger: if a byte exists at all,
      the deny cannot have taken effect before the wire, so the attempt stays potentially live even over a
      provable ``RESTRICT < SEND`` (§13 line 372 "missing ACK remains potentially accepted"; SIR-INV-007
      line 182 process state proves nothing). This never clears an attempt the ordering rule above would
      have kept live — it only adds a deny.

    The worst-credible capacity coverage is rcl-owned and +Broker (**rcl edge 0**); the no-blind-retry
    enforcement is egress / action-flow owned (design #28 §6b).

    **Closes no SIR-EV** (SIR-EV-007 substrate; ``EV-L3+Security``).

    Args:
        restriction_generation: The restriction's ordering scalar.
        send_generation: The send boundary's ordering scalar.
        first_byte_generation: The first-broker-byte ordering scalar (``None`` ⇒ no byte recorded).
        final_quantity_proof_present: Positive polarity — only ``is True`` proves final quantity.

    Returns:
        ``True`` iff the attempt remains potentially live and capacity-covered.
    """
    if final_quantity_proof_present is not True:
        return True
    # positive proof required: only a provable RESTRICT < SEND clears. `is not True` here is the
    # positive-polarity deny normalization over the ordering proof, so None / equal / AMBIGUOUS all
    # land on the conservative side (§16 line 431).
    if (
        incident_generation_advances(restriction_generation, send_generation)
        is not True
    ):
        return True
    # a recorded first broker byte contradicts the deny-before-send claim — strictly conservative.
    return first_byte_generation is not None


def external_activity_conservative(activity: ExternalActivityClaim | None) -> bool:
    """Whether external / manual emergency activity is treated conservatively (§15 line 405-412).

    §15 line 407-412 verbatim: such activity "is recorded as unattributed or attributed external activity
    under conservative evidence rules"; "**does not become retroactively compliant TOS transmission**";
    "does not prove execution, reduction, cancellation, or Final Quantity until normal evidence rules
    pass"; "**cannot release RCL capacity by operator statement**"; "**cannot clear HALT, close the
    incident, or re-arm**"; "**expands** reconciliation and dependency closure to every possibly affected
    account and order."

    The five "does not / cannot" coordinates are **negative** polarity and each must be positively
    ``False``; the expansion coordinate is **positive** polarity and must be positively ``True`` — §15
    line 412 makes the expansion mandatory, so an unknown ``None`` denies on both sides. The external
    incident procedure, the human authority, the credential custody and the reconciliation itself are
    +Broker / +Security runtime (design #28 §6b). **Broker-agnostic**: no concrete broker is named.

    **Closes no SIR-EV** (SIR-EV-011 substrate; ``EV-L2/3+Broker+Security``).

    Args:
        activity: The external / manual activity claim (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the external activity claims nothing and expands reconciliation and closure.
    """
    if activity is None:
        return False
    return (
        activity.retroactively_compliant_transmission is False
        and activity.proves_execution_or_final_quantity is False
        and activity.releases_capacity_by_operator_statement is False
        and activity.clears_halt_or_closes_incident is False
        and activity.re_arms is False
        and activity.expands_reconciliation_and_closure is True
    )
