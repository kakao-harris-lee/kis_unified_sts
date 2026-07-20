"""CII-EV-007 (core) capsule/snapshot binding + substitution resistance (§4.1).

Covers the design §4.1 / §7 CII-EV-007 core: frozen immutability, the
``canonical_digest == H_ver(canonicalize(covered))`` invariant, the derived
``id = f(digest)`` binding, covered-sensitivity, and rejection of mutate / union
/ partial-refresh / digest-substitution. Also the (A4) excluded-insensitivity
property at the model level (status + Layer-2 changes do not move the digest).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from pydantic import ValidationError
from tos.capsule import (
    ArtifactStatus,
    DecisionContextCapsule,
    derive_id,
)
from tos.capsule.capsule import Bindings, SnapshotRef

from ._strategies import REQUIRED_FIELD_TEXT, SCHEME, issue_snapshot
from ._strategies import issue_capsule as _issue_capsule

# ---- id = f(digest) + digest == canonicalize(covered) ----------------------


@given(issuer=REQUIRED_FIELD_TEXT)
def test_capsule_id_derived_from_digest(issuer: str) -> None:
    """An issued capsule's id is exactly ``derive_id(prefix, digest)`` (§4.1)."""
    cap = _issue_capsule(issuer_principal_id=issuer)
    assert cap.canonical_digest is not None
    assert cap.capsule_id == derive_id("dcc", cap.canonical_digest)
    assert cap.canonical_digest == SCHEME.compute_digest(cap.covered_content())


@given(issuer=REQUIRED_FIELD_TEXT)
def test_snapshot_id_derived_from_digest(issuer: str) -> None:
    """An issued snapshot's id is exactly ``derive_id(prefix, digest)`` (§4.1)."""
    snap = issue_snapshot(issuer_principal_id=issuer)
    assert snap.snapshot_id == derive_id("cis", snap.canonical_digest)
    assert snap.canonical_digest == SCHEME.compute_digest(snap.covered_content())


# ---- frozen immutability ---------------------------------------------------


def test_capsule_is_frozen() -> None:
    """A capsule is immutable: field assignment is rejected (§12/§4.1)."""
    cap = _issue_capsule(issuer_principal_id="iss")
    with pytest.raises(ValidationError):
        cap.issuer_principal_id = "other"  # type: ignore[misc]


# ---- covered sensitivity ---------------------------------------------------


@given(a=REQUIRED_FIELD_TEXT, b=REQUIRED_FIELD_TEXT)
def test_covered_change_changes_digest_and_id(a: str, b: str) -> None:
    """Changing a covered field yields a different digest and id (CII-EV-007)."""
    if a == b:
        return
    c1 = _issue_capsule(issuer_principal_id=a)
    c2 = _issue_capsule(issuer_principal_id=b)
    assert c1.canonical_digest != c2.canonical_digest
    assert c1.capsule_id != c2.capsule_id


# ---- substitution / mutate / union / partial-refresh rejection -------------


def _reissue_kwargs(cap: DecisionContextCapsule) -> dict:
    """Round-trippable construction kwargs from an issued capsule."""
    return cap.model_dump()


def test_reconstruction_control_succeeds() -> None:
    """Control: reconstructing from an unmodified dump succeeds and is equal."""
    cap = _issue_capsule(issuer_principal_id="iss")
    rebuilt = DecisionContextCapsule(**_reissue_kwargs(cap))
    assert rebuilt == cap


def test_mutate_with_stale_identity_rejected() -> None:
    """Changing a covered field while keeping the old digest/id is rejected."""
    cap = _issue_capsule(issuer_principal_id="iss")
    kwargs = _reissue_kwargs(cap)
    kwargs["issuer_principal_id"] = "tampered"  # covered change, identity stale
    with pytest.raises(ValidationError):
        DecisionContextCapsule(**kwargs)


def test_digest_substitution_rejected() -> None:
    """A substituted (wrong) digest is rejected even with a matching f(digest) id."""
    cap = _issue_capsule(issuer_principal_id="iss")
    kwargs = _reissue_kwargs(cap)
    wrong = "0" * 64
    kwargs["canonical_digest"] = wrong
    kwargs["capsule_id"] = derive_id("dcc", wrong)  # id stays f(digest)
    with pytest.raises(ValidationError):
        DecisionContextCapsule(**kwargs)


def test_id_substitution_rejected() -> None:
    """A correct digest with a non-derived id is rejected (§4.1)."""
    cap = _issue_capsule(issuer_principal_id="iss")
    kwargs = _reissue_kwargs(cap)
    kwargs["capsule_id"] = "dcc-not-derived"
    with pytest.raises(ValidationError):
        DecisionContextCapsule(**kwargs)


def test_partial_refresh_rejected() -> None:
    """Refreshing the embedded snapshot ref without re-deriving identity fails."""
    cap = _issue_capsule(
        issuer_principal_id="iss",
        critical_input_snapshot=SnapshotRef(snapshot_id="cis-a", canonical_digest="a"),
    )
    kwargs = _reissue_kwargs(cap)
    kwargs["critical_input_snapshot"] = {
        "snapshot_id": "cis-b",
        "canonical_digest": "b",
    }
    with pytest.raises(ValidationError):
        DecisionContextCapsule(**kwargs)


def test_union_of_two_capsules_rejected() -> None:
    """Splicing another capsule's covered field under the old identity fails."""
    left = _issue_capsule(issuer_principal_id="left", context_generation=1)
    right = _issue_capsule(issuer_principal_id="right", context_generation=9)
    kwargs = _reissue_kwargs(left)
    kwargs["context_generation"] = right.context_generation  # spliced field
    with pytest.raises(ValidationError):
        DecisionContextCapsule(**kwargs)


# ---- (A4) excluded insensitivity at the model level ------------------------


def test_status_change_preserves_digest_and_id() -> None:
    """Status is excluded from the digest: a SUPERSEDED twin keeps id/digest (§3.2)."""
    cap = _issue_capsule(issuer_principal_id="iss")
    kwargs = _reissue_kwargs(cap)
    kwargs["status"] = ArtifactStatus.SUPERSEDED
    superseded = DecisionContextCapsule(**kwargs)
    assert superseded.canonical_digest == cap.canonical_digest
    assert superseded.capsule_id == cap.capsule_id
    assert superseded.status == ArtifactStatus.SUPERSEDED


def test_layer2_population_preserves_digest() -> None:
    """Layer-2 back-references are excluded: populating them keeps the digest (§4.3)."""
    cap = _issue_capsule(issuer_principal_id="iss")
    kwargs = _reissue_kwargs(cap)
    kwargs["bindings"] = Bindings(proposal_id="prop-1")
    with_binding = DecisionContextCapsule(**kwargs)
    assert with_binding.canonical_digest == cap.canonical_digest
    assert with_binding.capsule_id == cap.capsule_id
    assert with_binding.bindings is not None
