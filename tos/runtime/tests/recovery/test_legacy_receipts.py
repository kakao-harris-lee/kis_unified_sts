"""Unit tests for :mod:`tos_runtime.recovery.legacy_receipts` (TOS Phase 5 W1; Phase 3
carryover ⓑ)."""

from __future__ import annotations

import pytest
from tos.engine.records import event_identity
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.recovery.legacy_receipts import legacy_receipts_in_window

from .conftest import SCHEME, fx

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _admit_and_consume(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    *,
    seq: int,
    flow_fingerprint: dict[str, object] | None,
) -> str:
    event = fx.crossing_event(seq=seq)
    receipt = inbox.enqueue(event)
    event_id = event_identity(event, scheme=SCHEME)
    payload: dict[str, object] = {"event_id": event_id, "outcome_digest": "digest-x"}
    if flow_fingerprint is not None:
        payload["flow_fingerprint"] = flow_fingerprint
    consumed = evidence_store.append(
        payload, kind="EVENT_CONSUMED", record_class="EVENT_CONSUMED"
    )
    inbox.mark_consumed(
        receipt.seq, evidence_seq=consumed.seq, generation=consumed.key_generation
    )
    return event_id


_FINGERPRINT = {
    "handed_off": True,
    "halt_step": None,
    "halt_reason": None,
    "attempt_id": "attempt-x",
}


def test_no_decision_tick_events_yields_no_legacy_receipts(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore
) -> None:
    facts = legacy_receipts_in_window(
        inbox, evidence_store, scheme=SCHEME, window_events=None
    )
    assert facts.count == 0
    assert facts.event_ids == ()


def test_fingerprinted_receipt_is_not_legacy(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore
) -> None:
    _admit_and_consume(inbox, evidence_store, seq=1, flow_fingerprint=_FINGERPRINT)
    facts = legacy_receipts_in_window(
        inbox, evidence_store, scheme=SCHEME, window_events=None
    )
    assert facts == legacy_receipts_in_window(
        inbox, evidence_store, scheme=SCHEME, window_events=None
    )
    assert facts.count == 0


def test_fingerprint_less_receipt_is_legacy(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore
) -> None:
    event_id = _admit_and_consume(inbox, evidence_store, seq=1, flow_fingerprint=None)
    facts = legacy_receipts_in_window(
        inbox, evidence_store, scheme=SCHEME, window_events=None
    )
    assert facts.count == 1
    assert facts.event_ids == (event_id,)


def test_unconsumed_decision_tick_is_not_legacy(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore
) -> None:
    """An admitted-but-never-consumed ``DECISION_TICK`` has no receipt at all yet — it is a
    pending/possibly-live concern (:mod:`tos_runtime.recovery.possibly_live`), never legacy.
    """
    inbox.enqueue(fx.crossing_event(seq=1))
    facts = legacy_receipts_in_window(
        inbox, evidence_store, scheme=SCHEME, window_events=None
    )
    assert facts.count == 0


def test_window_excludes_receipts_outside_it(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore
) -> None:
    """A fingerprint-less receipt admitted BEFORE the window starts is not flagged — mirrors
    ``replay_engine``'s own windowing exactly (module docstring)."""
    _admit_and_consume(inbox, evidence_store, seq=1, flow_fingerprint=None)
    in_window_id = _admit_and_consume(
        inbox, evidence_store, seq=2, flow_fingerprint=_FINGERPRINT
    )
    del in_window_id
    facts = legacy_receipts_in_window(
        inbox, evidence_store, scheme=SCHEME, window_events=1
    )
    assert facts.count == 0


def test_legacy_receipt_within_a_wider_window_is_still_found(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore
) -> None:
    legacy_id = _admit_and_consume(inbox, evidence_store, seq=1, flow_fingerprint=None)
    _admit_and_consume(inbox, evidence_store, seq=2, flow_fingerprint=_FINGERPRINT)
    facts = legacy_receipts_in_window(
        inbox, evidence_store, scheme=SCHEME, window_events=2
    )
    assert facts.count == 1
    assert facts.event_ids == (legacy_id,)


# ============================================================================
# Independent-review finding F4: validate against the real FlowFingerprint model
# ============================================================================


def test_empty_dict_flow_fingerprint_is_legacy(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore
) -> None:
    """An empty dict satisfies ``is not None`` (the module's own original, now-removed check)
    but fails ``FlowFingerprint`` validation (``handed_off`` is required)."""
    event_id = _admit_and_consume(inbox, evidence_store, seq=1, flow_fingerprint={})
    facts = legacy_receipts_in_window(
        inbox, evidence_store, scheme=SCHEME, window_events=None
    )
    assert facts.count == 1
    assert facts.event_ids == (event_id,)


def test_string_flow_fingerprint_is_legacy(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore
) -> None:
    """A bare string also satisfies ``is not None`` but is not even a mapping."""
    event = fx.crossing_event(seq=1)
    receipt = inbox.enqueue(event)
    event_id = event_identity(event, scheme=SCHEME)
    consumed = evidence_store.append(
        {
            "event_id": event_id,
            "outcome_digest": "digest-x",
            "flow_fingerprint": "not-a-fingerprint",
        },
        kind="EVENT_CONSUMED",
        record_class="EVENT_CONSUMED",
    )
    inbox.mark_consumed(
        receipt.seq, evidence_seq=consumed.seq, generation=consumed.key_generation
    )
    facts = legacy_receipts_in_window(
        inbox, evidence_store, scheme=SCHEME, window_events=None
    )
    assert facts.count == 1
    assert facts.event_ids == (event_id,)


def test_forged_shape_flow_fingerprint_is_legacy(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore
) -> None:
    """A dict with unrelated/wrong-typed fields (never a genuine ``FlowResult``-derived
    fingerprint) fails ``FlowFingerprint``'s own strict (``extra="forbid"``) validation.
    """
    event_id = _admit_and_consume(
        inbox,
        evidence_store,
        seq=1,
        flow_fingerprint={"unrelated_field": "forged", "handed_off": "not-a-bool"},
    )
    facts = legacy_receipts_in_window(
        inbox, evidence_store, scheme=SCHEME, window_events=None
    )
    assert facts.count == 1
    assert facts.event_ids == (event_id,)


def test_event_consumed_row_missing_event_id_counts_as_legacy(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore
) -> None:
    """A corrupted/forged ``EVENT_CONSUMED`` row with no ``event_id`` at all cannot be matched
    to a specific ``DECISION_TICK`` — it must still count, never be silently dropped by the
    ``event_id not in decision_tick_ids`` membership filter every genuine row goes through.
    """
    # A real, well-formed DECISION_TICK receipt in the window (so decision_tick_ids is
    # non-empty and the scan actually runs).
    _admit_and_consume(inbox, evidence_store, seq=1, flow_fingerprint=_FINGERPRINT)
    # Plus one corrupted row with no event_id at all.
    evidence_store.append(
        {"outcome_digest": "digest-corrupted"},
        kind="EVENT_CONSUMED",
        record_class="EVENT_CONSUMED",
    )
    facts = legacy_receipts_in_window(
        inbox, evidence_store, scheme=SCHEME, window_events=None
    )
    assert facts.count == 1
