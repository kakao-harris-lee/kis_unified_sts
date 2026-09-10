"""Unit tests for :mod:`tos_runtime.recovery.composite_state_writer` (TOS Phase 5 W1 close-out,
GAP 2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    IntentState,
    KnowledgeState,
    TransmissionAttemptState,
)
from tos.rcl import CapacityState
from tos.staterestore import IncompleteStoreError, reload_conservative
from tos_runtime.recovery.composite_state_writer import CompositeStateWriter

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _composite(
    *, intent_identity: str | None = "proposal-not-the-event-id"
) -> CompositeState:
    return CompositeState(
        intent_identity=intent_identity,
        intent_state=IntentState.ACTIVE,
        transmission_attempt_state=TransmissionAttemptState.ACK_OBSERVED,
        broker_order_state=BrokerOrderState.WORKING,
        knowledge_state=KnowledgeState.CONSISTENT,
        capacity_state=CapacityState.POSITION_CONSUMED,
    )


def test_write_then_reload_conservative_succeeds_keyed_by_event_id(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "composite_state.sqlite3"
    writer = CompositeStateWriter(store_path)
    writer("event-abc", _composite())

    reconstruction = reload_conservative(store_path, "event-abc")

    assert reconstruction.store_complete is True
    assert reconstruction.filled_dimensions == ()
    assert reconstruction.pre_restart.intent_identity == "event-abc"


def test_reload_by_a_different_event_id_still_raises_incomplete(tmp_path: Path) -> None:
    """The write is scoped to ITS OWN event id — no cross-attempt leakage."""
    store_path = tmp_path / "composite_state.sqlite3"
    writer = CompositeStateWriter(store_path)
    writer("event-abc", _composite())

    with pytest.raises(IncompleteStoreError):
        reload_conservative(store_path, "event-xyz")


def test_write_ignores_the_composites_own_intent_identity(tmp_path: Path) -> None:
    """The composite's own ``intent_identity`` (a proposal digest, per
    ``tos.engine.orthostate_projection.composite_state_for``'s own docstring) is never the
    durable key — only the caller-supplied ``event_id`` is."""
    store_path = tmp_path / "composite_state.sqlite3"
    writer = CompositeStateWriter(store_path)
    writer("event-abc", _composite(intent_identity="some-proposal-digest"))

    with pytest.raises(IncompleteStoreError):
        reload_conservative(store_path, "some-proposal-digest")
    # But the event id it was actually keyed under reloads cleanly.
    reload_conservative(store_path, "event-abc")


def test_write_creates_the_store_file_on_first_call(tmp_path: Path) -> None:
    store_path = tmp_path / "nested" / "composite_state.sqlite3"
    assert not store_path.exists()
    writer = CompositeStateWriter(store_path)
    writer("event-abc", _composite())
    assert store_path.is_file()


def test_two_events_persist_independently(tmp_path: Path) -> None:
    store_path = tmp_path / "composite_state.sqlite3"
    writer = CompositeStateWriter(store_path)
    writer("event-1", _composite())
    writer(
        "event-2",
        _composite().model_copy(
            update={
                "transmission_attempt_state": TransmissionAttemptState.SEND_FAILED_PROVEN
            }
        ),
    )

    r1 = reload_conservative(store_path, "event-1")
    r2 = reload_conservative(store_path, "event-2")
    assert (
        r1.pre_restart.transmission_attempt_state
        is TransmissionAttemptState.ACK_OBSERVED
    )
    assert (
        r2.pre_restart.transmission_attempt_state
        is TransmissionAttemptState.SEND_FAILED_PROVEN
    )
