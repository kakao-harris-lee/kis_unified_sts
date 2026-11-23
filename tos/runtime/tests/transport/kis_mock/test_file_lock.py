"""The shared-state file lock's own hygiene: tmp residue and directory mode (issue #1129)."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from tos_runtime.transport.kis_mock.file_lock import (
    atomic_private_write,
    ensure_private_dir,
    exclusive_file_lock,
)


def test_a_leftover_tmp_from_a_killed_writer_is_swept(tmp_path: Path) -> None:
    """LOW 3: SIGKILL between the tmp write and the rename leaves a token-bearing file."""
    path = tmp_path / "tokens" / "stock-mock.json"
    ensure_private_dir(path.parent)
    stale = path.with_name(f"{path.name}.999999.tmp")
    stale.write_text('{"entries":{"x":{"access_token":"leaked"}}}', encoding="utf-8")

    atomic_private_write(path, "fresh")

    assert path.read_text(encoding="utf-8") == "fresh"
    assert not stale.exists(), "a dead writer's token file survived the next write"
    assert list(path.parent.glob("*.tmp")) == []


def test_the_sweep_leaves_another_states_tmp_alone(tmp_path: Path) -> None:
    """The sweep is anchored to this path's own name — the pacer's grant file is not ours."""
    path = tmp_path / "stock-mock.json"
    other = tmp_path / "pacer.grant.4242.tmp"
    other.write_text("not ours", encoding="utf-8")

    atomic_private_write(path, "fresh")

    assert other.read_text(encoding="utf-8") == "not ours"


def test_an_existing_state_directory_is_narrowed(tmp_path: Path) -> None:
    """LOW 4: a directory made 0755 by an earlier boot stays readable to every local user."""
    directory = tmp_path / "tokens"
    directory.mkdir(mode=0o755)
    os.chmod(directory, 0o755)

    ensure_private_dir(directory)

    assert stat.S_IMODE(directory.stat().st_mode) == 0o700


def test_the_lock_narrows_the_directory_it_is_taken_in(tmp_path: Path) -> None:
    """Every entry point into the shared state goes through the same narrowing."""
    directory = tmp_path / "tokens"
    directory.mkdir(mode=0o700)
    os.chmod(directory, 0o777)

    with exclusive_file_lock(directory / "stock-mock.json.lock", wait_s=1.0):
        pass

    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
