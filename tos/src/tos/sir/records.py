"""sir digest-bound artifacts — the six safety-incident ledger citizens (design #28 §2).

Every artifact is a **pydantic v2 frozen model** (``frozen=True, extra="forbid"`` via
:class:`~tos.sir._base.FrozenModel`): ``extra="forbid"`` is the schema-level "omission is restrictive"
and frozen is the append-only realization; there is **no** update / delete / mutate / transmit / sign /
arm / clear-halt / declare / contain / shutdown / close method on any model (design #28 §2.3/§4.1 — the
constructive-absence canary). Field names use the ADR §5-§26 terms **verbatim** (spec terms = code
terms, boundary design #1 §2.4).

**Six id-independent artifacts (design #28 §2.1/§3.1).** ``SafetyIncidentPolicy`` /
``SafetyIncidentRecord`` / ``ActiveSafetyIncidentSet`` / ``IncidentContainmentPlan`` /
``IncidentRecoveryHandoffPackage`` / ``IncidentClosureDecision`` are **issued-identity** records
(:class:`~tos.sir._base.IndependentIdArtifact`, ``id != f(digest)``): the id is separately issued, so a
same-id / different-**covered**-bytes forged, re-issued or replayed record is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT`` — the structural defence ADR §22 line 536 demands against
"incident closure replay or duplicate consumption". §5.3 "an immutable **versioned** record"; §5.5 "One
**immutable canonical** set"; §5.7/§5.9 "immutable **non-authorizing**"; §5.10 "An immutable
independent result ... for one exact current incident and Active Safety Incident Set **digest**"; §20
line 505 "A closure decision is **single-use** for record transition only".

**SIR = greenfield incident-governance content owner, NO inbound deferee (design #28 §0.4b).** No
landed sibling defers incident *content* to ``tos.sir``: the concept sir produces is already consumed
by two siblings' de-restriction / recovery predicates and by wdr's injected generation coordinate, but
always as an **anonymous** ``bool | None`` / opaque scalar, never as a ``tos.sir`` type — so the seam is
**forward** and the sibling edge is **0**. sir re-authors **no** sibling boundary seal and imports
**neither** sibling.

**Malformed-model self-defence — positive-claim + incomplete-scope coexistence seal (the wdr
``SafetyDeviationDecision`` / rlp ``ExactTrialPlan`` / egress QCC isomorph; design #28 §2.3, #20
lesson).** Three artifacts carry a construction-time coexistence seal:

* ``IncidentClosureDecision`` — a ``CLOSE_ADMINISTRATIVELY`` result while the §20 mandated bindings
  (the exact Active Safety Incident Set digest, the 12-item closure contract with no unknown item) are
  missing is **unconstructable** (an administrative closure whose exact bindings are blank cannot
  exist, §5.10 / §20 line 490).
* ``ActiveSafetyIncidentSet`` — an ``is_complete`` / ``is_current`` claim while the set's Incident
  Generation or exact Safety Cell identity is absent is **unconstructable** (§5.5 "One immutable
  canonical set ... applicable to an **exact** Safety Cell and scope"), plus the per-member structural
  seal (no duplicate id, no dangling parent, ``shared_cause_ids`` ⊆ ``shared_dependencies``).
* ``SafetyIncidentRecord`` — a declared (non-``SUSPECTED``) lifecycle state while the greatest-credible
  incident scope is absent is **unconstructable** (§8 step 2 "the greatest credible affected dependency
  scope is calculated conservatively").

The ``model_construct`` escape hatch that skips validators is re-caught in the §5/§6 predicate layer
(defence in depth, design #28 §2.3): the yolk predicates re-derive completeness structurally and never
trust a stored flag.

**Coordinate non-collapse (design #28 §2.3).** No mutable lifecycle coordinate — the record
``lifecycle_state`` / ``record_state``, the active-set ``is_complete`` / ``is_current`` / ``state``, the
closure ``single_use_consumed`` / ``consumed_by_live_authority``, and the injected sibling verdicts
(``effective_principal_verdict`` hag, ``recovery_barrier_closed`` /
``accepted_by_recovery_session`` sbr, ``cancellation_arbiter_approved`` protective) — is a covered
digest field: a lawful transition (declaration, containment, closure, consumption) or an injected
verdict change must not change an artifact's digest and be mis-flagged as a same-id / different-bytes
``CRITICAL_CONFLICT`` (the rcl / egress / cur / rlp / wdr coordinate-non-collapse precedent). Every
covered field is an immutable claim; the current state / injected verdict is fed into the predicate.

**Digest rule (design #28 §2.3, Open Q 3).** ``_COVERED_FIELDS`` **excludes** each artifact's own
``*_digest`` field (preimage self-exclusion) but **includes** external reference digests
(``active_set_digest`` on the plan and the closure decision), so "which Active Safety Incident Set does
this close?" is bound unforgeably (§5.10). Numeric bounds (status / plan / closure-evidence ages, quorum
N) are excluded and Phase-1 null (design #28 §8). Nested models carrying ``frozenset`` / mapping fields
are kept **out** of the covered set to avoid unstable serialization (the wdr precedent); ``frozenset``
covered fields are **sorted** in :meth:`covered_content` so the digest is deterministic across
processes.

**All-false authority (design #28 §2.4; SIR-INV-001).** Every artifact carries an
:class:`~tos.sir._base.AllFalseIncidentAuthority` with every flag ``False`` — an incident artifact is
restrictive governed content, not permission.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.sir._base``) + ``tos.sir.*`` only; no
``shared.*``, no sibling ``tos.*`` (design #28 §0.3). Clock-free.

Regime tag: predicate substrate only; closes **no** SIR-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import model_validator

from tos.sir._base import (
    AllFalseIncidentAuthority,
    ArtifactIntegrityError,
    IndependentIdArtifact,
)
from tos.sir.state import (
    ActiveSetMember,
    ContainmentAction,
    ControlledShutdownProcedure,
    IncidentClassificationInput,
    IncidentDependencyClosure,
    IncidentScope,
    OngoingSafetyObligation,
    SafetySignal,
)
from tos.sir.vocabulary import (
    CLOSURE_CONTRACT_ITEM_COUNT,
    ClosureDecisionResult,
    IncidentLifecycleState,
    IncidentRecordState,
    SignalClassificationClass,
)

__all__ = [
    "SafetyIncidentPolicy",
    "SafetyIncidentRecord",
    "ActiveSafetyIncidentSet",
    "IncidentContainmentPlan",
    "IncidentRecoveryHandoffPackage",
    "IncidentClosureDecision",
    "AllFalseIncidentAuthority",
]


def _sorted_set_fields(content: dict[str, Any], *names: str) -> dict[str, Any]:
    """Sort the named ``frozenset``-derived list fields for a deterministic digest (§3.1)."""
    for name in names:
        value = content.get(name)
        if value is not None:
            content[name] = sorted(value)
    return content


class SafetyIncidentPolicy(IndependentIdArtifact):
    """The governed Safety Incident Policy content model (ADR-002-027 §5.1 line 106; design #28 §2.4).

    §5.1 verbatim: "An immutable ADR-002-014 governed policy defining authoritative signals,
    classification, severity, scope closure, required restrictions, containment and shutdown
    obligations, independence, evidence, currentness, escalation, closure, and recovery behavior." sir
    **authors** the policy *content* model, but the policy's **activation and generation are spg /
    ADR-002-014 governed** (§7 line 226 "Govern Safety Incident Policy | safety-configuration governance
    | ADR-002-014 activation | policy activation creates **no** incident or live permission") — carried
    as injected ``policy_generation`` / ``policy_digest`` scalars, re-authored not at all (design #28
    §3.5). An :class:`~tos.sir._base.IndependentIdArtifact` (``id != f(digest)``). Its
    :class:`~tos.sir._base.AllFalseIncidentAuthority` is all-false — a policy is governed content, not
    permission (SIR-INV-001).

    **Same-name / different-proposition seal** (design #28 §0.5 seal 2): ``spg/vocabulary.py:215-216``
    carries the governed-artifact-**kind** string tokens ``SAFETY_INCIDENT_POLICY`` /
    ``ACTIVE_SAFETY_INCIDENT_SET`` — those name the *kind of artifact ADR-002-014 governs*; this class
    is the *artifact model*. Different propositions; ``tos.spg`` is not imported (sibling edge 0).
    """

    _ID_FIELD: ClassVar[str] = "policy_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "policy_id",
        "policy_generation",
        "policy_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "policy_generation",
            "authoritative_signal_classes",
            "severity_rules",
            "scope_closure_rules",
            "required_restrictions",
            "escalation_paths",
            "controlled_shutdown_rules",
            "evidence_obligations",
            "independence_requirements",
            "closure_conditions",
            "failure_behavior",
            "authority_effect",
        }
    )

    policy_id: str | None = None
    #: Injected spg / ADR-002-014 activation generation (§7 line 226; ``None`` ⇒ fail-closed).
    policy_generation: int | None = None
    #: The policy's own digest — **self-excluded** from the covered preimage (design #28 §2.3).
    policy_digest: str | None = None
    #: The §8 line 248-257 classes the policy declares authoritative.
    authoritative_signal_classes: frozenset[SignalClassificationClass] = frozenset()
    severity_rules: tuple[str, ...] = ()
    scope_closure_rules: tuple[str, ...] = ()
    required_restrictions: tuple[str, ...] = ()
    escalation_paths: tuple[str, ...] = ()
    controlled_shutdown_rules: tuple[str, ...] = ()
    evidence_obligations: tuple[str, ...] = ()
    independence_requirements: tuple[str, ...] = ()
    closure_conditions: tuple[str, ...] = ()
    failure_behavior: tuple[str, ...] = ()
    #: §7 / SIR-INV-001 — a policy is governed content, not permission (all-false).
    authority_effect: AllFalseIncidentAuthority = AllFalseIncidentAuthority()

    def covered_content(self) -> dict[str, Any]:
        """Digest preimage with the ``frozenset`` class field serialized deterministically (§3.1)."""
        return _sorted_set_fields(
            super().covered_content(), "authoritative_signal_classes"
        )


class SafetyIncidentRecord(IndependentIdArtifact):
    """The immutable versioned Safety Incident Record (ADR-002-027 §5.3 line 116; design #28 §2.4).

    §5.3 verbatim: "An immutable versioned record of one incident identity, current Incident Generation,
    signals, severity, scope, dependency closure, restrictions, actions, obligations, evidence gaps,
    external activity, owners, and lifecycle state. **It grants no authority.**" §9 line 296: a material
    post-closure signal creates a new Incident Generation and a new or reopened immutable record — "it
    does not edit history", which is why ``predecessor_record_id`` is a covered claim and the lifecycle
    coordinates are not.

    **Coexistence seal (design #28 §2.3):** a declared (non-``SUSPECTED``) lifecycle state coexisting
    with an absent ``incident_scope`` is **unconstructable** — §8 step 2 requires that "the greatest
    credible affected dependency scope is calculated conservatively" before the restrictive workflow
    proceeds, so a record cannot claim to be past ``SUSPECTED`` while its exact scope is blank. The
    ``greatest_credible_scope_computed`` flag itself stays freely settable so the §5.1 polarity gate
    remains independently testable (the flag is a *claim*; this seal is about a *missing structure*).
    """

    _ID_FIELD: ClassVar[str] = "incident_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "incident_id",
        "record_version",
        "incident_generation",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "record_version",
            "predecessor_record_id",
            "incident_generation",
            "signals",
            "severity",
            "restrictions",
            "actions",
            "ongoing_obligations",
            "evidence_gaps",
            "external_activity",
            "owners",
            "classification",
            "greatest_credible_scope_computed",
            "restriction_workflow_gated",
            "severity_label_narrows_scope",
            "authority_effect",
        }
    )

    incident_id: str | None = None
    record_version: int | None = None
    #: The record's own digest — **self-excluded** from the covered preimage (design #28 §2.3).
    record_digest: str | None = None
    predecessor_record_id: str | None = None
    #: The §5.4 Incident Generation ordering scalar (an ordering identity, never a clock).
    incident_generation: int | None = None
    signals: tuple[SafetySignal, ...] = ()
    severity: str | None = None
    #: The §10 exact greatest-credible scope (kept out of the covered set — mapping/frozenset payload).
    incident_scope: IncidentScope | None = None
    #: The §5.6 22-dimension closure (kept out of the covered set — mapping/frozenset payload).
    dependency_closure: IncidentDependencyClosure | None = None
    restrictions: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    ongoing_obligations: tuple[OngoingSafetyObligation, ...] = ()
    evidence_gaps: tuple[str, ...] = ()
    external_activity: tuple[str, ...] = ()
    owners: tuple[str, ...] = ()
    #: Mutable lifecycle coordinate — **not** covered (coordinate non-collapse, design #28 §2.3).
    lifecycle_state: IncidentLifecycleState | None = None
    #: Mutable record-version coordinate — **not** covered (coordinate non-collapse).
    record_state: IncidentRecordState | None = None
    classification: IncidentClassificationInput | None = None
    #: Positive polarity (§8 step 2; SIR-INV-003) — only ``is True`` admits.
    greatest_credible_scope_computed: bool | None = None
    #: Negative polarity (§8 step 3 / §1 line 21; SIR-INV-002) — only ``is False`` clears.
    restriction_workflow_gated: bool | None = None
    #: Negative polarity (§8 line 269; SIR-INV-003) — only ``is False`` clears.
    severity_label_narrows_scope: bool | None = None
    #: §5.3 "It grants no authority" (all-false, SIR-INV-001).
    authority_effect: AllFalseIncidentAuthority = AllFalseIncidentAuthority()

    @model_validator(mode="after")
    def _declared_record_has_exact_scope(self) -> SafetyIncidentRecord:
        """A non-``SUSPECTED`` record with no exact scope is unconstructable (§8 step 2; §2.3)."""
        state = self.lifecycle_state
        if (
            state is not None
            and state is not IncidentLifecycleState.SUSPECTED
            and self.incident_scope is None
        ):
            raise ArtifactIntegrityError(
                "SafetyIncidentRecord past SUSPECTED requires an exact incident_scope "
                f"(lifecycle_state={state.value!r}, incident_scope=None) — the greatest credible "
                "affected dependency scope is calculated conservatively before the restrictive "
                "workflow proceeds (ADR-002-027 §8 step 2; SIR-INV-003 line 166 'Unknown, stale, "
                "conflicting, incomplete, wildcard, patched, or self-selected scope expands "
                "containment; it never narrows permission')"
            )
        return self


class ActiveSafetyIncidentSet(IndependentIdArtifact):
    """The immutable canonical Active Safety Incident Set (ADR §5.5 line 126; design #28 §2.4).

    §5.5 verbatim: "**One immutable canonical set of every** suspected or open incident and shared
    dependency **applicable to an exact Safety Cell and scope**. It is **restrictive input** to
    separately owned authority and currentness controls, **not authority itself**." SIR-INV-004 line 170:
    "A consumer **cannot select, union, or close** artifacts to create broader permission."

    **Per-member structure (design #28 §2.4 C2-2).** ``members`` is a tuple of
    :class:`~tos.sir.state.ActiveSetMember`, replacing v1.0's parallel ``member_incidents`` /
    ``member_digests`` tuples: the parallel form admitted a length-mismatch / order-skew defect class
    that the structure removes. The validator seals (i) no duplicate ``incident_id``, (ii) no dangling
    ``parent_id`` (a declared parent must be a member), (iii) ``shared_cause_ids`` ⊆
    ``shared_dependencies``.

    **Explicit-empty is valid (design #28 §4.4, the #26 MAJOR-1 over-sealing lesson).** A no-incident
    bundle's canonical representation is ``members = ()`` with ``is_complete`` / ``is_current``
    positively ``True``: §5.5 line 126 scopes the canonical set to what is "applicable to" the exact
    Safety Cell (applicable = ∅ ⇒ the canonical form is the explicit empty set), and §16 line 423-424
    requires every final-egress decision to actively establish the "current Incident Generation and
    exact Active Safety Incident Set digest" even with no incident — so a representation that cannot
    express ∅ would violate §16. Rejecting it would be a defect, not a seal.

    **Coexistence seal (design #28 §2.3):** an ``is_complete`` / ``is_current`` claim while the set's
    Incident Generation or exact Safety Cell identity is absent is **unconstructable** (§5.5 "an exact
    Safety Cell"; §10 line 311 "the remaining Active Safety Incident Set is complete and current").
    """

    _ID_FIELD: ClassVar[str] = "active_set_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "active_set_id",
        "active_set_generation",
        "incident_generation",
        "safety_cell",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "active_set_generation",
            "incident_generation",
            "safety_cell",
            "shared_dependencies",
            "authority_effect",
        }
    )

    active_set_id: str | None = None
    active_set_generation: int | None = None
    #: The set's own digest — **self-excluded** from the covered preimage (design #28 §2.3).
    active_set_digest: str | None = None
    #: The §5.4 Incident Generation ordering scalar this canonical set is fenced to.
    incident_generation: int | None = None
    #: The exact Safety Cell the set is applicable to (§5.5 line 126).
    safety_cell: str | None = None
    #: The per-incident structural members (kept out of the covered set — frozenset payload).
    members: tuple[ActiveSetMember, ...] = ()
    shared_dependencies: tuple[str, ...] = ()
    #: Positive polarity (§5.5 canonical set; §10 line 311) — only ``is True`` admits.
    is_complete: bool | None = None
    #: Positive polarity (§10 line 311; SIR-INV-011) — only ``is True`` admits.
    is_current: bool | None = None
    #: Mutable set-level lifecycle coordinate — **not** covered (coordinate non-collapse).
    state: IncidentLifecycleState | None = None
    #: §5.5 "not authority itself" (all-false, SIR-INV-001).
    authority_effect: AllFalseIncidentAuthority = AllFalseIncidentAuthority()

    @model_validator(mode="after")
    def _member_structure_is_sound(self) -> ActiveSafetyIncidentSet:
        """Seal duplicate ids, dangling parents and out-of-set shared causes (design #28 §2.4 C2-2)."""
        member_ids = [member.incident_id for member in self.members]
        if len(set(member_ids)) != len(member_ids):
            raise ArtifactIntegrityError(
                "ActiveSafetyIncidentSet members carry a duplicate incident_id — one canonical set "
                "represents each incident exactly once (ADR-002-027 §5.5; SIR-INV-004 line 170)"
            )
        known = set(member_ids)
        shared = set(self.shared_dependencies)
        for member in self.members:
            if member.parent_id is not None and member.parent_id not in known:
                raise ArtifactIntegrityError(
                    f"ActiveSafetyIncidentSet member {member.incident_id!r} declares parent_id "
                    f"{member.parent_id!r} which is not a member — a dangling parent would hide an "
                    "open parent from the no-favorable-subset derivation (ADR-002-027 §10 line "
                    "307-311; SIR-INV-004)"
                )
            if not member.shared_cause_ids <= shared:
                raise ArtifactIntegrityError(
                    f"ActiveSafetyIncidentSet member {member.incident_id!r} declares shared causes "
                    f"{sorted(member.shared_cause_ids - shared)!r} absent from the set's "
                    "shared_dependencies — the canonical set represents every shared dependency "
                    "(ADR-002-027 §5.5 line 126; §10 line 305)"
                )
        return self

    @model_validator(mode="after")
    def _complete_claim_requires_exact_identity(self) -> ActiveSafetyIncidentSet:
        """A complete / current claim needs the exact generation + Safety Cell (§5.5; §10 line 311)."""
        claims_complete = self.is_complete is True or self.is_current is True
        if claims_complete and (
            self.incident_generation is None or self.safety_cell is None
        ):
            raise ArtifactIntegrityError(
                "ActiveSafetyIncidentSet claims complete / current while its exact identity is "
                f"blank (incident_generation={self.incident_generation!r}, "
                f"safety_cell={self.safety_cell!r}) — the canonical set is 'applicable to an exact "
                "Safety Cell and scope' (ADR-002-027 §5.5 line 126) and §10 line 311 requires the "
                "remaining set to be complete and current for one exact generation"
            )
        return self

    def covered_content(self) -> dict[str, Any]:
        """Digest preimage (the member tuple stays out — frozenset payload, design #28 §2.3)."""
        return super().covered_content()


class IncidentContainmentPlan(IndependentIdArtifact):
    """The immutable non-authorizing Incident Containment Plan (ADR §5.7/§11; design #28 §2.4).

    §5.7 verbatim: "An immutable **non-authorizing** plan that orders restrictions, hard fences,
    reconciliation, protection review, capacity quarantine, evidence preservation, external-activity
    handling, notifications, and recovery prerequisites for **one exact Incident Generation**." §11 line
    320-329 enumerates the field groups the plan SHALL bind; line 332 "**The plan cannot authorize its
    actions.**"

    Each :class:`~tos.sir.state.ContainmentAction` carries the five §11 line 327 separately owned
    prerequisite references (classifier / authority / capacity / currentness / final-egress) as
    **injected opaque references** — sir re-authors none of those owners (design #28 §3.5). §11 line 333:
    an action labelled ``exit`` / ``reduce-only`` / ``cancel`` / ``replace`` / ``protective`` /
    ``emergency`` / ``incident-critical`` "is not assumed executable or risk reducing".

    The three §14 protective coordinates (``protection_blindly_cancelled`` /
    ``cancellation_arbiter_approved`` / ``exposure_reported_safely_closed``) are the §6.4 carriers of §14
    line 388 "Existing protection SHALL NOT be **blindly cancelled**", §12 step 6 "obtain **Cancellation
    Arbiter approval** before changing safety-owned protection" (a protective-owned injected verdict),
    and §14 line 397 "the system SHALL NOT **report the exposure safely closed**".
    """

    _ID_FIELD: ClassVar[str] = "plan_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "plan_id",
        "plan_generation",
        "incident_generation",
        "active_set_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "plan_generation",
            "incident_id",
            "active_set_digest",
            "incident_generation",
            "severity",
            "signals",
            "hazards",
            "committed_restrictions",
            "hard_fences",
            "stale_owner_disposition",
            "positions",
            "orders",
            "potentially_live_quantity",
            "external_activity",
            "rcl_commitments",
            "protection_obligations",
            "proposed_actions",
            "evidence",
            "notification",
            "handoff",
            "escalation",
            "failure_behavior",
            "recovery_barrier_trigger",
            "authority_effect",
        }
    )

    plan_id: str | None = None
    plan_generation: int | None = None
    #: The plan's own digest — **self-excluded** from the covered preimage (design #28 §2.3).
    plan_digest: str | None = None
    incident_id: str | None = None
    #: An **external** reference digest — covered, so "which set does this plan bind?" is unforgeable.
    active_set_digest: str | None = None
    #: The one exact §5.4 Incident Generation the plan is bound to (§11 line 322).
    incident_generation: int | None = None
    #: The §10 exact scope (kept out of the covered set — mapping/frozenset payload).
    scope: IncidentScope | None = None
    severity: str | None = None
    signals: tuple[SafetySignal, ...] = ()
    hazards: tuple[str, ...] = ()
    #: The §5.6 closure (kept out of the covered set — mapping/frozenset payload).
    dependency_closure: IncidentDependencyClosure | None = None
    committed_restrictions: tuple[str, ...] = ()
    hard_fences: tuple[str, ...] = ()
    stale_owner_disposition: tuple[str, ...] = ()
    positions: tuple[str, ...] = ()
    orders: tuple[str, ...] = ()
    potentially_live_quantity: tuple[str, ...] = ()
    external_activity: tuple[str, ...] = ()
    rcl_commitments: tuple[str, ...] = ()
    #: The §14 / §5.11 protection obligations the shutdown must preserve or deliberately transfer.
    protection_obligations: tuple[OngoingSafetyObligation, ...] = ()
    proposed_actions: tuple[ContainmentAction, ...] = ()
    #: The §5.8 ordered section (kept out of the covered set — frozenset payload).
    controlled_shutdown: ControlledShutdownProcedure | None = None
    evidence: tuple[str, ...] = ()
    notification: tuple[str, ...] = ()
    handoff: tuple[str, ...] = ()
    escalation: tuple[str, ...] = ()
    failure_behavior: tuple[str, ...] = ()
    recovery_barrier_trigger: str | None = None
    #: Negative polarity (§14 line 388) — only ``is False`` clears.
    protection_blindly_cancelled: bool | None = None
    #: Positive polarity (§12 step 6, protective-owned injected verdict) — only ``is True`` admits.
    cancellation_arbiter_approved: bool | None = None
    #: Negative polarity (§14 line 397) — only ``is False`` clears.
    exposure_reported_safely_closed: bool | None = None
    #: §11 line 332 "The plan cannot authorize its actions" (all-false, SIR-INV-001).
    authority_effect: AllFalseIncidentAuthority = AllFalseIncidentAuthority()


class IncidentRecoveryHandoffPackage(IndependentIdArtifact):
    """The immutable non-authorizing Recovery Handoff Package (ADR §5.9 line 142; design #28 §2.4).

    §5.9 verbatim: "An immutable **non-authorizing** package binding the exact incident and Active
    Safety Incident Set generation to every unresolved economic, protection, capacity, evidence,
    external-activity, fencing, and recovery obligation. **No obligation transfers until one current
    ADR-002-017 Recovery Session explicitly accepts the exact package.**" §21 line 511 "The Recovery
    Barrier remains closed."

    ``recovery_barrier_closed`` and ``accepted_by_recovery_session`` are **injected sbr (ADR-002-017)
    verdicts** — sir re-authors neither the Recovery Barrier nor the Recovery Session (design #28 §3.5).
    Both are positive polarity: only ``is True`` admits, so an unknown ``None`` blocks the handoff and
    leaves every obligation with its current owner.
    """

    _ID_FIELD: ClassVar[str] = "handoff_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "handoff_id",
        "handoff_generation",
        "incident_id",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "handoff_generation",
            "incident_id",
            "active_set_generation",
            "unresolved_obligations",
            "authority_effect",
        }
    )

    handoff_id: str | None = None
    handoff_generation: int | None = None
    #: The package's own digest — **self-excluded** from the covered preimage (design #28 §2.3).
    handoff_digest: str | None = None
    incident_id: str | None = None
    active_set_generation: int | None = None
    unresolved_obligations: tuple[OngoingSafetyObligation, ...] = ()
    #: Positive polarity — injected sbr (ADR-002-017) Recovery Barrier verdict (§21 line 511).
    recovery_barrier_closed: bool | None = None
    #: Positive polarity — injected sbr Recovery Session acceptance verdict (§5.9 line 142).
    accepted_by_recovery_session: bool | None = None
    #: §5.9 "non-authorizing" (all-false, SIR-INV-001).
    authority_effect: AllFalseIncidentAuthority = AllFalseIncidentAuthority()


class IncidentClosureDecision(IndependentIdArtifact):
    """The immutable single-use Incident Closure Decision (ADR §5.10/§20; design #28 §2.4).

    §5.10 verbatim: "An immutable independent result of ``DENY``, ``HOLD``, or
    ``CLOSE_ADMINISTRATIVELY`` for **one exact current incident and Active Safety Incident Set digest**.
    **It creates no permissive state.**" §20 line 505: "A closure decision is **single-use** for record
    transition only and **cannot be consumed by a live-authority path**." SIR-INV-012 line 202: closure
    "does not establish safe state, release capacity, clear UNKNOWN or HALT, validate configuration,
    restore scope, satisfy recovery, or authorize transmission."

    ``closure_contract_items`` carries the §20 line 492-503 **12-item** contract, one ``bool | None``
    per item, in ADR order; :data:`~tos.sir.vocabulary.CLOSURE_CONTRACT_ITEMS` labels them and
    :data:`~tos.sir.vocabulary.CLOSURE_CONTRACT_ITEM_POLARITY` fixes each slot's polarity (item 11 is
    the single negative slot). ``effective_principal_verdict`` is an **injected hag** (ADR-002-015)
    verdict (§20 item 10) — sir re-authors no quorum counting.

    **Coexistence seal (design #28 §2.3):** a ``CLOSE_ADMINISTRATIVELY`` result while the exact Active
    Safety Incident Set digest is absent, or while the 12-item contract is the wrong length or carries
    any unknown (``None``) item, is **unconstructable**. The predicate layer re-checks the same facts so
    a ``model_construct`` bypass is caught twice (defence in depth).
    """

    _ID_FIELD: ClassVar[str] = "closure_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "closure_id",
        "closure_generation",
        "incident_id",
        "active_set_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "closure_generation",
            "incident_id",
            "active_set_digest",
            "incident_generation",
            "result",
            "closure_contract_items",
            "authority_effect",
        }
    )

    closure_id: str | None = None
    closure_generation: int | None = None
    #: The decision's own digest — **self-excluded** from the covered preimage (design #28 §2.3).
    closure_digest: str | None = None
    incident_id: str | None = None
    #: An **external** reference digest — covered, so "which exact set does this close?" is unforgeable.
    active_set_digest: str | None = None
    incident_generation: int | None = None
    result: ClosureDecisionResult | None = None
    #: The §20 line 492-503 12-item contract, one ``bool | None`` per item in ADR order.
    closure_contract_items: tuple[bool | None, ...] = ()
    #: Positive polarity — injected hag (ADR-002-015) Effective Principal verdict (§20 item 10).
    effective_principal_verdict: bool | None = None
    #: Negative polarity (§20 line 505 "single-use") — **not** covered (mutable consumption coordinate).
    single_use_consumed: bool | None = None
    #: Negative polarity (§20 line 505 "cannot be consumed by a live-authority path") — not covered.
    consumed_by_live_authority: bool | None = None
    #: §5.10 "It creates no permissive state" (all-false, SIR-INV-001 / SIR-INV-012).
    authority_effect: AllFalseIncidentAuthority = AllFalseIncidentAuthority()

    @model_validator(mode="after")
    def _administrative_closure_binds_exactly(self) -> IncidentClosureDecision:
        """A ``CLOSE_ADMINISTRATIVELY`` decision with blank §20 bindings is unconstructable (§2.3)."""
        if self.result is not ClosureDecisionResult.CLOSE_ADMINISTRATIVELY:
            return self
        if self.active_set_digest is None:
            raise ArtifactIntegrityError(
                "CLOSE_ADMINISTRATIVELY requires the exact Active Safety Incident Set digest "
                "(active_set_digest=None) — ADR-002-027 §5.10 line 146 'for one exact current "
                "incident and Active Safety Incident Set digest'"
            )
        if len(self.closure_contract_items) != CLOSURE_CONTRACT_ITEM_COUNT:
            raise ArtifactIntegrityError(
                "CLOSE_ADMINISTRATIVELY requires exactly "
                f"{CLOSURE_CONTRACT_ITEM_COUNT} closure-contract items "
                f"(got {len(self.closure_contract_items)}) — ADR-002-027 §20 line 490-503 "
                "'Administrative closure requires all of the following'"
            )
        if any(item is None for item in self.closure_contract_items):
            unknown = [
                index
                for index, item in enumerate(self.closure_contract_items, start=1)
                if item is None
            ]
            raise ArtifactIntegrityError(
                f"CLOSE_ADMINISTRATIVELY carries unknown closure-contract items {unknown!r} — an "
                "unknown item is not a satisfied item (ADR-002-027 §20 line 490; SIR-INV-009 line "
                "190 UNKNOWN remains conservative)"
            )
        return self
