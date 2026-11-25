"""Unit tests for the tos import-firewall gate (``tools/tos_firewall_check.py``)."""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

from tests.support import git_env

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "tos_firewall_check.py"


def _load_firewall():
    spec = importlib.util.spec_from_file_location("tos_firewall_check", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fw = _load_firewall()


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _make_tos_src(repo: Path, filename: str, body: str) -> Path:
    """Create <repo>/tos/src/tos/<filename> with <body> and return the path."""
    return _write(repo / "tos" / "src" / "tos" / filename, body)


def _make_tos_runtime_src(repo: Path, filename: str, body: str) -> Path:
    """Create <repo>/tos/runtime/src/tos_runtime/<filename> with <body> and"""
    return _write(repo / "tos" / "runtime" / "src" / "tos_runtime" / filename, body)


def _runtime_rel(filename: str) -> str:
    """The repo-root-relative display path a real ``run_checks`` call would"""
    return f"tos/runtime/src/tos_runtime/{filename}"


def _rules(violations) -> set[str]:
    return {v.rule for v in violations}


@pytest.mark.parametrize(
    ("body", "display"),
    [
        ("import requests\n", "tos/src/tos/m.py"),
        ("from shared.execution import Foo\n", "tos/src/tos/m.py"),
        ("import shared\n", "m.py"),
        ("from shared.config import secrets\n", "m.py"),
        ("from shared.config import ConfigLoader\n", "m.py"),
    ],
)
def test_rule_a_denied_import(tmp_path, body, display):
    """Third-party, operational `shared`, bare `shared`, and all of `shared.config`."""
    path = _make_tos_src(tmp_path, "m.py", body)
    assert "TOS-FW-A" in _rules(fw.check_tos_file(path, display))


def test_rule_a_nested_import_is_caught(tmp_path):
    body = "def handler():\n    import requests\n    return requests\n"
    path = _make_tos_src(tmp_path, "m.py", body)
    violations = fw.check_tos_file(path, "m.py")
    assert "TOS-FW-A" in _rules(violations)
    assert violations[0].line == 2


@pytest.mark.parametrize(
    "body",
    [
        "import socket\n",
        "import ssl\n",
        "import subprocess\n",
        "import ctypes\n",
        "import http.client\n",
        "from urllib.request import urlopen\n",
        "from urllib import request\n",
    ],
)
def test_rule_b_forbidden_stdlib(tmp_path, body):
    path = _make_tos_src(tmp_path, "m.py", body)
    assert "TOS-FW-B" in _rules(fw.check_tos_file(path, "m.py"))


def test_rule_b_nested_forbidden_stdlib(tmp_path):
    body = "def f():\n    import socket\n    return socket\n"
    path = _make_tos_src(tmp_path, "m.py", body)
    assert "TOS-FW-B" in _rules(fw.check_tos_file(path, "m.py"))


@pytest.mark.parametrize(
    "body",
    [
        "import os\n\n\ndef f():\n    return os.getenv('X')\n",
        "import os\n\n\ndef f():\n    return os.environ['X']\n",
        "from os import getenv\n",
    ],
)
def test_rule_c_env_access(tmp_path, body):
    path = _make_tos_src(tmp_path, "m.py", body)
    assert "TOS-FW-C" in _rules(fw.check_tos_file(path, "m.py"))


@pytest.mark.parametrize(
    "body",
    [
        "x = eval('1 + 1')\n",
        "exec('x = 1')\n",
        "m = __import__('socket')\n",
        "import importlib\nm = importlib.import_module('socket')\n",
        "from importlib import import_module\n",
    ],
)
def test_rule_d_dynamic_import(tmp_path, body):
    path = _make_tos_src(tmp_path, "m.py", body)
    assert "TOS-FW-D" in _rules(fw.check_tos_file(path, "m.py"))


def test_rule_r_reverse_import_detected(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "services" / "foo.py", "import tos\n\nprint(tos.__version__)\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" in _rules(violations)
    assert any(v.path.endswith("foo.py") for v in violations)


def test_rule_r_from_tos_import_detected(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "cli" / "bar.py", "from tos.models import Thing\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" in _rules(violations)


def test_rule_r_similar_name_not_flagged(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "pkg" / "baz.py", "import tos_korean\nimport tosca\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" not in _rules(violations)


def test_rule_r_import_inside_tos_not_flagged(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _make_tos_src(tmp_path, "sub.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" not in _rules(violations)


def test_rule_r_nested_dir_named_tos_is_scanned(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "services" / "tos" / "x.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" in _rules(violations)
    assert any(v.path.endswith("services/tos/x.py") for v in violations)


@pytest.mark.parametrize(
    "rel",
    [
        ("shared", "node_modules", "x.py"),
        ("shared", "__pycache__", "x.py"),
        ("docs", "reviews", "phase0-completion-contract", "probe.py"),
        ("strategy-builder-ui", "tooling", "gen.py"),
    ],
)
def test_rule_r_directory_a_generic_walker_would_prune_is_scanned(tmp_path, rel):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path.joinpath(*rel), "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" in _rules(violations)


def test_rule_r_open_trading_api_pruned(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "open-trading-api" / "vendored" / "x.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert not any(
        v.path.endswith("open-trading-api/vendored/x.py") for v in violations
    )


def test_rule_r_strategy_builder_ui_node_modules_pruned_but_rest_scanned(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "strategy-builder-ui" / "node_modules" / "x.py", "import tos\n")
    _write(tmp_path / "strategy-builder-ui" / "x.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert not any(
        v.path.endswith("strategy-builder-ui/node_modules/x.py") for v in violations
    )
    assert any(v.path == "strategy-builder-ui/x.py" for v in violations)


def test_rule_r_nested_venv_named_dir_is_scanned(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "shared" / ".venv" / "x.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" in _rules(violations)


def test_rule_r_explicit_generated_roots_still_pruned(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / ".venv" / "lib" / "site-packages" / "x.py", "import tos\n")
    _write(tmp_path / ".omc" / "x.py", "import tos\n")
    _write(tmp_path / ".history" / "x.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" not in _rules(violations)


def test_rule_r_root_tos_dir_not_scanned_by_reverse_rule(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _make_tos_src(tmp_path, "y.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" not in _rules(violations)


_GIT_AVAILABLE = git_env.git_cli_available()


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "config",
            "user.name",
            "Test",
        ],
        cwd=repo,
        check=True,
    )


@pytest.mark.skipif(not _GIT_AVAILABLE, reason="git not available")
def test_rule_r_force_tracked_py_under_pruned_root_is_reported(tmp_path):
    _git_init(tmp_path)
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / ".gitignore", "open-trading-api/\n")
    _write(tmp_path / "open-trading-api" / "x.py", "import tos\n")
    _write(tmp_path / "open-trading-api" / "y.py", "import tos\n")
    subprocess.run(
        ["git", "add", "-f", "open-trading-api/x.py"], cwd=tmp_path, check=True
    )

    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert any(v.path.endswith("open-trading-api/x.py") for v in violations)
    assert not any(v.path.endswith("open-trading-api/y.py") for v in violations)


@pytest.mark.skipif(not _GIT_AVAILABLE, reason="git not available")
def test_rule_r_force_tracked_py_under_root_tos_not_yielded(tmp_path):
    _git_init(tmp_path)
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "tos" / "src" / "tos" / "z.py", "import tos\n")
    subprocess.run(["git", "add", "-f", "tos/src/tos/z.py"], cwd=tmp_path, check=True)

    walked = list(fw._walk_repo_py(tmp_path))
    assert not any("tos/src/tos/z.py" in str(p) for p in walked)


_SYMLINKS_SUPPORTED = hasattr(os, "symlink")


def _try_symlink(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(target, link)


@pytest.mark.skipif(not _GIT_AVAILABLE, reason="git not available")
@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_r_force_tracked_symlink_into_tos_is_reported_at_lexical_path(tmp_path):
    _git_init(tmp_path)
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "tos" / "src" / "tos" / "mod.py", "from tos import something\n")
    _write(tmp_path / ".gitignore", "open-trading-api/\n")
    _try_symlink(
        tmp_path / "open-trading-api" / "x.py",
        tmp_path / "tos" / "src" / "tos" / "mod.py",
    )
    subprocess.run(
        ["git", "add", "-f", "open-trading-api/x.py"], cwd=tmp_path, check=True
    )

    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert any(v.path.endswith("open-trading-api/x.py") for v in violations)


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_r_walked_symlink_into_tos_is_reported_at_lexical_path(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "tos" / "src" / "tos" / "mod.py", "from tos import x\n")
    _try_symlink(
        tmp_path / "shared" / "x.py", tmp_path / "tos" / "src" / "tos" / "mod.py"
    )

    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert any(v.path.endswith("shared/x.py") for v in violations)


def test_rule_r_real_file_under_tos_root_not_reported(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _make_tos_src(tmp_path, "mod.py", "from tos import x\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" not in _rules(violations)


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_r_symlink_with_no_tos_import_not_reported(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "shared" / "real.py", "import json\n")
    _try_symlink(tmp_path / "shared" / "y.py", tmp_path / "shared" / "real.py")

    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" not in _rules(violations)


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_forward_scan_symlink_out_of_tos_is_still_scanned(tmp_path):
    tos_dir = tmp_path / "tos"
    _write(tmp_path / "shared" / "execution.py", "import shared.execution\n")
    _try_symlink(
        tos_dir / "src" / "tos" / "leak.py", tmp_path / "shared" / "execution.py"
    )
    violations = fw.check_tos_file(
        tos_dir / "src" / "tos" / "leak.py", "tos/src/tos/leak.py"
    )
    assert "TOS-FW-A" in _rules(violations)


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_s_walked_dir_symlink_into_tos_is_reported(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "tos" / "src" / "tos" / "mod.py", "from tos import x\n")
    _try_symlink(tmp_path / "shared" / "link", tmp_path / "tos" / "src" / "tos")

    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    s_violations = [v for v in violations if v.rule == "TOS-FW-S"]
    assert any(v.path.endswith("shared/link") for v in s_violations)


@pytest.mark.skipif(not _GIT_AVAILABLE, reason="git not available")
@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_s_force_tracked_dir_symlink_under_pruned_root_is_reported(tmp_path):
    _git_init(tmp_path)
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "tos" / "src" / "tos" / "mod.py", "from tos import x\n")
    _write(tmp_path / ".gitignore", "open-trading-api/\n")
    _try_symlink(
        tmp_path / "open-trading-api" / "link", tmp_path / "tos" / "src" / "tos"
    )
    subprocess.run(
        ["git", "add", "-f", "open-trading-api/link"], cwd=tmp_path, check=True
    )

    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    s_violations = [v for v in violations if v.rule == "TOS-FW-S"]
    assert any(v.path.endswith("open-trading-api/link") for v in s_violations)


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_s_forward_dir_symlink_out_of_tos_is_reported(tmp_path):
    tos_dir = tmp_path / "tos"
    _write(tmp_path / "shared" / "execution" / "x.py", "import json\n")
    _try_symlink(tos_dir / "src" / "tos" / "out", tmp_path / "shared" / "execution")

    violations = fw._forward_scan_boundary_symlinks(tmp_path, tos_dir)
    s_violations = [v for v in violations if v.rule == "TOS-FW-S"]
    assert any(v.path.endswith("tos/src/tos/out") for v in s_violations)


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_s_same_side_symlinks_not_reported(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "shared" / "real" / "x.py", "import json\n")
    _try_symlink(tmp_path / "shared" / "alias", tmp_path / "shared" / "real")
    _write(tmp_path / "tos" / "src" / "tos" / "real" / "mod.py", "x = 1\n")
    _try_symlink(
        tmp_path / "tos" / "src" / "tos" / "alias",
        tmp_path / "tos" / "src" / "tos" / "real",
    )

    reverse_violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-S" not in _rules(reverse_violations)
    forward_violations = fw._forward_scan_boundary_symlinks(tmp_path, tmp_path / "tos")
    assert "TOS-FW-S" not in _rules(forward_violations)


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_s_dangling_symlink_is_reported_fail_closed(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _try_symlink(tmp_path / "shared" / "dead", tmp_path / "shared" / "does_not_exist")

    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    s_violations = [v for v in violations if v.rule == "TOS-FW-S"]
    assert any(v.path.endswith("shared/dead") for v in s_violations)


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_s_ancestor_of_tos_target_is_reported(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _try_symlink(tmp_path / "shared" / "up", tmp_path)

    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    s_violations = [v for v in violations if v.rule == "TOS-FW-S"]
    assert any(v.path.endswith("shared/up") for v in s_violations)


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_s_inside_tos_link_to_ancestor_within_tos_still_clean(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "tos" / "src" / "tos" / "deep" / "x.py", "x = 1\n")
    _try_symlink(
        tmp_path / "tos" / "src" / "tos" / "deep" / "link", tmp_path / "tos" / "src"
    )

    violations = fw._forward_scan_boundary_symlinks(tmp_path, tmp_path / "tos")
    assert "TOS-FW-S" not in _rules(violations)


@pytest.mark.skipif(not _GIT_AVAILABLE, reason="git not available")
@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_tos_root_as_resolvable_symlink_is_reported(tmp_path):
    _git_init(tmp_path)
    _write(tmp_path / "elsewhere" / "x.py", "x = 1\n")
    _try_symlink(tmp_path / "tos", tmp_path / "elsewhere")
    subprocess.run(["git", "add", "-f", "tos"], cwd=tmp_path, check=True)

    violations = fw.run_checks(tmp_path)
    s_violations = [v for v in violations if v.rule == "TOS-FW-S"]
    assert any(v.path == "tos" for v in s_violations)
    assert any("forward rules a-d cannot be evaluated" in v.message for v in violations)


@pytest.mark.skipif(not _GIT_AVAILABLE, reason="git not available")
@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_tos_root_as_dangling_symlink_is_reported(tmp_path):
    _git_init(tmp_path)
    _try_symlink(tmp_path / "tos", tmp_path / "does_not_exist")
    subprocess.run(["git", "add", "-f", "tos"], cwd=tmp_path, check=True)

    violations = fw.run_checks(tmp_path)
    s_violations = [v for v in violations if v.rule == "TOS-FW-S"]
    assert any(v.path == "tos" for v in s_violations)
    assert any("forward rules a-d cannot be evaluated" in v.message for v in violations)


@pytest.mark.skipif(not _GIT_AVAILABLE, reason="git not available")
@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_tos_root_symlink_drives_nonzero_exit_via_main(tmp_path):
    _git_init(tmp_path)
    _try_symlink(tmp_path / "tos", tmp_path / "does_not_exist")
    subprocess.run(["git", "add", "-f", "tos"], cwd=tmp_path, check=True)

    rc = fw.main(["--repo-root", str(tmp_path)])
    assert rc == 1


def test_real_tos_dir_not_flagged_as_symlink(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    violations = fw.run_checks(tmp_path)
    assert not any(v.path == "tos" and v.rule == "TOS-FW-S" for v in violations)
    assert not any(
        "forward rules a-d cannot be evaluated" in v.message for v in violations
    )


def test_missing_tos_dir_is_a_visible_failure_not_a_pass(tmp_path):
    violations = fw.run_checks(tmp_path)
    assert violations != []
    assert any("forward rules a-d cannot be evaluated" in v.message for v in violations)


def test_git_toplevel_probe_raises_on_dubious_ownership(monkeypatch, tmp_path):
    class _FakeResult:
        returncode = 128
        stdout = b""
        stderr = (
            b"fatal: detected dubious ownership in repository at '/x'\n"
            b"To add an exception for this directory, call:\n"
        )

    def _fake_run(args, **kwargs):
        return _FakeResult()

    monkeypatch.setattr(fw.subprocess, "run", _fake_run)
    with pytest.raises(RuntimeError):
        fw._git_toplevel_or_none(tmp_path)


def test_git_toplevel_probe_skips_silently_on_not_a_repo(monkeypatch, tmp_path):
    class _FakeResult:
        returncode = 128
        stdout = b""
        stderr = (
            b"fatal: not a git repository (or any of the parent directories): .git\n"
        )

    def _fake_run(args, **kwargs):
        return _FakeResult()

    monkeypatch.setattr(fw.subprocess, "run", _fake_run)
    assert fw._git_toplevel_or_none(tmp_path) is None


@pytest.mark.skipif(not _GIT_AVAILABLE, reason="git not available")
def test_run_checks_probes_git_at_most_once_per_kind(tmp_path, monkeypatch):
    _git_init(tmp_path)
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    real_run = fw.subprocess.run
    calls: list[list[str]] = []

    def _counting_run(args, **kwargs):
        calls.append(list(args))
        return real_run(args, **kwargs)

    monkeypatch.setattr(fw.subprocess, "run", _counting_run)
    fw.run_checks(tmp_path)

    rev_parse_calls = [c for c in calls if "rev-parse" in c]
    ls_files_calls = [c for c in calls if "ls-files" in c]
    assert len(rev_parse_calls) == 1
    assert len(ls_files_calls) <= 2


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_s_forward_venv_symlink_to_outside_is_reported(tmp_path):
    tos_dir = tmp_path / "tos"
    _write(tmp_path / "shared" / "x.py", "x = 1\n")
    _try_symlink(tos_dir / ".venv", tmp_path / "shared")

    violations = fw._forward_scan_boundary_symlinks(tmp_path, tos_dir)
    assert "TOS-FW-S" in _rules(violations)
    assert any(v.path.endswith("tos/.venv") for v in violations)


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_s_dangling_message_wording(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _try_symlink(tmp_path / "shared" / "dead2", tmp_path / "shared" / "gone")

    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    s_violations = [
        v
        for v in violations
        if v.rule == "TOS-FW-S" and v.path.endswith("shared/dead2")
    ]
    assert s_violations
    assert "dangling symlink (target unresolvable)" in s_violations[0].message
    assert "fail-closed" in s_violations[0].message


def test_allowed_imports_pass(tmp_path):
    body = (
        "import json\n"
        "import os\n"
        "import numpy\n"
        "import pandas as pd\n"
        "import yaml\n"
        "from datetime import datetime\n"
        "from urllib.parse import urlparse\n"
        "from pydantic import BaseModel\n"
        "from shared import models\n"
        "from shared.indicators import rsi\n"
        "from shared.determinism import LookaheadGuard\n"
        "from tos.models import Thing\n"
        "from . import sibling\n"
    )
    path = _make_tos_src(tmp_path, "m.py", body)
    violations = fw.check_tos_file(path, "m.py")
    assert violations == [], f"unexpected violations: {violations}"


def test_run_checks_clean_tree_passes(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _make_tos_src(tmp_path, "model.py", "from pydantic import BaseModel\n")
    _write(tmp_path / "tos" / "tests" / "test_x.py", "import tos\n")
    _write(tmp_path / "services" / "clean.py", "import json\n")
    assert fw.run_checks(tmp_path) == []


def test_run_checks_reports_multiple_rules(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _make_tos_src(tmp_path, "bad.py", "import socket\nimport requests\n")
    _write(tmp_path / "services" / "rev.py", "import tos\n")
    rules = _rules(fw.run_checks(tmp_path))
    assert {"TOS-FW-A", "TOS-FW-B", "TOS-FW-R"} <= rules


def test_iter_py_files_prunes_venv(tmp_path):
    tos_dir = tmp_path / "tos"
    _write(tos_dir / "src" / "tos" / "x.py", "import shared.execution\n")
    _write(
        tos_dir / ".venv" / "lib" / "python3.11" / "site-packages" / "leaked.py",
        "import shared.execution\n",
    )
    files = list(fw._iter_py_files(tos_dir))
    rels = {p.relative_to(tos_dir) for p in files}
    assert Path("src/tos/x.py") in rels
    assert not any(".venv" in p.parts for p in files)


def test_run_checks_ignores_venv_but_still_catches_src_violations(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "tos" / "src" / "tos" / "bad.py", "import shared.execution\n")
    _write(
        tmp_path
        / "tos"
        / ".venv"
        / "lib"
        / "python3.11"
        / "site-packages"
        / "leaked.py",
        "import shared.execution\n",
    )
    violations = fw.run_checks(tmp_path)
    assert any(v.path.endswith("bad.py") for v in violations)
    assert not any(".venv" in v.path for v in violations)


def test_iter_py_files_pycache_dir_still_scanned(tmp_path):
    tos_dir = tmp_path / "tos"
    path = _write(
        tos_dir / "src" / "tos" / "__pycache__" / "egress.py",
        "import shared.execution\n",
    )
    files = list(fw._iter_py_files(tos_dir))
    assert path in files


def test_run_checks_catches_violation_under_pycache_dir(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(
        tmp_path / "tos" / "src" / "tos" / "__pycache__" / "egress.py",
        "import shared.execution\n",
    )
    violations = fw.run_checks(tmp_path)
    assert any(v.path.endswith("egress.py") for v in violations)


def test_iter_py_files_node_modules_dir_still_scanned(tmp_path):
    tos_dir = tmp_path / "tos"
    path = _write(
        tos_dir / "src" / "tos" / "node_modules" / "egress.py",
        "import shared.execution\n",
    )
    files = list(fw._iter_py_files(tos_dir))
    assert path in files


def test_iter_py_files_nested_venv_not_top_level_still_scanned(tmp_path):
    tos_dir = tmp_path / "tos"
    path = _write(
        tos_dir / "src" / "tos" / ".venv" / "x.py", "import shared.execution\n"
    )
    files = list(fw._iter_py_files(tos_dir))
    assert path in files


def test_iter_py_files_venv_without_dot_still_scanned(tmp_path):
    tos_dir = tmp_path / "tos"
    path = _write(tos_dir / "venv" / "x.py", "import shared.execution\n")
    files = list(fw._iter_py_files(tos_dir))
    assert path in files


@pytest.mark.parametrize(
    "dotted,allowed",
    [
        ("json", True),
        ("os.path", True),
        ("urllib", True),
        ("urllib.parse", True),
        ("urllib.request", False),
        ("http", False),
        ("http.client", False),
        ("socket", False),
        ("numpy", True),
        ("numpy.linalg", True),
        ("requests", False),
        ("shared.config", False),
        ("shared.config.loader", False),
        ("shared.config.secrets", False),
        ("shared.execution", False),
        ("shared", False),
        ("tos", True),
        ("tos.models", True),
    ],
)
def test_classify_module(dotted, allowed):
    assert fw.classify_module(dotted)[0] is allowed


def test_scope_for_tos_path_runtime_vs_kernel(tmp_path):
    assert fw.scope_for_tos_path("tos/runtime/src/tos_runtime/x.py") == "runtime"
    assert fw.scope_for_tos_path("tos/runtime/tests/test_x.py") == "runtime"
    assert fw.scope_for_tos_path("tos/src/tos/x.py") == "kernel"
    assert fw.scope_for_tos_path("m.py") == "kernel"


def test_scope_for_tos_path_other_tos_sibling_dir_is_kernel_scope_fail_closed(tmp_path):
    assert fw.scope_for_tos_path("tos/sandbox/x.py") == "kernel"
    assert fw.scope_for_tos_path("tos/runtimeish/x.py") == "kernel"


def test_runtime_scope_file_importing_socket_passes(tmp_path):
    path = _make_tos_runtime_src(tmp_path, "adapter.py", "import socket\n")
    violations = fw.check_tos_file(path, _runtime_rel("adapter.py"))
    assert violations == [], f"unexpected violations: {violations}"


@pytest.mark.parametrize(
    "body",
    ["import ssl\n", "import http.client\n", "from urllib.request import urlopen\n"],
)
def test_runtime_scope_stdlib_carveout_passes(tmp_path, body):
    path = _make_tos_runtime_src(tmp_path, "adapter.py", body)
    violations = fw.check_tos_file(path, _runtime_rel("adapter.py"))
    assert violations == [], f"unexpected violations: {violations}"


def test_kernel_scope_file_importing_socket_still_fails(tmp_path):
    path = _make_tos_src(tmp_path, "m.py", "import socket\n")
    violations = fw.check_tos_file(path, "tos/src/tos/m.py")
    assert "TOS-FW-B" in _rules(violations)


def test_kernel_file_importing_tos_runtime_fails_rule_g(tmp_path):
    path = _make_tos_src(tmp_path, "m.py", "import tos_runtime\n")
    violations = fw.check_tos_file(path, "tos/src/tos/m.py")
    assert "TOS-FW-G" in _rules(violations)


def test_kernel_file_importing_tos_runtime_from_form_fails_rule_g(tmp_path):
    path = _make_tos_src(tmp_path, "m.py", "from tos_runtime import compose\n")
    violations = fw.check_tos_file(path, "tos/src/tos/m.py")
    assert "TOS-FW-G" in _rules(violations)


def test_runtime_scope_file_importing_tos_kernel_passes(tmp_path):
    path = _make_tos_runtime_src(
        tmp_path, "compose.py", "from tos.rcl import CommitLog\n"
    )
    violations = fw.check_tos_file(path, _runtime_rel("compose.py"))
    assert violations == [], f"unexpected violations: {violations}"


def test_runtime_scope_self_import_passes(tmp_path):
    path = _make_tos_runtime_src(tmp_path, "m.py", "import tos_runtime\n")
    violations = fw.check_tos_file(path, _runtime_rel("m.py"))
    assert violations == [], f"unexpected violations: {violations}"


def test_runtime_scope_file_importing_shared_models_fails_rule_h(tmp_path):
    path = _make_tos_runtime_src(tmp_path, "bad.py", "from shared import models\n")
    violations = fw.check_tos_file(path, _runtime_rel("bad.py"))
    assert "TOS-FW-H" in _rules(violations)


def test_runtime_scope_file_importing_shared_models_submodule_fails_rule_h(tmp_path):
    path = _make_tos_runtime_src(
        tmp_path, "bad2.py", "from shared.indicators import rsi\n"
    )
    violations = fw.check_tos_file(path, _runtime_rel("bad2.py"))
    assert "TOS-FW-H" in _rules(violations)


def test_runtime_scope_file_importing_shared_determinism_fails_rule_h(tmp_path):
    path = _make_tos_runtime_src(
        tmp_path, "bad3.py", "from shared.determinism import LookaheadGuard\n"
    )
    violations = fw.check_tos_file(path, _runtime_rel("bad3.py"))
    assert "TOS-FW-H" in _rules(violations)


def test_kernel_scope_file_importing_shared_models_still_passes(tmp_path):
    path = _make_tos_src(tmp_path, "ok.py", "from shared import models\n")
    violations = fw.check_tos_file(path, "tos/src/tos/ok.py")
    assert violations == [], f"unexpected violations: {violations}"


def test_file_outside_tos_importing_tos_runtime_fails_rule_e_extension(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "services" / "foo.py", "import tos_runtime\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" in _rules(violations)
    assert any(v.path.endswith("foo.py") for v in violations)


def test_file_outside_tos_importing_tos_runtime_from_form_fails(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "cli" / "bar.py", "from tos_runtime.compose import wire\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" in _rules(violations)


def test_file_outside_tos_importing_tos_runtime_similar_name_not_flagged(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(
        tmp_path / "pkg" / "baz.py", "import tos_runtime_extra\nimport tos_runtimeish\n"
    )
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" not in _rules(violations)


def test_runtime_scope_file_importing_subprocess_fails(tmp_path):
    path = _make_tos_runtime_src(tmp_path, "bad.py", "import subprocess\n")
    violations = fw.check_tos_file(path, _runtime_rel("bad.py"))
    assert "TOS-FW-B" in _rules(violations)


@pytest.mark.parametrize(
    "body",
    [
        "import os\n\n\ndef f():\n    return os.getenv('X')\n",
        "import os\n\n\ndef f():\n    return os.environ['X']\n",
    ],
)
def test_runtime_scope_file_using_os_environ_fails(tmp_path, body):
    path = _make_tos_runtime_src(tmp_path, "bad.py", body)
    violations = fw.check_tos_file(path, _runtime_rel("bad.py"))
    assert "TOS-FW-C" in _rules(violations)


def test_file_at_tos_other_sibling_dir_is_treated_as_kernel_scope(tmp_path):
    path = _write(tmp_path / "tos" / "sandbox" / "x.py", "import socket\n")
    violations = fw.check_tos_file(path, "tos/sandbox/x.py")
    assert "TOS-FW-B" in _rules(violations)


def test_run_checks_scope_split_end_to_end(tmp_path):
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _make_tos_runtime_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _make_tos_runtime_src(tmp_path, "adapter.py", "import socket\n")
    _make_tos_src(tmp_path, "bad_kernel.py", "import socket\n")
    _make_tos_src(tmp_path, "leak.py", "import tos_runtime\n")
    violations = fw.run_checks(tmp_path)
    assert not any(
        v.path.endswith("tos/runtime/src/tos_runtime/adapter.py") for v in violations
    )
    assert any(
        v.path.endswith("tos/src/tos/bad_kernel.py") and v.rule == "TOS-FW-B"
        for v in violations
    )
    assert any(
        v.path.endswith("tos/src/tos/leak.py") and v.rule == "TOS-FW-G"
        for v in violations
    )


def test_control_group_real_repo_tree_passes():
    violations = fw.run_checks(_REPO_ROOT)
    assert violations == [], f"unexpected violations on real tree: {violations}"
