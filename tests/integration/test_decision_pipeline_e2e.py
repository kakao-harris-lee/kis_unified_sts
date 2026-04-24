"""End-to-end decision pipeline integration test.

MarketContextReplay → BacktestDecisionHarness → SignalsAllWriter →
`kospi.signals_all` INSERT (mocked via AsyncMock).

Phase 3 is backtest-only: no order placement, `executed` is always 0.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

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
async def test_enqueue_and_flush_hits_ch_execute_with_expected_sql():
    ch = AsyncMock()
    writer = SignalsAllWriter(ch_client=ch, batch_size=2)
    await writer.enqueue(
        _signal("a"),
        LayerResult(
            passed=True, skip_reason=None, size_multiplier=1.0, filter_outcomes=[]
        ),
    )
    ch.execute.assert_not_awaited()
    await writer.enqueue(
        _signal("b"),
        LayerResult(
            passed=True, skip_reason=None, size_multiplier=1.0, filter_outcomes=[]
        ),
    )
    ch.execute.assert_awaited_once()
    sql = ch.execute.await_args.args[0]
    assert "INSERT INTO kospi.signals_all" in sql


@pytest.mark.asyncio
async def test_skip_reason_recorded_for_rejected_signal():
    ch = AsyncMock()
    writer = SignalsAllWriter(ch_client=ch, batch_size=1)
    rejected = LayerResult(
        passed=False,
        skip_reason="daily_mdd_exceeded",
        size_multiplier=1.0,
        filter_outcomes=[],
    )
    await writer.enqueue(_signal(), rejected, executed=False)
    ch.execute.assert_awaited_once()
    rows = ch.execute.await_args.args[1]
    assert len(rows) == 1
    row = rows[0]
    # column order: signal_id, generated_at, setup_type, direction, entry_price,
    # stop_loss, take_profit, confidence, executed, skip_reason, reason_tags
    assert row[8] == 0  # executed
    assert row[9] == "daily_mdd_exceeded"  # skip_reason


@pytest.mark.asyncio
async def test_generated_at_stripped_of_tzinfo():
    ch = AsyncMock()
    writer = SignalsAllWriter(ch_client=ch, batch_size=1)
    await writer.enqueue(
        _signal(),
        LayerResult(
            passed=True, skip_reason=None, size_multiplier=1.0, filter_outcomes=[]
        ),
    )
    ch.execute.assert_awaited_once()
    generated_at = ch.execute.await_args.args[1][0][1]
    assert isinstance(generated_at, datetime)
    assert generated_at.tzinfo is None, "aiochclient rejects tz-aware datetimes"


@pytest.mark.asyncio
async def test_flush_reraises_on_ch_failure():
    ch = AsyncMock()
    ch.execute.side_effect = RuntimeError("clickhouse down")
    writer = SignalsAllWriter(ch_client=ch, batch_size=1)
    with pytest.raises(RuntimeError, match="clickhouse down"):
        await writer.enqueue(
            _signal(),
            LayerResult(
                passed=True, skip_reason=None, size_multiplier=1.0, filter_outcomes=[]
            ),
        )


@pytest.mark.asyncio
async def test_full_pipeline_writes_candidates_to_signals_all():
    """End-to-end: replay → Setup → filter → SignalsAllWriter.

    Runs the same iteration the harness uses (Setup.check per ctx) but also
    enqueues each candidate+layer_result pair to the writer, verifying that
    rows land in ``kospi.signals_all`` via ``ch.execute``.
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

    ch = AsyncMock()
    writer = SignalsAllWriter(ch_client=ch, batch_size=10)

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
    assert ch.execute.await_count >= 1
    total_rows = sum(len(call.args[1]) for call in ch.execute.await_args_list)
    assert total_rows == candidates
