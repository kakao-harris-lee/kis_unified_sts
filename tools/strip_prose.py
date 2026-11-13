#!/usr/bin/env python3
"""Mechanical prose stripper for the tos trees (code-halving plan S4).

Keeps the **first line** of every docstring and deletes comments, except
comments that carry a tool marker (``noqa``, ``type:``, ``pragma``, ``fmt:``), a
shebang, or an encoding cookie.

The transformation is AST + tokenize based, idempotent (a second run is a
no-op), and behaviour preserving: ``--verify`` re-parses each file before and
after and compares ``ast.dump`` with every docstring constant normalised away,
so any change outside docstring text is a hard failure.

    python tools/strip_prose.py --check            # exit 1 if anything would change
    python tools/strip_prose.py --verify           # AST equivalence only, no writes
    python tools/strip_prose.py --write            # rewrite in place (verifies first)
    python tools/strip_prose.py --write tos/src    # explicit paths override the scope

Scope is the S4 scope of ``docs/plans/2026-11-13-tos-code-halving-plan.md``.
``shared/``, ``scripts/``, ``services/`` and ``cli/`` are refused outright even
when named explicitly: ``shared/decision/setups/vwap_reversion.py`` and its
dependencies are the B3 witness and must stay byte-identical until
``TOS_PAPER_READY``.

Docstrings that are read at run time are left intact. A module that reads a bare
``__doc__`` (the ``argparse.ArgumentParser(description=__doc__)`` idiom) keeps
its module docstring; a module that reads ``<name>.__doc__`` keeps the docstring
of every definition called ``<name>``. Cross-module ``__doc__`` reads cannot be
seen from one file -- those are handled by changing the reader, not by this tool.

Run ``black`` afterwards: stripping leaves blank-line runs this tool
deliberately does not normalise (it only ever deletes, so every edit stays
reviewable as a deletion).
"""

from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import tokenize
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

#: S4 scope (plan §S4). Directories are walked for ``*.py``; globs are expanded.
DEFAULT_SCOPE: tuple[str, ...] = (
    "tos/src",
    "tos/runtime/src",
    "tos/runtime/cp3",
    "tools/tos_cp3",
    "tools/tos_*.py",
    "tos/tests",
    "tos/runtime/tests",
    "tests/tools/test_tos_*.py",
)

#: Never stripped, whatever ``--root`` and the path arguments say. The check is on the path's
#: own parts, not on a position relative to ``--root``: ``--root <repo>/shared decision`` would
#: otherwise reach the B3 witness ``shared/decision/setups/vwap_reversion.py``, which must stay
#: byte-identical until ``TOS_PAPER_READY`` (root ``CLAUDE.md``).
FORBIDDEN_ROOTS: tuple[str, ...] = ("shared", "scripts", "services", "cli")

#: Directory names pruned while walking.
PRUNED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".mypy_cache",
        ".ruff_cache",
    }
)

#: A comment holding one of these substrings is machine-readable, not prose. The last entry is
#: this repo's own per-line directive: ``tos/runtime/tests/engine/test_no_direct_core_calls.py``
#: refuses a direct ``core.handle(``/``core.run(`` call unless its line carries that exact
#: comment, so stripping it turns five sanctioned call sites into pin violations (measured in
#: the S4 dry run).
KEEP_MARKERS: tuple[str, ...] = (
    "noqa",
    "type:",
    "pragma",
    "fmt:",
    "direct-core-call:",
)

_ENCODING_COOKIE = re.compile(r"coding[:=]\s*([-\w.]+)")

_DOC_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


class StripError(RuntimeError):
    """A file could not be stripped safely."""


@dataclass(frozen=True)
class _Edit:
    start: int
    end: int
    replacement: bytes


def _split_lines(source: str) -> list[str]:
    """Split on ``\\n`` only -- ``str.splitlines`` also splits on form feeds."""
    parts = source.split("\n")
    lines = [part + "\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def _line_start_offsets(lines: Sequence[str]) -> list[int]:
    """Byte offset of the start of each line, plus the end-of-file offset."""
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line.encode("utf-8")))
    return offsets


def _docstring_stmt(node: ast.AST) -> ast.Expr | None:
    body = getattr(node, "body", None)
    if not body:
        return None
    first = body[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return first
    return None


def _first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _literal(first: str) -> str:
    """A one-line string literal holding ``first``, stable under a second pass AND under black.

    A first line that starts or ends with a double quote goes to ``repr``. Ending with one
    would close the literal early. STARTING with one parses fine, but black then inserts a
    space after the opening delimiter to keep the quotes readable -- which adds a leading
    space to the docstring's VALUE, so the next strip takes it out again and the two tools
    oscillate forever (measured on 7 files, 2026-11-13).
    """
    if not first:
        return '""'
    if (
        '"""' not in first
        and "\\" not in first
        and not first.startswith('"')
        and not first.endswith('"')
    ):
        return f'"""{first}"""'
    # Pick the quote black would pick, or the two tools rewrite each other forever: black
    # prefers `"` and switches to `'` only when `"` would need strictly more escapes. A content
    # ending in a quote takes the other one so no escape lands against the closing delimiter.
    if first.endswith('"'):
        quote = "'"
    elif first.endswith("'"):
        quote = '"'
    else:
        quote = '"' if first.count('"') <= first.count("'") else "'"
    escaped = (
        first.replace("\\", "\\\\")
        .replace(quote, "\\" + quote)
        .replace("\t", "\\t")
        .replace("\r", "\\r")
    )
    candidate = f"{quote}{escaped}{quote}"
    return candidate if ast.literal_eval(candidate) == first else repr(first)


def _runtime_doc_targets(tree: ast.Module) -> tuple[bool, set[str]]:
    """``(module docstring is read, names whose docstrings are read)``.

    ``"*"`` in the name set means "keep every docstring in this file": the read is through
    something this scan cannot resolve to a definition in the file — ``self``/``cls``, a call
    result, a subscript, or a dynamic ``getattr(x, "__doc__")``.
    """
    keep_module = False
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "__doc__":
            target = node.value
            if isinstance(target, ast.Name) and target.id not in {"self", "cls"}:
                names.add(target.id)
            elif isinstance(target, ast.Attribute):
                names.add(target.attr)
            else:
                keep_module = True
                names.add("*")
        elif isinstance(node, ast.Name) and node.id == "__doc__":
            keep_module = True
        elif _is_dynamic_doc_read(node):
            keep_module = True
            names.add("*")
    return keep_module, names


def _is_dynamic_doc_read(node: ast.AST) -> bool:
    """``getattr(x, "__doc__")`` / ``vars(x)["__doc__"]`` and friends — unresolvable, so keep all."""
    if not isinstance(node, ast.Call):
        return False
    function = node.func
    name = function.id if isinstance(function, ast.Name) else None
    if name not in {"getattr", "hasattr"}:
        return False
    return any(
        isinstance(argument, ast.Constant) and argument.value == "__doc__"
        for argument in node.args
    )


def _docstring_edits(
    source: str, lines: Sequence[str], offsets: Sequence[int]
) -> list[_Edit]:
    tree = ast.parse(source)
    keep_module, keep_names = _runtime_doc_targets(tree)
    keep_all = "*" in keep_names
    edits: list[_Edit] = []
    for node in ast.walk(tree):
        if not isinstance(node, _DOC_OWNERS):
            continue
        stmt = _docstring_stmt(node)
        if stmt is None:
            continue
        if keep_all:
            continue
        if isinstance(node, ast.Module):
            if keep_module:
                continue
        elif node.name in keep_names:
            continue
        constant = stmt.value
        assert isinstance(constant, ast.Constant)
        text = constant.value
        assert isinstance(text, str)
        replacement = _literal(_first_line(text))
        start = offsets[stmt.lineno - 1] + stmt.col_offset
        assert stmt.end_lineno is not None and stmt.end_col_offset is not None
        end = offsets[stmt.end_lineno - 1] + stmt.end_col_offset
        if source.encode("utf-8")[start:end] == replacement.encode("utf-8"):
            continue
        edits.append(_Edit(start, end, replacement.encode("utf-8")))
    return edits


def _keep_comment(text: str, row: int) -> bool:
    if row == 1 and text.startswith("#!"):
        return True
    if row <= 2 and _ENCODING_COOKIE.search(text):
        return True
    lowered = text.lower()
    return any(marker in lowered for marker in KEEP_MARKERS)


def _comment_edits(
    source: str, lines: Sequence[str], offsets: Sequence[int]
) -> list[_Edit]:
    edits: list[_Edit] = []
    readline = io.StringIO(source, newline="").readline
    for token in tokenize.generate_tokens(readline):
        if token.type != tokenize.COMMENT:
            continue
        row, col = token.start
        if _keep_comment(token.string, row):
            continue
        line = lines[row - 1]
        prefix = line[:col]
        if not prefix.strip():
            # Comment-only line: delete the line, newline included.
            edits.append(_Edit(offsets[row - 1], offsets[row], b""))
            continue
        cut = col
        while cut > 0 and line[cut - 1] in " \t":
            cut -= 1
        start = offsets[row - 1] + len(line[:cut].encode("utf-8"))
        end = offsets[token.end[0] - 1] + len(
            lines[token.end[0] - 1][: token.end[1]].encode("utf-8")
        )
        edits.append(_Edit(start, end, b""))
    return edits


def strip_source(source: str) -> str:
    """Return ``source`` with prose removed. Pure; raises on unparseable input."""
    lines = _split_lines(source)
    offsets = _line_start_offsets(lines)
    edits = _docstring_edits(source, lines, offsets) + _comment_edits(
        source, lines, offsets
    )
    if not edits:
        return source
    edits.sort(key=lambda edit: (edit.start, edit.end))
    for previous, current in zip(edits, edits[1:]):
        if current.start < previous.end:
            raise StripError(
                f"overlapping edits at byte {current.start} (previous ends "
                f"{previous.end}) -- refusing to rewrite"
            )
    raw = bytearray(source.encode("utf-8"))
    for edit in reversed(edits):
        raw[edit.start : edit.end] = edit.replacement
    return raw.decode("utf-8")


def normalised_dump(source: str) -> str:
    """``ast.dump`` with every docstring constant blanked out."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, _DOC_OWNERS):
            continue
        stmt = _docstring_stmt(node)
        if stmt is None:
            continue
        constant = stmt.value
        assert isinstance(constant, ast.Constant)
        constant.value = ""
        constant.kind = None
    return ast.dump(tree)


def verify_equivalent(before: str, after: str) -> None:
    """Raise :class:`StripError` unless the two sources differ only in docstrings."""
    if normalised_dump(before) != normalised_dump(after):
        raise StripError("AST changed outside docstring constants")


def _is_forbidden(path: Path, root: Path) -> bool:
    """True unless ``path`` is under ``root`` and no part of it names a forbidden root.

    The forbidden check reads the WHOLE resolved path, not just its first part relative to
    ``root``: ``--root <repo>/shared decision`` would otherwise make
    ``shared/decision/setups/vwap_reversion.py`` — the B3 witness — reachable. A checkout whose
    own ancestor directory is named ``shared``/``scripts``/``services``/``cli`` therefore strips
    nothing: a false refusal, which is the direction this rail is allowed to be wrong in.
    """
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return True
    return any(part in FORBIDDEN_ROOTS for part in resolved.parts)


def _walk(directory: Path) -> Iterator[Path]:
    for child in sorted(directory.iterdir()):
        if child.is_dir():
            if child.name in PRUNED_DIRS:
                continue
            yield from _walk(child)
        elif child.suffix == ".py":
            yield child


def iter_files(patterns: Iterable[str], root: Path) -> list[Path]:
    """Expand directories and globs into a sorted list of in-scope ``*.py`` files."""
    found: set[Path] = set()
    for pattern in patterns:
        candidate = root / pattern
        if candidate.is_dir():
            found.update(_walk(candidate))
        elif candidate.is_file():
            found.add(candidate)
        else:
            found.update(
                match
                for match in root.glob(pattern)
                if match.is_file() and match.suffix == ".py"
            )
    return sorted(path for path in found if not _is_forbidden(path, root))


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check", action="store_true", help="exit 1 if anything would change"
    )
    mode.add_argument(
        "--verify", action="store_true", help="AST equivalence only, no writes"
    )
    mode.add_argument("--write", action="store_true", help="rewrite files in place")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repo root",
    )
    parser.add_argument("paths", nargs="*", help=f"default: {' '.join(DEFAULT_SCOPE)}")
    args = parser.parse_args(argv)

    patterns = tuple(args.paths) if args.paths else DEFAULT_SCOPE
    files = iter_files(patterns, args.root)
    if not files:
        print("strip_prose: no files in scope", file=sys.stderr)
        return 2

    changed: list[tuple[Path, str]] = []
    failures: list[tuple[Path, str]] = []
    before_total = 0
    after_total = 0
    for path in files:
        try:
            source = _read(path)
            stripped = strip_source(source)
            verify_equivalent(source, stripped)
            if strip_source(stripped) != stripped:
                raise StripError("not idempotent: a second pass changes the file")
        except Exception as exc:  # noqa: BLE001 — one bad file must not stop the run
            failures.append((path, f"{type(exc).__name__}: {exc}"))
            continue
        before_total += len(_split_lines(source))
        after_total += len(_split_lines(stripped))
        if stripped != source:
            changed.append((path, stripped))

    def relative(path: Path) -> Path:
        return path.relative_to(args.root)

    for path, reason in failures:
        print(f"FAIL {relative(path)}: {reason}", file=sys.stderr)

    # All or nothing: a single unverifiable file leaves the whole tree untouched, so a failed
    # run never has to be half-reverted.
    if args.write and not failures:
        for path, stripped in changed:
            path.write_bytes(stripped.encode("utf-8"))

    print(
        f"strip_prose: {len(files)} files, {len(changed)} would change, "
        f"{before_total} -> {after_total} lines "
        f"({before_total - after_total} removed), {len(failures)} failures"
    )
    if failures:
        return 2
    if args.write:
        for path, _ in changed:
            print(f"stripped {relative(path)}")
        return 0
    if args.verify:
        return 0
    for path, _ in changed:
        print(f"would strip {relative(path)}")
    return 1 if changed else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
