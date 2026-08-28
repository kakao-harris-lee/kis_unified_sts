"""Enforcement-evidence records (design §2.4; ADR-DEV-001 §8 L234-236).

The enforcement layers *produce* evidence — an admissibility result, a capability
manifest, and bound outcomes — as conforming inputs to ADR-002-016 replay
integrity; they define none of it (ADR-DEV-001 §8). All three are digest-bound
records with an **independent** id (design §2.4, the ``tos.evidence`` ledger
pattern), and each records an ``enforcement_mechanism_version`` — the L1 facet of
DCE-INV-005's version-recording obligation (ADR-DEV-001 §9 L254-257). **Phase 1
does not verify the mechanism** (DCE-INV-005 self-certification bar, design §3.5);
these records are provisional and non-authorizing, and DCE-EV-005 stays
NOT_IMPLEMENTED.

* :class:`AdmissibilityResult` — the only enforcement-evidence Phase 1 actually
  fills (layer 1 output, design §2.4). It **embeds** the analyzed candidate and its
  stored verdict/reasons are re-derived from the pure predicate at construction, so
  a producer cannot assert a verdict the checker did not yield (★ producer-optimism
  prohibition; mirrors the capsule ``verify_validity_result_conservative`` guard).
* :class:`CapabilityManifest` — layer 2 output *slot* (design §2.4). Phase 1 has no
  runtime, so it records only the fixed Phase-1 scope constant
  (:data:`PHASE1_CAPABILITY_SCOPE`); any other capability set is unconstructable.
* :class:`BoundOutcome` — layer 3 / bounded-eval output *slot* (design §2.4). Phase
  1 records only the terminal-state transition (no real metering, design §3.4); its
  ``degraded_to_no_action`` flag must agree with the pure bound predicate.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design §firewall).
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import model_validator

from tos.canonical import CanonicalizationScheme
from tos.dsl._base import (
    ArtifactIntegrityError,
    IndependentIdArtifact,
)
from tos.dsl.admissibility import AdmissibilityVerdict, analyze
from tos.dsl.bounds import BoundState, degrades_to_no_action
from tos.dsl.candidate import CandidateProgram

_ADMISSIBILITY_ARTIFACT_TYPE = "ADMISSIBILITY_RESULT"
_CAPABILITY_ARTIFACT_TYPE = "CAPABILITY_MANIFEST"
_BOUND_ARTIFACT_TYPE = "BOUND_OUTCOME"
_SCHEMA_VERSION = "1.0-DRAFT"

#: The exhaustive capability scope of Phase-1 evaluation (ADR-DEV-001 §8 layer 2):
#: the read-only Capsule and the effect-free Proposal Builder — no ambient
#: capability. Phase 1 has no runtime that could hold more; this is a recorded
#: constant, not an enforcement proof (design §2.4).
PHASE1_CAPABILITY_SCOPE: tuple[str, ...] = (
    "capsule:read-only",
    "proposal-builder:effect-free",
)


class AdmissibilityResult(IndependentIdArtifact):
    """Layer-1 static-admissibility evidence (design §2.4; ADR-DEV-001 §8).

    Embeds the analyzed ``candidate`` and records the verdict/reasons. A validator
    re-runs the pure predicate over the embedded candidate and requires the stored
    verdict **and** reasons to equal the computed ones — so the record cannot claim
    ADMISSIBLE for an inadmissible candidate, nor drop/forge reasons (★
    producer-optimism prohibition). Admissibility is not authority and is separate
    from ADR-002-029 software-artifact admission (ADR-DEV-001 §5 L123-124).
    """

    _ID_FIELD: ClassVar[str] = "result_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "candidate",
        "verdict",
        "enforcement_mechanism_version",
        "dsl_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "artifact_type",
            "schema_version",
            "candidate",
            "verdict",
            "reasons",
            "enforcement_mechanism_version",
            "dsl_version",
        }
    )

    # ---- Layer-0 identity (independent) ----
    result_id: str | None = None

    # ---- Layer-1 covered content ----
    artifact_type: str = _ADMISSIBILITY_ARTIFACT_TYPE
    schema_version: str = _SCHEMA_VERSION
    #: The analyzed candidate, embedded so the verdict is re-derivable (★2).
    candidate: CandidateProgram | None = None
    verdict: AdmissibilityVerdict | None = None
    reasons: tuple[str, ...] = ()
    enforcement_mechanism_version: str | None = None
    dsl_version: str | None = None

    @model_validator(mode="after")
    def _verdict_matches_predicate(self) -> AdmissibilityResult:
        """Re-derive the verdict from the candidate; reject any producer optimism (★2)."""
        if self.candidate is None or self.verdict is None:
            return self  # completeness is enforced by the required-covered guard
        computed = analyze(self.candidate)
        if self.verdict is not computed.verdict:
            raise ArtifactIntegrityError(
                "stored admissibility verdict does not match the pure predicate "
                f"(stored={self.verdict}, computed={computed.verdict}) — a producer "
                "cannot claim a verdict the checker did not yield (★ producer-optimism)"
            )
        if tuple(self.reasons) != computed.reasons:
            raise ArtifactIntegrityError(
                "stored admissibility reasons do not match the pure predicate "
                f"(stored={self.reasons}, computed={computed.reasons})"
            )
        # Belt-and-braces: reasons non-empty iff INADMISSIBLE.
        inadmissible = self.verdict is AdmissibilityVerdict.INADMISSIBLE
        if inadmissible != bool(self.reasons):
            raise ArtifactIntegrityError(
                "reasons must be non-empty iff INADMISSIBLE "
                f"(verdict={self.verdict}, reasons={self.reasons})"
            )
        return self


def analyze_candidate(
    candidate: CandidateProgram,
    *,
    scheme: CanonicalizationScheme,
    enforcement_mechanism_version: str,
    dsl_version: str,
    result_id: str,
) -> AdmissibilityResult:
    """Analyze a candidate and issue a faithful :class:`AdmissibilityResult` (design §2.4).

    The verdict/reasons are computed by the pure predicate, never supplied — the
    record is honest by construction. Pure and non-authorizing.

    Args:
        candidate: The candidate program to analyze.
        scheme: The canonicalization scheme to bind.
        enforcement_mechanism_version: The recorded escape-checker version
            (DCE-INV-005 version facet; injected, not hard-coded).
        dsl_version: The DSL version.
        result_id: The independent record id.

    Returns:
        The issued :class:`AdmissibilityResult`.
    """
    computed = analyze(candidate)
    return AdmissibilityResult.issue(  # type: ignore[return-value]
        scheme=scheme,
        result_id=result_id,
        candidate=candidate,
        verdict=computed.verdict,
        reasons=computed.reasons,
        enforcement_mechanism_version=enforcement_mechanism_version,
        dsl_version=dsl_version,
    )


class CapabilityManifest(IndependentIdArtifact):
    """Layer-2 capability-manifest *slot* (design §2.4) — Phase-1 constant only.

    Phase 1 implements no capability-restricted runtime (design §0/§3.5); this
    record therefore only asserts the fixed Phase-1 scope
    (:data:`PHASE1_CAPABILITY_SCOPE`). Any other capability set — in particular one
    naming an ambient capability — is unconstructable, so the record cannot
    misrepresent a wider scope than Phase 1 can hold.
    """

    _ID_FIELD: ClassVar[str] = "manifest_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("enforcement_mechanism_version",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "artifact_type",
            "schema_version",
            "capabilities",
            "enforcement_mechanism_version",
        }
    )

    # ---- Layer-0 identity (independent) ----
    manifest_id: str | None = None

    # ---- Layer-1 covered content ----
    artifact_type: str = _CAPABILITY_ARTIFACT_TYPE
    schema_version: str = _SCHEMA_VERSION
    capabilities: tuple[str, ...] = PHASE1_CAPABILITY_SCOPE
    enforcement_mechanism_version: str | None = None

    @model_validator(mode="after")
    def _capabilities_are_phase1_constant(self) -> CapabilityManifest:
        """Reject any capability set other than the fixed Phase-1 scope (design §2.4)."""
        if tuple(self.capabilities) != PHASE1_CAPABILITY_SCOPE:
            raise ArtifactIntegrityError(
                "CapabilityManifest.capabilities must be exactly the Phase-1 scope "
                f"{PHASE1_CAPABILITY_SCOPE} — no runtime exists to hold any other "
                "(and no ambient capability is in scope; DCE-INV-003)"
            )
        return self


class BoundOutcome(IndependentIdArtifact):
    """Layer-3 / bounded-evaluation *slot* (design §2.4) — transition result only.

    Records the terminal :class:`~tos.dsl.bounds.BoundState` of a bounded
    evaluation and whether it degraded to no-action. Phase 1 does no real metering
    (design §3.4). The ``degraded_to_no_action`` flag must agree with the pure bound
    predicate, and the state must be terminal — a recorded ``EVALUATING`` state
    would be the unbounded stall DCE-INV-007 forbids.
    """

    _ID_FIELD: ClassVar[str] = "bound_outcome_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "terminal_state",
        "enforcement_mechanism_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "artifact_type",
            "schema_version",
            "terminal_state",
            "degraded_to_no_action",
            "enforcement_mechanism_version",
        }
    )

    # ---- Layer-0 identity (independent) ----
    bound_outcome_id: str | None = None

    # ---- Layer-1 covered content ----
    artifact_type: str = _BOUND_ARTIFACT_TYPE
    schema_version: str = _SCHEMA_VERSION
    terminal_state: BoundState | None = None
    degraded_to_no_action: bool = False
    enforcement_mechanism_version: str | None = None

    @model_validator(mode="after")
    def _degrade_flag_matches_state(self) -> BoundOutcome:
        """Reject a stall state and any mis-stated degrade flag (★2; DCE-INV-007)."""
        if self.terminal_state is None:
            return self  # completeness enforced by the required-covered guard
        if self.terminal_state is BoundState.EVALUATING:
            raise ArtifactIntegrityError(
                "BoundOutcome.terminal_state must be terminal (COMPLETED or "
                "BOUND_EXHAUSTED); EVALUATING is the stall DCE-INV-007 forbids"
            )
        expected = degrades_to_no_action(self.terminal_state)
        if self.degraded_to_no_action != expected:
            raise ArtifactIntegrityError(
                "degraded_to_no_action must match the terminal state "
                f"(state={self.terminal_state}, expected={expected}, "
                f"stored={self.degraded_to_no_action}) — ★ producer-optimism"
            )
        return self
