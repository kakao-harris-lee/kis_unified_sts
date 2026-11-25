"""Shared machinery for asserting a shipped ``tos/runtime/config/*.example.yaml`` document is"""

from __future__ import annotations

import io
import tokenize
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
RUNTIME_SRC = Path(__file__).resolve().parents[2] / "src"

_STATEMENT_START = frozenset(
    {tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING}
)

KeyPath = tuple[str, ...]

LoaderSpec = tuple[Callable[..., Any], dict[str, Any]]


def load_example_document(stem: str) -> Any:
    """Parse ``config/{stem}.example.yaml`` and return the raw YAML value (a ``dict`` for every"""
    path = CONFIG_DIR / f"{stem}.example.yaml"
    assert path.is_file(), f"fixture assumption: {path} ships in this repo"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def has_key_path(document: Any, path: KeyPath) -> bool:
    """``True`` iff every key in ``path`` is an EXPLICIT key of ``document`` at its own nesting"""
    node = document
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return False
        node = node[key]
    return True


def assert_required_paths_present(stem: str, required_paths: list[KeyPath]) -> None:
    """Assert every path in ``required_paths`` is an explicit key of ``config/{stem}"""
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


def code_text(path: str | Path) -> str:
    """``path``'s source with comments and docstrings dropped, as joined token text."""
    source = Path(path).read_text(encoding="utf-8")
    kept: list[str] = []
    previous = tokenize.ENCODING
    for token in tokenize.generate_tokens(io.StringIO(source, newline="").readline):
        if token.type == tokenize.COMMENT:
            continue
        if token.type == tokenize.STRING and previous in _STATEMENT_START:
            previous = tokenize.STRING
            continue
        if token.type != tokenize.NL:
            previous = token.type
        kept.append(token.string)
    return "\n".join(kept)


def touchpoint_files(stem: str) -> frozenset[str]:
    """Live-grep the CODE of every ``*.py`` file under ``tos/runtime/src`` for the literal"""
    literal = f'"{stem}.yaml"'
    found: set[str] = set()
    for path in RUNTIME_SRC.rglob("*.py"):
        if literal in code_text(path):
            found.add(str(path.relative_to(RUNTIME_SRC)))
    return frozenset(found)


def call_loader(spec: LoaderSpec, path: Path) -> Any:
    """Call ``spec``'s statically-imported loader callable with ``path`` as the sole positional"""
    loader, kwargs = spec
    return loader(path, **kwargs)


def assert_shipped_example_still_refuses(stem: str, spec: LoaderSpec) -> None:
    """Call ``spec``'s loader against ``config/{stem}.example.yaml`` and assert it raises."""
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


def _leaf_values(node: Any) -> list[Any]:
    """Flatten ``node`` into its leaf values — recursing through NON-EMPTY mappings and lists,"""
    if isinstance(node, dict):
        if not node:
            return [node]
        leaves: list[Any] = []
        for value in node.values():
            leaves.extend(_leaf_values(value))
        return leaves
    if isinstance(node, list):
        if not node:
            return [node]
        leaves = []
        for item in node:
            leaves.extend(_leaf_values(item))
        return leaves
    return [node]


def is_template_document(document: Any) -> bool:
    """``True`` iff every leaf of ``document`` (see :func:`_leaf_values`) is ``None`` or an empty"""
    return all(leaf is None or leaf == [] for leaf in _leaf_values(document))


def assert_shipped_example_is_a_template(stem: str) -> None:
    """Assert every leaf of ``config/{stem}.example.yaml`` is ``None``/``[]`` (see"""
    document = load_example_document(stem)
    assert is_template_document(document), (
        f"{stem}.example.yaml has at least one non-null, non-empty leaf — its loader "
        "validates it via a record whose fields are ALL optional (module docstring), so it "
        "never raises on a filled-in value here; a real, concrete value appears to have "
        "leaked into a file that is supposed to ship as an all-null/empty template."
    )


def assert_risk_refuses_on_both_readers() -> None:
    """Call ALL THREE real reader functions of ``risk.example.yaml`` and assert each still"""
    from tos_runtime.compose._currentness_wiring import _load_action_flow_envelope
    from tos_runtime.risk.aggregate import (
        AggregateRiskConfigError,
        load_adverse_scenario_set,
        load_required_scenario_kinds,
    )

    example_path = CONFIG_DIR / "risk.example.yaml"
    for loader in (
        load_adverse_scenario_set,
        load_required_scenario_kinds,
        _load_action_flow_envelope,
    ):
        try:
            result = loader(example_path)
        except AggregateRiskConfigError:
            continue
        raise AssertionError(
            f"{example_path.name} loaded successfully via {loader.__qualname__} instead of "
            f"refusing (got {result!r}) — a real value appears to have leaked in."
        )


def assert_touchpoints_match(stem: str, expected_files: frozenset[str]) -> None:
    """Assert the LIVE set of files referencing ``"{stem}.yaml"`` (see :func:`touchpoint_files`)"""
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
