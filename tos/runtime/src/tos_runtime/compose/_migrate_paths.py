"""Resolve migration-store keys to their configured SQLite paths.

``MIGRATE_PATH_BY_STORE`` is the single mapping used by the CLI migration
command. ``migrate_path_for`` rejects unknown keys instead of falling back to
a hardcoded path, and the mapping is kept in one module so it can be checked
against ``STORE_MIGRATIONS`` without duplicating path logic.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tos_runtime.marketfeed.store import MARKETFEED_FILE_NAME
from tos_runtime.operations.backup_set import DurableSetPaths

__all__ = [
    "MIGRATE_PATH_BY_STORE",
    "migrate_path_for",
]

#: Path resolver per ``STORE_MIGRATIONS`` key; pinned equal to it by ``tests/compose/test_cli.py``.
#: ``marketfeed`` is not a backup-set member, so it derives straight from ``data_dir`` instead of
#: :class:`~tos_runtime.operations.backup_set.DurableSetPaths` — see
#: :mod:`tos_runtime.marketfeed.store`'s own ``MARKETFEED_FILE_NAME`` docstring for why.
MIGRATE_PATH_BY_STORE: dict[str, Callable[[DurableSetPaths, Path], Path]] = {
    "evidence": lambda paths, _data_dir: paths.evidence,
    "rcl": lambda paths, _data_dir: paths.rcl,
    "inbox": lambda paths, _data_dir: paths.inbox,
    "marketfeed": lambda _paths, data_dir: data_dir / MARKETFEED_FILE_NAME,
}


def migrate_path_for(
    store_name: str, *, paths: DurableSetPaths, data_dir: Path
) -> Path:
    """The file ``migrate`` should open for ``store_name``. Refuses BY NAME
    (:class:`RuntimeError` naming ``store_name``), never a bare ``KeyError``, when
    ``store_name`` has no entry in :data:`MIGRATE_PATH_BY_STORE` — this module's own docstring
    explains why that distinction is the whole point of this module existing.
    """
    resolve_path = MIGRATE_PATH_BY_STORE.get(store_name)
    if resolve_path is None:
        raise RuntimeError(
            f"migrate: no path resolver registered for store {store_name!r}"
        )
    return resolve_path(paths, data_dir)
