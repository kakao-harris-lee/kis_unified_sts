"""``release_admission`` — Phase 2 release-admission gate (design #40 §5 order"""

from __future__ import annotations

from tos.workload import RuntimeIdentity

from tos_runtime.operations.dependency_admission import RuntimeArtifactObservation
from tos_runtime.release.config import ReleaseAdmissionConfig
from tos_runtime.release.verdict import (
    AdmissionResult,
    ReleaseRestriction,
    software_deployment_ok_verdict,
)

__all__ = ["ReleaseAdmissionService", "ReleaseRestrictionLookup", "release_admission"]


class ReleaseRestrictionLookup:
    """The result of one restriction-registry lookup, positive-polarity-safe."""

    def __init__(
        self, *, resolved: bool | None, active: ReleaseRestriction | None
    ) -> None:
        self.resolved = resolved
        self.active = active

    @property
    def present(self) -> bool | None:
        """Negative-polarity ``restriction_present`` — ``None`` (unknown) when"""
        if self.resolved is not True:
            return None
        return self.active is not None


def _runtime_attestation_matches(
    identity: RuntimeIdentity,
    observation: RuntimeArtifactObservation,
    *,
    expected_code_digest: str,
    expected_dependency_set_digest: str,
) -> bool:
    """Whether the running artifact matches the operator-approved release —"""
    source_matches = (
        observation.source_tree_digest is not None
        and observation.source_tree_digest == expected_code_digest
    )
    dependency_matches = (
        observation.dependency_set_digest is not None
        and observation.dependency_set_digest == expected_dependency_set_digest
    )
    identity_matches = (
        identity.code_digest is not None
        and identity.code_digest == observation.source_tree_digest
    )
    return source_matches and dependency_matches and identity_matches


def release_admission(
    identity: RuntimeIdentity,
    admission: AdmissionResult | None,
    restriction: ReleaseRestrictionLookup,
    currentness_current: bool | None,
    observation: RuntimeArtifactObservation,
    *,
    expected_code_digest: str,
    expected_dependency_set_digest: str,
) -> bool:
    """Whether this release is admitted for deployment (kernel predicate only)."""
    matches = _runtime_attestation_matches(
        identity,
        observation,
        expected_code_digest=expected_code_digest,
        expected_dependency_set_digest=expected_dependency_set_digest,
    )
    return software_deployment_ok_verdict(
        admission_result=admission,
        runtime_attestation_matches=matches,
        active_currentness_current=currentness_current,
        restriction_present=restriction.present,
        restriction_state_resolved=restriction.resolved,
    )


class ReleaseAdmissionService:
    """Binds a :class:`~tos_runtime.release.config.ReleaseAdmissionConfig` AND"""

    def __init__(
        self,
        config: ReleaseAdmissionConfig,
        observation: RuntimeArtifactObservation,
    ) -> None:
        self._config = config
        self._observation = observation

    def decide(
        self, identity: RuntimeIdentity, currentness_current: bool | None
    ) -> bool:
        """Decide admission for ``identity`` under this service's config."""
        restriction = ReleaseRestrictionLookup(
            resolved=self._config.restriction_state_resolved,
            active=(
                self._config.restriction if self._config.restriction_present else None
            ),
        )
        return release_admission(
            identity,
            self._config.admission_result,
            restriction,
            currentness_current,
            self._observation,
            expected_code_digest=self._config.expected_code_digest,
            expected_dependency_set_digest=self._config.expected_dependency_set_digest,
        )
