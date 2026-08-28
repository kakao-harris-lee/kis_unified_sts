"""MAJOR-2 stored ``validity.result`` conservatism (design §5.1, CII-INV-005).

A snapshot must not store a ``validity.result`` less restrictive than the
intrinsic conservative aggregate of its own evaluations/cut/common-mode — closing
the fail-open gap where a snapshot carrying a blocking INVALID field could still
claim ``result=VALID``.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given
from pydantic import ValidationError
from tos.capsule import CriticalInputSnapshot
from tos.capsule.field_evaluation import FieldEvaluation
from tos.capsule.field_state import FieldState, restrictiveness
from tos.capsule.predicates import (
    aggregate_snapshot_validity,
    verify_validity_result_conservative,
)
from tos.capsule.snapshot import SnapshotValidity

from ._strategies import COMPATIBLE_CUT, issue_snapshot, snapshot_required_kwargs

_field_evaluations = st.lists(
    st.builds(
        FieldEvaluation,
        field_ref=st.text(min_size=1, max_size=4),
        state=st.sampled_from(list(FieldState)),
        blocking=st.booleans(),
    ),
    max_size=4,
)


def test_false_valid_result_rejected() -> None:
    """A blocking INVALID field with a stored result=VALID is unconstructable (MAJOR-2)."""
    with pytest.raises(ValidationError):
        issue_snapshot(
            field_evaluations=(
                FieldEvaluation(field_ref="x", state=FieldState.INVALID, blocking=True),
            ),
            validity=SnapshotValidity(result=FieldState.VALID),
        )


def test_conservative_result_allowed() -> None:
    """Storing a result at least as restrictive as the aggregate is allowed."""
    snap = issue_snapshot(
        field_evaluations=(
            FieldEvaluation(field_ref="x", state=FieldState.INVALID, blocking=True),
        ),
        validity=SnapshotValidity(result=FieldState.INVALID),
    )
    assert verify_validity_result_conservative(snap)


@given(evaluations=_field_evaluations, stored=st.sampled_from(list(FieldState)))
def test_issuance_iff_result_conservative(
    evaluations: list, stored: FieldState
) -> None:
    """A snapshot issues iff its stored result is >= the intrinsic aggregate (§5.1).

    The intrinsic aggregate is computed on a DRAFT twin (whose conservatism check
    is skipped) so the prediction never depends on the guard under test.
    """
    evals = tuple(evaluations)
    kwargs = snapshot_required_kwargs(
        field_evaluations=evals,
        consistency_cut=COMPATIBLE_CUT,
        validity=SnapshotValidity(result=stored),
    )
    draft = CriticalInputSnapshot(**kwargs)  # status defaults to DRAFT
    intrinsic = aggregate_snapshot_validity(draft, required_independent_paths=0)
    conservative = restrictiveness(stored) >= restrictiveness(intrinsic)

    if conservative:
        snap = issue_snapshot(
            field_evaluations=evals,
            consistency_cut=COMPATIBLE_CUT,
            validity=SnapshotValidity(result=stored),
        )
        assert verify_validity_result_conservative(snap)
    else:
        with pytest.raises(ValidationError):
            issue_snapshot(
                field_evaluations=evals,
                consistency_cut=COMPATIBLE_CUT,
                validity=SnapshotValidity(result=stored),
            )
