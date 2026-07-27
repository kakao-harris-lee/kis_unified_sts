"""combined_set_no_permissive_union + gate_states_separated yolk 5 (design #26 §5.5/§7.2).

Both-ways canary. Two seals:

* the #22 MAJOR-1 no-permissive-union seal (member == applicable, order-independent) **with the v1.1
  MAJOR-1 explicit-empty exception** (ADR §13 line 364 "either an explicit empty Active Deviation Set
  or one complete canonical set"): applicable = ∅ + members = ∅ + is_complete = True is **valid** and
  rejecting it is a defect (the three ∅ directions are asserted explicitly below);
* the six-stage gate separation + the readiness ≠ authority all-false seal, with the §26 line 687
  six-stage anchor drift.

Regime tag: combined-set / gate predicate substrate only; WDR-EV-012 NOT_IMPLEMENTED
(EV-L1/3+Security); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import tos.wdr as w

from ._wdr_strategies import clean_active_set, clean_ladder

# --- 5.5a combined_set_no_permissive_union -----------------------------------


def test_nonempty_complete_matching_set_is_valid() -> None:
    """(§5.5a positive) member_decisions == applicable, is_complete, within envelope ⇒ valid."""
    aset = clean_active_set(member_decisions=("d1", "d2"))
    assert (
        w.combined_set_no_permissive_union(aset, frozenset({"d1", "d2"}), True) is True
    )


def test_explicit_empty_set_is_valid_v1_1() -> None:
    """(§5.5a v1.1 MAJOR-1 — ADR §13 line 364) applicable=∅ + members=∅ + is_complete=True ⇒ VALID.

    An explicit empty Active Deviation Set is the canonical representation of a no-deviation bundle;
    rejecting it is a defect (design #26 v1.1 MAJOR-1). This is the regression the mutation "revert
    explicit-empty to a rejection" must break.
    """
    aset = clean_active_set(member_decisions=())
    assert w.combined_set_no_permissive_union(aset, frozenset(), True) is True


def test_empty_members_with_applicable_is_omission_deny() -> None:
    """(§5.5a) members=∅ but applicable≠∅ ⇒ an applicable deviation is omitted ⇒ invalid."""
    aset = clean_active_set(member_decisions=())
    assert w.combined_set_no_permissive_union(aset, frozenset({"d1"}), True) is False


def test_applicable_empty_with_members_is_surplus_deny() -> None:
    """(§5.5a both-ways) applicable=∅ but members≠∅ ⇒ a surplus / conflicting member ⇒ invalid."""
    aset = clean_active_set(member_decisions=("d1",))
    assert w.combined_set_no_permissive_union(aset, frozenset(), True) is False


def test_none_set_denies() -> None:
    """(§5.5a ∅-seal / §13 line 364) Absence of the set ⇒ invalid."""
    assert w.combined_set_no_permissive_union(None, frozenset(), True) is False


def test_omitted_or_surplus_member_denies() -> None:
    """(§13 line 364) A missing applicable member OR an extra member ⇒ invalid (both-ways)."""
    aset = clean_active_set(member_decisions=("d1",))
    assert (
        w.combined_set_no_permissive_union(aset, frozenset({"d1", "d2"}), True) is False
    )
    aset2 = clean_active_set(member_decisions=("d1", "d2", "d3"))
    assert (
        w.combined_set_no_permissive_union(aset2, frozenset({"d1", "d2"}), True)
        is False
    )


def test_reconcile_is_order_independent() -> None:
    """(§4.4) The verdict is order-independent (member tuple permutation ⇒ same verdict)."""
    applicable = frozenset({"d1", "d2", "d3"})
    a = clean_active_set(member_decisions=("d1", "d2", "d3"))
    b = clean_active_set(member_decisions=("d3", "d1", "d2"))
    assert w.combined_set_no_permissive_union(
        a, applicable, True
    ) is w.combined_set_no_permissive_union(b, applicable, True)


def test_is_complete_positive_polarity() -> None:
    """(§13 line 364 / §4.3 positive) is_complete None / False ⇒ invalid config."""
    for bad in (None, False):
        aset = clean_active_set(member_decisions=("d1",), is_complete=bad)
        assert (
            w.combined_set_no_permissive_union(aset, frozenset({"d1"}), True) is False
        )


def test_envelope_verdict_positive_polarity() -> None:
    """(§13 item 3 / §4.3 positive) member_within_envelope None / False ⇒ deny (spg injected)."""
    aset = clean_active_set(member_decisions=("d1",))
    for bad in (None, False):
        assert w.combined_set_no_permissive_union(aset, frozenset({"d1"}), bad) is False


def test_omitted_deviation_invalidates_supporting() -> None:
    """(§13 line 364 supporting) omitted_deviation_invalidates: None set / mismatch ⇒ True."""
    assert w.omitted_deviation_invalidates(None, frozenset()) is True
    aset = clean_active_set(member_decisions=("d1",))
    assert w.omitted_deviation_invalidates(aset, frozenset({"d1"})) is False
    assert w.omitted_deviation_invalidates(aset, frozenset({"d1", "d2"})) is True


# --- 5.5b gate_states_separated ----------------------------------------------


def test_clean_ladder_separated() -> None:
    """(§5.5b positive) Every stage explicit + all-false authority ⇒ separated."""
    assert w.gate_states_separated(clean_ladder()) is True


def test_none_ladder_denies() -> None:
    """(§5.5b ∅-seal) A None ladder ⇒ deny."""
    assert w.gate_states_separated(None) is False


def test_inferred_stage_denies() -> None:
    """(§5.5b) A None (inferred / implied) stage ⇒ deny (no_status_implication)."""
    for stage in w.GateSeparationLadder.STAGE_FIELDS:
        ladder = clean_ladder(**{stage: None})
        assert w.gate_states_separated(ladder) is False, stage


def test_readiness_not_authority() -> None:
    """(§5.5b / WDR-INV-001) A ladder whose authority is not all-false ⇒ deny.

    Any ``True`` authority flag is unconstructable, so we assert the supporting predicate directly on a
    None input and a clean all-false input.
    """
    assert w.readiness_not_authority(None) is False
    assert w.readiness_not_authority(clean_ladder()) is True
    assert w.no_status_implication(None) is False
    assert w.no_status_implication(clean_ladder()) is True


def test_six_stage_anchor_drift() -> None:
    """(§7.2 drift / §26 line 687) STAGE_FIELDS == the ladder's bool stages == exactly 6 stages."""
    stage_fields = set(w.GateSeparationLadder.STAGE_FIELDS)
    model_fields = set(w.GateSeparationLadder.model_fields) - {"authority_effect"}
    assert (
        stage_fields == model_fields
    ), f"drift: stages={stage_fields} fields={model_fields}"
    assert len(w.GateSeparationLadder.STAGE_FIELDS) == 6
