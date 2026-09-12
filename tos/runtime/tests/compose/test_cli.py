"""Hermetic tests for :mod:`tos_runtime.compose.cli` (TOS Phase 5 W4 plan §2 decision 10).

No filesystem/network access needed here beyond ``tmp_path``-rooted ``Path`` objects that are
never actually opened — every operations function this module dispatches to is monkeypatched, so
these tests pin ARGUMENT PARSING and DISPATCH shape only, never the underlying operations'
own behaviour (that is ``tests/operations/*``'s scope).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from tos_runtime.compose import cli
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.evidence.store import KeyContinuityVerdict, SqliteEvidenceStore
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


# -- rotate-key -----------------------------------------------------------------


def _write_key(root: Path, generation: int, data: bytes) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"evidence.key.{generation}"
    path.write_bytes(data)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def test_rotate_key_parses_args(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    custody_root = tmp_path / "custody"

    args = cli.parse_args(
        [
            "rotate-key",
            "--data-dir",
            str(data_dir),
            "--custody-root",
            str(custody_root),
            "--new-generation",
            "2",
        ]
    )

    assert isinstance(args, cli.RotateKeyArgs)
    assert args.data_dir == data_dir
    assert args.custody_root == custody_root
    assert args.new_generation == 2


def test_rotate_key_dispatches_with_the_right_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: dict[str, object] = {}

    class _FakeKeyProvider:
        pass

    class _FakeStore:
        def close(self) -> None:
            calls["store_closed"] = True

    class _FakeRclLog:
        def close(self) -> None:
            calls["rcl_closed"] = True

    def _fake_file_key_provider(custody_root: Path, *, expected_owner_uid: int):
        calls["custody_root"] = custody_root
        return _FakeKeyProvider()

    def _fake_store_ctor(
        path: Path, *, key_provider, permit_rotation_pending_for_generation
    ):
        calls["evidence_path"] = path
        calls["permit"] = permit_rotation_pending_for_generation
        return _FakeStore()

    def _fake_rcl_ctor(path: Path, *, evidence_port):
        calls["rcl_path"] = path
        calls["evidence_port"] = evidence_port
        return _FakeRclLog()

    def _fake_rotate(store, key_provider, rcl_log, new_generation):
        calls["rotate_args"] = (store, key_provider, rcl_log, new_generation)
        return cli.RotationOutcome.ROTATED

    monkeypatch.setattr(cli, "FileKeyProvider", _fake_file_key_provider)
    monkeypatch.setattr(cli, "SqliteEvidenceStore", _fake_store_ctor)
    monkeypatch.setattr(cli, "SqliteCommitLog", _fake_rcl_ctor)
    monkeypatch.setattr(cli, "rotate_evidence_key", _fake_rotate)

    data_dir = tmp_path / "data"
    custody_root = tmp_path / "custody"
    exit_code = cli.main(
        [
            "rotate-key",
            "--data-dir",
            str(data_dir),
            "--custody-root",
            str(custody_root),
            "--new-generation",
            "2",
        ]
    )

    assert exit_code == 0
    assert calls["custody_root"] == custody_root
    assert calls["permit"] == 2
    assert calls["evidence_path"] == DurableSetPaths.from_data_dir(data_dir).evidence
    assert calls["rcl_path"] == DurableSetPaths.from_data_dir(data_dir).rcl
    assert calls["store_closed"] is True
    assert calls["rcl_closed"] is True


def test_rotate_key_reports_non_zero_for_rotated_rcl_unrecorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FakeStore:
        def close(self) -> None:
            pass

    class _FakeRclLog:
        def close(self) -> None:
            pass

    monkeypatch.setattr(cli, "FileKeyProvider", lambda *_a, **_k: object())
    monkeypatch.setattr(cli, "SqliteEvidenceStore", lambda *_a, **_k: _FakeStore())
    monkeypatch.setattr(cli, "SqliteCommitLog", lambda *_a, **_k: _FakeRclLog())
    monkeypatch.setattr(
        cli,
        "rotate_evidence_key",
        lambda *_a, **_k: cli.RotationOutcome.ROTATED_RCL_UNRECORDED,
    )

    exit_code = cli.main(
        [
            "rotate-key",
            "--data-dir",
            str(tmp_path / "data"),
            "--custody-root",
            str(tmp_path / "custody"),
            "--new-generation",
            "2",
        ]
    )

    assert exit_code == 1


def test_rotate_key_reports_a_continuity_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _refuse(*args: object, **kwargs: object):
        raise cli.KeyContinuityRefused("boom")

    monkeypatch.setattr(cli, "FileKeyProvider", lambda *_a, **_k: object())
    monkeypatch.setattr(cli, "SqliteEvidenceStore", _refuse)

    def _must_not_be_called(*args: object, **kwargs: object):
        raise AssertionError(
            "rotate_evidence_key must not be called after a refused open"
        )

    monkeypatch.setattr(cli, "rotate_evidence_key", _must_not_be_called)

    exit_code = cli.main(
        [
            "rotate-key",
            "--data-dir",
            str(tmp_path / "data"),
            "--custody-root",
            str(tmp_path / "custody"),
            "--new-generation",
            "2",
        ]
    )

    assert exit_code == 1


def test_rotate_key_reports_a_rotation_refusal_and_still_closes_handles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: dict[str, object] = {}

    class _FakeStore:
        def close(self) -> None:
            calls["store_closed"] = True

    class _FakeRclLog:
        def close(self) -> None:
            calls["rcl_closed"] = True

    def _refuse(*args: object, **kwargs: object):
        raise cli.KeyRotationRefused("nope")

    monkeypatch.setattr(cli, "FileKeyProvider", lambda *_a, **_k: object())
    monkeypatch.setattr(cli, "SqliteEvidenceStore", lambda *_a, **_k: _FakeStore())
    monkeypatch.setattr(cli, "SqliteCommitLog", lambda *_a, **_k: _FakeRclLog())
    monkeypatch.setattr(cli, "rotate_evidence_key", _refuse)

    exit_code = cli.main(
        [
            "rotate-key",
            "--data-dir",
            str(tmp_path / "data"),
            "--custody-root",
            str(tmp_path / "custody"),
            "--new-generation",
            "2",
        ]
    )

    assert exit_code == 1
    assert calls["store_closed"] is True
    assert calls["rcl_closed"] is True


def test_rotate_key_real_end_to_end_gen1_then_place_gen2_then_rotate_then_reopen(
    tmp_path: Path,
) -> None:
    """The exact scenario team-lead's directive names: gen 1 → place gen 2 file 0600 →
    rotate → reopen succeeds."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    custody_root = tmp_path / "custody"

    _write_key(custody_root, 1, b"gen-1-key-bytes-000000000000000")
    provider = FileKeyProvider(custody_root, expected_owner_uid=os.getuid())
    store = SqliteEvidenceStore(data_dir / "evidence.sqlite3", key_provider=provider)
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    store.close()

    _write_key(custody_root, 2, b"gen-2-key-bytes-000000000000000")

    exit_code = cli.main(
        [
            "rotate-key",
            "--data-dir",
            str(data_dir),
            "--custody-root",
            str(custody_root),
            "--new-generation",
            "2",
        ]
    )
    assert exit_code == 0

    reopened_provider = FileKeyProvider(custody_root, expected_owner_uid=os.getuid())
    reopened = SqliteEvidenceStore(
        data_dir / "evidence.sqlite3", key_provider=reopened_provider
    )
    try:
        assert reopened.key_continuity.verdict == KeyContinuityVerdict.CONTINUOUS
        assert reopened.key_generation == 2
    finally:
        reopened.close()
