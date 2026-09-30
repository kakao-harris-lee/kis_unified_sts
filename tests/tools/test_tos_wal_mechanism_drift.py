"""The WAL birth-race mechanism exists TWICE; this is what keeps the two the same one.

``tos/src/tos/staterestore/_wal.py`` (kernel, #823) and
``tos/runtime/src/tos_runtime/operations/schema_ledger.py`` (runtime, #818 / PR #820)
carry the same "wait out the lock and retry once" mechanism. The duplication is
deliberate and not removable by either side:

* the kernel **cannot import** the runtime helper — ``tos -> tos_runtime`` is forbidden
  outright by the asymmetric import firewall (design §3, rule (g),
  ``.importlinter`` contract ``tos-kernel-must-not-import-runtime``);
* moving the helper DOWN into the kernel so the runtime imports it from there would add
  to the ratified pure-commons set, which is a design-document revision rather than a
  bug fix (issue #823 approach 2, not taken).

So the copy is held honest the way this repo already holds a duplicated ``entries`` DDL
honest (``tests/tools/test_tos_evidence_scan_bench.py``): a test READS both modules as
text and fails when they stop agreeing. Reading is firewall-safe — nothing is imported,
so no import edge is created in either direction, and this file lives in ``tests/tools``
rather than in either package's own suite precisely so it belongs to neither side.

**What is compared is the MECHANISM, not the prose.** The two modules differ on purpose:
the runtime one logs three ``WARNING`` lines (a refused boot there can block a
supervisor for ~3x the busy timeout per store, across four stores) while the kernel has
no logging convention at all, and their docstrings, refusal messages and module names
differ throughout. Pinning the source text would make that a permanent false alarm. What
is extracted instead is the seven facts that ARE the fix:

  1-2. the SQL each of the two statement-running helpers executes, in order;
  3.   how many times the switch is attempted (two: the retry is exactly one);
  4.   the guard that decides a retry happens at all (``mode is None``);
  5.   the discriminator that decides an error is a lock contest — by PRIMARY code;
  6.   the guard that re-raises a non-contest from the FIRST attempt;
  7.   the check that refuses a journal mode which is not ``wal``, and the two constants
       that check turns on.

A rename on one side does not quietly pass: :func:`_mechanism_of` RAISES when a named
function or constant is missing, so an extractor that finds nothing fails instead of
reporting two matching empties.
"""

from __future__ import annotations

import ast
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

#: Statements a module runs only to build a log line, filtered out before the SQL
#: sequences are compared. The runtime reads this one to name the file in its warning;
#: the kernel emits no warning and so runs it never. Filtering it is what lets the two
#: SQL sequences be compared as the mechanism they are (the same lesson PR #820's own
#: round-3 F4 recorded: pinning a diagnostic as mechanism makes harmless log changes
#: look like mechanism changes).
_DIAGNOSTIC_SQL = frozenset({"PRAGMA database_list"})

#: The functions and constants :func:`_mechanism_of` requires both modules to define.
_REQUIRED_FUNCTIONS = (
    "_is_lock_contest",
    "_switch_journal_to_wal",
    "_wait_out_the_lock_and_retry",
    "enable_wal_journal",
)
_REQUIRED_CONSTANTS = ("_WAL_JOURNAL_MODE", "_SQLITE_PRIMARY_CODE_MASK")


class MechanismNotFound(AssertionError):
    """A named function or constant is missing from a module under comparison.

    Its own exception type, and an ``AssertionError``, so a rename cannot be mistaken
    for agreement: without this the extractor would return two empty structures and the
    comparison below would pass while pinning nothing.
    """


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
    """The expression of the function's LAST top-level ``return``.

    Top-level on purpose. ``ast.walk`` is breadth-first, so taking its last ``Return``
    picks up whichever nested early-out happens to sit deepest — for
    ``_is_lock_contest`` that is the ``return False`` guard, not the discriminator this
    module exists to pin. Both modules would have yielded that same wrong answer and
    compared equal, which is why :func:`test_the_shared_mechanism_is_the_one_the_fix_describes`
    checks the VALUE and not only the agreement (it caught exactly this, measured).
    """
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


def _mechanism_of(path: Path) -> dict[str, object]:
    """The seven mechanism facts, read out of ``path``'s syntax tree.

    Raises:
        MechanismNotFound: A required function or constant is absent, or a required
            statement shape is not there to read. Never returns a partial answer — an
            extractor that shrugged would make this whole comparison vacuous.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {name: _function(tree, name) for name in _REQUIRED_FUNCTIONS}
    constants = {name: _constant(tree, name) for name in _REQUIRED_CONSTANTS}

    enable = functions["enable_wal_journal"]
    wait = functions["_wait_out_the_lock_and_retry"]

    handlers = [
        node for node in ast.walk(enable) if isinstance(node, ast.ExceptHandler)
    ]
    if len(handlers) != 1:
        raise MechanismNotFound(
            f"enable_wal_journal has {len(handlers)} except handlers, expected exactly 1"
        )
    handler_tests = [
        ast.unparse(node.test)
        for node in ast.walk(handlers[0])
        if isinstance(node, ast.If)
    ]
    if len(handler_tests) != 1:
        raise MechanismNotFound(
            "enable_wal_journal's except handler must hold exactly one `if`: the "
            f"re-raise guard; found {handler_tests}"
        )
    # The handler's own `if` is reachable from the function too, so it is removed here
    # rather than double-counted; what is left must be the retry guard and the refusal.
    body_tests = [test for test in _if_tests(enable) if test not in handler_tests]
    if len(body_tests) != 2:
        raise MechanismNotFound(
            "enable_wal_journal must hold exactly two `if`s outside its handler: the "
            f"retry guard and the refusal check; found {body_tests}"
        )

    return {
        "switch_sql": _executed_sql(functions["_switch_journal_to_wal"]),
        "wait_sql": _executed_sql(wait),
        "switch_attempts": _calls_to(enable, "_switch_journal_to_wal")
        + _calls_to(wait, "_switch_journal_to_wal"),
        "retry_guard": body_tests[0],
        "refusal_check": body_tests[1],
        "reraise_guard": handler_tests[0],
        "lock_contest_test": _final_return_expression(functions["_is_lock_contest"]),
        "constants": constants,
    }


def test_the_kernel_and_runtime_wal_mechanisms_are_the_same_mechanism() -> None:
    """The one assertion this module exists for.

    Goes RED the moment either side changes what the fix DOES — a second retry, a
    dropped return-value check, a discriminator that stops masking the extended result
    code, a different wait statement — while staying green for every difference the two
    are entitled to have (logging, docstrings, refusal wording, module identity).
    """
    kernel = _mechanism_of(KERNEL_MODULE)
    runtime = _mechanism_of(RUNTIME_MODULE)

    assert kernel == runtime, (
        "the kernel and runtime WAL birth-race mechanisms have drifted apart; they are "
        "duplicated on purpose (the import firewall forbids sharing) and must stay "
        "identical statement for statement"
    )


def test_the_shared_mechanism_is_the_one_the_fix_describes() -> None:
    """...and that it is the RIGHT mechanism, not merely two copies of the same wrong one.

    Equality alone would survive both sides being broken in step — which is exactly what
    a copy-paste change would do. These are the values #818's plan §2.1 names.
    """
    kernel = _mechanism_of(KERNEL_MODULE)

    assert kernel["switch_sql"] == ("PRAGMA journal_mode=WAL",)
    assert kernel["wait_sql"] == ("BEGIN IMMEDIATE", "ROLLBACK")
    # Two attempts total: the first one, and the single retry after the wait.
    assert kernel["switch_attempts"] == 2
    assert kernel["retry_guard"] == "mode is None"
    assert kernel["refusal_check"] == "mode != _WAL_JOURNAL_MODE"
    assert kernel["reraise_guard"] == "not _is_lock_contest(exc)"
    assert (
        kernel["lock_contest_test"]
        == "code & _SQLITE_PRIMARY_CODE_MASK == sqlite3.SQLITE_BUSY"
    )
    assert kernel["constants"] == {
        "_WAL_JOURNAL_MODE": "wal",
        "_SQLITE_PRIMARY_CODE_MASK": 0xFF,
    }


@pytest.mark.parametrize("name", _REQUIRED_FUNCTIONS)
def test_a_renamed_mechanism_function_is_refused_not_ignored(
    tmp_path: Path, name: str
) -> None:
    """∅-seal: the extractor must RAISE on a rename, never return a matching empty.

    Without this, renaming ``_is_lock_contest`` on one side would leave both extractions
    missing the same key and the comparison above would still pass — the "guard that
    admits what it names" failure this repo keeps re-finding.
    """
    source = KERNEL_MODULE.read_text(encoding="utf-8").replace(
        f"def {name}(", f"def {name}_renamed("
    )
    renamed = tmp_path / "_wal.py"
    renamed.write_text(source, encoding="utf-8")

    with pytest.raises(MechanismNotFound, match=name):
        _mechanism_of(renamed)


def test_a_second_retry_is_refused_by_the_comparison(tmp_path: Path) -> None:
    """The comparison is live: one extra switch attempt on one side makes it red.

    Proven by mutating a scratch copy rather than by arguing from the code, so "the pin
    fires" is measured. A second retry is the specific drift the plan's §2.1 "exactly
    one retry" decision forbids.
    """
    source = KERNEL_MODULE.read_text(encoding="utf-8").replace(
        '    conn.execute("ROLLBACK")\n    return _switch_journal_to_wal(conn)',
        '    conn.execute("ROLLBACK")\n    _switch_journal_to_wal(conn)\n'
        "    return _switch_journal_to_wal(conn)",
    )
    mutated = tmp_path / "_wal.py"
    mutated.write_text(source, encoding="utf-8")

    assert _mechanism_of(mutated)["switch_attempts"] == 3
    assert _mechanism_of(mutated) != _mechanism_of(RUNTIME_MODULE)
