#!/usr/bin/env python3
"""tos_runtime named-TBD placeholder guard checker (W-A A-0 round 2).

**Why this exists.** A-0's first round closed the named-TBD bypass class ("an operator
types the literal string ``"TBD"`` into a free-string config field, and it gets sealed
into a canonical digest as though it were a real value") in the 9 loader files a
hand-maintained file list named. Kernel round #4's re-review found the list itself was
stale — ``tos_runtime.safety.profile``, both ``tos_runtime.transport.kis_*.config``
modules, and ``tos_runtime.safety.rearm`` were missing from it and had NO guard at all.
This is the exact "레지스트리 + 고정 안 된 위성" failure shape this repo has hit before
(project memory ``registry-with-unpinned-satellite``): a hand list drifts from the real
population the moment a new loader is added.

**The fix: stop listing loaders, detect them.** This script scans
``tos/runtime/src/tos_runtime/**/*.py`` for the STRUCTURAL IDIOM every named-TBD-
relevant loader in this codebase actually uses to read a raw mapping — ``yaml.safe_load``/
``yaml.safe_load_all``/``yaml.load``/``tomllib.load``/``tomllib.loads``/the shared
``load_yaml_document`` helper, or an import of the shared venue-policy YAML primitives
(``tos_runtime.venue._policy_primitives``) — and checks whether that same file
references ANY of the known guard idioms this codebase's own named-TBD loaders use
(:mod:`tos_runtime._named_tbd`'s ``reject_named_tbd``/``is_named_tbd_placeholder``/
``first_named_tbd_leaf``, a local ``TBD_STR``/``_TBD_STR``/``TBD_DIGEST``/
``NAMED_TBD_PLACEHOLDER`` constant, or one of the pre-existing TBD-checking helpers
``require_filled_str``/``optional_str``/``require_str_field``/``_tbd_to_none``). A
candidate file with none of these is a violation — ``--check`` exits 1 — UNLESS it is
registered in ``config/tos_named_tbd_guard.yaml`` with a reason a human can verify
(mirrors ``tools/tos_size_budget.py``'s own "registration is visibility, not a licence"
discipline).

**A NEW loader added without a guard is caught automatically** — nothing needs to be
added to a list first. This is the direct answer to the re-review's demand: "새 로더가
가드 없이 추가되면 CI 가 잡는다".

**What this scan is, precisely — an idiom scan, not a semantic one (round 3 re-review
MEDIUM).** ``json.load``/``json.loads`` are deliberately EXCLUDED from the candidate
signature: a survey of every ``json.load(s)`` call site in ``tos_runtime`` (21 files)
found each one reads back an EVIDENCE STORE ROW or JOURNAL LINE this runtime itself
already durably wrote (``evidence/store.py``, ``marketfeed/journal.py``,
``compose/_operations_wiring.py``, and 18 more) — internal, machine-written data, never
an operator-authored config template an operator could type ``"TBD"`` into. Including
them would add ~21 candidates needing an exemption entry each, for zero real coverage
gain (measured, round 3). ``tomllib.load``/``tomllib.loads`` ARE included even though
NO file in ``tos_runtime`` uses them today (measured: zero hits) — a legitimate future
config format with the identical named-TBD risk, included at zero present cost.

**A real, permanent limitation of substring/idiom detection (documented, not solved
here): a function that receives an ALREADY-PARSED mapping as a plain argument — never
calling ``yaml.load``/``json.load``/etc. itself — is invisible to this scan.** Closing
that would need call-graph analysis (genuine AST-territory, a materially bigger tool
than this one). This scan's job is narrower and still load-bearing: catch the shape
every named-TBD loader in this codebase actually has TODAY, mechanically, so a new
loader written the same way nobody has to remember to add to a list.

**Why a widened string scan, not folding into ``tools/tos_firewall_check.py``'s
existing AST gate (round 3 re-review question).** That checker's AST walk answers one
question — "does this import cross the kernel/runtroshell boundary" — over import
statements only; a config-loader candidate is a CALL-EXPRESSION signature
(``yaml.safe_load(...)``), a different AST shape needing its own visitor, its own
config schema, and its own self-test additions layered onto an already-dense, already-
reviewed file. That is a new capability bolted onto an existing tool, not "reusing what
is already there" — the size-budget checker (registry + drift detection, no AST at all)
is the closer precedent, and this tool already follows it. Widening the string
signature (below) closes the concrete bypass the re-review demonstrated
(``yaml.load(text, Loader=yaml.SafeLoader)``) at near-zero cost and no new tool.

Failure classes enforced by ``--check`` (never silently pass):

    (a) an unregistered candidate file has no guard-idiom reference
    (b) a registered exemption's ``path`` does not exist under the scanned tree (stale)
    (c) a registered exemption's file is no longer a candidate at all (stale — the YAML
        consumption that made it a candidate was removed; the registration is now a dead
        entry that hides nothing)
    (d) a registered exemption's file NOW references a guard idiom (stale — someone
        added a guard without removing the registration, so the registry no longer
        reflects why the file is exempt)
    (e) the registry file itself is missing, unreadable, not valid YAML, or fails
        top-level schema validation

(a)-(d) are collected and each printed as one violation line; ``--check`` exits 1 if
that list is non-empty. (e) is a distinct hard failure, mirroring
``tools/tos_size_budget.py``'s own "a checker that never fails is dead" discipline.

This is a small stdlib(+PyYAML)-only text-scan tool — no AST needed for the reasons
above — and a false negative here (a file that references one of these tokens in a
comment, without really using it) is exactly the same conservative-pass shape
``tools/tos_size_budget.py`` already accepts for its own line-count heuristic: this
tool's job is to make "nobody looked at this file" impossible, not to replace the
review that decides each file's actual exemption reason.

**The checker's own candidate-detection signature is itself covered against silent
weakening (round 3 re-review MEDIUM — "the checker itself was not checked"): the real-
tree smoke test pins a candidate-count FLOOR, not just "0 violations" — removing a
signal from ``_CANDIDATE_SIGNALS`` silently shrinks the candidate set while staying
"clean" otherwise (proven: removing ``"load_yaml_document("`` drops 46 candidates to 42
with zero violations), so a bare ``violations == []`` assertion cannot catch that
regression. The floor makes it visible.**
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path("config/tos_named_tbd_guard.yaml")
DEFAULT_SCOPE = Path("tos/runtime/src/tos_runtime")

#: A file is a "candidate" — a config loader that reads a raw value out of YAML/TOML — if
#: it contains any of these substrings (module docstring's "what this scan is,
#: precisely" section explains what is deliberately excluded, and why).
_CANDIDATE_SIGNALS: tuple[str, ...] = (
    "yaml.safe_load(",
    "yaml.safe_load_all(",
    "yaml.load(",
    "tomllib.load(",
    "tomllib.loads(",
    "load_yaml_document(",
    "_policy_primitives import",
)

#: A candidate file PASSES if it references any of these guard idioms (module
#: docstring) — the full set of named-TBD-rejection mechanisms this codebase's loaders
#: actually use, as surveyed by W-A A-0 round 2.
_GUARD_TOKENS: tuple[str, ...] = (
    "reject_named_tbd",
    "is_named_tbd_placeholder",
    "first_named_tbd_leaf",
    "TBD_STR",
    "_TBD_STR",
    "TBD_DIGEST",
    "NAMED_TBD_PLACEHOLDER",
    "require_filled_str",
    "optional_str",
    "require_str_field",
    "_tbd_to_none",
)

_PRUNED_DIR_NAMES = frozenset({"__pycache__", ".venv"})


class NamedTbdGuardConfigError(Exception):
    """The registry config is missing, unparseable, or fails schema validation —
    failure class (e), a hard stop distinct from a collected violation."""


@dataclass(frozen=True)
class ExemptEntry:
    """One registered ``exempt_files:`` entry."""

    path: str
    reason: str


def _iter_scope_files(scope_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(scope_dir.rglob("*.py")):
        if any(part in _PRUNED_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return files


def _is_candidate(text: str) -> bool:
    return any(signal in text for signal in _CANDIDATE_SIGNALS)


def _is_guarded(text: str) -> bool:
    return any(token in text for token in _GUARD_TOKENS)


def load_config(config_path: Path) -> tuple[ExemptEntry, ...]:
    """Load + schema-validate ``config_path``, fail-closed (failure class e)."""
    if not config_path.is_file():
        raise NamedTbdGuardConfigError(
            f"tos_named_tbd_guard config file not found: {config_path}"
        )
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise NamedTbdGuardConfigError(
            f"tos_named_tbd_guard config file is not valid YAML: {config_path} ({exc})"
        ) from exc
    if not isinstance(raw, dict) or "exempt_files" not in raw:
        raise NamedTbdGuardConfigError(
            f"tos_named_tbd_guard config file must be a mapping with an 'exempt_files' "
            f"key: {config_path}"
        )
    entries_raw = raw["exempt_files"]
    if not isinstance(entries_raw, list):
        raise NamedTbdGuardConfigError(
            f"tos_named_tbd_guard config 'exempt_files' must be a list: {config_path}"
        )
    entries: list[ExemptEntry] = []
    seen_paths: set[str] = set()
    for i, entry in enumerate(entries_raw):
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("path"), str)
            or not entry["path"].strip()
            or not isinstance(entry.get("reason"), str)
            or not entry["reason"].strip()
        ):
            raise NamedTbdGuardConfigError(
                f"tos_named_tbd_guard config exempt_files[{i}] must be a mapping with "
                f"non-blank 'path' and 'reason' string fields: {config_path}"
            )
        path = entry["path"]
        if path in seen_paths:
            raise NamedTbdGuardConfigError(
                f"tos_named_tbd_guard config exempt_files has a duplicate path: {path!r}"
            )
        seen_paths.add(path)
        entries.append(ExemptEntry(path=path, reason=entry["reason"]))
    return tuple(entries)


def check(
    *, repo_root: Path, scope_dir: Path, config_path: Path
) -> tuple[list[str], list[str]]:
    """Run every failure class (a)-(d) — returns ``(candidates, violations)``.

    ``candidates`` is every file this scan judged a config loader (for reporting);
    ``violations`` is one string per failure, empty when clean.
    """
    exempt_by_path = {e.path: e for e in load_config(config_path)}
    candidates: list[str] = []
    guarded_candidates: set[str] = set()
    violations: list[str] = []

    for file_path in _iter_scope_files(scope_dir):
        rel_path = file_path.relative_to(repo_root).as_posix()
        text = file_path.read_text(encoding="utf-8")
        if not _is_candidate(text):
            continue
        candidates.append(rel_path)
        guarded = _is_guarded(text)
        if guarded:
            guarded_candidates.add(rel_path)
        exemption = exempt_by_path.get(rel_path)
        if exemption is None:
            if not guarded:
                violations.append(
                    f"[unguarded] {rel_path}: reads a raw YAML value but references no "
                    "named-TBD guard idiom and is not registered in "
                    f"{config_path} — either add a guard or register an exemption with "
                    "a reason"
                )
            continue
        # Registered — check for staleness (classes c/d). Class (c) (no longer a
        # candidate) cannot happen here since we only reach this branch for files the
        # loop already proved ARE candidates; a path that is no longer a candidate at
        # all is instead caught below, after the scan, as "registered path never seen".
        if guarded:
            violations.append(
                f"[stale-exemption] {rel_path}: registered in {config_path} as unguarded, "
                "but now references a guard idiom — remove the registration (it no "
                "longer reflects why this file is exempt)"
            )

    seen_candidates = set(candidates)
    for entry in exempt_by_path.values():
        full_path = repo_root / entry.path
        if not full_path.is_file():
            violations.append(
                f"[stale-registration] {entry.path}: registered in {config_path} but "
                "does not exist under the scanned tree"
            )
        elif entry.path not in seen_candidates:
            violations.append(
                f"[stale-registration] {entry.path}: registered in {config_path} but is "
                "no longer a named-TBD candidate (the YAML consumption that made it one "
                "was removed) — remove the registration"
            )

    return candidates, sorted(violations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Exit 1 on any violation (CI mode)."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to the registry config (default: {DEFAULT_CONFIG}).",
    )
    parser.add_argument(
        "--scope",
        type=Path,
        default=DEFAULT_SCOPE,
        help=f"Directory to scan (default: {DEFAULT_SCOPE}).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_REPO_ROOT,
        help="Repo root paths are reported relative to (default: this checkout).",
    )
    args = parser.parse_args(argv)

    config_path = args.config if args.config.is_absolute() else args.root / args.config
    scope_dir = args.scope if args.scope.is_absolute() else args.root / args.scope

    try:
        candidates, violations = check(
            repo_root=args.root, scope_dir=scope_dir, config_path=config_path
        )
    except NamedTbdGuardConfigError as exc:
        print(f"tos named-TBD guard config error: {exc}", file=sys.stderr)
        return 1

    if violations:
        print(f"tos named-TBD guard FAIL: {len(violations)} violation(s)")
        for violation in violations:
            print(f"  {violation}")
    else:
        print(
            f"tos named-TBD guard PASS: {len(candidates)} candidate file(s) scanned, "
            "0 violations"
        )

    if args.check:
        return 1 if violations else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
