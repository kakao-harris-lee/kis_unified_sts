"""CII-EV-012 (core) non-revival + context-generation ordering (design §4.4/§7).

A restricted (invalidated/superseded) capsule cannot be revived under the same
identity by restart/restore; new risk requires a new capsule. An older context
generation cannot authorize new risk after a newer restrictive generation.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.capsule import ArtifactStatus, DecisionContextCapsule
from tos.capsule.capsule import CapsuleValidity
from tos.capsule.context_generation import generation_can_authorize
from tos.capsule.predicates import capsule_can_authorize_new_risk, non_revival_holds

from ._strategies import issue_capsule


def _with_status(
    cap: DecisionContextCapsule, status: ArtifactStatus
) -> DecisionContextCapsule:
    """Reconstruct ``cap`` with a changed (digest-excluded) status."""
    kwargs = cap.model_dump()
    kwargs["status"] = status
    return DecisionContextCapsule(**kwargs)


def test_issued_capsule_can_authorize() -> None:
    """A clean ISSUED capsule (all required fields concrete) may ground new risk."""
    cap = issue_capsule()
    assert capsule_can_authorize_new_risk(cap) is True


@given(status=st.sampled_from([ArtifactStatus.INVALIDATED, ArtifactStatus.SUPERSEDED]))
def test_restricted_status_cannot_authorize(status: ArtifactStatus) -> None:
    """An INVALIDATED/SUPERSEDED capsule cannot ground new risk (fail-closed)."""
    restricted = _with_status(issue_capsule(), status)
    assert capsule_can_authorize_new_risk(restricted) is False


def test_draft_cannot_authorize() -> None:
    """A DRAFT capsule cannot ground new risk (pre-issuance, fail-closed)."""
    # A DRAFT legitimately has no digest/id (MINOR-3), so build a clean draft
    # rather than demoting an issued capsule (which MINOR-3 now forbids).
    draft = DecisionContextCapsule(status=ArtifactStatus.DRAFT)
    assert capsule_can_authorize_new_risk(draft) is False


def test_invalidation_generation_blocks_authorization() -> None:
    """An invalidation generation on the capsule blocks authorization."""
    cap = issue_capsule(validity=CapsuleValidity(invalidation_generation=7))
    assert capsule_can_authorize_new_risk(cap) is False


@given(now=st.integers(0, 10**6))
def test_expiry_blocks_authorization(now: int) -> None:
    """A passed expiry blocks authorization; an unexpired capsule authorizes."""
    expires_at = 500
    cap = issue_capsule(validity=CapsuleValidity(expires_at=expires_at))
    expected = now <= expires_at
    assert capsule_can_authorize_new_risk(cap, now_ms=now) is expected


def test_non_revival_of_same_identity_detected() -> None:
    """Restoring a restricted capsule under its old id is a revival (blocked)."""
    cap = issue_capsule()
    invalidated = _with_status(cap, ArtifactStatus.INVALIDATED)
    # Restoring the *same identity* to an authorizing state violates non-revival.
    assert non_revival_holds(invalidated, cap) is False


def test_new_capsule_respects_non_revival() -> None:
    """A genuinely new capsule (new identity) respects non-revival."""
    cap = issue_capsule()
    invalidated = _with_status(cap, ArtifactStatus.INVALIDATED)
    fresh = issue_capsule(issuer_principal_id="iss-new")
    assert fresh.capsule_id != invalidated.capsule_id
    assert non_revival_holds(invalidated, fresh) is True


# ---- context-generation ordering (design §2.8/§5.7) ------------------------


@given(subject=st.integers(0, 100), latest=st.integers(0, 100))
def test_generation_ordering(subject: int, latest: int) -> None:
    """An older generation cannot authorize after a newer restrictive one (§5.7)."""
    assert generation_can_authorize(subject, latest) is (subject >= latest)


@given(latest=st.integers(0, 100))
def test_generation_fail_closed_on_unknown(latest: int) -> None:
    """An unknown subject generation is denied (fail-closed)."""
    assert generation_can_authorize(None, latest) is False
    assert generation_can_authorize(latest, None) is False
