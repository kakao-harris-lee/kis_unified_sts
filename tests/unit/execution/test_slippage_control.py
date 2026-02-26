"""Tests for futures slippage control state machine."""

from datetime import datetime, time, timedelta

from shared.execution.slippage_control import (
    ExecutionAction,
    FuturesSlippageController,
    SlippageControlConfig,
    parse_orderbook_snapshot,
)


def _quote(
    *,
    bid: float = 330.48,
    ask: float = 330.50,
    bid_qty: float = 30.0,
    ask_qty: float = 30.0,
    close: float = 330.49,
) -> dict:
    return {
        "bid_price_1": bid,
        "ask_price_1": ask,
        "bid_qty_1": bid_qty,
        "ask_qty_1": ask_qty,
        "close": close,
        "timestamp": datetime.now().timestamp(),
    }


def test_parse_orderbook_snapshot_success():
    snap = parse_orderbook_snapshot("A05603", _quote())
    assert snap is not None
    assert snap.symbol == "A05603"
    assert snap.bid_price_1 == 330.48
    assert snap.ask_price_1 == 330.50
    assert snap.spread > 0


def test_evaluate_entry_blocks_wide_spread():
    cfg = SlippageControlConfig.from_dict(
        {
            "enabled": True,
            "tick_size": 0.02,
            "max_spread_ticks": 1,
            "min_depth_multiplier": 2.0,
            "cross_asset": {"enabled": False},
        }
    )
    controller = FuturesSlippageController(cfg)
    decision = controller.evaluate_entry(
        symbol="A05603",
        is_buy=True,
        quantity=1,
        signal_price=330.50,
        signal_timestamp=datetime.now(),
        quote_payload=_quote(ask=330.56),  # 4 ticks spread
        now=datetime.now(),
    )
    assert decision.action == ExecutionAction.BLOCK
    assert "wide_spread" in decision.reason


def test_evaluate_entry_passive_limit_when_filters_pass():
    cfg = SlippageControlConfig.from_dict(
        {
            "enabled": True,
            "tick_size": 0.02,
            "max_spread_ticks": 1,
            "min_depth_multiplier": 2.0,
            "max_price_deviation_ticks": 2,
            "cross_asset": {"enabled": False},
        }
    )
    controller = FuturesSlippageController(cfg)
    decision = controller.evaluate_entry(
        symbol="A05603",
        is_buy=True,
        quantity=2,
        signal_price=330.50,
        signal_timestamp=datetime.now(),
        quote_payload=_quote(bid_qty=20, ask_qty=20),
        now=datetime.now(),
    )
    assert decision.action == ExecutionAction.PASSIVE_LIMIT
    assert decision.target_price == 330.50


def test_evaluate_retry_cancels_when_price_deviation_exceeds_limit():
    cfg = SlippageControlConfig.from_dict(
        {
            "enabled": True,
            "tick_size": 0.02,
            "max_price_deviation_ticks": 1,
            "retry_policy": "market_once",
            "cross_asset": {"enabled": False},
        }
    )
    controller = FuturesSlippageController(cfg)
    retry = controller.evaluate_retry(
        symbol="A05603",
        is_buy=True,
        signal_price=330.50,
        quote_payload=_quote(ask=330.58),  # 4 ticks away
        now=datetime.now(),
    )
    assert retry.action == ExecutionAction.CANCEL
    assert "retry_deviation" in retry.reason


def test_evaluate_entry_blocks_stale_signal():
    cfg = SlippageControlConfig.from_dict(
        {
            "enabled": True,
            "max_signal_age_seconds": 0.5,
            "cross_asset": {"enabled": False},
        }
    )
    controller = FuturesSlippageController(cfg)
    decision = controller.evaluate_entry(
        symbol="A05603",
        is_buy=False,
        quantity=1,
        signal_price=330.48,
        signal_timestamp=datetime.now() - timedelta(seconds=2),
        quote_payload=_quote(),
        now=datetime.now(),
    )
    assert decision.action == ExecutionAction.BLOCK
    assert "stale_signal" in decision.reason


def test_evaluate_entry_blocks_insufficient_depth():
    cfg = SlippageControlConfig.from_dict(
        {
            "enabled": True,
            "tick_size": 0.02,
            "max_spread_ticks": 1,
            "min_depth_multiplier": 3.0,
            "cross_asset": {"enabled": False},
        }
    )
    controller = FuturesSlippageController(cfg)
    decision = controller.evaluate_entry(
        symbol="A05603",
        is_buy=True,
        quantity=2,  # required ask depth: 6
        signal_price=330.50,
        signal_timestamp=datetime.now(),
        quote_payload=_quote(ask_qty=4.0),
        now=datetime.now(),
    )
    assert decision.action == ExecutionAction.BLOCK
    assert "insufficient_depth" in decision.reason


def test_evaluate_entry_blocks_cross_asset_wide_spread():
    cfg = SlippageControlConfig.from_dict(
        {
            "enabled": True,
            "tick_size": 0.02,
            "max_spread_ticks": 1,
            "min_depth_multiplier": 1.0,
            "cross_asset": {
                "enabled": True,
                "reference_symbol": "101S6000",
                "max_spread_ticks": 1,
            },
        }
    )
    controller = FuturesSlippageController(cfg)
    decision = controller.evaluate_entry(
        symbol="A05603",
        is_buy=True,
        quantity=1,
        signal_price=330.50,
        signal_timestamp=datetime.now(),
        quote_payload=_quote(),
        cross_asset_payload=_quote(bid=331.00, ask=331.08),  # 4 ticks
        now=datetime.now(),
    )
    assert decision.action == ExecutionAction.BLOCK
    assert "cross_asset_wide_spread" in decision.reason


def test_evaluate_entry_blocks_during_time_window():
    cfg = SlippageControlConfig.from_dict(
        {
            "enabled": True,
            "tick_size": 0.02,
            "max_spread_ticks": 1,
            "min_depth_multiplier": 1.0,
            "cross_asset": {"enabled": False},
            "blocked_time_windows": [{"start": "09:00", "end": "09:05"}],
        }
    )
    controller = FuturesSlippageController(cfg)
    now = datetime(2026, 2, 25, 9, 1, 0)
    decision = controller.evaluate_entry(
        symbol="A05603",
        is_buy=True,
        quantity=1,
        signal_price=330.50,
        signal_timestamp=now,
        quote_payload=_quote(),
        now=now,
    )
    assert decision.action == ExecutionAction.BLOCK
    assert decision.reason == "blocked_time_window"


def test_evaluate_entry_blocks_during_event_window():
    cfg = SlippageControlConfig.from_dict(
        {
            "enabled": True,
            "tick_size": 0.02,
            "max_spread_ticks": 1,
            "min_depth_multiplier": 1.0,
            "cross_asset": {"enabled": False},
            "event_time_windows": [{"start": "21:25", "end": "21:35"}],
        }
    )
    controller = FuturesSlippageController(cfg)
    now = datetime(2026, 2, 25, 21, 30, 0)
    decision = controller.evaluate_entry(
        symbol="A05603",
        is_buy=True,
        quantity=1,
        signal_price=330.50,
        signal_timestamp=now,
        quote_payload=_quote(),
        now=now,
    )
    assert decision.action == ExecutionAction.BLOCK
    assert decision.reason == "blocked_time_window"


def test_evaluate_entry_blocks_overnight_event_window():
    cfg = SlippageControlConfig.from_dict(
        {
            "enabled": True,
            "cross_asset": {"enabled": False},
            "event_time_windows": [{"start": "23:58", "end": "00:05"}],
        }
    )
    controller = FuturesSlippageController(cfg)
    quote = _quote()

    late = datetime(2026, 2, 25, 23, 59, 0)
    early = datetime(2026, 2, 26, 0, 3, 0)
    clear = datetime(2026, 2, 26, 0, 15, 0)

    late_decision = controller.evaluate_entry(
        symbol="A05603",
        is_buy=True,
        quantity=1,
        signal_price=330.50,
        signal_timestamp=late,
        quote_payload=quote,
        now=late,
    )
    early_decision = controller.evaluate_entry(
        symbol="A05603",
        is_buy=True,
        quantity=1,
        signal_price=330.50,
        signal_timestamp=early,
        quote_payload=quote,
        now=early,
    )
    clear_decision = controller.evaluate_entry(
        symbol="A05603",
        is_buy=True,
        quantity=1,
        signal_price=330.50,
        signal_timestamp=clear,
        quote_payload=quote,
        now=clear,
    )

    assert late_decision.action == ExecutionAction.BLOCK
    assert early_decision.action == ExecutionAction.BLOCK
    assert clear_decision.action == ExecutionAction.PASSIVE_LIMIT


def test_time_window_contains_overnight_range():
    from shared.execution.slippage_control import TimeWindow

    window = TimeWindow(start=time(23, 50), end=time(0, 10))
    assert window.contains(time(23, 59)) is True
    assert window.contains(time(0, 5)) is True
    assert window.contains(time(0, 30)) is False


def test_evaluate_entry_blocks_during_volatility_cooldown():
    cfg = SlippageControlConfig.from_dict(
        {
            "enabled": True,
            "tick_size": 0.02,
            "max_spread_ticks": 1,
            "min_depth_multiplier": 1.0,
            "cross_asset": {"enabled": False},
            "volatility": {
                "window_ticks": 5,
                "spike_multiplier": 2.0,
                "cooldown_seconds": 3.0,
            },
        }
    )
    controller = FuturesSlippageController(cfg)
    base_ts = datetime(2026, 2, 25, 10, 0, 0)

    # Build low-vol baseline first.
    for i, px in enumerate([330.50, 330.51, 330.52, 330.53, 330.54]):
        controller.register_trade_tick("A05603", px, timestamp=base_ts + timedelta(seconds=i))

    # Spike triggers cooldown.
    controller.register_trade_tick("A05603", 330.70, timestamp=base_ts + timedelta(seconds=6))

    decision = controller.evaluate_entry(
        symbol="A05603",
        is_buy=True,
        quantity=1,
        signal_price=330.70,
        signal_timestamp=base_ts + timedelta(seconds=6),
        quote_payload=_quote(bid=330.68, ask=330.70, close=330.70),
        now=base_ts + timedelta(seconds=7),
    )
    assert decision.action == ExecutionAction.BLOCK
    assert "volatility_cooldown" in decision.reason


def test_evaluate_retry_cancel_when_policy_abort():
    cfg = SlippageControlConfig.from_dict(
        {
            "enabled": True,
            "retry_policy": "abort",
            "cross_asset": {"enabled": False},
        }
    )
    controller = FuturesSlippageController(cfg)
    retry = controller.evaluate_retry(
        symbol="A05603",
        is_buy=True,
        signal_price=330.50,
        quote_payload=_quote(),
        now=datetime.now(),
    )
    assert retry.action == ExecutionAction.CANCEL
    assert retry.reason == "retry_policy_abort"
