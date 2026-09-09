"""Tests for futures slippage control state machine."""

from datetime import datetime, time, timedelta

import pytest

from shared.execution.slippage_control import (
    ExecutionAction,
    FuturesSlippageController,
    SlippageControlConfig,
    load_futures_slippage_config,
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
        controller.register_trade_tick(
            "A05603", px, timestamp=base_ts + timedelta(seconds=i)
        )

    # Spike triggers cooldown.
    controller.register_trade_tick(
        "A05603", 330.70, timestamp=base_ts + timedelta(seconds=6)
    )

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


# ---------------------------------------------------------------------------
# load_futures_slippage_config — F-9 Gate 1b control-parity closure §2-A
# ---------------------------------------------------------------------------


def _exec_cfg(
    *,
    enabled: bool = True,
    max_spread_ticks: int = 1,
    order_router_gate: bool | None = None,
    paper_override: dict | None = None,
) -> dict:
    section: dict = {
        "enabled": enabled,
        "tick_size": 0.02,
        "max_spread_ticks": max_spread_ticks,
        "min_depth_multiplier": 3.0,
        "max_signal_age_seconds": 2.0,
        "blocked_time_windows": [{"start": "08:45", "end": "08:50"}],
        "cross_asset": {"enabled": True, "reference_symbol": "101S6000"},
    }
    if order_router_gate is not None:
        section["order_router_gate"] = order_router_gate
    if paper_override is not None:
        section["paper_override"] = paper_override
    return {"futures_slippage_control": section}


def test_load_applies_paper_override_when_paper_trading_and_override_enabled():
    exec_cfg = _exec_cfg(
        max_spread_ticks=1,
        paper_override={
            "enabled": True,
            "max_spread_ticks": 6,
            "blocked_time_windows": [],
        },
    )
    cfg = load_futures_slippage_config(exec_cfg, paper_trading=True)
    assert cfg.max_spread_ticks == 6
    assert cfg.blocked_time_windows == []


def test_load_does_not_apply_override_when_not_paper_trading():
    exec_cfg = _exec_cfg(
        max_spread_ticks=1,
        paper_override={"enabled": True, "max_spread_ticks": 6},
    )
    cfg = load_futures_slippage_config(exec_cfg, paper_trading=False)
    assert cfg.max_spread_ticks == 1


def test_load_does_not_apply_override_when_override_itself_disabled():
    exec_cfg = _exec_cfg(
        max_spread_ticks=1,
        paper_override={"enabled": False, "max_spread_ticks": 6},
    )
    cfg = load_futures_slippage_config(exec_cfg, paper_trading=True)
    assert cfg.max_spread_ticks == 1


def test_load_respects_enabled_false():
    exec_cfg = _exec_cfg(enabled=False)
    cfg = load_futures_slippage_config(exec_cfg, paper_trading=True)
    assert cfg.enabled is False


def test_load_order_router_gate_defaults_true():
    exec_cfg = _exec_cfg()
    cfg = load_futures_slippage_config(exec_cfg, paper_trading=False)
    assert cfg.order_router_gate is True


def test_load_order_router_gate_reads_explicit_false():
    exec_cfg = _exec_cfg(order_router_gate=False)
    cfg = load_futures_slippage_config(exec_cfg, paper_trading=False)
    assert cfg.order_router_gate is False


def test_load_missing_section_returns_disabled_default():
    cfg = load_futures_slippage_config({}, paper_trading=True)
    assert cfg == SlippageControlConfig()


# ---------------------------------------------------------------------------
# Quote-freshness knob + helper (order-router-only, like order_router_gate)
# ---------------------------------------------------------------------------


def test_load_max_quote_age_defaults_to_ten_seconds():
    cfg = load_futures_slippage_config(_exec_cfg(), paper_trading=False)
    assert cfg.order_router_max_quote_age_seconds == 10.0


def test_load_max_quote_age_reads_explicit_value():
    exec_cfg = _exec_cfg()
    exec_cfg["futures_slippage_control"]["order_router_max_quote_age_seconds"] = 2.5
    cfg = load_futures_slippage_config(exec_cfg, paper_trading=False)
    assert cfg.order_router_max_quote_age_seconds == 2.5


def test_load_max_quote_age_zero_is_preserved_as_disabled():
    exec_cfg = _exec_cfg()
    exec_cfg["futures_slippage_control"]["order_router_max_quote_age_seconds"] = 0
    cfg = load_futures_slippage_config(exec_cfg, paper_trading=False)
    assert cfg.order_router_max_quote_age_seconds == 0.0


def test_repo_execution_yaml_exposes_the_quote_age_knob():
    """The knob must survive `${VAR:default}` interpolation in the real file —
    a router-only key the monolith ignores, same shape as order_router_gate."""
    from shared.config.loader import ConfigLoader

    cfg = load_futures_slippage_config(
        ConfigLoader.load("execution.yaml"), paper_trading=True
    )
    assert cfg.order_router_max_quote_age_seconds == 10.0


def test_quote_age_seconds_reads_epoch_float_and_string_and_iso():
    from datetime import UTC

    from shared.execution.slippage_control import quote_age_seconds

    now = datetime(2026, 4, 28, 5, 0, 0, tzinfo=UTC)
    epoch = now.timestamp() - 3.0

    assert quote_age_seconds({"timestamp": epoch}, now=now) == 3.0
    # Redis Stream fields arrive as strings.
    assert quote_age_seconds({"timestamp": str(epoch)}, now=now) == 3.0
    assert quote_age_seconds({"timestamp": "2026-04-28T04:59:57+00:00"}, now=now) == 3.0


def test_quote_age_seconds_returns_none_when_unreadable():
    from shared.execution.slippage_control import quote_age_seconds

    assert quote_age_seconds(None) is None
    assert quote_age_seconds({}) is None
    assert quote_age_seconds({"timestamp": "not-a-time"}) is None


def test_quote_age_seconds_allows_a_producer_clock_slightly_ahead():
    from datetime import UTC

    from shared.execution.slippage_control import quote_age_seconds

    now = datetime(2026, 4, 28, 5, 0, 0, tzinfo=UTC)
    assert quote_age_seconds({"timestamp": now.timestamp() + 2.0}, now=now) == -2.0


def test_numeric_string_timestamp_no_longer_silently_reads_as_now():
    """Regression: `parse_orderbook_snapshot` fell back to `now` for a numeric
    string, i.e. it reported a stale quote as freshly timestamped."""
    from datetime import UTC

    quote = _quote(bid=331.20, ask=331.22)
    quote["timestamp"] = "1700000000.0"
    snapshot = parse_orderbook_snapshot("A05603", quote)

    assert snapshot is not None
    assert snapshot.timestamp == datetime.fromtimestamp(1700000000.0, tz=UTC)


@pytest.mark.parametrize("as_str", [False, True], ids=["float", "str"])
@pytest.mark.parametrize(
    "bogus",
    [0, 1.5, -1700000000, 1.7e11, 2.4e11, 1700000000000.0],
    ids=["zero", "small", "negative", "just-over", "far-future", "ms-epoch"],
)
def test_non_epoch_numeric_fails_closed(bogus, as_str):
    """Anything outside plausible epoch SECONDS must not date a quote.

    The dangerous range is just above the bound: a value in [1e11, ~2.5e11)
    parses to a far-future date, which makes the age NEGATIVE and passes every
    freshness bound. (A millisecond epoch is further out and already raised
    inside `fromtimestamp`, so it was never the hole.) A float reaches here on
    the decoded stream path and a string only from a raw Redis field, so both
    branches need the same bound.
    """
    from shared.execution.slippage_control import quote_age_seconds

    quote = _quote(bid=331.20, ask=331.22)
    quote["timestamp"] = str(bogus) if as_str else bogus
    assert parse_orderbook_snapshot("A05603", quote) is not None
    assert quote_age_seconds(quote) is None
