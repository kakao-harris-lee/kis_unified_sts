"""The WAL birth-race mechanism exists TWICE; this is what keeps the two the same one."""

from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

KERNEL_MODULE = _REPO_ROOT / "tos" / "src" / "tos" / "staterestore" / "_wal.py"
RUNTIME_MODULE = (
    _REPO_ROOT
    / "tos"
    / "runtime"
    / "src"
    / "tos_runtime"
    / "operations"
    / "schema_ledger.py"
)

_DIAGNOSTIC_SQL = frozenset({"PRAGMA database_list"})

_REQUIRED_FUNCTIONS = (
    "_is_lock_contest",
    "_switch_journal_to_wal",
    "_wait_out_the_lock_and_retry",
    "enable_wal_journal",
)
_REQUIRED_CONSTANTS = ("_WAL_JOURNAL_MODE", "_SQLITE_PRIMARY_CODE_MASK")

_COMPARED_FUNCTIONS = (
    "_is_lock_contest",
    "_switch_journal_to_wal",
    "_wait_out_the_lock_and_retry",
    "enable_wal_journal",
)


class MechanismNotFound(AssertionError):
    """A named function or constant is missing from a module under comparison."""


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise MechanismNotFound(f"no module-level function named {name!r}")


def _constant(tree: ast.Module, name: str) -> object:
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
            and isinstance(node.value, ast.Constant)
        ):
            return node.value.value
    raise MechanismNotFound(f"no module-level constant literal named {name!r}")


def _executed_sql(func: ast.FunctionDef) -> tuple[str, ...]:
    """The string literals this function passes to ``.execute(...)``, in source order."""
    return tuple(
        arg.value
        for node in ast.walk(func)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
        for arg in node.args
        if isinstance(arg, ast.Constant)
        and isinstance(arg.value, str)
        and arg.value not in _DIAGNOSTIC_SQL
    )


def _calls_to(func: ast.FunctionDef, name: str) -> int:
    return sum(
        1
        for node in ast.walk(func)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    )


def _final_return_expression(func: ast.FunctionDef) -> str:
    """The expression of the function's LAST top-level ``return``."""
    returns = [
        node
        for node in func.body
        if isinstance(node, ast.Return) and node.value is not None
    ]
    if not returns:
        raise MechanismNotFound(f"{func.name} has no top-level return expression")
    return ast.unparse(returns[-1].value)


def _if_tests(func: ast.FunctionDef) -> list[str]:
    return [
        ast.unparse(node.test) for node in ast.walk(func) if isinstance(node, ast.If)
    ]


def _reject_repetition(func: ast.FunctionDef, callees: tuple[str, ...]) -> None:
    """Refuse any shape that could run the switch more than the pinned number of times."""
    for node in ast.walk(func):
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            raise MechanismNotFound(
                f"{func.name} contains a {type(node).__name__} — the retry must be "
                "straight-line, since 'exactly one retry' is counted from call sites"
            )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in callees
        ):
            raise MechanismNotFound(
                f"{func.name} calls {node.func.id} — recursion would repeat the switch "
                "without adding a call site the attempt count can see"
            )


_LOG_SUPPORT_CALLS = frozenset({"_database_file"})

_LOG_OBJECT = "_LOG"


def _is_log_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == _LOG_OBJECT
    )


def _is_log_support_call(node: ast.AST | None) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _LOG_SUPPORT_CALLS
    )


class _Normalise(ast.NodeTransformer):
    """Strip exactly what the two copies are ENTITLED to differ on, and nothing else."""

    def __init__(self, refusal: str) -> None:
        self.refusal = refusal

    def visit_Expr(self, node: ast.Expr) -> ast.AST | None:
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        if _is_log_call(node.value):
            return None
        return self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> ast.AST | None:
        if _is_log_support_call(node.value):
            return None
        return self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> ast.AST | list[ast.stmt]:
        self.generic_visit(node)
        transparent = (
            len(node.handlers) == 1
            and not node.orelse
            and not node.finalbody
            and len(node.handlers[0].body) == 1
            and isinstance(node.handlers[0].body[0], ast.Raise)
            and node.handlers[0].body[0].exc is None
        )
        return list(node.body) if transparent else node

    def visit_Raise(self, node: ast.Raise) -> ast.AST:
        if (
            isinstance(node.exc, ast.Call)
            and isinstance(node.exc.func, ast.Name)
            and node.exc.func.id == self.refusal
        ):
            return ast.Raise(
                exc=ast.Call(
                    func=ast.Name(id="<REFUSAL>", ctx=ast.Load()), args=[], keywords=[]
                ),
                cause=None,
            )
        return self.generic_visit(node)


def _refusal_class_of(enable: ast.FunctionDef) -> str:
    """The name of the class ``enable_wal_journal`` raises for a non-WAL answer."""
    raised = [
        node.exc.func.id
        for node in ast.walk(enable)
        if isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
    ]
    if len(raised) != 1:
        raise MechanismNotFound(
            f"enable_wal_journal raises {len(raised)} named exceptions, expected exactly "
            f"one refusal class; found {raised}"
        )
    return raised[0]


def _mechanism_of(path: Path) -> dict[str, object]:
    """The three mechanism functions, normalised, plus the constants they turn on."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {name: _function(tree, name) for name in _REQUIRED_FUNCTIONS}
    constants = {name: _constant(tree, name) for name in _REQUIRED_CONSTANTS}

    enable = functions["enable_wal_journal"]
    wait = functions["_wait_out_the_lock_and_retry"]
    _reject_repetition(enable, ("enable_wal_journal",))
    _reject_repetition(wait, ("_wait_out_the_lock_and_retry", "enable_wal_journal"))
    _reject_repetition(functions["_switch_journal_to_wal"], ("_switch_journal_to_wal",))

    normalise = _Normalise(_refusal_class_of(enable))
    bodies: dict[str, str] = {}
    for name in _COMPARED_FUNCTIONS:
        copied = normalise.visit(copy.deepcopy(functions[name]))
        ast.fix_missing_locations(copied)
        bodies[name] = ast.dump(copied, include_attributes=False)
    return {"bodies": bodies, "constants": constants}


def _readable(path: Path, name: str) -> str:
    """The normalised source of one function, for a failure message a human can read."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    func = _function(tree, name)
    copied = _Normalise(_refusal_class_of(_function(tree, "enable_wal_journal"))).visit(
        copy.deepcopy(func)
    )
    ast.fix_missing_locations(copied)
    return ast.unparse(copied)


def test_the_kernel_and_runtime_wal_mechanisms_are_the_same_mechanism() -> None:
    """The one assertion this module exists for, now statement by statement."""
    kernel = _mechanism_of(KERNEL_MODULE)
    runtime = _mechanism_of(RUNTIME_MODULE)

    assert kernel["constants"] == runtime["constants"]
    for name in _COMPARED_FUNCTIONS:
        assert kernel["bodies"][name] == runtime["bodies"][name], (
            f"the kernel and runtime `{name}` have drifted apart; they are duplicated "
            "on purpose (the import firewall forbids sharing) and must stay identical "
            "statement for statement.\n\n--- kernel ---\n"
            f"{_readable(KERNEL_MODULE, name)}\n\n--- runtime ---\n"
            f"{_readable(RUNTIME_MODULE, name)}"
        )


def test_the_shared_mechanism_is_the_one_the_fix_describes() -> None:
    """...and that it is the RIGHT mechanism, not merely two copies of the same wrong one."""
    source = KERNEL_MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(KERNEL_MODULE))
    enable = _function(tree, "enable_wal_journal")
    wait = _function(tree, "_wait_out_the_lock_and_retry")

    assert _executed_sql(_function(tree, "_switch_journal_to_wal")) == (
        "PRAGMA journal_mode=WAL",
    )
    assert _executed_sql(wait) == ("BEGIN IMMEDIATE", "ROLLBACK")
    assert (
        _calls_to(enable, "_switch_journal_to_wal")
        + _calls_to(wait, "_switch_journal_to_wal")
        == 2
    )
    assert (
        _final_return_expression(_function(tree, "_is_lock_contest"))
        == "code & _SQLITE_PRIMARY_CODE_MASK == sqlite3.SQLITE_BUSY"
    )
    assert _mechanism_of(KERNEL_MODULE)["constants"] == {
        "_WAL_JOURNAL_MODE": "wal",
        "_SQLITE_PRIMARY_CODE_MASK": 0xFF,
    }


def test_a_dropped_lowercase_on_the_returned_mode_is_caught(tmp_path: Path) -> None:
    """**Review round-2 F7's own example**, which the seven-fact projection could not see."""
    source = KERNEL_MODULE.read_text(encoding="utf-8")
    marker = 'return "" if row is None else str(row[0]).lower()'
    assert source.count(marker) == 1, "the switch's return expression moved"
    mutated = tmp_path / "_wal.py"
    mutated.write_text(
        source.replace(marker, 'return "" if row is None else str(row[0])'),
        encoding="utf-8",
    )

    assert (
        _mechanism_of(mutated)["bodies"]["_switch_journal_to_wal"]
        != _mechanism_of(RUNTIME_MODULE)["bodies"]["_switch_journal_to_wal"]
    )


def test_a_module_with_two_named_raises_is_refused(tmp_path: Path) -> None:
    """∅-seal on the normalisation itself."""
    source = KERNEL_MODULE.read_text(encoding="utf-8")
    marker = "    mode: str | None = None\n"
    assert source.count(marker) == 1
    mutated = tmp_path / "_wal.py"
    mutated.write_text(
        source.replace(
            marker, marker + '    if conn is None:\n        raise ValueError("x")\n'
        ),
        encoding="utf-8",
    )

    with pytest.raises(MechanismNotFound, match="refusal class"):
        _mechanism_of(mutated)


@pytest.mark.parametrize("name", _REQUIRED_FUNCTIONS)
def test_a_renamed_mechanism_function_is_refused_not_ignored(
    tmp_path: Path, name: str
) -> None:
    """∅-seal: the extractor must RAISE on a rename, never return a matching empty."""
    source = KERNEL_MODULE.read_text(encoding="utf-8").replace(
        f"def {name}(", f"def {name}_renamed("
    )
    renamed = tmp_path / "_wal.py"
    renamed.write_text(source, encoding="utf-8")

    with pytest.raises(MechanismNotFound, match=name):
        _mechanism_of(renamed)


def test_a_looped_retry_is_refused_even_though_the_call_count_is_unchanged(
    tmp_path: Path,
) -> None:
    """**Review F3.** The loop shape that slipped past the attempt count, on the RUNTIME text."""
    source = RUNTIME_MODULE.read_text(encoding="utf-8")
    marker = '    conn.execute("BEGIN IMMEDIATE")\n    conn.execute("ROLLBACK")\n'
    assert source.count(marker) == 1, "the wait's statement pair moved"
    looped = source.replace(
        marker,
        "    for _attempt in range(5):\n"
        '        conn.execute("BEGIN IMMEDIATE")\n'
        '        conn.execute("ROLLBACK")\n'
        "        if _attempt >= 0:\n"
        "            break\n",
    )
    mutated = tmp_path / "schema_ledger.py"
    mutated.write_text(looped, encoding="utf-8")

    with pytest.raises(MechanismNotFound, match="For"):
        _mechanism_of(mutated)


def test_a_recursive_retry_is_refused(tmp_path: Path) -> None:
    """The other unbounded shape: the wait calling itself instead of looping."""
    source = KERNEL_MODULE.read_text(encoding="utf-8")
    marker = "    mode = _switch_journal_to_wal(conn)\n    return mode\n"
    assert source.count(marker) == 1, "the wait's tail moved"
    recursive = source.replace(
        marker,
        "    mode = _switch_journal_to_wal(conn)\n"
        "    if mode != _WAL_JOURNAL_MODE:\n"
        "        return _wait_out_the_lock_and_retry(conn)\n"
        "    return mode\n",
    )
    mutated = tmp_path / "_wal.py"
    mutated.write_text(recursive, encoding="utf-8")

    with pytest.raises(MechanismNotFound, match="recursion"):
        _mechanism_of(mutated)


def test_a_second_retry_is_refused_by_the_comparison(tmp_path: Path) -> None:
    """The comparison is live: one extra switch attempt on one side makes it red."""
    source = KERNEL_MODULE.read_text(encoding="utf-8")
    marker = "    mode = _switch_journal_to_wal(conn)\n    return mode\n"
    assert source.count(marker) == 1, "the wait's tail moved"
    mutated = tmp_path / "_wal.py"
    mutated.write_text(
        source.replace(
            marker,
            "    _switch_journal_to_wal(conn)\n"
            "    mode = _switch_journal_to_wal(conn)\n"
            "    return mode\n",
        ),
        encoding="utf-8",
    )

    assert (
        _mechanism_of(mutated)["bodies"]["_wait_out_the_lock_and_retry"]
        != _mechanism_of(RUNTIME_MODULE)["bodies"]["_wait_out_the_lock_and_retry"]
    )
