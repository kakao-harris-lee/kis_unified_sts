"""``release_admission`` / ``ReleaseAdmissionService`` tests (design #40 §5"""

from __future__ import annotations

from tos.workload import RuntimeIdentity
from tos_runtime.operations.dependency_admission import RuntimeArtifactObservation
from tos_runtime.release.admission import (
    ReleaseAdmissionService,
    ReleaseRestrictionLookup,
    release_admission,
)
from tos_runtime.release.config import ReleaseAdmissionConfig
from tos_runtime.release.verdict import AdmissionResult, ReleaseRestriction


def test_admits_when_every_clause_holds(
    identity: RuntimeIdentity, observation: RuntimeArtifactObservation
) -> None:
    restriction = ReleaseRestrictionLookup(resolved=True, active=None)
    admitted = release_admission(
        identity,
        AdmissionResult.ADMIT,
        restriction,
        currentness_current=True,
        observation=observation,
        expected_code_digest="digest-abc",
        expected_dependency_set_digest="dep-digest-abc",
    )
    assert admitted is True


def test_refuses_when_code_digest_mismatches(
    identity: RuntimeIdentity, observation: RuntimeArtifactObservation
) -> None:
    restriction = ReleaseRestrictionLookup(resolved=True, active=None)
    admitted = release_admission(
        identity,
        AdmissionResult.ADMIT,
        restriction,
        currentness_current=True,
        observation=observation,
        expected_code_digest="a-different-digest",
        expected_dependency_set_digest="dep-digest-abc",
    )
    assert admitted is False


def test_refuses_when_dependency_set_digest_mismatches(
    identity: RuntimeIdentity, observation: RuntimeArtifactObservation
) -> None:
    """M2 guard: a source-tree match alone must not admit — the dependency-"""
    restriction = ReleaseRestrictionLookup(resolved=True, active=None)
    admitted = release_admission(
        identity,
        AdmissionResult.ADMIT,
        restriction,
        currentness_current=True,
        observation=observation,
        expected_code_digest="digest-abc",
        expected_dependency_set_digest="a-different-dependency-digest",
    )
    assert admitted is False


def test_refuses_when_identity_code_digest_disagrees_with_the_observation(
    identity: RuntimeIdentity, observation: RuntimeArtifactObservation
) -> None:
    """Re-review disposition (HIGH, 2026-09-12): ``identity.code_digest`` used"""
    mismatched_identity = identity.model_copy(
        update={"code_digest": "identity-built-from-a-constant-not-the-observation"}
    )
    restriction = ReleaseRestrictionLookup(resolved=True, active=None)
    admitted = release_admission(
        mismatched_identity,
        AdmissionResult.ADMIT,
        restriction,
        currentness_current=True,
        observation=observation,
        expected_code_digest="digest-abc",
        expected_dependency_set_digest="dep-digest-abc",
    )
    assert admitted is False


def test_refuses_when_admission_is_not_admit(
    identity: RuntimeIdentity, observation: RuntimeArtifactObservation
) -> None:
    restriction = ReleaseRestrictionLookup(resolved=True, active=None)
    for result in (AdmissionResult.DENY, AdmissionResult.UNKNOWN, None):
        admitted = release_admission(
            identity,
            result,
            restriction,
            currentness_current=True,
            observation=observation,
            expected_code_digest="digest-abc",
            expected_dependency_set_digest="dep-digest-abc",
        )
        assert admitted is False


def test_refuses_when_currentness_is_not_current(
    identity: RuntimeIdentity, observation: RuntimeArtifactObservation
) -> None:
    restriction = ReleaseRestrictionLookup(resolved=True, active=None)
    for currentness in (False, None):
        admitted = release_admission(
            identity,
            AdmissionResult.ADMIT,
            restriction,
            currentness_current=currentness,
            observation=observation,
            expected_code_digest="digest-abc",
            expected_dependency_set_digest="dep-digest-abc",
        )
        assert admitted is False


def test_refuses_when_restriction_lookup_is_unresolved(
    identity: RuntimeIdentity, observation: RuntimeArtifactObservation
) -> None:
    """An unresolved restriction lookup denies conservatively regardless of"""
    for resolved in (False, None):
        restriction = ReleaseRestrictionLookup(resolved=resolved, active=None)
        admitted = release_admission(
            identity,
            AdmissionResult.ADMIT,
            restriction,
            currentness_current=True,
            observation=observation,
            expected_code_digest="digest-abc",
            expected_dependency_set_digest="dep-digest-abc",
        )
        assert admitted is False


def test_refuses_when_a_restriction_is_present(
    identity: RuntimeIdentity, observation: RuntimeArtifactObservation
) -> None:
    active = ReleaseRestriction(restriction_id="r-1", restriction_generation=1)
    restriction = ReleaseRestrictionLookup(resolved=True, active=active)
    admitted = release_admission(
        identity,
        AdmissionResult.ADMIT,
        restriction,
        currentness_current=True,
        observation=observation,
        expected_code_digest="digest-abc",
        expected_dependency_set_digest="dep-digest-abc",
    )
    assert admitted is False


def test_restriction_lookup_present_is_negative_polarity_unknown_when_unresolved() -> (
    None
):
    lookup = ReleaseRestrictionLookup(resolved=None, active=None)
    assert lookup.present is None
    lookup = ReleaseRestrictionLookup(resolved=True, active=None)
    assert lookup.present is False


def _config(**overrides: object) -> ReleaseAdmissionConfig:
    base: dict[str, object] = {
        "expected_code_digest": "digest-abc",
        "expected_dependency_set_digest": "dep-digest-abc",
        "admission_result": AdmissionResult.ADMIT,
        "restriction_state_resolved": True,
        "restriction_present": False,
        "restriction": None,
    }
    base.update(overrides)
    return ReleaseAdmissionConfig(**base)  # type: ignore[arg-type]


def test_service_decide_admits_under_a_clean_config(
    identity: RuntimeIdentity, observation: RuntimeArtifactObservation
) -> None:
    service = ReleaseAdmissionService(_config(), observation)
    assert service.decide(identity, currentness_current=True) is True


def test_service_decide_refuses_under_an_unresolved_restriction_config(
    identity: RuntimeIdentity, observation: RuntimeArtifactObservation
) -> None:
    service = ReleaseAdmissionService(
        _config(restriction_state_resolved=False), observation
    )
    assert service.decide(identity, currentness_current=True) is False


def test_service_decide_refuses_under_a_mismatched_dependency_set_digest(
    identity: RuntimeIdentity, observation: RuntimeArtifactObservation
) -> None:
    service = ReleaseAdmissionService(
        _config(expected_dependency_set_digest="a-different-dependency-digest"),
        observation,
    )
    assert service.decide(identity, currentness_current=True) is False


def test_service_reuses_the_same_observation_across_repeated_decide_calls(
    identity: RuntimeIdentity, observation: RuntimeArtifactObservation
) -> None:
    """No double observation: one :class:`ReleaseAdmissionService` bound to"""
    service = ReleaseAdmissionService(_config(), observation)
    assert service.decide(identity, currentness_current=True) is True
    assert service.decide(identity, currentness_current=True) is True
    assert service._observation is observation
