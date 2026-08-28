"""§5.2/§4.6 fill-to-obligation commit idempotency — the exhaustive truth table (PTF-EV-001).

Covers every cell of the design #24 §4.6 table plus the four pre-gates, in order:

* the ``RecordPairKind`` -> :class:`ObligationCommitOutcome` mapping is asserted **exhaustive**
  against the live canonical enum, so a future canonical member cannot fall through to a
  permissive default (the #21 C2 lesson);
* the **two forgery axes** are exercised separately and both fold to ``REJECTED_CONFLICT``:
  same **primary** id / different bytes is ``CRITICAL_CONFLICT``, same **idempotency** key /
  different bytes is ``DIVERGENT_EMISSION``. Both records survive — no last-write-wins;
* the **late-fill** canary re-applies one fill N >= 2 times and asserts the cumulative
  obligation effect count is exactly **1** (§12 line 347 harmlessness);
* ``COMMITTED_ONCE`` is reachable (the #21 C2 structurally-unreachable defect) and is reached
  **only** through the positive pre-gate conjunction — never as a dispatch residue.

[PTF-EV-001 coordinate; ``/2``, ``/3``, and ``+Broker`` remain open. Closing PTF-EV = 0.]
"""

from __future__ import annotations

import pytest
from hypothesis import given
from tos.canonical import ArtifactStatus, RecordPairKind, classify_record_pair
from tos.posttrade import (
    EconomicObligationRecord,
    ObligationCommitOutcome,
    PostTradeObligationLifecycleState,
    obligation_commit_idempotent,
)
from tos.posttrade.predicates import _RECORD_PAIR_OUTCOME

from ._posttrade_strategies import FORGED_FLAG, clean_obligation_record


def _classify(
    incoming: EconomicObligationRecord, prior: EconomicObligationRecord
) -> RecordPairKind:
    """Classify a pair exactly as the predicate does (the seam under test)."""
    return classify_record_pair(
        incoming.obligation_id,
        incoming.canonical_digest,
        prior.obligation_id,
        prior.canonical_digest,
        a_idempotency_id=incoming.idempotency_key,
        b_idempotency_id=prior.idempotency_key,
    )


# --- exhaustive mapping ------------------------------------------------------


def test_record_pair_mapping_is_exhaustive_over_the_live_canonical_enum() -> None:
    """(§4.6) All five ``RecordPairKind`` members are bound explicitly — no fall-through."""
    assert set(_RECORD_PAIR_OUTCOME) == set(RecordPairKind)
    assert len(_RECORD_PAIR_OUTCOME) == 5


def test_mapping_directions_match_the_truth_table() -> None:
    """(§4.6) The five cells map exactly as the design's truth table declares."""
    assert (
        _RECORD_PAIR_OUTCOME[RecordPairKind.IDEMPOTENT_DUP]
        is ObligationCommitOutcome.IDEMPOTENT_REPLAY
    )
    assert (
        _RECORD_PAIR_OUTCOME[RecordPairKind.CRITICAL_CONFLICT]
        is ObligationCommitOutcome.REJECTED_CONFLICT
    )
    assert (
        _RECORD_PAIR_OUTCOME[RecordPairKind.DIVERGENT_EMISSION]
        is ObligationCommitOutcome.REJECTED_CONFLICT
    )
    assert (
        _RECORD_PAIR_OUTCOME[RecordPairKind.DISTINCT]
        is ObligationCommitOutcome.REJECTED_UNKNOWN
    )
    assert (
        _RECORD_PAIR_OUTCOME[RecordPairKind.NOT_COMPARABLE]
        is ObligationCommitOutcome.REJECTED_UNKNOWN
    )


def test_no_record_pair_kind_maps_to_committed_once() -> None:
    """(§5.2) ``COMMITTED_ONCE`` is a **pre-gate** outcome; the classifier never yields it.

    If it did, a classified pair could increase the effect count a second time.
    """
    assert ObligationCommitOutcome.COMMITTED_ONCE not in set(
        _RECORD_PAIR_OUTCOME.values()
    )


# --- pre-gates, in order -----------------------------------------------------


def test_no_incoming_is_undecidable() -> None:
    """(pre-gate 1) Nothing to decide ⇒ fail closed."""
    assert (
        obligation_commit_idempotent(None, None, True)
        is ObligationCommitOutcome.REJECTED_UNKNOWN
    )


def test_a_correction_without_lineage_is_rejected() -> None:
    """(pre-gate 2, §20 line 460) A correction-claiming record owes a ``supersedes_ref``."""
    relabelled = clean_obligation_record(correction_bindings=("CORR-1",))
    assert (
        obligation_commit_idempotent(relabelled, None, True)
        is ObligationCommitOutcome.REJECTED_NO_LINEAGE
    )


@pytest.mark.parametrize(
    "state",
    [
        PostTradeObligationLifecycleState.CORRECTION_PENDING,
        PostTradeObligationLifecycleState.SUPERSEDED,
    ],
)
def test_a_correction_lifecycle_state_also_demands_lineage(
    state: PostTradeObligationLifecycleState,
) -> None:
    """(pre-gate 2) The two lifecycle states only a correction reaches demand lineage too."""
    relabelled = clean_obligation_record(lifecycle_state=state)
    assert (
        obligation_commit_idempotent(relabelled, None, True)
        is ObligationCommitOutcome.REJECTED_NO_LINEAGE
    )


def test_a_correction_with_lineage_passes_the_lineage_gate() -> None:
    """(positive side) Lineage present ⇒ the gate does not fire."""
    corrected = clean_obligation_record(
        correction_bindings=("CORR-1",), supersedes_ref="OBL-0"
    )
    assert (
        obligation_commit_idempotent(corrected, None, True)
        is ObligationCommitOutcome.COMMITTED_ONCE
    )


def test_an_original_obligation_owes_no_lineage() -> None:
    """(§5.2) Making ``supersedes_ref`` universal would make the first commit impossible."""
    original = clean_obligation_record()
    assert original.supersedes_ref is None
    assert (
        obligation_commit_idempotent(original, None, True)
        is ObligationCommitOutcome.COMMITTED_ONCE
    )


@pytest.mark.parametrize("retained", [False, None])
def test_an_unretained_original_is_an_overwrite(retained: bool | None) -> None:
    """(pre-gate 3, §11 line 330) Positive polarity: ``None`` and ``False`` both reject."""
    assert (
        obligation_commit_idempotent(clean_obligation_record(), None, retained)
        is ObligationCommitOutcome.REJECTED_OVERWRITE
    )


@given(retained=FORGED_FLAG)
def test_only_a_real_true_passes_the_retention_gate(retained: object) -> None:
    """(polarity) A truthy **or falsy** non-``bool`` is not proof of retention."""
    outcome = obligation_commit_idempotent(
        clean_obligation_record(), None, retained  # type: ignore[arg-type]
    )
    if retained is True:
        assert outcome is ObligationCommitOutcome.COMMITTED_ONCE
    else:
        assert outcome is ObligationCommitOutcome.REJECTED_OVERWRITE


def test_lineage_gate_precedes_the_overwrite_gate() -> None:
    """(order) A relabelled correction that is *also* an overwrite reports no-lineage first.

    The order is load-bearing: the §20 line 460 relabel is the more specific defect, and
    reporting the overwrite instead would hide it.
    """
    relabelled = clean_obligation_record(correction_bindings=("CORR-1",))
    assert (
        obligation_commit_idempotent(relabelled, None, False)
        is ObligationCommitOutcome.REJECTED_NO_LINEAGE
    )


def test_prior_is_none_gate_follows_the_lineage_and_overwrite_gates() -> None:
    """(order, §5.2) The first-commit branch is reached only after both earlier gates pass."""
    relabelled = clean_obligation_record(correction_bindings=("CORR-1",))
    assert (
        obligation_commit_idempotent(relabelled, None, True)
        is not ObligationCommitOutcome.COMMITTED_ONCE
    )


# --- the classifier truth table ----------------------------------------------


def test_same_bytes_replay_is_idempotent() -> None:
    """(row 1) Same primary id, same canonical bytes ⇒ a harmless re-apply."""
    first = clean_obligation_record()
    replay = clean_obligation_record()
    assert _classify(replay, first) is RecordPairKind.IDEMPOTENT_DUP
    assert (
        obligation_commit_idempotent(replay, first, True)
        is ObligationCommitOutcome.IDEMPOTENT_REPLAY
    )


def test_forgery_axis_one_same_primary_id_different_bytes() -> None:
    """(row 2, ``record_pair.py:96``) Obligation forgery ⇒ contained, never merged."""
    genuine = clean_obligation_record()
    forged = clean_obligation_record(obligation_type="TAX_LEG")
    assert genuine.obligation_id == forged.obligation_id
    assert genuine.canonical_digest != forged.canonical_digest
    assert _classify(forged, genuine) is RecordPairKind.CRITICAL_CONFLICT
    assert (
        obligation_commit_idempotent(forged, genuine, True)
        is ObligationCommitOutcome.REJECTED_CONFLICT
    )
    # contain both — neither record is destroyed or merged by the decision
    assert genuine.canonical_digest and forged.canonical_digest


def test_forgery_axis_two_same_idempotency_key_different_bytes() -> None:
    """(row 3, ``record_pair.py:103``) Two different fills claiming one commit key."""
    genuine = clean_obligation_record(obligation_id="OBL-A")
    forged = clean_obligation_record(obligation_id="OBL-B", obligation_type="TAX_LEG")
    assert genuine.obligation_id != forged.obligation_id
    assert genuine.idempotency_key == forged.idempotency_key
    assert genuine.canonical_digest != forged.canonical_digest
    assert _classify(forged, genuine) is RecordPairKind.DIVERGENT_EMISSION
    assert (
        obligation_commit_idempotent(forged, genuine, True)
        is ObligationCommitOutcome.REJECTED_CONFLICT
    )


def test_the_two_forgery_axes_are_distinct_kinds_folding_to_one_rejection() -> None:
    """(§4.6) Distinct canonical kinds, one contained rejection — no last-write-wins."""
    genuine = clean_obligation_record()
    primary_forgery = clean_obligation_record(obligation_type="TAX_LEG")
    key_forgery = clean_obligation_record(
        obligation_id="OBL-B", obligation_type="FEE_LEG"
    )
    assert _classify(primary_forgery, genuine) is not _classify(key_forgery, genuine)
    assert (
        obligation_commit_idempotent(primary_forgery, genuine, True)
        is obligation_commit_idempotent(key_forgery, genuine, True)
        is ObligationCommitOutcome.REJECTED_CONFLICT
    )


def test_distinct_prior_is_a_selection_contract_violation() -> None:
    """(row 4) A prior sharing neither axis is not the prior at all ⇒ fail closed."""
    incoming = clean_obligation_record(obligation_id="OBL-A", idempotency_key="IDEM-A")
    unrelated = clean_obligation_record(
        obligation_id="OBL-B", idempotency_key="IDEM-B", obligation_type="TAX_LEG"
    )
    assert _classify(incoming, unrelated) is RecordPairKind.DISTINCT
    assert (
        obligation_commit_idempotent(incoming, unrelated, True)
        is ObligationCommitOutcome.REJECTED_UNKNOWN
    )


def test_pre_issuance_prior_is_not_comparable() -> None:
    """(row 5) A null-digest DRAFT is not a ledger citizen ⇒ undecidable ⇒ fail closed."""
    incoming = clean_obligation_record()
    draft = EconomicObligationRecord(
        obligation_id="OBL-1", status=ArtifactStatus.DRAFT, idempotency_key="IDEM-1"
    )
    assert _classify(incoming, draft) is RecordPairKind.NOT_COMPARABLE
    assert (
        obligation_commit_idempotent(incoming, draft, True)
        is ObligationCommitOutcome.REJECTED_UNKNOWN
    )


# --- the late-fill effect count ----------------------------------------------


def _effect_count(outcomes: list[ObligationCommitOutcome]) -> int:
    """Count the outcomes that increase the obligation effect count (only ``COMMITTED_ONCE``)."""
    return sum(
        1 for outcome in outcomes if outcome is ObligationCommitOutcome.COMMITTED_ONCE
    )


@pytest.mark.parametrize("replays", [2, 3, 5])
def test_late_fill_replayed_n_times_yields_exactly_one_effect(replays: int) -> None:
    """(§12 line 347) A fill discovered after a claimed terminal outcome is harmless.

    The first application commits once; every re-application is an idempotent replay. The
    cumulative economic effect is exactly **1**, however many times the late fill arrives.
    """
    fill = clean_obligation_record()
    outcomes = [obligation_commit_idempotent(fill, None, True)]
    committed = fill
    for _ in range(replays - 1):
        outcomes.append(obligation_commit_idempotent(fill, committed, True))
    assert outcomes[0] is ObligationCommitOutcome.COMMITTED_ONCE
    assert all(
        outcome is ObligationCommitOutcome.IDEMPOTENT_REPLAY for outcome in outcomes[1:]
    )
    assert _effect_count(outcomes) == 1


def test_a_forged_late_fill_adds_no_effect() -> None:
    """(§4.6) A same-key / different-bytes late fill is contained, not double-committed."""
    genuine = clean_obligation_record()
    committed = obligation_commit_idempotent(genuine, None, True)
    forged = clean_obligation_record(obligation_id="OBL-B", obligation_type="TAX_LEG")
    rejected = obligation_commit_idempotent(forged, genuine, True)
    assert _effect_count([committed, rejected]) == 1


def test_two_genuinely_distinct_first_fills_each_commit_once() -> None:
    """(both-ways positive) Distinct series each get their own single commit."""
    first = clean_obligation_record(obligation_id="OBL-A", idempotency_key="IDEM-A")
    second = clean_obligation_record(obligation_id="OBL-B", idempotency_key="IDEM-B")
    outcomes = [
        obligation_commit_idempotent(first, None, True),
        obligation_commit_idempotent(second, None, True),
    ]
    assert _effect_count(outcomes) == 2
