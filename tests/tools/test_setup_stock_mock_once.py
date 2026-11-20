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


def test_a_named_symbol_gets_its_own_data_ops_and_custody(
    host: tuple[Path, Path],
) -> None:
    """One stock tenant per symbol (operator directive 2026-11-19).

    Custody is the one that may NEVER be shared: the standing approval artifact's path is
    fixed relative to the custody root and the document binds to one tenant's rendered
    config, so a shared root would have each tenant's boot bind another tenant's approval.
    Only 005930 keeps the symbol-less host paths its 2026-11-06 deployment was born with.
    """
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
    # The legacy tenant's places are untouched, so this is additive on a live host.
    assert not (state / "cp3-setup-d-stock-custody").exists()
    assert not (state / "cp3-setup-d-stock-ops").exists()
    assert not (state / "cp3-setup-d-stock-005930-data").exists()
    # And a second symbol lands beside the first rather than refusing it.
    assert _run(state, env_mock, "005380", "--apply").returncode == 0
    assert (state / "cp3-setup-d-stock-005380-custody/kis_mock.app_key").is_file()


def test_a_symbol_the_runner_does_not_know_is_refused(host: tuple[Path, Path]) -> None:
    """The tenant set lives in `cp3_tenant_daily.sh`, and this script reads it from there.

    Preparing host state for a symbol the runner will never start leaves custody keys and a
    durable-set parent that nothing owns — and, worse, makes it look like the tenant is
    ready. Two copies of the set would be the same defect one edit later, so there is one.
    """
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
    """#1125: one KIS app key, one token a minute, so one token FILE for every tenant.

    2026-11-20 12:50 KST: 005930's own token issuance lost the per-minute race to 000660
    and 005380 on every retry, which left its broker facts None and every signal at
    SEND_REFUSED for the session.
    """
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
        # One queue too: KIS counts requests per app key, so three tenants pacing
        # themselves independently put three into one second (11-20 13:00 HTTP 500).
        assert f'shared_pacer_path: "{pacer}"' in text
        assert "shared_max_rps: 2.0" in text
        # ≥65s, not 60: a 60s cooldown against a ~60s poll put every other retry
        # 0.4s inside its own window (TokenStale at 59.6s on 11-20).
        assert "token_reissue_min_interval_s: 65" in text
