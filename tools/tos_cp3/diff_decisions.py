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
it therefore keeps locally are pinned to B1a's by
``tests/tools/test_cp3_diff_decisions.py`` as NORMALIZED-AST SOURCE equality —
the function's own name, its argument names and its docstring may differ,
nothing else — so the two copies cannot become two implementations. (An
earlier revision said "byte-for-byte", which was not what the test did: it
compared one sample document's output, and a ``sort_keys`` divergence passed.)

What it refuses
---------------
A join on ``raw_event_id`` is only meaningful if the three artifacts are about
the same bars. The key carries no window anchor, so a mismatched trio is NOT
detectable from the lines themselves — only from the lineage blocks. B2's
lineage states the contract in its own words
(``join.b3_contract``): *"B3 MUST REFUSE a (B1a, B2) pair whose
join.window_identity blocks differ in any field, rather than join on
raw_event_id and report the difference as a decision mismatch."* This tool
implements that refusal and fifteen more (:data:`CHECK_NAMES`). A refused run
writes NOTHING — the refusal is exit code 2 and a message on stderr — so the
output lineage's ``checks`` list only ever enumerates checks that held; there
is no FAIL row and the list carries no ``status`` field claiming one. What
makes each entry a guard rather than a label is that
``tests/tools/test_cp3_diff_decisions.py`` carries a red proof for every one.

What it does NOT compare
------------------------
Fills and PnL. ``tos.backtest`` holds at most ONE order per scope for the whole
run (B1b-D1), so the first firing is realized and every later one is an exact
capacity denial; and its result types carry no Sharpe/PnL/return/edge field at
all (B1b's ``claims.performance_surface``: "ABSENT BY CONSTRUCTION"). kickoff
§3 B4 poses this and §4 결정 7 disposes of it as **체결 비교 포기** — the
comparison is decision and intent level, never fill for fill. ``summary.json`` says so in its ``scope``
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
#:
#: **1 -> 2 (2026-10-09, direction awareness).** Both sidecars lost and gained
#: keys, so a consumer written against v1 would read a v2 sidecar wrong rather
#: than fail: ``config.z_entry_max_x1000`` and its ``_source`` sibling became
#: ``config.z_entry_binding_key`` + ``config.z_entry_threshold_x1000`` +
#: ``config.z_entry_threshold_source`` (the key name now depends on the
#: direction); ``config.deployment_direction`` is new;
#: ``totals.legacy_fired_long_admitted_by_position_model`` became
#: ``totals.legacy_fired_in_deployment_direction_admitted_by_position_model``
#: beside a new ``totals.legacy_fired_in_deployment_direction``; and the third
#: rate's KEY is now per-direction
#: (``rates.tos_action_explained_by_a_legacy_{long,short}_fire``). ``diff.jsonl``
#: is unchanged — the LONG run still reproduces ``ce36450f…`` byte for byte —
#: which is exactly why the sidecars need the bump: the payload's stability
#: would otherwise suggest the whole report was unchanged.
#:
#: :data:`SUMMARY_SCHEMA_VERSION` moves with it: the two are bumped together
#: because every shape change so far has touched both, and a reader comparing
#: the two numbers should not have to work out which one lagged.
LINEAGE_SCHEMA_VERSION = 2

#: Summary schema version — see :data:`LINEAGE_SCHEMA_VERSION` for the 1 -> 2
#: change. A literal in ``build_summary`` before 2026-10-09, which is why the
#: shape moved without it.
SUMMARY_SCHEMA_VERSION = 2

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


#: Why this module has NO quantization-edge attribution rule — the derivation,
#: kept because an earlier revision shipped one and the premise was false.
#:
#: Let ``m = extreme_atr_mult``, ``f = m * 1000`` and ``T = -trunc(f)`` (the
#: deployed binding). B1a truncates toward zero, so for ``z < 0`` the published
#: integer is ``trunc(z*1000) = -floor(|z|*1000)`` and the TOS condition
#: ``trunc(z*1000) <= T`` is ``floor(|z|*1000) >= floor(f)``; the legacy
#: condition is ``|z|*1000 >= f``.
#:
#: (1) **f integral** — ``floor(y) >= n`` iff ``y >= n`` for integer ``n``, so
#:     the two conditions are IDENTICAL. No edge exists. This is what B1a's own
#:     D8 says ("a policy written on the integer NEVER fires where the legacy
#:     setup did not") and the earlier rule's comment contradicted it.
#: (2) **f non-integral** (e.g. ``m = 1.8005``) — TOS fires on
#:     ``|z|*1000 ∈ [floor(f), f)`` where legacy does not, so the TOS side is
#:     more permissive by at most one unit, ONE-SIDED and at the single integer
#:     ``z_x1000 == T``. On such a bar ``check()`` rejects at step 4 with
#:     ``NOT_EXTREME``, which means ``stall_ok`` and ``reversal_ok`` were never
#:     evaluated and B1a publishes them as ``False`` (its D5, fail-closed).
#:     ``R1-ENTRY-LONG`` ANDs both, so the TOS side yields NO_ACTION too: the
#:     quantization gap is MASKED by D5 and cannot produce a disagreement.
#:     The real run agrees — the legacy-outcome x TOS-kind matrix has zero
#:     ``NOT_EXTREME x ACTION`` bars.
#:
#: So there is no reachable bar to attribute, and a rule for it would only act
#: as a last-position catch-all converting bars the kickoff plan requires to be
#: left UNRESOLVED into a reason. ``tests/tools/test_cp3_diff_decisions.py``
#: pins (1) as arithmetic over a range of z, which is what would go red if the
#: binding stopped being ``-trunc(extreme_atr_mult * 1000)``.
#:
#: **The SHORT mirror (2026-10-09).** For ``z > 0`` the published integer is
#: ``trunc(z*1000) = floor(z*1000)`` and the TOS condition
#: ``trunc(z*1000) >= +trunc(f)`` is again ``floor(z*1000) >= floor(f)``, so
#: (1) and (2) hold verbatim with the inequality reflected: an integral ``f``
#: leaves no edge, a non-integral one leaves a one-integer gap that
#: ``NOT_EXTREME`` masks the same way. The derivation is therefore rendered
#: per direction rather than restated for one of them.
def quantization_edge_derivation(direction: str) -> str:
    """The derivation, with the inequality this deployment's side uses."""
    key = ENTRY_BINDING_KEY[direction]
    op = "<=" if direction == DIRECTION_LONG else ">="
    return (
        "No quantization-edge attribution rule exists. With an integral "
        "extreme_atr_mult*1000 the published-integer condition "
        f"trunc(z*1000) {op} {key} is IDENTICAL to the legacy "
        "abs(z) >= extreme_atr_mult (floor(y) >= n iff y >= n for integer n), "
        "so there is no edge; with a non-integral product the TOS side is "
        f"more permissive at the single integer z_x1000 == {key}, but on "
        "such a bar check() rejects at NOT_EXTREME and B1a therefore publishes "
        "stall_ok and reversal_ok as False (its D5, fail-closed), so R1's AND "
        "is false and the TOS side yields NO_ACTION as well. The gap is masked "
        "and no bar can be attributed to it; a bar that nonetheless reached "
        "the threshold unexplained is left UNRESOLVED rather than given this "
        "reason."
    )


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

#: The two members of B2's closed set this module names. The set itself is read
#: from B2's lineage at run time; these two are the ones classification and
#: attribution branch on, so :func:`assert_entry_outcome_literals` asserts both
#: are members of the set that was read — a rename upstream refuses instead of
#: silently moving every bar out of AGREE_ENTRY.
NAMED_LEGACY_OUTCOMES = (OUTCOME_FIRED, OUTCOME_LOW_CONFIDENCE)

#: The ``decision.direction`` tokens B2 publishes. Mirrors
#: ``emit_legacy_decisions.py::DIRECTION_TOKENS`` values; B2's lineage does not
#: declare them, so this is a literal, pinned to that module's own constant by
#: ``tests/tools/test_cp3_diff_decisions.py``. A FIRED bar whose direction is
#: outside this set is refused: direction decides AGREE_ENTRY vs
#: LEGACY_ONLY_ENTRY, and a case or token change would otherwise move every
#: long fire into LEGACY_ONLY_ENTRY and report the headline rate as 0/0.
DIRECTION_LONG = "LONG"
DIRECTION_SHORT = "SHORT"
DIRECTION_TOKENS = (DIRECTION_LONG, DIRECTION_SHORT)

#: The side a deployment does NOT render. Its legacy fires are the declared
#: difference B1b-D5, in whichever direction the compared run was.
OPPOSITE_DIRECTION = {DIRECTION_LONG: DIRECTION_SHORT, DIRECTION_SHORT: DIRECTION_LONG}

#: The bindings key each direction's entry rule reads, and the sign its
#: threshold must carry. The DSL has no ``abs()``, so a LONG render compares
#: the NEGATIVE side (``z_x1000 <= -1800``) and a SHORT render the POSITIVE one
#: (``z_x1000 >= +1800``) — two different keys because the bindings loader
#: refuses a key no rule references. Pairing them here is what lets this tool
#: refuse a B1b lineage whose declared direction and deployed threshold
#: disagree, instead of trusting whichever one it read first.
ENTRY_BINDING_KEY = {
    DIRECTION_LONG: "z_entry_max_x1000",
    DIRECTION_SHORT: "z_entry_min_x1000",
}

#: ``value * sign > 0`` must hold. A SHORT render with a negative threshold
#: would fire ``z_x1000 >= -1800`` on nearly every bar; a LONG render with a
#: positive one, likewise. The sign is a property of the derivation
#: (``∓trunc(extreme_atr_mult * 1000)``), not a style choice.
ENTRY_THRESHOLD_SIGN = {DIRECTION_LONG: -1, DIRECTION_SHORT: 1}

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
        return self.legacy_fired and self.legacy_direction == DIRECTION_LONG

    @property
    def legacy_fired_short(self) -> bool:
        return self.legacy_fired and self.legacy_direction == DIRECTION_SHORT

    def legacy_fired_in(self, direction: str) -> bool:
        """Did the legacy entry rule fire on this bar, in *direction*?"""
        return self.legacy_fired and self.legacy_direction == direction

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


def classification_decision_tree(direction: str) -> str:
    """The classifier, restated for the lineage, for the compared direction.

    A reader of the sidecar should not have to read this module to know what a
    bucket name means — nor have to guess which half of the legacy fires
    ``AGREE_ENTRY`` was counting over. That half is this deployment's own
    direction, which is why the sentence names it.
    """
    other = OPPOSITE_DIRECTION[direction]
    return (
        f"1. TOS ACTION and legacy FIRED {direction}            -> AGREE_ENTRY. "
        "2. TOS ACTION otherwise                        -> TOS_ONLY_ENTRY. "
        "3. not TOS ACTION and legacy FIRED (either direction) -> "
        "LEGACY_ONLY_ENTRY. "
        "4. TOS FLAT and legacy did not fire            -> "
        "TOS_EXIT_ON_LEGACY_<legacy outcome>. "
        "5. TOS NO_ACTION and legacy did not fire       -> AGREE_NO_ACTION. "
        "Exhaustive over outcome_kind x fired: every bar lands in exactly one "
        "bucket, and an outcome_kind outside TOS_OUTCOME_KINDS is a refusal, "
        f"not a bucket. AGREE_ENTRY is {direction}-only on the legacy side "
        "because this TOS deployment renders one direction (B1b-D5); a legacy "
        f"{other} fire is therefore LEGACY_ONLY_ENTRY, not a disagreement "
        f"about the {direction.lower()} rule."
    )


def classify(bar: JoinedBar, ctx: DiffContext) -> str:
    """The bar's bucket — exactly one, per :func:`classification_decision_tree`.

    ``ctx.direction`` is the direction B1b's lineage reports for the strategy
    file that produced the trace. It decides which legacy fires can agree with
    this run at all, so it is a parameter rather than the literal ``LONG`` the
    first revision hardcoded: that literal silently reported a SHORT render's
    headline agreement as ``0/374`` instead of refusing or reflecting.
    """
    if bar.tos_outcome_kind not in TOS_OUTCOME_KINDS:
        raise DiffDecisionsError(
            f"{bar.raw_event_id}: unknown TOS outcome_kind " f"{bar.tos_outcome_kind!r}"
        )
    if bar.tos_action:
        return (
            BUCKET_AGREE_ENTRY
            if bar.legacy_fired_in(ctx.direction)
            else BUCKET_TOS_ONLY_ENTRY
        )
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
    """What the compared TOS run deployed, read from B1b's own lineage.

    Both values come from the B1b sidecar and **nothing else** — there is no
    ``--direction`` flag on this tool and there must not be one. The direction
    decides which legacy fires are ``AGREE_ENTRY`` and which are the declared
    difference B1b-D5, so a caller-supplied token would let a run assert that
    the wrong half agreed and the report would carry no trace of the lie.
    ``parents.strategy_file.direction`` is itself derived by B1b from the
    authored ACTION targets (``cp3.strategy._single_direction``), so the chain
    ends at the strategy file.

    ``z_entry_threshold_x1000`` is read from
    ``parents.strategy_bindings_file.bindings`` under the key this direction's
    rule references (:data:`ENTRY_BINDING_KEY`). It is not a literal here: a
    threshold restated in a second place is a threshold that can disagree with
    the deployment it claims to describe. No attribution predicate reads it
    (see :func:`quantization_edge_derivation`); it is carried so the report
    records which threshold the compared run deployed, and so the direction and
    the threshold can be checked against each other.
    """

    direction: str
    z_entry_binding_key: str
    z_entry_threshold_x1000: int


@dataclass(frozen=True)
class AttributionRule:
    """One (predicate, declared-difference ids) pair, read in table order."""

    name: str
    ids: tuple[str, ...]
    why: str
    predicate: Callable[[JoinedBar, str, DiffContext], bool]


def _legacy_opposite_direction_entry(
    bar: JoinedBar, bucket: str, ctx: DiffContext
) -> bool:
    """A legacy fire on the unrendered side **that this run did not act on**.

    Scoped to ``LEGACY_ONLY_ENTRY`` deliberately (2026-10-09 review M2). Without
    the bucket test this rule also matched a ``TOS_ONLY_ENTRY`` bar — the legacy
    rule fired SHORT while the TOS policy proposed a LONG entry on the same bar,
    which is the most severe disagreement these artifacts can express — and
    filed it under B1b-D5, "no counterpart in THIS run by construction". That
    bar HAS a counterpart: this run acted, in the opposite direction. It must
    stay UNRESOLVED (real-data count: 0 in both the LONG and the SHORT run, so
    the fix moves no measured bar; the point is that it would not silently
    swallow one).
    """
    return (
        bucket == BUCKET_LEGACY_ONLY_ENTRY
        and bar.legacy_fired
        and bar.legacy_direction != ctx.direction
    )


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


def build_attribution_rules(direction: str) -> tuple[AttributionRule, ...]:
    """The attribution table — ordered, data-driven, first match wins.

    Every id named here must exist in one of the three lineages'
    ``declared_differences`` lists; :func:`assert_attribution_ids_declared`
    checks that at run time and refuses otherwise, so a rule cannot cite a
    difference nobody declared.

    Order matters and the two fill-level rules are LAST on purpose, and are
    scoped to the ``AGREE_ENTRY`` bucket. Every TOS ACTION in a B1b run after
    the first realized order is capacity-denied, so a capacity rule read
    earlier would absorb every entry disagreement and hide its decision-level
    cause. There is deliberately NO catch-all last entry: a bar nothing
    explains is UNRESOLVED (kickoff §5 2).

    **Only rule #1 depends on the direction**, and only in its name and prose:
    the thing it names is "a legacy fire on the half this deployment does not
    render", which is ``legacy_short_entry`` for a LONG run and
    ``legacy_long_entry`` for a SHORT one. The name is built rather than fixed
    so a reader of ``diff.jsonl`` sees which half was unrendered, and so the
    LONG table keeps the exact name the 2026-10-08 artifact recorded (diff
    sha256 ``ce36450f…`` still reproduces).

    Args:
        direction: ``LONG`` or ``SHORT``, from :class:`DiffContext`.

    Returns:
        The five rules, in read order.
    """
    other = OPPOSITE_DIRECTION[direction]
    key = ENTRY_BINDING_KEY[direction]
    op = "<=" if direction == DIRECTION_LONG else ">="
    return (
        AttributionRule(
            name=f"legacy_{other.lower()}_entry",
            ids=("B1b-D5",),
            why=(
                "The legacy entry fires on abs(z) >= extreme_atr_mult, i.e. "
                "BOTH sides. The DSL has no abs() and direction is a "
                "per-deployment fact, so this TOS deployment compares one side "
                f"only (z_x1000 {op} {key}) and the {other} half is a separate "
                "render with its own strategy file (kickoff §4 결정 4). A "
                f"legacy {other} fire has no counterpart in THIS run by "
                "construction. SCOPED to LEGACY_ONLY_ENTRY: if this run DID "
                f"act on such a bar (TOS ACTION {direction} against a legacy "
                f"{other} fire) the bar is a TOS_ONLY_ENTRY and the two sides "
                "disagree about DIRECTION, which is not what this difference "
                "explains — that bar stays UNRESOLVED."
            ),
            predicate=_legacy_opposite_direction_entry,
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
                "disagreement about when to exit. ⚠ OBLIGATION UNMET: B1b-D7's "
                "own note asks B3 to 'scope the legacy side to bars where a "
                "position was held'. This predicate does NOT do that — it reads "
                "`TOS FLAT and the legacy strategy did not fire`, because B2's "
                "payload carries no position or exposure field and nothing in "
                "these three artifacts says whether a legacy position was open on "
                "a bar. The count below is therefore an UPPER BOUND on the "
                "position-scoped comparison, not that comparison; see "
                "summary.json's scope.b1b_d7_obligation."
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
                "capacity denial (AT_MOST_ONE_EXPOSURE_HELD). kickoff §3 B4 poses "
                "this and §4 결정 7 disposes of it as '체결 비교 포기' "
                "(operator-approved 2026-10-07): the decision agreed on this "
                "bar and the denial is about the fill, which this report does not "
                "compare. This rule only reaches bars no EARLIER rule explains, so "
                "an AGREE_ENTRY bar that was also rejected by the position model "
                "carries that attribution instead and its capacity denial is NOT "
                "in its `attribution` list — the fact is on the line itself "
                "(`tos.capacity_denied`) and in summary.json's "
                "`totals.tos_action_capacity_denied`, which is where a reader "
                "counts denials."
            ),
            predicate=_agree_entry_capacity_denied,
        ),
    )


#: Every declared-difference id EITHER direction's table can cite. The two
#: tables differ only in rule #1's name and prose — never in the ids — so the
#: run-time check that "no rule cites an undeclared difference" is
#: direction-invariant and can therefore stay FIRST in :data:`CHECK_NAMES`,
#: before the direction has been read. ``tests/tools/test_cp3_diff_decisions.py``
#: pins the invariance rather than this comment asserting it.
ALL_ATTRIBUTION_RULES: tuple[AttributionRule, ...] = build_attribution_rules(
    DIRECTION_LONG
) + build_attribution_rules(DIRECTION_SHORT)


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
    rules: tuple[AttributionRule, ...],
) -> tuple[str, tuple[str, ...]]:
    """``(rule name, declared-difference ids)`` for this bar; first match wins.

    ``rules`` has no default on purpose: a default would be one direction's
    table, and a caller that forgot to pass the other's would get a silently
    LONG-shaped attribution for a SHORT run.
    """
    if not needs_attribution(bar, bucket):
        return ATTRIBUTION_AGREED, ()
    for rule in rules:
        if rule.predicate(bar, bucket, ctx):
            return rule.name, rule.ids
    return ATTRIBUTION_UNRESOLVED, ()


def assert_entry_outcome_literals(legacy_outcomes: tuple[str, ...]) -> None:
    """Refuse unless the outcomes this module branches on are in B2's own set.

    Concrete failing input: B2 renames ``LOW_CONFIDENCE`` (or drops it from
    ``outcomes.closed_set``). Without this, every bar that outcome names stops
    matching the low-confidence attribution rule, those bars become
    ``UNRESOLVED``, and nothing says why.
    """
    missing = [name for name in NAMED_LEGACY_OUTCOMES if name not in legacy_outcomes]
    if missing:
        raise DiffDecisionsError(
            "B2's declared outcomes.closed_set does not contain "
            f"{', '.join(missing)}, which this tool's classification and "
            "attribution branch on. The closed set moved; the comparison would "
            "silently stop recognising those bars."
        )


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
                f"{label} lineage has no {dotted} — this report quotes that "
                "value, so it cannot be produced without it"
            )
        node = node[part]
    return node


def _dig_mapping(lineage: dict[str, Any], dotted: str, label: str) -> dict[str, Any]:
    """:func:`_dig`, refusing when the value is not a block.

    Every caller that subscripts a dug-out value goes through this instead, so
    a malformed sidecar is the documented exit-2 refusal rather than a
    ``TypeError`` traceback at exit 1.
    """
    node = _dig(lineage, dotted, label)
    if not isinstance(node, dict):
        raise DiffDecisionsError(
            f"{label} lineage {dotted} is {type(node).__name__}, not a block"
        )
    return node


def b1a_window_identity(lineage: dict[str, Any]) -> dict[str, Any]:
    """B1a's window identity, projected from its dataset/strategy blocks."""
    return {
        field: _dig(lineage, B1A_IDENTITY_PROJECTION[field], LABEL_FIELDS)
        for field in WINDOW_IDENTITY_FIELDS
    }


def b2_window_identity(lineage: dict[str, Any]) -> dict[str, Any]:
    """B2's declared ``join.window_identity``, exactly as it records it."""
    block = _dig_mapping(lineage, "join.window_identity", LABEL_LEGACY)
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


def _published_gates(
    published: dict[str, Any], raw_event_id: str
) -> tuple[bool, bool, bool, bool]:
    """B1a's four gate booleans, refusing a missing or non-boolean one."""
    gates: list[bool] = []
    for gate in GATE_FIELDS:
        if gate not in published:
            raise DiffDecisionsError(
                f"{raw_event_id}: B1a publishes no {gate!r} — the tenant entry "
                "rule ANDs it, so its absence makes the comparison undefined"
            )
        value = published[gate]
        if not isinstance(value, bool):
            raise DiffDecisionsError(
                f"{raw_event_id}: B1a {gate!r} is {value!r}, not a boolean"
            )
        gates.append(value)
    return (gates[0], gates[1], gates[2], gates[3])


def _legacy_direction(
    decision: dict[str, Any], outcome: Any, raw_event_id: str
) -> str | None:
    """B2's direction token, refusing drift.

    Concrete failing input: ``emit_legacy_decisions`` publishes ``"Long"``.
    Direction decides AGREE_ENTRY vs LEGACY_ONLY_ENTRY, so without this every
    long fire would move bucket and the headline rate would read 0/0
    "undefined" with every check recorded.
    """
    direction = decision.get("direction")
    if direction is not None and direction not in DIRECTION_TOKENS:
        raise DiffDecisionsError(
            f"{raw_event_id}: B2 direction {direction!r} is not one of "
            f"{DIRECTION_TOKENS} — direction decides AGREE_ENTRY vs "
            "LEGACY_ONLY_ENTRY, so an unrecognised token would move bars "
            "between buckets silently"
        )
    if outcome == OUTCOME_FIRED and direction not in DIRECTION_TOKENS:
        raise DiffDecisionsError(
            f"{raw_event_id}: B2 reports {OUTCOME_FIRED} with direction "
            f"{direction!r} — a fire with no direction cannot be placed on "
            "either side of a one-directional comparison"
        )
    return direction


def _require_bool(
    block: dict[str, Any], key: str, label: str, raw_event_id: str
) -> bool:
    value = block.get(key)
    if not isinstance(value, bool):
        raise DiffDecisionsError(
            f"{raw_event_id}: {label} {key} is {value!r}, not a boolean"
        )
    return value


def project_bar(
    *,
    raw_event_id: str,
    as_of_ms: int,
    fields_payload: dict[str, Any],
    legacy_payload: dict[str, Any],
    tos_payload: dict[str, Any],
    index: int,
    legacy_outcome_set: set[str],
) -> JoinedBar:
    """One bar as all three artifacts describe it, every field refused on drift.

    Nothing here reads a value with a bare ``.get`` and compares it to a
    literal: an unrecognised outcome, outcome_kind, direction or non-boolean
    flag is a refusal, because every one of them decides a bucket.
    """
    published = _require(fields_payload, "fields", LABEL_FIELDS, index)
    if not isinstance(published, dict):
        raise DiffDecisionsError(f"B1a line {index + 1} fields is not a block")
    decision = _require(legacy_payload, "decision", LABEL_LEGACY, index)
    if not isinstance(decision, dict):
        raise DiffDecisionsError(f"B2 line {index + 1} decision is not a block")

    legacy_outcome = decision.get("outcome")
    direction = _legacy_direction(decision, legacy_outcome, raw_event_id)
    if legacy_outcome not in legacy_outcome_set:
        raise DiffDecisionsError(
            f"{raw_event_id}: legacy outcome {legacy_outcome!r} is not in B2's "
            "declared closed set — a bucket named after it would name an "
            "outcome B2 does not claim to produce"
        )
    tos_kind = tos_payload.get("outcome_kind")
    if tos_kind not in TOS_OUTCOME_KINDS:
        raise DiffDecisionsError(
            f"{raw_event_id}: TOS outcome_kind {tos_kind!r} is not one of "
            f"{TOS_OUTCOME_KINDS}"
        )
    z_value = published.get("z_x1000")
    if not isinstance(z_value, int) or isinstance(z_value, bool):
        raise DiffDecisionsError(
            f"{raw_event_id}: B1a z_x1000 is {z_value!r}, not an integer"
        )
    return JoinedBar(
        raw_event_id=raw_event_id,
        as_of_ms=as_of_ms,
        legacy_outcome=str(legacy_outcome),
        legacy_direction=direction,
        admitted=_require_bool(
            decision,
            "would_be_admitted_by_legacy_position_model",
            "B2",
            raw_event_id,
        ),
        tos_outcome_kind=str(tos_kind),
        tos_rule_id=tos_payload.get("rule_id"),
        tos_capacity_denied=_require_bool(
            tos_payload, "capacity_denied", "B1b", raw_event_id
        ),
        gates=_published_gates(published, raw_event_id),
        z_x1000=z_value,
    )


def _refuse_bar_mismatch(
    id_mismatch: dict[str, Any] | None, as_of_mismatch: dict[str, Any] | None
) -> None:
    """Turn a recorded lockstep disagreement into the refusal, naming the position."""
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


def _join_checks(
    bars: list[JoinedBar], legacy_outcomes: tuple[str, ...]
) -> list[dict[str, Any]]:
    """The per-line checks the lockstep pass enforced, in CHECK_NAMES order."""
    return [
        check_entry(
            "raw_event_id_sequences_identical",
            "every position of the three artifacts carries the same " "raw_event_id",
            bars=len(bars),
        ),
        check_entry(
            "as_of_ms_identical",
            "every position carries the same as_of_ms in all three",
        ),
        check_entry(
            "no_floats_in_payloads",
            "enforced by json.loads parse_float/parse_constant hooks on every "
            "line of all three artifacts, so a float LITERAL is refused even "
            "where its value is integral",
        ),
        check_entry(
            "legacy_outcome_in_declared_closed_set",
            "every B2 outcome is a member of that run's lineage "
            "outcomes.closed_set, so every TOS_EXIT_ON_LEGACY_<outcome> bucket "
            "name is one B2 declares",
            closed_set_size=len(legacy_outcomes),
        ),
        check_entry(
            "legacy_direction_in_published_token_set",
            "every B2 direction is null or one of "
            f"{list(DIRECTION_TOKENS)}, and every {OUTCOME_FIRED} bar carries "
            "one of them — direction decides AGREE_ENTRY vs LEGACY_ONLY_ENTRY, "
            "so a token change must refuse rather than move bars between "
            "buckets",
            tokens=list(DIRECTION_TOKENS),
        ),
        check_entry(
            "tos_outcome_kind_in_closed_set",
            f"every B1b outcome_kind is one of {list(TOS_OUTCOME_KINDS)}",
        ),
    ]


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

        bars.append(
            project_bar(
                raw_event_id=str(fields_id),
                as_of_ms=int(fields_as_of),
                fields_payload=fields_payload,
                legacy_payload=legacy_payload,
                tos_payload=tos_payload,
                index=index,
                legacy_outcome_set=legacy_outcome_set,
            )
        )

    _refuse_bar_mismatch(id_mismatch, as_of_mismatch)
    checks.extend(_join_checks(bars, legacy_outcomes))
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
    """Bucket and attribute every bar, in input order.

    The attribution table is built ONCE from ``ctx.direction``, so every line
    in one ``diff.jsonl`` is attributed by the same table — the table cannot
    change between bars of a run.
    """
    rules = build_attribution_rules(ctx.direction)
    records: list[DiffRecord] = []
    for bar in bars:
        bucket = classify(bar, ctx)
        rule_name, ids = attribute(bar, bucket, ctx, rules)
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


#: B1b-D7 asks B3 for something these three artifacts cannot supply. Stated,
#: not silently skipped, and NOT replaced by an inferred position state.
B1B_D7_OBLIGATION_NOTE = (
    "UNMET. B1b-D7's note asks that 'B3's diff has to scope the legacy side "
    "to bars where a position was held' "
    "(tos/runtime/cp3/differences.py, declared difference B1b-D7). This "
    "report does not: B2's per-bar payload carries no position or exposure "
    "field, and neither B1a's fields nor B1b's trace says whether a legacy "
    "Setup D position was open on a bar — the walk-forward position model is "
    "visible only as the per-bar verdict "
    "would_be_admitted_by_legacy_position_model, which answers 'was this fire "
    "admitted', not 'was something open now'. So the "
    "TOS_EXIT_ON_LEGACY_<outcome> buckets and the "
    "tos_flat_without_legacy_fire attribution count TOS FLAT INTENT on bars "
    "where the legacy strategy did not fire, which is an UPPER BOUND on the "
    "position-scoped comparison B1b-D7 asks for. No position state is "
    "inferred here: deriving one from the admitted flag plus an exit "
    "simulation would be a fourth implementation of the harness's exit path "
    "(B2-L3) and its errors would be reported as policy differences. Closing "
    "this needs a position/exposure field published by one of the producers, "
    "which is a B2 or kernel change and outside this tool."
)

#: Said in the summary rather than left to be inferred from a missing section.
SCOPE_NOTE = (
    "Fills and PnL are NOT compared. Two independent reasons, both recorded by "
    "the TOS artifact itself: (1) tos.backtest holds at most ONE order per "
    "scope for the whole run, so after the first realized order every firing is "
    "an exact capacity denial (B1b-D1); kickoff §3 B4 poses this and §4 결정 7 "
    "disposes of it as '체결 비교 포기' (operator-approved 2026-10-07) — the "
    "comparison is decision and intent level, never fill for fill. (2) The performance surface is sealed: no Sharpe, PnL, return or "
    "edge field exists anywhere in tos.backtest's result types (design #33 "
    "§1.2 B1), so the TOS side cannot make a performance claim to compare "
    "against. The legacy side's would_be_admitted_by_legacy_position_model flag "
    "is a GATING verdict, not a fill: it emits no PnL, slippage, commission or "
    "quantity (B2-L3), and it is an upper bound on what paper would have "
    "entered because the live post-exit cooldown is absent from it (B2-L10)."
)


def _summary_totals(
    records: list[DiffRecord], buckets: Counter[str], ctx: DiffContext
) -> dict[str, int]:
    """The counts both agreement rates are computed from.

    Both directions are counted unconditionally so a reader sees the whole
    legacy FIRED split, and the rate denominators then name the one this run
    rendered (``..._in_deployment_direction``) rather than a fixed ``_long``
    key that is the wrong half for half the deployments.
    """
    direction = ctx.direction
    return {
        "legacy_fired": sum(1 for r in records if r.bar.legacy_fired),
        "legacy_fired_long": sum(1 for r in records if r.bar.legacy_fired_long),
        "legacy_fired_short": sum(1 for r in records if r.bar.legacy_fired_short),
        "legacy_fired_in_deployment_direction": sum(
            1 for r in records if r.bar.legacy_fired_in(direction)
        ),
        "legacy_fired_in_deployment_direction_admitted_by_position_model": sum(
            1 for r in records if r.bar.legacy_fired_in(direction) and r.bar.admitted
        ),
        "agree_entry": buckets.get(BUCKET_AGREE_ENTRY, 0),
        "agree_entry_admitted_by_position_model": sum(
            1 for r in records if r.bucket == BUCKET_AGREE_ENTRY and r.bar.admitted
        ),
        "tos_action": sum(1 for r in records if r.bar.tos_action),
        "tos_action_capacity_denied": sum(
            1 for r in records if r.bar.tos_action and r.bar.tos_capacity_denied
        ),
        "tos_flat": sum(1 for r in records if r.bar.tos_flat),
        "tos_no_action": sum(
            1 for r in records if r.bar.tos_outcome_kind == TOS_NO_ACTION
        ),
    }


def _summary_rates(totals: dict[str, int], ctx: DiffContext) -> dict[str, Any]:
    """The headline rates, each with the definition it is a rate OF.

    Rule level and position-model level differ in their DENOMINATOR: the first
    asks "did the two entry RULES fire on the same bars", the second restricts
    to the fires the walk-forward single-position model would actually have
    entered. Both are computed, because "agreement" without saying which
    question it answers is the thing this report exists not to say.

    Every denominator is scoped to ``ctx.direction``, and every definition
    names it: a rate whose denominator is the other half would read as a
    catastrophic disagreement while actually measuring nothing.
    """
    side = ctx.direction
    lower = side.lower()
    return {
        "rule_level_entry_agreement": {
            "definition": (
                "AGREE_ENTRY / (legacy outcome FIRED and direction "
                f"{side}). 'Did the tenant policy's entry rule fire on the "
                "bars the legacy ENTRY RULE fired on, "
                f"{lower} side?' Neither side's "
                "position state enters this rate: it is a rule-to-rule "
                f"comparison. The denominator is {side}-only because this TOS "
                "deployment renders one direction (B1b-D5)."
            ),
            **_rate(
                totals["agree_entry"],
                totals["legacy_fired_in_deployment_direction"],
            ),
        },
        "position_model_level_entry_agreement": {
            "definition": (
                "(AGREE_ENTRY and would_be_admitted_by_legacy_position_model) "
                f"/ (legacy FIRED {side} and would_be_admitted_by_legacy_"
                f"position_model). 'Of the {lower} fires the walk-forward "
                "harness's single-position model would actually have entered, "
                "on how many did the tenant policy also propose an entry?' The "
                "TOS side contributes no position state to either side of this "
                "rate — it has none (B1b-D7) — so the rate narrows the "
                "denominator only."
            ),
            **_rate(
                totals["agree_entry_admitted_by_position_model"],
                totals[
                    "legacy_fired_in_deployment_direction_admitted_by_position_model"
                ],
            ),
        },
        f"tos_action_explained_by_a_legacy_{lower}_fire": {
            "definition": (
                "AGREE_ENTRY / (TOS outcome_kind ACTION). The same numerator "
                "read from the TOS side: 'of the bars where the tenant policy "
                "proposed an entry, on how many did the legacy rule also fire "
                f"{lower}?' Below 1 because the published field set cannot "
                "express min_confidence, so the policy is a SUPERSET of "
                "'legacy fired' (B1a-D1 / B2-L9)."
            ),
            **_rate(totals["agree_entry"], totals["tos_action"]),
        },
    }


def _summary_scope(tos_lineage: dict[str, Any]) -> dict[str, Any]:
    """What this report does NOT compare, and the TOS counts that say why."""
    counts = tos_lineage.get("counts")
    counts = counts if isinstance(counts, dict) else {}
    claims = tos_lineage.get("claims")
    claims = claims if isinstance(claims, dict) else {}
    return {
        "fills_and_pnl_not_compared": SCOPE_NOTE,
        "b1b_d7_obligation": B1B_D7_OBLIGATION_NOTE,
        "tos_fill_records": counts.get("fill_records"),
        "tos_handoffs": counts.get("handoffs"),
        "tos_capacity_denials": counts.get("capacity_denials"),
        "tos_realized_orders": counts.get("realized_orders"),
        "tos_realized_orders_note": (
            "echoed from B1b's own counts, which it added so that handoffs=1 "
            "is not misread as 'one bar handed off out of many': ONE order was "
            "realized in the whole run, on the bar named here, and every later "
            "firing is a capacity denial (B1b-D1). Read beside "
            "totals.tos_action_capacity_denied."
        ),
        "tos_performance_surface": claims.get("performance_surface"),
        "tos_oracle_scope": claims.get("oracle_scope"),
    }


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

    rules_table = build_attribution_rules(ctx.direction)
    totals = _summary_totals(records, buckets, ctx)
    unresolved = [
        r.bar.raw_event_id
        for r in records
        if r.attribution_rule == ATTRIBUTION_UNRESOLVED
    ]
    absorbed = {
        label: [
            {
                "id": entry["id"],
                "item": entry["item"],
                "absorbed_bars": ids.get(entry["id"], 0),
            }
            for entry in entries
        ]
        for label, entries in declared_index.items()
    }

    return {
        "summary_schema_version": SUMMARY_SCHEMA_VERSION,
        "tool": {"name": "tools/tos_cp3/diff_decisions.py", "source_id": SOURCE_ID},
        "window_identity": dict(identity),
        "bars": len(records),
        "buckets": dict(sorted(buckets.items())),
        "attribution_rules": {
            name: {
                "bars": count,
                "ids": list(
                    next(
                        (rule.ids for rule in rules_table if rule.name == name),
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
        "totals": totals,
        "rates": _summary_rates(totals, ctx),
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
                "difference is absent. ⚠ And for an id NO attribution rule "
                "cites, the zero is STRUCTURAL: it would be zero however the "
                "window behaved, so it is not evidence about the difference at "
                "all. Check attribution_table[].ids before reading a zero as a "
                "measurement; the ids that can be non-zero are exactly the "
                "ones listed there. What a bar no rule explains produces is an "
                "UNRESOLVED entry, which is why the unresolved count — not a "
                "zero here — is what backs 'this window hid nothing'."
            ),
            "cited_ids": sorted(
                {difference_id for rule in rules_table for difference_id in rule.ids}
            ),
            "by_artifact": absorbed,
        },
        "config": _lineage_config(ctx),
        "scope": _summary_scope(tos_lineage),
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
    "scalars came from — ADR-002-018 §10's point about a shared library being "
    "a common mode rather than independent corroboration, which all three "
    "artifacts restate in their own common_mode blocks."
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


#: What "first match wins" and UNRESOLVED mean, restated for a reader of the
#: sidecar who has not read this module.
ATTRIBUTION_SEMANTICS = (
    "Ordered, first match wins. A bar with nothing to explain is "
    f"{ATTRIBUTION_AGREED!r}; a bar with something to explain that no "
    f"rule matches is {ATTRIBUTION_UNRESOLVED!r} and is listed in "
    "summary.json rather than given a reason. Every id a rule names is "
    "checked against the three lineages' declared_differences at run "
    "time (check attribution_ids_declared); an undeclared id is a "
    "refusal, not a dangling reference. There is no catch-all last "
    "entry, and in particular no quantization-edge rule — see "
    "config.quantization_edge for the derivation of why none can "
    "match a bar these producers can emit."
)


def _lineage_classification(
    records: list[DiffRecord], refs: dict[str, ArtifactRef], ctx: DiffContext
) -> dict[str, Any]:
    """What a bucket name means, and which strategy the gate list came from."""
    return {
        "buckets": sorted({record.bucket for record in records}),
        "bucket_families": [
            BUCKET_AGREE_NO_ACTION,
            BUCKET_AGREE_ENTRY,
            BUCKET_TOS_ONLY_ENTRY,
            BUCKET_LEGACY_ONLY_ENTRY,
            f"{BUCKET_TOS_EXIT_PREFIX}<legacy outcome>",
        ],
        "decision_tree": classification_decision_tree(ctx.direction),
        "gate_fields": list(GATE_FIELDS),
        "gate_fields_source": (
            f"the five comparisons of R1-ENTRY-{ctx.direction} in the strategy "
            "file identified below — four booleans plus z_x1000 against the "
            "bound threshold. The field NAMES are direction-invariant (B1a "
            "publishes no SHORT variant: the gate booleans' direction comes "
            "from the sign of z, not from the deployment), so this list is one "
            "literal in this tool, which never reads either file; "
            "tests/tools/test_cp3_diff_decisions.py parses BOTH committed "
            "strategy YAMLs and pins the list against each R1's own refs, so a "
            "fifth gate or a rename in either goes red there, not silently "
            "green here."
        ),
        "gate_fields_derived_from_strategy": {
            key: value
            for key, value in (
                refs[LABEL_TOS]
                .lineage.get("parents", {})
                .get("strategy_file", {})
                .items()
            )
            if key in ("path", "sha256", "canonical_digest", "strategy_id")
        },
    }


def _lineage_attribution_table(
    records: list[DiffRecord], ctx: DiffContext
) -> list[dict[str, Any]]:
    """The ordered table as it was read, with each rule's match count."""
    return [
        {
            "order": order,
            "name": rule.name,
            "ids": list(rule.ids),
            "why": rule.why,
            "matched_bars": sum(
                1 for record in records if record.attribution_rule == rule.name
            ),
        }
        for order, rule in enumerate(build_attribution_rules(ctx.direction))
    ]


def _lineage_config(ctx: DiffContext) -> dict[str, Any]:
    """The compared run's operating point, read from B1b's own lineage.

    One function, used by both ``summary.json`` and ``lineage.json`` — the
    previous revision wrote the same three keys twice with two different
    source strings, which is the shape that drifts.
    """
    return {
        "deployment_direction": ctx.direction,
        "deployment_direction_source": (
            "B1b lineage parents.strategy_file.direction, which B1b derives "
            "from the authored ACTION targets (cp3.strategy._single_direction)."
            " This tool has NO --direction flag: the direction decides which "
            "legacy fires are AGREE_ENTRY and which are B1b-D5, so it is read "
            "from the artifact, never supplied by the caller"
        ),
        "z_entry_binding_key": ctx.z_entry_binding_key,
        "z_entry_threshold_x1000": ctx.z_entry_threshold_x1000,
        "z_entry_threshold_source": (
            "B1b lineage parents.strategy_bindings_file.bindings."
            f"{ctx.z_entry_binding_key} — the key THIS direction's entry rule "
            "references (the bindings loader refuses an unreferenced key, so "
            "the two directions carry different key names)"
        ),
        "quantization_edge": quantization_edge_derivation(ctx.direction),
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
        "classification": _lineage_classification(records, refs, ctx),
        "attribution_table": _lineage_attribution_table(records, ctx),
        "attribution_semantics": ATTRIBUTION_SEMANTICS,
        "declared_differences_index": declared_index,
        "config": _lineage_config(ctx),
        "common_mode": COMMON_MODE,
        "scope": {
            "compares": "decision and intent level only",
            "does_not_compare": SCOPE_NOTE,
            "b1b_d7_obligation": B1B_D7_OBLIGATION_NOTE,
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


#: The checks this tool performs, in the order the lineage records them. The
#: list is the enumeration — prose that states a count is pinned to
#: ``len(CHECK_NAMES)`` by the test suite, so the four-different-numbers defect
#: an independent review found in the first revision cannot recur.
CHECK_NAMES = (
    "attribution_ids_declared",
    "entry_outcome_literals_are_closed_set_members",
    "window_identity_agreement",
    "strategy_yaml_and_input_files_agreement",
    "artifact_matches_its_own_lineage",
    "tos_parent_is_this_fields_artifact",
    "tos_deployment_direction_matches_entry_binding",
    "line_counts_equal",
    "raw_event_id_sequences_identical",
    "as_of_ms_identical",
    "no_floats_in_payloads",
    "legacy_outcome_in_declared_closed_set",
    "legacy_direction_in_published_token_set",
    "tos_outcome_kind_in_closed_set",
    "buckets_sum_equals_input_line_count",
    "report_carries_no_floats",
)


def check_entry(name: str, detail: str, **extra: Any) -> dict[str, Any]:
    """One ``checks`` row. No ``status`` field — see the module docstring.

    A refused run writes no artifact, so a row can only ever describe a check
    that held; a ``status`` key would be a literal that is always the same.
    """
    if name not in CHECK_NAMES:
        raise DiffDecisionsError(f"{name!r} is not in CHECK_NAMES")
    return {"name": name, "detail": detail, **extra}


def _canonical_digest(value: Any) -> str:
    """sha256 over a canonical JSON rendering — used to compare long lists."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _check_attribution_ids(
    refs: dict[str, ArtifactRef],
) -> tuple[dict[str, list[dict[str, str]]], dict[str, Any]]:
    declared_index = declared_difference_index(
        {label: ref.lineage for label, ref in refs.items()}
    )
    declared_ids = {
        entry["id"] for entries in declared_index.values() for entry in entries
    }
    assert_attribution_ids_declared(ALL_ATTRIBUTION_RULES, declared_ids)
    return declared_index, check_entry(
        "attribution_ids_declared",
        "every declared-difference id named by the attribution table exists in "
        "one of the three input lineages",
        declared_ids=len(declared_ids),
        cited_ids=sorted({i for rule in ALL_ATTRIBUTION_RULES for i in rule.ids}),
    )


def _check_window_identity(
    refs: dict[str, ArtifactRef],
) -> tuple[dict[str, Any], dict[str, Any]]:
    b1a_identity = b1a_window_identity(refs[LABEL_FIELDS].lineage)
    b2_identity = b2_window_identity(refs[LABEL_LEGACY].lineage)
    differing = {
        field: (b1a_identity[field], b2_identity[field])
        for field in WINDOW_IDENTITY_FIELDS
        if b1a_identity[field] != b2_identity[field]
    }
    if differing:
        raise DiffDecisionsError(
            "B1a and B2 describe different windows: "
            + "; ".join(
                f"{field} B1a={a!r} B2={b!r}" for field, (a, b) in differing.items()
            )
            + ". B2's lineage states the contract: 'B3 MUST REFUSE a (B1a, B2) "
            "pair whose join.window_identity blocks differ in any field, rather "
            "than join on raw_event_id and report the difference as a decision "
            "mismatch.'"
        )
    return b2_identity, check_entry(
        "window_identity_agreement",
        "B1a's projected identity equals B2's declared join.window_identity in "
        f"all {len(WINDOW_IDENTITY_FIELDS)} fields",
        identity=dict(b2_identity),
    )


def _check_strategy_and_inputs(refs: dict[str, ArtifactRef]) -> dict[str, Any]:
    """The (B1a, B2) edge, pinned on more than the six identity fields.

    Concrete failing input: the Setup D YAML's ``extreme_atr_mult`` is edited
    between the B1a run and the B2 run, or one of them reads a re-written
    Parquet part. The six identity fields are all unchanged, every
    ``raw_event_id`` still lines up, and the two sides would be compared as if
    they had run the same strategy over the same bytes. The (B1a, B1b) edge is
    already sha-pinned through B1b's ``parents``; this closes the asymmetry.
    """
    pins: dict[str, dict[str, Any]] = {}
    for label in (LABEL_FIELDS, LABEL_LEGACY):
        lineage = refs[label].lineage
        strategy = _dig_mapping(lineage, "strategy", label)
        dataset = _dig_mapping(lineage, "dataset", label)
        for key, where in (("sha256", strategy), ("path", strategy)):
            if key not in where:
                raise DiffDecisionsError(f"{label} lineage strategy has no {key}")
        if "input_files" not in dataset:
            raise DiffDecisionsError(f"{label} lineage dataset has no input_files")
        pins[label] = {
            "strategy_path": strategy["path"],
            "strategy_sha256": strategy["sha256"],
            "input_files_digest": _canonical_digest(dataset["input_files"]),
            "input_file_count": dataset.get("input_file_count"),
        }
    differing = {
        key: (pins[LABEL_FIELDS][key], pins[LABEL_LEGACY][key])
        for key in pins[LABEL_FIELDS]
        if pins[LABEL_FIELDS][key] != pins[LABEL_LEGACY][key]
    }
    if differing:
        raise DiffDecisionsError(
            "B1a and B2 did not read the same strategy file and input bytes: "
            + "; ".join(
                f"{key} B1a={a!r} B2={b!r}" for key, (a, b) in differing.items()
            )
            + ". The six window-identity fields cannot see this, so a parameter "
            "or data edit between the two runs would be reported as a decision "
            "difference."
        )
    return check_entry(
        "strategy_yaml_and_input_files_agreement",
        "B1a and B2 record the same strategy YAML path and sha256, the same "
        "input-file count, and the same digest over dataset.input_files",
        **pins[LABEL_FIELDS],
    )


#: Where each artifact's own sidecar records its payload digest and line count.
SELF_DIGEST_SOURCES = {
    LABEL_FIELDS: ("output.jsonl_sha256", "output.jsonl_lines"),
    LABEL_LEGACY: ("output.jsonl_sha256", "output.jsonl_lines"),
    LABEL_TOS: ("output.trace_jsonl_sha256", "output.trace_jsonl_lines"),
}


def _check_self_digests(refs: dict[str, ArtifactRef]) -> dict[str, Any]:
    for label, (sha_key, lines_key) in SELF_DIGEST_SOURCES.items():
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
    return check_entry(
        "artifact_matches_its_own_lineage",
        "each of the three files' sha256 and line count equals the value its "
        "own sidecar records",
        sources={k: list(v) for k, v in SELF_DIGEST_SOURCES.items()},
    )


def _check_tos_parent(refs: dict[str, ArtifactRef]) -> dict[str, Any]:
    tos_parents = _dig_mapping(refs[LABEL_TOS].lineage, "parents", LABEL_TOS)
    parent_fields = tos_parents.get("fields_jsonl")
    parent_lineage = tos_parents.get("fields_lineage_json")
    if not isinstance(parent_fields, dict) or not isinstance(parent_lineage, dict):
        raise DiffDecisionsError(
            "B1b lineage parents must carry fields_jsonl and "
            "fields_lineage_json blocks — without them nothing ties the trace "
            "to a particular field stream"
        )
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
    return check_entry(
        "tos_parent_is_this_fields_artifact",
        "B1b's parents.fields_jsonl sha256/lines and "
        "parents.fields_lineage_json sha256 all match the B1a artifact and "
        "sidecar given to this run",
        fields_jsonl_sha256=fields_ref.jsonl_sha256,
        fields_lineage_sha256=fields_ref.lineage_sha256,
    )


def _check_line_counts(refs: dict[str, ArtifactRef]) -> tuple[int, dict[str, Any]]:
    counts = {label: ref.jsonl_lines for label, ref in refs.items()}
    if len(set(counts.values())) != 1:
        raise DiffDecisionsError(
            "the three artifacts have different line counts "
            f"({counts}) — they cannot be joined line for line"
        )
    lines = counts[LABEL_FIELDS]
    return lines, check_entry(
        "line_counts_equal",
        f"all three artifacts have {lines} lines",
        lines=lines,
    )


def _read_deployment_context(
    refs: dict[str, ArtifactRef],
) -> tuple[DiffContext, dict[str, Any]]:
    """The compared run's direction + entry threshold, cross-checked.

    Three ways to fail, each with a concrete failing input:

    * **no usable direction** — B1b's lineage has no
      ``parents.strategy_file.direction``, or it is a token outside
      :data:`DIRECTION_TOKENS` (a trace produced before 2026-10-09, or by a
      fork that renamed the token). Without it this tool would have to assume
      one, and the assumption it used to make was ``LONG``: a SHORT trace then
      reported ``rule_level_entry_agreement`` as ``0/374`` — a catastrophic
      disagreement that never happened.
    * **the threshold key for that direction is absent or not an int** — e.g.
      a SHORT lineage carrying only ``z_entry_max_x1000``. The bindings loader
      refuses a key no rule references, so the key present IS evidence of which
      side the rule compares, and a lineage whose key contradicts its declared
      direction is describing two different deployments. ``both`` keys present
      is the same failure and is refused too: "the key present is evidence"
      only holds while exactly one is — a check that read the expected key and
      ignored the other would admit the very thing this sentence claims it
      rejects.
    * **the threshold's sign contradicts the direction** — a SHORT render with
      ``z_entry_min_x1000: -1800`` would fire ``z_x1000 >= -1800`` on nearly
      every bar, and the resulting "agreement" would be an artifact of the
      wrong sign rather than a measurement. The sign is a property of the
      derivation ``∓trunc(extreme_atr_mult * 1000)``, not a style choice.

    Returns:
        ``(context, the recorded check row)``.
    """
    strategy = _dig_mapping(refs[LABEL_TOS].lineage, "parents.strategy_file", LABEL_TOS)
    direction = strategy.get("direction")
    if direction not in DIRECTION_TOKENS:
        raise DiffDecisionsError(
            "B1b lineage parents.strategy_file.direction is "
            f"{direction!r}, not one of {DIRECTION_TOKENS}. The direction "
            "decides which legacy fires this run could have agreed with "
            "(AGREE_ENTRY) and which are the declared difference B1b-D5; this "
            "tool reads it from the artifact and has no flag to override it, "
            "so an unreadable direction is a refusal, never a default"
        )
    key = ENTRY_BINDING_KEY[direction]
    bindings = _dig_mapping(
        refs[LABEL_TOS].lineage, "parents.strategy_bindings_file.bindings", LABEL_TOS
    )
    value = bindings.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise DiffDecisionsError(
            "B1b lineage parents.strategy_bindings_file.bindings has no "
            f"integer {key} — that is the key a {direction} entry rule "
            f"references, and the bindings present are {sorted(bindings)}. "
            "The threshold the compared run deployed is unknown, and the "
            "declared direction is not corroborated by the binding it would "
            f"have to have (got {value!r})"
        )
    other_key = ENTRY_BINDING_KEY[OPPOSITE_DIRECTION[direction]]
    if other_key in bindings:
        raise DiffDecisionsError(
            f"B1b lineage declares direction {direction} but its bindings "
            f"carry BOTH {key} and {other_key}. A deployment compares ONE side "
            "(the DSL has no abs()) and the bindings loader refuses a key no "
            "rule references, so two entry thresholds mean the artifact does "
            "not describe one deployment — and reading only the expected key "
            "would let this report name a direction the other half contradicts"
        )
    sign = ENTRY_THRESHOLD_SIGN[direction]
    if value * sign <= 0:
        raise DiffDecisionsError(
            f"B1b lineage declares direction {direction} but {key}={value}, "
            f"whose sign contradicts it (a {direction} entry threshold is "
            f"{'negative' if sign < 0 else 'positive'}: "
            "∓trunc(extreme_atr_mult * 1000)). A comparison run against this "
            "threshold would fire on almost every bar and report the result "
            "as agreement"
        )
    ctx = DiffContext(
        direction=direction, z_entry_binding_key=key, z_entry_threshold_x1000=value
    )
    return ctx, check_entry(
        "tos_deployment_direction_matches_entry_binding",
        "B1b's lineage declares a direction in "
        f"{DIRECTION_TOKENS}, its bindings carry the integer key that "
        "direction's entry rule references AND NOT the other direction's, and "
        "that threshold's sign agrees with the direction",
        direction=direction,
        z_entry_binding_key=key,
        z_entry_threshold_x1000=value,
    )


def _check_reconciliation(
    records: list[DiffRecord], input_lines: int
) -> dict[str, Any]:
    """Bucket total against the INDEPENDENTLY measured input line count.

    Concrete failing input: ``classify_all`` or the lockstep loop drops or
    duplicates a bar. ``sum(buckets.values()) == len(records)`` is true by
    construction and cannot see that; ``input_lines`` is a newline count taken
    in the digest pass, before any JSON was parsed, so the two numbers are
    arrived at by different routes.
    """
    bucket_total = sum(Counter(record.bucket for record in records).values())
    if not bucket_total == len(records) == input_lines:
        raise DiffDecisionsError(
            f"bucket total {bucket_total} / classified bars {len(records)} / "
            f"input lines {input_lines} do not reconcile — a bar was lost or "
            "duplicated between reading and classifying"
        )
    return check_entry(
        "buckets_sum_equals_input_line_count",
        "the bucket counts sum to the number of classified bars and to the "
        "newline count taken from the input files in the digest pass, before "
        "any line was parsed",
        bars=input_lines,
    )


def _refuse_floats_in_report(*rendered: tuple[str, bytes]) -> dict[str, Any]:
    """Scan the rendered bytes of EVERY sidecar this tool writes.

    ``summary.json`` is built from integers, but ``lineage.json`` copies
    ``producer.{name,version,source_id,git_commit}`` straight out of the input
    sidecars, and :func:`load_lineage` deliberately permits floats there (a
    producer records its strategy's float parameters). So a sidecar carrying
    ``"version": 1.0`` would put a float in this tool's own output. Scanning
    the rendered bytes of both files is what closes that; scanning only the
    summary, as the first revision did, could not see it.
    """
    found: list[str] = []
    for name, payload in rendered:
        for where in _float_paths(json.loads(payload.decode("utf-8"))):
            found.append(f"{name}:{where}")
    if found:
        raise DiffDecisionsError("this report would carry a float: " + ", ".join(found))
    return check_entry(
        "report_carries_no_floats",
        "the rendered bytes of summary.json AND lineage.json hold integers, "
        "booleans, strings and nulls only — rates are integer "
        "numerator/denominator plus a half-up rate_x10000, and a float copied "
        "out of an input sidecar's producer block refuses the run",
        scanned=[name for name, _ in rendered],
    )


def _float_scan_check() -> dict[str, Any]:
    """The recorded row for the scan :func:`_refuse_floats_in_report` performs."""
    return check_entry(
        "report_carries_no_floats",
        "the rendered bytes of summary.json AND lineage.json hold integers, "
        "booleans, strings and nulls only",
        scanned=[SUMMARY_FILENAME, LINEAGE_FILENAME],
    )


def _load_refs(
    *specs: tuple[str, Path, Path | None],
) -> dict[str, ArtifactRef]:
    """Digest and parse each artifact and its sidecar, keyed by label."""
    return {
        label: _load_ref(
            label=label,
            jsonl_path=jsonl,
            lineage_path=_sidecar_for(jsonl, explicit),
        )
        for label, jsonl, explicit in specs
    }


def _lineage_refusals(
    refs: dict[str, ArtifactRef], legacy_outcomes: tuple[str, ...]
) -> tuple[
    dict[str, list[dict[str, str]]],
    dict[str, Any],
    DiffContext,
    int,
    list[dict[str, Any]],
]:
    """The refusals that read only the sidecars, in :data:`CHECK_NAMES` order.

    Appended one at a time rather than built eagerly and listed afterwards:
    the order a malformed trio is REFUSED in has to be the order the
    enumeration promises, and the eager version silently reordered them.
    """
    checks: list[dict[str, Any]] = []
    declared_index, ids_check = _check_attribution_ids(refs)
    checks.append(ids_check)
    # AFTER the attribution-id check, not before it: `run` used to call this
    # one first, so a trio violating BOTH was refused with check #2's message
    # while the enumeration promised #1 — "거부 순서 = 기록 순서" was false for
    # exactly that pair.
    assert_entry_outcome_literals(legacy_outcomes)
    checks.append(
        check_entry(
            "entry_outcome_literals_are_closed_set_members",
            "the two B2 outcomes this tool branches on "
            f"({', '.join(NAMED_LEGACY_OUTCOMES)}) are members of the "
            "outcomes.closed_set its lineage declares",
            closed_set_size=len(legacy_outcomes),
        )
    )
    identity, identity_check = _check_window_identity(refs)
    checks.append(identity_check)
    checks.append(_check_strategy_and_inputs(refs))
    checks.append(_check_self_digests(refs))
    checks.append(_check_tos_parent(refs))
    ctx, direction_check = _read_deployment_context(refs)
    checks.append(direction_check)
    input_lines, lines_check = _check_line_counts(refs)
    checks.append(lines_check)
    return declared_index, identity, ctx, input_lines, checks


def _write_report(target: Path, *rendered: tuple[str, bytes]) -> None:
    """Create ``target`` and write each rendered file into it."""
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DiffDecisionsError(f"cannot create {target}: {exc}") from exc
    for name, payload in rendered:
        (target / name).write_bytes(payload)


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
    """Refuse or diff; write ``diff.jsonl``, ``summary.json`` and ``lineage.json``.

    Every refusal happens before ``mkdir``, so a refused trio leaves nothing
    behind. The one exception by necessity is the float scan of this tool's own
    output, which needs the rendered bytes — it too raises before any write.
    """
    refs = _load_refs(
        (LABEL_FIELDS, fields_jsonl, fields_lineage),
        (LABEL_LEGACY, legacy_jsonl, legacy_lineage),
        (LABEL_TOS, tos_jsonl, tos_lineage),
    )
    legacy_outcomes = tuple(
        _dig(refs[LABEL_LEGACY].lineage, "outcomes.closed_set", LABEL_LEGACY)
    )
    declared_index, identity, ctx, input_lines, checks = _lineage_refusals(
        refs, legacy_outcomes
    )

    joined = join_artifacts(
        fields_path=fields_jsonl,
        legacy_path=legacy_jsonl,
        tos_path=tos_jsonl,
        legacy_outcomes=legacy_outcomes,
    )
    checks.extend(joined.checks)

    records = classify_all(joined.bars, ctx)
    checks.append(_check_reconciliation(records, input_lines))
    summary = build_summary(
        records=records,
        identity=identity,
        declared_index=declared_index,
        ctx=ctx,
        tos_lineage=refs[LABEL_TOS].lineage,
    )

    diff_bytes = render_jsonl(records)
    summary_bytes = render_json(summary)
    checks.append(_float_scan_check())
    lineage = build_lineage(
        refs=refs,
        identity=identity,
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
    # Raises before any write; the recorded row above describes what held.
    _refuse_floats_in_report(
        (SUMMARY_FILENAME, summary_bytes), (LINEAGE_FILENAME, lineage_bytes)
    )
    if [entry["name"] for entry in checks] != list(CHECK_NAMES):
        raise DiffDecisionsError(
            "the recorded checks are not CHECK_NAMES in order: "
            f"{[entry['name'] for entry in checks]}"
        )

    target = out_dir if out_dir is not None else default_out_dir(identity)
    _write_report(
        target,
        (DIFF_FILENAME, diff_bytes),
        (SUMMARY_FILENAME, summary_bytes),
        (LINEAGE_FILENAME, lineage_bytes),
    )
    return RunResult(
        out_dir=target,
        diff_path=target / DIFF_FILENAME,
        summary_path=target / SUMMARY_FILENAME,
        lineage_path=target / LINEAGE_FILENAME,
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
