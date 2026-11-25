"""tools/tos_cp3/runners/setup_stock_mock_once.sh — the one-time stock MOCK setup (runbook §7.2-f)."""

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
    assert "PSFAKEKEY" not in result.stdout + result.stderr
    assert "FAKESECRET" not in result.stdout + result.stderr


def test_a_named_symbol_gets_its_own_data_ops_and_custody(
    host: tuple[Path, Path],
) -> None:
    """One stock tenant per symbol (operator directive 2026-11-19)."""
    state, env_mock = host
    assert _run(state, env_mock, "000660", "--apply").returncode == 0
    for directory in (
        state / "cp3-setup-d-stock-000660-data",
        state / "cp3-setup-d-stock-000660-ops",
        state / "cp3-setup-d-stock-000660-custody",
        state / "cp3-setup-d-stock-000660-custody/approvals",
    ):
        assert directory.is_dir() and _mode(directory) == 0o700, directory
    assert (state / "cp3-setup-d-stock-000660-ops/kis_mock_transport.yaml").is_file()
    assert not (state / "cp3-setup-d-stock-custody").exists()
    assert not (state / "cp3-setup-d-stock-ops").exists()
    assert not (state / "cp3-setup-d-stock-005930-data").exists()
    assert _run(state, env_mock, "005380", "--apply").returncode == 0
    assert (state / "cp3-setup-d-stock-005380-custody/kis_mock.app_key").is_file()


def test_a_symbol_the_runner_does_not_know_is_refused(host: tuple[Path, Path]) -> None:
    """The tenant set lives in `cp3_tenant_daily.sh`, and this script reads it from there."""
    state, env_mock = host
    result = _run(state, env_mock, "999999", "--apply")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "STOCK_SYMBOLS" in result.stderr, result.stderr
    assert list(state.iterdir()) == []


def test_a_symbol_that_is_not_six_digits_is_refused(host: tuple[Path, Path]) -> None:
    state, env_mock = host
    result = _run(state, env_mock, "00066", "--apply")
    assert result.returncode == 2, result.stdout + result.stderr
    assert list(state.iterdir()) == []


def test_rerun_refuses_to_overwrite(host: tuple[Path, Path]) -> None:
    state, env_mock = host
    assert _run(state, env_mock, "--apply").returncode == 0
    key = state / "cp3-setup-d-stock-custody/kis_mock.app_key"
    before = key.read_bytes()
    again = _run(state, env_mock, "--apply")
    assert again.returncode != 0
    assert key.read_bytes() == before


def test_every_tenant_is_pointed_at_one_shared_token_cache(
    host: tuple[Path, Path],
) -> None:
    """#1125: one KIS app key, one token a minute, so one token FILE for every tenant."""
    state, env_mock = host
    assert _run(state, env_mock, "--apply").returncode == 0
    assert _run(state, env_mock, "000660", "--apply").returncode == 0
    cache = state / "kis-mock-token" / "stock-mock.json"
    pacer = state / "kis-mock-token" / "stock-mock.pace"
    assert _mode(cache.parent) == 0o700
    for ops in ("cp3-setup-d-stock-ops", "cp3-setup-d-stock-000660-ops"):
        text = (state / ops / "kis_mock_transport.yaml").read_text(encoding="utf-8")
        assert f'token_cache_path: "{cache}"' in text
        assert "token_cache_refresh_margin_s: 600" in text
        assert f'shared_pacer_path: "{pacer}"' in text
        assert "shared_max_rps: 2.0" in text
        assert "shared_window_margin_s: 0.25" in text
        assert "token_reissue_min_interval_s: 65" in text
