"""Config-driven cold-backup tests (evidence growth plan §2 A3,
``docs/plans/2026-09-29-tos-evidence-growth-and-purge-plan.md``).

Covers :func:`~tos_runtime.operations.cold_backup.cold_backup` and its loader against a real
(but standalone, non-composed) durable set — the same ``_build_live_set`` fixture
``tests/operations/test_backup_set.py`` owns and ``test_backup_archive.py`` already reuses, so
the three suites cannot drift about what a durable set is.

What this suite is NOT re-testing: the archive's own round-trip refusals (byte rot, a swapped
member, a checkless container, trailing bytes) all belong to
:mod:`~tos_runtime.operations.backup_archive` and are proven in ``test_backup_archive.py``.
What IS tested here is that a cold copy stored by this module can be re-checked later and
refuses when it has rotted — the operational reason the archive is kept at all — plus the four
things this module adds on top: generation allocation, destination refusals, the capacity
floor, and the report.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.custody.ports import CustodyLoadRefused
from tos_runtime.evidence.store import EvidenceCorruption
from tos_runtime.operations import cold_backup as cold_backup_module
from tos_runtime.operations.backup_archive import BackupArchiveRefused, verify_archive
from tos_runtime.operations.backup_set import next_generation
from tos_runtime.operations.cold_backup import (
    ColdBackupConfig,
    ColdBackupFailed,
    ColdBackupRefused,
    ColdBackupReport,
    FilesystemFreeSpace,
    cold_backup,
    load_cold_backup_config,
)
from tos_runtime.operations.key_rotation import KeyContinuityRefused
from tos_runtime.operations.schema_ledger import SchemaVersionRefused

from .conftest import FixedKeyProvider
from .test_backup_set import _build_live_set

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: Small enough that a tmpfs/tmp_path filesystem always clears it.
_FLOOR = 1024


def _config(tmp_path: Path, **overrides: object) -> ColdBackupConfig:
    fields: dict[str, object] = {
        "backup_root": tmp_path / "backups",
        "archive_dir": tmp_path / "cold",
        "verify_root": tmp_path / "verify",
        "minimum_free_bytes": _FLOOR,
        "xz_preset": 1,  # fast: these fixtures are kilobytes, not gigabytes
    }
    fields.update(overrides)
    return ColdBackupConfig(**fields)  # type: ignore[arg-type]


def _live(tmp_path: Path) -> Path:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    _build_live_set(live_dir, with_marketfeed=True)
    return live_dir


def _fingerprint(directory: Path) -> dict[str, tuple[str, int]]:
    """``name -> (sha256, st_mtime_ns)`` for every file directly under ``directory``.

    Digest AND mtime: a digest alone would pass a rewrite that happened to reproduce the same
    bytes (e.g. a sqlite VACUUM into an identical file), which is still a write to a live store
    this module promises never to open.
    """
    return {
        child.name: (
            hashlib.sha256(child.read_bytes()).hexdigest(),
            child.stat().st_mtime_ns,
        )
        for child in sorted(directory.iterdir())
        if child.is_file()
    }


def _run(tmp_path: Path, live_dir: Path, **overrides: object) -> ColdBackupReport:
    return cold_backup(
        live_dir, _config(tmp_path, **overrides), key_provider=FixedKeyProvider()
    )


# -- the run ------------------------------------------------------------------


def test_a_cold_backup_snapshots_archives_verifies_and_reports(tmp_path: Path) -> None:
    live_dir = _live(tmp_path)

    report = _run(tmp_path, live_dir)

    assert report.generation == 1
    assert report.chain_verified is True
    assert set(report.files_verified) == {
        "evidence",
        "rcl",
        "inbox",
        "composite_state",
        "marketfeed",
    }
    archive = Path(report.archive_path)
    assert archive == tmp_path / "cold" / "gen1.set.tar.xz"
    assert archive.is_file()
    assert report.archive_bytes == archive.stat().st_size
    assert report.archive_bytes < report.source_bytes
    # The uncompressed generation and its manifest are left exactly as backup_set wrote them.
    assert (tmp_path / "backups" / "gen1").is_dir()
    assert Path(report.manifest_path) == tmp_path / "backups" / "gen1.set.manifest.json"
    assert Path(report.manifest_path).is_file()
    # The scratch directory is gone: verification passed.
    assert not (tmp_path / "verify" / "gen1.verify").exists()


def test_the_report_is_written_next_to_the_archive_and_round_trips(
    tmp_path: Path,
) -> None:
    """The run's record is a JSON file, not an evidence row — see the module docstring for
    why (the live stores are closed and must stay byte-identical; the one existing
    operations→evidence path is the BOOT-time ``BACKUP_SET_OBSERVED`` observer)."""
    live_dir = _live(tmp_path)

    report = _run(tmp_path, live_dir)

    report_path = Path(report.report_path)
    assert report_path == tmp_path / "cold" / "gen1.cold-backup.report.json"
    assert report_path.is_file()
    assert ColdBackupReport.model_validate_json(report_path.read_text()) == report
    on_disk = json.loads(report_path.read_text())
    assert on_disk["chain_verified"] is True
    assert on_disk["minimum_free_bytes"] == _FLOOR


def test_the_live_set_is_byte_and_mtime_identical_afterwards(tmp_path: Path) -> None:
    live_dir = _live(tmp_path)
    before = _fingerprint(live_dir)
    assert before  # the fixture really did create files

    _run(tmp_path, live_dir)

    assert _fingerprint(live_dir) == before
    # Not even a WAL/SHM sidecar: this module opens no store in the live directory.
    assert {child.name for child in live_dir.iterdir()} == set(before)


def test_consecutive_runs_take_consecutive_generations(tmp_path: Path) -> None:
    """The generation is READ from the backup root, which is what lets an unattended cron line
    spell its Nth run exactly like its first."""
    live_dir = _live(tmp_path)

    first = _run(tmp_path, live_dir)
    second = _run(tmp_path, live_dir)

    assert (first.generation, second.generation) == (1, 2)
    assert (tmp_path / "cold" / "gen2.set.tar.xz").is_file()
    assert (tmp_path / "cold" / "gen2.cold-backup.report.json").is_file()
    # Generation 1's archive and report are untouched additions, never overwritten.
    assert (tmp_path / "cold" / "gen1.set.tar.xz").is_file()
    assert next_generation(tmp_path / "backups") == 3


def test_a_stored_cold_copy_that_rotted_is_refused_when_re_verified(
    tmp_path: Path,
) -> None:
    """The operational reason a cold copy is kept: it can be re-checked months later, without
    writing a new one, and refuses if it has rotted (``verify_archive``, the public
    re-check door added by #816 deviation 3). Same corruption shape as
    ``test_backup_archive.py``'s own byte-rot case, applied to what THIS module stored.
    """
    live_dir = _live(tmp_path)
    report = _run(tmp_path, live_dir)
    archive = Path(report.archive_path)

    raw = bytearray(archive.read_bytes())
    midpoint = len(raw) // 2
    raw[midpoint] ^= 0xFF
    archive.write_bytes(bytes(raw))

    with pytest.raises(BackupArchiveRefused) as refusal:
        verify_archive(
            archive,
            Path(report.manifest_path),
            tmp_path / "recheck",
            key_provider=FixedKeyProvider(),
        )
    assert "could not be read back" in str(refusal.value)


def test_an_unverifiable_archive_leaves_no_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A report exists only for a run that fully verified — and the archive layer's refusal
    keeps its own type rather than being flattened into :class:`ColdBackupRefused`."""
    live_dir = _live(tmp_path)

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise BackupArchiveRefused("decompressed 'evidence' digests abc")

    monkeypatch.setattr(cold_backup_module, "archive_backup_set", _refuse)

    with pytest.raises(BackupArchiveRefused):
        _run(tmp_path, live_dir)

    assert not (tmp_path / "cold" / "gen1.cold-backup.report.json").exists()
    assert not (tmp_path / "cold" / "gen1.set.tar.xz").exists()
    # The snapshot itself still happened and is complete — the same discipline
    # `backup-set --archive-dir` already has: a refused archive never retracts a good snapshot.
    assert (tmp_path / "backups" / "gen1.set.manifest.json").is_file()


# -- destinations -------------------------------------------------------------


def test_an_archive_dir_inside_the_live_data_dir_is_refused(tmp_path: Path) -> None:
    live_dir = _live(tmp_path)
    before = _fingerprint(live_dir)

    with pytest.raises(ColdBackupRefused) as refusal:
        _run(tmp_path, live_dir, archive_dir=live_dir / "cold")

    assert "is inside the live data directory" in str(refusal.value)
    # Refused BEFORE anything is written: no snapshot, no archive, no live-set change.
    assert not (tmp_path / "backups").exists()
    assert _fingerprint(live_dir) == before


def test_an_archive_dir_that_contains_the_live_data_dir_is_refused(
    tmp_path: Path,
) -> None:
    """The reverse containment is refused too: cold storage grows without bound (there is no
    retention), so sharing a subtree with the live runtime means filling it takes the runtime
    down."""
    live_dir = _live(tmp_path)

    with pytest.raises(ColdBackupRefused) as refusal:
        _run(tmp_path, live_dir, archive_dir=live_dir.parent)

    assert "CONTAINS the live data directory" in str(refusal.value)
    assert not (tmp_path / "backups").exists()


@pytest.mark.parametrize("key", ["archive_dir", "backup_root", "verify_root"])
def test_a_destination_inside_a_git_worktree_is_refused(
    tmp_path: Path, key: str
) -> None:
    """All three destinations, not just the archive: a multi-gigabyte uncompressed generation
    inside a checkout is as much a commit away as the compressed one. ``.git`` is matched as a
    FILE as well as a directory, which is what a linked worktree has."""
    live_dir = _live(tmp_path)
    worktree = tmp_path / "checkout"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: /elsewhere/.git/worktrees/checkout\n")

    with pytest.raises(ColdBackupRefused) as refusal:
        _run(tmp_path, live_dir, **{key: worktree / "evidence-archives"})

    assert "is inside the git worktree" in str(refusal.value)
    assert key in str(refusal.value)


# -- the capacity floor (plan §5) ---------------------------------------------


def _free_space_stub(
    free_by_root: Mapping[str, int],
) -> Callable[[Mapping[str, Path]], tuple[FilesystemFreeSpace, ...]]:
    """A ``_free_space`` replacement that answers for **the roots it is actually given**.

    Deliberately not a fixed reading: a stub that ignored its argument would return the same
    low number however few roots the caller measured, so a regression narrowing the check
    back to ``archive_dir`` alone would still see a refusal and the test would stay green —
    a test that cannot fail for the reason it exists. Reading ``roots`` is what makes
    ``test_the_floor_is_checked_on_backup_root_not_only_on_cold_storage`` real; a root the
    caller asks about and this mapping does not model raises ``KeyError``, which is also a
    signal worth having.
    """

    def _stub(roots: Mapping[str, Path]) -> tuple[FilesystemFreeSpace, ...]:
        return tuple(
            FilesystemFreeSpace(
                roots=(label,),
                measured_path=f"/fake/{label}",
                free_bytes=free_by_root[label],
            )
            for label in roots
        )

    return _stub


#: Every root comfortably above any floor these tests use.
_ROOMY: Mapping[str, int] = {
    "archive_dir": 10**12,
    "backup_root": 10**12,
    "verify_root": 10**12,
}


def test_free_space_below_the_floor_refuses_before_anything_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live_dir = _live(tmp_path)
    monkeypatch.setattr(
        cold_backup_module,
        "_free_space",
        _free_space_stub(dict.fromkeys(_ROOMY, 10)),
    )

    with pytest.raises(ColdBackupRefused) as refusal:
        _run(tmp_path, live_dir, minimum_free_bytes=1_000_000)

    message = str(refusal.value)
    assert "below the configured floor" in message
    # The refusal says what to do, and what NOT to do — deleting cold copies is Track B.
    assert "never deletes a cold copy" in message
    assert not (tmp_path / "backups").exists()
    assert not (tmp_path / "cold").exists()


def test_the_floor_is_checked_on_backup_root_not_only_on_cold_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``backup_root`` holds the UNCOMPRESSED generations — the fastest-growing tree this
    command writes, and on a different medium from ``archive_dir`` whenever the runbook's own
    advice is followed. Measuring only cold storage would watch the wrong disk, and the
    failure would arrive as a mid-copy error rather than as this refusal."""
    live_dir = _live(tmp_path)
    monkeypatch.setattr(
        cold_backup_module,
        "_free_space",
        _free_space_stub({**_ROOMY, "backup_root": 10}),
    )

    with pytest.raises(ColdBackupRefused) as refusal:
        _run(tmp_path, live_dir, minimum_free_bytes=1_000_000)

    message = str(refusal.value)
    assert "backup_root at /fake/backup_root has 10 bytes free" in message
    assert "below the configured floor" in message
    # Cold storage is roomy, so narrowing the check back to it would see nothing.
    assert "archive_dir" not in message
    assert not (tmp_path / "backups").exists()


def test_free_space_reports_one_entry_per_filesystem_not_per_root(
    tmp_path: Path,
) -> None:
    """Three roots on one disk are ONE headroom. Reporting it three times would read as
    three numbers that could be spent independently."""
    measured = cold_backup_module._free_space(
        {
            "archive_dir": tmp_path / "cold",
            "backup_root": tmp_path / "backups",
            "verify_root": tmp_path / "verify",
        }
    )

    assert len(measured) == 1
    assert measured[0].roots == ("archive_dir", "backup_root", "verify_root")
    # None of the three exists yet — the nearest existing ancestor is what was measured.
    assert measured[0].measured_path == str(tmp_path)
    assert measured[0].free_bytes > 0


def test_a_run_that_ends_below_the_floor_completes_and_flags_the_alarm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The alarm never retracts a verified backup. The run that CROSSES the floor finishes and
    records that it did; the next one is the one that refuses."""
    live_dir = _live(tmp_path)
    readings = iter(
        [
            _free_space_stub(dict.fromkeys(_ROOMY, 5_000_000)),
            _free_space_stub(dict.fromkeys(_ROOMY, 10)),
        ]
    )
    monkeypatch.setattr(
        cold_backup_module, "_free_space", lambda roots: next(readings)(roots)
    )

    report = _run(tmp_path, live_dir, minimum_free_bytes=1_000_000)

    assert report.chain_verified is True
    assert {entry.free_bytes for entry in report.free_space_before} == {5_000_000}
    assert {entry.free_bytes for entry in report.free_space_after} == {10}
    assert report.free_bytes_below_minimum_after is True
    assert Path(report.archive_path).is_file()


def test_the_measured_ancestor_is_the_nearest_existing_directory(
    tmp_path: Path,
) -> None:
    """A root does not exist before the first run, so the floor is checked against the
    filesystem that will hold it rather than skipped."""
    deep = tmp_path / "a" / "b" / "c"

    assert cold_backup_module._measurable_ancestor(deep) == tmp_path
    assert not deep.exists()


# -- a failed run must not wedge the next one (review F1) ---------------------


def test_a_leftover_generation_directory_does_not_wedge_the_next_run(
    tmp_path: Path,
) -> None:
    """The failure this guards is a permanent outage from one transient fault.

    `backup_set` creates `gen{N}/` and writes the manifest LAST, so a run that dies in
    between (the runtime still holding a handle, the disk full mid-copy) leaves a
    manifest-less directory. If the allocator counted manifests only it would hand back the
    same N every night and `backup_set` would refuse it every night — forever, unattended,
    until someone deleted the directory by hand.
    """
    live_dir = _live(tmp_path)
    # Exactly what a died-part-way run leaves behind.
    (tmp_path / "backups" / "gen1").mkdir(parents=True)
    (tmp_path / "backups" / "gen1" / "evidence.sqlite3").write_bytes(b"partial")

    report = _run(tmp_path, live_dir)

    assert report.generation == 2
    assert Path(report.archive_path).is_file()
    # Nothing was deleted: the partial directory is still there, byte for byte.
    assert (
        tmp_path / "backups" / "gen1" / "evidence.sqlite3"
    ).read_bytes() == b"partial"
    # And the run after that keeps stepping forward.
    assert _run(tmp_path, live_dir).generation == 3


# -- unattended failures are reported, never raised (review F2) ---------------


def test_a_held_sqlite_handle_surfaces_as_a_named_snapshot_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The precondition no code can check — the runtime still running — is the single most
    likely cron-time fault, and it arrives from sqlite as an `OperationalError`. It must come
    out tagged with the stage, not as a bare sqlite exception."""
    live_dir = _live(tmp_path)

    def _locked(*_args: object, **_kwargs: object) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(cold_backup_module, "backup_set", _locked)

    with pytest.raises(ColdBackupFailed) as failure:
        _run(tmp_path, live_dir)

    assert failure.value.stage == "snapshot"
    assert "OperationalError" in str(failure.value)
    assert "database is locked" in str(failure.value)
    assert isinstance(failure.value.__cause__, sqlite3.OperationalError)


def test_a_full_disk_during_the_archive_surfaces_as_a_named_archive_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live_dir = _live(tmp_path)

    def _enospc(*_args: object, **_kwargs: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(cold_backup_module, "archive_backup_set", _enospc)

    with pytest.raises(ColdBackupFailed) as failure:
        _run(tmp_path, live_dir)

    assert failure.value.stage == "archive"
    assert "No space left on device" in str(failure.value)
    # The snapshot itself still stands — a failed archive never retracts a good snapshot.
    assert (tmp_path / "backups" / "gen1.set.manifest.json").is_file()
    assert not (tmp_path / "cold" / "gen1.cold-backup.report.json").exists()


@pytest.mark.parametrize(
    "refusal",
    [
        BackupArchiveRefused("the archive does not hold what it claims to"),
        EvidenceCorruption("chain digest mismatch at seq 7"),
        CustodyLoadRefused("no evidence.key.<generation> files found"),
        KeyContinuityRefused("HISTORY_UNVERIFIABLE"),
        SchemaVersionRefused(
            "evidence: on-disk schema user_version=1 is BEHIND this code's schema_version=2",
            direction="BEHIND",
        ),
        SchemaVersionRefused(
            "evidence: on-disk schema user_version=3 is AHEAD of this code's schema_version=2",
            direction="AHEAD",
        ),
    ],
)
def test_a_verdict_is_never_rewrapped_as_an_environment_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, refusal: Exception
) -> None:
    """ "Refused" and "failed" are different facts, and the most serious verdict this command
    can reach is the chain failing to re-verify out of the archive — "**do not trust this
    copy**". Wrapping that as a stage failure filed it under "the host broke, fix it and
    re-run", the wrong instruction in the one case where re-running is not the answer.

    :class:`~tos_runtime.operations.schema_ledger.SchemaVersionRefused` is the same criterion
    applied a fourth time (plan §7.1.28): the archive's chain re-verification constructs
    a store out of the decompressed copy, and an older on-disk schema is a judgement about
    the TARGET, not about the host. Re-running cannot change it. BEHIND is fixed by
    ``migrate``; AHEAD is not (``apply_migrations`` refuses that too), which is why the
    dispatch splits the two by ``direction`` even though one type passes through here.
    """
    live_dir = _live(tmp_path)

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise refusal

    monkeypatch.setattr(cold_backup_module, "archive_backup_set", _raise)

    with pytest.raises(type(refusal)) as raised:
        _run(tmp_path, live_dir)

    assert raised.value is refusal
    assert not isinstance(raised.value, ColdBackupFailed)


def test_a_destination_that_is_a_file_is_refused_before_the_snapshot(
    tmp_path: Path,
) -> None:
    """Free space resolves to the nearest existing ancestor, so a file where a directory
    belongs sails through the preflight and is only discovered by the archive step's own
    mkdir — after a whole durable set has been copied. Caught here instead."""
    live_dir = _live(tmp_path)
    (tmp_path / "cold-file").write_text("not a directory")

    with pytest.raises(ColdBackupRefused) as refusal:
        _run(tmp_path, live_dir, archive_dir=tmp_path / "cold-file")

    assert "exists and is not a directory" in str(refusal.value)
    assert not (tmp_path / "backups").exists()


# -- the three roots are kept apart (review F5) -------------------------------


def test_two_roots_pointing_at_the_same_directory_are_refused(tmp_path: Path) -> None:
    live_dir = _live(tmp_path)

    with pytest.raises(ColdBackupRefused) as refusal:
        _run(tmp_path, live_dir, verify_root=tmp_path / "cold")

    assert "are the same directory" in str(refusal.value)
    assert not (tmp_path / "backups").exists()


@pytest.mark.parametrize(
    ("overrides", "inner", "outer"),
    [
        ({"verify_root": "cold/scratch"}, "verify_root", "archive_dir"),
        ({"archive_dir": "backups/cold"}, "archive_dir", "backup_root"),
    ],
)
def test_one_root_nested_inside_another_is_refused(
    tmp_path: Path, overrides: dict[str, str], inner: str, outer: str
) -> None:
    """Merely sharing a parent is fine and ordinary; containment is not — it silently undoes
    the separate-medium arrangement the example config asks for."""
    live_dir = _live(tmp_path)

    with pytest.raises(ColdBackupRefused) as refusal:
        _run(
            tmp_path,
            live_dir,
            **{key: tmp_path / value for key, value in overrides.items()},
        )

    message = str(refusal.value)
    assert f"{inner} " in message
    assert f"is inside {outer} " in message


# -- cold storage is part of the allocation (review round 2, F2) --------------


def test_a_backup_root_that_was_emptied_does_not_collide_with_cold_storage(
    tmp_path: Path,
) -> None:
    """Runbook §6 tells the operator to move OLD ARCHIVES elsewhere when the floor fires, and
    `backup_root` is the tree that actually grows — so "backup_root emptied or recreated
    while archive_dir still holds gen1..genK" is an ordinary consequence of following the
    runbook. Allocating from `backup_root` alone picked 1, copied the whole durable set, and
    only then refused on the existing archive — every night, for K nights."""
    live_dir = _live(tmp_path)
    first = _run(tmp_path, live_dir)
    assert first.generation == 1

    # The operator clears the warm tree (a new disk, a move, a cleanup) and leaves cold
    # storage exactly as it is.
    shutil.rmtree(tmp_path / "backups")

    second = _run(tmp_path, live_dir)

    assert second.generation == 2
    assert Path(second.archive_path).is_file()
    # gen1's cold copy and report are untouched.
    assert (tmp_path / "cold" / "gen1.set.tar.xz").is_file()
    assert (tmp_path / "cold" / "gen1.cold-backup.report.json").is_file()


@pytest.mark.parametrize(
    "existing",
    ["cold/gen1.set.tar.xz", "cold/gen1.cold-backup.report.json", "verify/gen1.verify"],
)
def test_an_existing_artifact_for_the_chosen_generation_is_refused_before_the_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: str
) -> None:
    """Belt and braces behind the allocator: if the chosen generation already has ANY of its
    three artifacts on disk, refuse before copying rather than after. The report in
    particular used to be written with a plain ``write_text`` that would have overwritten an
    existing one without a word."""
    live_dir = _live(tmp_path)
    # Pin the allocator so the collision is actually reached (otherwise it steps past).
    monkeypatch.setattr(cold_backup_module, "_highest_cold_generation", lambda _c: None)
    path = tmp_path / existing
    path.parent.mkdir(parents=True, exist_ok=True)
    if existing.endswith(".verify"):
        path.mkdir()
    else:
        path.write_text("previous")

    with pytest.raises(ColdBackupRefused) as refusal:
        _run(tmp_path, live_dir)

    assert "already exists" in str(refusal.value)
    assert not (tmp_path / "backups").exists()
    # Untouched.
    if not existing.endswith(".verify"):
        assert path.read_text() == "previous"


# -- custody is exercised before anything is copied (review round 2, F3) ------


def test_an_unusable_custody_root_is_refused_before_the_snapshot(
    tmp_path: Path,
) -> None:
    """A REAL custody failure, not a monkeypatched constructor.

    ``FileKeyProvider.__init__`` only stores fields, so the previous test for this named a
    case the real constructor cannot produce. An empty custody root is the genuine article:
    nothing raises until ``current()`` is called, which is exactly why the preflight now
    calls it — otherwise the whole durable set is copied and compressed first and the
    failure arrives labelled as an archive-stage fault.
    """
    live_dir = _live(tmp_path)
    empty_custody = tmp_path / "no-keys"
    empty_custody.mkdir()

    with pytest.raises(CustodyLoadRefused):
        cold_backup(
            live_dir,
            _config(tmp_path),
            key_provider=FileKeyProvider(empty_custody, expected_owner_uid=os.getuid()),
        )

    assert not (tmp_path / "backups").exists()
    assert not (tmp_path / "cold").exists()


# -- the loader ---------------------------------------------------------------


def _write_config(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "evidence_cold_backup.yaml"
    path.write_text(body)
    return path


_FILLED = """
backup_root: /srv/tos/backups
archive_dir: /srv/tos/cold
verify_root: /srv/tos/verify
minimum_free_bytes: 53687091200
"""


def test_a_filled_config_loads(tmp_path: Path) -> None:
    config = load_cold_backup_config(_write_config(tmp_path, _FILLED))

    assert config.backup_root == Path("/srv/tos/backups")
    assert config.archive_dir == Path("/srv/tos/cold")
    assert config.verify_root == Path("/srv/tos/verify")
    assert config.minimum_free_bytes == 53687091200
    # Absent `xz_preset` means the already-named default, never an invented value.
    assert config.xz_preset == cold_backup_module.DEFAULT_XZ_PRESET


def test_a_missing_config_file_is_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(ColdBackupRefused) as refusal:
        load_cold_backup_config(tmp_path / "evidence_cold_backup.yaml")

    message = str(refusal.value)
    assert "does not exist" in message
    # The message points at the template rather than leaving the operator to guess the shape.
    assert "evidence_cold_backup.example.yaml" in message


def test_a_non_mapping_config_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ColdBackupRefused) as refusal:
        load_cold_backup_config(_write_config(tmp_path, "- a\n- b\n"))

    assert "is not a YAML mapping" in str(refusal.value)


@pytest.mark.parametrize(
    "key", ["backup_root", "archive_dir", "verify_root", "minimum_free_bytes"]
)
def test_a_missing_required_key_is_refused(tmp_path: Path, key: str) -> None:
    body = "\n".join(
        line for line in _FILLED.strip().splitlines() if not line.startswith(f"{key}:")
    )

    with pytest.raises(ColdBackupRefused) as refusal:
        load_cold_backup_config(_write_config(tmp_path, body))

    assert f"missing the required key {key!r}" in str(refusal.value)


@pytest.mark.parametrize(
    "key", ["backup_root", "archive_dir", "verify_root", "minimum_free_bytes"]
)
def test_a_null_value_is_refused_rather_than_defaulted(
    tmp_path: Path, key: str
) -> None:
    """The committed ``config/tos_runtime/paper/evidence_cold_backup.yaml`` ships exactly this
    way — every host coordinate ``null`` — so this is the state an un-filled deployment is in,
    and it must refuse loudly rather than back up somewhere invented."""
    body = "\n".join(
        f"{key}: null" if line.startswith(f"{key}:") else line
        for line in _FILLED.strip().splitlines()
    )

    with pytest.raises(ColdBackupRefused) as refusal:
        load_cold_backup_config(_write_config(tmp_path, body))

    assert "still null (named-TBD)" in str(refusal.value)


def test_the_named_tbd_placeholder_string_is_refused(tmp_path: Path) -> None:
    body = _FILLED.replace("/srv/tos/cold", "TBD")

    with pytest.raises(ColdBackupRefused) as refusal:
        load_cold_backup_config(_write_config(tmp_path, body))

    assert "template placeholder" in str(refusal.value)


def test_a_relative_path_is_refused(tmp_path: Path) -> None:
    """A relative destination depends on the cron line's working directory."""
    body = _FILLED.replace("/srv/tos/cold", "relative/cold")

    with pytest.raises(ColdBackupRefused) as refusal:
        load_cold_backup_config(_write_config(tmp_path, body))

    assert "not an absolute path" in str(refusal.value)


@pytest.mark.parametrize("value", ["~/cold", "~deploy/cold"])
def test_a_tilde_path_is_refused_as_a_tilde_path(tmp_path: Path, value: str) -> None:
    """And it says ``~``, not merely "not absolute".

    This is the distinction worth a test of its own: a tilde path is ALREADY non-absolute, so
    an ``is_absolute()`` check placed first would catch it and the tilde branch behind it
    could never fire — a guard naming a case it cannot reach. Ordering it first is what makes
    the specific message real, and this test is what holds the ordering (reverse the two
    branches and it goes red).
    """
    body = _FILLED.replace("/srv/tos/cold", value)

    with pytest.raises(ColdBackupRefused) as refusal:
        load_cold_backup_config(_write_config(tmp_path, body))

    message = str(refusal.value)
    assert "no tilde expansion" in message
    assert "not an absolute path" not in message


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        ("minimum_free_bytes: 'lots'", "must be an integer number of bytes"),
        ("minimum_free_bytes: true", "must be an integer number of bytes"),
        ("minimum_free_bytes: -1", "Zero and negative are not floors"),
        ("minimum_free_bytes: 0", "Zero and negative are not floors"),
    ],
)
def test_a_malformed_free_space_floor_is_refused(
    tmp_path: Path, raw: str, fragment: str
) -> None:
    body = _FILLED.replace("minimum_free_bytes: 53687091200", raw)

    with pytest.raises(ColdBackupRefused) as refusal:
        load_cold_backup_config(_write_config(tmp_path, body))

    assert fragment in str(refusal.value)


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        ("xz_preset: null", "still null (named-TBD)"),
        ("xz_preset: 10", "outside the 0-9 range"),
        ("xz_preset: 'six'", "must be an integer 0-9"),
    ],
)
def test_a_present_but_unusable_xz_preset_is_refused(
    tmp_path: Path, raw: str, fragment: str
) -> None:
    """Optional means ABSENT, not empty: a key written and left null is a half-filled file, and
    silently reading the default there would make it look complete."""
    with pytest.raises(ColdBackupRefused) as refusal:
        load_cold_backup_config(_write_config(tmp_path, f"{_FILLED}{raw}\n"))

    assert fragment in str(refusal.value)


def test_a_present_xz_preset_is_honoured(tmp_path: Path) -> None:
    config = load_cold_backup_config(
        _write_config(tmp_path, f"{_FILLED}xz_preset: 0\n")
    )

    assert config.xz_preset == 0


def test_the_shipped_example_config_is_the_shape_this_loader_reads(
    tmp_path: Path,
) -> None:
    """The template and the loader are checked against each other, so the example cannot drift
    into documenting keys nothing reads (the ``registry-with-unpinned-satellite`` shape).

    It is read as TEXT and re-serialized under ``tmp_path`` rather than loaded in place: the
    hermetic write guard allows no reads to matter outside ``tmp_path``'s tree for the write
    side, and this keeps the test from depending on the repo path at run time beyond locating
    the file.
    """
    example = (
        Path(__file__).resolve().parents[3]
        / "runtime"
        / "config"
        / "evidence_cold_backup.example.yaml"
    )
    body = example.read_text()

    # Every required key is present and null — the template is un-filled by construction.
    with pytest.raises(ColdBackupRefused) as refusal:
        load_cold_backup_config(_write_config(tmp_path, body))
    assert "still null (named-TBD)" in str(refusal.value)

    # And filling the four required keys is sufficient: no hidden fifth requirement.
    filled = (
        body.replace("backup_root: null", "backup_root: /srv/b")
        .replace("archive_dir: null", "archive_dir: /srv/c")
        .replace("verify_root: null", "verify_root: /srv/v")
        .replace("minimum_free_bytes: null", "minimum_free_bytes: 1")
    )
    config = load_cold_backup_config(_write_config(tmp_path, filled))
    assert config.archive_dir == Path("/srv/c")
