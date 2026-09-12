"""Hermetic tests for :mod:`tos_runtime.compose.cli` (TOS Phase 5 W4 plan §2 decision 10).

No filesystem/network access needed here beyond ``tmp_path``-rooted ``Path`` objects that are
never actually opened — every operations function this module dispatches to is monkeypatched, so
these tests pin ARGUMENT PARSING and DISPATCH shape only, never the underlying operations'
own behaviour (that is ``tests/operations/*``'s scope).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos_runtime.compose import cli
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.operations.backup_set import DurableSetPaths
from tos_runtime.operations.schema_migrations import STORE_MIGRATIONS

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


# -- `run`: no subcommand token given (backward compatibility) ----------------


def test_run_default_parsing_with_no_subcommand_token(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    custody_root = tmp_path / "custody"

    args = cli.parse_args(
        [
            "--config-dir",
            str(config_dir),
            "--data-dir",
            str(data_dir),
            "--custody-root",
            str(custody_root),
            "--environment-label",
            "non-live-test",
        ]
    )

    assert isinstance(args, cli.Args)
    assert args.config_dir == config_dir
    assert args.data_dir == data_dir
    assert args.custody_root == custody_root
    assert args.environment_label == "non-live-test"
    assert args.transport is TransportKind.SYNTHETIC
    assert args.projection_path is None
    assert args.backup_root is None


def test_run_explicit_subcommand_token_parses_identically(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    custody_root = tmp_path / "custody"

    without_token = cli.parse_args(
        [
            "--config-dir",
            str(config_dir),
            "--data-dir",
            str(data_dir),
            "--custody-root",
            str(custody_root),
            "--environment-label",
            "non-live-test",
        ]
    )
    with_token = cli.parse_args(
        [
            "run",
            "--config-dir",
            str(config_dir),
            "--data-dir",
            str(data_dir),
            "--custody-root",
            str(custody_root),
            "--environment-label",
            "non-live-test",
        ]
    )

    assert without_token == with_token


def test_run_accepts_the_two_new_optional_flags(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    custody_root = tmp_path / "custody"
    projection_path = tmp_path / "projection.json"
    backup_root = tmp_path / "backups"

    args = cli.parse_args(
        [
            "--config-dir",
            str(config_dir),
            "--data-dir",
            str(data_dir),
            "--custody-root",
            str(custody_root),
            "--environment-label",
            "non-live-test",
            "--projection-path",
            str(projection_path),
            "--backup-root",
            str(backup_root),
        ]
    )

    assert isinstance(args, cli.Args)
    assert args.projection_path == projection_path
    assert args.backup_root == backup_root


def test_run_main_returns_zero_and_never_calls_an_operations_function(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _must_not_be_called(name: str, *_args: object, **_kwargs: object) -> None:
        raise AssertionError(f"{name} must not be called for `run`")

    for name in (
        "backup_set",
        "restore_set",
        "apply_migrations",
        "observe_runtime_artifact",
    ):
        monkeypatch.setattr(
            cli, name, lambda *a, _name=name, **k: _must_not_be_called(_name, *a, **k)
        )
    exit_code = cli.main(
        [
            "--config-dir",
            str(tmp_path / "config"),
            "--data-dir",
            str(tmp_path / "data"),
            "--custody-root",
            str(tmp_path / "custody"),
            "--environment-label",
            "non-live-test",
        ]
    )
    assert exit_code == 0


# -- backup-set ----------------------------------------------------------------


def test_backup_set_dispatches_with_the_right_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple] = []

    class _FakeManifest:
        generation = 3

    def _fake_backup_set(
        paths, dest_dir, generation, *, readiness_verdict_at_backup=None
    ):
        calls.append((paths, dest_dir, generation, readiness_verdict_at_backup))
        return _FakeManifest()

    monkeypatch.setattr(cli, "backup_set", _fake_backup_set)

    data_dir = tmp_path / "data"
    dest = tmp_path / "backups"
    exit_code = cli.main(
        [
            "backup-set",
            "--data-dir",
            str(data_dir),
            "--dest",
            str(dest),
            "--generation",
            "3",
        ]
    )

    assert exit_code == 0
    assert len(calls) == 1
    paths, dest_dir, generation, readiness_verdict = calls[0]
    assert paths == DurableSetPaths.from_data_dir(data_dir)
    assert dest_dir == dest
    assert generation == 3
    assert readiness_verdict is None


def test_backup_set_forwards_readiness_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple] = []

    class _FakeManifest:
        generation = 1

    def _fake_backup_set(
        paths, dest_dir, generation, *, readiness_verdict_at_backup=None
    ):
        calls.append(readiness_verdict_at_backup)
        return _FakeManifest()

    monkeypatch.setattr(cli, "backup_set", _fake_backup_set)

    cli.main(
        [
            "backup-set",
            "--data-dir",
            str(tmp_path / "data"),
            "--dest",
            str(tmp_path / "backups"),
            "--generation",
            "1",
            "--readiness-verdict",
            "READY",
        ]
    )

    assert calls == ["READY"]


# -- restore-drill --------------------------------------------------------------


@pytest.mark.parametrize("live_label", ["paper", "restricted-live", "production"])
def test_restore_drill_refuses_live_labels_before_doing_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, live_label: str
) -> None:
    def _must_not_be_called(*args, **kwargs):
        raise AssertionError(
            "restore_set must not be called for a live environment_label"
        )

    monkeypatch.setattr(cli, "restore_set", _must_not_be_called)

    exit_code = cli.main(
        [
            "restore-drill",
            "--manifest",
            str(tmp_path / "gen1.set.manifest.json"),
            "--dest",
            str(tmp_path / "restored"),
            "--environment-label",
            live_label,
            "--custody-root",
            str(tmp_path / "custody"),
        ]
    )

    assert exit_code == 1


def test_restore_drill_dispatches_to_restore_set_for_a_non_live_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple] = []

    class _FakeManifest:
        generation = 9

    class _FakeRestored:
        manifest = _FakeManifest()

    def _fake_restore_set(manifest_path, dest_dir, *, key_provider):
        calls.append((manifest_path, dest_dir, key_provider))
        return _FakeRestored()

    monkeypatch.setattr(cli, "restore_set", _fake_restore_set)

    manifest_path = tmp_path / "gen9.set.manifest.json"
    dest = tmp_path / "restored"
    exit_code = cli.main(
        [
            "restore-drill",
            "--manifest",
            str(manifest_path),
            "--dest",
            str(dest),
            "--environment-label",
            "non-live-test",
            "--custody-root",
            str(tmp_path / "custody"),
        ]
    )

    assert exit_code == 0
    assert len(calls) == 1
    called_manifest_path, called_dest, key_provider = calls[0]
    assert called_manifest_path == manifest_path
    assert called_dest == dest
    assert key_provider is not None


# -- migrate --------------------------------------------------------------------


def test_migrate_runs_every_store_when_store_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        cli,
        "apply_migrations",
        lambda path, store_name: calls.append((path, store_name)),
    )

    data_dir = tmp_path / "data"
    exit_code = cli.main(["migrate", "--data-dir", str(data_dir)])

    assert exit_code == 0
    assert {store_name for _, store_name in calls} == set(STORE_MIGRATIONS)
    assert len(calls) == len(STORE_MIGRATIONS)


def test_migrate_runs_only_the_named_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        cli,
        "apply_migrations",
        lambda path, store_name: calls.append((path, store_name)),
    )

    data_dir = tmp_path / "data"
    exit_code = cli.main(["migrate", "--data-dir", str(data_dir), "--store", "rcl"])

    assert exit_code == 0
    assert len(calls) == 1
    path, store_name = calls[0]
    assert store_name == "rcl"
    assert path == DurableSetPaths.from_data_dir(data_dir).rcl


def test_migrate_rejects_an_unregistered_store_at_parse_time(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        cli.parse_args(
            ["migrate", "--data-dir", str(tmp_path / "data"), "--store", "nonexistent"]
        )


# -- print-digests ----------------------------------------------------------------


def test_print_digests_dispatches_and_prints_the_exact_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sentinel_observation = object()
    monkeypatch.setattr(cli, "observe_runtime_artifact", lambda: sentinel_observation)
    monkeypatch.setattr(
        cli,
        "print_digests_text",
        lambda observation: (
            "SENTINEL-OUTPUT\n" if observation is sentinel_observation else "WRONG"
        ),
    )

    exit_code = cli.main(["print-digests"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "SENTINEL-OUTPUT\n"


def test_print_digests_takes_no_extra_arguments(tmp_path: Path) -> None:
    args = cli.parse_args(["print-digests"])
    assert isinstance(args, cli.PrintDigestsArgs)
