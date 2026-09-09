"""Grep-pin canary: nothing in ``tos_runtime`` calls ``EngineCore.handle``/``run`` except
:mod:`tos_runtime.engine.driver` and :mod:`tos_runtime.engine.replay` (TOS Phase 3 Wave 1 Lane
A-R; plan §1.1 "테스트가 코어를 직접 호출하는 경로 제거 — grep 0").

A pattern match, not an AST walk — deliberately simple and impossible to defeat by accident
(a genuinely new direct call site would have to literally spell ``core.handle(``/``core.run(``
to be missed, at which point it is also missing the crash-window idempotency and yield-order
stamping this whole package exists to provide).

**Independent review finding #15 (2026-09-09), narrowed here.** The allowance for
``test_driver.py`` used to exempt the WHOLE FILE — so a genuinely new, un-reviewed direct
``core.handle(``/``core.run(`` call site added to that file later would silently evade this pin.
It is narrowed to the exact sanctioned LINE(s), each tagged with ``_SANCTIONED_LINE_MARKER``
below (deliberately calling ``core.handle`` directly to simulate a process crash strictly between
that call and the driver's own durable bookkeeping — there is no public/private driver API that
stops partway through an atomic drain step). Any OTHER direct call added to that file, sanctioned
comment or not, still trips this pin unless it carries the exact marker.
"""

from __future__ import annotations

import re
from pathlib import Path

_RUNTIME_ROOT = Path(__file__).resolve().parents[2]  # tos/runtime
_SRC = _RUNTIME_ROOT / "src"
_TESTS = _RUNTIME_ROOT / "tests"

#: The only MODULES allowed to call ``core.handle(``/``core.run(`` directly, file-wide — these
#: two ARE the sanctioned call sites, by design (module docstring). Nothing else gets a
#: whole-file exemption; see ``_SANCTIONED_LINE_MARKER`` for the narrower, per-line allowance.
_ALLOWED_FILES = {
    _SRC / "tos_runtime" / "engine" / "driver.py",
    _SRC / "tos_runtime" / "engine" / "replay.py",
}

#: A direct call outside the two files above is refused UNLESS its own line carries this exact
#: marker comment (independent review finding #15) — e.g. ``test_driver.py``'s crash-window
#: simulations, which deliberately replicate ``EngineDriver._process_next``'s body up to (but not
#: including) its own durable bookkeeping, to model a process death in exactly that gap.
_SANCTIONED_LINE_MARKER = "# direct-core-call: sanctioned (determinism control)"

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
        "tos_runtime/engine/{driver,replay}.py (and not tagged with "
        f"{_SANCTIONED_LINE_MARKER!r}):\n" + "\n".join(offenders)
    )
