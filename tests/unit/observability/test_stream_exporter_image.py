"""The stream-exporter minimal image must actually import (#591, #753).

``Dockerfile.stream_exporter`` copies individual ``shared/`` subpackages rather
than the repo, so a ``shared.*`` import it does not cover passes every test and
kills only that one container at runtime. Parsing the exporter's own import
lines is not enough: the break can arrive through an ``import shared.x`` form,
a function-local import, or — the shape #753 introduced — a package
``__init__`` that reaches somewhere uncopied. So this rebuilds the image's file
tree from the ``COPY`` lines and imports the exporter against nothing else.

Mutating this test honestly is narrower than it looks. The mutation has to name
a module that **exists in the repo but is not COPYed** — ``shared.config.loader``
is one, ``shared.streaming.stage`` is not (it is copied). A module that exists
nowhere, such as ``shared.config.settings``, fails the same way in a full
checkout and so demonstrates nothing about COPY coverage; an import of a real
module but a missing *symbol* raises ``ImportError``, not
``ModuleNotFoundError``, and likewise proves nothing here. Both vacuous forms
were tried while writing this and are recorded so the next person does not
repeat them.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCKERFILE = _REPO_ROOT / "Dockerfile.stream_exporter"
_ENTRYPOINT = "services/monitoring/stream_exporter.py"

# Executed inside the sandbox. The sys.modules registration is load-bearing:
# @dataclass resolves its own module through sys.modules, so exec_module on an
# unregistered module raises AttributeError instead of the import error we care
# about. The sandbox assertion keeps a broken PYTHONPATH from passing vacuously.
# The AST sweep afterwards covers imports the module body never executes: a
# function-local `from shared.x import y` still kills the container the moment
# that function runs, and every function here runs during startup.
_IMPORT_PROBE = """
import ast, importlib, importlib.util, sys
sandbox, entrypoint = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("stream_exporter", entrypoint)
module = importlib.util.module_from_spec(spec)
sys.modules["stream_exporter"] = module
spec.loader.exec_module(module)

import shared
assert shared.__file__.startswith(sandbox), f"leaked out of sandbox: {shared.__file__}"

for node in ast.walk(ast.parse(open(entrypoint, encoding="utf-8").read())):
    if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("shared"):
        importlib.import_module(node.module)
    elif isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.startswith("shared"):
                importlib.import_module(alias.name)
"""


def _build_image_tree(destination: Path) -> None:
    """Replicate what the Dockerfile puts under /app, and nothing more."""
    dockerfile = _DOCKERFILE.read_text(encoding="utf-8").replace("\\\n", " ")
    sources = [
        line.split()[1] for line in dockerfile.splitlines() if line.startswith("COPY ")
    ]
    assert sources, "no COPY lines found — the Dockerfile's shape changed"

    for source in sources:
        target = destination / source
        target.parent.mkdir(parents=True, exist_ok=True)
        origin = _REPO_ROOT / source
        if origin.is_dir():
            shutil.copytree(
                origin, target, ignore=shutil.ignore_patterns("__pycache__")
            )
        else:
            shutil.copy2(origin, target)

    # The image also creates empty package markers via `touch` in a RUN layer.
    for marker in re.findall(r"touch\s+/app/(\S+)", dockerfile):
        (destination / marker).parent.mkdir(parents=True, exist_ok=True)
        (destination / marker).touch()


def test_minimal_image_can_import_the_exporter(tmp_path: Path) -> None:
    _build_image_tree(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            _IMPORT_PROBE,
            str(tmp_path),
            str(tmp_path / _ENTRYPOINT),
        ],
        cwd=tmp_path,
        env={"PYTHONPATH": str(tmp_path), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, (
        "the stream-exporter image cannot import its own entrypoint — add the "
        f"missing COPY to {_DOCKERFILE.name}:\n{result.stderr}"
    )
