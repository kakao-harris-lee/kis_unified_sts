"""S-2 / S-3 — the restart read path: conservative fill, then re-derivation."""

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
    """Narrow a dimension marker from ``object`` to its concrete dimension enum."""
    if not isinstance(value, enum_type):
        raise TypeError(
            f"expected a {enum_type.__name__} member, got {value!r} — "
            "staterestore.store / ABSENT_DIMENSION_FILL invariant violated"
        )
    return value


ABSENT_DIMENSION_FILL: dict[StateDimension, object] = {
    StateDimension.TRANSMISSION_ATTEMPT: TransmissionAttemptState.NONE,
    StateDimension.BROKER_ORDER: BrokerOrderState.UNKNOWN,
    StateDimension.KNOWLEDGE: KnowledgeState.UNOBSERVED,
    StateDimension.CAPACITY: CapacityState.POTENTIALLY_LIVE,
}


class StoreOpenRefused(RuntimeError):
    """The durable store could not be OPENED — a substrate refusal, not a verdict."""


def open_store(path: Path) -> CompositeStateStore:
    """Open the durable store, or refuse with :class:`StoreOpenRefused`."""
    try:
        return CompositeStateStore(path)
    except (StoreJournalModeRefused, sqlite3.Error, OSError) as exc:
        raise StoreOpenRefused(
            f"the composite-state store at {path} could not be opened on the WAL "
            f"substrate this package is defined over: {type(exc).__name__}: {exc}"
        ) from exc


class IncompleteStoreError(RuntimeError):
    """The store cannot identify the record it holds (fail-closed)."""


@dataclass(frozen=True)
class RestartReconstruction:
    """The outcome of one restart reload (design #39 §5.1 S-2)."""

    pre_restart: CompositeState
    composite: CompositeState
    store_complete: bool
    filled_dimensions: tuple[StateDimension, ...]
    discarded_caches: tuple[str, ...]


def discard_caches(cache_paths: tuple[Path, ...] | list[Path]) -> tuple[str, ...]:
    """Discard resume-time caches (S-3) and report which ones existed."""
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
    """Re-derive a conservative post-restart composite from the durable store alone."""
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
            continue
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
