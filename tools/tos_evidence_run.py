#!/usr/bin/env python3
"""EV-L1 / EV-L2 / EV-L3 evidence run harness — design #1 §5.1 run-manifest contract.

Ratified sources (this file mechanizes them; it does not own them):

  * ``docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md`` §5.1 —
    the seven run-manifest items every evidence-producing run SHALL record, and
    the declaration that those seven are the **EV-L1 subset** of
    VER-002-001 §2.3 / §3 / §9.1 / §9.2.
  * ``tos-spec/src/part-1-foundation/VER-002-001-*.md`` §3 (:84-109, the 22-field
    Verification Object Baseline — "A run without a complete baseline is
    invalid"), §8 (:299-340, evidence package structure), §9.1 (append-only run
    record incl. seed), §9.2 (artifact hashing), §9.3 (wall clock + monotonic),
    §9.5 (:364-366, a PASS is incomplete until independent review signs).

Honesty contract
----------------
VER §3 lists 22 baseline fields. Several name artifacts that **do not exist** at
this stage (Hard Safety Envelope instance, Runtime Safety Profile instance, the
policy generations, Broker Capability Profile, deployment manifest, key
versions). Those fields are emitted with an explicit ``NOT_APPLICABLE_EV_L1``
status **and a reason**, never with a fabricated value, on the design #1 §5.1
"EV-L1 subset" basis. The manifest states in-band that under VER §3's full
standard the baseline is complete only for EV-L1.

This harness never moves an Evidence Register row to ``PASS``. Every manifest
carries the discipline tag in ``DISCIPLINE_TAG`` / ``DISCIPLINE_TAG_L2``.

EV-L2 stage (manifest v2)
-------------------------
``--evidence-level-stage EV-L2`` produces a **superset** manifest: every v1 field
is retained unchanged and four field groups are added (EV-L2 pilot design
``docs/plans/2026-07-29-tos-ev-l2-pilot-design.md`` §6.2) —
``prior_stage_runs`` (the EV-L1 run(s) this stage builds on, bound by their
``sha256sums.txt`` digest and baseline commit), ``fault_injection`` (catalog ref,
append-only schedule artifact, seed, and the **re-counted** per-row fault
totals), ``coverage_argument`` (VER-002-001 §2.7), and the ``claim`` block's
``stages_executed`` / ``covered_axis``.

Four EV-L2-only gates can withhold GREEN, and none of them is a self-report:

  * ``fault_injection.all_faults_met`` — every row's outcome is **re-derived**
    from its observed vs expected disposition (the row's own ``outcome`` field is
    cross-checked, never believed). A deviation, a misreported outcome, an
    undefined Expected, an unobserved disposition, a duplicated fault id, a row
    from another evidence id, **zero rows**, or a recount that disagrees with
    ``--expected-fault-count`` all withhold it ("0 faults injected" is not "no
    violations", and a deselected fault must not shrink the schedule silently;
    design §0.5-2 / C2-c).
  * ``fault_injection.l1_hardening_prereq_met`` — the design §5 H-1/H-2/H-4
    hardening is confirmed by parsing the executed source and inspecting its
    syntax tree, never from a flag the caller passes and never by a substring
    scan a comment could satisfy.
  * ``prior_stage_runs[*]`` — the prior package is re-verified (every recorded
    digest re-hashed, no uncovered file, matching evidence id, green outcome),
    and ``baseline_matches_this_run`` carries design §6.2 M9: an EV-L1 run taken
    at a different baseline commit is stale evidence, so the staged ``L1 ∧ L2``
    claim is unsupported until EV-L1 is re-executed at this baseline.
  * ``fault_injection.seed`` — an EV-L2 stage must be seed-reproducible
    (VER §9.1), so an unpinned seed policy withholds GREEN.

EV-L3 stage (manifest v3)
-------------------------
``--evidence-level-stage EV-L3`` produces a **superset of v2**: every earlier
field is retained and two field groups are added (EV-L3 pilot design
``docs/plans/2026-08-06-tos-ev-l3-pilot-design.md`` §6.1) — ``integration_boundary``
(the persistence substrate, the process boundary with its measured pids and crash
mechanism, and the ``modeled_axes`` this stage did NOT exercise as real
boundaries) and ``crash_injection`` (catalog ref, the append-only crash schedule,
seed, and the **re-counted** per-row scenario totals). ``fault_injection`` is an
EV-L2 block and is not emitted at EV-L3: the two schedules have different row
shapes and different gates.

Six EV-L3-only gates can withhold GREEN, and none of them is a self-report:

  * ``crash_injection.all_crash_scenarios_met`` — every row's outcome is
    **re-derived** from its observed vs expected reconstruction (the row's own
    ``outcome`` is cross-checked, never believed). The expected reconstruction is
    a hand-derived anchor produced outside ``tos/``, where the firewall's reverse
    rule makes calling ``reconstruct_conservative`` impossible — so the oracle
    cannot be the implementation. Zero rows withholds it.
  * ``crash_injection.process_boundary_real`` — ``writer_pid != reader_pid``,
    both positive, on every row. An in-process fallback would forge exactly the
    "real … boundaries" EV-L3 is defined by (VER §5 line 151-153).
  * ``crash_injection.persistence_real`` — the conjunction of a run-time
    measurement (a non-empty store file observed after its writer died) and a
    **source property** (:func:`check_persistence_substrate`: one connection, no
    literal target, no ``:memory:``, both pragmas). Either alone is satisfiable
    by something that is not really durable.
  * ``prior_stage_runs[*]`` — STATE-EV-001's EV-L1 **AND** EV-L2 must both be
    bound at THIS baseline. Not this row's own staging requirement: it is the
    durable-limb continuity that lets L3 evidence attach to a non-stale model
    base (design §6.2 gate 4).
  * ``integration_boundary.modeled_axes[*].residual_ref`` — an axis this stage
    modelled or deferred must name the §378 residual carrying it, so a modelled
    boundary can never be recorded as a real one.
  * ``crash_injection.seed`` — as at EV-L2 (VER §9.1).

Layout produced (VER §8-equivalent, run-scoped)::

    tos-evidence/<EVIDENCE-ID>/<run-id>/
        manifest.yaml       run metadata + result + discipline tag
        baseline.yaml       design #1 §5.1 seven items + VER §3 22 fields
        traceability.csv    EV-ID -> ADR -> design document -> test node
        junit.xml           pytest --junitxml output
        run.log             captured stdout+stderr of the pytest invocation
        fault-timeline.jsonl  EV-L2 only: the append-only VER §9.1 fault schedule
        crash-timeline.jsonl  EV-L3 only: the append-only VER §9.1 crash schedule
        sha256sums.txt      sha256 of every retained file (written last)

``run-id`` is ``<UTC timestamp>-<git short sha>``. The run directory is created
exclusively and every file is opened with mode ``"x"``: an existing run is never
overwritten (VER §9.1 append-only). A run that raises before its package is
closed leaves an ``INCOMPLETE_RUN.txt`` marker instead of a silent partial.

Exit codes: ``0`` all selected tests green; ``1`` tests not green or nothing
executed; ``2`` precondition failure, append-only violation, or an integrity
violation (an executed file changed during the run).

This tool lives under ``tools/`` (outside ``tos/``) and is therefore not
governed by the import firewall; it must still never ``import tos`` (TOS-FW-R).
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import os
import platform
import re
import subprocess
import sys
import time
import tomllib
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import yaml

# ============================================================================
# Ratified constants
# ============================================================================

#: Attached to every manifest. Prevents a stage record from being read as a row
#: PASS (VER §9.5 independent sign-off; VER:171 staged-level rule; P0-1 open).
DISCIPLINE_TAG = (
    "EV-L1 stage execution record only; not a row PASS; incomplete until "
    "independent review signs (VER §9.5) and P0-1 (bounds approval) closes; "
    "staged rows require higher stages before acceptance (VER:171)."
)

#: The EV-L2 counterpart (EV-L2 pilot design §6.2 N8, verbatim). It names the four
#: outstanding gates by the manifest blocks that carry their state, so a reader never
#: has to trust the tag alone.
DISCIPLINE_TAG_L2 = (
    "EV-L2 stage execution record only; not a row PASS; L1 hardening prereq + "
    "coverage argument + P0-1 + independent review remain as stated in "
    "claim/coverage_argument blocks."
)

#: The EV-L3 counterpart (EV-L3 pilot design §6.2, verbatim). Like its EV-L2 sibling it
#: names the outstanding gates by the manifest blocks that carry their state, so a
#: reader never has to trust the tag alone.
DISCIPLINE_TAG_L3 = (
    "EV-L3 stage execution record only; not a row PASS; restart coverage argument + "
    "network/identity residuals + independent review remain as stated in "
    "claim/coverage_argument blocks."
)

STAGE_L1 = "EV-L1"
STAGE_L2 = "EV-L2"
STAGE_L3 = "EV-L3"
STAGES = (STAGE_L1, STAGE_L2, STAGE_L3)

#: The Verification Profile is PROPOSED, not approved — P0-1 is open. Recorded
#: verbatim so no downstream reader can mistake it for an approved profile.
VERIFICATION_PROFILE_VERSION = "2.1 (PROPOSED — P0-1 open)"

NOT_APPLICABLE = "NOT_APPLICABLE_EV_L1"
#: The EV-L2 N/A token (design §6.2 M2). The baseline note is *updated*, never deleted:
#: the VER §3 unmet-field list and every reason survive the stage change, they are just
#: attributed to the pure-model L2 stage instead of to EV-L1.
NOT_APPLICABLE_L2 = "NOT_APPLICABLE_PURE_MODEL_L2"
#: The EV-L3 N/A token (EV-L3 pilot design §6.3). The stage integrates real persistence
#: and a real process boundary, so "pure model" would be a false attribution; what is
#: still absent is the **transport** (the send boundary is a modelled marker, zero real
#: bytes) and everything that hangs off it. Same M2 discipline: the field, its N/A status
#: and its reason are retained — only the stage attribution changes.
NOT_APPLICABLE_L3 = "NOT_APPLICABLE_MODELED_TRANSPORT_L3"
RECORDED = "RECORDED"
PARTIAL = "PARTIAL_EV_L1"

DESIGN_1_PATH = "docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md"
VER_SPEC_PATH = (
    "tos-spec/src/part-1-foundation/"
    "VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md"
)
REGISTER_CSV_PATH = (
    "tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv"
)
PROFILE_YAML_PATH = (
    "tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml"
)

#: Third-party distributions whose *installed* versions are measured (design #1
#: §5.1 item 2). ``tos`` is included to record whether the kernel under test is
#: installed in the target interpreter.
PROBED_DISTRIBUTIONS = (
    "pydantic",
    "hypothesis",
    "pytest",
    "numpy",
    "pandas",
    "pyyaml",
    "tos",
)

MANIFEST_NAME = "manifest.yaml"
BASELINE_NAME = "baseline.yaml"
TRACEABILITY_NAME = "traceability.csv"
JUNIT_NAME = "junit.xml"
RUNLOG_NAME = "run.log"
FAULT_TIMELINE_NAME = "fault-timeline.jsonl"
#: The EV-L3 append-only crash schedule (EV-L3 pilot design §6.1). A separate artifact
#: from the EV-L2 fault timeline: the two schedules have different row shapes and
#: different gates, and merging them would let one stage's rows satisfy the other's
#: recount.
CRASH_TIMELINE_NAME = "crash-timeline.jsonl"
SHA256SUMS_NAME = "sha256sums.txt"
INCOMPLETE_MARKER_NAME = "INCOMPLETE_RUN.txt"

# ---------------------------------------------------------------------------
# EV-L2 constants (EV-L2 pilot design §5 / §6.2)
# ---------------------------------------------------------------------------

EVL2_DESIGN_PATH = "docs/plans/2026-07-29-tos-ev-l2-pilot-design.md"
EVL3_DESIGN_PATH = "docs/plans/2026-08-06-tos-ev-l3-pilot-design.md"

#: EV-L3 pilot design §6.2 gate 4. The prior-stage binding an EV-L3 crash/restart run
#: requires is **this row's** continuity, and the row is named: STATE-EV-001 is where the
#: durable limb (R-1) lives, and its EV-L1 ∧ EV-L2 stages are what the L3 durable
#: evidence attaches to. The id is checked structurally because STATE-EV-003 is also
#: registered at ``EV-L1/3`` and could otherwise satisfy the gate with the wrong row's
#: stages (design §6.2 MINOR-2).
L3_PRIOR_STAGE_EVIDENCE_ID = "STATE-EV-001"

#: The stages that binding must cover, both of them, at THIS baseline. Named "AND", not
#: "OR": one stale stage is one stage whose model no longer describes the code the crash
#: run executed (design §6.2 NIT-2).
L3_REQUIRED_PRIOR_STAGES = (STAGE_L1, STAGE_L2)

#: The design §5 L1 hardening prerequisites. Confirming the hardening by reading the
#: executed code, rather than by trusting a ``--hardening-done`` flag, is the whole point:
#: a stage run that exercised SPG-05/06/08 or ST-07 against an un-hardened component would
#: be recording DEVIATIONs as if they were MET (design §5 gating).
#:
#: Each entry is checked **structurally** (:func:`check_l1_hardening`), never by scanning
#: the file for a substring. A file-wide substring test is satisfied by the token appearing
#: *anywhere*, including in a comment or a docstring — so H-1 could be rolled back while a
#: sentence merely mentioning ``allow_inf_nan=False`` kept the gate green (measured). H-1
#: is therefore read out of the parsed AST: the keyword must be bound in the actual
#: ``ConfigDict(...)`` call assigned to ``FrozenModel.model_config``, with the literal
#: value ``False``. H-2/H-4 are matched against **code tokens only**, with comments and
#: string contents removed by :mod:`tokenize` first.
#:
#: This harness must never ``import tos`` (TOS-FW-R), so every check is static analysis of
#: the source, not introspection of loaded objects.
#: The §11 step 3 metadata axes ``_UNIT_METADATA_KEYS`` must compare for H-2.
H2_REQUIRED_METADATA_KEYS = frozenset(
    {"unit", "multiplier", "sign", "precision", "rounding", "boundary"}
)


def _assigned_value(tree: ast.AST, name: str) -> ast.expr | None:
    """The value expression assigned to a module-level ``name``, or ``None``."""
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            return node.value
    return None


def _class_attr_value(tree: ast.AST, class_name: str, attr: str) -> ast.expr | None:
    """The value expression assigned to ``<class_name>.<attr>``, or ``None``."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for stmt in node.body:
                targets: list[ast.expr] = []
                if isinstance(stmt, ast.Assign):
                    targets = list(stmt.targets)
                elif isinstance(stmt, ast.AnnAssign):
                    targets = [stmt.target]
                if any(isinstance(t, ast.Name) and t.id == attr for t in targets):
                    return stmt.value
    return None


def _function_def(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    """The (first) function definition called ``name``, or ``None``."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _raised_names(scope: ast.AST) -> list[str]:
    """The exception class names raised anywhere inside ``scope``."""
    names: list[str] = []
    for node in ast.walk(scope):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        exc = node.exc
        func = exc.func if isinstance(exc, ast.Call) else exc
        if isinstance(func, ast.Name):
            names.append(func.id)
        elif isinstance(func, ast.Attribute):
            names.append(func.attr)
    return names


def check_h1(tree: ast.AST) -> tuple[bool, dict]:
    """H-1: ``FrozenModel.model_config = ConfigDict(..., allow_inf_nan=False)``.

    Read out of the AST, so the pin must be a real keyword bound in the real call with
    the literal ``False``. A substring scan would also accept the token sitting in a
    comment or docstring while the pin itself was deleted (measured).
    """
    value = _class_attr_value(tree, "FrozenModel", "model_config")
    if not (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "ConfigDict"
    ):
        return False, {
            "reason": "FrozenModel.model_config is not a ConfigDict(...) call"
        }
    bound = {kw.arg: kw.value for kw in value.keywords if kw.arg is not None}
    pin = bound.get("allow_inf_nan")
    met = isinstance(pin, ast.Constant) and pin.value is False
    return met, {
        "bound_keywords": sorted(bound),
        "allow_inf_nan": None if pin is None else ast.unparse(pin),
    }


def check_h2(tree: ast.AST) -> tuple[bool, dict]:
    """H-2: the six §11 step 3 metadata axes are compared, and the boundary test exists."""
    value = _assigned_value(tree, "_UNIT_METADATA_KEYS")
    keys = (
        [e.value for e in value.elts if isinstance(e, ast.Constant)]
        if isinstance(value, ast.Tuple)
        else []
    )
    missing = sorted(H2_REQUIRED_METADATA_KEYS - set(keys))
    has_comparison = _function_def(tree, "_exceeds_envelope_maximum") is not None
    return (not missing and has_comparison), {
        "unit_metadata_keys": keys,
        "missing_metadata_keys": missing,
        "boundary_comparison_defined": has_comparison,
    }


def check_h4(tree: ast.AST) -> tuple[bool, dict]:
    """H-4: ``get_scheme`` raises ``ArtifactIntegrityError`` and no raw ``KeyError`` survives."""
    scheme_fn = _function_def(tree, "get_scheme")
    inner = _raised_names(scheme_fn) if scheme_fn is not None else []
    module_wide = _raised_names(tree)
    met = "ArtifactIntegrityError" in inner and "KeyError" not in module_wide
    return met, {
        "get_scheme_raises": sorted(set(inner)),
        "module_raises": sorted(set(module_wide)),
    }


_H1_LABEL = "H-1 allow_inf_nan=False pinned on FrozenModel.model_config"

#: ``(label, repo-relative path, structural checker)``. Every checker takes the parsed
#: module AST and returns ``(met, detail)``; the detail is recorded either way so an unmet
#: run says exactly *what* was measured, not merely that something failed.
L1_HARDENING_PREREQUISITES: tuple[
    tuple[str, str, Callable[[ast.AST], tuple[bool, dict]]], ...
] = (
    (_H1_LABEL, "tos/src/tos/canonical/_base.py", check_h1),
    (
        "H-2 precision/rounding/boundary comparability + boundary-aware comparison",
        "tos/src/tos/spg/predicates.py",
        check_h2,
    ),
    (
        "H-4 canonicalization scheme lookup wrapped as ArtifactIntegrityError",
        "tos/src/tos/canonical/canonicalization.py",
        check_h4,
    ),
)

#: VER-002-001 §2.7 (line 76-78) coverage-argument legs. ``boundary_values`` and
#: ``adverse_scenario_set`` are corpus-level facts, so they are stated here once;
#: ``unexercised_residual_ref`` is row-specific and comes from ``--residual-ref``.
COVERAGE_BOUNDARY_VALUES = "per-dimension boundary combinations exercised (seed-fixed)"
#: The EV-L3 restart axis (EV-L3 pilot design §6.1). Same leg, different quantifier: the
#: boundary values are crash points crossed with composite boundary combinations, and
#: the enumeration is deterministic rather than sampled.
COVERAGE_BOUNDARY_VALUES_L3 = (
    "per crash-point x composite boundary combinations, deterministically enumerated "
    "(seed-fixed); the restart axis only"
)
COVERAGE_ADVERSE_SCENARIO_SET = (
    "ADR-002-021 PROPOSED (unapproved) — adversarial-combination leg UNMET; "
    "applicability to non-risk row = OQ; residual per §378"
)
#: design §6.2 N4 — the §378 register instance is **absent** (measured: only
#: RESIDUAL-RISK-ACCEPTANCE-RECORD-template.yaml under verification/, zero residual
#: artifacts under tos-evidence/), so creating it is prerequisite work. Each entry must
#: carry all twelve VER:3293-3306 SHALL fields, and separate residuals SHALL NOT be
#: unioned at a consumer (VER:3308) — the refs below are pointers, not a union.
COVERAGE_RESIDUAL_NOTE = (
    "The §378 Residual Risk Register INSTANCE is absent (measured: "
    "verification/ holds only RESIDUAL-RISK-ACCEPTANCE-RECORD-template.yaml; "
    "tos-evidence/ holds zero residual artifacts) — creating it is prerequisite "
    "work. Each entry SHALL carry all twelve VER:3293-3306 fields (risk identity; "
    "affected requirement/ADR; scope; credible failure sequence; maximum economic "
    "effect; existing controls; detection/containment bound; owner; approver; "
    "expiration/review date; required scope reduction; evidence references), and "
    "owner/approver come through the P0-3 role system (D1). The refs above are "
    "pointers, not a union: separate residual risks SHALL NOT be unioned at a "
    "consumer (VER:3308) — each is registered independently."
)


class HarnessError(RuntimeError):
    """A precondition or append-only violation. Never a test failure."""


# ============================================================================
# primitives
# ============================================================================


def _utc_now() -> datetime:
    """UTC wall clock (seam: monkeypatched by the harness self-tests)."""
    return datetime.now(UTC)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo_root: Path, *args: str, strip: bool = True) -> str:
    """Run git. ``strip=False`` for output whose leading blanks are significant.

    ``git status --porcelain`` encodes the staged/unstaged axis in two leading
    status characters, the first of which is a space for an unstaged change:
    stripping the output would shift the first line by one column, mis-classify
    it as staged AND truncate its path — which would make the dirty-target guard
    fail OPEN for exactly that file.
    """
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise HarnessError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip() if strip else proc.stdout


def parse_porcelain(raw: str) -> dict:
    """Parse ``git status --porcelain=v1 -z -uall`` output.

    ``-z`` is used because the default format C-quotes any path containing a
    space, a quote, or a non-ASCII byte — a quoted path never matches an
    executed file, so the dirty-target guard would fail OPEN for it. In ``-z``
    mode paths are emitted raw and NUL-separated, and a rename/copy entry is
    followed by a second NUL field holding the original path, which must be
    consumed so it is not mistaken for a status entry.

    ``-uall`` is used because the default collapses an untracked directory to a
    single ``?? pkg/`` entry: an executed file *inside* a brand-new package
    would then match nothing in the dirty set and pass the guard as clean.
    """
    fields = raw.split("\0")
    untracked: list[str] = []
    modified: list[str] = []
    staged: list[str] = []
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        if code[0] in "RC":  # the next field is the rename/copy source
            index += 1
        if code == "??":
            untracked.append(path)
            continue
        if code[0] not in " ?":
            staged.append(path)
        if code[1] not in " ?":
            modified.append(path)
    dirty = sorted(set(untracked) | set(modified) | set(staged))
    return {
        "clean": not dirty,
        "untracked": sorted(untracked),
        "modified_unstaged": sorted(modified),
        "staged": sorted(staged),
        "all_dirty_paths": dirty,
        "note": (
            "A non-empty list does not by itself invalidate the run: the executed "
            "files are pinned individually by target_file_digests below. Paths "
            "outside the executed set belong to other work in the same worktree."
        ),
    }


def worktree_status(repo_root: Path) -> dict:
    """Honest worktree record: every untracked / modified / staged path.

    Other sessions' in-flight work is enumerated rather than hidden, so a reader
    can judge whether the recorded commit sha describes the executed bytes.
    """
    return parse_porcelain(
        _git(repo_root, "status", "--porcelain=v1", "-z", "-uall", strip=False)
    )


def is_dirty_target(rel: str, dirty_paths: list[str]) -> bool:
    """Is ``rel`` covered by the dirty set, directly or by a dirty directory?

    ``-uall`` already enumerates untracked files individually; the trailing-slash
    prefix arm is belt-and-braces for any git version or configuration that
    still emits a directory entry.
    """
    if rel in dirty_paths:
        return True
    return any(entry.endswith("/") and rel.startswith(entry) for entry in dirty_paths)


def collect_digests(repo_root: Path, rels: list[str]) -> dict[str, str]:
    """sha256 of each repo-relative path (seam: stubbed by the self-tests)."""
    return {rel: sha256_file(repo_root / rel) for rel in rels}


def digest_report(
    pre: dict[str, str],
    post: dict[str, str],
    dirty_paths: list[str],
    guarded_rels: list[str] | None = None,
) -> list[dict]:
    """Per-file record binding the executed bytes, before AND after the run.

    Digesting only after execution would let a file mutated *during* the run be
    recorded as the file that ran (TOCTOU). Both observations are kept and a
    disagreement is named, never averaged away.
    """
    guarded = set(guarded_rels) if guarded_rels is not None else set(pre)
    report = []
    for rel in sorted(pre):
        before, after = pre[rel], post.get(rel, "FILE_ABSENT_AFTER_RUN")
        report.append(
            {
                "path": rel,
                "sha256_before_run": before,
                "sha256_after_run": after,
                "status": (
                    "STABLE_DURING_RUN" if before == after else "MUTATED_DURING_RUN"
                ),
                "git_clean": not is_dirty_target(rel, dirty_paths),
                # False = watched for mutation but exempt from the cleanliness
                # refusal (the harness itself; its provenance is recorded in item 4).
                "cleanliness_guarded": rel in guarded,
            }
        )
    return report


def worktree_delta(before: dict, after: dict) -> dict:
    """What the worktree gained or lost while the tests ran."""
    b, a = set(before["all_dirty_paths"]), set(after["all_dirty_paths"])
    return {
        "became_dirty_during_run": sorted(a - b),
        "became_clean_during_run": sorted(b - a),
        "stable": a == b,
    }


def git_blob_sha(repo_root: Path, rel: str) -> str:
    """The blob sha this path has *in HEAD*, or ``NOT_IN_COMMIT``."""
    try:
        return _git(repo_root, "rev-parse", f"HEAD:{rel}")
    except HarnessError:
        return "NOT_IN_COMMIT"


def harness_provenance(
    repo_root: Path, harness_path: Path, status: dict, pytest_version: str | None
) -> dict:
    """Self-provenance, derived from the worktree — never assumed.

    Recording the repository HEAD as the harness version while the harness file
    is untracked would fabricate its provenance — the same defect this tool
    refuses to commit for every other baseline field.
    """
    rel = str(harness_path.relative_to(repo_root))
    dirty = status["all_dirty_paths"]
    untracked = is_dirty_target(rel, status["untracked"])
    blob = "NOT_IN_COMMIT" if untracked else git_blob_sha(repo_root, rel)
    return {
        "harness_path": rel,
        "harness_sha256": sha256_file(harness_path),
        "harness_tracked": not untracked,
        "harness_at_commit": blob,
        "harness_dirty": is_dirty_target(rel, dirty),
        "pytest_version": pytest_version,
        "note": (
            "design #1 §5.1 item 4 — Phase 1 harness version = git digest, which "
            "exists only once the harness is committed. Until then "
            "harness_at_commit is NOT_IN_COMMIT and harness_sha256 is the only "
            "identity of the code that ran."
        ),
    }


def classify_outcome(return_code: int, junit: dict) -> str:
    """Green requires *executed* assertions, not merely a zero exit code.

    A selection that collected nothing, or whose every test skipped, exits 0 —
    a vacuous green that would read as evidence that the properties held.
    """
    tests = junit.get("tests", 0) or 0
    skipped = junit.get("skipped", 0) or 0
    failures = junit.get("failures", 0) or 0
    errors = junit.get("errors", 0) or 0
    if tests <= 0 or (tests - skipped) <= 0:
        return "NO_TEST_EXECUTED"
    if return_code != 0 or failures or errors:
        return "SELECTED_TESTS_NOT_GREEN"
    return "ALL_SELECTED_TESTS_GREEN"


def iter_py_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        p for p in path.rglob("*.py") if "__pycache__" not in p.parts and p.is_file()
    )


def node_file(node: str) -> str:
    """``pkg/test_x.py::TestC::test_y`` -> ``pkg/test_x.py``."""
    return node.split("::", 1)[0]


def parse_node_spec(spec: str) -> tuple[str, str]:
    """``"<node> | <mapping basis>"`` -> ``(node, basis)``.

    The basis is the measured reason this node belongs to the evidence row (a
    file:line citation). An absent basis is recorded as ``UNSPECIFIED`` rather
    than invented.
    """
    if "|" in spec:
        node, basis = spec.split("|", 1)
        return node.strip(), basis.strip()
    return spec.strip(), "UNSPECIFIED"


def read_nodes_file(path: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(parse_node_spec(line))
    return out


# ============================================================================
# environment / dependency measurement
# ============================================================================

_PROBE_SOURCE = r"""
import json, platform, sys
import importlib.metadata as md

dists = json.loads(sys.argv[1])
installed = {}
for name in dists:
    try:
        installed[name] = md.version(name)
    except Exception:
        installed[name] = "NOT_INSTALLED"
print(json.dumps({
    "python": {
        "version": platform.python_version(),
        "version_full": sys.version.replace("\n", " "),
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
    },
    "installed": installed,
}))
"""


def probe_interpreter(
    python: Path, distributions: tuple[str, ...] = PROBED_DISTRIBUTIONS
) -> dict:
    """Measure the *target* interpreter (the one that will run pytest)."""
    proc = subprocess.run(
        [str(python), "-c", _PROBE_SOURCE, json.dumps(list(distributions))],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise HarnessError(
            f"interpreter probe failed for {python}: {proc.stderr.strip()}"
        )
    probed: dict = json.loads(proc.stdout)
    return probed


def read_pinned_dependencies(repo_root: Path) -> dict[str, str]:
    """Pins declared in ``tos/pyproject.toml`` (§3.2 / §5.1)."""
    pyproject = repo_root / "tos" / "pyproject.toml"
    if not pyproject.is_file():
        return {}
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data.get("project", {})
    pins: dict[str, str] = {}
    specs = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        specs.extend(extra)
    for spec in specs:
        if "==" in spec:
            name, version = spec.split("==", 1)
            pins[name.strip()] = version.strip()
    return pins


def read_tos_package_version(repo_root: Path) -> str:
    pyproject = repo_root / "tos" / "pyproject.toml"
    if not pyproject.is_file():
        return NOT_APPLICABLE
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return str(data.get("project", {}).get("version", NOT_APPLICABLE))


# ============================================================================
# EV-L2: hardening prerequisite, fault schedule, prior-stage binding
# ============================================================================


def check_l1_hardening(repo_root: Path) -> dict:
    """Confirm the design §5 L1 hardening **structurally** (never from a flag).

    Each prerequisite is decided by parsing the file that realizes it and inspecting the
    syntax tree — the pin must be a real keyword in a real call, the metadata tuple must
    really contain the six axes, ``get_scheme`` must really raise the integrity error and
    no raw ``KeyError`` may survive anywhere in that module. This is deliberately not a
    substring scan: a substring is satisfied by the token appearing in a comment or a
    docstring, so the gate would stay green with the hardening rolled back.

    A file that is absent, or that does not parse, is unmet — an unparseable file cannot
    be certified, and treating a parse failure as "no violations found" would be the same
    ∅-fail-open the fault schedule refuses.

    Returns:
        ``{"met": bool, "items": [...]}`` — every item is reported, met or not, with the
        structural detail measured, so an unmet run says *which* hardening is absent.
    """
    items: list[dict] = []
    for label, rel, checker in L1_HARDENING_PREREQUISITES:
        path = repo_root / rel
        if not path.is_file():
            items.append(
                {"hardening": label, "path": rel, "met": False, "reason": "FILE_ABSENT"}
            )
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            items.append(
                {
                    "hardening": label,
                    "path": rel,
                    "met": False,
                    "reason": f"SOURCE_DOES_NOT_PARSE: {exc}",
                }
            )
            continue
        met, detail = checker(tree)
        items.append(
            {
                "hardening": label,
                "path": rel,
                "sha256": sha256_file(path),
                "met": met,
                "measured": detail,
            }
        )
    return {
        "met": all(item["met"] for item in items),
        "measured_from": (
            "structural analysis of the executed source's syntax tree; comments and "
            "docstrings cannot satisfy any check (the harness never imports tos)"
        ),
        "items": items,
    }


def read_fault_timeline(path: Path) -> list[dict]:
    """Parse the append-only fault schedule (one JSON object per line).

    A malformed line is surfaced as a ``HarnessError`` rather than skipped: a schedule
    the harness cannot fully read must not be summarised as if it had been.
    """
    if not path.is_file():
        return []
    rows: list[dict] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HarnessError(
                f"{FAULT_TIMELINE_NAME} line {number} is not valid JSON: {exc}"
            ) from exc
        if not isinstance(row, dict):
            raise HarnessError(
                f"{FAULT_TIMELINE_NAME} line {number} is not a JSON object"
            )
        rows.append(row)
    return rows


#: The design §6.1 placeholder for a disposition the run has not actually observed. A row
#: carrying it verbatim was never filled in at runtime, so it proves nothing.
RUNTIME_OBSERVED_PLACEHOLDER = "<runtime-observed>"

#: The design §6.1 outcome vocabulary. Duplicated from ``tos/tests/conftest.py`` by
#: necessity, not oversight: this tool must never ``import tos`` (TOS-FW-R), and the two
#: sides agreeing is exactly what the re-derivation below checks — a shared import would
#: make the producer and the auditor the same authority.
OUTCOME_MET = "MET"
OUTCOME_DEVIATION = "DEVIATION"


def summarise_fault_schedule(
    rows: list[dict],
    *,
    expected_fault_count: int | None = None,
    evidence_id: str | None = None,
) -> dict:
    """Re-derive the fault schedule's verdict (design §6.2 C2-c).

    ``fault_count`` is **recounted from the artifact**, never taken from the catalog or
    from an argument, so a suite that silently stops injecting a fault shows up as a
    smaller count instead of an unchanged claim.

    Every row's ``outcome`` is likewise **re-derived here** rather than believed: a row is
    met only when its observed disposition equals its expected one. Consuming the row's
    own ``outcome`` field would make the schedule self-certifying — the emitting test
    could label a mismatch ``MET`` and this summary would agree.

    ``all_faults_met`` is withheld when any of the following holds:

      * the schedule is **empty** — "0 faults injected" is not "no violations found"
        (design §0.5-2 ∅-seal, both directions);
      * a row's observed disposition differs from its expected one, or its self-reported
        ``outcome`` disagrees with that re-derivation (§6.1);
      * a row's ``expected_disposition`` is missing or empty — an Expected that is not
        stated cannot be falsified, so it can never be counted as met (§0.5-4);
      * a row's ``observed_disposition`` is still the design §6.1
        ``<runtime-observed>`` placeholder — a template that never met a runtime;
      * a ``fault_id`` is duplicated (it would inflate the recount);
      * the recount disagrees with ``expected_fault_count`` (the catalog size), or a row
        belongs to a different ``evidence_id`` — deselecting one fault would otherwise
        shrink the schedule silently while every remaining row still read ``MET``.
    """

    def _fid(row: dict) -> str:
        return str(row.get("fault_id", "<unnamed>"))

    def _derived_outcome(row: dict) -> str:
        expected = str(row.get("expected_disposition") or "").strip()
        observed = str(row.get("observed_disposition") or "").strip()
        if not expected or not observed or observed == RUNTIME_OBSERVED_PLACEHOLDER:
            return OUTCOME_DEVIATION
        return OUTCOME_MET if observed == expected else OUTCOME_DEVIATION

    fault_ids = [_fid(row) for row in rows]
    deviations = sorted(
        _fid(row) for row in rows if _derived_outcome(row) != OUTCOME_MET
    )
    # A row whose self-report disagrees with the re-derivation is itself the finding.
    misreported = sorted(
        _fid(row) for row in rows if row.get("outcome") != _derived_outcome(row)
    )
    undefined_expected = sorted(
        _fid(row)
        for row in rows
        if not str(row.get("expected_disposition") or "").strip()
    )
    unobserved = sorted(
        _fid(row)
        for row in rows
        if str(row.get("observed_disposition") or "").strip()
        in ("", RUNTIME_OBSERVED_PLACEHOLDER)
    )
    duplicates = sorted({fid for fid in fault_ids if fault_ids.count(fid) > 1})
    foreign = sorted(
        {
            f"{_fid(row)}@{row.get('evidence_id')}"
            for row in rows
            if evidence_id is not None and row.get("evidence_id") != evidence_id
        }
    )
    count_matches = expected_fault_count is None or len(rows) == expected_fault_count
    return {
        "schedule_artifact": FAULT_TIMELINE_NAME,
        "fault_count": len(rows),
        "expected_fault_count": expected_fault_count,
        "fault_count_matches_catalog": count_matches,
        "fault_ids": fault_ids,
        "duplicate_fault_ids": duplicates,
        "foreign_evidence_id_rows": foreign,
        "deviation_faults": deviations,
        "misreported_outcome_faults": misreported,
        "expected_undefined_faults": undefined_expected,
        "unobserved_disposition_faults": unobserved,
        "all_faults_met": (
            bool(rows)
            and not deviations
            and not misreported
            and not undefined_expected
            and not unobserved
            and not duplicates
            and not foreign
            and count_matches
        ),
        "all_faults_met_basis": (
            "every row's outcome RE-DERIVED from observed vs expected (the row's own "
            "outcome field is cross-checked, never trusted); withheld on an empty "
            "schedule (0 injected != 0 violations), any deviation or misreport, any "
            "undefined Expected or unobserved disposition, a duplicated fault id, a row "
            "from another evidence id, or a recount that disagrees with the catalog size"
        ),
    }


def read_crash_timeline(path: Path) -> list[dict]:
    """Parse the append-only EV-L3 crash schedule (one JSON object per line).

    Same refusal as its EV-L2 sibling: a malformed line is a ``HarnessError`` rather
    than a skipped row, because a schedule the harness cannot fully read must not be
    summarised as if it had been.
    """
    if not path.is_file():
        return []
    rows: list[dict] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HarnessError(
                f"{CRASH_TIMELINE_NAME} line {number} is not valid JSON: {exc}"
            ) from exc
        if not isinstance(row, dict):
            raise HarnessError(
                f"{CRASH_TIMELINE_NAME} line {number} is not a JSON object"
            )
        rows.append(row)
    return rows


def summarise_crash_schedule(
    rows: list[dict],
    *,
    expected_scenario_count: int | None = None,
    evidence_id: str | None = None,
) -> dict:
    """Re-derive the crash schedule's three EV-L3 verdicts (design §6.2 gates 1-3).

    Nothing here is believed. ``crash_scenario_count`` is **recounted from the
    artifact**; every row's ``outcome`` is **re-derived** from its observed vs expected
    reconstruction and the row's own ``outcome`` is then cross-checked against that
    re-derivation; and the two boundary facts are **structural properties of the row's
    own measurements**, not flags the suite set:

      * ``process_boundary_real`` — ``writer_pid`` and ``reader_pid`` are both positive
        and different. An in-process fallback (or a suite that recorded one pid twice)
        would forge exactly the "real … boundaries" EV-L3 is defined by (VER §5 line
        151-153).
      * ``persistence_real`` — the store the reader read was a real file with a non-zero
        size *after* its writer died. The EV-L2 pilot's C1 finding was a durable claim
        satisfied in memory; recording a byte count observed on the filesystem is what
        makes the recurrence detectable.

    ``all_crash_scenarios_met`` is withheld when any of the following holds:

      * the schedule is **empty** — "0 crashes injected" is not "no violations found"
        (design §0.5-2 ∅-seal, both directions);
      * a row's observed reconstruction differs from its expected one, or its
        self-reported ``outcome`` disagrees with that re-derivation;
      * a row's ``expected_reconstruction`` is missing or empty — an Expected that is
        not stated cannot be falsified (§0.5-4);
      * a row's process boundary or persistence measurement does not hold;
      * a ``scenario_id`` is duplicated (it would inflate the recount);
      * the recount disagrees with ``expected_scenario_count`` (the catalog size), or a
        row belongs to a different ``evidence_id``.
    """

    def _sid(row: dict) -> str:
        return str(row.get("scenario_id", "<unnamed>"))

    def _boundary_real(row: dict) -> bool:
        writer, reader = row.get("writer_pid"), row.get("reader_pid")
        if not isinstance(writer, int) or not isinstance(reader, int):
            return False
        return writer > 0 and reader > 0 and writer != reader

    def _persistence_real(row: dict) -> bool:
        on_disk = row.get("store_real_on_disk")
        size = row.get("store_bytes")
        return on_disk is True and isinstance(size, int) and size > 0

    def _derived_outcome(row: dict) -> str:
        expected = str(row.get("expected_reconstruction") or "").strip()
        observed = str(row.get("observed_reconstruction") or "").strip()
        if not expected or not observed:
            return OUTCOME_DEVIATION
        if observed != expected:
            return OUTCOME_DEVIATION
        if not _boundary_real(row) or not _persistence_real(row):
            return OUTCOME_DEVIATION
        return OUTCOME_MET

    scenario_ids = [_sid(row) for row in rows]
    deviations = sorted(
        _sid(row) for row in rows if _derived_outcome(row) != OUTCOME_MET
    )
    misreported = sorted(
        _sid(row) for row in rows if row.get("outcome") != _derived_outcome(row)
    )
    undefined_expected = sorted(
        _sid(row)
        for row in rows
        if not str(row.get("expected_reconstruction") or "").strip()
    )
    unobserved = sorted(
        _sid(row)
        for row in rows
        if not str(row.get("observed_reconstruction") or "").strip()
    )
    shared_pid = sorted(_sid(row) for row in rows if not _boundary_real(row))
    not_on_disk = sorted(_sid(row) for row in rows if not _persistence_real(row))
    duplicates = sorted({sid for sid in scenario_ids if scenario_ids.count(sid) > 1})
    foreign = sorted(
        {
            f"{_sid(row)}@{row.get('evidence_id')}"
            for row in rows
            if evidence_id is not None and row.get("evidence_id") != evidence_id
        }
    )
    count_matches = (
        expected_scenario_count is None or len(rows) == expected_scenario_count
    )
    return {
        "schedule_artifact": CRASH_TIMELINE_NAME,
        "crash_scenario_count": len(rows),
        "expected_crash_scenario_count": expected_scenario_count,
        "crash_scenario_count_matches_catalog": count_matches,
        "scenario_ids": scenario_ids,
        "duplicate_scenario_ids": duplicates,
        "foreign_evidence_id_rows": foreign,
        "deviation_scenarios": deviations,
        "misreported_outcome_scenarios": misreported,
        "expected_undefined_scenarios": undefined_expected,
        "unobserved_reconstruction_scenarios": unobserved,
        "shared_process_scenarios": shared_pid,
        "non_durable_store_scenarios": not_on_disk,
        "crash_points": sorted({str(row.get("crash_point", "")) for row in rows}),
        "process_boundary_real": bool(rows) and not shared_pid,
        "persistence_real_measured": bool(rows) and not not_on_disk,
        "all_crash_scenarios_met": (
            bool(rows)
            and not deviations
            and not misreported
            and not undefined_expected
            and not unobserved
            and not shared_pid
            and not not_on_disk
            and not duplicates
            and not foreign
            and count_matches
        ),
        "all_crash_scenarios_met_basis": (
            "every row's outcome RE-DERIVED from observed vs expected reconstruction "
            "plus the row's own structural boundary measurements (the row's outcome "
            "field is cross-checked, never trusted); withheld on an empty schedule "
            "(0 injected != 0 violations), any deviation or misreport, any undefined "
            "Expected or unobserved reconstruction, a writer/reader pid that is not a "
            "real distinct pair, a store that was not a non-empty on-disk file, a "
            "duplicated scenario id, a row from another evidence id, or a recount that "
            "disagrees with the catalog size"
        ),
    }


#: The EV-L3 persistence substrate, checked **structurally** (design §6.2 gate 3). The
#: run-time rows say the store file existed; this says the component cannot be anything
#: other than a real on-disk sqlite database in the first place. Both are needed: a row
#: measurement proves what one execution did, a source property proves what any
#: execution can do. Verified by parsing the source, never by importing it (TOS-FW-R).
PERSISTENCE_SUBSTRATE_PATH = "tos/src/tos/staterestore/store.py"

#: The pragmas the pilot substrate decision (design §3.2 candidate A) names. Each must be
#: bound in a real ``execute(...)`` call argument — see :func:`_executed_pragmas`.
PERSISTENCE_REQUIRED_PRAGMAS = ("journal_mode=WAL", "synchronous=FULL")

#: Matches one ``PRAGMA <name>=<value>`` statement, normalised for whitespace and case.
_PRAGMA_RE = re.compile(r"^\s*PRAGMA\s+(\w+)\s*=\s*(\w+)\s*$", re.IGNORECASE)


def _executed_pragmas(tree: ast.AST) -> dict[str, str]:
    """The ``PRAGMA name=value`` settings really passed to an ``execute(...)`` call.

    Read out of the syntax tree, and **only** from a string literal sitting in the
    argument position of a call named ``execute``. A file-wide substring scan is
    satisfied by the token appearing anywhere — including in the very docstring that
    documents the pragma — so under a substring test the store's real
    ``PRAGMA synchronous=FULL`` could be changed to ``OFF`` while the module docstring
    kept the gate green (measured: that is exactly what happened before this function
    existed). This is the same discipline :func:`check_h1` already applies to the H-1
    pin, applied to the substrate pragmas.

    Returns:
        ``{pragma_name_lowercased: value_uppercased}``. A later ``execute`` of the same
        pragma wins, matching what sqlite would actually end up with.
    """
    executed: dict[str, str] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
        ):
            continue
        for arg in node.args:
            if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                continue
            match = _PRAGMA_RE.match(arg.value)
            if match:
                executed[match.group(1).lower()] = match.group(2).upper()
    return executed


def check_persistence_substrate(repo_root: Path) -> dict:
    """Confirm the store is a real on-disk sqlite substrate, from its syntax tree.

    Three structural facts, each falsifiable:

      * the module opens exactly one connection, and its target is **not a string
        literal** — so no ``":memory:"`` (or any other hardcoded target) can be what a
        run actually exercised;
      * neither ``:memory:`` nor ``mode=memory`` appears anywhere in the module, so the
        in-memory redefinition is unreachable rather than merely unused;
      * both design §3.2 pragmas are **executed** — bound as a string literal in a real
        ``execute(...)`` argument, not merely mentioned somewhere in the file.

    An absent or unparseable file is unmet — treating a parse failure as "nothing found"
    would be the same ∅-fail-open the schedule summary refuses.

    Returns:
        ``{"met": bool, "path": str, "measured": {...}}`` — the measurements are
        recorded either way, so an unmet run says exactly what was seen.
    """
    path = repo_root / PERSISTENCE_SUBSTRATE_PATH
    if not path.is_file():
        return {
            "met": False,
            "path": PERSISTENCE_SUBSTRATE_PATH,
            "reason": "FILE_ABSENT",
        }
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return {
            "met": False,
            "path": PERSISTENCE_SUBSTRATE_PATH,
            "reason": f"SOURCE_DOES_NOT_PARSE: {exc}",
        }
    connects = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "connect"
    ]
    literal_targets = sorted(
        {
            arg.value
            for call in connects
            for arg in call.args
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
        }
    )
    executed_pragmas = _executed_pragmas(tree)
    pragmas_present: list[str] = []
    pragmas_missing: list[str] = []
    for pragma in PERSISTENCE_REQUIRED_PRAGMAS:
        name, _, value = pragma.partition("=")
        if executed_pragmas.get(name.lower()) == value.upper():
            pragmas_present.append(pragma)
        else:
            pragmas_missing.append(pragma)
    in_memory_tokens = sorted(
        token for token in (":memory:", "mode=memory") if token in source
    )
    met = (
        len(connects) == 1
        and not literal_targets
        and not in_memory_tokens
        and not pragmas_missing
    )
    return {
        "met": met,
        "path": PERSISTENCE_SUBSTRATE_PATH,
        "sha256": sha256_file(path),
        "measured_from": (
            "structural analysis of the executed source's syntax tree; pragmas are read "
            "out of real execute(...) arguments, so a docstring or comment mentioning "
            "one cannot satisfy the check; the harness never imports tos (TOS-FW-R)"
        ),
        "measured": {
            "connect_call_sites": len(connects),
            "literal_connection_targets": literal_targets,
            "in_memory_tokens_present": in_memory_tokens,
            "executed_pragmas": dict(sorted(executed_pragmas.items())),
            "pragmas_present": sorted(pragmas_present),
            "pragmas_missing": sorted(pragmas_missing),
            "pragmas_required": list(PERSISTENCE_REQUIRED_PRAGMAS),
        },
    }


def parse_modeled_axis_spec(spec: str) -> dict:
    """``"<axis> | <disposition> | <residual-ref> | <note>"`` -> the manifest entry.

    An axis this stage did not really exercise must name the residual that carries it
    (design §6.2 gate 5). Parsing it as a required positional field — rather than as an
    optional key — is what makes an over-claim impossible to express: there is no way to
    declare a modelled axis and leave its residual blank.
    """
    parts = [part.strip() for part in spec.split("|")]
    if len(parts) < 3:
        raise HarnessError(
            "--modeled-axis expects '<axis> | <disposition> | <residual-ref> "
            f"[| <note>]', got {spec!r}"
        )
    axis, disposition, residual_ref = parts[0], parts[1], parts[2]
    note = " | ".join(parts[3:]).strip()
    if not axis or not disposition or not residual_ref:
        raise HarnessError(
            f"--modeled-axis has an empty axis / disposition / residual_ref in {spec!r}"
        )
    return {
        "axis": axis,
        "disposition": disposition,
        "residual_ref": residual_ref,
        "note": note or "UNSPECIFIED",
    }


def parse_prior_stage_spec(spec: str) -> tuple[str, str, str]:
    """``"<EVIDENCE-ID>/<run-id> | <reconcile note>"`` -> ``(evidence_id, run_id, note)``."""
    ref, _, note = spec.partition("|")
    ref = ref.strip()
    if "/" not in ref:
        raise HarnessError(
            f"--prior-stage-run expects '<EVIDENCE-ID>/<run-id> | <note>', got {spec!r}"
        )
    evidence_id, _, run_id = ref.partition("/")
    if not evidence_id.strip() or not run_id.strip():
        raise HarnessError(f"--prior-stage-run has an empty id in {spec!r}")
    return evidence_id.strip(), run_id.strip(), note.strip()


def bind_prior_stage_run(
    evidence_root: Path,
    evidence_id: str,
    run_id: str,
    reconcile_note: str,
    this_commit_sha: str,
) -> dict:
    """Bind an earlier stage run by artifact closure + baseline (design §6.2 M9).

    The binding is the prior package's ``sha256sums.txt`` digest — that file closes over
    every retained artifact including its manifest, so one digest pins the whole package
    and a later edit of any prior artifact breaks the reference. Recording that digest is
    **not** on its own a verification, so the prior package is re-verified here: every
    entry in its ``sha256sums.txt`` is re-hashed on disk and the directory is checked for
    files the sums file does not list. Otherwise a prior package could be edited (or
    quietly extended) and this run would still cite it as intact.

    ``baseline_matches_this_run`` is the M9 acceptance condition: an EV-L1 run taken at a
    different baseline commit is stale, and a staged ``L1 ∧ L2`` claim built on it would
    assert that both stages describe the same code when they do not.

    Raises:
        HarnessError: If the reference escapes the evidence root, the package is not
            closed, its recorded digests no longer match the files on disk, it retains a
            file the sums do not cover, its evidence id disagrees with the directory it
            sits in, or its own run was not green. A prior stage that did not pass cannot
            support a staged claim.
    """
    root = evidence_root.resolve()
    run_dir = (evidence_root / evidence_id / run_id).resolve()
    # Symmetric with create_run_directory: an id carrying ".." must not read outside
    # the evidence store.
    if root != run_dir and root not in run_dir.parents:
        raise HarnessError(
            f"--prior-stage-run {evidence_id}/{run_id} escapes the evidence root {root}"
        )
    sums = run_dir / SHA256SUMS_NAME
    if not sums.is_file():
        raise HarnessError(
            f"--prior-stage-run {evidence_id}/{run_id}: {sums} not found — a prior "
            "stage run must be a closed package (sha256sums.txt is written last)"
        )

    listed: dict[str, str] = {}
    for number, line in enumerate(sums.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        digest, _, name = line.partition("  ")
        if not digest or not name:
            raise HarnessError(
                f"--prior-stage-run {evidence_id}/{run_id}: {SHA256SUMS_NAME} line "
                f"{number} is malformed"
            )
        listed[name] = digest
    mismatched = sorted(
        name
        for name, digest in listed.items()
        if not (run_dir / name).is_file() or sha256_file(run_dir / name) != digest
    )
    if mismatched:
        raise HarnessError(
            f"--prior-stage-run {evidence_id}/{run_id}: recorded digests no longer "
            f"describe the files on disk: {mismatched}"
        )
    uncovered = sorted(
        p.name
        for p in run_dir.iterdir()
        if p.is_file() and p.name != SHA256SUMS_NAME and p.name not in listed
    )
    if uncovered:
        raise HarnessError(
            f"--prior-stage-run {evidence_id}/{run_id}: retains files that "
            f"{SHA256SUMS_NAME} does not cover: {uncovered}"
        )

    for required in (MANIFEST_NAME, BASELINE_NAME):
        if not (run_dir / required).is_file():
            raise HarnessError(
                f"--prior-stage-run {evidence_id}/{run_id}: {required} not found"
            )
    prior_manifest = yaml.safe_load(
        (run_dir / MANIFEST_NAME).read_text(encoding="utf-8")
    )
    prior_baseline = yaml.safe_load(
        (run_dir / BASELINE_NAME).read_text(encoding="utf-8")
    )

    prior_evidence_id = prior_manifest.get("evidence_id")
    if prior_evidence_id != evidence_id:
        raise HarnessError(
            f"--prior-stage-run {evidence_id}/{run_id}: the package declares "
            f"evidence_id {prior_evidence_id!r} — a run filed under another row cannot "
            "be bound as this row's prior stage"
        )
    prior_outcome = prior_manifest.get("execution", {}).get("outcome", "UNKNOWN")
    if prior_outcome != "ALL_SELECTED_TESTS_GREEN":
        raise HarnessError(
            f"--prior-stage-run {evidence_id}/{run_id}: prior outcome is "
            f"{prior_outcome!r} — a stage that did not pass cannot support a staged "
            "L1 ∧ L2 claim (VER:171)"
        )
    prior_commit = (
        prior_baseline.get("design1_5_1", {})
        .get("item_1_repository_and_package", {})
        .get("git_commit_sha", "UNKNOWN")
    )
    return {
        "evidence_id": evidence_id,
        "run_id": run_id,
        "stage": prior_manifest.get("evidence_level_stage", "UNKNOWN"),
        "sha256sums_digest": sha256_file(sums),
        "artifacts_reverified": sorted(listed),
        "baseline_commit_sha": prior_commit,
        "baseline_matches_this_run": prior_commit == this_commit_sha,
        "outcome": prior_outcome,
        "reconcile_note": reconcile_note or "UNSPECIFIED",
    }


def read_register_row(repo_root: Path, evidence_id: str, csv_path: str) -> dict:
    path = repo_root / csv_path
    if not path.is_file():
        raise HarnessError(f"evidence register not found: {path}")
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if row["evidence_id"] == evidence_id:
                return row
    raise HarnessError(
        f"evidence id {evidence_id!r} is not in {csv_path} — refusing to produce "
        "evidence for an unregistered item"
    )


# ============================================================================
# baseline construction
# ============================================================================


def _field(status: str, value: object = None, reason: str | None = None) -> dict:
    out: dict = {"status": status}
    if value is not None:
        out["value"] = value
    if reason is not None:
        out["reason"] = reason
    return out


_NA_TEMPLATE_ONLY = (
    "No instance artifact exists in the corpus (template only under "
    "tos-spec/src/part-1-foundation/verification/); an EV-L1 model/property run "
    "consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER §3)."
)

_NA_TEMPLATE_ONLY_L2 = (
    "No instance artifact exists in the corpus (template only under "
    "tos-spec/src/part-1-foundation/verification/); a pure-model EV-L2 "
    "component-fault run consumes none — it injects faults into a single "
    "in-process component and inspects that component's own authoritative "
    "verdict. Recorded N/A per design #1 §5.1 read forward to EV-L2 "
    "(EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its "
    "reason are retained, only the stage attribution changes."
)


_NA_TEMPLATE_ONLY_L3 = (
    "No instance artifact exists in the corpus (template only under "
    "tos-spec/src/part-1-foundation/verification/); an EV-L3 crash/restart run "
    "on a real local persistence substrate and a real process boundary consumes "
    "none — its send boundary is a MODELLED marker (zero real bytes, zero real "
    "orders), so no broker, authority/human, network or recovery instance is "
    "brought into existence. Recorded N/A per design #1 §5.1 read forward to "
    "EV-L3 (EV-L3 pilot design §6.3): the field, its N/A status and its reason "
    "are retained, only the stage attribution changes."
)


def na_status_for(stage: str) -> str:
    """The N/A token for ``stage`` (design §6.2 M2 — the note is updated, not deleted)."""
    if stage == STAGE_L1:
        return NOT_APPLICABLE
    if stage == STAGE_L3:
        return NOT_APPLICABLE_L3
    return NOT_APPLICABLE_L2


def unmet_ver3_fields(ver3: dict) -> list[str]:
    """The VER §3 baseline fields this run does **not** fully satisfy, by name.

    VER-002-001 §3 line 109 — "A run without a complete baseline is invalid" — carries no
    "as applicable" clause, unlike §7 line 258. The gap is therefore kept structurally
    enumerable rather than described in prose: a reader (and the harness self-test) can
    check that the list is non-empty without substring-matching a sentence, and the list
    itself names exactly which of the 22 fields are outstanding (design §6.2 M2 canary).
    """
    return sorted(name for name, entry in ver3.items() if entry["status"] != RECORDED)


def build_ver3_baseline(
    *,
    commit_sha: str,
    doc_digests: list[dict],
    environment: dict,
    harness: dict,
    seed_policy: dict,
    register_row: dict,
    profile_digest: dict,
    stage: str = STAGE_L1,
    fault_schedule: dict | None = None,
) -> dict:
    """The 22 VER §3 fields, in specification order (:86-107).

    Every field is present. A field is either ``RECORDED`` with a measured
    value, ``PARTIAL_EV_L1``, or the stage's N/A token with a reason. No
    field is silently dropped and none is fabricated.

    At ``EV-L2`` two things change and nothing is removed: the N/A token becomes
    ``NOT_APPLICABLE_PURE_MODEL_L2`` (design §6.2 M2), and
    ``fault_injection_schedule_and_seed`` — ``PARTIAL_EV_L1`` with a deferred fault
    schedule at EV-L1 — is completed with the real schedule summary.
    """
    na = na_status_for(stage)
    template_only = {
        STAGE_L1: _NA_TEMPLATE_ONLY,
        STAGE_L2: _NA_TEMPLATE_ONLY_L2,
        STAGE_L3: _NA_TEMPLATE_ONLY_L3,
    }[stage]
    if fault_schedule is None:
        fault_field = _field(
            PARTIAL,
            {
                "fault_schedule": _field(
                    na,
                    reason=(
                        "Fault injection begins at EV-L2 (VER §5); design #1 §5.1 "
                        "adds the §9.1 fault schedule on EV-L2 entry."
                    ),
                ),
                "seed": seed_policy,
            },
        )
    else:
        fault_field = _field(
            RECORDED,
            {"fault_schedule": fault_schedule, "seed": seed_policy},
            reason=(
                f"{stage}: the VER §9.1 append-only "
                + ("crash schedule" if stage == STAGE_L3 else "fault schedule")
                + " and the seed are both recorded. This field is no longer PARTIAL — "
                f"it is the one VER §3 field the {stage} stage completes relative to "
                "EV-L1."
            ),
        )
    return {
        "repository_commit_sha": _field(RECORDED, commit_sha),
        "build_artifact_digest": _field(
            na,
            reason=(
                "Phase 1 executes from the source tree; no built distribution "
                "artifact is produced or consumed (design #1 §5.1 items 1/4 — the "
                "git digest stands in). The executed bytes are pinned individually "
                "by design1_5_1.item_1_repository_and_package.target_file_digests."
            ),
        ),
        "rfc_adr_versions": _field(
            RECORDED,
            doc_digests,
            reason=(
                "The corpus documents carry no separate version field; their "
                "content sha256 is the version identity."
            ),
        ),
        "hard_safety_envelope_version": _field(na, reason=template_only),
        "runtime_safety_profile_version": _field(na, reason=template_only),
        "human_authority_policy_generation_and_digest": _field(
            na, reason=template_only
        ),
        "effective_principal_graph_generation_and_digest": _field(
            na, reason=template_only
        ),
        "evidence_integrity_policy_generation_and_digest": _field(
            na, reason=template_only
        ),
        "recovery_barrier_policy_generation_and_digest": _field(
            na, reason=template_only
        ),
        "critical_input_policy_generation_and_digest": _field(na, reason=template_only),
        "venue_constraint_policy_generation_and_digest": _field(
            na, reason=template_only
        ),
        "trading_approval_policy_generation_and_digest": _field(
            na, reason=template_only
        ),
        "currentness_policy_generation_and_digest": _field(na, reason=template_only),
        "restricted_live_trial_policy_generation_and_digest": _field(
            na, reason=template_only
        ),
        "broker_capability_profile_version": _field(
            na,
            reason=(
                "Evidence Register broker_capability_profile_version for this row "
                f"= {register_row.get('broker_capability_profile_version', '')!r}; "
                "the row's minimum evidence level "
                f"({register_row.get('minimum_evidence_level', '')}) carries no "
                "+Broker suffix and no Broker Capability Profile instance exists "
                "(template only). P0-2 is not in this run's scope."
            ),
        ),
        "verification_profile_version": _field(
            RECORDED,
            {
                "version": VERIFICATION_PROFILE_VERSION,
                "register_column_value": register_row.get(
                    "verification_profile_version", ""
                ),
                "artifact": profile_digest,
                "approval_state": "PROPOSED — P0-1 (bounds approval) OPEN",
            },
            reason=(
                "Recorded, not approved. VER §6 numeric bounds remain unapproved; "
                "no bound value is consumed by this run (bounds are hypothesis-"
                "injected, not hardcoded)."
            ),
        ),
        "database_schema_migration_version": _field(
            na,
            reason=(
                # At EV-L3 the earlier reason would be false: a persistence substrate
                # IS exercised. The field stays N/A for a different, stated reason —
                # the pilot store is a fixed single-table schema created on open, with
                # no migration history and no versioned schema artifact, and it is
                # explicitly NOT the ADR-002-005 §4 line 61 project persistence
                # decision (EV-L3 pilot design §3.3, still an open gate).
                "The EV-L3 pilot exercises a real local persistence substrate "
                "(stdlib sqlite3, WAL, synchronous=FULL) whose schema is a single "
                "fixed table created on open: there is no migration history and no "
                "versioned schema artifact to record. This substrate is a "
                "PILOT-SCOPE choice, NOT the ADR-002-005 §4 line 61 project "
                "persistence-technology decision, which remains open."
                if stage == STAGE_L3
                else (
                    "EV-L1 model/property verification exercises no persistence "
                    "substrate; durable persistence is the deferred /2 stage."
                )
            ),
        ),
        "deployment_manifest_digest": _field(
            na,
            reason=(
                "Nothing is deployed: the kernel is non-transmitting and is "
                "executed in-process by pytest."
            ),
        ),
        "workload_identities_and_key_versions": _field(
            na,
            reason=(
                "No workload identity, credential, or key material is used — the "
                "run is hermetic (no network, no .env, no clock authority)."
            ),
        ),
        "environment_identifier": _field(RECORDED, environment),
        "test_harness_version": _field(RECORDED, harness),
        "fault_injection_schedule_and_seed": fault_field,
    }


def build_baseline(
    *,
    args: argparse.Namespace,
    repo_root: Path,
    run_id: str,
    commit_sha: str,
    short_sha: str,
    nodes: list[tuple[str, str]],
    target_digests: list[dict],
    worktree_before: dict,
    worktree_after: dict,
    probe: dict,
    pins: dict[str, str],
    register_row: dict,
    harness: dict,
    seed_policy: dict,
    config_artifacts: list[dict],
    stage: str = STAGE_L1,
    fault_schedule: dict | None = None,
) -> dict:
    installed = probe["installed"]
    drift = [
        {"distribution": name, "pinned": pins[name], "installed": installed.get(name)}
        for name in sorted(pins)
        if name in installed and installed[name] != pins[name]
    ]

    doc_digests = []
    for label, rel in (
        ("primary_adr", args.primary_adr_path),
        ("design_document", args.design_doc),
        ("ver_specification", VER_SPEC_PATH),
        ("boundary_design_1", DESIGN_1_PATH),
    ):
        if not rel:
            continue
        path = repo_root / rel
        if path.is_file():
            doc_digests.append(
                {"role": label, "path": rel, "sha256": sha256_file(path)}
            )
        else:
            doc_digests.append({"role": label, "path": rel, "sha256": "FILE_ABSENT"})

    environment = {
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "python_implementation": probe["python"]["implementation"],
    }
    profile_path = repo_root / PROFILE_YAML_PATH
    profile_digest = (
        {"path": PROFILE_YAML_PATH, "sha256": sha256_file(profile_path)}
        if profile_path.is_file()
        else {"path": PROFILE_YAML_PATH, "sha256": "FILE_ABSENT"}
    )
    ver3 = build_ver3_baseline(
        commit_sha=commit_sha,
        doc_digests=doc_digests,
        environment=environment,
        harness=harness,
        seed_policy=seed_policy,
        register_row=register_row,
        profile_digest=profile_digest,
        stage=stage,
        fault_schedule=fault_schedule,
    )
    if stage == STAGE_L3:
        # Same M2 discipline as EV-L2: the note is UPDATED, not deleted. What changes
        # at EV-L3 is only which absences remain — persistence and the process boundary
        # are now real, so they are no longer among them.
        completeness = (
            "EV-L3 integrated crash/restart. VER §3 requires 22 baseline fields and "
            "states that 'A run without a complete baseline is invalid' (line 109) — a "
            "clause carrying no 'as applicable' qualifier, unlike §7 line 258, so it "
            "stands beside P0-1 and the independent signature as a gate, not a "
            "waivable formality. The unmet-field list and every reason are retained "
            f"with the stage attribution updated ({NOT_APPLICABLE} -> "
            f"{NOT_APPLICABLE_L3}); the enumerated list is "
            "ver_002_001_section_3_unmet_fields below. This stage DOES bring a real "
            "local persistence substrate and a real OS process boundary into "
            "existence; what remains absent is the transport and everything hanging "
            "off it — the broker, authority/human, network and recovery instances — "
            "because the send boundary is a MODELLED marker emitting zero real bytes "
            "and zero real orders (residuals R-N / R-I). Under VER §3's full standard "
            "this baseline is NOT complete."
        )
    elif stage == STAGE_L1:
        completeness = (
            "EV-L1 subset. VER §3 requires 22 baseline fields and states that "
            "'A run without a complete baseline is invalid'; design #1 §5.1 "
            "ratifies the seven items below as the EV-L1 subset. Fields whose "
            "artifacts do not exist at this stage are marked "
            f"{NOT_APPLICABLE} with a reason. Under VER §3's full standard "
            "this baseline is complete for EV-L1 only and is NOT a complete "
            "baseline for EV-L2 and above."
        )
    else:
        # design §6.2 M2: the EV-L1 note is UPDATED, not deleted. The unmet-field
        # list and every reason are retained; only the stage attribution changes.
        completeness = (
            "EV-L2 component-fault. VER §3 requires 22 baseline fields and states "
            "that 'A run without a complete baseline is invalid' (line 109) — a "
            "clause carrying no 'as applicable' qualifier, unlike §7 line 258, so "
            "it stands beside P0-1 and the independent signature as a gate, not a "
            "waivable formality. The unmet-field list and every reason are retained "
            f"from EV-L1 with the stage attribution updated ({NOT_APPLICABLE} -> "
            f"{NOT_APPLICABLE_L2}); the enumerated list is "
            "ver_002_001_section_3_unmet_fields below. The absent artifacts are the "
            "broker, authority/human, reconciliation, network and recovery "
            "instances — none of which a pure-model, single-component, "
            "non-transmitting fault run brings into existence. Under VER §3's full "
            "standard this baseline is NOT complete."
        )
    baseline_schema_version = {STAGE_L1: "v1", STAGE_L2: "v2", STAGE_L3: "v3"}[stage]
    return {
        "schema": f"tos-evidence/baseline/{baseline_schema_version}",
        "run_id": run_id,
        "evidence_id": args.evidence_id,
        "evidence_level_stage": stage,
        "generated_utc": _utc_now().isoformat(),
        "contract": {
            "run_manifest_contract": f"{DESIGN_1_PATH} §5.1 (seven items)",
            "ver_specification": f"{VER_SPEC_PATH} §2.3/§3/§8/§9.1/§9.2/§9.5",
            "completeness": completeness,
        },
        "evidence_register_row": {
            # the register actually read by THIS run (``--register-csv``; default
            # REGISTER_CSV_PATH) — never a constant, so the recorded provenance
            # cannot claim a file the run did not read
            "source": args.register_csv,
            "evidence_id": register_row.get("evidence_id"),
            "domain": register_row.get("domain"),
            "title": register_row.get("title"),
            "primary_adr": register_row.get("primary_adr"),
            "criticality": register_row.get("criticality"),
            "minimum_evidence_level": register_row.get("minimum_evidence_level"),
            "status_at_run_time": register_row.get("status"),
            "implementation_owner": register_row.get("implementation_owner"),
            "evidence_owner": register_row.get("evidence_owner"),
            "independent_reviewer": register_row.get("independent_reviewer"),
        },
        # ---- design #1 §5.1 — the seven items -------------------------------
        "design1_5_1": {
            "item_1_repository_and_package": {
                "git_commit_sha": commit_sha,
                "git_short_sha": short_sha,
                "tos_package_version": read_tos_package_version(repo_root),
                "worktree": worktree_before,
                "worktree_after_run": worktree_after,
                "worktree_delta": worktree_delta(worktree_before, worktree_after),
                "target_files_clean": all(
                    d["git_clean"] for d in target_digests if d["cleanliness_guarded"]
                ),
                "target_files_stable_during_run": all(
                    d["status"] == "STABLE_DURING_RUN" for d in target_digests
                ),
                "target_file_digests": target_digests,
            },
            "item_2_interpreter_and_dependencies": {
                "python": probe["python"],
                "installed_versions_measured": installed,
                "pinned_in_tos_pyproject": pins,
                "pins_satisfied": not drift,
                "pin_vs_installed_drift": drift,
                "drift_note": (
                    "pins_satisfied is the machine-readable claim; an empty drift "
                    "list = the executed interpreter matches every pin. A non-empty "
                    "list is recorded, not resolved: the installed version is what "
                    "executed."
                ),
            },
            "item_3_execution_environment": environment,
            "item_4_harness_version": harness,
            "item_5_seed_policy": seed_policy,
            "item_6_consumed_configuration_artifacts": (
                config_artifacts
                if config_artifacts
                else _field(
                    na_status_for(stage),
                    reason=(
                        "No configuration artifact is consumed: bounds are "
                        "hypothesis-injected generated values, not read from a "
                        "profile, and the run is hermetic (no .env, no YAML)."
                    ),
                )
            ),
            "item_7_retained_artifact_digests": (
                f"Enumerated in {MANIFEST_NAME} (artifacts) and closed over by "
                f"{SHA256SUMS_NAME}, which is written last and covers every "
                "retained file including the manifest."
            ),
        },
        # ---- VER §3 — all 22 fields ----------------------------------------
        "ver_002_001_section_3_baseline": ver3,
        # The §3 gap, enumerable rather than described (design §6.2 M2 canary).
        "ver_002_001_section_3_unmet_fields": unmet_ver3_fields(ver3),
        "ver_002_001_section_3_unmet_note": (
            "VER §3 line 109 ('A run without a complete baseline is invalid') has no "
            "'as applicable' clause. This list names every field that is not RECORDED, "
            "so the gap is machine-checkable: an empty list would be the claim that the "
            "baseline is complete, and this run does not make that claim."
        ),
        "test_nodes": [n for n, _ in nodes],
    }


# ============================================================================
# execution
# ============================================================================


def build_seed_policy(policy: str) -> tuple[dict, list[str]]:
    """Resolve ``--seed-policy`` to (recorded policy, extra pytest flags).

    ``default``    hypothesis default entropy (per-run random seeds).
    ``fixed:<int>``pass ``--hypothesis-seed=<int>`` (the hypothesis pytest
                   plugin option) so the run is seed-reproducible.
    """
    if policy == "default":
        return (
            {
                "policy": "default",
                "pytest_flags": [],
                "hypothesis_seed": "UNPINNED (per-run entropy)",
                "note": (
                    "VER §9.1 append-only: this policy is recorded as executed. "
                    "A failing example is reproducible via the @reproduce_failure "
                    "blob hypothesis prints, not via a run-level seed."
                ),
            },
            [],
        )
    if policy.startswith("fixed:"):
        raw = policy.split(":", 1)[1]
        try:
            seed = int(raw)
        except ValueError as exc:
            raise HarnessError(f"--seed-policy fixed:<int> — bad int {raw!r}") from exc
        return (
            {
                "policy": "fixed",
                "pytest_flags": [f"--hypothesis-seed={seed}"],
                "hypothesis_seed": seed,
                "note": "VER §9.1 append-only: seed pinned before the run began.",
            },
            [f"--hypothesis-seed={seed}"],
        )
    raise HarnessError(f"unknown --seed-policy {policy!r} (use default | fixed:<int>)")


def run_pytest(
    *,
    python: Path,
    repo_root: Path,
    nodes: list[str],
    junit_path: Path,
    log_path: Path,
    extra_flags: list[str],
) -> dict:
    command = [
        str(python),
        "-m",
        "pytest",
        *nodes,
        "-q",
        f"--junitxml={junit_path}",
        *extra_flags,
    ]
    env_overrides = {"PYTHONPATH": "tos/src", "PYTHONHASHSEED": "0"}
    env = dict(os.environ)
    env.update(env_overrides)

    started_wall = _utc_now()
    started_mono = time.monotonic()
    proc = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    duration = time.monotonic() - started_mono
    finished_wall = _utc_now()

    with open(log_path, "x", encoding="utf-8") as fh:
        fh.write(f"$ PYTHONPATH=tos/src PYTHONHASHSEED=0 {' '.join(command)}\n\n")
        fh.write("--- stdout ---\n")
        fh.write(proc.stdout)
        fh.write("\n--- stderr ---\n")
        fh.write(proc.stderr)
        fh.write(f"\n--- return code: {proc.returncode} ---\n")

    return {
        "command": command,
        "cwd": str(repo_root),
        "env_overrides": env_overrides,
        "started_utc": started_wall.isoformat(),
        "finished_utc": finished_wall.isoformat(),
        "monotonic_duration_s": round(duration, 6),
        "return_code": proc.returncode,
    }


def parse_junit(path: Path) -> dict:
    if not path.is_file():
        return {"status": "JUNIT_ABSENT"}
    root = ET.parse(path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        return {"status": "JUNIT_UNPARSEABLE"}

    def _int(name: str) -> int:
        try:
            return int(suite.get(name, "0"))
        except ValueError:
            return 0

    return {
        "tests": _int("tests"),
        "failures": _int("failures"),
        "errors": _int("errors"),
        "skipped": _int("skipped"),
        "time_s": suite.get("time"),
    }


# ============================================================================
# output
# ============================================================================


def dump_yaml(data: dict) -> str:
    return yaml.safe_dump(
        data, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100
    )


def write_exclusive(path: Path, text: str) -> None:
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(text)


def create_run_directory(run_dir: Path, evidence_root: Path | None = None) -> None:
    """Append-only (VER §9.1): an existing run directory is never reopened.

    ``evidence_root`` (when given) is a containment check: an evidence id
    carrying ``..`` or an absolute path must not place a run package outside the
    evidence store.
    """
    if evidence_root is not None:
        root = evidence_root.resolve()
        resolved = run_dir.resolve()
        if root != resolved and root not in resolved.parents:
            raise HarnessError(
                f"run directory {resolved} escapes the evidence root {root} — "
                "refusing (check --evidence-id for path separators)"
            )
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise HarnessError(
            f"append-only violation: run directory already exists: {run_dir}. "
            "Existing runs are immutable; start a new run instead."
        ) from exc


#: A ``path/to/file.py:12`` or ``file.md:3,9`` citation inside a mapping basis.
BASIS_CITATION = re.compile(r"([A-Za-z0-9_\-./]+\.(?:py|md)):(\d+(?:,\d+)*)")

#: Where a bare-basename citation may be resolved from. Deliberately narrow: a basis
#: citing ``predicates.py`` is ambiguous across the kernel, and an ambiguous citation is
#: not evidence, so it must be written with its path.
BASIS_SEARCH_ROOTS = ("tos/src", "tos/tests", "docs/plans", "tos-spec/src")


def _basis_file_index(repo_root: Path) -> dict[str, list[Path]]:
    """Index candidate citation targets by basename **and** by repo-relative path."""
    index: dict[str, list[Path]] = {}
    for rel in BASIS_SEARCH_ROOTS:
        base = repo_root / rel
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.suffix not in (".py", ".md") or "__pycache__" in path.parts:
                continue
            index.setdefault(path.name, []).append(path)
            index.setdefault(str(path.relative_to(repo_root)), []).append(path)
    return index


def _selector_line_span(path: Path, selector: str) -> tuple[int, int] | None:
    """The ``[first, last]`` source lines of the test the node selector names.

    ``selector`` is the part of a pytest node id after ``::`` (``TestClass::test_x`` or
    ``test_x``); the last component is the function. Returns ``None`` when the file does
    not parse or the function is not found — an unknown span cannot constrain anything.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return None
    wanted = selector.split("::")[-1].split("[")[0]
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == wanted
        ):
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            return start, (node.end_lineno or node.lineno)
    return None


def verify_basis_citations(repo_root: Path, nodes: list[tuple[str, str]]) -> list[dict]:
    """Re-measure every ``file:line`` citation in the mapping bases (design v1.2 N3).

    A mapping basis is the *measured reason* a test node belongs to an evidence row, so a
    citation inside it is a load-bearing claim about the executed source — not decoration.
    Bases are supplied on the command line and are routinely copied forward from a previous
    run, which is exactly how they go stale: an independent review measured a re-executed
    L1 stage whose basis still cited pre-hardening line numbers that had since drifted onto
    unrelated docstring lines. The run recorded them as its mapping evidence anyway.

    Every citation is therefore resolved against the source on disk. A line past EOF, a
    blank line, or a basename that resolves to more than one file is a defect: an ambiguous
    citation cannot be checked, and an unchecked citation is indistinguishable from a
    fabricated one.

    One sharper case is also caught. When the node id carries a ``::selector`` and the
    citation points at that same file, the cited line must fall inside that test's own
    source span — this is the drift that survives every existence check, because the stale
    line still exists and still holds real code, just somebody else's. That is exactly the
    shape the independent review found.

    **Limitation, stated rather than papered over**: a citation into a *different* file
    that has drifted onto an unrelated but non-blank line cannot be detected here, because
    the harness has no way to know what the line was supposed to say. Existence,
    unambiguity, and node-scope containment are the mechanically checkable floor; they do
    not make a citation true.

    Returns:
        One record per defective citation (empty when every citation resolves).
    """
    index = _basis_file_index(repo_root)
    defects: list[dict] = []
    for node, basis in nodes:
        node_path, _, selector = node.partition("::")
        for name, numbers in BASIS_CITATION.findall(basis):
            candidates = index.get(name, [])
            if len(candidates) != 1:
                defects.append(
                    {
                        "node": node,
                        "citation": f"{name}:{numbers}",
                        "defect": (
                            "AMBIGUOUS_BASENAME" if candidates else "UNRESOLVABLE_FILE"
                        ),
                        "candidates": sorted(
                            str(c.relative_to(repo_root)) for c in candidates
                        ),
                    }
                )
                continue
            target = candidates[0]
            source = target.read_text(encoding="utf-8").splitlines()
            # Only constrain scope when the citation is about the very test the node
            # selects; a citation into any other file is out of this check's reach.
            span = (
                _selector_line_span(target, selector)
                if selector and target == (repo_root / node_path).resolve()
                else None
            )
            for number in (int(n) for n in numbers.split(",")):
                if not 1 <= number <= len(source):
                    defects.append(
                        {
                            "node": node,
                            "citation": f"{name}:{number}",
                            "defect": "PAST_EOF",
                            "file_lines": len(source),
                        }
                    )
                elif not source[number - 1].strip():
                    defects.append(
                        {
                            "node": node,
                            "citation": f"{name}:{number}",
                            "defect": "CITES_A_BLANK_LINE",
                        }
                    )
                elif span is not None and not span[0] <= number <= span[1]:
                    defects.append(
                        {
                            "node": node,
                            "citation": f"{name}:{number}",
                            "defect": "OUTSIDE_THE_SELECTED_TEST",
                            "selected_test_span": f"{span[0]}-{span[1]}",
                            "cited_line": source[number - 1].strip()[:80],
                        }
                    )
    return defects


def write_traceability(
    path: Path,
    *,
    evidence_id: str,
    primary_adr: str,
    design_doc: str,
    nodes: list[tuple[str, str]],
) -> None:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "evidence_id",
            "primary_adr",
            "design_document",
            "test_node",
            "mapping_basis",
            "evidence_claim",
        ]
    )
    for node, basis in nodes:
        writer.writerow(
            [
                evidence_id,
                primary_adr,
                design_doc,
                node,
                basis,
                "STAGE_RECORD_ONLY (does not close the evidence item)",
            ]
        )
    write_exclusive(path, buf.getvalue())


def write_sha256sums(run_dir: Path) -> Path:
    """Digest every retained file. A subdirectory would silently escape it."""
    subdirs = [p.name for p in sorted(run_dir.iterdir()) if p.is_dir()]
    if subdirs:
        raise HarnessError(
            f"run directory contains subdirectories {subdirs}: sha256sums.txt is "
            "flat, so their contents would be retained without a digest "
            "(VER §9.2 requires a digest for every retained artifact)"
        )
    path = run_dir / SHA256SUMS_NAME
    lines = [
        f"{sha256_file(p)}  {p.name}\n"
        for p in sorted(run_dir.iterdir())
        if p.is_file() and p.name != SHA256SUMS_NAME
    ]
    write_exclusive(path, "".join(lines))
    return path


# ============================================================================
# CLI
# ============================================================================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "EV-L1 evidence run harness (design #1 §5.1 run manifest; "
            "VER-002-001 §3/§8/§9). Produces an append-only run package; "
            "never moves an Evidence Register row to PASS."
        )
    )
    parser.add_argument("--evidence-id", required=True, help="e.g. STATE-EV-001")
    parser.add_argument(
        "--node",
        action="append",
        default=[],
        metavar="'NODE | mapping basis'",
        help="pytest node id, optionally followed by '| <measured mapping basis>'",
    )
    parser.add_argument(
        "--nodes-file",
        type=Path,
        default=None,
        help="file with one '<node> | <basis>' per line (# comments allowed)",
    )
    parser.add_argument(
        "--source-path",
        action="append",
        default=[],
        help="source file or directory whose .py files are digested into the baseline",
    )
    parser.add_argument("--primary-adr", default="", help="e.g. ADR-002-005")
    parser.add_argument(
        "--primary-adr-path", default="", help="repo-relative path of the ADR document"
    )
    parser.add_argument(
        "--design-doc", default="", help="repo-relative path of the design document"
    )
    parser.add_argument(
        "--seed-policy",
        default="default",
        help="default | fixed:<int> (hypothesis seed policy — append-only record)",
    )
    parser.add_argument(
        "--config-artifact",
        action="append",
        default=[],
        help="repo-relative configuration artifact consumed by the run (digested)",
    )
    parser.add_argument(
        "--evidence-level-stage",
        default=STAGE_L1,
        choices=list(STAGES),
        help=(
            "the stage this run executes. EV-L2 emits the manifest/v2 superset "
            "(prior_stage_runs + fault_injection + coverage_argument) and passes the "
            "append-only fault-schedule sink to pytest; EV-L3 emits the manifest/v3 "
            "superset (adds integration_boundary + crash_injection) and passes the "
            "append-only crash-schedule sink instead"
        ),
    )
    parser.add_argument(
        "--fault-catalog-ref",
        default="",
        help=(
            "the ratified catalog this run executes, e.g. "
            f"'{EVL2_DESIGN_PATH}#3' at EV-L2 or '{EVL3_DESIGN_PATH}#4' at EV-L3 "
            "(required for both staged levels)"
        ),
    )
    parser.add_argument(
        "--modeled-axis",
        action="append",
        default=[],
        metavar="'axis | disposition | residual-ref | note'",
        help=(
            "an EV-L3 axis this stage MODELS or DEFERS rather than exercises "
            "(EV-L3 only; repeatable). The residual ref is mandatory: an axis "
            "declared without one withholds GREEN, so a modelled boundary can never "
            "be recorded as a real one"
        ),
    )
    parser.add_argument(
        "--prior-stage-run",
        action="append",
        default=[],
        metavar="'EVIDENCE-ID/run-id | reconcile note'",
        help=(
            "an earlier stage run this stage builds on; bound by its sha256sums.txt "
            "digest and baseline commit (EV-L2 only; repeatable)"
        ),
    )
    parser.add_argument(
        "--expected-fault-count",
        type=int,
        default=None,
        help=(
            "the number of catalog entries the ratified catalog defines for this row "
            "(faults at EV-L2, crash scenarios at EV-L3; required for both). The "
            "schedule is recounted and must match, so deselecting one cannot shrink "
            "the evidence unnoticed"
        ),
    )
    parser.add_argument(
        "--covered-axis",
        default="",
        help=(
            "the exact axis this stage covers, stated by the operator (EV-L2 only; "
            "required for EV-L2 — the harness never infers a coverage claim)"
        ),
    )
    parser.add_argument(
        "--supersedes-run-id",
        action="append",
        default=[],
        help=(
            "a run id this package supersedes (EV-L2 only; repeatable). The superseded "
            "package is RETAINED unmodified (VER §2.2 / design §9 gate 6); this records "
            "the forward pointer"
        ),
    )
    parser.add_argument(
        "--residual-ref",
        action="append",
        default=[],
        help=(
            "a VER §378 residual this run does NOT evidence (EV-L2 only; repeatable). "
            "Pointers, never a union — VER:3308"
        ),
    )
    parser.add_argument("--evidence-root", type=Path, default=None)
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--python", type=Path, default=None)
    parser.add_argument("--register-csv", default=REGISTER_CSV_PATH)
    parser.add_argument(
        "--allow-dirty-targets",
        action="store_true",
        help="record and proceed when an executed file is dirty (default: refuse)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    harness_path = Path(__file__).resolve()
    repo_root = (args.repo_root or harness_path.parent.parent).resolve()

    stage = args.evidence_level_stage
    is_l2 = stage == STAGE_L2
    is_l3 = stage == STAGE_L3
    #: The staged levels share the "this claim is not measurable, state it" argument
    #: surface (catalog ref, covered axis, prior stage, catalog size).
    is_staged = is_l2 or is_l3

    try:
        nodes = [parse_node_spec(spec) for spec in args.node]
        if args.nodes_file:
            nodes.extend(read_nodes_file(args.nodes_file))
        if not nodes:
            raise HarnessError("no test nodes given (--node / --nodes-file)")

        # EV-L2 preconditions. Each of these is a *claim* the harness cannot measure —
        # which catalog is being executed, which axis is covered, which prior stage this
        # builds on — so it is required as an explicit argument rather than defaulted.
        # The measurable parts (fault counts, hardening, baseline identity) are measured.
        if is_staged:
            if not args.fault_catalog_ref.strip():
                raise HarnessError(
                    f"--fault-catalog-ref is required for an {stage} stage run: an "
                    "unattributed schedule cannot be checked against a catalog"
                )
            if not args.covered_axis.strip():
                raise HarnessError(
                    f"--covered-axis is required for an {stage} stage run: the "
                    "harness never infers what a stage covers"
                )
            if not args.prior_stage_run:
                raise HarnessError(
                    f"--prior-stage-run is required for an {stage} stage run: a "
                    "staged row (VER:171) needs its prior stage(s) bound, not assumed"
                )
            if args.expected_fault_count is None:
                raise HarnessError(
                    f"--expected-fault-count is required for an {stage} stage run: "
                    "without the catalog size, a deselected entry shrinks the "
                    "schedule while every remaining row still reads MET"
                )
            if args.expected_fault_count <= 0:
                raise HarnessError(
                    "--expected-fault-count must be positive: a catalog of zero "
                    "entries cannot evidence anything (design §0.5-2)"
                )
        else:
            for flag, value in (
                ("--fault-catalog-ref", args.fault_catalog_ref),
                ("--covered-axis", args.covered_axis),
                ("--prior-stage-run", args.prior_stage_run),
                ("--residual-ref", args.residual_ref),
                ("--expected-fault-count", args.expected_fault_count),
                ("--supersedes-run-id", args.supersedes_run_id),
            ):
                if value:
                    raise HarnessError(
                        f"{flag} is a staged-level option; this run is "
                        f"--evidence-level-stage {stage}"
                    )
        if is_l3:
            # The modelled/deferred axes are a claim about what this stage did NOT
            # exercise. Requiring them explicitly is what keeps an EV-L3 record from
            # reading as if all three of VER §5's boundaries had been real.
            if not args.modeled_axis:
                raise HarnessError(
                    "--modeled-axis is required for an EV-L3 stage run: VER §5 line "
                    "151-153 defines EV-L3 by real persistence, identity AND network "
                    "boundaries, so every axis this pilot models or defers must be "
                    "declared with the residual that carries it"
                )
        elif args.modeled_axis:
            raise HarnessError(
                "--modeled-axis is an EV-L3 option; this run is "
                f"--evidence-level-stage {stage}"
            )
        modeled_axes = [parse_modeled_axis_spec(spec) for spec in args.modeled_axis]

        for node, _ in nodes:
            if not (repo_root / node_file(node)).is_file():
                raise HarnessError(f"test node file does not exist: {node_file(node)}")

        # A mapping basis is measured evidence, so its citations are re-measured here
        # rather than trusted. Bases are hand-supplied and routinely carried forward
        # between runs, which is how they go stale (an independent review caught exactly
        # that). Refuse before the run: a package whose traceability cites lines that no
        # longer hold the cited code is worse than no package.
        basis_defects = verify_basis_citations(repo_root, nodes)
        if basis_defects:
            detail = "; ".join(
                f"{d['node']} -> {d['citation']} [{d['defect']}]" for d in basis_defects
            )
            raise HarnessError(
                "mapping-basis citations do not resolve against the executed source "
                f"({len(basis_defects)} defective): {detail}. Re-measure them; a stale "
                "file:line is a fabricated mapping claim, and an ambiguous basename "
                "cannot be checked at all (write the repo-relative path)."
            )

        register_row = read_register_row(repo_root, args.evidence_id, args.register_csv)
        commit_sha = _git(repo_root, "rev-parse", "HEAD")
        short_sha = _git(repo_root, "rev-parse", "--short", "HEAD")
        worktree_before = worktree_status(repo_root)
        dirty = worktree_before["all_dirty_paths"]

        target_files: list[Path] = []
        for node, _ in nodes:
            target_files.append(repo_root / node_file(node))
        for src in args.source_path:
            path = repo_root / src
            if not path.exists():
                raise HarnessError(f"--source-path does not exist: {src}")
            target_files.extend(iter_py_files(path))
        guarded_rels = sorted({str(p.relative_to(repo_root)) for p in target_files})

        dirty_targets = [rel for rel in guarded_rels if is_dirty_target(rel, dirty)]
        if dirty_targets and not args.allow_dirty_targets:
            raise HarnessError(
                "executed files are not clean at HEAD — the recorded commit would "
                f"not describe the executed bytes: {dirty_targets}. Commit them or "
                "pass --allow-dirty-targets (the dirt is then recorded in-band)."
            )

        # The harness watches itself: it is digested and mutation-checked like any
        # executed file, but exempt from the cleanliness REFUSAL — its provenance
        # is recorded honestly (harness_tracked / harness_at_commit) instead of
        # being asserted against a commit that may not contain it.
        harness_rel = str(harness_path.relative_to(repo_root))
        watched_rels = sorted({*guarded_rels, harness_rel})
        pre_digests = collect_digests(repo_root, watched_rels)

        python = args.python or (repo_root / ".venv" / "bin" / "python")
        if not python.is_file():
            python = Path(sys.executable)
        probe = probe_interpreter(python)
        pins = read_pinned_dependencies(repo_root)
        seed_policy, seed_flags = build_seed_policy(args.seed_policy)

        config_artifacts = []
        for rel in args.config_artifact:
            path = repo_root / rel
            if not path.is_file():
                raise HarnessError(f"--config-artifact does not exist: {rel}")
            config_artifacts.append({"path": rel, "sha256": sha256_file(path)})

        run_id = f"{_utc_now().strftime('%Y%m%dT%H%M%SZ')}-{short_sha}"
        evidence_root = args.evidence_root or (repo_root / "tos-evidence")
        run_dir = evidence_root / args.evidence_id / run_id

        # Bind the prior stage(s) BEFORE creating this run directory, so a bad
        # reference fails without leaving an orphan package behind.
        prior_stage_runs = [
            bind_prior_stage_run(
                evidence_root, *parse_prior_stage_spec(spec), commit_sha
            )
            for spec in args.prior_stage_run
        ]
        create_run_directory(run_dir, evidence_root)

        fault_timeline_path = run_dir / FAULT_TIMELINE_NAME
        crash_timeline_path = run_dir / CRASH_TIMELINE_NAME
        extra_flags = list(seed_flags)
        if is_l2:
            extra_flags.append(f"--l2-fault-timeline={fault_timeline_path}")
        if is_l3:
            extra_flags.append(f"--l3-crash-timeline={crash_timeline_path}")

        try:
            execution = run_pytest(
                python=python,
                repo_root=repo_root,
                nodes=[n for n, _ in nodes],
                junit_path=run_dir / JUNIT_NAME,
                log_path=run_dir / RUNLOG_NAME,
                extra_flags=extra_flags,
            )
            junit = parse_junit(run_dir / JUNIT_NAME)

            # TOCTOU: re-observe the executed bytes and the worktree AFTER the run.
            post_digests = collect_digests(repo_root, watched_rels)
            worktree_after = worktree_status(repo_root)
        except Exception:
            # A half-written package must announce itself; an unmarked partial
            # directory would read as a completed run whose files went missing.
            write_exclusive(
                run_dir / INCOMPLETE_MARKER_NAME,
                "INCOMPLETE RUN — the harness raised before the package was "
                "closed. This directory is NOT an evidence package: no manifest, "
                "baseline, or sha256sums may be assumed present or correct. It is "
                "retained (append-only) as the record that a run was attempted.\n",
            )
            raise

        target_digests = digest_report(
            pre_digests, post_digests, dirty, guarded_rels=guarded_rels
        )
        harness = harness_provenance(
            repo_root, harness_path, worktree_before, probe["installed"].get("pytest")
        )

        fault_injection: dict | None = None
        if is_l2:
            hardening = check_l1_hardening(repo_root)
            fault_injection = {
                "catalog_ref": args.fault_catalog_ref,
                "seed": seed_policy.get("hypothesis_seed"),
                "seed_pinned": seed_policy.get("policy") == "fixed",
                **summarise_fault_schedule(
                    read_fault_timeline(fault_timeline_path),
                    expected_fault_count=args.expected_fault_count,
                    evidence_id=args.evidence_id,
                ),
                "l1_hardening_prereq_met": hardening["met"],
                "l1_hardening_prereq": hardening,
            }

        crash_injection: dict | None = None
        integration_boundary: dict | None = None
        if is_l3:
            crash_rows = read_crash_timeline(crash_timeline_path)
            substrate = check_persistence_substrate(repo_root)
            schedule = summarise_crash_schedule(
                crash_rows,
                expected_scenario_count=args.expected_fault_count,
                evidence_id=args.evidence_id,
            )
            # persistence_real is the CONJUNCTION of a run-time measurement and a
            # source property: what one execution observed on the filesystem, AND that
            # the component cannot be an in-memory database in the first place. Either
            # alone is satisfiable by an implementation that is not really durable.
            persistence_real = bool(
                schedule["persistence_real_measured"] and substrate["met"]
            )
            crash_injection = {
                "catalog_ref": args.fault_catalog_ref,
                "seed": seed_policy.get("hypothesis_seed"),
                "seed_pinned": seed_policy.get("policy") == "fixed",
                **schedule,
                "persistence_real": persistence_real,
                "persistence_substrate_check": substrate,
            }
            integration_boundary = {
                "persistence": {
                    "technology": (
                        "stdlib sqlite3 WAL, synchronous=FULL (PILOT-SCOPE; NOT the "
                        "ADR-002-005 §4 line 61 project persistence-technology "
                        "decision, which remains an open gate)"
                    ),
                    "real_on_disk": persistence_real,
                    "substrate_source": substrate.get("path"),
                    "substrate_check": substrate,
                    "measured_store_bytes": sorted(
                        {
                            row.get("store_bytes")
                            for row in crash_rows
                            if isinstance(row.get("store_bytes"), int)
                        }
                    ),
                },
                "process_boundary": {
                    "writer_pids": [row.get("writer_pid") for row in crash_rows],
                    "reader_pids": [row.get("reader_pid") for row in crash_rows],
                    "distinct_per_scenario": schedule["process_boundary_real"],
                    "crash_mechanism": (
                        "deterministic os._exit at a parametrized crash point (not a "
                        "racy externally delivered SIGKILL)"
                    ),
                    "observed_crash_exit_statuses": sorted(
                        {
                            row.get("crash_exit_status")
                            for row in crash_rows
                            if row.get("crash_exit_status") is not None
                        }
                    ),
                    "crash_points": schedule["crash_points"],
                },
                "modeled_axes": modeled_axes,
                # design §6.2 gate 5, as a directly readable boolean beside the list it
                # summarises — a reader should not have to re-derive the gate's input.
                "modeled_axis_residual_declared": bool(modeled_axes)
                and all(axis["residual_ref"] for axis in modeled_axes),
                "modeled_axes_note": (
                    "An axis listed here was NOT exercised as a real boundary by this "
                    "stage; each carries the §378 residual that holds it. VER §5 line "
                    "151-153 defines EV-L3 by real persistence, identity and network "
                    "boundaries — this run realizes persistence, the process boundary "
                    "and logical identity re-derivation only."
                ),
            }

        baseline = build_baseline(
            args=args,
            repo_root=repo_root,
            run_id=run_id,
            commit_sha=commit_sha,
            short_sha=short_sha,
            nodes=nodes,
            target_digests=target_digests,
            worktree_before=worktree_before,
            worktree_after=worktree_after,
            probe=probe,
            pins=pins,
            register_row=register_row,
            harness=harness,
            seed_policy=seed_policy,
            config_artifacts=config_artifacts,
            stage=stage,
            # VER §3's ``fault_injection_schedule_and_seed`` is one field for the whole
            # notion of injected faults; at EV-L3 the injection is a crash schedule, so
            # that is what completes it. Emitting the field as PARTIAL while a real
            # schedule existed would understate the baseline.
            fault_schedule=crash_injection if is_l3 else fault_injection,
        )
        write_exclusive(run_dir / BASELINE_NAME, dump_yaml(baseline))
        write_traceability(
            run_dir / TRACEABILITY_NAME,
            evidence_id=args.evidence_id,
            primary_adr=args.primary_adr or register_row.get("primary_adr", ""),
            design_doc=args.design_doc,
            nodes=nodes,
        )

        outcome = classify_outcome(execution["return_code"], junit)
        green = outcome == "ALL_SELECTED_TESTS_GREEN"
        mutated = [
            d["path"] for d in target_digests if d["status"] != "STABLE_DURING_RUN"
        ]

        # ---- EV-L2 stage gates (each measured, none self-reported) -----------
        # The gates are kept in their OWN field: overwriting execution.outcome would
        # erase whether the tests themselves passed, so a gated run and a run whose
        # tests actually failed would become indistinguishable.
        stage_gates: list[str] = []
        if is_l2:
            assert fault_injection is not None
            if not fault_injection["all_faults_met"]:
                stage_gates.append("FAULT_SCHEDULE_NOT_ALL_MET")
            if not fault_injection["l1_hardening_prereq_met"]:
                stage_gates.append("L1_HARDENING_PREREQ_UNMET")
            if not fault_injection["seed_pinned"]:
                # VER §9.1 makes the seed part of the append-only run record; an
                # unpinned seed makes the fault schedule unreproducible.
                stage_gates.append("SEED_NOT_PINNED")
            if not any(
                prior["stage"] == STAGE_L1 and prior["baseline_matches_this_run"]
                for prior in prior_stage_runs
            ):
                # design §6.2 M9: an EV-L1 run at a different baseline is stale, so the
                # staged L1 ∧ L2 claim would assert both stages describe the same code.
                stage_gates.append("NO_PRIOR_EV_L1_RUN_AT_THIS_BASELINE")
            if stage_gates:
                green = False

        # ---- EV-L3 stage gates (EV-L3 pilot design §6.2, six of them) --------
        if is_l3:
            assert crash_injection is not None
            if not crash_injection["all_crash_scenarios_met"]:
                stage_gates.append("CRASH_SCHEDULE_NOT_ALL_MET")
            if not crash_injection["process_boundary_real"]:
                # A writer and reader sharing a pid is an in-process fallback wearing
                # EV-L3's name; VER §5 line 151-153 is about real boundaries.
                stage_gates.append("PROCESS_BOUNDARY_NOT_REAL")
            if not crash_injection["persistence_real"]:
                # The EV-L2 pilot's C1 finding was a durable claim satisfied in memory.
                stage_gates.append("PERSISTENCE_NOT_REAL")
            if not crash_injection["seed_pinned"]:
                stage_gates.append("SEED_NOT_PINNED")
            bound_stages = {
                prior["stage"]
                for prior in prior_stage_runs
                if prior["evidence_id"] == L3_PRIOR_STAGE_EVIDENCE_ID
                and prior["baseline_matches_this_run"]
            }
            if not set(L3_REQUIRED_PRIOR_STAGES) <= bound_stages:
                # design §6.2 gate 4 (NIT-2 naming): BOTH prior stages of
                # STATE-EV-001 must be bound at THIS baseline. This is not
                # STATE-EV-004's own staging requirement — its minimum level is
                # EV-L3 alone — it is the durable-limb continuity that lets the L3
                # evidence discharge STATE-EV-001's R-1 against a non-stale model base.
                stage_gates.append("PRIOR_EV_L1_AND_L2_NOT_BOTH_BOUND_AT_THIS_BASELINE")
            assert integration_boundary is not None
            if not integration_boundary["modeled_axis_residual_declared"]:
                stage_gates.append("MODELED_AXIS_RESIDUAL_NOT_DECLARED")
            if stage_gates:
                green = False

        artifacts = [
            {
                "name": p.name,
                "sha256": sha256_file(p),
                "bytes": p.stat().st_size,
            }
            for p in sorted(run_dir.iterdir())
            if p.is_file()
        ]
        discipline_tag = {
            STAGE_L1: DISCIPLINE_TAG,
            STAGE_L2: DISCIPLINE_TAG_L2,
            STAGE_L3: DISCIPLINE_TAG_L3,
        }[stage]
        manifest_schema_version = {STAGE_L1: "v1", STAGE_L2: "v2", STAGE_L3: "v3"}[
            stage
        ]
        _stage_token = stage.upper().replace("-", "_")
        # v2 is a strict SUPERSET of v1 and v3 a strict superset of v2 (design §6.2 N8 /
        # EV-L3 §6.1): every earlier field below is retained unchanged at the higher
        # stage; the newer field groups are added around them.
        manifest = {
            "schema": f"tos-evidence/manifest/{manifest_schema_version}",
            "run_id": run_id,
            "evidence_id": args.evidence_id,
            "primary_adr": args.primary_adr or register_row.get("primary_adr", ""),
            "design_document": args.design_doc,
            "evidence_level_stage": stage,
            "discipline_tag": discipline_tag,
            "claim": {
                "closes_evidence_item": False,
                "register_status_moved_by_this_run": False,
                "register_status_at_run_time": register_row.get("status"),
                "minimum_evidence_level": register_row.get(
                    "minimum_evidence_level", ""
                ),
                "independent_review": "NOT_SIGNED (VER §9.5)",
                "p0_1_bounds_approval": "OPEN",
                "verification_profile_version": VERIFICATION_PROFILE_VERSION,
                "target_integrity": (
                    "STABLE_DURING_RUN" if not mutated else "MUTATED_DURING_RUN"
                ),
                "mutated_during_run": mutated,
                "note": (
                    "This document records that named tests executed at the "
                    "recorded baseline. It asserts no acceptance, no PASS, and no "
                    "coverage of the higher stages the row's minimum level names."
                ),
                # A gated run makes NO stage or coverage claim: emitting
                # stages_executed / covered_axis regardless would state that both
                # stages stand and that the axis is covered, which is exactly what the
                # unmet gate denies. The withheld claim is named instead.
                **(
                    {
                        # ev_l2_stage_gates_unmet / ev_l3_stage_gates_unmet — the block
                        # is named for the stage that owns it, so a v3 manifest never
                        # reports its gates under the v2 field name.
                        f"{_stage_token.lower()}_stage_gates_unmet": stage_gates,
                        **(
                            {
                                "stages_executed": (
                                    [STAGE_L1, STAGE_L2]
                                    if is_l2
                                    else [STAGE_L1, STAGE_L2, STAGE_L3]
                                ),
                                "stages_executed_note": (
                                    "EV-L1 is executed as its own run package and "
                                    "bound here by prior_stage_runs; this package is "
                                    "the EV-L2 stage."
                                    if is_l2
                                    else (
                                        "EV-L1 and EV-L2 are executed as their own run "
                                        "packages and bound here by prior_stage_runs; "
                                        "this package is the EV-L3 stage."
                                    )
                                ),
                                "covered_axis": args.covered_axis,
                            }
                            if not stage_gates
                            else {
                                "stages_executed": (
                                    f"WITHHELD ({stage} stage gate unmet)"
                                ),
                                "covered_axis": (
                                    f"WITHHELD ({stage} stage gate unmet) — the axis "
                                    "this run was invoked for is recorded in "
                                    "invoked_covered_axis; it is NOT claimed as covered."
                                ),
                                "invoked_covered_axis": args.covered_axis,
                            }
                        ),
                    }
                    if is_staged
                    else {}
                ),
            },
            **(
                {
                    "prior_stage_runs": prior_stage_runs,
                    # design §9 gate 6 / VER §2.2: a failed or gated run package is
                    # PRESERVED, never deleted or overwritten. When a later run replaces
                    # one, it names it here with the reason, so the superseded package
                    # stays discoverable instead of being quietly orphaned.
                    "supersedes_run_id": list(args.supersedes_run_id),
                    "supersedes_note": (
                        "Superseded packages are retained unmodified (VER §2.2); this "
                        "field is the forward pointer, not a deletion record."
                    ),
                    **({"fault_injection": fault_injection} if is_l2 else {}),
                    **(
                        {
                            "integration_boundary": integration_boundary,
                            "crash_injection": crash_injection,
                        }
                        if is_l3
                        else {}
                    ),
                    "coverage_argument": {
                        "specification": (
                            f"{VER_SPEC_PATH} §2.7 (line 76-78) — a finite set of "
                            "executed evidence cases does not by itself discharge a "
                            "universally-quantified safety claim. Both this row's "
                            "Expected clauses are universally quantified, so the "
                            "coverage argument is mandatory."
                        ),
                        "boundary_values": (
                            COVERAGE_BOUNDARY_VALUES_L3
                            if is_l3
                            else COVERAGE_BOUNDARY_VALUES
                        ),
                        "adverse_scenario_set": COVERAGE_ADVERSE_SCENARIO_SET,
                        "unexercised_residual_ref": list(args.residual_ref),
                        "unexercised_residual_note": COVERAGE_RESIDUAL_NOTE,
                        "discharged": False,
                        "discharged_note": (
                            "The adversarial-combination leg cannot be discharged "
                            "while ADR-002-021 is PROPOSED, and an unresolved "
                            "applicability question defaults to APPLICABLE (VER §2.4 "
                            "line 64-66; VER:173 'Missing resolution is a blocker and "
                            "SHALL NOT default to the lowest level'). This run "
                            "therefore records the argument's state; it does not "
                            "claim to have made it."
                        ),
                    },
                }
                if is_staged
                else {}
            ),
            "execution": {
                **execution,
                # The test result, preserved verbatim: SELECTED_TESTS_NOT_GREEN and
                # NO_TEST_EXECUTED stay visible even when a stage gate also fires.
                "outcome": outcome,
                "junit_summary": junit,
                **(
                    {
                        "stage_gate_outcome": (
                            f"{_stage_token}_STAGE_GATE_UNMET[{','.join(stage_gates)}]"
                            if stage_gates
                            else f"{_stage_token}_STAGE_GATES_MET"
                        )
                    }
                    if is_staged
                    else {}
                ),
            },
            "test_nodes": [n for n, _ in nodes],
            "baseline": {
                "file": BASELINE_NAME,
                "sha256": sha256_file(run_dir / BASELINE_NAME),
                "completeness": (
                    f"EV-L1 subset (design #1 §5.1); VER §3 fields without an "
                    f"existing artifact are {NOT_APPLICABLE}."
                    if not is_staged
                    else (
                        "NOT complete (VER §3 line 109 has no 'as applicable' "
                        f"clause). VER §3 fields without an existing artifact are "
                        f"{na_status_for(stage)}; the unmet set is enumerated in "
                        "baseline.yaml::ver_002_001_section_3_unmet_fields."
                    )
                ),
                "ver3_unmet_field_count": len(
                    baseline["ver_002_001_section_3_unmet_fields"]
                ),
            },
            "artifacts": artifacts,
            "artifact_closure_note": (
                f"{MANIFEST_NAME} cannot contain its own digest; {SHA256SUMS_NAME} "
                "is written last and closes over every retained file including "
                "this manifest (VER §9.2)."
            ),
        }
        write_exclusive(run_dir / MANIFEST_NAME, dump_yaml(manifest))
        write_sha256sums(run_dir)

    except HarnessError as exc:
        print(f"tos-evidence-run: ERROR — {exc}", file=sys.stderr)
        return 2

    print(f"tos-evidence-run: wrote {run_dir}")
    print(
        f"  outcome={manifest['execution']['outcome']} rc={execution['return_code']} "
        f"junit={junit}"
    )
    if is_l2 and fault_injection is not None:
        print(
            f"  stage={stage} faults={fault_injection['fault_count']} "
            f"all_faults_met={fault_injection['all_faults_met']} "
            f"l1_hardening={fault_injection['l1_hardening_prereq_met']}"
        )
    if is_l3 and crash_injection is not None:
        print(
            f"  stage={stage} crashes={crash_injection['crash_scenario_count']} "
            f"all_crash_scenarios_met={crash_injection['all_crash_scenarios_met']} "
            f"process_boundary_real={crash_injection['process_boundary_real']} "
            f"persistence_real={crash_injection['persistence_real']}"
        )
    if is_staged and stage_gates:
        print(f"  {stage} stage gates UNMET: {stage_gates}", file=sys.stderr)
    print(f"  {manifest['discipline_tag']}")
    if mutated:
        print(
            "tos-evidence-run: ERROR — executed files changed DURING the run "
            f"{mutated}: the baseline does not describe the bytes that ran. The "
            "package is retained and marked MUTATED_DURING_RUN.",
            file=sys.stderr,
        )
        return 2
    return 0 if green else 1


if __name__ == "__main__":
    sys.exit(main())
