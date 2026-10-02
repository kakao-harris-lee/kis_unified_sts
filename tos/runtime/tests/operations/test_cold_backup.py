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
from pathlib import Path

import pytest
from tos_runtime.operations import cold_backup as cold_backup_module
from tos_runtime.operations.backup_archive import BackupArchiveRefused, verify_archive
from tos_runtime.operations.backup_set import next_generation
from tos_runtime.operations.cold_backup import (
    ColdBackupConfig,
    ColdBackupRefused,
    ColdBackupReport,
    cold_backup,
    load_cold_backup_config,
)

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


def test_an_unverifiable_archive_leaves_no_report(tmp_path: Path) -> None:
    """A report exists only for a run that fully verified — and the archive layer's refusal
    keeps its own type rather than being flattened into :class:`ColdBackupRefused`."""
    live_dir = _live(tmp_path)
    # A pre-existing scratch directory is refused by `archive_backup_set` itself: a directory
    # it did not create could hide a missing member behind a stale file.
    (tmp_path / "verify" / "gen1.verify").mkdir(parents=True)

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


def test_free_space_below_the_floor_refuses_before_anything_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live_dir = _live(tmp_path)
    monkeypatch.setattr(cold_backup_module, "_free_bytes", lambda _path: 10)

    with pytest.raises(ColdBackupRefused) as refusal:
        _run(tmp_path, live_dir, minimum_free_bytes=1_000_000)

    message = str(refusal.value)
    assert "below the configured floor" in message
    # The refusal says what to do, and what NOT to do — deleting cold copies is Track B.
    assert "never deletes a cold copy" in message
    assert not (tmp_path / "backups").exists()
    assert not (tmp_path / "cold").exists()


def test_a_run_that_ends_below_the_floor_completes_and_flags_the_alarm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The alarm never retracts a verified backup. The run that CROSSES the floor finishes and
    records that it did; the next one is the one that refuses."""
    live_dir = _live(tmp_path)
    readings = iter([5_000_000, 10])
    monkeypatch.setattr(cold_backup_module, "_free_bytes", lambda _path: next(readings))

    report = _run(tmp_path, live_dir, minimum_free_bytes=1_000_000)

    assert report.chain_verified is True
    assert (report.free_bytes_before, report.free_bytes_after) == (5_000_000, 10)
    assert report.free_bytes_below_minimum_after is True
    assert Path(report.archive_path).is_file()


def test_free_bytes_measures_the_nearest_existing_ancestor(tmp_path: Path) -> None:
    """``archive_dir`` does not exist before the first run, so the floor is checked against the
    filesystem that will hold it rather than skipped."""
    deep = tmp_path / "a" / "b" / "c"

    measured = cold_backup_module._free_bytes(deep)

    assert measured > 0
    assert not deep.exists()


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
        ("minimum_free_bytes: -1", "which is negative"),
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
