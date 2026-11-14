"""Grep-pin canary: nothing in ``tos_runtime`` calls ``EngineCore.handle``/``run`` except"""

from __future__ import annotations

import re
from pathlib import Path

_RUNTIME_ROOT = Path(__file__).resolve().parents[2]
_SRC = _RUNTIME_ROOT / "src"
_TESTS = _RUNTIME_ROOT / "tests"

_ALLOWED_FILES = {
    _SRC / "tos_runtime" / "engine" / "driver.py",
    _SRC / "tos_runtime" / "engine" / "replay.py",
    _SRC / "tos_runtime" / "engine" / "replay_stage.py",
}

_SANCTIONED_LINE_MARKER = "# direct-core-call: sanctioned (determinism control)"

_DIRECT_CALL = re.compile(r"\bcore\.(handle|run)\(")


def _python_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
        and path.name != "test_no_direct_core_calls.py"
    ]


def test_no_direct_engine_core_calls_outside_driver_and_replay() -> None:
    offenders: list[str] = []
    for path in _python_files(_SRC) + _python_files(_TESTS):
        if path in _ALLOWED_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _DIRECT_CALL.search(line) and _SANCTIONED_LINE_MARKER not in line:
                offenders.append(
                    f"{path.relative_to(_RUNTIME_ROOT)}:{lineno}: {line.strip()}"
                )
    assert offenders == [], (
        "direct EngineCore.handle/run call(s) found outside "
        "tos_runtime/engine/{driver,replay,replay_stage}.py (and not tagged with "
        f"{_SANCTIONED_LINE_MARKER!r}):\n" + "\n".join(offenders)
    )
