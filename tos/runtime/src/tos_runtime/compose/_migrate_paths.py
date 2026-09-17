"""``tos_runtime.compose._migrate_paths`` — path resolution for the ``migrate`` CLI subcommand
(the SAME "``cli.py``'s size budget pushed a print-only helper here" idiom
:mod:`tos_runtime.compose._cli_ops` already uses for :func:`~tos_runtime.compose._cli_ops
.rearm_and_clear` / :func:`~tos_runtime.compose._cli_ops.risk_state_policy_digest_lines`).

**Why this exists as its own module, not inline in ``cli.py``.** Two reasons, landed together
(tick-source wave, lane B fix): (1) ``compose/cli.py``'s own ``migrate`` dispatch resolved each
:data:`~tos_runtime.operations.schema_migrations.STORE_MIGRATIONS` key's path from a hardcoded
dict that only ever listed ``evidence``/``rcl``/``inbox`` — when ``"marketfeed"`` joined
``STORE_MIGRATIONS``, that dict was never updated, and ``migrate`` (with no ``--store`` given)
raised a bare ``KeyError`` deep inside the dispatch loop instead of running. (2) ``cli.py`` was
already sitting at exactly its 1000-line size budget (``config/tos_size_budget.yaml``) before
this fix — zero headroom, so any new code there, however small, pushed it over. Extracting the
path resolver here (rather than registering the runtime tree's first size-budget exception, which
the tick-source wave plan explicitly rules out) fixes the DRIFT CLASS, not just this one instance,
and leaves ``cli.py`` with headroom for the next change too.

:data:`MIGRATE_PATH_BY_STORE` resolves every :data:`~tos_runtime.operations.schema_migrations
.STORE_MIGRATIONS` key to the file ``migrate`` should open; :func:`migrate_path_for` is the
lookup :mod:`tos_runtime.compose.cli` calls, and refuses BY NAME (naming the unresolved store) on
a key with no matching entry — never a bare ``KeyError`` from inside a loop. ``tests/compose
/test_cli.py`` pins ``set(MIGRATE_PATH_BY_STORE) == set(STORE_MIGRATIONS)`` so the two can never
drift apart again.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``collections.abc``,
``pathlib``) + ``tos_runtime.marketfeed.store`` + ``tos_runtime.operations.backup_set`` only.
No ``shared.*``.
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
