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


def test_rule_a_secrets_carveout_denied(tmp_path):
    # shared.config is allowed, but the secrets submodule is a denied carve-out.
    path = _make_tos_src(tmp_path, "m.py", "from shared.config import secrets\n")
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
        "from shared.config import ConfigLoader\n"
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
        ("shared.config", True),
        ("shared.config.loader", True),
        ("shared.config.secrets", False),
        ("shared.execution", False),
        ("shared", False),
        ("tos", True),
        ("tos.models", True),
    ],
)
def test_classify_module(dotted, allowed):
    assert fw.classify_module(dotted)[0] is allowed
