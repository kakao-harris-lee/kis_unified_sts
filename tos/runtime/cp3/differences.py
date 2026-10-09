"""The intended differences this slice carries, each with its approval basis.

**Data, in a module of its own.** This is a 150-line literal; inline inside
:func:`cp3.lineage.build_lineage` it was most of why that function stood at 333
lines against the 100-line function cap ``config/tos_size_budget.yaml`` now
enforces over this tree, and wrapping it in a function only moved the violation.
A module-level constant is what it actually is — and it is also the part a
reviewer reads on its own, without the block-assembly code around it.

Nine entries:

* **B1b-D1..D6** — this slice's own structural differences from the legacy
  runtime (the one-order cap, the band-form exit, already-admitted field values,
  the injected time/session stance, one-side-only, no mandated ScenarioId).
* **B1b-D7** — the exposure-precondition gap the 2026-10-08 independent review
  found unrecorded: the DSL has no position operand, so FLAT is proposed on every
  reverted/EOD bar regardless of exposure.
* **B1b-D8 / B1b-D9** — the two the **operator** approved on 2026-10-07
  (kickoff §4 결정 5: delete ``short_blocked_regimes``; 결정 6: the 1.5x ATR stop
  is out of first-slice scope). They were approved as *intended differences* and
  therefore belong in any artifact the parity report is built from; the review
  found them missing from this block.

**Direction (2026-10-09).** B1b-D5 is the declared difference that *names a
direction*, so this is a function of the deployment's direction rather than a
constant: a SHORT render whose lineage says "LONG side only" would be a
difference block describing a run that did not happen. The direction is the one
``cp3.strategy.load_strategy_content`` derives from the authored ACTION targets
(``_single_direction``) — the file, never a caller's flag — and the one-side
comparison is rendered from the authored compare + its resolved binding, so the
``(z_x1000 <= -1800)`` phrase cannot go stale against the file it describes.

Firewall: stdlib only. No ``tos.*`` import is needed — this is prose and ids.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

__all__ = ["declared_difference_ids", "declared_differences"]

#: The two tokens ``_single_direction`` can return. Named here because this
#: module renders the mirror of whichever one it is handed.
_DIRECTIONS = ("LONG", "SHORT")

#: ``LONG -> SHORT`` and back: B1b-D5's note names the half this run does NOT
#: render, which is the half a separate render covers.
_OTHER_SIDE: Mapping[str, str] = {"LONG": "SHORT", "SHORT": "LONG"}


#: The eight direction-INDEPENDENT entries, split around B1b-D5 so the id
#: order stays explicit at the one place that assembles them. Module-level
#: data rather than a function body: it IS data, and a 170-line function
#: breaks config/tos_size_budget.yaml's 100-line cap over this tree.
_D1_TO_D4: Sequence[Mapping[str, Any]] = [
    {
        "id": "B1b-D1",
        "item": "one order per scope per run (B4)",
        "note": (
            "tos.backtest holds at most ONE order per scope for the "
            "whole run — the provisional projection has no release path "
            "(state.py:22) — so the FIRST firing is realized and every "
            "later firing is an exact capacity denial "
            "(AT_MOST_ONE_EXPOSURE_HELD), recorded as "
            "capacity_denied=true. kickoff §3 B4 disposes this as "
            "'체결 비교 포기': the comparison is decision/intent level, "
            "never fill-for-fill. The denials are the seal FIRING, not "
            "run failures. ⚠ The single order is spent by the FIRST "
            "firing(s) of ANY rule — an exit FLAT on an early bar takes "
            "it just as readily as an entry — so counts.realized_orders "
            "names which bar(s) actually reached the send boundary; "
            "handoffs=1 beside ACTION=N must NOT be read as 'an entry "
            "was realized'. The budget is the INJECTED "
            "max_unresolved_send_per_scope, never a hardcoded 1 — but "
            "MEASURED (bounds 1/2/3, "
            "tests/test_cp3_review_dispositions.py): raising that "
            "bound does NOT raise the realized-order count, which "
            "stays 1. The binding constraint is the provisional "
            "reservation projection's absent release path, which "
            "tos.backtest declares itself; the bound only moves "
            "where the flow halts (LEDGER_VERIFICATION at 1, "
            "ATOMIC_COMMIT at 2+). So --max-unresolved-send-per-scope "
            "cannot buy a second fill out of this harness."
        ),
    },
    {
        "id": "B1b-D2",
        "item": "vwap_reverted is the band form (B1a D3)",
        "note": (
            "the exit gate reads B1a's `vwap_reverted` = abs(z) <= 0.2, "
            "where 0.2 comes from "
            "strategy.entry.params.reversal_confirm_atr_mult as a "
            "FALLBACK: config/strategies/futures/"
            "setup_d_vwap_reversion.yaml declares no "
            "vwap_revert_band_atr_mult. The legacy exit is therefore not "
            "reproduced from a declared band of its own; B1a's lineage "
            "records the same difference on its side as **D3**. (The "
            "previous revision cited 'B1a D7' — wrong entry: D7 is "
            "about the measured D7 generator and its own note says its "
            "COUNTS must not be read as the band's error bar. The band "
            "form itself is D3.)"
        ),
    },
    {
        "id": "B1b-D3",
        "item": "fields enter as already-admitted values",
        "note": (
            "the backtest harness exposes no critical_input_policy seam: "
            "ContextValueView.values is 'VALID by construction' because "
            "the tos.marketfeed producer applied the gate, and "
            "ContextValue carries no field_state. B1b publishes B1a's "
            "fields directly and RECORDS each field's five governed "
            "values (versions.field_policy) instead of enforcing them. "
            "max_age_ms has no consumer here — freshness is judged from "
            "versions.injected_time_bounds."
        ),
    },
    {
        "id": "B1b-D4",
        "item": "injected time/session stance",
        "note": (
            "session phase CONTINUOUS / is_open=true and the trustworthy-"
            "time bounds are INJECTED, not derived from the bars: the "
            "kernel reads no market hours and session_token stays "
            "opaque. The capsule's session_and_tradability slot is left "
            "EMPTY on purpose (kickoff §2 ①: entry_window/eod are "
            "strategy gates, not tradability evidence)."
        ),
    },
]

#: The four that follow B1b-D5, same discipline.
_D6_TO_D9: Sequence[Mapping[str, Any]] = [
    {
        "id": "B1b-D6",
        "item": "no mandated ScenarioId",
        "note": (
            "scenario_id is null: this replay is not one of design #33 "
            "§5.1's seven mandated rows, and borrowing a row's id would "
            "claim a scenario it does not realize."
        ),
    },
    {
        "id": "B1b-D7",
        "item": "FLAT rules carry no exposure precondition",
        "note": (
            "the DSL environment exposes no position/exposure operand at "
            "all (the Capsule has no holdings slot and resolved_values "
            "carries only B1a's 15 fields), so R2/R3 propose FLAT on "
            "EVERY reverted/EOD bar regardless of whether anything is "
            "open — this run emits 3,353 FLATs with no position ever "
            "opened. The legacy exit is position-scoped: it fires for an "
            "open Setup D position and not otherwise. A decision-level "
            "comparison must therefore compare FLAT INTENT, never FLAT "
            "count, and B3's diff has to scope the legacy side to bars "
            "where a position was held. Closing this inside the DSL "
            "would need an exposure Critical Input, which is a kernel/"
            "policy change and out of CP-3 scope."
        ),
    },
    {
        "id": "B1b-D8",
        "item": "short_blocked_regimes deleted (operator 결정 5)",
        "note": (
            "the legacy Setup D YAML carries "
            "short_blocked_regimes: [BULL_STRONG] (133행), the one line "
            "that keeps the adapter reading an LLM/metadata regime "
            "label. kickoff §4 결정 5 DELETES it and registers the "
            "deletion as an intended difference (operator-approved "
            "2026-10-07): TOS has no regime input and the rule is "
            "symmetric, but that guard was what blocked the dominant "
            "trend-day failure, so the 2026-07-07 exposure (13 "
            "consecutive counter-trend longs, -8.4 pt) is open on BOTH "
            "sides now. ⚠ MEASURED 2026-10-09, and it corrects the "
            "previous revision's forward-looking claim that 'the "
            "comparison will meet it': this guard CANNOT produce a "
            "decision-level difference in a B1a/B2/B1b comparison, in "
            "EITHER direction. It is applied by "
            "shared/strategy/entry/setup_d_adapter.py (the "
            "`if cfg.long_blocked_regimes or cfg.short_blocked_regimes` "
            "branch) AFTER `self._setup.check(mc)` has already returned a "
            "signal, and B2 drives `SetupDVWAPReversion.check()` itself — "
            "never the adapter — so the legacy side of this comparison "
            "never applied the block either. The two sides are therefore "
            "EQUALLY unguarded here, and the item absorbs zero bars. The "
            "difference is registered because it is real for the "
            "DEPLOYMENT (paper/live runs the adapter), and B3's "
            "summary.json counts it at zero rather than omitting it — a "
            "zero means this comparison exercised nothing the difference "
            "explains, not that the difference is absent. Closing it at "
            "the decision level would need B2 to publish the adapter's "
            "verdict, which is a B2 change."
        ),
    },
    {
        "id": "B1b-D9",
        "item": "ATR stop (1.5x) out of first-slice scope (operator 결정 6)",
        "note": (
            "kickoff §4 결정 6 (operator-approved 2026-10-07) fixes the "
            "first slice's exits at vwap_reverted FLAT + eod FLAT and "
            "leaves the legacy 1.5x ATR stop OUT, with the approval "
            "rationale recorded: the DSL has no entry price and no "
            "numeric Proposal slot, and protective classification is "
            "PAC's to make, so a strategy cannot declare its own stop. "
            "Mapping it onto a TOS protection lane (aggregate risk / "
            "safety mesh) is a separate design. Consequence for this "
            "artifact: a legacy trade that the stop closed has no "
            "counterpart here, and the diff must not read that as the "
            "policy disagreeing."
        ),
    },
]


def _d5(*, direction: str, entry_comparison: str) -> dict[str, Any]:
    """The one entry that names a direction — rendered, never a constant."""
    return {
        "id": "B1b-D5",
        "item": f"{direction} side only",
        "note": (
            "the DSL has no abs() (DSL-G1) and direction is a "
            "per-deployment fact, so the entry rule compares one side "
            f"({entry_comparison}). The legacy entry fires on abs(z) >= "
            f"1.8, i.e. BOTH sides; the {_OTHER_SIDE[direction]} half is "
            "a separate render "
            "with its own strategy file (kickoff §4 결정 4). Expect this "
            "run's ACTION/firing count to be a SUBSET of B1a's "
            "entry-AND bar count for that reason."
        ),
    }


def _entries(*, direction: str, entry_comparison: str) -> list[dict[str, Any]]:
    """The nine entries, in id order, rendered for *direction*."""
    return [
        *(dict(item) for item in _D1_TO_D4),
        _d5(direction=direction, entry_comparison=entry_comparison),
        *(dict(item) for item in _D6_TO_D9),
    ]


def declared_differences(
    *, direction: str, entry_comparison: str
) -> Sequence[Mapping[str, Any]]:
    """The nine declared differences, rendered for this deployment's direction.

    Args:
        direction: ``"LONG"`` or ``"SHORT"`` — the one
            :func:`cp3.strategy._single_direction` read off the authored ACTION
            targets. A caller cannot pass a third token: an unknown direction
            is refused rather than rendered, because B1b-D5's whole content is
            "which side this run compares" and a block that names a side the
            run did not take is worse than no block.
        entry_comparison: The authored one-side comparison with its resolved
            binding, e.g. ``"z_x1000 <= -1800"``. Rendered by
            :func:`cp3.lineage` from the strategy file itself so the phrase
            cannot drift from the file it describes.

    Returns:
        The entries, in id order.

    Raises:
        ValueError: ``direction`` is not one of :data:`_DIRECTIONS`.
    """
    if direction not in _DIRECTIONS:
        raise ValueError(
            f"direction {direction!r} is not one of {_DIRECTIONS} — the "
            "declared-difference block names the side this run compared and "
            "cannot be rendered for an unknown one"
        )
    return _entries(direction=direction, entry_comparison=entry_comparison)


def declared_difference_ids() -> tuple[str, ...]:
    """The declared ids, in order — the set a test pins.

    Direction-invariant by construction: both renders carry the same nine ids
    and differ only in prose, which is what lets B3 check an attribution's ids
    against a lineage without knowing which direction produced it.
    """
    return tuple(
        str(item["id"])
        for item in _entries(direction="LONG", entry_comparison="(ids only)")
    )
