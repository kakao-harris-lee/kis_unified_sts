"""``CompositeStateWriter`` — persists a projected orthostate ``CompositeState`` into the kernel
``tos.staterestore`` composite-state store (TOS Phase 5 W1 close-out, GAP 2).

**What this closes.** :mod:`tos_runtime.recovery.inputs`'s own module docstring recorded, at
landing time, a "disclosed limitation": "nothing in this runtime shell writes to that store yet
... every attempt is ALSO flagged incomplete here until a future wave wires the driver's own
write path into this store". This module is that write path.

**Why keyed by ``event_id``, not ``composite.intent_identity``.** ``tos.staterestore
.CompositeStateStore.commit_composite`` requires a truthy ``composite.intent_identity`` and
persists under exactly that key; :func:`tos.engine.orthostate_projection.composite_state_for`
populates that field from ``projection.proposal_id`` — a DSL ``Proposal``'s own content-addressed
digest, a completely different identity space from the event identity
:func:`tos_runtime.recovery.possibly_live.reconstruct_possibly_live_attempts` uses to name a
possibly-live attempt (:func:`tos.engine.records.event_identity` of the interrupted
``EngineEvent``). ``tos_runtime.recovery.inputs``'s own
``_composite_state_incomplete_ids`` already reads the store back by ``attempt.event_id``
(the only durable identity available at that boot-time layer, per that module's own docstring:
"there is no other durable identity to key a restart-time composite reload on"). For the write
side to ever satisfy the read side, this writer therefore keys under the EVENT id the driver was
processing when it produced this composite — never the composite's own ``intent_identity`` — by
constructing a shallow copy with ``intent_identity`` overridden. This is a deliberate, disclosed
identity substitution, not an oversight: it makes the write and read sides agree on what "this
possibly-live attempt's composite state" durably means, at the cost of the persisted
``intent_identity`` no longer being a genuine ADR-002-005 Intent identity (it already was not one
— ``composite_state_for``'s own docstring: "it is honestly not an ADR-002-005 Intent identity").

**One event, one write, called once per driver turn.** A caller (``tos_runtime.engine.driver
.EngineDriver``) calls this exactly once per ``EGRESS_RESULT`` event whose projection produced a
composite, passing that event's OWN ``event_id`` (the same identity
:func:`tos.engine.records.event_identity` derives, computed once per event and already used for
that event's ``EVENT_HANDLING_STARTED``/``EVENT_CONSUMED`` receipts) — never the attempt id, never
a DECISION_TICK's event id from earlier in the same flow.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``pathlib``) +
``tos.orthostate`` + ``tos.staterestore`` only. No ``shared.*``, no network, no ambient
environment-variable reads.
"""

from __future__ import annotations

from pathlib import Path

from tos.orthostate import CompositeState
from tos.staterestore import CompositeStateStore

__all__ = ["COMPOSITE_STATE_STORE_FILE_NAME", "CompositeStateWriter"]

#: Where a per-data-dir ``tos.staterestore`` composite-state store lives — the SAME literal
#: :mod:`tos_runtime.compose._recovery_wiring`'s own ``COMPOSITE_STATE_STORE_FILE_NAME`` names.
#: Duplicated here rather than imported from that module to avoid a
#: ``tos_runtime.recovery -> tos_runtime.compose`` import edge running backwards against this
#: runtime's own composition-root layering (mirrors
#: :mod:`tos_runtime.engine.orthostate_projection`'s own documented reason for injecting
#: ``authority_epoch_current`` as a callable rather than importing ``tos_runtime.compose``
#: directly) — and, at landing time, because ``tos_runtime/compose/_recovery_wiring.py`` was
#: concurrently being edited by a sibling lane closing GAP 1 in the same worktree; re-pointing
#: the constant's single source of truth is left for that reconciliation, not done here as a
#: side effect of GAP 2. **Disclosed duplication, not an oversight** — a future pass should make
#: one of the two an import of the other rather than carrying the literal in two places.
COMPOSITE_STATE_STORE_FILE_NAME = "composite_state.sqlite3"


class CompositeStateWriter:
    """Persists a projected :class:`~tos.orthostate.CompositeState` into a
    :class:`~tos.staterestore.CompositeStateStore`, keyed by the driver's own already-durable
    event id (module docstring).

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

    def __call__(self, event_id: str, composite: CompositeState) -> None:
        """Durably commit ``composite``'s five dimensions under ``event_id`` (module docstring's
        identity substitution).

        Args:
            event_id: The content-addressed identity of the event whose processing produced
                ``composite`` (:func:`tos.engine.records.event_identity`) — the key
                :mod:`tos_runtime.recovery.inputs` reloads by, never ``composite
                .intent_identity``.
            composite: The composite state to persist. All five dimensions are committed in one
                call (:meth:`~tos.staterestore.CompositeStateStore.commit_composite`'s own
                per-dimension-transaction behaviour — a crash mid-call leaves a genuinely
                INCOMPLETE store, the correct conservative outcome, never a torn record).
        """
        keyed = composite.model_copy(update={"intent_identity": event_id})
        with CompositeStateStore(self._store_path) as store:
            store.commit_composite(keyed)
