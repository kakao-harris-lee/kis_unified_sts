#!/usr/bin/env python3
"""EV-L1 evidence run harness — design #1 §5.1 run-manifest contract (7 items).

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
carries the discipline tag in ``DISCIPLINE_TAG``.

Layout produced (VER §8-equivalent, run-scoped)::

    tos-evidence/<EVIDENCE-ID>/<run-id>/
        manifest.yaml       run metadata + result + discipline tag
        baseline.yaml       design #1 §5.1 seven items + VER §3 22 fields
        traceability.csv    EV-ID -> ADR -> design document -> test node
        junit.xml           pytest --junitxml output
        run.log             captured stdout+stderr of the pytest invocation
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
import csv
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import time
import tomllib
import xml.etree.ElementTree as ET
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

#: The Verification Profile is PROPOSED, not approved — P0-1 is open. Recorded
#: verbatim so no downstream reader can mistake it for an approved profile.
VERIFICATION_PROFILE_VERSION = "2.1 (PROPOSED — P0-1 open)"

NOT_APPLICABLE = "NOT_APPLICABLE_EV_L1"
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
SHA256SUMS_NAME = "sha256sums.txt"
INCOMPLETE_MARKER_NAME = "INCOMPLETE_RUN.txt"


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


def build_ver3_baseline(
    *,
    commit_sha: str,
    doc_digests: list[dict],
    environment: dict,
    harness: dict,
    seed_policy: dict,
    register_row: dict,
    profile_digest: dict,
) -> dict:
    """The 22 VER §3 fields, in specification order (:86-107).

    Every field is present. A field is either ``RECORDED`` with a measured
    value, ``PARTIAL_EV_L1``, or ``NOT_APPLICABLE_EV_L1`` with a reason. No
    field is silently dropped and none is fabricated.
    """
    return {
        "repository_commit_sha": _field(RECORDED, commit_sha),
        "build_artifact_digest": _field(
            NOT_APPLICABLE,
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
        "hard_safety_envelope_version": _field(
            NOT_APPLICABLE, reason=_NA_TEMPLATE_ONLY
        ),
        "runtime_safety_profile_version": _field(
            NOT_APPLICABLE, reason=_NA_TEMPLATE_ONLY
        ),
        "human_authority_policy_generation_and_digest": _field(
            NOT_APPLICABLE, reason=_NA_TEMPLATE_ONLY
        ),
        "effective_principal_graph_generation_and_digest": _field(
            NOT_APPLICABLE, reason=_NA_TEMPLATE_ONLY
        ),
        "evidence_integrity_policy_generation_and_digest": _field(
            NOT_APPLICABLE, reason=_NA_TEMPLATE_ONLY
        ),
        "recovery_barrier_policy_generation_and_digest": _field(
            NOT_APPLICABLE, reason=_NA_TEMPLATE_ONLY
        ),
        "critical_input_policy_generation_and_digest": _field(
            NOT_APPLICABLE, reason=_NA_TEMPLATE_ONLY
        ),
        "venue_constraint_policy_generation_and_digest": _field(
            NOT_APPLICABLE, reason=_NA_TEMPLATE_ONLY
        ),
        "trading_approval_policy_generation_and_digest": _field(
            NOT_APPLICABLE, reason=_NA_TEMPLATE_ONLY
        ),
        "currentness_policy_generation_and_digest": _field(
            NOT_APPLICABLE, reason=_NA_TEMPLATE_ONLY
        ),
        "restricted_live_trial_policy_generation_and_digest": _field(
            NOT_APPLICABLE, reason=_NA_TEMPLATE_ONLY
        ),
        "broker_capability_profile_version": _field(
            NOT_APPLICABLE,
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
            NOT_APPLICABLE,
            reason=(
                "EV-L1 model/property verification exercises no persistence "
                "substrate; durable persistence is the deferred /2 stage."
            ),
        ),
        "deployment_manifest_digest": _field(
            NOT_APPLICABLE,
            reason=(
                "Nothing is deployed: the kernel is non-transmitting and is "
                "executed in-process by pytest."
            ),
        ),
        "workload_identities_and_key_versions": _field(
            NOT_APPLICABLE,
            reason=(
                "No workload identity, credential, or key material is used — the "
                "run is hermetic (no network, no .env, no clock authority)."
            ),
        ),
        "environment_identifier": _field(RECORDED, environment),
        "test_harness_version": _field(RECORDED, harness),
        "fault_injection_schedule_and_seed": _field(
            PARTIAL,
            {
                "fault_schedule": _field(
                    NOT_APPLICABLE,
                    reason=(
                        "Fault injection begins at EV-L2 (VER §5); design #1 §5.1 "
                        "adds the §9.1 fault schedule on EV-L2 entry."
                    ),
                ),
                "seed": seed_policy,
            },
        ),
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
    return {
        "schema": "tos-evidence/baseline/v1",
        "run_id": run_id,
        "evidence_id": args.evidence_id,
        "generated_utc": _utc_now().isoformat(),
        "contract": {
            "run_manifest_contract": f"{DESIGN_1_PATH} §5.1 (seven items)",
            "ver_specification": f"{VER_SPEC_PATH} §2.3/§3/§8/§9.1/§9.2/§9.5",
            "completeness": (
                "EV-L1 subset. VER §3 requires 22 baseline fields and states that "
                "'A run without a complete baseline is invalid'; design #1 §5.1 "
                "ratifies the seven items below as the EV-L1 subset. Fields whose "
                "artifacts do not exist at this stage are marked "
                f"{NOT_APPLICABLE} with a reason. Under VER §3's full standard "
                "this baseline is complete for EV-L1 only and is NOT a complete "
                "baseline for EV-L2 and above."
            ),
        },
        "evidence_register_row": {
            "source": REGISTER_CSV_PATH,
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
                    NOT_APPLICABLE,
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
        "ver_002_001_section_3_baseline": build_ver3_baseline(
            commit_sha=commit_sha,
            doc_digests=doc_digests,
            environment=environment,
            harness=harness,
            seed_policy=seed_policy,
            register_row=register_row,
            profile_digest=profile_digest,
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

    try:
        nodes = [parse_node_spec(spec) for spec in args.node]
        if args.nodes_file:
            nodes.extend(read_nodes_file(args.nodes_file))
        if not nodes:
            raise HarnessError("no test nodes given (--node / --nodes-file)")

        for node, _ in nodes:
            if not (repo_root / node_file(node)).is_file():
                raise HarnessError(f"test node file does not exist: {node_file(node)}")

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
        create_run_directory(run_dir, evidence_root)

        try:
            execution = run_pytest(
                python=python,
                repo_root=repo_root,
                nodes=[n for n, _ in nodes],
                junit_path=run_dir / JUNIT_NAME,
                log_path=run_dir / RUNLOG_NAME,
                extra_flags=seed_flags,
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
        artifacts = [
            {
                "name": p.name,
                "sha256": sha256_file(p),
                "bytes": p.stat().st_size,
            }
            for p in sorted(run_dir.iterdir())
            if p.is_file()
        ]
        manifest = {
            "schema": "tos-evidence/manifest/v1",
            "run_id": run_id,
            "evidence_id": args.evidence_id,
            "primary_adr": args.primary_adr or register_row.get("primary_adr", ""),
            "design_document": args.design_doc,
            "evidence_level_stage": "EV-L1",
            "discipline_tag": DISCIPLINE_TAG,
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
            },
            "execution": {
                **execution,
                "outcome": outcome,
                "junit_summary": junit,
            },
            "test_nodes": [n for n, _ in nodes],
            "baseline": {
                "file": BASELINE_NAME,
                "sha256": sha256_file(run_dir / BASELINE_NAME),
                "completeness": (
                    f"EV-L1 subset (design #1 §5.1); VER §3 fields without an "
                    f"existing artifact are {NOT_APPLICABLE}."
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
    print(f"  {DISCIPLINE_TAG}")
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
