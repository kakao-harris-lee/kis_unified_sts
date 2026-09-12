"""``release_admission`` — Phase 2 release-admission gate (design #40 §5 order
6, lane R item 4;
`docs/plans/2026-09-08-tos-phase2-runtime-slice3-authority-risk-currentness-
compose-plan.md` §3 item 4).

Calls the kernel's :func:`~tos.sci.predicates.software_deployment_ok_verdict`
**only** — this module makes no admission decision of its own. The two
comparisons it performs itself are ``observation.source_tree_digest ==
config.expected_code_digest`` and ``observation.dependency_set_digest ==
config.expected_dependency_set_digest`` (Phase 5 W4 plan §2 decision 5 — the
``observation`` is a REAL measurement from
:mod:`tos_runtime.operations.dependency_admission`, replacing the earlier
constant ``code_digest`` fixture): no kernel predicate computes
``RuntimeArtifactAttestation.runtime_artifact_match`` (the §18 runtime-
measurement predicates are explicitly not-Phase-1, per that record's own
module docstring), so this is "runtime input collection: equality" — the
plain fallback the slice plan itself names when no kernel predicate exists
("비교 자체는 커널 술어가 하면 그것을 쓰고, 없으면 «단순 동등 비교 = 런타임
입력 수집»으로 docstring 명시").
"""

from __future__ import annotations

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.sci import (
    AdmissionResult,
    ReleaseRestriction,
    RuntimeArtifactAttestation,
    software_deployment_ok_verdict,
)
from tos.workload import RuntimeIdentity

from tos_runtime.operations.dependency_admission import RuntimeArtifactObservation
from tos_runtime.release.config import ReleaseAdmissionConfig

__all__ = ["ReleaseAdmissionService", "ReleaseRestrictionLookup", "release_admission"]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


class ReleaseRestrictionLookup:
    """The result of one restriction-registry lookup, positive-polarity-safe.

    ``resolved`` is ``True`` only when the lookup itself completed (finding
    either an active restriction or confirming none) — an unresolved lookup
    (``resolved`` is ``False``/``None``) denies conservatively regardless of
    what ``active`` carries (SCI-INV-014; §21 line 427 "No retry, mirror,
    cache ... may select a more permissive state when ... unknown").
    """

    def __init__(
        self, *, resolved: bool | None, active: ReleaseRestriction | None
    ) -> None:
        self.resolved = resolved
        self.active = active

    @property
    def present(self) -> bool | None:
        """Negative-polarity ``restriction_present`` — ``None`` (unknown) when
        the lookup itself did not resolve, never a permissive assumed
        ``False``."""
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
    """Build the :class:`~tos.sci.RuntimeArtifactAttestation` and derive its
    ``runtime_artifact_match`` — the module docstring's "runtime input
    collection: equality" fallback (no kernel predicate computes this).

    ``runtime_artifact_match`` is ``True`` only when BOTH the observed
    source-tree digest and the observed dependency-set digest match their
    operator-approved expected values (Phase 5 W4 plan §2 decision 5 (e)) —
    a single-coordinate match is not sufficient.
    """
    source_matches = (
        observation.source_tree_digest is not None
        and observation.source_tree_digest == expected_code_digest
    )
    dependency_matches = (
        observation.dependency_set_digest is not None
        and observation.dependency_set_digest == expected_dependency_set_digest
    )
    match = source_matches and dependency_matches
    attestation = RuntimeArtifactAttestation.issue(
        scheme=_SCHEME,
        attestation_id=f"attest-{identity.process_nonce}",
        runtime_continuity_generation=identity.runtime_generation,
        actual_executable_and_image_digest=observation.source_tree_digest,
        actual_library_dependency_set_digest=observation.dependency_set_digest,
        observed_runtime_artifact_set_digest=observation.source_tree_digest,
        expected_runtime_artifact_set_digest=expected_code_digest,
        runtime_artifact_match=match,
    )
    assert isinstance(attestation, RuntimeArtifactAttestation)
    return attestation.runtime_artifact_match is True


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
    """Whether this release is admitted for deployment (kernel predicate only).

    Args:
        identity: This process's :class:`~tos.workload.RuntimeIdentity`.
        admission: The exact :class:`~tos.sci.AdmissionResult` for the
            deployed artifact (Phase 2: an operator-approved static value,
            never computed here — see :mod:`tos_runtime.release.config`).
        restriction: The :class:`ReleaseRestrictionLookup` result.
        currentness_current: The injected ``tos.cur`` active-currentness
            verdict (e.g. ``proof.result is ProofResult.CURRENT``, from
            :mod:`tos_runtime.currentness`).
        observation: The REAL
            :class:`~tos_runtime.operations.dependency_admission.RuntimeArtifactObservation`
            (source-tree + dependency-set digests) this process was actually
            built from.
        expected_code_digest: The operator-approved expected source-tree
            digest this release must match.
        expected_dependency_set_digest: The operator-approved expected
            dependency-set digest this release must match.

    Returns:
        ``True`` iff :func:`~tos.sci.predicates.software_deployment_ok_verdict`
        holds. Even a ``True`` here is a negative gate only — it supplies no
        capacity, authority, protection, approval, or admissibility (§1
        line 27).
    """
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
    """Binds a :class:`~tos_runtime.release.config.ReleaseAdmissionConfig` AND
    one :class:`~tos_runtime.operations.dependency_admission.RuntimeArtifactObservation`
    to :func:`release_admission`, so the composition root does not have to
    thread the expected digests / the static admission+restriction facts /
    the observation through every call site itself — and so STAGE A and
    STAGE B (:mod:`tos_runtime.compose._wiring`) reuse the SAME observation
    (computed once at construction) rather than each re-walking the source
    tree / re-enumerating installed distributions (Phase 5 W4 plan §2
    decision 5 (e))."""

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
        """Decide admission for ``identity`` under this service's config.

        Args:
            identity: This process's :class:`~tos.workload.RuntimeIdentity`.
            currentness_current: The injected ``tos.cur`` active-currentness
                verdict.

        Returns:
            The :func:`release_admission` verdict.
        """
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
