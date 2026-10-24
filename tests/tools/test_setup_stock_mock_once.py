"""tools/tos_cp3/runners/setup_stock_mock_once.sh — the one-time stock MOCK setup (runbook §7.2-f).

The incident this pins (#953 review H1): the host's `.env.mock` values are QUOTED, and a custody
file that keeps the quotes is only refused at the first in-session token use — after genesis.
Hermetic: everything lives under tmp_path; the values are fake.
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools/tos_cp3/runners/setup_stock_mock_once.sh"
)


def _run(state: Path, env_mock: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(_SCRIPT), *args],
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(state),
            "TOS_STATE_ROOT": str(state),
            "TOS_ENV_MOCK": str(env_mock),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


@pytest.fixture()
def host(tmp_path: Path) -> tuple[Path, Path]:
    state = tmp_path / "state"
    state.mkdir()
    env_mock = tmp_path / ".env.mock"
    env_mock.write_text(
        'KIS_STOCK_ACCOUNT_NO="50000000-01"\n'
        "KIS_STOCK_APP_KEY='PSFAKEKEY'\n"
        'KIS_STOCK_APP_SECRET="FAKESECRET"\n',
        encoding="utf-8",
    )
    return state, env_mock


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_dry_run_writes_nothing(host: tuple[Path, Path]) -> None:
    state, env_mock = host
    result = _run(state, env_mock)
    assert result.returncode == 0, result.stderr
    assert list(state.iterdir()) == []


def test_apply_writes_unquoted_custody_with_narrow_modes(
    host: tuple[Path, Path],
) -> None:
    state, env_mock = host
    result = _run(state, env_mock, "--apply")
    assert result.returncode == 0, result.stderr
    custody = state / "cp3-setup-d-stock-custody"
    # Single- and double-quoted values both land without their quotes (#953 H1).
    assert (custody / "kis_mock.app_key").read_text(encoding="utf-8") == "PSFAKEKEY"
    assert (custody / "kis_mock.app_secret").read_text(encoding="utf-8") == "FAKESECRET"
    for directory in (
        state / "cp3-setup-d-stock-005930-data",
        state / "cp3-setup-d-stock-ops",
        custody,
        custody / "approvals",
    ):
        assert _mode(directory) == 0o700, directory
    for name in (
        "read.principal",
        "evidence.key",
        "evidence.key.1",
        "replay.params",
        "kis_mock.app_key",
        "kis_mock.app_secret",
        "custody.manifest.yaml",
    ):
        assert _mode(custody / name) == 0o600, name
    transport = state / "cp3-setup-d-stock-ops/kis_mock_transport.yaml"
    assert _mode(transport) == 0o600
    text = transport.read_text(encoding="utf-8")
    assert 'ACNT_PRDT_CD: "01"' in text and "mode: live" in text
    assert (
        "principal: kis-mock-order-paper"
        in (custody / "custody.manifest.yaml").read_text()
    )
    # Secrets never reach the terminal.
    assert "PSFAKEKEY" not in result.stdout + result.stderr
    assert "FAKESECRET" not in result.stdout + result.stderr


def test_rerun_refuses_to_overwrite(host: tuple[Path, Path]) -> None:
    state, env_mock = host
    assert _run(state, env_mock, "--apply").returncode == 0
    key = state / "cp3-setup-d-stock-custody/kis_mock.app_key"
    before = key.read_bytes()
    again = _run(state, env_mock, "--apply")
    assert again.returncode != 0
    assert key.read_bytes() == before
