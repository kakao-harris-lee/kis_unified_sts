"""RCLP-EV-001 (core, L1 slice) — deterministic reducer / no-double-spend (§5.2).

No-double-spend under the aggregate envelope (INV-001; AC-001) on a *given*
committed order, plus determinism, idempotency (RCLP-INV-006), CAS, and the
producer-optimism canary. (That a single order is produced by quorum under
concurrency is EV-L3, §0.2 — not claimed here.)
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from tos.rcl import (
    ApplyReason,
    CommittedReservation,
    LedgerState,
    apply_committed,
    available_headroom,
    committed_usage,
    fold_commands,
)

from ._rcl_strategies import commit_reservation_command, vec

DIMS = ["gross_notional"]
LIMITS = vec(gross_notional=10)


def _commit(ci: str, expected_revision: int, reservation_id: str, magnitude: int, **kw):
    return commit_reservation_command(
        command_identity=ci,
        expected_revision=expected_revision,
        reservation_id=reservation_id,
        increment=vec(gross_notional=magnitude),
        **kw,
    )


def test_two_jointly_exceeding_admits_exactly_one() -> None:
    """Two individually-valid reservations jointly exceeding a limit => one admitted."""
    s0 = LedgerState()
    o1 = apply_committed(
        s0, _commit("c1", 0, "r1", 7), limits=LIMITS, applicable_dimensions=DIMS
    )
    o2 = apply_committed(
        o1.state, _commit("c2", 0, "r2", 7), limits=LIMITS, applicable_dimensions=DIMS
    )
    assert o1.admitted is True and o1.reason is ApplyReason.ADMITTED
    # The second, submitted against the stale revision, fails CAS (§8.4).
    assert o2.admitted is False and o2.reason is ApplyReason.REJECTED_STALE_REVISION
    admitted = [o for o in (o1, o2) if o.admitted]
    assert len(admitted) == 1


def test_reevaluation_against_current_revision_hits_limit() -> None:
    """Resubmitting the second with the current revision fails on the envelope, not CAS."""
    s0 = LedgerState()
    o1 = apply_committed(
        s0, _commit("c1", 0, "r1", 7), limits=LIMITS, applicable_dimensions=DIMS
    )
    o2 = apply_committed(
        o1.state, _commit("c2", 1, "r2", 7), limits=LIMITS, applicable_dimensions=DIMS
    )
    assert o2.admitted is False and o2.reason is ApplyReason.REJECTED_LIMIT_EXCEEDED


def test_single_reservation_exceeding_limit_rejected() -> None:
    """A reservation whose own increment exceeds the limit is rejected."""
    o = apply_committed(
        LedgerState(),
        _commit("c1", 0, "r1", 11),
        limits=LIMITS,
        applicable_dimensions=DIMS,
    )
    assert o.admitted is False and o.reason is ApplyReason.REJECTED_LIMIT_EXCEEDED


def test_idempotent_retry_returns_same_result_no_duplicate_transition() -> None:
    """Same command_identity + same bytes => same result, no duplicate transition."""
    s0 = LedgerState()
    o1 = apply_committed(
        s0, _commit("c1", 0, "r1", 7), limits=LIMITS, applicable_dimensions=DIMS
    )
    # Replay the exact same command against the advanced state.
    replay = apply_committed(
        o1.state, _commit("c1", 0, "r1", 7), limits=LIMITS, applicable_dimensions=DIMS
    )
    assert replay.reason is ApplyReason.IDEMPOTENT_REPLAY
    assert replay.admitted == o1.admitted
    # No duplicate reservation / revision advance from the replay.
    assert replay.state.revision == o1.state.revision
    assert len(replay.state.committed) == len(o1.state.committed)


def test_same_id_different_bytes_is_contained_conflict() -> None:
    """Same command_identity + different bytes => contained Critical conflict."""
    s0 = LedgerState()
    o1 = apply_committed(
        s0, _commit("c1", 0, "r1", 7), limits=LIMITS, applicable_dimensions=DIMS
    )
    # Same identity, different bytes (different increment).
    conflict = apply_committed(
        o1.state, _commit("c1", 0, "r1", 3), limits=LIMITS, applicable_dimensions=DIMS
    )
    assert conflict.admitted is False
    assert conflict.reason is ApplyReason.REJECTED_CRITICAL_CONFLICT
    # Contained: no state change (both original observations preserved).
    assert conflict.state.revision == o1.state.revision


def test_determinism_same_order_same_result() -> None:
    """Determinism: same ordered command sequence + initial state => same final state."""
    commands = [
        _commit("c1", 0, "r1", 3),
        _commit("c2", 1, "r2", 3),
        _commit("c3", 2, "r3", 3),
    ]
    s_a = fold_commands(
        LedgerState(), commands, limits=LIMITS, applicable_dimensions=DIMS
    )
    s_b = fold_commands(
        LedgerState(), commands, limits=LIMITS, applicable_dimensions=DIMS
    )
    assert s_a == s_b
    assert s_a.revision == 3 and len(s_a.committed) == 3


@given(order=st.permutations(range(4)))
def test_aggregate_usage_order_independent(order) -> None:
    """(shuffle canary) Aggregate committed usage is invariant under reservation order.

    The aggregate envelope depends on the *set* of committed reservations, not their
    listing order — shuffling unordered inputs does not change the result (§5.2).
    """
    reservations = [
        CommittedReservation(
            reservation_id=f"r{i}", adverse_increment=vec(gross_notional=i + 1)
        )
        for i in range(4)
    ]
    base = committed_usage(LedgerState(committed=tuple(reservations)))
    shuffled = committed_usage(
        LedgerState(committed=tuple(reservations[i] for i in order))
    )
    assert base.magnitude("gross_notional") == shuffled.magnitude("gross_notional")
    assert base.magnitude("gross_notional") == Decimal(1 + 2 + 3 + 4)


@given(
    magnitude=st.integers(min_value=0, max_value=10),
    counter=st.integers(),
    priority=st.integers(),
)
def test_producer_local_counter_creates_no_headroom(
    magnitude: int, counter: int, priority: int
) -> None:
    """Producer-local counters / scheduler priority create no headroom (§11.2 step 10)."""
    plain = _commit("c1", 0, "r1", magnitude)
    optimistic = _commit(
        "c1b",
        0,
        "r1b",
        magnitude,
        producer_local_counter=counter,
        scheduler_priority=priority,
    )
    o_plain = apply_committed(
        LedgerState(), plain, limits=LIMITS, applicable_dimensions=DIMS
    )
    o_opt = apply_committed(
        LedgerState(), optimistic, limits=LIMITS, applicable_dimensions=DIMS
    )
    # Same admission and same resulting committed headroom regardless of the counters.
    assert o_plain.admitted == o_opt.admitted
    h_plain = available_headroom(o_plain.state, LIMITS, DIMS)
    h_opt = available_headroom(o_opt.state, LIMITS, DIMS)
    assert h_plain is not None and h_opt is not None
    assert h_plain.magnitude("gross_notional") == h_opt.magnitude("gross_notional")


def test_headroom_computed_only_from_committed_state() -> None:
    """Headroom is limit - committed usage; empty state => full limit."""
    empty = available_headroom(LedgerState(), LIMITS, DIMS)
    assert empty is not None and empty.magnitude("gross_notional") == Decimal(10)
    o1 = apply_committed(
        LedgerState(),
        _commit("c1", 0, "r1", 4),
        limits=LIMITS,
        applicable_dimensions=DIMS,
    )
    used = available_headroom(o1.state, LIMITS, DIMS)
    assert used is not None and used.magnitude("gross_notional") == Decimal(6)


def test_headroom_empty_dimensions_is_none() -> None:
    """Empty applicable dimensions => no headroom may be claimed (fail-closed)."""
    assert available_headroom(LedgerState(), LIMITS, []) is None


def test_unidentified_draft_command_refused_no_ledger_effect() -> None:
    """(fail-closed) A DRAFT / unidentified command mutates no capacity (§4.1)."""
    from tos.rcl import LedgerCommandRecord

    # A DRAFT command has null command_identity + null canonical_digest.
    draft = LedgerCommandRecord()
    assert draft.canonical_digest is None
    outcome = apply_committed(
        LedgerState(), draft, limits=LIMITS, applicable_dimensions=DIMS
    )
    assert outcome.admitted is False
    assert outcome.reason is ApplyReason.REJECTED_UNIDENTIFIED
    assert outcome.state == LedgerState()  # no ledger effect at all
