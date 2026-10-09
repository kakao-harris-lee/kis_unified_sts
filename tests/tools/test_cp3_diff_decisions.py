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
import copy
import hashlib
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.tos_cp3 import diff_decisions as dd
from tools.tos_cp3 import emit_legacy_decisions, produce_fields

SYMBOL = "101S6000"
WINDOW_START = "2025-12-01"
WINDOW_END = "2026-04-30"
MARKET_OPEN = "09:00"
MARKET_OPEN_SOURCE = "era-rule"
MIN_BARS_PER_DAY = 330
#: B1a's z scale (thousandths of one ATR), imported rather than restated.
Z_SCALE = produce_fields.Z_SCALE
#: The deployed entry thresholds, pinned to the two bindings files by
#: ``test_the_binding_is_the_truncated_extreme_multiple``. Two, because the
#: DSL has no ``abs()``: a LONG render compares the negative side and a SHORT
#: render the positive one, and the bindings loader refuses a key no rule
#: references — so the two deployments carry different key NAMES as well as
#: different values.
Z_ENTRY_MAX_X1000 = -1800
Z_ENTRY_MIN_X1000 = 1800
Z_ENTRY_THRESHOLD = {
    dd.DIRECTION_LONG: Z_ENTRY_MAX_X1000,
    dd.DIRECTION_SHORT: Z_ENTRY_MIN_X1000,
}

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

#: The three producers' source files. B3 reads none of them at run time; the
#: suite reads them so that a fixture cannot drift away from what a real run
#: would be given. ``differences.py`` lives inside ``tos/`` — read as TEXT,
#: never imported (the firewall forbids the import, not the read).
PRODUCE_FIELDS_SOURCE = dd.REPO_ROOT / "tools" / "tos_cp3" / "produce_fields.py"
EMIT_LEGACY_SOURCE = dd.REPO_ROOT / "tools" / "tos_cp3" / "emit_legacy_decisions.py"
B1B_DIFFERENCES_SOURCE = dd.REPO_ROOT / "tos" / "runtime" / "cp3" / "differences.py"
B1B_STRATEGY_SOURCE = (
    dd.REPO_ROOT
    / "tos"
    / "runtime"
    / "cp3"
    / "strategies"
    / "setup_d_long.strategy.yaml"
)
#: The SHORT render's own strategy file. It lives in a SEPARATE config_dir
#: because B1b refuses a ``strategies/`` directory holding two strategies, and
#: it is read here for the same reason as the LONG one: the gate-field list
#: this tool ships must be pinned against BOTH committed entry rules, or a
#: rename in the unread one stays green.
B1B_SHORT_STRATEGY_SOURCE = (
    dd.REPO_ROOT
    / "tos"
    / "runtime"
    / "cp3"
    / "short"
    / "strategies"
    / "setup_d_short.strategy.yaml"
)
#: The two YAML files the quantization derivation actually rests on. Read here,
#: never restated: an earlier revision asserted the derivation against
#: test-local literals (`extreme = 1.8`, `threshold = -1800`), so mutating
#: either file left the suite green while the derivation this tool SHIPS in
#: `config.quantization_edge` became false.
B1B_BINDINGS_SOURCE = (
    dd.REPO_ROOT / "tos" / "runtime" / "cp3" / "strategy_bindings.yaml"
)
B1B_SHORT_BINDINGS_SOURCE = (
    dd.REPO_ROOT / "tos" / "runtime" / "cp3" / "short" / "strategy_bindings.yaml"
)
SETUP_D_YAML_SOURCE = (
    dd.REPO_ROOT / "config" / "strategies" / "futures" / "setup_d_vwap_reversion.yaml"
)

#: ``direction -> (bindings file, strategy stem, strategy file)``.
DEPLOYED_SOURCES = {
    dd.DIRECTION_LONG: (
        B1B_BINDINGS_SOURCE,
        "setup_d_long.strategy",
        B1B_STRATEGY_SOURCE,
    ),
    dd.DIRECTION_SHORT: (
        B1B_SHORT_BINDINGS_SOURCE,
        "setup_d_short.strategy",
        B1B_SHORT_STRATEGY_SOURCE,
    ),
}


def deployed_entry_threshold(direction: str = dd.DIRECTION_LONG) -> int:
    """This direction's entry threshold as its deployed bindings file states it."""
    source, stem, _ = DEPLOYED_SOURCES[direction]
    document = yaml.safe_load(source.read_text(encoding="utf-8"))
    return int(
        document["strategies"][stem]["bindings"][dd.ENTRY_BINDING_KEY[direction]]
    )


def legacy_extreme_atr_mult() -> float:
    """``extreme_atr_mult`` as the legacy Setup D YAML states it."""
    document = yaml.safe_load(SETUP_D_YAML_SOURCE.read_text(encoding="utf-8"))
    return float(document["strategy"]["entry"]["params"]["extreme_atr_mult"])


def _declared_ids_from_source(path: Path, pattern: str) -> tuple[str, ...]:
    """Every ``"id": "<literal>"`` in *path* matching *pattern*, in file order.

    Derived, not restated: a renumbering or a dropped difference in
    ``produce_fields.py`` / ``emit_legacy_decisions.py`` /
    ``tos/runtime/cp3/differences.py`` changes these tuples, so a fixture built
    from them stops containing an id the attribution table cites and the
    suite goes red — where the first revision's hand-written ``D1..D10`` stayed
    green while every real run refused.
    """
    compiled = re.compile(pattern)
    found: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if (
                isinstance(key, ast.Constant)
                and key.value == "id"
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and compiled.fullmatch(value.value)
                and value.value not in found
            ):
                found.append(value.value)
    assert found, f"no declared-difference ids matching {pattern} in {path}"
    return tuple(found)


B1A_DIFFERENCE_IDS = _declared_ids_from_source(PRODUCE_FIELDS_SOURCE, r"D\d+")
B2_DIFFERENCE_IDS = _declared_ids_from_source(EMIT_LEGACY_SOURCE, r"L\d+")
B1B_DIFFERENCE_IDS = _declared_ids_from_source(B1B_DIFFERENCES_SOURCE, r"B1b-D\d+")

#: The strategy-file pin both (B1a, B2) lineages carry, and the input-file
#: list digest derived from it. Values are synthetic; what matters is that the
#: two sides agree, which is the thing the check tests.
STRATEGY_PATH = "config/strategies/futures/setup_d_vwap_reversion.yaml"
STRATEGY_SHA256 = "8d" * 32
INPUT_FILES = [
    {"path": "futures/minute/code=101S6000/part-0.parquet", "sha256": "ab" * 32},
    {"path": "futures/minute/code=101S6000/part-1.parquet", "sha256": "cd" * 32},
]


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
    direction: str = dd.DIRECTION_LONG,
    bindings: dict[str, Any] | None = None,
    b1b_parent_overrides: dict[str, Any] | None = None,
    b1a_pin: dict[str, Any] | None = None,
    b2_pin: dict[str, Any] | None = None,
    b1a_producer: dict[str, Any] | None = None,
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

    #: The (B1a, B2) pin: strategy file identity plus the input bytes both
    #: sides read. Equal by default; a test moves one side to prove the check.
    pin_a = {
        "strategy_path": STRATEGY_PATH,
        "strategy_sha256": STRATEGY_SHA256,
        "input_files": INPUT_FILES,
        **(b1a_pin or {}),
    }
    pin_b = {
        "strategy_path": STRATEGY_PATH,
        "strategy_sha256": STRATEGY_SHA256,
        "input_files": INPUT_FILES,
        **(b2_pin or {}),
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
                    **(b1a_producer or {}),
                },
                "dataset": {
                    "symbol": identity_a["symbol"],
                    "min_bars_per_day": identity_a["min_bars_per_day"],
                    "requested_start": identity_a["window_start"],
                    "requested_end": identity_a["window_end"],
                    "input_files": pin_a["input_files"],
                    "input_file_count": len(pin_a["input_files"]),
                },
                "strategy": {
                    "path": pin_a["strategy_path"],
                    "sha256": pin_a["strategy_sha256"],
                    "market_open_kst": identity_a["market_open_kst"],
                    "market_open_source": identity_a["market_open_source"],
                    # A float, on purpose: a lineage records its strategy's
                    # float parameters and `load_lineage` must permit them.
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
                "dataset": {
                    "symbol": identity_b["symbol"],
                    "input_files": pin_b["input_files"],
                    "input_file_count": len(pin_b["input_files"]),
                },
                "strategy": {
                    "path": pin_b["strategy_path"],
                    "sha256": pin_b["strategy_sha256"],
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
            "path": (
                str(DEPLOYED_SOURCES[direction][0].relative_to(dd.REPO_ROOT))
                if direction in DEPLOYED_SOURCES
                else "tos/runtime/cp3/strategy_bindings.yaml"
            ),
            "bindings": (
                {dd.ENTRY_BINDING_KEY[direction]: Z_ENTRY_THRESHOLD[direction]}
                if bindings is None and direction in Z_ENTRY_THRESHOLD
                else (bindings or {})
            ),
        },
        "strategy_file": {
            "path": (
                str(DEPLOYED_SOURCES[direction][2].relative_to(dd.REPO_ROOT))
                if direction in DEPLOYED_SOURCES
                else "tos/runtime/cp3/strategies/setup_d_long.strategy.yaml"
            ),
            "sha256": "47" * 32,
            "canonical_digest": "3a" * 32,
            "strategy_id": "astrat-" + "3a" * 32,
            # The key B3 reads to decide which legacy fires its AGREE_ENTRY
            # half is. B1b derives it from the authored ACTION targets; here it
            # is a fixture value so a test can make it wrong.
            "direction": direction,
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
                "counts": {
                    "fill_records": 1,
                    "handoffs": 1,
                    "capacity_denials": 3,
                    "realized_orders": [
                        {
                            "bar_index": 0,
                            "outcome_kind": "FLAT",
                            "raw_event_id": COVERAGE_BARS[0].raw_event_id,
                            "rule_id": "R2-EXIT-VWAP-REVERTED",
                        }
                    ],
                },
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
    # TOS_ONLY_ENTRY / UNRESOLVED — a COUNTERFACTUAL, and deliberately so.
    #
    # Under today's producers UNRESOLVED is unreachable, and that is not an
    # accident: B1a publishes an unevaluated gate as False (its D5), so a TOS
    # ACTION requires the legacy setup to have evaluated all four gates true,
    # which means it got past its own extreme/trend/stall/reversal checks and
    # can only have rejected on confidence — the one rule that covers it.
    # Every other reachable disagreement is covered by the other four rules.
    # So the only way to exercise UNRESOLVED is a bar the producers cannot
    # currently emit, and this is the shape that would appear FIRST if that
    # stopped being true: TOS fires at exactly the deployed threshold while
    # the legacy setup rejected as NOT_EXTREME. That is the very shape the
    # deleted quantization-edge rule claimed to explain
    # (`dd.quantization_edge_derivation`); the tool must leave it UNRESOLVED
    # and list it, not attribute it to B1a-D8.
    BarSpec(
        minute=8,
        legacy_outcome="NOT_EXTREME",
        legacy_direction=None,
        admitted=False,
        tos_outcome_kind="ACTION",
        tos_rule_id="R1-ENTRY-LONG",
        capacity_denied=True,
        hi_vol=True,
        stall_ok=True,
        reversal_ok=True,
        z_x1000=Z_ENTRY_MAX_X1000,
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
        dd.BUCKET_LEGACY_ONLY_ENTRY: 1,
        f"{dd.BUCKET_TOS_EXIT_PREFIX}AFTER_CUTOFF": 1,
        f"{dd.BUCKET_TOS_EXIT_PREFIX}VOL_BELOW_GATE": 1,
        dd.BUCKET_TOS_ONLY_ENTRY: 2,
    }


def test_every_attribution_rule_is_exercised(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    """Each rule in the table matched at least one bar, plus AGREED/UNRESOLVED."""
    _, result = coverage
    matched = result.summary["attribution_rules"]
    for rule in dd.build_attribution_rules(dd.DIRECTION_LONG):
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
        8: (dd.BUCKET_TOS_ONLY_ENTRY, dd.ATTRIBUTION_UNRESOLVED, []),
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
    assert unresolved["raw_event_ids"] == [COVERAGE_BARS[8].raw_event_id]
    assert unresolved["raw_event_ids_truncated"] is False


def ctx_for(direction: str) -> dd.DiffContext:
    """The deployment context a run of *direction* would read from B1b."""
    return dd.DiffContext(
        direction=direction,
        z_entry_binding_key=dd.ENTRY_BINDING_KEY[direction],
        z_entry_threshold_x1000=Z_ENTRY_THRESHOLD[direction],
    )


LONG_CTX = ctx_for(dd.DIRECTION_LONG)
SHORT_CTX = ctx_for(dd.DIRECTION_SHORT)


def expected_buckets(deployment: str) -> dict[tuple[str, str, str | None], str]:
    """The whole classification table for a deployment, written out.

    Membership in a family is not a property — swapping AGREE_ENTRY and
    TOS_ONLY_ENTRY would satisfy it — so every cell names the ONE bucket the
    decision tree must return. The table is a FUNCTION of the deployment's
    direction and the two renders are mirror images: only the two
    ``("ACTION", "FIRED", …)`` cells move, which is exactly the claim
    "direction decides which fires could agree".
    """
    other = dd.OPPOSITE_DIRECTION[deployment]
    return {
        ("ACTION", "FIRED", deployment): dd.BUCKET_AGREE_ENTRY,
        ("ACTION", "FIRED", other): dd.BUCKET_TOS_ONLY_ENTRY,
        ("ACTION", "VOL_BELOW_GATE", None): dd.BUCKET_TOS_ONLY_ENTRY,
        ("ACTION", "LOW_CONFIDENCE", deployment): dd.BUCKET_TOS_ONLY_ENTRY,
        ("FLAT", "FIRED", deployment): dd.BUCKET_LEGACY_ONLY_ENTRY,
        ("FLAT", "FIRED", other): dd.BUCKET_LEGACY_ONLY_ENTRY,
        ("FLAT", "VOL_BELOW_GATE", None): (
            f"{dd.BUCKET_TOS_EXIT_PREFIX}VOL_BELOW_GATE"
        ),
        ("FLAT", "LOW_CONFIDENCE", deployment): (
            f"{dd.BUCKET_TOS_EXIT_PREFIX}LOW_CONFIDENCE"
        ),
        ("NO_ACTION", "FIRED", deployment): dd.BUCKET_LEGACY_ONLY_ENTRY,
        ("NO_ACTION", "FIRED", other): dd.BUCKET_LEGACY_ONLY_ENTRY,
        ("NO_ACTION", "VOL_BELOW_GATE", None): dd.BUCKET_AGREE_NO_ACTION,
        ("NO_ACTION", "LOW_CONFIDENCE", deployment): dd.BUCKET_AGREE_NO_ACTION,
    }


@pytest.mark.parametrize("deployment", dd.DIRECTION_TOKENS)
def test_classification_is_exhaustive_over_kind_times_fire(deployment: str) -> None:
    """Every (outcome_kind, legacy outcome, direction) cell names one bucket.

    Run for BOTH deployments. The first revision ran it for one and hardcoded
    ``LONG`` in the classifier; the mirror run is what makes "AGREE_ENTRY is
    this deployment's own half" a measured property rather than a sentence.
    """
    table = expected_buckets(deployment)
    ctx = ctx_for(deployment)
    other = dd.OPPOSITE_DIRECTION[deployment]
    seen: set[tuple[str, str, str | None]] = set()
    for kind in dd.TOS_OUTCOME_KINDS:
        for outcome, direction in (
            ("FIRED", deployment),
            ("FIRED", other),
            ("VOL_BELOW_GATE", None),
            ("LOW_CONFIDENCE", deployment),
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
            cell = (kind, outcome, direction)
            assert dd.classify(bar, ctx) == table[cell], cell
            seen.add(cell)
    assert seen == set(table)


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
        dd.classify(bar, LONG_CTX)


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
    ctx = LONG_CTX
    table = dd.build_attribution_rules(ctx.direction)
    bucket = dd.classify(joined, ctx)
    assert dd.attribute(joined, bucket, ctx, table)[0] == (
        "agree_entry_rejected_by_legacy_position_model"
    )
    reversed_table = tuple(reversed(table))
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
    ctx = LONG_CTX
    assert dd.needs_attribution(joined, dd.BUCKET_AGREE_NO_ACTION) is False
    assert dd.attribute(
        joined,
        dd.BUCKET_AGREE_NO_ACTION,
        ctx,
        dd.build_attribution_rules(ctx.direction),
    ) == (
        dd.ATTRIBUTION_AGREED,
        (),
    )


@pytest.mark.parametrize("direction", dd.DIRECTION_TOKENS)
def test_the_binding_is_the_truncated_extreme_multiple(direction: str) -> None:
    """``z_entry_*_x1000 == ∓trunc(extreme_atr_mult * 1000)``, from the files.

    Both sides are READ, not restated. Concrete failing input: edit
    ``tos/runtime/cp3/strategy_bindings.yaml`` (or the SHORT render's own
    sibling under ``short/``) to ``∓1801``, or change the scale on either side.
    """
    sign = dd.ENTRY_THRESHOLD_SIGN[direction]
    assert deployed_entry_threshold(direction) == sign * int(
        legacy_extreme_atr_mult() * Z_SCALE
    )
    # The fixture constant is a convenience for the synthetic trios; it must
    # not be allowed to drift away from the deployment it stands in for.
    assert deployed_entry_threshold(direction) == Z_ENTRY_THRESHOLD[direction]


@pytest.mark.parametrize("direction", dd.DIRECTION_TOKENS)
def test_there_is_no_quantization_edge_rule_and_the_arithmetic_says_why(
    direction: str,
) -> None:
    """The premise an earlier revision shipped is false; this is the proof.

    The two predicates are compared over z values read nowhere else and the
    quantizer is B1a's own ``scaled_int_toward_zero``, so three different
    mutations turn this red — each of which would make the derivation this
    tool SHIPS (``config.quantization_edge``) false:

    * **the binding** — ``strategy_bindings.yaml``'s ``z_entry_max_x1000``
      moved off ``-trunc(extreme_atr_mult * 1000)`` (caught by the pin above
      and by the sweep).
    * **the strategy parameter** — ``extreme_atr_mult`` becomes non-integral
      at this scale (``1.8005``): the binding still truncates to ``-1800`` so
      the pin alone cannot see it, but ``z = -1.800`` then fires on the TOS
      side and not on the legacy one.
    * **the quantizer** — ``trunc`` replaced by ``floor``/``round``/``ceil``.
      This is why the sweep visits HALF-GRID z: at ``z = -1.7995`` trunc gives
      ``-1799`` (no fire, agreeing with legacy) while floor gives ``-1800``
      (fires, disagreeing). An on-grid-only sweep, as an earlier revision had,
      cannot tell the four apart at all — every quantizer agrees on an exact
      1/1000 point, so the loop was blind to the one operation the derivation
      rests on.
    """
    extreme = legacy_extreme_atr_mult()
    threshold = deployed_entry_threshold(direction)
    quantize = produce_fields.scaled_int_toward_zero
    long_side = direction == dd.DIRECTION_LONG

    sampled_half_grid = False
    # Tenths of a milli-ATR either side of zero: on-grid points (…, -1.800, …)
    # AND the half-grid points between them (…, -1.7995, …).
    for half in range(-40000, 40001):
        z = half / (Z_SCALE * 20)
        published = quantize(z, Z_SCALE)
        tos_fires = published <= threshold if long_side else published >= threshold
        legacy_fires_this_side = (z < 0 if long_side else z > 0) and abs(z) >= extreme
        assert tos_fires == legacy_fires_this_side, (
            z,
            published,
            threshold,
            extreme,
            direction,
        )
        if abs(half) % 20 == 10:
            sampled_half_grid = True
    assert sampled_half_grid, "the sweep must visit points between the grid"

    derivation = dd.quantization_edge_derivation(direction)
    assert "IDENTICAL" in derivation
    assert "NOT_EXTREME" in derivation
    assert dd.ENTRY_BINDING_KEY[direction] in derivation
    table = dd.build_attribution_rules(direction)
    assert not [rule for rule in table if "quantization" in rule.name]
    assert not [rule for rule in table if "B1a-D8" in rule.ids]


def test_the_sweep_would_catch_a_floor_quantizer() -> None:
    """The half-grid point, isolated, so the previous test's claim is checkable.

    With ``floor`` the published integer at ``z = -1.7995`` clears a threshold
    the real value does not, which is exactly the "edge" the deleted rule
    claimed — it exists only if the quantizer stops truncating toward zero.
    """
    extreme = legacy_extreme_atr_mult()
    threshold = deployed_entry_threshold()
    z = -(extreme - 0.0005)
    assert produce_fields.scaled_int_toward_zero(z, Z_SCALE) > threshold
    assert math.floor(z * Z_SCALE) <= threshold
    assert abs(z) < extreme  # legacy does not fire here


def test_the_deployed_threshold_is_read_from_the_bindings(tmp_path: Path) -> None:
    """No predicate reads it, but the report must record which one ran."""
    trio = write_trio(
        tmp_path / "in",
        list(COVERAGE_BARS[:2]),
        bindings={"z_entry_max_x1000": -2500},
    )
    result = run_trio(trio, tmp_path / "out")
    assert result.summary["config"]["z_entry_threshold_x1000"] == -2500
    assert result.lineage["config"]["z_entry_threshold_x1000"] == -2500
    assert result.summary["config"]["z_entry_binding_key"] == "z_entry_max_x1000"


@pytest.mark.parametrize("bindings", [{}, {"z_entry_max_x1000": "-1800"}])
def test_a_binding_without_an_integer_threshold_is_refused(
    tmp_path: Path, bindings: dict[str, Any]
) -> None:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS[:1]), bindings=bindings)
    with pytest.raises(dd.DiffDecisionsError, match="no.*integer z_entry_max_x1000"):
        run_trio(trio, tmp_path / "out")


@pytest.mark.parametrize(
    "direction", [None, "Long", "long", "", "BOTH", "SHORT_AND_LONG"]
)
def test_a_b1b_lineage_without_a_usable_direction_is_refused(
    tmp_path: Path, direction: Any
) -> None:
    """Red proof #1 for ``tos_deployment_direction_matches_entry_binding``.

    Concrete failing input: a B1b trace produced before 2026-10-09 (no
    ``parents.strategy_file.direction`` at all — the ``None`` case), or one
    whose token was renamed or case-folded. Before this check the tool assumed
    LONG, so a SHORT trace reported a headline agreement of ``0/374``.
    """
    trio = write_trio(
        tmp_path / "in",
        list(COVERAGE_BARS[:2]),
        b1b_parent_overrides={"strategy_file": {"direction": direction}},
    )
    out = tmp_path / "out"
    with pytest.raises(dd.DiffDecisionsError, match="parents.strategy_file.direction"):
        run_trio(trio, out)
    assert not (out / dd.DIFF_FILENAME).exists()


@pytest.mark.parametrize(
    ("direction", "bindings"),
    [
        (dd.DIRECTION_SHORT, {"z_entry_max_x1000": -1800}),
        (dd.DIRECTION_LONG, {"z_entry_min_x1000": 1800}),
    ],
)
def test_a_direction_contradicted_by_the_binding_key_is_refused(
    tmp_path: Path, direction: str, bindings: dict[str, Any]
) -> None:
    """Red proof #2: the declared direction and the deployed key disagree.

    The bindings loader refuses a key no rule references, so the key PRESENT
    is evidence of which side the entry rule compares. A lineage carrying the
    other direction's key is describing two different deployments at once.
    """
    trio = write_trio(
        tmp_path / "in",
        list(COVERAGE_BARS[:1]),
        direction=direction,
        bindings=bindings,
    )
    with pytest.raises(
        dd.DiffDecisionsError, match=f"no integer {dd.ENTRY_BINDING_KEY[direction]}"
    ):
        run_trio(trio, tmp_path / "out")


@pytest.mark.parametrize("direction", dd.DIRECTION_TOKENS)
def test_a_lineage_carrying_both_entry_thresholds_is_refused(
    tmp_path: Path, direction: str
) -> None:
    """Red proof #2b: the expected key is present, and so is the other one.

    Without this the check reads the expected key and ignores the rest, which
    admits exactly what its own sentence ("the key present IS evidence of
    which side the rule compares") says it rejects — the repo's
    ``guards-that-admit-what-they-name`` shape. A real B1b lineage cannot
    carry both (the bindings loader refuses a key no rule references), so an
    artifact that does is not describing one deployment.
    """
    trio = write_trio(
        tmp_path / "in",
        list(COVERAGE_BARS[:1]),
        direction=direction,
        bindings={
            "z_entry_max_x1000": Z_ENTRY_MAX_X1000,
            "z_entry_min_x1000": Z_ENTRY_MIN_X1000,
        },
    )
    with pytest.raises(dd.DiffDecisionsError, match="carry BOTH"):
        run_trio(trio, tmp_path / "out")


@pytest.mark.parametrize(
    ("direction", "bindings"),
    [
        (dd.DIRECTION_SHORT, {"z_entry_min_x1000": -1800}),
        (dd.DIRECTION_LONG, {"z_entry_max_x1000": 1800}),
        (dd.DIRECTION_SHORT, {"z_entry_min_x1000": 0}),
    ],
)
def test_a_threshold_whose_sign_contradicts_the_direction_is_refused(
    tmp_path: Path, direction: str, bindings: dict[str, Any]
) -> None:
    """Red proof #3: right key, wrong sign.

    ``z_x1000 >= -1800`` is true on almost every bar; a run against it would
    report near-total "agreement" that measures the sign error, not the
    policy. ``0`` is included because it is the value a half-edited file
    lands on and ``value * sign > 0`` must reject it.
    """
    trio = write_trio(
        tmp_path / "in",
        list(COVERAGE_BARS[:1]),
        direction=direction,
        bindings=bindings,
    )
    with pytest.raises(dd.DiffDecisionsError, match="sign contradicts it"):
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
    monkeypatch.setattr(
        dd, "ALL_ATTRIBUTION_RULES", dd.ALL_ATTRIBUTION_RULES + (bogus,)
    )
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
    cited = {i for rule in dd.ALL_ATTRIBUTION_RULES for i in rule.ids}
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
    assert "buckets_reconcile_to_bars" not in summary
    reconcile = next(
        check
        for check in result.lineage["checks"]
        if check["name"] == "buckets_sum_equals_input_line_count"
    )
    assert reconcile["bars"] == len(COVERAGE_BARS)
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

    They differ in their DENOMINATOR, not (under these producers) in their
    value: the position-model rate counts only the long fires the walk-forward
    gate would actually have entered — minutes 1 and 3 of 1, 2, 3. Both come
    out at 1 here for the same structural reason the real run does (a legacy
    long fire implies all four published gates are true, so the TOS rule fires
    too), which is why the test pins the four counts and not just the ratios: a
    regression that collapsed the two definitions into one would keep the
    ratios and lose the denominators.
    """
    rates = coverage[1].summary["rates"]
    rule_level = rates["rule_level_entry_agreement"]
    pm_level = rates["position_model_level_entry_agreement"]
    assert rule_level["numerator"] == 3  # minutes 1, 2, 3
    assert rule_level["denominator"] == 3  # the long fires
    assert rule_level["rate_x10000"] == 10000
    assert pm_level["numerator"] == 2  # minutes 1 and 3 were admitted
    assert pm_level["denominator"] == 2
    assert pm_level["rate_x10000"] == 10000
    assert rule_level["denominator"] != pm_level["denominator"]
    assert rule_level["definition"] != pm_level["definition"]
    for block in rates.values():
        assert block["definition"].strip()
    tos_side = rates["tos_action_explained_by_a_legacy_long_fire"]
    assert tos_side["numerator"] == 3
    assert tos_side["denominator"] == 5  # minutes 1-4 and 8 proposed an entry
    assert tos_side["rate_x10000"] == 6000


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
    assert checks["report_carries_no_floats"]["scanned"] == [
        dd.SUMMARY_FILENAME,
        dd.LINEAGE_FILENAME,
    ]


# ---------------------------------------------------------------------------
# Lineage shape
# ---------------------------------------------------------------------------


def test_every_check_is_recorded_in_the_lineage(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    _, result = coverage
    names = [check["name"] for check in result.lineage["checks"]]
    assert names == list(dd.CHECK_NAMES)
    # No `status` key: a refused run writes nothing, so a row could only ever
    # read "PASS" and asserting that would be a tautology (an earlier revision
    # did exactly that). What makes a row a guard is the red proof elsewhere in
    # this file, one per name.
    assert not [check for check in result.lineage["checks"] if "status" in check]
    assert all(check["detail"].strip() for check in result.lineage["checks"])
    # The module docstring states a count; it is derived from this list, so the
    # four-different-numbers defect cannot recur.
    assert f"and {_NUMBER_WORDS[len(dd.CHECK_NAMES) - 1]} more" in dd.__doc__


#: Only as many as the docstring needs; indexed by count.
_NUMBER_WORDS = {
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
}


def test_the_refusal_order_is_the_recorded_order_for_the_first_pair(
    tmp_path: Path,
) -> None:
    """Violate checks #1 and #2 together; #1's message must be the one raised.

    `run` used to call `assert_entry_outcome_literals` BEFORE
    `_lineage_refusals`, whose first act is the attribution-id check — so this
    trio was refused with check #2's message while the enumeration (and the PR
    body, and the kickoff doc) said the order was #1 then #2. The claim is only
    true if the first pair is ordered, and only a trio that breaks both can
    tell.
    """
    trio = write_trio(
        tmp_path / "in",
        list(COVERAGE_BARS[:1]),
        b1a_ids=tuple(i for i in B1A_DIFFERENCE_IDS if i != "D1"),
        legacy_outcomes=tuple(o for o in LEGACY_OUTCOMES if o != "LOW_CONFIDENCE"),
    )
    with pytest.raises(dd.DiffDecisionsError) as excinfo:
        run_trio(trio, tmp_path / "out")
    message = str(excinfo.value)
    assert "attribution table cites declared-difference ids" in message
    assert "B1a-D1" in message
    assert "closed_set" not in message
    # Both really were broken: each alone refuses with its own message.
    assert dd.CHECK_NAMES[0] == "attribution_ids_declared"
    assert dd.CHECK_NAMES[1] == "entry_outcome_literals_are_closed_set_members"
    with pytest.raises(dd.DiffDecisionsError, match="does not contain"):
        dd.assert_entry_outcome_literals(
            tuple(o for o in LEGACY_OUTCOMES if o != "LOW_CONFIDENCE")
        )


def test_a_check_name_outside_the_enumeration_is_refused() -> None:
    """``check_entry`` is the only way a row is built, and it is closed."""
    with pytest.raises(dd.DiffDecisionsError, match="not in CHECK_NAMES"):
        dd.check_entry("something_new", "detail")
    assert len(set(dd.CHECK_NAMES)) == len(dd.CHECK_NAMES)


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
    # Both shapes: the ISO form, and the compact ``20251208T084500+0900`` form
    # the sibling B1b guard was widened for (#877). Bare dates are NOT matched
    # — the window bounds are dates and are not clock reads.
    for pattern in (
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}",
        r"\d{8}T\d{6}",
        r"\d{2}:\d{2}:\d{2}",
    ):
        assert not re.search(pattern, text), pattern

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
        rule.name for rule in dd.build_attribution_rules(dd.DIRECTION_LONG)
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


class _RenameLocals(ast.NodeTransformer):
    """Rewrite argument names to positional placeholders."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.arg = self.mapping.get(node.arg, node.arg)
        return node

    def visit_Name(self, node: ast.Name) -> ast.Name:
        node.id = self.mapping.get(node.id, node.id)
        return node


def _normalized_function_ast(path: Path, name: str) -> str:
    """One function's AST with its own name, arg names and docstring removed.

    Projection comparisons (same output on one sample input) do not establish
    that two implementations are the same implementation — project memory
    ``guards-that-admit-what-they-name``: two implementations are compared by
    NORMALIZED AST, not by projection. Names are normalized because the two
    copies legitimately differ there (``render_json(document)`` vs
    ``render_lineage(lineage)``); everything else must match exactly.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            clone = copy.deepcopy(node)
            clone.name = "f"
            args = clone.args
            positional = args.posonlyargs + args.args + args.kwonlyargs
            mapping = {arg.arg: f"a{i}" for i, arg in enumerate(positional)}

            clone = _RenameLocals(mapping).visit(clone)
            if (
                clone.body
                and isinstance(clone.body[0], ast.Expr)
                and isinstance(clone.body[0].value, ast.Constant)
                and isinstance(clone.body[0].value.value, str)
            ):
                clone.body = clone.body[1:]
            return ast.dump(clone)
    raise AssertionError(f"{name} not found in {path}")


@pytest.mark.parametrize(
    "mine,theirs",
    [("render_json", "render_lineage"), ("_git_identity", "_git_identity")],
)
def test_the_local_provenance_helpers_are_b1as_implementation(
    mine: str, theirs: str
) -> None:
    """B3 keeps its own copies on purpose; they must BE the same implementation.

    ``diff_decisions`` deliberately does not import ``produce_fields`` (see the
    previous test), so these two helpers exist twice. What this pins is the
    SOURCE, normalized for the names that are allowed to differ — not one
    sample document's bytes, which an earlier revision compared and which a
    ``sort_keys`` divergence would have passed. Concrete failing input: flip
    ``sort_keys=False`` to ``True``, or drop the ``+ "\n"``, in either file.
    """
    assert _normalized_function_ast(
        dd.REPO_ROOT / "tools" / "tos_cp3" / "diff_decisions.py", mine
    ) == _normalized_function_ast(PRODUCE_FIELDS_SOURCE, theirs)


def test_the_provenance_helpers_also_agree_on_an_unsorted_document() -> None:
    """The behavioural half, on keys that are NOT already in sorted order."""
    document = {"z": 1, "a": {"y": True, "b": None}, "m": [3, "텍스트"]}
    assert dd.render_json(document) == produce_fields.render_lineage(document)
    assert b'"z": 1' in dd.render_json(document).split(b"\n")[1]
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


# ---------------------------------------------------------------------------
# Review dispositions (PR #878) — one red proof per new refusal
# ---------------------------------------------------------------------------


def test_a_float_in_a_producer_sidecar_refuses_the_report(tmp_path: Path) -> None:
    """Finding 4: the lineage copies the producer block out of the sidecars.

    ``load_lineage`` permits floats in a sidecar on purpose (a producer records
    its strategy's float parameters), and ``ArtifactRef.to_lineage`` copies
    ``producer.{name,version,source_id,git_commit}`` verbatim — so a sidecar
    whose ``tool.version`` is ``1.0`` puts a float in THIS tool's output.
    Scanning only ``summary.json``, as the first revision did, could not see
    it; the scan now covers the rendered bytes of both files.
    """
    trio = write_trio(
        tmp_path / "in", list(COVERAGE_BARS[:3]), b1a_producer={"version": 1.0}
    )
    out = tmp_path / "out"
    with pytest.raises(dd.DiffDecisionsError, match="would carry a float"):
        run_trio(trio, out)
    assert not out.exists() or not list(out.iterdir())


def test_the_float_scan_covers_both_sidecars(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    check = next(
        entry
        for entry in coverage[1].lineage["checks"]
        if entry["name"] == "report_carries_no_floats"
    )
    assert check["scanned"] == [dd.SUMMARY_FILENAME, dd.LINEAGE_FILENAME]
    scanned = dd._refuse_floats_in_report(
        (dd.SUMMARY_FILENAME, b"{}"), (dd.LINEAGE_FILENAME, b"{}")
    )
    assert scanned["scanned"] == [dd.SUMMARY_FILENAME, dd.LINEAGE_FILENAME]
    with pytest.raises(dd.DiffDecisionsError, match="lineage.json:a=1.5"):
        dd._refuse_floats_in_report(
            (dd.SUMMARY_FILENAME, b"{}"), (dd.LINEAGE_FILENAME, b'{"a": 1.5}')
        )


def test_the_direction_tokens_are_b2s_own(coverage: tuple[Trio, dd.RunResult]) -> None:
    """Finding 5: B2 does not declare them in its lineage, so pin the module.

    Concrete failing input: ``emit_legacy_decisions.DIRECTION_TOKENS`` starts
    publishing ``"Long"``. Without this pin, every long fire would move from
    ``AGREE_ENTRY`` to ``LEGACY_ONLY_ENTRY`` and the headline rate would read
    ``0/0`` "undefined" with every check recorded.
    """
    assert set(dd.DIRECTION_TOKENS) == set(
        emit_legacy_decisions.DIRECTION_TOKENS.values()
    )
    check = next(
        entry
        for entry in coverage[1].lineage["checks"]
        if entry["name"] == "legacy_direction_in_published_token_set"
    )
    assert check["tokens"] == list(dd.DIRECTION_TOKENS)


@pytest.mark.parametrize("token", ["Long", "long", "", "BOTH"])
def test_an_unrecognised_direction_is_refused(tmp_path: Path, token: str) -> None:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS[:3]))

    def retoken(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        payloads[1]["decision"]["direction"] = token
        return payloads

    mutate_jsonl(trio.legacy, retoken)
    seal(trio)
    with pytest.raises(dd.DiffDecisionsError, match="is not one of"):
        run_trio(trio, tmp_path / "out")


def test_a_fire_without_a_direction_is_refused(tmp_path: Path) -> None:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS[:3]))

    def drop(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        payloads[1]["decision"]["direction"] = None
        return payloads

    mutate_jsonl(trio.legacy, drop)
    seal(trio)
    with pytest.raises(dd.DiffDecisionsError, match="with direction None"):
        run_trio(trio, tmp_path / "out")


@pytest.mark.parametrize("dropped", ["FIRED", "LOW_CONFIDENCE"])
def test_an_outcome_literal_missing_from_the_closed_set_is_refused(
    tmp_path: Path, dropped: str
) -> None:
    """Finding 5: the two literals this tool branches on must be B2's own."""
    trio = write_trio(
        tmp_path / "in",
        list(COVERAGE_BARS[:1]),
        legacy_outcomes=tuple(o for o in LEGACY_OUTCOMES if o != dropped),
    )
    with pytest.raises(dd.DiffDecisionsError, match=dropped):
        run_trio(trio, tmp_path / "out")
    dd.assert_entry_outcome_literals(LEGACY_OUTCOMES)


def test_the_reconciliation_check_can_fail(coverage: tuple[Trio, dd.RunResult]) -> None:
    """Finding 8: the old flag was true by construction; this one is not.

    Concrete failing input: a bar lost between the digest pass's newline count
    and the classified record list.
    """
    _, result = coverage
    bars = [
        dd.JoinedBar(
            raw_event_id="x",
            as_of_ms=0,
            legacy_outcome="VOL_BELOW_GATE",
            legacy_direction=None,
            admitted=False,
            tos_outcome_kind="NO_ACTION",
            tos_rule_id=None,
            tos_capacity_denied=False,
            gates=(True, False, False, False),
            z_x1000=0,
        )
    ]
    records = dd.classify_all(bars, LONG_CTX)
    assert dd._check_reconciliation(records, 1)["bars"] == 1
    with pytest.raises(dd.DiffDecisionsError, match="do not reconcile"):
        dd._check_reconciliation(records, 2)


@pytest.mark.parametrize("direction", dd.DIRECTION_TOKENS)
def test_the_gate_fields_are_r1s_own_operands(direction: str) -> None:
    """(a): the literal list, pinned to the strategy files it was derived from.

    B3 never reads those files at run time (they are inside ``tos/`` and B3 is
    artifact-only), so the list is a literal — which is exactly why it needs a
    pin. Concrete failing input: a fifth gate, a rename, or a reordering of
    ``R1-ENTRY-<direction>``'s comparisons in **either** render. Both are
    checked: the field NAMES are direction-invariant (B1a publishes no SHORT
    variant — the gate booleans' direction comes from the sign of z), so one
    list covers both files, and a rename in the unchecked one would otherwise
    stay green.
    """
    _, _, source = DEPLOYED_SOURCES[direction]
    document = yaml.safe_load(source.read_text(encoding="utf-8"))
    r1 = document["policy"]["rules"][0]["all_of"]
    operands = [compare["left"]["ref"] for compare in r1]
    assert all(ref[:2] == ["capsule", "resolved_values"] for ref in operands)
    names = [ref[2] for ref in operands]
    # The four booleans, in R1's order; the fifth comparison is z_x1000
    # against the bound threshold, which is not a gate boolean.
    assert names[:-1] == list(dd.GATE_FIELDS)
    assert names[-1] == "z_x1000"
    assert r1[-1]["right"]["ref"] == ["config", dd.ENTRY_BINDING_KEY[direction]]
    # The comparison OPERATOR is the other half of "this render compares one
    # side": a LONG file with GE would fire on the SHORT extreme.
    assert r1[-1]["op"] == ("LE" if direction == dd.DIRECTION_LONG else "GE")


def test_the_two_attribution_tables_cite_exactly_the_same_ids() -> None:
    """Direction-invariance of the cited ids, which check #1 relies on.

    ``attribution_ids_declared`` runs FIRST, before the direction has been
    read, over the union of both tables. That is only sound while the two
    tables cite the same ids — if a future SHORT-only rule cited a new id, the
    union check would still pass for a LONG run whose lineage never declares
    it. Pinned here rather than asserted in a comment.
    """
    long_ids = {
        i for rule in dd.build_attribution_rules(dd.DIRECTION_LONG) for i in rule.ids
    }
    short_ids = {
        i for rule in dd.build_attribution_rules(dd.DIRECTION_SHORT) for i in rule.ids
    }
    assert long_ids == short_ids
    assert {i for rule in dd.ALL_ATTRIBUTION_RULES for i in rule.ids} == long_ids
    # Only the first rule's NAME is direction-dependent; the other four are not.
    long_names = [rule.name for rule in dd.build_attribution_rules(dd.DIRECTION_LONG)]
    short_names = [rule.name for rule in dd.build_attribution_rules(dd.DIRECTION_SHORT)]
    assert long_names[0] == "legacy_short_entry"
    assert short_names[0] == "legacy_long_entry"
    assert long_names[1:] == short_names[1:]
    assert len(long_names) == len(short_names) == 5


#: A trio a SHORT deployment would actually produce — **not** the LONG coverage
#: bars relabelled (2026-10-09 review M1). Relabelling gives a SHORT run with
#: ZERO ``AGREE_ENTRY`` bars, so neither headline rate has a non-empty
#: denominator and a mutation of
#: ``legacy_fired_in_deployment_direction_admitted_by_position_model`` back to
#: the hardcoded ``legacy_fired_long and admitted`` stayed green across the
#: whole file. Every bar here has a positive ``z_x1000``, which is the side a
#: SHORT entry rule compares.
SHORT_COVERAGE_BARS: tuple[BarSpec, ...] = (
    # AGREE_NO_ACTION / AGREED.
    BarSpec(minute=0, z_x1000=120),
    # AGREE_ENTRY, admitted, capacity available -> AGREED. Counts in BOTH
    # rates' numerator and denominator.
    BarSpec(
        minute=1,
        legacy_outcome="FIRED",
        legacy_direction="SHORT",
        admitted=True,
        tos_outcome_kind="ACTION",
        tos_rule_id="R1-ENTRY-SHORT",
        hi_vol=True,
        stall_ok=True,
        reversal_ok=True,
        z_x1000=2800,
    ),
    # AGREE_ENTRY the legacy position model would NOT have entered. In the
    # rule-level denominator, OUT of the position-model one: the single bar
    # that makes the two rates differ.
    BarSpec(
        minute=2,
        legacy_outcome="FIRED",
        legacy_direction="SHORT",
        admitted=False,
        tos_outcome_kind="ACTION",
        tos_rule_id="R1-ENTRY-SHORT",
        hi_vol=True,
        stall_ok=True,
        reversal_ok=True,
        z_x1000=2900,
    ),
    # AGREE_ENTRY, admitted, capacity denied -> the fill-level rule. Still in
    # both denominators: the decision agreed.
    BarSpec(
        minute=3,
        legacy_outcome="FIRED",
        legacy_direction="SHORT",
        admitted=True,
        tos_outcome_kind="ACTION",
        tos_rule_id="R1-ENTRY-SHORT",
        capacity_denied=True,
        hi_vol=True,
        stall_ok=True,
        reversal_ok=True,
        z_x1000=3100,
    ),
    # The unrendered half: a legacy LONG fire this run did not act on.
    BarSpec(
        minute=4,
        legacy_outcome="FIRED",
        legacy_direction="LONG",
        admitted=True,
        hi_vol=True,
        stall_ok=True,
        reversal_ok=True,
        z_x1000=-2600,
    ),
    # TOS_ONLY_ENTRY on a legacy LOW_CONFIDENCE bar — the published field set
    # cannot express min_confidence (B1a-D1 / B2-L9).
    BarSpec(
        minute=5,
        legacy_outcome="LOW_CONFIDENCE",
        legacy_direction="SHORT",
        tos_outcome_kind="ACTION",
        tos_rule_id="R1-ENTRY-SHORT",
        capacity_denied=True,
        hi_vol=True,
        stall_ok=True,
        reversal_ok=True,
        z_x1000=2100,
    ),
)


def test_a_short_run_mirrors_the_long_classification_and_attribution(
    tmp_path: Path,
) -> None:
    """A SHORT deployment's own trio, with both rates' denominators non-empty.

    What this pins that the LONG coverage run cannot: the rate denominators
    follow ``ctx.direction``. Concrete failing input (review M1): restore
    ``legacy_fired_in_deployment_direction_admitted_by_position_model`` to
    ``r.bar.legacy_fired_long and r.bar.admitted`` — identical for a LONG run,
    so every other test stays green, while this one reports ``2/1`` instead of
    ``2/2`` and on the real SHORT window would have reported ``56/96``.

    The three ``AGREE_ENTRY`` bars differ in exactly the two facts the two
    rates disagree about, so the rates come out 3/3 and 2/2 rather than being
    equal by accident.
    """
    trio = write_trio(
        tmp_path / "in", list(SHORT_COVERAGE_BARS), direction=dd.DIRECTION_SHORT
    )
    result = run_trio(trio, tmp_path / "out")

    assert result.summary["buckets"] == {
        dd.BUCKET_AGREE_ENTRY: 3,
        dd.BUCKET_AGREE_NO_ACTION: 1,
        dd.BUCKET_LEGACY_ONLY_ENTRY: 1,
        dd.BUCKET_TOS_ONLY_ENTRY: 1,
    }
    rules = result.summary["attribution_rules"]
    assert "legacy_long_entry" in rules
    assert "legacy_short_entry" not in rules
    assert rules["legacy_long_entry"]["ids"] == ["B1b-D5"]
    assert rules["legacy_long_entry"]["bars"] == 1
    assert rules["agree_entry_rejected_by_legacy_position_model"]["bars"] == 1
    assert rules["agree_entry_capacity_denied"]["bars"] == 1
    assert rules["tos_action_on_legacy_low_confidence"]["bars"] == 1

    totals = result.summary["totals"]
    assert totals["legacy_fired"] == 4
    assert totals["legacy_fired_long"] == 1
    assert totals["legacy_fired_short"] == 3
    assert totals["legacy_fired_in_deployment_direction"] == 3
    assert (
        totals["legacy_fired_in_deployment_direction_admitted_by_position_model"] == 2
    )
    assert totals["agree_entry"] == 3
    assert totals["agree_entry_admitted_by_position_model"] == 2
    assert totals["tos_action"] == 4

    rates = result.summary["rates"]
    rule_level = rates["rule_level_entry_agreement"]
    assert (rule_level["numerator"], rule_level["denominator"]) == (3, 3)
    assert "direction SHORT" in rule_level["definition"]
    position_level = rates["position_model_level_entry_agreement"]
    assert (position_level["numerator"], position_level["denominator"]) == (2, 2)
    assert "legacy FIRED SHORT" in position_level["definition"]
    tos_side = rates["tos_action_explained_by_a_legacy_short_fire"]
    assert (tos_side["numerator"], tos_side["denominator"]) == (3, 4)

    assert result.summary["unresolved"]["count"] == 0
    assert result.summary["config"]["deployment_direction"] == dd.DIRECTION_SHORT
    assert result.summary["config"]["z_entry_binding_key"] == "z_entry_min_x1000"


def test_a_tos_action_against_an_opposite_direction_legacy_fire_is_unresolved(
    tmp_path: Path,
) -> None:
    """Review M2's red proof: the severest disagreement must not be absorbed.

    The legacy rule fired LONG and this SHORT deployment proposed an entry on
    the SAME bar. That is a disagreement about DIRECTION, not "the other half
    has no counterpart here" — B1b-D5 says the unrendered half produces no TOS
    action, and this bar produced one. Concrete failing input: drop the
    ``bucket == BUCKET_LEGACY_ONLY_ENTRY`` scope from
    ``_legacy_opposite_direction_entry`` and the bar is filed under B1b-D5.
    """
    bars = [
        BarSpec(minute=0, z_x1000=120),
        BarSpec(
            minute=1,
            legacy_outcome="FIRED",
            legacy_direction="LONG",
            admitted=True,
            tos_outcome_kind="ACTION",
            tos_rule_id="R1-ENTRY-SHORT",
            capacity_denied=True,
            hi_vol=True,
            stall_ok=True,
            reversal_ok=True,
            z_x1000=2700,
        ),
    ]
    trio = write_trio(tmp_path / "in", bars, direction=dd.DIRECTION_SHORT)
    result = run_trio(trio, tmp_path / "out")

    record = next(
        r for r in _records(result) if r["raw_event_id"] == bars[1].raw_event_id
    )
    assert record["bucket"] == dd.BUCKET_TOS_ONLY_ENTRY
    assert record["attribution_rule"] == dd.ATTRIBUTION_UNRESOLVED
    assert record["attribution"] == []
    assert result.summary["unresolved"]["count"] == 1
    assert result.summary["unresolved"]["raw_event_ids"] == [bars[1].raw_event_id]
    assert "legacy_long_entry" not in result.summary["attribution_rules"]


def test_both_sidecars_declare_schema_version_two(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    """Review M3: the shape changed, so the version must say so.

    ``diff.jsonl`` is byte-identical across the 1 -> 2 change (the LONG run
    still reproduces ``ce36450f…``), which is precisely the trap: a consumer
    diffing payloads would conclude nothing moved while
    ``config.z_entry_max_x1000`` and
    ``totals.legacy_fired_long_admitted_by_position_model`` had been replaced.
    Pinned as a literal here AND asserted against the module constants, so
    neither can drift alone.
    """
    _, result = coverage
    assert dd.LINEAGE_SCHEMA_VERSION == dd.SUMMARY_SCHEMA_VERSION == 2
    assert result.lineage["lineage_schema_version"] == 2
    assert result.summary["summary_schema_version"] == 2
    # The v1 keys are gone, which is what makes the bump necessary rather than
    # cosmetic. Asserted as absences: a bump beside a key that never left would
    # be a version number with nothing behind it.
    assert "z_entry_max_x1000" not in result.summary["config"]
    assert "z_entry_max_x1000_source" not in result.summary["config"]
    assert "z_entry_max_x1000" not in result.lineage["config"]
    assert (
        "legacy_fired_long_admitted_by_position_model" not in result.summary["totals"]
    )
    # The third rate's KEY is per-direction now, which is the other half of the
    # v1 -> v2 shape change. Asserted on a SHORT run against the LONG one, not
    # as the absence of a key no version ever had: the first revision asserted
    # `"tos_action_explained_by_a_legacy_fire" not in rates`, which no
    # implementation could ever violate (2026-10-09 review).
    assert "tos_action_explained_by_a_legacy_long_fire" in result.summary["rates"]
    assert "tos_action_explained_by_a_legacy_short_fire" not in result.summary["rates"]


def test_the_absorbed_counts_say_which_ids_could_be_non_zero(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    """``declared_differences.cited_ids`` makes the structural zeros checkable.

    ``absorbed_bars: 0`` reads as a measurement, and for ``B1b-D8`` / ``B1b-D9``
    it is not: no attribution rule cites them, so their count is zero however
    the window behaved. The note beside the numbers says so, but a sentence is
    not a gate — ``cited_ids`` puts the list of ids that CAN be non-zero in the
    same block, derived from the table this run actually read.

    Concrete failing input: a rule's ``ids`` tuple changes and the block keeps
    claiming the old set.
    """
    _, result = coverage
    block = result.summary["declared_differences"]
    cited = set(block["cited_ids"])
    assert cited == {
        difference_id
        for rule in dd.build_attribution_rules(dd.DIRECTION_LONG)
        for difference_id in rule.ids
    }
    # The two the review was about are NOT in it, which is exactly why their
    # zero is structural.
    assert "B1b-D8" not in cited
    assert "B1b-D9" not in cited
    # Every uncited id really does sit at zero, and every non-zero id is cited
    # — the property that makes `cited_ids` a readable filter rather than a
    # decorative list.
    for entries in block["by_artifact"].values():
        for entry in entries:
            if entry["id"] not in cited:
                assert entry["absorbed_bars"] == 0, entry
    assert "STRUCTURAL" in block["note"]
    assert "UNRESOLVED" in block["note"]
    assert "cited_ids" in block["note"]


def test_the_absorbed_note_sends_the_reader_somewhere_that_exists(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    """A note in summary.json may only name keys summary.json actually has.

    Concrete failing input, and the one this test was written for: the note
    said "Check attribution_table[].ids". ``attribution_table`` exists only in
    ``lineage.json``, so a reader following the note found nothing — a
    cross-document pointer that reads as if it were local (2026-10-09 review).

    Asserted as a CLASS, not as that one string: every snake_case identifier
    the note mentions that is a key of ``lineage.json`` must also be reachable
    in ``summary.json``. That catches the next note which points at the other
    sidecar, which a literal ``"attribution_table" not in note`` would not.
    """
    _, result = coverage
    note = result.summary["declared_differences"]["note"]

    def keys_of(document: Any) -> set[str]:
        found: set[str] = set()
        stack = [document]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                found.update(node)
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
        return found

    summary_keys = keys_of(result.summary)
    lineage_only = keys_of(result.lineage) - summary_keys
    mentioned = set(re.findall(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+", note))
    assert not (mentioned & lineage_only), (
        f"declared_differences.note points at {sorted(mentioned & lineage_only)}, "
        "which exist in lineage.json but not in summary.json — a reader of the "
        "summary follows that pointer into nothing"
    )
    # And it does point at something: a note naming no key at all would pass
    # the assertion above vacuously.
    assert mentioned & summary_keys


def test_the_third_rate_key_names_the_deployment_direction(tmp_path: Path) -> None:
    """The SHORT half of the per-direction rate key.

    Concrete failing input: pin the key back to ``_long`` (or to any fixed
    token). A LONG run cannot see that — its key IS ``_long`` — so the
    assertion that bites has to be made on a SHORT run, which is what this
    test is for. Both halves are asserted so neither direction of the mistake
    passes: the SHORT key present AND the LONG key absent.
    """
    trio = write_trio(
        tmp_path / "in", list(SHORT_COVERAGE_BARS), direction=dd.DIRECTION_SHORT
    )
    rates = run_trio(trio, tmp_path / "out").summary["rates"]
    assert "tos_action_explained_by_a_legacy_short_fire" in rates
    assert "tos_action_explained_by_a_legacy_long_fire" not in rates
    # The two direction-independent keys stay put — the bump moved one key, not
    # all three, and a test that allowed the other two to drift would not say
    # which change it was pinning.
    assert "rule_level_entry_agreement" in rates
    assert "position_model_level_entry_agreement" in rates


def test_the_strategy_file_the_gate_list_came_from_is_recorded(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    classification = coverage[1].lineage["classification"]
    pinned = classification["gate_fields_derived_from_strategy"]
    assert pinned["canonical_digest"] and pinned["sha256"]
    assert pinned["path"].endswith("setup_d_long.strategy.yaml")


@pytest.mark.parametrize(
    "pin",
    [
        {"strategy_sha256": "ff" * 32},
        {"strategy_path": "config/strategies/futures/other.yaml"},
        {"input_files": [{"path": "p", "sha256": "ee" * 32}]},
    ],
)
def test_a_strategy_or_input_disagreement_between_b1a_and_b2_is_refused(
    tmp_path: Path, pin: dict[str, Any]
) -> None:
    """(b): the (B1a, B2) edge was pinned only on the six identity fields.

    Concrete failing input: the Setup D YAML is edited between the two runs, or
    one of them reads a re-written Parquet part. All six identity fields are
    unchanged and every ``raw_event_id`` lines up, so without this the two
    sides would be compared as if they had run the same strategy over the same
    bytes. The (B1a, B1b) edge is sha-pinned through B1b's ``parents``; this
    closes the asymmetry.
    """
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS[:2]), b2_pin=pin)
    with pytest.raises(
        dd.DiffDecisionsError, match="did not read the same strategy file"
    ):
        run_trio(trio, tmp_path / "out")


def test_the_strategy_and_input_pin_is_recorded_when_it_agrees(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    check = next(
        entry
        for entry in coverage[1].lineage["checks"]
        if entry["name"] == "strategy_yaml_and_input_files_agreement"
    )
    assert check["strategy_sha256"] == STRATEGY_SHA256
    assert check["strategy_path"] == STRATEGY_PATH
    assert check["input_file_count"] == len(INPUT_FILES)
    assert len(check["input_files_digest"]) == 64


@pytest.mark.parametrize("missing", ["strategy", "dataset"])
def test_a_lineage_without_the_pin_blocks_is_refused(
    tmp_path: Path, missing: str
) -> None:
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS[:1]))
    lineage = json.loads(trio.legacy_lineage.read_text(encoding="utf-8"))
    del lineage[missing]
    trio.legacy_lineage.write_bytes(dd.render_json(lineage))
    with pytest.raises(dd.DiffDecisionsError, match=f"has no {missing}"):
        run_trio(trio, tmp_path / "out")


def test_a_non_block_where_a_block_is_required_is_a_refusal_not_a_traceback(
    tmp_path: Path,
) -> None:
    """(g): a malformed sidecar must exit 2, not traceback at exit 1."""
    trio = write_trio(tmp_path / "in", list(COVERAGE_BARS[:1]))
    lineage = json.loads(trio.tos_lineage.read_text(encoding="utf-8"))
    lineage["parents"] = "not a block"
    trio.tos_lineage.write_bytes(dd.render_json(lineage))
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


def test_the_scope_block_echoes_b1bs_own_order_counts(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    """(c): B1b added these counts so handoffs=1 is not misread."""
    scope = coverage[1].summary["scope"]
    assert scope["tos_handoffs"] == 1
    assert scope["tos_fill_records"] == 1
    assert scope["tos_capacity_denials"] == 3
    assert scope["tos_realized_orders"][0]["raw_event_id"] == (
        COVERAGE_BARS[0].raw_event_id
    )
    assert "handoffs=1 is not misread" in scope["tos_realized_orders_note"]


def test_the_b1b_d7_obligation_is_recorded_as_unmet(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    """Finding 7: B1b-D7 asks for something these artifacts cannot supply.

    The requirement is stated, not silently skipped, and no position state is
    inferred — which is why the FLAT rule's own ``why`` carries the same
    warning as the scope block.
    """
    _, result = coverage
    note = result.summary["scope"]["b1b_d7_obligation"]
    assert note.startswith("UNMET.")
    assert "scope the legacy side to bars where a position was held" in note
    assert "UPPER BOUND" in note
    assert result.lineage["scope"]["b1b_d7_obligation"] == note
    flat_rule = next(
        entry
        for entry in result.lineage["attribution_table"]
        if entry["name"] == "tos_flat_without_legacy_fire"
    )
    assert "OBLIGATION UNMET" in flat_rule["why"]
    # And the obligation's own words really are in B1b's source, not invented.
    source = B1B_DIFFERENCES_SOURCE.read_text(encoding="utf-8")
    assert "scope the legacy side to bars " in source


def test_the_capacity_rules_why_does_not_overclaim(
    coverage: tuple[Trio, dd.RunResult],
) -> None:
    """(e): an earlier `why` said no ACTION bar carries an unrecorded denial.

    Fixture minute 2 is both un-admitted and capacity-denied and takes the
    earlier rule, so its denial is NOT in `attribution` — the claim was false
    and the text now says where a reader counts denials instead.
    """
    _, result = coverage
    record = next(
        r
        for r in _records(result)
        if r["raw_event_id"] == COVERAGE_BARS[2].raw_event_id
    )
    assert record["tos"]["capacity_denied"] is True
    assert "B1b-D1" not in record["attribution"]
    rule = next(
        entry
        for entry in result.lineage["attribution_table"]
        if entry["name"] == "agree_entry_capacity_denied"
    )
    assert "is NOT in its `attribution` list" in rule["why"]
    assert result.summary["totals"]["tos_action_capacity_denied"] == 4
