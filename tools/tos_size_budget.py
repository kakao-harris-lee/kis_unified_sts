#!/usr/bin/env python3
"""tos kernel module/function size budget checker (Phase 1 작업 6).

Enforces a configurable size budget (``config/tos_size_budget.yaml``) over the tos
kernel source tree: any module or function whose physical line count exceeds the
configured threshold must be listed in the config's ``exceptions:`` register with an
owner, a ``decomposition_order``, and an ``expires_on`` date. Registration is
**visibility, not a licence** (design decision,
``docs/plans/2026-09-07-tos-phase1-kernel-hard-gate-execution-plan.md`` §3):
decomposing the currently over-budget targets is out of Phase 1 scope, but an
unregistered, expired, or stale exception fails ``--check``.

Why a bespoke tool: ruff has no file-length rule, and pylint's ``C0302``
(too-many-lines) / ``R0915`` (too-many-statements) cannot express an owner + expiry
register — so this is a small stdlib(+PyYAML)-only AST tool (design decision, plan
§3), not a general linter. Thresholds and the scope directory list are config
(``config/tos_size_budget.yaml``), never hardcoded here, per the repo's
non-negotiable "configuration-driven only" rule.

Failure classes enforced by ``--check`` (never silently pass):

    (a) an over-budget target has no matching ``exceptions:`` entry
    (b) an exception's ``expires_on`` has passed (fail-closed: expiry is not
        renewed by inaction)
    (c) a *stale* exception — its target no longer exists in scope, or is no longer
        over budget (the register must not accumulate dead entries)
    (d) a malformed exception entry (missing/mistyped field) or a duplicate
        ``decomposition_order`` across entries
    (e) the config file itself is missing, unreadable, not valid YAML, or fails
        top-level schema validation
    (f) an exception's registered ``measured`` no longer matches the target's actual
        current line count (growth *or* shrinkage) — the register is a ratchet, not
        a snapshot: a target that keeps growing under an unchanged ``measured`` value
        would pass ``--check`` forever with no visible record that it grew.
        Re-registering (fixing ``measured`` to the new actual count) is a deliberate
        act, never automatic — the check only flags the drift, it never silently
        accepts it.

(a)-(d) and (f) are collected and each printed as one violation line; ``--check``
exits 1 if that list is non-empty. (e) is a distinct hard failure — the checker
cannot even measure without a valid config, so it raises immediately rather than
reporting "0 violations" (see the "a checker that never fails is dead" fail-open
discipline documented via ``--self-test`` in ``tools/tos_contract_check.py``: a
size-budget checker with no live red path would be exactly that kind of dead check,
which is why ``tests/tools/test_tos_size_budget.py`` proves each class (a)-(f) red
on a synthetic fixture, not just green on the real tree).
"""

from __future__ import annotations

import argparse
import ast
import datetime as _dt
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path("config/tos_size_budget.yaml")

#: Directory names pruned from the scope walk by exact name (not full path), matching
#: the firewall forward-scan convention documented in tos/CLAUDE.md.
_PRUNED_DIR_NAMES = frozenset({"__pycache__", ".venv"})

REQUIRED_ENTRY_FIELDS = (
    "target",
    "measured",
    "owner",
    "decomposition_order",
    "expires_on",
    "note",
)


class SizeBudgetConfigError(Exception):
    """The config file is missing, unparseable, or fails top-level schema validation.

    This is failure class (e) — a hard stop, not a collected violation, because the
    checker cannot measure anything without a structurally valid config.
    """


@dataclass(frozen=True)
class ExceptionEntry:
    """One registered ``exceptions:`` entry (already schema-validated)."""

    target: str
    measured: int
    owner: str
    decomposition_order: int
    expires_on: _dt.date
    note: str


@dataclass(frozen=True)
class BudgetConfig:
    module_max_lines: int
    function_max_lines: int
    scope: tuple[str, ...]
    exceptions: tuple[ExceptionEntry, ...]


@dataclass(frozen=True)
class Measured:
    """One module or function as measured from source, over-budget or not.

    Attributes:
        target: The module's scope-relative posix path, or ``"<path>::<qualname>"``
            for a function (``qualname`` dotted through enclosing classes/functions).
        kind: ``"module"`` or ``"function"`` — selects which configured threshold
            applies.
        lines: Physical line count. For a function this is
            ``end_lineno - lineno + 1`` of the ``FunctionDef``/``AsyncFunctionDef``
            node (decorators excluded, matching each decorator's own ``lineno``).
    """

    target: str
    kind: str
    lines: int


def _parse_date(value: object, *, where: str) -> _dt.date:
    if not isinstance(value, str):
        raise SizeBudgetConfigError(
            f"{where}: expires_on must be a string (ISO date), got {value!r}"
        )
    try:
        return _dt.date.fromisoformat(value)
    except ValueError as exc:
        raise SizeBudgetConfigError(
            f"{where}: expires_on {value!r} is not an ISO date (YYYY-MM-DD)"
        ) from exc


def _is_plain_int(value: object) -> bool:
    # bool is an int subclass; a YAML "true"/"false" must not silently pass as 0/1.
    return isinstance(value, int) and not isinstance(value, bool)


def load_config(config_path: Path) -> tuple[BudgetConfig, list[str]]:
    """Load and schema-validate the size budget config.

    Structural problems with the config *file itself* (missing, unreadable, invalid
    YAML, root not a mapping, a required top-level key absent or mistyped) raise
    :class:`SizeBudgetConfigError` immediately — failure class (e).

    A malformed individual ``exceptions:`` entry (missing/mistyped field) does
    *not* abort loading: it is excluded from the returned config's ``exceptions``
    and reported as a ``"[malformed-entry] ..."`` string in the second return
    value, so ``run_check`` can report it as a class-(d) violation alongside every
    other well-formed entry's checks.

    Returns:
        ``(config, malformed_entry_messages)``.
    """
    if not config_path.is_file():
        raise SizeBudgetConfigError(f"config not found: {config_path}")
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SizeBudgetConfigError(f"config unreadable: {config_path}: {exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SizeBudgetConfigError(
            f"config is not valid YAML: {config_path}: {exc}"
        ) from exc

    if not isinstance(raw, dict):
        raise SizeBudgetConfigError(f"config root must be a mapping: {config_path}")

    missing_top = [
        key
        for key in ("module_max_lines", "function_max_lines", "scope")
        if key not in raw
    ]
    if missing_top:
        raise SizeBudgetConfigError(f"config missing required key(s): {missing_top}")

    module_max_lines = raw["module_max_lines"]
    function_max_lines = raw["function_max_lines"]
    scope = raw["scope"]
    if not _is_plain_int(module_max_lines) or module_max_lines <= 0:
        raise SizeBudgetConfigError("module_max_lines must be a positive int")
    if not _is_plain_int(function_max_lines) or function_max_lines <= 0:
        raise SizeBudgetConfigError("function_max_lines must be a positive int")
    if (
        not isinstance(scope, list)
        or not scope
        or not all(isinstance(item, str) and item for item in scope)
    ):
        raise SizeBudgetConfigError(
            "scope must be a non-empty list of directory strings"
        )

    raw_exceptions = raw.get("exceptions", [])
    if raw_exceptions is None:
        raw_exceptions = []
    if not isinstance(raw_exceptions, list):
        raise SizeBudgetConfigError("exceptions must be a list")

    entries: list[ExceptionEntry] = []
    malformed: list[str] = []
    for index, raw_entry in enumerate(raw_exceptions):
        where = f"exceptions[{index}]"
        entry = _parse_entry(raw_entry, where=where)
        if isinstance(entry, str):
            malformed.append(entry)
        else:
            entries.append(entry)

    config = BudgetConfig(
        module_max_lines=module_max_lines,
        function_max_lines=function_max_lines,
        scope=tuple(scope),
        exceptions=tuple(entries),
    )
    return config, malformed


def _parse_entry(raw_entry: object, *, where: str) -> ExceptionEntry | str:
    """Parse one ``exceptions:`` entry, returning a malformed-entry message on failure."""
    if not isinstance(raw_entry, dict):
        return f"[malformed-entry] {where}: entry must be a mapping, got {raw_entry!r}"
    missing = [field for field in REQUIRED_ENTRY_FIELDS if field not in raw_entry]
    if missing:
        return f"[malformed-entry] {where}: missing field(s) {missing}"

    target = raw_entry["target"]
    measured = raw_entry["measured"]
    owner = raw_entry["owner"]
    decomposition_order = raw_entry["decomposition_order"]
    note = raw_entry["note"]

    if not isinstance(target, str) or not target:
        return f"[malformed-entry] {where}: target must be a non-empty string"
    if not _is_plain_int(measured):
        return f"[malformed-entry] {where} ({target}): measured must be an int"
    if not isinstance(owner, str) or not owner:
        return f"[malformed-entry] {where} ({target}): owner must be a non-empty string"
    if not _is_plain_int(decomposition_order):
        return (
            f"[malformed-entry] {where} ({target}): decomposition_order must be an int"
        )
    if not isinstance(note, str) or not note:
        return f"[malformed-entry] {where} ({target}): note must be a non-empty string"
    try:
        expires_on = _parse_date(raw_entry["expires_on"], where=f"{where} ({target})")
    except SizeBudgetConfigError as exc:
        return f"[malformed-entry] {exc}"

    return ExceptionEntry(
        target=target,
        measured=measured,
        owner=owner,
        decomposition_order=decomposition_order,
        expires_on=expires_on,
        note=note,
    )


def _iter_scope_files(root: Path, scope: Sequence[str]) -> Iterator[Path]:
    seen: set[Path] = set()
    for rel in scope:
        base = (root / rel).resolve()
        if not base.is_dir():
            raise SizeBudgetConfigError(f"scope directory not found: {rel}")
        for path in sorted(base.rglob("*.py")):
            if any(part in _PRUNED_DIR_NAMES for part in path.parts):
                continue
            if path in seen:
                continue
            seen.add(path)
            yield path


def _target_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        # A symlink under a scope directory that resolves outside --root is a
        # measurement that cannot be honestly reported as a scope-relative path — fail
        # closed with the checker's own error class instead of letting a bare ValueError
        # (from pathlib) propagate as an unhandled crash.
        raise SizeBudgetConfigError(
            f"{path}: resolves to {resolved} which is outside --root {root} "
            "(a symlink escaping scope?)"
        ) from exc


def _iter_functions(tree: ast.Module, *, target: str) -> Iterator[tuple[str, int, int]]:
    """Yield ``(qualname, lineno, end_lineno)`` for every function, nested or a method.

    ``qualname`` is dotted through enclosing ``ClassDef``/``FunctionDef`` scopes (e.g.
    ``"Foo.bar"`` for method ``bar`` of class ``Foo``, ``"outer.inner"`` for a nested
    function) so two same-named functions in different scopes never collide as budget
    targets.

    Args:
        tree: The parsed module.
        target: The module's scope-relative path, used only to name the source in a
            :class:`SizeBudgetConfigError` if a function's span cannot be measured.
    """

    def walk(node: ast.AST, prefix: tuple[str, ...]) -> Iterator[tuple[str, int, int]]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                qualname = ".".join((*prefix, child.name))
                end_lineno = child.end_lineno
                if end_lineno is None:
                    # A measurement that cannot be taken is red, not silently skipped —
                    # matching the sibling SyntaxError path in ``measure()`` below. This
                    # should not happen for anything ``ast.parse`` itself produced (only a
                    # hand-built/mutated AST node lacks ``end_lineno``), but a skip here
                    # would silently under-count the module and hide a real function from
                    # the budget entirely.
                    raise SizeBudgetConfigError(
                        f"{target}::{qualname}: cannot measure — end_lineno is None"
                    )
                yield qualname, child.lineno, end_lineno
                yield from walk(child, (*prefix, child.name))
            elif isinstance(child, ast.ClassDef):
                yield from walk(child, (*prefix, child.name))
            else:
                yield from walk(child, prefix)

    yield from walk(tree, ())


def measure(root: Path, config: BudgetConfig) -> list[Measured]:
    """Measure every module and function in ``config.scope`` — over-budget or not."""
    results: list[Measured] = []
    for path in _iter_scope_files(root, config.scope):
        target = _target_path(path, root)
        text = path.read_text(encoding="utf-8")
        results.append(
            Measured(target=target, kind="module", lines=len(text.splitlines()))
        )
        try:
            tree = ast.parse(text, filename=target)
        except SyntaxError as exc:
            raise SizeBudgetConfigError(
                f"{target}: cannot parse for function measurement: {exc}"
            ) from exc
        for qualname, lineno, end_lineno in _iter_functions(tree, target=target):
            results.append(
                Measured(
                    target=f"{target}::{qualname}",
                    kind="function",
                    lines=end_lineno - lineno + 1,
                )
            )
    return results


def _limit_for(kind: str, config: BudgetConfig) -> int:
    return config.module_max_lines if kind == "module" else config.function_max_lines


def over_budget(measured: Sequence[Measured], config: BudgetConfig) -> list[Measured]:
    return [m for m in measured if m.lines > _limit_for(m.kind, config)]


def run_check(
    root: Path,
    config: BudgetConfig,
    malformed_entries: Sequence[str],
    *,
    today: _dt.date,
) -> list[str]:
    """Run every check class (a)-(d) and return one violation string per hit.

    Class (e) is not handled here — it is a load-time hard failure (see
    :func:`load_config`), never a member of this list.
    """
    violations: list[str] = list(malformed_entries)  # (d) malformed entries

    # (d) duplicate decomposition_order across otherwise well-formed entries
    order_seen: dict[int, str] = {}
    for entry in config.exceptions:
        prior = order_seen.get(entry.decomposition_order)
        if prior is not None:
            violations.append(
                f"[duplicate-order] decomposition_order={entry.decomposition_order} "
                f"used by both {prior!r} and {entry.target!r}"
            )
        else:
            order_seen[entry.decomposition_order] = entry.target

    measured = measure(root, config)
    measured_by_target = {m.target: m for m in measured}
    over = {m.target: m for m in over_budget(measured, config)}
    exceptions_by_target = {e.target: e for e in config.exceptions}

    # (a) over-budget target with no exception entry
    for target in sorted(over):
        if target not in exceptions_by_target:
            m = over[target]
            violations.append(
                f"[unregistered] {target}: {m.lines} lines exceeds "
                f"{_limit_for(m.kind, config)} with no exceptions entry"
            )

    # (b) expired exception — fail-closed regardless of current over-budget status
    for entry in config.exceptions:
        if entry.expires_on < today:
            violations.append(
                f"[expired] {entry.target}: exception expired "
                f"{entry.expires_on.isoformat()} (owner={entry.owner})"
            )

    # (c) stale exception — target gone, or no longer over budget
    for entry in config.exceptions:
        if entry.target not in measured_by_target:
            violations.append(
                f"[stale-missing] {entry.target}: no longer exists in scope — remove "
                "from exceptions"
            )
        elif entry.target not in over:
            violations.append(
                f"[stale-under-budget] {entry.target}: measured "
                f"{measured_by_target[entry.target].lines} lines, at or under budget — "
                "remove from exceptions"
            )

    # (f) measured drift — the registered `measured` is decorative unless it is
    # checked against what the target actually measures today (a target still
    # present and still over budget can grow silently forever otherwise).
    for entry in config.exceptions:
        current = measured_by_target.get(entry.target)
        if current is not None and current.lines != entry.measured:
            violations.append(
                f"[measured-drift] {entry.target}: registered {entry.measured}, actual "
                f"{current.lines} — re-register deliberately"
            )

    return violations


def _render_summary(root: Path, config: BudgetConfig, today: _dt.date) -> str:
    measured = measure(root, config)
    over = sorted(over_budget(measured, config), key=lambda m: -m.lines)
    exceptions_by_target = {e.target: e for e in config.exceptions}
    lines = [f"tos size budget — {len(over)} over-budget target(s) in scope"]
    for m in over:
        entry = exceptions_by_target.get(m.target)
        if entry is None:
            status = "UNREGISTERED"
        elif entry.expires_on < today:
            status = f"EXPIRED {entry.expires_on.isoformat()} (owner={entry.owner})"
        else:
            status = (
                f"registered order={entry.decomposition_order} "
                f"expires={entry.expires_on.isoformat()} owner={entry.owner}"
            )
        lines.append(f"  [{m.kind:8}] {m.lines:5} lines  {m.target}  -- {status}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 and print one line per violation instead of the summary table",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="path to the size budget YAML config",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_REPO_ROOT,
        help="root that scope directories and reported targets are relative to",
    )
    parser.add_argument(
        "--today",
        type=str,
        default=None,
        help="override today's date (YYYY-MM-DD) for deterministic expiry checks",
    )
    args = parser.parse_args(argv)

    today = (
        _dt.date.today()
        if args.today is None
        else _parse_date(args.today, where="--today")
    )

    try:
        config, malformed = load_config(args.config)
        if args.check:
            violations = run_check(args.root, config, malformed, today=today)
            if violations:
                print(f"tos size budget FAIL: {len(violations)} violation(s)")
                for line in violations:
                    print(f"  {line}")
                return 1
            print(
                f"tos size budget PASS: 0 violations "
                f"({len(config.exceptions)} registered exception(s))"
            )
            return 0
        print(_render_summary(args.root, config, today))
        return 0
    except SizeBudgetConfigError as exc:
        print(f"tos size budget FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
