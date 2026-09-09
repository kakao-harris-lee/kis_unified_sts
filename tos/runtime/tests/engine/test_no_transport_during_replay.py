"""AST-pin canary: neither :mod:`tos_runtime.engine.replay` nor
:mod:`tos_runtime.engine.replay_transmit` import a transport-capable package (CR5, 2026-09-09) —
mirrors ``test_no_direct_core_calls.py``'s own stated idiom for a different invariant.

**Why this exists.** :class:`~tos_runtime.engine.replay_transmit.RecordedTransmit` stands in for
the real send boundary (``tos.engine.sequencer.Transmit``) during boot-time replay. Its own module
docstring states the firewall it must hold to: stdlib ``json`` + ``tos.engine`` +
``tos_runtime.evidence.store`` only — never a real transport. A per-call behavioral assertion
("the live run's transport was never invoked during replay", see
``test_replay.py::test_replay_never_calls_the_live_runs_transport``) only proves this for the
scenarios a test happens to exercise; this pin makes it true STRUCTURALLY, for every scenario,
by forbidding the two replay modules from importing a transport-capable package AT ALL — a
transport that is never imported cannot be constructed or called, by construction.

``tos.brokeradapter`` (the ``Transmit`` Protocol's own real implementations, including
``synthetic.py``) and ``tos.egressgw`` (the broker gateway / send-boundary sealing package) are
the two transport-capable packages in this kernel (measured: ``grep -rl`` for
``brokeradapter\\|send_once\\|class.*Transport`` under ``tos/src/tos`` returns exactly these two
packages plus ``tos.engine`` itself, which only *defines* the ``Transmit`` Protocol and is
already an allowed import).

An AST walk over each file's own ``import``/``from ... import`` statements — not a text grep —
so a multi-line or aliased import cannot slip past it.
"""

from __future__ import annotations

import ast
from pathlib import Path

_RUNTIME_ROOT = Path(__file__).resolve().parents[2]  # tos/runtime
_SRC = _RUNTIME_ROOT / "src"

#: The two boot-time replay modules this pin covers.
_REPLAY_FILES = {
    _SRC / "tos_runtime" / "engine" / "replay.py",
    _SRC / "tos_runtime" / "engine" / "replay_transmit.py",
}

#: The transport-capable packages a replay module must never import (module docstring).
_FORBIDDEN_PREFIXES = ("tos.brokeradapter", "tos.egressgw")


def _imported_module_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _is_forbidden(module_name: str) -> bool:
    return any(
        module_name == prefix or module_name.startswith(prefix + ".")
        for prefix in _FORBIDDEN_PREFIXES
    )


def test_replay_modules_never_import_a_transport_capable_package() -> None:
    offenders: list[str] = []
    for path in sorted(_REPLAY_FILES):
        for module_name in _imported_module_names(path):
            if _is_forbidden(module_name):
                offenders.append(
                    f"{path.relative_to(_RUNTIME_ROOT)}: imports {module_name!r}"
                )
    assert offenders == [], (
        "boot-time replay module(s) import a transport-capable package — replay must never be "
        "ABLE to construct or call a real transport, structurally, regardless of what any given "
        "test scenario happens to exercise (CR5, 2026-09-09):\n" + "\n".join(offenders)
    )
