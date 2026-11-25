"""Durable-set backup/restore tests (TOS Phase 5 W4 plan §2 decisions 1-2; ``marketfeed``"""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from tos.marketfeed import MarketFeedContextResolver
from tos.marketfeed.vocabulary import ValueViewDisposition
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.marketfeed.store import MARKETFEED_FILE_NAME, SqliteSnapshotStore
from tos_runtime.operations.backup_set import (
    BackupSetRefused,
    DurableSetPaths,
    RestoreRefused,
    backup_set,
    manifest_path_for,
    next_generation,
    restore_set,
)
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.venue_ledger.synthetic import (
    VENUE_LEDGER_FILE_NAME,
    SyntheticVenueLedger,
    VenueLedgerReader,
)

from ..marketfeed._store_fixtures import INSTRUMENT_KEY, one_bar
from ..marketfeed._store_fixtures import SCHEME as MARKETFEED_SCHEME
from .conftest import SCHEME, FixedKeyProvider

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


_VENUE_ATTEMPT = "attempt-backup"
_VENUE_EXECUTION_ID = f"syn-exec:{_VENUE_ATTEMPT}:FULL_FILL"


def _build_live_set(
    data_dir: Path,
    *,
    with_entries: bool = True,
    with_marketfeed: bool = False,
    with_venue_ledger: bool = False,
) -> DurableSetPaths:
    """Build one real, closed durable set directly under ``data_dir`` (the SAME filenames"""
    key_provider = FixedKeyProvider()
    evidence = SqliteEvidenceStore(
        data_dir / "evidence.sqlite3", key_provider=key_provider
    )
    if with_entries:
        evidence.append({"n": 1}, kind="EVENT_CONSUMED", record_class="EVENT_CONSUMED")
        evidence.append({"n": 2}, kind="EVENT_CONSUMED", record_class="EVENT_CONSUMED")
    rcl = SqliteCommitLog(data_dir / "rcl.sqlite3", evidence_port=evidence)
    if with_entries:
        rcl.acquire_epoch(_fake_identity())
    inbox = SqliteEventInbox(data_dir / "inbox.sqlite3", scheme=SCHEME)
    evidence.close()
    rcl.close()
    inbox.close()

    composite_conn = sqlite3.connect(str(data_dir / "composite_state.sqlite3"))
    composite_conn.close()

    if with_marketfeed:
        marketfeed_store = SqliteSnapshotStore(data_dir / MARKETFEED_FILE_NAME)
        marketfeed_store.close()

    if with_venue_ledger:
        ledger = SyntheticVenueLedger(data_dir / VENUE_LEDGER_FILE_NAME)
        ledger.record(
            attempt_id=_VENUE_ATTEMPT,
            broker_execution_id=_VENUE_EXECUTION_ID,
            account="acct-backup",
            instrument="101W12",
            side="BUY",
            quantity=Decimal("1"),
            filled_quantity=Decimal("1"),
            remaining_quantity=Decimal("0"),
            result_kind="FULL_FILL",
            trading_date="20261031",
        )
        ledger.close()

    return DurableSetPaths.from_data_dir(data_dir)


def _fake_identity():
    from tos.workload import RuntimeIdentity

    return RuntimeIdentity(
        cell_id="cell-1",
        runtime_generation=1,
        process_nonce="nonce-1",
        code_digest="digest-1",
    )


def test_backup_set_writes_a_manifest_with_six_files_and_facts(tmp_path: Path) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"

    manifest = backup_set(paths, backups_dir, generation=1)

    assert manifest.generation == 1
    assert set(manifest.files) == {
        "evidence",
        "rcl",
        "inbox",
        "composite_state",
        "marketfeed",
        "venue_ledger",
    }
    for name, entry in manifest.files.items():
        if name in ("marketfeed", "venue_ledger"):
            continue
        assert entry is not None
        assert Path(entry.path).is_file()
        assert len(entry.file_digest) == 64

    assert manifest.evidence.last_seq == 1
    assert manifest.evidence.event_consumed_count == 2
    assert manifest.rcl.writer_epoch == 1
    assert manifest.inbox.last_seq is None
    composite_state_entry = manifest.files["composite_state"]
    assert composite_state_entry is not None
    assert composite_state_entry.last_seq is None
    assert manifest.files["marketfeed"] is None
    assert manifest.files["venue_ledger"] is None

    manifest_path = backups_dir / "gen1.set.manifest.json"
    assert manifest_path.is_file()


def test_backup_set_includes_marketfeed_when_present(tmp_path: Path) -> None:
    """Membership: a marketfeed file that DOES exist at backup time is backed up like any other"""
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir, with_marketfeed=True)
    backups_dir = tmp_path / "backups"

    manifest = backup_set(paths, backups_dir, generation=1)

    entry = manifest.files["marketfeed"]
    assert entry is not None
    assert Path(entry.path).is_file()
    assert len(entry.file_digest) == 64
    assert entry.last_seq is None


def test_backup_set_refuses_a_non_increasing_generation(tmp_path: Path) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"

    backup_set(paths, backups_dir, generation=5)

    with pytest.raises(BackupSetRefused, match="strictly greater"):
        backup_set(paths, backups_dir, generation=5)
    with pytest.raises(BackupSetRefused, match="strictly greater"):
        backup_set(paths, backups_dir, generation=3)

    manifest = backup_set(paths, backups_dir, generation=6)
    assert manifest.generation == 6


def test_backup_set_refuses_a_missing_source_file(tmp_path: Path) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    (live_dir / "inbox.sqlite3").unlink()

    with pytest.raises(BackupSetRefused, match="inbox"):
        backup_set(paths, tmp_path / "backups", generation=1)


def test_backup_set_never_deletes_an_existing_generation_directory(
    tmp_path: Path,
) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    (backups_dir / "gen1.set.manifest.json").unlink()
    with pytest.raises(BackupSetRefused) as refusal:
        backup_set(paths, backups_dir, generation=1)
    assert "already exists" in str(refusal.value)
    assert "died part-way" in str(refusal.value)
    assert (backups_dir / "gen1" / "evidence.sqlite3").is_file()


def test_next_generation_steps_past_a_generation_that_was_attempted_but_never_finished(
    tmp_path: Path,
) -> None:
    """The manifest is written LAST, so a run that died mid-copy leaves a ``gen{N}/`` with no"""
    backups_dir = tmp_path / "backups"
    (backups_dir / "gen7").mkdir(parents=True)

    assert next_generation(backups_dir) == 8
    assert (backups_dir / "gen7").is_dir()


def test_next_generation_takes_the_higher_of_manifest_and_directory(
    tmp_path: Path,
) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=3)
    assert next_generation(backups_dir) == 4

    (backups_dir / "gen9").mkdir()
    assert next_generation(backups_dir) == 10


def test_next_generation_is_one_for_an_absent_or_empty_directory(
    tmp_path: Path,
) -> None:
    assert next_generation(tmp_path / "nothing-here") == 1
    (tmp_path / "empty").mkdir()
    assert next_generation(tmp_path / "empty") == 1


def test_restore_set_round_trips_and_verifies_the_evidence_chain(
    tmp_path: Path,
) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"
    manifest = backup_set(paths, backups_dir, generation=1)

    restore_dir = tmp_path / "restored"
    restored = restore_set(
        backups_dir / "gen1.set.manifest.json",
        restore_dir,
        key_provider=FixedKeyProvider(),
    )

    assert restored.non_live is True
    assert restored.manifest.generation == manifest.generation
    for name in ("evidence", "rcl", "inbox", "composite_state"):
        assert getattr(restored.paths, name).is_file()
    assert restored.paths.marketfeed == restore_dir / "marketfeed.sqlite3"
    assert not restored.paths.marketfeed.is_file()

    reopened = SqliteEvidenceStore(
        restored.paths.evidence, key_provider=FixedKeyProvider()
    )
    key_generation, key_bytes = FixedKeyProvider().current()
    assert reopened.verify({key_generation: key_bytes}) is True
    reopened.close()


def test_restore_set_refuses_when_destination_is_the_live_data_dir(
    tmp_path: Path,
) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    with pytest.raises(RestoreRefused, match="live source data directory"):
        restore_set(
            backups_dir / "gen1.set.manifest.json",
            live_dir,
            key_provider=FixedKeyProvider(),
        )


def test_restore_set_refuses_when_destination_is_inside_the_live_data_dir(
    tmp_path: Path,
) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    nested = live_dir / "nested-restore"
    with pytest.raises(RestoreRefused, match="live source data directory"):
        restore_set(
            backups_dir / "gen1.set.manifest.json",
            nested,
            key_provider=FixedKeyProvider(),
        )


def test_restore_set_refuses_on_a_mutated_restored_file_digest(tmp_path: Path) -> None:
    """(M1) One byte flipped in a restored file must refuse — never silently accepted."""
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    backup_inbox_path = backups_dir / "gen1" / "inbox.sqlite3"
    raw = bytearray(backup_inbox_path.read_bytes())
    raw[-1] ^= 0xFF
    backup_inbox_path.write_bytes(bytes(raw))

    with pytest.raises(RestoreRefused, match="mutation M1"):
        restore_set(
            backups_dir / "gen1.set.manifest.json",
            tmp_path / "restored",
            key_provider=FixedKeyProvider(),
        )


def test_restore_set_refuses_when_evidence_key_generation_disagrees(
    tmp_path: Path,
) -> None:
    """A restored evidence store whose chain cannot verify under the supplied key provider"""
    from tos_runtime.evidence.store import EvidenceCorruption

    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    wrong_key_provider = FixedKeyProvider(
        key_generation=1, key=b"a-completely-different-key"
    )
    with pytest.raises(EvidenceCorruption):
        restore_set(
            backups_dir / "gen1.set.manifest.json",
            tmp_path / "restored",
            key_provider=wrong_key_provider,
        )


def test_restore_set_refuses_on_a_mutated_marketfeed_digest(tmp_path: Path) -> None:
    """(M1) A marketfeed backup is verified the same as every other member — a flipped byte in"""
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir, with_marketfeed=True)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    backup_marketfeed_path = backups_dir / "gen1" / "marketfeed.sqlite3"
    raw = bytearray(backup_marketfeed_path.read_bytes())
    raw[-1] ^= 0xFF
    backup_marketfeed_path.write_bytes(bytes(raw))

    with pytest.raises(RestoreRefused, match="mutation M1"):
        restore_set(
            backups_dir / "gen1.set.manifest.json",
            tmp_path / "restored",
            key_provider=FixedKeyProvider(),
        )


def test_restore_set_handles_a_manifest_written_before_marketfeed_joined_the_set(
    tmp_path: Path,
) -> None:
    """Backward compatibility: a manifest whose ``files``/``source_paths`` carry no"""
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    manifest_path = backups_dir / "gen1.set.manifest.json"
    manifest_json = json.loads(manifest_path.read_text())
    assert "marketfeed" in manifest_json["files"]
    del manifest_json["files"]["marketfeed"]
    del manifest_json["source_paths"]["marketfeed"]
    manifest_path.write_text(json.dumps(manifest_json))

    restore_dir = tmp_path / "restored"
    restored = restore_set(manifest_path, restore_dir, key_provider=FixedKeyProvider())

    assert restored.paths.marketfeed == restore_dir / "marketfeed.sqlite3"
    assert not restored.paths.marketfeed.is_file()
    assert restored.paths.evidence.is_file()
    assert restored.paths.rcl.is_file()
    assert restored.paths.inbox.is_file()


def test_restore_set_marketfeed_republishes_a_pre_backup_snapshot_through_the_real_kernel(
    tmp_path: Path,
) -> None:
    """The restore-path mirror of lane B's own restart-durability proof"""
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir)

    capsule, snapshot, payload = one_bar()
    producer = SqliteSnapshotStore(paths.marketfeed)
    producer.put(snapshot, {"raw-1": payload})
    producer.close()
    del producer

    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    restore_dir = tmp_path / "restored"
    restored = restore_set(
        backups_dir / "gen1.set.manifest.json",
        restore_dir,
        key_provider=FixedKeyProvider(),
    )
    assert restored.paths.marketfeed.is_file()

    reopened = SqliteSnapshotStore(restored.paths.marketfeed)
    resolver = MarketFeedContextResolver(
        snapshot_store=reopened,
        candidate_source=reopened.candidates,
        scheme=MARKETFEED_SCHEME,
    )

    resolved = resolver.resolve(capsule, instrument_key=INSTRUMENT_KEY)

    assert resolved.resolution.disposition == ValueViewDisposition.RESOLVED
    assert resolved.value_surface_published is True
    assert resolved.resolution.view is not None
    values_by_key = {
        value.field_key: value for value in resolved.resolution.view.values
    }
    assert values_by_key["close"].value == 4_512_500
    assert (
        values_by_key["close"].payload_digest
        == snapshot.observations[0].raw.payload_digest
    )
    reopened.close()


def test_last_seq_for_handles_every_durable_set_paths_member(tmp_path: Path) -> None:
    """Pin: every field of :class:`DurableSetPaths` must be handled by ``_last_seq_for`` — via a"""
    from tos_runtime.operations.backup_set import _last_seq_for

    empty_db = tmp_path / "empty.sqlite3"
    sqlite3.connect(str(empty_db)).close()

    for name in DurableSetPaths.model_fields:
        _last_seq_for(name, empty_db)

    with pytest.raises(RuntimeError, match="nonexistent-store"):
        _last_seq_for("nonexistent-store", empty_db)


def test_a_set_containing_a_venue_ledger_backs_up_restores_and_reopens(
    tmp_path: Path,
) -> None:
    """The present case: back up a set WITH a venue ledger, restore it, reopen the store."""
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir, with_venue_ledger=True)
    assert paths.venue_ledger.is_file()
    backups_dir = tmp_path / "backups"

    manifest = backup_set(paths, backups_dir, generation=1)

    entry = manifest.files["venue_ledger"]
    assert entry is not None
    assert Path(entry.path).is_file()
    assert len(entry.file_digest) == 64
    assert entry.last_seq is None

    restore_dir = tmp_path / "restored"
    restored = restore_set(
        manifest_path_for(backups_dir, 1), restore_dir, key_provider=FixedKeyProvider()
    )

    assert restored.paths.venue_ledger == restore_dir / VENUE_LEDGER_FILE_NAME
    assert restored.paths.venue_ledger.is_file()

    reopened = SyntheticVenueLedger(restored.paths.venue_ledger)
    try:
        fills = VenueLedgerReader(restored.paths.venue_ledger).fills()
    finally:
        reopened.close()
    assert [fill.attempt_id for fill in fills] == [_VENUE_ATTEMPT]
    assert fills[0].broker_execution_id == _VENUE_EXECUTION_ID
    assert fills[0].filled_quantity == Decimal("1")


def test_restore_set_handles_a_manifest_written_before_the_venue_ledger_joined_the_set(
    tmp_path: Path,
) -> None:
    """Backward compatibility: every manifest taken from a tree running today has no key."""
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir, with_venue_ledger=True)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    manifest_path = manifest_path_for(backups_dir, 1)
    manifest_json = json.loads(manifest_path.read_text())
    assert "venue_ledger" in manifest_json["files"]
    del manifest_json["files"]["venue_ledger"]
    del manifest_json["source_paths"]["venue_ledger"]
    manifest_path.write_text(json.dumps(manifest_json))

    restore_dir = tmp_path / "restored"
    restored = restore_set(manifest_path, restore_dir, key_provider=FixedKeyProvider())

    assert restored.paths.venue_ledger == restore_dir / VENUE_LEDGER_FILE_NAME
    assert not restored.paths.venue_ledger.is_file()
    assert restored.paths.evidence.is_file()
    assert restored.paths.rcl.is_file()
    assert restored.paths.inbox.is_file()
