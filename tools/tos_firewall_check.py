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
  (f) TOS-FW-S  no SYMLINK (file or directory, walked or git-tracked) may
                cross the tos/ boundary: crossing means SUBTREE
                INTERSECTION, not merely "which side" — a link outside
                tos/ pointing at tos/ itself, a descendant of it, OR an
                ANCESTOR of it (whose subtree therefore reaches tos/ too,
                e.g. ``shared/up -> <repo root>``) all cross; a link inside
                tos/ pointing anywhere outside its own subtree (ancestors
                included) crosses. Dangling targets always cross
                (fail-closed; an unresolvable target is presumed to cross,
                never presumed safe). Closes a bypass neither (e)'s content
                scan nor the git-tracked-``.py`` union can reach: a
                directory symlink is never traversed by ``os.walk``
                regardless of where it points, and git tracks a symlink as
                one index entry, never descending through it either — so
                nothing on the far side of the alias is ever visible to
                either scan. Rather than try to traverse through it, rule S
                forbids the alias itself. The repo-root ``tos/`` entry may
                NEVER be a symlink, checked first and unconditionally in
                ``run_checks`` before rules (a)-(d) even attempt to run —
                a missing or symlinked ``tos/`` is always a visible,
                reported failure, never a silent PASS.

Two further diagnostic IDs are structural, not content rules, and so sit
outside the (a)-(f) enumeration above (parallel to how a build tool reports
"file not found" separately from its lint rules) — named here so neither is
an undocumented orphan string:

  TOS-FW-SYNTAX  a ``tos/`` ``.py`` file failed to AST-parse; a file that
                 does not parse cannot be certified against (a)-(d).
  TOS-FW-MISSING the repo-root ``tos/`` entry does not exist, or exists but
                 is not a directory (and is not a symlink either — that
                 case is TOS-FW-S, above). Rules (a)-(d) and the forward
                 rule-S mirror cannot be evaluated with no ``tos/`` to
                 evaluate them against; ``run_checks`` reports this
                 explicitly rather than silently producing zero violations.

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
import subprocess
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
#
# NB: ``shared.config`` is deliberately ABSENT (removed 2026-07-20, §6.1). Its
# ``__init__`` unconditionally executes ``from shared.config.secrets import ...``,
# so any ``shared.config`` import transitively pulls in ambient credential access
# (``os.environ``), violating C2 (§4 3차 방어). The whole package is therefore off
# the allowlist — no ``shared.config.secrets`` carve-out is needed, because the
# parent is no longer allowed in the first place. Policy loading uses pyyaml per
# design #2 §0.3, not ``shared.config``.
SHARED_ALLOWED: frozenset[str] = frozenset(
    {
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

# Full stdlib top-level module name set (§3.3-① mandates sys.stdlib_module_names).
STDLIB: frozenset[str] = frozenset(sys.stdlib_module_names)

# The reverse scan (rule e / R-reverse, repo files OUTSIDE tos/) prunes ONLY
# an explicit, small set of repo-root-relative roots, matched by
# resolved-path IDENTITY — never by name, and never at any depth. Each root
# below is resolved once (as `repo_root / rel`) before the walk starts.
#
# `_REVERSE_SCAN_PRUNE_ROOTS` = VCS/generated/gitignored roots — `.git`
# (VCS internals), `.venv` (this repo's own dev venv), `.omc` and `.history`
# (tooling scratch dirs) — verified 2026-09-04 to be where this checkout's
# gitignored `.py` files live (`git ls-files --others --ignored --exclude-standard
# | grep '\.py$'`). Plus `tos` at the repo root: the forward scan's territory
# (rules a-d), not a name-based exclusion — a NESTED dir literally named
# `tos` (e.g. `services/tos/`) is NOT this root and IS scanned.
#
# Two earlier versions of this were both rejected by Codex review:
#   1. A fixed name set (`_REVERSE_SCAN_PRUNE = {"tos", ".git", ".venv",
#      "node_modules", "__pycache__", ".omc", ".history"}`) pruned at ANY
#      depth — `tos`, `node_modules`, `__pycache__` are valid identifiers, so
#      e.g. `shared/node_modules/x.py` containing `import tos` would have
#      been silently skipped by rule e yet remained importable.
#   2. An `isidentifier()` predicate (prune any dir whose name is not a
#      valid Python identifier, at any depth) was rejected too: §3.2
#      R-역방향 requires scanning EVERY Python file outside tos/, and a
#      tracked script under a non-identifier-named directory (e.g.
#      `docs/reviews/phase0-completion-contract/probe.py`) still executes by
#      path — a hyphenated/dotted directory name says nothing about
#      importability. `node_modules`/`__pycache__`/hyphenated dirs like
#      `strategy-builder-ui` are therefore NOT pruned; they are ordinary,
#      scanned directories under this design.
#
# Two further explicit roots, added after measuring the live-tree wall time
# (2026-09-04):
#
#   - `open-trading-api/` — a gitignored, root-level clone of KIS's own
#     sample-code repo (`.gitignore:60`; `git ls-files open-trading-api` = 0
#     tracked files). Measured 12,247 `.py` files, by far the dominant cost
#     of this scan (`grep -rl '^import tos\|^from tos' open-trading-api` = 0
#     matches — an independent, unrelated codebase that was never going to
#     trip rule e). This alone was the majority of the ~7.7s live-tree wall
#     time before pruning.
#   - `strategy-builder-ui/node_modules` — npm's vendor tree (gitignored,
#     2995 subdirectories). NOTE this is a deliberate scope tradeoff, not a
#     "zero Python" claim: it in fact contains exactly one `.py` file
#     measured (`flatted/python/flatted.py`, a vendored npm package's
#     optional Python bridge script, unrelated to this repo's own `tos`
#     package and never containing `import tos`). `strategy-builder-ui/`
#     itself is NOT pruned — only its `node_modules/` subtree — so a real
#     script directly under `strategy-builder-ui/` is still scanned.
_REVERSE_SCAN_PRUNE_ROOTS: tuple[str, ...] = (
    ".git",
    ".venv",
    ".omc",
    ".history",
    "tos",
    "open-trading-api",
    "strategy-builder-ui/node_modules",
)

# The forward scan (rules a-d, inside tos/ itself) excludes ONLY the
# uv-generated top-level `tos/.venv/` tree — i.e. `p.relative_to(tos_dir).parts[0]
# == ".venv"`, not any-depth pruning by directory name. `.venv` is not a valid
# Python identifier, so it can never be a package/module path component; a
# top-level-only check is therefore safe with zero bypass risk. An earlier
# version of this fix pruned `node_modules`/`__pycache__`/`.git`/`.venv` at ANY
# depth (mirroring `_REVERSE_SCAN_PRUNE`), but that was rejected on Codex
# review: `node_modules` and `__pycache__` ARE valid identifiers, so a tracked
# `tos/src/tos/node_modules/egress.py` would have been silently skipped by
# rules A-D yet remained importable via `from .node_modules import egress` —
# an exact bypass of the firewall this file exists to enforce. Rationale for
# excluding `.venv` at all: a developer running `cd tos && uv sync` creates a
# gitignored `tos/.venv/`, and without this exclusion the forward scan walks
# into its vendored site-packages and reports thousands of false violations.
#
# `_iter_py_files` deliberately does NOT skip `__pycache__` directories either
# (a second Codex review finding, 2026-09-04): `__pycache__` is likewise a
# valid identifier, so a package literally named that would have been
# silently skipped by rules A-D yet remained importable via
# `from .__pycache__ import egress` — the same bypass class as `node_modules`
# above. No exclusion is needed for the *real* compiled-cache use case: Python
# writes only `.pyc` files under `__pycache__/`, and `root.rglob("*.py")`
# never matches those, so the directory is already inert to this scan without
# any special-casing.

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
        if _matches_prefix(dotted, SHARED_ALLOWED):
            return True, None
        # e.g. shared.config (+ .secrets), shared.execution, bare `shared`
        return False, "TOS-FW-A"
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
                # `from shared import execution` (denied), `from shared.config
                # import ConfigLoader` (parent no longer allowed) and `from urllib
                # import request` (forbidden) are caught, while `from
                # shared.indicators import atr` (attr of an allowed pkg) stays
                # allowed.
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
        rel_parts = p.relative_to(root).parts
        if rel_parts and rel_parts[0] == ".venv":
            continue
        yield p


# ============================================================================
# Reverse scan — repo files OUTSIDE tos/ (rule e / R-reverse)
# ============================================================================

# Sentinel for an "unset" keyword-only parameter, distinct from `None` (which
# is itself a meaningful value here — "no git work tree"). Lets a caller that
# already computed something ONCE (`run_checks`) pass it down explicitly,
# while a caller that has no such value (a test calling a function directly)
# leaves the parameter at its default and gets it computed on demand —
# without conflating "not yet computed" with "computed as None".
_UNSET = object()


def _run_git(args: list[str], repo_root: Path) -> subprocess.CompletedProcess:
    """Run ``git -C repo_root <args>``, bytes in and out (Claude-side review
    batch 2, LOW: ``text=True`` would raise ``UnicodeDecodeError`` on a
    non-UTF-8 filename anywhere in the output; every caller here decodes
    path bytes itself with ``os.fsdecode`` instead, which round-trips even
    surrogate-escaped bytes).

    Forces ``LC_ALL=C`` so git's fatal/error messages come back in English
    and are safe to substring-match, regardless of the invoking user's
    locale — verified 2026-09-04 that this is NOT a hypothetical concern:
    this very checkout's git prints Korean-locale messages by default (e.g.
    "fatal: not a git repository" renders as "깃 저장소가 아닙니다" without
    this), which would have silently broken the not-a-work-tree detection
    in ``_git_toplevel_or_none`` below on this exact machine.
    """
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        env=env,
        check=False,
    )


def _git_toplevel_or_none(repo_root: Path) -> Path | None:
    """Resolved toplevel of the git work tree containing ``repo_root``, but
    ONLY if ``repo_root`` itself IS that toplevel — ``None`` otherwise
    (covers both "no git work tree here at all" and "inside SOME work tree,
    but not its toplevel").

    Called ONCE per ``run_checks`` invocation and threaded through every
    caller that needs it (``_walk_repo_py``, ``_git_tracked_py_under_pruned_roots``,
    ``_git_tracked_symlinks``, ``_tos_root_is_symlink``) — this used to be a
    verbatim-duplicated probe inside each of the latter two (DRY, CLAUDE.md
    non-negotiable), and duplicating it meant up to three separate
    ``rev-parse`` subprocess calls per firewall run for no reason.

    Fail-open (return ``None``, no error) ONLY when genuinely not inside a
    git work tree at all (``git rev-parse --show-toplevel``'s own stderr
    says so) or git is not installed. Fail-CLOSED (raise ``RuntimeError``)
    for ANY OTHER probe failure — most importantly a real work tree that
    git refuses to probe for "dubious ownership" reasons (CVE-2022-24765;
    a live scenario for a CI checkout owned by a different uid than the
    one running this tool). Claude-side review, batch 2: the earlier code
    treated every non-zero exit as "not a work tree", which would silently
    have dropped the tracked-``.py`` union AND the tracked-symlink source —
    exactly the class of bypass this whole rule-R/rule-S effort exists to
    close — with no error, no warning, nothing.
    """
    try:
        result = _run_git(["rev-parse", "--show-toplevel"], repo_root)
    except FileNotFoundError:
        return None  # git itself is not installed
    if result.returncode == 0:
        toplevel = Path(os.fsdecode(result.stdout.strip())).resolve()
        return toplevel if toplevel == repo_root.resolve() else None
    stderr = result.stderr.decode("utf-8", errors="replace")
    if "not a git repository" in stderr:
        return None  # genuinely no git work tree here
    raise RuntimeError(
        "tos_firewall_check: `git rev-parse --show-toplevel` failed "
        "unexpectedly (not a plain \"not a git repository\" case — this "
        f"could be masking a real work tree, exit {result.returncode}): "
        f"{stderr.strip()}"
    )


def _git_ls_files(repo_root: Path, args: list[str]) -> bytes:
    """Run ``git -C repo_root ls-files <args>`` and return raw stdout bytes.

    By the time this is called, the caller has already established (via
    ``_git_toplevel_or_none``) that ``repo_root`` genuinely IS a git work
    tree's toplevel — so a non-zero exit here is never "not a repo" and
    must never be silently swallowed; it always raises ``RuntimeError``.
    """
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
    """Every git-tracked ``.py`` beneath a pruned root OTHER than ``tos``.

    Closes a bypass (Codex re-review #7, 2026-09-04): ``git add -f`` can
    force-track a file under a normally-pruned root (e.g.
    ``open-trading-api/x.py``, ``.venv/x.py``) even though that root is
    gitignored. CI checks out and runs that file, but ``_walk_repo_py``'s
    filesystem-walk-only scan would never see it — the walk prunes the
    directory before descending, so the AST never gets a chance to catch an
    `import tos`. The fix is the UNION of the pruned walk with this: every
    git-tracked ``.py`` under a pruned root. ``tos`` itself is excluded from
    the query (the forward scan's territory, not rule e's).

    ``toplevel`` must be the result of ONE prior ``_git_toplevel_or_none(repo_root)``
    call (that function owns all the git-availability / fail-open-vs-fail-closed
    semantics — this function trusts its answer and does not re-probe).
    ``None`` means "not a usable git work tree here" — return ``[]``.
    """
    if toplevel is None:
        return []

    pruned_roots_for_union = [r for r in _REVERSE_SCAN_PRUNE_ROOTS if r != "tos"]
    raw = _git_ls_files(repo_root, ["-z", "--", *pruned_roots_for_union])

    # Lexical (not resolved): a force-tracked symlink under a pruned root
    # must be identified by its OWN path, never by the path its target
    # happens to resolve to (Codex re-review #8 — see `check_reverse_imports`
    # and the module-level comment on lexical boundary classification).
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
):
    """Yield every ``.py`` reachable outside the pruned roots.

    ``symlinks_out``, if given, is a side-channel: every ``dirnames``/
    ``filenames`` entry the walk visits that is itself a symlink (file OR
    directory, ANY extension) is appended to it as a lexical absolute path,
    recorded BEFORE that entry is pruned — so a directory symlink that would
    otherwise be stripped from ``dirnames`` (because its RESOLVED target
    happens to equal a pruned root's identity) is still recorded first. This
    feeds rule S (TOS-FW-S, see the module docstring); ``symlinks_out`` is
    fully populated only once this generator has been drained to completion.

    ``toplevel``: pass the result of a prior ``_git_toplevel_or_none(repo_root)``
    call to avoid re-probing (DRY — see that function's docstring); left at
    its default, this computes it itself (one ``rev-parse``), so a direct
    standalone call (as this module's own tests make) still works.
    """
    if toplevel is _UNSET:
        toplevel = _git_toplevel_or_none(repo_root)
    # Resolve each explicit prune root once, before the walk starts (see the
    # module-level comment above `_REVERSE_SCAN_PRUNE_ROOTS`).
    pruned_roots_resolved = frozenset(
        (repo_root / rel).resolve() for rel in _REVERSE_SCAN_PRUNE_ROOTS
    )
    # Lexical (abspath, not resolved) dedup keys — must match the lexical
    # paths `_git_tracked_py_under_pruned_roots` returns, so the union
    # de-duplicates like-for-like rather than comparing a walked path's
    # lexical location against a tracked path's resolved target (or vice
    # versa), which could silently under- or over-count.
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

    # UNION: close the "git add -f under a pruned root" bypass — see
    # `_git_tracked_py_under_pruned_roots`'s docstring. Sorted for
    # determinism; de-duplicated against the walk (paths already yielded
    # above can never come from inside a pruned dir, so no real overlap is
    # expected, but the guard is cheap and correctness should not depend on
    # that never happening).
    for p in sorted(_git_tracked_py_under_pruned_roots(repo_root, toplevel), key=str):
        if p not in walked_lexical:
            yield p


def _git_tracked_symlinks(repo_root: Path, toplevel: Path | None) -> list[Path]:
    """Every git-tracked symlink (index mode ``120000``) EXCEPT beneath
    (strictly under) the repo-root ``tos/`` (the forward-scan mirror owns
    tos-INTERNAL symlinks — see ``_forward_scan_boundary_symlinks``). A
    tracked symlink AT ``tos`` itself IS returned — narrowed from
    ``rel == "tos" or rel.startswith("tos/")`` to `rel.startswith("tos/")``
    only (Claude-side review, 2026-09-04): the repo-root `tos` path is not
    "inside tos/", it IS the boundary marker, and ``_tos_root_is_symlink``
    (called from ``run_checks``) needs this function's output to detect a
    tracked-but-not-yet-materialized symlink there. Lexical paths, not
    resolved.

    Closes the directory-symlink half of the same bypass class as
    ``_git_tracked_py_under_pruned_roots`` (Codex re-review #9):
    ``os.walk(followlinks=False)`` never descends into ANY directory
    symlink, regardless of where it points or whether its parent is a
    pruned root — so a directory alias force-tracked under a pruned root
    (e.g. ``open-trading-api/link -> tos/src/tos``) is invisible to
    ``_walk_repo_py``'s side-channel too (the walk never reaches
    ``open-trading-api/`` at all once it is pruned). ``git ls-files -s``
    finds the symlink OBJECT directly from the index, with no directory
    traversal at all.

    ``toplevel`` must be the result of ONE prior ``_git_toplevel_or_none(repo_root)``
    call — see that function's docstring (this function does not re-probe).
    ``None`` means "not a usable git work tree here" — return ``[]``.
    """
    if toplevel is None:
        return []

    raw = _git_ls_files(repo_root, ["-s", "-z"])
    symlinks: list[Path] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        # `-s` record format: "<mode> <object-sha> <stage>\t<path>"
        meta, sep, rel_bytes = record.partition(b"\t")
        if not sep:
            continue
        mode = meta.split(b" ", 1)[0]
        if mode != b"120000":
            continue
        rel = os.fsdecode(rel_bytes)
        if rel.startswith("tos/"):
            continue  # forward-scan mirror's territory (tos-INTERNAL only)
        symlinks.append(Path(os.path.abspath(repo_root / rel)))
    return symlinks


def _subtree_contains(root: Path, candidate: Path) -> bool:
    """True if ``candidate`` IS ``root``, or lies within ``root``'s subtree.

    Comparison is EXACT-CASE (``PurePath.__eq__`` on POSIX never folds
    case). On a case-INSENSITIVE filesystem (the default on macOS dev
    machines) two differently-cased paths can name the same physical file
    while comparing unequal here — a gap noted, not closed: enforcement is
    Linux CI, where the filesystem is case-sensitive and this is exact by
    construction (LOW, Claude-side review batch 2).
    """
    return candidate == root or root in candidate.parents


def _classify_symlink_crossing(
    link_lexical: Path, tos_dir_lexical: Path
) -> tuple[bool, Path | None]:
    """Does ``link_lexical`` (a symlink) cross the tos/ boundary?

    Crossing is SUBTREE INTERSECTION, not "which side is the target on"
    (Claude-side review, 2026-09-04 — the earlier "which side" check missed
    a link OUTSIDE tos/ pointing at an ANCESTOR of tos/, e.g.
    ``shared/up -> <repo root>``: the repo root is "outside" tos/ too, so
    the old same-side/different-side comparison judged it clean, even
    though the ancestor's subtree obviously *contains* tos/ —
    ``shared.up.tos.src.tos`` reaches the kernel through it, invisible to
    rule R's own walk since a directory symlink is never traversed):

      - Link lexically OUTSIDE tos/: crossing iff the target's subtree and
        tos_dir's subtree overlap AT ALL — target IS tos_dir, target is a
        DESCENDANT of tos_dir, OR target is an ANCESTOR of tos_dir (its
        subtree therefore reaches tos_dir too).
      - Link lexically INSIDE tos/: crossing iff the target's subtree is
        NOT entirely contained within tos_dir's subtree — anything outside,
        ancestors of tos_dir included. (An ancestor that is still WITHIN
        tos_dir's own subtree, e.g. a deep link pointing back up at
        ``tos/src``, stays clean — its subtree is still wholly inside.)

    Returns ``(crosses, target_lexical)``. A dangling or otherwise
    unresolvable target is ALWAYS treated as crossing regardless of the
    link's side (fail-closed — an unknown target could later resolve to
    either side, so it is never presumed safe); ``target_lexical`` is
    ``None`` in that case.
    """
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
    """Rule S, mirrored for symlinks lexically INSIDE tos/ (the forward
    scan's side of the boundary): a directory or file alias under tos/
    pointing OUTSIDE it looks tos-governed (importable as ``tos.*``,
    forward-scanned by rules a-d) but is physically living — and mutable —
    somewhere else entirely. Walks ``tos_dir`` directly with
    ``os.walk(followlinks=False)`` (never descends into a directory
    symlink), mirroring ``_iter_py_files``'s top-level `.venv/` exclusion so
    this stays as cheap as the forward `.py` scan. Known residue (Claude-side
    review pass 2, SUGGESTION): the `.venv` entry itself is classified, but a
    symlink one level deeper (``tos/.venv/leak -> ../../shared/real``) is not
    reached because the tree is pruned after recording; bounded, since nothing
    under ``tos/.venv`` is importable as ``tos.*``.

    RECORDS symlinks in ``dirnames``/``filenames`` BEFORE pruning `.venv`
    out of ``dirnames`` — same discipline as ``_walk_repo_py``'s
    ``symlinks_out`` side-channel. An earlier version pruned `.venv` FIRST
    (Claude-side review batch 2, MEDIUM): a force-tracked (or merely
    present) `tos/.venv` symlink to somewhere outside tos/ was stripped out
    of ``dirnames`` before the islink check ever ran, so nothing ever
    reported it.
    """
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
                _make_symlink_crossing_violation(link_lexical, target_lexical, repo_root)
            )
        if is_top:
            dirnames[:] = [d for d in dirnames if d != ".venv"]
            is_top = False
    return violations


def _safe_rel(path: Path, root: Path) -> str:
    """Relative path of ``path`` under ``root`` for display — LEXICAL, not
    resolved (``os.path.relpath`` normalises to absolute but never follows
    symlinks). A violation must name the file that actually contains it: if
    ``path`` is a symlink, resolving it here would substitute its TARGET's
    path in the report, misattributing the violation to a different file
    (Codex re-review #8 — the same lexical-vs-resolved bug class as the
    boundary classification in ``check_reverse_imports`` below).
    """
    try:
        return os.path.relpath(path, root)
    except ValueError:
        # Windows: `path` and `root` on different drives — no relative path
        # is expressible at all; fall back to the absolute string.
        return str(path)


def _make_symlink_crossing_violation(
    link_lexical: Path, target_lexical: Path | None, repo_root: Path
) -> Violation:
    """Build the one ``TOS-FW-S`` ``Violation`` shape both the reverse loop
    (``check_reverse_imports``) and the forward mirror
    (``_forward_scan_boundary_symlinks``) need — DRY (they used to build
    this inline, verbatim, in both places).

    Message wording: a dangling target (``target_lexical is None``) gets
    its own wording, "dangling symlink (target unresolvable) — fail-closed",
    rather than reusing the generic "crosses the tos/ boundary" phrasing —
    a dangling link hasn't been PROVEN to cross anything; it is flagged
    because its status is unknown, and that distinction is worth keeping
    visible in the message itself (LOW, Claude-side review batch 2).
    """
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
    """Detect any file outside ``tos/`` that imports the ``tos`` package
    (rule R), plus (rule S) any symlink lexically OUTSIDE tos/ whose
    resolved target crosses to the other side of the boundary.

    ``toplevel``/``tracked_symlinks``: pass ``run_checks``'s already-computed
    values to avoid re-probing git (DRY — see ``_git_toplevel_or_none``'s
    docstring); left at their defaults, both are computed here (a direct
    standalone call, as this module's own tests make throughout, still
    works with exactly one ``rev-parse`` and two ``ls-files`` calls).
    """
    if toplevel is _UNSET:
        toplevel = _git_toplevel_or_none(repo_root)
    if tracked_symlinks is _UNSET:
        tracked_symlinks = _git_tracked_symlinks(repo_root, toplevel)

    violations: list[Violation] = []
    # LEXICAL boundary, not resolved: a file's tos/-membership is decided by
    # where it lexically SITS in the tree, never by what a symlink resolves
    # to. `.resolve()` here would misclassify a symlink OUTSIDE tos/ whose
    # target happens to live inside tos/ as tos-internal, silently exempting
    # it from rule e even though it is importable exactly where it sits
    # (Codex re-review #8). `os.path.abspath` normalises without following
    # symlinks.
    tos_dir_lexical = Path(os.path.abspath(tos_dir))

    # ---- rule S sources, gathered alongside rule R's walk ----
    # (1) every symlink `_walk_repo_py` sees during its walk (recorded before
    # any pruning — see that function's docstring); (2) every git-tracked
    # symlink outside tos/, including ones under a pruned root that source
    # (1) can never reach (see `_git_tracked_symlinks`'s docstring).
    walked_symlinks: list[Path] = []

    for path in _walk_repo_py(repo_root, symlinks_out=walked_symlinks, toplevel=toplevel):
        path_lexical = Path(os.path.abspath(path))
        if path_lexical == tos_dir_lexical or tos_dir_lexical in path_lexical.parents:
            continue  # inside tos/ (lexically) — governed by the forward rules
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

    # ---- rule S: boundary-crossing symlinks lexically OUTSIDE tos/ ----
    # (symlinks lexically INSIDE tos/, strictly under it, are
    # `_forward_scan_boundary_symlinks`'s job — `walked_symlinks` and
    # `_git_tracked_symlinks` already exclude those by construction, but the
    # `in .parents` half of the guard below is kept as an explicit invariant
    # check, not dead code removed for looking redundant. `tos` ITSELF is
    # neither this loop's job NOR the forward mirror's — see
    # `_tos_root_is_symlink`, called unconditionally from `run_checks`
    # before anything else; the `== tos_dir_lexical` half of the guard below
    # exists only to keep this generic per-symlink loop from double-counting
    # that dedicated, more specific check).
    all_symlinks = {*walked_symlinks, *tracked_symlinks}
    for link_lexical in sorted(all_symlinks, key=str):
        if link_lexical == tos_dir_lexical or tos_dir_lexical in link_lexical.parents:
            continue  # tos/ itself, or strictly inside it
        crosses, target_lexical = _classify_symlink_crossing(
            link_lexical, tos_dir_lexical
        )
        if not crosses:
            continue
        violations.append(
            _make_symlink_crossing_violation(link_lexical, target_lexical, repo_root)
        )

    return violations


# ============================================================================
# Orchestration
# ============================================================================


def _tos_root_is_symlink(
    tos_dir: Path, tracked_symlinks: list[Path]
) -> tuple[bool, Path | None]:
    """Is the repo-root ``tos/`` entry ITSELF a symlink?

    ``tos/`` must NEVER be a symlink — it IS the boundary marker every other
    check in this file is anchored to; there is no target that keeps it "on
    the same side", because the symlink's mere existence means the kernel's
    real content lives somewhere physically else. Checked FIRST, from
    ``run_checks``, before anything else runs (Claude-side review,
    2026-09-04): neither the reverse rule-S loop (which explicitly skips
    anything lexically equal to ``tos_dir``) nor the forward mirror (which
    walks INSIDE ``tos_dir`` as its OWN root, so it structurally can never
    inspect ``tos_dir`` itself) can ever catch this — and the old
    ``run_checks`` gated the ENTIRE forward scan (rules a-d AND the forward
    rule-S mirror) on ``tos_dir.is_dir()``, so a dangling symlink at ``tos``
    made every one of those checks silently vanish, reporting a clean PASS
    despite the kernel being structurally unverifiable.

    Two independent sources, fail-closed if EITHER says yes:
      1. The filesystem (``os.path.islink`` directly on ``tos_dir``).
      2. The git index — ``tracked_symlinks`` (mode ``120000``, from ONE
         prior ``_git_tracked_symlinks`` call, reused rather than re-probed
         here — DRY, see ``_git_toplevel_or_none``'s docstring): the working
         tree might not currently reflect what the index claims (e.g.
         before a checkout materializes it), and the index is what CI
         actually checks out, so it is checked too even when (1) says no.

    Returns ``(is_symlink, target_lexical)`` — ``target_lexical`` is
    ``None`` when dangling, or when the answer came only from source (2)
    and there is nothing on the filesystem yet to resolve.
    """
    if os.path.islink(tos_dir):
        target_real = Path(os.path.realpath(tos_dir))
        if target_real.exists():
            return True, Path(os.path.abspath(target_real))
        return True, None

    tos_dir_lexical = Path(os.path.abspath(tos_dir))
    for tracked in tracked_symlinks:
        if tracked == tos_dir_lexical:
            # Index says symlink; filesystem disagrees (or has nothing at
            # all there) — still fail-closed, since CI trusts the index.
            return True, None
    return False, None


def run_checks(repo_root: Path) -> list[Violation]:
    """Run the full firewall (forward tos/ scan + reverse repo scan).

    ``tos/`` itself is checked FIRST, unconditionally: a symlink there, or a
    missing/non-directory entry there, is ALWAYS a visible, reported
    failure — never a silent PASS (see ``_tos_root_is_symlink``).

    Git is probed exactly ONCE here (``_git_toplevel_or_none``) and the
    tracked-symlink query exactly ONCE (``_git_tracked_symlinks``); both
    results are threaded down to every function that needs them
    (``_tos_root_is_symlink``, ``check_reverse_imports`` and, through it,
    ``_walk_repo_py``) instead of each re-probing independently (DRY,
    CLAUDE.md non-negotiable — this used to be up to three separate
    ``rev-parse`` calls and two duplicate ``ls-files -s`` calls per run).
    """
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
            except SyntaxError as exc:  # a tos file that will not parse fails hard
                violations.append(
                    Violation(
                        "TOS-FW-SYNTAX",
                        rel,
                        exc.lineno or 0,
                        f"could not parse tos file: {exc.msg}",
                    )
                )
        # rule S, forward side: symlinks lexically INSIDE tos/ crossing OUT.
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
