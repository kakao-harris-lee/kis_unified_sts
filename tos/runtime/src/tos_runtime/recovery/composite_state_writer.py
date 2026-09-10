"""``CompositeStateWriter`` — persists a projected orthostate ``CompositeState`` into the kernel
``tos.staterestore`` composite-state store (TOS Phase 5 W1 close-out, GAP 2).

**What this closes.** :mod:`tos_runtime.recovery.inputs`'s own module docstring recorded, at
landing time, a "disclosed limitation": "nothing in this runtime shell writes to that store yet
... every attempt is ALSO flagged incomplete here until a future wave wires the driver's own
write path into this store". This module is that write path.

**Why keyed by ``attempt_id``, not ``composite.intent_identity`` — and not ``event_id`` either
(independent-review finding F3, 2026-09-10, superseding this module's own original design).**
``tos.staterestore.CompositeStateStore.commit_composite`` requires a truthy
``composite.intent_identity`` and persists under exactly that key;
:func:`tos.engine.orthostate_projection.composite_state_for` populates that field from
``projection.proposal_id`` — a DSL ``Proposal``'s own content-addressed digest, a different
identity space again. This module's FIRST landing keyed the write under the EGRESS_RESULT
event's own ``event_id`` instead, reasoning that :mod:`tos_runtime.recovery.inputs`'s read side
also used ``event_id``. That was measurably wrong: :func:`~tos_runtime.engine.orthostate_projection
.OrthostateProjector.project` returns ``None`` for a ``DECISION_TICK`` (only an ``EGRESS_RESULT``
ever produces a composite), so the EGRESS_RESULT's own ``event_id`` is NEVER the identity a
possibly-live ``DECISION_TICK`` attempt (the crash window :mod:`tos_runtime.recovery.possibly_live`
names — "the interrupted flow may already have reached the send boundary") is keyed by; the write
and read sides could structurally never agree, and obligation 6 was unreachable-SATISFIED-or-not
by construction. The fix keys the write under the ``attempt_id`` the ``EGRESS_RESULT`` payload
already carries (:attr:`tos.engine.records.EgressResultPayload.attempt_id`) — the SAME identity
:meth:`~tos_runtime.engine.inbox.SqliteEventInbox.record_composite` already durably tracks its own
side-table composite by (``tos_runtime.engine.orthostate_projection``'s own call site), so this
staterestore write finally agrees with an identity this runtime ALREADY treats as canonical for
"this attempt's composite state" elsewhere. The read side
(:mod:`tos_runtime.recovery.inputs`) now resolves a possibly-live attempt's ``event_id`` to this
SAME ``attempt_id`` via the durable ``SEND_HANDED_OFF`` link
(:func:`tos_runtime.recovery.reconciliation.send_handed_off_attempt_id`) before reloading — the
identical bridge :mod:`tos_runtime.recovery.reconciliation` already uses for the SAME
event_id -> attempt_id gap. ``composite.intent_identity`` (the proposal digest) is still
overridden, never used directly, by the SAME shallow-copy substitution as before.

**One event, one write, called once per driver turn.** A caller (``tos_runtime.engine.driver
.EngineDriver``) calls this exactly once per ``EGRESS_RESULT`` event whose projection produced a
composite, passing that event's own ``attempt_id`` (:attr:`~tos.engine.records
.EgressResultPayload.attempt_id`) — never the event id, never a DECISION_TICK's identity from
earlier in the same flow.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``pathlib``) +
``tos.orthostate`` + ``tos.staterestore`` only. No ``shared.*``, no network, no ambient
environment-variable reads.
"""

from __future__ import annotations

from pathlib import Path

from tos.orthostate import CompositeState
from tos.staterestore import CompositeStateStore

__all__ = ["COMPOSITE_STATE_STORE_FILE_NAME", "CompositeStateWriter"]

#: Where a per-data-dir ``tos.staterestore`` composite-state store lives — the SINGLE source of
#: truth (independent-review finding F7, 2026-09-10, resolved a landing-time duplication: this
#: constant briefly existed twice, once here and once in ``tos_runtime.compose._recovery_wiring``,
#: because that module was concurrently being edited by a sibling lane when this one landed).
#: Both :func:`~tos_runtime.compose._engine_wiring.build_engine_driver` and
#: :func:`~tos_runtime.compose._recovery_wiring.apply_recovery_barrier` import it FROM here —
#: never the reverse (this module has no ``tos_runtime.compose`` import at all, preserving the
#: same "engine/recovery packages never import compose" layering
#: :mod:`tos_runtime.engine.orthostate_projection`'s own docstring documents for
#: ``authority_epoch_current``).
COMPOSITE_STATE_STORE_FILE_NAME = "composite_state.sqlite3"


class CompositeStateWriter:
    """Persists a projected :class:`~tos.orthostate.CompositeState` into a
    :class:`~tos.staterestore.CompositeStateStore`, keyed by the attempt's own durable
    ``attempt_id`` (module docstring — independent-review finding F3 superseded the original
    event-id keying).

    A fresh :class:`~tos.staterestore.CompositeStateStore` connection is opened and closed on
    every call — matching :func:`tos.staterestore.reload_conservative`'s own "no write buffer, no
    in-process cache" discipline (that module's own docstring) and
    :mod:`tos_runtime.recovery.inputs`'s own read-side call pattern
    (``with CompositeStateStore(Path(store_path)) as store:``) — never a long-lived handle this
    class would need to coordinate closing on process shutdown.
    """

    def __init__(self, store_path: Path) -> None:
        """Bind this writer to a store file path.

        Args:
            store_path: The on-disk ``tos.staterestore`` composite-state store file (created on
                first write if it does not yet exist — :class:`~tos.staterestore
                .CompositeStateStore`'s own constructor behaviour).
        """
        self._store_path = Path(store_path)

    def __call__(self, attempt_id: str, composite: CompositeState) -> None:
        """Durably commit ``composite``'s five dimensions under ``attempt_id`` (module
        docstring's identity substitution).

        Args:
            attempt_id: The attempt identity the ``EGRESS_RESULT`` payload that produced
                ``composite`` already carries (:attr:`tos.engine.records.EgressResultPayload
                .attempt_id`) — the key :mod:`tos_runtime.recovery.inputs` reloads by (after
                resolving a possibly-live attempt's own ``event_id`` onto this SAME identity via
                :func:`tos_runtime.recovery.reconciliation.send_handed_off_attempt_id`), never
                ``composite.intent_identity``.
            composite: The composite state to persist. All five dimensions are committed in one
                call (:meth:`~tos.staterestore.CompositeStateStore.commit_composite`'s own
                per-dimension-transaction behaviour — a crash mid-call leaves a genuinely
                INCOMPLETE store, the correct conservative outcome, never a torn record).
        """
        keyed = composite.model_copy(update={"intent_identity": attempt_id})
        with CompositeStateStore(self._store_path) as store:
            store.commit_composite(keyed)
