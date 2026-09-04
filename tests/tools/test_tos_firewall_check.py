"""Unit tests for the tos import-firewall gate (``tools/tos_firewall_check.py``).

Each of the five firewall rules (a)-(e) from design §3.3-① gets a dedicated
violation fixture (a fake ``tos`` tree, or a fake repo, built in ``tmp_path``),
plus positive tests proving the allowlist genuinely allows what §3.2 permits.

The module under test lives at ``tools/tos_firewall_check.py`` (outside the
package tree); it is loaded directly from its file path so these tests do not
depend on ``tools`` being importable as a package.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "tos_firewall_check.py"


def _load_firewall():
    spec = importlib.util.spec_from_file_location("tos_firewall_check", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fw = _load_firewall()


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _make_tos_src(repo: Path, filename: str, body: str) -> Path:
    """Create <repo>/tos/src/tos/<filename> with <body> and return the path."""
    return _write(repo / "tos" / "src" / "tos" / filename, body)


def _rules(violations) -> set[str]:
    return {v.rule for v in violations}


# --------------------------------------------------------------------------
# (a) TOS-FW-A — import not on the §3.2 allowlist
# --------------------------------------------------------------------------


def test_rule_a_disallowed_third_party(tmp_path):
    path = _make_tos_src(tmp_path, "m.py", "import requests\n")
    violations = fw.check_tos_file(path, "tos/src/tos/m.py")
    assert "TOS-FW-A" in _rules(violations)


def test_rule_a_disallowed_operational_shared(tmp_path):
    path = _make_tos_src(tmp_path, "m.py", "from shared.execution import Foo\n")
    violations = fw.check_tos_file(path, "tos/src/tos/m.py")
    assert "TOS-FW-A" in _rules(violations)


def test_rule_a_bare_shared_denied(tmp_path):
    path = _make_tos_src(tmp_path, "m.py", "import shared\n")
    assert "TOS-FW-A" in _rules(fw.check_tos_file(path, "m.py"))


def test_rule_a_shared_config_denied_entirely(tmp_path):
    # ALL of shared.config is denied (7b09e58f, design #1 §3.2 amendment): its
    # __init__ unconditionally imports shared.config.secrets, so ANY submodule
    # import transitively reaches ambient credential access. No carve-out.
    for stmt in (
        "from shared.config import secrets\n",
        "from shared.config import ConfigLoader\n",
    ):
        path = _make_tos_src(tmp_path, "m.py", stmt)
        assert "TOS-FW-A" in _rules(fw.check_tos_file(path, "m.py"))


def test_rule_a_nested_import_is_caught(tmp_path):
    body = "def handler():\n    import requests\n    return requests\n"
    path = _make_tos_src(tmp_path, "m.py", body)
    violations = fw.check_tos_file(path, "m.py")
    assert "TOS-FW-A" in _rules(violations)
    assert violations[0].line == 2  # nested import reported at its real line


# --------------------------------------------------------------------------
# (b) TOS-FW-B — forbidden stdlib egress/process/FFI primitive
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# (c) TOS-FW-C — os.environ / os.getenv usage (C2 flag ban)
# --------------------------------------------------------------------------


def test_rule_c_os_getenv_call(tmp_path):
    body = "import os\n\n\ndef f():\n    return os.getenv('X')\n"
    path = _make_tos_src(tmp_path, "m.py", body)
    assert "TOS-FW-C" in _rules(fw.check_tos_file(path, "m.py"))


def test_rule_c_os_environ_subscript(tmp_path):
    body = "import os\n\n\ndef f():\n    return os.environ['X']\n"
    path = _make_tos_src(tmp_path, "m.py", body)
    assert "TOS-FW-C" in _rules(fw.check_tos_file(path, "m.py"))


def test_rule_c_from_os_import_getenv(tmp_path):
    body = "from os import getenv\n"
    path = _make_tos_src(tmp_path, "m.py", body)
    assert "TOS-FW-C" in _rules(fw.check_tos_file(path, "m.py"))


# --------------------------------------------------------------------------
# (d) TOS-FW-D — dynamic import / exec / eval
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# (e) TOS-FW-R — file OUTSIDE tos/ imports tos
# --------------------------------------------------------------------------


def test_rule_r_reverse_import_detected(tmp_path):
    # A clean tos tree ...
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    # ... plus an operational file that imports the kernel.
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
    # `tos_korean` / `import tosca` must NOT trip the reverse rule (top-level
    # module name must be exactly `tos`).
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "pkg" / "baz.py", "import tos_korean\nimport tosca\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" not in _rules(violations)


def test_rule_r_import_inside_tos_not_flagged(tmp_path):
    # A file *inside* tos/ importing tos is self-import, not a reverse import.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _make_tos_src(tmp_path, "sub.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" not in _rules(violations)


# --------------------------------------------------------------------------
# _walk_repo_py — reverse-scan pruning is by EXPLICIT-ROOT IDENTITY, not by
# name (any depth) and not by an `isidentifier()` predicate.
#
# The reverse scan used to prune `_REVERSE_SCAN_PRUNE = {"tos", ".git", ".venv",
# "node_modules", "__pycache__", ".omc", ".history"}` at ANY depth. Codex review
# found the same bypass class as the forward scan: `tos`, `node_modules`, and
# `__pycache__` are valid Python identifiers, so `services/tos/x.py` or
# `shared/node_modules/x.py` containing `import tos` would be silently skipped
# by rule e yet remain importable. A follow-up fix pruned any dir whose name
# is NOT a valid Python identifier — but Codex rejected that too: §3.2
# R-역방향 requires scanning EVERY Python file outside tos/, and a script
# under a non-identifier directory (e.g. a tracked `.py` under
# `docs/reviews/phase0-completion-contract/`) still executes by path; a
# hyphenated or dotted directory name says nothing about importability.
#
# The final design prunes ONLY an explicit, small set of repo-root-relative
# roots, matched by resolved-path IDENTITY (not name, not any-depth): VCS/
# generated/gitignored roots (`.git`, `.venv`, `.omc`, `.history`) plus the
# repo-root `tos/` (the forward scan's territory). Everything else — nested
# `.venv`-named dirs, `node_modules`, `__pycache__`, hyphenated dirs like
# `strategy-builder-ui` — is scanned, because Python runs code by path, not
# by whether the containing directory name looks like a package.
# --------------------------------------------------------------------------


def test_rule_r_nested_dir_named_tos_is_scanned(tmp_path):
    # A nested dir literally named `tos` (NOT the repo-root tos/) is scanned
    # — only the repo-root tos/ is pruned, and only by identity.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "services" / "tos" / "x.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" in _rules(violations)
    assert any(v.path.endswith("services/tos/x.py") for v in violations)


def test_rule_r_node_modules_dir_is_scanned(tmp_path):
    # `node_modules` is not one of the explicit pruned roots — must be scanned.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "shared" / "node_modules" / "x.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" in _rules(violations)


def test_rule_r_pycache_dir_is_scanned(tmp_path):
    # `__pycache__` is not one of the explicit pruned roots — must be scanned.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "shared" / "__pycache__" / "x.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" in _rules(violations)


def test_rule_r_docs_dir_is_scanned(tmp_path):
    # A tracked `.py` under a docs/ subtree still executes by path — §3.2
    # R-역방향 requires scanning it. This is exactly the case that sank the
    # `isidentifier()` predicate (Codex review): `docs` and its subdirs are
    # ordinary identifiers, not pruned roots, so they must be scanned.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(
        tmp_path / "docs" / "reviews" / "phase0-completion-contract" / "probe.py",
        "import tos\n",
    )
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" in _rules(violations)


def test_rule_r_hyphenated_dir_is_scanned(tmp_path):
    # `strategy-builder-ui` (hyphenated, a valid directory name but NOT a
    # valid Python identifier) is not one of the explicit pruned roots either
    # — it must be scanned. This replaces the old isidentifier-era negative
    # test that treated hyphenated dirs as un-scannable.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "strategy-builder-ui" / "tooling" / "gen.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" in _rules(violations)


def test_rule_r_open_trading_api_pruned(tmp_path):
    # `open-trading-api` IS an explicit pruned root — a gitignored, untracked
    # clone of KIS's own sample-code repo at the repo root, measured 2026-09-04
    # to hold 12,247 `.py` files and zero `import tos`/`from tos` matches; it
    # was the dominant wall-clock cost of the live-tree scan (~7.7s down to
    # ~1.3s once pruned, alongside strategy-builder-ui/node_modules below).
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "open-trading-api" / "vendored" / "x.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert not any(
        v.path.endswith("open-trading-api/vendored/x.py") for v in violations
    )


def test_rule_r_strategy_builder_ui_node_modules_pruned_but_rest_scanned(tmp_path):
    # `strategy-builder-ui/node_modules` IS an explicit pruned root (npm's
    # vendor tree, 2995 subdirectories, measured 2026-09-04) — but only that
    # subtree, not `strategy-builder-ui/` itself.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(
        tmp_path / "strategy-builder-ui" / "node_modules" / "x.py", "import tos\n"
    )
    _write(tmp_path / "strategy-builder-ui" / "x.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert not any(
        v.path.endswith("strategy-builder-ui/node_modules/x.py") for v in violations
    )
    assert any(
        v.path == "strategy-builder-ui/x.py" for v in violations
    )


def test_rule_r_nested_venv_named_dir_is_scanned(tmp_path):
    # Only the repo ROOT `.venv` is pruned, by identity. A directory that
    # happens to be named `.venv` somewhere else in the tree (not the
    # explicit pruned root) is not exempt — it is scanned like any other dir.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "shared" / ".venv" / "x.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" in _rules(violations)


def test_rule_r_explicit_generated_roots_still_pruned(tmp_path):
    # The repo-root `.venv/`, `.omc/`, and `.history/` ARE the explicit
    # pruned roots (VCS/generated/gitignored — verified 2026-09-04 via
    # `git ls-files --others --ignored`) — matched by identity at the root,
    # not by name at any depth.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / ".venv" / "lib" / "site-packages" / "x.py", "import tos\n")
    _write(tmp_path / ".omc" / "x.py", "import tos\n")
    _write(tmp_path / ".history" / "x.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" not in _rules(violations)


def test_rule_r_root_tos_dir_not_scanned_by_reverse_rule(tmp_path):
    # The repo-root tos/ tree stays the forward scan's territory — a self-
    # import inside it must NOT be reported by the reverse rule.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _make_tos_src(tmp_path, "y.py", "import tos\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" not in _rules(violations)


# --------------------------------------------------------------------------
# _walk_repo_py — force-tracked files under a pruned root close a bypass
#
# Codex review (re-review #7): `git add -f` can force-track a `.py` under a
# pruned root (`open-trading-api`, `strategy-builder-ui/node_modules`,
# `.venv`, `.omc`, `.history`) even though the filesystem-walk-only scan
# never descends into it — CI checks that file out and runs it, but rule e
# would never see it. The fix takes the UNION of the pruned filesystem walk
# and every git-tracked `.py` beneath a pruned root OTHER than `tos` (the
# forward scan's territory). These tests require a real `git` binary and
# `git init` their own isolated `tmp_path` — unrelated to (and independent
# of) this repo's own git state.
# --------------------------------------------------------------------------

_GIT_AVAILABLE = shutil.which("git") is not None


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "config", "user.name", "Test"],
        cwd=repo,
        check=True,
    )


@pytest.mark.skipif(not _GIT_AVAILABLE, reason="git not available")
def test_rule_r_force_tracked_py_under_pruned_root_is_reported(tmp_path):
    _git_init(tmp_path)
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / ".gitignore", "open-trading-api/\n")
    _write(tmp_path / "open-trading-api" / "x.py", "import tos\n")
    # Control: an UNTRACKED sibling under the same pruned root — the walk
    # prunes the directory, and it was never `git add`ed, so it must NOT be
    # reported.
    _write(tmp_path / "open-trading-api" / "y.py", "import tos\n")
    subprocess.run(
        ["git", "add", "-f", "open-trading-api/x.py"], cwd=tmp_path, check=True
    )

    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert any(v.path.endswith("open-trading-api/x.py") for v in violations)
    assert not any(v.path.endswith("open-trading-api/y.py") for v in violations)


@pytest.mark.skipif(not _GIT_AVAILABLE, reason="git not available")
def test_rule_r_force_tracked_py_under_root_tos_not_yielded(tmp_path):
    # The repo-root tos/ tree is excluded from the tracked-under-pruned-root
    # union entirely (the forward scan owns it) — a git-tracked file under
    # it must never be yielded by `_walk_repo_py`, force-tracked or not.
    _git_init(tmp_path)
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "tos" / "src" / "tos" / "z.py", "import tos\n")
    subprocess.run(
        ["git", "add", "-f", "tos/src/tos/z.py"], cwd=tmp_path, check=True
    )

    walked = list(fw._walk_repo_py(tmp_path))
    assert not any("tos/src/tos/z.py" in str(p) for p in walked)


# --------------------------------------------------------------------------
# Boundary classification is LEXICAL, never resolved — symlinks cannot
# relocate a file across the tos/ boundary in either direction.
#
# Codex re-review #8: `check_reverse_imports` classified a file as
# "inside tos/" (and skipped it) by comparing `path.resolve()` against
# `tos_dir.resolve()`. A symlink OUTSIDE tos/ whose TARGET happens to live
# inside tos/ was therefore misclassified as tos-internal and silently
# skipped — both for a force-tracked union path and for a plain walked
# path. The fix compares un-resolved, `os.path.abspath`-normalised paths
# instead (`_safe_rel` likewise switched to `os.path.relpath`, so a reported
# violation names the symlink's own lexical location, not its target).
# --------------------------------------------------------------------------

_SYMLINKS_SUPPORTED = hasattr(os, "symlink")


def _try_symlink(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(target, link)


@pytest.mark.skipif(not _GIT_AVAILABLE, reason="git not available")
@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_r_force_tracked_symlink_into_tos_is_reported_at_lexical_path(tmp_path):
    # A force-tracked SYMLINK under a pruned root, pointing INSIDE tos/, must
    # be reported at its own lexical location — not silently reclassified as
    # tos-internal by following the symlink to its target.
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
    # Same lexical-boundary requirement via the plain filesystem walk (no
    # git involved): a symlink under `shared/` pointing INSIDE tos/ must be
    # reported as `shared/x.py`, not reclassified as tos-internal.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "tos" / "src" / "tos" / "mod.py", "from tos import x\n")
    _try_symlink(
        tmp_path / "shared" / "x.py", tmp_path / "tos" / "src" / "tos" / "mod.py"
    )

    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert any(v.path.endswith("shared/x.py") for v in violations)


def test_rule_r_real_file_under_tos_root_not_reported(tmp_path):
    # Control: a REAL (non-symlink) file under the repo-root tos/ tree stays
    # exempt from rule e, exactly as before the lexical-boundary fix.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _make_tos_src(tmp_path, "mod.py", "from tos import x\n")
    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" not in _rules(violations)


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_r_symlink_with_no_tos_import_not_reported(tmp_path):
    # Control: a symlink whose target has no `tos` import is not reported —
    # the lexical-boundary fix must not turn every symlink into a violation.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "shared" / "real.py", "import json\n")
    _try_symlink(tmp_path / "shared" / "y.py", tmp_path / "shared" / "real.py")

    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    assert "TOS-FW-R" not in _rules(violations)


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_forward_scan_symlink_out_of_tos_is_still_scanned(tmp_path):
    # Mirror check on the FORWARD scan (rules a-d): a symlink INSIDE tos/
    # pointing OUTSIDE it must still have its content scanned — `read_text`
    # follows the link, so a disallowed import is caught regardless of
    # where the bytes physically live. Canary: keep this green.
    tos_dir = tmp_path / "tos"
    _write(tmp_path / "shared" / "execution.py", "import shared.execution\n")
    _try_symlink(
        tos_dir / "src" / "tos" / "leak.py", tmp_path / "shared" / "execution.py"
    )
    violations = fw.check_tos_file(
        tos_dir / "src" / "tos" / "leak.py", "tos/src/tos/leak.py"
    )
    assert "TOS-FW-A" in _rules(violations)


# --------------------------------------------------------------------------
# TOS-FW-S — boundary-crossing symlinks (fail-closed, no traversal)
#
# Codex re-review #9: a DIRECTORY symlink is neither walked
# (`os.walk(followlinks=False)` never descends into ANY directory symlink,
# regardless of where it points or whether its parent is a pruned root) nor
# discoverable via `_git_tracked_py_under_pruned_roots` (that query is
# `.py`-filename-filtered; a bare directory alias has no `.py` suffix to
# match, and git never lists the CONTENTS of a tracked symlink target
# anyway — it tracks the symlink object itself, one index entry). Neither
# side can safely traverse through the alias to see what is on the other
# side, so instead of trying, rule S forbids the alias itself: any symlink
# (file OR directory, walked OR git-tracked, dangling included) whose
# lexical location and resolved target lie on different sides of the tos/
# boundary is a violation, full stop.
# --------------------------------------------------------------------------


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
    # `open-trading-api/link` is a DIRECTORY symlink under a pruned,
    # gitignored root — invisible to the filesystem walk in EITHER source
    # (open-trading-api/ is pruned at the top, so the walk never even
    # reaches `link`). Only the git-tracked-symlink query (mode 120000) can
    # find it.
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
    # The inverse direction: a directory alias INSIDE tos/ pointing OUTSIDE
    # it — code that looks tos-governed but physically lives (and is
    # mutable) somewhere else entirely.
    tos_dir = tmp_path / "tos"
    _write(tmp_path / "shared" / "execution" / "x.py", "import json\n")
    _try_symlink(tos_dir / "src" / "tos" / "out", tmp_path / "shared" / "execution")

    violations = fw._forward_scan_boundary_symlinks(tmp_path, tos_dir)
    s_violations = [v for v in violations if v.rule == "TOS-FW-S"]
    assert any(v.path.endswith("tos/src/tos/out") for v in s_violations)


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_s_same_side_symlinks_not_reported(tmp_path):
    # Controls: a symlink whose target stays on the SAME side of the
    # boundary as its own lexical location is allowed on both sides.
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
    forward_violations = fw._forward_scan_boundary_symlinks(
        tmp_path, tmp_path / "tos"
    )
    assert "TOS-FW-S" not in _rules(forward_violations)


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_s_dangling_symlink_is_reported_fail_closed(tmp_path):
    # A dangling target could be on EITHER side once something eventually
    # gets created there — unknown means "assume crossing" (fail-closed),
    # never "assume safe".
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _try_symlink(tmp_path / "shared" / "dead", tmp_path / "shared" / "does_not_exist")

    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    s_violations = [v for v in violations if v.rule == "TOS-FW-S"]
    assert any(v.path.endswith("shared/dead") for v in s_violations)


# --------------------------------------------------------------------------
# rule S — crossing is SUBTREE INTERSECTION, not "which side"
#
# Claude-side review found a gap in the first cut of rule S: it asked only
# whether the target was on the OTHER side, not whether the target's
# subtree overlaps tos/'s subtree at all. A link OUTSIDE tos/ pointing at an
# ANCESTOR of tos/ (e.g. `shared/up -> <repo root>`) was judged same-side
# (repo root is "outside" too) even though the ancestor's subtree obviously
# *contains* tos/ — `from shared.up.tos.src.tos import KERNEL` reaches the
# kernel through it, and rule R's own AST scan never sees it (the walk never
# descends a directory symlink, so no `.py` under `shared/up/...` is ever
# read). Fixed definition: for a link OUTSIDE tos/, crossing iff the
# target's subtree and tos_dir's subtree overlap AT ALL (target == tos_dir,
# target is a descendant of tos_dir, OR target is an ANCESTOR of tos_dir);
# for a link INSIDE tos/, crossing iff the target's subtree is NOT entirely
# contained within tos_dir's subtree (anything outside, ancestors included).
# --------------------------------------------------------------------------


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_s_ancestor_of_tos_target_is_reported(tmp_path):
    # `shared/up` points at the REPO ROOT — an ancestor of tos/, not a
    # descendant. The old "which side" check missed this entirely.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _try_symlink(tmp_path / "shared" / "up", tmp_path)

    violations = fw.check_reverse_imports(tmp_path, tmp_path / "tos")
    s_violations = [v for v in violations if v.rule == "TOS-FW-S"]
    assert any(v.path.endswith("shared/up") for v in s_violations)


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_s_inside_tos_link_to_ancestor_within_tos_still_clean(tmp_path):
    # A link INSIDE tos/ pointing at an ANCESTOR directory that is itself
    # still WITHIN tos/'s subtree (e.g. `tos/src/tos/deep/link -> tos/src`)
    # must stay clean — the target's subtree is entirely contained in
    # tos_dir's subtree, even though it is "above" the link's own location.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "tos" / "src" / "tos" / "deep" / "x.py", "x = 1\n")
    _try_symlink(
        tmp_path / "tos" / "src" / "tos" / "deep" / "link", tmp_path / "tos" / "src"
    )

    violations = fw._forward_scan_boundary_symlinks(tmp_path, tmp_path / "tos")
    assert "TOS-FW-S" not in _rules(violations)


# --------------------------------------------------------------------------
# rule S — tos/ itself may NEVER be a symlink
#
# Claude-side review found a second gap: `_git_tracked_symlinks` skipped
# `rel == "tos"` outright, and the reverse rule-S loop's own guard ALSO
# skips anything lexically equal to tos_dir ("inside tos/, the forward
# mirror owns it") — but the forward mirror walks INSIDE tos_dir as its
# root, so it structurally can never inspect tos_dir itself either. Worse:
# `run_checks` gates the entire forward scan (rules a-d AND the forward
# rule-S mirror) on `tos_dir.is_dir()`, and a dangling symlink at `tos`
# makes that False — so every forward check silently vanishes and the tool
# reports a clean PASS despite the kernel being structurally unverifiable.
# Fixed: a dedicated check runs FIRST, before anything else, and a symlink
# (or missing directory) at `tos` is now always a visible, reported failure.
# --------------------------------------------------------------------------


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
    # The forward scan must be visibly failed-closed too, not silently
    # skipped — rules a-d cannot run without a real tos/ to certify.
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
    # Control: a real, ordinary tos/ directory triggers no tos-root-symlink
    # violation at all.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    violations = fw.run_checks(tmp_path)
    assert not any(
        v.path == "tos" and v.rule == "TOS-FW-S" for v in violations
    )
    assert not any("forward rules a-d cannot be evaluated" in v.message for v in violations)


def test_missing_tos_dir_is_a_visible_failure_not_a_pass(tmp_path):
    # `tos/` absent entirely (no dir, no symlink) must not silently produce
    # an empty (PASS) violations list — regression test for the bug
    # confirmed present before this fix: `run_checks` on a tos/-less repo
    # root returned `[]`.
    violations = fw.run_checks(tmp_path)
    assert violations != []
    assert any("forward rules a-d cannot be evaluated" in v.message for v in violations)


# --------------------------------------------------------------------------
# git probe: fail-CLOSED on "work tree but probe failed", fail-open only on
# genuinely "not a work tree at all"
#
# Claude-side review (batch 2): `git rev-parse --show-toplevel` can exit 128
# INSIDE a genuine work tree — e.g. "dubious ownership" (a CI checkout owned
# by a different uid). The prior code treated ANY non-zero exit as "not a
# work tree", silently dropping the git-tracked-`.py` union AND the
# git-tracked-symlink source with no error at all. `_git_toplevel_or_none`
# now distinguishes the two by the (English, LC_ALL=C-forced) stderr text:
# "not a git repository" means genuinely no work tree (skip silently, same
# as before); anything else means the probe itself failed while a work tree
# likely exists (raise `RuntimeError` — same fail-closed policy already used
# for `git ls-files` failures).
# --------------------------------------------------------------------------


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
        stderr = b"fatal: not a git repository (or any of the parent directories): .git\n"

    def _fake_run(args, **kwargs):
        return _FakeResult()

    monkeypatch.setattr(fw.subprocess, "run", _fake_run)
    assert fw._git_toplevel_or_none(tmp_path) is None


# --------------------------------------------------------------------------
# DRY: one rev-parse, at most two ls-files per `run_checks` invocation
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# MEDIUM: forward mirror must record symlinks BEFORE pruning `.venv`, same
# discipline as the reverse walk — a force-tracked (or merely present)
# `tos/.venv` symlink was reported by nothing, because the old code pruned
# `.venv` out of `dirnames` before ever checking `os.path.islink` on it.
# --------------------------------------------------------------------------


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED, reason="platform has no symlink support")
def test_rule_s_forward_venv_symlink_to_outside_is_reported(tmp_path):
    tos_dir = tmp_path / "tos"
    _write(tmp_path / "shared" / "x.py", "x = 1\n")
    _try_symlink(tos_dir / ".venv", tmp_path / "shared")

    violations = fw._forward_scan_boundary_symlinks(tmp_path, tos_dir)
    assert "TOS-FW-S" in _rules(violations)
    assert any(v.path.endswith("tos/.venv") for v in violations)


# --------------------------------------------------------------------------
# LOW: dangling-symlink message wording
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# positive path — the allowlist genuinely allows §3.2 imports
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# _iter_py_files — forward-scan pruning (top-level `tos/.venv/` ONLY)
#
# Regression coverage for: `cd tos && uv sync` creates a gitignored
# `tos/.venv/`, and the forward scan (unlike the reverse scan, which already
# prunes via `_REVERSE_SCAN_PRUNE`) walked into it and reported thousands of
# site-packages violations.
#
# An earlier version of this fix pruned `.venv`/`node_modules`/`__pycache__`/
# `.git` at ANY depth, mirroring `_REVERSE_SCAN_PRUNE`. Codex review rejected
# that: `node_modules` and `__pycache__` are valid Python identifiers, so a
# tracked `tos/src/tos/node_modules/egress.py` would be silently skipped by
# rules A-D yet remain importable via `from .node_modules import egress` — an
# exact bypass of the firewall. The fix now excludes ONLY the top-level
# `tos/.venv/` tree (`.venv` is not a valid identifier, so it can never be a
# real package/module path component and top-level-only pruning is safe).
# --------------------------------------------------------------------------


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
    # Positive control: a real src/ violation is still caught.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(
        tmp_path / "tos" / "src" / "tos" / "bad.py", "import shared.execution\n"
    )
    # Negative control: the identical violating import sitting under a
    # `.venv` site-packages tree must NOT be reported.
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
    # `__pycache__` is a valid Python identifier — a package literally named
    # that (`tos/src/tos/__pycache__/`) must still be scanned by rules A-D, or
    # `from .__pycache__ import egress` would bypass the firewall. Real
    # compiled caches hold only `.pyc` files, which `rglob("*.py")` never
    # matches in the first place, so no `__pycache__` exclusion is needed.
    tos_dir = tmp_path / "tos"
    path = _write(
        tos_dir / "src" / "tos" / "__pycache__" / "egress.py",
        "import shared.execution\n",
    )
    files = list(fw._iter_py_files(tos_dir))
    assert path in files


def test_run_checks_catches_violation_under_pycache_dir(tmp_path):
    # Same regression at the run_checks level (mirrors
    # test_run_checks_ignores_venv_but_still_catches_src_violations): a real
    # violation sitting under a directory literally named `__pycache__` must
    # still be reported.
    _make_tos_src(tmp_path, "__init__.py", '__version__ = "0.0.1"\n')
    _write(
        tmp_path / "tos" / "src" / "tos" / "__pycache__" / "egress.py",
        "import shared.execution\n",
    )
    violations = fw.run_checks(tmp_path)
    assert any(v.path.endswith("egress.py") for v in violations)


def test_iter_py_files_node_modules_dir_still_scanned(tmp_path):
    # `node_modules` is a valid Python identifier — a package literally named
    # that (`tos/src/tos/node_modules/`) must still be scanned by rules A-D,
    # or `from .node_modules import egress` would bypass the firewall.
    tos_dir = tmp_path / "tos"
    path = _write(
        tos_dir / "src" / "tos" / "node_modules" / "egress.py",
        "import shared.execution\n",
    )
    files = list(fw._iter_py_files(tos_dir))
    assert path in files


def test_iter_py_files_nested_venv_not_top_level_still_scanned(tmp_path):
    # Only the TOP-LEVEL `tos/.venv/` is excluded. A `.venv` directory nested
    # deeper (`tos/src/tos/.venv/`) is not the uv-generated env tree and must
    # still be scanned.
    tos_dir = tmp_path / "tos"
    path = _write(
        tos_dir / "src" / "tos" / ".venv" / "x.py", "import shared.execution\n"
    )
    files = list(fw._iter_py_files(tos_dir))
    assert path in files


def test_iter_py_files_venv_without_dot_still_scanned(tmp_path):
    # `venv` (no leading dot) is a valid Python identifier, distinct from the
    # excluded `.venv` — must still be scanned.
    tos_dir = tmp_path / "tos"
    path = _write(tos_dir / "venv" / "x.py", "import shared.execution\n")
    files = list(fw._iter_py_files(tos_dir))
    assert path in files


# --------------------------------------------------------------------------
# classify_module unit coverage of the tricky prefix cases
# --------------------------------------------------------------------------


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
        ("shared.config", False),  # entire package denied since 7b09e58f
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
