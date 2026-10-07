#!/usr/bin/env python3
"""CP-3 B3 — bar-by-bar decision-level diff of the legacy and TOS artifacts.

What this is
------------
The third of the kickoff plan's four builds
(``docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md`` §3 B3, §5 step 2):
given B1a's published field stream, B2's per-bar legacy outcome stream and
B1b's per-bar TOS trace, say **for every bar** whether the two sides reached
the same decision, and where they did not, which *already declared* difference
explains it.

It is **artifact to artifact** (design #33 §6.1). It reads three JSONL files
and their lineage sidecars and nothing else: no Parquet, no strategy YAML, no
``shared.*`` strategy code, no ``tos``/``tos_runtime`` (the import firewall is
bidirectional — ``tools/`` is in its reverse scan, ``tools/tos_firewall_check.py``
TOS-FW-R — so B1b's trace is consumed as a FILE, never by driving the kernel).
That is also why this module does not import B1a's ``produce_fields``: B3's
claim is about three files, so a B3 run must stay valid when the legacy band
math behind those files is gone (CP-4 deletes it). The two provenance helpers
it therefore keeps locally are pinned byte-for-byte against B1a's by
``tests/tools/test_cp3_diff_decisions.py`` so they cannot drift apart.

What it refuses
---------------
A join on ``raw_event_id`` is only meaningful if the three artifacts are about
the same bars. The key carries no window anchor, so a mismatched trio is NOT
detectable from the lines themselves — only from the lineage blocks. B2's
lineage states the contract in its own words
(``join.b3_contract``): *"B3 MUST REFUSE a (B1a, B2) pair whose
join.window_identity blocks differ in any field, rather than join on
raw_event_id and report the difference as a decision mismatch."* This tool
implements that refusal and five more; every one of them, passed or not, is
recorded in the output lineage's ``checks`` list (exit code 2 on refusal).

What it does NOT compare
------------------------
Fills and PnL. ``tos.backtest`` holds at most ONE order per scope for the whole
run (B1b-D1), so the first firing is realized and every later one is an exact
capacity denial; and its result types carry no Sharpe/PnL/return/edge field at
all (B1b's ``claims.performance_surface``: "ABSENT BY CONSTRUCTION"). kickoff
§3 B4 disposes of this as **체결 비교 포기** — the comparison is decision and
intent level, never fill for fill. ``summary.json`` says so in its ``scope``
block rather than leaving a reader to infer it from a missing section.

Output layout
-------------
``--out`` is a directory holding ``diff.jsonl`` + ``summary.json`` +
``lineage.json``. kickoff §5 step 2 left the placement to B3; the default is::

    reports/tos-cp3/<symbol>_<window_start>_<window_end>/

keyed on the agreed window identity rather than on a run counter, so two runs
over the same window land in the same place and a reader can tell from the path
which window an artifact is about. ``reports/**`` is gitignored (``.gitignore``
78행): artifacts are not committed.

Usage
-----
::

    .venv/bin/python tools/tos_cp3/diff_decisions.py \\
        --fields  /path/cp3-b1a-run1/fields.jsonl \\
        --legacy  /path/cp3-b2-run3/decisions.jsonl \\
        --tos     /path/cp3-b1b-run1/trace.jsonl \\
        --out     /path/cp3-b3-run1

Each artifact's lineage sidecar is auto-discovered as ``lineage.json`` beside
it; ``--fields-lineage`` / ``--legacy-lineage`` / ``--tos-lineage`` override.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Repo root of the checkout this file belongs to, inserted at the FRONT of
#: ``sys.path`` for the same reason B1a and B2 do it: an editable install of
#: another checkout must not shadow this worktree's ``tools/``.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.tos_cp3 import TOS_CP3_VERSION  # noqa: E402

#: Lineage schema version — separate from the tool version so a reader can tell
#: "values may differ" from "the sidecar is shaped differently".
LINEAGE_SCHEMA_VERSION = 1

#: Stable identity stamped on every diff line as ``source_id``.
SOURCE_ID = f"tos-cp3-b3/{TOS_CP3_VERSION}"

#: Output file names inside ``--out``.
DIFF_FILENAME = "diff.jsonl"
SUMMARY_FILENAME = "summary.json"
LINEAGE_FILENAME = "lineage.json"

#: Sidecar name looked for beside each input artifact.
SIDECAR_FILENAME = "lineage.json"

#: Default output root (see the module docstring's "Output layout").
DEFAULT_OUT_ROOT = REPO_ROOT / "reports" / "tos-cp3"

#: Cap on the UNRESOLVED id list carried in ``summary.json`` — mirrors B1a's
#: ``OMITTED_ID_LIST_CAP`` so a pathological run cannot write a summary larger
#: than the diff it summarizes. The count is never capped, only the id list.
UNRESOLVED_ID_LIST_CAP = 200

#: One x1000 quantization unit. B1a publishes ``z_x1000`` truncated toward zero
#: (its D8), so a published integer understates the real magnitude by at most
#: one unit: a legacy fire at a real ``|z|`` just over the threshold can land on
#: a published integer just under it. A bar within this many units of the
#: threshold is therefore attributable to the quantization rather than to the
#: policy.
Z_EDGE_UNITS = 1


class DiffDecisionsError(RuntimeError):
    """Raised when the three artifacts cannot be joined, or must not be."""


class _FloatInPayload(Exception):
    """Internal: a JSON float literal was seen while parsing a payload line."""

    def __init__(self, literal: str) -> None:
        super().__init__(literal)
        self.literal = literal


# ---------------------------------------------------------------------------
# Artifact labels and declared-difference ids
# ---------------------------------------------------------------------------

#: The three artifacts, in the order a reader meets them.
LABEL_FIELDS = "B1a"
LABEL_LEGACY = "B2"
LABEL_TOS = "B1b"
ARTIFACT_LABELS = (LABEL_FIELDS, LABEL_LEGACY, LABEL_TOS)


def qualify_difference_id(label: str, raw_id: str) -> str:
    """Namespace a declared-difference id by the artifact that declares it.

    The three artifacts number their differences independently and two of the
    numberings collide: B1a declares ``D1..D10`` and B1b declares
    ``B1b-D1..B1b-D9``. Qualifying by label gives one flat namespace in which
    ``B1a-D1`` and ``B1b-D1`` are different things, which is what an
    attribution has to be able to say. An id that already carries its label
    (B1b's do) is left alone rather than doubled.
    """
    prefix = f"{label}-"
    return raw_id if raw_id.startswith(prefix) else f"{prefix}{raw_id}"


def declared_difference_index(
    lineages: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    """Per-artifact list of ``{id, raw_id, item}`` in each lineage's own order."""
    index: dict[str, list[dict[str, str]]] = {}
    seen: set[str] = set()
    for label in ARTIFACT_LABELS:
        declared = lineages[label].get("declared_differences")
        if not isinstance(declared, list) or not declared:
            raise DiffDecisionsError(
                f"{label} lineage carries no declared_differences list — an "
                "artifact that declares no differences cannot absorb one, and "
                "an attribution naming its ids could never be checked"
            )
        entries: list[dict[str, str]] = []
        for entry in declared:
            raw_id = entry.get("id")
            if not isinstance(raw_id, str) or not raw_id:
                raise DiffDecisionsError(
                    f"{label} lineage has a declared difference with no id"
                )
            qualified = qualify_difference_id(label, raw_id)
            if qualified in seen:
                raise DiffDecisionsError(
                    f"declared-difference id {qualified} appears twice across "
                    "the three lineages — the attribution namespace is ambiguous"
                )
            seen.add(qualified)
            entries.append(
                {
                    "id": qualified,
                    "raw_id": raw_id,
                    "item": str(entry.get("item", "")),
                }
            )
        index[label] = entries
    return index


# ---------------------------------------------------------------------------
# The joined bar
# ---------------------------------------------------------------------------

#: B2's one firing outcome. Every other member of its closed set is a reject
#: reason; the set itself is read from B2's lineage, never restated here.
OUTCOME_FIRED = "FIRED"

#: B2's reject reason for the legacy confidence gate (``min_confidence``), the
#: one gate B1a's published field set cannot express (B1a-D1 / B2-L9).
OUTCOME_LOW_CONFIDENCE = "LOW_CONFIDENCE"

#: The TOS outcome kinds. NO_ACTION is a first-class result, not a gap.
TOS_ACTION = "ACTION"
TOS_FLAT = "FLAT"
TOS_NO_ACTION = "NO_ACTION"
TOS_OUTCOME_KINDS = (TOS_ACTION, TOS_FLAT, TOS_NO_ACTION)

#: The four published gate booleans the tenant entry rule ANDs, in the order
#: ``tos/runtime/cp3/strategies/setup_d_long.strategy.yaml`` compares them.
GATE_FIELDS = ("entry_window", "hi_vol", "stall_ok", "reversal_ok")


@dataclass(frozen=True)
class JoinedBar:
    """One bar as all three artifacts describe it."""

    raw_event_id: str
    as_of_ms: int
    # B2 (legacy)
    legacy_outcome: str
    legacy_direction: str | None
    admitted: bool
    # B1b (TOS)
    tos_outcome_kind: str
    tos_rule_id: str | None
    tos_capacity_denied: bool
    # B1a (the shared field set the TOS rule reads)
    gates: tuple[bool, bool, bool, bool]
    z_x1000: int

    @property
    def legacy_fired(self) -> bool:
        return self.legacy_outcome == OUTCOME_FIRED

    @property
    def legacy_fired_long(self) -> bool:
        return self.legacy_fired and self.legacy_direction == "LONG"

    @property
    def legacy_fired_short(self) -> bool:
        return self.legacy_fired and self.legacy_direction == "SHORT"

    @property
    def tos_action(self) -> bool:
        return self.tos_outcome_kind == TOS_ACTION

    @property
    def tos_flat(self) -> bool:
        return self.tos_outcome_kind == TOS_FLAT


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

BUCKET_AGREE_NO_ACTION = "AGREE_NO_ACTION"
BUCKET_AGREE_ENTRY = "AGREE_ENTRY"
BUCKET_TOS_ONLY_ENTRY = "TOS_ONLY_ENTRY"
BUCKET_LEGACY_ONLY_ENTRY = "LEGACY_ONLY_ENTRY"
#: Prefix of the TOS-exit family; the suffix is the bar's legacy outcome, which
#: is why that outcome is checked against B2's declared closed set first.
BUCKET_TOS_EXIT_PREFIX = "TOS_EXIT_ON_LEGACY_"

#: Buckets in which the two sides reached the same decision.
AGREE_BUCKETS = (BUCKET_AGREE_NO_ACTION, BUCKET_AGREE_ENTRY)

#: The classifier, restated for the lineage so a reader of the sidecar does not
#: have to read this module to know what a bucket name means.
CLASSIFICATION_DECISION_TREE = (
    "1. TOS ACTION and legacy FIRED LONG            -> AGREE_ENTRY. "
    "2. TOS ACTION otherwise                        -> TOS_ONLY_ENTRY. "
    "3. not TOS ACTION and legacy FIRED (either direction) -> LEGACY_ONLY_ENTRY. "
    "4. TOS FLAT and legacy did not fire            -> TOS_EXIT_ON_LEGACY_<legacy outcome>. "
    "5. TOS NO_ACTION and legacy did not fire       -> AGREE_NO_ACTION. "
    "Exhaustive over outcome_kind x fired: every bar lands in exactly one "
    "bucket, and an outcome_kind outside TOS_OUTCOME_KINDS is a refusal, not a "
    "bucket. AGREE_ENTRY is LONG-only on the legacy side because this TOS "
    "deployment renders one direction (B1b-D5); a legacy SHORT fire is "
    "therefore LEGACY_ONLY_ENTRY, not a disagreement about the long rule."
)


def classify(bar: JoinedBar) -> str:
    """The bar's bucket — exactly one, per :data:`CLASSIFICATION_DECISION_TREE`."""
    if bar.tos_outcome_kind not in TOS_OUTCOME_KINDS:
        raise DiffDecisionsError(
            f"{bar.raw_event_id}: unknown TOS outcome_kind " f"{bar.tos_outcome_kind!r}"
        )
    if bar.tos_action:
        return BUCKET_AGREE_ENTRY if bar.legacy_fired_long else BUCKET_TOS_ONLY_ENTRY
    if bar.legacy_fired:
        return BUCKET_LEGACY_ONLY_ENTRY
    if bar.tos_flat:
        return f"{BUCKET_TOS_EXIT_PREFIX}{bar.legacy_outcome}"
    return BUCKET_AGREE_NO_ACTION


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiffContext:
    """Config-sourced values the attribution predicates compare against.

    ``z_entry_max_x1000`` is read from B1b's lineage
    (``parents.strategy_bindings_file.bindings``), which is where the deployed
    threshold lives — ``tos/runtime/cp3/strategy_bindings.yaml``. It is not a
    literal here: a threshold restated in a second place is a threshold that
    can disagree with the deployment it claims to describe.
    """

    z_entry_max_x1000: int
    z_edge_units: int = Z_EDGE_UNITS


@dataclass(frozen=True)
class AttributionRule:
    """One (predicate, declared-difference ids) pair, read in table order."""

    name: str
    ids: tuple[str, ...]
    why: str
    predicate: Callable[[JoinedBar, str, DiffContext], bool]


def _legacy_short_entry(bar: JoinedBar, bucket: str, ctx: DiffContext) -> bool:
    return bar.legacy_fired_short


def _tos_action_on_legacy_low_confidence(
    bar: JoinedBar, bucket: str, ctx: DiffContext
) -> bool:
    return bar.tos_action and bar.legacy_outcome == OUTCOME_LOW_CONFIDENCE


def _tos_flat_without_legacy_fire(
    bar: JoinedBar, bucket: str, ctx: DiffContext
) -> bool:
    return bar.tos_flat and not bar.legacy_fired


def _agree_entry_rejected_by_position_model(
    bar: JoinedBar, bucket: str, ctx: DiffContext
) -> bool:
    return bucket == BUCKET_AGREE_ENTRY and not bar.admitted


def _agree_entry_capacity_denied(bar: JoinedBar, bucket: str, ctx: DiffContext) -> bool:
    return bucket == BUCKET_AGREE_ENTRY and bar.tos_capacity_denied


def _z_quantization_edge(bar: JoinedBar, bucket: str, ctx: DiffContext) -> bool:
    return abs(abs(bar.z_x1000) - abs(ctx.z_entry_max_x1000)) <= ctx.z_edge_units


#: The attribution table — ordered, data-driven, first match wins.
#:
#: Every id named here must exist in one of the three lineages'
#: ``declared_differences`` lists; :func:`assert_attribution_ids_declared`
#: checks that at run time and refuses otherwise, so a rule cannot cite a
#: difference nobody declared.
#:
#: Order matters and the two fill-level rules are LAST among the ACTION rules
#: on purpose. Every TOS ACTION in a B1b run after the first realized order is
#: capacity-denied, so a capacity rule read earlier would absorb every entry
#: disagreement and hide its decision-level cause.
ATTRIBUTION_RULES: tuple[AttributionRule, ...] = (
    AttributionRule(
        name="legacy_short_entry",
        ids=("B1b-D5",),
        why=(
            "The legacy entry fires on abs(z) >= extreme_atr_mult, i.e. BOTH "
            "sides. The DSL has no abs() and direction is a per-deployment "
            "fact, so this TOS deployment compares one side only "
            "(z_x1000 <= z_entry_max_x1000) and the SHORT half is a separate "
            "render with its own strategy file (kickoff §4 결정 4). A legacy "
            "SHORT fire has no counterpart in THIS run by construction."
        ),
        predicate=_legacy_short_entry,
    ),
    AttributionRule(
        name="tos_action_on_legacy_low_confidence",
        ids=("B1a-D1", "B2-L9"),
        why=(
            "The legacy confidence gate (min_confidence) has no published "
            "field: the DSL has no arithmetic and the Proposal no numeric "
            "slot, so a policy written on B1a's fields is a SUPERSET of "
            "'legacy fired'. B2's L9 states the attribution in its own words: "
            "'A B3 mismatch on a bar whose B2 outcome is LOW_CONFIDENCE is "
            "therefore attributable to B1a D1, not to the policy.'"
        ),
        predicate=_tos_action_on_legacy_low_confidence,
    ),
    AttributionRule(
        name="tos_flat_without_legacy_fire",
        ids=("B1b-D7",),
        why=(
            "The DSL environment exposes no position or exposure operand at "
            "all, so the FLAT rules propose FLAT on every reverted/EOD bar "
            "regardless of whether anything is open. The legacy exit is "
            "position-scoped. A TOS FLAT on a bar where the legacy strategy "
            "did not even propose an entry is that difference, not a "
            "disagreement about when to exit."
        ),
        predicate=_tos_flat_without_legacy_fire,
    ),
    AttributionRule(
        name="agree_entry_rejected_by_legacy_position_model",
        ids=("B1b-D7", "B2-L3", "B2-L10"),
        why=(
            "Both entry rules fired on this bar; they differ on whether an "
            "entry would have OCCURRED. The TOS side cannot suppress one — it "
            "has no exposure operand (B1b-D7). The legacy side's suppression "
            "is the walk-forward harness's single-position model, whose notion "
            "of 'still open' is that script's own exit simulation (B2-L3), and "
            "which carries no post-exit cooldown, so the flag is an UPPER "
            "BOUND on what paper would have entered (B2-L10). This is a "
            "fill-level divergence on a bar where the decision agreed."
        ),
        predicate=_agree_entry_rejected_by_position_model,
    ),
    AttributionRule(
        name="agree_entry_capacity_denied",
        ids=("B1b-D1",),
        why=(
            "tos.backtest holds at most ONE order per scope for the whole run, "
            "so the first firing is realized and every later one is an exact "
            "capacity denial (AT_MOST_ONE_EXPOSURE_HELD). kickoff §3 B4 "
            "disposes of this as '체결 비교 포기': the decision agreed on this "
            "bar and the denial is about the fill, which this report does not "
            "compare. Recorded rather than dropped so no ACTION bar silently "
            "carries an unrecorded inability to fill."
        ),
        predicate=_agree_entry_capacity_denied,
    ),
    AttributionRule(
        name="z_quantization_edge",
        ids=("B1a-D8",),
        why=(
            "B1a publishes z truncated toward zero, so a published integer "
            "understates the real magnitude by up to one x1000 unit. Within "
            "one unit of the deployed threshold the two sides can disagree "
            "about whether the threshold was cleared without disagreeing about "
            "the policy."
        ),
        predicate=_z_quantization_edge,
    ),
)

#: What an attribution says when there is nothing to explain, and when there is
#: but no rule explains it. ``UNRESOLVED`` is left standing: the kickoff plan
#: §5 2 requires mismatches to be left unresolved rather than given a reason.
ATTRIBUTION_AGREED = "AGREED"
ATTRIBUTION_UNRESOLVED = "UNRESOLVED"


def needs_attribution(bar: JoinedBar, bucket: str) -> bool:
    """Whether this bar has anything for the attribution table to explain.

    A bucket-level disagreement always does. An ``AGREE_ENTRY`` bar does when
    the two sides agreed on the decision but could not have agreed on the fill
    — the legacy position model would not have entered, or the TOS run had no
    capacity left.
    """
    if bucket == BUCKET_AGREE_NO_ACTION:
        return False
    if bucket == BUCKET_AGREE_ENTRY:
        return (not bar.admitted) or bar.tos_capacity_denied
    return True


def attribute(
    bar: JoinedBar,
    bucket: str,
    ctx: DiffContext,
    rules: tuple[AttributionRule, ...] = ATTRIBUTION_RULES,
) -> tuple[str, tuple[str, ...]]:
    """``(rule name, declared-difference ids)`` for this bar; first match wins."""
    if not needs_attribution(bar, bucket):
        return ATTRIBUTION_AGREED, ()
    for rule in rules:
        if rule.predicate(bar, bucket, ctx):
            return rule.name, rule.ids
    return ATTRIBUTION_UNRESOLVED, ()


def assert_attribution_ids_declared(
    rules: tuple[AttributionRule, ...],
    declared_ids: set[str],
) -> None:
    """Refuse a table that cites a difference none of the three artifacts declares.

    The guard exists because an attribution is only worth reading if the thing
    it names was declared, with a reason, by the artifact it belongs to. A
    renamed or dropped declared difference must stop a B3 run, not silently
    turn its attributions into dangling references.
    """
    missing: list[str] = []
    for rule in rules:
        if not rule.ids:
            raise DiffDecisionsError(
                f"attribution rule {rule.name!r} names no declared difference"
            )
        for difference_id in rule.ids:
            if difference_id not in declared_ids:
                missing.append(f"{rule.name} -> {difference_id}")
    if missing:
        raise DiffDecisionsError(
            "attribution table cites declared-difference ids that no input "
            "lineage declares: " + "; ".join(missing)
        )


# ---------------------------------------------------------------------------
# Window identity
# ---------------------------------------------------------------------------

#: The fields B2's ``join.window_identity`` carries, and therefore the fields a
#: refusal compares. Order is B2's.
WINDOW_IDENTITY_FIELDS = (
    "symbol",
    "market_open_kst",
    "market_open_source",
    "min_bars_per_day",
    "window_start",
    "window_end",
)

#: Where each field of B1a's identity is projected from. B1a's lineage has no
#: ``join`` block — it is the producer, not a side of the join — so the
#: identity is projected from the blocks it does carry. Recorded in the output
#: lineage so a reader can check the projection rather than trust it.
B1A_IDENTITY_PROJECTION = {
    "symbol": "dataset.symbol",
    "market_open_kst": "strategy.market_open_kst",
    "market_open_source": "strategy.market_open_source",
    "min_bars_per_day": "dataset.min_bars_per_day",
    "window_start": "dataset.requested_start",
    "window_end": "dataset.requested_end",
}


def _dig(lineage: dict[str, Any], dotted: str, label: str) -> Any:
    node: Any = lineage
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise DiffDecisionsError(
                f"{label} lineage has no {dotted} — the window identity cannot "
                "be established, so the join cannot be shown to be meaningful"
            )
        node = node[part]
    return node


def b1a_window_identity(lineage: dict[str, Any]) -> dict[str, Any]:
    """B1a's window identity, projected from its dataset/strategy blocks."""
    return {
        field: _dig(lineage, B1A_IDENTITY_PROJECTION[field], LABEL_FIELDS)
        for field in WINDOW_IDENTITY_FIELDS
    }


def b2_window_identity(lineage: dict[str, Any]) -> dict[str, Any]:
    """B2's declared ``join.window_identity``, exactly as it records it."""
    block = _dig(lineage, "join.window_identity", LABEL_LEGACY)
    if not isinstance(block, dict):
        raise DiffDecisionsError("B2 lineage join.window_identity is not a block")
    missing = [f for f in WINDOW_IDENTITY_FIELDS if f not in block]
    if missing:
        raise DiffDecisionsError(
            "B2 lineage join.window_identity is missing "
            f"{', '.join(missing)} — the refusal its own b3_contract requires "
            "cannot be performed on a partial identity"
        )
    return {field: block[field] for field in WINDOW_IDENTITY_FIELDS}


# ---------------------------------------------------------------------------
# Reading the artifacts
# ---------------------------------------------------------------------------


def sha256_and_lines(path: Path) -> tuple[str, int]:
    """``(sha256 hexdigest, line count)`` of *path*, read once in chunks.

    Refuses a file that does not end with a newline: the line count is a
    newline count, and a truncated final line would otherwise be silently
    dropped from it.
    """
    digest = hashlib.sha256()
    lines = 0
    last = b""
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
                lines += chunk.count(b"\n")
                last = chunk[-1:]
    except OSError as exc:
        raise DiffDecisionsError(f"cannot read {path}: {exc}") from exc
    if lines == 0 or last != b"\n":
        raise DiffDecisionsError(
            f"{path} does not end with a newline — its final line is truncated "
            "and would be dropped from every count in this report"
        )
    return digest.hexdigest(), lines


def sha256_file(path: Path) -> str:
    """``sha256`` hexdigest of *path* (used for the lineage sidecars)."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
    except OSError as exc:
        raise DiffDecisionsError(f"cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def load_lineage(path: Path, label: str) -> dict[str, Any]:
    """Parse one lineage sidecar. Floats are allowed here and only here.

    A lineage records the strategy's own float-valued parameters
    (``extreme_atr_mult: 1.8``), so the no-floats rule belongs to the payload
    lines, not to the sidecars that describe them.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DiffDecisionsError(f"cannot read {label} lineage {path}: {exc}") from exc
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DiffDecisionsError(f"{label} lineage {path} is not JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise DiffDecisionsError(f"{label} lineage {path} is not a JSON object")
    return parsed


def _refuse_float(literal: str) -> float:
    raise _FloatInPayload(literal)


def _refuse_constant(name: str) -> float:
    raise _FloatInPayload(name)


def _float_paths(node: Any, path: str = "") -> list[str]:
    """Every dotted path at which *node* holds a float (for the refusal message)."""
    found: list[str] = []
    if isinstance(node, float):
        found.append(f"{path or '<root>'}={node!r}")
    elif isinstance(node, dict):
        for key, value in node.items():
            found.extend(_float_paths(value, f"{path}.{key}" if path else str(key)))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_float_paths(value, f"{path}[{index}]"))
    return found


def parse_payload_line(line: str, label: str, index: int) -> dict[str, Any]:
    """Parse one JSONL payload line, refusing any float it carries.

    The float refusal is enforced by ``json.loads``'s own ``parse_float`` and
    ``parse_constant`` hooks rather than by a walk of the parsed object: a hook
    sees the JSON *literal*, so ``1.0`` is refused even though its value is
    integral, and ``NaN``/``Infinity`` are refused rather than becoming floats
    nothing downstream could compare. All three producers publish integers and
    booleans only (B1a ``encoding.no_floats_in_fields``, B2
    ``encoding.no_floats_in_payload``); a float appearing here means one of them
    changed in a way that makes the comparison no longer exact.
    """
    try:
        parsed = json.loads(
            line, parse_float=_refuse_float, parse_constant=_refuse_constant
        )
    except _FloatInPayload as exc:
        # Re-parse permissively to name WHERE the float is; this path is only
        # ever taken on the way to a refusal.
        try:
            permissive = json.loads(line)
        except json.JSONDecodeError:  # pragma: no cover - unreachable in practice
            permissive = None
        where = ", ".join(_float_paths(permissive)) or f"literal {exc.literal}"
        raise DiffDecisionsError(
            f"{label} line {index + 1} carries a float: {where}. Every payload "
            "value must be an integer, a boolean or a string — a float makes "
            "the bar-for-bar comparison inexact."
        ) from exc
    except json.JSONDecodeError as exc:
        raise DiffDecisionsError(
            f"{label} line {index + 1} is not JSON: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise DiffDecisionsError(f"{label} line {index + 1} is not a JSON object")
    return parsed


def _require(payload: dict[str, Any], key: str, label: str, index: int) -> Any:
    if key not in payload:
        raise DiffDecisionsError(f"{label} line {index + 1} has no {key!r}")
    return payload[key]


def _iter_lines(path: Path) -> Iterator[str]:
    with path.open("r", encoding="utf-8") as handle:
        yield from handle


# ---------------------------------------------------------------------------
# The join
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JoinResult:
    """Validated per-bar join plus the evidence that it was validated."""

    bars: list[JoinedBar]
    checks: list[dict[str, Any]]


def join_artifacts(
    *,
    fields_path: Path,
    legacy_path: Path,
    tos_path: Path,
    legacy_outcomes: tuple[str, ...],
) -> JoinResult:
    """Read the three artifacts in lockstep, refusing any disagreement about bars.

    Nothing is written before this returns: the refusals come first, so a
    refused trio leaves no partial report behind.
    """
    checks: list[dict[str, Any]] = []
    bars: list[JoinedBar] = []
    legacy_outcome_set = set(legacy_outcomes)
    id_mismatch: dict[str, Any] | None = None
    as_of_mismatch: dict[str, Any] | None = None

    streams = zip(
        _iter_lines(fields_path), _iter_lines(legacy_path), _iter_lines(tos_path)
    )
    for index, (fields_line, legacy_line, tos_line) in enumerate(streams):
        fields_payload = parse_payload_line(fields_line, LABEL_FIELDS, index)
        legacy_payload = parse_payload_line(legacy_line, LABEL_LEGACY, index)
        tos_payload = parse_payload_line(tos_line, LABEL_TOS, index)

        fields_id = _require(fields_payload, "raw_event_id", LABEL_FIELDS, index)
        legacy_id = _require(legacy_payload, "raw_event_id", LABEL_LEGACY, index)
        tos_id = _require(tos_payload, "raw_event_id", LABEL_TOS, index)
        if not (fields_id == legacy_id == tos_id) and id_mismatch is None:
            id_mismatch = {
                "position": index,
                LABEL_FIELDS: fields_id,
                LABEL_LEGACY: legacy_id,
                LABEL_TOS: tos_id,
            }
            break

        fields_as_of = _require(fields_payload, "as_of_ms", LABEL_FIELDS, index)
        legacy_as_of = _require(legacy_payload, "as_of_ms", LABEL_LEGACY, index)
        tos_as_of = _require(tos_payload, "as_of_ms", LABEL_TOS, index)
        if not (fields_as_of == legacy_as_of == tos_as_of) and as_of_mismatch is None:
            as_of_mismatch = {
                "position": index,
                "raw_event_id": fields_id,
                LABEL_FIELDS: fields_as_of,
                LABEL_LEGACY: legacy_as_of,
                LABEL_TOS: tos_as_of,
            }
            break

        published = _require(fields_payload, "fields", LABEL_FIELDS, index)
        if not isinstance(published, dict):
            raise DiffDecisionsError(f"B1a line {index + 1} fields is not a block")
        decision = _require(legacy_payload, "decision", LABEL_LEGACY, index)
        if not isinstance(decision, dict):
            raise DiffDecisionsError(f"B2 line {index + 1} decision is not a block")

        legacy_outcome = decision.get("outcome")
        if legacy_outcome not in legacy_outcome_set:
            raise DiffDecisionsError(
                f"{fields_id}: legacy outcome {legacy_outcome!r} is not in B2's "
                "declared closed set — a bucket named after it would name an "
                "outcome B2 does not claim to produce"
            )
        tos_kind = tos_payload.get("outcome_kind")
        if tos_kind not in TOS_OUTCOME_KINDS:
            raise DiffDecisionsError(
                f"{fields_id}: TOS outcome_kind {tos_kind!r} is not one of "
                f"{TOS_OUTCOME_KINDS}"
            )

        gates = []
        for gate in GATE_FIELDS:
            if gate not in published:
                raise DiffDecisionsError(
                    f"{fields_id}: B1a publishes no {gate!r} — the tenant entry "
                    "rule ANDs it, so its absence makes the comparison undefined"
                )
            value = published[gate]
            if not isinstance(value, bool):
                raise DiffDecisionsError(
                    f"{fields_id}: B1a {gate!r} is {value!r}, not a boolean"
                )
            gates.append(value)
        z_value = published.get("z_x1000")
        if not isinstance(z_value, int) or isinstance(z_value, bool):
            raise DiffDecisionsError(
                f"{fields_id}: B1a z_x1000 is {z_value!r}, not an integer"
            )
        admitted = decision.get("would_be_admitted_by_legacy_position_model")
        if not isinstance(admitted, bool):
            raise DiffDecisionsError(
                f"{fields_id}: B2 would_be_admitted_by_legacy_position_model is "
                f"{admitted!r}, not a boolean"
            )
        capacity_denied = tos_payload.get("capacity_denied")
        if not isinstance(capacity_denied, bool):
            raise DiffDecisionsError(
                f"{fields_id}: B1b capacity_denied is {capacity_denied!r}, not a "
                "boolean"
            )

        bars.append(
            JoinedBar(
                raw_event_id=str(fields_id),
                as_of_ms=int(fields_as_of),
                legacy_outcome=str(legacy_outcome),
                legacy_direction=decision.get("direction"),
                admitted=admitted,
                tos_outcome_kind=str(tos_kind),
                tos_rule_id=tos_payload.get("rule_id"),
                tos_capacity_denied=capacity_denied,
                gates=(gates[0], gates[1], gates[2], gates[3]),
                z_x1000=z_value,
            )
        )

    if id_mismatch is not None:
        raise DiffDecisionsError(
            "raw_event_id sequences differ at position "
            f"{id_mismatch['position']}: B1a={id_mismatch[LABEL_FIELDS]!r} "
            f"B2={id_mismatch[LABEL_LEGACY]!r} B1b={id_mismatch[LABEL_TOS]!r}. "
            "The three artifacts are not about the same bars in the same order, "
            "so a positional join would compare different bars to each other."
        )
    if as_of_mismatch is not None:
        raise DiffDecisionsError(
            "as_of_ms differ at position "
            f"{as_of_mismatch['position']} ({as_of_mismatch['raw_event_id']}): "
            f"B1a={as_of_mismatch[LABEL_FIELDS]} "
            f"B2={as_of_mismatch[LABEL_LEGACY]} "
            f"B1b={as_of_mismatch[LABEL_TOS]}"
        )

    checks.append(
        {
            "name": "raw_event_id_sequences_identical",
            "status": "PASS",
            "detail": (
                "every position of the three artifacts carries the same " "raw_event_id"
            ),
            "bars": len(bars),
        }
    )
    checks.append(
        {
            "name": "as_of_ms_identical",
            "status": "PASS",
            "detail": "every position carries the same as_of_ms in all three",
        }
    )
    checks.append(
        {
            "name": "no_floats_in_payloads",
            "status": "PASS",
            "detail": (
                "enforced by json.loads parse_float/parse_constant hooks on "
                "every line of all three artifacts, so a float LITERAL is "
                "refused even where its value is integral"
            ),
        }
    )
    checks.append(
        {
            "name": "legacy_outcome_in_declared_closed_set",
            "status": "PASS",
            "detail": (
                "every B2 outcome is a member of that run's lineage "
                "outcomes.closed_set, so every TOS_EXIT_ON_LEGACY_<outcome> "
                "bucket name is one B2 declares"
            ),
            "closed_set_size": len(legacy_outcomes),
        }
    )
    checks.append(
        {
            "name": "tos_outcome_kind_in_closed_set",
            "status": "PASS",
            "detail": f"every B1b outcome_kind is one of {list(TOS_OUTCOME_KINDS)}",
        }
    )
    return JoinResult(bars=bars, checks=checks)


# ---------------------------------------------------------------------------
# Diff lines
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiffRecord:
    """One bar's classified comparison — the wire form of ``diff.jsonl``."""

    bar: JoinedBar
    bucket: str
    attribution_rule: str
    attribution: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        bar = self.bar
        return {
            "raw_event_id": bar.raw_event_id,
            "source_id": SOURCE_ID,
            "as_of_ms": bar.as_of_ms,
            "legacy": {
                "outcome": bar.legacy_outcome,
                "direction": bar.legacy_direction,
                "would_be_admitted_by_legacy_position_model": bar.admitted,
            },
            "tos": {
                "outcome_kind": bar.tos_outcome_kind,
                "rule_id": bar.tos_rule_id,
                "capacity_denied": bar.tos_capacity_denied,
            },
            "fields": {
                **dict(zip(GATE_FIELDS, bar.gates)),
                "z_x1000": bar.z_x1000,
            },
            "bucket": self.bucket,
            "attribution_rule": self.attribution_rule,
            "attribution": list(self.attribution),
        }

    def to_json_line(self) -> str:
        return json.dumps(self.to_payload(), separators=(",", ":"), ensure_ascii=True)


def render_jsonl(records: list[DiffRecord]) -> bytes:
    """Serialize *records* to the exact bytes written to disk."""
    return "".join(f"{record.to_json_line()}\n" for record in records).encode("utf-8")


def render_json(document: dict[str, Any]) -> bytes:
    """Serialize a sidecar (lineage or summary) to the exact bytes written."""
    return (
        json.dumps(document, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    ).encode("utf-8")


def classify_all(bars: list[JoinedBar], ctx: DiffContext) -> list[DiffRecord]:
    """Bucket and attribute every bar, in input order."""
    records: list[DiffRecord] = []
    for bar in bars:
        bucket = classify(bar)
        rule_name, ids = attribute(bar, bucket, ctx)
        records.append(
            DiffRecord(
                bar=bar, bucket=bucket, attribution_rule=rule_name, attribution=ids
            )
        )
    return records


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    """A rate as integers only — no float ever enters an artifact of this tool.

    ``rate_x10000`` is half-up at the last digit; the numerator and denominator
    are carried so a reader recomputes rather than trusts the rounding.
    """
    if denominator == 0:
        return {
            "numerator": numerator,
            "denominator": 0,
            "rate_x10000": None,
            "note": "undefined — the denominator is empty",
        }
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate_x10000": (numerator * 20000 + denominator) // (2 * denominator),
    }


#: Said in the summary rather than left to be inferred from a missing section.
SCOPE_NOTE = (
    "Fills and PnL are NOT compared. Two independent reasons, both recorded by "
    "the TOS artifact itself: (1) tos.backtest holds at most ONE order per "
    "scope for the whole run, so after the first realized order every firing is "
    "an exact capacity denial (B1b-D1); kickoff §3 B4 disposes of this as "
    "'체결 비교 포기' — the comparison is decision and intent level, never fill "
    "for fill. (2) The performance surface is sealed: no Sharpe, PnL, return or "
    "edge field exists anywhere in tos.backtest's result types (design #33 "
    "§1.2 B1), so the TOS side cannot make a performance claim to compare "
    "against. The legacy side's would_be_admitted_by_legacy_position_model flag "
    "is a GATING verdict, not a fill: it emits no PnL, slippage, commission or "
    "quantity (B2-L3), and it is an upper bound on what paper would have "
    "entered because the live post-exit cooldown is absent from it (B2-L10)."
)


def build_summary(
    *,
    records: list[DiffRecord],
    identity: dict[str, Any],
    declared_index: dict[str, list[dict[str, str]]],
    ctx: DiffContext,
    tos_lineage: dict[str, Any],
) -> dict[str, Any]:
    """The decision/reject/risk difference report (kickoff §5 step 5)."""
    buckets = Counter(record.bucket for record in records)
    rules = Counter(record.attribution_rule for record in records)
    ids = Counter(
        difference_id for record in records for difference_id in record.attribution
    )
    bucket_by_rule: dict[str, Counter[str]] = {}
    for record in records:
        bucket_by_rule.setdefault(record.attribution_rule, Counter())[
            record.bucket
        ] += 1

    matrix: dict[str, Counter[str]] = {}
    for record in records:
        matrix.setdefault(record.bar.legacy_outcome, Counter())[
            record.bar.tos_outcome_kind
        ] += 1

    legacy_fired = sum(1 for r in records if r.bar.legacy_fired)
    legacy_fired_long = sum(1 for r in records if r.bar.legacy_fired_long)
    legacy_fired_short = sum(1 for r in records if r.bar.legacy_fired_short)
    legacy_fired_long_admitted = sum(
        1 for r in records if r.bar.legacy_fired_long and r.bar.admitted
    )
    tos_action = sum(1 for r in records if r.bar.tos_action)
    tos_action_capacity_denied = sum(
        1 for r in records if r.bar.tos_action and r.bar.tos_capacity_denied
    )
    agree_entry = buckets.get(BUCKET_AGREE_ENTRY, 0)
    agree_entry_admitted = sum(
        1 for r in records if r.bucket == BUCKET_AGREE_ENTRY and r.bar.admitted
    )

    unresolved = [
        r.bar.raw_event_id
        for r in records
        if r.attribution_rule == ATTRIBUTION_UNRESOLVED
    ]

    absorbed: dict[str, list[dict[str, Any]]] = {}
    for label, entries in declared_index.items():
        absorbed[label] = [
            {
                "id": entry["id"],
                "item": entry["item"],
                "absorbed_bars": ids.get(entry["id"], 0),
            }
            for entry in entries
        ]

    return {
        "summary_schema_version": 1,
        "tool": {"name": "tools/tos_cp3/diff_decisions.py", "source_id": SOURCE_ID},
        "window_identity": dict(identity),
        "bars": len(records),
        "buckets": dict(sorted(buckets.items())),
        "buckets_reconcile_to_bars": sum(buckets.values()) == len(records),
        "attribution_rules": {
            name: {
                "bars": count,
                "ids": list(
                    next(
                        (rule.ids for rule in ATTRIBUTION_RULES if rule.name == name),
                        (),
                    )
                ),
                "buckets": dict(sorted(bucket_by_rule.get(name, Counter()).items())),
            }
            for name, count in sorted(rules.items())
        },
        "attribution_ids": dict(sorted(ids.items())),
        "legacy_outcome_by_tos_kind": {
            outcome: dict(sorted(kinds.items()))
            for outcome, kinds in sorted(matrix.items())
        },
        "totals": {
            "legacy_fired": legacy_fired,
            "legacy_fired_long": legacy_fired_long,
            "legacy_fired_short": legacy_fired_short,
            "legacy_fired_long_admitted_by_position_model": (
                legacy_fired_long_admitted
            ),
            "tos_action": tos_action,
            "tos_action_capacity_denied": tos_action_capacity_denied,
            "tos_flat": sum(1 for r in records if r.bar.tos_flat),
            "tos_no_action": sum(
                1 for r in records if r.bar.tos_outcome_kind == TOS_NO_ACTION
            ),
        },
        "rates": {
            "rule_level_entry_agreement": {
                "definition": (
                    "AGREE_ENTRY / (legacy outcome FIRED and direction LONG). "
                    "'Did the tenant policy's entry rule fire on the bars the "
                    "legacy ENTRY RULE fired on, long side?' Neither side's "
                    "position state enters this rate: it is a rule-to-rule "
                    "comparison. The denominator is LONG-only because this TOS "
                    "deployment renders one direction (B1b-D5)."
                ),
                **_rate(agree_entry, legacy_fired_long),
            },
            "position_model_level_entry_agreement": {
                "definition": (
                    "(AGREE_ENTRY and would_be_admitted_by_legacy_position_model) "
                    "/ (legacy FIRED LONG and would_be_admitted_by_legacy_"
                    "position_model). 'Of the long fires the walk-forward "
                    "harness's single-position model would actually have "
                    "entered, on how many did the tenant policy also propose an "
                    "entry?' The TOS side contributes no position state to "
                    "either side of this rate — it has none (B1b-D7) — so the "
                    "rate narrows the denominator only."
                ),
                **_rate(agree_entry_admitted, legacy_fired_long_admitted),
            },
            "tos_action_explained_by_a_legacy_long_fire": {
                "definition": (
                    "AGREE_ENTRY / (TOS outcome_kind ACTION). The same "
                    "numerator read from the TOS side: 'of the bars where the "
                    "tenant policy proposed an entry, on how many did the "
                    "legacy rule also fire long?' Below 1 because the published "
                    "field set cannot express min_confidence, so the policy is a "
                    "SUPERSET of 'legacy fired' (B1a-D1 / B2-L9)."
                ),
                **_rate(agree_entry, tos_action),
            },
        },
        "unresolved": {
            "count": len(unresolved),
            "id_list_cap": UNRESOLVED_ID_LIST_CAP,
            "raw_event_ids": unresolved[:UNRESOLVED_ID_LIST_CAP],
            "raw_event_ids_truncated": len(unresolved) > UNRESOLVED_ID_LIST_CAP,
            "note": (
                "A bar the attribution table cannot explain is left UNRESOLVED "
                "and listed, never given a reason (kickoff §5 2: 불일치는 "
                "미해결로 남기되)."
            ),
        },
        "declared_differences": {
            "note": (
                "Every difference the three artifacts declare, with the number "
                "of bars this report attributed to it. A zero means this window "
                "exercised nothing that the difference explains — not that the "
                "difference is absent."
            ),
            "by_artifact": absorbed,
        },
        "config": {
            "z_entry_max_x1000": ctx.z_entry_max_x1000,
            "z_entry_max_x1000_source": (
                "B1b lineage parents.strategy_bindings_file.bindings — "
                "tos/runtime/cp3/strategy_bindings.yaml"
            ),
            "z_edge_units": ctx.z_edge_units,
        },
        "scope": {
            "fills_and_pnl_not_compared": SCOPE_NOTE,
            "tos_fill_records": tos_lineage.get("counts", {}).get("fill_records"),
            "tos_performance_surface": tos_lineage.get("claims", {}).get(
                "performance_surface"
            ),
            "tos_oracle_scope": tos_lineage.get("claims", {}).get("oracle_scope"),
        },
    }


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------

#: Echoed from all three artifacts, which each carry their own copy.
COMMON_MODE = (
    "This is NOT independent corroboration of the band math. Both sides of this "
    "comparison read ONE implementation of the indicator math — "
    "shared/decision/setups/vwap_reversion.py, driven bar by bar by B1a — so "
    "agreement here confirms the POLICY (which published scalars the tenant "
    "rules compare, and when they fire), never the VWAP/ATR/z arithmetic those "
    "scalars came from. ADR-002-018 §10: 'the same function call is a common "
    "mode, not independent corroboration'."
)


def _runtime_versions() -> dict[str, str]:
    """Interpreter identity. This tool's inputs are JSON text and its only
    dependency is the standard library, so no third-party version can change
    its output and none is recorded — a recorded version that cannot affect the
    artifact is a provenance claim with nothing behind it."""
    return {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "third_party": "none — standard library only",
    }


def _git_identity(repo_root: Path) -> dict[str, Any]:
    """Record the worktree's commit and whether it is dirty (provenance only)."""

    def run_git(args: list[str]) -> str | None:
        try:
            done = subprocess.run(
                ["git", "-C", str(repo_root), *args],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        return done.stdout.strip() if done.returncode == 0 else None

    commit = run_git(["rev-parse", "HEAD"])
    status = run_git(["status", "--porcelain"])
    return {
        "repo_root": str(repo_root),
        "commit": commit or "unknown",
        "branch": run_git(["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown",
        "dirty": bool(status) if status is not None else None,
    }


@dataclass(frozen=True)
class ArtifactRef:
    """One input artifact and its sidecar, with both digests."""

    label: str
    jsonl_path: Path
    jsonl_sha256: str
    jsonl_lines: int
    lineage_path: Path
    lineage_sha256: str
    lineage: dict[str, Any]

    def to_lineage(self) -> dict[str, Any]:
        tool = self.lineage.get("tool", {})
        return {
            "role": self.label,
            "path": str(self.jsonl_path),
            "sha256": self.jsonl_sha256,
            "lines": self.jsonl_lines,
            "lineage_json": {
                "path": str(self.lineage_path),
                "sha256": self.lineage_sha256,
            },
            "producer": {
                "name": tool.get("name"),
                "version": tool.get("version"),
                "source_id": tool.get("source_id"),
                "git_commit": (tool.get("git") or {}).get("commit"),
            },
        }


def build_lineage(
    *,
    refs: dict[str, ArtifactRef],
    identity: dict[str, Any],
    checks: list[dict[str, Any]],
    records: list[DiffRecord],
    declared_index: dict[str, list[dict[str, str]]],
    ctx: DiffContext,
    outputs: dict[str, Any],
) -> dict[str, Any]:
    """ADR-002-018 §10 lineage for the diff: parents, tool, checks, outputs.

    No clock is read anywhere in this tool, so the sidecar carries no
    timestamp: every value in it is a function of the three inputs and the code
    that read them, which is what makes two runs byte-identical.
    """
    return {
        "lineage_schema_version": LINEAGE_SCHEMA_VERSION,
        "tool": {
            "name": "tools/tos_cp3/diff_decisions.py",
            "version": f"tos_cp3/{TOS_CP3_VERSION}",
            "source_id": SOURCE_ID,
            "git": _git_identity(REPO_ROOT),
            "runtime": _runtime_versions(),
        },
        "parents": {
            "fields_jsonl": refs[LABEL_FIELDS].to_lineage(),
            "legacy_decisions_jsonl": refs[LABEL_LEGACY].to_lineage(),
            "tos_trace_jsonl": refs[LABEL_TOS].to_lineage(),
        },
        "window_identity": dict(identity),
        "window_identity_projection": {
            "note": (
                "B2 declares join.window_identity; B1a has no join block (it is "
                "the producer, not a side of the join) so its identity is "
                "projected from the blocks it does carry. The projection is "
                "recorded so a reader checks it rather than trusting it."
            ),
            "b1a_sources": dict(B1A_IDENTITY_PROJECTION),
            "b2_source": "join.window_identity",
            "refusal_contract": (
                refs[LABEL_LEGACY].lineage.get("join", {}).get("b3_contract")
            ),
        },
        "join": {
            "key": "raw_event_id",
            "mode": (
                "positional lockstep over three line-for-line joinable files, "
                "with the key equality asserted at every position — not a hash "
                "join, so a reordering is a refusal rather than a silent "
                "re-pairing"
            ),
            "key_derivation": (
                "produce_fields.derive_raw_event_id (B1a); B2 imports it and "
                "B1b carries it through from the fields file"
            ),
            "bars": len(records),
        },
        "checks": checks,
        "classification": {
            "buckets": sorted({record.bucket for record in records}),
            "bucket_families": [
                BUCKET_AGREE_NO_ACTION,
                BUCKET_AGREE_ENTRY,
                BUCKET_TOS_ONLY_ENTRY,
                BUCKET_LEGACY_ONLY_ENTRY,
                f"{BUCKET_TOS_EXIT_PREFIX}<legacy outcome>",
            ],
            "decision_tree": CLASSIFICATION_DECISION_TREE,
            "gate_fields": list(GATE_FIELDS),
            "gate_fields_source": (
                "the five comparisons of R1-ENTRY-LONG in "
                "tos/runtime/cp3/strategies/setup_d_long.strategy.yaml — four "
                "booleans plus z_x1000 against the bound threshold"
            ),
        },
        "attribution_table": [
            {
                "order": order,
                "name": rule.name,
                "ids": list(rule.ids),
                "why": rule.why,
                "matched_bars": sum(
                    1 for record in records if record.attribution_rule == rule.name
                ),
            }
            for order, rule in enumerate(ATTRIBUTION_RULES)
        ],
        "attribution_semantics": (
            "Ordered, first match wins. A bar with nothing to explain is "
            f"{ATTRIBUTION_AGREED!r}; a bar with something to explain that no "
            f"rule matches is {ATTRIBUTION_UNRESOLVED!r} and is listed in "
            "summary.json rather than given a reason. Every id a rule names is "
            "checked against the three lineages' declared_differences at run "
            "time (check attribution_ids_declared); an undeclared id is a "
            "refusal, not a dangling reference."
        ),
        "declared_differences_index": declared_index,
        "config": {
            "z_entry_max_x1000": ctx.z_entry_max_x1000,
            "z_entry_max_x1000_source": (
                "B1b lineage parents.strategy_bindings_file.bindings."
                "z_entry_max_x1000"
            ),
            "z_edge_units": ctx.z_edge_units,
            "z_edge_units_rationale": (
                "one x1000 quantization unit; B1a truncates z toward zero "
                "(B1a-D8) so a published integer understates the magnitude by "
                "at most one unit"
            ),
        },
        "common_mode": COMMON_MODE,
        "scope": {
            "compares": "decision and intent level only",
            "does_not_compare": SCOPE_NOTE,
        },
        "determinism": {
            "no_clock_reads": True,
            "no_clock_derived_timestamp": True,
            "no_rng": True,
            "note": (
                "every value in this sidecar is a function of (the three input "
                "files, their sidecars, this code, the checkout's git "
                "identity); two runs over the same inputs write byte-identical "
                "diff.jsonl, summary.json and lineage.json"
            ),
        },
        "output": outputs,
    }


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunResult:
    """Paths written plus the in-memory lineage and summary."""

    out_dir: Path
    diff_path: Path
    summary_path: Path
    lineage_path: Path
    lineage: dict[str, Any]
    summary: dict[str, Any]


def _sidecar_for(jsonl_path: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    return jsonl_path.parent / SIDECAR_FILENAME


def _load_ref(*, label: str, jsonl_path: Path, lineage_path: Path) -> ArtifactRef:
    jsonl_sha, lines = sha256_and_lines(jsonl_path)
    return ArtifactRef(
        label=label,
        jsonl_path=jsonl_path,
        jsonl_sha256=jsonl_sha,
        jsonl_lines=lines,
        lineage_path=lineage_path,
        lineage_sha256=sha256_file(lineage_path),
        lineage=load_lineage(lineage_path, label),
    )


def default_out_dir(identity: dict[str, Any]) -> Path:
    """``reports/tos-cp3/<symbol>_<window_start>_<window_end>/`` (module docstring)."""
    return DEFAULT_OUT_ROOT / (
        f"{identity['symbol']}_{identity['window_start']}_{identity['window_end']}"
    )


def run(
    *,
    fields_jsonl: Path,
    legacy_jsonl: Path,
    tos_jsonl: Path,
    out_dir: Path | None = None,
    fields_lineage: Path | None = None,
    legacy_lineage: Path | None = None,
    tos_lineage: Path | None = None,
) -> RunResult:
    """Refuse or diff; write ``diff.jsonl``, ``summary.json`` and ``lineage.json``."""
    refs = {
        LABEL_FIELDS: _load_ref(
            label=LABEL_FIELDS,
            jsonl_path=fields_jsonl,
            lineage_path=_sidecar_for(fields_jsonl, fields_lineage),
        ),
        LABEL_LEGACY: _load_ref(
            label=LABEL_LEGACY,
            jsonl_path=legacy_jsonl,
            lineage_path=_sidecar_for(legacy_jsonl, legacy_lineage),
        ),
        LABEL_TOS: _load_ref(
            label=LABEL_TOS,
            jsonl_path=tos_jsonl,
            lineage_path=_sidecar_for(tos_jsonl, tos_lineage),
        ),
    }
    checks: list[dict[str, Any]] = []

    # --- refusal 0: the attribution table cites only declared differences ---
    declared_index = declared_difference_index(
        {label: ref.lineage for label, ref in refs.items()}
    )
    declared_ids = {
        entry["id"] for entries in declared_index.values() for entry in entries
    }
    assert_attribution_ids_declared(ATTRIBUTION_RULES, declared_ids)
    checks.append(
        {
            "name": "attribution_ids_declared",
            "status": "PASS",
            "detail": (
                "every declared-difference id named by the attribution table "
                "exists in one of the three input lineages"
            ),
            "declared_ids": len(declared_ids),
            "cited_ids": sorted({i for rule in ATTRIBUTION_RULES for i in rule.ids}),
        }
    )

    # --- refusal 1: the window identities must agree ---
    b1a_identity = b1a_window_identity(refs[LABEL_FIELDS].lineage)
    b2_identity = b2_window_identity(refs[LABEL_LEGACY].lineage)
    differing = {
        field: {LABEL_FIELDS: b1a_identity[field], LABEL_LEGACY: b2_identity[field]}
        for field in WINDOW_IDENTITY_FIELDS
        if b1a_identity[field] != b2_identity[field]
    }
    if differing:
        raise DiffDecisionsError(
            "B1a and B2 describe different windows: "
            + "; ".join(
                f"{field} B1a={values[LABEL_FIELDS]!r} B2={values[LABEL_LEGACY]!r}"
                for field, values in differing.items()
            )
            + ". B2's lineage states the contract: 'B3 MUST REFUSE a (B1a, B2) "
            "pair whose join.window_identity blocks differ in any field, rather "
            "than join on raw_event_id and report the difference as a decision "
            "mismatch.'"
        )
    checks.append(
        {
            "name": "window_identity_agreement",
            "status": "PASS",
            "detail": (
                "B1a's projected identity equals B2's declared "
                "join.window_identity in all "
                f"{len(WINDOW_IDENTITY_FIELDS)} fields"
            ),
            "identity": dict(b2_identity),
        }
    )

    # --- refusal 2: each artifact is the one its own lineage describes ---
    self_digest_sources = {
        LABEL_FIELDS: ("output.jsonl_sha256", "output.jsonl_lines"),
        LABEL_LEGACY: ("output.jsonl_sha256", "output.jsonl_lines"),
        LABEL_TOS: ("output.trace_jsonl_sha256", "output.trace_jsonl_lines"),
    }
    for label, (sha_key, lines_key) in self_digest_sources.items():
        ref = refs[label]
        declared_sha = _dig(ref.lineage, sha_key, label)
        declared_lines = _dig(ref.lineage, lines_key, label)
        if declared_sha != ref.jsonl_sha256 or declared_lines != ref.jsonl_lines:
            raise DiffDecisionsError(
                f"{label} artifact {ref.jsonl_path} does not match its own "
                f"lineage {ref.lineage_path}: file sha256={ref.jsonl_sha256} "
                f"lines={ref.jsonl_lines}, lineage says sha256={declared_sha} "
                f"lines={declared_lines}. The lineage this report quotes must "
                "describe the file it read."
            )
    checks.append(
        {
            "name": "artifact_matches_its_own_lineage",
            "status": "PASS",
            "detail": (
                "each of the three files' sha256 and line count equals the "
                "value its own sidecar records"
            ),
            "sources": {k: list(v) for k, v in self_digest_sources.items()},
        }
    )

    # --- refusal 3: B1b consumed THIS fields.jsonl (and its sidecar) ---
    tos_parents = _dig(refs[LABEL_TOS].lineage, "parents", LABEL_TOS)
    parent_fields = tos_parents.get("fields_jsonl") or {}
    parent_lineage = tos_parents.get("fields_lineage_json") or {}
    fields_ref = refs[LABEL_FIELDS]
    if parent_fields.get("sha256") != fields_ref.jsonl_sha256:
        raise DiffDecisionsError(
            "B1b was not run over this fields.jsonl: its lineage records "
            f"parents.fields_jsonl.sha256={parent_fields.get('sha256')} but "
            f"{fields_ref.jsonl_path} hashes to {fields_ref.jsonl_sha256}. The "
            "TOS trace would then be about different field values than the ones "
            "this report shows beside it."
        )
    if parent_fields.get("lines") != fields_ref.jsonl_lines:
        raise DiffDecisionsError(
            "B1b's recorded parent line count "
            f"({parent_fields.get('lines')}) differs from this fields.jsonl "
            f"({fields_ref.jsonl_lines})"
        )
    if parent_lineage.get("sha256") != fields_ref.lineage_sha256:
        raise DiffDecisionsError(
            "B1b consumed a different B1a lineage sidecar: it records "
            f"parents.fields_lineage_json.sha256={parent_lineage.get('sha256')} "
            f"but {fields_ref.lineage_path} hashes to "
            f"{fields_ref.lineage_sha256}. The field policy and declared "
            "differences this report quotes would not be the ones the TOS run "
            "was governed by."
        )
    checks.append(
        {
            "name": "tos_parent_is_this_fields_artifact",
            "status": "PASS",
            "detail": (
                "B1b's parents.fields_jsonl sha256/lines and "
                "parents.fields_lineage_json sha256 all match the B1a artifact "
                "and sidecar given to this run"
            ),
            "fields_jsonl_sha256": fields_ref.jsonl_sha256,
            "fields_lineage_sha256": fields_ref.lineage_sha256,
        }
    )

    # --- refusal 4: equal line counts ---
    counts = {label: ref.jsonl_lines for label, ref in refs.items()}
    if len(set(counts.values())) != 1:
        raise DiffDecisionsError(
            "the three artifacts have different line counts "
            f"({counts}) — they cannot be joined line for line"
        )
    checks.append(
        {
            "name": "line_counts_equal",
            "status": "PASS",
            "detail": f"all three artifacts have {counts[LABEL_FIELDS]} lines",
            "lines": counts[LABEL_FIELDS],
        }
    )

    # --- refusals 5-7: ids, as_of_ms, floats (and the closed sets) ---
    legacy_outcomes = tuple(
        _dig(refs[LABEL_LEGACY].lineage, "outcomes.closed_set", LABEL_LEGACY)
    )
    joined = join_artifacts(
        fields_path=fields_jsonl,
        legacy_path=legacy_jsonl,
        tos_path=tos_jsonl,
        legacy_outcomes=legacy_outcomes,
    )
    checks.extend(joined.checks)

    bindings = _dig(
        refs[LABEL_TOS].lineage, "parents.strategy_bindings_file.bindings", LABEL_TOS
    )
    if "z_entry_max_x1000" not in bindings:
        raise DiffDecisionsError(
            "B1b lineage parents.strategy_bindings_file.bindings has no "
            "z_entry_max_x1000 — the deployed entry threshold is unknown, so "
            "the quantization-edge attribution cannot be evaluated"
        )
    ctx = DiffContext(z_entry_max_x1000=int(bindings["z_entry_max_x1000"]))

    records = classify_all(joined.bars, ctx)
    summary = build_summary(
        records=records,
        identity=b2_identity,
        declared_index=declared_index,
        ctx=ctx,
        tos_lineage=refs[LABEL_TOS].lineage,
    )

    diff_bytes = render_jsonl(records)
    summary_bytes = render_json(summary)
    self_floats = _float_paths(summary) + _float_paths(
        json.loads(summary_bytes.decode("utf-8"))
    )
    if self_floats:
        raise DiffDecisionsError(
            "this report would carry a float: " + ", ".join(self_floats)
        )
    checks.append(
        {
            "name": "report_carries_no_floats",
            "status": "PASS",
            "detail": (
                "summary.json holds integers, booleans, strings and nulls only "
                "— rates are reported as integer numerator/denominator plus a "
                "half-up rate_x10000"
            ),
        }
    )

    target = out_dir if out_dir is not None else default_out_dir(b2_identity)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DiffDecisionsError(f"cannot create {target}: {exc}") from exc
    diff_path = target / DIFF_FILENAME
    summary_path = target / SUMMARY_FILENAME
    lineage_path = target / LINEAGE_FILENAME

    lineage = build_lineage(
        refs=refs,
        identity=b2_identity,
        checks=checks,
        records=records,
        declared_index=declared_index,
        ctx=ctx,
        outputs={
            "diff_jsonl": DIFF_FILENAME,
            "diff_jsonl_sha256": hashlib.sha256(diff_bytes).hexdigest(),
            "diff_jsonl_bytes": len(diff_bytes),
            "diff_jsonl_lines": len(records),
            "summary_json": SUMMARY_FILENAME,
            "summary_json_sha256": hashlib.sha256(summary_bytes).hexdigest(),
            "summary_json_bytes": len(summary_bytes),
            "out_dir_layout": (
                "reports/tos-cp3/<symbol>_<window_start>_<window_end>/ by "
                "default (kickoff §5 step 2 left the layout to B3); "
                "reports/** is gitignored, artifacts are not committed"
            ),
        },
    )
    lineage_bytes = render_json(lineage)

    diff_path.write_bytes(diff_bytes)
    summary_path.write_bytes(summary_bytes)
    lineage_path.write_bytes(lineage_bytes)
    return RunResult(
        out_dir=target,
        diff_path=diff_path,
        summary_path=summary_path,
        lineage_path=lineage_path,
        lineage=lineage,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="diff_decisions",
        description=(
            "CP-3 B3 — bar-by-bar decision-level diff of B1a's fields, B2's "
            "legacy outcomes and B1b's TOS trace"
        ),
    )
    parser.add_argument(
        "--fields",
        type=Path,
        required=True,
        help="B1a fields.jsonl (its lineage.json sidecar is auto-discovered)",
    )
    parser.add_argument(
        "--legacy",
        type=Path,
        required=True,
        help="B2 decisions.jsonl (sidecar auto-discovered)",
    )
    parser.add_argument(
        "--tos",
        type=Path,
        required=True,
        help="B1b trace.jsonl (sidecar auto-discovered)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "output directory; default "
            "reports/tos-cp3/<symbol>_<window_start>_<window_end>/"
        ),
    )
    parser.add_argument(
        "--fields-lineage",
        type=Path,
        default=None,
        help="override the B1a lineage sidecar path",
    )
    parser.add_argument(
        "--legacy-lineage",
        type=Path,
        default=None,
        help="override the B2 lineage sidecar path",
    )
    parser.add_argument(
        "--tos-lineage",
        type=Path,
        default=None,
        help="override the B1b lineage sidecar path",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run(
            fields_jsonl=args.fields,
            legacy_jsonl=args.legacy,
            tos_jsonl=args.tos,
            out_dir=args.out,
            fields_lineage=args.fields_lineage,
            legacy_lineage=args.legacy_lineage,
            tos_lineage=args.tos_lineage,
        )
    except DiffDecisionsError as exc:
        print(f"diff_decisions: {exc}", file=sys.stderr)
        return 2

    summary = result.summary
    print(f"wrote {result.diff_path} ({summary['bars']} lines)")
    print(f"wrote {result.summary_path}")
    print(f"wrote {result.lineage_path}")
    print(f"diff sha256: {result.lineage['output']['diff_jsonl_sha256']}")
    print("buckets:")
    for bucket, count in summary["buckets"].items():
        print(f"  {bucket}: {count}")
    print("attribution rules:")
    for name, block in summary["attribution_rules"].items():
        ids = ",".join(block["ids"]) or "-"
        print(f"  {name}: {block['bars']} [{ids}]")
    for name, block in summary["rates"].items():
        print(
            f"{name}: {block['numerator']}/{block['denominator']} "
            f"(x10000={block['rate_x10000']})"
        )
    unresolved = summary["unresolved"]
    print(f"unresolved: {unresolved['count']}")
    for raw_event_id in unresolved["raw_event_ids"][:10]:
        print(f"  {raw_event_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
