"""§3.4 cycle-0 + pure/adapter canaries for ``tos.marketfeed`` — closure canaries are table-driven."""

from __future__ import annotations

import ast
import multiprocessing as mp
from pathlib import Path

from .. import _closure_table
from .._closure_policy import SRC_ROOT
from . import _cycle_children

_MARKETFEED_SRC = SRC_ROOT / "marketfeed"

_PURE_MODULE_FILES = (
    "__init__.py",
    "_base.py",
    "vocabulary.py",
    "records.py",
    "value.py",
)
_ADAPTER_MODULE_FILE = "resolver.py"


def _run_cycle_child(target) -> list[str]:
    """Spawn a cycle-0 child (defined in a marketfeed-free module) and return its report."""
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=target, args=(queue,))
    proc.start()
    result = queue.get(timeout=120)
    proc.join(timeout=120)
    assert proc.exitcode == 0, f"cycle child exited abnormally: {proc.exitcode}"
    return list(result)


def test_importing_dsl_alone_never_pulls_in_marketfeed() -> None:
    """(§3.4 ★ cycle-0) ``dsl -> marketfeed -> dsl`` has no first edge, measured in a fresh child."""
    assert _run_cycle_child(_cycle_children.dsl_only_child) == []


def test_importing_engine_alone_never_pulls_in_marketfeed() -> None:
    """(§2.2 F1 ★ cycle-0) ``engine -> marketfeed -> engine`` has no first edge either."""
    assert _run_cycle_child(_cycle_children.engine_only_child) == []


def test_importing_capsule_alone_never_pulls_in_marketfeed() -> None:
    """(§0.2-1) The ratified Capsule package is untouched — it does not learn about marketfeed."""
    assert _run_cycle_child(_cycle_children.capsule_only_child) == []


def test_the_cycle_children_module_imports_nothing_at_module_scope() -> None:
    """(anti-phantom) The measurement is real only if its child module is marketfeed-free."""
    source = Path(_cycle_children.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    module_level = [
        node
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
    ]
    assert (
        module_level == []
    ), "the cycle-child module must import nothing at module scope"


def test_no_dsl_or_engine_source_statically_imports_marketfeed() -> None:
    """(§3.4, static mirror) The runtime measurement above is confirmed at the source level."""
    src_root = _MARKETFEED_SRC.parent
    offenders: list[str] = []
    for package in ("dsl", "engine"):
        for path in sorted((src_root / package).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                entries: list[tuple[str, int]] = []
                if isinstance(node, ast.Import):
                    entries = [(alias.name, node.lineno) for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    entries = [(node.module, node.lineno)]
                for name, lineno in entries:
                    if name == "tos.marketfeed" or name.startswith("tos.marketfeed."):
                        offenders.append(
                            f"{package}/{path.name}:{lineno} import {name}"
                        )
    assert (
        offenders == []
    ), f"a dsl/engine source imports marketfeed — cycle risk: {offenders}"


def test_the_engine_allowlist_still_omits_marketfeed() -> None:
    """(§15.2 ③) The committed engine policy's own allowlist is read and confirmed unchanged."""
    declared = _closure_table.POLICIES["engine"].allowed_tos
    assert (
        declared
    ), "could not read the engine policy's allowlist — the anti-phantom read failed"
    assert "tos.marketfeed" not in declared
    assert len(declared) == 15


def _statically_imported_tos_modules(path: Path) -> set[str]:
    """Every ``tos.*`` module a source statically imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return {name for name in imported if name == "tos" or name.startswith("tos.")}


def test_the_pure_layer_statically_imports_no_engine() -> None:
    """(§3.4 ★) Only the resolver adapter may name ``tos.engine``."""
    offenders: list[str] = []
    for filename in _PURE_MODULE_FILES:
        if filename == "__init__.py":
            continue
        imported = _statically_imported_tos_modules(_MARKETFEED_SRC / filename)
        for name in sorted(imported):
            if name == "tos.engine" or name.startswith("tos.engine."):
                offenders.append(f"{filename} imports {name}")
    assert offenders == [], f"the pure value layer reached tos.engine: {offenders}"


def test_the_adapter_layer_really_holds_the_engine_edge() -> None:
    """(anti-phantom §0.5) The split is real in both directions — the adapter does import engine."""
    imported = _statically_imported_tos_modules(_MARKETFEED_SRC / _ADAPTER_MODULE_FILE)
    assert any(
        name == "tos.engine" or name.startswith("tos.engine.") for name in imported
    ), "resolver.py declares no tos.engine import — the declared adapter edge would be a phantom"


def test_the_pure_module_file_list_matches_disk() -> None:
    """Anti-phantom: the pure/adapter partition names every shipped file, exactly once."""
    on_disk = {path.name for path in _MARKETFEED_SRC.glob("*.py")}
    assert on_disk == set(_PURE_MODULE_FILES) | {_ADAPTER_MODULE_FILE}
    assert _ADAPTER_MODULE_FILE not in _PURE_MODULE_FILES
