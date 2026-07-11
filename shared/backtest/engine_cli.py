"""Engine-selection CLI helpers for the futures walk-forward/optimizer scripts.

Single source for the ``--engine`` argparse block and the parity-failure
operator warning shared by the five scripts (``scripts/walk_forward_*.py``,
``scripts/optimize_decision_engine.py``). Before this module each script
carried its own copy (three of them with hardcoded choices), so the flag help
and the warning wording drifted independently.

**Import-weight contract**: this module imports the standard library only.
``walk_forward_sensitivity.py`` / ``walk_forward_paper_foldin.py`` keep their
heavy imports lazy so ``--help`` stays fast — do not import
``shared.backtest.harness_engine`` (pandas/harness stack) from here.
:mod:`shared.backtest.harness_engine` re-exports these constants for its own
callers instead (dependency points harness_engine → engine_cli, never back).

plan: docs/plans/2026-07-08-new-architecture-refactoring-plan.md §5 (P3-d).
"""

from __future__ import annotations

import argparse
import logging

# Engine labels — argparse choices AND the "actually used engine" labels
# recorded in script outputs. ENGINE_VECTORBT_PARITY_FAILED is a result label
# only (never a valid input).
ENGINE_HARNESS = "harness"
ENGINE_VECTORBT = "vectorbt"
ENGINE_VECTORBT_PARITY_FAILED = "vectorbt_parity_failed"
SUPPORTED_ENGINES: tuple[str, ...] = (ENGINE_HARNESS, ENGINE_VECTORBT)

_ENGINE_HELP = (
    "Backtest engine: 'harness' (default, BacktestDecisionHarness) or "
    "'vectorbt' (opt-in VbtHarnessRunner — same harness plus a from_orders "
    "parity cross-check; requires the backtest extra: "
    'pip install -e ".[backtest]"). Parity failures log a warning and the '
    "first-run harness (SoT) result is kept (label 'vectorbt_parity_failed')."
)


def add_engine_argument(
    parser: argparse.ArgumentParser, *, extra_help: str = ""
) -> None:
    """Register the standard ``--engine`` flag on ``parser``.

    Args:
        parser: Target argparse parser.
        extra_help: Optional script-specific sentence(s) appended to the
            shared help text (e.g. the optimizer's per-trial cost warning).
    """
    help_text = _ENGINE_HELP if not extra_help else f"{_ENGINE_HELP} {extra_help}"
    parser.add_argument(
        "--engine",
        choices=list(SUPPORTED_ENGINES),
        default=ENGINE_HARNESS,
        help=help_text,
    )


def warn_parity_failures(
    logger: logging.Logger, count: int, unit: str = "window"
) -> None:
    """Emit the shared operator warning when parity fallbacks occurred.

    No-op when ``count`` is zero. ``unit`` names what fell back ("window"
    for the walk-forward scripts, "trial" for the optimizer).
    """
    if not count:
        return
    logger.warning(
        "%d %s(s) fell back to the first-run harness result after a "
        "vectorbt parity failure — results are still harness(SoT)-accurate, "
        "but investigate (scripts/vbt_parity_report.py)",
        count,
        unit,
    )
