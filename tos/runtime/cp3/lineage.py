"""The ADR-002-018 §10 lineage block and the artifact writer.

Part of the CP-3 B1b runner (``cp3`` package). The runner was one module until the
2026-10-08 review: at 1,820 lines it broke ``config/tos_size_budget.yaml``'s
1,000-line module cap and its 100-line function cap three times over, and
registering four day-one exceptions against a budget whose own header calls
registration "가시성, 면허가 아니라" would have been the wrong answer for NEW code.
So the module was decomposed along the seams it already had, and
``tos/runtime/cp3`` was added to that budget's ``scope`` so the caps are actually
enforced here (the review's fourth gate).

Firewall: ``tos.*`` + ``tos_runtime.*`` + stdlib + ``pyyaml`` only. No
``shared.*``, no clock, no RNG, no ``subprocess``, no network. Intra-package
imports are RELATIVE — the allowlist does not name ``cp3``, so an absolute
``import cp3.…`` from a file under ``tos/`` is a TOS-FW-A violation while a
relative import carries no absolute name for the gate to classify.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sqlite3
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tos.canonical import EV_L1_PROVISIONAL_VERSION
from tos.dsl.context_value import VALUE_NAMESPACE
from tos_runtime.operations.dependency_admission import observe_source_tree_digest

from . import __version__ as CP3_VERSION
from ._base import LINEAGE_SCHEMA_VERSION, SCHEME
from .contract import FIELD_POLICY, REQUIRED_FIELD_KEYS
from .differences import DECLARED_DIFFERENCES
from .replay import PROVISIONAL_TIME_BOUNDS, RunArtifacts
from .strategy import LoadedStrategyContent

__all__ = ["build_lineage", "write_artifacts"]

# ===========================================================================
# Artifacts
# ===========================================================================


def _sha256_file(path: Path) -> str:
    """The sha256 of a file's bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


#: Directory names ``observe_source_tree_digest`` prunes, mirrored so this
#: package's digest and the installed-tree digest are computed over the same
#: notion of "a source file" (``dependency_admission._SKIP_DIR_NAMES``).
_SKIP_DIR_NAMES: frozenset[str] = frozenset({"__pycache__"})


def _cp3_code_digest() -> str:
    """This package's own source digest — EVERY ``*.py`` under it.

    An ``rglob`` with the same skip set and the same canonical scheme
    ``tos_runtime.operations.dependency_admission.observe_source_tree_digest``
    uses, so the two digests in the lineage block are commensurable.

    It walks the tree rather than naming files (2026-10-08 review item 17): the
    previous revision hashed a hardcoded ``("__init__.py", "runner.py")`` list,
    which was already wrong the moment the module was decomposed into siblings
    and would have silently stopped covering new code — the
    "registry with an unpinned satellite" shape this repo has been bitten by.
    Tests ARE included: they are part of what the package is, and excluding them
    would make the digest unable to see a weakened assertion.
    """
    root = Path(__file__).resolve().parent
    entries = [
        [path.relative_to(root).as_posix(), _sha256_file(path)]
        for path in sorted(root.rglob("*.py"))
        if not any(part in _SKIP_DIR_NAMES for part in path.parts)
    ]
    digest = SCHEME.compute_digest({"files": entries})
    assert isinstance(digest, str)
    return digest


def _git_identity() -> dict[str, Any]:
    """The repo coordinates of the tree this artifact was produced from.

    Read from ``.git`` **directly**, never through ``git``: ``subprocess`` is in
    the firewall's ``FORBIDDEN_STDLIB`` for BOTH scopes
    (``tools/tos_firewall_check.py``; the RUNTIME carve-out adds only
    ``socket``/``ssl``/``http``/``urllib.request``), so shelling out is not an
    option here — which is fine, because the three facts wanted are all plain
    files. ``dirty`` is the honest hard part: without ``git status`` there is no
    cheap exact answer, so it is derived by comparing the index's mtime/size
    stat cache against the worktree for tracked paths, and reported as
    ``"UNKNOWN"`` rather than ``false`` when that cannot be determined — a
    guessed ``false`` on a dirty tree is the failure mode worth avoiding
    (2026-10-08 review item 9).
    """
    root = Path(__file__).resolve()
    for candidate in root.parents:
        if (candidate / ".git").exists():
            repo_root = candidate
            break
    else:
        return {"repo_root": None, "commit": None, "branch": None, "dirty": "UNKNOWN"}
    git_dir = repo_root / ".git"
    if git_dir.is_file():  # a LINKED worktree: ".git" is a pointer file
        pointer = git_dir.read_text(encoding="utf-8").strip()
        prefix = "gitdir: "
        git_dir = (
            Path(pointer[len(prefix) :]) if pointer.startswith(prefix) else git_dir
        )
    # In a linked worktree HEAD and index are per-worktree but REFS live in the
    # shared common dir, named by ``commondir`` (measured: without this, commit
    # read as None in exactly the worktree this artifact is produced from).
    refs_dir = git_dir
    try:
        common = (git_dir / "commondir").read_text(encoding="utf-8").strip()
    except OSError:
        common = ""
    if common:
        candidate = Path(common)
        refs_dir = candidate if candidate.is_absolute() else (git_dir / candidate)
        refs_dir = refs_dir.resolve()
    branch: str | None = None
    commit: str | None = None
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        head = ""
    if head.startswith("ref: "):
        ref = head[len("ref: ") :].strip()
        # Strip the NAMESPACE, not everything before the last slash: a branch
        # named ``feat/tos-cp3-b1b-tos-runner`` reported as
        # ``tos-cp3-b1b-tos-runner`` by an rpartition is simply the wrong branch
        # name (measured on this very branch).
        branch = ref[len("refs/heads/") :] if ref.startswith("refs/heads/") else ref
        loose = refs_dir / ref
        if loose.is_file():
            commit = loose.read_text(encoding="utf-8").strip() or None
        else:
            commit = _packed_ref(refs_dir, ref)
    elif head:
        commit = head  # detached HEAD
    return {
        "repo_root": str(repo_root),
        "commit": commit,
        "branch": branch,
        "dirty": _worktree_dirty(repo_root, git_dir),
    }


def _packed_ref(git_dir: Path, ref: str) -> str | None:
    """Resolve ``ref`` out of ``packed-refs`` (a freshly-cloned or gc'd repo)."""
    try:
        text = (git_dir / "packed-refs").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("#") or " " not in line:
            continue
        sha, _, name = line.partition(" ")
        if name.strip() == ref:
            return sha.strip()
    return None


def _worktree_dirty(repo_root: Path, git_dir: Path) -> bool | str:
    """Whether any tracked file differs from the index, or ``"UNKNOWN"``.

    Parses ``.git/index`` v2/v3 (stdlib ``struct``) and compares each entry's
    recorded size and mtime against the worktree. That is the same cheap check
    ``git status`` starts from; it can report a false ``True`` for a file whose
    content was rewritten identically with a new mtime, which is the SAFE
    direction. Anything it cannot read at all returns ``"UNKNOWN"``.
    """
    index_path = git_dir / "index"
    try:
        blob = index_path.read_bytes()
    except OSError:
        return "UNKNOWN"
    if len(blob) < 12 or blob[:4] != b"DIRC":
        return "UNKNOWN"
    version, count = struct.unpack(">II", blob[4:12])
    if version not in (2, 3):
        return "UNKNOWN"
    offset = 12
    for _ in range(count):
        if offset + 62 > len(blob):
            return "UNKNOWN"
        mtime_s, mtime_ns = struct.unpack(">II", blob[offset + 8 : offset + 16])
        size = struct.unpack(">I", blob[offset + 36 : offset + 40])[0]
        name_end = blob.index(b"\x00", offset + 62)
        name = blob[offset + 62 : name_end].decode("utf-8", "replace")
        entry_len = name_end - offset + 1
        offset += entry_len + ((8 - (entry_len % 8)) % 8 or 0)
        if version == 3:
            pass  # extended flags are inside the 62-byte prefix already handled
        path = repo_root / name
        try:
            stat = path.stat()
        except OSError:
            return True  # tracked file deleted
        if int(stat.st_size) != size:
            return True
        if int(stat.st_mtime) != mtime_s or (
            mtime_ns and int(stat.st_mtime_ns % 1_000_000_000) != mtime_ns
        ):
            return True
    return False


def _runtime_identity() -> dict[str, Any]:
    """Interpreter + library coordinates (review item 9 / #875 items 14/17).

    Without these, a 3.12 run and a 3.11 run of the same inputs produced
    byte-identical lineage — the artifact could not evidence what executed it.
    ``sqlite3.sqlite_version`` is included because the sibling
    ``observe_dependency_set_digest`` covers it, so the two stay comparable.
    """
    return {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "sqlite": sqlite3.sqlite_version,
        "pydantic": _distribution_version("pydantic"),
        "tos": _distribution_version("tos"),
        "tos_runtime": _distribution_version("tos-runtime"),
    }


def _distribution_version(name: str) -> str | None:
    """An installed distribution's version, or ``None`` when it is not installed.

    ``None`` is a real answer here: this package runs from ``PYTHONPATH`` as
    often as from an install, and inventing a version for an uninstalled
    distribution would be a phantom.
    """
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _counts_block(*, artifacts: RunArtifacts) -> dict[str, Any]:
    """What the run actually produced, counted."""
    run = artifacts.run
    return {
        "bars_read": artifacts.bars_read,
        "bars_driven": artifacts.bars_driven,
        "bars_consumed_reported": artifacts.bars_consumed_reported,
        "events_yielded": run.events_yielded,
        "trace_entries": len(run.trace.entries),
        "trace_lines": len(artifacts.trace_lines),
        "outcome_kinds": dict(artifacts.outcome_counts),
        "rule_fires": dict(artifacts.rule_fire_counts),
        "capacity_denials": artifacts.capacity_denials,
        "halt_reasons": dict(artifacts.halt_counts),
        "handoffs": run.handoff_count,
        # Which bar(s) spent the order budget (B1b-D1). They are the first
        # firing(s) of ANY rule, which need NOT be entries. A list, because
        # the budget is the injected `max_unresolved_send_per_scope`.
        "realized_orders": [dict(order) for order in artifacts.realized_orders],
        "halt_records": len(run.halts),
        "fill_records": len(run.fill_records),
        "unsettled_fill_records": len(run.unsettled_fill_records),
    }


def _versions_block(
    *,
    content: LoadedStrategyContent,
    budget_steps: int,
    max_unresolved_send_per_scope: int,
) -> dict[str, Any]:
    """The governing versions, bounds and field policy this run consumed."""
    return {
        "canonicalization_version": EV_L1_PROVISIONAL_VERSION,
        "dsl_evaluation_budget_steps": budget_steps,
        "dsl_evaluation_budget_steps_source": (
            "config/tos_runtime/paper/engine.yaml::dsl_evaluation_budget_steps"
        ),
        "max_unresolved_send_per_scope": max_unresolved_send_per_scope,
        "policy_work_steps": content.work_steps,
        "value_namespace": VALUE_NAMESPACE,
        "field_policy": {key: dict(FIELD_POLICY[key]) for key in REQUIRED_FIELD_KEYS},
        "injected_time_bounds": {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in PROVISIONAL_TIME_BOUNDS.items()
        },
    }


def _parents_block(
    *,
    artifacts: RunArtifacts,
    content: LoadedStrategyContent,
    fields_path: Path,
    fields_lineage_path: Path | None,
) -> dict[str, Any]:
    """The exact parents this artifact was derived from (ADR-002-018 §10)."""
    return {
        "fields_jsonl": {
            "path": str(fields_path),
            "sha256": _sha256_file(fields_path),
            "lines": artifacts.bars_read,
            # The VALUE, not a pointer to it (2026-10-08 review item 5): a
            # lineage-only consumer must be able to learn the producer
            # identity from the block (ADR-002-018 §10 "exact parents"), and
            # `read_field_records` refuses a file that mixes two.
            "source_id": artifacts.source_id,
        },
        "fields_lineage_json": (
            None
            if fields_lineage_path is None
            else {
                "path": str(fields_lineage_path),
                "sha256": _sha256_file(fields_lineage_path),
            }
        ),
        "strategy_file": {
            "path": str(content.strategy_path),
            "sha256": content.strategy_sha256,
            "strategy_id": content.strategy.strategy_id,
            "canonical_digest": content.strategy.canonical_digest,
            "dsl_version": content.strategy.dsl_version,
            "config_binding_version": content.strategy.config_binding_version,
        },
        "strategy_bindings_file": {
            "path": str(content.bindings_path),
            "sha256": content.bindings_sha256,
            "bindings": dict(content.bindings),
        },
        "installed_code": {
            "source_tree_digest": observe_source_tree_digest(),
            "roots": ["tos/src/tos", "tos/runtime/src/tos_runtime"],
            "note": (
                "the SAME digest `tos_runtime.compose.cli print-digests` "
                "prints as expected_code_digest; cp3 adds zero bytes under "
                "either root, so this value is unchanged by B1b"
            ),
        },
    }


#: Why a match here corroborates the POLICY and not the band arithmetic.
_COMMON_MODE = (
    "This is NOT independent corroboration of the band math. The "
    "indicator fields this run compares are B1a's, produced by driving "
    "the ONE legacy implementation "
    "(shared/decision/setups/vwap_reversion.py); the TOS side evaluates "
    "a policy over them. What a match therefore corroborates is the "
    "POLICY, never the band arithmetic (ADR-002-018 §10: 'same function "
    "call' is a common mode, not independent confirmation)."
)


def _tool_block() -> dict[str, Any]:
    """What produced this artifact — identity, source digest, repo, interpreter."""
    return {
        "name": "tos/runtime/cp3/",
        "version": CP3_VERSION,
        "module": "cp3.runner",
        "code_digest": _cp3_code_digest(),
        "canonicalization_version": EV_L1_PROVISIONAL_VERSION,
        "git": _git_identity(),
        "runtime": _runtime_identity(),
    }


def _assurance_blocks(*, artifacts: RunArtifacts) -> dict[str, Any]:
    """The reconciliation / determinism / claims trio.

    One helper because the three are read together: what was checked, what makes
    the artifact reproducible, and what the run does and does not assert.
    """
    run = artifacts.run
    return {
        "reconciliation": {
            # NOT a pair of booleans. The previous revision recorded
            # `bars_read_equals_bars_driven` and `trace_lines_equals_bars_driven`,
            # which could not be False: `run_replay` already REFUSES
            # `len(lines) != len(records)`, and both counts derive from `lines`,
            # so every lineage that reaches disk had them `true` by construction
            # and the test asserting them asserted a tautology (2026-10-08 review
            # item 4). The refusal is the real check; what belongs here is the
            # numbers it compared and the statement of what was enforced.
            "bars_read": artifacts.bars_read,
            "bars_driven": artifacts.bars_driven,
            "trace_lines": len(artifacts.trace_lines),
            "enforced_by": (
                "run_replay refuses the run unless every record produced exactly "
                "one DECISION_TICK result AND every bar emitted an outcome; "
                "these three counts are therefore equal in any artifact that "
                "exists, and unequal counts are a refusal, never a false flag"
            ),
        },
        "determinism": {
            # "no CLOCK-DERIVED timestamp" — narrowed from the previous
            # "no_timestamps: true", which sat beside
            # `realized_orders[0].raw_event_id = "…20251208T084500+0900"` and was
            # therefore readable as false (2026-10-08 review item 16). B1a's
            # event ids and session tokens DO carry datetimes: they are input
            # data, reproduced verbatim, and are exactly what makes replay
            # comparable. What is absent is any value this process read from a
            # clock.
            "no_clock_derived_timestamp": True,
            "no_clock_reads": True,
            "no_rng": True,
            "datetime_bearing_inputs_reproduced_verbatim": [
                "parents.fields_jsonl.path",
                "counts.realized_orders[].raw_event_id",
                "dataset event ids and session tokens inside trace.jsonl",
            ],
            "note": (
                "every value in this block is a function of (fields.jsonl, "
                "strategy file, bindings file, injected bounds, installed "
                "code); two runs over the same inputs are byte-identical"
            ),
        },
        "claims": {
            "closes_no_ev": run.closes_no_ev,
            "label": run.label,
            "oracle_scope": "DECISION_AND_INTENT_LEVEL_ONLY",
            "performance_surface": (
                "ABSENT BY CONSTRUCTION — no Sharpe/PnL/return/edge field exists "
                "anywhere in tos.backtest's result types (design #33 §1.2 B1), "
                "so this run makes no performance claim"
            ),
        },
    }


def build_lineage(
    *,
    artifacts: RunArtifacts,
    content: LoadedStrategyContent,
    fields_path: Path,
    fields_lineage_path: Path | None,
    budget_steps: int,
    max_unresolved_send_per_scope: int,
) -> dict[str, Any]:
    """The ADR-002-018 §10 lineage block for this run — the same shape B1a emits.

    Parents, versions, counts, reconciliation, determinism, declared
    differences. **No timestamps and no wall-clock reads anywhere**: every value
    is a function of the inputs, so two runs over the same inputs produce a
    byte-identical block (that is the determinism claim, asserted by the
    suite's two-run test).

    Args:
        artifacts: The completed run's artifacts.
        content: The admitted strategy content.
        fields_path: B1a's ``fields.jsonl``.
        fields_lineage_path: B1a's ``lineage.json`` beside it, when present.
        budget_steps: The injected DSL budget.
        max_unresolved_send_per_scope: The injected send bound.

    Returns:
        The JSON-native lineage mapping.
    """
    return {
        "lineage_schema_version": LINEAGE_SCHEMA_VERSION,
        "tool": _tool_block(),
        "common_mode": _COMMON_MODE,
        "parents": _parents_block(
            artifacts=artifacts,
            content=content,
            fields_path=fields_path,
            fields_lineage_path=fields_lineage_path,
        ),
        "versions": _versions_block(
            content=content,
            budget_steps=budget_steps,
            max_unresolved_send_per_scope=max_unresolved_send_per_scope,
        ),
        "counts": _counts_block(artifacts=artifacts),
        **_assurance_blocks(artifacts=artifacts),
        "declared_differences": [dict(item) for item in DECLARED_DIFFERENCES],
        "output": {
            "trace_jsonl": "trace.jsonl",
            "trace_digest": artifacts.trace_digest,
            "trace_digest_scope": (
                "tos.backtest.trace_digest over the run's wiring-trace document "
                "— reproducibility, never distinctness (design #33 §5.2)"
            ),
        },
    }


def _write_jsonl(path: Path, lines: Sequence[Mapping[str, Any]]) -> str:
    """Write one JSON object per line and return the file's sha256."""
    with path.open("w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(json.dumps(line, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    return _sha256_file(path)


def write_artifacts(
    *,
    out_dir: Path,
    artifacts: RunArtifacts,
    content: LoadedStrategyContent,
    fields_path: Path,
    budget_steps: int,
    max_unresolved_send_per_scope: int,
) -> tuple[Path, Path]:
    """Write ``trace.jsonl`` + ``lineage.json`` into ``out_dir``.

    Returns:
        ``(trace path, lineage path)``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "trace.jsonl"
    lineage_path = out_dir / "lineage.json"
    trace_sha = _write_jsonl(trace_path, artifacts.trace_lines)
    fields_lineage = fields_path.parent / "lineage.json"
    lineage = build_lineage(
        artifacts=artifacts,
        content=content,
        fields_path=fields_path,
        fields_lineage_path=fields_lineage if fields_lineage.is_file() else None,
        budget_steps=budget_steps,
        max_unresolved_send_per_scope=max_unresolved_send_per_scope,
    )
    lineage["output"]["trace_jsonl_sha256"] = trace_sha
    lineage["output"]["trace_jsonl_lines"] = len(artifacts.trace_lines)
    lineage_path.write_text(
        json.dumps(lineage, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return trace_path, lineage_path
