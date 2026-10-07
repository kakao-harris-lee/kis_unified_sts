"""CP-3 B1b — B1a's field JSONL → ``tos.backtest.Bar`` → ``BacktestDriver`` trace.

`docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md` §3 구축물 B1b, §5 2.
Placement rationale (digest-untouched + firewall scope) is in this package's
``__init__.py`` — read that first.

What this package is
--------------------
A **loader + driver**, nothing else. ``tos.backtest`` ships no loader on
purpose (``bars.py`` 4-7행: parquet/pandas ingestion is out-of-tree because a
harness that reads files is no longer a pure function of its inputs) and the
harness is handed a ``tuple[Bar, ...]``. This package is that out-of-tree loader
for the one input shape CP-3 defines — B1a's five-key journal JSONL — plus the
wiring that drives it through the single shipped event core and writes the
trace artifact the out-of-tree comparator (B3) reads.

**This module is the CLI and the package's single import surface.** The work
lives in siblings — ``contract`` (the journal contract + field policy), ``bars``,
``seam`` (the Capsule / value-view seam), ``strategy``, ``replay``, ``lineage``,
``differences`` — split there by the 2026-10-08 review's size-budget finding, not
by a change of design; every public name is re-exported here so a caller does not
have to know which sibling a name lives in.

It **re-authors nothing** — now. ``validate_bar_stream``, ``CausalBarConverter``,
``BacktestDriver``, ``EngineCore``, ``trace_document`` / ``trace_digest``,
``context_value_view_digest``, the strategy loader, the bindings loader and the
bindings resolution rules are all consumed verbatim.

⚠ That sentence was **false for one value** until 2026-10-08, and the way it was
false is worth keeping on the page: the published ``ContextValueView``'s
``canonical_digest`` was computed locally, in emission order, without the
snapshot binding in its preimage — so ``view_digest_matches`` was ``False`` on
every bar (``a82270de…`` recorded vs ``41faf4ac…`` canonical) and the mismatch
rode into every ``outcome_digest`` and the ``trace_digest``. Nothing rejected it;
a claim in a docstring is not a gate. The fix imports the kernel function and a
test asserts the predicate — which is the only form of that claim that holds.

The value-surface seam (how per-bar fields reach the DSL)
---------------------------------------------------------
This is the one non-obvious part, so it is stated precisely.

``tos.backtest`` injects two slots per bar: a ``CapsuleSource``
(``(Bar) -> DecisionContextCapsule``) and a ``DecisionContextResolver``
(``(capsule, *, instrument_key) -> DecisionTickPayload``). The shipped
``ProvisionalContextResolver`` resolves **nothing** — slice #1 binds the
Capsule's ``SnapshotRef`` only, so "the mechanism runs, the decision starves"
(``resolver.py`` class docstring). The **typed seam for values already exists**
one layer down: ``DecisionTickPayload.value_view`` is a
``tos.dsl.ContextValueView``, and ``tos.engine.pipeline`` passes it straight
into ``evaluate_resolved(resolved_context=payload.value_view)``, which merges
it at ``env["capsule"]["resolved_values"][field_key]``
(``tos.dsl.determinism.build_environment``). So a DSL ref
``("capsule", "resolved_values", "z_x1000")`` resolves iff a view carrying that
``field_key`` is published for that tick.

:class:`Cp3CapsuleSource` therefore mints a **per-bar** Capsule whose
``SnapshotRef`` is derived from that bar's own record, and
:class:`Cp3FieldResolver` resolves that reference back to the bar's fields and
publishes the view — the same ``snapshot_id`` + ``canonical_digest`` round trip
``tos.marketfeed.resolver`` performs (``resolver.py`` 170-192행), and the same
refusal: a view is published **only** on an exact binding match, never on a
near miss. Per-bar Capsules are also what makes the bars *distinguishable* at
all (the shipped suite issues one identical Capsule for every bar, which is
honest for a value-free slice but useless here).

**Declared difference — the fields enter as already-admitted values.** The
production path admits a Critical Input through
``tos.marketfeed``'s five-value policy (unit / scale / multiplier / sign /
max_age_ms) and its VALID gate, and ``ContextValueView.values`` is "VALID by
construction" because *that producer* applied the gate
(``tos.dsl.context_value`` class docstring). The backtest harness has **no
policy seam at all**: there is no injection point in ``tos.backtest`` for a
``critical_input_policy``, and ``ContextValue`` deliberately carries no
``field_state``. So B1b publishes B1a's fields as already-admitted values and
records each field's five governed values in the lineage block
(:data:`FIELD_POLICY`) rather than enforcing them here. Two consequences, both
recorded in ``lineage.json::declared_differences``:

* a field whose scale/sign disagrees with B1a's lineage would not be caught
  here — it is caught by B1a's own per-bar equality tests against the legacy
  implementation;
* ``max_age_ms`` has no consumer in this path: freshness is judged from the
  injected :class:`~tos.backtest.BarTimeProjection` bounds, not from the field
  policy.

What the run can and cannot claim
---------------------------------
Exactly what ``tos.backtest`` already declares, carried through unchanged:
``closes_no_ev`` is ``True``, there is no performance surface anywhere, and the
run is a **mechanism / parity demonstration**. Plus the B4 cap: at most **one
order per scope for the whole run**, so every later firing is an exact capacity
denial (``AT_MOST_ONE_EXPOSURE_HELD``) rather than a failure — recorded as
``capacity_denied: true``.

Firewall: ``tos.*`` + ``tos_runtime.*`` + stdlib + ``pyyaml``(transitively, via
the loaders). No ``shared.*``, no clock, no RNG, no subprocess, no network.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from tos.canonical import ArtifactIntegrityError
from tos_runtime.strategy.bindings import STRATEGY_BINDINGS_FILE_NAME

# Relative, not absolute: the import firewall's allowlist (kernel §3.2 / runtime
# R1) names stdlib + pydantic/numpy/pandas/pyyaml + ``tos.*`` + ``tos_runtime.*``
# and nothing else, so `import cp3` would be a TOS-FW-A violation. A relative
# import carries no absolute module name for the gate to classify
# (``tools/tos_firewall_check.py`` skips ``node.level > 0``), which is why every
# intra-package import in this directory — the tests' included — is relative.
from ._base import LINEAGE_SCHEMA_VERSION, SCHEME, Cp3RunnerRefusal
from .bars import build_bars
from .contract import (
    BAR_FIELD_KEYS,
    FIELD_POLICY,
    FIELD_POLICY_GOVERNED_KEYS,
    INDICATOR_FIELD_KEYS,
    JOURNAL_REQUIRED_KEYS,
    REQUIRED_FIELD_KEYS,
    FieldRecord,
    read_field_records,
)
from .lineage import build_lineage, write_artifacts
from .replay import (
    DEFAULT_BUDGET_STEPS,
    DEFAULT_MAX_UNRESOLVED_SEND_PER_SCOPE,
    PROVISIONAL_TIME_BOUNDS,
    RunArtifacts,
    run_replay,
)
from .seam import Cp3CapsuleSource, Cp3FieldResolver
from .strategy import LoadedStrategyContent, load_strategy_content

#: Re-exported so the package has ONE import surface: the decomposition into
#: sibling modules is a size-budget/readability change, not a new API, and a
#: caller (or a test) should not have to know which module a name moved to.
__all__ = [
    "BAR_FIELD_KEYS",
    "DEFAULT_BUDGET_STEPS",
    "DEFAULT_MAX_UNRESOLVED_SEND_PER_SCOPE",
    "FIELD_POLICY",
    "FIELD_POLICY_GOVERNED_KEYS",
    "INDICATOR_FIELD_KEYS",
    "JOURNAL_REQUIRED_KEYS",
    "LINEAGE_SCHEMA_VERSION",
    "PROVISIONAL_TIME_BOUNDS",
    "REQUIRED_FIELD_KEYS",
    "SCHEME",
    "Cp3CapsuleSource",
    "Cp3FieldResolver",
    "Cp3RunnerRefusal",
    "FieldRecord",
    "LoadedStrategyContent",
    "RunArtifacts",
    "build_bars",
    "build_lineage",
    "load_strategy_content",
    "main",
    "read_field_records",
    "run_replay",
    "write_artifacts",
]

# ===========================================================================
# CLI
# ===========================================================================


def _parser() -> argparse.ArgumentParser:
    """The CLI surface."""
    parser = argparse.ArgumentParser(
        prog="cp3.runner",
        description=(
            "CP-3 B1b — drive B1a's field JSONL through tos.backtest and emit a "
            "decision-level trace + lineage. Closes no EV; makes no performance "
            "claim."
        ),
    )
    parser.add_argument("--fields", required=True, type=Path, help="B1a's fields.jsonl")
    parser.add_argument(
        "--strategy",
        required=True,
        type=Path,
        help="the Authored Strategy YAML (its parent directory is loaded)",
    )
    parser.add_argument(
        "--bindings",
        required=True,
        type=Path,
        help=f"the sibling {STRATEGY_BINDINGS_FILE_NAME}",
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="output directory for the artifacts"
    )
    parser.add_argument(
        "--budget-steps",
        type=int,
        default=DEFAULT_BUDGET_STEPS,
        help=(
            "injected dsl_evaluation_budget_steps (default %(default)s, from "
            "config/tos_runtime/paper/engine.yaml)"
        ),
    )
    parser.add_argument(
        "--max-unresolved-send-per-scope",
        type=int,
        default=DEFAULT_MAX_UNRESOLVED_SEND_PER_SCOPE,
        help=(
            "injected max_unresolved_send_per_scope (default %(default)s). NOTE: "
            "raising it does NOT raise how many orders are realized — the cap is "
            "the backtest reservation projection's absent release path, not this "
            "bound (measured; see lineage declared_differences B1b-D1). It only "
            "moves where a denied flow halts."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Returns:
        ``0`` on success, ``2`` on any typed refusal.
    """
    args = _parser().parse_args(argv)
    try:
        records = read_field_records(args.fields)
        content = load_strategy_content(
            strategy_path=args.strategy, bindings_path=args.bindings
        )
        artifacts = run_replay(
            records=records,
            content=content,
            budget_steps=args.budget_steps,
            max_unresolved_send_per_scope=args.max_unresolved_send_per_scope,
        )
        trace_path, lineage_path = write_artifacts(
            out_dir=args.out,
            artifacts=artifacts,
            content=content,
            fields_path=args.fields,
            budget_steps=args.budget_steps,
            max_unresolved_send_per_scope=args.max_unresolved_send_per_scope,
        )
    except Cp3RunnerRefusal as exc:
        print(f"cp3.runner: REFUSED — {exc}", file=sys.stderr)
        return 2
    except ArtifactIntegrityError as exc:
        print(f"cp3.runner: REFUSED (kernel) — {exc}", file=sys.stderr)
        return 2
    print(f"bars_read={artifacts.bars_read} bars_driven={artifacts.bars_driven}")
    print(f"outcome_kinds={artifacts.outcome_counts}")
    print(f"rule_fires={artifacts.rule_fire_counts}")
    print(f"capacity_denials={artifacts.capacity_denials}")
    print(f"halt_reasons={artifacts.halt_counts}")
    print(f"handoffs={artifacts.run.handoff_count}")
    print(f"realized_orders={list(artifacts.realized_orders)}")
    print(f"trace_digest={artifacts.trace_digest}")
    print(f"trace={trace_path}")
    print(f"lineage={lineage_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
