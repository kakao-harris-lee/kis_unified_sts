#!/usr/bin/env python3
"""CP-3 B2 — legacy per-bar candidate/reject emitter.

What this is
------------
The legacy half of the CP-3 "same input, compare decisions" path
(``docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md`` §3 B2, §5 step 2).
The plan's §3 names the gap this fills: neither backtest path emits a per-bar
candidate/reject record — ``shared/backtest/signals_writer.py`` is a no-op and
the only rejection evidence a harness run produces is the single number
``total_rejected_by_filter``. So "did the tenant policy fire on the same bars
the legacy strategy fired on, and where it did not, WHY not" cannot be asked of
any existing artifact.

This tool replays **the same bars as B1a** through
:class:`~shared.decision.setups.vwap_reversion.SetupDVWAPReversion` and writes
one line per bar carrying that bar's outcome — ``FIRED`` or the reject reason
— plus the setup's own evaluation trace, projected to integers and booleans.

Same window as B1a, by construction
-----------------------------------
The window is resolved by calling B1a's own
:func:`tools.tos_cp3.produce_fields.load_window` — the same Parquet loader, the
same ``--market-open`` era rule and the same ``--min-bars-per-day`` default. The
join keys come from B1a's :func:`~tools.tos_cp3.produce_fields.derive_raw_event_id`
and :func:`~tools.tos_cp3.produce_fields.derive_as_of_ms`. Nothing here
re-derives either: a second derivation, however identical-looking, is how the
two artifacts would come to disagree about which bar a line is about.

The bars B1a declines to publish (``_inputs_unusable`` — ``atr_14 <= 0``,
``vwap <= 0``, ``close <= 0``) are declined here too, by calling B1a's own
predicate, so the two files are line-for-line joinable on ``raw_event_id``. Each
such bar is still EVALUATED (the setup's causal deques must advance exactly as
in the legacy replay) and its outcome is recorded in the lineage rather than
dropped. One case is refused outright rather than declared: a bar with
``vwap <= 0`` but a usable ``atr``/``close`` is a bar on which ``check()`` can
FIRE on the fabricated extreme its own ``REQUIRES_VWAP`` docstring names, while
B1a omits the line — the join would then silently lose a FIRED bar.

Two questions, two answers per line
-----------------------------------
``outcome`` answers "did the RULE fire on this bar". It is not the same question
as "would the legacy system have entered here", because the walk-forward
harness that produced Setup D's published OOS numbers holds **one position at a
time**: a fire inside an open position is evaluated and discarded
(``scripts/analysis/walkforward_setup_d_vwap_reversion.py::collect_entries``,
lines 150-203 — ``last_exit_idx``, "evaluate-and-discard rather than skip").
The second answer is therefore the boolean
``would_be_admitted_by_legacy_position_model``, computed by replicating that
gate, with exits simulated by **that script's own**
``_simulate_exit`` (same file, lines 206-263: intrabar stop-before-target, then
EOD at its own ``EOD_HOUR``/``EOD_MINUTE`` = 15:15, then day-close, then
end-of-series) — loaded from the script by path rather than copied, so there is
no second exit simulation to drift (declared difference L3).

No floats
---------
The kernel drops a float field at its border
(``tos/src/tos/marketfeed/value.py``), so a float anywhere in this artifact
would be a value the comparison silently loses. :func:`_assert_no_floats` walks
the whole nested payload; the scaling rules are B1a's
(``scaled_int_half_up`` for price magnitudes, ``scaled_int_toward_zero`` for
signed, threshold-compared values), imported rather than restated.

Firewall
--------
``tools/`` is inside the reverse scan of ``tools/tos_firewall_check.py``
(TOS-FW-R), so this module imports **nothing** from ``tos`` or ``tos_runtime``.

Usage
-----
::

    .venv/bin/python tools/tos_cp3/emit_legacy_decisions.py \\
        --data-root /home/deploy/project/kis_unified_sts/data/market \\
        --symbol 101S6000 --start 2025-12-01 --end 2026-04-30 \\
        --strategy-yaml config/strategies/futures/setup_d_vwap_reversion.yaml \\
        --out /tmp/cp3-b2-run1
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import logging
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

#: Repo root of the checkout this file belongs to, inserted at the FRONT of
#: ``sys.path`` for the same reason B1a does it: an editable install of another
#: checkout must not shadow this worktree's ``shared/``, or the emitter would
#: run a different copy of the band math than the one under review.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.backtest.market_context_replay import (  # noqa: E402
    MarketContextReplay,
)
from shared.decision.setups.vwap_reversion import (  # noqa: E402
    SetupDConfig,
    SetupDVWAPReversion,
)
from shared.instruments.contract_spec import ContractSpec  # noqa: E402
from tools.tos_cp3 import TOS_CP3_VERSION  # noqa: E402

# Imported, not restated. The leading-underscore names are B1a's internals on
# purpose: the window loader, the bar accounting, the omission predicate and
# the provenance helpers must be THE SAME code on both sides of the join, and a
# "public" copy of each here is exactly the second implementation the kickoff
# plan §3 warns about. tools/tos_cp3 is one package with one owner.
from tools.tos_cp3.produce_fields import (  # noqa: E402
    DEFAULT_MIN_BARS_PER_DAY,
    OMITTED_ID_LIST_CAP,
    OPEN_ANCHOR_CUTOVER,
    PRE_CUTOVER_OPEN,
    PRICE_SCALE,
    Z_SCALE,
    InputFile,
    OpenAnchor,
    ProduceFieldsError,
    StrategyInputs,
    _bar_accounting,
    _bar_lookup,
    _git_identity,
    _inputs_unusable,
    _runtime_versions,
    derive_as_of_ms,
    derive_raw_event_id,
    load_window,
    render_lineage,
    scaled_int_half_up,
    scaled_int_toward_zero,
)

#: Lineage schema version for THIS artifact — separate from B1a's so a reader
#: can tell "values may differ" from "the sidecar is shaped differently".
LINEAGE_SCHEMA_VERSION = 1

#: Stable emitter identity stamped on every line as ``source_id``.
SOURCE_ID = f"tos-cp3-b2/{TOS_CP3_VERSION}"

#: Output file names inside ``--out``.
DECISIONS_FILENAME = "decisions.jsonl"
LINEAGE_FILENAME = "lineage.json"

#: Top-level keys of every line. ``raw_event_id`` and ``as_of_ms`` are B1a's
#: join keys, derived by B1a's own helpers — **those two are the join**.
#: ``instrument`` agrees with B1a's, and ``source_id`` deliberately DIFFERS
#: (``tos-cp3-b2/…`` vs ``tos-cp3-b1a/…``): it names which producer wrote the
#: line, so a tool that joined on it would match nothing. The payload hangs off
#: ``decision`` where B1a has ``fields``. This artifact is NOT read by the TOS
#: journal (it is legacy-side input to B3), so the journal's required-key set is
#: not a constraint here — only the join is.
LINE_KEYS = ("raw_event_id", "source_id", "instrument", "as_of_ms", "decision")

#: The legacy source whose ``_reject`` branches and ``ev[...]`` keys the two
#: closed sets below mirror. Both mirrors are pinned against this file's AST by
#: ``tests/tools/test_cp3_emit_legacy_decisions.py`` — a new reject branch or a
#: new trace key fails that test instead of becoming an unknown string at run
#: time (which this module also refuses).
LEGACY_SETUP_SOURCE = REPO_ROOT / "shared" / "decision" / "setups" / "vwap_reversion.py"

#: The walk-forward harness whose single-position gate and exit simulation the
#: ``would_be_admitted_by_legacy_position_model`` flag replicates. Loaded BY
#: PATH (``scripts/`` is not a package) the way the repo already loads analysis
#: scripts from tests — e.g. ``tests/unit/analysis/test_regime_gate_counterfactual.py``
#: lines 6-9 — so the exit simulation is that script's own code and not a copy.
WALKFORWARD_SCRIPT = (
    REPO_ROOT / "scripts" / "analysis" / "walkforward_setup_d_vwap_reversion.py"
)

#: The name the loaded script is registered under in ``sys.modules`` — needed
#: before execution, see :func:`load_walkforward_module`. Deliberately not the
#: script's own stem, so this private load cannot be mistaken for (or collide
#: with) an importable module of that name.
WALKFORWARD_MODULE_NAME = "cp3_b2_walkforward_setup_d"

#: The open anchor ``collect_entries`` takes TODAY, read off the
#: ``MarketContextReplay`` dataclass rather than written as a literal: the
#: script builds its replay without ``market_open_hour``/``market_open_minute``
#: (lines 160-167), so this field default IS what it uses, and a change to the
#: default must move this value rather than silently contradict it.
WALKFORWARD_TODAY_OPEN = (
    MarketContextReplay.__dataclass_fields__["market_open_hour"].default,
    MarketContextReplay.__dataclass_fields__["market_open_minute"].default,
)

#: Names this module needs from that script. Checked on load so a refactor
#: there fails loudly here instead of silently changing what "admitted" means.
WALKFORWARD_REQUIRED_NAMES = (
    "collect_entries",
    "_simulate_exit",
    "EOD_HOUR",
    "EOD_MINUTE",
)


class EmitLegacyDecisionsError(RuntimeError):
    """Raised when bars cannot be turned into a trustworthy decision stream."""


# ---------------------------------------------------------------------------
# Outcomes — the closed set
# ---------------------------------------------------------------------------

#: The one non-reject outcome.
OUTCOME_FIRED = "FIRED"

#: Every ``self._reject(...)`` branch of
#: :meth:`SetupDVWAPReversion.check`, as ``(match, literal, outcome)``.
#:
#: ``match`` is ``"exact"`` for a parameterless reason and ``"prefix"`` for one
#: that formats numbers into its tail. The numbers are deliberately NOT parsed
#: back out: every quantity they restate is already in the projected ``eval``
#: trace as an integer, and re-reading a ``.2f`` rendering would put a lossy
#: float back into this artifact.
#:
#: The three ``awaiting_reversal_confirm`` branches are kept apart because they
#: are three different causes (no prior close / no price turn / insufficient z
#: improvement). There is deliberately NO generic
#: ``awaiting_reversal_confirm(`` entry, so a fourth sub-cause added upstream
#: lands in :func:`outcome_for_reject_reason`'s refusal rather than being
#: quietly absorbed.
REJECT_OUTCOME_RULES: tuple[tuple[str, str, str], ...] = (
    ("exact", "no_atr", "NO_ATR"),
    ("exact", "no_price", "NO_PRICE"),
    (
        "exact",
        "awaiting_reversal_confirm(no_prev_close)",
        "AWAITING_REVERSAL_CONFIRM_NO_PREV_CLOSE",
    ),
    (
        "prefix",
        "awaiting_reversal_confirm(price_turn=",
        "AWAITING_REVERSAL_CONFIRM_PRICE_TURN",
    ),
    (
        "prefix",
        "awaiting_reversal_confirm(z_improve=",
        "AWAITING_REVERSAL_CONFIRM_Z_IMPROVE",
    ),
    ("prefix", "before_window(", "BEFORE_WINDOW"),
    ("prefix", "after_cutoff(", "AFTER_CUTOFF"),
    ("prefix", "vol_below_gate(", "VOL_BELOW_GATE"),
    ("prefix", "not_extreme(", "NOT_EXTREME"),
    ("prefix", "against_trend(", "AGAINST_TREND"),
    ("prefix", "still_trending_up(", "STILL_TRENDING_UP"),
    ("prefix", "still_trending_down(", "STILL_TRENDING_DOWN"),
    ("prefix", "low_confidence(", "LOW_CONFIDENCE"),
)

#: The closed set a line's ``outcome`` is drawn from, in a stable order.
OUTCOMES: tuple[str, ...] = (OUTCOME_FIRED,) + tuple(
    outcome for _, _, outcome in REJECT_OUTCOME_RULES
)


def outcome_for_reject_reason(reason: str) -> str:
    """Map a legacy ``last_reject_reason`` onto the closed outcome set.

    Refuses an unknown string. That refusal is the point: a reject branch added
    to the legacy setup must not silently become an ``UNKNOWN`` bucket that B3
    then reports as "no mismatch", nor a raw string that makes the outcome
    histogram unbounded. The concrete input it rejects, in the shape a future
    branch would take: ``"mystery_gate(1.00<2.00)"``.
    """
    matches = [
        outcome
        for match, literal, outcome in REJECT_OUTCOME_RULES
        if (reason == literal if match == "exact" else reason.startswith(literal))
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise EmitLegacyDecisionsError(
            f"unknown legacy reject reason {reason!r}: it matches none of the "
            f"{len(REJECT_OUTCOME_RULES)} enumerated branches of "
            "SetupDVWAPReversion.check(). A new reject branch must be added to "
            "REJECT_OUTCOME_RULES (and will have failed "
            "test_reject_reason_prefixes_cover_every_legacy_reject_branch "
            "first) — emitting it as an unclassified string would make the "
            "outcome histogram unbounded and let B3 read a new rejection as "
            "'no mismatch'"
        )
    raise EmitLegacyDecisionsError(
        f"ambiguous legacy reject reason {reason!r}: it matches "
        f"{matches} — REJECT_OUTCOME_RULES must not contain one literal that "
        "is a prefix of another"
    )


def classify_outcome(*, fired: bool, reject_reason: str | None) -> str:
    """Return this bar's outcome, refusing a fired/rejected contradiction.

    ``check()`` either returns a ``Signal`` (clearing ``last_reject_reason``)
    or takes exactly one ``_reject`` branch, so exactly one of the two inputs
    carries the answer. A bar that claims both, or neither, means the setup's
    own invariant broke and nothing downstream should be trusted.
    """
    if fired and reject_reason is None:
        return OUTCOME_FIRED
    if not fired and reject_reason is not None:
        return outcome_for_reject_reason(reject_reason)
    raise EmitLegacyDecisionsError(
        f"check() reported fired={fired} with last_reject_reason="
        f"{reject_reason!r}: exactly one of 'a signal' and 'a reject reason' "
        "must be present on every bar"
    )


# ---------------------------------------------------------------------------
# The evaluation trace — the other closed set
# ---------------------------------------------------------------------------

#: Projection kinds. The scaling rules are B1a's, for the same reasons:
#: price-like MAGNITUDES round half-up (monotone, nearest representable), while
#: SIGNED values that a threshold is compared against truncate toward zero so
#: the projection is symmetric about zero and never reads as clearing a
#: threshold the real value did not clear.
PROJ_BOOL = "bool"
PROJ_DIRECTION = "direction"
PROJ_PRICE_X100_HALF_UP = "price_x100_half_up"
PROJ_SIGNED_X100_TOWARD_ZERO = "signed_x100_toward_zero"
PROJ_SIGNED_X1000_TOWARD_ZERO = "signed_x1000_toward_zero"

#: Every key :meth:`SetupDVWAPReversion.check` writes into ``last_eval``, in
#: the order it writes them, as ``(trace key, published key, projection)``.
#:
#: Key ABSENCE is meaningful and is preserved: ``last_eval`` records a key only
#: for a branch ``check()`` actually took, so an absent key means "never
#: evaluated on this bar" and the published ``eval`` object simply does not
#: carry it. (This is where B2 differs from B1a, which maps an absent gate to
#: ``False`` because a Critical Input field has to have a value — declared
#: difference L6.) A key present with a ``None`` value is published as ``null``,
#: which is a different statement: "evaluated, no value".
EVAL_PROJECTION: tuple[tuple[str, str, str], ...] = (
    ("minutes_since_open", "minutes_since_open_x1000", PROJ_SIGNED_X1000_TOWARD_ZERO),
    ("entry_window", "entry_window", PROJ_BOOL),
    ("atr_14", "atr14_x100", PROJ_PRICE_X100_HALF_UP),
    ("close", "close_x100", PROJ_PRICE_X100_HALF_UP),
    ("vwap", "vwap_x100", PROJ_PRICE_X100_HALF_UP),
    ("inputs_usable", "inputs_usable", PROJ_BOOL),
    ("prev_close", "prev_close_x100", PROJ_PRICE_X100_HALF_UP),
    ("vol_ref", "vol_ref_x100", PROJ_PRICE_X100_HALF_UP),
    ("vol_gate_active", "vol_gate_active", PROJ_BOOL),
    ("vol_ratio", "vol_ratio_x1000", PROJ_SIGNED_X1000_TOWARD_ZERO),
    ("recent_high", "recent_high_x100", PROJ_PRICE_X100_HALF_UP),
    ("recent_low", "recent_low_x100", PROJ_PRICE_X100_HALF_UP),
    ("trend_score", "trend_score_x1000", PROJ_SIGNED_X1000_TOWARD_ZERO),
    ("hi_vol", "hi_vol", PROJ_BOOL),
    ("z", "z_x1000", PROJ_SIGNED_X1000_TOWARD_ZERO),
    ("extreme", "extreme", PROJ_BOOL),
    ("direction", "direction", PROJ_DIRECTION),
    ("trend_ok", "trend_ok", PROJ_BOOL),
    ("trend_override", "trend_override", PROJ_BOOL),
    ("stall_distance", "stall_distance_x100", PROJ_SIGNED_X100_TOWARD_ZERO),
    ("stall_buffer", "stall_buffer_x100", PROJ_PRICE_X100_HALF_UP),
    ("stall_ok", "stall_ok", PROJ_BOOL),
    ("prev_z", "prev_z_x1000", PROJ_SIGNED_X1000_TOWARD_ZERO),
    ("reversal_price_turn", "reversal_price_turn", PROJ_BOOL),
    (
        "reversal_z_improvement",
        "reversal_z_improvement_x1000",
        PROJ_SIGNED_X1000_TOWARD_ZERO,
    ),
    ("reversal_ok", "reversal_ok", PROJ_BOOL),
    ("confidence", "confidence_x1000", PROJ_SIGNED_X1000_TOWARD_ZERO),
    ("confidence_ok", "confidence_ok", PROJ_BOOL),
    ("fired", "fired", PROJ_BOOL),
)

#: ``last_eval`` key → (published key, projection).
_EVAL_BY_KEY: dict[str, tuple[str, str]] = {
    key: (published, projection) for key, published, projection in EVAL_PROJECTION
}

#: What each projection kind means on the wire, in the shape
#: ``config/tos_runtime/paper/critical_input_policy.yaml`` uses (a TOKEN for
#: ``scale``, a STRING for ``multiplier``) and B1a's lineage mirrors. Bare
#: numbers are deliberately not used: a reader reconstructing the real value
#: needs to know the rounding rule as much as the factor.
PROJECTION_ENCODING: dict[str, dict[str, str]] = {
    PROJ_BOOL: {
        "scale": "none",
        "multiplier": "1",
        "sign": "unsigned",
        "type": "bool",
        "quantization": "exact",
    },
    PROJ_DIRECTION: {
        "scale": "none",
        "multiplier": "1",
        "sign": "unsigned",
        "type": "str",
        "quantization": "exact",
    },
    PROJ_PRICE_X100_HALF_UP: {
        "scale": "hundredths",
        "multiplier": str(PRICE_SCALE),
        "sign": "unsigned",
        "type": "int",
        "quantization": "half_up",
    },
    PROJ_SIGNED_X100_TOWARD_ZERO: {
        "scale": "hundredths",
        "multiplier": str(PRICE_SCALE),
        "sign": "signed",
        "type": "int",
        "quantization": "truncate_toward_zero",
    },
    PROJ_SIGNED_X1000_TOWARD_ZERO: {
        "scale": "thousandths",
        "multiplier": str(Z_SCALE),
        "sign": "signed",
        "type": "int",
        "quantization": "truncate_toward_zero",
    },
}

#: The unit each trace key carries, keyed by ``last_eval`` key. Kept beside
#: :data:`EVAL_PROJECTION` rather than folded into it so the tuple arity the
#: tests unpack stays stable; a test asserts the two key sets are equal, so
#: this table cannot rot behind a new projection entry.
EVAL_UNITS: dict[str, str] = {
    "minutes_since_open": "minute",
    "entry_window": "bool",
    "atr_14": "index_point",
    "close": "index_point",
    "vwap": "index_point",
    "inputs_usable": "bool",
    "prev_close": "index_point",
    "vol_ref": "index_point",
    "vol_gate_active": "bool",
    "vol_ratio": "ratio",
    "recent_high": "index_point",
    "recent_low": "index_point",
    "trend_score": "atr",
    "hi_vol": "bool",
    "z": "atr",
    "extreme": "bool",
    "direction": "enum_long_short",
    "trend_ok": "bool",
    "trend_override": "bool",
    "stall_distance": "index_point",
    "stall_buffer": "index_point",
    "stall_ok": "bool",
    "prev_z": "atr",
    "reversal_price_turn": "bool",
    "reversal_z_improvement": "atr",
    "reversal_ok": "bool",
    "confidence": "ratio",
    "confidence_ok": "bool",
    "fired": "bool",
}

#: The four integers taken from the fired ``Signal`` rather than from the trace,
#: as ``(published key, projection, unit, parent)``.
BRACKET_PROJECTION: tuple[tuple[str, str, str, str], ...] = (
    (
        "confidence_x1000",
        PROJ_SIGNED_X1000_TOWARD_ZERO,
        "ratio",
        "signal:confidence",
    ),
    ("entry_x100", PROJ_PRICE_X100_HALF_UP, "index_point", "signal:entry_price"),
    ("stop_x100", PROJ_PRICE_X100_HALF_UP, "index_point", "signal:stop_loss"),
    ("target_x100", PROJ_PRICE_X100_HALF_UP, "index_point", "signal:take_profit"),
)

#: The legacy ``direction`` token → the published one.
DIRECTION_TOKENS = {"long": "LONG", "short": "SHORT"}


def _project_eval_value(
    key: str, published: str, projection: str, value: Any
) -> int | bool | str | None:
    """Project one ``last_eval`` value to an int / bool / str / null."""
    if value is None:
        return None
    if projection == PROJ_BOOL:
        if not isinstance(value, bool):
            raise EmitLegacyDecisionsError(
                f"last_eval[{key!r}] is {type(value).__name__} {value!r}, not a "
                f"bool, but {published!r} is published as one"
            )
        return value
    if projection == PROJ_DIRECTION:
        token = DIRECTION_TOKENS.get(str(value))
        if token is None:
            raise EmitLegacyDecisionsError(
                f"last_eval[{key!r}] is {value!r}; the legacy fade direction is "
                f"one of {sorted(DIRECTION_TOKENS)}"
            )
        return token
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EmitLegacyDecisionsError(
            f"last_eval[{key!r}] is {type(value).__name__} {value!r}, which "
            f"cannot be scaled as {projection}"
        )
    if projection == PROJ_PRICE_X100_HALF_UP:
        return scaled_int_half_up(float(value), PRICE_SCALE)
    if projection == PROJ_SIGNED_X100_TOWARD_ZERO:
        return scaled_int_toward_zero(float(value), PRICE_SCALE)
    if projection == PROJ_SIGNED_X1000_TOWARD_ZERO:
        return scaled_int_toward_zero(float(value), Z_SCALE)
    raise EmitLegacyDecisionsError(f"unknown projection {projection!r} for {key!r}")


def project_eval(
    last_eval: dict[str, Any],
) -> dict[str, int | bool | str | None]:
    """Project the setup's ``last_eval`` trace, refusing an unknown key.

    The order of :data:`EVAL_PROJECTION` is imposed on the result so the JSONL
    is byte-stable regardless of ``dict`` insertion order upstream.

    An unknown key is refused for the same reason an unknown reject reason is:
    a trace key added to the legacy setup carries a quantity nobody has chosen
    a scale for, and silently dropping it would make this artifact an
    incomplete record of a decision it claims to explain. The concrete input it
    rejects: ``{"some_new_gate_score": 1.5}``.
    """
    unknown = sorted(set(last_eval) - set(_EVAL_BY_KEY))
    if unknown:
        raise EmitLegacyDecisionsError(
            f"unknown last_eval key(s) {unknown}: SetupDVWAPReversion.check() "
            "now records a quantity this emitter has no declared scale for. Add "
            "it to EVAL_PROJECTION (test_eval_projection_covers_every_legacy_"
            "trace_key will have failed first) — dropping it silently would "
            "make this artifact an incomplete record of the decision it "
            "claims to explain"
        )
    out: dict[str, int | bool | str | None] = {}
    for key, published, projection in EVAL_PROJECTION:
        if key not in last_eval:
            continue
        out[published] = _project_eval_value(key, published, projection, last_eval[key])
    return out


# ---------------------------------------------------------------------------
# Config source: the strategy YAML vs the harness's own defaults
# ---------------------------------------------------------------------------


def config_source_diff(strategy: StrategyInputs) -> dict[str, dict[str, Any]]:
    """Per-field diff between the YAML this run used and the harness defaults.

    The walk-forward script that produced Setup D's published OOS numbers
    **never reads the strategy YAML**: it builds
    ``SetupDConfig(trend_filter_enabled=…, trend_window_bars=…,
    trend_warmup_bars=…, trend_block_threshold=…,
    against_trend_extreme_atr_mult=…)`` (lines 441-447) and takes the field
    default for everything else. So any field the YAML sets away from its
    default is a value the published run did not use — and some of those change
    which outcomes are *reachable at all*, not merely how often they occur.

    Computed from ``SetupDConfig()`` rather than written down, so it cannot
    describe a default that has since moved.
    """
    defaults = SetupDConfig()
    diff: dict[str, dict[str, Any]] = {}
    for name in type(defaults).model_fields:
        used = getattr(strategy.entry_config, name)
        default = getattr(defaults, name)
        if used != default:
            diff[name] = {"yaml": used, "harness_default": default}
    return diff


def outcomes_unreachable_under_harness_defaults() -> list[str]:
    """Outcomes no run at the harness defaults could ever emit.

    Derived from ``SetupDConfig()``, not listed: the gates that make these
    branches reachable are config-gated in ``check()``, so with the default
    value the branch is dead rather than rare. Today that is ``LOW_CONFIDENCE``
    (``min_confidence`` defaults to 0.0 and the gate is
    ``if c.min_confidence > 0.0 and …``) and all three
    ``AWAITING_REVERSAL_CONFIRM_*`` (``reversal_confirm_enabled`` defaults to
    False and the whole confirmation block sits under
    ``if c.reversal_confirm_enabled:``), plus ``AGAINST_TREND`` whenever the
    trend filter is off.

    This is why the published outcome mix cannot be compared to this run's:
    four of the fourteen outcomes could not occur in it.
    """
    defaults = SetupDConfig()
    unreachable: list[str] = []
    if not defaults.min_confidence > 0.0:
        unreachable.append("LOW_CONFIDENCE")
    if not defaults.reversal_confirm_enabled:
        unreachable.extend(
            outcome
            for outcome in OUTCOMES
            if outcome.startswith("AWAITING_REVERSAL_CONFIRM_")
        )
    if not defaults.trend_filter_enabled:
        unreachable.append("AGAINST_TREND")
    return [outcome for outcome in OUTCOMES if outcome in set(unreachable)]


# ---------------------------------------------------------------------------
# No floats
# ---------------------------------------------------------------------------


def _assert_no_floats(payload: Any, raw_event_id: str, path: str = "") -> None:
    """Refuse a float anywhere in the nested payload.

    The nested, ``None``-tolerant counterpart of B1a's
    ``produce_fields._assert_scalar_fields`` (which takes a flat field mapping
    and admits no ``None``). The rule it enforces is the same one and comes from
    the same place: ``tos/src/tos/marketfeed/value.py`` drops a float outright,
    so a float here would show up downstream as a silently missing value rather
    than as an error. Concretely this fires if a projection is ever changed to
    return ``value * scale`` instead of an ``int``.
    """
    if isinstance(payload, dict):
        for key, value in payload.items():
            _assert_no_floats(value, raw_event_id, f"{path}.{key}" if path else key)
        return
    if isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            _assert_no_floats(value, raw_event_id, f"{path}[{index}]")
        return
    if payload is None or isinstance(payload, (bool, int, str)):
        return
    raise EmitLegacyDecisionsError(
        f"{raw_event_id}: {path or '<root>'} is {type(payload).__name__} "
        f"{payload!r}; this artifact carries int/bool/str/null only"
    )


# ---------------------------------------------------------------------------
# The walk-forward harness, loaded by path
# ---------------------------------------------------------------------------

_WALKFORWARD_MODULE: ModuleType | None = None


def load_walkforward_module() -> ModuleType:
    """Load ``walkforward_setup_d_vwap_reversion.py`` as a module.

    ``scripts/`` is not a package, so the script is loaded by file path. The
    point of loading rather than copying is that :func:`emit_decisions` then
    runs the SAME single-position gate and exit simulation the published
    walk-forward used, so there is no second implementation to drift — the
    hazard the kickoff plan §3 names.

    The script has **module-level side effects**, because it is a script:

    * ``logging.basicConfig(level=INFO, format=…, stream=sys.stderr)`` — which
      on a process with no root handler yet installs one and sets the root
      level, changing logging for everything else in the process (a pytest
      session included).
    * ``sys.path.insert(0, PROJECT_ROOT)``.

    Both are saved and restored around ``exec_module`` so importing the script
    to borrow two functions does not reconfigure the caller's process. The
    registration in ``sys.modules`` is NOT undone on success — see below.
    """
    global _WALKFORWARD_MODULE
    if _WALKFORWARD_MODULE is not None:
        return _WALKFORWARD_MODULE
    if not WALKFORWARD_SCRIPT.is_file():
        raise EmitLegacyDecisionsError(
            f"{WALKFORWARD_SCRIPT} is missing: the single-position / re-entry "
            "gate this emitter reports is defined there and is not reproduced "
            "here"
        )
    spec = importlib.util.spec_from_file_location(
        WALKFORWARD_MODULE_NAME, WALKFORWARD_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise EmitLegacyDecisionsError(f"cannot load {WALKFORWARD_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    # Registered BEFORE exec_module: the script declares ``SimTrade`` as a
    # dataclass under ``from __future__ import annotations``, so
    # ``dataclasses`` resolves its string annotations through
    # ``sys.modules[cls.__module__].__dict__``. Without this line that lookup
    # returns None and the module raises ``AttributeError: 'NoneType' object
    # has no attribute '__dict__'`` while being defined. Same reason, same
    # shape as ``tools/tos_evidence_scan_measure.py`` lines ~442-452, which
    # loads its bench module this way and says so in the same words.
    #
    # It STAYS registered after a successful load: the dataclasses defined in
    # the module keep resolving annotations through it for the life of the
    # process (``SimTrade`` instances are created on every admitted entry), so
    # removing the entry would break the very objects this load exists to get.
    sys.modules[WALKFORWARD_MODULE_NAME] = module
    # Save the process-global state the script's module level writes to.
    saved_handlers = list(logging.root.handlers)
    saved_level = logging.root.level
    saved_path = list(sys.path)
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(WALKFORWARD_MODULE_NAME, None)
        raise
    finally:
        logging.root.handlers[:] = saved_handlers
        logging.root.setLevel(saved_level)
        sys.path[:] = saved_path
    missing = [name for name in WALKFORWARD_REQUIRED_NAMES if not hasattr(module, name)]
    if missing:
        raise EmitLegacyDecisionsError(
            f"{WALKFORWARD_SCRIPT} no longer defines {missing}: the "
            "single-position gate and its exit simulation have been "
            "refactored, so what 'admitted' means here is no longer the "
            "published harness's meaning"
        )
    _WALKFORWARD_MODULE = module
    return module


def assert_eod_agreement(wf: ModuleType, strategy: StrategyInputs) -> None:
    """Refuse when the harness's EOD constants and the YAML's cutoff disagree.

    The admission flag's exits come from the harness's own
    ``EOD_HOUR``/``EOD_MINUTE`` (declared difference L3), while the published
    ``eod`` field and the live exit come from
    ``SetupTargetExitConfig.eod_close_time``. They agree today (both 15:15),
    and the earlier revision of this tool merely PRINTED both into the lineage
    and let a reader notice. That is the wrong shape: if the YAML cutoff moved
    to 15:10, every admitted entry would still be held to 15:15 by the harness
    constant, the two numbers would sit side by side in the sidecar, and
    nothing would say the artifact had become incoherent.

    The concrete input this refuses: ``eod_close_minute: 10`` in the strategy
    YAML (or an ``EOD_MINUTE`` changed in the harness) — either direction.
    """
    cutoff = strategy.exit_config.eod_close_time
    harness = (int(wf.EOD_HOUR), int(wf.EOD_MINUTE))
    configured = (cutoff.hour, cutoff.minute)
    if harness != configured:
        raise EmitLegacyDecisionsError(
            "EOD cutoff disagreement: the walk-forward harness exits at "
            f"{harness[0]:02d}:{harness[1]:02d} "
            "(walkforward_setup_d_vwap_reversion.py EOD_HOUR/EOD_MINUTE) but "
            f"{strategy.path} sets eod_close_time "
            f"{configured[0]:02d}:{configured[1]:02d}. The admission flag and "
            "the eod semantics of the joined B1a field set would then describe "
            "different session ends, so the artifact would be incoherent in a "
            "way no count in the lineage reveals"
        )


# ---------------------------------------------------------------------------
# Emission
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionRecord:
    """One replayed bar's legacy decision.

    ``bar_kst`` is carried for the lineage summary and for tests; it is not
    published (the wire form is exactly :data:`LINE_KEYS`).
    """

    raw_event_id: str
    instrument: str
    as_of_ms: int
    outcome: str
    direction: str | None
    confidence_x1000: int | None
    entry_x100: int | None
    stop_x100: int | None
    target_x100: int | None
    would_be_admitted_by_legacy_position_model: bool
    eval_trace: dict[str, int | bool | str | None]
    bar_kst: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "raw_event_id": self.raw_event_id,
            "source_id": SOURCE_ID,
            "instrument": self.instrument,
            "as_of_ms": self.as_of_ms,
            "decision": {
                "outcome": self.outcome,
                "direction": self.direction,
                "confidence_x1000": self.confidence_x1000,
                "entry_x100": self.entry_x100,
                "stop_x100": self.stop_x100,
                "target_x100": self.target_x100,
                "would_be_admitted_by_legacy_position_model": (
                    self.would_be_admitted_by_legacy_position_model
                ),
                "eval": self.eval_trace,
            },
        }

    def to_json_line(self) -> str:
        return json.dumps(self.to_payload(), separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class EmittedDecisions:
    """Emitted records plus the bars deliberately left unpublished."""

    records: list[DecisionRecord]
    bars_replayed: int
    #: ``(raw_event_id, omission reason, legacy outcome)`` — the outcome is
    #: kept so an omitted bar's decision is recorded somewhere even though it
    #: has no line.
    omitted: list[tuple[str, str, str]]
    #: Bar indices (into the gated frame) the single-position model admitted.
    admitted_indices: list[int]


def emit_decisions(
    df: Any,
    *,
    symbol: str,
    strategy: StrategyInputs,
    contract_spec: ContractSpec,
    anchor: OpenAnchor,
) -> EmittedDecisions:
    """Replay the gated frame and project each bar's legacy decision.

    One ``check()`` call per bar, in bar order — that single call is what
    advances the setup's causal ATR / close / VWAP windows, so calling it more
    or fewer times than the legacy replay would change ``hi_vol`` and
    ``stall_ok``. Nothing here recomputes a threshold or a formula the setup
    owns; the decision is read off the returned ``Signal``,
    ``last_reject_reason`` and ``last_eval``.

    The single-position gate runs in this same pass, so its state
    (``last_exit_idx``) advances on the same call sequence rather than on a
    second replay.
    """
    import pandas as pd

    wf = load_walkforward_module()
    assert_eod_agreement(wf, strategy)

    # B1a's OHLCV lookup, called for its REFUSAL, not for its result: it
    # rejects a duplicated bar timestamp (the #516 minute-dedup defect). B2
    # publishes no OHLC, but the same duplicate would be worse here than there
    # — ``ts_to_idx`` below would keep only the LAST index for the repeated
    # stamp, so ``last_exit_idx`` would be compared against the wrong bar and
    # the emitted join key would appear twice, which B3 joins one-to-many
    # without noticing. Calling B1a's assertion rather than restating it keeps
    # one definition of "this frame is usable" on both sides of the join.
    _bar_lookup(df)

    setup = SetupDVWAPReversion(config=strategy.entry_config)
    replay = MarketContextReplay(
        df=df,
        symbol=symbol,
        macro_snapshot=None,
        scheduled_events=[],
        contract_spec=contract_spec,
        market_open_hour=anchor.hour,
        market_open_minute=anchor.minute,
        min_volume=0,
    )

    # Mirrors collect_entries lines 170-171 exactly: the position model's state
    # is an index into the GATED frame, not a position in the replayed stream.
    ts_to_idx = {
        pd.Timestamp(stamp): index
        for index, stamp in enumerate(df["timestamp"].tolist())
    }

    records: list[DecisionRecord] = []
    omitted: list[tuple[str, str, str]] = []
    admitted_indices: list[int] = []
    bars_replayed = 0
    last_exit_idx = -1  # collect_entries line 174 — one position at a time

    for ctx in replay.iter_contexts():
        now: datetime = ctx.now
        stamp = pd.Timestamp(now)
        ts_naive = stamp.tz_localize(None) if stamp.tzinfo else stamp
        raw_event_id = derive_raw_event_id(symbol, now)
        idx = ts_to_idx.get(ts_naive)
        if idx is None:
            # collect_entries line 179-180 CONTINUES here, skipping check() and
            # so freezing the causal windows. A replay built from this very
            # frame cannot reach that branch, and B1a raises on the same
            # condition. Refuse rather than diverge silently from both.
            raise EmitLegacyDecisionsError(
                f"{raw_event_id}: the replay yielded a bar with no row in the "
                "loaded frame. The walk-forward harness skips such a bar "
                "WITHOUT evaluating it (collect_entries lines 179-180), which "
                "would freeze the setup's causal windows and make this "
                "artifact disagree with both the harness and B1a"
            )

        signal = setup.check(ctx)
        bars_replayed += 1
        outcome = classify_outcome(
            fired=signal is not None, reject_reason=setup.last_reject_reason
        )
        last_eval = dict(setup.last_eval)

        # Single-position / re-entry gate, in collect_entries' order: the bar
        # is evaluated above either way, and only then discarded if a prior
        # position is still open (lines 182-189).
        admitted = False
        if idx > last_exit_idx and signal is not None:
            side = "BUY" if signal.direction == "long" else "SELL"  # line 191
            trade = wf._simulate_exit(  # lines 192-200
                df,
                idx,
                ts_naive,
                signal.entry_price,
                side,
                signal.stop_loss,
                signal.take_profit,
            )
            last_exit_idx = trade.bar_idx  # line 202
            admitted = True
            admitted_indices.append(idx)

        unusable = _inputs_unusable(
            float(ctx.current_price), float(ctx.vwap), float(ctx.atr_14)
        )
        if unusable is not None:
            if signal is not None:
                raise EmitLegacyDecisionsError(
                    f"{raw_event_id}: check() FIRED on a bar B1a declines to "
                    f"publish ({unusable}). The documented case is vwap <= 0 "
                    "with a usable atr/close, where the extension degenerates "
                    "to close/atr — 'a huge FABRICATED extreme' "
                    "(SetupDVWAPReversion.REQUIRES_VWAP). Emitting no line for "
                    "it would make the join lose a FIRED bar; emitting one "
                    "would break the line-for-line join with B1a. Neither is "
                    "acceptable without a decision, so the run refuses"
                )
            omitted.append((raw_event_id, unusable, outcome))
            continue

        projected = project_eval(last_eval)
        record = DecisionRecord(
            raw_event_id=raw_event_id,
            instrument=symbol,
            as_of_ms=derive_as_of_ms(now),
            outcome=outcome,
            # The published spelling of the trace's own ``direction`` key, so
            # the top-level field and the trace can never disagree.
            direction=projected.get(_EVAL_BY_KEY["direction"][0]),  # type: ignore[arg-type]
            confidence_x1000=(
                scaled_int_toward_zero(float(signal.confidence), Z_SCALE)
                if signal is not None
                else None
            ),
            entry_x100=(
                scaled_int_half_up(float(signal.entry_price), PRICE_SCALE)
                if signal is not None
                else None
            ),
            stop_x100=(
                scaled_int_half_up(float(signal.stop_loss), PRICE_SCALE)
                if signal is not None
                else None
            ),
            target_x100=(
                scaled_int_half_up(float(signal.take_profit), PRICE_SCALE)
                if signal is not None
                else None
            ),
            would_be_admitted_by_legacy_position_model=admitted,
            eval_trace=projected,
            bar_kst=now,
        )
        payload = record.to_payload()
        _assert_no_floats(payload, raw_event_id)
        if set(payload) != set(LINE_KEYS):
            raise EmitLegacyDecisionsError(
                f"{raw_event_id}: line keys {sorted(payload)} != "
                f"{sorted(LINE_KEYS)}"
            )
        if admitted and outcome != OUTCOME_FIRED:
            raise EmitLegacyDecisionsError(
                f"{raw_event_id}: admitted by the position model with outcome "
                f"{outcome}; only {OUTCOME_FIRED} can be admitted"
            )
        records.append(record)

    if not records:
        raise EmitLegacyDecisionsError(
            "replay yielded no publishable bars: a window shorter than the "
            "replay warmup, a first session with no prior-session close, or "
            f"{len(omitted)} unusable-input bars"
        )
    return EmittedDecisions(
        records=records,
        bars_replayed=bars_replayed,
        omitted=omitted,
        admitted_indices=admitted_indices,
    )


def render_jsonl(records: list[DecisionRecord]) -> bytes:
    """Serialize *records* to the exact bytes written to disk."""
    return "".join(f"{record.to_json_line()}\n" for record in records).encode("utf-8")


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------

# The omitted-id list cap is B1a's ``OMITTED_ID_LIST_CAP``, imported above: the
# two sidecars truncate the same list at the same length, so a reader comparing
# them never sees one artifact's sample end where the other's continues. (The
# count and the per-outcome tally are always exact; only the id list is capped.)


def _declared_differences(
    strategy: StrategyInputs, anchor: OpenAnchor
) -> list[dict[str, Any]]:
    """Every way B2's view differs from what the live paper orchestrator does."""
    cfg = strategy.entry_config
    wf = load_walkforward_module()
    return [
        {
            "id": "L1",
            "item": "regime direction blocks cannot fire",
            "value": {
                "long_blocked_regimes": strategy.entry_params.get(
                    "long_blocked_regimes"
                ),
                "short_blocked_regimes": strategy.entry_params.get(
                    "short_blocked_regimes"
                ),
                "regime_gate_enabled": bool(
                    (strategy.entry_params.get("regime_gate") or {}).get(
                        "enabled", False
                    )
                ),
            },
            "note": (
                "This emitter runs SetupDVWAPReversion.check() ALONE. The live "
                "paper path runs it behind shared/strategy/entry/"
                "setup_d_adapter.py, which — when long_blocked_regimes or "
                "short_blocked_regimes is non-empty (lines 174-199) — resolves "
                "a regime label via setup_llm_gate.resolve_regime_label (LLM "
                "market context, else EntryContext.metadata 'regime' / "
                "'market_state'; lines 67-84) and drops a SHORT whose regime is "
                "in short_blocked_regimes. B2 builds no EntryContext and has no "
                "LLM context, so that block CANNOT fire here and every SHORT "
                "the rule produced is reported. Note the adapter itself skips "
                "the block when the label is unavailable (lines 176-178, "
                "'block skipped (signal passes)'), so the difference is "
                "'B2 never resolves a label' rather than 'B2 ignores one'. "
                "Kickoff §4 decision 5 deletes short_blocked_regimes as an "
                "intended difference; until the YAML changes, a SHORT diff in "
                "a paper comparison is attributable to this item."
            ),
        },
        {
            "id": "L2",
            "item": (
                "the admitted count is not the published trade count — four "
                "reasons, one of them unresolved"
            ),
            "value": {
                "this_run_anchor": anchor.kst,
                "this_run_anchor_source": anchor.source,
                "collect_entries_anchor_today": (
                    f"{WALKFORWARD_TODAY_OPEN[0]:02d}:"
                    f"{WALKFORWARD_TODAY_OPEN[1]:02d}"
                ),
                "collect_entries_anchor_source": (
                    "MarketContextReplay.market_open_hour/minute field "
                    "defaults — collect_entries lines 160-167 pass neither"
                ),
                "era_cutover": OPEN_ANCHOR_CUTOVER.isoformat(),
                "pre_cutover_open": (
                    f"{PRE_CUTOVER_OPEN[0]:02d}:{PRE_CUTOVER_OPEN[1]:02d}"
                ),
                "anchor_of_published_numbers": "unresolved — see note (c)",
                "published_oos_trades": 135,
                "published_fold_mode": (
                    "daily-stride, --is-days 40 / --oos-days 10 / --step-days "
                    "10 (walkforward script lines 405-416, 486-491; folds built "
                    "by split_folds_trading_days lines 372-392)"
                ),
                "config_source_diff": "see the top-level config_source_diff block",
            },
            "note": (
                "The flag replicates the harness's GATING ALGORITHM, not its "
                "published run, and four separate things stand between the two "
                "numbers. "
                f"(a) THIS RUN is anchored at {anchor.kst} ({anchor.source}), "
                "the same rule B1a uses, so the two artifacts line up bar for "
                "bar. "
                "(b) collect_entries TODAY takes "
                f"{WALKFORWARD_TODAY_OPEN[0]:02d}:"
                f"{WALKFORWARD_TODAY_OPEN[1]:02d} because it passes no open to "
                "MarketContextReplay and that is the field default — but that "
                "default POSTDATES the script (the session moved 2026-06-28, "
                "#552), so it is not evidence about what the published run "
                "used. "
                "(c) UNRESOLVED: two sources say the published numbers were "
                "computed at 09:00 — market_context_replay.py lines ~86-91 "
                "('Setup A / Setup D OOS Sharpe were computed at 09:00', and a "
                "pre-cutover replay MUST pass 09:00) and "
                "docs/plans/2026-07-06-futures-strategy-improvement-roadmap.md "
                "P1.3 ('Their headline numbers were computed at the 09:00 "
                "anchor ... Re-run the dedicated walk-forwards at 08:45 before "
                "any promotion decision' — still unexecuted). Against that, the "
                "2026-07-06 re-examination that records the +2.135 / 135-trade "
                "figures is dated AFTER the 2026-06-28 cutover, when a plain "
                "re-run would have picked up the 08:45 default. This tool does "
                "not settle it: an earlier revision of this entry asserted the "
                "published run used 08:45, which contradicted the "
                "PRE_CUTOVER_OPEN constant this very module imports. Treat the "
                "anchor of the published numbers as UNKNOWN until P1.3 is run. "
                "(d) Even with the anchor settled the counts could not match, "
                "for two reasons that have nothing to do with it: the published "
                "135 is a concatenation of OOS fold blocks (40 trading days IS "
                "/ 10 OOS, stride 10) and so covers only part of the window an "
                "admitted count here covers in full; and the script never reads "
                "the strategy YAML, so it ran a different operating point — see "
                "config_source_diff, which also lists the outcomes that were "
                "UNREACHABLE in it."
            ),
        },
        {
            "id": "L3",
            "item": "exit simulation is the harness's, not the live exit path",
            "value": {
                "source": (
                    "scripts/analysis/walkforward_setup_d_vwap_reversion.py"
                    "::_simulate_exit (lines 206-263), loaded by path and "
                    "called, not copied"
                ),
                "eod_hour": wf.EOD_HOUR,
                "eod_minute": wf.EOD_MINUTE,
                "strategy_yaml_eod_close_time": (
                    strategy.exit_config.eod_close_time.isoformat()
                ),
            },
            "note": (
                "The flag's notion of 'the position is still open' comes from "
                "that script: intrabar stop checked BEFORE target (conservative "
                "when both touch in one bar), then its own EOD_HOUR/EOD_MINUTE "
                "constants, then a day-close when the next bar is a new date, "
                "then end-of-series. It is NOT shared/strategy/exit/"
                "setup_target_exit.py (the live exit), and its EOD constants "
                "are the script's own, not the strategy YAML's eod_close_time "
                "— they happen to agree at 15:15 for this file, which the "
                "value above lets a reader check rather than assume. No PnL, "
                "slippage, commission or quantity is emitted; the flag answers "
                "only 'was the bar admitted'."
            ),
        },
        {
            "id": "L4",
            "item": "omitted bars mirror B1a",
            "value": ("tools/tos_cp3/produce_fields.py::_inputs_unusable, called here"),
            "note": (
                "A bar B1a declines to publish is declined here too, so the two "
                "files are line-for-line joinable on raw_event_id. Such a bar is "
                "still EVALUATED (the causal deques advance as in the legacy "
                "replay) and its legacy outcome is recorded under "
                "dataset.omitted_bars.outcome_counts, so nothing about it is "
                "lost — it simply has no line. A bar that FIRES while being "
                "unpublishable aborts the run instead (see the emitter's "
                "docstring)."
            ),
        },
        {
            "id": "L5",
            "item": "quantization",
            "value": {
                "price_magnitudes": {
                    "scale": "hundredths",
                    "multiplier": str(PRICE_SCALE),
                    "quantization": "half_up",
                },
                "signed_threshold_compared": {
                    "scale": "thousandths",
                    "multiplier": str(Z_SCALE),
                    "quantization": "truncate_toward_zero",
                },
                "signed_price_distances": {
                    "scale": "hundredths",
                    "multiplier": str(PRICE_SCALE),
                    "quantization": "truncate_toward_zero",
                },
                "per_field": "see the fields block for the exact pairing",
            },
            "note": (
                "B1a's rules, imported rather than restated "
                "(produce_fields.scaled_int_half_up / "
                "scaled_int_toward_zero), so a quantity present in both "
                "artifacts — z_x1000 above all — is comparable without a "
                "conversion. Toward-zero on a threshold-compared value means "
                "the published integer never reads as clearing a threshold the "
                "real value did not clear, at the cost of understating the "
                "magnitude by up to one unit."
            ),
        },
        {
            "id": "L6",
            "item": "an unevaluated trace key is ABSENT, not false",
            "value": "key omitted from decision.eval",
            "note": (
                "B1a maps an unevaluated gate to False because a Critical Input "
                "field must have a value (its D5, fail-closed). B2's trace is "
                "not a field set, and 'where did check() stop' is the question "
                "it exists to answer, so absence is preserved: a key missing "
                "from decision.eval was never evaluated, while a key present "
                "with null was evaluated and had no value. A reader must not "
                "read a missing hi_vol as hi_vol=false."
            ),
        },
        {
            "id": "L7",
            "item": "trend_filter_enabled",
            "value": cfg.trend_filter_enabled,
            "note": (
                "Inherited refusal: the window is resolved through B1a's "
                "load_strategy_inputs, which refuses while the trend gate is "
                "on. B2 could in principle emit the trend trace (trend_score / "
                "trend_ok / trend_override are projected), but a B2 run whose "
                "B1a counterpart cannot exist has nothing to be joined to, so "
                "the refusal is kept rather than relaxed. It ships off in the "
                "YAML, so the refusal is latent today."
            ),
        },
        {
            "id": "L8",
            "item": "no macro snapshot, no scheduled events",
            "value": {"macro_snapshot": None, "scheduled_events": []},
            "note": (
                "The replay is built macro- and event-free, exactly as "
                "collect_entries builds it (lines 160-167). Setup D reads "
                "neither (kickoff §1: 'macro, event and screener: none'), so "
                "this does not change check(); it is recorded because the "
                "orchestrator path around it does read them for other setups "
                "and a reader should not infer their presence."
            ),
        },
        {
            "id": "L9",
            "item": "min_confidence IS reproduced here (unlike B1a)",
            "value": cfg.min_confidence,
            "note": (
                "Not a difference from the legacy strategy but a difference "
                "from B1a, and B3 needs it: B2's FIRED is the complete legacy "
                "fire, confidence gate included (the trace carries "
                "confidence_x1000 and confidence_ok). B1a's published field set "
                "cannot express it at all (its D1 — the DSL has no arithmetic), "
                "so a tenant policy written on B1a's fields is a SUPERSET of "
                "'legacy fired'. A B3 mismatch on a bar whose B2 outcome is "
                "LOW_CONFIDENCE is therefore attributable to B1a D1, not to "
                "the policy."
            ),
        },
        {
            "id": "L10",
            "item": "the live post-exit re-entry guard is not applied",
            "value": {
                "config": "config/execution.yaml::entry_reentry_guard",
                "enabled_in_config": True,
                "scope": "symbol_strategy",
                "futures_override": (
                    "config/execution.yaml::entry_reentry_guard.futures — "
                    "default_cooldown_seconds 600, stop_loss "
                    "${FUTURES_REENTRY_STOP_LOSS_COOLDOWN_SECONDS:180}"
                ),
                "live_filter": (
                    "services/trading/orchestrator.py::"
                    "_filter_reentry_guarded_signals (defined line 5209, "
                    "applied line 5411)"
                ),
            },
            "note": (
                "Live, a signal is dropped when the same (symbol, strategy) "
                "exited inside a reason-dependent cooldown — a SECOND "
                "suppression on top of the single-position model, keyed on time "
                "since the last exit and on its reason (#601 fixed a dead-key "
                "mismatch that had made it silently inert). The walk-forward "
                "gate this flag replicates has no cooldown at all: it admits "
                "the next fire on the bar after the exit bar. So "
                "would_be_admitted_by_legacy_position_model is an UPPER BOUND "
                "on what paper would have entered, and a B3 comparison against "
                "a paper session must not read an admitted bar that paper "
                "skipped as a policy mismatch."
            ),
        },
        {
            "id": "L11",
            "item": "two more adapter-level reject paths are absent",
            "value": {
                "no_market_context": (
                    "shared/strategy/entry/setup_d_adapter.py lines 158-163 — "
                    "_build_market_context returns None, the setup is never "
                    "called, and the adapter publishes reject "
                    "'no_market_context'"
                ),
                "regime_gate_blocked": (
                    "same file lines 204-217 — _apply_regime_gate with a "
                    "GateConfig, publishing reject 'regime_gate_blocked'"
                ),
                "regime_gate_enabled_in_yaml": bool(
                    (strategy.entry_params.get("regime_gate") or {}).get(
                        "enabled", False
                    )
                ),
            },
            "note": (
                "L1 covers the direction blocks; these are the other two ways "
                "the live adapter returns None around a check() that fired or "
                "was never reached. 'no_market_context' has no counterpart here "
                "by construction — MarketContextReplay yields a context for "
                "every replayed bar or yields nothing, so B2's outcome set has "
                "no 'the inputs never assembled' member and a live session's "
                "no_market_context bars are simply ABSENT from a comparison "
                "rather than disagreeing with one. The regime gate ships "
                "disabled (value above), so it is latent, not active."
            ),
        },
        {
            "id": "L12",
            "item": "VWAP/ATR come from the replay, not the live indicator pipeline",
            "value": {
                "here": (
                    "shared/backtest/market_context_replay.py — session-anchored "
                    "VWAP and the trailing atr_partial(14) series, from bars at "
                    "or before the current index"
                ),
                "live": (
                    "the orchestrator's indicator pipeline fills "
                    "EntryContext.market_data; "
                    "setup_d_adapter.required_indicators is ['atr', 'vwap'] "
                    "(lines 153-156)"
                ),
            },
            "note": (
                "Both of Setup D's GATE references are causal and "
                "self-computed by the setup from the per-bar inputs — the "
                "parity argument the walk-forward script's own docstring makes "
                "('Look-ahead safety + live parity', lines 18-34: the high-vol "
                "reference comes from a trailing window of past ATRs, NOT the "
                "replay's full-series atr_90th_percentile, and the stall range "
                "from past closes, NOT last_15min_high/low which has no live "
                "producer). That argument covers the GATES. It does NOT say the "
                "VWAP and ATR-14 fed IN are bit-identical to the live "
                "pipeline's, which aggregates ticks through a different code "
                "path. So an equal decision here is evidence about the POLICY, "
                "not proof that live would have seen the same z — the same "
                "common-mode caveat ADR-002-018 §10 attaches to 'the same "
                "function call'."
            ),
        },
    ]


def _observed_range(
    records: list[DecisionRecord], published: str, from_trace: bool
) -> dict[str, Any]:
    """Observed value range for one published key, over the emitted lines.

    B1a's ``_observed_range`` can assume every field is present on every line
    with a non-null value. Neither holds here: a trace key is absent on bars
    that never reached it (declared difference L6) and the bracket integers are
    null off a FIRED bar. So ``present`` and ``null`` are reported alongside
    the range — a reader must be able to tell "never observed" from "observed
    as false".
    """
    values: list[Any] = []
    present = 0
    for record in records:
        source = record.eval_trace if from_trace else record.to_payload()["decision"]
        if published not in source:
            continue
        present += 1
        values.append(source[published])
    non_null = [value for value in values if value is not None]
    observed: dict[str, Any] = {
        "present": present,
        "null": len(values) - len(non_null),
    }
    if not non_null:
        return observed
    if isinstance(non_null[0], bool):
        true_count = sum(1 for value in non_null if value)
        observed["true"] = true_count
        observed["false"] = len(non_null) - true_count
        return observed
    if isinstance(non_null[0], str):
        observed["distinct"] = sorted({str(value) for value in non_null})
        return observed
    observed["min"] = min(int(value) for value in non_null)
    observed["max"] = max(int(value) for value in non_null)
    return observed


def _field_lineage(records: list[DecisionRecord]) -> dict[str, dict[str, Any]]:
    """Per-key provenance for everything this artifact publishes as a number.

    Same ADR-002-018 §10 derived-Critical-Input shape B1a's ``fields`` block
    uses — unit, scale token, multiplier string, sign, type, quantization,
    parents, and the range actually observed in this run — so a reader of
    either sidecar reconstructs a value the same way. B1a's block describes
    fields derived from bars; this one describes a projection of the legacy
    setup's own trace, so every ``parents`` entry names the ``last_eval`` key
    (or the ``Signal`` attribute) the value came from, and nothing here is a
    second computation of anything.
    """
    spec: dict[str, dict[str, Any]] = {}
    for key, published, projection in EVAL_PROJECTION:
        entry = dict(PROJECTION_ENCODING[projection])
        entry["unit"] = EVAL_UNITS[key]
        entry["parents"] = [f"last_eval:{key}"]
        entry["source"] = (
            "SetupDVWAPReversion.check() wrote this key on the branch it took; "
            "this tool projects it and recomputes nothing"
        )
        entry["range_observed"] = _observed_range(records, published, from_trace=True)
        spec[published] = entry
    for published, projection, unit, parent in BRACKET_PROJECTION:
        entry = dict(PROJECTION_ENCODING[projection])
        entry["unit"] = unit
        entry["parents"] = [parent]
        entry["source"] = "the fired Signal's own value; null on every non-FIRED bar"
        entry["range_observed"] = _observed_range(records, published, from_trace=False)
        spec[published] = entry
    return spec


def build_lineage(
    *,
    emitted: EmittedDecisions,
    jsonl_bytes: bytes,
    symbol: str,
    strategy: StrategyInputs,
    contract_spec: ContractSpec,
    anchor: OpenAnchor,
    data_root: Path,
    requested_start: date,
    requested_end: date,
    min_bars_per_day: int,
    bars_loaded: int,
    bars_after_density_gate: int,
    warmup_skipped: int,
    first_session_dropped: int,
    input_files: list[InputFile],
) -> dict[str, Any]:
    """Assemble the lineage sidecar (ADR-002-018 §10 shape, as B1a uses it).

    Deliberately carries **no run timestamp and no duration**: two runs over the
    same inputs must produce identical bytes, so a changed lineage means changed
    inputs, parameters or code — never merely a re-run.

    The loaded → gated → replayed → emitted chain is ASSERTED here, not merely
    reported: a count that does not reconcile aborts the run.
    """
    records = emitted.records
    session_dates = sorted({record.bar_kst.date() for record in records})
    outcome_counts = Counter(record.outcome for record in records)
    omitted_outcome_counts = Counter(outcome for _, _, outcome in emitted.omitted)
    admitted = sum(
        1 for record in records if record.would_be_admitted_by_legacy_position_model
    )

    dropped_before_replay = warmup_skipped + first_session_dropped
    if bars_after_density_gate - dropped_before_replay != emitted.bars_replayed:
        raise EmitLegacyDecisionsError(
            "bar accounting does not reconcile: "
            f"{bars_after_density_gate} after the density gate minus "
            f"{dropped_before_replay} dropped before replay != "
            f"{emitted.bars_replayed} replayed"
        )
    if emitted.bars_replayed - len(emitted.omitted) != len(records):
        raise EmitLegacyDecisionsError(
            f"{emitted.bars_replayed} replayed minus {len(emitted.omitted)} "
            f"omitted != {len(records)} emitted"
        )
    if sum(outcome_counts.values()) != len(records):
        raise EmitLegacyDecisionsError(
            f"outcome counts sum to {sum(outcome_counts.values())} but "
            f"{len(records)} lines were emitted"
        )
    unknown_outcomes = sorted(set(outcome_counts) - set(OUTCOMES))
    if unknown_outcomes:
        raise EmitLegacyDecisionsError(
            f"emitted outcomes outside the closed set: {unknown_outcomes}"
        )
    if admitted != len(emitted.admitted_indices):
        raise EmitLegacyDecisionsError(
            f"{admitted} emitted lines are admitted but the position model "
            f"admitted {len(emitted.admitted_indices)} bars — an admitted bar "
            "was omitted from the output"
        )
    if admitted > outcome_counts.get(OUTCOME_FIRED, 0):
        raise EmitLegacyDecisionsError(
            f"{admitted} admitted bars exceed {outcome_counts.get(OUTCOME_FIRED, 0)} "
            f"{OUTCOME_FIRED} bars"
        )
    if bars_loaded > 0 and not input_files:
        raise EmitLegacyDecisionsError(
            f"{bars_loaded} bars were loaded but no Parquet partition was found "
            f"under {data_root} for {symbol} in "
            f"{requested_start}..{requested_end} — the lineage would claim an "
            "input list it does not have"
        )

    return {
        "lineage_schema_version": LINEAGE_SCHEMA_VERSION,
        "tool": {
            "name": "tools/tos_cp3/emit_legacy_decisions.py",
            "version": f"tos_cp3/{TOS_CP3_VERSION}",
            "source_id": SOURCE_ID,
            "git": _git_identity(REPO_ROOT),
            "runtime": _runtime_versions(),
        },
        "parents": {
            "legacy_setup": str(LEGACY_SETUP_SOURCE.relative_to(REPO_ROOT)),
            "legacy_setup_sha256": hashlib.sha256(
                LEGACY_SETUP_SOURCE.read_bytes()
            ).hexdigest(),
            "position_model": str(WALKFORWARD_SCRIPT.relative_to(REPO_ROOT)),
            "position_model_sha256": hashlib.sha256(
                WALKFORWARD_SCRIPT.read_bytes()
            ).hexdigest(),
            "window_loader": "tools/tos_cp3/produce_fields.py::load_window",
            "window_loader_sha256": hashlib.sha256(
                (REPO_ROOT / "tools" / "tos_cp3" / "produce_fields.py").read_bytes()
            ).hexdigest(),
            "strategy_yaml": str(strategy.path),
            "strategy_yaml_sha256": strategy.sha256,
        },
        "common_mode": (
            "This is NOT independent corroboration of the band math. Both sides "
            "of the CP-3 comparison read ONE implementation — "
            "shared/decision/setups/vwap_reversion.py — which this emitter "
            "drives bar by bar, reading the Signal it returns plus "
            "last_reject_reason and last_eval rather than restating any "
            "threshold. A defect in that implementation appears on both sides "
            "identically (ADR-002-018 §10)."
        ),
        "join": {
            "key": "raw_event_id",
            "counterpart": "tools/tos_cp3/produce_fields.py (B1a) fields.jsonl",
            "key_derivation": (
                "produce_fields.derive_raw_event_id / derive_as_of_ms — ONE "
                "definition, imported by both sides"
            ),
            "omission_predicate": "produce_fields._inputs_unusable",
            # The key encodes symbol + timeframe + bar instant and NOTHING about
            # how the bar was reduced to fields. Two runs of the same window at
            # different anchors therefore join PERFECTLY and diff garbage: every
            # entry_window / eod / minutes_since_open on one side is shifted.
            # These four values are the window identity a consumer must compare
            # BEFORE joining.
            "window_identity": {
                "symbol": symbol,
                "market_open_kst": anchor.kst,
                "market_open_source": anchor.source,
                "min_bars_per_day": min_bars_per_day,
                "window_start": requested_start.isoformat(),
                "window_end": requested_end.isoformat(),
            },
            "b3_contract": (
                "B3 MUST REFUSE a (B1a, B2) pair whose join.window_identity "
                "blocks differ in any field, rather than join on raw_event_id "
                "and report the difference as a decision mismatch. The key "
                "carries no anchor, so a mismatched pair is not detectable from "
                "the lines themselves — only from these blocks. B3 implements "
                "the refusal; this producer's job is to record the identity so "
                "the refusal is possible."
            ),
            "shared_quantity": (
                "decision.eval.z_x1000 uses B1a's scale and quantization "
                "exactly, so where present it is directly comparable to B1a's "
                "z_x1000. It is absent on bars where check() returned before "
                "step 4, whereas B1a publishes it on every emitted bar."
            ),
        },
        "dataset": {
            "symbol": symbol,
            "instrument": symbol,
            "asset_class": strategy.asset_class,
            "timeframe": "minute",
            "data_root": str(data_root),
            "requested_start": requested_start.isoformat(),
            "requested_end": requested_end.isoformat(),
            "min_bars_per_day": min_bars_per_day,
            "min_volume": 0,
            "bars_loaded": bars_loaded,
            "bars_after_density_gate": bars_after_density_gate,
            "replay_warmup_bars_skipped": warmup_skipped,
            "first_session_bars_dropped_no_prior_close": first_session_dropped,
            "bars_replayed": emitted.bars_replayed,
            "bars_emitted": len(records),
            "reconciliation": {
                "asserted": (
                    "bars_after_density_gate - (replay_warmup_bars_skipped + "
                    "first_session_bars_dropped_no_prior_close) == "
                    "bars_replayed; bars_replayed - omitted_bars.count == "
                    "bars_emitted; sum(outcomes.counts) == bars_emitted"
                ),
                "bars_dropped_before_replay": dropped_before_replay,
            },
            "omitted_bars": {
                "count": len(emitted.omitted),
                "reasons": sorted({reason for _, reason, _ in emitted.omitted}),
                "outcome_counts": dict(sorted(omitted_outcome_counts.items())),
                "raw_event_ids": [
                    raw_event_id
                    for raw_event_id, _, _ in emitted.omitted[:OMITTED_ID_LIST_CAP]
                ],
                "raw_event_ids_truncated": len(emitted.omitted) > OMITTED_ID_LIST_CAP,
            },
            "session_dates": len(session_dates),
            "first_session_date": session_dates[0].isoformat(),
            "last_session_date": session_dates[-1].isoformat(),
            "first_raw_event_id": records[0].raw_event_id,
            "last_raw_event_id": records[-1].raw_event_id,
            "first_as_of_ms": records[0].as_of_ms,
            "last_as_of_ms": records[-1].as_of_ms,
            "input_files": [
                {
                    "path": item.path,
                    "sha256": item.sha256,
                    "size_bytes": item.size_bytes,
                }
                for item in input_files
            ],
            "input_file_count": len(input_files),
        },
        "outcomes": {
            "closed_set": list(OUTCOMES),
            "closed_set_source": (
                "every self._reject(...) branch of "
                "SetupDVWAPReversion.check() plus FIRED. An unknown reason "
                "aborts the run (outcome_for_reject_reason); the mirror is "
                "pinned against that module's AST by "
                "tests/tools/test_cp3_emit_legacy_decisions.py"
            ),
            "counts": dict(sorted(outcome_counts.items())),
            "counts_unobserved": [
                outcome for outcome in OUTCOMES if outcome not in outcome_counts
            ],
        },
        "position_model": {
            "flag": "would_be_admitted_by_legacy_position_model",
            "source": (
                "scripts/analysis/walkforward_setup_d_vwap_reversion.py"
                "::collect_entries (lines 150-203) — one open position, "
                "last_exit_idx, evaluate-and-discard; exits by its own "
                "_simulate_exit (lines 206-263)"
            ),
            "admitted": admitted,
            "fired": outcome_counts.get(OUTCOME_FIRED, 0),
            "fired_but_inside_an_open_position": (
                outcome_counts.get(OUTCOME_FIRED, 0) - admitted
            ),
            "note": (
                "'Rule fired' and 'legacy would have entered' are different "
                "questions; both are answered per line. See declared "
                "differences L2 (anchor) and L3 (exit simulation) before "
                "comparing the admitted count to a published trade count."
            ),
        },
        "strategy": {
            "path": str(strategy.path),
            "sha256": strategy.sha256,
            "entry_type": SetupDVWAPReversion.REGISTRY_NAME,
            "entry_params_yaml": strategy.entry_params,
            "exit_params_yaml": strategy.exit_params,
            "entry_params_used": strategy.entry_config.model_dump(mode="json"),
            "market_open_kst": anchor.kst,
            "market_open_source": anchor.source,
            "contract_spec": {
                "name": contract_spec.name,
                "multiplier_krw_per_point": contract_spec.multiplier_krw_per_point,
                "tick_size_points": contract_spec.tick_size_points,
                "tick_value_krw": contract_spec.tick_value_krw,
                "source": "config/execution.yaml::futures_contract_spec",
            },
        },
        "encoding": {
            "line_keys": list(LINE_KEYS),
            "no_floats_in_payload": True,
            "payload_keys": [
                "outcome",
                "direction",
                "confidence_x1000",
                "entry_x100",
                "stop_x100",
                "target_x100",
                "would_be_admitted_by_legacy_position_model",
                "eval",
            ],
            "eval_key_order": [published for _, published, _ in EVAL_PROJECTION],
            "eval_projections": {
                published: projection for _, published, projection in EVAL_PROJECTION
            },
            "eval_absent_key_semantics": (
                "a key missing from decision.eval was NEVER EVALUATED on that "
                "bar (check() returned before the branch that records it); a "
                "key present with null was evaluated and had no value. See "
                "declared difference L6"
            ),
            "bracket_semantics": (
                "entry_x100 / stop_x100 / target_x100 / confidence_x1000 are "
                "the fired Signal's own values and are null on every "
                "non-FIRED bar. direction is the fade direction check() had "
                "decided by step 4, so it is non-null on bars rejected AFTER "
                "the extension trigger (the trend, stall, reversal and "
                "confidence branches) as well as on FIRED bars"
            ),
            "as_of_ms_semantics": (
                "epoch milliseconds of the bar's labelled KST minute — "
                "produce_fields.derive_as_of_ms, the same derivation B1a uses"
            ),
            "published_bools_are_authoritative": (
                "A published bool (stall_ok, hi_vol, reversal_ok, extreme, "
                "entry_window, confidence_ok, trend_ok) is the branch check() "
                "ACTUALLY took. Recomputing one from the published integers can "
                "disagree at a boundary, because the operands are quantized by "
                "DIFFERENT rules: stall_distance_x100 truncates toward zero "
                "while stall_buffer_x100 rounds half-up, so a bar whose real "
                "stall_distance only just exceeds its buffer can publish "
                "stall_distance_x100 <= stall_buffer_x100 while stall_ok is "
                "false (and the symmetric case for z_x1000 against a threshold "
                "a reader rounds the other way). Where the pair and the bool "
                "disagree, the BOOL is the decision; the integers are evidence "
                "about magnitude, not a re-derivation of the gate."
            ),
        },
        "config_source_diff": {
            "this_run": str(strategy.path),
            "harness": (
                "scripts/analysis/walkforward_setup_d_vwap_reversion.py lines "
                "441-447 — SetupDConfig(trend_* only); every other field takes "
                "its dataclass default and the strategy YAML is never read"
            ),
            "differs": config_source_diff(strategy),
            "outcomes_unreachable_under_harness_defaults": (
                outcomes_unreachable_under_harness_defaults()
            ),
            "note": (
                "Machine-computed against SetupDConfig(), so it cannot describe "
                "a default that has since moved. Every field listed under "
                "'differs' is a value the published walk-forward did NOT use, "
                "and the outcomes listed above were UNREACHABLE in it — not "
                "rare, but dead, because the gates that produce them are "
                "config-gated in check(). Read this block before comparing any "
                "count here to a published number (declared difference L2)."
            ),
        },
        "fields": _field_lineage(records),
        "declared_differences": _declared_differences(strategy, anchor),
        "output": {
            "jsonl": DECISIONS_FILENAME,
            "jsonl_sha256": hashlib.sha256(jsonl_bytes).hexdigest(),
            "jsonl_bytes": len(jsonl_bytes),
            "jsonl_lines": len(records),
        },
    }


# ---------------------------------------------------------------------------
# The legacy reject/trace mirrors, read back out of the legacy source
# ---------------------------------------------------------------------------


def legacy_reject_prefixes(source: Path = LEGACY_SETUP_SOURCE) -> list[str]:
    """Every literal prefix a ``self._reject(...)`` call in *source* can produce.

    Walks the AST rather than the text so a reject branch cannot hide behind
    formatting. For a plain string argument the whole string is the prefix; for
    an f-string it is the leading constant run, up to the first interpolation
    (adjacent string literals are already concatenated by the parser, so
    ``"a(" f"b={x}"`` yields ``a(b=``).

    Used by the test suite to pin :data:`REJECT_OUTCOME_RULES` against the
    legacy source, and kept here so the walk and the table it checks live
    together.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    prefixes: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "_reject"):
            continue
        if not node.args:
            raise EmitLegacyDecisionsError(
                f"{source}: a _reject() call has no argument at line {node.lineno}"
            )
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            prefixes.append(arg.value)
            continue
        if isinstance(arg, ast.JoinedStr):
            head: list[str] = []
            for part in arg.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    head.append(part.value)
                else:
                    break
            if not head:
                raise EmitLegacyDecisionsError(
                    f"{source}: the _reject() f-string at line {node.lineno} "
                    "starts with an interpolation, so it has no literal prefix "
                    "to classify on"
                )
            prefixes.append("".join(head))
            continue
        raise EmitLegacyDecisionsError(
            f"{source}: the _reject() argument at line {node.lineno} is a "
            f"{type(arg).__name__}, which has no literal prefix"
        )
    return sorted(set(prefixes))


def legacy_trace_keys(source: Path = LEGACY_SETUP_SOURCE) -> list[str]:
    """Every key assigned into the ``ev`` trace dict in ``check()``.

    ``ev`` is the local alias :meth:`SetupDVWAPReversion.check` binds to
    ``self.last_eval`` before writing to it, so ``ev["k"] = ...`` is today's
    complete set of trace keys. Walking the AST is what lets the test suite pin
    :data:`EVAL_PROJECTION` against the source instead of against a hand-kept
    list.

    **What this walk does and does not see.** It matches only ``ast.Assign``
    nodes whose target is ``ev[<string literal>]``. It does NOT see
    ``ev.update({...})``, ``ev |= {...}``, an augmented assignment, a
    non-literal key, or a write through ``self.last_eval[...]`` instead of the
    alias — a key added in any of those forms would leave this pin green. That
    is why the pin is a **second** guard and not the only one:
    :func:`project_eval` refuses an unknown key at RUN time, so such a key
    aborts the run on the first bar that records it rather than being dropped.
    A non-literal ``ev[...]`` key raises here instead of being skipped, so the
    one form that would make the static set unknowable is loud.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    keys: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Subscript):
                continue
            if not (isinstance(target.value, ast.Name) and target.value.id == "ev"):
                continue
            index = target.slice
            if isinstance(index, ast.Constant) and isinstance(index.value, str):
                keys.append(index.value)
            else:
                raise EmitLegacyDecisionsError(
                    f"{source}: ev[...] is assigned with a non-literal key at "
                    f"line {node.lineno}; the trace key set cannot be read "
                    "statically"
                )
    return sorted(set(keys))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunResult:
    """What a completed run wrote, for the CLI summary and for tests."""

    records: list[DecisionRecord]
    jsonl_bytes: bytes
    lineage: dict[str, Any]
    lineage_bytes: bytes
    jsonl_path: Path
    lineage_path: Path


def run(
    *,
    data_root: Path,
    symbol: str,
    start: date,
    end: date,
    strategy_yaml: Path,
    out_dir: Path,
    min_bars_per_day: int = DEFAULT_MIN_BARS_PER_DAY,
    market_open: str = "auto",
) -> RunResult:
    """Emit the decision JSONL and lineage sidecar for one dataset window."""
    window = load_window(
        data_root=data_root,
        symbol=symbol,
        start=start,
        end=end,
        strategy_yaml=strategy_yaml,
        min_bars_per_day=min_bars_per_day,
        market_open=market_open,
    )
    warmup_skipped, first_session_dropped = _bar_accounting(window.df)

    emitted = emit_decisions(
        window.df,
        symbol=symbol,
        strategy=window.strategy,
        contract_spec=window.contract_spec,
        anchor=window.anchor,
    )
    jsonl_bytes = render_jsonl(emitted.records)
    lineage = build_lineage(
        emitted=emitted,
        jsonl_bytes=jsonl_bytes,
        symbol=symbol,
        strategy=window.strategy,
        contract_spec=window.contract_spec,
        anchor=window.anchor,
        data_root=data_root,
        requested_start=start,
        requested_end=end,
        min_bars_per_day=min_bars_per_day,
        bars_loaded=window.bars_loaded,
        bars_after_density_gate=int(len(window.df)),
        warmup_skipped=warmup_skipped,
        first_session_dropped=first_session_dropped,
        input_files=window.input_files,
    )
    lineage_bytes = render_lineage(lineage)

    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / DECISIONS_FILENAME
    lineage_path = out_dir / LINEAGE_FILENAME
    jsonl_path.write_bytes(jsonl_bytes)
    lineage_path.write_bytes(lineage_bytes)
    return RunResult(
        records=emitted.records,
        jsonl_bytes=jsonl_bytes,
        lineage=lineage,
        lineage_bytes=lineage_bytes,
        jsonl_path=jsonl_path,
        lineage_path=lineage_path,
    )


def build_parser() -> argparse.ArgumentParser:
    """CLI mirroring B1a's, minus its ``--measure-d7`` side errand."""
    parser = argparse.ArgumentParser(
        prog="emit_legacy_decisions",
        description=(
            "CP-3 B2 — replay the same bars as B1a through the legacy Setup D "
            "path and emit a per-bar candidate/reject JSONL plus a lineage "
            "sidecar."
        ),
    )
    parser.add_argument(
        "--data-root",
        required=True,
        type=Path,
        help=(
            "Market-data Parquet root (e.g. "
            "/home/deploy/project/kis_unified_sts/data/market). Required: the "
            "tree is gitignored and exists only in the primary checkout."
        ),
    )
    parser.add_argument(
        "--symbol", required=True, help="Instrument code, e.g. 101S6000"
    )
    parser.add_argument(
        "--start", required=True, type=date.fromisoformat, help="Inclusive KST date"
    )
    parser.add_argument(
        "--end", required=True, type=date.fromisoformat, help="Inclusive KST date"
    )
    parser.add_argument(
        "--strategy-yaml",
        required=True,
        type=Path,
        help="Setup D strategy YAML — the source of every threshold and window",
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output directory for the two artifacts",
    )
    parser.add_argument(
        "--min-bars-per-day",
        type=int,
        default=DEFAULT_MIN_BARS_PER_DAY,
        help=(
            "Drop sessions with fewer bars than this before replay (default "
            f"{DEFAULT_MIN_BARS_PER_DAY}, matching B1a and the walk-forward "
            "script; 0 is the explicit opt-out). Must match the B1a run this "
            "artifact is joined to."
        ),
    )
    parser.add_argument(
        "--market-open",
        default="auto",
        help=(
            "Futures open anchor as HH:MM, or 'auto' (default) for B1a's era "
            f"rule: {PRE_CUTOVER_OPEN[0]:02d}:{PRE_CUTOVER_OPEN[1]:02d} for "
            f"data before {OPEN_ANCHOR_CUTOVER}, else "
            "config/market_schedule.yaml. A window straddling the cutover is "
            "refused. Must match the B1a run this artifact is joined to."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run(
            data_root=args.data_root,
            symbol=args.symbol,
            start=args.start,
            end=args.end,
            strategy_yaml=args.strategy_yaml,
            out_dir=args.out,
            min_bars_per_day=args.min_bars_per_day,
            market_open=args.market_open,
        )
    except (EmitLegacyDecisionsError, ProduceFieldsError) as exc:
        print(f"emit_legacy_decisions: {exc}", file=sys.stderr)
        return 2

    lineage = result.lineage
    dataset = lineage["dataset"]
    print(f"wrote {result.jsonl_path} ({lineage['output']['jsonl_lines']} lines)")
    print(f"wrote {result.lineage_path}")
    print(f"jsonl sha256: {lineage['output']['jsonl_sha256']}")
    print(
        "bars loaded/gated/replayed/emitted/omitted: "
        f"{dataset['bars_loaded']}/{dataset['bars_after_density_gate']}/"
        f"{dataset['bars_replayed']}/{dataset['bars_emitted']}/"
        f"{dataset['omitted_bars']['count']}"
    )
    print(
        "open anchor: "
        f"{lineage['strategy']['market_open_kst']} "
        f"({lineage['strategy']['market_open_source']})"
    )
    print("outcome counts:")
    for outcome, count in lineage["outcomes"]["counts"].items():
        print(f"  {outcome}: {count}")
    unobserved = lineage["outcomes"]["counts_unobserved"]
    if unobserved:
        print(f"  (not observed: {', '.join(unobserved)})")
    position_model = lineage["position_model"]
    print(
        "position model admitted/fired: "
        f"{position_model['admitted']}/{position_model['fired']} "
        f"({position_model['fired_but_inside_an_open_position']} fired inside "
        "an open position)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
