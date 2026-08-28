"""stm digest-bound artifacts — the seven safety-telemetry ledger citizens (design #30 §2).

Every artifact is a **pydantic v2 frozen model** (``frozen=True, extra="forbid"`` via
:class:`~tos.stm._base.FrozenModel`): ``extra="forbid"`` is the schema-level "omission is restrictive"
and frozen is the append-only realization; there is **no** update / delete / mutate / transmit / collect
/ publish / deliver / escalate / suppress method on any model (design #30 §2.3/§4.1 — the
constructive-absence canary). Field names use the ADR §5-§24 terms **verbatim** (spec terms = code
terms, boundary design #1 §2.4).

**Seven id-independent artifacts (design #30 §2.1/§3.1).** ``SafetyMonitoringPolicy`` /
``CriticalTelemetryManifest`` / ``MonitorCoverageManifest`` / ``ContinuousConformanceSnapshot`` /
``SafetyMonitoringGap`` / ``SafetyAlertRecord`` / ``AlertEscalationRecord`` are **issued-identity**
records (:class:`~tos.stm._base.IndependentIdArtifact`, ``id != f(digest)``): the id is separately
issued, so a same-id / different-**covered**-bytes forged, re-issued or replayed record is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT`` — the structural defence ADR §22 line 474 demands for
"raw and derived telemetry integrity and continuity". §5.1 "The **immutable** governed policy"; §5.3
"The **immutable** registry ... **It grants no authority**"; §5.4 "The **immutable** mapping"; §5.6 "A
**non-authorizing** consistency cut"; §5.7 "An **immutable** record"; §5.8/§5.9 "An **immutable
non-authorizing** record".

**STM = greenfield telemetry-integrity content owner, NO inbound deferee (design #30 §0.4b).** No landed
sibling defers telemetry *content* to ``tos.stm``. What is unusual is the richness of the **forward**
seam: four committed siblings already consume coordinates stm will produce — cur's
``MONITORING`` currentness dimension key (``cur/vocabulary.py:144``, inside cur's mandated
floor at ``:172``), spg's three governed-artifact-**kind** tokens (``spg/vocabulary.py:217-219``), rlp's
``monitoring_not_preventive`` plus its "injected -028 (STM) coordinate, not landed"
(``rlp/predicates.py:774-780``) and sir's anticipated "-028 handoff" (``sir/predicates.py:15``;
``sir/state.py:46``). **Every one of those consumptions is an anonymous dimension name, string token,
``bool | None`` or opaque generation — none references a ``tos.stm`` type — so the seam is forward and
the sibling edge is 0.** stm produces those coordinates' *values* and *artifacts*; the MONITORING
dimension's **completeness judgement stays cur-owned** and is re-authored here not at all.

**Malformed-model self-defence — CONFORMING-claim + incomplete-scope coexistence seal (the sir
``IncidentClosureDecision`` / wdr ``SafetyDeviationDecision`` / egress QCC isomorph; design #30 §2.3, #20
lesson).** Two artifacts carry a construction-time coexistence seal:

* ``ContinuousConformanceSnapshot`` — a ``CONFORMING`` aggregate result while the §12 line 324-333
  mandated bindings are absent, while **no** monitor result is bound, while the source-continuity fact
  is unknown, or while an active violation / unknown / gap / delivery failure is recorded, is
  **unconstructable** (§12 line 335 "``CONFORMING`` requires **every** required item to be current,
  complete, and independently valid under policy").
* ``MonitorCoverageManifest`` — an ``is_complete`` claim while the manifest's identity, generation or
  policy binding is absent, or while any coverage item carries no obligation reference, or while any
  submitted Monitored Assumption carries no id, is **unconstructable** (§9 "complete and exact"; §5.4
  "The immutable mapping from **every** applicable ... item").

A third, ``AlertEscalationRecord``, carries the §5.9 single-binding structural seal: a record with
delivery attempts, escalation stages or handoffs but no ``bound_alert_id`` is unconstructable ("bound to
**exactly one** Safety Alert Record").

Each seal is about a **missing structure**, never about a flag's value — the polarity flags stay freely
settable so the §5/§6 gates remain independently testable. The ``model_construct`` escape hatch that
skips validators is re-caught in the §5/§6 predicate layer (defence in depth, design #30 §2.3): the yolk
and supporting predicates re-derive completeness structurally and never trust a stored flag.

**Coordinate non-collapse (design #30 §2.3).** No mutable lifecycle coordinate — the snapshot
``aggregate_result``, the gap ``closure_proof_present``, and every injected sibling verdict — is a
covered digest field: a lawful transition (evaluate / gap / suppress / escalate / close) must not change
an artifact's digest and be mis-flagged as a same-id / different-bytes ``CRITICAL_CONFLICT``. Every
covered field is an immutable claim; the current state is fed into the predicate instead.

**Digest rule (design #30 §2.3).** ``_COVERED_FIELDS`` **excludes** each artifact's own ``*_digest``
field (preimage self-exclusion) but **includes** external reference digests (``policy_digest`` on the
coverage manifest and the snapshot, ``bound_alert_id`` on the escalation record), so "which alert does
this escalation belong to?" is bound unforgeably (§5.9). Numeric bounds (telemetry / snapshot / alert
ages, suppression duration) are excluded and Phase-1 null (design #30 §8). Nested models carrying
``frozenset`` fields are kept **out** of the covered set to avoid unstable serialization (the sir / wdr
precedent); ``frozenset`` covered fields are **sorted** in :meth:`covered_content` so the digest is
deterministic across processes.

**All-false authority (design #30 §2.4; STM-INV-001).** Every artifact carries an
:class:`~tos.stm._base.AllFalseMonitoringAuthority` with every flag ``False`` — a monitoring artifact is
non-authorizing observation, not permission. That holds for a ``CONFORMING`` snapshot too (§1 line 25).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.stm._base``) + ``tos.stm.*`` only; no
``shared.*``, no sibling ``tos.*`` (design #30 §0.3). Clock-free.

Regime tag: coverage-completeness / deterministic-evaluation predicate substrate only; closes **no**
STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import model_validator

from tos.stm._base import (
    AllFalseMonitoringAuthority,
    ArtifactIntegrityError,
    IndependentIdArtifact,
)
from tos.stm.state import (
    ApprovedBoundBinding,
    CoverageItem,
    CriticalTelemetryIdentity,
    MonitoredAssumptionIntake,
    MonitorEvaluation,
)
from tos.stm.vocabulary import AggregateConformanceResult, MonitoringGapKind

__all__ = [
    "SafetyMonitoringPolicy",
    "CriticalTelemetryManifest",
    "MonitorCoverageManifest",
    "ContinuousConformanceSnapshot",
    "SafetyMonitoringGap",
    "SafetyAlertRecord",
    "AlertEscalationRecord",
    "AllFalseMonitoringAuthority",
]


class SafetyMonitoringPolicy(IndependentIdArtifact):
    """The governed Safety Monitoring Policy content model (ADR-002-028 §5.1 line 111; design #30 §2.4).

    §5.1 verbatim: "The immutable governed policy defining Critical Telemetry, coverage, approved
    monitors, semantics, bounds, independence, restrictive response, suppression, alerting, escalation,
    evidence, currentness, and recovery behavior." §1 line 19 requires exactly "One active ADR-002-014
    governed Safety Monitoring Policy". stm **authors** the policy *content* model, but the policy's
    **activation and generation are spg / ADR-002-014 governed** (§7 line 228 "Govern telemetry and
    coverage semantics | Safety Monitoring Policy governance | cannot activate configuration or arm live
    scope") — carried as injected ``policy_generation`` / ``policy_digest`` scalars, re-authored not at
    all (design #30 §3.5). Its :class:`~tos.stm._base.AllFalseMonitoringAuthority` is all-false — a
    policy is governed content, not permission (STM-INV-001).

    **Same-name / different-proposition seal** (design #30 §0.5 seal 2): ``spg/vocabulary.py:217``
    carries the governed-artifact-**kind** string token ``SAFETY_MONITORING_POLICY`` — that names the
    *kind of artifact ADR-002-014 governs*; this class is the *artifact model*. Different propositions;
    ``tos.spg`` is not imported (sibling edge 0).
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
            "critical_telemetry_classes",
            "coverage_requirements",
            "approved_monitor_digests",
            "bound_bindings",
            "independence_requirements",
            "suppression_rules",
            "alert_escalation_paths",
            "evidence_obligations",
            "currentness_rules",
            "recovery_behavior",
            "failure_behavior",
            "authority_effect",
        }
    )

    policy_id: str | None = None
    #: Injected spg / ADR-002-014 activation generation (§7 line 228; ``None`` ⇒ fail-closed).
    policy_generation: int | None = None
    #: The policy's own digest — **self-excluded** from the covered preimage (design #30 §2.3).
    policy_digest: str | None = None
    critical_telemetry_classes: tuple[str, ...] = ()
    coverage_requirements: tuple[str, ...] = ()
    approved_monitor_digests: tuple[str, ...] = ()
    #: The §11 approved bound bindings (evaluator digest, units, states, windows, uncertainty).
    bound_bindings: tuple[ApprovedBoundBinding, ...] = ()
    independence_requirements: tuple[str, ...] = ()
    suppression_rules: tuple[str, ...] = ()
    alert_escalation_paths: tuple[str, ...] = ()
    evidence_obligations: tuple[str, ...] = ()
    currentness_rules: tuple[str, ...] = ()
    recovery_behavior: tuple[str, ...] = ()
    failure_behavior: tuple[str, ...] = ()
    #: §1 line 25 / STM-INV-001 — a policy is governed content, not permission (all-false).
    authority_effect: AllFalseMonitoringAuthority = AllFalseMonitoringAuthority()


class CriticalTelemetryManifest(IndependentIdArtifact):
    """The immutable Critical Telemetry registry (ADR-002-028 §5.3 line 119; §8; design #30 §2.4).

    §5.3 verbatim: "The immutable registry of exact telemetry identities, owners, source identities,
    scopes, units, schemas, semantics, continuity rules, derivations, time bases, freshness rules,
    failure domains, and consumers. **It grants no authority.**" The twelve §8 line 253-265 binding
    groups are transcribed as :data:`~tos.stm.vocabulary.CRITICAL_TELEMETRY_BINDING_GROUPS`; each
    identity is a :class:`~tos.stm.state.CriticalTelemetryIdentity`.

    §8 line 249 governs classification: "**Unknown materiality is Critical.** A producer, monitor owner,
    dashboard owner, or consumer SHALL NOT self-classify a telemetry item as non-Critical merely because
    the underlying preventive control exists elsewhere." §8 line 267: "Hash equality, metric name,
    topic, label, dashboard panel, or source health alone does not establish semantic equivalence."

    The ADR-002-029 release-lineage group (§8 line 253) is an **injected opaque coordinate**: the -029
    owner is not landed at authoring time and its content is never re-judged here (design #30 §0.4f).

    **Same-name / different-proposition seal** (design #30 §0.5 seal 2): ``spg/vocabulary.py:218``
    ``CRITICAL_TELEMETRY_MANIFEST`` is a governed-artifact-**kind** token, not this model.
    """

    _ID_FIELD: ClassVar[str] = "manifest_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "manifest_id",
        "manifest_generation",
        "manifest_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "manifest_generation",
            "telemetry_identities",
            "authority_effect",
        }
    )

    manifest_id: str | None = None
    manifest_generation: int | None = None
    #: The manifest's own digest — **self-excluded** from the covered preimage (design #30 §2.3).
    manifest_digest: str | None = None
    #: The §8 line 253-265 bound telemetry identities.
    telemetry_identities: tuple[CriticalTelemetryIdentity, ...] = ()
    #: §5.3 line 119 verbatim "It grants no authority" (all-false).
    authority_effect: AllFalseMonitoringAuthority = AllFalseMonitoringAuthority()


class MonitorCoverageManifest(IndependentIdArtifact):
    """The immutable Monitor Coverage Manifest (§5.4 line 123; §9; design #30 §2.4 — yolk 1 carrier).

    §5.4 verbatim: "The immutable mapping from **every** applicable Critical requirement, hazard,
    accepted control, bound, live prerequisite, and failure mode to its exact telemetry, evaluator,
    dependency closure, restrictive response, alert path, evidence path, and currentness rule." §9 line
    273: "Coverage SHALL begin from the **normative requirement and hazard registry**, not from whichever
    metrics happen to exist."

    ``coverage_score_present`` is **negative** polarity and carries §9 line 292 verbatim: "**Coverage
    percentages, monitor counts, or dashboard completeness scores cannot replace item-level closure. A
    favorable union of narrow manifests cannot create broader coverage.**" A manifest that offers a score
    in place of item-level closure denies.

    ``submitted_monitored_assumptions`` carries the §9 line 288 (v0.2 patch) intake: each Monitored
    Assumption (ADR-DEV-011 TAB-INV-006) is "a manifest item subject to the same 1-12 closure ... and
    **never as an out-of-band addition**".

    **Coexistence seal (design #30 §2.3):** an ``is_complete`` claim coexisting with an absent identity /
    generation / policy binding, with a coverage item that has no obligation reference, or with a
    submitted assumption that has no id is **unconstructable** — a "complete and exact" mapping whose
    structure is blank cannot exist. The flags themselves stay freely settable so the §5.1 polarity gates
    remain independently testable (the flag is a *claim*; this seal is about a *missing structure*).
    """

    _ID_FIELD: ClassVar[str] = "coverage_manifest_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "coverage_manifest_id",
        "coverage_generation",
        "policy_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "coverage_generation",
            "policy_digest",
            "submitted_monitored_assumptions",
            "is_complete",
            "coverage_score_present",
            "authority_effect",
        }
    )

    coverage_manifest_id: str | None = None
    coverage_generation: int | None = None
    #: The manifest's own digest — **self-excluded** from the covered preimage (design #30 §2.3).
    coverage_manifest_digest: str | None = None
    #: External reference digest — **covered**, so "which policy?" is bound unforgeably (§2.3).
    policy_digest: str | None = None
    #: The per-obligation mappings (kept out of the covered set — nested ``frozenset`` payload).
    coverage_items: tuple[CoverageItem, ...] = ()
    #: The §9 line 290 approved exclusions (kept out of the covered set — nested payload).
    approved_exclusions: tuple[CoverageItem, ...] = ()
    #: The §9 line 288 assumption-derived intake (ADR-DEV-011 TAB-INV-006).
    submitted_monitored_assumptions: tuple[MonitoredAssumptionIntake, ...] = ()
    #: Positive — §9 "complete and exact"; STM-INV-002 line 163.
    is_complete: bool | None = None
    #: **Negative** — §9 line 292 a score cannot replace item-level closure.
    coverage_score_present: bool | None = None
    #: §1 line 25 / STM-INV-001 — a coverage manifest grants nothing (all-false).
    authority_effect: AllFalseMonitoringAuthority = AllFalseMonitoringAuthority()

    @model_validator(mode="after")
    def _complete_claim_requires_structure(self) -> MonitorCoverageManifest:
        """Reject an ``is_complete`` claim coexisting with missing structure (§5.4/§9; design #30 §2.3)."""
        if self.is_complete is not True:
            return self
        for name in ("coverage_manifest_id", "coverage_generation", "policy_digest"):
            if getattr(self, name) is None:
                raise ArtifactIntegrityError(
                    f"MonitorCoverageManifest.is_complete is True while {name} is absent — a "
                    "'complete and exact' mapping (ADR-002-028 §5.4 line 123; §9) cannot exist "
                    "without its exact identity, generation and policy binding"
                )
        for item in self.coverage_items:
            if item.obligation_ref is None:
                raise ArtifactIntegrityError(
                    "MonitorCoverageManifest.is_complete is True while a coverage item carries no "
                    "obligation_ref — a complete mapping maps *every applicable* obligation "
                    "(ADR-002-028 §5.4 line 123; STM-INV-002 line 163)"
                )
        for intake in self.submitted_monitored_assumptions:
            if intake.assumption_id is None:
                raise ArtifactIntegrityError(
                    "MonitorCoverageManifest.is_complete is True while a submitted Monitored "
                    "Assumption carries no assumption_id — §9 line 288 admits it as a manifest "
                    "item, never as an out-of-band addition"
                )
        return self


class ContinuousConformanceSnapshot(IndependentIdArtifact):
    """The non-authorizing Continuous Conformance Snapshot (§5.6 line 131; §12; design #30 §2.4).

    §5.6 verbatim: "A **non-authorizing** consistency cut of coverage, exact monitor results, unresolved
    violations, gaps, suppressions, delivery state, and generation for one scope and time basis." §12
    line 324-333 lists the nine bindings; §12 line 335: "``CONFORMING`` requires **every** required item
    to be current, complete, and independently valid under policy. ``RESTRICTED``, ``NON_CONFORMING``, or
    ``UNKNOWN`` denies dependent new risk for the affected scope."

    **Even ``CONFORMING`` grants nothing** — §1 line 25 enumerates the twelve things it does not do, and
    the all-false :class:`~tos.stm._base.AllFalseMonitoringAuthority` holds regardless of result.

    ``aggregate_result`` is a **mutable lifecycle coordinate** and is deliberately **not** covered
    (coordinate non-collapse, design #30 §2.3): a lawful re-evaluation must not look like a same-id /
    different-bytes forgery.

    **Coexistence seal (design #30 §2.3, the #20 lesson):** a ``CONFORMING`` result coexisting with an
    absent §12 binding, with **no** bound monitor result, with an unknown source-continuity fact, or with
    a recorded active violation / unknown / gap / delivery failure is **unconstructable**. The predicate
    layer re-derives the same fact for a ``model_construct`` bypass
    (:func:`~tos.stm.predicates.conformance_requires_complete_current_valid`, two layers).
    """

    _ID_FIELD: ClassVar[str] = "snapshot_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "snapshot_id",
        "snapshot_generation",
        "monitor_generation",
        "policy_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "snapshot_generation",
            "monitor_generation",
            "policy_digest",
            "critical_telemetry_manifest_digest",
            "coverage_manifest_digest",
            "scope",
            "owner_epoch",
            "monitor_results",
            "source_continuity_present",
            "authority_effect",
        }
    )

    snapshot_id: str | None = None
    snapshot_generation: int | None = None
    #: The snapshot's own digest — **self-excluded** from the covered preimage (design #30 §2.3).
    snapshot_digest: str | None = None
    #: The §5.5 Monitor Generation ordering scalar (an ordering identity, never a clock).
    monitor_generation: int | None = None
    policy_digest: str | None = None
    critical_telemetry_manifest_digest: str | None = None
    coverage_manifest_digest: str | None = None
    scope: str | None = None
    #: The §12 line 328 fenced owner epoch (STM-INV-016 line 219 stale-writer fence).
    owner_epoch: str | None = None
    #: The §12 line 329 "every required monitor and result" atoms.
    monitor_results: tuple[MonitorEvaluation, ...] = ()
    #: Positive — §12 line 330 source continuity is part of the snapshot binding.
    source_continuity_present: bool | None = None
    active_violations: tuple[str, ...] = ()
    active_unknowns: tuple[str, ...] = ()
    active_gaps: tuple[str, ...] = ()
    active_suppressions: tuple[str, ...] = ()
    delivery_failures: tuple[str, ...] = ()
    #: Mutable lifecycle coordinate — **not** covered (coordinate non-collapse, design #30 §2.3).
    aggregate_result: AggregateConformanceResult | None = None
    #: §1 line 25 / §5.6 — a snapshot is non-authorizing, even when ``CONFORMING`` (all-false).
    authority_effect: AllFalseMonitoringAuthority = AllFalseMonitoringAuthority()

    @model_validator(mode="after")
    def _conforming_claim_requires_complete_scope(
        self,
    ) -> ContinuousConformanceSnapshot:
        """Reject a ``CONFORMING`` claim coexisting with an incomplete scope (§12 line 335; §2.3)."""
        if self.aggregate_result is not AggregateConformanceResult.CONFORMING:
            return self
        for name in (
            "snapshot_id",
            "snapshot_generation",
            "monitor_generation",
            "policy_digest",
            "critical_telemetry_manifest_digest",
            "coverage_manifest_digest",
            "scope",
            "owner_epoch",
        ):
            if getattr(self, name) is None:
                raise ArtifactIntegrityError(
                    f"ContinuousConformanceSnapshot.aggregate_result is CONFORMING while {name} "
                    "is absent — ADR-002-028 §12 line 335 requires *every* required item to be "
                    "current, complete, and independently valid under policy"
                )
        if not self.monitor_results:
            raise ArtifactIntegrityError(
                "ContinuousConformanceSnapshot.aggregate_result is CONFORMING while no monitor "
                "result is bound — §12 line 329 binds 'every required monitor and result', and an "
                "empty query proves nothing (STM-INV-004 line 171)"
            )
        if self.source_continuity_present is None:
            raise ArtifactIntegrityError(
                "ContinuousConformanceSnapshot.aggregate_result is CONFORMING while source "
                "continuity is unknown — §12 line 330 binds source continuity, and UNKNOWN is "
                "restrictive (STM-INV-005 line 175)"
            )
        for name in (
            "active_violations",
            "active_unknowns",
            "active_gaps",
            "delivery_failures",
        ):
            if getattr(self, name):
                raise ArtifactIntegrityError(
                    f"ContinuousConformanceSnapshot.aggregate_result is CONFORMING while "
                    f"{name} is non-empty — §12 line 335 'CONFORMING requires every required item "
                    "to be current, complete, and independently valid under policy'"
                )
        return self


class SafetyMonitoringGap(IndependentIdArtifact):
    """The immutable Safety Monitoring Gap (§5.7 line 135; §13; design #30 §2.4).

    §5.7 verbatim: "An immutable record of **missing, stale, conflicting, ambiguous, discontinuous,
    incomplete, unverified, common-mode, failed, or suppressed** monitoring coverage and its greatest
    credible affected scope and restrictive disposition" — the ten
    :class:`~tos.stm.vocabulary.MonitoringGapKind` members. §13 line 343: a gap "SHALL record exact
    scope, first observation, credible start interval, source and evaluator state, missing evidence,
    common modes, greatest credible impact, required restrictions, alert state, owner, current
    generation, and closure proof."

    **A gap is a gap, not an exemption** (STM-INV-002 line 163) and §13 line 349: "**Monitoring recovery
    does not close the gap by itself.** Closure requires continuity re-established under a new or current
    fenced generation, loss interval bounded, missed violations conservatively reconstructed, dependent
    state re-evaluated, evidence gaps resolved or explicitly restrictive, and every required owner
    handoff accepted." ``closure_proof_present`` is therefore a **positive**-polarity lifecycle
    coordinate, deliberately **not** covered (a lawful closure must not look like a forgery), and is the
    sole clearing path in :func:`~tos.stm.predicates.gap_is_restrictive_not_exemption`.
    """

    _ID_FIELD: ClassVar[str] = "gap_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "gap_id",
        "gap_generation",
        "monitor_generation",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "gap_generation",
            "monitor_generation",
            "gap_kind",
            "exact_scope",
            "first_observation",
            "credible_start_interval",
            "source_evaluator_state",
            "missing_evidence",
            "greatest_credible_impact",
            "required_restrictions",
            "alert_state",
            "authority_effect",
        }
    )

    gap_id: str | None = None
    gap_generation: int | None = None
    #: The gap's own digest — **self-excluded** from the covered preimage (design #30 §2.3).
    gap_digest: str | None = None
    #: The §5.5 Monitor Generation ordering scalar (an ordering identity, never a clock).
    monitor_generation: int | None = None
    #: The §5.7 line 135 ten-kind classification (``None`` ⇒ unclassified ⇒ fail-closed).
    gap_kind: MonitoringGapKind | None = None
    exact_scope: str | None = None
    first_observation: str | None = None
    credible_start_interval: str | None = None
    source_evaluator_state: str | None = None
    missing_evidence: tuple[str, ...] = ()
    #: Kept out of the covered set — ``frozenset`` payload (design #30 §2.3).
    common_modes: frozenset[str] = frozenset()
    greatest_credible_impact: str | None = None
    required_restrictions: tuple[str, ...] = ()
    alert_state: str | None = None
    #: Positive lifecycle coordinate — **not** covered; §13 line 349 is the sole clearing path.
    closure_proof_present: bool | None = None
    #: §1 line 25 / STM-INV-001 — a gap record grants nothing (all-false).
    authority_effect: AllFalseMonitoringAuthority = AllFalseMonitoringAuthority()


class SafetyAlertRecord(IndependentIdArtifact):
    """The immutable non-authorizing Safety Alert Record (§5.8 line 139; §16 line 384; design #30 §2.4).

    §5.8 verbatim: "An immutable **non-authorizing** record of one alert identity, signal lineage, exact
    scope, severity proposal, correlation facts, required delivery and escalation policy, and linkage to
    restrictive and incident workflows." §16 line 384 binds the seven elements: "signal lineage, exact
    scope, Monitor Generation, first-known time, severity proposal, required restriction, and
    incident-classification rule."

    §16 line 386: correlation and deduplication "may link related records but SHALL **preserve each
    distinct source, scope, trigger, first-observed time, bound, restrictive state, and evidence
    lineage**. It cannot collapse a broader or more severe condition into a favorable parent or reset
    elapsed time." §7 line 236: "alert severity is **not** protective classification" — which is exactly
    what ``AllFalseMonitoringAuthority.classifies_protective`` denies.

    ``first_known_time`` is an **injected** trustworthy-time coordinate (ADR-002-008-owned); stm reads no
    clock (design #30 §8).
    """

    _ID_FIELD: ClassVar[str] = "alert_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "alert_id",
        "alert_generation",
        "monitor_generation",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "alert_generation",
            "monitor_generation",
            "signal_lineage",
            "exact_scope",
            "first_known_time",
            "severity_proposal",
            "correlation_facts",
            "required_delivery_policy",
            "required_escalation_policy",
            "restriction_linkage",
            "incident_classification_rule",
            "authority_effect",
        }
    )

    alert_id: str | None = None
    alert_generation: int | None = None
    #: The alert's own digest — **self-excluded** from the covered preimage (design #30 §2.3).
    alert_digest: str | None = None
    #: The §5.5 Monitor Generation ordering scalar (an ordering identity, never a clock).
    monitor_generation: int | None = None
    signal_lineage: str | None = None
    exact_scope: str | None = None
    #: Injected ADR-002-008 trustworthy-time coordinate (§16 line 384); never a clock read.
    first_known_time: str | None = None
    #: A *proposal* only — §7 line 236 "alert severity is not protective classification".
    severity_proposal: str | None = None
    correlation_facts: tuple[str, ...] = ()
    required_delivery_policy: str | None = None
    required_escalation_policy: str | None = None
    restriction_linkage: str | None = None
    #: The §16 line 384 rule; ADR-002-027 retains the incident authority (§17 line 400).
    incident_classification_rule: str | None = None
    #: §5.8 line 139 verbatim "non-authorizing" (all-false).
    authority_effect: AllFalseMonitoringAuthority = AllFalseMonitoringAuthority()


class AlertEscalationRecord(IndependentIdArtifact):
    """The immutable non-authorizing Alert Escalation Record (§5.9 line 143; design #30 §2.4).

    §5.9 verbatim: "An immutable **non-authorizing** record bound to **exactly one** Safety Alert Record
    and one policy and Monitor Generation. It records ordered delivery attempts, acknowledgements,
    escalation stages, failures, alternate paths, handoffs, and retirement criteria. One alert may have
    multiple records for independent paths or successive escalation generations, but **records cannot be
    unioned, substituted, or used to narrow the alert scope or reset its first-observed time.**"

    ``bound_alert_id`` is an **external reference that is covered** and is in ``_REQUIRED_COVERED``, so
    "which alert is this bound to?" is unforgeable (design #30 §2.3). ``unioned_or_substituted`` is
    **negative** polarity and is the §5.9 line 143 no-union / no-substitution seal, judged by
    :func:`~tos.stm.predicates.escalation_single_binding` — the shape reused (never imported) from the
    iap single-use gate (``iap/predicates.py:176`` ``single_use is not True`` ⇒ deny).

    **Structural seal (design #30 §2.3):** a record carrying delivery attempts, escalation stages or
    handoffs while ``bound_alert_id`` is absent is **unconstructable** — an escalation "bound to exactly
    one Safety Alert Record" cannot exist unbound.
    """

    _ID_FIELD: ClassVar[str] = "escalation_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "escalation_id",
        "escalation_generation",
        "bound_alert_id",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "escalation_generation",
            "bound_alert_id",
            "policy_digest",
            "monitor_generation",
            "ordered_delivery_attempts",
            "acknowledgements",
            "escalation_stages",
            "failures",
            "alternate_paths",
            "handoffs",
            "retirement_criteria",
            "unioned_or_substituted",
            "authority_effect",
        }
    )

    escalation_id: str | None = None
    escalation_generation: int | None = None
    #: The record's own digest — **self-excluded** from the covered preimage (design #30 §2.3).
    escalation_digest: str | None = None
    #: External reference — **covered**, so the single binding is unforgeable (§5.9 line 143).
    bound_alert_id: str | None = None
    policy_digest: str | None = None
    #: The §5.5 Monitor Generation ordering scalar (an ordering identity, never a clock).
    monitor_generation: int | None = None
    ordered_delivery_attempts: tuple[str, ...] = ()
    acknowledgements: tuple[str, ...] = ()
    escalation_stages: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()
    alternate_paths: tuple[str, ...] = ()
    handoffs: tuple[str, ...] = ()
    retirement_criteria: tuple[str, ...] = ()
    #: **Negative** — §5.9 line 143 records cannot be unioned or substituted.
    unioned_or_substituted: bool | None = None
    #: §5.9 line 143 verbatim "non-authorizing" (all-false).
    authority_effect: AllFalseMonitoringAuthority = AllFalseMonitoringAuthority()

    @model_validator(mode="after")
    def _escalation_content_requires_a_binding(self) -> AlertEscalationRecord:
        """Reject escalation content coexisting with no bound alert (§5.9 line 143; design #30 §2.3)."""
        if self.bound_alert_id is not None:
            return self
        for name in ("ordered_delivery_attempts", "escalation_stages", "handoffs"):
            if getattr(self, name):
                raise ArtifactIntegrityError(
                    f"AlertEscalationRecord.{name} is recorded while bound_alert_id is absent — "
                    "ADR-002-028 §5.9 line 143 binds an escalation record to *exactly one* Safety "
                    "Alert Record; an unbound escalation could be unioned or substituted across "
                    "alerts, which the same line forbids"
                )
        return self
