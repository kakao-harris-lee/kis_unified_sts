"""AST-pin canary: none of the boot-time replay stand-in modules
(:mod:`tos_runtime.engine.replay`, :mod:`tos_runtime.engine.replay_transmit`,
:mod:`tos_runtime.engine.replay_stage`) import a transport-capable package or a
:mod:`tos_runtime` SERVICE package (CR5/CR5-3, 2026-09-09) — mirrors
``test_no_direct_core_calls.py``'s own stated idiom for a different invariant.

**Why this exists.** :class:`~tos_runtime.engine.replay_transmit.RecordedTransmit` stands in for
the real send boundary and :class:`~tos_runtime.engine.replay_stage.RecordedStage` stands in for
every real commitment-flow stage, during boot-time replay. Both classes' own module docstrings
state the same firewall: read durable evidence back out of the SAME store a prior boot already
wrote, and nothing else — never a real transport call, never a real service call (independent
approval, aggregate risk, currentness, RCL). A per-call behavioral assertion ("the live run's
transport/stage was never invoked during replay") only proves this for the scenarios a test
happens to exercise; this pin makes it true STRUCTURALLY, for every scenario, by forbidding the
three replay modules from importing a transport-capable or service package AT ALL — something
never imported cannot be constructed or called, by construction.

``tos.brokeradapter`` (the ``Transmit`` Protocol's own real implementations, including
``synthetic.py``) and ``tos.egressgw`` (the broker gateway / send-boundary sealing package) are
the two transport-capable packages in this kernel (measured: ``grep -rl`` for
``brokeradapter\\|send_once\\|class.*Transport`` under ``tos/src/tos`` returns exactly these two
packages plus ``tos.engine`` itself, which only *defines* the ``Transmit`` Protocol and is
already an allowed import). ``tos_runtime.authority`` (Safety Authority Epoch), ``tos_runtime.risk``
(Aggregate Risk Engine), and ``tos_runtime.currentness`` (Critical Input currentness) are the
:mod:`tos_runtime` SERVICE packages a real commitment-flow stage would call (CR5-3, 2026-09-09) —
listed in the ``_engine_wiring.py`` module docstring's own "owns three things" section as exactly
what the LIVE stage wiring depends on that the replay wiring must not.

An AST walk over each file's own ``import``/``from ... import`` statements — not a text grep —
so a multi-line or aliased import cannot slip past it.
"""

from __future__ import annotations

import ast
from pathlib import Path

_RUNTIME_ROOT = Path(__file__).resolve().parents[2]  # tos/runtime
_SRC = _RUNTIME_ROOT / "src"

#: The three boot-time replay stand-in modules this pin covers.
_REPLAY_FILES = {
    _SRC / "tos_runtime" / "engine" / "replay.py",
    _SRC / "tos_runtime" / "engine" / "replay_transmit.py",
    _SRC / "tos_runtime" / "engine" / "replay_stage.py",
}

#: The transport-capable and tos_runtime SERVICE packages a replay module must never import
#: (module docstring).
_FORBIDDEN_PREFIXES = (
    "tos.brokeradapter",
    "tos.egressgw",
    "tos_runtime.authority",
    "tos_runtime.risk",
    "tos_runtime.currentness",
)


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


def test_replay_modules_never_import_a_transport_or_service_package() -> None:
    offenders: list[str] = []
    for path in sorted(_REPLAY_FILES):
        for module_name in _imported_module_names(path):
            if _is_forbidden(module_name):
                offenders.append(
                    f"{path.relative_to(_RUNTIME_ROOT)}: imports {module_name!r}"
                )
    assert offenders == [], (
        "boot-time replay module(s) import a transport-capable or tos_runtime service package — "
        "replay must never be ABLE to construct or call a real transport/service, structurally, "
        "regardless of what any given test scenario happens to exercise (CR5/CR5-3, 2026-09-09):"
        "\n" + "\n".join(offenders)
    )
