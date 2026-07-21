"""Gap state machine — ERI-EV-004/012 (design #4 §2.7).

The gap status transition SUSPECTED -> CONFIRMED -> CONTAINED -> REPAIRED ->
INDEPENDENTLY_REVIEWED is an appended chain (never a mutated field): forward-only,
no skip, no regression, with per-state preconditions and a fail-closed
new-risk block. A gap record's authority is always false in every state.
"""

from __future__ import annotations

import itertools

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from tos.evidence import (
    GAP_STATUS_ORDER,
    EvidenceGapRecord,
    GapStatus,
    gap_blocks_new_risk,
    gap_chain_current_status,
    gap_chain_valid,
    gap_transition_allowed,
    grants_no_authority,
)
from tos.evidence.gap import GapResponse

from ._evidence_strategies import gap_chain, make_gap

_STATUSES = list(GapStatus)


# ---- forward-only transition predicate -------------------------------------


@given(frm=st.sampled_from(_STATUSES), to=st.sampled_from(_STATUSES))
def test_transition_allowed_iff_next_step(frm: GapStatus, to: GapStatus) -> None:
    """A transition is allowed iff ``to`` is exactly one step after ``frm`` (§2.7)."""
    expected = GAP_STATUS_ORDER.index(to) == GAP_STATUS_ORDER.index(frm) + 1
    assert gap_transition_allowed(frm, to) is expected


def test_skip_transition_rejected() -> None:
    """SUSPECTED -> REPAIRED (skipping CONTAINED) is not allowed."""
    assert gap_transition_allowed(GapStatus.SUSPECTED, GapStatus.REPAIRED) is False


def test_regression_transition_rejected() -> None:
    """REPAIRED -> SUSPECTED (regression) is not allowed."""
    assert gap_transition_allowed(GapStatus.REPAIRED, GapStatus.SUSPECTED) is False


# ---- appended chain --------------------------------------------------------


def test_full_forward_chain_is_valid() -> None:
    """The full forward chain is a valid appended progression, head = last status."""
    chain = gap_chain(*GAP_STATUS_ORDER)
    assert gap_chain_valid(chain) is True
    assert gap_chain_current_status(chain) is GapStatus.INDEPENDENTLY_REVIEWED


def test_chain_with_skip_is_invalid() -> None:
    """A chain that skips a state is not a valid progression."""
    chain = gap_chain(GapStatus.SUSPECTED, GapStatus.CONTAINED)
    assert gap_chain_valid(chain) is False


def test_chain_with_mixed_gap_ids_is_invalid() -> None:
    """A chain mixing gap ids is not a single-gap progression."""
    a = make_gap(GapStatus.SUSPECTED, gap_id="gap-1")
    b = make_gap(GapStatus.CONFIRMED, gap_id="gap-2")
    assert gap_chain_valid([a, b]) is False


# ---- per-state preconditions (unconstructable when unmet) ------------------


def test_confirmed_requires_detection_basis() -> None:
    """A CONFIRMED gap without detected_by is unconstructable (§2.7)."""
    with pytest.raises(ValidationError):
        EvidenceGapRecord(gap_id="g", status=GapStatus.CONFIRMED)


def test_contained_requires_containment_generation() -> None:
    """A CONTAINED gap without a containment generation is unconstructable (§2.7)."""
    with pytest.raises(ValidationError):
        EvidenceGapRecord(gap_id="g", status=GapStatus.CONTAINED, detected_by="d")


def test_repaired_requires_recovery_sources() -> None:
    """A REPAIRED gap without recovered ids + recovery sources is rejected (§2.7)."""
    with pytest.raises(ValidationError):
        EvidenceGapRecord(
            gap_id="g",
            status=GapStatus.REPAIRED,
            detected_by="d",
            response=GapResponse(new_risk_blocked=True, containment_generation=1),
        )


# ---- fail-closed new-risk block --------------------------------------------


@given(status=st.sampled_from(_STATUSES))
def test_gap_blocks_new_risk_in_every_valid_state(status: GapStatus) -> None:
    """A validly-built gap keeps new risk blocked in every state (fail-closed §2.7)."""
    gap = make_gap(status)
    assert gap_blocks_new_risk(gap) is True


@given(status=st.sampled_from(_STATUSES[:-1]))  # all but INDEPENDENTLY_REVIEWED
def test_unblocking_before_review_is_unconstructable(status: GapStatus) -> None:
    """Unblocking new risk before independent review is unconstructable (§2.7)."""
    with pytest.raises(ValidationError):
        make_gap(status, response=GapResponse(new_risk_blocked=False))


# ---- authority always false ------------------------------------------------


@given(status=st.sampled_from(_STATUSES))
def test_gap_grants_no_authority(status: GapStatus) -> None:
    """A gap closes no UNKNOWN / releases no capacity / never re-arms (§4.6/§1 25)."""
    gap = make_gap(status)
    assert grants_no_authority(gap.authority_effect) is True


def test_true_gap_authority_is_unconstructable() -> None:
    """Any true gap authority flag makes the record unconstructable (ERI-INV-001/014)."""
    from tos.evidence.gap import GapAuthorityEffect

    with pytest.raises(ValidationError):
        GapAuthorityEffect(closes_unknown=True)


def test_no_mutating_transition_between_records() -> None:
    """State advances only by appending a *new* record, never by mutating one (§2.7)."""
    suspected = make_gap(GapStatus.SUSPECTED)
    with pytest.raises(ValidationError):
        suspected.status = GapStatus.CONFIRMED  # type: ignore[misc]


def test_consecutive_pairs_of_valid_chain_are_allowed_transitions() -> None:
    """Every consecutive pair in the valid chain is an allowed transition."""
    chain = gap_chain(*GAP_STATUS_ORDER)
    for earlier, later in itertools.pairwise(chain):
        assert gap_transition_allowed(earlier.status, later.status) is True
