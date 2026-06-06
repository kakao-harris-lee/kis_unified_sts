"""e2e: M5b cron shadow run -> trading:stock:market_context:shadow (live key untouched)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import fakeredis
import pytest

import scripts.analysis.llm_market_context as m
import shared.streaming.trading_state as ts
from services.trading import llm_context_publisher as lcp
from shared.llm.market_context import MarketContext
from shared.streaming.trading_state import TradingStateReader


@pytest.mark.asyncio
async def test_shadow_publishes_to_suffixed_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fakeredis.FakeStrictRedis(db=1)
    monkeypatch.setattr(ts, "_get_redis", lambda: fake)
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "")  # run_once forces 'shadow'

    ctx = MarketContext(regime="BULL_STRONG", confidence=0.8)
    monkeypatch.setattr(
        lcp.LLMContextPublisher, "run_analysis", AsyncMock(return_value=ctx)
    )
    # no-op the SQLite ledger append so the test has no filesystem side effects
    monkeypatch.setattr(
        lcp.LLMContextPublisher,
        "_append_market_context_history",
        lambda _self, _c: None,
    )

    rc = await m.run_once("shadow")
    assert rc == 0

    # shadow key written; live key untouched (orchestrator's dashboard safe)
    assert fake.exists("trading:stock:market_context:shadow") == 1
    assert fake.exists("trading:stock:market_context") == 0

    # the consumer's reader (with the suffix set) reads it back
    read = TradingStateReader("stock").get_market_context()
    assert read is not None
    assert read.regime == "BULL_STRONG"
    assert read.confidence == 0.8
