#!/usr/bin/env python3
"""tos import-firewall gate (design §3.3-①) — default-deny AST enforcement.

This is the *first* of the three enforcement layers defined in
``docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md`` §3.3::

  ① this custom AST gate      default-deny allowlist (§3.2) — the layer that
                              import-linter's denylist-only contracts cannot
                              express.
  ② .importlinter             transitive defense for the internal forbidden
                              packages (§3.3-②).
  ③ CI job ``tos-firewall``   runs ①+② + ``pytest tos/tests`` on every PR.

It parses every ``.py`` under ``tos/`` (src AND tests — §2.4, because a test
that imports a forbidden module breaks the hermetic claim) and enforces:

  (a) TOS-FW-A  every import (top-level OR nested in a function/try/class) must
                be on the §3.2 allowlist; otherwise it is a violation.
  (b) TOS-FW-B  forbidden stdlib egress / process / FFI primitives (§3.2).
  (c) TOS-FW-C  ``os.environ`` / ``os.getenv`` usage is forbidden (C2 — the §4
                "flag ban": capability must not be reachable via ambient env).
  (d) TOS-FW-D  dynamic import / exec / eval — closes the static-analysis
                escape hatch that would let (a)/(b) be bypassed at runtime.
  (e) TOS-FW-R  no file OUTSIDE ``tos/`` may ``import tos`` (R-reverse — §3.2):
                the operational system must never depend on the unverified
                kernel.

Exit code is 1 with ``path:line [RULE-ID] message`` diagnostics on any
violation, 0 otherwise.

------------------------------------------------------------------------------
ALLOWLIST CONTRACT (SoT = design doc §3.2)
------------------------------------------------------------------------------
The allowlist / forbidden constants below are a *ratified contract*. Their
Source of Truth is the design document §3.2. They may be changed ONLY by a PR
that edits that document and records a §6.1 revision-log line (governance
§6.1). Do not edit them here in isolation — this file merely mechanizes the
contract, it does not own it.

This gate itself lives under ``tools/`` (outside ``tos/``) and is therefore NOT
governed by the firewall; it may use ``os``/``argparse``/etc. freely.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from collections import namedtuple
from pathlib import Path

# ============================================================================
# §3.2 allowlist (ratified contract; SoT = design doc §3.2)
# ============================================================================

# Third-party distributions whose top-level *import name* is allowed. Versions
# are pinned in ``tos/pyproject.toml`` (§3.2 / §5.1). NB: pyyaml is imported as
# ``yaml``, so the import name — not the distribution name — is listed.
THIRD_PARTY_ALLOWED: frozenset[str] = frozenset(
    {"pydantic", "numpy", "pandas", "pytest", "hypothesis", "yaml"}
)

# stdlib modules forbidden for *direct* import: egress / process / FFI
# primitives (C2 §4; DSL escape-closure spirit). Matched as an exact name OR a
# dotted prefix, so "http" also bans "http.client", while "urllib.request" bans
# only that submodule and leaves plain "urllib"/"urllib.parse" allowed.
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

# Commons subpackages tos may import (§3.2). A package-level allow is only valid
# under the import-linter transitive check (§3.3-②), which proves the package's
# closure does not reach a §2.3 forbidden package.
SHARED_ALLOWED: frozenset[str] = frozenset(
    {
        "shared.config",
        "shared.models",
        "shared.indicators",
        "shared.resilience",
        "shared.utils",
        "shared.exceptions",
        # §3.4 dual-use extraction (created in parallel work); allowed per §3.2
        # "커먼즈(신설 후)" row.
        "shared.determinism",
    }
)

# Commons carve-outs denied even though their parent package is allowed: ambient
# credential access conflicts with C2 (§3.2 — ``shared.config.secrets`` excluded).
SHARED_DENIED: frozenset[str] = frozenset({"shared.config.secrets"})

# Full stdlib top-level module name set (§3.3-① mandates sys.stdlib_module_names).
STDLIB: frozenset[str] = frozenset(sys.stdlib_module_names)

# Directory names pruned from the repo-wide reverse scan (rule e). Matches the
# design task's exclusion set exactly.
_REVERSE_SCAN_PRUNE: frozenset[str] = frozenset(
    {"tos", ".git", ".venv", "node_modules", "__pycache__", ".omc", ".history"}
)

# Line-level fallback used only when a repo file outside tos/ fails to AST-parse
# (a SyntaxError must not let an `import tos` slip through silently).
_REVERSE_LINE_RE = re.compile(r"^\s*(?:import|from)\s+tos(?:\.|\s|$)")

# ============================================================================
# Model
# ============================================================================

Violation = namedtuple("Violation", ["rule", "path", "line", "message"])


def _matches_prefix(dotted: str, names: frozenset[str]) -> bool:
    """True if ``dotted`` equals, or is a dotted-child of, any name in ``names``."""
    return any(dotted == n or dotted.startswith(n + ".") for n in names)


def classify_module(dotted: str) -> tuple[bool, str | None]:
    """Classify an absolute dotted module path against the §3.2 allowlist.

    Returns ``(allowed, rule_id)`` where ``rule_id`` is the violated rule ID
    when ``allowed`` is False, else None.
    """
    if not dotted:
        return True, None
    # (b) forbidden stdlib is checked first so `socket`, `http.client`,
    # `urllib.request` etc. report as B rather than a generic A.
    if _matches_prefix(dotted, FORBIDDEN_STDLIB):
        return False, "TOS-FW-B"
    top = dotted.split(".")[0]
    if top == "tos":  # self
        return True, None
    if top == "shared":
        # Denied carve-outs (e.g. shared.config.secrets) win over the allow.
        if _matches_prefix(dotted, SHARED_DENIED):
            return False, "TOS-FW-A"
        if _matches_prefix(dotted, SHARED_ALLOWED):
            return True, None
        return False, "TOS-FW-A"  # e.g. shared.execution, bare `shared`
    if top in THIRD_PARTY_ALLOWED:
        return True, None
    if top in STDLIB:
        return True, None
    return False, "TOS-FW-A"


# ============================================================================
# Forward scan — tos/ files (rules a, b, c, d)
# ============================================================================


def check_tos_file(path: Path, rel_display: str) -> list[Violation]:
    """AST-scan a single ``tos/`` .py file for rules (a)-(d).

    Raises ``SyntaxError`` if the file cannot be parsed (surfaced by callers as
    a hard failure — a tos file that does not parse cannot be certified).
    """
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    violations: list[Violation] = []

    for node in ast.walk(tree):
        # ---- (a)/(b) imports (top-level AND nested — ast.walk visits all) ----
        if isinstance(node, ast.Import):
            for alias in node.names:
                allowed, rule = classify_module(alias.name)
                if not allowed:
                    violations.append(
                        Violation(
                            rule,
                            rel_display,
                            node.lineno,
                            f"disallowed import '{alias.name}'",
                        )
                    )
        elif isinstance(node, ast.ImportFrom):
            if not (node.level and node.level > 0):
                # Absolute `from X import a, b`: classify each X.a candidate so
                # `from shared import execution` (denied) and `from urllib import
                # request` (forbidden) are caught, while `from shared.config
                # import ConfigLoader` (attr of an allowed pkg) stays allowed.
                module = node.module or ""
                for alias in node.names:
                    cand = f"{module}.{alias.name}" if module else alias.name
                    allowed, rule = classify_module(cand)
                    if not allowed:
                        violations.append(
                            Violation(
                                rule,
                                rel_display,
                                node.lineno,
                                f"disallowed import '{cand}'",
                            )
                        )
            # else: relative import (`from . import x`) resolves within tos → self.

            # ---- (c) `from os import environ/getenv` ----
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
            # ---- (d) `from importlib import import_module` ----
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
        # ---- (c) attribute access os.environ / os.getenv ----
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
        # ---- (d) dynamic import / exec / eval calls ----
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


def _iter_py_files(root: Path):
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        yield p


# ============================================================================
# Reverse scan — repo files OUTSIDE tos/ (rule e / R-reverse)
# ============================================================================


def _walk_repo_py(repo_root: Path):
    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Prune noise / vendored / vcs dirs (and any nested dir literally named
        # `tos`, whose forward rules are enforced separately).
        dirnames[:] = [d for d in dirnames if d not in _REVERSE_SCAN_PRUNE]
        for fn in filenames:
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def _safe_rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def check_reverse_imports(repo_root: Path, tos_dir: Path) -> list[Violation]:
    """Detect any file outside ``tos/`` that imports the ``tos`` package."""
    violations: list[Violation] = []
    tos_dir_resolved = tos_dir.resolve()

    for path in _walk_repo_py(repo_root):
        rp = path.resolve()
        if rp == tos_dir_resolved or tos_dir_resolved in rp.parents:
            continue  # inside tos/ — governed by the forward rules
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "tos" not in text:
            continue  # cheap prefilter: cannot import `tos` without the substring

        rel = _safe_rel(path, repo_root)
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            # A non-parseable file must not hide an import — line-scan fallback.
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
                    if alias.name == "tos" or alias.name.startswith("tos."):
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
                    and (node.module == "tos" or node.module.startswith("tos."))
                ):
                    violations.append(
                        Violation(
                            "TOS-FW-R",
                            rel,
                            node.lineno,
                            f"file outside tos/ imports 'from {node.module}'",
                        )
                    )

    return violations


# ============================================================================
# Orchestration
# ============================================================================


def run_checks(repo_root: Path) -> list[Violation]:
    """Run the full firewall (forward tos/ scan + reverse repo scan)."""
    repo_root = repo_root.resolve()
    tos_dir = repo_root / "tos"
    violations: list[Violation] = []

    if tos_dir.is_dir():
        for path in _iter_py_files(tos_dir):
            rel = _safe_rel(path, repo_root)
            try:
                violations.extend(check_tos_file(path, rel))
            except SyntaxError as exc:  # a tos file that will not parse fails hard
                violations.append(
                    Violation(
                        "TOS-FW-SYNTAX",
                        rel,
                        exc.lineno or 0,
                        f"could not parse tos file: {exc.msg}",
                    )
                )

    violations.extend(check_reverse_imports(repo_root, tos_dir))
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
