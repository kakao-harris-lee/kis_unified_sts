"""Tests for shared/paper/oco_broker_shim.py — Phase 4 Task 6."""

import pytest

from shared.paper.oco_broker_shim import OCOBrokerShim, StopOrder


@pytest.fixture
def shim():
    return OCOBrokerShim()


class TestPlaceStop:
    def test_returns_handle_with_id(self, shim):
        h = shim.place_stop_order(
            symbol="A05603", side="short", quantity=1, trigger_price=330.0
        )
        assert isinstance(h, StopOrder)
        assert h.id.startswith("STOP-")
        assert h.symbol == "A05603"
        assert h.trigger_price == 330.0

    def test_unique_ids(self, shim):
        h1 = shim.place_stop_order(
            symbol="A", side="short", quantity=1, trigger_price=1.0
        )
        h2 = shim.place_stop_order(
            symbol="A", side="short", quantity=1, trigger_price=2.0
        )
        assert h1.id != h2.id


class TestStopFiring:
    def test_no_fire_when_price_above_long_stop(self, shim):
        # long position → SELL stop at 330; price 331 → no fire
        shim.place_stop_order(
            symbol="A05603", side="short", quantity=1, trigger_price=330.0
        )
        fired = shim.on_tick("A05603", 331.0)
        assert fired == []

    def test_fires_when_price_crosses_long_stop(self, shim):
        # long position → SELL stop at 330; price drops to 329.9 → fire
        h = shim.place_stop_order(
            symbol="A05603", side="short", quantity=1, trigger_price=330.0
        )
        fired = shim.on_tick("A05603", 329.9)
        assert len(fired) == 1
        assert fired[0].id == h.id

    def test_fires_when_price_equals_long_stop(self, shim):
        # boundary — exact touch should trigger
        shim.place_stop_order(
            symbol="A05603", side="short", quantity=1, trigger_price=330.0
        )
        fired = shim.on_tick("A05603", 330.0)
        assert len(fired) == 1

    def test_no_fire_when_price_below_short_stop(self, shim):
        # short position → BUY stop at 332; price 331 → no fire
        shim.place_stop_order(
            symbol="A05603", side="long", quantity=1, trigger_price=332.0
        )
        fired = shim.on_tick("A05603", 331.0)
        assert fired == []

    def test_fires_when_price_crosses_short_stop(self, shim):
        # short position → BUY stop at 332; price rises to 332.1 → fire
        h = shim.place_stop_order(
            symbol="A05603", side="long", quantity=1, trigger_price=332.0
        )
        fired = shim.on_tick("A05603", 332.1)
        assert len(fired) == 1
        assert fired[0].id == h.id

    def test_fired_stops_removed_from_pending(self, shim):
        shim.place_stop_order(
            symbol="A05603", side="short", quantity=1, trigger_price=330.0
        )
        shim.on_tick("A05603", 329.0)
        # Second tick should not re-fire
        fired_again = shim.on_tick("A05603", 328.0)
        assert fired_again == []

    def test_unrelated_symbol_does_not_fire(self, shim):
        shim.place_stop_order(
            symbol="A05603", side="short", quantity=1, trigger_price=330.0
        )
        fired = shim.on_tick("DIFFERENT", 100.0)
        assert fired == []

    def test_only_triggered_orders_fire(self, shim):
        # Two stops, only one should fire
        h_low = shim.place_stop_order(
            symbol="A05603", side="short", quantity=1, trigger_price=330.0
        )
        h_lower = shim.place_stop_order(
            symbol="A05603", side="short", quantity=1, trigger_price=325.0
        )
        fired = shim.on_tick("A05603", 329.0)  # crosses 330 only
        assert len(fired) == 1
        assert fired[0].id == h_low.id
        # Second stop still pending
        fired2 = shim.on_tick("A05603", 324.0)
        assert len(fired2) == 1
        assert fired2[0].id == h_lower.id


class TestCancel:
    def test_cancel_removes_stop(self, shim):
        h = shim.place_stop_order(
            symbol="A05603", side="short", quantity=1, trigger_price=330.0
        )
        assert shim.cancel_stop(h.id) is True
        # Should not fire after cancel
        fired = shim.on_tick("A05603", 329.0)
        assert fired == []

    def test_cancel_unknown_id_returns_false(self, shim):
        assert shim.cancel_stop("STOP-999") is False

    def test_cancel_idempotent(self, shim):
        h = shim.place_stop_order(
            symbol="A05603", side="short", quantity=1, trigger_price=330.0
        )
        assert shim.cancel_stop(h.id) is True
        assert shim.cancel_stop(h.id) is False


class TestQuery:
    def test_pending_for_symbol(self, shim):
        h = shim.place_stop_order(
            symbol="A05603", side="short", quantity=1, trigger_price=330.0
        )
        pending = shim.pending_for("A05603")
        assert len(pending) == 1
        assert pending[0].id == h.id

    def test_pending_for_unknown_symbol(self, shim):
        assert shim.pending_for("UNKNOWN") == []

    def test_pending_count_decreases_after_fire(self, shim):
        shim.place_stop_order(
            symbol="A05603", side="short", quantity=1, trigger_price=330.0
        )
        assert len(shim.pending_for("A05603")) == 1
        shim.on_tick("A05603", 329.0)
        assert len(shim.pending_for("A05603")) == 0
