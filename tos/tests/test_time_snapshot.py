"""Time Health Snapshot — digest binding, id⊥digest, consumer binding (time design §2.1/§7)."""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.canonical import ArtifactIntegrityError, ArtifactStatus
from tos.time import HealthState, TimeHealthSnapshot, snapshot_consumer_binding_ok

from ._time_strategies import issue_time_snapshot


def _snapshot_id(snap: TimeHealthSnapshot) -> str:
    """``snap.snapshot_id``, asserted present — every fixture below issues via"""
    value = snap.snapshot_id
    assert value is not None
    return value


def _digest(snap: TimeHealthSnapshot) -> str:
    """``snap.canonical_digest``, asserted present — an ISSUED artifact always has a"""
    value = snap.canonical_digest
    assert value is not None
    return value


def test_issued_snapshot_binds_its_digest() -> None:
    """An issued snapshot self-verifies its canonical digest (REUSE §2.1)."""
    snap = issue_time_snapshot()
    assert snap.status is ArtifactStatus.ISSUED
    assert snap.canonical_digest is not None
    assert TimeHealthSnapshot(**snap.model_dump()) == snap


def test_snapshot_id_is_independent_not_derived_from_digest() -> None:
    """``snapshot_id`` is service-assigned, NOT ``f(digest)`` (§0.4a / gap 6a)."""
    snap = issue_time_snapshot(snapshot_id="ths-service-assigned")
    assert snap.snapshot_id == "ths-service-assigned"
    assert snap.snapshot_id != snap.canonical_digest
    assert snap.snapshot_id != f"ths-{snap.canonical_digest}"


def test_same_bytes_different_declared_generation_is_representable() -> None:
    """generation ⊥ digest: same covered bytes can carry a different generation (§8 208)."""
    a = issue_time_snapshot(generation=1)
    b = issue_time_snapshot(generation=2)
    assert a.canonical_digest == b.canonical_digest
    assert a.generation != b.generation


def test_tampered_digest_is_unconstructable() -> None:
    """A mismatched stored digest fails construction (digest binding, §2.1)."""
    snap = issue_time_snapshot()
    kwargs = snap.model_dump()
    kwargs["canonical_digest"] = "deadbeef"
    try:
        TimeHealthSnapshot(**kwargs)
    except (ArtifactIntegrityError, ValueError):
        return
    raise AssertionError("tampered digest was accepted")


def test_missing_required_covered_cannot_issue() -> None:
    """Issuing without a required structural field is rejected (not a valid snapshot)."""
    from ._time_strategies import SCHEME

    try:
        TimeHealthSnapshot.issue(
            scheme=SCHEME,
            snapshot_id="x",
            generation=1,
            health_state=HealthState.TRUSTED,
        )
    except (ArtifactIntegrityError, ValueError):
        return
    raise AssertionError("issued a snapshot missing required-covered fields")


def test_bounds_stay_optional_null_still_issues() -> None:
    """numeric bounds/max-age null must NOT force DRAFT (time design §2.1)."""
    snap = issue_time_snapshot(maximum_consumer_age_ms=None)
    assert snap.status is ArtifactStatus.ISSUED
    assert snap.maximum_consumer_age_ms is None


def test_consumer_binding_ok_on_exact_match() -> None:
    """A consumer's exact (id, generation, digest) binding matches (§7 MINOR-1)."""
    snap = issue_time_snapshot(snapshot_id="ths-9", generation=5)
    assert snapshot_consumer_binding_ok(
        snap,
        expected_snapshot_id="ths-9",
        expected_canonical_digest=_digest(snap),
        expected_generation=5,
        expected_verification_profile_version="vp-0",
        expected_safety_profile_version="sp-0",
    )


@given(expected_gen=st.integers(0, 50), actual_gen=st.integers(0, 50))
def test_wrong_generation_rejected(expected_gen: int, actual_gen: int) -> None:
    """A generation mismatch is rejected even with a matching digest (§8 208)."""
    snap = issue_time_snapshot(generation=actual_gen)
    ok = snapshot_consumer_binding_ok(
        snap,
        expected_snapshot_id=_snapshot_id(snap),
        expected_canonical_digest=_digest(snap),
        expected_generation=expected_gen,
    )
    assert ok is (expected_gen == actual_gen)


def test_null_generation_fails_closed_against_concrete_expectation() -> None:
    """A null snapshot generation cannot satisfy a concrete expected generation."""
    snap = issue_time_snapshot(generation=None)
    assert (
        snapshot_consumer_binding_ok(
            snap,
            expected_snapshot_id=_snapshot_id(snap),
            expected_canonical_digest=_digest(snap),
            expected_generation=7,
        )
        is False
    )


def test_wrong_digest_or_id_rejected() -> None:
    """A wrong id or digest is rejected regardless of generation (§8 208)."""
    snap = issue_time_snapshot()
    assert not snapshot_consumer_binding_ok(
        snap,
        expected_snapshot_id="other",
        expected_canonical_digest=_digest(snap),
    )
    assert not snapshot_consumer_binding_ok(
        snap,
        expected_snapshot_id=_snapshot_id(snap),
        expected_canonical_digest="not-the-digest",
    )


def test_wrong_config_version_rejected() -> None:
    """A wrong verification/safety profile (config) version is rejected (§8 208)."""
    snap = issue_time_snapshot()
    assert not snapshot_consumer_binding_ok(
        snap,
        expected_snapshot_id=_snapshot_id(snap),
        expected_canonical_digest=_digest(snap),
        expected_verification_profile_version="wrong",
    )
    assert not snapshot_consumer_binding_ok(
        snap,
        expected_snapshot_id=_snapshot_id(snap),
        expected_canonical_digest=_digest(snap),
        expected_safety_profile_version="wrong",
    )
