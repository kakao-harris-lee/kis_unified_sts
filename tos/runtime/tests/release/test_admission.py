"""``release_admission`` / ``ReleaseAdmissionService`` tests (design #40 §5
order 6, lane R item 4)."""

from __future__ import annotations

from tos.sci import AdmissionResult
from tos.workload import RuntimeIdentity
from tos_runtime.release.admission import (
    ReleaseAdmissionService,
    ReleaseRestrictionLookup,
    release_admission,
)
from tos_runtime.release.config import ReleaseAdmissionConfig


def test_admits_when_every_clause_holds(identity: RuntimeIdentity) -> None:
    restriction = ReleaseRestrictionLookup(resolved=True, active=None)
    admitted = release_admission(
        identity,
        AdmissionResult.ADMIT,
        restriction,
        currentness_current=True,
        expected_code_digest="digest-abc",
    )
    assert admitted is True


def test_refuses_when_code_digest_mismatches(identity: RuntimeIdentity) -> None:
    restriction = ReleaseRestrictionLookup(resolved=True, active=None)
    admitted = release_admission(
        identity,
        AdmissionResult.ADMIT,
        restriction,
        currentness_current=True,
        expected_code_digest="a-different-digest",
    )
    assert admitted is False


def test_refuses_when_admission_is_not_admit(identity: RuntimeIdentity) -> None:
    restriction = ReleaseRestrictionLookup(resolved=True, active=None)
    for result in (AdmissionResult.DENY, AdmissionResult.UNKNOWN, None):
        admitted = release_admission(
            identity,
            result,
            restriction,
            currentness_current=True,
            expected_code_digest="digest-abc",
        )
        assert admitted is False


def test_refuses_when_currentness_is_not_current(identity: RuntimeIdentity) -> None:
    restriction = ReleaseRestrictionLookup(resolved=True, active=None)
    for currentness in (False, None):
        admitted = release_admission(
            identity,
            AdmissionResult.ADMIT,
            restriction,
            currentness_current=currentness,
            expected_code_digest="digest-abc",
        )
        assert admitted is False


def test_refuses_when_restriction_lookup_is_unresolved(
    identity: RuntimeIdentity,
) -> None:
    """An unresolved restriction lookup denies conservatively regardless of
    what `active` carries (SCI-INV-014)."""
    for resolved in (False, None):
        restriction = ReleaseRestrictionLookup(resolved=resolved, active=None)
        admitted = release_admission(
            identity,
            AdmissionResult.ADMIT,
            restriction,
            currentness_current=True,
            expected_code_digest="digest-abc",
        )
        assert admitted is False


def test_refuses_when_a_restriction_is_present(identity: RuntimeIdentity) -> None:
    from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
    from tos.sci import ReleaseRestriction, SupplyChainScope

    scheme = get_scheme(EV_L1_PROVISIONAL_VERSION)
    active = ReleaseRestriction.issue(
        scheme=scheme,
        restriction_id="r-1",
        restriction_generation=1,
        restricted_scope=SupplyChainScope(),
    )
    restriction = ReleaseRestrictionLookup(resolved=True, active=active)
    admitted = release_admission(
        identity,
        AdmissionResult.ADMIT,
        restriction,
        currentness_current=True,
        expected_code_digest="digest-abc",
    )
    assert admitted is False


def test_restriction_lookup_present_is_negative_polarity_unknown_when_unresolved() -> (
    None
):
    lookup = ReleaseRestrictionLookup(resolved=None, active=None)
    assert lookup.present is None
    lookup = ReleaseRestrictionLookup(resolved=True, active=None)
    assert lookup.present is False


# ============================================================================
# ReleaseAdmissionService — binds a config to release_admission
# ============================================================================


def _config(**overrides: object) -> ReleaseAdmissionConfig:
    base: dict[str, object] = {
        "expected_code_digest": "digest-abc",
        "admission_result": AdmissionResult.ADMIT,
        "restriction_state_resolved": True,
        "restriction_present": False,
        "restriction": None,
    }
    base.update(overrides)
    return ReleaseAdmissionConfig(**base)  # type: ignore[arg-type]


def test_service_decide_admits_under_a_clean_config(identity: RuntimeIdentity) -> None:
    service = ReleaseAdmissionService(_config())
    assert service.decide(identity, currentness_current=True) is True


def test_service_decide_refuses_under_an_unresolved_restriction_config(
    identity: RuntimeIdentity,
) -> None:
    service = ReleaseAdmissionService(_config(restriction_state_resolved=False))
    assert service.decide(identity, currentness_current=True) is False
