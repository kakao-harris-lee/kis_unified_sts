"""Tests for shared/execution/pseudo_oco.py — Phase 4 Task 7."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from shared.decision.signal import Signal
from shared.execution.passive_maker import Fill
from shared.execution.pseudo_oco import OCOHandle, OCOState, PseudoOCO


def _signal(direction: str = "long") -> Signal:
    return Signal(
        setup_type="A_gap_reversion",
        direction=direction,
        symbol="A05603",
        entry_price=331.20,
        stop_loss=330.00 if direction == "long" else 332.40,
        take_profit=333.00 if direction == "long" else 329.40,
        confidence=0.85,
        valid_until=datetime(2026, 4, 27, 6, 0, tzinfo=UTC),
        generated_at=datetime(2026, 4, 27, 5, 0, tzinfo=UTC),
    )


def _fill() -> Fill:
    return Fill(order_id="ENTRY-1", price=331.20, quantity=1, filled_at_ms=1000)


@pytest.fixture
def fill_logger():
    return AsyncMock()


@pytest.fixture
def oco(fill_logger):
    return PseudoOCO(fill_logger=fill_logger)


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_returns_handle(self, oco):
        h = await oco.register_bracket(
            signal=_signal("long"), signal_id="sig-1", fill=_fill()
        )
        assert isinstance(h, OCOHandle)
        assert h.signal_id == "sig-1"
        assert h.symbol == "A05603"
        assert h.state is OCOState.ACTIVE
        assert h.stop_price == 330.00
        assert h.target_price == 333.00

    @pytest.mark.asyncio
    async def test_handle_ids_unique(self, oco):
        h1 = await oco.register_bracket(
            signal=_signal("long"), signal_id="sig-1", fill=_fill()
        )
        h2 = await oco.register_bracket(
            signal=_signal("long"), signal_id="sig-2", fill=_fill()
        )
        assert h1.handle_id != h2.handle_id

    @pytest.mark.asyncio
    async def test_register_short_uses_inverted_levels(self, oco):
        h = await oco.register_bracket(
            signal=_signal("short"), signal_id="sig-s", fill=_fill()
        )
        # Short: stop above entry, target below
        assert h.stop_price == 332.40
        assert h.target_price == 329.40
        assert h.direction == "short"


class TestStopTrigger:
    @pytest.mark.asyncio
    async def test_long_stop_fires_on_drop(self, oco, fill_logger):
        h = await oco.register_bracket(
            signal=_signal("long"), signal_id="sig-1", fill=_fill()
        )
        fired = await oco.on_tick(symbol="A05603", price=329.50, now_ms=2000)
        assert len(fired) == 1
        assert fired[0].handle_id == h.handle_id
        assert fired[0].state is OCOState.STOP_HIT
        # Logged a stop_loss fill
        kwargs = fill_logger.log_fill.call_args.kwargs
        assert kwargs["trade_role"] == "stop_loss"
        assert kwargs["filled_price"] == 330.00  # at trigger
        assert kwargs["side"] == "short"  # closing direction

    @pytest.mark.asyncio
    async def test_short_stop_fires_on_rise(self, oco, fill_logger):
        await oco.register_bracket(
            signal=_signal("short"), signal_id="sig-s", fill=_fill()
        )
        fired = await oco.on_tick(symbol="A05603", price=332.50, now_ms=2000)
        assert len(fired) == 1
        assert fired[0].state is OCOState.STOP_HIT
        kwargs = fill_logger.log_fill.call_args.kwargs
        assert kwargs["side"] == "long"
        assert kwargs["filled_price"] == 332.40


class TestTargetTrigger:
    @pytest.mark.asyncio
    async def test_long_target_fires_on_rise(self, oco, fill_logger):
        h = await oco.register_bracket(
            signal=_signal("long"), signal_id="sig-1", fill=_fill()
        )
        fired = await oco.on_tick(symbol="A05603", price=333.20, now_ms=2000)
        assert len(fired) == 1
        assert fired[0].handle_id == h.handle_id
        assert fired[0].state is OCOState.TARGET_HIT
        kwargs = fill_logger.log_fill.call_args.kwargs
        assert kwargs["trade_role"] == "take_profit"
        assert kwargs["filled_price"] == 333.00  # at trigger

    @pytest.mark.asyncio
    async def test_short_target_fires_on_drop(self, oco):
        await oco.register_bracket(
            signal=_signal("short"), signal_id="sig-s", fill=_fill()
        )
        fired = await oco.on_tick(symbol="A05603", price=329.20, now_ms=2000)
        assert len(fired) == 1
        assert fired[0].state is OCOState.TARGET_HIT


class TestStopVsTargetSameTick:
    """Spec §4.2 'loss wins on ties' — stop has priority."""

    @pytest.mark.asyncio
    async def test_loss_wins_on_simultaneous_cross(self, oco):
        await oco.register_bracket(
            signal=_signal("long"), signal_id="sig-1", fill=_fill()
        )
        # If the price drops well below stop and somehow above target in same tick
        # (only possible via a wide range bar), the stop wins.
        # Simulate by sending a price below stop — can't realistically be above target,
        # so we test the rule by sending a price equal to both extremes is impossible.
        # Instead verify: a wide bar represented by a single sub-stop price → STOP_HIT.
        fired = await oco.on_tick(symbol="A05603", price=329.00, now_ms=2000)
        assert fired[0].state is OCOState.STOP_HIT


class TestCancellation:
    @pytest.mark.asyncio
    async def test_cancel_removes_handle(self, oco):
        h = await oco.register_bracket(
            signal=_signal("long"), signal_id="sig-1", fill=_fill()
        )
        assert oco.cancel(h.handle_id) is True
        fired = await oco.on_tick(symbol="A05603", price=329.0, now_ms=2000)
        assert fired == []

    @pytest.mark.asyncio
    async def test_cancel_unknown_returns_false(self, oco):
        assert oco.cancel("OCO-999") is False

    @pytest.mark.asyncio
    async def test_fired_handle_removed_from_active(self, oco):
        await oco.register_bracket(
            signal=_signal("long"), signal_id="sig-1", fill=_fill()
        )
        await oco.on_tick(symbol="A05603", price=329.0, now_ms=2000)
        # Second tick — same handle should not refire
        fired_again = await oco.on_tick(symbol="A05603", price=328.0, now_ms=3000)
        assert fired_again == []


class TestExpiry:
    @pytest.mark.asyncio
    async def test_expired_handle_force_closes(self, oco, fill_logger):
        sig = _signal("long")
        valid_until_ms = int(sig.valid_until.timestamp() * 1000)
        h = await oco.register_bracket(signal=sig, signal_id="sig-1", fill=_fill())

        # Advance time past valid_until
        expired = await oco.check_expiry(now_ms=valid_until_ms + 1)
        assert len(expired) == 1
        assert expired[0].handle_id == h.handle_id
        assert expired[0].state is OCOState.EXPIRED
        kwargs = fill_logger.log_fill.call_args.kwargs
        assert kwargs["trade_role"] == "force_close"
        assert kwargs["order_type"] == "market"

    @pytest.mark.asyncio
    async def test_not_expired_when_in_window(self, oco):
        sig = _signal("long")
        valid_until_ms = int(sig.valid_until.timestamp() * 1000)
        await oco.register_bracket(signal=sig, signal_id="sig-1", fill=_fill())

        expired = await oco.check_expiry(now_ms=valid_until_ms - 1)
        assert expired == []

    @pytest.mark.asyncio
    async def test_expiry_uses_supplied_market_price(self, oco, fill_logger):
        """Daemon supplies real market quote → that price lands in audit row."""
        sig = _signal("long")
        valid_until_ms = int(sig.valid_until.timestamp() * 1000)
        await oco.register_bracket(signal=sig, signal_id="sig-1", fill=_fill())

        await oco.check_expiry(now_ms=valid_until_ms + 1, market_price=331.05)

        log = fill_logger.log_fill.call_args.kwargs
        # NOT the target_price (333.00) — uses the actual market quote.
        assert log["filled_price"] == 331.05

    @pytest.mark.asyncio
    async def test_expiry_falls_back_to_target_price_when_no_market_price(
        self, oco, fill_logger
    ):
        """Harness path with no market_price uses target_price as documented."""
        sig = _signal("long")
        valid_until_ms = int(sig.valid_until.timestamp() * 1000)
        await oco.register_bracket(signal=sig, signal_id="sig-1", fill=_fill())

        await oco.check_expiry(now_ms=valid_until_ms + 1)

        log = fill_logger.log_fill.call_args.kwargs
        assert log["filled_price"] == 333.00


class TestCloseFailureSafety:
    @pytest.mark.asyncio
    async def test_log_fill_failure_does_not_cause_duplicate_on_retick(self, oco):
        """If log_fill raises (CH outage), the handle must NOT re-fire on next tick."""
        # First call raises, second would be the duplicate we're guarding against
        oco.fill_logger.log_fill = AsyncMock(side_effect=RuntimeError("ch down"))
        await oco.register_bracket(
            signal=_signal("long"), signal_id="sig-1", fill=_fill()
        )

        with pytest.raises(RuntimeError):
            await oco.on_tick(symbol="A05603", price=329.0, now_ms=2000)

        # Reset side_effect so a duplicate fire would succeed
        oco.fill_logger.log_fill = AsyncMock()
        # Second tick at an even-lower price — must not refire
        fired = await oco.on_tick(symbol="A05603", price=328.0, now_ms=3000)
        assert fired == []
        oco.fill_logger.log_fill.assert_not_awaited()


class TestPnLRecording:
    @pytest.mark.asyncio
    async def test_entry_price_stored(self, fill_logger):
        oco = PseudoOCO(fill_logger=fill_logger)
        h = await oco.register_bracket(
            signal=_signal("long"), signal_id="s1", fill=_fill()
        )
        assert h.entry_price == 331.20

    @pytest.mark.asyncio
    async def test_long_stop_records_loss(self, fill_logger):
        rs = AsyncMock()
        oco = PseudoOCO(
            fill_logger=fill_logger, runtime_state=rs, multiplier_krw_per_point=50_000
        )
        await oco.register_bracket(signal=_signal("long"), signal_id="s1", fill=_fill())
        # long entry 331.20, stop 330.00 → loss = (330.00-331.20)*1*1*50000 = -60000
        await oco.on_tick(symbol="A05603", price=329.0, now_ms=2000)
        rs.record_trade.assert_awaited_once()
        assert rs.record_trade.await_args.kwargs["pnl_krw"] == pytest.approx(-60_000.0)
        rs.record_loss.assert_awaited_once()
        rs.record_win.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_long_target_records_win(self, fill_logger):
        rs = AsyncMock()
        oco = PseudoOCO(
            fill_logger=fill_logger, runtime_state=rs, multiplier_krw_per_point=50_000
        )
        await oco.register_bracket(signal=_signal("long"), signal_id="s1", fill=_fill())
        # target 333.00 → win = (333.00-331.20)*50000 = +90000
        await oco.on_tick(symbol="A05603", price=334.0, now_ms=2000)
        assert rs.record_trade.await_args.kwargs["pnl_krw"] == pytest.approx(90_000.0)
        rs.record_win.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_short_stop_records_loss(self, fill_logger):
        rs = AsyncMock()
        oco = PseudoOCO(
            fill_logger=fill_logger, runtime_state=rs, multiplier_krw_per_point=50_000
        )
        await oco.register_bracket(
            signal=_signal("short"), signal_id="s1", fill=_fill()
        )
        # short entry 331.20, stop 332.40 → loss = (332.40-331.20)*(-1)*1*50000 = -60000
        await oco.on_tick(symbol="A05603", price=333.0, now_ms=2000)
        assert rs.record_trade.await_args.kwargs["pnl_krw"] == pytest.approx(-60_000.0)
        rs.record_loss.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_runtime_state_records_nothing(self, fill_logger):
        oco = PseudoOCO(fill_logger=fill_logger)  # back-compat: no recording
        await oco.register_bracket(signal=_signal("long"), signal_id="s1", fill=_fill())
        fired = await oco.on_tick(symbol="A05603", price=329.0, now_ms=2000)
        assert len(fired) == 1  # still closes
        fill_logger.log_fill.assert_awaited_once()  # still logs


class TestCloseExecutor:
    @pytest.mark.asyncio
    async def test_live_close_uses_real_fill_price(self, fill_logger):
        from shared.execution.passive_maker import Fill

        executor = AsyncMock()
        executor.flatten.return_value = Fill(
            order_id="EXIT-1", price=329.5, quantity=1, filled_at_ms=2000
        )
        rs = AsyncMock()
        oco = PseudoOCO(
            fill_logger=fill_logger,
            runtime_state=rs,
            multiplier_krw_per_point=50_000,
            close_executor=executor,
        )
        await oco.register_bracket(signal=_signal("long"), signal_id="s1", fill=_fill())
        fired = await oco.on_tick(symbol="A05603", price=329.0, now_ms=2000)
        assert len(fired) == 1
        executor.flatten.assert_awaited_once()
        assert executor.flatten.await_args.kwargs["side"] == "short"  # flatten a long
        # logged + PnL use the REAL fill price 329.5, not the stop 330.00
        assert fill_logger.log_fill.await_args.kwargs["filled_price"] == 329.5
        assert rs.record_trade.await_args.kwargs["pnl_krw"] == pytest.approx(
            (329.5 - 331.20) * 50_000
        )

    @pytest.mark.asyncio
    async def test_live_close_blocked_keeps_handle_active(self, fill_logger):
        executor = AsyncMock()
        executor.flatten.return_value = None  # guard-blocked / unfilled
        oco = PseudoOCO(fill_logger=fill_logger, close_executor=executor)
        h = await oco.register_bracket(
            signal=_signal("long"), signal_id="s1", fill=_fill()
        )
        fired = await oco.on_tick(symbol="A05603", price=329.0, now_ms=2000)
        assert fired == []  # not closed
        assert h.state is OCOState.ACTIVE  # stays active for retry
        fill_logger.log_fill.assert_not_awaited()
        assert len(oco.active_handles) == 1
