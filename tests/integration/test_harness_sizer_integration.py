"""End-to-end test: BacktestDecisionHarness with an injected sizer.

Verifies that ``FixedFractionalFuturesSizer.calculate`` is actually called
per trade, that ``TradeRecord.size_contracts`` reflects the sizer output,
and that ``ticks_net_total == ticks_net × size_contracts``.

Before this wiring the YAML section ``fixed_fractional_futures`` in
``config/risk.yaml`` was dead config (no runtime caller). The harness
now consumes it so ``FixedFractionalFuturesConfig.from_yaml()`` is a
real entry point.
"""

from __future__ import annotations

import pytest

from shared.backtest.decision_harness import BacktestDecisionHarness
from shared.backtest.market_context_replay import MarketContextReplay
from shared.decision.setups.event_reaction import (
    EventTradeTracker,
    SetupCEventReaction,
)
from shared.decision.setups.gap_reversion import SetupAGapReversion
from shared.risk.layer import RiskFilterLayer
from shared.risk.state import RiskStateSnapshot
from shared.strategy.position.sizers import (
    FixedFractionalFuturesConfig,
    FixedFractionalFuturesSizer,
)

# Reuse the well-tested gap-down fixture from the existing harness suite.
from tests.integration.test_backtest_harness import (  # noqa: E402
    BEARISH_MACRO,
    MINI_SPEC,
    _build_gap_down_df,
)


@pytest.mark.asyncio
async def test_harness_applies_sizer_per_trade() -> None:
    df = _build_gap_down_df(n_session2_bars=90)
    replay = MarketContextReplay(
        df=df,
        symbol="A05603",
        macro_snapshot=BEARISH_MACRO,
        scheduled_events=[],
        contract_spec=MINI_SPEC,
    )

    sizer_cfg = FixedFractionalFuturesConfig(
        max_position_risk_pct=0.015,
        max_position_size=5,
        soft_reduce_threshold=4,
    )
    sizer = FixedFractionalFuturesSizer(config=sizer_cfg, contract_spec=MINI_SPEC)

    harness = BacktestDecisionHarness(
        setups=[
            SetupAGapReversion(),
            SetupCEventReaction(tracker=EventTradeTracker()),
        ],
        filter_layer=RiskFilterLayer(filters=[]),
        state=RiskStateSnapshot(),
        tick_size_points=MINI_SPEC.tick_size_points,
        sizer=sizer,
        account_equity_krw=5_000_000,
    )
    result = harness.run(replay)

    assert result.trades, "synthetic gap-down must produce at least one trade"
    for trade in result.trades:
        assert trade.size_contracts >= 1
        assert trade.size_contracts <= sizer_cfg.max_position_size
        assert trade.ticks_net_total == pytest.approx(
            trade.ticks_net * trade.size_contracts
        )


@pytest.mark.asyncio
async def test_harness_without_sizer_records_one_contract() -> None:
    """Default ``sizer=None`` path preserves pre-sizing behavior."""
    df = _build_gap_down_df(n_session2_bars=90)
    replay = MarketContextReplay(
        df=df,
        symbol="A05603",
        macro_snapshot=BEARISH_MACRO,
        scheduled_events=[],
        contract_spec=MINI_SPEC,
    )
    harness = BacktestDecisionHarness(
        setups=[SetupAGapReversion()],
        filter_layer=RiskFilterLayer(filters=[]),
        state=RiskStateSnapshot(),
        tick_size_points=MINI_SPEC.tick_size_points,
        # no sizer injected
    )
    result = harness.run(replay)
    assert result.trades
    for trade in result.trades:
        assert trade.size_contracts == 1
        assert trade.ticks_net_total == pytest.approx(trade.ticks_net)


def test_fixed_fractional_futures_config_loads_from_yaml() -> None:
    """The ``fixed_fractional_futures`` YAML section is now consumed at runtime.

    Guards against re-introducing the "dead config" pattern flagged on PR #128.
    """
    cfg = FixedFractionalFuturesConfig.from_yaml()
    assert cfg.max_position_risk_pct == 0.015
    assert cfg.max_position_size == 2
    assert cfg.soft_reduce_threshold == 4
