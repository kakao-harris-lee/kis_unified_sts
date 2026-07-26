"""§2.2-1 / §3.2 — lifecycle orthogonality + the three append-only generation series.

The §4.5-B truth-table rows this module owns:

* **row 5** (generation N -> N+1 on a correction) — legitimate, monotone increase;
* **row 6** (generation N -> N-1) — a revert is blocked by the ``tos.ordering`` REUSE.

Plus the §10 line 303-310 no-collapse structure: the five orthostate-owned axes stay five
separate injected fields and the posttrade-owned ``lifecycle_state`` is a **sixth**
coordinate.

The order is REUSED from ``tos.ordering``, never re-authored (design #24 §3.2), and the
package is **clock-free**: two records from different series are ``AMBIGUOUS`` rather than
silently ordered by anything resembling a timestamp.
"""

from __future__ import annotations

import pytest
from tos.canonical import ArtifactStatus
from tos.ordering import Ordering
from tos.posttrade import (
    ORTHOGONAL_POST_TRADE_AXES,
    EconomicObligationRecord,
    PostTradeFinalityProof,
    StatementCoverageManifest,
    finality_proof_generation_append_only,
    finality_proof_generation_order,
    obligation_axes_not_collapsed,
    obligation_generation_append_only,
    obligation_generation_order,
    statement_manifest_generation_append_only,
    statement_manifest_generation_order,
)

from ._posttrade_strategies import (
    clean_finality_proof,
    clean_obligation_record,
    clean_statement_manifest,
)

# --- §10 line 303-310 orthogonality ------------------------------------------


def test_the_five_axes_stay_five_separate_fields() -> None:
    """(§10 line 303-310) The obligation lifecycle is a **sixth** coordinate."""
    assert obligation_axes_not_collapsed(clean_obligation_record()) is True


def test_an_absent_record_proves_no_orthogonality() -> None:
    """(fail-closed) Nothing to inspect ⇒ nothing proven."""
    assert obligation_axes_not_collapsed(None) is False


def test_each_axis_is_its_own_field_and_none_is_the_lifecycle_state() -> None:
    """(§10 line 303-310) No axis is fused with the posttrade-owned coordinate."""
    fields = set(EconomicObligationRecord.model_fields)
    assert "lifecycle_state" in fields
    for axis in ORTHOGONAL_POST_TRADE_AXES:
        assert axis in fields
        assert axis != "lifecycle_state"


def test_the_axes_carry_sibling_tokens_this_package_never_sets() -> None:
    """(sibling edge 0) The five axes are opaque strings, not imported sibling types.

    ``tos.posttrade`` cannot name orthostate's ``BrokerOrderState`` or rcl's
    ``CapacityState`` — it holds sibling edge 0 — so each axis is annotated ``str | None``
    and consumed, never set.
    """
    for axis in ORTHOGONAL_POST_TRADE_AXES:
        annotation = EconomicObligationRecord.model_fields[axis].annotation
        assert annotation == (str | None), f"{axis} is not an opaque injected token"


def test_a_record_can_carry_a_conflicting_combination_of_axes() -> None:
    """(§10 line 303-310) The state that must stay representable really is representable.

    "The obligation says ``SATISFIED_PENDING_FINALITY`` while the broker order state is
    ``UNKNOWN`` and the capacity is ``TRAPPED_CONSUMED``" — a fused single token could not
    express it, which is the ADR-002-005 §11 defect class this must not repeat.
    """
    from tos.posttrade import PostTradeObligationLifecycleState

    record = clean_obligation_record(
        lifecycle_state=PostTradeObligationLifecycleState.SATISFIED_PENDING_FINALITY,
        order_state="UNKNOWN",
        capacity_state="TRAPPED_CONSUMED",
        knowledge_state="UNKNOWN",
    )
    assert obligation_axes_not_collapsed(record) is True
    assert record.capacity_state == "TRAPPED_CONSUMED"


# --- §3.2 obligation generation series ---------------------------------------


def test_obligation_generations_order_within_one_series() -> None:
    """(§3.2 / §4.5-B row 5) A correction appends at the next generation."""
    earlier = clean_obligation_record(obligation_generation=1)
    later = clean_obligation_record(obligation_generation=2)
    assert obligation_generation_order(earlier, later) is Ordering.BEFORE
    assert obligation_generation_order(later, earlier) is Ordering.AFTER


def test_records_from_different_series_are_ambiguous_never_silently_ordered() -> None:
    """(§3.2) A wall clock never orders — and neither does a cross-series comparison."""
    first = clean_obligation_record(idempotency_key="IDEM-A", obligation_generation=1)
    second = clean_obligation_record(idempotency_key="IDEM-B", obligation_generation=2)
    assert obligation_generation_order(first, second) is Ordering.AMBIGUOUS


def test_a_missing_generation_is_ambiguous_not_an_assumed_precedence() -> None:
    """(fail-closed) An unordered record is not "earlier by default"."""
    concrete = clean_obligation_record(obligation_generation=1)
    unordered = EconomicObligationRecord(
        status=ArtifactStatus.DRAFT,
        idempotency_key="IDEM-1",
        obligation_generation=None,
    )
    assert obligation_generation_order(unordered, concrete) is Ordering.AMBIGUOUS


def test_an_increasing_obligation_sequence_is_append_only() -> None:
    """(positive side, §11 line 330) Strictly increasing generations are an append."""
    sequence = [clean_obligation_record(obligation_generation=n) for n in (1, 2, 3)]
    assert obligation_generation_append_only(sequence) is True


def test_a_reverting_obligation_sequence_is_not_append_only() -> None:
    """(§4.5-B row 6) A generation revert is blocked."""
    sequence = [clean_obligation_record(obligation_generation=n) for n in (1, 3, 2)]
    assert obligation_generation_append_only(sequence) is False


def test_a_repeated_generation_is_an_in_place_edit() -> None:
    """(§20 line 460) Two records at one generation are an overwrite, not an append."""
    sequence = [clean_obligation_record(obligation_generation=n) for n in (1, 1)]
    assert obligation_generation_append_only(sequence) is False


def test_an_absent_generation_fails_the_append_only_check() -> None:
    """(fail-closed) An unordered record cannot be **proven** append-only."""
    unordered = EconomicObligationRecord(
        status=ArtifactStatus.DRAFT,
        idempotency_key="IDEM-1",
        obligation_generation=None,
    )
    assert obligation_generation_append_only([unordered]) is False


@pytest.mark.parametrize("length", [0, 1])
def test_a_short_sequence_has_nothing_to_violate(length: int) -> None:
    """(boundary) Zero or one concrete record cannot break an ordering."""
    sequence = [clean_obligation_record(obligation_generation=1)][:length]
    assert obligation_generation_append_only(sequence) is True


# --- §3.2 finality-proof generation series -----------------------------------


def test_finality_proof_generations_order_and_append() -> None:
    """(§11 line 330) Superseding proofs form their own append-only series."""
    earlier = clean_finality_proof(bound_generation=1)
    later = clean_finality_proof(bound_generation=2)
    assert finality_proof_generation_order(earlier, later) is Ordering.BEFORE
    assert finality_proof_generation_append_only([earlier, later]) is True
    assert finality_proof_generation_append_only([later, earlier]) is False


def test_a_proof_series_with_an_absent_generation_fails_closed() -> None:
    """(fail-closed) A proof that never declared its generation cannot be ordered."""
    unbound = PostTradeFinalityProof(
        status=ArtifactStatus.DRAFT, idempotency_key="IDEM-P1", bound_generation=None
    )
    assert finality_proof_generation_append_only([unbound]) is False


def test_the_proof_series_advance_is_exactly_what_reopens_finality() -> None:
    """(§11 line 330 / PTF-INV-013) The append and the reopen are one event, two views."""
    from tos.posttrade import finality_proof_current

    original = clean_finality_proof(bound_generation=1)
    correction = clean_finality_proof(bound_generation=2)
    assert finality_proof_generation_append_only([original, correction]) is True
    # the same advance that makes the series append-only makes the earlier proof stale
    assert finality_proof_current(original, correction.bound_generation) is False
    assert finality_proof_current(correction, correction.bound_generation) is True


# --- §3.2 statement-manifest generation series -------------------------------


def test_statement_manifest_generations_order_and_append() -> None:
    """(§19 line 442) A restatement is an append at the next generation."""
    preliminary = clean_statement_manifest(manifest_generation=1)
    revised = clean_statement_manifest(manifest_generation=2)
    assert statement_manifest_generation_order(preliminary, revised) is Ordering.BEFORE
    assert statement_manifest_generation_append_only([preliminary, revised]) is True
    assert statement_manifest_generation_append_only([revised, preliminary]) is False


def test_a_manifest_series_with_an_absent_generation_fails_closed() -> None:
    """(fail-closed) An unordered manifest cannot be proven append-only."""
    unordered = StatementCoverageManifest(
        status=ArtifactStatus.DRAFT, idempotency_key="IDEM-M1", manifest_generation=None
    )
    assert statement_manifest_generation_append_only([unordered]) is False


def test_the_three_series_share_one_ordering_rule() -> None:
    """(§3.2) One helper serves all three, so the series cannot drift apart."""
    generations = (1, 2, 3)
    assert (
        obligation_generation_append_only(
            [clean_obligation_record(obligation_generation=n) for n in generations]
        )
        is finality_proof_generation_append_only(
            [clean_finality_proof(bound_generation=n) for n in generations]
        )
        is statement_manifest_generation_append_only(
            [clean_statement_manifest(manifest_generation=n) for n in generations]
        )
        is True
    )


def test_no_transition_predicate_exists() -> None:
    """(§2.2-1) Transition **validity** is not Phase-1 — nothing here sets or gates a state.

    Whether ``SATISFIED_PENDING_FINALITY -> FINALITY_PROVEN`` may occur depends on the rcl
    capacity state, the recon field confidence, the field-specific finality proof, and the
    statement coverage — all EV-L2/L3 runtime gates.
    """
    import tos.posttrade.state as posttrade_state

    for forbidden in (
        "transition_valid",
        "may_transition",
        "advance_lifecycle",
        "set_lifecycle_state",
        "close_obligation",
    ):
        assert not hasattr(posttrade_state, forbidden)
