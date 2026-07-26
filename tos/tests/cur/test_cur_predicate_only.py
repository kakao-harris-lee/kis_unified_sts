"""Predicate-only §6 substrate + not-Phase-1 §6b thin models (design #23 §6/§6b).

The predicate-only substrate closes **no** CUR-EV (each row is ≥ EV-L2 + +Security/+Broker, and the
not-Phase-1 rows 005/006 are EV-L3+Security runtime). These tests exercise the L1-decidable structural
/ coordinate substrate: floor met, fence advance, malformed-model re-check, parent/child monotone,
expiry / unknown / recovery / protective-label / broker-reachable rejections, and the thin race /
partition model.

Regime tag: predicate substrate only; CUR-EV-002/003/004/008/010/011/012 NOT_IMPLEMENTED (≥ EV-L2 +
+Security/+Broker); CUR-EV-005/006 not-Phase-1 (EV-L3+Security runtime); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.cur import (
    RestrictiveFenceRecord,
    all_floors_met,
    broker_reachable_not_authority,
    expiry_denies_future_use_only,
    fence_advances_floor,
    floor_strictly_advances,
    parent_child_floor_monotone,
    proof_structurally_complete,
    protective_label_not_authority,
    race_order_admissible,
    unknown_preserves_capacity,
)

from ._cur_strategies import (
    clean_dimension,
    clean_dimensions,
    clean_fence,
    clean_revision,
)

# ---------------------------------------------------------------------------
# §6.1 all_floors_met
# ---------------------------------------------------------------------------


def test_all_floors_met_both_ways() -> None:
    """(§6.1) Every dimension meeting its floor passes; a below-floor / None / ∅ fails."""
    rev = clean_revision()
    assert all_floors_met(clean_dimensions(revision=rev)) is True
    assert all_floors_met([]) is False
    below = clean_dimension(
        dimension_key=next(iter(clean_dimensions(revision=rev))).dimension_key,
        revision=rev,
        bound_generation=1,
        restrictive_floor=9,  # generation below floor ⇒ stale
    )
    assert all_floors_met([below]) is False


def test_all_floors_met_equal_generation_is_met() -> None:
    """(§6.1 / §0.4e) The equal case is MET (direct >= shape, not strict compare_order BEFORE)."""
    rev = clean_revision()
    equal = clean_dimension(
        dimension_key=next(iter(clean_dimensions(revision=rev))).dimension_key,
        revision=rev,
        bound_generation=4,
        restrictive_floor=4,
    )
    assert all_floors_met([equal]) is True


# ---------------------------------------------------------------------------
# §6.4 fence_advances_floor + floor_strictly_advances (ordering REUSE)
# ---------------------------------------------------------------------------


def test_fence_advances_floor_both_ways() -> None:
    """(§6.4) A monotonically advancing fence passes; a non-advancing / None fails; terminal passes."""
    assert (
        fence_advances_floor(clean_fence(predecessor_floor=3, advanced_floor=7)) is True
    )
    assert (
        fence_advances_floor(clean_fence(predecessor_floor=7, advanced_floor=7))
        is False
    )  # equal
    assert (
        fence_advances_floor(clean_fence(predecessor_floor=7, advanced_floor=3))
        is False
    )  # regress
    assert fence_advances_floor(None) is False
    # a terminal denial fence is admissible regardless of the floor delta.
    assert (
        fence_advances_floor(
            clean_fence(predecessor_floor=7, advanced_floor=3, terminal_denial=True)
        )
        is True
    )


def test_floor_strictly_advances_reuses_ordering() -> None:
    """(§3.2/§6.4) floor_strictly_advances is strict-BEFORE (equal fails); None fails closed."""
    assert floor_strictly_advances(3, 7) is True
    assert floor_strictly_advances(7, 7) is False
    assert floor_strictly_advances(7, 3) is False
    assert floor_strictly_advances(None, 7) is False
    assert floor_strictly_advances(3, None) is False


def test_fence_none_floor_regresses_but_terminal_still_holds() -> None:
    """(§6.4 fail-closed) A None floor with no terminal flag ⇒ False; terminal alone still holds."""
    assert (
        fence_advances_floor(clean_fence(predecessor_floor=None, advanced_floor=7))
        is False
    )
    assert (
        fence_advances_floor(
            clean_fence(
                predecessor_floor=None, advanced_floor=None, terminal_denial=True
            )
        )
        is True
    )


# ---------------------------------------------------------------------------
# §6.5 malformed-model re-check (model_construct bypass)
# ---------------------------------------------------------------------------


def test_proof_structural_completeness_catches_model_construct_bypass() -> None:
    """(§2.3/§6.5) A model_construct proof with a None required field is caught by the predicate."""
    from tos.cur import EgressCurrentnessProof

    # model_construct skips the validator; a None nonce would otherwise be smuggled past.
    smuggled = EgressCurrentnessProof.model_construct(
        proof_id="p",
        nonce=None,
        vector_id="v",
        vector_digest="d",
        committed_revision=None,
    )
    assert proof_structurally_complete(smuggled) is False


# ---------------------------------------------------------------------------
# §6.8 parent/child floor monotone
# ---------------------------------------------------------------------------


def test_parent_child_floor_monotone_both_ways() -> None:
    """(§6.8) child >= parent floor passes; a stale child / None fails."""
    assert parent_child_floor_monotone(5, 5) is True
    assert parent_child_floor_monotone(6, 5) is True
    assert (
        parent_child_floor_monotone(4, 5) is False
    )  # child stale after parent floor advance
    assert parent_child_floor_monotone(None, 5) is False
    assert parent_child_floor_monotone(5, None) is False


# ---------------------------------------------------------------------------
# §6.9-6.11 protective label / expiry / unknown-capacity
# ---------------------------------------------------------------------------


def test_protective_label_is_never_authority() -> None:
    """(§6.9 / §17 line 393) A protective label is never currentness authority (unconditional False)."""
    assert protective_label_not_authority("EMERGENCY_EXIT") is False
    assert protective_label_not_authority(None) is False


def test_expiry_denies_future_use_only() -> None:
    """(§6.10) is_expired True / None ⇒ deny future use; explicit False ⇒ allow (capacity unchanged)."""
    assert expiry_denies_future_use_only(True) is True
    assert (
        expiry_denies_future_use_only(None) is True
    )  # negative polarity — None is denial
    assert expiry_denies_future_use_only(False) is False


def test_unknown_preserves_capacity() -> None:
    """(§6.11 / CUR-INV-011) Unknown currentness preserves the worst-credible obligation; known ⇒ None."""
    # currentness not known (None / False) ⇒ preserve the worst credible capacity obligation.
    assert unknown_preserves_capacity(None, 100) == 100
    assert unknown_preserves_capacity(False, 100) == 100
    # currentness positively known ⇒ no unknown-preservation obligation asserted here.
    assert unknown_preserves_capacity(True, 100) is None


# ---------------------------------------------------------------------------
# §6b not-Phase-1 thin models (close NO CUR-EV)
# ---------------------------------------------------------------------------


def test_race_order_admissible_thin_model() -> None:
    """(§6b / CUR-EV-005) claim-before-fence AND no-fence-before-first-byte admits; None ⇒ deny."""
    assert race_order_admissible(True, False) is True
    assert race_order_admissible(False, False) is False  # fence before claim
    assert race_order_admissible(True, True) is False  # fence before first byte
    assert race_order_admissible(None, False) is False  # unknown order ⇒ deny
    assert race_order_admissible(True, None) is False  # unknown order ⇒ deny


def test_broker_reachable_is_never_authority() -> None:
    """(§6b / CUR-EV-006 / §15 line 358) Broker reachability is never send authority (unconditional False)."""
    assert broker_reachable_not_authority(True) is False
    assert broker_reachable_not_authority(None) is False


def test_fence_record_is_digest_bound() -> None:
    """(§2.1) The RestrictiveFenceRecord is a digest-verified issued citizen (affected_scope sorted)."""
    fence = clean_fence(affected_scope=frozenset({"z", "a", "m"}))
    assert fence.canonical_digest is not None
    assert isinstance(fence, RestrictiveFenceRecord)
    # the frozenset is intact for the §6.3 union math.
    assert fence.affected_scope == frozenset({"a", "m", "z"})
