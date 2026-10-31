"""Durable-set backup/restore tests (TOS Phase 5 W4 plan §2 decisions 1-2; ``marketfeed``
membership added by the tick-source wave, plan
``docs/plans/2026-09-16-tos-tick-source-plan.md`` §6 ④).

The full recompose-and-drill path (:func:`~tos_runtime.operations.backup_set.restore_drill`) is
exercised in ``tests/recovery/test_drill.py`` against a real ``compose_paper_runtime`` boot — this
module covers :func:`~tos_runtime.operations.backup_set.backup_set` and
:func:`~tos_runtime.operations.backup_set.restore_set` directly, against real (but standalone,
non-composed) evidence/RCL/inbox/marketfeed stores plus a synthetic composite-state file, so the
digest/generation/refusal mechanics are tested without needing a full boot for every case.
"""

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


#: The one venue result ``_build_live_set(with_venue_ledger=True)`` records, so the
#: restore assertions name a concrete row rather than merely a non-empty file.
_VENUE_ATTEMPT = "attempt-backup"
_VENUE_EXECUTION_ID = f"syn-exec:{_VENUE_ATTEMPT}:FULL_FILL"


def _build_live_set(
    data_dir: Path,
    *,
    with_entries: bool = True,
    with_marketfeed: bool = False,
    with_venue_ledger: bool = False,
) -> DurableSetPaths:
    """Build one real, closed durable set directly under ``data_dir`` (the SAME filenames
    :func:`~tos_runtime.operations.backup_set.DurableSetPaths.from_data_dir` expects).

    ``marketfeed`` mirrors ``composite_state``'s own optionality: most tests leave it absent
    (``with_marketfeed=False``, the default) to exercise the "never fabricate a backup for an
    absent optional member" path; the tests that need a real one pass ``with_marketfeed=True``.
    ``venue_ledger`` (#1011 P2) is optional for the same reason and then some: a boot whose
    ``finality.yaml`` does not select the venue-ledger witness never creates that file, which
    is every shipped tree today.
    """
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

    # Composite-state is kernel-owned and opaque to this package — a bare sqlite file with no
    # recognized shape is exactly what this module treats it as.
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


# -- backup_set ---------------------------------------------------------------------------------


def test_backup_set_writes_a_manifest_with_six_files_and_facts(tmp_path: Path) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(
        live_dir
    )  # marketfeed absent — the default, mirrors composite_state
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
            # Both absent in this fixture — asserted below. `venue_ledger` is absent on
            # every boot that does not set `finality.yaml::witness` (#1011 P2), which is
            # every shipped tree today.
            continue
        # composite_state IS present in this fixture (_build_live_set always creates it) —
        # only marketfeed is the absent-optional-member case here.
        assert entry is not None
        assert Path(entry.path).is_file()
        assert len(entry.file_digest) == 64  # sha256 hex

    assert manifest.evidence.last_seq == 1  # two entries appended, seq is 0-indexed
    assert manifest.evidence.event_consumed_count == 2
    assert manifest.rcl.writer_epoch == 1
    assert manifest.inbox.last_seq is None  # no events enqueued in this fixture
    composite_state_entry = manifest.files["composite_state"]
    assert composite_state_entry is not None
    assert composite_state_entry.last_seq is None  # kernel-owned — never queried
    assert manifest.files["marketfeed"] is None  # absent — never fabricated
    assert manifest.files["venue_ledger"] is None  # ditto (#1011 P2)

    manifest_path = backups_dir / "gen1.set.manifest.json"
    assert manifest_path.is_file()


def test_backup_set_includes_marketfeed_when_present(tmp_path: Path) -> None:
    """Membership: a marketfeed file that DOES exist at backup time is backed up like any other
    member — content-addressed, digested, and recorded — even though it has no ``seq`` column
    (``last_seq`` is honestly ``None``, the same way it is for ``composite_state``, but for a
    different reason — see ``_last_seq_for``'s own docstring)."""
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir, with_marketfeed=True)
    backups_dir = tmp_path / "backups"

    manifest = backup_set(paths, backups_dir, generation=1)

    entry = manifest.files["marketfeed"]
    assert entry is not None
    assert Path(entry.path).is_file()
    assert len(entry.file_digest) == 64  # sha256 hex
    assert (
        entry.last_seq is None
    )  # no seq column — optional for a different reason than absence


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

    # A strictly greater generation still succeeds.
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

    # Tamper with the manifest file name so _highest_existing_generation no longer sees gen1,
    # then try to reuse generation=1 — the pre-existing gen1/ directory must not be silently
    # overwritten. The refusal is NAMED now (it used to be a bare FileExistsError out of
    # `mkdir(exist_ok=False)`): the same invariant, said in words, because the caller that
    # hits this shape in production is an unattended one and a traceback told it nothing.
    (backups_dir / "gen1.set.manifest.json").unlink()
    with pytest.raises(BackupSetRefused) as refusal:
        backup_set(paths, backups_dir, generation=1)
    assert "already exists" in str(refusal.value)
    assert "died part-way" in str(refusal.value)
    # And it really did not delete or overwrite it.
    assert (backups_dir / "gen1" / "evidence.sqlite3").is_file()


def test_next_generation_steps_past_a_generation_that_was_attempted_but_never_finished(
    tmp_path: Path,
) -> None:
    """The manifest is written LAST, so a run that died mid-copy leaves a ``gen{N}/`` with no
    manifest. Counting manifests alone would hand that same N back to the next unattended run
    forever (and `backup_set` would refuse it, every time) — one transient fault becoming a
    permanent outage of the backup. Nothing is deleted; the number is skipped."""
    backups_dir = tmp_path / "backups"
    (backups_dir / "gen7").mkdir(parents=True)

    assert next_generation(backups_dir) == 8
    # The leftover is still there for an operator to look at.
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


# -- restore_set --------------------------------------------------------------------------------


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
    # marketfeed was absent at backup time (default fixture) — restored honestly as no file,
    # never fabricated.
    assert restored.paths.marketfeed == restore_dir / "marketfeed.sqlite3"
    assert not restored.paths.marketfeed.is_file()

    # The restored evidence store re-opens and verifies cleanly.
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

    # Mutate the BACKUP copy of the inbox file (what restore_set actually copies from).
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
    """A restored evidence store whose chain cannot verify under the supplied key provider
    raises the store's own EvidenceCorruption — restore_set does not swallow it."""
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


# -- marketfeed backup-set membership (tick-source wave, plan §6 ④) -----------------------------


def test_restore_set_refuses_on_a_mutated_marketfeed_digest(tmp_path: Path) -> None:
    """(M1) A marketfeed backup is verified the same as every other member — a flipped byte in
    the backup copy must refuse, never be silently accepted."""
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
    """Backward compatibility: a manifest whose ``files``/``source_paths`` carry no
    ``"marketfeed"`` key at all (the real shape of every manifest written before this wave) must
    restore cleanly — the restored set simply has no such file, never a fabricated one and never
    a bare ``KeyError``."""
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(
        live_dir
    )  # marketfeed absent — key still present pre-mutation below
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    manifest_path = backups_dir / "gen1.set.manifest.json"
    manifest_json = json.loads(manifest_path.read_text())
    assert (
        "marketfeed" in manifest_json["files"]
    )  # sanity: this wave's own code wrote it
    del manifest_json["files"]["marketfeed"]
    del manifest_json["source_paths"]["marketfeed"]
    manifest_path.write_text(json.dumps(manifest_json))

    restore_dir = tmp_path / "restored"
    restored = restore_set(manifest_path, restore_dir, key_provider=FixedKeyProvider())

    assert restored.paths.marketfeed == restore_dir / "marketfeed.sqlite3"
    assert not restored.paths.marketfeed.is_file()
    # The other four members are unaffected by the missing key.
    assert restored.paths.evidence.is_file()
    assert restored.paths.rcl.is_file()
    assert restored.paths.inbox.is_file()


def test_restore_set_marketfeed_republishes_a_pre_backup_snapshot_through_the_real_kernel(
    tmp_path: Path,
) -> None:
    """The restore-path mirror of lane B's own restart-durability proof
    (``tos/runtime/tests/marketfeed/test_store.py
    ::test_restart_durability_real_resolver_still_admits``): a snapshot issued and durably stored
    BEFORE a backup must still resolve through the REAL kernel
    :class:`~tos.marketfeed.MarketFeedContextResolver` after ``backup_set`` -> ``restore_set``
    into a fresh directory and a freshly opened :class:`~tos_runtime.marketfeed.store
    .SqliteSnapshotStore` over the restored file. This is exactly the failure mode marketfeed's
    backup-set membership exists to close (module docstring): without it, a restored deployment
    could not re-publish a view for any snapshot issued before the restore."""
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(
        live_dir
    )  # marketfeed file created below via the real store

    capsule, snapshot, payload = one_bar()
    producer = SqliteSnapshotStore(paths.marketfeed)
    producer.put(snapshot, {"raw-1": payload})
    producer.close()
    del producer  # the producing process/object is gone — only the file remains

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
    """Pin: every field of :class:`DurableSetPaths` must be handled by ``_last_seq_for`` — via a
    real seq-table lookup or via ``_OPTIONAL_FILES`` — and an unregistered name must fail LOUDLY
    and BY NAME, never a bare ``KeyError``. This is the fourth instance, within this one wave, of
    a registry paired with a hand-maintained satellite that nothing pinned together: the first was
    ``STORE_MIGRATIONS`` vs ``cli.py``'s hardcoded path dict (fixed by extracting
    ``compose/_migrate_paths.py``, pinned by ``tests/compose/test_cli.py``'s own
    ``set(MIGRATE_PATH_BY_STORE) == set(STORE_MIGRATIONS)``), the second/third were
    ``MARKETFEED_SCHEMA_VERSION`` vs ``MARKETFEED_MIGRATIONS[-1].version``. Naming the pattern
    here so it is not rediscovered a fifth time."""
    from tos_runtime.operations.backup_set import _last_seq_for

    # Any sqlite file works for the table-backed names: a file with none of the expected tables
    # answers None via _read_optional_int's own OperationalError handling, rather than raising —
    # this pin is about NAME coverage, not about real seq values (those are covered by the
    # backup_set()-level tests above).
    empty_db = tmp_path / "empty.sqlite3"
    sqlite3.connect(str(empty_db)).close()

    for name in DurableSetPaths.model_fields:
        _last_seq_for(name, empty_db)  # must not raise for any real member

    with pytest.raises(RuntimeError, match="nonexistent-store"):
        _last_seq_for("nonexistent-store", empty_db)


# ===========================================================================
# #1011 P2 (review-1018 L1) — the venue ledger as a backup-set member
# ===========================================================================


def test_a_set_containing_a_venue_ledger_backs_up_restores_and_reopens(
    tmp_path: Path,
) -> None:
    """The present case: back up a set WITH a venue ledger, restore it, reopen the store.

    Concrete input: a live set whose ``venue_ledger.sqlite3`` holds one recorded FULL_FILL.
    Concrete result: the manifest carries a digested entry for it (``last_seq`` honestly
    ``None`` — it is an optional member with no ``seq`` column this module queries), the
    restored file is byte-verified against that digest, and the restored file reopens through
    the REAL :class:`~tos_runtime.venue_ledger.synthetic.SyntheticVenueLedger` constructor,
    which re-runs the schema-ledger version check — so a restored ledger is a bootable one.

    Why it matters rather than being symmetry: on a synthetic tree the ledger IS the venue's
    record, and it is what decides whether a filled entry's capacity is ever released. A
    restored set without it fails closed (every reconciliation answers ``WitnessUnavailable``),
    but the deployment can then never close the entry it restored.
    """
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
    assert entry.last_seq is None  # optional member — never queried for a seq

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
    """Backward compatibility: every manifest taken from a tree running today has no key.

    Concrete input: a manifest with ``"venue_ledger"`` deleted from both ``files`` and
    ``source_paths`` — the real shape of every backup written before #1011 P2. Concrete
    result: the restored set is given the path with no file behind it, never a fabricated
    file and never a bare ``KeyError``, exactly as the pre-marketfeed case above.
    """
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    paths = _build_live_set(live_dir, with_venue_ledger=True)
    backups_dir = tmp_path / "backups"
    backup_set(paths, backups_dir, generation=1)

    manifest_path = manifest_path_for(backups_dir, 1)
    manifest_json = json.loads(manifest_path.read_text())
    assert "venue_ledger" in manifest_json["files"]  # sanity: this wave's code wrote it
    del manifest_json["files"]["venue_ledger"]
    del manifest_json["source_paths"]["venue_ledger"]
    manifest_path.write_text(json.dumps(manifest_json))

    restore_dir = tmp_path / "restored"
    restored = restore_set(manifest_path, restore_dir, key_provider=FixedKeyProvider())

    assert restored.paths.venue_ledger == restore_dir / VENUE_LEDGER_FILE_NAME
    assert not restored.paths.venue_ledger.is_file()
    # The members that WERE in that manifest are unaffected by the missing key.
    assert restored.paths.evidence.is_file()
    assert restored.paths.rcl.is_file()
    assert restored.paths.inbox.is_file()
