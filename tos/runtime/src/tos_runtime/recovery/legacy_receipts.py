"""Legacy (fingerprint-less) receipt detection (TOS Phase 5 W1; plan §2 decision 2; Phase 3
carryover ⓑ — "legacy(지문 없는) 영수증이 재생 창에 남은 채 실주문 권한 승격 금지").

**The fingerprint field, precisely.** :mod:`tos_runtime.engine.flow_fingerprint` gives every
``DECISION_TICK`` ``EVENT_CONSUMED`` receipt a ``flow_fingerprint`` payload field (wave-3 review
finding #1(b)) alongside its ``outcome_digest`` — ``handed_off``/``halt_step``/``halt_reason``/
``attempt_id``, off the flow's own ``FlowResult``. A receipt written before that fix landed (a
"pre-CR6 receipt", :mod:`tos_runtime.engine.replay`'s own module docstring) carries no such
field at all. :func:`~tos_runtime.compose._boot_integrity.verify_engine_replay_or_halt` already
detects this at every boot (:attr:`~tos_runtime.engine.replay.ReplayVerdict
.has_unverifiable_receipts`) and records a non-halting ``REPLAY_RECEIPTS_UNVERIFIABLE`` evidence
row for it — but that fact alone is documentary, not yet a boot **gate**. This module is the ⓑ
gate: it independently re-derives which ``DECISION_TICK`` receipts in the CURRENT replay window
lack a fingerprint, over the SAME public surface
(:meth:`~tos_runtime.engine.inbox.SqliteEventInbox.replay`, the evidence store's own
``entries`` table), so :mod:`tos_runtime.recovery.barrier` can gate on it directly rather than
re-parsing a documentary evidence row.

**Why this is not a duplicate of ``tos_runtime.engine.replay``'s own comparison.** That module's
``_recorded_receipts``/``_compare_one_event`` are private (underscore-prefixed) and entangled
with digest/divergence comparison this module has no business re-running (replay divergence is
already a hard boot halt, handled entirely inside ``_finalize`` before this module's caller ever
runs — see :mod:`tos_runtime.recovery.barrier`'s own module docstring). This module asks a
narrower, purely structural question — "does this window hold a consumed ``DECISION_TICK``
receipt with no fingerprint at all" — using only the same two public tables every other
``tos_runtime.recovery`` module reads.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``json``) + ``tos.*`` +
``tos_runtime.*`` only. No ``shared.*``.
"""

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

#: The same evidence ``kind`` literal :mod:`tos_runtime.engine.replay`'s own
#: ``_EVENT_CONSUMED_KIND`` names (that constant is private to that module; replicated here as a
#: citation, not a re-derivation — the kind name is a stable, already-shipped evidence contract).
_EVENT_CONSUMED_KIND = "EVENT_CONSUMED"


def _has_a_valid_flow_fingerprint(payload: object) -> bool:
    """Whether ``payload`` (an ``EVENT_CONSUMED`` receipt's own ``flow_fingerprint`` field)
    validates as a genuine :class:`~tos_runtime.engine.flow_fingerprint.FlowFingerprint`
    (independent-review finding F4) — never a bare presence check
    (``payload.get("flow_fingerprint") is not None``, this module's own original check, which
    an empty dict / bare string / forged shape all satisfy vacuously)."""
    if payload is None:
        return False
    try:
        FlowFingerprint.model_validate(payload)
    except ValidationError:
        return False
    return True


@dataclass(frozen=True)
class LegacyReceiptFacts:
    """The legacy-receipt facts for one replay window (module docstring).

    Attributes:
        count: How many ``DECISION_TICK`` receipts in the window are consumed but carry no
            VALID ``flow_fingerprint`` (independent-review finding F4 — validated against the
            real :class:`~tos_runtime.engine.flow_fingerprint.FlowFingerprint` model, never a
            bare presence check), PLUS how many ``EVENT_CONSUMED`` rows in the ``entries`` table
            carry no ``event_id`` at all (corrupted/forged — never correlatable to a specific
            tick, so never silently dropped either).
        event_ids: Those receipts' own content-addressed event ids, in ascending order — a
            malformed no-``event_id`` row contributes to :attr:`count` but has no event id of
            its own to report here.
    """

    count: int
    event_ids: tuple[str, ...]


def legacy_receipts_in_window(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    *,
    scheme: CanonicalizationScheme,
    window_events: int | None,
) -> LegacyReceiptFacts:
    """Find every fingerprint-less ``DECISION_TICK`` receipt in the current replay window.

    Mirrors :func:`tos_runtime.engine.replay.replay_engine`'s own windowing exactly (the last
    ``window_events`` admitted rows, or the whole inbox when ``window_events`` is ``None``) so
    this gate covers precisely the same window the boot-time replay check already verified —
    never a narrower or wider one that could silently miss or over-flag a receipt.

    Args:
        inbox: The durable event admission queue — read-only.
        evidence_store: The durable evidence store — read-only (a raw ``SELECT`` over its own
            ``entries`` table via the public :attr:`~tos_runtime.evidence.store.SqliteEvidenceStore
            .connection`, the same seam :mod:`tos_runtime.engine.replay` uses).
        scheme: The canonicalization scheme used to derive each event's ``event_id`` (must match
            the scheme the runtime composed this inbox with).
        window_events: The SAME bound ``engine_driver.yaml``'s ``replay_window_events`` supplies
            to ``replay_engine`` (``None`` => the whole inbox).

    Returns:
        The :class:`LegacyReceiptFacts` for this window.
    """
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

    # Keyed by event_id, overwritten on every row seen (ascending seq) -- mirrors
    # tos_runtime.engine.replay._recorded_receipts' own dict semantics EXACTLY: only the LAST
    # recorded receipt for a given event_id is "the" receipt replay (and this gate) ever
    # consults, never a union across every receipt ever appended for that id.
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
            # Independent-review finding F4: a genuine EngineDriver-written EVENT_CONSUMED
            # receipt always carries event_id (a required _record_consumed argument) -- a row
            # without one is corrupted/forged and cannot be matched to a specific tick, so it is
            # counted directly rather than silently dropped by the membership check below.
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
