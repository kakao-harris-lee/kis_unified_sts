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

import contextlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransmissionAttemptState,
    reconstruct_conservative,
)
from tos.rcl import CapacityState
from tos.staterestore._wal import StoreJournalModeRefused
from tos.staterestore.store import DIMENSION_COMMIT_ORDER, CompositeStateStore

_EnumMarker = TypeVar(
    "_EnumMarker",
    IntentState,
    TransmissionAttemptState,
    BrokerOrderState,
    KnowledgeState,
    CapacityState,
)


def _typed_marker(value: object, enum_type: type[_EnumMarker]) -> _EnumMarker:
    """Narrow a dimension marker from ``object`` to its concrete dimension enum.

    Pure mypy narrowing, not a behavioural change: :meth:`CompositeStateStore.read_markers`
    already coerces every stored value through the dimension's own enum type
    (``_DIMENSION_ENUM`` in :mod:`tos.staterestore.store`) before returning it, and every
    :data:`ABSENT_DIMENSION_FILL` entry is itself built from that same enum — so at each
    call site in :func:`reload_conservative` ``value`` is already guaranteed to be an
    ``enum_type`` member. mypy cannot see that guarantee through the heterogeneous
    ``dict[StateDimension, object]`` typing shared by ``markers`` and
    ``ABSENT_DIMENSION_FILL`` (five differently-typed dimensions in one dict), so this
    isinstance check makes the invariant executable — a real violation raises rather than
    being papered over by a cast.

    Raises:
        TypeError: If ``value`` is not an ``enum_type`` member (would indicate a
            ``staterestore.store`` / ``ABSENT_DIMENSION_FILL`` invariant violation, not a
            reachable outcome of normal reload).
    """
    if not isinstance(value, enum_type):
        raise TypeError(
            f"expected a {enum_type.__name__} member, got {value!r} — "
            "staterestore.store / ABSENT_DIMENSION_FILL invariant violated"
        )
    return value


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


class StoreOpenRefused(RuntimeError):
    """The durable store could not be OPENED — a substrate refusal, not a verdict.

    Raised only around :class:`~tos.staterestore.store.CompositeStateStore`'s
    construction (review round-2 F4), and chained onto whatever sqlite or
    :class:`~tos.staterestore.StoreJournalModeRefused` actually raised. Its whole job is
    to be distinguishable from the two findings this module produces about a store it
    DID read — :class:`IncompleteStoreError` and
    :class:`~tos.staterestore.store.StoreIntegrityError` — so a caller classifying
    outcomes cannot collapse "there was no store to read" into "this is what the store
    said".
    """


def open_store(path: Path) -> CompositeStateStore:
    """Open the durable store, or refuse with :class:`StoreOpenRefused`.

    **The one open boundary** (review round-3 F8). ``run_reader`` reached it through
    :func:`reload_conservative` while ``run_writer`` had its own copy of the same
    ``try``/``except`` tuple and the same message; finding 3 then required widening
    that tuple, in two places, with nothing holding them together. There is one now,
    and both callers catch one type.

    The OPEN and the READ are separate on purpose (review round-2 F4). They fail for
    different reasons and a caller must be able to tell them apart: a store that cannot
    be opened is a substrate finding, while anything raised after a successful open — a
    malformed page, a column that is not there — is a finding ABOUT a store that WAS
    read, which is what this package exists to produce.

    Args:
        path: The store file. Its parent is created by the constructor, so a parent
            that cannot be made is an open failure like any other.

    Raises:
        StoreOpenRefused: The store could not be opened, chained onto the underlying
            error. Three families reach this, and the third is the one review round-3
            F3 found escaping: the fail-closed WAL switch
            (:class:`~tos.staterestore.StoreJournalModeRefused`), sqlite itself
            (:class:`sqlite3.Error` — a lock contest, a read-only file, a path sqlite
            cannot open), and the filesystem (:class:`OSError` from the parent
            ``mkdir`` — a parent that is a regular file, or one that may not be written,
            both of which raise BEFORE ``sqlite3.connect`` is ever called).
    """
    try:
        return CompositeStateStore(path)
    except (StoreJournalModeRefused, sqlite3.Error, OSError) as exc:
        raise StoreOpenRefused(
            f"the composite-state store at {path} could not be opened on the WAL "
            f"substrate this package is defined over: {type(exc).__name__}: {exc}"
        ) from exc


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
        cache_paths: Optimistic caches to discard before re-deriving (S-3). Discarded
            only once the store has been opened — a refused open leaves them in place
            (review round-3 F4).
        state_model_version: Carried onto the rebuilt composite when known.

    Returns:
        The :class:`RestartReconstruction`.

    Raises:
        IncompleteStoreError: If the Intent dimension is absent (unidentifiable record).
        tos.staterestore.store.StoreIntegrityError: If a stored marker is unreadable.
        StoreOpenRefused: If the store could not be OPENED — the fail-closed
            ``journal_mode=WAL`` switch refused (#823), its lock could not be taken, or
            sqlite could not open the file at all. Chained onto the underlying error.
            A read-only store file lands here with ``attempt to write a readonly
            database``, as it did before #823 (measured on both trees: the bare
            ``PRAGMA journal_mode=WAL`` raised the same error at the same statement).
        sqlite3.Error: Raised unchanged by the READ, after a successful open — a
            malformed page, a missing column. Deliberately not wrapped: it is a finding
            about a store that was opened (review round-2 F4).
    """
    # OPEN FIRST, then discard (review round-3 F4). Discarding is irreversible — the
    # files are unlinked — and a refused open is now a distinguishable, retryable
    # condition (:class:`StoreOpenRefused`, added so a supervisor could tell a lock
    # contest from a verdict). Discarding before the open destroyed the optimistic
    # caches on the way to telling the caller the open had failed, so a retry ran
    # against a tree whose cache evidence was already gone and the eventual
    # ``discarded_caches`` no longer said what had really been there.
    #
    # S-3 is unaffected: the discard still happens before anything is READ, and nothing
    # in this module consults a cache on any path, so "re-derived from evidence alone"
    # does not depend on which of the two statements comes first.
    store = open_store(Path(store_path))
    discarded = discard_caches(cache_paths)
    with contextlib.closing(store):
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
        intent_state=_typed_marker(markers[StateDimension.INTENT], IntentState),
        transmission_attempt_state=_typed_marker(
            resolved[StateDimension.TRANSMISSION_ATTEMPT], TransmissionAttemptState
        ),
        broker_order_state=_typed_marker(
            resolved[StateDimension.BROKER_ORDER], BrokerOrderState
        ),
        knowledge_state=_typed_marker(
            resolved[StateDimension.KNOWLEDGE], KnowledgeState
        ),
        capacity_state=_typed_marker(resolved[StateDimension.CAPACITY], CapacityState),
        state_model_version=state_model_version,
    )
    return RestartReconstruction(
        pre_restart=pre,
        composite=reconstruct_conservative(pre),
        store_complete=not filled,
        filled_dimensions=tuple(filled),
        discarded_caches=discarded,
    )
