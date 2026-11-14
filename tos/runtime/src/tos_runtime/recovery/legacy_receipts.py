"""Legacy (fingerprint-less) receipt detection (TOS Phase 5 W1; plan §2 decision 2; Phase 3"""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import ValidationError
from tos.canonical import CanonicalizationScheme
from tos.engine import EventKind
from tos.engine.records import event_identity

from tos_runtime.engine.flow_fingerprint import FlowFingerprint
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["LegacyReceiptFacts", "legacy_receipts_in_window"]

_EVENT_CONSUMED_KIND = "EVENT_CONSUMED"


def _has_a_valid_flow_fingerprint(payload: object) -> bool:
    """Whether ``payload`` (an ``EVENT_CONSUMED`` receipt's own ``flow_fingerprint`` field)"""
    if payload is None:
        return False
    try:
        FlowFingerprint.model_validate(payload)
    except ValidationError:
        return False
    return True


@dataclass(frozen=True)
class LegacyReceiptFacts:
    """The legacy-receipt facts for one replay window (module docstring)."""

    count: int
    event_ids: tuple[str, ...]


def legacy_receipts_in_window(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    *,
    scheme: CanonicalizationScheme,
    window_events: int | None,
) -> LegacyReceiptFacts:
    """Find every fingerprint-less ``DECISION_TICK`` receipt in the current replay window."""
    admitted = list(inbox.replay())
    if window_events is not None:
        admitted = admitted[-window_events:]
    decision_tick_ids = {
        event_identity(event, scheme=scheme)
        for _seq, event in admitted
        if event.kind is EventKind.DECISION_TICK
    }
    if not decision_tick_ids:
        return LegacyReceiptFacts(count=0, event_ids=())

    has_fingerprint_by_event: dict[str, bool] = {}
    malformed_no_event_id = 0
    cursor = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
        (_EVENT_CONSUMED_KIND,),
    )
    for (payload_json,) in cursor:
        payload = json.loads(payload_json).get("payload", {})
        event_id = payload.get("event_id")
        if event_id is None:
            malformed_no_event_id += 1
            continue
        if event_id not in decision_tick_ids:
            continue
        has_fingerprint_by_event[event_id] = _has_a_valid_flow_fingerprint(
            payload.get("flow_fingerprint")
        )

    legacy_ids = tuple(
        sorted(
            event_id
            for event_id, has_fingerprint in has_fingerprint_by_event.items()
            if not has_fingerprint
        )
    )
    return LegacyReceiptFacts(
        count=len(legacy_ids) + malformed_no_event_id, event_ids=legacy_ids
    )
