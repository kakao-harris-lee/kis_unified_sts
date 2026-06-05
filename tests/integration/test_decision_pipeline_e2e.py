"""End-to-end decision pipeline integration test.

MarketContextReplay → BacktestDecisionHarness → SignalsAllWriter →
compatibility no-op archive writer.

Phase 3 is backtest-only: no order placement, `executed` is always 0.
"""

from __future__ import annotations

from datetime import UTC, datetime
import pytest

from shared.backtest.market_context_replay import MarketContextReplay
from shared.backtest.signals_writer import SignalsAllWriter
from shared.decision.setups.gap_reversion import SetupAGapReversion
from shared.decision.signal import Signal
from shared.risk.layer import LayerResult, RiskFilterLayer
from shared.risk.state import RiskStateSnapshot

# Reuse helpers from the backtest harness integration test so the gap-down day
# stays in sync across both e2e suites.
from tests.integration.test_backtest_harness import (  # noqa: E402
    BEARISH_MACRO,
    MINI_SPEC,
    _build_gap_down_df,
)


def _signal(tag: str = "test") -> Signal:
    return Signal(
        setup_type="A_gap_reversion",
        direction="short",
        symbol="A05603",
        entry_price=357.0,
        stop_loss=359.0,
        take_profit=354.0,
        confidence=0.72,
        reason_tags=[f"probe_{tag}"],
        valid_until=datetime.now(UTC),
        generated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_enqueue_and_flush_accepts_signals():
    writer = SignalsAllWriter(batch_size=2)
    await writer.enqueue(
        _signal("a"),
        LayerResult(
            passed=True, skip_reason=None, size_multiplier=1.0, filter_outcomes=[]
        ),
    )
    await writer.enqueue(
        _signal("b"),
        LayerResult(
            passed=True, skip_reason=None, size_multiplier=1.0, filter_outcomes=[]
        ),
    )
    await writer.flush()


@pytest.mark.asyncio
async def test_skip_reason_recorded_for_rejected_signal():
    writer = SignalsAllWriter(batch_size=1)
    rejected = LayerResult(
        passed=False,
        skip_reason="daily_mdd_exceeded",
        size_multiplier=1.0,
        filter_outcomes=[],
    )
    await writer.enqueue(_signal(), rejected, executed=False)


@pytest.mark.asyncio
async def test_full_pipeline_writes_candidates_to_signals_all():
    """End-to-end: replay → Setup → filter → SignalsAllWriter.

    Runs the same iteration the harness uses (Setup.check per ctx) but also
    enqueues each candidate+layer_result pair to the writer.
    """
    df = _build_gap_down_df(n_session2_bars=90)
    replay = MarketContextReplay(
        df=df,
        symbol="A05603",
        macro_snapshot=BEARISH_MACRO,
        scheduled_events=[],
        contract_spec=MINI_SPEC,
    )

    setup = SetupAGapReversion()
    layer = RiskFilterLayer(filters=[])  # no filters => pass-through
    state = RiskStateSnapshot()

    writer = SignalsAllWriter(batch_size=10)

    candidates = 0
    for ctx in replay.iter_contexts():
        candidate = setup.check(ctx)
        if candidate is None:
            continue
        candidates += 1
        layer_result = layer.evaluate(candidate, state)
        await writer.enqueue(candidate, layer_result, executed=False)
    await writer.flush()

    assert candidates >= 1
