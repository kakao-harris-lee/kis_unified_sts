"""tools/tos_cp3/ops/restart_stock_tenant.sh — the gates that run before anything is touched.

Every case here stops in the argument/precondition block, so the script never
stops a session, never reads a balance and never moves a leaf: the assertions are
that it exits 2 and that the state root is still empty. That ordering is the
safety property — a restart that was invoked without the account fingerprint, or
for a symbol that is not a tenant, must not have killed the session it was about
to repair.

Hermetic: fake state root, fake primary checkout, no broker call, no git clone.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[2] / "tools/tos_cp3/ops/restart_stock_tenant.sh"
)
_FP = "ee1bdb5f1ca2"


@pytest.fixture()
def host(tmp_path: Path) -> Path:
    """A state root with the session directory the script requires, nothing else."""
    (tmp_path / "state" / "cp3-sessions").mkdir(parents=True)
    (tmp_path / "main").mkdir()
    return tmp_path


def _run(
    host: Path, *args: str, fingerprint: str | None = None
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(host),
        "CP3_DAILY_MAIN": str(host / "main"),
        "CP3_DAILY_STATE": str(host / "state"),
    }
    if fingerprint is not None:
        env["CP3_EXPECT_ACCOUNT_FP"] = fingerprint
    return subprocess.run(
        ["bash", str(_SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _untouched(host: Path) -> bool:
    return list((host / "state").iterdir()) == [host / "state" / "cp3-sessions"] and (
        list((host / "state" / "cp3-sessions").iterdir()) == []
    )


def test_script_parses() -> None:
    result = subprocess.run(
        ["bash", "-n", str(_SCRIPT)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_missing_fingerprint_refuses_before_touching_anything(host: Path) -> None:
    result = _run(host, "005930")
    assert result.returncode == 2, result.stderr
    assert "CP3_EXPECT_ACCOUNT_FP" in result.stderr
    assert _untouched(host)


def test_empty_fingerprint_env_is_still_a_refusal(host: Path) -> None:
    result = _run(host, "005930", fingerprint="")
    assert result.returncode == 2, result.stderr
    assert "CP3_EXPECT_ACCOUNT_FP" in result.stderr
    assert _untouched(host)


def test_fingerprint_flag_is_accepted_and_the_next_gate_refuses(host: Path) -> None:
    # The flag satisfies the fingerprint gate; the fake primary checkout has no
    # .venv, so the run still stops — before the stop/flat-check/archive steps.
    result = _run(host, "005930", "--expect-account-fingerprint", _FP)
    assert result.returncode == 2, result.stderr
    assert ".venv/bin/python" in result.stdout + result.stderr
    assert _untouched(host)


def test_fingerprint_flag_without_a_value_is_a_usage_error(host: Path) -> None:
    result = _run(host, "005930", "--expect-account-fingerprint")
    assert result.returncode == 2, result.stderr
    assert _untouched(host)


@pytest.mark.parametrize("symbol", ["5930", "0059300", "00593a"])
def test_symbol_must_be_six_digits(host: Path, symbol: str) -> None:
    result = _run(host, symbol, fingerprint=_FP)
    assert result.returncode == 2, result.stderr
    assert "6자리" in result.stderr
    assert _untouched(host)


def test_symbol_must_be_one_of_the_runners_tenants(host: Path) -> None:
    result = _run(host, "999999", fingerprint=_FP)
    assert result.returncode == 2, result.stderr
    assert "STOCK_SYMBOLS" in result.stderr
    assert _untouched(host)


def test_tag_cannot_escape_the_archive_directory_name(host: Path) -> None:
    result = _run(host, "005930", "../../etc", fingerprint=_FP)
    assert result.returncode == 2, result.stderr
    assert _untouched(host)


def test_extra_positional_arguments_are_refused(host: Path) -> None:
    result = _run(host, "005930", "tag", "surplus", fingerprint=_FP)
    assert result.returncode == 2, result.stderr
    assert _untouched(host)


def test_help_exits_zero_without_touching_the_host(host: Path) -> None:
    result = _run(host, "--help")
    assert result.returncode == 0, result.stderr
    assert "restart_stock_tenant.sh" in result.stdout
    assert _untouched(host)
