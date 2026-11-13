"""Enforcement-evidence records (design §2.4; ADR-DEV-001 §8 L234-236)."""

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

PHASE1_CAPABILITY_SCOPE: tuple[str, ...] = (
    "capsule:read-only",
    "proposal-builder:effect-free",
)


class AdmissibilityResult(IndependentIdArtifact):
    """Layer-1 static-admissibility evidence (design §2.4; ADR-DEV-001 §8)."""

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
            "strategy_id",
            "strategy_digest",
        }
    )

    result_id: str | None = None

    artifact_type: str = _ADMISSIBILITY_ARTIFACT_TYPE
    schema_version: str = _SCHEMA_VERSION
    candidate: CandidateProgram | None = None
    verdict: AdmissibilityVerdict | None = None
    reasons: tuple[str, ...] = ()
    enforcement_mechanism_version: str | None = None
    dsl_version: str | None = None
    strategy_id: str | None = None
    strategy_digest: str | None = None

    @model_validator(mode="after")
    def _verdict_matches_predicate(self) -> AdmissibilityResult:
        """Re-derive the verdict from the candidate; reject any producer optimism (★2)."""
        if self.candidate is None or self.verdict is None:
            return self
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
    strategy_id: str | None = None,
    strategy_digest: str | None = None,
) -> AdmissibilityResult:
    """Analyze a candidate and issue a faithful :class:`AdmissibilityResult` (design §2.4)."""
    computed = analyze(candidate)
    return AdmissibilityResult.issue(
        scheme=scheme,
        result_id=result_id,
        candidate=candidate,
        verdict=computed.verdict,
        reasons=computed.reasons,
        enforcement_mechanism_version=enforcement_mechanism_version,
        dsl_version=dsl_version,
        strategy_id=strategy_id,
        strategy_digest=strategy_digest,
    )


class CapabilityManifest(IndependentIdArtifact):
    """Layer-2 capability-manifest *slot* (design §2.4) — Phase-1 constant only."""

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

    manifest_id: str | None = None

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
    """Layer-3 / bounded-evaluation *slot* (design §2.4) — transition result only."""

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

    bound_outcome_id: str | None = None

    artifact_type: str = _BOUND_ARTIFACT_TYPE
    schema_version: str = _SCHEMA_VERSION
    terminal_state: BoundState | None = None
    degraded_to_no_action: bool = False
    enforcement_mechanism_version: str | None = None

    @model_validator(mode="after")
    def _degrade_flag_matches_state(self) -> BoundOutcome:
        """Reject a stall state and any mis-stated degrade flag (★2; DCE-INV-007)."""
        if self.terminal_state is None:
            return self
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
