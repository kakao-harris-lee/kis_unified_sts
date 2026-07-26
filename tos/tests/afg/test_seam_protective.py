"""MANDATED test-only seam cross-check: afg <-> protective (design #16 §3.4(d) / §6.4/§6.6).

afg does **not** import ``tos.protective`` at runtime (the §7.1 allowlist closure test
asserts its absence); this file imports **both** as a **test** to lock the three injected
protective seams and, above all, their **polarity**:

* ``is_reserved_guarantee`` (``predicates.py:129``) returns a ``bool``; afg normalizes it
  with ``is not True`` so an unproven reserve is **not** reserved;
* ``partition_lease_admissible`` (``predicates.py:460``) returns the **3-token**
  ``Admissibility`` StrEnum (``vocabulary.py:118/137``) — design #16 **M2** corrected the
  v1.0 mis-declaration of ``bool | None``. Every member is truthy, so afg's gate admits
  only ``ADMISSIBLE``; this file drives all three members **plus** ``None``;
* ``retry_admissible`` bounded-retry budget (``predicates.py:590-615``) — ``None`` / ``<=
  0`` means no retry, which afg's ``no_blind_retry`` mirrors.

It also locks the ``GuaranteeLevel`` token drift: afg carries afg-local coordinate constants
(it cannot import the enum), so the seam asserts the constants equal the real members —
including the M1 correction that the enum is ``GuaranteeLevel``, **not** a phantom
``ReserveGuaranteeLevel``.

Causal isolation: each polarity assertion fixes a valid baseline and flips one input.

A test-only cross-import is **not** a runtime package edge (design #16 §3.4(d)/§7.1).
"""

from __future__ import annotations

from tos.afg import (
    ADMISSIBILITY_ADMISSIBLE,
    RESERVED_GUARANTEE_TOKENS,
    no_blind_retry,
    partition_lease_exclusive,
    priority_is_not_reserve,
    reserve_exclusive,
)
from tos.protective import (
    Admissibility,
    GuaranteeLevel,
    ProtectiveActionKind,
    is_reserved_guarantee,
    partition_lease_admissible,
    retry_admissible,
)

from ._afg_strategies import reserve_claim

# ---------------------------------------------------------------------------
# GuaranteeLevel token parity (M1 — the phantom-name correction)
# ---------------------------------------------------------------------------


def test_guarantee_level_is_the_real_enum_name_not_a_phantom() -> None:
    """(M1) The reserve-classification enum is ``GuaranteeLevel``; the 5 members are exact."""
    assert {level.value for level in GuaranteeLevel} == {
        "PHYSICALLY_RESERVED",
        "LOGICALLY_RESERVED",
        "PRIORITIZED_ONLY",
        "BEST_EFFORT",
        "UNAVAILABLE",
    }


def test_afg_reserved_tokens_match_the_protective_enum() -> None:
    """(token drift lock) afg's local reserved-token set equals the two reserved members."""
    assert {
        GuaranteeLevel.PHYSICALLY_RESERVED.value,
        GuaranteeLevel.LOGICALLY_RESERVED.value,
    } == RESERVED_GUARANTEE_TOKENS


def test_priority_only_is_never_a_reservation_on_either_side() -> None:
    """(§16:372 / protective §3.1.4:144) PRIORITIZED_ONLY / BEST_EFFORT / UNAVAILABLE deny."""
    for level in (
        GuaranteeLevel.PRIORITIZED_ONLY,
        GuaranteeLevel.BEST_EFFORT,
        GuaranteeLevel.UNAVAILABLE,
    ):
        assert level.value not in RESERVED_GUARANTEE_TOKENS
        assert (
            priority_is_not_reserve(level.value, exclusive_capacity_present=True)
            is False
        )
    for level in (
        GuaranteeLevel.PHYSICALLY_RESERVED,
        GuaranteeLevel.LOGICALLY_RESERVED,
    ):
        assert (
            priority_is_not_reserve(level.value, exclusive_capacity_present=True)
            is True
        )


# ---------------------------------------------------------------------------
# is_reserved_guarantee -> reserve_exclusive (bool seam, `is not True` normalization)
# ---------------------------------------------------------------------------


def _reserve(is_reserved: bool | None) -> bool:
    return reserve_exclusive(
        reserve_claim(),
        is_reserved,
        normal_traffic_borrowed=False,
        normal_traffic_consumed=False,
        relabelled_as_normal=False,
        repay_reserve_later_claimed=False,
    )


def test_protective_none_declaration_produces_a_non_reserved_bool() -> None:
    """(seam) ``is_reserved_guarantee(None)`` is ``False``; afg refuses on that value."""
    produced = is_reserved_guarantee(None)
    assert produced is False
    assert _reserve(produced) is False


def test_afg_treats_an_unproven_reserve_as_not_reserved() -> None:
    """(truthy seal, ``is not True``) ``None`` / ``False`` both deny; only ``True`` passes."""
    assert _reserve(None) is False
    assert _reserve(False) is False
    assert _reserve(True) is True  # causal isolation: only this input changed


# ---------------------------------------------------------------------------
# partition_lease_admissible -> partition_lease_exclusive (M2: 3-token StrEnum)
# ---------------------------------------------------------------------------


def _lease(verdict: object) -> bool:
    return partition_lease_exclusive(
        verdict,  # type: ignore[arg-type]
        3,
        "cont-1",
        reference_continuity_id="cont-1",
        new_normal_permit_during_partition=False,
        lease_refilled_remotely_or_by_wall_clock=False,
        exclusivity_retained=True,
        stale_writer_hard_fenced=True,
    )


def test_partition_lease_admissible_returns_the_admissibility_strenum_not_a_bool() -> (
    None
):
    """(M2) The protective predicate returns ``Admissibility`` — **not** ``bool | None``."""
    verdict = partition_lease_admissible(
        ProtectiveActionKind.OVERLAP_FIRST_ADD_ONLY,
        None,
        within_pre_proven_scope=None,
        staleness_ok=None,
        lease_valid_for_new_transmission=None,
        partition_new_commitment_denied=None,
    )
    assert isinstance(verdict, Admissibility)
    assert not isinstance(verdict, bool)


def test_all_three_admissibility_tokens_plus_none_have_the_right_polarity() -> None:
    """(M2 exhaustive polarity) Only ADMISSIBLE passes — TRAPPED / PROHIBITED / None deny."""
    assert _lease(Admissibility.ADMISSIBLE) is True
    assert _lease(Admissibility.TRAPPED) is False
    assert _lease(Admissibility.PROHIBITED) is False
    assert _lease(None) is False
    # ...and every non-admissible token is nonetheless *truthy*, which is exactly why a
    # bare truthiness gate would be a fail-open defect.
    assert bool(Admissibility.TRAPPED) is True
    assert bool(Admissibility.PROHIBITED) is True


def test_afg_admissible_constant_equals_the_protective_member() -> None:
    """(token drift lock) afg's local ``ADMISSIBILITY_ADMISSIBLE`` is the real member value."""
    assert Admissibility.ADMISSIBLE.value == ADMISSIBILITY_ADMISSIBLE


def test_prohibited_verdict_from_the_real_predicate_denies_the_afg_lease() -> None:
    """(seam, end-to-end polarity) A protective ``PROHIBITED`` verdict denies the afg gate."""
    verdict = partition_lease_admissible(
        ProtectiveActionKind.OVERLAP_FIRST_ADD_ONLY,
        None,
        within_pre_proven_scope=True,
        staleness_ok=True,
        lease_valid_for_new_transmission=False,  # no valid lease => PROHIBITED
        partition_new_commitment_denied=True,
    )
    assert verdict is Admissibility.PROHIBITED
    assert _lease(verdict) is False


# ---------------------------------------------------------------------------
# bounded-retry budget -> no_blind_retry (int | None seam)
# ---------------------------------------------------------------------------


def _retry(budget: int | None) -> bool:
    return no_blind_retry(
        "SEND_FAILED_PROVEN",
        "NONE_OBSERVED",
        True,
        budget,
        complete_evidence_capability_coverage_authority=True,
        blind_failover_attempted=False,
    )


def test_protective_retry_budget_polarity_matches_afg() -> None:
    """(seam) protective refuses a ``None`` / exhausted budget; afg refuses on the same values."""
    for budget in (None, 0, -1):
        assert (
            retry_admissible(
                budget_remaining=budget,
                duplicate_economic_effect_possible=False,
                unknown_outcome=False,
                dedup_proven=True,
            )
            is False
        )
        assert _retry(budget) is False
    # Causal isolation: only the budget changes and both sides flip together.
    assert (
        retry_admissible(
            budget_remaining=1,
            duplicate_economic_effect_possible=False,
            unknown_outcome=False,
            dedup_proven=True,
        )
        is True
    )
    assert _retry(1) is True
