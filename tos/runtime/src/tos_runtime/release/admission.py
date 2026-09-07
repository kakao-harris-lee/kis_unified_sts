"""``release_admission`` — Phase 2 release-admission gate (design #40 §5 order
6, lane R item 4;
`docs/plans/2026-09-08-tos-phase2-runtime-slice3-authority-risk-currentness-
compose-plan.md` §3 item 4).

Calls the kernel's :func:`~tos.sci.predicates.software_deployment_ok_verdict`
**only** — this module makes no admission decision of its own. The one
comparison it performs itself is ``identity.code_digest ==
config.expected_code_digest``: no kernel predicate computes
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
    identity: RuntimeIdentity, expected_code_digest: str
) -> bool:
    """Build the :class:`~tos.sci.RuntimeArtifactAttestation` and derive its
    ``runtime_artifact_match`` — the module docstring's "runtime input
    collection: equality" fallback (no kernel predicate computes this)."""
    match = (
        identity.code_digest is not None
        and identity.code_digest == expected_code_digest
    )
    attestation = RuntimeArtifactAttestation.issue(
        scheme=_SCHEME,
        attestation_id=f"attest-{identity.process_nonce}",
        runtime_continuity_generation=identity.runtime_generation,
        observed_runtime_artifact_set_digest=identity.code_digest,
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
    *,
    expected_code_digest: str,
) -> bool:
    """Whether this release is admitted for deployment (kernel predicate only).

    Args:
        identity: This process's :class:`~tos.workload.RuntimeIdentity`
            (carries ``code_digest``, the runtime artifact-set observation).
        admission: The exact :class:`~tos.sci.AdmissionResult` for the
            deployed artifact (Phase 2: an operator-approved static value,
            never computed here — see :mod:`tos_runtime.release.config`).
        restriction: The :class:`ReleaseRestrictionLookup` result.
        currentness_current: The injected ``tos.cur`` active-currentness
            verdict (e.g. ``proof.result is ProofResult.CURRENT``, from
            :mod:`tos_runtime.currentness`).
        expected_code_digest: The operator-approved expected runtime
            artifact-set digest this release must match.

    Returns:
        ``True`` iff :func:`~tos.sci.predicates.software_deployment_ok_verdict`
        holds. Even a ``True`` here is a negative gate only — it supplies no
        capacity, authority, protection, approval, or admissibility (§1
        line 27).
    """
    matches = _runtime_attestation_matches(identity, expected_code_digest)
    return software_deployment_ok_verdict(
        admission_result=admission,
        runtime_attestation_matches=matches,
        active_currentness_current=currentness_current,
        restriction_present=restriction.present,
        restriction_state_resolved=restriction.resolved,
    )


class ReleaseAdmissionService:
    """Binds a :class:`~tos_runtime.release.config.ReleaseAdmissionConfig` to
    :func:`release_admission` so the composition root does not have to
    thread ``expected_code_digest``/the static admission+restriction facts
    through every call site itself."""

    def __init__(self, config: ReleaseAdmissionConfig) -> None:
        self._config = config

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
            expected_code_digest=self._config.expected_code_digest,
        )
