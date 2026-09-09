"""Grep-pin canary: nothing in ``tos_runtime`` calls ``EngineCore.handle``/``run`` except
:mod:`tos_runtime.engine.driver` and :mod:`tos_runtime.engine.replay` (TOS Phase 3 Wave 1 Lane
A-R; plan §1.1 "테스트가 코어를 직접 호출하는 경로 제거 — grep 0").

A pattern match, not an AST walk — deliberately simple and impossible to defeat by accident
(a genuinely new direct call site would have to literally spell ``core.handle(``/``core.run(``
to be missed, at which point it is also missing the crash-window idempotency and yield-order
stamping this whole package exists to provide).
"""

from __future__ import annotations

import re
from pathlib import Path

_RUNTIME_ROOT = Path(__file__).resolve().parents[2]  # tos/runtime
_SRC = _RUNTIME_ROOT / "src"
_TESTS = _RUNTIME_ROOT / "tests"

#: The only modules allowed to call ``core.handle(``/``core.run(`` directly.
_ALLOWED = {
    _SRC / "tos_runtime" / "engine" / "driver.py",
    _SRC / "tos_runtime" / "engine" / "replay.py",
    # test_driver.py's crash-window-2 test deliberately replicates
    # EngineDriver._process_next's body UP TO (but not including) the
    # inbox.mark_consumed call, to simulate a process death in exactly that
    # gap — there is no public/private driver API that stops partway
    # through an atomic drain step, so the test calls core.handle directly,
    # on purpose, as the ONE place outside the driver itself that needs to.
    _TESTS / "engine" / "test_driver.py",
}

#: Matches a direct call on something bound to a variable/attribute named exactly ``core``
#: (``core.handle(...)``, ``self._core.handle(...)``, ``self.core.run(...)``) — a plain textual
#: pattern, not an import-aware AST resolution, per this module's own docstring.
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
        if path in _ALLOWED:
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _DIRECT_CALL.search(line):
                offenders.append(
                    f"{path.relative_to(_RUNTIME_ROOT)}:{lineno}: {line.strip()}"
                )
    assert offenders == [], (
        "direct EngineCore.handle/run call(s) found outside "
        "tos_runtime/engine/{driver,replay}.py:\n" + "\n".join(offenders)
    )
