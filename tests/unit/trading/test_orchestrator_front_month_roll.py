"""Orchestrator re-resolves the futures front month at every session start.

Regression for 2026-09-11: trader-futures resolved A01609 at process start,
kept looping sessions in-process, and opened the day-after-expiry session on
the dead contract (WS subscribed, zero ticks). Dates are pinned through the
resolver's ``target_date``; nothing compares against the wall clock.
"""

from __future__ import annotations

import functools
import logging
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.trading import orchestrator as orch_mod
from services.trading.orchestrator import TradingConfig, TradingOrchestrator
from shared.execution.futures_instrument import resolve_futures_instrument_from_env

_EXPIRY_DAY = date(2026, 9, 10)
_DAY_AFTER = date(2026, 9, 11)
_ROLL_WARNING = "futures front-month rolled: A01609 -> A01612 (expiry 2026-12-10)"


def _pin_resolver(monkeypatch, on: date, **env: str) -> None:
    monkeypatch.setattr(
        orch_mod,
        "resolve_futures_instrument_from_env",
        functools.partial(
            resolve_futures_instrument_from_env,
            environ={"FUTURES_TRADING_PRODUCT": "kospi200", **env},
            target_date=on,
        ),
    )


def _bare(symbols: list[str], *, auto_resolved: bool = True) -> TradingOrchestrator:
    o = TradingOrchestrator.__new__(TradingOrchestrator)
    o.config = TradingConfig(
        asset_class="futures",
        symbols=symbols,
        futures_symbol_auto_resolved=auto_resolved,
    )
    o._futures_daily_reference = {"A01609": {"prev_close": 400.0}}
    return o


def test_day_after_expiry_swaps_symbol_and_drops_stale_reference(monkeypatch, caplog):
    _pin_resolver(monkeypatch, _DAY_AFTER)
    o = _bare(["A01609"])

    with caplog.at_level(logging.WARNING, logger=orch_mod.logger.name):
        o._roll_futures_front_month_at_session_start()

    assert o.config.symbols == ["A01612"]
    assert "A01609" not in o._futures_daily_reference
    assert _ROLL_WARNING in caplog.text


def test_roll_keeps_recovered_extra_symbols(monkeypatch):
    _pin_resolver(monkeypatch, _DAY_AFTER)
    o = _bare(["A01609", "A05610"])

    o._roll_futures_front_month_at_session_start()

    assert o.config.symbols == ["A01612", "A05610"]


def test_expiry_day_keeps_symbol(monkeypatch, caplog):
    _pin_resolver(monkeypatch, _EXPIRY_DAY)
    o = _bare(["A01609"])

    with caplog.at_level(logging.WARNING, logger=orch_mod.logger.name):
        o._roll_futures_front_month_at_session_start()

    assert o.config.symbols == ["A01609"]
    assert "front-month rolled" not in caplog.text


def test_pinned_strategy_symbol_is_never_rolled(monkeypatch):
    _pin_resolver(monkeypatch, _DAY_AFTER, FUTURES_STRATEGY_SYMBOL="A01609")
    o = _bare(["A01609"])

    o._roll_futures_front_month_at_session_start()

    assert o.config.symbols == ["A01609"]


def test_explicitly_passed_symbols_are_never_rolled(monkeypatch):
    _pin_resolver(monkeypatch, _DAY_AFTER)
    o = _bare(["A01609"], auto_resolved=False)

    o._roll_futures_front_month_at_session_start()

    assert o.config.symbols == ["A01609"]


def test_futures_factory_marks_only_env_resolved_symbols(monkeypatch):
    monkeypatch.delenv("FUTURES_STRATEGY_SYMBOL", raising=False)
    assert TradingConfig.futures().futures_symbol_auto_resolved is True
    assert (
        TradingConfig.futures(symbols=["A01609"]).futures_symbol_auto_resolved is False
    )


@pytest.mark.asyncio
async def test_start_rolls_before_feed_prefetch_and_components(monkeypatch):
    """The new code reaches the WS feed subscription and the prev_close prefetch."""
    import shared.kis.error_rate as error_rate

    _pin_resolver(monkeypatch, _DAY_AFTER)
    monkeypatch.setattr(
        error_rate.KISApiErrorRateTracker,
        "get_instance",
        classmethod(lambda cls: MagicMock(start=AsyncMock())),
    )
    o = TradingOrchestrator(
        TradingConfig(
            asset_class="futures",
            symbols=["A01609"],
            futures_symbol_auto_resolved=True,
        )
    )

    seen_by_components: list[list[str]] = []

    async def _init_components() -> None:
        seen_by_components.append(list(o.config.symbols))

    feed = MagicMock(start=AsyncMock(), symbol_count=1)
    kis_client = MagicMock(
        _get_futures_price=AsyncMock(return_value={"prev_close": 812.5})
    )
    o._initialize_components = _init_components
    o._reset_futures_daily_risk_state_at_session_start = AsyncMock()
    o._kis_client = kis_client
    o._futures_price_feed = feed
    o._futures_slippage_aux_symbols = []
    o._market_data_loop = AsyncMock()
    o._start_llm_context_publisher = AsyncMock()
    o._start_kill_switch_consumer = AsyncMock()
    o._start_shadow_loggers_flush = AsyncMock()
    o._create_pipeline = MagicMock(return_value=MagicMock(start=AsyncMock()))
    o._metrics = MagicMock()
    o._notify = AsyncMock()

    await o.start()
    if o._market_data_task is not None:
        await o._market_data_task

    assert seen_by_components == [["A01612"]]
    feed.update_symbols.assert_called_once_with(["A01612"], auxiliary_symbols=[])
    kis_client._get_futures_price.assert_awaited_once_with("A01612")
    assert o._futures_daily_reference == {"A01612": {"prev_close": 812.5}}


# --------------------------------------------------------------------------- #
# Candle cache (review F1): the expired contract must not come back from Redis
# --------------------------------------------------------------------------- #


def _candle(close: float) -> SimpleNamespace:
    return SimpleNamespace(
        open=close, high=close, low=close, close=close, volume=1, minute=540
    )


@pytest.mark.asyncio
async def test_candle_cache_load_skips_rolled_out_contract(monkeypatch):
    """09-11 prod: `Candle cache loaded` seeded A01609 next to A01612."""
    import shared.streaming.trading_state as trading_state

    cache = {
        "A01609": [{"close": 400.0}],
        "A01612": [{"close": 405.0}],
    }
    monkeypatch.setattr(
        trading_state,
        "TradingStateReader",
        lambda asset_class: SimpleNamespace(get_candle_cache=lambda: cache),
    )
    o = _bare(["A01612"])
    o._position_tracker = None
    o._indicator_engine = MagicMock()
    o._indicator_engine.is_warm.return_value = False

    loaded = await o._load_candle_cache_from_redis()

    assert loaded == 1
    o._indicator_engine.seed_candles.assert_called_once_with("A01612", cache["A01612"])


def test_candle_cache_save_drops_rolled_out_contract():
    """09-11 prod: `Candle cache saved: 2 symbols` re-published A01609."""
    o = _bare(["A01612"])
    o._position_tracker = None
    o._state_publisher = MagicMock()
    o._indicator_engine = SimpleNamespace(
        _accumulators={
            "A01609": SimpleNamespace(candles=[_candle(400.0)]),
            "A01612": SimpleNamespace(candles=[_candle(405.0)]),
        }
    )

    o._save_candle_cache_to_redis()

    (saved,), _ = o._state_publisher.publish_candle_cache.call_args
    assert set(saved) == {"A01612"}


def test_candle_cache_save_keeps_symbols_of_open_positions():
    o = _bare(["A01612"])
    o._position_tracker = SimpleNamespace(positions=[SimpleNamespace(code="A05610")])
    o._state_publisher = MagicMock()
    o._indicator_engine = SimpleNamespace(
        _accumulators={
            "A05610": SimpleNamespace(candles=[_candle(300.0)]),
            "A01612": SimpleNamespace(candles=[_candle(405.0)]),
        }
    )

    o._save_candle_cache_to_redis()

    (saved,), _ = o._state_publisher.publish_candle_cache.call_args
    assert set(saved) == {"A01612", "A05610"}
