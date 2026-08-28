"""S-2 / S-3 — the restart read path: conservative fill, then re-derivation.

ADR-002-005 §13, the three SHALLs this module realizes (design #39 §5.1):

* line 197 "All five dimensions SHALL be durable and **reconstructable** after crash,
  restart, or failover" — the store is re-read from disk by a *fresh process* and a
  composite is rebuilt from it.
* line 198 "On restart, any Attempt that reached ``SEND_STARTED`` and any Broker Order
  that is not provably terminal SHALL be treated as ``POTENTIALLY_LIVE``/``UNKNOWN``
  until reconciled" — delegated verbatim to
  :func:`tos.orthostate.reconstruct_conservative`; this module does **not** re-author it.
* line 199 "Knowledge SHALL be re-derived from evidence, defaulting to
  ``UNOBSERVED``/``CONFLICTED``, never to ``RECONCILED``".

S-2 — the per-dimension conservative fill
-----------------------------------------
An incomplete store (STATE-EV-004 line 1045 "restart with incomplete stores") leaves
some dimension absent. Absence is **not** an excuse to guess favourably, so each
dimension's fill value is argued from the spec rather than picked for convenience
(design #39 §5.1 S-2, table :data:`ABSENT_DIMENSION_FILL`):

* **Knowledge → ``UNOBSERVED``.** §13 line 199 permits ``UNOBSERVED``/``CONFLICTED``
  and forbids ``RECONCILED``. Of the two permitted values the natural reading of "no
  durable evidence" is ``UNOBSERVED`` — an *absence of observation* — whereas
  ``CONFLICTED`` would assert a conflict that was never observed. The load-bearing
  guarantee is nevertheless the **negative** one, ``knowledge ∉ {RECONCILED,
  CONSISTENT}``: the positive value is a deterministic anchor, the negative invariant is
  what the outside oracle checks independently.
* **Broker Order → ``UNKNOWN``.** §13 line 198 — a broker order that is not *provably*
  terminal is ``UNKNOWN``; no durable evidence is the weakest possible proof. ``UNKNOWN``
  is capacity-consuming and never means rejected / cancelled / safe-to-retry (§1 line
  27).
* **Transmission Attempt → ``NONE``.** §6 line 96 makes the transition into
  ``SEND_STARTED`` durable **before** the external call, so a store with no attempt
  marker structurally implies the external call had not been made. This is a *structural*
  safe reading derived from the write-ahead ordering, not an optimistic default.
* **Capacity → ``POTENTIALLY_LIVE``.** The CPL-1 minimum for a possibly-live effect
  (§10 line 156). ``reconstruct_conservative`` may raise it further but never lowers it.
* **Intent → refused.** An absent intent marker means the record cannot be identified,
  and a reconstruction that invented an identity would be a fabrication rather than a
  re-derivation. :class:`IncompleteStoreError` is raised (fail-closed).

S-3 — no stale cache
--------------------
Caches are **discarded** on resume and the composite is re-derived from the store alone
(§13 line 199 "re-derived from evidence"; line 1045 "stale caches"). :func:`discard_caches`
unlinks them, so "the reader ignored the cache" is observable as *the cache is gone*
rather than as an absence of a code path. :func:`reload_conservative` has no parameter,
branch, or fallback that could consume a cache's contents.

Non-transmitting: this module reads a local file. No socket, no route, no credential
(``tos/__init__.py`` line 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    KnowledgeState,
    StateDimension,
    TransmissionAttemptState,
    reconstruct_conservative,
)
from tos.rcl import CapacityState
from tos.staterestore.store import DIMENSION_COMMIT_ORDER, CompositeStateStore

#: The S-2 conservative fill for an absent dimension (argued in the module docstring).
#: ``StateDimension.INTENT`` is deliberately **absent from this table**: there is no
#: conservative value for "which intent is this", so an absent intent marker is refused
#: rather than filled. A future edit that adds an INTENT entry here would be adding a
#: fabricated identity, and :mod:`tos.tests.staterestore` fails if the key appears.
ABSENT_DIMENSION_FILL: dict[StateDimension, object] = {
    StateDimension.TRANSMISSION_ATTEMPT: TransmissionAttemptState.NONE,
    StateDimension.BROKER_ORDER: BrokerOrderState.UNKNOWN,
    StateDimension.KNOWLEDGE: KnowledgeState.UNOBSERVED,
    StateDimension.CAPACITY: CapacityState.POTENTIALLY_LIVE,
}


class IncompleteStoreError(RuntimeError):
    """The store cannot identify the record it holds (fail-closed).

    Raised when the Intent dimension is absent. Every other dimension has a defensible
    conservative fill; identity does not, and a reconstruction under a synthesised
    identity would attach conservative state to the wrong trading action.
    """


@dataclass(frozen=True)
class RestartReconstruction:
    """The outcome of one restart reload (design #39 §5.1 S-2).

    Attributes:
        pre_restart: The composite as re-derived from the store, with absent dimensions
            conservatively filled — the *input* to the §13 projection.
        composite: The post-restart composite, i.e.
            ``reconstruct_conservative(pre_restart)``. This is the authoritative result.
        store_complete: Whether all five dimensions were durable (no fill applied).
        filled_dimensions: The dimensions that were absent and conservatively filled, in
            :data:`tos.staterestore.store.DIMENSION_COMMIT_ORDER`. Reported so a caller
            can tell "the store said ``UNKNOWN``" from "the store said nothing and the
            reload chose ``UNKNOWN``" — collapsing those two would hide an incomplete
            store behind a value that happens to look the same.
        discarded_caches: The cache files unlinked before re-derivation (S-3).
    """

    pre_restart: CompositeState
    composite: CompositeState
    store_complete: bool
    filled_dimensions: tuple[StateDimension, ...]
    discarded_caches: tuple[str, ...]


def discard_caches(cache_paths: tuple[Path, ...] | list[Path]) -> tuple[str, ...]:
    """Discard resume-time caches (S-3) and report which ones existed.

    Unlinking rather than merely not-reading is the point: after this call the optimistic
    cache is *gone*, so a later regression that tried to consult one would have nothing
    to consult. The return value is the executable observation that a cache was present
    and was dropped, which is what distinguishes "the stale-cache scenario ran" from
    "no cache was ever written".

    Args:
        cache_paths: Candidate cache files. A path that does not exist is simply not
            reported; discarding is idempotent.

    Returns:
        The string paths of the caches that existed and were removed.
    """
    discarded: list[str] = []
    for path in cache_paths:
        candidate = Path(path)
        if candidate.is_file():
            candidate.unlink()
            discarded.append(str(candidate))
    return tuple(discarded)


def reload_conservative(
    store_path: Path,
    intent_identity: str,
    *,
    cache_paths: tuple[Path, ...] | list[Path] = (),
    state_model_version: str | None = None,
) -> RestartReconstruction:
    """Re-derive a conservative post-restart composite from the durable store alone.

    The sequence is fixed and has no alternative branch: discard caches (S-3), read the
    store from disk (S-1), fill absent dimensions conservatively (S-2), then apply the
    §13 projection :func:`tos.orthostate.reconstruct_conservative`. The projection is
    **not** re-implemented here — re-authoring it would make this module both the guard
    and the oracle, which is the failure mode design #39 §5.3 exists to structurally
    prevent.

    Args:
        store_path: The on-disk store written before the crash.
        intent_identity: The identity whose markers are re-derived.
        cache_paths: Optimistic caches to discard before re-deriving (S-3).
        state_model_version: Carried onto the rebuilt composite when known.

    Returns:
        The :class:`RestartReconstruction`.

    Raises:
        IncompleteStoreError: If the Intent dimension is absent (unidentifiable record).
        tos.staterestore.store.StoreIntegrityError: If a stored marker is unreadable.
    """
    discarded = discard_caches(cache_paths)
    with CompositeStateStore(Path(store_path)) as store:
        markers = store.read_markers(intent_identity)

    if StateDimension.INTENT not in markers:
        raise IncompleteStoreError(
            f"no durable Intent marker for {intent_identity!r}: the record cannot be "
            "identified, so it is refused rather than reconstructed under a "
            "synthesised identity"
        )

    filled: list[StateDimension] = []
    resolved: dict[StateDimension, object] = {}
    for dimension in DIMENSION_COMMIT_ORDER:
        if dimension not in ABSENT_DIMENSION_FILL:
            continue  # Intent: refused above, never filled
        if dimension in markers:
            resolved[dimension] = markers[dimension]
        else:
            resolved[dimension] = ABSENT_DIMENSION_FILL[dimension]
            filled.append(dimension)

    pre = CompositeState(
        intent_identity=intent_identity,
        intent_state=markers[StateDimension.INTENT],
        transmission_attempt_state=resolved[StateDimension.TRANSMISSION_ATTEMPT],
        broker_order_state=resolved[StateDimension.BROKER_ORDER],
        knowledge_state=resolved[StateDimension.KNOWLEDGE],
        capacity_state=resolved[StateDimension.CAPACITY],
        state_model_version=state_model_version,
    )
    return RestartReconstruction(
        pre_restart=pre,
        composite=reconstruct_conservative(pre),
        store_complete=not filled,
        filled_dimensions=tuple(filled),
        discarded_caches=discarded,
    )
