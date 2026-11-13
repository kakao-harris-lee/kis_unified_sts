"""Resolve migration-store keys to their configured SQLite paths."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tos_runtime.marketfeed.store import MARKETFEED_FILE_NAME
from tos_runtime.operations.backup_set import DurableSetPaths

__all__ = [
    "MIGRATE_PATH_BY_STORE",
    "migrate_path_for",
]

MIGRATE_PATH_BY_STORE: dict[str, Callable[[DurableSetPaths, Path], Path]] = {
    "evidence": lambda paths, _data_dir: paths.evidence,
    "rcl": lambda paths, _data_dir: paths.rcl,
    "inbox": lambda paths, _data_dir: paths.inbox,
    "marketfeed": lambda _paths, data_dir: data_dir / MARKETFEED_FILE_NAME,
    "venue_ledger": lambda paths, _data_dir: paths.venue_ledger,
}


def migrate_path_for(
    store_name: str, *, paths: DurableSetPaths, data_dir: Path
) -> Path:
    """The file ``migrate`` should open for ``store_name``. Refuses BY NAME"""
    resolve_path = MIGRATE_PATH_BY_STORE.get(store_name)
    if resolve_path is None:
        raise RuntimeError(
            f"migrate: no path resolver registered for store {store_name!r}"
        )
    return resolve_path(paths, data_dir)
