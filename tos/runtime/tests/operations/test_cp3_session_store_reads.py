"""The tos half of the CP-3 §3.6 extractor hinge: the columns it reads exist.

``tools/tos_cp3/session_inputs.py`` (CP-3 plan 2026-10-10 §3.6, PR-3) reads a
tenant session's ``marketfeed.sqlite3`` and ``evidence.sqlite3`` as plain
sqlite files to produce B3's two session-derived inputs. It cannot import
``tos_runtime`` — the firewall is bidirectional — and this package cannot
import ``tools``, so neither side can check the other directly.

The committed fixture ``fixtures/cp3-session-store-reads.json`` is the hinge:

* here — every (table, column) it names is one the registered migrations for
  that store actually declare, and the ``schema_version`` it names is the
  latest version those migrations reach;
* in ``tests/tools/test_cp3_session_inputs.py`` — the extractor's pinned
  versions are these, and the stores its tests build carry exactly these
  columns.

Either half failing alone is drift this repo would otherwise find at the first
genesis session's post-mortem, where the extractor would raise
``no such column`` against a store nobody could re-run.

Hermetic (D1.4): reads one committed file and some module constants, writes
nothing, opens no socket.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from tos_runtime.evidence.store import EVIDENCE_SCHEMA_VERSION
from tos_runtime.marketfeed.store import (
    MARKETFEED_FILE_NAME,
    MARKETFEED_SCHEMA_VERSION,
)
from tos_runtime.operations.backup_set import EVIDENCE_FILE_NAME
from tos_runtime.operations.schema_migrations import STORE_MIGRATIONS

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "cp3-session-store-reads.json"
)

#: ``store name in STORE_MIGRATIONS`` -> ``(file name, running schema version)``
#: as the two store modules themselves declare them.
DECLARED = {
    "marketfeed": (MARKETFEED_FILE_NAME, MARKETFEED_SCHEMA_VERSION),
    "evidence": (EVIDENCE_FILE_NAME, EVIDENCE_SCHEMA_VERSION),
}


@pytest.fixture(scope="module")
def pinned() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return document


@pytest.mark.parametrize("store", sorted(DECLARED))
def test_the_extractor_pins_this_stores_file_name_and_version(
    store: str, pinned: dict[str, Any]
) -> None:
    """The file name and schema version the extractor was written against.

    Concrete failing input: an ``EVIDENCE_SCHEMA_VERSION`` bump to 3. The
    extractor pins 2 and would refuse every session store on this host with
    "pinned to 2" — correct behaviour, but nobody would learn why until a
    genesis post-mortem. This turns that bump red in the PR that makes it.
    """
    file_name, version = DECLARED[store]
    assert pinned[store]["file_name"] == file_name
    assert pinned[store]["schema_version"] == version
    assert version == max(
        migration.version for migration in STORE_MIGRATIONS[store]
    ), "the store's running version is not the latest registered migration"


@pytest.mark.parametrize("store", sorted(DECLARED))
def test_every_column_the_extractor_reads_is_one_the_migrations_declare(
    store: str, pinned: dict[str, Any]
) -> None:
    """Column-level, not table-level: a rename is the drift that matters.

    Concrete failing input: ``preimages.raw_event_id`` renamed to
    ``observation_id``. Both tables still exist, the version may or may not
    move, and the extractor's ``SELECT snapshot_id, raw_event_id FROM
    preimages`` becomes a sqlite ``OperationalError`` against a real session —
    after the session, when it cannot be re-run.
    """
    declared: dict[str, set[str]] = {}
    for migration in STORE_MIGRATIONS[store]:
        for table, columns in migration.expected_tables.items():
            declared.setdefault(table, set()).update(columns)
    for table, columns in pinned[store]["reads"].items():
        assert (
            table in declared
        ), f"{store}.{table} is not a table these migrations create"
        missing = sorted(set(columns) - declared[table])
        assert not missing, f"{store}.{table} no longer declares {missing}"
