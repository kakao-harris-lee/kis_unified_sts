"""Flag routing for the stock strategy daemon entrypoint."""

from __future__ import annotations

import services.stock_strategy.main as m


def test_resolve_mode_default_off(monkeypatch):
    monkeypatch.delenv("STOCK_STRATEGY_DAEMON", raising=False)
    assert m._resolve_mode() == "off"


def test_resolve_mode_shadow(monkeypatch):
    monkeypatch.setenv("STOCK_STRATEGY_DAEMON", "shadow")
    assert m._resolve_mode() == "shadow"
    assert m._candidate_stream_for("shadow") == "signal.candidate.stock.shadow"
    assert m._candidate_stream_for("off") == "signal.candidate.stock"


def test_live_mode_is_active_and_unsuffixed() -> None:
    assert m._is_active_mode("live") is True
    assert m._candidate_stream_for("live") == "signal.candidate.stock"
    assert m._is_active_mode("off") is False


import pytest


@pytest.mark.asyncio
async def test_build_prewarm_fn_calls_warmup_engine(monkeypatch):
    from services.stock_strategy import main as main_mod
    from shared.streaming.candle_warmup import StockPrewarmConfig, WarmupResult

    seen = {}

    async def _fake_warmup(engine, symbol, *, store, kis_client, config):
        seen["symbol"] = symbol
        seen["config"] = config
        return WarmupResult(120, 252, "parquet")

    monkeypatch.setattr(main_mod, "warmup_engine", _fake_warmup)
    fn = main_mod.build_prewarm_fn(
        engine=object(), store=object(), kis_client=object(),
        cfg=StockPrewarmConfig(rest_enabled=True),
    )
    res = await fn("000660")
    assert seen["symbol"] == "000660"
    assert seen["config"].rest_enabled is True
    assert res.source == "parquet"
