"""Shared machinery for asserting a shipped ``tos/runtime/config/*.example.yaml`` document is
STRUCTURALLY complete — as opposed to merely "refuses to load", which a document missing an
entire required key ALSO does, identically, to a document that carries the key as an explicit
``null`` (every ``tos_runtime.*``/``tos_runtime.compose._*`` loader treats "key absent" and "key
present but null" as the SAME named-TBD refusal — ``raw.get(key) is None`` does not distinguish
them). A naive ``pytest.raises(SomeConfigError)`` around a shipped example therefore CANNOT catch
a whole required key being missing from the document: the loader refuses either way, for what
looks like the right reason, and the test stays green.

Closes the class ``docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md`` names A-0b:
``safety_activation.example.yaml`` satisfied ONE of its two real readers
(``tos_runtime.safety.profile``'s ``activation:``/``not_expired:`` schema) while silently missing
the key a SECOND, independent reader added later (``tos_runtime.venue.activation
.load_activation_members``'s ``members:`` key) — the exact same shape of bug W2 hit once already
for ``marketfeed.example.yaml``'s missing ``intake_kind`` (commit ``47cf1671``), which is why this
module makes the check itself, not just one more instance fix.

Two independent assertions close this, together:

* :func:`assert_required_paths_present` — the document declared in ``config/EXAMPLE_NAME
  .example.yaml`` must carry every key path any of its real readers require, as an EXPLICIT key
  (value may be ``null`` — that is the correct named-TBD template state) at every level.
* :func:`assert_touchpoints_match` — a live grep of ``tos_runtime`` for the config's own deployed
  filename literal (``f'"{stem}.yaml"'``) must match a RECORDED set of touch-point files exactly.
  A new file referencing that literal (a new wiring call site, or a genuinely new independent
  schema reader) flips this red until a human looks — this is what makes the check follow a NEW
  loader being added later, rather than rotting the moment ``EXAMPLE_REQUIRED_PATHS`` goes stale
  (the "레지스트리 + 고정 안 된 위성" class this repo has already hit once at the kernel layer).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
RUNTIME_SRC = Path(__file__).resolve().parents[2] / "src"

#: A key path into a nested mapping, e.g. ``("activation", "not_expired")``.
KeyPath = tuple[str, ...]

#: A statically-imported loader callable plus its own extra keyword arguments (never sourced from
#: the example file itself — see each ``EXAMPLE_LOADERS`` entry's own comment in
#: ``example_integrity_registry.py``). Deliberately a plain callable, not a
#: ``(module_name, func_name)`` string pair resolved via ``importlib.import_module`` at test time
#: — the tos import firewall (``tools/tos_firewall_check.py`` rule TOS-FW-D) forbids dynamic
#: import/``getattr``-chain dispatch precisely to close that static-analysis escape hatch, and
#: this test tree is scanned by that same firewall (module docstring's own §2.4 note: "a test
#: that imports a forbidden module breaks the hermetic claim").
LoaderSpec = tuple[Callable[..., Any], dict[str, Any]]


def load_example_document(stem: str) -> Any:
    """Parse ``config/{stem}.example.yaml`` and return the raw YAML value (a ``dict`` for every
    config this module knows about)."""
    path = CONFIG_DIR / f"{stem}.example.yaml"
    assert path.is_file(), f"fixture assumption: {path} ships in this repo"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def has_key_path(document: Any, path: KeyPath) -> bool:
    """``True`` iff every key in ``path`` is an EXPLICIT key of ``document`` at its own nesting
    level — the value at the final key may be ``null`` (the named-TBD template convention this
    whole codebase uses) and this still returns ``True``. Returns ``False`` the moment a key is
    absent from a mapping at any level, which is the one thing ``dict.get`` cannot tell apart
    from "present and null" — exactly the gap this module exists to check independently of the
    loaders themselves."""
    node = document
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return False
        node = node[key]
    return True


def assert_required_paths_present(stem: str, required_paths: list[KeyPath]) -> None:
    """Assert every path in ``required_paths`` is an explicit key of ``config/{stem}
    .example.yaml`` at every nesting level (see :func:`has_key_path`). Raising here means a copy
    of this template would refuse to boot for a STRUCTURAL reason — a key genuinely missing from
    the document — never because a leaf still needs an operator-filled value."""
    document = load_example_document(stem)
    assert isinstance(
        document, dict
    ), f"{stem}.example.yaml must be a top-level mapping"
    missing = [
        ".".join(path) for path in required_paths if not has_key_path(document, path)
    ]
    assert not missing, (
        f"{stem}.example.yaml is missing required key path(s) {missing} that its own reader(s) "
        "demand. A deployment config copied from this template would refuse to boot for a "
        "STRUCTURAL reason (the key is not there at all), not because a named-TBD placeholder "
        "needs filling. Add the key in named-TBD form (null, matching every other leaf in this "
        "file) — do not invent a concrete value (docs/plans/2026-09-18-tos-config-adoption-and-"
        "carryover-plan.md §0.1.4)."
    )


def touchpoint_files(stem: str) -> frozenset[str]:
    """Live-grep every ``*.py`` file under ``tos/runtime/src`` for the literal deployed filename
    (``"{stem}.yaml"``) and return the set of files (paths relative to ``tos/runtime/src``) where
    it appears — comments and docstrings included on purpose: a NEW mention is exactly the signal
    this check exists to surface, whether it turns out to be a real new reader or not.
    """
    literal = f'"{stem}.yaml"'
    found: set[str] = set()
    for path in RUNTIME_SRC.rglob("*.py"):
        if literal in path.read_text(encoding="utf-8"):
            found.add(str(path.relative_to(RUNTIME_SRC)))
    return frozenset(found)


def call_loader(spec: LoaderSpec, path: Path) -> Any:
    """Call ``spec``'s statically-imported loader callable with ``path`` as the sole positional
    argument plus ``spec``'s own keyword arguments."""
    loader, kwargs = spec
    return loader(path, **kwargs)


def assert_shipped_example_still_refuses(stem: str, spec: LoaderSpec) -> None:
    """Call ``spec``'s loader against ``config/{stem}.example.yaml`` and assert it raises.

    Every shipped example in ``EXAMPLE_LOADERS`` is an all-``null`` template (module docstrings
    across this codebase say so explicitly) — it must still refuse to load as-is. A loader that
    unexpectedly SUCCEEDS on the shipped example means a real, filled-in value leaked into a file
    that is supposed to ship as a template — a different bug from the structural one
    :func:`assert_required_paths_present` targets, but one this same sweep should still catch.
    """
    example_path = CONFIG_DIR / f"{stem}.example.yaml"
    loader, _ = spec
    try:
        result = call_loader(spec, example_path)
    except Exception:  # noqa: BLE001 - any refusal is the expected outcome here
        return
    raise AssertionError(
        f"{stem}.example.yaml loaded successfully via {loader.__module__}.{loader.__qualname__} "
        f"instead of refusing (got {result!r}) — this file is supposed to ship as an all-null "
        "template; a concrete value appears to have leaked into it."
    )


def assert_touchpoints_match(stem: str, expected_files: frozenset[str]) -> None:
    """Assert the LIVE set of files referencing ``"{stem}.yaml"`` (see :func:`touchpoint_files`)
    equals ``expected_files`` exactly.

    This is the drift guard ``EXAMPLE_REQUIRED_PATHS`` alone cannot provide: a hand-maintained
    required-paths registry only stays correct as long as nobody adds a NEW file that reads this
    same config for a NEW purpose. When one does, this test goes red — pointing at exactly which
    file is new/gone — until a human decides whether it is a real independent schema reader (in
    which case ``EXAMPLE_REQUIRED_PATHS`` for this ``stem`` must grow to cover it too, mirroring
    how ``safety_activation``'s entry covers BOTH ``tos_runtime.safety.profile`` and
    ``tos_runtime.venue.activation``) or just another wiring call site that forwards to an
    already-covered canonical loader (in which case the recorded set is simply updated).
    """
    found = touchpoint_files(stem)
    assert found == expected_files, (
        f"{stem}.yaml touch points drifted from the recorded set in EXAMPLE_TOUCHPOINTS.\n"
        f"  now:      {sorted(found)}\n"
        f"  recorded: {sorted(expected_files)}\n"
        "A file was added to (or removed from) the set of tos_runtime source files that "
        "reference this config's deployed filename literal. Update EXAMPLE_TOUCHPOINTS in "
        "example_integrity_registry.py to match, and — if the new file is a genuinely "
        "independent schema reader rather than another wiring call site forwarding to an "
        "already-covered canonical loader — extend EXAMPLE_REQUIRED_PATHS for this config too. "
        "This is exactly the class docs/plans/2026-09-18-tos-config-adoption-and-carryover-"
        "plan.md §0.1.4 (A-0b) closed: one file, multiple schemas, only one covered."
    )
