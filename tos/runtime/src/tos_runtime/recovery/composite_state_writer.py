"""``CompositeStateWriter`` — persists a projected orthostate ``CompositeState`` into the kernel"""

from __future__ import annotations

from pathlib import Path

from tos.orthostate import CompositeState
from tos.staterestore import CompositeStateStore

__all__ = ["COMPOSITE_STATE_STORE_FILE_NAME", "CompositeStateWriter"]

COMPOSITE_STATE_STORE_FILE_NAME = "composite_state.sqlite3"


class CompositeStateWriter:
    """Persists a projected :class:`~tos.orthostate.CompositeState` into a"""

    def __init__(self, store_path: Path) -> None:
        """Bind this writer to a store file path."""
        self._store_path = Path(store_path)

    def __call__(self, attempt_id: str, composite: CompositeState) -> None:
        """Durably commit ``composite``'s five dimensions under ``attempt_id`` (module"""
        keyed = composite.model_copy(update={"intent_identity": attempt_id})
        with CompositeStateStore(self._store_path) as store:
            store.commit_composite(keyed)
