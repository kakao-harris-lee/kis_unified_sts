"""core §5.2 — bounded amplification + complete cause lineage (AFG-EV-002 substrate).

ADR-002-022 §11 line 284-296; AFG-INV-002; §5.8 line 141 "unknown or unbounded
amplification is denial". Both-ways canaries on every guard (design #16 §4.2/§4.7):
the forbidden direction (bound exceeded, lineage missing / cyclic, duplicate minting a new
allowance) **and** the permitted direction (every count within bound + a complete attested
lineage passes).

Closes **no** AFG-EV: predicate / coordinate substrate only (design #16 §1).
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from tos.afg import (
    ActionAmplificationEnvelope,
    ActionCause,
    ObservedAmplification,
    amplification_bounded,
    cause_lineage_complete,
    changed_command_is_new_action,
)

from ._afg_strategies import clean_cause, full_envelope, within_observation

_INT_AXES = (
    ("max_fan_out", "fan_out"),
    ("max_depth", "depth"),
    ("max_attempts", "attempts"),
    ("max_mutations", "mutations"),
    ("max_queries", "queries"),
    ("max_queue_depth", "queue_depth"),
    ("max_in_flight", "in_flight"),
    ("max_duplicate_redelivery_expansion", "duplicate_redelivery_expansion"),
    (
        "max_failover_reconnect_replay_expansion",
        "failover_reconnect_replay_expansion",
    ),
)


# ---------------------------------------------------------------------------
# amplification_bounded (§11 line 284-296; §5.8 line 141)
# ---------------------------------------------------------------------------


def test_the_governed_axis_list_is_non_empty_and_covers_every_envelope_field() -> None:
    """(anti-vacuity) The axis table is not empty and leaves no envelope bound unchecked.

    An empty (or partial) axis table would make :func:`amplification_bounded` a vacuous
    ``True`` for the unlisted axes — exactly the "empty required set" fail-open class. The
    table must therefore cover **every** declared envelope field and every observation
    field except the three §11 line 294 boolean witnesses.
    """
    from tos.afg.predicates import _AMPLIFICATION_AXES

    assert _AMPLIFICATION_AXES, "the amplification axis table must not be empty"
    bounds = {bound for bound, _ in _AMPLIFICATION_AXES}
    observations = {observed for _, observed in _AMPLIFICATION_AXES}
    assert bounds == set(ActionAmplificationEnvelope.model_fields)
    witness_fields = {
        "duplicate_event_created_new_allowance",
        "envelope_reset_on_duplicate",
        "concurrent_consumers_share_one_envelope",
    }
    assert observations == set(ObservedAmplification.model_fields) - witness_fields


def test_every_count_within_a_fully_declared_envelope_passes() -> None:
    """(canary + §5.2) All counts <= their injected bound + §11:294 witnesses => True."""
    assert amplification_bounded(full_envelope(), within_observation()) is True


def test_exceeding_any_integer_axis_is_denial() -> None:
    """(canary - §11:284-292) Exceeding **any** axis bound => False (each axis checked)."""
    for bound_field, observed_field in _INT_AXES:
        bound = getattr(full_envelope(), bound_field)
        observed = within_observation(**{observed_field: bound + 1})
        assert (
            amplification_bounded(full_envelope(), observed) is False
        ), f"exceeding {observed_field} must deny"


def test_exceeding_a_decimal_axis_is_denial() -> None:
    """(canary -) Elapsed monotonic / per-cause amplification above bound => False."""
    assert (
        amplification_bounded(
            full_envelope(),
            within_observation(elapsed_monotonic=Decimal("1000.01")),
        )
        is False
    )
    assert (
        amplification_bounded(
            full_envelope(),
            within_observation(amplification_per_cause=Decimal("8.01")),
        )
        is False
    )


def test_empty_envelope_is_denial() -> None:
    """(∅ §4.7 row 4) A bare envelope declares no bound => unbounded => denial (§5.8:141)."""
    assert (
        amplification_bounded(ActionAmplificationEnvelope(), within_observation())
        is False
    )
    assert ActionAmplificationEnvelope().declares_every_bound() is False
    assert full_envelope().declares_every_bound() is True


def test_a_single_undeclared_axis_is_denial() -> None:
    """(∅ §4.7 row 4) One ``None`` bound leaves that axis unbounded => denial."""
    for bound_field, _ in _INT_AXES:
        envelope = full_envelope(**{bound_field: None})
        assert amplification_bounded(envelope, within_observation()) is False


def test_unknown_observation_is_denial() -> None:
    """(fail-closed) A ``None`` observed count is UNKNOWN => denial, never assume-zero."""
    for _, observed_field in _INT_AXES:
        observed = within_observation(**{observed_field: None})
        assert amplification_bounded(full_envelope(), observed) is False


def test_none_envelope_or_observation_fails_closed() -> None:
    """(fail-closed) A ``None`` envelope or observation => False."""
    assert amplification_bounded(None, within_observation()) is False
    assert amplification_bounded(full_envelope(), None) is False
    assert amplification_bounded(None, None) is False


def test_duplicate_event_may_not_create_a_new_allowance() -> None:
    """(canary - §11:294) A duplicate event creating another allowance => False."""
    for value in (True, None):
        assert (
            amplification_bounded(
                full_envelope(),
                within_observation(duplicate_event_created_new_allowance=value),
            )
            is False
        )


def test_duplicate_may_not_reset_the_envelope() -> None:
    """(canary - §11:294) An envelope reset on a duplicate observation => False."""
    for value in (True, None):
        assert (
            amplification_bounded(
                full_envelope(),
                within_observation(envelope_reset_on_duplicate=value),
            )
            is False
        )


def test_concurrent_consumers_must_share_one_envelope() -> None:
    """(canary - §11:294) Concurrent consumers not sharing one envelope => False."""
    for value in (False, None):
        assert (
            amplification_bounded(
                full_envelope(),
                within_observation(concurrent_consumers_share_one_envelope=value),
            )
            is False
        )


@given(fan_out=st.integers(min_value=0, max_value=20))
def test_amplification_is_monotone_in_the_fan_out_axis(fan_out: int) -> None:
    """(property) The verdict follows ``observed <= bound`` exactly on the fan-out axis."""
    envelope = full_envelope()
    verdict = amplification_bounded(envelope, within_observation(fan_out=fan_out))
    assert verdict is (fan_out <= envelope.max_fan_out)


# ---------------------------------------------------------------------------
# cause_lineage_complete (§11 line 284 / 296)
# ---------------------------------------------------------------------------


def test_complete_attested_lineage_passes() -> None:
    """(canary + §5.2) Root identity + non-empty attested lineage + no defects => True."""
    assert cause_lineage_complete(clean_cause()) is True


def test_none_cause_fails_closed() -> None:
    """(fail-closed) A ``None`` cause proves nothing => False."""
    assert cause_lineage_complete(None) is False


def test_empty_lineage_is_not_completeness() -> None:
    """(∅ §4.7 row 5) An empty parent lineage is UNKNOWN, never "no parents therefore done"."""
    assert cause_lineage_complete(clean_cause(parent_lineage=())) is False


def test_bare_cause_fails_closed() -> None:
    """(∅) A bare :class:`ActionCause` (every field defaulted) => False."""
    assert cause_lineage_complete(ActionCause()) is False


def test_missing_root_identity_fails_closed() -> None:
    """(canary - §11:284) A missing / "TBD" root-cause identity => False."""
    assert cause_lineage_complete(clean_cause(root_cause_identity=None)) is False
    assert cause_lineage_complete(clean_cause(root_cause_identity="TBD")) is False


def test_unattested_lineage_fails_closed() -> None:
    """(fail-closed) Completeness must be positively attested; ``None`` / ``False`` => False."""
    for value in (False, None):
        assert cause_lineage_complete(clean_cause(lineage_attested=value)) is False


def test_cyclic_forked_or_inconsistent_lineage_is_contained() -> None:
    """(canary - §11:296) Cyclic / forked-beyond-bound / inconsistent lineage => False."""
    for field in ("cyclic", "forked_beyond_bound", "inconsistent"):
        for value in (True, None):
            assert cause_lineage_complete(clean_cause(**{field: value})) is False


# ---------------------------------------------------------------------------
# changed_command_is_new_action (§11 line 294; AFG-AC-002)
# ---------------------------------------------------------------------------


def test_unchanged_command_needs_no_fresh_artifacts() -> None:
    """(canary +) A positively unchanged command => True (nothing to re-derive)."""
    assert (
        changed_command_is_new_action(
            command_changed=False, fresh_cause_and_artifacts=None
        )
        is True
    )


def test_changed_command_requires_fresh_cause_and_artifacts() -> None:
    """(canary + §11:294) A changed command with fresh cause + artifacts => True."""
    assert (
        changed_command_is_new_action(
            command_changed=True, fresh_cause_and_artifacts=True
        )
        is True
    )


def test_changed_command_reusing_old_artifacts_is_rejected() -> None:
    """(canary - §11:294) A changed command without fresh artifacts => False."""
    for fresh in (False, None):
        assert (
            changed_command_is_new_action(
                command_changed=True, fresh_cause_and_artifacts=fresh
            )
            is False
        )


def test_unknown_change_status_fails_closed() -> None:
    """(fail-closed) An unknown (``None``) change status => False."""
    assert (
        changed_command_is_new_action(
            command_changed=None, fresh_cause_and_artifacts=True
        )
        is False
    )
