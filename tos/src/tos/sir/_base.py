"""sir-local base re-export shim + all-false incident authority effect (design #28 §2/§3.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``, ``CanonicalDecimal``,
``classify_record_pair`` / ``RecordPairKind``) is REUSED verbatim from :mod:`tos.canonical` (design #28
§3.1 — no redefinition; **PROMOTE 0**: ``IndependentIdArtifact`` is already core from design #6). The
six digest-bound SIR citizens (``SafetyIncidentPolicy`` / ``SafetyIncidentRecord`` /
``ActiveSafetyIncidentSet`` / ``IncidentContainmentPlan`` / ``IncidentRecoveryHandoffPackage`` /
``IncidentClosureDecision``) inherit :class:`~tos.canonical.IndependentIdArtifact` (``id !=
f(digest)``): the id is separately issued, so a same-id / different-**covered**-bytes forged, re-issued
or replayed record is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` — the structural
defence ADR §22 line 536 demands against "incident closure replay or duplicate consumption" (design #28
§2.1/§3.1). This module is a thin re-export shim (the ``tos.wdr._base`` / ``tos.rlp._base`` /
``tos.cur._base`` precedent), so ``from tos.sir._base import IndependentIdArtifact`` reads locally while
the definition stays single-sourced in core.

The one sir-local addition is :class:`AllFalseIncidentAuthority` — an authority block whose every
declared boolean flag is forced ``false`` at construction (SIR-INV-001 line 158 verbatim: "Policy,
signal, record, severity, plan, task, message, timeline, evidence, review, and closure artifacts create
**no** capacity, protection, Safety Authority, Live Authorization, Transmission Capability, broker
permission, HALT clear, production scope, or re-arm authority" + §7 line 231 "responder cannot
self-label an action protective" + §7 line 237 "incident closure cannot declare readiness"). The
all-false authority *contract* is **not** in ``tos.canonical``, so it is authored **locally, fresh**
here (the rcl ``AllFalseAuthority`` / egress ``AllFalseEgressAuthority`` / cur
``AllFalseCurrentnessAuthority`` / rlp ``AllFalseTrialAuthority`` / wdr ``AllFalseDeviationAuthority``
precedent — 16 files, design #28 §3.3) rather than imported from a sibling: sir imports **no** sibling
(sibling edge 0, design #28 §0.3/§3.4), and the flag names are incident-specific, so the all-false
contract is re-expressed with a note — the codebase's REPLICATE-WITH-NOTE convention for pure authority
contracts.

``incident artifact != authority``: holding a Safety Incident Policy / Record / Active Safety Incident
Set / Containment Plan / Recovery Handoff Package / Closure Decision creates no capacity, protection,
Safety Authority, Live Authorization, Transmission Capability, broker permission, HALT clear, production
scope, re-arm, protective classification, or recovery readiness. Any ``True`` flag makes the artifact
unconstructable.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no sibling ``tos.*``
(design #28 §0.3). Clock-free.

Regime tag: predicate substrate only; closes **no** SIR-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    DigestBoundArtifact,
    FrozenModel,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)

__all__ = [
    "AllFalseIncidentAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
]


class AllFalseIncidentAuthority(FrozenModel):
    """Authority effect of an incident artifact — every flag forced ``false`` (SIR-INV-001; §7).

    The pure-model realization of ``incident artifact != authority`` (SIR-INV-001; ADR-002-027 §7): a
    Safety Incident Policy / Record / Active Safety Incident Set / Containment Plan / Recovery Handoff
    Package / Closure Decision permits nothing at runtime — it creates / mutates / releases no capacity,
    classifies / creates no protection, issues no Live Authorization, creates no Transmission
    Capability, grants no broker permission, clears no HALT, creates no production scope, re-arms
    nothing, and establishes no recovery readiness. SIR-INV-001 line 158 verbatim: "Policy, signal,
    record, severity, plan, task, message, timeline, evidence, review, and closure artifacts create
    **no** capacity, protection, Safety Authority, Live Authorization, Transmission Capability, broker
    permission, HALT clear, production scope, or re-arm authority" (+ §7 line 231 "responder cannot
    self-label an action protective"; §7 line 237 "incident closure cannot declare readiness";
    SIR-INV-012 line 202 for the closure decision specifically). Authority comes only from the positive
    §5/§6 structural / polarity predicates plus the owning +Security / +Broker runtime and the human
    governance steps — never from the mere existence or possession of an incident artifact. Isomorphic
    to the rcl / egress / cur / rlp / wdr all-false blocks (authored locally-fresh, **not** imported —
    sir has sibling edge 0, design #28 §0.3/§2.4; the flag names are incident-specific). Any ``True``
    authority flag makes the artifact unconstructable.

    The construction-time rejection holds on the **normal validation path** only:
    ``pydantic.BaseModel.model_construct`` is an unsafe escape hatch that skips validators, so a
    consuming runtime never trusts an un-validated block (defence in depth — the §5/§6 predicates
    re-derive the all-false shape through :func:`~tos.sir.predicates.all_false_incident_authority` and
    never read this block as a grant, design #28 §2.3).
    """

    creates_capacity: bool = False
    creates_protection: bool = False
    creates_safety_authority: bool = False
    issues_live_authorization: bool = False
    creates_transmission_capability: bool = False
    grants_broker_permission: bool = False
    clears_halt: bool = False
    creates_production_scope: bool = False
    re_arms: bool = False
    classifies_protective_action: bool = False
    establishes_recovery_readiness: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseIncidentAuthority:
        """Reject construction if any authority flag is ``True`` (SIR-INV-001; §7)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(incident artifact != authority — SIR-INV-001 / ADR-002-027 §7; a Safety "
                    "Incident Policy / Record / Active Safety Incident Set / Containment Plan / "
                    "Recovery Handoff Package / Closure Decision cannot create or release "
                    "capacity, classify or create protection, create Safety Authority, issue Live "
                    "Authorization, create Transmission Capability, grant broker permission, clear "
                    "a HALT, create production scope, re-arm, or establish recovery readiness — it "
                    "is restrictive governed content, not permission)"
                )
        return self
