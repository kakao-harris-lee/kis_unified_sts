"""Futures backtest engine selector — harness vs vectorbt opt-in (P3-d follow-up).

Single chokepoint for the walk-forward / optimizer scripts
(``scripts/walk_forward_*.py``, ``scripts/optimize_decision_engine.py``) to
choose between the production :class:`~shared.backtest.decision_harness.
BacktestDecisionHarness` (default, SoT) and the opt-in
:class:`~shared.backtest.vbt_harness_runner.VbtHarnessRunner` composition
wrapper. Keeping the selection logic here avoids duplicating the
try/except/fallback dance across the scripts.

Engine semantics (fixed by design — do not change):

* ``engine="harness"`` (default): run :class:`BacktestDecisionHarness`
  unchanged — current behaviour.
* ``engine="vectorbt"``: run :class:`VbtHarnessRunner`.
  :class:`VbtHarnessNotSupportedError` (vectorbt not installed) **propagates**
  — these are manually-run operator scripts with an explicit opt-in flag, so
  an explicit failure beats a silent fallback (no automated consumers). The
  exception message already carries the ``pip install -e ".[backtest]"`` hint.
* :class:`VbtHarnessParityError` is **not** swallowed silently: it is logged
  as a warning (with the mismatch detail) and the SoT result is restored from
  ``exc.harness_result`` — the first-run harness result the runner attaches
  before propagating. The harness is **never rerun** here: stateful setups
  (e.g. Setup C's ``EventTradeTracker`` marks events during the first run)
  would lose their trades on a rerun. A parity error without
  ``harness_result`` is an explicit hard failure, not a silent rerun. The
  returned label is ``"vectorbt_parity_failed"`` so callers can surface the
  investigation signal in their output JSON. Result correctness is unaffected
  (the harness is the SoT either way).
* Unknown ``engine`` values raise :class:`ValueError`.

The engine label constants live in :mod:`shared.backtest.engine_cli`
(stdlib-only, shared with the scripts' argparse wiring) and are re-exported
here for import compatibility.

plan: docs/plans/2026-07-08-new-architecture-refactoring-plan.md §5 (P3-d).
"""

from __future__ import annotations

import logging
from typing import Any

from shared.backtest.decision_harness import BacktestDecisionHarness, HarnessResult
from shared.backtest.engine_cli import (
    ENGINE_HARNESS,
    ENGINE_VECTORBT,
    ENGINE_VECTORBT_PARITY_FAILED,
    SUPPORTED_ENGINES,
)
from shared.backtest.market_context_replay import MarketContextReplay
from shared.backtest.vbt_harness_runner import VbtHarnessParityError, VbtHarnessRunner
from shared.decision.setup_base import Setup
from shared.risk.layer import RiskFilterLayer
from shared.risk.state import RiskStateSnapshot

__all__ = [
    "ENGINE_HARNESS",
    "ENGINE_VECTORBT",
    "ENGINE_VECTORBT_PARITY_FAILED",
    "SUPPORTED_ENGINES",
    "run_futures_backtest",
]

logger = logging.getLogger(__name__)


def run_futures_backtest(
    setups: list[Setup],
    filter_layer: RiskFilterLayer,
    state: RiskStateSnapshot,
    tick_size_points: float,
    replay: MarketContextReplay,
    *,
    engine: str = ENGINE_HARNESS,
    sizer: Any | None = None,
    account_equity_krw: float = 0.0,
) -> tuple[HarnessResult, str]:
    """Run one futures backtest window through the selected engine.

    Args:
        setups: Setup instances to evaluate (same contract as
            :class:`BacktestDecisionHarness`).
        filter_layer: RiskFilterLayer applied to candidate signals.
        state: Immutable RiskStateSnapshot.
        tick_size_points: Tick size (slippage + tick P&L conversion).
        replay: :class:`MarketContextReplay` over the window's bars.
        engine: ``"harness"`` (default) or ``"vectorbt"`` — see module
            docstring for the exact semantics.
        sizer: Optional PositionSizer forwarded to the engine.
        account_equity_krw: Account equity forwarded to the sizer.

    Returns:
        ``(result, engine_label)`` where ``engine_label`` is the engine that
        actually produced the result: ``"harness"``, ``"vectorbt"``, or
        ``"vectorbt_parity_failed"`` (vectorbt parity cross-check failed —
        SoT result restored from the first-run harness result carried on the
        exception, without a rerun).

    Raises:
        ValueError: Unknown ``engine`` value.
        VbtHarnessNotSupportedError: ``engine="vectorbt"`` but vectorbt is not
            installed (``pip install -e ".[backtest]"``) — deliberately not
            swallowed (explicit opt-in, no silent fallback).
        RuntimeError: A :class:`VbtHarnessParityError` arrived without the
            first-run ``harness_result`` — restoring the SoT would require a
            rerun, which silently loses trades for stateful setups, so this
            fails loudly instead.
    """
    if engine not in SUPPORTED_ENGINES:
        raise ValueError(
            f"unknown engine {engine!r} — expected one of {SUPPORTED_ENGINES}"
        )

    if engine == ENGINE_HARNESS:
        result = BacktestDecisionHarness(
            setups,
            filter_layer,
            state,
            tick_size_points,
            sizer=sizer,
            account_equity_krw=account_equity_krw,
        ).run(replay)
        return result, ENGINE_HARNESS

    # engine == ENGINE_VECTORBT.
    # VbtHarnessNotSupportedError (vectorbt not installed) propagates on
    # purpose — see module docstring.
    runner = VbtHarnessRunner(
        setups,
        filter_layer,
        state,
        tick_size_points,
        sizer=sizer,
        account_equity_krw=account_equity_krw,
    )
    try:
        return runner.run(replay), ENGINE_VECTORBT
    except VbtHarnessParityError as exc:
        harness_result = getattr(exc, "harness_result", None)
        if harness_result is None:
            # No first-run result to restore. Deliberately NOT rerunning the
            # harness: stateful setups (Setup C EventTradeTracker) consumed
            # their state during the first run, so a rerun would silently
            # drop their trades — fail loudly instead.
            raise RuntimeError(
                "VbtHarnessParityError carried no harness_result — cannot "
                "restore the SoT result without a harness rerun, and a rerun "
                "would silently lose trades for stateful setups (e.g. Setup "
                "C's EventTradeTracker); investigate the parity mismatch "
                "(scripts/vbt_parity_report.py)"
            ) from exc
        logger.warning(
            "vectorbt from_orders parity cross-check FAILED (%s) — restoring "
            "the first-run BacktestDecisionHarness (SoT) result (no rerun); "
            "investigate the parity mismatch (scripts/vbt_parity_report.py)",
            exc,
        )
        return harness_result, ENGINE_VECTORBT_PARITY_FAILED
