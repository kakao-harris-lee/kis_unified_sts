"""stm-local base re-export shim + all-false monitoring authority effect (design #30 §2/§3.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``, ``CanonicalDecimal``,
``classify_record_pair`` / ``RecordPairKind``, ``EVL1ProvisionalCanonicalizer``) is REUSED verbatim
from :mod:`tos.canonical` (design #30 §3.1 — no redefinition; **PROMOTE 0**:
``IndependentIdArtifact`` is already core from design #6). The seven digest-bound STM citizens
(``SafetyMonitoringPolicy`` / ``CriticalTelemetryManifest`` / ``MonitorCoverageManifest`` /
``ContinuousConformanceSnapshot`` / ``SafetyMonitoringGap`` / ``SafetyAlertRecord`` /
``AlertEscalationRecord``) inherit :class:`~tos.canonical.IndependentIdArtifact` (``id !=
f(digest)``): the id is separately issued, so a same-id / different-**covered**-bytes forged, re-issued
or replayed record is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` — the structural
defence ADR §22 line 474 demands for "raw and derived telemetry integrity and continuity" (design #30
§2.1/§3.1). This module is a thin re-export shim (the ``tos.sir._base`` / ``tos.wdr._base`` /
``tos.cur._base`` precedent), so ``from tos.stm._base import IndependentIdArtifact`` reads locally
while the definition stays single-sourced in core.

``EVL1ProvisionalCanonicalizer`` is re-exported because it is the **foundation of yolk 2**: a
``MonitorEvaluation.canonical_input_digest`` is a canonical deterministic digest, so "identical inputs
⇒ identical key" is already a tested property of core and is **not re-authored here** (design #30
§3.1/§5.2). stm layers only the *relation* — identical key ⇒ identical result — on top of it.

The one stm-local addition is :class:`AllFalseMonitoringAuthority` — an authority block whose every
declared boolean flag is forced ``false`` at construction. Its fourteen flags transcribe ADR §1 line 25
verbatim (a ``CONFORMING`` snapshot "does not approve an action, create headroom, mark an RFC
requirement ``PASS``, satisfy preventive control, establish broker finality, activate configuration,
issue authority, permit transmission, close an incident, establish recovery readiness, restore scope,
or re-arm" — twelve verbs) plus STM-INV-001 line 159 (no "capacity") and §7 line 236 ("alert severity is
not protective classification"). The all-false authority *contract* is **not** in ``tos.canonical``, so
it is authored **locally, fresh** here (the seventeen-package ``AllFalse*Authority`` precedent — afg /
are / authority / cur / dsl / egress / failuredomain / iap / ioc / liveauth / nontrade / rcl /
replacement / rlp / sir / time / wdr, design #30 §3.3) rather than imported from a sibling: stm imports
**no** sibling (sibling edge 0, design #30 §0.3/§3.4), and the flag names are monitoring-specific, so
the all-false contract is re-expressed with a note — the codebase's REPLICATE-WITH-NOTE convention for
pure authority contracts.

``monitoring artifact != authority``: holding a Safety Monitoring Policy / Critical Telemetry Manifest /
Monitor Coverage Manifest / Continuous Conformance Snapshot / Safety Monitoring Gap / Safety Alert
Record / Alert Escalation Record creates no capacity, approval, headroom, requirement ``PASS``,
preventive-control satisfaction, broker finality, configuration activation, authority, transmission
permission, incident closure, recovery readiness, restored scope, re-arm, or protective classification.
Any ``True`` flag makes the artifact unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling ``tos.*``
(design #30 §0.3). Clock-free.

Regime tag: coverage-completeness / deterministic-evaluation predicate substrate only; closes **no**
STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    DigestBoundArtifact,
    EVL1ProvisionalCanonicalizer,
    FrozenModel,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)

__all__ = [
    "AllFalseMonitoringAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "DigestBoundArtifact",
    "EVL1ProvisionalCanonicalizer",
    "FrozenModel",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
]


class AllFalseMonitoringAuthority(FrozenModel):
    """Authority effect of a monitoring artifact — every flag forced ``false`` (STM-INV-001; §1; §7).

    The pure-model realization of ``monitoring artifact != authority`` (STM-INV-001 line 159: "No
    policy, manifest, snapshot, gap, alert, acknowledgement, page, dashboard, or monitoring workflow
    creates capacity, approval, live authority, transmission permission, incident closure, readiness, or
    re-arm"). ADR §1 line 25 states the same for the *best possible* result: even a ``CONFORMING``
    Continuous Conformance Snapshot "does not approve an action, create headroom, mark an RFC
    requirement ``PASS``, satisfy preventive control, establish broker finality, activate configuration,
    issue authority, permit transmission, close an incident, establish recovery readiness, restore
    scope, or re-arm." §7 line 236 adds the protective axis: "alert severity is not protective
    classification."

    The fourteen fields are those twelve §1 line 25 verbs plus ``creates_capacity`` (STM-INV-001) and
    ``classifies_protective`` (§7 line 236); they correspond 1:1, in declaration order, to
    :data:`~tos.stm.vocabulary.ALL_FALSE_AUTHORITY_VERBS`, and the §7.2 (c) ADR-enumeration-closure
    property asserts that correspondence both ways (過 0 · 不 0).

    ``satisfies_preventive_control`` in particular is the model half of STM-INV-014 line 211
    ("Metrics, logs, alerts, dashboards, pages, audit, replay, reports, and postmortems cannot replace a
    preventive or restrictive enforcement point"): evidence is **not** prevention, so a monitoring
    artifact can never mark a preventive control satisfied.

    Authority comes only from the separately owned runtime, the +Security / +Broker evidence and the
    human governance steps — never from the existence or possession of a monitoring artifact.
    Isomorphic to the seventeen sibling all-false blocks (authored locally-fresh, **not** imported —
    stm has sibling edge 0, design #30 §0.3/§2.4). Any ``True`` authority flag makes the artifact
    unconstructable.

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators, so a
    consuming runtime never trusts an un-validated block (defence in depth — the §5/§6 predicates
    re-derive the all-false shape through
    :func:`~tos.stm.predicates.all_false_monitoring_authority` and never read this block as a grant,
    design #30 §2.3).
    """

    creates_capacity: bool = False
    approves_action: bool = False
    creates_headroom: bool = False
    marks_requirement_pass: bool = False
    satisfies_preventive_control: bool = False
    establishes_broker_finality: bool = False
    activates_configuration: bool = False
    issues_authority: bool = False
    permits_transmission: bool = False
    closes_incident: bool = False
    establishes_recovery_readiness: bool = False
    restores_scope: bool = False
    re_arms: bool = False
    classifies_protective: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseMonitoringAuthority:
        """Reject construction if any authority flag is ``True`` (STM-INV-001; §1 line 25; §7)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(monitoring artifact != authority — STM-INV-001 / ADR-002-028 §1 line 25; a "
                    "Safety Monitoring Policy / Critical Telemetry Manifest / Monitor Coverage "
                    "Manifest / Continuous Conformance Snapshot / Safety Monitoring Gap / Safety "
                    "Alert Record / Alert Escalation Record cannot create capacity, approve an "
                    "action, create headroom, mark a requirement PASS, satisfy a preventive "
                    "control, establish broker finality, activate configuration, issue authority, "
                    "permit transmission, close an incident, establish recovery readiness, restore "
                    "scope, re-arm, or classify an action protective — it is non-authorizing "
                    "observation, not permission)"
                )
        return self
