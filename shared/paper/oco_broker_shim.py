"""Stop-order simulation shim for paper trading.

Phase 4 Task 6 — :class:`shared.paper.broker.VirtualBroker` only handles
single market/limit orders, so we cannot simulate brackets natively. This
shim tracks pending stop orders in memory and fires them when the
:meth:`on_tick` method observes a crossing price.

The shim is intentionally storage-only — it returns the list of triggered
:class:`StopOrder` objects on each tick and lets the caller (Pseudo-OCO
watcher in Task 7) drive the actual broker market-close. Keeping fill
mechanics out of this module avoids tangling with VirtualBroker's
position/PnL accounting.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StopOrder:
    id: str
    symbol: str
    side: str  # closing direction: "short" closes long, "long" closes short
    quantity: int
    trigger_price: float


def _is_triggered(order: StopOrder, price: float) -> bool:
    if order.side == "short":
        return price <= order.trigger_price
    return price >= order.trigger_price


class OCOBrokerShim:
    """Track pending stops; fire on crossing tick.

    Long position closes via a SELL stop (``side="short"``), triggers when
    market trades at or below ``trigger_price``. Short position closes via a
    BUY stop (``side="long"``), triggers at or above.
    """

    def __init__(self) -> None:
        self._pending: dict[str, list[StopOrder]] = {}
        self._next_id: int = 1

    def place_stop_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: int,
        trigger_price: float,
    ) -> StopOrder:
        order = StopOrder(
            id=f"STOP-{self._next_id}",
            symbol=symbol,
            side=side,
            quantity=quantity,
            trigger_price=trigger_price,
        )
        self._next_id += 1
        self._pending.setdefault(symbol, []).append(order)
        return order

    def cancel_stop(self, order_id: str) -> bool:
        for symbol, orders in self._pending.items():
            for o in orders:
                if o.id == order_id:
                    orders.remove(o)
                    if not orders:
                        del self._pending[symbol]
                    return True
        return False

    def on_tick(self, symbol: str, price: float) -> list[StopOrder]:
        orders = self._pending.get(symbol)
        if not orders:
            return []
        fired: list[StopOrder] = []
        remaining: list[StopOrder] = []
        for order in orders:
            if _is_triggered(order, price):
                fired.append(order)
            else:
                remaining.append(order)
        if remaining:
            self._pending[symbol] = remaining
        else:
            del self._pending[symbol]
        return fired

    def pending_for(self, symbol: str) -> list[StopOrder]:
        return list(self._pending.get(symbol, ()))
