"""Focused tests for the ``expected_code_digest`` re-derivation tool.

One test per property the tool is relied on for: ``--check`` is RED when any of the
three pins is stale and GREEN when they all match; ``--write`` rewrites the pin in all
three files and changes NOTHING else; an unreadable pin is an error, not a pass (a
checker that cannot measure must not report success -- the "empty equals empty is not a
match" lesson from the resident session's own digest guard).

The three fixtures are copies of the REAL deploy files, so "only the pin line changed"
is asserted about the file an operator actually deploys. The measurement is stubbed in
the file-level tests (the tool's subprocess call into the runtime CLI is covered on its
own by the last test, which proves the real path produces a real digest).
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "tos_redigest.py"


def _load_redigest_module():
    spec = importlib.util.spec_from_file_location("tos_redigest", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tr = _load_redigest_module()

#: Two digests that are structurally valid but different -- "stale" has to be another
#: well-formed digest, not garbage, or the test would prove only that the tool rejects
#: garbage.
_MEASURED = "a" * 64
_STALE = "b" * 64


@pytest.fixture()
def fake_repo(tmp_path: Path) -> Path:
    """A scratch repo root holding copies of the three real ``release.yaml`` files."""
    for name in tr.RELEASE_FILES:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_REPO_ROOT / name, destination)
    return tmp_path


def _stub_measurement(monkeypatch: pytest.MonkeyPatch, digest: str) -> None:
    monkeypatch.setattr(tr, "measure_code_digest", lambda *a, **k: digest)


def test_check_is_green_when_every_pin_matches_the_measurement(
    fake_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in tr.RELEASE_FILES:
        tr.write_pin(fake_repo / name, _MEASURED)
    _stub_measurement(monkeypatch, _MEASURED)

    assert tr.main(["--check", "--repo-root", str(fake_repo)]) == 0
    assert "OK" in capsys.readouterr().out


@pytest.mark.parametrize("stale_file", tr.RELEASE_FILES)
def test_check_is_red_when_any_one_pin_is_stale(
    stale_file: str,
    fake_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Parametrized over all three files: the tenant copies have never booted, so a
    stale pin there has no other lane in which it could surface before the boot that
    fails."""
    for name in tr.RELEASE_FILES:
        tr.write_pin(fake_repo / name, _MEASURED)
    tr.write_pin(fake_repo / stale_file, _STALE)
    _stub_measurement(monkeypatch, _MEASURED)

    assert tr.main(["--check", "--repo-root", str(fake_repo)]) == 1
    err = capsys.readouterr().err
    assert _MEASURED in err and _STALE in err
    assert stale_file in err
    assert "tools/tos_redigest.py --write" in err


def test_write_changes_the_pin_line_in_all_three_files_and_nothing_else(
    fake_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = {
        name: (fake_repo / name).read_text(encoding="utf-8")
        for name in tr.RELEASE_FILES
    }
    _stub_measurement(monkeypatch, _MEASURED)

    assert tr.main(["--write", "--repo-root", str(fake_repo)]) == 0

    for name in tr.RELEASE_FILES:
        after = (fake_repo / name).read_text(encoding="utf-8")
        assert tr.read_pin(fake_repo / name) == _MEASURED
        # Exactly one line moved, and it is the pin line -- the header comments, which
        # carry the file's provenance and its history, are untouched.
        before_lines = before[name].splitlines(keepends=True)
        after_lines = after.splitlines(keepends=True)
        assert len(before_lines) == len(after_lines)
        moved = [i for i, (b, a) in enumerate(zip(before_lines, after_lines)) if b != a]
        assert len(moved) == 1, f"{name}: {len(moved)} lines changed, expected 1"
        assert after_lines[moved[0]].startswith("expected_code_digest:")


def test_write_is_a_no_op_when_the_pins_are_already_current(
    fake_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in tr.RELEASE_FILES:
        tr.write_pin(fake_repo / name, _MEASURED)
    mtimes = {name: (fake_repo / name).stat().st_mtime_ns for name in tr.RELEASE_FILES}
    _stub_measurement(monkeypatch, _MEASURED)

    assert tr.main(["--write", "--repo-root", str(fake_repo)]) == 0
    assert "already current" in capsys.readouterr().out
    for name in tr.RELEASE_FILES:
        assert (fake_repo / name).stat().st_mtime_ns == mtimes[name]


def test_an_unreadable_pin_is_an_error_not_a_pass(
    fake_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fail-closed: if the key is renamed away, ``--check`` must not conclude that
    nothing disagrees."""
    target = fake_repo / tr.RELEASE_FILES[0]
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            "\nexpected_code_digest:", "\nrenamed_key:"
        ),
        encoding="utf-8",
    )
    _stub_measurement(monkeypatch, _MEASURED)

    assert tr.main(["--check", "--repo-root", str(fake_repo)]) == 2
    assert "ERROR" in capsys.readouterr().err


def test_measurement_runs_the_runtime_cli_and_returns_a_real_digest() -> None:
    """The one test that exercises the real subprocess path: the tool must get its
    number from the runtime's own ``print-digests`` (the function boot-time admission
    calls), never from a reimplementation of the digest scheme."""
    measured = tr.measure_code_digest(_REPO_ROOT)
    assert re.fullmatch(r"[0-9a-f]{64}", measured)


def test_measurement_output_without_a_digest_line_is_an_error(
    fake_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``print-digests`` exiting 0 is not the same as ``print-digests`` answering.

    If the CLI's output ever stops carrying the key -- renamed, reformatted, or
    swallowed -- the measured value would be the empty string, and comparing it against
    a pin read by the same kind of regex is how "empty equals empty" passes for nothing.
    The regex demands 64 lowercase hex characters, so there is no empty measurement to
    compare; the absence is an error.
    """
    (fake_repo / "tos" / "src").mkdir(parents=True)
    (fake_repo / "tos" / "runtime" / "src").mkdir(parents=True)
    monkeypatch.setattr(
        tr.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="python_version: 3.12.12\n", stderr=""
        ),
    )

    assert tr.main(["--check", "--repo-root", str(fake_repo)]) == 2
    err = capsys.readouterr().err
    assert "ERROR" in err and "refusing to compare nothing" in err


def test_a_repo_root_without_the_source_roots_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """⛔ The failure this guard exists for: measuring one tree, pinning another.

    ``--repo-root`` only steers where the two packages are imported FROM. Point it at a
    directory that is not a checkout and the import would fall through to an installed
    (editable) ``tos``/``tos_runtime`` -- a different tree -- and ``--write`` would put
    that tree's digest into this one's ``release.yaml``, honest-looking and wrong. So a
    missing source root is refused before anything is measured.
    """
    assert tr.main(["--check", "--repo-root", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "missing source root(s)" in err
    assert str(tmp_path / "tos" / "src") in err


def test_source_roots_that_cannot_serve_the_packages_are_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same failure one step in: the roots EXIST but hold no packages.

    Which branch answers depends on the environment, and both are exit 2:

    * nothing installed (a plain dev checkout) -- the import fails and the subprocess
      exits non-zero;
    * ``tos``/``tos_runtime`` installed editable (this repo's CI installs both) -- the
      editable finder in ``sys.meta_path`` answers the import AHEAD of ``sys.path``, and
      the program's own ``commonpath`` check refuses because the module resolved outside
      the root it was told to measure.

    The second branch is the one that cannot be arranged hermetically (it needs an
    installed copy of another checkout), so this test is where CI exercises it. Asserting
    only "exit 2 with a message" is deliberate: pinning either wording would make the
    test pass in one environment and fail in the other.
    """
    (tmp_path / "tos" / "src").mkdir(parents=True)
    (tmp_path / "tos" / "runtime" / "src").mkdir(parents=True)

    assert tr.main(["--check", "--repo-root", str(tmp_path)]) == 2
    assert "tos_redigest: ERROR" in capsys.readouterr().err
