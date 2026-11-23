"""(#992) The causal-ordering reference survives a restart, so live and boot replay agree."""

from __future__ import annotations

import pytest
from tos.canonical import ArtifactIntegrityError
from tos.engine import HaltReason, OrderingAdmission

from ._engine_fixtures import RecordingTransmit, build_core, decision_tick, ordering

LAST_CONSUMED_SEQUENCE = 5
OUT_OF_ORDER_SEQUENCE = 3


def _core():
    """One core wired with the suite's defaults (a fresh ``RecordingTransmit`` each time)."""
    core, _ = build_core(transmit=RecordingTransmit())
    return core


def test_a_core_that_consumed_nothing_has_no_ordering_reference() -> None:
    """(#992 step 2) A freshly wired core starts with no ordering coordinate at all."""
    assert _core().last_reference is None


def test_consuming_an_event_publishes_the_last_consumed_coordinate() -> None:
    """(§2.1(ii)) The reference the core compares against is readable, not private state."""
    core = _core()
    core.handle(decision_tick(sequence=LAST_CONSUMED_SEQUENCE))
    assert core.last_reference == ordering(LAST_CONSUMED_SEQUENCE)


def test_the_boot_replay_core_reverses_the_out_of_order_event() -> None:
    """(#992 step 4) Replaying both events in inbox order positively refuses the second."""
    replay_core = _core()
    replay_core.handle(decision_tick(sequence=LAST_CONSUMED_SEQUENCE))
    replayed = replay_core.handle(decision_tick(sequence=OUT_OF_ORDER_SEQUENCE))
    assert replayed.ordering is OrderingAdmission.REVERSED
    assert replayed.halt_reason is HaltReason.EVENT_ORDER_REVERSED


def test_a_restarted_core_seeded_from_the_replay_agrees_with_it() -> None:
    """(#992) The restart's live core, handed the replay's reference, refuses what replay refuses."""
    booted = _core()
    booted.handle(decision_tick(sequence=LAST_CONSUMED_SEQUENCE))

    restarted = _core()
    restarted.adopt_ordering_reference(booted.last_reference)
    live = restarted.handle(decision_tick(sequence=OUT_OF_ORDER_SEQUENCE))

    assert live.ordering is OrderingAdmission.REVERSED
    assert live.halt_reason is HaltReason.EVENT_ORDER_REVERSED
    assert live.outcome_digest is None


def test_an_unseeded_restart_is_the_divergence_this_closes() -> None:
    """(#992 step 3) Without the hand-off the same event is admitted MONOTONE live — the"""
    restarted = _core()
    live = restarted.handle(decision_tick(sequence=OUT_OF_ORDER_SEQUENCE))
    assert live.ordering is OrderingAdmission.MONOTONE
    assert live.halt_reason is not HaltReason.EVENT_ORDER_REVERSED


def test_adopting_nothing_leaves_a_first_boot_core_pristine() -> None:
    """(#992) An empty inbox replays nothing, so the hand-off is ``None`` and changes nothing."""
    restarted = _core()
    restarted.adopt_ordering_reference(None)
    assert restarted.last_reference is None
    assert (
        restarted.handle(decision_tick(sequence=OUT_OF_ORDER_SEQUENCE)).ordering
        is OrderingAdmission.MONOTONE
    )


def test_a_monotone_continuation_is_unchanged_by_the_hand_off() -> None:
    """(#992) A leaf whose live stream keeps rising is admitted and digested exactly as before."""
    booted = _core()
    booted.handle(decision_tick(sequence=LAST_CONSUMED_SEQUENCE))

    seeded = _core()
    seeded.adopt_ordering_reference(booted.last_reference)
    seeded_result = seeded.handle(decision_tick(sequence=LAST_CONSUMED_SEQUENCE + 1))

    unseeded = _core()
    unseeded_result = unseeded.handle(
        decision_tick(sequence=LAST_CONSUMED_SEQUENCE + 1)
    )

    assert seeded_result.ordering is OrderingAdmission.MONOTONE
    assert seeded_result.ordering is unseeded_result.ordering
    assert seeded_result.halt_reason == unseeded_result.halt_reason
    assert seeded_result.outcome_digest == unseeded_result.outcome_digest


def test_a_core_that_already_consumed_refuses_a_second_seating() -> None:
    """(#992) Re-seating a running core would rewind its ordering coordinate — fail-closed."""
    core = _core()
    core.handle(decision_tick(sequence=LAST_CONSUMED_SEQUENCE))
    with pytest.raises(ArtifactIntegrityError, match="already consumed"):
        core.adopt_ordering_reference(ordering(OUT_OF_ORDER_SEQUENCE))
    assert core.last_reference == ordering(LAST_CONSUMED_SEQUENCE)
