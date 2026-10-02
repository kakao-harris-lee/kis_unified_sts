"""``cold-backup`` subcommand tests (evidence growth plan §2 A3,
``docs/plans/2026-09-29-tos-evidence-growth-and-purge-plan.md``).

Unlike ``test_cli.py``, which monkeypatches every operations function and pins argument
parsing only, these drive the REAL
:func:`~tos_runtime.operations.cold_backup.cold_backup` against a real durable set — because
the thing this subcommand adds over ``backup-set --archive-dir`` is precisely that an operator
(or a cron line) supplies no coordinates beyond three directories, so the only way to show it
works is to let it do the whole run. The one substitution is the custody key source: a D4
custody root is this suite's heaviest fixture and contributes nothing to what is under test,
so :class:`FixedKeyProvider` stands in for it, exactly as ``test_cli.py``'s own archive tests
already substitute ``FileKeyProvider``.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest
from tos_runtime.compose import _backup_dispatch, cli
from tos_runtime.operations import cold_backup as cold_backup_module
from tos_runtime.operations.cold_backup import FilesystemFreeSpace

from ..engine.conftest import FixedKeyProvider
from ..operations.test_backup_set import _build_live_set

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_CONFIG = """
backup_root: {backups}
archive_dir: {cold}
verify_root: {verify}
minimum_free_bytes: {floor}
xz_preset: 1
"""


def _prepare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, floor: int = 1024
) -> Path:
    """A live set, a filled config directory, and a stand-in key provider. Returns the live
    data directory."""
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    _build_live_set(live_dir, with_marketfeed=True)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "evidence_cold_backup.yaml").write_text(
        _CONFIG.format(
            backups=tmp_path / "backups",
            cold=tmp_path / "cold",
            verify=tmp_path / "verify",
            floor=floor,
        )
    )
    monkeypatch.setattr(
        _backup_dispatch, "FileKeyProvider", lambda _root, **_kw: FixedKeyProvider()
    )
    return live_dir


def _argv(tmp_path: Path, live_dir: Path) -> list[str]:
    return [
        "cold-backup",
        "--data-dir",
        str(live_dir),
        "--config-dir",
        str(tmp_path / "config"),
        "--custody-root",
        str(tmp_path / "custody"),
    ]


def test_cold_backup_runs_the_whole_thing_from_three_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live_dir = _prepare(tmp_path, monkeypatch)

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "cold-backup: archived gen1" in out
    assert "read back and verified" in out
    assert (tmp_path / "cold" / "gen1.set.tar.xz").is_file()
    report_path = tmp_path / "cold" / "gen1.cold-backup.report.json"
    assert report_path.is_file()
    assert str(report_path) in out
    assert json.loads(report_path.read_text())["chain_verified"] is True


def test_a_second_run_needs_no_different_command_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The point of the subcommand: the Nth cron run is spelled exactly like the first. With
    ``backup-set`` the operator had to type an increasing ``--generation``."""
    live_dir = _prepare(tmp_path, monkeypatch)
    argv = _argv(tmp_path, live_dir)

    assert cli.main(argv) == 0
    assert cli.main(list(argv)) == 0

    out = capsys.readouterr().out
    assert "archived gen1" in out
    assert "archived gen2" in out


def test_a_missing_config_file_exits_one_and_names_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live_dir = _prepare(tmp_path, monkeypatch)
    (tmp_path / "config" / "evidence_cold_backup.yaml").unlink()

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert err.startswith("cold-backup: refused —")
    assert "evidence_cold_backup.yaml" in err
    # A refusal before anything is written: no snapshot, no archive.
    assert not (tmp_path / "backups").exists()
    assert not (tmp_path / "cold").exists()


def test_an_unfilled_config_exits_one_rather_than_backing_up_somewhere_invented(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The shipped ``config/tos_runtime/paper/evidence_cold_backup.yaml`` is in exactly this
    state until an operator fills it."""
    live_dir = _prepare(tmp_path, monkeypatch)
    (tmp_path / "config" / "evidence_cold_backup.yaml").write_text(
        "backup_root: null\narchive_dir: null\nverify_root: null\n"
        "minimum_free_bytes: null\n"
    )

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    assert "still null (named-TBD)" in capsys.readouterr().err


def test_an_archive_refusal_keeps_its_own_prefix_and_leaves_the_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Three refusal families, three prefixes — a cron mail says which layer refused rather
    than flattening them into one word."""
    live_dir = _prepare(tmp_path, monkeypatch)
    (tmp_path / "verify" / "gen1.verify").mkdir(parents=True)

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    assert capsys.readouterr().err.startswith("cold-backup: archive refused —")
    assert (tmp_path / "backups" / "gen1.set.manifest.json").is_file()
    assert not (tmp_path / "cold" / "gen1.cold-backup.report.json").exists()


def _free_space_stub(
    free_bytes: int,
) -> Callable[[Mapping[str, Path]], tuple[FilesystemFreeSpace, ...]]:
    def _stub(_roots: Mapping[str, Path]) -> tuple[FilesystemFreeSpace, ...]:
        return (
            FilesystemFreeSpace(
                roots=("archive_dir", "backup_root", "verify_root"),
                measured_path="/fake/root",
                free_bytes=free_bytes,
            ),
        )

    return _stub


def test_a_run_that_crosses_the_capacity_floor_warns_but_still_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live_dir = _prepare(tmp_path, monkeypatch, floor=1_000_000)
    readings = iter([_free_space_stub(5_000_000), _free_space_stub(10)])
    monkeypatch.setattr(
        cold_backup_module, "_free_space", lambda roots: next(readings)(roots)
    )

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "cold-backup: archived gen1" in captured.out
    assert "WARNING" in captured.err
    assert "the NEXT run will refuse" in captured.err
    assert (tmp_path / "cold" / "gen1.set.tar.xz").is_file()


def test_the_capacity_floor_refusal_exits_one_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live_dir = _prepare(tmp_path, monkeypatch, floor=1_000_000)
    monkeypatch.setattr(cold_backup_module, "_free_space", _free_space_stub(10))

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert err.startswith("cold-backup: refused —")
    assert "below the configured floor" in err
    assert not (tmp_path / "backups").exists()


# -- the §5 contract: every unattended failure is ONE line, never a traceback -


def _raise_locked(*_args: object, **_kwargs: object) -> None:
    raise sqlite3.OperationalError("database is locked")


def _raise_enospc(*_args: object, **_kwargs: object) -> None:
    raise OSError(28, "No space left on device")


@pytest.mark.parametrize(
    ("patched", "raises", "expected_prefix"),
    [
        (
            "backup_set",
            _raise_locked,
            "cold-backup: snapshot failed — OperationalError: database is locked",
        ),
        (
            "archive_backup_set",
            _raise_enospc,
            "cold-backup: archive failed — OSError:",
        ),
    ],
)
def test_an_environment_fault_prints_one_line_naming_the_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patched: str,
    raises: object,
    expected_prefix: str,
) -> None:
    """The runbook §5 table promises the operator one line saying which layer stopped. Before
    this, the likeliest cron-time faults — the runtime still up, the disk full — were the ones
    that broke that promise, arriving as tracebacks."""
    live_dir = _prepare(tmp_path, monkeypatch)
    monkeypatch.setattr(cold_backup_module, patched, raises)

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert err.startswith(expected_prefix)
    assert "Traceback" not in err
    assert len(err.strip().splitlines()) == 1


def test_an_unreadable_custody_root_prints_one_line_and_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live_dir = _prepare(tmp_path, monkeypatch)

    def _no_custody(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError("custody.manifest.yaml")

    monkeypatch.setattr(_backup_dispatch, "FileKeyProvider", _no_custody)

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert err.startswith("cold-backup: custody failed — FileNotFoundError:")
    # Refused before the snapshot: custody is read before anything is written.
    assert not (tmp_path / "backups").exists()


def test_an_unparseable_config_prints_one_line_and_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live_dir = _prepare(tmp_path, monkeypatch)

    def _boom(_path: Path) -> None:
        raise RuntimeError("loader blew up in a way this module does not model")

    monkeypatch.setattr(_backup_dispatch, "load_cold_backup_config", _boom)

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    assert capsys.readouterr().err.startswith(
        "cold-backup: config failed — RuntimeError:"
    )


def test_cold_backup_parses_into_its_own_args_object(tmp_path: Path) -> None:
    args = cli.parse_args(
        [
            "cold-backup",
            "--data-dir",
            str(tmp_path / "data"),
            "--config-dir",
            str(tmp_path / "config"),
            "--custody-root",
            str(tmp_path / "custody"),
        ]
    )

    assert isinstance(args, _backup_dispatch.ColdBackupArgs)
    assert args.data_dir == tmp_path / "data"
    assert args.config_dir == tmp_path / "config"
    assert args.custody_root == tmp_path / "custody"


def test_backup_set_still_takes_an_explicit_generation(tmp_path: Path) -> None:
    """``cold-backup`` is additive: the interactive one-off door is unchanged, including its
    hand-typed generation (TOS Phase 5 W4 decision 1, "세대는 호출자 지정")."""
    args = cli.parse_args(
        [
            "backup-set",
            "--data-dir",
            str(tmp_path / "data"),
            "--dest",
            str(tmp_path / "backups"),
            "--generation",
            "4",
        ]
    )

    assert isinstance(args, cli.BackupSetArgs)
    assert args.generation == 4
    assert args.archive_dir is None
