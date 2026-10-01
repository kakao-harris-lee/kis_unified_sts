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
no logging convention at all, their refusal classes are deliberately named differently
(review round-2 F5), and their docstrings differ throughout. Pinning the source text
would make all of that a permanent false alarm.

So what is compared is the **normalised syntax tree** of the four mechanism functions,
with exactly three things stripped and one renamed — each because it is a difference the
two copies are entitled to, and each enumerated in :class:`_Normalise`: docstrings,
``_LOG`` calls and the assignments that only feed them, a handler whose whole body is a
bare re-raise, and each module's own refusal class (rewritten to a placeholder with its
message dropped). Everything else must match statement for statement.

**An earlier cut compared seven extracted facts instead, and review round-2 F7 was right
that a projection cannot do this job.** Measured on its own example: drop the ``.lower()``
from ``_switch_journal_to_wal``'s return and the two mechanisms start accepting different
answers from sqlite, while all seven facts — both SQL sequences, the attempt count, the
three guards, the constants — are byte-identical. The tree comparison sees it;
:func:`test_a_dropped_lowercase_on_the_returned_mode_is_caught` pins that.

Equality alone is still not enough, because both sides can be wrong in step — which has
happened here once already, when the fact extractor read ``return False`` out of
``_is_lock_contest`` on both sides and compared the two matching wrong answers as
agreement. :func:`test_the_shared_mechanism_is_the_one_the_fix_describes` therefore
asserts a handful of values outright. And a rename does not quietly pass:
:func:`_mechanism_of` RAISES when a named function, constant or refusal class is missing,
so an extractor that finds nothing fails instead of reporting two matching empties.
"""

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

#: The functions whose normalised bodies must be identical. ``enable_wal_journal`` and
#: the two helpers it reaches are the whole mechanism; nothing else in either module is
#: shared, and nothing in the mechanism is left out.
_COMPARED_FUNCTIONS = (
    "_is_lock_contest",
    "_switch_journal_to_wal",
    "_wait_out_the_lock_and_retry",
    "enable_wal_journal",
)


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


def _reject_repetition(func: ast.FunctionDef, callees: tuple[str, ...]) -> None:
    """Refuse any shape that could run the switch more than the pinned number of times.

    **Review F3.** ``switch_attempts`` counts CALL SITES, which is only the same thing as
    "attempts" while the code is straight-line. Wrap the wait and the retry in
    ``for _ in range(5): ...`` and the count stays 2 while the mechanism has become an
    unbounded hammer — precisely the drift this module says it forbids, passing green.
    So a loop anywhere in these two functions is refused outright, and so is recursion
    back into the switch or the wait.

    ``ast.Try`` is deliberately NOT refused, though the review listed it: both sides
    legitimately contain one — ``enable_wal_journal``'s classifying handler on both, and
    the runtime's logging re-raise in the wait — so banning it would turn this pin red on
    the current, correct code. A ``try`` cannot repeat anything by itself; the ``if``
    counts in :func:`_mechanism_of` already pin the handler's shape.
    """
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


#: Helpers that exist only to build a log line. An assignment whose value is a call to
#: one of these is stripped along with the ``_LOG`` call it feeds — the runtime reads the
#: database filename to name it in its warning, and the kernel, which logs nothing, has
#: no counterpart. Named explicitly rather than inferred, so widening the exemption is a
#: visible edit to this list.
_LOG_SUPPORT_CALLS = frozenset({"_database_file"})

#: The logger object whose calls are stripped. Same reasoning.
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
    """Strip exactly what the two copies are ENTITLED to differ on, and nothing else.

    Three rules, each one a thing the kernel deliberately does not have:

    1. **Docstrings.** Every prose difference between the two lives here.
    2. **Logging.** ``_LOG.<level>(...)`` statements, and assignments that only feed
       them (:data:`_LOG_SUPPORT_CALLS`). The kernel emits no log line at all — `tos/src`
       has no logging convention — which is a documented decision, not drift.
    3. **A handler that only re-raises.** After rule 2, the runtime's
       ``try: X / except E: raise`` has an empty-but-for-``raise`` handler, which is
       semantically transparent: it is replaced by ``X``. A handler with anything else
       in it — such as ``enable_wal_journal``'s own classifying ``if`` — is left alone,
       because that one IS the mechanism.

    And one renaming, not a strip: each module's own refusal class is rewritten to a
    placeholder with its message dropped, so the two may name and word their refusals
    differently (they must — review round-2 F5 made the kernel's name distinct on
    purpose) while still having to refuse at the same point. A ``raise`` of anything
    else is untouched and therefore compared.
    """

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
    """The name of the class ``enable_wal_journal`` raises for a non-WAL answer.

    Located from the code rather than configured, so a module that stopped raising — or
    started raising two different things — is a :class:`MechanismNotFound` rather than a
    silently unnormalised comparison. The bare ``re-raise`` carries no ``exc`` and is not
    counted.
    """
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
    """The three mechanism functions, normalised, plus the constants they turn on.

    What is compared is the **normalised syntax tree of the function bodies**, not a
    hand-picked projection of them (review round-2 F7). The projection compared seven
    facts and therefore could not see a semantic change outside those seven — a dropped
    ``.lower()`` on the returned mode, a different ``fetchone()`` handling, a statement
    that is not an ``.execute`` literal. A tree comparison has no such blind spot: every
    statement either matches or the test is red.

    Raises:
        MechanismNotFound: A required function or constant is absent, the refusal class
            cannot be located, or the retry is written as a loop or a recursion rather
            than straight-line (:func:`_reject_repetition`). Never returns a partial
            answer — an extractor that shrugged would make this comparison vacuous.
    """
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
    """The one assertion this module exists for, now statement by statement.

    Goes RED on ANY semantic difference between the two bodies — a second retry, a
    dropped return-value check, a discriminator that stops masking the extended result
    code, a different wait statement, a dropped ``.lower()`` on the mode sqlite returns,
    a ``fetchone()`` handled differently. The previous cut compared seven extracted
    facts and was blind to everything outside them (review round-2 F7).

    It stays green for the three differences the two copies are entitled to:
    docstrings, logging, and the name and wording of each module's own refusal class.
    :class:`_Normalise` carries the reasoning for each.
    """
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
    """...and that it is the RIGHT mechanism, not merely two copies of the same wrong one.

    Equality alone would survive both sides being broken in step — which is exactly what
    a copy-paste change would do, and it is not hypothetical: an earlier cut of this
    module read ``return False`` out of ``_is_lock_contest`` on BOTH sides and compared
    the two matching wrong answers as agreement. So a handful of values are asserted
    outright, against what #818's plan §2.1 names.
    """
    source = KERNEL_MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(KERNEL_MODULE))
    enable = _function(tree, "enable_wal_journal")
    wait = _function(tree, "_wait_out_the_lock_and_retry")

    assert _executed_sql(_function(tree, "_switch_journal_to_wal")) == (
        "PRAGMA journal_mode=WAL",
    )
    assert _executed_sql(wait) == ("BEGIN IMMEDIATE", "ROLLBACK")
    # Two attempts total: the first one, and the single retry after the wait.
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
    """**Review round-2 F7's own example**, which the seven-fact projection could not see.

    ``_switch_journal_to_wal`` normalises sqlite's answer with ``.lower()`` before the
    caller compares it to ``"wal"``. Drop that on one side and the two mechanisms accept
    different answers from sqlite — while ``switch_sql``, ``wait_sql``, the attempt
    count, the guards and the constants are all unchanged.
    """
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
    """∅-seal on the normalisation itself.

    The refusal class is located from the code so each module can name its own (review
    round-2 F5 made the kernel's distinct on purpose). A locator that shrugged when it
    could not identify one would normalise nothing and quietly turn the comparison into
    a comparison of un-normalised trees — green for the wrong reason. Two named raises
    is the ambiguous case; it refuses.
    """
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


def test_a_looped_retry_is_refused_even_though_the_call_count_is_unchanged(
    tmp_path: Path,
) -> None:
    """**Review F3.** The loop shape that slipped past the attempt count, on the RUNTIME text.

    The mutation is the one the review named: wrap the wait and the retry in
    ``for _ in range(5)`` with a ``break`` on success. ``_switch_journal_to_wal`` is
    still called once in the wait and once in ``enable_wal_journal``, so
    ``switch_attempts`` stays 2 and ``wait_sql`` is unchanged — the comparison alone
    could not see it. It is measured on the runtime module rather than the kernel one
    because that is the side with the more elaborate wait, and the pin has to hold for
    whichever side drifts.
    """
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
    """The other unbounded shape: the wait calling itself instead of looping.

    Recursion adds no call site inside the function body that ``switch_attempts`` can
    see, so without this the attempt count would still read 2.
    """
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
    """The comparison is live: one extra switch attempt on one side makes it red.

    Proven by mutating a scratch copy rather than by arguing from the code, so "the pin
    fires" is measured. A second retry is the specific drift the plan's §2.1 "exactly
    one retry" decision forbids.
    """
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
