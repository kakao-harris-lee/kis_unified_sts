"""The POST_TRADE currentness dimension's own read over release evidence.

Extracted from :mod:`tos_runtime.posttrade.release_consumer` to keep that module under the
repo's 1000-line size budget (``tools/tos_size_budget.py``) — a pure decomposition, no
behaviour change, the same discipline :mod:`tos_runtime.posttrade.entry_discharge` was split
out under. It is also a genuinely separate concern: its one consumer is
:mod:`tos_runtime.compose._currentness_wiring`'s dimension reader, not the release path.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos_runtime.evidence
.store`` + ``tos_runtime.rcl.reservation_identity`` only. No ``shared.*``; read-only throughout
(this module never calls ``append``).
"""

from __future__ import annotations

import json

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.reservation_identity import scope_reservation_id

__all__ = ["latest_release_is_conflict_free"]

#: The two evidence kinds this read scans, and the one hold reason that structurally means a
#: reconciliation conflict — redeclared as literals rather than imported from
#: :mod:`tos_runtime.posttrade.release_consumer` (which imports THIS module), exactly the
#: lockstep-literal convention that module already uses for its own kind strings. The compose
#: e2e suite queries these same strings against a real, shared evidence store.
_INTENT_KIND = "CAPACITY_RELEASE_INTENT"
_HELD_KIND = "CAPACITY_RELEASE_HELD"
_NOT_CORROBORATED = "NOT_CORROBORATED"


def latest_release_is_conflict_free(
    evidence_store: SqliteEvidenceStore, *, account: str, instrument: str
) -> bool:
    """Whether this scope's MOST RECENT recorded post-trade release evidence is conflict-free.

    Scans the scope's own ``CAPACITY_RELEASE_INTENT`` / ``CAPACITY_RELEASE_HELD`` rows, newest
    ``seq`` first, for the first one belonging to this scope: the scope id itself (a pre-#966
    row) or one of its per-attempt ids, which are the scope id plus ``-<permit identity>``
    (:func:`~tos_runtime.rcl.reservation_identity.permit_reservation_id`) — and nothing from a
    sibling scope whose instrument merely starts with the same characters (review-973 L3). A row
    that could not be attributed to any reservation at all (``reservation_id`` null) is skipped;
    it says nothing about a reservation's post-trade state. The dimension then reads:

    - No matching row at all (no post-trade fact yet for this scope) ⇒ ``True`` — a scope that
      has never sent an attempt has no post-trade fact YET, which is the normal state before any
      send, never treated as a conflict.
    - The latest matching row is a ``CAPACITY_RELEASE_INTENT`` (a release actually proceeded)
      ⇒ ``True``.
    - The latest matching row is a ``CAPACITY_RELEASE_HELD`` whose recorded ``reason`` is
      ``NOT_CORROBORATED`` ⇒ ``False`` — the ONE hold reason that structurally means gate 3's
      reconciliation found a genuine conflict (an orphan broker order, or a non-``MATCHED``
      classification) between what this scope expected and what actually happened downstream.
    - Any OTHER ``CAPACITY_RELEASE_HELD`` reason (no witness yet, proof not yet reloaded,
      reconciliation itself unavailable, the RCL transition itself refused, a quantity not yet
      proven, ...) ⇒ ``True`` — a normal, transient "not yet complete" gate, never a conflict;
      folding every hold into ``False`` would permanently block new risk on ordinary pipeline
      timing, which this dimension does not do.

    Args:
        evidence_store: The durable evidence store the rows live in.
        account: The scope account.
        instrument: The scope instrument.

    Returns:
        ``True`` unless the most recent recorded outcome for this scope is a genuine
        reconciliation conflict.
    """
    scope_id = scope_reservation_id(account, instrument)
    rows = evidence_store.connection.execute(
        "SELECT kind, payload_json FROM entries WHERE kind IN (?, ?) ORDER BY seq DESC",
        (_INTENT_KIND, _HELD_KIND),
    ).fetchall()
    for kind, payload_json in rows:
        decoded = json.loads(payload_json)["payload"]
        reservation_id = decoded.get("reservation_id")
        if not isinstance(reservation_id, str) or not (
            reservation_id == scope_id or reservation_id.startswith(f"{scope_id}-")
        ):
            continue
        if kind == _INTENT_KIND:
            return True
        return bool(decoded.get("reason") != _NOT_CORROBORATED)
    return True
