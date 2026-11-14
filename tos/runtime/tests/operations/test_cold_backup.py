"""Config-driven cold-backup tests (evidence growth plan §2 A3,"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import pickle
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

_FLOOR = 1024


def _config(tmp_path: Path, **overrides: object) -> ColdBackupConfig:
    fields: dict[str, object] = {
        "backup_root": tmp_path / "backups",
        "archive_dir": tmp_path / "cold",
        "verify_root": tmp_path / "verify",
        "minimum_free_bytes": _FLOOR,
        "xz_preset": 1,
    }
    fields.update(overrides)
    return ColdBackupConfig(**fields)  # type: ignore[arg-type]


def _live(tmp_path: Path) -> Path:
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    _build_live_set(live_dir, with_marketfeed=True)
    return live_dir


def _fingerprint(directory: Path) -> dict[str, tuple[str, int]]:
    """``name -> (sha256, st_mtime_ns)`` for every file directly under ``directory``."""
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
    assert (tmp_path / "backups" / "gen1").is_dir()
    assert Path(report.manifest_path) == tmp_path / "backups" / "gen1.set.manifest.json"
    assert Path(report.manifest_path).is_file()
    assert not (tmp_path / "verify" / "gen1.verify").exists()


def test_the_report_is_written_next_to_the_archive_and_round_trips(
    tmp_path: Path,
) -> None:
    """The run's record is a JSON file, not an evidence row — see the module docstring for"""
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
    assert before

    _run(tmp_path, live_dir)

    assert _fingerprint(live_dir) == before
    assert {child.name for child in live_dir.iterdir()} == set(before)


def test_consecutive_runs_take_consecutive_generations(tmp_path: Path) -> None:
    """The generation is READ from the backup root, which is what lets an unattended cron line"""
    live_dir = _live(tmp_path)

    first = _run(tmp_path, live_dir)
    second = _run(tmp_path, live_dir)

    assert (first.generation, second.generation) == (1, 2)
    assert (tmp_path / "cold" / "gen2.set.tar.xz").is_file()
    assert (tmp_path / "cold" / "gen2.cold-backup.report.json").is_file()
    assert (tmp_path / "cold" / "gen1.set.tar.xz").is_file()
    assert next_generation(tmp_path / "backups") == 3


def test_a_stored_cold_copy_that_rotted_is_refused_when_re_verified(
    tmp_path: Path,
) -> None:
    """The operational reason a cold copy is kept: it can be re-checked months later, without"""
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
    """A report exists only for a run that fully verified — and the archive layer's refusal"""
    live_dir = _live(tmp_path)

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise BackupArchiveRefused("decompressed 'evidence' digests abc")

    monkeypatch.setattr(cold_backup_module, "archive_backup_set", _refuse)

    with pytest.raises(BackupArchiveRefused):
        _run(tmp_path, live_dir)

    assert not (tmp_path / "cold" / "gen1.cold-backup.report.json").exists()
    assert not (tmp_path / "cold" / "gen1.set.tar.xz").exists()
    assert (tmp_path / "backups" / "gen1.set.manifest.json").is_file()


def test_an_archive_dir_inside_the_live_data_dir_is_refused(tmp_path: Path) -> None:
    live_dir = _live(tmp_path)
    before = _fingerprint(live_dir)

    with pytest.raises(ColdBackupRefused) as refusal:
        _run(tmp_path, live_dir, archive_dir=live_dir / "cold")

    assert "is inside the live data directory" in str(refusal.value)
    assert not (tmp_path / "backups").exists()
    assert _fingerprint(live_dir) == before


def test_an_archive_dir_that_contains_the_live_data_dir_is_refused(
    tmp_path: Path,
) -> None:
    """The reverse containment is refused too: cold storage grows without bound (there is no"""
    live_dir = _live(tmp_path)

    with pytest.raises(ColdBackupRefused) as refusal:
        _run(tmp_path, live_dir, archive_dir=live_dir.parent)

    assert "CONTAINS the live data directory" in str(refusal.value)
    assert not (tmp_path / "backups").exists()


@pytest.mark.parametrize("key", ["archive_dir", "backup_root", "verify_root"])
def test_a_destination_inside_a_git_worktree_is_refused(
    tmp_path: Path, key: str
) -> None:
    """All three destinations, not just the archive: a multi-gigabyte uncompressed generation"""
    live_dir = _live(tmp_path)
    worktree = tmp_path / "checkout"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: /elsewhere/.git/worktrees/checkout\n")

    with pytest.raises(ColdBackupRefused) as refusal:
        _run(tmp_path, live_dir, **{key: worktree / "evidence-archives"})

    assert "is inside the git worktree" in str(refusal.value)
    assert key in str(refusal.value)


def _free_space_stub(
    free_by_root: Mapping[str, int],
) -> Callable[[Mapping[str, Path]], tuple[FilesystemFreeSpace, ...]]:
    """A ``_free_space`` replacement that answers for **the roots it is actually given**."""

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
    assert "never deletes a cold copy" in message
    assert not (tmp_path / "backups").exists()
    assert not (tmp_path / "cold").exists()


def test_the_floor_is_checked_on_backup_root_not_only_on_cold_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``backup_root`` holds the UNCOMPRESSED generations — the fastest-growing tree this"""
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
    assert "archive_dir" not in message
    assert not (tmp_path / "backups").exists()


def test_free_space_reports_one_entry_per_filesystem_not_per_root(
    tmp_path: Path,
) -> None:
    """Three roots on one disk are ONE headroom. Reporting it three times would read as"""
    measured = cold_backup_module._free_space(
        {
            "archive_dir": tmp_path / "cold",
            "backup_root": tmp_path / "backups",
            "verify_root": tmp_path / "verify",
        }
    )

    assert len(measured) == 1
    assert measured[0].roots == ("archive_dir", "backup_root", "verify_root")
    assert measured[0].measured_path == str(tmp_path)
    assert measured[0].free_bytes > 0


def test_a_run_that_ends_below_the_floor_completes_and_flags_the_alarm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The alarm never retracts a verified backup. The run that CROSSES the floor finishes and"""
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
    """A root does not exist before the first run, so the floor is checked against the"""
    deep = tmp_path / "a" / "b" / "c"

    assert cold_backup_module._measurable_ancestor(deep) == tmp_path
    assert not deep.exists()


def test_a_leftover_generation_directory_does_not_wedge_the_next_run(
    tmp_path: Path,
) -> None:
    """The failure this guards is a permanent outage from one transient fault."""
    live_dir = _live(tmp_path)
    (tmp_path / "backups" / "gen1").mkdir(parents=True)
    (tmp_path / "backups" / "gen1" / "evidence.sqlite3").write_bytes(b"partial")

    report = _run(tmp_path, live_dir)

    assert report.generation == 2
    assert Path(report.archive_path).is_file()
    assert (
        tmp_path / "backups" / "gen1" / "evidence.sqlite3"
    ).read_bytes() == b"partial"
    assert _run(tmp_path, live_dir).generation == 3


def test_a_held_sqlite_handle_surfaces_as_a_named_snapshot_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The precondition no code can check — the runtime still running — is the single most"""
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
    '"Refused" and "failed" are different facts, and the most serious verdict this command'
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
    """Free space resolves to the nearest existing ancestor, so a file where a directory"""
    live_dir = _live(tmp_path)
    (tmp_path / "cold-file").write_text("not a directory")

    with pytest.raises(ColdBackupRefused) as refusal:
        _run(tmp_path, live_dir, archive_dir=tmp_path / "cold-file")

    assert "exists and is not a directory" in str(refusal.value)
    assert not (tmp_path / "backups").exists()


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
    """Merely sharing a parent is fine and ordinary; containment is not — it silently undoes"""
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


def test_a_backup_root_that_was_emptied_does_not_collide_with_cold_storage(
    tmp_path: Path,
) -> None:
    """Runbook §6 tells the operator to move OLD ARCHIVES elsewhere when the floor fires, and"""
    live_dir = _live(tmp_path)
    first = _run(tmp_path, live_dir)
    assert first.generation == 1

    shutil.rmtree(tmp_path / "backups")

    second = _run(tmp_path, live_dir)

    assert second.generation == 2
    assert Path(second.archive_path).is_file()
    assert (tmp_path / "cold" / "gen1.set.tar.xz").is_file()
    assert (tmp_path / "cold" / "gen1.cold-backup.report.json").is_file()


@pytest.mark.parametrize(
    "existing",
    ["cold/gen1.set.tar.xz", "cold/gen1.cold-backup.report.json", "verify/gen1.verify"],
)
def test_an_existing_artifact_for_the_chosen_generation_is_refused_before_the_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: str
) -> None:
    """Belt and braces behind the allocator: if the chosen generation already has ANY of its"""
    live_dir = _live(tmp_path)
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
    if not existing.endswith(".verify"):
        assert path.read_text() == "previous"


def test_an_unusable_custody_root_is_refused_before_the_snapshot(
    tmp_path: Path,
) -> None:
    """A REAL custody failure, not a monkeypatched constructor."""
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
    assert config.xz_preset == cold_backup_module.DEFAULT_XZ_PRESET


def test_a_missing_config_file_is_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(ColdBackupRefused) as refusal:
        load_cold_backup_config(tmp_path / "evidence_cold_backup.yaml")

    message = str(refusal.value)
    assert "does not exist" in message
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
    """The committed ``config/tos_runtime/paper/evidence_cold_backup.yaml`` ships exactly this"""
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
    """And it says ``~``, not merely "not absolute"."""
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
    """Optional means ABSENT, not empty: a key written and left null is a half-filled file, and"""
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
    """The template and the loader are checked against each other, so the example cannot drift"""
    example = (
        Path(__file__).resolve().parents[3]
        / "runtime"
        / "config"
        / "evidence_cold_backup.example.yaml"
    )
    body = example.read_text()

    with pytest.raises(ColdBackupRefused) as refusal:
        load_cold_backup_config(_write_config(tmp_path, body))
    assert "still null (named-TBD)" in str(refusal.value)

    filled = (
        body.replace("backup_root: null", "backup_root: /srv/b")
        .replace("archive_dir: null", "archive_dir: /srv/c")
        .replace("verify_root: null", "verify_root: /srv/v")
        .replace("minimum_free_bytes: null", "minimum_free_bytes: 1")
    )
    config = load_cold_backup_config(_write_config(tmp_path, filled))
    assert config.archive_dir == Path("/srv/c")


class _NarrowerColdBackupFailure(ColdBackupFailed):
    """A subclass at MODULE level, because pickle stores a qualified name."""


def test_a_wrapped_failure_survives_pickle_and_copy() -> None:
    """The wrapper itself must serialize — the same two-positional defect, one class over."""
    original = ColdBackupFailed("archive", OSError("no space left on device"))

    for rebuilt in (
        pickle.loads(pickle.dumps(original)),
        copy.copy(original),
        copy.deepcopy(original),
    ):
        assert type(rebuilt) is ColdBackupFailed
        assert str(rebuilt) == str(original)
        assert rebuilt.args == original.args
        assert rebuilt.stage == "archive"


def test_a_wrapped_failure_rebuilds_as_its_own_subclass_and_keeps_notes() -> None:
    """Exact type and instance state, for the same reasons as the version refusal."""
    original = _NarrowerColdBackupFailure("snapshot", OSError("read-only file system"))
    original.add_note("ran under the 18:00 cron")

    for rebuilt in (
        pickle.loads(pickle.dumps(original)),
        copy.copy(original),
        copy.deepcopy(original),
    ):
        assert type(rebuilt) is _NarrowerColdBackupFailure
        assert rebuilt.stage == "snapshot"
        assert rebuilt.__notes__ == ["ran under the 18:00 cron"]
