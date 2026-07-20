"""CII-EV-001 classification completeness + CII-EV-011 authority absence.

* CII-EV-001 (design §5.8): every *material* input must be classified critical;
  unknown materiality is conservatively treated as material.
* CII-EV-011 (design §4.4): every authority flag is forced ``false`` — a ``True``
  value makes the artifact unconstructable (the full "no authority path anywhere"
  proof is EV-L2/L3; L1 verifies only the invariant).
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given
from pydantic import ValidationError
from tos.capsule import CapsuleAuthority, SnapshotAuthority
from tos.capsule.predicates import (
    InputClassification,
    classification_complete,
    grants_no_authority,
    is_material,
)

from ._strategies import issue_capsule, issue_snapshot

_classifications = st.lists(
    st.builds(
        InputClassification,
        input_id=st.text(min_size=1, max_size=4),
        could_change_decision=st.none() | st.booleans(),
        classified_critical=st.booleans(),
    ),
    max_size=6,
)


# ---- CII-EV-001 ------------------------------------------------------------


@given(inputs=_classifications)
def test_classification_complete_iff_all_material_classified(inputs: list) -> None:
    """Completeness holds iff every material input is classified critical (§5.8)."""
    expected = all(
        inp.classified_critical
        for inp in inputs
        if is_material(inp.could_change_decision)
    )
    assert classification_complete(inputs) is expected


def test_unknown_materiality_is_material() -> None:
    """Unknown materiality (None) is treated as material (conservative, §5.8)."""
    assert is_material(None) is True
    unclassified_unknown = [
        InputClassification(input_id="x", could_change_decision=None)
    ]
    assert classification_complete(unclassified_unknown) is False


def test_immaterial_input_need_not_be_classified() -> None:
    """A definitively immaterial input does not break completeness."""
    inputs = [
        InputClassification(
            input_id="x", could_change_decision=False, classified_critical=False
        )
    ]
    assert classification_complete(inputs) is True


# ---- CII-EV-011 ------------------------------------------------------------


_SNAPSHOT_AUTHORITY_FLAGS = list(SnapshotAuthority.model_fields)
_CAPSULE_AUTHORITY_FLAGS = list(CapsuleAuthority.model_fields)


@given(flag=st.sampled_from(_SNAPSHOT_AUTHORITY_FLAGS))
def test_snapshot_authority_true_flag_rejected(flag: str) -> None:
    """Any true snapshot-authority flag is unconstructable (CII-INV-011)."""
    with pytest.raises(ValidationError):
        SnapshotAuthority(**{flag: True})


@given(flag=st.sampled_from(_CAPSULE_AUTHORITY_FLAGS))
def test_capsule_authority_true_flag_rejected(flag: str) -> None:
    """Any true capsule-authority flag is unconstructable (CII-INV-011)."""
    with pytest.raises(ValidationError):
        CapsuleAuthority(**{flag: True})


def test_issued_artifacts_grant_no_authority() -> None:
    """Issued snapshot and capsule grant no authority (design §4.4)."""
    snap = issue_snapshot()
    cap = issue_capsule()
    assert grants_no_authority(snap) is True
    assert grants_no_authority(cap) is True
