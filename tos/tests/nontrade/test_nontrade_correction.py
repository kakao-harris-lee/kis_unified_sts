"""§5.3/§4.6 correction / reversal idempotency + lineage (NT-EV-010 substrate).

*Discipline tag: predicate / coordinate substrate only. NT-EV-010 is ``EV-L1/3`` — this
authors the L1 slice and closes **nothing**; the ``/3`` integration-fault and adversarial
replay evidence and the independent review remain outstanding. No EV-L1-complete claim.*

This is the series' **first idempotency-centred L1 slice**, so the two properties the
design singles out are asserted directly:

* the **double-application canary** — applying one correction N >= 2 times leaves the
  cumulative economic effect count at exactly **1**;
* the **two forgery axes**, kept separate — a same **primary** id / different-bytes pair is
  a ``CRITICAL_CONFLICT`` and a same **idempotency key** / different-bytes pair is a
  ``DIVERGENT_EMISSION``. Both fold to ``REJECTED_CONFLICT``, both records survive, and
  neither is ever silently double-applied.

The v1.0 defects this file regresses against are (a) an inverted kind mapping and (b) a
structurally unreachable ``APPLIED_ONCE`` (a first correction routed into
``classify_record_pair`` returns ``NOT_COMPARABLE`` and would have been rejected forever).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.canonical import RecordPairKind
from tos.nontrade import CorrectionReversalOutcome, correction_reversal_idempotent
from tos.nontrade.predicates import _RECORD_PAIR_OUTCOME

from ._nontrade_strategies import TRUTHY_NON_BOOL, issue_correction

# ---------------------------------------------------------------------------
# The exhaustive RecordPairKind mapping (§4.6 / C2)
# ---------------------------------------------------------------------------


def test_the_record_pair_mapping_covers_every_canonical_member() -> None:
    """(C2) All **five** ``RecordPairKind`` members are bound — no silent fall-through.

    A future canonical member would make this fail rather than land on a permissive
    default, which is precisely the v1.0 gap (``DIVERGENT_EMISSION`` was unmapped).
    """
    assert set(_RECORD_PAIR_OUTCOME) == set(RecordPairKind)
    assert len(_RECORD_PAIR_OUTCOME) == 5


def test_the_mapping_directions_are_the_measured_ones() -> None:
    """(C2 inversion regression) Each kind maps to the outcome the ADR / canonical pins."""
    assert (
        _RECORD_PAIR_OUTCOME[RecordPairKind.IDEMPOTENT_DUP]
        is CorrectionReversalOutcome.IDEMPOTENT_REPLAY
    )
    assert (
        _RECORD_PAIR_OUTCOME[RecordPairKind.CRITICAL_CONFLICT]
        is CorrectionReversalOutcome.REJECTED_CONFLICT
    )
    assert (
        _RECORD_PAIR_OUTCOME[RecordPairKind.DIVERGENT_EMISSION]
        is CorrectionReversalOutcome.REJECTED_CONFLICT
    )
    assert (
        _RECORD_PAIR_OUTCOME[RecordPairKind.DISTINCT]
        is CorrectionReversalOutcome.REJECTED_UNKNOWN
    )
    assert (
        _RECORD_PAIR_OUTCOME[RecordPairKind.NOT_COMPARABLE]
        is CorrectionReversalOutcome.REJECTED_UNKNOWN
    )
    # the two forgery axes are DIFFERENT canonical kinds that fold to ONE rejection
    assert RecordPairKind.CRITICAL_CONFLICT is not RecordPairKind.DIVERGENT_EMISSION


def test_no_record_pair_kind_maps_to_applied_once() -> None:
    """(C2) ``APPLIED_ONCE`` is reachable **only** through the ``prior is None`` pre-gate.

    If a classify branch could yield it, a forged pair could be applied as a fresh effect.
    """
    assert CorrectionReversalOutcome.APPLIED_ONCE not in set(
        _RECORD_PAIR_OUTCOME.values()
    )


# ---------------------------------------------------------------------------
# Pre-gates, in order (§4.6)
# ---------------------------------------------------------------------------


def test_no_incoming_record_is_undecidable() -> None:
    """(fail-closed) Nothing to decide ⇒ ``REJECTED_UNKNOWN``."""
    assert (
        correction_reversal_idempotent(None, None, True)
        is CorrectionReversalOutcome.REJECTED_UNKNOWN
    )


def test_a_missing_supersedes_ref_is_rejected_no_lineage() -> None:
    """(§16 line 311 / §4.7 row 7) No relabelling an unexplained change as a correction."""
    lineage_less = issue_correction(supersedes_ref=None)
    assert (
        correction_reversal_idempotent(lineage_less, None, True)
        is CorrectionReversalOutcome.REJECTED_NO_LINEAGE
    )


def test_the_lineage_gate_precedes_the_retention_gate() -> None:
    """(§4.6 order) A lineage-less **and** overwritten record reports the lineage failure.

    The order is load-bearing: a caller told "no lineage" fixes the linkage, whereas one
    told "overwrite" might merely flip a flag.
    """
    lineage_less = issue_correction(supersedes_ref=None)
    assert (
        correction_reversal_idempotent(lineage_less, None, False)
        is CorrectionReversalOutcome.REJECTED_NO_LINEAGE
    )


@pytest.mark.parametrize("retained", [False, None, *TRUTHY_NON_BOOL])
def test_anything_but_singleton_true_retention_is_rejected_overwrite(
    retained: object,
) -> None:
    """(§10 line 219) ``original_retained`` is **positive polarity**: only ``True`` passes.

    ``None`` (unknown) and every truthy non-``bool`` are rejected, so an ``is not True``
    reading — which would have cleared ``1`` / ``"yes"`` / ``[1]`` — cannot creep in.
    """
    record = issue_correction()
    assert (
        correction_reversal_idempotent(record, None, retained)  # type: ignore[arg-type]
        is CorrectionReversalOutcome.REJECTED_OVERWRITE
    )


def test_the_first_correction_is_applied_once() -> None:
    """(C2 pre-gate) ``prior is None`` ⇒ ``APPLIED_ONCE``, never ``NOT_COMPARABLE``.

    Without this pre-gate every legitimate first correction would be routed into
    ``classify_record_pair`` against a ``None`` prior and rejected forever — the v1.0
    "structurally unreachable ``APPLIED_ONCE``" defect.
    """
    assert (
        correction_reversal_idempotent(issue_correction(), None, True)
        is CorrectionReversalOutcome.APPLIED_ONCE
    )


def test_distinct_legitimate_first_corrections_each_apply_once() -> None:
    """(availability side) Two unrelated corrections are both legitimately applied."""
    for correction_id in ("nt-corr-a", "nt-corr-b"):
        record = issue_correction(
            correction_id=correction_id, idempotency_key=f"idem-{correction_id}"
        )
        assert (
            correction_reversal_idempotent(record, None, True)
            is CorrectionReversalOutcome.APPLIED_ONCE
        )


# ---------------------------------------------------------------------------
# The §4.6 truth table, cell by cell
# ---------------------------------------------------------------------------


def test_same_record_reapplied_is_an_idempotent_replay() -> None:
    """(§4.6 row 1) Same id, same bytes ⇒ ``IDEMPOTENT_DUP`` ⇒ ``IDEMPOTENT_REPLAY``."""
    incoming = issue_correction()
    prior = issue_correction()
    assert incoming.canonical_digest == prior.canonical_digest
    assert (
        correction_reversal_idempotent(incoming, prior, True)
        is CorrectionReversalOutcome.IDEMPOTENT_REPLAY
    )


def test_same_primary_id_different_bytes_is_rejected_conflict() -> None:
    """(§4.6 row 2 / §4.7 row 8) Record forgery ⇒ ``CRITICAL_CONFLICT`` ⇒ conflict."""
    incoming = issue_correction()
    forged = issue_correction(correction_kind="REVERSAL")
    assert incoming.correction_id == forged.correction_id
    assert incoming.canonical_digest != forged.canonical_digest
    assert (
        correction_reversal_idempotent(incoming, forged, True)
        is CorrectionReversalOutcome.REJECTED_CONFLICT
    )


def test_same_idempotency_key_different_bytes_is_rejected_conflict() -> None:
    """(§4.6 row 3 / §4.7 row 9) Divergent emission ⇒ ``DIVERGENT_EMISSION`` ⇒ conflict."""
    incoming = issue_correction(correction_id="nt-corr-a")
    other = issue_correction(correction_id="nt-corr-b", correction_kind="REVERSAL")
    assert incoming.correction_id != other.correction_id
    assert incoming.idempotency_key == other.idempotency_key
    assert incoming.canonical_digest != other.canonical_digest
    assert (
        correction_reversal_idempotent(incoming, other, True)
        is CorrectionReversalOutcome.REJECTED_CONFLICT
    )


def test_the_two_forgery_axes_are_separately_reachable() -> None:
    """(C2) Both axes really are exercised — one fixture cannot stand in for the other.

    The pair that produces ``CRITICAL_CONFLICT`` shares the primary id; the pair that
    produces ``DIVERGENT_EMISSION`` shares only the idempotency key. Conflating them was
    the v1.0 inversion.
    """
    same_id_a = issue_correction()
    same_id_b = issue_correction(correction_kind="REVERSAL")
    same_key_a = issue_correction(correction_id="nt-corr-a")
    same_key_b = issue_correction(correction_id="nt-corr-b", correction_kind="REVERSAL")
    assert same_id_a.correction_id == same_id_b.correction_id
    assert same_key_a.correction_id != same_key_b.correction_id
    assert same_key_a.idempotency_key == same_key_b.idempotency_key
    for pair in ((same_id_a, same_id_b), (same_key_a, same_key_b)):
        assert (
            correction_reversal_idempotent(pair[0], pair[1], True)
            is CorrectionReversalOutcome.REJECTED_CONFLICT
        )


def test_a_prior_sharing_neither_identity_axis_is_undecidable() -> None:
    """(§4.6 row 4 / §4.7 row 10) ``DISTINCT`` is a caller contract violation ⇒ UNKNOWN."""
    incoming = issue_correction(correction_id="nt-corr-a", idempotency_key="idem-a")
    unrelated = issue_correction(correction_id="nt-corr-b", idempotency_key="idem-b")
    assert (
        correction_reversal_idempotent(incoming, unrelated, True)
        is CorrectionReversalOutcome.REJECTED_UNKNOWN
    )


def test_a_pre_issuance_prior_is_undecidable() -> None:
    """(§4.6 row 5 / §4.7 row 10) A null digest is not a ledger citizen ⇒ UNKNOWN."""
    incoming = issue_correction()
    draft = issue_correction().model_copy(update={"canonical_digest": None})
    assert draft.canonical_digest is None
    assert (
        correction_reversal_idempotent(incoming, draft, True)
        is CorrectionReversalOutcome.REJECTED_UNKNOWN
    )


# ---------------------------------------------------------------------------
# The double-application canary (§4.6 / §7)
# ---------------------------------------------------------------------------


def _apply(times: int) -> tuple[int, list[CorrectionReversalOutcome]]:
    """Apply one correction ``times`` times against an accumulating ledger.

    Only ``APPLIED_ONCE`` increases the economic effect count — the definition of
    "reapplication is harmless" (§19 line 366 idempotent version checks).
    """
    effect_count = 0
    outcomes: list[CorrectionReversalOutcome] = []
    prior = None
    for _ in range(times):
        incoming = issue_correction()
        outcome = correction_reversal_idempotent(incoming, prior, True)
        outcomes.append(outcome)
        if outcome is CorrectionReversalOutcome.APPLIED_ONCE:
            effect_count += 1
            prior = incoming
    return effect_count, outcomes


@given(st.integers(min_value=2, max_value=8))
def test_reapplying_one_correction_n_times_yields_exactly_one_effect(n: int) -> None:
    """(§4.6 double-application canary) N >= 2 applications ⇒ cumulative effect count == 1."""
    effect_count, outcomes = _apply(n)
    assert effect_count == 1
    assert outcomes[0] is CorrectionReversalOutcome.APPLIED_ONCE
    assert all(
        outcome is CorrectionReversalOutcome.IDEMPOTENT_REPLAY
        for outcome in outcomes[1:]
    )


def test_a_forged_reapplication_adds_no_effect_either() -> None:
    """(§4.6) The conflict path is ``+0`` too — a rejection never double-applies."""
    first = issue_correction()
    assert (
        correction_reversal_idempotent(first, None, True)
        is CorrectionReversalOutcome.APPLIED_ONCE
    )
    forged = issue_correction(correction_kind="REVERSAL")
    outcome = correction_reversal_idempotent(forged, first, True)
    assert outcome is CorrectionReversalOutcome.REJECTED_CONFLICT
    # both observations survive: neither record was mutated or dropped
    assert first.canonical_digest is not None
    assert forged.canonical_digest is not None
    assert first.canonical_digest != forged.canonical_digest


def test_the_outcome_is_never_truthy_tested_by_a_consumer() -> None:
    """(§4) Every rejection is truthy as a string — the gate must be identity."""
    outcome = correction_reversal_idempotent(
        issue_correction(supersedes_ref=None), None, True
    )
    with pytest.raises(TypeError):
        bool(outcome)
    assert outcome is CorrectionReversalOutcome.REJECTED_NO_LINEAGE
