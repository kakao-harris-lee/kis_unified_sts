"""Evidence Gap Record (design #4 §2.3, §2.7, template SoT)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from tos.canonical import ArtifactIntegrityError, FrozenModel
from tos.evidence._base import AllFalseFlags
from tos.evidence.elements import ObservedBranch, RecoverySource, RemainingUncertainty

_GAP_TYPE_DEFAULT = "UNKNOWN"


class GapStatus(StrEnum):
    """Gap lifecycle states (design §2.7, ADR §14 line 369). Forward-only."""

    SUSPECTED = "SUSPECTED"
    CONFIRMED = "CONFIRMED"
    CONTAINED = "CONTAINED"
    REPAIRED = "REPAIRED"
    INDEPENDENTLY_REVIEWED = "INDEPENDENTLY_REVIEWED"


GAP_STATUS_ORDER: tuple[GapStatus, ...] = (
    GapStatus.SUSPECTED,
    GapStatus.CONFIRMED,
    GapStatus.CONTAINED,
    GapStatus.REPAIRED,
    GapStatus.INDEPENDENTLY_REVIEWED,
)


class CapacityTreatment(StrEnum):
    """Capacity treatment under an open gap (template line 35, ERI-INV-003)."""

    CONSERVATIVE_UNKNOWN = "CONSERVATIVE_UNKNOWN"


class AffectedScope(FrozenModel):
    """Scope a gap affects (template lines 8-20) — id lists only."""

    environments: tuple[str, ...] = ()
    safety_cells: tuple[str, ...] = ()
    capacity_domains: tuple[str, ...] = ()
    accounts: tuple[str, ...] = ()
    brokers: tuple[str, ...] = ()
    instruments: tuple[str, ...] = ()
    source_continuity_ids: tuple[str, ...] = ()
    authority_generations: tuple[int, ...] = ()
    profile_generations: tuple[int, ...] = ()
    egress_generations: tuple[int, ...] = ()
    recovery_generations: tuple[int, ...] = ()
    recovery_session_ids: tuple[str, ...] = ()


class GapDetail(FrozenModel):
    """The gap itself (template lines 22-30). ``economic_effect_unknown`` defaults true."""

    gap_type: str = _GAP_TYPE_DEFAULT
    expected_record_classes: tuple[str, ...] = ()
    missing_or_conflicting_ids: tuple[str, ...] = ()
    expected_sequence_start: int | None = None
    expected_sequence_end: int | None = None
    observed_branches: tuple[ObservedBranch, ...] = ()
    affected_causal_roots: tuple[str, ...] = ()
    economic_effect_unknown: bool = True


class GapResponse(FrozenModel):
    """Containment response (template lines 32-37). Fail-closed defaults."""

    new_risk_blocked: bool = True
    containment_generation: int | None = None
    capacity_treatment: CapacityTreatment = CapacityTreatment.CONSERVATIVE_UNKNOWN
    existing_protection_preserved: bool = True
    escalation_id: str | None = None


class GapRepair(FrozenModel):
    """Repair block (template lines 39-44). ``remaining_uncertainty`` preserved."""

    recovered_record_ids: tuple[str, ...] = ()
    recovery_sources: tuple[RecoverySource, ...] = ()
    repair_method: str | None = None
    remaining_uncertainty: RemainingUncertainty = RemainingUncertainty.UNKNOWN
    independently_reviewed: bool = False


class GapAuthorityEffect(AllFalseFlags):
    """Gap authority effect — all false (template lines 46-50, design §4.6/§1 line 25)."""

    closes_unknown: bool = False
    releases_capacity: bool = False
    creates_live_authorization: bool = False
    may_rearm: bool = False


class EvidenceGapRecord(FrozenModel):
    """An immutable Evidence Gap Record (design #4 §2.3/§2.7)."""

    gap_id: str | None = None
    status: GapStatus = GapStatus.SUSPECTED
    detected_by: str | None = None
    detected_at_time_snapshot_id: str | None = None
    evidence_integrity_policy_id: str | None = None
    evidence_integrity_policy_generation: int | None = None

    affected_scope: AffectedScope = AffectedScope()
    gap: GapDetail = GapDetail()
    response: GapResponse = GapResponse()
    repair: GapRepair = GapRepair()
    authority_effect: GapAuthorityEffect = GapAuthorityEffect()

    @model_validator(mode="after")
    def _state_preconditions(self) -> EvidenceGapRecord:
        """Enforce §2.7 per-record preconditions + fail-closed new-risk block."""
        status = self.status
        if (
            status is not GapStatus.INDEPENDENTLY_REVIEWED
            and not self.response.new_risk_blocked
        ):
            raise ArtifactIntegrityError(
                f"gap in status {status} must keep new_risk_blocked=true "
                "(fail-closed until independent review) — §2.7"
            )
        if status is GapStatus.CONFIRMED and not self.detected_by:
            raise ArtifactIntegrityError(
                "CONFIRMED gap requires a detection basis (detected_by) — §2.7"
            )
        if status is GapStatus.CONTAINED and (
            not self.response.new_risk_blocked
            or self.response.containment_generation is None
        ):
            raise ArtifactIntegrityError(
                "CONTAINED gap requires new_risk_blocked=true and a "
                "containment_generation — §2.7"
            )
        if status is GapStatus.REPAIRED and (
            not self.repair.recovered_record_ids or not self.repair.recovery_sources
        ):
            raise ArtifactIntegrityError(
                "REPAIRED gap requires recovered_record_ids and recovery_sources "
                "(repair is appended with sources/method/uncertainty) — §2.7"
            )
        if (
            status is GapStatus.INDEPENDENTLY_REVIEWED
            and not self.repair.independently_reviewed
        ):
            raise ArtifactIntegrityError(
                "INDEPENDENTLY_REVIEWED gap requires independently_reviewed=true — §2.7"
            )
        return self
