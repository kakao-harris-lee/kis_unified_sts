"""Tests for the CP-3 B3 decision-level diff (``tools/tos_cp3/diff_decisions.py``).

Hermetic: the three input artifacts are **built in-test as minimal JSONL**, not
produced by B1a/B2/B1b. B3 reads files, so a file is the right fixture — and
only a hand-built trio can place a bar in every bucket and on every attribution
rule, including the ones a real window never reaches (the quantization edge, and
UNRESOLVED). The real-artifact behaviour is pinned by the PR's recorded run, not
by this suite.

What is pinned here:

* **Every refusal has a red proof** — mismatched ``join.window_identity`` (one
  test per field), a B1b parent ``fields.jsonl`` sha that is not the file's, a
  dropped line, a reordered id, a differing ``as_of_ms``, a float in a payload,
  an artifact that does not match its own lineage, a file with no trailing
  newline, an outcome outside B2's declared closed set, and an attribution id no
  lineage declares.
* **Every bucket and every attribution rule is exercised** by at least one
  synthetic bar, and ``classify`` is shown exhaustive over
  (outcome_kind x legacy fire) by enumeration.
* **Ordering** — the table is read in order and first match wins, shown on a bar
  two rules both match.
* **Determinism** — two runs write byte-identical ``diff.jsonl``,
  ``summary.json`` and ``lineage.json``.
* **Reconciliation** — bucket counts sum to the bar count, which equals the
  input line count and the diff line count.
* **No drift in the two provenance helpers B3 keeps locally** instead of
  importing from B1a (see that module's docstring): both are compared against
  B1a's.

File name: deliberately NOT ``test_tos_cp3_*``, for the reason B1a's and B2's
suites state — ``tos-firewall.yml`` runs ``pytest tests/tools/test_tos_*.py``
with a minimal dependency set and ``test.yml``'s path filter negates the same
prefix.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from tools.tos_cp3 import diff_decisions as dd
from tools.tos_cp3 import produce_fields

SYMBOL = "101S6000"
WINDOW_START = "2025-12-01"
WINDOW_END = "2026-04-30"
MARKET_OPEN = "09:00"
MARKET_OPEN_SOURCE = "era-rule"
MIN_BARS_PER_DAY = 330
Z_ENTRY_MAX_X1000 = -1800

#: B2's declared closed set, copied here as a fixture value (the tool reads it
#: from the lineage it is given, so the fixture is what makes the bucket names
#: in these tests legitimate).
LEGACY_OUTCOMES = (
    "FIRED",
    "NO_ATR",
    "NO_PRICE",
    "AWAITING_REVERSAL_CONFIRM_NO_PREV_CLOSE",
    "AWAITING_REVERSAL_CONFIRM_PRICE_TURN",
    "AWAITING_REVERSAL_CONFIRM_Z_IMPROVE",
    "BEFORE_WINDOW",
    "AFTER_CUTOFF",
    "VOL_BELOW_GATE",
    "NOT_EXTREME",
    "AGAINST_TREND",
    "STILL_TRENDING_UP",
    "STILL_TRENDING_DOWN",
    "LOW_CONFIDENCE",
)

#: The declared-difference ids each artifact really publishes, so the
#: attribution table's run-time guard is exercised against a realistic index.
B1A_DIFFERENCE_IDS = tuple(f"D{n}" for n in range(1, 11))
B2_DIFFERENCE_IDS = tuple(f"L{n}" for n in range(1, 13))
B1B_DIFFERENCE_IDS = tuple(f"B1b-D{n}" for n in range(1, 10))


# ---------------------------------------------------------------------------
# Fixture trio
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BarSpec:
    """One synthetic bar as all three artifacts would describe it."""

    minute: int
    legacy_outcome: str = "VOL_BELOW_GATE"
    legacy_direction: str | None = None
    admitted: bool = False
    tos_outcome_kind: str = "NO_ACTION"
    tos_rule_id: str = "R0-DEFAULT-NO-ACTION"
    capacity_denied: bool = False
    entry_window: bool = True
    hi_vol: bool = False
    stall_ok: bool = False
    reversal_ok: bool = False
    z_x1000: int = -100

    @property
    def raw_event_id(self) -> str:
        return f"{SYMBOL}:1m:20251208T{9 + self.minute // 60:02d}{self.minute % 60:02d}00+0900"

    @property
    def as_of_ms(self) -> int:
        return 1765153200000 + self.minute * 60_000

    def fields_payload(self) -> dict[str, Any]:
        return {
            "raw_event_id": self.raw_event_id,
            "source_id": "tos-cp3-b1a/0.1.0",
            "instrument": SYMBOL,
            "as_of_ms": self.as_of_ms,
            "fields": {
                "close_x100": 58000,
                "entry_window": self.entry_window,
                "hi_vol": self.hi_vol,
                "stall_ok": self.stall_ok,
                "reversal_ok": self.reversal_ok,
                "vwap_reverted": False,
                "eod": False,
                "z_x1000": self.z_x1000,
            },
        }

    def legacy_payload(self) -> dict[str, Any]:
        return {
            "raw_event_id": self.raw_event_id,
            "source_id": "tos-cp3-b2/0.1.0",
            "instrument": SYMBOL,
            "as_of_ms": self.as_of_ms,
            "decision": {
                "outcome": self.legacy_outcome,
                "direction": self.legacy_direction,
                "would_be_admitted_by_legacy_position_model": self.admitted,
                "eval": {"entry_window": self.entry_window},
            },
        }

    def tos_payload(self) -> dict[str, Any]:
        return {
            "as_of_ms": self.as_of_ms,
            "bar_index": self.minute,
            "capacity_denied": self.capacity_denied,
            "outcome_kind": self.tos_outcome_kind,
            "raw_event_id": self.raw_event_id,
            "rule_id": self.tos_rule_id,
        }


def _write_jsonl(path: Path, payloads: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(payload, separators=(",", ":"), ensure_ascii=True) + "\n"
            for payload in payloads
        ),
        encoding="utf-8",
    )


def _sha_and_lines(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), data.count(b"\n")


def _declared(ids: tuple[str, ...]) -> list[dict[str, str]]:
    return [{"id": raw_id, "item": f"synthetic {raw_id}"} for raw_id in ids]


@dataclass(frozen=True)
class Trio:
    """Paths of a written artifact trio."""

    root: Path

    @property
    def fields(self) -> Path:
        return self.root / "b1a" / "fields.jsonl"

    @property
    def fields_lineage(self) -> Path:
        return self.root / "b1a" / "lineage.json"

    @property
    def legacy(self) -> Path:
        return self.root / "b2" / "decisions.jsonl"

    @property
    def legacy_lineage(self) -> Path:
        return self.root / "b2" / "lineage.json"

    @property
    def tos(self) -> Path:
        return self.root / "b1b" / "trace.jsonl"

    @property
    def tos_lineage(self) -> Path:
        return self.root / "b1b" / "lineage.json"


def seal(
    trio: Trio,
    *,
    b1a_identity: dict[str, Any] | None = None,
    b2_identity: dict[str, Any] | None = None,
    b1a_ids: tuple[str, ...] = B1A_DIFFERENCE_IDS,
    b2_ids: tuple[str, ...] = B2_DIFFERENCE_IDS,
    b1b_ids: tuple[str, ...] = B1B_DIFFERENCE_IDS,
    legacy_outcomes: tuple[str, ...] = LEGACY_OUTCOMES,
    bindings: dict[str, Any] | None = None,
    b1b_parent_overrides: dict[str, Any] | None = None,
) -> Trio:
    """(Re)write the three lineage sidecars from whatever the JSONL files hold.

    Called after every mutation so that a test aims at ONE refusal: without a
    reseal, any edit to a payload file trips the "artifact matches its own
    lineage" check first and the intended refusal is never reached.
    """
    identity_a = {
        "symbol": SYMBOL,
        "market_open_kst": MARKET_OPEN,
        "market_open_source": MARKET_OPEN_SOURCE,
        "min_bars_per_day": MIN_BARS_PER_DAY,
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        **(b1a_identity or {}),
    }
    identity_b = {
        "symbol": SYMBOL,
        "market_open_kst": MARKET_OPEN,
        "market_open_source": MARKET_OPEN_SOURCE,
        "min_bars_per_day": MIN_BARS_PER_DAY,
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        **(b2_identity or {}),
    }

    fields_sha, fields_lines = _sha_and_lines(trio.fields)
    trio.fields_lineage.write_bytes(
        dd.render_json(
            {
                "lineage_schema_version": 2,
                "tool": {
                    "name": "tools/tos_cp3/produce_fields.py",
                    "version": "tos_cp3/0.1.0",
                    "source_id": "tos-cp3-b1a/0.1.0",
                    "git": {"commit": "0" * 40},
                },
                "dataset": {
                    "symbol": identity_a["symbol"],
                    "min_bars_per_day": identity_a["min_bars_per_day"],
                    "requested_start": identity_a["window_start"],
                    "requested_end": identity_a["window_end"],
                },
                "strategy": {
                    "market_open_kst": identity_a["market_open_kst"],
                    "market_open_source": identity_a["market_open_source"],
                    "entry_params_yaml": {"extreme_atr_mult": 1.8},
                },
                "declared_differences": _declared(b1a_ids),
                "output": {
                    "jsonl": "fields.jsonl",
                    "jsonl_sha256": fields_sha,
                    "jsonl_lines": fields_lines,
                },
            }
        )
    )

    legacy_sha, legacy_lines = _sha_and_lines(trio.legacy)
    trio.legacy_lineage.write_bytes(
        dd.render_json(
            {
                "lineage_schema_version": 1,
                "tool": {
                    "name": "tools/tos_cp3/emit_legacy_decisions.py",
                    "version": "tos_cp3/0.1.0",
                    "source_id": "tos-cp3-b2/0.1.0",
                    "git": {"commit": "1" * 40},
                },
                "join": {
                    "key": "raw_event_id",
                    "window_identity": identity_b,
                    "b3_contract": "B3 MUST REFUSE a (B1a, B2) pair whose ...",
                },
                "outcomes": {"closed_set": list(legacy_outcomes)},
                "declared_differences": _declared(b2_ids),
                "output": {
                    "jsonl": "decisions.jsonl",
                    "jsonl_sha256": legacy_sha,
                    "jsonl_lines": legacy_lines,
                },
            }
        )
    )

    fields_lineage_sha = hashlib.sha256(trio.fields_lineage.read_bytes()).hexdigest()
    tos_sha, tos_lines = _sha_and_lines(trio.tos)
    parents = {
        "fields_jsonl": {
            "path": str(trio.fields),
            "sha256": fields_sha,
            "lines": fields_lines,
            "source_id": "tos-cp3-b1a/0.1.0",
        },
        "fields_lineage_json": {
            "path": str(trio.fields_lineage),
            "sha256": fields_lineage_sha,
        },
        "strategy_bindings_file": {
            "path": "tos/runtime/cp3/strategy_bindings.yaml",
            "bindings": (
                {"z_entry_max_x1000": Z_ENTRY_MAX_X1000}
                if bindings is None
                else bindings
            ),
        },
    }
    for key, value in (b1b_parent_overrides or {}).items():
        parents[key] = {**parents.get(key, {}), **value}
    trio.tos_lineage.write_bytes(
        dd.render_json(
            {
                "lineage_schema_version": 2,
                "tool": {
                    "name": "tos/runtime/cp3/",
                    "version": "tos_cp3_b1b/0.1.0",
                    "module": "cp3.runner",
                    "git": {"commit": "2" * 40},
                },
                "parents": parents,
                "claims": {
                    "oracle_scope": "DECISION_AND_INTENT_LEVEL_ONLY",
                    "performance_surface": "ABSENT BY CONSTRUCTION",
                },
                "counts": {"fill_records": 1},
                "declared_differences": _declared(b1b_ids),
                "output": {
                    "trace_jsonl": "trace.jsonl",
                    "trace_jsonl_sha256": tos_sha,
                    "trace_jsonl_lines": tos_lines,
                },
            }
        )
    )
    return trio


def write_trio(root: Path, bars: list[BarSpec], **seal_kwargs: Any) -> Trio:
    """Write the three JSONL files from *bars*, then seal their sidecars."""
    trio = Trio(root=root)
    for sub in ("b1a", "b2", "b1b"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    _write_jsonl(trio.fields, [bar.fields_payload() for bar in bars])
    _write_jsonl(trio.legacy, [bar.legacy_payload() for bar in bars])
    _write_jsonl(trio.tos, [bar.tos_payload() for bar in bars])
    return seal(trio, **seal_kwargs)


def run_trio(trio: Trio, out: Path) -> dd.RunResult:
    return dd.run(
        fields_jsonl=trio.fields,
        legacy_jsonl=trio.legacy,
        tos_jsonl=trio.tos,
        out_dir=out,
    )


def mutate_jsonl(
    path: Path, transform: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]
) -> None:
    payloads = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]
    _write_jsonl(path, transform(payloads))


# ---------------------------------------------------------------------------
# The synthetic series that covers every bucket and every attribution rule
# ---------------------------------------------------------------------------

#: One bar per outcome B3 can classify. The comment on each names the bucket
#: and the attribution rule it is here to exercise.
COVERAGE_BARS: tuple[BarSpec, ...] = (
    # AGREE_NO_ACTION / AGREED — neither side acted, nothing to explain.
    BarSpec(minute=0),
    # AGREE_ENTRY / agree_entry_capacity_denied — decision agreed, no capacity.
    BarSpec(
        minute=1,
        legacy_outcome="FIRED",
        legacy_direction="LONG",
        admitted=True,
        tos_outcome_kind="ACTION",
        tos_rule_id="R1-ENTRY-LONG",
        capacity_denied=True,
        hi_vol=True,
        stall_ok=True,
        reversal_ok=True,
        z_x1000=-3091,
    ),
    # AGREE_ENTRY / agree_entry_rejected_by_legacy_position_model.
    BarSpec(
        minute=2,
        legacy_outcome="FIRED",
        legacy_direction="LONG",
        admitted=False,
        tos_outcome_kind="ACTION",
        tos_rule_id="R1-ENTRY-LONG",
        capacity_denied=True,
        hi_vol=True,
        stall_ok=True,
        reversal_ok=True,
        z_x1000=-2900,
    ),
    # AGREE_ENTRY with nothing to explain — admitted and capacity available.
    BarSpec(
        minute=3,
        legacy_outcome="FIRED",
        legacy_direction="LONG",
        admitted=True,
        tos_outcome_kind="ACTION",
        tos_rule_id="R1-ENTRY-LONG",
        capacity_denied=False,
        hi_vol=True,
        stall_ok=True,
        reversal_ok=True,
        z_x1000=-2800,
    ),
    # TOS_ONLY_ENTRY / tos_action_on_legacy_low_confidence.
    BarSpec(
        minute=4,
        legacy_outcome="LOW_CONFIDENCE",
        legacy_direction="LONG",
        tos_outcome_kind="ACTION",
        tos_rule_id="R1-ENTRY-LONG",
        capacity_denied=True,
        hi_vol=True,
        stall_ok=True,
        reversal_ok=True,
        z_x1000=-2095,
    ),
    # LEGACY_ONLY_ENTRY / legacy_short_entry.
    BarSpec(
        minute=5,
        legacy_outcome="FIRED",
        legacy_direction="SHORT",
        admitted=True,
        hi_vol=True,
        stall_ok=True,
        reversal_ok=True,
        z_x1000=2594,
    ),
    # TOS_EXIT_ON_LEGACY_VOL_BELOW_GATE / tos_flat_without_legacy_fire.
    BarSpec(
        minute=6,
        legacy_outcome="VOL_BELOW_GATE",
        tos_outcome_kind="FLAT",
        tos_rule_id="R2-EXIT-VWAP-REVERTED",
        capacity_denied=True,
    ),
    # TOS_EXIT_ON_LEGACY_AFTER_CUTOFF — a second suffix, so the family is shown
    # to be keyed on the legacy outcome rather than fixed.
    BarSpec(
        minute=7,
        legacy_outcome="AFTER_CUTOFF",
        entry_window=False,
        tos_outcome_kind="FLAT",
        tos_rule_id="R3-EXIT-EOD",
        capacity_denied=True,
    ),
    # LEGACY_ONLY_ENTRY / z_quantization_edge — a long fire one x1000 unit
    # inside the deployed threshold, which the TOS rule therefore misses.
    BarSpec(
        minute=8,
        legacy_outcome="FIRED",
        legacy_direction="LONG",
        admitted=True,
        hi_vol=True,
        stall_ok=True,
        reversal_ok=True,
        z_x1000=-1799,
    ),
    # LEGACY_ONLY_ENTRY / UNRESOLVED — a long fire deep past the threshold that
    # the TOS rule did not take. No declared difference explains it, so none is
    # invented.
    BarSpec(
        minute=9,
        legacy_outcome="FIRED",
        legacy_direction="LONG",
        admitted=True,
        hi_vol=True,
        stall_ok=True,
        reversal_ok=True,
        z_x1000=-3500,
    ),
)


@pytest.fixture()
def coverage(tmp_path: Path) -> tuple[Trio, dd.RunResult]:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS))
    result = run_trio(trio, tmp_path / "out")
    return trio, result


def _records(result: dd.RunResult) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in result.diff_path.read_text(encoding="utf-8").splitlines()
    ]


# ---------------------------------------------------------------------------
# Coverage: every bucket, every attribution rule
# ---------------------------------------------------------------------------


def test_every_bucket_family_is_exercised(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    _, result = coverage
    buckets = result.summary["buckets"]
    assert buckets == {
        dd.BUCKET_AGREE_ENTRY: 3,
        dd.BUCKET_AGREE_NO_ACTION: 1,
        dd.BUCKET_LEGACY_ONLY_ENTRY: 3,
        f"{dd.BUCKET_TOS_EXIT_PREFIX}AFTER_CUTOFF": 1,
        f"{dd.BUCKET_TOS_EXIT_PREFIX}VOL_BELOW_GATE": 1,
        dd.BUCKET_TOS_ONLY_ENTRY: 1,
    }


def test_every_attribution_rule_is_exercised(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    """Each rule in the table matched at least one bar, plus AGREED/UNRESOLVED."""
    _, result = coverage
    matched = result.summary["attribution_rules"]
    for rule in dd.ATTRIBUTION_RULES:
        assert matched.get(rule.name, {}).get("bars", 0) >= 1, rule.name
    assert matched[dd.ATTRIBUTION_AGREED]["bars"] == 2  # minute 0 and minute 3
    assert matched[dd.ATTRIBUTION_UNRESOLVED]["bars"] == 1


def test_each_bar_lands_on_the_bucket_and_rule_its_comment_names(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    _, result = coverage
    by_minute = {bar.raw_event_id: bar for bar in COVERAGE_BARS}
    expected = {
        0: (dd.BUCKET_AGREE_NO_ACTION, dd.ATTRIBUTION_AGREED, []),
        1: (dd.BUCKET_AGREE_ENTRY, "agree_entry_capacity_denied", ["B1b-D1"]),
        2: (
            dd.BUCKET_AGREE_ENTRY,
            "agree_entry_rejected_by_legacy_position_model",
            ["B1b-D7", "B2-L3", "B2-L10"],
        ),
        3: (dd.BUCKET_AGREE_ENTRY, dd.ATTRIBUTION_AGREED, []),
        4: (
            dd.BUCKET_TOS_ONLY_ENTRY,
            "tos_action_on_legacy_low_confidence",
            ["B1a-D1", "B2-L9"],
        ),
        5: (dd.BUCKET_LEGACY_ONLY_ENTRY, "legacy_short_entry", ["B1b-D5"]),
        6: (
            f"{dd.BUCKET_TOS_EXIT_PREFIX}VOL_BELOW_GATE",
            "tos_flat_without_legacy_fire",
            ["B1b-D7"],
        ),
        7: (
            f"{dd.BUCKET_TOS_EXIT_PREFIX}AFTER_CUTOFF",
            "tos_flat_without_legacy_fire",
            ["B1b-D7"],
        ),
        8: (dd.BUCKET_LEGACY_ONLY_ENTRY, "z_quantization_edge", ["B1a-D8"]),
        9: (dd.BUCKET_LEGACY_ONLY_ENTRY, dd.ATTRIBUTION_UNRESOLVED, []),
    }
    for record in _records(result):
        bar = by_minute[record["raw_event_id"]]
        bucket, rule, ids = expected[bar.minute]
        assert record["bucket"] == bucket, bar.minute
        assert record["attribution_rule"] == rule, bar.minute
        assert record["attribution"] == ids, bar.minute


def test_the_unresolved_bar_is_listed_not_explained(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    _, result = coverage
    unresolved = result.summary["unresolved"]
    assert unresolved["count"] == 1
    assert unresolved["raw_event_ids"] == [COVERAGE_BARS[9].raw_event_id]
    assert unresolved["raw_event_ids_truncated"] is False


def test_classification_is_exhaustive_over_kind_times_fire() -> None:
    """Every (outcome_kind, legacy fire/direction) pair yields exactly one bucket."""
    families = {
        dd.BUCKET_AGREE_NO_ACTION,
        dd.BUCKET_AGREE_ENTRY,
        dd.BUCKET_TOS_ONLY_ENTRY,
        dd.BUCKET_LEGACY_ONLY_ENTRY,
    }
    for kind in dd.TOS_OUTCOME_KINDS:
        for outcome, direction in (
            ("FIRED", "LONG"),
            ("FIRED", "SHORT"),
            ("VOL_BELOW_GATE", None),
            ("LOW_CONFIDENCE", "LONG"),
        ):
            bar = dd.JoinedBar(
                raw_event_id="x",
                as_of_ms=0,
                legacy_outcome=outcome,
                legacy_direction=direction,
                admitted=False,
                tos_outcome_kind=kind,
                tos_rule_id=None,
                tos_capacity_denied=False,
                gates=(False, False, False, False),
                z_x1000=0,
            )
            bucket = dd.classify(bar)
            assert bucket in families or bucket.startswith(dd.BUCKET_TOS_EXIT_PREFIX), (
                kind,
                outcome,
                direction,
                bucket,
            )


def test_an_unknown_tos_outcome_kind_is_refused() -> None:
    bar = dd.JoinedBar(
        raw_event_id="x",
        as_of_ms=0,
        legacy_outcome="FIRED",
        legacy_direction="LONG",
        admitted=False,
        tos_outcome_kind="SOMETHING_ELSE",
        tos_rule_id=None,
        tos_capacity_denied=False,
        gates=(True, True, True, True),
        z_x1000=-2000,
    )
    with pytest.raises(dd.DiffDecisionsError, match="unknown TOS outcome_kind"):
        dd.classify(bar)


def test_the_attribution_table_is_read_in_order(tmp_path: Path) -> None:
    """A bar two rules both match takes the earlier one.

    An AGREE_ENTRY bar that was not admitted AND had no capacity matches rules
    4 and 5. The position-model rule is earlier, so that is the attribution —
    reversing the table would change this bar's answer, which is what makes
    "read in order" a property and not a comment.
    """
    bar = BarSpec(
        minute=0,
        legacy_outcome="FIRED",
        legacy_direction="LONG",
        admitted=False,
        tos_outcome_kind="ACTION",
        tos_rule_id="R1-ENTRY-LONG",
        capacity_denied=True,
        hi_vol=True,
        stall_ok=True,
        reversal_ok=True,
        z_x1000=-3000,
    )
    joined = dd.JoinedBar(
        raw_event_id=bar.raw_event_id,
        as_of_ms=bar.as_of_ms,
        legacy_outcome=bar.legacy_outcome,
        legacy_direction=bar.legacy_direction,
        admitted=bar.admitted,
        tos_outcome_kind=bar.tos_outcome_kind,
        tos_rule_id=bar.tos_rule_id,
        tos_capacity_denied=bar.capacity_denied,
        gates=(True, True, True, True),
        z_x1000=bar.z_x1000,
    )
    ctx = dd.DiffContext(z_entry_max_x1000=Z_ENTRY_MAX_X1000)
    bucket = dd.classify(joined)
    assert dd.attribute(joined, bucket, ctx)[0] == (
        "agree_entry_rejected_by_legacy_position_model"
    )
    reversed_table = tuple(reversed(dd.ATTRIBUTION_RULES))
    assert dd.attribute(joined, bucket, ctx, reversed_table)[0] == (
        "agree_entry_capacity_denied"
    )


def test_an_agreeing_bar_carries_no_attribution() -> None:
    joined = dd.JoinedBar(
        raw_event_id="x",
        as_of_ms=0,
        legacy_outcome="VOL_BELOW_GATE",
        legacy_direction=None,
        admitted=False,
        tos_outcome_kind="NO_ACTION",
        tos_rule_id="R0-DEFAULT-NO-ACTION",
        tos_capacity_denied=False,
        gates=(True, False, False, False),
        z_x1000=-100,
    )
    ctx = dd.DiffContext(z_entry_max_x1000=Z_ENTRY_MAX_X1000)
    assert dd.needs_attribution(joined, dd.BUCKET_AGREE_NO_ACTION) is False
    assert dd.attribute(joined, dd.BUCKET_AGREE_NO_ACTION, ctx) == (
        dd.ATTRIBUTION_AGREED,
        (),
    )


def test_the_quantization_edge_threshold_comes_from_the_bindings(
    tmp_path: Path,
) -> None:
    """Move the deployed threshold and the edge attribution moves with it.

    The edge is not a literal in this module: it is read from B1b's lineage
    (``parents.strategy_bindings_file.bindings``). A run whose binding says
    -2500 must stop calling z=-1799 an edge bar and start calling z=-2499 one.
    """
    bars = [
        replace(COVERAGE_BARS[8], minute=8),
        replace(COVERAGE_BARS[8], minute=9, z_x1000=-2499),
    ]
    trio = write_trio(tmp_path / "in", bars, bindings={"z_entry_max_x1000": -2500})
    result = run_trio(trio, tmp_path / "out")
    rules = {
        record["raw_event_id"]: record["attribution_rule"]
        for record in _records(result)
    }
    assert rules[bars[0].raw_event_id] == dd.ATTRIBUTION_UNRESOLVED
    assert rules[bars[1].raw_event_id] == "z_quantization_edge"
    assert result.summary["config"]["z_entry_max_x1000"] == -2500


def test_a_binding_without_the_entry_threshold_is_refused(tmp_path: Path) -> None:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS[:1]), bindings={})
    with pytest.raises(dd.DiffDecisionsError, match="no z_entry_max_x1000"):
        run_trio(trio, tmp_path / "out")


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("symbol", "A05610"),
        ("market_open_kst", "08:45"),
        ("market_open_source", "field-default"),
        ("min_bars_per_day", 0),
        ("window_start", "2026-05-01"),
        ("window_end", "2026-05-31"),
    ],
)
def test_a_window_identity_disagreement_in_any_field_is_refused(
    tmp_path: Path, field: str, value: Any
) -> None:
    """B2's own ``b3_contract`` requires this refusal, field by field.

    The join key carries no window anchor, so a B1a/B2 pair from two different
    windows would join bar-for-bar and report every difference as a decision
    mismatch. One parameter per field because a refusal that only checks the
    symbol is a refusal that lets the other five through.
    """
    trio = write_trio(
        tmp_path / "in", list(COVERAGE_BARS[:2]), b2_identity={field: value}
    )
    with pytest.raises(
        dd.DiffDecisionsError, match="B1a and B2 describe different windows"
    ) as excinfo:
        run_trio(trio, tmp_path / "out")
    assert field in str(excinfo.value)


def test_the_window_identity_is_echoed_when_it_agrees(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    _, result = coverage
    expected = {
        "symbol": SYMBOL,
        "market_open_kst": MARKET_OPEN,
        "market_open_source": MARKET_OPEN_SOURCE,
        "min_bars_per_day": MIN_BARS_PER_DAY,
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
    }
    assert result.lineage["window_identity"] == expected
    assert result.summary["window_identity"] == expected
    assert set(dd.B1A_IDENTITY_PROJECTION) == set(dd.WINDOW_IDENTITY_FIELDS)


def test_a_partial_b2_window_identity_is_refused(tmp_path: Path) -> None:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS[:1]))
    lineage = json.loads(trio.legacy_lineage.read_text(encoding="utf-8"))
    del lineage["join"]["window_identity"]["window_end"]
    trio.legacy_lineage.write_bytes(dd.render_json(lineage))
    with pytest.raises(dd.DiffDecisionsError, match="missing window_end"):
        run_trio(trio, tmp_path / "out")


def test_a_b1b_parent_fields_sha_that_is_not_the_file_is_refused(
    tmp_path: Path,
) -> None:
    """The swapped-fields red proof: B1b's trace must be about THESE fields."""
    trio = write_trio(
        tmp_path / "in",
        list(COVERAGE_BARS[:3]),
        b1b_parent_overrides={"fields_jsonl": {"sha256": "0" * 64}},
    )
    with pytest.raises(
        dd.DiffDecisionsError, match="was not run over this fields.jsonl"
    ):
        run_trio(trio, tmp_path / "out")


def test_a_b1b_parent_fields_lineage_sha_mismatch_is_refused(
    tmp_path: Path,
) -> None:
    trio = write_trio(
        tmp_path / "in",
        list(COVERAGE_BARS[:3]),
        b1b_parent_overrides={"fields_lineage_json": {"sha256": "f" * 64}},
    )
    with pytest.raises(
        dd.DiffDecisionsError, match="consumed a different B1a lineage sidecar"
    ):
        run_trio(trio, tmp_path / "out")


def test_a_dropped_line_is_refused(tmp_path: Path) -> None:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS))
    mutate_jsonl(trio.legacy, lambda payloads: payloads[:-1])
    seal(trio)
    with pytest.raises(dd.DiffDecisionsError, match="different line counts"):
        run_trio(trio, tmp_path / "out")


def test_a_dropped_line_without_a_reseal_is_refused_earlier(
    tmp_path: Path,
) -> None:
    """The self-digest check fires first, which is the stronger refusal."""
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS))
    mutate_jsonl(trio.legacy, lambda payloads: payloads[:-1])
    with pytest.raises(dd.DiffDecisionsError, match="does not match its own lineage"):
        run_trio(trio, tmp_path / "out")


def test_reordered_ids_are_refused(tmp_path: Path) -> None:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS))

    def swap(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        payloads[3], payloads[4] = payloads[4], payloads[3]
        return payloads

    mutate_jsonl(trio.legacy, swap)
    seal(trio)
    with pytest.raises(
        dd.DiffDecisionsError, match=r"raw_event_id sequences differ at position 3"
    ):
        run_trio(trio, tmp_path / "out")


def test_a_differing_as_of_ms_is_refused(tmp_path: Path) -> None:
    """Same ids, different instants — the bars are not the same bars."""
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS))

    def shift(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        payloads[2]["as_of_ms"] += 60_000
        return payloads

    mutate_jsonl(trio.tos, shift)
    seal(trio)
    with pytest.raises(dd.DiffDecisionsError, match=r"as_of_ms differ at position 2"):
        run_trio(trio, tmp_path / "out")


@pytest.mark.parametrize("artifact", ["fields", "legacy", "tos"])
def test_a_float_in_any_payload_is_refused(tmp_path: Path, artifact: str) -> None:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS[:3]))
    path = getattr(trio, artifact)

    def inject(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if artifact == "fields":
            payloads[1]["fields"]["z_x1000"] = -1800.5
        elif artifact == "legacy":
            payloads[1]["decision"]["confidence_x1000"] = 800.0
        else:
            payloads[1]["bar_index"] = 1.0
        return payloads

    mutate_jsonl(path, inject)
    seal(trio)
    with pytest.raises(dd.DiffDecisionsError, match="carries a float"):
        run_trio(trio, tmp_path / "out")


def test_a_float_literal_with_an_integral_value_is_still_refused(
    tmp_path: Path,
) -> None:
    """``1.0`` is a float LITERAL; the hook sees the literal, not the value."""
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS[:2]))
    raw = trio.fields.read_text(encoding="utf-8").splitlines()
    raw[0] = raw[0].replace('"z_x1000":-100', '"z_x1000":-100.0')
    trio.fields.write_text("\n".join(raw) + "\n", encoding="utf-8")
    seal(trio)
    with pytest.raises(dd.DiffDecisionsError, match="carries a float"):
        run_trio(trio, tmp_path / "out")


def test_a_nan_in_a_payload_is_refused(tmp_path: Path) -> None:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS[:2]))
    raw = trio.fields.read_text(encoding="utf-8").splitlines()
    raw[0] = raw[0].replace('"z_x1000":-100', '"z_x1000":NaN')
    trio.fields.write_text("\n".join(raw) + "\n", encoding="utf-8")
    seal(trio)
    with pytest.raises(dd.DiffDecisionsError, match="carries a float"):
        run_trio(trio, tmp_path / "out")


def test_a_file_without_a_trailing_newline_is_refused(tmp_path: Path) -> None:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS[:3]))
    trio.tos.write_text(
        trio.tos.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8"
    )
    with pytest.raises(dd.DiffDecisionsError, match="does not end with a newline"):
        run_trio(trio, tmp_path / "out")


def test_an_outcome_outside_b2s_declared_closed_set_is_refused(
    tmp_path: Path,
) -> None:
    """A bucket may only be named after an outcome B2 claims to produce."""
    bars = [replace(COVERAGE_BARS[0], legacy_outcome="SOMETHING_NEW")]
    trio = write_trio(tmp_path / "in", bars)
    with pytest.raises(dd.DiffDecisionsError, match="not in B2's declared closed set"):
        run_trio(trio, tmp_path / "out")


# ---------------------------------------------------------------------------
# The attribution-id guard
# ---------------------------------------------------------------------------


def test_the_attribution_id_guard_refuses_an_undeclared_id() -> None:
    bogus = dd.AttributionRule(
        name="bogus",
        ids=("B1a-D99",),
        why="synthetic",
        predicate=lambda bar, bucket, ctx: True,
    )
    with pytest.raises(dd.DiffDecisionsError, match="B1a-D99"):
        dd.assert_attribution_ids_declared((bogus,), {"B1a-D1"})


def test_the_attribution_id_guard_refuses_a_rule_that_names_nothing() -> None:
    empty = dd.AttributionRule(
        name="empty",
        ids=(),
        why="synthetic",
        predicate=lambda bar, bucket, ctx: True,
    )
    with pytest.raises(dd.DiffDecisionsError, match="names no declared difference"):
        dd.assert_attribution_ids_declared((empty,), {"B1a-D1"})


def test_an_undeclared_attribution_id_refuses_the_whole_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard is a run-time refusal, not just a unit-testable function."""
    bogus = dd.AttributionRule(
        name="bogus",
        ids=("B2-L99",),
        why="synthetic",
        predicate=lambda bar, bucket, ctx: True,
    )
    monkeypatch.setattr(dd, "ATTRIBUTION_RULES", dd.ATTRIBUTION_RULES + (bogus,))
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS[:2]))
    out = tmp_path / "out"
    with pytest.raises(dd.DiffDecisionsError, match="B2-L99"):
        run_trio(trio, out)
    assert not (out / dd.DIFF_FILENAME).exists()


def test_dropping_a_declared_difference_refuses_the_run(tmp_path: Path) -> None:
    """A difference removed upstream must stop B3, not dangle in its output."""
    trio = write_trio(
        tmp_path / "in",
        list(COVERAGE_BARS[:2]),
        b1a_ids=tuple(i for i in B1A_DIFFERENCE_IDS if i != "D1"),
    )
    with pytest.raises(dd.DiffDecisionsError, match="B1a-D1"):
        run_trio(trio, tmp_path / "out")


def test_every_cited_id_is_declared_by_the_real_artifacts(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    _, result = coverage
    declared = {
        entry["id"]
        for entries in result.lineage["declared_differences_index"].values()
        for entry in entries
    }
    cited = {i for rule in dd.ATTRIBUTION_RULES for i in rule.ids}
    assert cited <= declared
    assert cited  # the table cites something


def test_a_lineage_with_no_declared_differences_is_refused(tmp_path: Path) -> None:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS[:1]))
    lineage = json.loads(trio.tos_lineage.read_text(encoding="utf-8"))
    lineage["declared_differences"] = []
    trio.tos_lineage.write_bytes(dd.render_json(lineage))
    with pytest.raises(dd.DiffDecisionsError, match="carries no declared_differences"):
        run_trio(trio, tmp_path / "out")


def test_colliding_difference_ids_are_refused(tmp_path: Path) -> None:
    """B1a's ``D1`` and B1b's ``B1b-D1`` must stay distinguishable.

    Label-qualification is what makes the namespace flat. If one artifact began
    publishing an id that qualifies to the same string as another's, an
    attribution would become ambiguous, so the index refuses rather than
    picking one.
    """
    trio = write_trio(
        tmp_path / "in",
        list(COVERAGE_BARS[:1]),
        b1a_ids=B1A_DIFFERENCE_IDS + ("B1a-D1",),
    )
    with pytest.raises(dd.DiffDecisionsError, match="appears twice"):
        run_trio(trio, tmp_path / "out")


def test_qualification_leaves_an_already_labelled_id_alone() -> None:
    assert dd.qualify_difference_id("B1a", "D1") == "B1a-D1"
    assert dd.qualify_difference_id("B2", "L10") == "B2-L10"
    assert dd.qualify_difference_id("B1b", "B1b-D7") == "B1b-D7"


# ---------------------------------------------------------------------------
# Reconciliation, rates, scope
# ---------------------------------------------------------------------------


def test_summary_counts_reconcile_to_the_line_count(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    trio, result = coverage
    summary = result.summary
    inputs = {
        path.read_text(encoding="utf-8").count("\n")
        for path in (trio.fields, trio.legacy, trio.tos)
    }
    assert inputs == {len(COVERAGE_BARS)}
    assert summary["bars"] == len(COVERAGE_BARS)
    assert sum(summary["buckets"].values()) == summary["bars"]
    assert summary["buckets_reconcile_to_bars"] is True
    assert (
        sum(block["bars"] for block in summary["attribution_rules"].values())
        == summary["bars"]
    )
    assert len(_records(result)) == summary["bars"]
    assert result.lineage["output"]["diff_jsonl_lines"] == summary["bars"]
    matrix_total = sum(
        count
        for kinds in summary["legacy_outcome_by_tos_kind"].values()
        for count in kinds.values()
    )
    assert matrix_total == summary["bars"]


def test_both_agreement_rates_are_defined_and_computed(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    """Rule level and position-model level are different questions.

    The coverage series has four long fires (minutes 1, 2, 3, 8, 9 — five, of
    which three became TOS ACTION) precisely so the two rates differ: the
    position-model denominator drops the bar the harness would not have entered.
    """
    rates = coverage[1].summary["rates"]
    rule_level = rates["rule_level_entry_agreement"]
    pm_level = rates["position_model_level_entry_agreement"]
    assert rule_level["numerator"] == 3  # minutes 1, 2, 3
    assert rule_level["denominator"] == 5  # minutes 1, 2, 3, 8, 9
    assert rule_level["rate_x10000"] == 6000
    assert pm_level["numerator"] == 2  # minutes 1 and 3 were admitted
    assert pm_level["denominator"] == 4  # 1, 3, 8, 9 were admitted
    assert pm_level["rate_x10000"] == 5000
    for block in rates.values():
        assert block["definition"].strip()
    tos_side = rates["tos_action_explained_by_a_legacy_long_fire"]
    assert tos_side["numerator"] == 3
    assert tos_side["denominator"] == 4  # minute 4 actioned on LOW_CONFIDENCE


def test_an_empty_denominator_is_undefined_not_zero(tmp_path: Path) -> None:
    trio = write_trio(tmp_path / "in", [COVERAGE_BARS[0]])
    result = run_trio(trio, tmp_path / "out")
    rule_level = result.summary["rates"]["rule_level_entry_agreement"]
    assert rule_level["denominator"] == 0
    assert rule_level["rate_x10000"] is None
    assert "undefined" in rule_level["note"]


def test_the_rate_rounds_half_up_at_the_last_digit() -> None:
    assert dd._rate(1, 3)["rate_x10000"] == 3333
    assert dd._rate(2, 3)["rate_x10000"] == 6667
    assert dd._rate(1, 8)["rate_x10000"] == 1250
    assert dd._rate(1, 16)["rate_x10000"] == 625
    assert dd._rate(3, 8)["rate_x10000"] == 3750


def test_the_summary_says_plainly_that_fills_and_pnl_are_not_compared(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    scope = coverage[1].summary["scope"]
    note = scope["fills_and_pnl_not_compared"]
    assert "Fills and PnL are NOT compared" in note
    assert "체결 비교 포기" in note
    assert "ONE order per scope" in note
    assert "performance surface is sealed" in note
    assert scope["tos_performance_surface"] == "ABSENT BY CONSTRUCTION"
    assert scope["tos_oracle_scope"] == "DECISION_AND_INTENT_LEVEL_ONLY"


def test_the_declared_difference_section_lists_all_three_artifacts(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    by_artifact = coverage[1].summary["declared_differences"]["by_artifact"]
    assert set(by_artifact) == set(dd.ARTIFACT_LABELS)
    assert len(by_artifact["B1a"]) == len(B1A_DIFFERENCE_IDS)
    assert len(by_artifact["B2"]) == len(B2_DIFFERENCE_IDS)
    assert len(by_artifact["B1b"]) == len(B1B_DIFFERENCE_IDS)
    absorbed = {
        entry["id"]: entry["absorbed_bars"]
        for entries in by_artifact.values()
        for entry in entries
    }
    assert absorbed["B1a-D1"] == 1
    assert absorbed["B1b-D5"] == 1
    assert absorbed["B1b-D7"] == 3  # two FLAT bars plus the position-model bar
    assert absorbed["B1a-D2"] == 0  # declared, not exercised by this window


def test_no_float_reaches_either_output(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    """The report's own float-free claim, checked on the bytes it wrote."""
    _, result = coverage

    def refuse(literal: str) -> float:
        raise AssertionError(f"float in output: {literal}")

    for path in (result.summary_path, result.lineage_path):
        json.loads(
            path.read_text(encoding="utf-8"),
            parse_float=refuse,
            parse_constant=refuse,
        )
    for line in result.diff_path.read_text(encoding="utf-8").splitlines():
        json.loads(line, parse_float=refuse, parse_constant=refuse)
    checks = {check["name"]: check for check in result.lineage["checks"]}
    assert checks["report_carries_no_floats"]["status"] == "PASS"


# ---------------------------------------------------------------------------
# Lineage shape
# ---------------------------------------------------------------------------


def test_every_check_is_recorded_in_the_lineage(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    _, result = coverage
    names = [check["name"] for check in result.lineage["checks"]]
    assert names == [
        "attribution_ids_declared",
        "window_identity_agreement",
        "artifact_matches_its_own_lineage",
        "tos_parent_is_this_fields_artifact",
        "line_counts_equal",
        "raw_event_id_sequences_identical",
        "as_of_ms_identical",
        "no_floats_in_payloads",
        "legacy_outcome_in_declared_closed_set",
        "tos_outcome_kind_in_closed_set",
        "report_carries_no_floats",
    ]
    assert all(check["status"] == "PASS" for check in result.lineage["checks"])


def test_the_lineage_names_three_parents_with_both_digests(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    trio, result = coverage
    parents = result.lineage["parents"]
    assert set(parents) == {
        "fields_jsonl",
        "legacy_decisions_jsonl",
        "tos_trace_jsonl",
    }
    for key, jsonl, sidecar in (
        ("fields_jsonl", trio.fields, trio.fields_lineage),
        ("legacy_decisions_jsonl", trio.legacy, trio.legacy_lineage),
        ("tos_trace_jsonl", trio.tos, trio.tos_lineage),
    ):
        block = parents[key]
        assert block["sha256"] == hashlib.sha256(jsonl.read_bytes()).hexdigest()
        assert block["lines"] == len(COVERAGE_BARS)
        assert block["lineage_json"]["sha256"] == (
            hashlib.sha256(sidecar.read_bytes()).hexdigest()
        )
        assert block["producer"]["source_id"] or block["producer"]["name"]


def test_the_lineage_carries_no_clock_timestamp(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    _, result = coverage
    determinism = result.lineage["determinism"]
    assert determinism["no_clock_reads"] is True
    assert determinism["no_clock_derived_timestamp"] is True
    assert determinism["no_rng"] is True
    # A wall-clock reading would surface as an ISO datetime value or as an
    # "...at" key. Dates DO appear (the window bounds) and are not clock reads;
    # a time-of-day stamp is what would make two runs differ.
    text = result.lineage_path.read_text(encoding="utf-8")
    assert not re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", text)

    def keys(node: Any) -> list[str]:
        if isinstance(node, dict):
            return [k for key, value in node.items() for k in [key] + keys(value)]
        if isinstance(node, list):
            return [k for value in node for k in keys(value)]
        return []

    # The determinism block is skipped: its keys are the NEGATIVE declarations
    # ("no_clock_derived_timestamp"), which is the opposite of a stamp.
    scanned = {k: v for k, v in result.lineage.items() if k != "determinism"}
    assert not [
        key for key in keys(scanned) if key.endswith(("_at", "_time", "_timestamp"))
    ]


def test_the_lineage_restates_the_classifier_and_the_table(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    _, result = coverage
    classification = result.lineage["classification"]
    assert classification["gate_fields"] == list(dd.GATE_FIELDS)
    assert "Exhaustive" in classification["decision_tree"]
    table = result.lineage["attribution_table"]
    assert [entry["name"] for entry in table] == [
        rule.name for rule in dd.ATTRIBUTION_RULES
    ]
    assert [entry["order"] for entry in table] == list(range(len(table)))
    for entry in table:
        assert entry["why"].strip()
        assert entry["matched_bars"] >= 1
    assert result.lineage["window_identity_projection"]["b1a_sources"] == dict(
        dd.B1A_IDENTITY_PROJECTION
    )


def test_the_default_out_dir_is_keyed_on_the_window(tmp_path: Path) -> None:
    identity = {
        "symbol": SYMBOL,
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
    }
    assert dd.default_out_dir(identity) == (
        dd.REPO_ROOT / "reports" / "tos-cp3" / f"{SYMBOL}_{WINDOW_START}_{WINDOW_END}"
    )


# ---------------------------------------------------------------------------
# Determinism, CLI, firewall
# ---------------------------------------------------------------------------


def test_two_runs_write_byte_identical_artifacts(tmp_path: Path) -> None:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS))
    first = run_trio(trio, tmp_path / "out1")
    second = run_trio(trio, tmp_path / "out2")
    for attr in ("diff_path", "summary_path", "lineage_path"):
        assert (
            getattr(first, attr).read_bytes() == getattr(second, attr).read_bytes()
        ), attr


def test_the_cli_writes_the_three_outputs_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS))
    out = tmp_path / "out"
    code = dd.main(
        [
            "--fields",
            str(trio.fields),
            "--legacy",
            str(trio.legacy),
            "--tos",
            str(trio.tos),
            "--out",
            str(out),
        ]
    )
    assert code == 0
    assert (out / dd.DIFF_FILENAME).exists()
    assert (out / dd.SUMMARY_FILENAME).exists()
    assert (out / dd.LINEAGE_FILENAME).exists()
    printed = capsys.readouterr().out
    assert "rule_level_entry_agreement" in printed
    assert "unresolved: 1" in printed


def test_the_cli_returns_two_on_a_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    trio = write_trio(
        tmp_path / "in", list(COVERAGE_BARS[:2]), b2_identity={"symbol": "A05610"}
    )
    code = dd.main(
        [
            "--fields",
            str(trio.fields),
            "--legacy",
            str(trio.legacy),
            "--tos",
            str(trio.tos),
            "--out",
            str(tmp_path / "out"),
        ]
    )
    assert code == 2
    assert "different windows" in capsys.readouterr().err


def test_the_sidecars_are_auto_discovered_and_overridable(tmp_path: Path) -> None:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS[:3]))
    auto = run_trio(trio, tmp_path / "auto")
    explicit = dd.run(
        fields_jsonl=trio.fields,
        legacy_jsonl=trio.legacy,
        tos_jsonl=trio.tos,
        out_dir=tmp_path / "explicit",
        fields_lineage=trio.fields_lineage,
        legacy_lineage=trio.legacy_lineage,
        tos_lineage=trio.tos_lineage,
    )
    assert auto.diff_path.read_bytes() == explicit.diff_path.read_bytes()
    moved = tmp_path / "moved.json"
    moved.write_bytes(trio.legacy_lineage.read_bytes())
    trio.legacy_lineage.unlink()
    relocated = dd.run(
        fields_jsonl=trio.fields,
        legacy_jsonl=trio.legacy,
        tos_jsonl=trio.tos,
        out_dir=tmp_path / "relocated",
        legacy_lineage=moved,
    )
    assert relocated.diff_path.read_bytes() == auto.diff_path.read_bytes()


def _imported_module_roots() -> set[str]:
    """Every module this tool imports, by dotted name, from its AST.

    An AST walk rather than a line scan: it sees imports nested in functions,
    classes and ``try`` blocks too — which is the hole a line-prefix check
    leaves open and the real firewall gate (``tools/tos_firewall_check.py``)
    closes.
    """
    tree = ast.parse(
        (dd.REPO_ROOT / "tools" / "tos_cp3" / "diff_decisions.py").read_text(
            encoding="utf-8"
        )
    )
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names.add(base)
            names.update(f"{base}.{alias.name}" for alias in node.names)
    return names


def test_the_differ_imports_nothing_from_tos() -> None:
    """The reverse firewall, restated where a reader of this suite sees it.

    ``tools/tos_firewall_check.py`` is the gate; this is a fast local echo of
    it over the one module this PR adds, so a ``from tos...`` import added
    here — at any nesting depth — fails in the unit suite too.
    """
    for name in _imported_module_roots():
        root = name.split(".", 1)[0]
        assert root not in {"tos", "tos_runtime"}, name


def test_the_differ_reads_no_strategy_code() -> None:
    """B3 is artifact-to-artifact: no ``shared.*``, and not B1a's module either.

    The claim matters for CP-4, which deletes the legacy runtime: a B3 run over
    artifacts produced today must stay valid after the band math behind them is
    gone. Importing ``produce_fields`` would transitively require
    ``shared.decision.setups.vwap_reversion``, pandas and pyarrow to import
    cleanly for a run that reads three JSON files.
    """
    imported = _imported_module_roots()
    assert not {name for name in imported if name.split(".", 1)[0] == "shared"}
    assert not {name for name in imported if "produce_fields" in name}
    # The one thing it does take from the package is the suite version string.
    assert "tools.tos_cp3.TOS_CP3_VERSION" in imported


def test_the_local_provenance_helpers_do_not_drift_from_b1as() -> None:
    """B3 keeps its own copies on purpose; they must still behave identically.

    ``diff_decisions`` deliberately does not import ``produce_fields`` (see the
    previous test), so the two provenance helpers exist twice. This test is the
    guard that makes that duplication safe: the sidecar byte rendering and the
    git identity must be the same function in both, or a B3 lineage would stop
    being comparable with a B1a one.
    """
    document = {"a": 1, "b": [True, None, "텍스트"], "c": {"d": "x"}}
    assert dd.render_json(document) == produce_fields.render_lineage(document)
    assert dd._git_identity(dd.REPO_ROOT) == produce_fields._git_identity(dd.REPO_ROOT)


def test_the_runtime_block_records_no_library_that_cannot_change_the_output() -> None:
    """B3's only dependency is the standard library; the lineage says so.

    B1a records numpy/pandas/pyarrow because those libraries compute its
    values. None of them is reachable from B3, so recording a version for them
    would be a provenance claim with nothing behind it.
    """
    runtime = dd._runtime_versions()
    assert set(runtime) == {"python", "python_implementation", "third_party"}
    assert runtime["third_party"] == "none — standard library only"
