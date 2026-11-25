#!/usr/bin/env python3
"""tos import-firewall gate (design §3.3-①) — default-deny AST enforcement."""

from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
from collections import namedtuple
from collections.abc import Iterator
from pathlib import Path

THIRD_PARTY_ALLOWED: frozenset[str] = frozenset(
    {"pydantic", "numpy", "pandas", "pytest", "hypothesis", "yaml"}
)

FORBIDDEN_STDLIB: frozenset[str] = frozenset(
    {
        "socket",
        "ssl",
        "http",
        "urllib.request",
        "ftplib",
        "smtplib",
        "poplib",
        "imaplib",
        "telnetlib",
        "subprocess",
        "ctypes",
    }
)

SHARED_ALLOWED: frozenset[str] = frozenset(
    {
        "shared.models",
        "shared.indicators",
        "shared.resilience",
        "shared.utils",
        "shared.exceptions",
        "shared.determinism",
    }
)

STDLIB: frozenset[str] = frozenset(sys.stdlib_module_names)


TOS_RUNTIME_PACKAGE_NAME: str = "tos_runtime"

RUNTIME_STDLIB_CARVEOUT: frozenset[str] = frozenset(
    {"socket", "ssl", "http", "urllib.request"}
)

FORBIDDEN_STDLIB_RUNTIME: frozenset[str] = FORBIDDEN_STDLIB - RUNTIME_STDLIB_CARVEOUT

_REVERSE_SCAN_PRUNE_ROOTS: tuple[str, ...] = (
    ".git",
    ".venv",
    ".omc",
    ".history",
    "tos",
    "open-trading-api",
    "strategy-builder-ui/node_modules",
)


_REVERSE_SCAN_TARGET_NAMES: frozenset[str] = frozenset({"tos", "tos_runtime"})

_REVERSE_LINE_RE = re.compile(r"^\s*(?:import|from)\s+(?:tos|tos_runtime)(?:\.|\s|$)")


Violation = namedtuple("Violation", ["rule", "path", "line", "message"])


def _matches_prefix(dotted: str, names: frozenset[str]) -> bool:
    """True if ``dotted`` equals, or is a dotted-child of, any name in ``names``."""
    return any(dotted == n or dotted.startswith(n + ".") for n in names)


def scope_for_tos_path(rel_display: str) -> str:
    """Classify a ``tos/`` file's repo-root-relative display path into"""
    parts = Path(rel_display).parts
    if len(parts) >= 2 and parts[0] == "tos" and parts[1] == "runtime":
        return "runtime"
    return "kernel"


def classify_module(dotted: str, scope: str = "kernel") -> tuple[bool, str | None]:
    """Classify an absolute dotted module path against the §3.2 allowlist"""
    if not dotted:
        return True, None
    forbidden_stdlib = (
        FORBIDDEN_STDLIB_RUNTIME if scope == "runtime" else FORBIDDEN_STDLIB
    )
    if _matches_prefix(dotted, forbidden_stdlib):
        return False, "TOS-FW-B"
    top = dotted.split(".")[0]
    if top == "tos":
        return True, None
    if top == "tos_runtime":
        if scope == "runtime":
            return True, None
        return False, "TOS-FW-G"
    if top == "shared":
        if scope == "runtime":
            return False, "TOS-FW-H"
        if _matches_prefix(dotted, SHARED_ALLOWED):
            return True, None
        return False, "TOS-FW-A"
    if top in THIRD_PARTY_ALLOWED:
        return True, None
    if top in STDLIB:
        return True, None
    return False, "TOS-FW-A"


def _import_violation_message(rule: str | None, name: str) -> str:
    """Build the diagnostic message for an (a)/(b)/(g)/(h) import violation."""
    if rule == "TOS-FW-G":
        return (
            f"kernel-scope file imports 'tos_runtime' via '{name}' — forbidden "
            "(rule g, design #40 D1.3: runtime may depend on the kernel, "
            "never the reverse)"
        )
    if rule == "TOS-FW-H":
        return (
            f"runtime-scope file imports 'shared.*' via '{name}' — forbidden "
            "(rule h, design #40 D1.1/D1.3 v1.2: the runtime shell opens no "
            "new commons dependency, even a commons package the KERNEL is "
            "itself allowed to import)"
        )
    return f"disallowed import '{name}'"


def check_tos_file(path: Path, rel_display: str) -> list[Violation]:
    """AST-scan a single ``tos/`` .py file for rules (a)-(d)/(g)/(h)."""
    scope = scope_for_tos_path(rel_display)
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                allowed, rule = classify_module(alias.name, scope)
                if not allowed:
                    violations.append(
                        Violation(
                            rule,
                            rel_display,
                            node.lineno,
                            _import_violation_message(rule, alias.name),
                        )
                    )
        elif isinstance(node, ast.ImportFrom):
            if not (node.level and node.level > 0):
                module = node.module or ""
                for alias in node.names:
                    cand = f"{module}.{alias.name}" if module else alias.name
                    allowed, rule = classify_module(cand, scope)
                    if not allowed:
                        violations.append(
                            Violation(
                                rule,
                                rel_display,
                                node.lineno,
                                _import_violation_message(rule, cand),
                            )
                        )

            if node.module == "os":
                for alias in node.names:
                    if alias.name in {"environ", "getenv"}:
                        violations.append(
                            Violation(
                                "TOS-FW-C",
                                rel_display,
                                node.lineno,
                                f"forbidden env access via import 'os.{alias.name}'",
                            )
                        )
            if node.module == "importlib":
                for alias in node.names:
                    if alias.name == "import_module":
                        violations.append(
                            Violation(
                                "TOS-FW-D",
                                rel_display,
                                node.lineno,
                                "forbidden dynamic import 'importlib.import_module'",
                            )
                        )
        elif isinstance(node, ast.Attribute):
            if (
                node.attr in {"environ", "getenv"}
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
            ):
                violations.append(
                    Violation(
                        "TOS-FW-C",
                        rel_display,
                        node.lineno,
                        f"forbidden env access 'os.{node.attr}'",
                    )
                )
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in {"__import__", "exec", "eval"}:
                violations.append(
                    Violation(
                        "TOS-FW-D",
                        rel_display,
                        node.lineno,
                        f"forbidden dynamic call '{func.id}'",
                    )
                )
            elif isinstance(func, ast.Attribute) and func.attr == "import_module":
                violations.append(
                    Violation(
                        "TOS-FW-D",
                        rel_display,
                        node.lineno,
                        "forbidden dynamic call 'importlib.import_module'",
                    )
                )

    return violations


def _iter_py_files(root: Path) -> Iterator[Path]:
    for p in sorted(root.rglob("*.py")):
        rel_parts = p.relative_to(root).parts
        if rel_parts and rel_parts[0] == ".venv":
            continue
        yield p


_UNSET = object()


def _run_git(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[bytes]:
    """Run git with byte output so non-UTF-8 filenames survive os.fsdecode."""
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        env=env,
        check=False,
    )


def _git_toplevel_or_none(repo_root: Path) -> Path | None:
    """Resolved toplevel of the git work tree containing ``repo_root``, but"""
    try:
        result = _run_git(["rev-parse", "--show-toplevel"], repo_root)
    except FileNotFoundError:
        return None
    if result.returncode == 0:
        toplevel = Path(os.fsdecode(result.stdout.strip())).resolve()
        return toplevel if toplevel == repo_root.resolve() else None
    stderr = result.stderr.decode("utf-8", errors="replace")
    if "not a git repository" in stderr:
        return None
    raise RuntimeError(
        "tos_firewall_check: `git rev-parse --show-toplevel` failed "
        'unexpectedly (not a plain "not a git repository" case — this '
        f"could be masking a real work tree, exit {result.returncode}): "
        f"{stderr.strip()}"
    )


def _git_ls_files(repo_root: Path, args: list[str]) -> bytes:
    """Run ``git -C repo_root ls-files <args>`` and return raw stdout bytes."""
    result = _run_git(["ls-files", *args], repo_root)
    if result.returncode != 0:
        raise RuntimeError(
            f"tos_firewall_check: `git ls-files {' '.join(args)}` failed "
            f"(exit {result.returncode}): "
            f"{result.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return result.stdout


def _git_tracked_py_under_pruned_roots(
    repo_root: Path, toplevel: Path | None
) -> list[Path]:
    """Every git-tracked ``.py`` beneath a pruned root OTHER than ``tos``."""
    if toplevel is None:
        return []

    pruned_roots_for_union = [r for r in _REVERSE_SCAN_PRUNE_ROOTS if r != "tos"]
    raw = _git_ls_files(repo_root, ["-z", "--", *pruned_roots_for_union])

    return [
        Path(os.path.abspath(repo_root / os.fsdecode(rel)))
        for rel in raw.split(b"\0")
        if rel and rel.endswith(b".py")
    ]


def _walk_repo_py(
    repo_root: Path,
    *,
    symlinks_out: list[Path] | None = None,
    toplevel: Path | None = _UNSET,  # type: ignore[assignment]
) -> Iterator[Path]:
    """Yield every ``.py`` reachable outside the pruned roots."""
    if toplevel is _UNSET:
        toplevel = _git_toplevel_or_none(repo_root)
    pruned_roots_resolved = frozenset(
        (repo_root / rel).resolve() for rel in _REVERSE_SCAN_PRUNE_ROOTS
    )
    walked_lexical: set[Path] = set()
    for dirpath, dirnames, filenames in os.walk(repo_root):
        if symlinks_out is not None:
            for name in (*dirnames, *filenames):
                candidate = Path(dirpath) / name
                if os.path.islink(candidate):
                    symlinks_out.append(Path(os.path.abspath(candidate)))
        dirnames[:] = [
            d
            for d in dirnames
            if (Path(dirpath) / d).resolve() not in pruned_roots_resolved
        ]
        for fn in filenames:
            if fn.endswith(".py"):
                p = Path(dirpath) / fn
                walked_lexical.add(Path(os.path.abspath(p)))
                yield p

    for p in sorted(_git_tracked_py_under_pruned_roots(repo_root, toplevel), key=str):
        if p not in walked_lexical:
            yield p


def _git_tracked_symlinks(repo_root: Path, toplevel: Path | None) -> list[Path]:
    """Every git-tracked symlink (index mode ``120000``) EXCEPT beneath"""
    if toplevel is None:
        return []

    raw = _git_ls_files(repo_root, ["-s", "-z"])
    symlinks: list[Path] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, sep, rel_bytes = record.partition(b"\t")
        if not sep:
            continue
        mode = meta.split(b" ", 1)[0]
        if mode != b"120000":
            continue
        rel = os.fsdecode(rel_bytes)
        if rel.startswith("tos/"):
            continue
        symlinks.append(Path(os.path.abspath(repo_root / rel)))
    return symlinks


def _subtree_contains(root: Path, candidate: Path) -> bool:
    """True if ``candidate`` IS ``root``, or lies within ``root``'s subtree."""
    return candidate == root or root in candidate.parents


def _classify_symlink_crossing(
    link_lexical: Path, tos_dir_lexical: Path
) -> tuple[bool, Path | None]:
    """Does ``link_lexical`` (a symlink) cross the tos/ boundary?"""
    link_inside = _subtree_contains(tos_dir_lexical, link_lexical)
    target_real = Path(os.path.realpath(link_lexical))
    if not target_real.exists():
        return True, None
    target_lexical = Path(os.path.abspath(target_real))

    if link_inside:
        crosses = not _subtree_contains(tos_dir_lexical, target_lexical)
    else:
        crosses = _subtree_contains(
            tos_dir_lexical, target_lexical
        ) or _subtree_contains(target_lexical, tos_dir_lexical)
    return crosses, target_lexical


def _forward_scan_boundary_symlinks(repo_root: Path, tos_dir: Path) -> list[Violation]:
    """Rule S, mirrored for symlinks lexically INSIDE tos/ (the forward"""
    tos_dir_lexical = Path(os.path.abspath(tos_dir))
    violations: list[Violation] = []
    is_top = True
    for dirpath, dirnames, filenames in os.walk(tos_dir):
        for name in (*dirnames, *filenames):
            candidate = Path(dirpath) / name
            if not os.path.islink(candidate):
                continue
            link_lexical = Path(os.path.abspath(candidate))
            crosses, target_lexical = _classify_symlink_crossing(
                link_lexical, tos_dir_lexical
            )
            if not crosses:
                continue
            violations.append(
                _make_symlink_crossing_violation(
                    link_lexical, target_lexical, repo_root
                )
            )
        if is_top:
            dirnames[:] = [d for d in dirnames if d != ".venv"]
            is_top = False
    return violations


def _safe_rel(path: Path, root: Path) -> str:
    """Relative path of ``path`` under ``root`` for display — LEXICAL, not"""
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return str(path)


def _make_symlink_crossing_violation(
    link_lexical: Path, target_lexical: Path | None, repo_root: Path
) -> Violation:
    """Build the one ``TOS-FW-S`` ``Violation`` shape both the reverse loop"""
    rel = _safe_rel(link_lexical, repo_root)
    if target_lexical is None:
        message = "dangling symlink (target unresolvable) — fail-closed"
    else:
        message = f"symlink crosses the tos/ boundary (target: {_safe_rel(target_lexical, repo_root)})"
    return Violation("TOS-FW-S", rel, 0, message)


def check_reverse_imports(
    repo_root: Path,
    tos_dir: Path,
    *,
    toplevel: Path | None = _UNSET,  # type: ignore[assignment]
    tracked_symlinks: list[Path] = _UNSET,  # type: ignore[assignment]
) -> list[Violation]:
    """Detect any file outside ``tos/`` that imports the ``tos`` package"""
    if toplevel is _UNSET:
        toplevel = _git_toplevel_or_none(repo_root)
    if tracked_symlinks is _UNSET:
        tracked_symlinks = _git_tracked_symlinks(repo_root, toplevel)

    violations: list[Violation] = []
    tos_dir_lexical = Path(os.path.abspath(tos_dir))

    walked_symlinks: list[Path] = []

    for path in _walk_repo_py(
        repo_root, symlinks_out=walked_symlinks, toplevel=toplevel
    ):
        path_lexical = Path(os.path.abspath(path))
        if path_lexical == tos_dir_lexical or tos_dir_lexical in path_lexical.parents:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "tos" not in text:
            continue

        rel = _safe_rel(path, repo_root)
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            for i, line in enumerate(text.splitlines(), start=1):
                if _REVERSE_LINE_RE.match(line):
                    violations.append(
                        Violation(
                            "TOS-FW-R",
                            rel,
                            i,
                            "file outside tos/ imports 'tos' (unparseable; line scan)",
                        )
                    )
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _matches_prefix(alias.name, _REVERSE_SCAN_TARGET_NAMES):
                        violations.append(
                            Violation(
                                "TOS-FW-R",
                                rel,
                                node.lineno,
                                f"file outside tos/ imports '{alias.name}'",
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                if (
                    not node.level
                    and node.module
                    and _matches_prefix(node.module, _REVERSE_SCAN_TARGET_NAMES)
                ):
                    violations.append(
                        Violation(
                            "TOS-FW-R",
                            rel,
                            node.lineno,
                            f"file outside tos/ imports 'from {node.module}'",
                        )
                    )

    all_symlinks = {*walked_symlinks, *tracked_symlinks}
    for link_lexical in sorted(all_symlinks, key=str):
        if link_lexical == tos_dir_lexical or tos_dir_lexical in link_lexical.parents:
            continue
        crosses, target_lexical = _classify_symlink_crossing(
            link_lexical, tos_dir_lexical
        )
        if not crosses:
            continue
        violations.append(
            _make_symlink_crossing_violation(link_lexical, target_lexical, repo_root)
        )

    return violations


def _tos_root_is_symlink(
    tos_dir: Path, tracked_symlinks: list[Path]
) -> tuple[bool, Path | None]:
    """Is the repo-root ``tos/`` entry ITSELF a symlink?"""
    if os.path.islink(tos_dir):
        target_real = Path(os.path.realpath(tos_dir))
        if target_real.exists():
            return True, Path(os.path.abspath(target_real))
        return True, None

    tos_dir_lexical = Path(os.path.abspath(tos_dir))
    for tracked in tracked_symlinks:
        if tracked == tos_dir_lexical:
            return True, None
    return False, None


def run_checks(repo_root: Path) -> list[Violation]:
    """Run the full firewall (forward tos/ scan + reverse repo scan)."""
    repo_root = repo_root.resolve()
    tos_dir = repo_root / "tos"
    violations: list[Violation] = []

    toplevel = _git_toplevel_or_none(repo_root)
    tracked_symlinks = _git_tracked_symlinks(repo_root, toplevel)

    is_tos_symlink, tos_symlink_target = _tos_root_is_symlink(tos_dir, tracked_symlinks)
    if is_tos_symlink:
        tgt_display = (
            "<dangling>"
            if tos_symlink_target is None
            else _safe_rel(tos_symlink_target, repo_root)
        )
        violations.append(
            Violation(
                "TOS-FW-S",
                "tos",
                0,
                f"tos/ itself is a symlink (target: {tgt_display}); "
                "tos/ may never be a symlink, regardless of target",
            )
        )
        violations.append(
            Violation(
                "TOS-FW-S",
                "tos",
                0,
                "tos/ is a symlink; forward rules a-d cannot be evaluated",
            )
        )
    elif not tos_dir.is_dir():
        violations.append(
            Violation(
                "TOS-FW-MISSING",
                "tos",
                0,
                "tos/ does not exist or is not a directory; "
                "forward rules a-d cannot be evaluated",
            )
        )
    else:
        for path in _iter_py_files(tos_dir):
            rel = _safe_rel(path, repo_root)
            try:
                violations.extend(check_tos_file(path, rel))
            except SyntaxError as exc:
                violations.append(
                    Violation(
                        "TOS-FW-SYNTAX",
                        rel,
                        exc.lineno or 0,
                        f"could not parse tos file: {exc.msg}",
                    )
                )
        violations.extend(_forward_scan_boundary_symlinks(repo_root, tos_dir))

    violations.extend(
        check_reverse_imports(
            repo_root, tos_dir, toplevel=toplevel, tracked_symlinks=tracked_symlinks
        )
    )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="tos import-firewall gate (design §3.3-①)"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="repo root to scan (default: the parent of tools/)",
    )
    args = parser.parse_args(argv)
    repo_root = (args.repo_root or Path(__file__).resolve().parent.parent).resolve()

    violations = run_checks(repo_root)

    if violations:
        print(f"tos-firewall: FAIL — {len(violations)} violation(s)")
        for v in sorted(violations, key=lambda x: (x.path, x.line, x.rule)):
            print(f"  {v.path}:{v.line}: [{v.rule}] {v.message}")
        print(
            "\nAllowlist SoT: "
            "docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md §3.2"
        )
        print("Changing the allowlist requires a PR editing that doc (§6.1).")
        return 1

    print("tos-firewall: PASS — no import-firewall violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
